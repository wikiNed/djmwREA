# 内层 DES 填充：为什么改过的存档会让游戏卡在标题页

> 结论先行：**内层 DES 必须用 PKCS7 填充**。用 NUL 填充会在游戏侧抛
> `CryptographicException: Bad PKCS7 padding`，游戏卡死在标题页且不留可见痕迹。
> 修复提交：`d412971`（`scripts/es3save.py`）。

## 1. 症状

推送修改后的存档、启动游戏后：

- 画面停在标题页（「点击魔王」logo + TapTap 登录按钮），**帧完全冻结**
- 存档 `mtime` 不更新 —— 说明游戏根本没走到回写存档那一步
- `adb shell pidof` 有进程，`mCurrentFocus` 正常是 `UnityPlayerActivity`
- **没有** `FormatException`（ES3 层解密是成功的）

第一反应会怀疑：改的值不合法 / 新 salt-iv 被拒 / SELinux 标签 / mtime / 文件大小。
**以上全部不是原因。**

## 2. 决定性证据：logcat 里的 CryptographicException

```
E Unity : CryptographicException: Bad PKCS7 padding. Invalid length 0.
E Unity :   at Mono.Security.Cryptography.SymmetricTransform.ThrowBadPaddingException(...)
E Unity :   at System.Security.Cryptography.CryptoStream.FlushFinalBlock()
E Unity :   at ShuJuDate.DesDecrypt (System.String DecryptText, System.String sKey)
E Unity :   at ShuJuDate.LoadGame ()
E Unity :   at ChuangJianPlayer.DengLuChengGong ()
E Unity :   at TapDengLuUI+<TapDengLu>d__17.MoveNext ()
```

调用链说明：AES 层（ES3）已经解密成功，**失败发生在最内层的 DES 解密**，
位置是 `ShuJuDate.DesDecrypt`。该方法走 `CryptoStream` + `PaddingMode.PKCS7`，
末字节校验不通过就抛异常，`LoadGame()` 直接中断，协程不返回，
于是 `DengLuChengGong()` 之后的 UI 流程永远不执行 —— 表现为标题页冻结。

## 3. 原档的实际填充

```
des ct len: 38184
pt len:     38184
pt tail 16: b'ingJia":0}\x06\x06\x06\x06\x06\x06'
last byte:  6
JSON end:   b'ianID":"","ChaiFengID":"","IsPingJia":0}'
```

明文 38178 字节，`38178 % 8 = 2`，需要补 **6** 字节 → 补的是 **6 个 `0x06`**。
这是标准 PKCS7。游戏侧的要求很明确，没有自定义。

## 4. 错误实现的由来

`scripts/es3save.py` 早期的 `des_encrypt` 是这么写的：

```python
if len(plain) % 8:
    plain = plain + b"\0" * (8 - len(plain) % 8)   # ← 补 NUL
```

对应的 `des_decrypt` 还留了一段把结论说反的注释：

> 实测明文尾部填充是 `\x04\x04\x04\x04`（4 个 0x04），
> 说明游戏给 CryptoStream 传的 PaddingMode 让最后一字节是填充长度，
> 但 38144 是 8 的整数倍 —— 填充长度本来就该是 8 才对。

那段注释里引用的 `38144` 和 `\x04\x04\x04\x04` 来自**另一次解出来的中间态**，
不是原档的真实尾部；据此推出「原文件本来就是 8 对齐的」是错的。
实测原档明文 38178 字节、尾部 6 个 `0x06`，与「8 对齐」的说法矛盾。

`des_decrypt` 本身按「末尾 n 个相同字节就剥」实现，**语义上恰好就是 PKCS7**，
所以读取一直是对的 —— 错的只有加密方向。这也解释了为什么
`read_save()` 往返测试一直「通过」而推送后游戏崩溃：
自检用的是自己的 encrypt 再自己的 decrypt，两边都错反而对上了。

## 5. 修复

