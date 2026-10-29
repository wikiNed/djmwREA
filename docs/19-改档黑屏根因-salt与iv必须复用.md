# 19 - 改档黑屏的根因：salt/iv 必须复用原档

> 状态：已定位、已修复、已上机验证
> 日期：2026-10-29 / 2026-10-30
> 设备：雷电模拟器-2（`emulator-5558`，V1938T，Android 9 / API 28，x86_64）
> 游戏：点击魔王 TapDemons v5.9.2（`game.taptap.HQGAMES.TapDemons`，加载 `lib/arm/libil2cpp.so`）

## 一、现象

把改过的存档推上设备后，游戏**能过启动画面，然后永久黑屏**：

- 进程活着（`ps -A` 能看到）
- 前台 Activity 正常（`mResumedActivity = .../UnityPlayerActivity`）
- SurfaceFlinger 认为已经画过（`Surface: shown=true`，`mDrawState=HAS_DRAWN`，720x1280）
- 截图是纯黑（26996 字节，多次 `screencap` 的 sha256 完全相同）

同时 logcat 出现：

```
E Unity: FormatException: Cannot load from file because the data in it
         is not JSON data, or the data is encrypted.
  at ES3Internal.ES3JSONReader..ctor (System.IO.Stream, ES3Settings, Boolean)
  at ES3Reader.Create (ES3Settings settings)
  at ES3.KeyExists (System.String key, ES3Settings settings)
  at LanguageDataManager.Load ()
  at ChuangJianPlayer.Start ()
```

`MoShiKuManager.PaiQianIsOver () ← MoShiKuManager.Start ()` 有同样的异常。

**容易误判的两个点：**

1. 黑屏不是渲染管线坏了。`screencap` 抓桌面（`input keyevent KEYCODE_HOME`）出的是正常的 1920x1080 画面。EGL 也正常（`eglMakeCurrent: ... ver 3 1`）。
2. 黑屏不是「存档太大」。`playerDate_03.json`（104886 B）能复现，但**只改一个数字、字节数完全不变**也一样复现。

## 二、根因

`ES3` 的 AES 外层**用文件自己的前 32 字节当参数**：前 16 字节是 salt（PBKDF2 的盐），接下来 16 字节是 IV。

```
key = PBKDF2-HMAC-SHA1(password="hqgames@2013", salt=file[0:16], iterations=100, dkLen=16)
pt  = AES-128-CBC-decrypt(key, iv=file[16:32], ct=file[32:])
```

改档时如果用**新的随机 salt/iv** 重新加密，游戏侧 `ES3.KeyExists()` 会抛 `FormatException`，`LanguageDataManager.Load()` 中断，`ChuangJianPlayer.Start()` 整个协程链被打断 —— 表现就是启动画面之后黑屏。

### 决定性对照实验

同一份明文、只改 `ZuanShi` 一个数字，唯一变量是 salt/iv：

| 存档 | 明文字节数 | 文件字节数 | salt/iv | 结果 |
|---|---|---|---|---|
| 原档 | 38140 | 76896 | 原值 | ✅ 登录页 |
| `ZuanShi` 9→8（等长） | 38140 | 76896 | **随机** | ❌ 黑屏 |
| `ZuanShi` 9→8（等长） | 38140 | 76896 | **复用原档** | ✅ 登录页 |
| `ZuanShi` 9→999999 | 38145 | 76912 | 复用原档 | ✅ 登录页，`FormatException` 计数 **0** |

后两行是修复后的验证，第二行是故障复现。

### 为什么之前的回归测试一直是绿的

`encrypt_bytes()` 和 `decrypt_bytes()` 都用同一套随机 salt/iv 做往返，**两边同时错也会通过**。这是教训：自检不能只测「自己加密 → 自己解密」，必须拿真机原档做逐字节比对。

## 三、第二个坑：桶布局不能重拼

修复 salt/iv 后又发现，`build_bucket()` **无条件补 `_Key` 条目**，但：

- `saves/SaveFile_orig.es3` 的桶里**没有** `_Key`
- `evidence/saves/SaveFile_device_orig.es3` 的桶里**有** `_Key`（值 2640）

