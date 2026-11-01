# 27 · frida 在 Houdini 下逆向 IL2CPP 的方法与能力边界

> 目标：在雷电模拟器（Intel Houdini 翻译层）里，定位 v5.5.7 的 `GameGUI` 单例与宠物 UI 引用，
> 判断「宠物 UI 无入口」到底是**场景没挂**还是**挂了但引用失效**。
>
> 结论先说：**这一问能答**（`ChongWuUIManager_New` 从未实例化），
> 但「通过 frida 强行调起来」**答不了**——Houdini 下 frida 不能执行 ARM 代码。
> 下面把能做的和不能做的都钉死，附可复现的命令。

---

## 一、为什么传统路子在这台机器上全废

| 路子 | 结果 |
|---|---|
| `Process.enumerateModules()` 找 `libil2cpp.so` | **不存在**。200 个模块里只有 x86 侧的 `libnb.so` / `libhoudini.so` / `libtcb.so` |
| 静态反查 `Il2CppCodeRegistration.methodPointers` | `int32 == 31519`（methods 条数）在整个 .so **零命中**；`.data.rel.ro` 里最长连续指针段只有 15098 项 → **Stripping 构建** |
| 按 `[r0,#0x60]` + `mov r1,#1` + `b/bl` 做字节特征搜 `OpenChongWuUI` | **0 命中**。单独看 `[rN,#0x60]` 有 14200 处，`0x5c` 有 19139 处，偏移完全无判别力 |
| 扫 GC 堆找带类名的字符串反推对象 | 命中的全是 **IL2CPP 字段名索引表**（每条 16 字节、字典序、第三列恒为 `0x49`），不是托管对象 |
| `Interceptor.attach` 到 ARM 段 | **字节一个没变，hits 恒 0**（见第四节） |

`libil2cpp.so` 是 ARM 库，被 Houdini 当**数据**读入、翻译后放进 code cache 执行，
所以它不出现在模块表里，但**它的内存映射照常存在**——这是本法的立足点：

```
05014000-0618d000 r--p 00000000  /data/app/.../lib/arm/libil2cpp.so   ← ①代码
0618e000-061c9000 r--p 01179000  /data/app/.../lib/arm/libil2cpp.so   ← ②只读数据
061c9000-06240000 rw-p 011b4000  /data/app/.../lib/arm/libil2cpp.so   ← ③可写数据
06240000-062c0000 rw-p 00000000  [anon:dalvik-...]                    ← ④bss 扩展
cd7f1000-cdb6xxxx r--p ...       /data/app/.../files/global-metadata.dat  ← ⑤元数据
```

映射基址随进程重启而变（ASLR），**不要硬编码**，每次从 `/proc/<pid>/maps` 重新取，
或用 `Process.findRangeByAddress()` 现查。

---

## 二、立足点：一个 `ldr r0,[r0,#0x5c]; bx lr` 给出的偏移

`il2cpp_class_get_static_field_data` 在 v557 的 PLT 桩解析后指向 `0x001fe730`，它的机器码只有两条：

```
0x001fe730: e590005c   ldr  r0, [r0, #0x5c]
0x001fe734: e12fff1e   bx   lr
```

即 **`Il2CppClass + 0x5c == static_fields 指针`**。这是整个定位链的钥匙：
拿到 `Il2CppClass` 就能拿静态字段，不用碰任何代码。

顺带确认了构造：`Il2CppClass` 的

| 偏移 | 含义 | 本项目的实测值（`GameGUI`） |
|---|---|---|
| `+0x00` | `image` | `0xcd74b840`（有效指针） |
| `+0x04` | `gc_desc` | `0`（非托管类就是 0） |
| `+0x08` | `name`（`char*`） | `0xcd8b8380` → `"GameGUI"` |
| `+0x0c` | `namesp` | `0xcd838a09` |
| `+0x5c` | `static_fields` | `0xebb02628` |

---

## 三、通用定位法：拿类名字符串当锚点反查 `Il2CppClass`

代码数据都翻不出来，但**类名字符串一定在**——它躺在 `global-metadata.dat` 的映射里，
而那个文件是**明文**的（`files/old/global-metadata_v557.dat`，3,728,272 字节）。
于是：

### 三步

1. **在 metadata 映射里扫 `"<类名>\0"`**
   ```js
   Memory.scanSync(metaRange.base, metaRange.size, '47 61 6d 65 47 55 49 00')  // "GameGUI\0"
   ```
2. **全内存搜「值等于该字符串地址」的 4 字节指针**
   ```js
   var pat = nameAddr.toMatchPattern();
   // 命中处 at 减 8 就是 Il2CppClass 的起始（name 在 +0x08）
   ```
3. **验证** `Il2CppClass`：`+0x00` 非 0、`+0x08` 必须指回那个类名字符串

### 实测（`GameGUI`）

扫出 2 个命中，**只有 1 个是真的**：

