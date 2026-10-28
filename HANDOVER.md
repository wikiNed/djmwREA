# 《点击魔王》逆向工程 — 交接文档

> **项目**：TapTap 独立游戏《点击魔王》(TapDemons) v5.9.2 存档逆向
> **包名**：`game.taptap.HQGAMES.TapDemons`
> **引擎**：Unity + IL2CPP（ARM64）
> **状态**：存档结构 100% 破译、修改工具全通过；**真实存档的 ES3 AES 口令未取得**
> **最后更新**：2026-10-28

---

## 一、给接手人的三句话

1. **存档格式已完全搞清楚**——14 段用 `$` 拼接的明文 JSON，字段级映射全部有据可查，修改工具 `savedit.py` 五条命令全部实测通过。
2. **卡点是口令**——游戏运行时把存档用 ES3 AES 加密写盘，`key = PBKDF2-HMAC-SHA1(password, salt, 100, 16)`，管道逐指令还原完毕，但 `password` 那串字符串拿不到。
3. **换台 ARM64 真机，十分钟能解决**——所有失败都源于 MuMu 12 的 x86 翻译层（Intel Houdini）无法被 frida hook。真机上 `base + RVA` 直接可用。

---

## 二、成果清单

### 2.1 存档结构（已完成）

存档 = **多段独立 JSON 用 `$` 字符拼接**，每段自带 `DateID` 字段（0~13）。**无 BOM、无加密、无压缩、无 HMAC/CRC/签名。**

| 段 | DateID | 类名 | 内容 |
|---|---|---|---|
| 0 | 0 | — | 基础/账号信息 |
| 1 | 1 | `Date_HeroDong` | **`HerosDates[]`** — 主角、`HeroBaoShis[]`（宝石实体）、`HeroZhuangBeis[]`（装备） |
| 6 | 6 | — | 宠物相关 |
| 9 | 9 | `Date_BaoShiDong` | `BaoShiSuiPian`（宝石碎片）、`SuoYouBaoShiTongJi`（统计） |
| 11 | 11 | — | **黄金树** `IsJiHuo` / `IsHuangJin` / 到期时间 |
| 13 | 13 | — | `LiBaoIDs`（已领取礼包码） |

完整字段表见 [`docs/06-存档修改实战.md`](docs/06-存档修改实战.md) 与 [`notes/存档修改速查表.md`](notes/存档修改速查表.md)。

### 2.2 修改工具 `scripts/savedit.py`（已完成，全通过）

```
python savedit.py info       <save.json>                 # 概况
python savedit.py roundtrip  <save.json>                 # 无损往返验证
python savedit.py get        <save.json> <段> <字段>
python savedit.py set        <save.json> <段> <字段> <值>
python savedit.py libao      <save.json> --keep 11,35    # 重置礼包码可重兑
python savedit.py baoshi     <save.json> --to 999999     # 宝石碎片
python savedit.py baoshiall  <save.json> --level 99 --pinjie 6 --xiyoudu 5
python savedit.py pets       <save.json>                 # 宠物全获取
python savedit.py tree       <save.json> --days 99999    # 黄金树永久
```

**实测结果**（`saves/playerDate_03.json`，497 颗宝石）：

```
本次强化宝石总数: 497
Level 99-99  PinJie [6]  XiYouDu [5]
变化段: [1, 9]  顶层字段: ['HerosDates','SuoYouBaoShiTongJi']
对账 Jie_0N [0,0,0,0,0,0,497] == [0,0,0,0,0,0,497]
     品质   [0,0,0,0,0,497]   == [0,0,0,0,0,497]
镶嵌一致性 293/293，0 不一致
四步串跑: 段 [1, 6, 9, 11] 全部生效
```

### 2.3 ES3 加密管道（已 100% 还原）

用 capstone 反汇编 `libil2cpp.so`，逐指令还原：

```
key  = PBKDF2-HMAC-SHA1(password_utf8, salt, iterations=100, dkLen=16)
alg  = AES-128-CBC, padding = PKCS7
file = salt(16) ‖ iv(16) ‖ cipher
```

