# files/patched —— 手机版（ARM64）可玩成品

本目录是 **v5.5.7 手机版补丁工程**的二进制交付物，配套文档见
[`docs/31-真机64位补丁交付手册.md`](../../docs/31-真机64位补丁交付手册.md)。

> 大文件走 Git LFS（见仓库根 `.gitattributes`）。
> 拉下来第一件事：`git lfs pull`，然后按下表核对 `git lfs ls-files` 与本地 MD5。

| 文件 | 大小 | MD5 | 说明 |
|---|---|---|---|
| `djmw_v19_arm64_signed.apk` | 100,787,044 B | `F0380CCCF90FBB81D2B194227AA23292` | **成品（最新，v19）**：v18 全部 + 魔石 99999999。魔窟：体力不消耗 / 商店不扣资源 / 库存不减 / 魔物碎片恒 1000。见 [`docs/33`](../../docs/33-魔窟补丁-体力商店魔石魔物碎片.md) |
| `djmw_v18_arm64_signed.apk` | 100,787,031 B | `D34A12D27560078CA44FE7EC4891BBD9` | v18：v17 + 商店库存不减（8 处 `add w8,w8,#1` → NOP） |
| `djmw_v16_arm64_signed.apk` | 100,787,037 B | `09B9435CF16B48AC53963DB40E323BB4` | v16：缓存字段直写 1000（魔石那格写错成 0，已被 v17/v19 修） |
| `djmw_v15_arm64_signed.apk` | 100,787,034 B | `D71CEFD296A644C923F106EA702171B8` | v15：v14 + 补齐 6 处扣费 NOP（改 getter，界面不读，未生效） |
| `djmw_v14_arm64_signed.apk` | 100,787,054 B | `D0CDCC7D2AC1C6CA4845427B8DC24C8E` | v14：魔窟体力不消耗 + 魔石 getter→1000 + 首处扣费 NOP |
| `djmw_v13_arm64_signed.apk` | 100,787,043 B | `8A692A6D38CD65DE6A2327ADE603C7E7` | v13：v12 全部 + 欧气/非气恒 50 + 神秘商店库存重置为满。与 v9~v12 同签名，`install -r` 覆盖装 |
| `djmw_v12_arm64_signed.apk` | 100,787,041 B | `5BD79447AF384580BAB68B1FFD1D59AB` | v12：宝石升级下限 90% + 升级消耗 ÷10（欧气/非气与商店那两项未生效，被 v13 修） |
| `djmw_v11_arm64_signed.apk` | 100,787,048 B | `C42A202C7EA1E4BEBB80C4A1CFC36EE3` | v11：v10 + 宝石升级成功率下限 75% |
| `djmw_v10_arm64_signed.apk` | 100,787,040 B | `F43E7709910B43D41EB3737F95E72DB1` | v10：v9 全部 + 派遣时长改成 3 秒 |
| `djmw_v9_arm64_signed.apk` | 100,787,042 B | `889F29682948830ABE50977563ED61DC` | v9：v8 全部 + 广告 80 次不减 / 木 50 万·矿 30 万每秒 / 六色等概率 |
| `djmw_v8_arm64_signed.apk` | 100,787,103 B | `FB145DE7E65E87C253864C1BA8E9448A` | v8：手机原版包 + 36 条补丁（资源 50,000/s）。**签名与 v9+ 不同**，互装必须卸载 |
| `libil2cpp_64_v19.so` | 21,504,968 B | `EA37C1F97619024D7D4C8C4309B8B542` | v19 的补丁库（v18 + 魔石 99999999，含 .rodata 常量池写入） |
| `libil2cpp_64_v18.so` | 21,504,968 B | `4EA14A46C3E24B4AB3AA10864EF1EA7C` | v18 的补丁库（8 处库存自增 NOP） |
| `libil2cpp_64_v16.so` | 21,504,968 B | `C7509FE5A9AD4B0AE659E9118E6DABFC` | v16 的补丁库 |
| `libil2cpp_64_v15.so` | 21,504,968 B | `E6024AFC8AA32FF8F832A0B05B73542C` | v15 的补丁库 |
| `libil2cpp_64_v14.so` | 21,504,968 B | `567F5492E29C724297BA9B6A8640469A` | v14 的补丁库 |
| `libil2cpp_64_v13.so` | 21,504,968 B | `AD7AC757EA8A7464C12B72447EE2E34E` | v13 的补丁库 |
| `libil2cpp_64_v12.so` | 21,504,968 B | `7B93E1BE58F2DF857ECA9B7DF0F0BC42` | v12 的补丁库 |
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
