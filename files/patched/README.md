# files/patched —— 手机版（ARM64）可玩成品

本目录是 **v5.5.7 手机版补丁工程**的二进制交付物，配套文档见
[`docs/31-真机64位补丁交付手册.md`](../../docs/31-真机64位补丁交付手册.md)。

> 大文件走 Git LFS（见仓库根 `.gitattributes`）。
> 拉下来第一件事：`git lfs pull`，然后按下表核对 `git lfs ls-files` 与本地 MD5。

| 文件 | 大小 | MD5 | 说明 |
|---|---|---|---|
| `djmw_v11_arm64_signed.apk` | 100,787,048 B | `C42A202C7EA1E4BEBB80C4A1CFC36EE3` | **成品（最新，v11）**：v10 全部 + 宝石升级成功率下限 75%。与 v9/v10 同签名，`install -r` 覆盖装 |
| `djmw_v10_arm64_signed.apk` | 100,787,040 B | `F43E7709910B43D41EB3737F95E72DB1` | v10：v9 全部 + 派遣时长改成 3 秒。与 v9 同签名，`adb install -r` 覆盖装即可，数据不动 |
| `djmw_v9_arm64_signed.apk` | 100,787,042 B | `889F29682948830ABE50977563ED61DC` | v8 全部 + 广告 80 次不减 / 木 50 万·矿 30 万每秒 / 六色等概率（派遣遗留了"改错函数"的问题，已被 v10 修） |
| `djmw_v8_arm64_signed.apk` | 100,787,103 B | `FB145DE7E65E87C253864C1BA8E9448A` | v8：手机原版包 + 36 条补丁（资源 50,000/s）。**签名与 v9+ 不同**，互装必须卸载 |
| `libil2cpp_64_v11.so` | 21,504,968 B | `E9C5B973F8589D50A8792EFC89976525` | v11 的补丁库（v10 + 2 条宝石升级补丁） |
| `libil2cpp_64_v10.so` | 21,504,968 B | `F89570FB093B50020D6F07488E905830` | v10 的补丁库（v9 + 7 条派遣补丁） |
| `libil2cpp_64_v9.so` | 21,504,968 B | `7C9836B324B6245D52E8CEBB309C182E` | v9 的补丁库（`scripts/build_lib64_v9b.py` 产物） |
| `libil2cpp_64_patched_v8.so` | 21,504,968 B | `21C0E9E16E26617CB169BFF4A8BE8EA3` | v8 的补丁库（`scripts/build_patched_lib64.py` 产物） |
| `phone_base_arm64.apk` | 100,720,865 B | `D8EB6343F1C236CE7EE2E8343EAEFD30` | 手机上的**原版** `base.apk`（从 `/data/app/.../base.apk` 拉出）。重打包的底，也是补丁地址的唯一权威来源 |
| `v7_base.save` | 84,911 B | — | 推给手机的那份存档（`ZuanShi=50000`、`ChongWuSiLiao=597`、`DangTianZhuaChongShu=0`），放在 `Android/data/com.HQGAMES.TopDemons/files/djmw@163.com` |

> v9/v10 的改动明细（RVA 表 + 派遣公式推导）见
> [`docs/32-v9v10-广告产量派遣与宝石颜色.md`](../../docs/32-v9v10-广告产量派遣与宝石颜色.md)。

> v7（资源 10,000/s）的 `djmw_v7_arm64_signed.apk`（`9D7551988F1E8E79805670028E1DFB72`）/
> `libil2cpp_64_patched_v7.so`（`A09E1F90EE8B3E8D2FFE442B2B459411`）已被 v8 取代，
> 需要的话把 `0xEBF9D0`/`0xEC0550` 的 `52986A08` 改回 `5284E208` 重新构建即可。

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