实测 `emu/SaveFile.es3`：
```
salt = 07 2f b2 a5 75 48 75 46 f2 ea 5d 11 c8 e7 59 ce
iv   = 0c 9c 94 d5 fb 6e 4e 36 df b1 60 ff c6 d2 06 46   (salt ≠ iv)
```

**口令写入点**（铁证）：
```
ES3Settings..ctor(EncryptionType, string) @ RVA 0x175226C
  0x175227C  mov  x19, x2
  0x1752284  bl   #0x1751f88          ; .ctor(applyDefaults)
  0x1752288  str  x19, [x21, #0x28]!  ; this.encryptionPassword ★
  0x175228C  stur w20, [x21, #-8]     ; +0x20 = encryptionType
```
偏移 `0x28` = `encryptionPassword`、`0x20` = `encryptionType`，与 `dump.cs:563867` 完全吻合。

**口令读取点**：
```
SaveManager..ctor @ RVA 0x17A64D8
  0x17A64EC  adrp x20, #0x35e7000
  0x17A64F8  ldr  x20, [x20, #0x408]   ; x20 = 静态字段槽
  0x17A6510  adrp x0,  #0x35e7000
  0x17A6514  ldr  x0,  [x0, #0x408]
  0x17A6518  bl   #0x1653b4c          ; il2cpp_class_init
  0x17A652C  ldr  x2,  [x20]          ; x2 = password
  0x17A6530  mov  w1,  #1             ; EncryptionType.AES
  0x17A653C  bl   #0x175226c          ; ES3Settings..ctor(this, 1, password)
  0x17A6544  str  x20, [x0, #0x10]!   ; this.setting =
```

**静态分析结果**：全文件扫 `adrp #0x35e7000` + `ldr/str [xN, #0x408]` → **10 处访问全部是读，零处写**。
文件里 `0x35e7000` 起 512 字节全零。说明口令由 `il2cpp_class_init` 运行时填充，
**不是硬编码字面量赋值**——这解释了为什么 metadata 里的 133048 条字符串字面量全部试遍也没命中。

详见 [`docs/07-ES3口令追踪-阶段性结论.md`](docs/07-ES3口令追踪-阶段性结论.md) 与 [`docs/07-ES3密钥攻关.md`](docs/07-ES3密钥攻关.md)。

---

## 三、已穷尽的失败路径（**别重复踩**）

### 3.1 密钥爆破 — 全部失败

| 方法 | 规模 | 结果 |
|---|---|---|
| metadata 字符串字面量爆破 | 133048 条 → 去重 14583 条（len 1~64） | **0 命中** |
| 参数穷举（布局 × 哈希 × 迭代 × 编码 × dkLen） | 密码候选 × 2 布局 × sha1/sha256 × 100/10/1000/10000 × utf8/utf16le × 16/32 | **0 命中** |
| 已知常量试解（`PJSQJ678`/`UJHJKOikhS`/`TSHYUJKSds`） | — | 全部失败 |
| 资产排查（`ES3Defaults` ScriptableObject、`data.unity3d`、`resources.assets`、`global-metadata.dat`） | 全量 | **口令不在任何资源里** |
| 结构扫描锚点区（`[len][bytes][pad]`） | 锚点区全扫 | 0 候选（Unity 字符串长度含 `\0`，字段间夹 `0xf1` 标志字节，纯结构扫描不可靠） |

### 3.2 内存搜明文 — 全部失败

| 方法 | 规模 | 结果 |
|---|---|---|
| dump ≥4MB 的 `rw` 段搜 `DateID`/`BaoShiSuiPian`/`SaveFile` | 12 段（含 402MB dalvik-main） | **0 命中** |
| 遍历全部 `rw` 段（UTF-8 + UTF-16LE 双编码） | 2071 段（≥256KB） | **0 命中**，连 `SaveFile` 路径串都没有 |
| 存档窗口内 40 轮高频 burst 扫描 | 40 轮 × 切后台触发 `YanShiTime=6` | **0 命中** |

