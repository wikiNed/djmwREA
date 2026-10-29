# 17 — 防沉迷 / 实名认证：dex 层的完整判定链

> 目标（docs/14 §七 第 3 条）：反编译 dex，看 `AntiAddictionCore` 是否有客户端绕过点。
> 结论先说：**这个游戏没有自己的 `AntiAddictionCore`。防沉迷、实名、未成年人限时全部由 TapTap 官方 SDK `com.taptap.sdk.compliance` 托管，纯客户端绕过点在理论上存在（改 4 个静态布尔），但实际上会被服务端 `checkPlay` 的返回值反复覆盖，而且它和本项目真正关心的「封号清档」是两套独立机制。**

---

## 一、先纠正一个前提：`AntiAddictionCore` 不存在

`docs/14` 里写的 `AntiAddictionCore` 是推测名。实际扫 3 个 dex 的结果：

| dex | 大小 | `AntiAddiction` 出现 | `taptap` 类数 |
|---|---|---|---|
| `classes.dex` | 7,751,488 | 0 | 0 |
| `classes2.dex` | 7,474,188 | 0 | 0 |
| `classes3.dex` | 9,898,792 | 1 处（7845761，是字符串池） | **1515** |

- `fangchenmi` / `FangChenMi` / `healthedu` 全部零命中 —— 没有国产常见的那套自建防沉迷。
- `Compliance` 三个 dex 都有，但只有 `classes3.dex` 里的那 239 个类属于 `com.taptap.sdk.compliance`，其余是广告 SDK 的同名词噪音。
- **`com/unity3d/player` 只有 165 个类**（标准 Unity 运行时），游戏逻辑全在 IL2CPP 的 `libil2cpp.so` 里，dex 层不含游戏业务。

结论：本地 dex 里**唯一**的防沉迷实现就是 TapTap SDK。

---

## 二、核心状态机 `TapComplianceInternal`

`Lcom/taptap/sdk/compliance/internal/TapComplianceInternal;`
- `access_flags = 0x0011` (PUBLIC FINAL)，`super = Ljava/lang/Object;`
- `source file = TapComplianceInternal.kt`（Kotlin 单例）
- 静态字段 17 个、实例字段 0 个、直接方法 50 个（含 22 个 `access$xxx` 合成桥）、虚方法 23 个

### 2.1 决定「能不能玩」的静态布尔

| # | 字段 | 类型 | 访问 | 作用 |
|---|---|---|---|---|
| 2 | `canPlay` | `Z` | PRIVATE STATIC | **是否允许进入游戏** |
| 9 | `isManuallyVerify` | `Z` | PRIVATE STATIC | 是否走人工实名 |
| 11 | `noticeGameCanPlay` | `Z` | PRIVATE STATIC | 是否已通知过「可以玩」 |
| 16 | `withUserAgeInfo` | `Z` | PRIVATE STATIC | 请求是否带年龄信息（`<clinit>` 置 `true`） |
| 10 | `isRunning` | `Z` | PRIVATE STATIC **VOLATILE** | 状态机是否已启动 |
| 8 | `isFirstUseTapRealName` | `Z` | PRIVATE STATIC | 首次使用 Tap 实名 |
| 5 | `currentRemindType` | `I` | PRIVATE STATIC | 提示类型（`<clinit>` 置 `-1`） |
| 6 | `currentSessionId` | `String` | PRIVATE STATIC | 本次会话 id |
| 13 | `regionType` | `RegionType` | PRIVATE STATIC | 地区（`<clinit>` 置 `CN`） |
| 15 | `userId` / 3 `clientId` | `String` | PRIVATE STATIC | 账号 / 应用标识 |

`<clinit>` 里没有任何一个布尔被初始化为 `true`（只置 `withUserAgeInfo=true`、`currentRemindType=-1`、`regionType=CN`、`userId=""`、`clientId=""`），说明 `canPlay` 默认 `false`，**必须由服务器回调把它翻成 `true`**。

### 2.2 `isAdult()` —— 唯一的数据来源是 `UserModel`

```
38e538: isAdult:()Z
 0000: sget-object v0, Lcom/taptap/sdk/compliance/model/UserModel;.INSTANCE
 0002: invoke-virtual {v0}, UserModel.getCurrentUser:()Lcom/taptap/sdk/compliance/bean/UserInfo;
 0005: move-result-object v0
 0006: const/4 v1, #int 0
 0007: if-eqz v0, 0011        ; null -> 返回 false
 0009: invoke-virtual {v0}, UserInfo.isAdult:()Z
 0011: return v1
```

