# files/ — 大文件（Git LFS 管理）

本目录存放逆向所需的原始产物。文件通过 **Git LFS** 存储，
克隆时需先装好 Git LFS，否则拿到的只是 133 字节的指针文本。

```bash
git lfs install
git clone https://github.com/wikiNed/djmwREA.git
```

---

## 文件清单

| 文件 | 大小 | SHA256 |
|---|---|---|
| `TapDemons_v5.9.2.apk` | 132.15 MB (138 569 807 B) | `4ce0925fcec7c06b5d50dffd794f699da49643c5c27f86276acee2ac9441e7d1` |
| `libil2cpp.so` | 56.32 MB (59 058 224 B) | `bf781eb1625149de1992f9722b15fde110ee436cbbb20c638280b2e472505a7c` |
| `global-metadata.dat` | 10.16 MB (10 650 796 B) | `b458f3df25e0a5e636700abce1abcda7ad2456826a40ba9fce4af0714b7a7d00` |
| `dump.cs` | 22.03 MB (23 096 652 B) | `db5277a4c5ccc7c8a20b0a85f7785cdd38016dffb6e11b66ab9fe7926a546d37` |

### 校验

```bash
# Linux / macOS
sha256sum -c <<'EOF'
4ce0925fce (略) TapDemons_v5.9.2.apk
EOF

# 直接算
sha256sum files/*
# Windows
Get-FileHash files\* -Algorithm SHA256
```

`libil2cpp.so` 另有 MD5 可用于快速核对（与设备上的文件一致）：
```
MD5 = 3466135958c06c40a50d4fa8bd458d0e
```

---

## 各文件从哪来

### `TapDemons_v5.9.2.apk`
从 TapTap 下载的官方安装包（搜索「点击魔王」）。未做任何修改。

### `libil2cpp.so`
从 APK 的 `lib/arm64-v8a/libil2cpp.so` 解出，直接是原文件。

```bash
unzip -j TapDemons_v5.9.2.apk 'lib/arm64-v8a/libil2cpp.so' -d .
```

### `global-metadata.dat`
从 APK 的 `assets/bin/Data/Managed/Metadata/global-metadata.dat` 解出。

```bash
unzip -j TapDemons_v5.9.2.apk 'assets/bin/Data/Managed/Metadata/global-metadata.dat' -d .
```

### `dump.cs`
用 **Il2CppDumper** 对上面两个文件生成的产物，666 763 行。

```bash
Il2CppDumper.exe libil2cpp.so global-metadata.dat out_dir
# 产物：out_dir/dump.cs
```

**这是全项目最有用的一个文件**——所有字段偏移、方法 RVA 都在里面。
配合 [`docs/09-dump关键类摘录.md`](../docs/09-dump关键类摘录.md) 的方法索引表直接查。

---

## 重要：`RVA` ≠ `Offset`

`dump.cs` 里每个方法都有两个数：

```
// RVA: 0x1782D44 Offset: 0x177ED44 VA: 0x1782D44
```

- **`RVA`** —— hook 用（运行时地址 = `load_base + RVA`）
- **`Offset`** —— 静态读文件用

两者**不相等**，差值随 ELF 段变化（0x4000 / 0x8000）。正确换算：

```
fileoff = RVA - p_vaddr + p_offset      # 按 program header 分段算
```

`libil2cpp.so` 的 program header（`e_phoff = 0x40`）：

| idx | Offset | vaddr | filesz | flags |
|---|---|---|---|---|
| 1 | `0x0` | `0x0` | `0x1432aec` | R-- |
| 2 | `0x1432aec` | `0x1436aec` | `0x1fe97f4` | R-X |
| 3 | `0x341c2e0` | `0x34242e0` | `0x21dbb0` | RW- |
| 4 | `0x3639e90` | `0x3645e90` | `0x218008` | RW- |

直接用 `scripts/disasm_range.py` 可以自动处理这个换算，并回查 `dump.cs` 标注函数名。

---

## 版权

`TapDemons_v5.9.2.apk`、`libil2cpp.so`、`global-metadata.dat` 均为《点击魔王》
版权持有人的作品，此处仅作**逆向技术研究**留存，不用于任何商业目的。
`dump.cs` 是由上述文件派生的分析产物。

如版权方要求，可随时删除本目录。