| 命中 | `+0x00` image | `+0x08` name | 判定 |
|---|---|---|---|
| `0xc5d68fb0` | **`0`** | 指回 `"GameGUI"` | ❌ 干扰：某个结构里恰好也存了这个指针 |
| **`0xc5d6c700`** | `0xcd74b840` | 指回 `"GameGUI"` | ✅ **真 `Il2CppClass`** |

**判据是 `+0x00` 非零**。只看「`+0x08` 是不是类名字符串」会挑到假货。

### 四个类的实测结果

| 类 | `Il2CppClass` | `static_fields` | 实例 |
|---|---|---|---|
| `GameGUI` | `0xc5d6c700` | `0xebb02628` | `sf[0] = 0xc7636c98` ✅ |
| `ChongWuPool` | `0xc5ea54a0` | `0xebb02d68` | `sf[0] = 0xc5fa9f80` ✅ |
| `ChongWuUIManager_New` | `0xc5f5dd60` | `0xebb02668` | **无** ❌ |
| `ChongWuUI` | `0xc5d6d420` | `0` | **无** ❌ |

判实例的方法：`static_fields[i]` 非零 → 读该对象的 `+0x00`，若等于本类的 `Il2CppClass`
地址就是它的实例。`GameGUI` 与 `ChongWuPool` 的唯一一个非零槽都精确命中自己。

工具已经固化进仓库：

```bash
python scripts/il2cpp_class_locator.py GameGUI ChongWuPool --fields 12
```

---

## 四、能力边界（这是本文最重要的部分）

在雷电 + Houdini 下，frida 对 ARM 侧的能力实测如下：

| 能力 | 结果 | 证据 |
|---|---|---|
| **读 ARM 段内存** | ✅ 可以 | `0x061c9000 rw-p` 读 487,424 字节成功；`0xcd8b8380` 读回 `"GameGUI"` |
| **改段权限** | ✅ 可以 | `Memory.protect(0x05014000, 0x1000, 'rwx')` 返回 `true`，复查 `r-x → rwx`，**游戏存活** |
| **往 ARM 段写指令** | ✅ 可以 | 在 `0x0618cf00` 写入 `e1a00000 ×3 + e12fff1e`，读回 `00 00 a0 e1 00 00 a0 e1 00 00 a0 e1 1e ff 2f e1` 完全正确，还原后未崩溃 |
| **`Interceptor.attach` ARM 函数** | ❌ **无效** | 对 `BASE+0x002b8b50` attach：`attached=true`，但前后字节**完全相同**，`hits=0` |
| **调用 ARM 函数** | ❌ **无桥** | `libhoudini.so` 的 62 个导出全是 `NativeBridgeItf` 和 `android_*`，没有 x86→ARM 调用入口 |

### 为什么 attach 不报错却不生效

`Interceptor.attach` 返回 `true` 只说明 frida **登记**了这个地址，它会尝试在目标指令处
写跳转。但 Houdini 执行的是**已翻译成 x86 的 code cache**，ARM 段的原始指令根本不参与执行，
所以改它等于改一份没人读的副本。**没有报错，因为内存写入确实成功了——只是没人看。**

### 结论

> **能看数据，不能动代码。**

凡是「改内存里的值就能达成」的目标都可行；凡是「必须让某个方法跑起来」的目标，
在这台机器上没有客户端解法。宠物 UI 恰好属于后者。

---

## 五、用这套方法确认的宠物 UI 结论

四条证据，逐条独立：

### 5.1 场景 UI 遍历：无入口
九个位置点遍，全部无关：主界面 5 个 tab、装备页（4 阶×4 格 + 6 职业）、角色面板 5 个标签、
战斗内 4 个 tab、「图鉴」tab（打开的是**怪物**图鉴 1/61）、家园 5 个标签（派遣点击无反应）、
地图白色光点（`ShuaChongWuDian` 的 `caoCong` 草丛）、新手指南 24 页（下一页点不动）。
`uiautomator dump` 只有 `unitySurfaceView`，Unity 自绘无层级可查。

### 5.2 资源层：prefab 在，但没被挂载
`files/old/djmw_5.5.7.apk` → `assets/bin/Data/data.unity3d`（24,486,488 B，`UnityFS`）里
`ChongWuUI` 出现 2 次、`ChongWuUIManager` 1 次、`ChongWu` 47 次：

```
0x0b9266d  "...\x00ChongWuUI\xdf O_New\xe3 ...CloseUI..."
0x10b8e4d  "...\x00ChongWuUIManager_New, Assembly-CSharp..."
```

### 5.3 运行时：UI 管理器**从未实例化**（本段新增，最硬的一条）
`ChongWuUIManager_New` 的 16 个静态字段里，**没有任何一项的 `+0x00` 等于它自己的
`Il2CppClass`（`0xc5f5dd60`）** → `Instance == null`。
`ChongWuUI` 的 `static_fields` 直接是 `0`（没有静态字段）。