注意 `getCurrentUser()` 是**判空就返回 false**。`UserInfo` 不是从本地存档来的，而是 `UserModel` 在登录回调里从服务器响应构造的。

### 2.3 `checkPlayable()` —— 只是个转发

```
38eaf4: checkPlayable:(Lcom/taptap/sdk/kit/internal/callback/TapTapCallback;)V
 0000: sget-object v0, Lcom/taptap/sdk/compliance/model/PlayLogModel;.INSTANCE
 0002: new-instance v1, TapComplianceInternal$checkPlayable$1
 0004: invoke-direct {v1, v3}            ; 把 callback 包进协程
 0009: invoke-virtual {v0, v1}, PlayLogModel.checkUserState:(Lcom/taptap/sdk/kit/internal/callback/TapTapCallback;)V
 000c: return-void
```

**判断逻辑完全不在这个方法里**，实际判定在 `PlayLogModel.checkUserState`（内部再调 `IdentityVerifyApi.checkPlay`，`POST` 到服务器）。

### 2.4 `handleUnlimitedAge()` —— 「无限时长」也照样拦

```
38ee64: handleUnlimitedAge:(Lcom/taptap/sdk/compliance/bean/CheckPlayResult;)V
 0011: const/4 v0, #int 2
 0012: const/16 v2, #int 500           ; 消息码 500
 0015: if-eqz v1, 001b                ; isAdult() == false -> 走 500
 001b: CheckPlayResult.getRemainTime()
 001f: if-gtz v1, 0039                ; remainTime <= 0 -> 走 1095
 002f: TapComplianceSettings.generateAlertMessage(int,String,String)
 0033: const/16 v0, #int 1030         ; 消息码 1030
```

三档语义：`500` = 未成人未实名、`1030` = 有剩余时长提示、`1095` = 时长耗尽。**都是通过 `notifyMessageInternal` 推给游戏侧**，游戏只是被动接收。

### 2.5 `checkUserIdentification()` —— 三条分支

```
38eb20: checkUserIdentification:(Landroid/app/Activity;)V
 0002: TapComplianceSettings.getCachedAccessTokenV2()
 000d: if-lez v0, 0011                ; token 长度 > 0
 0026: new-instance IdentityVerifyState
 0028: const-string v2, "pass"        ; ★ 状态直接写 "pass"
 002b: const/4 v5, #int 4             ; 第 4 个参数 = 4
 0031: handleVerifyResult(Activity, IdentityVerifyState)
 0035: TapLoginModel.checkAccessTokenLocally(null)
 0040: "has local oauth access token" -> verifyWithTapToken()
 0049: "no local access token, fetch from server" -> verifyFromServer()
```

**这里有本地短路**：只要 `TapComplianceSettings.getCachedAccessTokenV2()` 非空，就直接构造一个 `status="pass"` 的 `IdentityVerifyState` 交给 `handleVerifyResult`，根本不问服务器。这个 token 存在 `SharedPreferences`（`SP_KEY_USER_ACCESS_TOKEN_V2`）。

---

## 三、客户端绕过点评估

### 3.1 技术上可行的三个口子

| 口子 | 位置 | 做法 | 可靠性 |
|---|---|---|---|
| A | `TapComplianceInternal.canPlay`（静态布尔 `Z`） | 直接改成 `true` | **低** —— 每次 `checkPlayable` 回调都会重写 |
| B | `TapComplianceSettings` 的 `SP_KEY_USER_ACCESS_TOKEN_V2` | 塞一个非空串，让 `checkUserIdentification` 走 `"pass"` 短路 | **中** —— 但 `PlayLogModel.checkUserState` 仍会查服务器 |
| C | `UserInfo.isAdult()` 返回值 | hook 成恒 `true`（需 frida，xposed） | **中** —— 只影响 `handleUnlimitedAge` 的分支，不改 `remainTime` |

前两个都是纯「改文件 + 重打包」，不涉及内存 hook。

### 3.2 为什么说绕不过去

