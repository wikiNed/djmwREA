import struct, sys
import capstone

path = sys.argv[1]
start = int(sys.argv[2], 0)
count = int(sys.argv[3]) if len(sys.argv) > 3 else 40
mode = sys.argv[4] if len(sys.argv) > 4 else "thumb"

data = open(path, "rb").read()
# parse ELF32 program headers
assert data[:4] == b"\x7fELF"
(e_phoff,) = struct.unpack_from("<I", data, 0x1C)
(e_phentsize, e_phnum) = struct.unpack_from("<HH", data, 0x2A)
segs = []
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from("<8I", data, off)
    if p_type == 1:
        segs.append((p_vaddr, p_offset, p_filesz))

def va2off(va):
    for v, o, sz in segs:
        if v <= va < v + sz:
            return o + (va - v)
    return None

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if mode == "thumb" else capstone.CS_MODE_ARM)
md.detail = False
md.skipdata = True
addr = start & ~1
o = va2off(addr)
if o is None:
    print("va not mapped:", hex(addr), [hex(v) for v, _, _ in segs])
    sys.exit(1)
n = 0
for ins in md.disasm(data[o:o + count * 4], addr):
    print("0x%08x  %-8s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
    n += 1
    if n >= count:
        break
