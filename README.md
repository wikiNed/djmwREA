# djmwREA — 《点击魔王》存档逆向工程

> TapTap 独立游戏 **《点击魔王》(TapDemons) v5.9.2** 的 Unity IL2CPP 存档逆向记录。
> 存档结构与**完整加密链**已 100% 还原，`.es3` 可直接读写。
> 口令 `hqgames@2013` 已取得 —— 见 [docs/10](docs/10-ES3口令已取得.md)；
> 内层还有一层游戏自写的 DES —— 见 [docs/11](docs/11-存档双层加密还原.md)。
>
> **⚠ 三项修改已在真机验证，但触发了服务端封号** —— 封号机制、旧版本对比、
> 工具链全图见 [docs/14](docs/14-封号机制与旧版对比.md)。
> 一句话：**存档能改，墙在服务端账号级封禁，换号即可。**

---

## 这是干什么的

游戏存档是 **14 段用 `$` 拼接的明文 JSON**，结构已 100% 破译，字段级映射全部有据可查。
修改工具 `savedit.py` 十几条命令全部实测通过：

```
python scripts/savedit.py baoshiall save.json --level 99 --pinjie 6 --xiyoudu 5   # 宝石全满
python scripts/savedit.py pets      save.json                                    # 宠物全获取
python scripts/savedit.py tree      save.json --days 99999                       # 黄金树永久
python scripts/savedit.py baoshi    save.json --to 999999                        # 宝石碎片
python scripts/savedit.py libao     save.json --keep 11,35                       # 礼包码重兑
python scripts/savedit.py currency  save.json --zuanshi 999999                   # 钻石/经验
python scripts/savedit.py equip     save.json --level 999                        # 装备全满
python scripts/savedit.py heroes    save.json --level 60 --shenqi 20             # 英雄/神器
python scripts/savedit.py resources save.json --mucai 500000                     # 木材/矿石
python scripts/savedit.py level     save.json --guanka 200                       # 关卡/点击等级
python scripts/savedit.py chengjiu  save.json --level 99                         # 成就
```

**`saves/*.es3` 现在可以直接改**，不必先手动解密 —— 工具会透明完成
「ES3 AES 第一层 → 游戏自写 DES 第二层」的解包与封回：

```
python scripts/savedit.py currency saves/SaveFile_orig.es3 --zuanshi 888888
```

全部回归：`python tools/test_savedit.py` → **ALL PASS**。

---

## 快速开始

### 只改演示存档（无需任何逆向环境）

```bash
pip install pycryptodome

python scripts/savedit.py info      saves/playerDate_03.json
python scripts/savedit.py roundtrip saves/playerDate_03.json    # 无损验证
python scripts/savedit.py baoshiall saves/playerDate_03.json --level 99
```

`saves/playerDate_*.json` 是官方放出的**明文**演示存档，可直接编辑。

实测输出（`playerDate_03.json`，497 颗宝石）：

```
各英雄宝石数 (HeroID, 名字, 颗数):
   0   莉安卡      133
   1   妮娅        98
   ...
本次强化宝石总数: 497
段9 统计已重算 (品阶 7 项 + 品质 6 项)，最大品质计数: 497
```

### 双向读写真实存档

口令 `hqgames@2013` 已取得，`.es3` 可以直接改：

```python
from es3save import read_save, write_save

plain = read_save('saves/SaveFile_orig.es3')   # 两层都解开，返回 14 段明文
# plain = b'{"DateID":0,...}${"DateID":1,...}$...'
write_save('saves/out.es3', plain)             # 两层都封回
```

或命令行：

```bash
python scripts/es3save.py unpack saves/SaveFile_orig.es3 plain.json
python scripts/es3save.py pack   plain.json            out.es3
python scripts/es3save.py verify out.es3               # 回读校验
```

`scripts/es3decrypt.py` 只解**第一层**，保留它是为了研究用途（打印 ES3 桶的原始条目）。
**口令错误时 `decrypt_or_raise()` 会抛 `PasswordError`**，不会静默返回乱码
（AES-CBC 用错口令也会解出等长字节，所以必须校验明文形态）。
用 `check_password(path, pw)` 可快速判定单个口令。

### ⚠ 改档时 salt/iv 必须复用原档

`write_save()` 的 `reuse_outer=True`（默认）会自动处理，但如果你自己写封包代码，
必须遵守这条：

```python
# 外层 AES 的参数取自文件自己的前 32 字节
key  = PBKDF2-HMAC-SHA1(b"hqgames@2013", salt=old[0:16], iterations=100, dkLen=16)
pt   = AES128CBC_decrypt(key, iv=old[16:32], ct=old[32:])

# 重封时必须用同样的 salt / iv，不能重新生成
new  = salt + iv + AES128CBC_encrypt(key, iv=iv, pt=new_plain)
```