1. **`canPlay` 是被写入方**：真正的判定在 `PlayLogModel.checkUserState` → `IdentityVerifyApi.checkPlay` → 服务器。客户端每次回到前台都会重查。
2. **时长由服务器下发**：`CheckPlayResult.getRemainTime()` 是响应体字段，本地没有任何"累计时长"的自增逻辑（`TimingModel` 只有心跳上报 `sendGameTimeToServerSync`）。
3. **重打包代价**：Unity 的 `libil2cpp.so` 有完整性校验链路，改 dex 需要重签名，且这是 TapTap 渠道包，TapTap SDK 初始化本身会校验渠道签名。
4. **A/B/C 三个口子都改不到真正关心的东西** —— 见下节。

---

## 四、关键澄清：防沉迷 ≠ 封号清档

这是本项目最容易被混淆的地方，必须写清：

| | 防沉迷 / 实名 | 封号清档 |
|---|---|---|
| 实现层 | **dex**（TapTap SDK，Kotlin） | **IL2CPP**（`libil2cpp.so`，C#） |
| 触发点 | `TapComplianceInternal.checkPlayable` | `ChuangJianPlayer.DengLuChengGong()` → `XianShiNiCheng.HeiMingDan()` |
| 服务端 | `TapTap`（`checkPlay` 接口） | **`http://www.hqgames2013.com/heiMingDan.asp`** |
| 后果 | 弹窗提示、限制时长 | `ShuJuDate.Init()` / `SaveManager.Clear()` / `PlayerPrefs.DeleteAll()` |
| 客户端能否绕过 | 理论上可改静态布尔，实际会被覆盖 | **不能**，收尾无条件执行（docs/14 §二） |

也就是说：**即便把防沉迷完全绕过，封号清档照样会执行**。docs/14 里的 `heiMingDan` 链路才是存档丢失的真正原因，跟 TapTap 的这个 SDK 无关。

---

## 五、工具链与复现

dex 解析这次踩了大坑，记录下来。

### 5.1 `E:\DSH\game\dex_scan.py` 的 `class_data_item` 实现是错的

自写的 DEX 解析器在 `classes.dex` 上「验证通过」是**假象**：它把 `La/a/a/a;` 解析成 `getAAID/getAAID/loadIcon/getLongVersionCode`，而真实是 `getAAID/getOAID/getVAID/isSupported`。全量自检：

```
ok 1473  bad 5477      # classes.dex 7251 个类，79% 解析越界
```

根因没查出来（按规范应是 `(diff uleb128, access uleb128)` 交替、每组从 0 累加，试过仍不对）。**教训：不要用「解析不抛异常」当验证，要用已知正确的成员列表做交叉。**

### 5.2 改用设备自带的 `dexdump`（已验证可靠）

雷电模拟器-2（`emulator-5558`）的 `/system/bin/dexdump` 可用：

```sh
adb -s emulator-5558 push files/TapDemons_v5.9.2.apk /data/local/tmp/t.apk
adb -s emulator-5558 shell 'su 0 mkdir -p /data/local/tmp/dex; su 0 unzip -o -q /data/local/tmp/t.apk "classes*.dex" -d /data/local/tmp/dex'
adb -s emulator-5558 shell 'su 0 dexdump -d /data/local/tmp/dex/classes3.dex > /data/local/tmp/d3.txt'
# 1,890,580 行
```

查类：
```sh
grep -n "Class descriptor  : .Lcom/taptap/sdk/compliance/internal/TapComplianceInternal;'" /data/local/tmp/d3.txt
# 562435
```

**坑**：
- `unzip` 在设备上报 `unzip: invalid zip magic 00001FF8`，但文件其实解出来了 —— APK 用了 zip64/新压缩，busybox unzip 认不全但能过。
- `su 0 grep '...' file` 会被 `su` 的参数解析吃掉引号，报 `can't execute: Permission denied`。**正确做法：把命令写成 `.sh` 文件 `adb push` 上去再 `sh /data/local/tmp/x.sh`**。
- `sed -n 'A,Bp'` 同样要落在脚本里，否则引号被 PowerShell 吞。

---

## 六、一句话总结

游戏的防沉迷是 **TapTap 官方 SDK** 托管（`com.taptap.sdk.compliance`，239 个类，全在 `classes3.dex`），核心状态是 `TapComplianceInternal` 的 `canPlay` 静态布尔与 `PlayLogModel.checkUserState` 的服务器返回值；客户端存在「改静态布尔」「伪造 cached token」两个理论绕法，但都会被下次 `checkPlay` 覆盖，且**与本项目真正要解决的封号清档完全无关**——后者在 IL2CPP 层，收尾无条件执行。