**原因**：ES3 用流式 `CopyStream(input, cryptoStream)` 边加密边写，**完整 JSON 从不在托管堆上成形**；
`SaveFile.es3` 路径串由原生层拼接，不以明文驻留。

### 3.3 frida hook — 全部零命中 或 SIGILL 崩溃

| 目标 | RVA | 结果 |
|---|---|---|
| `AESEncryptionAlgorithm.Encrypt/Decrypt`（4 处） | `0x1782D44` 等 | 装入成功，**从未命中** |
| `Rfc2898DeriveBytes..ctor` | `0x27A87E0` | 装入成功，**从未命中** |
| `ES3.Save<int>` / `LoadGame` / `BaoCunDate` | `0x1A71D64` 等 | **从未命中**；`LoadGame` 报 `unable to intercept function` |
| libc `open`/`openat`/`fopen` | — | **零命中**（游戏走 ARM 侧，不经 x86 libc） |
| 27 个 hook 批量装 | — | **全零命中**，且把进程拖死 |
| 26 个写入型 `str [xN,#0x408]` 批量 hook | — | **进程被拖死** |

---

## 四、根因：MuMu 12 的 x86 翻译层挡住了一切

### 4.1 翻译层身份

```
/system/lib64/libhoudini.so          Intel Houdini，ARM→x86 翻译器（145 个导出）
/system/lib64/arm64/nb/libtcb.so     translator control block
/system/lib64/libnb.so               MuMu 包装（NativeBridgeItf @ 0x7d3a35947740）
```

实例标签 `120.2.161.006-nemux-default-x64-release`，`MuMuManager setting -v 0 -a` 的全部设置项里
**没有任何 arch / abi / engine / arm 切换项**——MuMu 12 不提供纯 ARM 实例。

### 4.2 核心矛盾：ARM 代码段是 `r--p`

```
07354000 r--p 00000000   file off 0x0        ELF 头
08b14000 r-xp 017bc000   4KB stub
08b1b000 r-xp 017c3000   4KB stub   ← 0x174B720 在这里
08b1c000 r--p 017c4000   ARM 主体代码（只读、不可执行！）
0a999000 rw-p 03639000   .data
```

CPU 从不直接执行 ARM 指令。Houdini 把 `libil2cpp.so` 当数据读入、翻译成 x86、
放进 code cache 执行。**frida 的 ARM inline hook 需要 `rwx`，写入 `r--p` 段就是 SIGILL。**

### 4.3 Houdini code cache（唯一可写可执行区）

`Process.enumerateRanges('rwx')` 只有 4 段：

```
0xd4da000       73 728 B   rwx
0xd4ec000   65 454 080 B   rwx   ← 62 MB 主 code cache
0x11358000      16 384 B   rwx
0x7d3cdde3c000  73 728 B   rwx
```

在其中搜 4 个关键 ARM 函数地址（32 位 / 64 位两种形式，全 62 MB）：
```
writer 0x08b1b720 = 0    aes 0x08866d44 = 0
kdf    0x0988c7e0 = 0    loadgame 0x08b4e374 = 0
```
**全部零命中** → Houdini 的 TB 表用哈希索引，不存明文源地址；或位于 `libtcb.so` 的
`rw` 段（`0x0d4af000-0x0d4d8000`）内，布局无公开文档。

### 4.4 base 定案（由 tombstone）

`/sdcard/Android/data/game.taptap.HQGAMES.TapDemons/files/tombstone_00`：
```
signal 4 (SIGILL), code 0 (SI_USER)
pc  0000000008b1b720
backtrace:
  #00 pc 000000000174b720   ← RVA 0x174B720 == ES3Writer.Create
  #01 pc 0000000001a722d0   ← 紧邻 ES3.Save<object> @0x1A722C8
  #02 pc 00000000018a7634   ← ShuJuDate.Init 尾部
  #03 pc 00000000018a710c   ← ShuJuDate.SaveGame 附近
```
**backtrace 打印的是 RVA**，故：