用新的随机 salt/iv 会让游戏 `ES3.KeyExists()` 抛 `FormatException`，
表现是**启动画面之后永久黑屏**（进程活着、`dumpsys` 显示 `HAS_DRAWN`、截图纯黑）。
细节见 [docs/19](docs/19-改档黑屏根因-salt与iv必须复用.md)。

同理**不要重新拼装桶结构**——不同存档的桶条目集合与顺序不同
（`saves/SaveFile_orig.es3` 没有 `_Key`，`evidence/saves/SaveFile_device_orig.es3` 有），
正确做法是原地替换内层 hex。

### 依赖

| 用途 | 包 |
|---|---|
| `savedit.py` / `es3decrypt.py` | `pycryptodome` |
| `disasm_range.py` 反汇编 | `capstone` |
| `unitypy_*.py` 读资源 | `UnityPy` |
| `frida_*.py` 运行时 hook | `frida` / `frida-tools` |

### 在自己的 ARM64 真机上取口令（已完成，留作方法论）

> 口令已经静态挖到了（`hqgames@2013`），本节不再需要执行，
> 保留是因为它是「如果静态失败该怎么办」的通用解法。
> 完整取证过程见 [docs/10](docs/10-ES3口令已取得.md)。

```bash
# 1. 取 base
adb shell "cat /proc/\$(pidof game.taptap.HQGAMES.TapDemons)/maps | grep libil2cpp" | head -1

# 2. 推 frida-server（arm64）
adb push frida-server-*-android-arm64 /data/local/tmp/fs
adb shell "su -c 'chmod 755 /data/local/tmp/fs; /data/local/tmp/fs &'"
adb forward tcp:27042 tcp:27042

# 3. hook ES3Settings..ctor，直接打印口令
python scripts/frida_hook_es3_ctor.py <pid> <base>
```

hook 点是 `ES3Settings..ctor(EncryptionType, string)` @ RVA `0x175226C`，
参数 `x2` 就是 `password`（Il2CppString*）。拿到后 `read_save()` 即可。

---

## 为什么在模拟器上不行

本项目的全部失败都源于一个根因：**MuMu 12 的 x86 翻译层（Intel Houdini）**。

`libil2cpp.so` 的 ARM 主体代码段在进程里是 **`r--p`（只读、不可执行）**：

```
08b1b000 r-xp 017c3000   4KB stub
08b1c000 r--p 017c4000   ARM 主体代码（不可执行！）
```

CPU 从不直接执行 ARM 指令，Houdini 把它当数据读入、翻译成 x86、
放进 code cache（`0xd4ec000`，62 MB，`rwx`）执行。
**frida 的 ARM inline hook 需要 `rwx`，写入 `r--p` 段就是 SIGILL。**

在 62 MB code cache 里搜 ARM 源地址常量（32 位 / 64 位）：**全部零命中**，
因为 Houdini 的 TB 表用哈希索引。

详见 [docs/08-模拟器翻译层调研.md](docs/08-模拟器翻译层调研.md)。

---

## 目录

