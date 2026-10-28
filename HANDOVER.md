# 《点击魔王》逆向工程 — 交接文档

> **项目**：TapTap 独立游戏《点击魔王》(TapDemons) v5.9.2 存档逆向
> **包名**：`game.taptap.HQGAMES.TapDemons`
> **引擎**：Unity + IL2CPP（ARM64）
> **状态**：存档结构 100% 破译、**双层加密 100% 还原**、口令与 DES key 均已取得、
> `saves/*.es3` 可直接读写、回归 30/30 通过
> **最后更新**：2026-10-28

---

## 〇、本轮的突破（补充在原有文档之前）

> **原文档的第四、五节已经过时**——口令没有卡住，是用纯静态方法挖到的。

| 项 | 结果 | 文档 |
|---|---|---|
| ES3 AES 口令 | **`hqgames@2013`** | [docs/10](docs/10-ES3口令已取得.md) |
| 内层 DES key | **`PJSQJ678`**（`ShuJuDate.MIMA`，`iv == key`） | [docs/11](docs/11-存档双层加密还原.md) |

取证链（一行版）：

```
0x35e7408(GOT) → addend 0x36FC618 → 0xA0005EF3
  → usage index = 0x5EF3 >> 1 = 12153
  → stringLiteral 表第 12153 行（len-first 格式）→ "hqgames@2013"
```

**原文档认为卡死的原因全部被绕过了**：不需要真机、不需要 frida、
不需要内存搜索——口令就是 metadata 里一条普通字面量，
只是它被 il2cpp 的 `Il2CppMetadataUsage` 哨兵机制（`0xA0000000|(idx<<1)|1`）
包了四层间接（GOT → `.data` 槽 → 哨兵值 → usage 表下标）。

**因此第五节「下一步」里的路线 A/B/C/D 全部作废**，实际采用的是「路线 C+」：
解析 ELF 重定位 + 解析 metadata usage 表。原路线 C 之所以失败，
是因为 `find_slot_writers.py` 只认 `str` 直写，而这批槽是**运行时由 il2cpp 初始化器填充**的，
静态代码里永远找不到 `str`（实测 10 处访问全是 `ldr`）。

---

## 一、给接手人的三句话

1. **存档格式与加密链都已完全搞清楚**——14 段 `$` 拼接的 JSON，
   外层 ES3 AES、内层游戏自写 DES，两层密钥都在手，`saves/*.es3` 直接改。
2. **`savedit.py` 十几条命令 + 30 项回归全通过**，`.json` 与 `.es3` 用法完全一致。
3. **原文档的模拟器/frida 分析仍然有价值**（作为「为什么静态更省事」的对照），
   但**不再是必读的路障**——真机上跑 frida 只是可选的验证手段。

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

## 五、原定下一步（已作废，保留作方法论）

> **本节四条路线全部不再需要** —— 口令与 DES key 已用纯静态方法取得。
> 保留是因为它们写清了「静态失败时该怎么办」的备选思路。

### 实际采用的路线 C+：静态解析 il2cpp 初始化链 ★★★★★ **已成功**

不需要设备、不需要 hook、不需要内存搜索。三步：

1. **解析 ELF 重定位**（`scripts/rela_resolve.py`）：
   `0x35e7408` 在 `.got`，`.rela.dyn` 给出 `type=1027 (R_AARCH64_RELATIVE)`、`addend=0x36FC618`。
   > ⚠️ 原 docs/07 写的 addend `0x36F5DB0` 是**错的**（追到了 `.data` 里无关的一段）。
2. **识别 il2cpp metadata usage 哨兵**（`scripts/peek_literal.py`）：
   `.data` 中 `0x36e4a90 .. 0x3705208` 有 16623 项，
   全是 `0xA0000000 | ((idx << 1) | 1)`，`idx = (0x5EF3 >> 1) = 12153`。
3. **按 index 查 stringLiteral 表**：
   `global-metadata.dat` 表头 `off=0x100 size=0x207b8`，行格式 **length-first** `(int32 len, int32 off)`，
   内容在 `off=0x208b8` 起的 literalData 里。第 12153 行 → `hqgames@2013`。

### 路线 A：真机 ARM64 ★★★★☆（可选验证）

若想交叉验证静态结论，真机 hook 仍是最快的：
`base + 0x175226C` 处 `x2` 即 password。但**已经没有必要**。

### 路线 B：官方 ARM64 AVD ★★☆☆☆

需下载 ~8–10 GB。x86 主机上是 qemu 全模拟，性能不可用。

### 路线 C（原案）：纯静态挖写入指令 ★☆☆☆☆ 已证明走不通

原计划扩展 `find_slot_writers.py` 识别间接写入（`str xN, [xM]`）。
**实测证明这条路是死路**：`0x35e7408` 在 `.text` 里共 10 处访问，**全部是 `ldr`，零处 `str`** ——
这类槽由 il2cpp 的类初始化器在运行时填充，根本不存在对应的 `str` 指令。
正确方向是**读重定位 + 读 metadata**，不是找写入点。

### 路线 D：绕开密钥 — 直接改内存 ★★☆☆☆

同样受制于无法 hook。且现在已有明文读写能力，无需此路。

---

## 五之二、现在该做什么

1. **验证**：`python tools/test_savedit.py`（30 项）+ `python tools/smoke_test.py`（3 项）。
2. **实战**：直接对 `.es3` 跑编辑命令，例如
   `python scripts/savedit.py currency saves/SaveFile_orig.es3 --zuanshi 888888`。
3. **可选的延伸**：
   - 补全 `Date_*` 各段里尚未做编辑器的字段（现有命令覆盖了货币/装备/英雄/资源/关卡/成就/宝石/宠物/黄金树/礼包码）。
   - 若游戏后续版本改了 `PASSWORD` / `MIMA`，按 docs/10 + docs/11 的链路重跑一遍即可
     （两处都是 metadata 字面量，脚本通用）。

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
  10-ES3口令已取得.md               ★ 口令 hqgames@2013 的完整取证链
  11-存档双层加密还原.md            ★ ES3-AES 套 DES，含双向封包与踩坑

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

**验证「干净机器」行为**：`paths.py` 里保留了一条指向开发机
`E:\DSH\game\.rea-study` 的兜底路径，方便原作者本机继续用。
在你自己机器上验证可移植性时，设 `REA_NO_LEGACY=1` 禁用这条兜底——
否则兜底会掩盖隐藏依赖，让你误以为一切正常。
`tools/smoke_test.py` 默认就带这个变量跑。

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

> 存档是 14 段明文 JSON，外套两层加密：ES3 的 AES 与游戏自写的 DES。
> 两把钥匙都没藏在运行时——**它们是 `global-metadata.dat` 里的两条普通字符串字面量**
> （`hqgames@2013` 和 `PJSQJ678`），只是被 il2cpp 的 metadata-usage 哨兵机制
> 包了四层间接：`GOT 槽 → .data 槽 → 0xA0005EF3 → usage index 12153`。
> **找 `str` 指令是死路；解析重定位读 metadata 才是正解。**