重拼导致桶比原档多 9 字节，`零改动重封 == 原档` 的断言直接失败（76880 vs 76896）。不同存档的桶条目集合和顺序都不一样，**只能原地替换 hex，不能重新生成**。

## 四、修复

`scripts/es3save.py`：

```python
def split_outer(blob): ...          # 拆 (salt, iv, ct)
def salt_iv_of(blob): ...           # 取既有文件的 (salt, iv)

def encrypt_bytes(plain, password=PASSWORD, salt=None, iv=None): ...
    # salt/iv 可传入；不给才随机（只能用于新建文件）

def replace_hex(bucket, old_hex, new_hex): ...
    # 桶里只换 hex 值，其余字节一个不动

def write_save(path, plain, ..., reuse_outer=True): ...
    # 默认从目标文件取 salt/iv/桶布局，原地替换 hex
```

`write_save()` 现在是：

1. `des_encrypt(plain)` 得到新 hex
2. 读旧文件 → `salt_iv_of()` 取 salt/iv
3. `decrypt_bytes()` 得旧桶 → `parse_bucket()` 取旧 hex
4. `replace_hex(旧桶, 旧hex, 新hex)` → 只替换 hex
5. `encrypt_bytes(新桶, salt=旧salt, iv=旧iv)`

目标文件不存在时退化为 `build_bucket()` 新建。

## 五、回归测试

`tools/test_savedit.py` 新增 `[5] salt/iv 复用（黑屏事故回归）`，六条断言覆盖四个独立失效面：

| 断言 | 防止什么 |
|---|---|
| 重封后 salt 复用 | 主故障 |
| 重封后 iv 复用 | 主故障 |
| 桶条目集合继承 | 多/少 `_Key` 之类的布局漂移 |
| string key 继承 | 换了 key 等于换了存档槽 |
| `reuse_outer=False` 会换 salt | **防止前两条假绿** —— 证明断言真的在测东西 |
| 零改动重封 == 原档 | 全链路逐字节正确 |

最后一条是最强的：不满足它，前面几条就都是空话。

## 六、验证记录

```
$ python tools/test_savedit.py
  [5] salt/iv 复用（黑屏事故回归）
  重封后 salt 复用       PASS
  重封后 iv 复用         PASS
  桶条目集合继承          PASS
  string key 继承       PASS
  reuse_outer=False 会换 salt   PASS
  零改动重封 == 原档      PASS
  ALL PASS
```

上机（`emulator-5558`，改 `ZuanShi` = 999999，文件 76912 字节）：

- 截图 sha256 = `ecc306...`（= 正常登录页的哈希，非黑屏的 `5c49fd...`）
- logcat `FormatException` 计数 **0**
- logcat `LanguageDataManager` 计数 **0**

## 七、尚未闭环的部分

**这条链路到「游戏正常读取改过的存档」为止，没有到「进游戏看到数值变了」。**

游戏卡在 TapTap 登录页，没有账号进不去，所以 `ZuanShi` 是 8 还是 999999，游戏都还没机会展示。已经确认的是**加密管道对游戏完全透明**（零改动能逐字节还原、改动后不报异常），而不是数值生效。

要真正闭环，卡点仍是登录：

- 服务器 `qingQiu.asp` 的 `qingQiuID=100`（注册）是桩：4 个字段非空 + 验证码正确 → 直接打印 `222`，**不写数据库**（SQL 注入载荷都能过）
- `qingQiuID=111/222`（登录）返回 `?`（ASP 未捕获异常），账号表已不可用
- `DengLuChengGong @ 0x1892A24` 需要有效的 `this`（`x19`）和已初始化的单例，不能裸调用

详见 `docs/18-游戏自建账号系统已失效.md`。

## 八、给后来者的三条经验

1. **看到「进程活着但黑屏」，先查 `FormatException`**，不要先怀疑渲染。`dumpsys window` 显示 `HAS_DRAWN` 是假象 —— 画过一次之后就不再画了。
2. **改档工具的自检必须包含「零改动往返逐字节等于原文件」**。只做 encrypt→decrypt 的往返，两边同时错也会绿。
3. **不要重新生成容器结构**（桶条目、顺序、salt/iv）。改档的本质是「在别人的容器里换一段数据」，不是「按自己的理解造一个容器」。