```
HANDOVER.md            ★ 交接文档：成果、失败路径、下一步
docs/
  05-IL2CPP黄金树宠物宝石.md     字段定位
  06-存档修改实战.md             ★ 五条命令完整实战
  07-ES3密钥攻关.md              加密管道还原过程
  07-ES3口令追踪-阶段性结论.md   ★ 追踪证据与失败路径
  08-模拟器翻译层调研.md         ★ Houdini 为何不可 hook
  09-dump关键类摘录.md           9 个关键类的 dump.cs 摘录
  10-ES3口令已取得.md            ★ 口令 hqgames@2013 的完整取证链
  11-存档双层加密还原.md         ★ ES3-AES 套 DES，含双向封包
  12-存档编辑速查.md             命令速查
  13-内层DES填充与卡死根因.md    ★ 改档卡死的 PKCS7 根因
  14-封号机制与旧版对比.md       ★★ 必读：三项修改验证、封号链路、
                                    旧版 v5.5.7 对比、工具链全图
  18-游戏自建账号系统已失效.md   ★ 注册是桩、登录返回 `?`，无账号可得
  19-改档黑屏根因-salt与iv必须复用.md ★★ 黑屏根因与修复
notes/
  REA学习笔记.md                 REA 工具链方法论
  存档修改速查表.md               ★ 字段速查
  点击魔王_逆向分析报告.md        完整逆向报告
scripts/                         102 个脚本
  savedit.py                    ★ 主工具（.json / .es3 皆可直接读写）
  es3save.py                    ★ 两层拆封/封装
  es3decrypt.py                 只解第一层（研究用）
  pet_from_template.py          ★ 从官方模板生成 85 只满级宠物
  fix_pets.py / pet_diff.py     宠物字段补齐与对比
  give_resources.py             钻石 / 肉 / 进化石 / 草丛
  unlock_progress.py            关卡进度（门槛 GuanKaLevel > 20）
  safe_edit.py                  只改到模板范围内的安全编辑
  push_save.py                  ★ 推存档（正确处理 SELinux MLS 类别）
  rela_resolve.py               ★ ELF 重定位解析
  peek_literal.py               ★ 按 usage index 读 metadata 字面量
  disasm_range.py               ★ capstone 反汇编 + dump.cs 自动标注
tools/
  smoke_test.py                 环境冒烟测试（3 项）
  find_undefined.py             AST 检查未定义常量
  test_savedit.py               ★ 存档编辑全量回归（41 项，含 salt/iv 组）
saves/                           演示存档（明文）+ 真实存档样本（加密）
emu-notes/                       模拟器操作脚本与结论
evidence/
  templates/                    ★ 从 data.unity3d 导出的 TextAsset 模板
  saves/                        ★ 各阶段存档证据样本
  web/                          PlayerPrefs / 防沉迷 USER_INFO
  其余                           frida 输出、maps、base 验证记录
files/
  TapDemons_v5.9.2.apk          TapTap 版 APK（LFS）
  libil2cpp.so / global-metadata.dat / dump.cs   （LFS）
  old/                          旧版 v5.5.7 三大件（LFS）
```

---

## 关键地址

| 符号 | RVA |
|---|---|
| `ES3Settings..ctor(EncryptionType,string)` | `0x175226C` |
| `SaveManager..ctor` | `0x17A64D8` |
| `AESEncryptionAlgorithm.Encrypt(Stream)` | `0x1782D44` |
| `AESEncryptionAlgorithm.Decrypt(Stream)` | `0x178329C` |
| `Rfc2898DeriveBytes..ctor(string,byte[],int)` | `0x27A87E0` |
| `ShuJuDate.SaveGame` | `0x18A7034` |
| `ShuJuDate.BaoCunDate` | `0x18A71B4` |
| `ShuJuDate.Encrypt(string,string)` | `0x18A8A68` |

### 关键静态槽

| VA | 用途 |
|---|---|
| `0x35e7408` (GOT) | → addend `0x36FC618` → `0xA0005EF3` → usage index 12153 → 口令 |
| `0x35ee2b0` (GOT) | → addend `0x36f1f10` → `0xA0003529` → DES key `PJSQJ678` |

**`RVA ≠ file offset`** —— ELF 段间有 `0x4000` / `0x8000` 差值，
正确换算：`fileoff = RVA - p_vaddr + p_offset`，必须按 program header 分段算。
`scripts/rela_resolve.py` 里的 `Elf.va2off()` 已实现，**不要再用固定偏移**。

---

## 自行获取的大文件

| 文件 | 大小 | 来源 |
|---|---|---|
| `TapDemons_v5.9.2.apk` | 132 MB | TapTap 搜索「点击魔王」（已入 LFS） |
| `libil2cpp.so` | 56 MB | APK `lib/arm64-v8a/`，MD5 `3466135958c06c40a50d4fa8bd458d0e`（已入 LFS） |
| `global-metadata.dat` | 10 MB | APK `assets/bin/Data/Managed/Metadata/`（已入 LFS） |
| `dump.cs` | 22 MB | `Il2CppDumper.exe libil2cpp.so global-metadata.dat out/`（已入 LFS） |
| `files/old/djmw_5.5.7.apk` | 83 MB | 旧版 v5.5.7，无 TapTap 接入（已入 LFS） |
| `files/old/global-metadata_v557.dat` | 3.6 MB | 旧版 metadata（version 27） |
| `files/old/libil2cpp_v557_arm32.so` | 18 MB | 旧版 32 位 libil2cpp |

`data.unity3d`（20 MB）**不入库** —— 用 `scripts/paths.py:unity_data_asset()` 从 APK 现取，已验证字节一致。

---

## 免责声明

本项目仅用于**个人学习与逆向技术研究**。所有分析均针对单机存档数据，
不涉及网络协议、不提供任何在线作弊或破坏游戏公平性的手段。
请勿用于商业用途或传播修改后的存档。游戏版权归原作者所有。
