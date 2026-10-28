"""解析 metadata v31 的 usage 表，反查 metadata usage 槽 -> 字符串字面量。"""
import struct

META = r"E:\DSH\game\.rea-study\lib\global-metadata.dat"
data = open(META, "rb").read()

hdr = struct.unpack_from("<64i", data, 0)
# v31 header 布局（按 Il2CppGlobalMetadataHeader）
names = [
    "sanity", "version",
    "stringLiteralOffset", "stringLiteralCount",
    "stringLiteralDataOffset", "stringLiteralDataCount",
    "stringOffset", "stringCount",
    "eventsOffset", "eventsCount",
    "propertiesOffset", "propertiesCount",
    "methodsOffset", "methodsCount",
    "parameterDefaultValuesOffset", "parameterDefaultValuesCount",
    "fieldDefaultValuesOffset", "fieldDefaultValuesCount",
    "fieldAndParameterDefaultValueDataOffset", "fieldAndParameterDefaultValueDataCount",
    "fieldMarshaledSizesOffset", "fieldMarshaledSizesCount",
    "parametersOffset", "parametersCount",
    "fieldsOffset", "fieldsCount",
    "genericParametersOffset", "genericParametersCount",
    "genericParameterConstraintsOffset", "genericParameterConstraintsCount",
    "genericContainersOffset", "genericContainersCount",
    "nestedTypesOffset", "nestedTypesCount",
    "interfacesOffset", "interfacesCount",
    "vtableMethodsOffset", "vtableMethodsCount",
    "interfaceOffsetsOffset", "interfaceOffsetsCount",
    "typeDefinitionsOffset", "typeDefinitionsCount",
]
H = {names[i]: hdr[i] for i in range(len(names))}
print("sanity:", hex(H["sanity"] & 0xFFFFFFFF), "version:", H["version"])
for k in ("stringLiteralOffset", "stringLiteralCount", "stringLiteralDataOffset",
          "stringLiteralDataCount", "stringOffset", "stringCount",
          "typeDefinitionsOffset", "typeDefinitionsCount"):
    print(f"  {k} = {H[k]} ({H[k]:#x})")


def read_str(idx):
    """从 string literal 表读第 idx 个字面量。"""
    ln, di = struct.unpack_from("<ii", data, H["stringLiteralOffset"] + idx * 8)
    return data[H["stringLiteralDataOffset"] + di : H["stringLiteralDataOffset"] + di + ln].decode(
        "utf-8", "replace"
    )


for i in (2347, 7398):
    print(f"literal[{i}] = {read_str(i)!r}")
