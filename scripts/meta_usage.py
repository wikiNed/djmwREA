"""定位 metadata usage 槽编号，反查其指向的字符串字面量。

IL2CPP 生成代码的模式是：
    ldr x0, [x28_locals_metadataSlots_ + N]  或
    adrp xN, page; ldr xN,[xN+off]  -> MetadataUsage slot
每个 slot 里有 (encodedSourceIndex, encodedType)。运行时由
il2cpp_codegen_initialize_runtime_metadata 把 slot 填成
Il2CppMetadataUsage -> 真实指针。

我们已有 metadata 的 stringLiteral 表。如果能算出 slot 的序号，
就能配合 metadataUsagePairs 表找到对应 literal index。
"""
from paths import META

import struct
data = open(META, "rb").read()
hdr = struct.unpack_from("<64i", data, 0)

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
    "imagesOffset", "imagesCount",
    "assembliesOffset", "assembliesCount",
]
H = {names[i]: hdr[i] for i in range(len(names))}

print("=== 全 header ===")
for k, v in H.items():
    if k in ("sanity", "version"):
        continue
    print(f"  {k:<40} {v:>10} {v:#x}")

# metadataUsage 表（v31: metadataUsageOffset / metadataUsageCount）
# 尝试按 v27+ 命名推测：在 0x40 之后还有更多字段
n = len(data)
print("\n=== 扫描所有 offset/count 对，找可能的 usage 表 ===")
for i in range(2, 120, 2):
    if i + 1 >= len(hdr):
        break
    off, cnt = hdr[i], hdr[i + 1]
    if off <= 0 or cnt <= 0:
        continue
    if off + cnt > n:
        continue
    if cnt % 8 == 0 and cnt >= 8:
        end = off + cnt
        print(f"  hdr[{i:>3}] off={off:#x} cnt={cnt:#x} cnt/8={cnt//8}")