```
base = 0x08b1b720 - 0x174b720 = 0x073D0000
```

`0x073D0000` 是正确 load base（中途怀疑的 `0x07354000`、`0x7d3964715000` 都不对）。
**但即使 base 正确，目标段只读，写就崩。**

完整调研见 [`docs/08-模拟器翻译层调研.md`](docs/08-模拟器翻译层调研.md)、[`emu-notes/frida-结论.md`](emu-notes/frida-结论.md)。

### 4.5 另一个易踩的坑：PowerShell 解析

`adb shell "su -c '... | grep a\\|b'"` 会被 PowerShell 自己吃掉（报
`一元运算符'-'后面缺少表达式`）。**正确做法：把命令写成 `.sh` 文件推上去，`sh /data/local/tmp/x.sh` 执行。**
或者用 `MuMuManager sh -v 0 -c "..."`（root shell，比 `adb shell` 稳，不易挂住）。

---

## 五、下一步（按成本排序）

### 路线 A：真机 ARM64 ★★★★★ 推荐

**成本最低、成功率最高。** 任意 Android 手机 + USB 调试即可。

```bash
# 1. 取 base（真机上 libil2cpp.so 是正常 r-xp，可直接 hook）
adb shell "cat /proc/\$(pidof game.taptap.HQGAMES.TapDemons)/maps | grep libil2cpp" | head -1

# 2. 推 frida-server（arm64）
adb push frida-server-*-android-arm64 /data/local/tmp/fs
adb shell "chmod 755 /data/local/tmp/fs && su -c '/data/local/tmp/fs -l 0.0.0.0:27042 &'"
adb forward tcp:27042 tcp:27042

# 3. hook ES3Settings..ctor，直接打印 password
#    运行时地址 = base + 0x175226C
```

**`scripts/frida_hook_settings.py` 已写好**，只需把 `BASE` 改成真机的 base 即可。
hook 时 `x2` 就是 password 指针（Il2CppString*），`x2+0x10` 起是 UTF-16 字符数据，长度在 `x2+0x10`（int）。

拿到口令后：
```python
from scripts.es3decrypt import decrypt
data = decrypt(r'emu/SaveFile.es3', password)
```

### 路线 B：官方 ARM64 AVD ★★☆☆☆

需下载 ~8–10 GB（SDK + arm64 system image）。但 x86 主机上是 **qemu 全模拟、无硬件加速**，
Unity 3D 游戏大概率跑不起来。

### 路线 C：纯静态挖初始化函数 ★★★☆☆

不需要设备。需要扩展 `scripts/find_slot_writers.py` 识别"间接写入"形态
（`str xN, [xM]`，其中 `xM` 由前序计算得到）。工作量不小，且没有 frida 反馈验证，属于盲搜。

### 路线 D：绕开口令 — 直接改内存 ★★☆☆☆

游戏运行时把存档 `Load` 成 `ShuJuDate.gameDate` 对象。如果能定位该对象在堆上的地址，
可以直接改内存而不碰存档。但同样受制于无法 hook。

**备选**：`scripts/find_plaintext.py` / `scripts/scan_mem.py` 已在模拟器上零命中，
但如果能在**游戏刚读完存档、尚未加密回写**的那一瞬间 dump 堆，理论上能抓到明文。
需要精确的时机控制——真机上用 frida hook `LoadGame` 的返回点即可。

---

## 六、资料清单

