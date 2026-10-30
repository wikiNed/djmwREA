"""仓库路径解析：让所有脚本在任意机器上都能找到 files/ 下的大文件。

用法：
    from paths import SO, DUMP, META, APK, SAVES, WORK
    from paths import find, dump_rva_map

优先级：环境变量 > 仓库内 files/ > 原始开发机路径（仅兜底）。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FILES = REPO / "files"

# 开发机上的原始位置，仅作最后兜底，方便原作者本机继续用。
# 设 REA_NO_LEGACY=1 可禁用这个兜底，用来验证「在干净机器上也能跑」——
# 否则本机验证会被兜底掩盖，看不出是不是真有隐藏依赖。
_LEGACY = Path(r"E:\DSH\game\.rea-study")
_USE_LEGACY = os.environ.get("REA_NO_LEGACY", "") not in ("1", "true", "yes")


def _pick(rel: str, env: str, legacy: str | None = None) -> Path:
    """按 环境变量 > 仓库 files/ > 开发机路径 的顺序找文件。"""
    v = os.environ.get(env)
    if v:
        p = Path(v)
        if p.exists():
            return p
        raise FileNotFoundError(f"{env}={v} 指向的文件不存在")
    p = FILES / rel
    if p.exists():
        return p
    if legacy and _USE_LEGACY:
        lp = _LEGACY / legacy
        if lp.exists():
            return lp
    return p  # 返回期望路径，由调用方给出友好报错


def _pick_dir(rel: str, env: str, legacy: str | None = None) -> Path:
    v = os.environ.get(env)
    if v:
        return Path(v)
    p = REPO / rel
    if p.exists():
        return p
    if legacy and _USE_LEGACY:
        lp = _LEGACY / legacy
        if lp.exists():
            return lp
    return p


# ---- 主要产物 ----
SO = _pick("libil2cpp.so", "IL2CPP_SO", r"lib\libil2cpp.so")
DUMP = _pick("dump.cs", "IL2CPP_DUMP", r"dump\dump.cs")
META = _pick("global-metadata.dat", "IL2CPP_META", r"lib\global-metadata.dat")
APK = _pick("TapDemons_v5.9.2.apk", "TAPDEMONS_APK", r"apk\TapDemons_v5.9.2.apk")

# ---- 目录 ----
SAVES = _pick_dir("saves", "REA_SAVES", r"saves")
WORK = _pick_dir("work", "REA_WORK", r"work")
EVIDENCE = _pick_dir("evidence", "REA_EVIDENCE", r"evidence")
EMU = _pick_dir("emu", "REA_EMU", r"emu")
#: 从 data.unity3d 导出的 TextAsset 模板（playerDate_03 等官方存档骨架）
TEMPLATES = EVIDENCE / "templates"

# ---- 常见派生文件（避免各脚本重复拼路径）----
# 模拟器上拉下来的真实存档（ES3 AES 加密）
ES3_FILE = EMU / "SaveFile.es3"
# 内存 dump 与解密中间产物
MEMDUMP = EMU / "memdump.bin"
SAVE_PLAIN = EMU / "save_plain.json"


def unity_data_asset(cache_dir: Path | None = None) -> Path:
    """取得 APK 内的 Unity 资源包 data.unity3d。

    优先用已解出的副本（assets/data.unity3d 或缓存目录），
    没有再直接从 APK 里提取一次并缓存到 work/assets/ 下。

    这样仓库不必入库 10MB 的 data.unity3d —— 它本来就在 APK 里。
    """
    import zipfile

    candidates = [REPO / "assets" / "data.unity3d"]
    if _USE_LEGACY:
        candidates.append(_LEGACY / "assets" / "data.unity3d")
    for c in candidates:
        if c.exists():
            return c

    # work/ 下的缓存优先于重新解包（解 20MB 每次都要几秒）
    out_dir = cache_dir or (WORK / "assets")
    out = out_dir / "data.unity3d"
    if out.exists():
        return out

    if not APK.exists():
        raise FileNotFoundError(
            f"找不到 APK（{APK}），无法提取 data.unity3d。\n"
            f"请先 git lfs pull，或设置 TAPDEMONS_APK 指向 APK。"
        )

    # APK 内路径：assets/bin/Data/data.unity3d
    with zipfile.ZipFile(APK) as z:
        names = [n for n in z.namelist() if n.endswith("data.unity3d")]
        if not names:
            raise FileNotFoundError(f"{APK} 内没有 data.unity3d")
        out_dir.mkdir(parents=True, exist_ok=True)
        with z.open(names[0]) as src, open(out, "wb") as dst:
            while True:
                buf = src.read(1 << 20)
                if not buf:
                    break
                dst.write(buf)
    return out

# ---- ES3 加密常量（已由反汇编证实，见 docs/05、docs/07）----
ES3_SALT_LEN = 16
ES3_IV_LEN = 16
ES3_ITERATIONS = 100          # Rfc2898DeriveBytes(password, salt, 100)
ES3_KEYLEN = 16               # GetBytes(16) -> AES-128

# ---- 关键方法 RVA（来自 dump.cs，已逐指令核对）----
RVA = {
    "SaveManager..ctor": 0x17A64D8,
    "SaveManager.get_Instance": 0x17A5D84,
    "ES3Settings..ctor(EncryptionType,string)": 0x175226C,
    "AESEncryptionAlgorithm.Encrypt(Stream)": 0x1782D44,
    "AESEncryptionAlgorithm.Decrypt(Stream)": 0x178329C,
    "Rfc2898DeriveBytes..ctor(string,byte[],int)": 0x27A87E0,
    "ShuJuDate.SaveGame": 0x18A7034,
    "ShuJuDate.BaoCunDate": 0x18A71B4,
    "ShuJuDate.LoadGame": 0x18A9374,
    "ShuJuDate.Encrypt(string,string)": 0x18A8A68,
}

# ---- ELF 解析（RVA -> 文件偏移，必须按 program header 分段算）----
import struct

PT_LOAD = 1


def parse_phdrs(path=None):
    """返回 [(p_offset, p_vaddr, p_filesz, p_flags)]。"""
    path = path or SO
    segs = []
    with open(path, "rb") as f:
        ident = f.read(16)
        if ident[:4] != b"\x7fELF" or ident[4] != 2:
            raise ValueError(f"{path} 不是 ELF64")
        f.seek(0x20)
        e_phoff = struct.unpack("<Q", f.read(8))[0]
        f.seek(0x36)
        e_phentsize, e_phnum = struct.unpack("<HH", f.read(4))
        for i in range(e_phnum):
            f.seek(e_phoff + i * e_phentsize)
            raw = f.read(e_phentsize)
            p_type, p_flags, p_offset, p_vaddr, _pa, p_filesz = struct.unpack(
                "<IIQQQQ", raw[:40]
            )
            if p_type == PT_LOAD:
                segs.append((p_offset, p_vaddr, p_filesz, p_flags))
    return segs


def rva_to_fileoff(rva, segs=None, path=None):
    """RVA -> 文件偏移。返回 None 表示不在任何可加载段内。"""
    segs = segs or parse_phdrs(path)
    for p_offset, p_vaddr, p_filesz, _fl in segs:
        if p_vaddr <= rva < p_vaddr + p_filesz:
            return p_offset + (rva - p_vaddr)
    return None


def read_rva(rva, size, path=None):
    """从 SO 读出 [rva, rva+size) 的字节。"""
    path = path or SO
    segs = parse_phdrs(path)
    off = rva_to_fileoff(rva, segs, path)
    if off is None:
        raise ValueError(f"RVA 0x{rva:X} 不在任何 PT_LOAD 段内")
    with open(path, "rb") as f:
        f.seek(off)
        return f.read(size)


def dump_rva_map(dump_path=None):
    """解析 dump.cs: RVA -> 方法签名。"""
    dump_path = dump_path or DUMP
    m = {}
    with open(dump_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i, ln in enumerate(lines):
        got = re.search(r"// RVA: 0x([0-9A-Fa-f]+)", ln)
        if got:
            rva = int(got.group(1), 16)
            if rva:
                m.setdefault(rva, lines[i + 1].strip()[:120] if i + 1 < len(lines) else "")
    return m


def require(p: Path, hint: str = ""):
    """断言文件存在，否则给出可操作的报错。"""
    if not Path(p).exists():
        raise FileNotFoundError(
            f"找不到 {p}\n{hint or '请确认已执行 git lfs pull，或放好对应文件'}"
        )
    return Path(p)
