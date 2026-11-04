import zipfile, hashlib
p=r'E:\DSH\game\work\phone64\base.apk'
z=zipfile.ZipFile(p)
for name in ['lib/arm64-v8a/libil2cpp.so','lib/armeabi-v7a/libil2cpp.so']:
    b=z.read(name)
    print(name, len(b), hashlib.md5(b).hexdigest())
import os
for f in [r'E:\DSH\game\work\phone64\libil2cpp_64.so',
          r'E:\DSH\game\djmwREA\files\old\libil2cpp_v557_arm32.so']:
    if os.path.exists(f):
        b=open(f,'rb').read()
        print(os.path.basename(f), len(b), hashlib.md5(b).hexdigest())