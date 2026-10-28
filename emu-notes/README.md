# 模拟器环境验证报告（2026-10-28）

## 一、结论摘要

| 项 | 状态 |
|---|---|
| 模拟器安装 | ✅ 本机已有 MuMu 12，**无需新装** |
| 游戏安装 | ✅ Success |
| 游戏启动 | ✅ 正常（ARM 翻译层工作） |
| 登录 | ✅ 用户扫码后进入游戏 |
| 存档定位 | ✅ `/sdcard/Android/data/game.taptap.HQGAMES.TapDemons/files/SaveFile.es3` |
| 存档格式 | ⛔ **ES3 AES 加密**（此前演示存档是明文 JSON） |
| 密钥获取 | ⚠️ 未突破（frida 无法注入 ARM 翻译层进程；内存中无明文密钥字符串） |

---

## 二、模拟器环境

本机已安装 **MuMu 12 (MuMuPlayer 5.27.4.3536, engine=nemux)**，路径 `E:\Program Files\Netease\MuMu`。

**关键：x64 引擎自带 ARM 翻译层，不需要另装 ARM 专用模拟器。**

```
adb shell getprop ro.product.cpu.abilist
→ x86_64,arm64-v8a,x86,armeabi-v7a,armeabi
```

APK 只含 `arm64-v8a` / `armeabi-v7a`（无 x86_64 库），但实际运行的是
`/data/app/.../lib/arm64/libil2cpp.so`，即 **ARM64 代码在翻译层中执行**。

### 环境参数

| 项 | 值 |
|---|---|
| Hyper-V | 已启用（`hyperv_enabled=true`, `vt_enabled=true`） |
| Android | 12 |
| adb | `E:\Program Files\Netease\MuMu\nx_main\adb.exe` (1.0.41 / 36.0.0) |
| adb 端口 | 127.0.0.1:16384 |
| 屏幕 | 1080×1920 @ 280dpi |
| root | ✅ 已开（`MuMuManager setting -v 0 -k root_permission -val true`） |

### 常用命令

```powershell
$M   = 'E:\Program Files\Netease\MuMu'
$MUM = "$M\nx_main\MuMuManager.exe"
$ADB = "$M\nx_main\adb.exe"
$S   = '127.0.0.1:16384'

& $MUM info -v 0            # 状态
& $MUM control -v 0 launch  # 启动
& $MUM control -v 0 shutdown
& $ADB connect $S
& $ADB -s $S shell "su -c '...'"
& $MUM sh -v 0 -c "su -c '...'"    # ← 后台任务用这个更可靠
```

**坑 1：** `adb shell` 里跑后台命令容易挂住；`MuMuManager sh -v 0 -c` 更稳。
**坑 2：** PowerShell 里 `adb shell "su -c '... grep a\\|b'"` 会被 PS 解析器吃掉，**写成 .sh 推上去跑**。

---

## 三、游戏信息

| 项 | 值 |
|---|---|
| APK | `files/TapDemons_v5.9.2.apk` (132.2 MB) |
| 包名 | `game.taptap.HQGAMES.TapDemons` |
| 版本 | 5.9.2 |
| 登录 Activity | `.MoeNativeActivity` |
| 游戏 Activity | `com.unity3d.player.UnityPlayerActivity` |
| 进程名 | `点击魔王（TapTap测试版）`（中文！按名字匹配会失败，要用 PID） |
| 运行库 | `/data/app/.../lib/arm64/{libil2cpp,libunity,libmain}.so` |

---

## 四、存档位置与格式（关键发现）

### 位置

```
/sdcard/Android/data/game.taptap.HQGAMES.TapDemons/files/SaveFile.es3
```

登录前不存在；登录并进入游戏后生成。首次 76832 字节，之后 76912 字节。

### 格式：ES3 AES 加密

```
size: 76832   len % 16 = 0
前 16 字节 = IV: 07 2f b2 a5 75 48 75 46 f2 ea 5d 11 c8 e7 59 ce
密文 = 76816 字节（从偏移 16 开始）
```

结构与 ES3 官方 AES 格式一致：`IV(16B) + AES-CBC(payload)`。

> **注意：** 这与分析阶段用的演示存档（`playerDate_01/02/03.json`，明文 `$` 拼接 JSON）
> **完全不同**。演示存档是官方放出来的**明文导出**，真实运行时存档是加密的。

### 相关代码

