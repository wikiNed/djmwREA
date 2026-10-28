"""下载 JDK 25 Windows x64 zip。多源尝试。"""
import sys
import urllib.request

URLS = [
    # Oracle JDK 25 GA (needs license accept param)
    "https://download.oracle.com/java/25/latest/jdk-25_windows-x64_bin.zip",
    # Microsoft OpenJDK 25 (aka.ms 短链)
    "https://aka.ms/download-jdk/microsoft-jdk-25.0.5-windows-x64.zip",
    "https://aka.ms/download-jdk/microsoft-jdk-25.0.4-windows-x64.zip",
    # Adoptium
    "https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25%2B36/OpenJDK25U-jdk_x64_windows_hotspot_25_36.zip",
]

OUT = r"E:\DSH\game\.rea-study\jdk\jdk25.zip"

hdr = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "*/*",
}

for u in URLS:
    try:
        print("trying:", u)
        req = urllib.request.Request(u, headers=hdr)
        with urllib.request.urlopen(req, timeout=60) as r:
            total = r.headers.get("Content-Length")
            ctype = r.headers.get("Content-Type")
            print("  status", r.status, "type", ctype, "len", total)
            if total and int(total) < 1_000_000:
                print("  too small, skip")
                continue
            with open(OUT, "wb") as f:
                n = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    n += len(chunk)
                    if n % (50 << 20) < (1 << 20):
                        print(f"   {n/1e6:.0f} MB", flush=True)
        print("OK ->", OUT, n)
        sys.exit(0)
    except Exception as e:
        print("  fail:", type(e).__name__, e)
        continue

print("all sources failed")
sys.exit(1)
