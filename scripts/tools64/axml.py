import zipfile, struct, sys

def parse_axml(data):
    # header
    assert struct.unpack_from('<H', data, 0)[0] == 0x0003
    pos = 8
    strings = []
    resmap = []
    out = []
    while pos < len(data):
        typ, hsz, sz = struct.unpack_from('<HHI', data, pos)
        if typ == 0x0001:  # string pool
            cnt, styc, flags, sstart, sstyle = struct.unpack_from('<IIIII', data, pos+8)
            offs = struct.unpack_from('<%dI' % cnt, data, pos+hsz)
            base = pos + sstart
            utf8 = bool(flags & 0x100)
            for o in offs:
                p = base + o
                if utf8:
                    # u16len, u8len
                    n = data[p]; p += 1
                    if n & 0x80: p += 1
                    m = data[p]; p += 1
                    if m & 0x80:
                        m = ((m & 0x7f) << 8) | data[p]; p += 1
                    strings.append(data[p:p+m].decode('utf-8', 'replace'))
                else:
                    n = struct.unpack_from('<H', data, p)[0]; p += 2
                    if n & 0x8000:
                        n = ((n & 0x7fff) << 16) | struct.unpack_from('<H', data, p)[0]; p += 2
                    strings.append(data[p:p+n*2].decode('utf-16-le', 'replace'))
        elif typ == 0x0180:  # resource map
            n = (sz - hsz)//4
            resmap = list(struct.unpack_from('<%dI' % n, data, pos+hsz))
        elif typ == 0x0102:  # start element
            ns, name, astart, asize, acount = struct.unpack_from('<IIHHH', data, pos+16)
            el = strings[name]
            attrs = []
            for i in range(acount):
                a = pos + 16 + astart + i*asize
                ans, aname, rawv, tsz, rsv, dtype, dval = struct.unpack_from('<IIIHBBI', data, a)
                an = strings[aname] if aname < len(strings) else '?'
                val = None
                if dtype == 3:
                    val = strings[dval] if dval < len(strings) else None
                elif dtype == 0x10:
                    val = dval
                elif dtype == 0x12:
                    val = bool(dval)
                rid = resmap[aname] if aname < len(resmap) else 0
                attrs.append((an, rid, val))
            out.append((el, attrs))
        pos += sz
    return out

apk = r'E:\DSH\game\djmwREA\files\old\djmw_5.5.7.apk'
with zipfile.ZipFile(apk) as z:
    data = z.read('AndroidManifest.xml')
els = parse_axml(data)
for el, attrs in els:
    if el in ('manifest','uses-sdk','application','uses-permission'):
        keep = [(n,hex(r),v) for n,r,v in attrs if n in ('package','versionCode','versionName','minSdkVersion','targetSdkVersion','compileSdkVersion','extractNativeLibs','debuggable','platformBuildVersionCode')]
        print(el, keep if keep else '')