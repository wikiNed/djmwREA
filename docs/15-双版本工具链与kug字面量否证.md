# 15 — 双版本工具链、`kug` 字面量否证

> **更新**：2026-10-29
> **前情**：[docs/14 §3.3](14-封号机制与旧版对比.md) 发现旧版 v5.5.7 用另一套 ES3 口令
> `65w84e4p994z3Oq`，并在「未解疑点」里留了一个 `kug1oghhkt71gstktf`。
> **本文做两件事**：把工具链做成两版通用（`--variant`），顺手把那个疑点彻底否证。

---

## 一、`--variant`：一条命令切换两代加密

### 1.1 为什么值得做

两版存档**结构完全相同** —— 官方模板 `playerDate_03` 在 v5.5.7 与 v5.9.2 里
逐字节一致（104886 B，sha256 `95884f9213c49d7feff151a9…`）。
差异只在**外层 ES3 口令**，内层 DES 的 `PJSQJ678` 两版相同。

所以「支持旧版」在代码上只是一张口令表，不需要任何分支逻辑。

### 1.2 用法

```bash
# 默认就是 TapTap v5.9.2，行为和以前完全一致
python scripts/es3save.py unpack saves/SaveFile_orig.es3 out.json

# 旧版加 --variant 即可，所有命令通用
python scripts/es3save.py verify --variant v5.5.7 legacy.es3
python scripts/savedit.py info      --variant v5.5.7 legacy.es3
python scripts/savedit.py currency  --variant v5.5.7 legacy.es3 --zuanshi 888888

# 查表：顺带核对每个版本的口令与它 metadata 里的字面量是否对得上
python scripts/es3save.py variants
```

`variants` 的实测输出：

```
版本       外层口令                 DES key    metadata 校验
v5.5.7   65w84e4p994z3Oq      PJSQJ678   OK  index 656 == '65w84e4p994z3Oq'
v5.9.2   hqgames@2013         PJSQJ678   OK  index 12153 == 'hqgames@2013'
```

**这一列 `OK` 是活校验**，不是写死的字符串：它现场读对应版本的
`global-metadata.dat`，按 usage index 取出字面量再比对。metadata 换了、
口令改了，这里立刻会变成「不一致」。

### 1.3 两版口令的来源其实不同（这点值得记住）

| | v5.9.2 | v5.5.7 |
|---|---|---|
| 口令 | `hqgames@2013` | `65w84e4p994z3Oq` |
| usage index | **12153** | **656** |
| metadata 里的 `encryptionpassword` 键 | **没有** | **有** |
| 机制 | 硬编码进代码，经 IL2CPP 字面量哨兵 `0xA0005EF3` 间接引用 | 走 ES3 默认配置 `ES3Defaults.encryptionpassword` |
| 字面量表位置 | `off=0x100 size=0x207b8` → 16631 行 | `off=0x100 size=70448` → 8806 行 |
| metadata 大小 | 10650796 | 3728272 |

旧版 metadata 是 **version 27**，header 布局与新版不同（`0x100` 处那对
`(length, offset)` 表的起始位置相同，但 literalData 的基准要单独算：
`base = 0x100 + 70448`）。`scripts/es3save.py:_check_variant()` 里对旧版
单独走了这条路径。

> **教训**：`hqgames@2013` 是「硬编码 + 哨兵」型，`65w84e4p994z3Oq` 是
> 「配置默认值」型。**同一款游戏的两代版本用了两种完全不同的密钥托管方式**，
> 找法自然也不同 —— 不能指望一个脚本通吃。

---

## 二、`kug1oghhkt71gstktf` 已被否证：它不是口令

docs/14 曾把它列为「疑似另一套口令的残留，未验证」。本轮**验证完毕，结论是否定的**。

### 2.1 它确实存在，而且位置很像

在 `files/global-metadata.dat` 里，两者都在 stringLiteral 表中，且都是字典序排列：

```
index 12153 → 'hqgames@2013'      （前: hover  /  后: hr）
index 12597 → 'kug1oghhkt71gstktf'（前: ks_c_5601_1987  /  后: ky）
```

`kug…` 在 `ks_c_5601_1987` 与 `ky` 之间，说明它就是一条普通随机串字面量 ——
托管在 `'k'` 开头的字母序位置，和 `hqgments@2013` 托管在 `'h'` 位置完全同构。
**光看位置无法区分「另一个口令」和「一个恰好存在的随机串」**，必须实测。

### 2.2 实测：13 份存档，全部解不开

对 `saves/` 与 `evidence/saves/` 下全部 `.es3` 逐个试四个候选口令
（判据是解出来的字节像不像 ES3 桶，而不是「没抛异常」）：

