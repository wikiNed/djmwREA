# -*- coding: utf-8 -*-
"""纯 Python 的 APK v1（JAR）签名器 —— 本机没有 JDK 的 jarsigner / apksigner 时用。

背景（docs/31）：这台机器只有 JetBrains Runtime（java/javac/keytool，**没有 jdk.jartool
模块，也没有 apksigner.jar**），而 `git`/GitHub 直连不通，装不了 uber-apk-signer。
于是用 `cryptography` 直接按 JAR 签名规范生成 META-INF/MANIFEST.MF、CERT.SF、
CERT.RSA（PKCS#7 detached + signed attributes），Android 侧的 StrictJarVerifier
认这套。

用法：
    python sign_apk_v1.py <in.apk> <out.apk> [--key work/dshmod.key.pem --cert work/dshmod.cert.pem]

注意：v1 签名对 targetSdk < 30 的包足够；本包 AndroidManifest 里 targetSdkVersion=29，
因此 Android 11+ 也接受（≥30 才强制 v2+）。
"""
import base64
import datetime
import hashlib
import os
import sys
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

SIG_SUFFIXES = ('.SF', '.RSA', '.DSA', '.EC')
MAX_LINE = 72  # JAR 规范：manifest 每行（含续行）不超过 72 字节


def log(*a):
    print(*a)


# ---------------------------------------------------------------- 密钥 / 证书

def load_or_make_key(key_path, cert_path):
    """复用已有 key/cert（同一签名的后续版本可以直接覆盖安装）。"""
    if os.path.exists(key_path) and os.path.exists(cert_path):
        key = serialization.load_pem_private_key(open(key_path, 'rb').read(), None)
        cert = x509.load_pem_x509_certificate(open(cert_path, 'rb').read())
        log('复用密钥 %s' % key_path)
        return key, cert

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'dshmod'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'dshmod'),
        x509.NameAttribute(NameOID.COUNTRY_NAME, u'CN'),
    ])
    cert = (x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime(2020, 1, 1))
            .not_valid_after(datetime.datetime(2050, 1, 1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    os.makedirs(os.path.dirname(key_path) or '.', exist_ok=True)
    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    log('已生成新密钥 %s（证书 2020-2050）' % key_path)
    return key, cert


# ---------------------------------------------------------------- JAR 清单

def _wrap(line):
    """按 72 字节折行，续行以单个空格开头。"""
    out = []
    rest = line
    while len(rest) > MAX_LINE:
        out.append(rest[:MAX_LINE])
        rest = b' ' + rest[MAX_LINE:]
    out.append(rest)
    return b'\r\n'.join(out) + b'\r\n'


def _attr(name, value):
    return _wrap(('%s: %s' % (name, value)).encode('ascii'))


def build_manifest(items):
    """items: [(entry_name, content_bytes)] -> (manifest_bytes, {name: section_bytes})"""
    out = [_attr('Manifest-Version', '1.0'), _attr('Created-By', '1.0 (dshmod)')]
    out.append(b'\r\n')
    sections = {}
    for name, data in items:
        digest = base64.b64encode(hashlib.sha256(data).digest()).decode('ascii')
        sec = _attr('Name', name) + _attr('SHA-256-Digest', digest) + b'\r\n'
        sections[name] = sec
        out.append(sec)
    return b''.join(out), sections


def build_sf(manifest_bytes, sections):
    whole = base64.b64encode(hashlib.sha256(manifest_bytes).digest()).decode('ascii')
    out = [_attr('Signature-Version', '1.0'),
           _attr('Created-By', '1.0 (dshmod)'),
           _attr('SHA-256-Digest-Manifest', whole),
           b'\r\n']
    for name, sec in sections.items():
        digest = base64.b64encode(hashlib.sha256(sec).digest()).decode('ascii')
        out.append(_attr('Name', name))
        out.append(_attr('SHA-256-Digest', digest))
        out.append(b'\r\n')
    return b''.join(out)


def build_pkcs7(sf_bytes, key, cert):
    """detached PKCS#7 SignedData（带 signed attributes），等价于 jarsigner 的 .RSA。"""
    # NoCapabilities 必须加：OpenSSL 默认会塞 SMIMECapabilities 属性，
    # Android 的 StrictJarVerifier 直接报
    # "PKCS9 SMIMECapability attribute not supported"（INSTALL_PARSE_FAILED_NO_CERTIFICATES）。
    return (pkcs7.PKCS7SignatureBuilder()
            .set_data(sf_bytes)
            .add_signer(cert, key, hashes.SHA256())
            .sign(serialization.Encoding.DER,
                  [pkcs7.PKCS7Options.Binary,
                   pkcs7.PKCS7Options.DetachedSignature,
                   pkcs7.PKCS7Options.NoCapabilities]))


# ---------------------------------------------------------------- 主流程

def sign(src, dst, key_path, cert_path):
    key, cert = load_or_make_key(key_path, cert_path)

    with zipfile.ZipFile(src) as z:
        entries = []  # (name, info, content)
        dropped = []
        for info in z.infolist():
            nm = info.filename
            if nm.startswith('META-INF/') and nm.upper().endswith(SIG_SUFFIXES + ('.MF',)):
                dropped.append(nm)
                continue
            entries.append((nm, info, z.read(nm)))
    log('入口 %d 个；丢弃旧签名 %d 个：%s' % (len(entries), len(dropped), dropped))

    items = [(nm, content) for nm, _info, content in entries]
    manifest, sections = build_manifest(items)
    sf = build_sf(manifest, sections)
    sig = build_pkcs7(sf, key, cert)
    log('MANIFEST.MF %d B / CERT.SF %d B / CERT.RSA %d B' % (len(manifest), len(sf), len(sig)))

    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    with zipfile.ZipFile(dst, 'w') as out:
        # JAR 规范建议签名文件排在前面
        for nm, data in (('META-INF/MANIFEST.MF', manifest),
                         ('META-INF/CERT.SF', sf),
                         ('META-INF/CERT.RSA', sig)):
            out.writestr(zipfile.ZipInfo(nm, date_time=(2020, 1, 1, 0, 0, 0)),
                         data, compress_type=zipfile.ZIP_DEFLATED)
        for nm, info, content in entries:
            zi = zipfile.ZipInfo(nm, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            out.writestr(zi, content)

    log('已写出 %s（%d 字节）' % (dst, os.path.getsize(dst)))
    return dst


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, dst = argv[1], argv[2]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_path = os.path.join(root, 'work', 'dshmod.key.pem')
    cert_path = os.path.join(root, 'work', 'dshmod.cert.pem')
    args = argv[3:]
    if '--key' in args:
        key_path = args[args.index('--key') + 1]
    if '--cert' in args:
        cert_path = args[args.index('--cert') + 1]
    sign(src, dst, key_path, cert_path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
