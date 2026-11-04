# files/patched —— 手机版（ARM64）可玩成品

本目录是 **v5.5.7 手机版补丁工程**的二进制交付物，配套文档见
[`docs/31-真机64位补丁交付手册.md`](../../docs/31-真机64位补丁交付手册.md)。

> 大文件走 Git LFS（见仓库根 `.gitattributes`）。
> 拉下来第一件事：`git lfs pull`，然后按下表核对 `git lfs ls-files` 与本地 MD5。

| 文件 | 大小 | MD5 | 说明 |
|---|---|---|---|
| `djmw_v7_arm64_signed.apk` | 100,787,100 B | `9D7551988F1E8E79805670028E1DFB72` | **成品**：手机原版包 + 36 条补丁，已用 `scripts/sign_apk_v1.py` 做过 v1 签名。`adb install -r` 即可 |
| `libil2cpp_64_patched_v7.so` | 21,504,968 B | `A09E1F90EE8B3E8D2FFE442B2B459411` | 打进上面那个 APK 的 64 位补丁库；由 `scripts/build_patched_lib64.py` 生成 |
| `phone_base_arm64.apk` | 100,720,865 B | `D8EB6343F1C236CE7EE2E8343EAEFD30` | 手机上的**原版** `base.apk`（从 `/data/app/.../base.apk` 拉出）。重打包的底，也是补丁地址的唯一权威来源 |
| `v7_base.save` | 84,911 B | — | 推给手机的那份存档（`ZuanShi=50000`、`ChongWuSiLiao=597`、`DangTianZhuaChongShu=0`），放在 `Android/data/com.HQGAMES.TopDemons/files/djmw@163.com` |

## 重建（三条命令，详见 docs/31 §三）

```bash
python scripts/build_patched_lib64.py --out out/libil2cpp_64_patched.so
python scripts/build_apk64.py --lib out/libil2cpp_64_patched.so --out out/djmw_unsigned.apk
python scripts/sign_apk_v1.py out/djmw_unsigned.apk out/djmw_signed.apk
```

`build_patched_lib64.py` 的 `SRC` 默认指向本机路径；换机器时改 `SRC` 为
`files/patched/phone_base_arm64.apk` 里解出来的 `lib/arm64-v8a/libil2cpp.so`（MD5 应为
`24E1EABBA8CEC154C265F95D7DE8F841`）。

## 注意

- **签名密钥**：仓库里的 `work/dshmod.key.pem` / `work/dshmod.cert.pem` 是打包时用的自签证书。
  换新证书重签不会导致启动崩溃——`nullfix`（`0x406D9C`）已经在补丁表里兜住了那条空指针路径。
- 包名 `com.HQGAMES.TopDemons`，`targetSdkVersion=29`，所以 v1 签名足够被 Android 11+ 接受。
- 这是**修改版客户端**，仅供本机存档与个人测试使用，不要再分发。
