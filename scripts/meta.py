"""解析 global-metadata.dat，定位 string literal 表。"""
import struct
import sys

META = r"E:\DSH\game\.rea-study\lib\global-metadata.dat"


def parse_header(data):
    consts = struct.unpack_from("<II", data, 0)
    print("sanity:", [hex(c) for c in consts])
    if consts[0] == 0xFAB11BAF:
        ver = struct.unpack_from("<i", data, 4)[0]
        print("version:", ver)
    # header 是 int32 数组
    n = 40
    hdr = struct.unpack_from("<%di" % n, data, 0)
    names = [
        "sanity",
        "version",
        "stringLiteralOffset",
        "stringLiteralCount",
        "stringLiteralDataOffset",
        "stringLiteralDataCount",
        "stringOffset",
        "stringCount",
        "eventsOffset",
        "eventsCount",
        "propertiesOffset",
        "propertiesCount",
        "methodsOffset",
        "methodsCount",
        "parameterDefaultValuesOffset",
        "parameterDefaultValuesCount",
        "fieldDefaultValuesOffset",
        "fieldDefaultValuesCount",
        "fieldAndParameterDefaultValueDataOffset",
        "fieldAndParameterDefaultValueDataCount",
        "fieldMarshaledSizesOffset",
        "fieldMarshaledSizesCount",
        "parametersOffset",
        "parametersCount",
        "fieldsOffset",
        "fieldsCount",
        "genericParametersOffset",
        "genericParametersCount",
        "genericParameterConstraintsOffset",
        "genericParameterConstraintsCount",
        "genericContainersOffset",
        "genericContainersCount",
        "nestedTypesOffset",
        "nestedTypesCount",
        "interfacesOffset",
        "interfacesCount",
        "vtableMethodsOffset",
        "vtableMethodsCount",
        "interfaceOffsetsOffset",
        "interfaceOffsetsCount",
    ]
    return {names[i]: hdr[i] for i in range(n)}


if __name__ == "__main__":
    data = open(META, "rb").read()
    print("meta size:", len(data), hex(len(data)))
    h = parse_header(data)
    for k in [
        "sanity",
        "version",
        "stringLiteralOffset",
        "stringLiteralCount",
        "stringLiteralDataOffset",
        "stringLiteralDataCount",
        "stringOffset",
        "stringCount",
    ]:
        print(f"  {k}: {h[k]} ({h[k]:#x})")
