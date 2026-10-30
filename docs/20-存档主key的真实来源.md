# docs/20 — 存档主 key 的真实来源（推翻旧论断）

> 结论先行：**存档主 key 不是随机哈希，而是 `ShuJuDate.playerZhangHao`**。
> 旧记录里「随每次保存变化、生成规则未解出」是**槽名被截断**造成的错觉。
> 这意味着「从零构造存档」在技术上已经没有障碍。

## 一、旧论断与它错在哪

`HANDOVER.md`（2026-10-30 版）§五之二 原文：

> 存档主 key 是个**随每次保存变化的哈希名**
> （`o74JUkh9jw==` → `o2D+pAPsvrXCo74JUkh9jw==`），生成规则**未解出**。

观察到的事实本身没错，对「变化」的解释错了：

| 观察 | 当时解释 | 实际原因 |
|---|---|---|
| `SaveFile_device_orig.es3` 槽名是 24 字符 `o2D+pAPsvrXCo74JUkh9jw==` | — | 完整值 |
| `SaveFile_live.es3` 里有两个槽：12 字符 `o74JUkh9jw==` + 32 字符 `1wQ0d2jg...` | 以为是「新随机名」 | **游戏写入时槽名被截断**，12 字符只是 24 字符值的尾巴 |

关键对照：`o2D+pAPsvrXCo74JUkh9jw==` base64 解码 = 16 字节
`a360fea403ecbeb5c2a3be0952487d8f`，而 `o74JUkh9jw==` 解码 = 7 字节 `a3be0952487d8f`
—— **后者正是前者的最后 7 字节**。9 字节前缀 `a360fea403ecbeb5c2`（`o2D+pAPsvrXC`）
被丢掉了。

## 二、证据链（三条独立确认）

### 2.1 `PlayerData.GetID @ 0x1896030` 是纯转发

```asm
0x1896054:  adrp  x8, #0x35e7000
0x1896058:  ldr   x8, [x8, #0x8a0]     ; ShuJuDate.<Instance> 静态字段
0x189605C:  ldr   x8, [x8]             ; → 单例实例（MonoBehaviour）
0x1896060:  ldr   x8, [x8, #0xb8]      ; → gameDate（序列化数据对象）
0x1896064:  ldr   x0, [x8]             ; → 首字段 playerZhangHao
0x1896068:  cbz   x0, #0x1896078       ; null → 抛 NRE
0x1896070:  ldp   x30, x19, [sp], #0x10
0x1896074:  b     #0x18a6e98           ; tail call get_PlayerZhangHao()
```

`[x8]` 这个偏移 0 的字段，按 `ShuJuDate`（TypeDefIndex 3052, dump.cs:262692）的
字段布局，第一个序列化字段就是 `playerZhangHao`（`// 0x28`，但 `gameDate` 是独立的
序列化载体，其首字段为 `playerZhangHao`）。

**整个函数里没有任何 `GetHashCode` / `MD5` / `Random` / `Base64` 调用**，
只有三次 `ldr` 加一次尾调用。

### 2.2 `BaoCunDate @ 0x18A71B4` 的调用点

函数尾部（`0x18A75C8` 起）是拼装 + 加密 + 落盘的完整流程：

```asm
0x18A75C8:  bl       #0x18a89d0   ; ZhuanHuanString(string[] strArr) — 拼接 14 段
0x18A75CC:  ldr      x2, [x21]    ; x2 = key（静态串 @0x35EE2B0）
0x18A75D0:  mov      x1, x0
0x18A75D4:  bl       #0x18a8a68   ; Encrypt(string SourceText, string key)
0x18A75D8:  str      x0, [x19, #0x40]!   ; → ShuJuDate.gameDateStr (+0x40)

0x18A7608:  bl       #0x1892cec   ; PlayerData.GetInstance()
0x18A7614:  bl       #0x1896030   ; ★ PlayerData.GetID()
0x18A761C:  adrp     x8, #0x35ee000
0x18A7620:  ldr      x8, [x8, #0x2a8]    ; 方法槽（ES3.Save 的静态引用）
0x18A7624:  ldr      x2, [x19]           ; x2 = gameDate（ES3 写入器）
0x18A7628:  mov      x1, x0              ; x1 = GetID() 返回值 ← 作为 key
0x18A762C:  mov      x0, x20
0x18A7630:  ldr      x3, [x8]
0x18A7634:  bl       #0x1d184c8         ; ES3.Save(key, value)
```