| 文件 | 大小 | `hqgames@2013` | `kug1oghhkt71gstktf` | `65w84e4p994z3Oq` | `PJSQJ678` |
|---|---|---|---|---|---|
| `SaveFile.es3` | 76832 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_orig.es3` | 76896 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_live.es3` | 76896 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_device_orig.es3` | 76976 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_pets_all.es3` | 77952 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_banned.es3` | 76560 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_safe.es3` | 76704 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_rich.es3` | 77216 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_lv21.es3` | 77184 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_fix_tree.es3` | 76976 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_after_orig.es3` | 76944 | **OK** | FAIL | FAIL | FAIL |
| `SaveFile_after_safe.es3` | 76560 | **OK** | FAIL | FAIL | FAIL |
| `evidence/SaveFile_live.es3` | 153520 | **OK** | FAIL | FAIL | FAIL |
| `zeros.es3` | 76896 | FAIL（负样本，符合预期） | FAIL | FAIL | FAIL |

**13/13 全 FAIL**，而 `hqgames@2013` 13/13 全 OK（除负样本）。
一个口令只要是对的，就不可能在一份用同代代码加密的档上完全失败。

### 2.3 那它是什么

最可能是 **ES3 内部生成的随机 key** 之一。回忆 ES3 桶的结构：那里本来就有一个
32 字符的 base64 key（`o2D+pAPsvrXCo74JUkh9jw==` 之类）。
`kug1oghhkt71gstktf` 是 18 字符、小写字母+数字，风格与
`hqgames@2013`/`65w84e4p994z3Oq` 同属「随机串」，但长度和字符集都不合 ES3
口令的常见形态。

**目前无法进一步定性**，但也**不影响任何功能** —— 两个真正的口令都已定位并校验。
这条从「未解疑点」降级为「已知非口令」，不再追踪。

### 2.4 复现命令

```bash
python - <<'EOF'
import sys; sys.path.insert(0, 'scripts')
import glob, os, es3save as E
cands = ['hqgames@2013', 'kug1oghhkt71gstktf', '65w84e4p994z3Oq', 'PJSQJ678']
for f in sorted(glob.glob('saves/*.es3') + glob.glob('evidence/saves/*.es3')):
    blob = open(f, 'rb').read()
    row = []
    for pw in cands:
        try:
            pt = E.decrypt_bytes(blob, pw)
            row.append('%s:%s' % (pw[:10], 'OK' if E._looks_like_save(pt) else 'junk'))
        except Exception:
            row.append('%s:FAIL' % pw[:10])
    print('%-40s %7d  %s' % (os.path.basename(f), len(blob), '  '.join(row)))
EOF
```

---

## 三、旧版的验证边界（必须说清）

`--variant v5.5.7` **只用合成档自证过**：

1. 取一份 14 段真实明文（`saves/playerDate_01.json`）；
2. 用 `v5.5.7` 口令封成 `.es3`；
3. 用 `v5.5.7` 解回来 → 字节一致；
4. 用 `v5.9.2`（默认）去解同一份 → 抛 `PasswordError`。

这证明**参数表与代码路径正确**，但**没有**证明「旧版游戏能读回这个档」。
真要做到那一步，需要一份**真实的旧版存档**，而目前手上没有。

旧版本身也不好跑：

* 实名弹窗 `AntiAddictionCore` 在 dex 里，绕不开（[docs/14 §3.5–3.6](14-封号机制与旧版对比.md)）；
* Unity 2020.3.4f1c1 + armv7 + 翻译层，点昵称输入框就 SIGSEGV（[docs/14 §3.7](14-封号机制与旧版对比.md)）。

**所以这一项的定位是「工具链就绪，等样本」，不是「已验证可用」。**

---

## 四、本轮的代码改动

| 文件 | 改动 |
|---|---|
| `scripts/es3save.py` | 新增 `Variant` 类、`V592` / `V557` 常量、`get_variant()` / `_resolve()` / `_check_variant()`；`read_save` / `write_save` / `unwrap_bucket` / `decrypt_bytes` 全部接受 `variant`；新增 `PasswordError`；CLI 加 `--variant` 与 `variants` 子命令 |
| `scripts/savedit.py` | 模块级 `_VARIANT`，主函数摘出 `--variant`；`read_file` / `write_file` 透传 |
| `scripts/peek_literal.py` | 修 docstring 的 GBK→UTF-8 双重编码乱码 |
| `tools/test_savedit.py` | 新增 `[4] 版本变体` 共 11 项断言 |

### 4.1 `PasswordError` 为什么单独定义

AES-CBC **用错口令也会解出等长字节**，只是 PKCS7 校验不过。
早先直接把 `ValueError: Padding is incorrect.` 抛给使用者，很容易被误读成
「文件损坏了」。现在转成带建议的 `PasswordError`，并且**按当前版本给不同的提示**
（用 v5.9.2 失败就提示「可能是旧版，加 `--variant v5.5.7`」；用 v5.5.7 失败则
反过来提示回默认）。

### 4.2 回归

```
python tools/test_savedit.py   → 41 项 ALL PASS（原 30 + 新增 11）
python tools/smoke_test.py     → 3/3 通过
```

新增的 11 项里有两项是**否定断言**（错版本必须抛 `PasswordError`、
v5.9.2 读 v5.5.7 档必须失败）。只有正向断言的测试挡不住「什么都解得开」的实现。

---

## 五、一句话总结

**工具链现在两版通用了：`--variant v5.5.7` 就切旧版，一条命令的事。
那个 `kug…` 字面量也顺手验死了 —— 13 份存档零命中，它不是口令，不用再惦记。**
