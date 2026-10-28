"""解析 data.unity3d 中偏移 15390638 附近的 ES3Defaults MonoBehaviour。

Unity 序列化字符串格式：int32 长度（4字节对齐，含尾部\\0）+ bytes + 对齐填充。
Typetree 被剥离，所以按已知 ES3Defaults 字段顺序手工解析：

ES3Defaults（ES3 源码）:
  public ES3SerializableSettings settings = new ES3SerializableSettings();
  public bool addMgrToSceneAutomatically;
  public bool autoUpdateReferences;
  public bool addAllPrefabsToManager;
  public int serializationDepthLimit;

ES3SerializableSettings（按 ES3Settings 序列化):
  path(string), encryptionType(int), compressionType(int), encryptionPassword(string),
  directory(int), format(int), prettyPrint(bool), bufferSize(int), encoding(int),
  saveChildren(bool), postprocessRawCachedData(bool), typeChecking(bool),
  safeReflection(bool), memberReferenceMode(int), referenceMode(int),
  serializationDepthLimit(int), assemblyNames(string[])
"""
import struct

PATH = r"E:\DSH\game\.rea-study\assets\data.unity3d"
raw = open(PATH, "rb").read()
ANCHOR = 15390638

# 已知 ES3.EncryptionType: None=0, AES=1
# ES3.CompressionType: None=0, Gzip=1
# ES3.Directory: Invalid=0, PersistentDataPath=1, DataPath=2, StreamingAssets=3


def read_string(buf, off):
    (ln,) = struct.unpack_from("<i", buf, off)
    off += 4
    if ln < 0 or ln > 4096 or off + ln > len(buf):
        return None, off
    s = buf[off : off + ln]
    off += ln
    # 对齐到 4 字节
    pad = (4 - (ln % 4)) % 4
    off += pad
    return s, off


print("=== 从 anchor 前后 600 字节做 hexdump+ASCII ===")
start = ANCHOR - 80
chunk = raw[start : ANCHOR + 520]
for i in range(0, len(chunk), 16):
    row = chunk[i : i + 16]
    hx = " ".join(f"{b:02x}" for b in row)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print(f"{start + i:08x}  {hx:<48}  {asc}")

print("\n=== 尝试按字符串序列解析 ===")
off = ANCHOR
for label in ("settingsObjectName", "A", "B", "C", "D"):
    s, no = read_string(raw, off)
    if s is None:
        print(f"{label} @{off}: <not a string>")
        break
    print(f"{label} @{off}: {s[:80]!r} (len={len(s)})")
    off = no
    if label == "D":
        break
