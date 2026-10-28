# frida 在 MuMu ARM 翻译层下的 Hook 可行性结论

> 日期：2026-10-28　目标：《点击魔王》v5.9.2 (IL2CPP arm64-v8a) on MuMu 12 x86_64

## 一、结论（有 tombstone 硬证据）

**frida(x86_64 frida-server) 可以对 ARM 进程 `Interceptor.attach` 且不立刻报错，
但控制流执行到被 patch 的指令时立即 `SIGILL` 崩溃。**

日志证据（`/sdcard/Android/data/game.taptap.HQGAMES.TapDemons/files/tombstone_00`）：

```
signal 4 (SIGILL), code 0 (SI_USER)
pc  0000000008b1b720     <- 被 hook 的地址（ES3Writer.Create）
lr  0000000008e422d4
backtrace:
  #00 pc 000000000174b720   libil2cpp.so   <- RVA 0x174B720 = ES3Writer.Create
  #01 pc 0000000001a722d0   libil2cpp.so   <- RVA 0x1A722D0，紧邻 ES3.Save<object> @0x1A722C8
  #02 pc 00000000018a7634   libil2cpp.so   <- RVA 0x18A7634，ShuJuDate.Init 尾部
  #03 pc 00000000018a710c   libil2cpp.so   <- 0x18A710C，ShuJuDate.SaveGame 附近
```

**backtrace 里的 pc 打印的是 RVA，不是绝对地址。**

## 二、base 到底是多少

由 `pc 0x08b1b720`（绝对）与 `RVA 0x174b720` 反推：

```
base = 0x08b1b720 - 0x174b720 = 0x073D0000
```

**`0x073D0000` 是正确的 load base。** 之前中途怀疑的 `0x07354000`、`0x7d3964715000` 都是错的。

- `0x07354000` 是 `libil2cpp.so` **首个 r--p 段**（file off 0）的起点，但 ELF 的 `p_vaddr`
  与运行时基址不相等，so 被拆成十余段分别 mmap，`0x073D0000` 正好落在第一段内部。
- `0x7d3964715000` 是 **x86 翻译层输出的另一份镜像**，内存扫描能命中部分函数，
  但不是 ARM 侧执行流使用的地址，且生命周期不稳定（切后台后消失）。

## 三、为什么之前二十多次 hook 全部"装入成功但零命中"

分两种失败：

| 失败类型 | 现象 | 原因 |
|---|---|---|
| 地址错 | `attached ok: true` + 永不命中 | 用了 `0x07354000` / `0x7d39...` 之类错误 base |
| 地址对 | `attached ok: true` + 执行即 SIGILL | ARM 代码位于**翻译层的输入区**，frida 的 x86 inline hook 写进去后被翻译层执行崩溃 |

`0x174B720` 落在 `08b1b000-08b1c000 r-xp`（仅 4KB）——那是 **ARM stub 区**，不是常规代码段。
主体代码在 `08b1c000-08e3f000 r--p`（**只读、不可执行**）→ MuMu 把 ARM 代码当**数据**喂给翻译层，
CPU 从不直接执行 ARM 指令。因此：
- **`frida` 的 inline hook（写 ARM 指令）从根本上没有被执行的机会**；
- 上次之所以崩，是翻译层对该区域做了特殊处理，写入破坏了翻译层元数据。

## 四、可行的替代路线（按性价比排序）

### A. ES3 口令静态求解（继续做，无需运行时）★推荐
已完整还原加密管道（见 docs / 之前记录）：
```
key = PBKDF2-HMAC-SHA1(password_utf8, salt, iterations=100, dkLen=16)
算法 AES-128-CBC + PKCS7
布局 salt(16) + iv(16) + cipher
```
缺的只是 `password`。已知在 `SaveManager..ctor` @ `0x17A64D8` 里通过
`ES3Settings..ctor(this, 1, password)` 传入，password 来自静态字段槽
`[0x35e7000+0x408]`。该槽在 `.data` 段（file off `0x3639000`），**文件里全为 0**，
运行时由 `il2cpp_codegen_initialize` 系列填充。

→ 下一步应**静态反汇编给该槽写值的代码**（`adrp 0x35e7000` + `str` 模式扫描），
而不是运行时 hook。

### B. 换用支持 ARM 的调试通道
- **GDB/gdbserver（arm64 版）**：在翻译层下同样受制，不推荐。
- **真机 ARM64**：唯一能零障碍跑 frida 的方案。
- **MuMu 的 arm 引擎版本**：`MuMuManager info` 显示当前是 `x64-release`，
  存在为 ARM 应用准备的纯 arm 实例模式，值得尝试。

### C. 内存 dump 后离线解（不需要 hook）
存档写入时，明文一定短暂存在于进程堆里。已知 `ES3Writer` 会拼出完整 JSON 字符串。
→ 在存档时刻 dump 整个 Java/Unity 堆（`rw-` 大段），按 `{"DateID"` 或 `$` 分隔特征
直接捞明文。**这一步不依赖任何 hook，成功率最高，且已具备全部前置（root + dd）。**

### D. 放弃运行时，回到"改存档 + 伪造密文"
在拿到 password 之前不可行。拿到后 A/C 任一即可闭环。

## 五、环境事实速查

```
MuMu 12  MuMuPlayer 5.27.4.3536  engine=nemux
adb      E:\Program Files\Netease\MuMu\nx_main\adb.exe   127.0.0.1:16384
root     MuMuManager sh -v 0 -c "..."   (uid=0)
包名     game.taptap.HQGAMES.TapDemons
进程名   点击魔王（TapTap测试版）   ← 中文，按 ASCII 名匹配会失败
存档     /sdcard/Android/data/game.taptap.HQGAMES.TapDemons/files/SaveFile.es3
Unity    2022.3.62f2c1  Release  il2cpp  arm64-v8a
abi     ro.product.cpu.abilist = x86_64,arm64-v8a,x86,armeabi-v7a,armeabi
```

`libil2cpp.so` 段布局（`/proc/PID/maps`，file off 与 vaddr 不同）：
```
07354000-08787000 r--p 00000000
0878a000-08b14000 r--p 01432000
08b14000-08b15000 r-xp 017bc000   <- 4KB stub
08b15000-08b1b000 r--p 017bd000
08b1b000-08b1c000 r-xp 017c3000   <- 4KB stub，0x174B720 落在这里
08b1c000-08e3f000 r--p 017c4000   <- ARM 主体代码（不可执行！）
08e3f000-08e40000 r-xp 01ae7000
08e40000-08e41000 r--p 01ae8000
08e41000-08e42000 r-xp 01ae9000
08e42000-0a775000 r--p 01aea000
0a778000-0a996000 r--p 0341c000
0a999000-0abb2000 rw-p 03639000   <- .data，静态字段槽在这里
```

## 六、本轮新增脚本

| 脚本 | 用途 |
|---|---|
| `frida_open.py` | hook libc open/openat/fopen，抓 .es3 打开者 |
| `frida_verify_base.py` | 比对内存字节 vs 文件字节，判定 base 是否正确 |
| `frida_verify2.py` | 多候选 base 批量校验 |
| `frida_findbase.py` | 用 6 个函数中部指纹全局 scan 定位 base 候选 |
| `frida_realtime.py` | 自动求 base + hook get_location/Save/BaoCunDate |
| `frida_getlocation.py` | 单独 hook ES3Settings.get_location（一切 ES3 读写必经点） |
| `base_finder_note.py` | base 推导方法备忘 |