```
docs/
  05-IL2CPP黄金树宠物宝石.md        黄金树 / 宠物 / 宝石 的字段定位
  06-存档修改实战.md                五条修改命令的完整实战记录 ★★★
  07-ES3密钥攻关.md                 加密管道还原过程（含反汇编逐指令）
  07-ES3口令追踪-阶段性结论.md      口令追踪的全部证据与失败路径 ★★★
  08-模拟器翻译层调研.md            MuMu/Houdini 为什么不可 hook ★★★
  09-dump关键类摘录.md              dump.cs 中 9 个关键类的完整摘录

notes/
  REA学习笔记.md                    REA 工具链方法论（项目起点）
  存档修改速查表.md                 字段速查 ★★★
  点击魔王_逆向分析报告.md          完整逆向报告

scripts/                            78 个脚本
  savedit.py                       ★ 主工具，五条修改命令
  es3decrypt.py                    ★ ES3 解密（拿到口令后直接用）
  disasm_range.py                  ★ capstone 反汇编 + 自动标注 dump.cs 函数名
  frida_hook_settings.py           ★ 真机上 hook 口令（改 BASE 即可）
  find_slot_writers.py             静态找静态字段写入点
  crack_es3.py                     metadata 字面量爆破
  scan_mem.py / find_plaintext.py  内存明文搜索
  ...                              其余为各阶段探查脚本，保留供参考

saves/
  playerDate_01/02/02.test/03.json 官方演示存档（明文，可直接用 savedit.py 改）
  SaveFile.es3                     真实加密存档样本（salt 072fb2a5...）
  SaveFile_live.es3 / _orig.es3    运行时抓取的另两份
  zeros.es3                        对照组

emu-notes/                         模拟器阶段的操作脚本与结论
evidence/                          hook 输出、maps、base 验证记录
```

### 大文件（已通过 Git LFS 入库）

| 文件 | 大小 | 位置 |
|---|---|---|
| `TapDemons_v5.9.2.apk` | 132 MB | `files/TapDemons_v5.9.2.apk` |
| `libil2cpp.so` | 56 MB | `files/libil2cpp.so`（MD5 `3466135958c06c40a50d4fa8bd458d0e`，59058224 字节） |
| `global-metadata.dat` | 10 MB | `files/global-metadata.dat` |
| `dump.cs` | 22 MB / 666763 行 | `files/dump.cs` |
| `data.unity3d` | 20 MB | **不入库** — 用 `scripts/paths.py:unity_data_asset()` 从 APK 现取（已验证字节一致） |

```bash
git lfs install
git clone https://github.com/wikiNed/djmwREA.git   # 会自动拉 LFS 对象
git lfs pull                                        # 若被跳过则手动拉
```

```bash
# dump.cs 若需重新生成
Il2CppDumper.exe files/libil2cpp.so files/global-metadata.dat out_dir
```

**注意**：`dump.cs` 里的 `RVA` 才是 hook 用的地址。
`Offset` 是文件偏移，两者**不相等**（ELF 段间存在 `0x4000` / `0x8000` 的差值）。
正确换算：`fileoff = RVA - p_vaddr + p_offset`，必须按 program header 分段算。

### 脚本的路径解析（**克隆即可跑，无需改代码**）

所有脚本统一走 `scripts/paths.py`，不再硬编码本机绝对路径：

| 变量 | 默认位置 | 可用环境变量覆盖 |
|---|---|---|
| `SO` | `files/libil2cpp.so` | `IL2CPP_SO` |
| `DUMP` | `files/dump.cs` | `IL2CPP_DUMP` |
| `META` | `files/global-metadata.dat` | `IL2CPP_META` |
| `APK` | `files/TapDemons_v5.9.2.apk` | `TAPDEMONS_APK` |
| `SAVES` | `saves/` | `REA_SAVES` |
| `EMU` | `emu/` | `REA_EMU` |

派生文件：`ES3_FILE` = `emu/SaveFile.es3`，`MEMDUMP` = `emu/memdump.bin`，
`SAVE_PLAIN` = `emu/save_plain.json`。
Unity 资源包：`unity_data_asset()` — 优先 `assets/data.unity3d`，
没有就从 APK 提取到 `work/assets/` 并缓存。

工具链（不入库，需自行安装并设环境变量）：
`$JAVA_HOME`（JDK 21+，Ghidra 用）、`$GHIDRA_INSTALL_DIR`（Ghidra 12.2+）。