也就是说：不是「打开了但没渲染」，而是**这个版本的场景里根本没有创建过它**。

### 5.4 `GameGUI.ChongWuUIGO` 的指向
`GameGUI.instance = 0xc7636c98`，`ChongWuUIGO`（字段 22，偏移 `0x60`）= `0xbf141030`，
其 `+0x00 = 0xece1d320`，读回类名 `"GameObject"` —— **类型对，是一个 GameObject 引用**。

> **记录一个弯路（别重走）**：我一度把 `托管对象 +0x08 == 0` 当成「`m_CachedPtr == 0`
> 即对象已销毁」的证据。**这个判据是错的**——对 `GameGUI` 子类来说 `+0x08` 是它自己的
> 第一个字段（`gameManager`，本来就该是 0）；`UnityEngine.Object` 的
> `m_InstanceID` / `m_CachedPtr` 落在 `+0x0c` / `+0x10`。
> 实测 `ChongWuUIGO` 的 `+0x0c = 0x00460032`、`+0x10 = 0xece56600`，都合理，
> **不能据此断定它已销毁**。

所以 5.4 只能说「引用存在、类型正确」，不能证明它活着或死掉。
真正定性的是 5.3 —— 管理器没有实例，UI 无从显示。

### 5.5 想调起来，缺什么
`GameGUI.OpenChongWuUI()`（`tok=0x060005a9`，public，**无参**，典型
`Button.onClick` 绑定）地址拿不到（Stripping），即便拿到也**调不动**（第四节）。
唯一可行的是改内存数据，但「让 UI 出现」不是数据能解决的事。

---

## 六、复现步骤

```bash
# 1. 起 frida-server（设备需 root）
su 0 /data/local/tmp/frida-server -D &
adb forward tcp:27042 tcp:27042

# 2. 拿最新 pid（★ 不要用记下来的旧 pid）
adb shell "ps -A | grep TopDemons"

# 3. 定位类
python scripts/il2cpp_class_locator.py GameGUI ChongWuPool ChongWuUIManager_New --fields 12

# 4. 验证 ARM 写能力（可选）
python E:\DSH\game\frida_protect.py     # 改段权限
python E:\DSH\game\frida_write.py       # 写 ARM 指令并读回

# 5. 验证 Interceptor 无效（可选，铁证）
python E:\DSH\game\frida_verify_hook.py # 期望：字节不变、hits=0
```

---

## 七、踩坑清单

| 坑 | 正解 |
|---|---|
| `dev.enumerate_processes()` 看不到游戏 | **pid 变了**。先用 `adb shell ps -A` 取最新 pid 再 `attach`，别急着判定 frida 不可用 |
| `attach` 报 `ProcessNotFoundError` | 同上，pid 已死 |
| 直接 `add_remote_device('127.0.0.1:27042')` 连不上 | **必须先 `adb forward tcp:27042 tcp:27042`** |
| `ptr.readByteArray(n)` 报 `not a function` | 用 `Memory.readByteArray(p, n)` 或 `p.readByteArray(n)`（frida 17 的 NativePointer 才有） |
| `hex()` 不存在 | frida 17 里没有全局 `hex()`，用 `ptr.toString()` |
| `cands[d].sub(a).abs()` 报 `TypeError: not a function` | **frida 17 的 `NativePointer` 没有 `abs()`**，用 `a.compare(b)` 分情况 `sub` 再 `toUInt32()` |
| `Memory.scanSync` 的命中地址 | `res[k].address` **已经是绝对地址**，不要再 `r.base.add(...)`（会全错） |
| 类名字符串命中 2 个，挑错 | 只认 `+0x00`（image）非零的那个 |
| 用 `+0x08 == 0` 判 GameObject 死活 | **错的**。见 §5.4，`m_InstanceID`/`m_CachedPtr` 在 `+0x0c`/`+0x10` |
| `Memory.protect` 后忘了还原 | 写完要还原成原权限，否则可能影响后续执行 |

---

## 八、对项目路线的影响

| 之前 | 现在 |
|---|---|
| HANDOVER「想看到宠物界面只能 frida 强行调用」 | **frida 强行调用在 Houdini 下不可行**，这条路要划掉 |
| 剩「换 v5.9.2」 | 仍然成立，但那是另一条线（TapTap 版，卡登录） |
| 数据层可控性 | `ChongWuPool` 实例存活、`GameGUI.instance` 可定位 —— **数据层完全可控**，只是没有 UI 观察窗口 |

宠物加成的效果已经用**战斗力数值**验证过了（`IsXieDai=1` 使武器栏 1 → 3.60 万，总战力 7.20 万），
见 [docs/26](26-v557宠物系统实测-UI无入口数据层可控.md)。**没有 UI 截图不影响这个结论的效力。**