`x1 = GetID()` 直接作为 ES3 写入的 key，**没有经过任何变换**。

### 2.3 运行时实锤

`PlayerPrefs` 与 logcat 交叉印证（见 docs/14 §2.3）：

```xml
<!-- /data/data/game.taptap.HQGAMES.TapDemons/shared_prefs/*.v2.playerprefs.xml -->
<string name="UJHJKOikhS">o2D%2BpAPsvrXCo74JUkh9jw%3D%3D</string>
```

URL 解码 = `o2D+pAPsvrXCo74JUkh9jw==`，与 TapTap SDK 上报的
`"anti_addict_user_identifier":"o2D+pAPsvrXCo74JUkh9jw=="` 完全一致，
也与存档桶里的 string 槽名完全一致。

## 三、完整链路

```
TapTap 登录 → anti_addict_user_identifier = "o2D+pAPsvrXCo74JUkh9jw=="
                          ↓
        ShuJuDate.SetZhangHao(z, m)  →  PlayerPrefs["UJHJKOikhS"] = z
                          ↓
              ShuJuDate.playerZhangHao = z
                          ↓
    BaoCunDate: ES3.Save(PlayerData.GetID(), gameDateStr)
                          ↓
        SaveFile.es3 桶内 string 槽名 = "o2D+pAPsvrXCo74JUkh9jw=="
```

**账号名（`UJHJKOikhS` 的值）是唯一决定槽名的输入。**

## 四、顺带解出的第二个函数：昵称校验

紧随 `GetID` 之后（`0x1896080` 起）是一个字符串校验函数，用连续 `IndexOf` 探测
非法字符，命中即跳 `0x18961D8`（拒绝）。探测的字符码点：

| 码点 | 字符 | 码点 | 字符 |
|---|---|---|---|
| `0x20` | 空格 | `0x25` | `%` |
| `0x21` | `!` | `0x5e` | `^` |
| `0x40` | `@` | `0x26` | `&` |
| `0x23` | `#` | `0x2a` | `*` |
| `0x24` | **`$`** | `0x2f` | `/` |
| | | `0x7c` | `\` |

**`$` 在禁用列表里**（`0x1896130: IndexOf(0x24)`）—— 这正是 14 段存档用的
`SEP = "$"`。昵称禁止 `$` 是设计自洽约束：否则 `ZhuanHuanString` 拼出来的
段落会被错误切分。同理 `!@#$%^&*/` 中 `|` 也在内。

> 推论：如果哪天要让昵称含 `$`，必须同时改 `SEP`，否则存档直接坏掉。

## 五、可复用脚本

`scripts/probe_taptap_login.py`（D1，本轮新增）
—— 探测 `qingQiu_Tap.asp` 与 `qingQiu.asp` 的行为差异。

本轮 D1 实测结果（2026-10-30）：

| qingQiuID | `qingQiu.asp` | `qingQiu_Tap.asp` |
|---|---|---|
| 0 | `2` | `0` |
| 1 | `?` | `0` |
| 2 | `?` | `0` |
| 100 | `111` | `0` |
| 111 / 222 / 333 | `?` | `0` |
| GET | `-1` | `-1` |

**`qingQiu_Tap.asp` 对任何输入恒返回 `0`**，而返回码表里 `0` 落在
「错误！！」分支（只有 `222`/`111` 进游戏）。→ **TapTap 通道与自建账号通道同样已废**。

附带发现：`qingQiu.asp` 的 `qingQiuID=100` 这次返回 `111` 而非 docs/18 记的 `222`
—— 两者在代码里都直接进游戏，不影响结论，但说明**服务器有会话态**。

## 六、对「新建存档」的意义

旧结论认为新建存档不可能，因为槽名未知。现在已知：

1. 槽名 = 账号名（`playerZhangHao`）
2. `_Key` 的值 = `key_counter`（原档 2640），游戏自增
3. 7 个 `*ShuChu_Key` 计数器初值 0
4. salt/iv 必须复用（docs/19）

→ **给定一个账号名，就能完整拼出一个游戏可读的存档**，不需要任何现有文件。

但注意 docs/14 §二：账号在黑名单时，`heiMingDan` 流程会清档，
所以「新建存档」只在**未封禁账号**上有意义。