```python
def des_encrypt(plain: bytes, key: str = DES_KEY) -> str:
    kb = key.encode("ascii")[:8].ljust(8, b"\0")
    plain = pad(plain, 8)          # PKCS7，与游戏 CryptoStream 一致
    ct = DES.new(kb, DES.MODE_CBC, kb).encrypt(plain)
    return ct.hex().upper()
```

`des_decrypt` 保留 PKCS7 剥离，非法时退化为 `rstrip(b"\x00")`，
以兼容早期按 NUL 填充生成的历史文件（读得进来就行，写出去一律用 PKCS7）。

修复后 `des_encrypt(read_save(orig))` 得到 hex 长度 **76368**，
与真机原档的 slot 长度完全一致，此前是 76370（多出 2 个字符 = 1 个 NUL 字节）。

## 6. 对照实验（证明根因，也记录排除项）

| 推入的档 | 内容 | 画面 | logcat |
|---|---|---|---|
| `device_orig.es3` | 真机原档，未过 savedit | 正常进游戏 | 无异常 |
| `t0_none.es3` | **一个值都不改**，只 `load→dump→encrypt` | 卡死 | 无 FormatException |
| `fix_bao1.es3` | `BaoShiSuiPian` 0→1，等长替换 | 卡死 | — |
| `fix_bao.es3` | `BaoShiSuiPian` 0→88888 | 卡死 | — |
| `fix_bao.es3`（**修复后**） | 同上 | **正常进游戏** | 无异常 |
| `SaveFile_final.es3`（修复后） | 三项全改（碎片/黄金树/90 只宠物） | **正常进游戏** | 无异常 |

`t0_none` 是关键：它证明**卡死与「改了什么值」完全无关**，
只要重新封包就会卡死 → 问题一定在封包环节。
「0→1 等长替换」进一步排除数值大小与长度。

## 7. 排掉的其他假设（别再走一遍）

| 假设 | 否证方式 |
|---|---|
| 新随机 salt/iv 会被游戏拒绝 | 用原档 salt/iv 重封仍然卡死；游戏自己回写时也换了新 salt |
| 改的值触发游戏逻辑异常 | `t0_none` 一值不改照样卡死 |
| `88888` 超出字段类型上限 | `0→1` 同样卡死 |
| mtime / 文件大小 / SELinux 标签 | 原档走同一套 `push_save.py` 推送后正常进游戏 |
| 浮点末位精度（`...235`→`...234`） | 确实存在，但只造成明文差异，不是卡死原因 |

## 8. 排查方法论（可复用）

1. **先拿一份能用的基线**。真机原档先推一遍确认能进游戏，
   否则后面所有「卡死」都分不清是改动引起还是环境本来就有问题。
2. **零改动重封包**（`t0_none`）。这一步把「内容问题」和「封装问题」切开，
   是整个排查里性价比最高的一次实验。
3. **看 logcat，不要猜**。`CryptographicException` 一直躺在日志里，
   但 `FormatException` 没出现，容易误判成「解密成功、逻辑出错」。
   `adb logcat -d | Select-String 'Exception'` 是必做项。
4. **越界对照**。把原档尾部字节打出来直接看填充值，
   比读代码里的注释可靠 —— 注释可能是错的（本例就是）。
5. **自检要交叉**。只用自己 encrypt + 自己 decrypt 做往返，
   两边同时错也会「通过」。要么对比真机原档的密文长度，
   要么让游戏自己判定（推上去实测）。

## 9. 相关文件

- `scripts/es3save.py` — `des_encrypt` / `des_decrypt`（本次修复）
- `scripts/push_save.py` — 推送后修复 SELinux MLS 类别，否则游戏读不到
- `scripts/es3_reencrypt.py` — `--same-key` 自检、`splice` 用基准档 salt/iv 重加密
- `docs/11-存档双层加密还原.md` — 两层加密结构（AES 外层 + DES 内层）
- `docs/12-存档编辑速查.md` — 面向使用者的操作流程