`dump.cs:251899` `SaveManager`（TypeDefIndex 2846）：

```csharp
public class SaveManager
{
    private static SaveManager instance;   // 0x0
    private ES3Settings setting;           // 0x10   ← 密钥在这里
    public bool IsCunZai(string key);
    public void Save<T>(string key, T value);
    public T    Load<T>(string key);
    public void LoadInto<T>(string key, T t);
    public void DeleteData(string key);
}
```

`dump.cs:563867` `ES3Settings` 有字段 `public string encryptionPassword; // 0x28`。
`dump.cs:562031` `public const ES3.EncryptionType AES = 1;`
`get_Instance` @ RVA `0x17A5D84` Offset `0x17A1D84`

---

## 五、失败的路（避免重复踩）

### 1. frida 注入失败 —— 翻译层挡住

- 推送 x86_64 版 frida-server（17.24.3），能启动、能连、`enumerate_processes` 能看到游戏 PID 2808
- **但 `attach(2808)` 附着上的是错误进程**：枚举到 297 个模块、全是 `app_process64` 那套，
  完全没有 `libil2cpp.so`
- 也试了 arm64 版 frida-server：能 `--version`，后台常驻后 `attach` 同样拿不到 il2cpp
- 原因：游戏跑在 ARM 翻译层（arm64 代码），x86_64 frida-server 只能看到 x86 世界
- 残留物：`/data/local/tmp/frida-helper-*.dex`

**教训：** 模拟器 + ARM 翻译层下，frida 这条路基本堵死，别浪费时间。

### 2. 内存直接搜密钥 —— 无明文

拉出游戏进程全部 `rw-` 匿名段共 **535 MB** 做离线分析：

- 搜 `ES3` / `ES3File` / `ES3Settings` 类名字符串 → **0 命中**
- 搜 `.es3` / `SaveFile` → **0 命中**
- 搜 UTF-16 的 `pass` / `encrypt` / `es3` / `SaveFile` → 只有广告 SDK 噪音
- 搜 32/64 位 hex 串 → 150/14 个唯一值，多为随机数，唯一像密钥的
  `0123456789abcdef0123456789ABCDEF` 是 AES 测试向量，不是真密钥

**推断：** 密钥不以 .NET string 形式长期驻留堆上（可能初始化后即转 byte[]，
或被保护层持有，或来自加密的元数据）。

### 3. 冷门线索

内存中有 `ES3KEY` / `ES3Key` / `ES3KeyFactory` / `ES3Oji` 符号，
但 `dump.cs` 里**搜不到**对应 C# 类 —— 说明它们是**原生层 .so 里的符号**（保护 SDK），
可能是 Tapsdk 的 `ASSES`（`classes3.dex` 里出现过 `asses3.dex`）。

---

## 六、下一步选项

| 方案 | 说明 | 难度 |
|---|---|---|
| A. hook x86 侧 | 找翻译库的 C#→native 桥，在 x86 侧拦截 ES3 调用 | 高 |
| B. 静态追 key | 反汇编 libil2cpp.so 中 `SaveManager` 构造处，找 encryptionPassword 赋值 | 中高 |
| C. 用 Ghidra | 需要先装 JDK 21+，本机当前无 java | 中（环境成本） |
| D. 绕过存档 | 不碰存档，直接在运行时改内存值（需 A 或 B 先打通） | 高 |
| E. 停在演示存档层 | 演示存档层的结论已足够 | 低 |

**推荐 B**：`SaveManager` 的 RVA 已知，反汇编看它怎么构造 `ES3Settings`，
密钥大概率是 immediates 或 string 常量引用。装个 JDK 就能上 Ghidra。

---

## 七、辅助脚本

全部在 `emu/`：

| 文件 | 作用 |
|---|---|
| `probe1..6.py` | frida 探测（进程列表 / 模块枚举） |
| `proctree.sh` | 找带 il2cpp 的进程 |
| `maps.sh` | 看 il2cpp/unity 映射路径与架构 |
| `scan.sh` | 读 /proc/pid/mem 导出 rw- 段（535MB） |
| `grep_mem.sh` / `grep2.sh` / `ctx.sh` | 离线搜内存 |
| `find_save.sh` | 找存档文件 |
| `start_fs.sh` / `check_fs.sh` | frida-server 启动/检查 |
| `es3probe.py` | ES3 文件头结构分析 |