自检：

```bash
python tools/smoke_test.py        # 冒烟测试：路径解析 + 反汇编 + 未定义检查
python tools/find_undefined.py    # AST 检查脚本是否引用了未定义的常量
```

---

## 七、关键地址速查

| 符号 | RVA | 说明 |
|---|---|---|
| `SaveManager..ctor` | `0x17A64D8` | 读口令 |
| `ES3Settings..ctor(EncryptionType,string)` | `0x175226C` | **写口令，hook 首选** |
| `SaveManager.get_Instance` | `0x17A5D84` | |
| `SaveManager.IsCunZai` | `0x17A55B0` | |
| `AESEncryptionAlgorithm.Encrypt(Stream)` | `0x1782D44` | |
| `AESEncryptionAlgorithm.Decrypt(Stream)` | `0x178329C` | |
| `Rfc2898DeriveBytes..ctor(string,byte[],int)` | `0x27A87E0` | KDF |
| `ES3.Save<int>` | `0x1D18338` | |
| `ShuJuDate.SaveGame` | `0x18A7034` | |
| `ShuJuDate.LoadGame` | `0x18A9374` | |
| `ShuJuDate.Encrypt(string,string)` | `0x18A8A68` | 游戏自己的一套加密（非 ES3） |

---

## 八、环境备忘

| 项 | 值 |
|---|---|
| 模拟器 | MuMu 12 `MuMuPlayer 5.27.4.3536`，引擎 `nemux` x64 |
| MuMuManager | `E:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe` |
| adb | `E:\Program Files\Netease\MuMu\nx_main\adb.exe`，端口 `127.0.0.1:16384` |
| root | `MuMuManager setting -v 0 -k root_permission -val true` 后重启 |
| Android | 12，`ro.product.cpu.abilist` = `x86_64,arm64-v8a,x86,armeabi-v7a` |
| 游戏进程名 | **`点击魔王（TapTap测试版）`**（中文，按 ASCII 匹配会失败） |
| 存档路径 | `/sdcard/Android/data/game.taptap.HQGAMES.TapDemons/files/SaveFile.es3` |
| Python（含 frida/UnityPy/capstone） | `C:\Users\86156\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe` |
| JDK 25 | `$JAVA_HOME` 指向的 JDK（本机工具，不入库，Ghidra 用) |
| Ghidra 项目 | `E:\rea_ghidra\proj`，72117 个函数（但函数边界错位，实际用 capstone） |

**存档写入时机**：`ShuJuDate.ziDongSaveTime = 180`（自动存档 180 秒）、
`YanShiTime = 6`（切后台延迟 6 秒存档）。抓时机用这两个常量。

---

## 九、工程约定（本轮踩过的坑）

1. **`RVA ≠ file offset`**——必须按 ELF program header 分段换算。早期脚本假设相等，导致大量误判。
2. **`libil2cpp.so` load base 每次重启都变**——不要在脚本里硬编码，每次重新从 `/proc/PID/maps` 取。
3. **frida 17 移除了 `Module.findExportByName` / `getExportByName`**——只能用 `Process.getModuleByName()`。
4. **`grep /proc/PID/mem` 不可靠**（非规则文件 seek 失效）——必须先 `dd` 落盘再搜；
   且 `dd` 读 `/proc/PID/mem` 要 **`bs=1`** 才能按任意字节偏移 seek。
5. **Unity 的 "missing script" 警告 ≠ 功能在用**——曾因 `ES2 Auto Save Manager` 警告误判存档走 ES2，
   实际 `dump.cs` 里**没有任何 ES2 类**。
6. **PowerShell 会吃掉 `adb shell` 里的管道与转义**——命令写成 `.sh` 推上去执行。

---

## 十、一句话总结

> 存档本身是明文 JSON，改起来毫无难度；难的是游戏把它加密了。
> 加密算法已经完全还原，只差一个运行时生成的字符串。
> **换 ARM64 真机，hook `0x175226C`，`x2` 就是那串口令。**
