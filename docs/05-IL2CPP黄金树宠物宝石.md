# 点击魔王 v5.9.2 — 逆向作战手册（IL2CPP 篇）

> 基于 `dump.cs`（666,763 行，Il2CppDumper 实际产出）逐行核对。
> 文中所有类名/方法名/RVA/行号均可直接在 `files/dump.cs` 里检索验证。

---

## 一、结论速览

| 目标 | 入口 | 关键方法 | 实现难度 |
|---|---|---|---|
| **黄金树无限** | `ShengMingShuDate.GetIntance()` | `JiHuoHuangJinShu()` + `ShengMingShuXuMing(9999)` | ★☆☆☆☆ |
| **宠物全开** | `ChongWuPool.Instens` | `OpenAllChongWu()` | ★☆☆☆☆ |
| **宝石碎片** | `ShenQiBaoShiDateModel.Instens` | `AddBaoShiSuiPian(ulong)` | ★☆☆☆☆ |
| **指定宝石** | 同上 | `ZhiDingBaoShi(yanSe,jieDuan,xYD)` + `AddBaoShi()` | ★★☆☆☆ |
| **全局加成** | `ShengMingShuDate` getter | Hook 只读属性 | ★☆☆☆☆ |

**全部是游戏自带的公开方法，不需要写汇编补丁。**

---

## 二、三个开发者遗留密码

这是本次逆向最有价值的发现：三个类各自藏着一个 8 位大写字母常量，风格完全一致：

| 类 | 常量名 | 值 | dump.cs 行 |
|---|---|---|---|
| `ShengMingShuDate` | `shuMiMa` | **`HTGFROKU`** | 262241 |
| `ChongWuManager` | `MiMa` | **`HYTGBFRO`** | 255862 |
| `ShenQiBaoShiDateModel` | `MIMA` | **`JNHPLSWE`** | 253732 |

第三个常量所在的类里还有一个方法叫 **`BaoShiMiMi()`**（"宝石密码"），
`dump.cs:253887`：

```csharp
public void BaoShiMiMi() { }
```

**判断**：这是开发者留的调试/测试入口。游戏 UI 里极可能存在隐藏输入框，
输入 `JNHPLSWE` 之类的口令直接发宝石。值得实测。

> ⚠️ 注意：`shuMiMa` / `MIMA` 是 `private const`，编译后**不会**留字符串在
> 常量池里以变量名出现，但字符串字面量本身在 `global-metadata.dat` 里是明文的。
> 可以直接 strings 搜到。

---

## 三、黄金树（生命树）

### 类结构 `ShengMingShuDate`（dump.cs:262226，TypeDefIndex 3044）

```csharp
public class ShengMingShuDate
{
    // 实例字段
    private int  jiHuoCiShu;              // 0x10  激活次数
    private bool guoShiIsLingQu;          // 0x14  果实是否领取
    private long chongZhiGuoShiTime;      // 0x18
    private string isZiDongKey_New;       // 0x20  PlayerPrefs 键名
    private string ziDongTimeKey_New;     // 0x28
    private string isZiDongJiangLiKey_New;// 0x30
    private float ziYuanCD;               // 0x38
    private int   ziYuanChanLiang;        // 0x3C
    private float paiQianTime;            // 0x40

    // 静态字段 —— 注意这些是 static
    private static bool  isJiHuo;         // 0x0
    private static bool  isHuangJin;      // 0x1   ★ 黄金树是否激活
    private static bool  isZiDongShua;    // 0x2
    private static float ziDongTime;      // 0x4
    private static bool  isZiDongJiangLi; // 0x8
    private static long  guoQiTime;       // 0x10  ★ 过期时间戳
    private static ShengMingShuDate _instance; // 0x18

    private const string shuMiMa = "HTGFROKU";
}
```

### 关键方法

```csharp
public static ShengMingShuDate GetIntance()      // 取单例
public void JiHuoShengMingShu()                   // 激活生命树
public void JiHuoHuangJinShu()                    // 激活黄金树
private void JiHuoShu(bool l, bool h)             // 两者共用核心(l=生命,h=黄金)
public bool UpHuangJinShu(int needZuanShi)        // 花钻石升级
public bool ShengMingShuXuMing(int day)           // ★ 续命 day 天
public bool IsGuoQi()                             // 是否过期
public long get_GuoQiDay()                        // 剩余天数
public void Load()                                // 从存储读入
```

### 实现方式（三选一）

**A. 运行时调用（推荐）**

```js
const K = Il2Cpp.domain.assembly("Assembly-CSharp").image.class("ShengMingShuDate");
const inst = K.method("GetIntance").invoke();
K.method("JiHuoHuangJinShu").invoke(inst);
K.method("ShengMingShuXuMing").invoke(inst, 9999);
```

**B. Hook `IsGuoQi()` 恒返回 false**

```js
K.method("IsGuoQi").implementation = function () { return false; };
K.method("get_GuoQiDay").implementation = function () { return 99999; };
```

**C. 直接改静态字段**

`guoQiTime` 在 `.bss`/静态区，偏移是类静态字段基址 +0x10。
用 `Il2Cpp` bridge 可以直接 `K.field("guoQiTime").value = 4102444800`。

### 注意点

- `isHuangJin` 和 `guoQiTime` 是 **static**，游戏重启会重新 `Load()` 覆盖。
  所以方案 A 每次启动都要跑一次；方案 B 的 hook 也要每次注入。
- `ShengMingShuXuMing(int day)` 返回 `bool`，`day` 是**天数**，传 9999 约 27 年。
- **`Load()` 里会从 PlayerPrefs 读 `isZiDongKey_New` 等，可能覆盖。**
  若要持久化，需同时改 PlayerPrefs。

---

## 四、宠物系统

### `ChongWuPool`（dump.cs:~256140）

```csharp
public class ChongWuPool : MonoBehaviour
{
    public static ChongWuPool Instens { get; }     // 单例

    public void LoadChongWuPool()                  // 加载
    public void SaveAllChongWu()                   // 保存全部
    public void OpenAllChongWu()                   // ★★ 一键全开
    public void AddCiShu()                         // +1 抓捕次数
    public void RemoveCiShu(int c)                 // -c 抓捕次数
    public void ChongZhiDan()                      // 重置蛋
    public void ZaDan(int id)                      // ★ 砸蛋(id)
    public bool[] get_DanIsOpens()                 // 蛋是否开启
    public int get_ZhuaLeJiCi()                    // 已抓次数
    public int get_ZhuaCiShuMax()                  // 抓捕上限
}
```

`OpenAllChongWu()` 就在 `dump.cs:256215`，紧跟在 `SaveAllChongWu()` 后面。
**这是游戏开发者自己写的"全部开放"函数**——很可能是给内部测试或特殊活动用的。
直接调用即可，而不用自己遍历宠物表。

### `ChongWuManager`（dump.cs:~255854）

```csharp
public class ChongWuManager : MonoBehaviour
{
    private const string MiMa = "HYTGBFRO";   // ★
    private int shiBaiCiShu;                  // 失败次数
    private string ShiBaiKey;
}
```

`ChongWuDate[]` 数组在 `ChongWuManager` 里（`suoYouChongWuDates`，0x30），
通过 `get_SuoYouChongWuDates()` 访问。

### 抓捕次数无限

```js
const K = cls("ChongWuPool");
const inst = K.method("get_Instens").invoke();
K.method("ChongZhiDan").invoke(inst);       // 重置蛋
// 或直接把已用次数清零:
const used = K.method("get_ZhuaCiShu").invoke(inst);
K.method("RemoveCiShu").invoke(inst, used);
```

---

## 五、宝石系统

### `ShenQiBaoShiDateModel`（dump.cs:253673，TypeDefIndex 2901）

```csharp
public class ShenQiBaoShiDateModel : MonoBehaviour
{
    private const string MIMA = "JNHPLSWE";          // ★
    private const ulong baoShiJiaCheng_JiChuMax = 10;
    private const ulong needMuCai_JiChu = 1000;
    private const ulong needKuangShi_JiChu = 800;

    public static ShenQiBaoShiDateModel Instens { get; set; }

    // 数据属性
    public ulong BaoShiSuiPian { get; }              // 碎片数
    public ulong BaoShiSuiPianMax { get; }           // 碎片上限
    public uint  BaoShiLevelMax { get; }             // 宝石等级上限
    public uint  BaoShiDaiMax { get; }               // 宝石袋上限
    public BaoShiTongJi BaoShiTongJi { get; }        // ★ 统计
    public List<ShenQiBaoShiClass> Hero01BaoShiList { get; }  // 5 个英雄各自的宝石
    // ... Hero02BaoShiList ~ Hero06BaoShiList

    // 核心操作
    public bool AddBaoShiSuiPian(ulong l)            // ★ 加碎片 (253905)
    public bool RemoveBaoShiSuiPian(ulong l)         // 扣碎片 (253908)
    public bool AddBaoShi(ShenQiBaoShiClass baoShi)  // ★ 加宝石 (253911)
    public void RemoveBaoShi(ShenQiBaoShiClass b)    // 移除 (253914)
    public bool FenSuiBaoShi(ShenQiBaoShiClass b)    // 粉碎 (253917)
    public int  BaoShiLevelUp(ShenQiBaoShiClass b)   // 升级 (253923)

    // ★ 开发者接口
    public void BaoShiMiMi()                                        // (253887)
    public ShenQiBaoShiClass ZhiDingBaoShi(uint yanSe,              // (253896)
                                            uint jieDuan,
                                            BaoShiXiYouDu xYD) { }
    public ShenQiBaoShiClass GetMoshiKuBaoShi(int nanDu)            // 模式库 (253899)
    public void YiJianFenJieBaoShi(int heroID, bool[] xiYouDu)      // 一键分解
    public void XiangQianBaoShi(ShenQiBaoShiClass b, bool isZB, int[] ZBID) // 镶嵌

    // 计算辅助
    public ulong GetLevelUpSuiPianShu(ShenQiBaoShiClass b)  // 升级所需碎片
    public float GetLevelUpChengGongLv(ShenQiBaoShiClass b) // 升级成功率
    public ulong GetFenJieSuiPianShu(ShenQiBaoShiClass b)   // 分解所得碎片
}
```

### 直接加碎片（最稳）

```js
const K = cls("ShenQiBaoShiDateModel");
const inst = K.method("get_Instens").invoke();
K.method("AddBaoShiSuiPian").invoke(inst, 999999);   // ulong 参数
```

> ⚠️ `AddBaoShiSuiPian` 是 `ulong` 参数，`frida-il2cpp-bridge` 里要传 BigInt
> 或 `Il2Cpp.ulong(999999)`。直接传 JS number 在小数值下通常也行，
> 但超过 2^53 会丢精度。

### 指定生成宝石

```csharp
ZhiDingBaoShi(uint yanSe, uint jieDuan, BaoShiXiYouDu xYD)
```

- `yanSe`（颜色）：对应 `BaoShiXiYouYanSe()` 里的颜色枚举
- `jieDuan`（阶段）：宝石阶数
- `xYD`（稀有度）：`BaoShiXiYouDu` 枚举

先用小值试探（如 `ZhiDingBaoShi(1, 1, 0)`），确认不崩再调大。
返回 `ShenQiBaoShiClass`，再 `AddBaoShi(result)` 入库。

---

## 六、全局加成（隐藏的数值金矿）

`ShengMingShuDate` 上挂了一整排**只读属性**，全是全局倍率。
Hook 它们的 getter 就等于改全部数值：

| 属性 | 含义 | 默认值（源码常量） |
|---|---|---|
| `get_ZiYuanChanLiang` | 资源产量 | 1 |
| `get_BaoShiTiLiJiaCheng` | 宝石体力加成 | 20 |
| `get_BaoShiNextCengJiaCheng` | 宝石下层加成 | 0.03 |
| `get_YaoShiMaxUP` | 钥匙最大升级 | 25 |
| `get_SiLiaoMaxUP` | 饲料最大升级 | 99 |
| `get_ChongWuCaoCong` | 宠物草丛 | 2 |
| `get_ZhuaBuNengLi` | 抓捕能力 | 1.3 |
| `get_GuangGaoMax` | 广告上限 | 30 |
| `get_JiChengLv` | 继承率 | 0.15 |
| `get_GuoShi` | 果实数 | 50 |
| `get_PaiQian` | 派遣 | 1 |
| `get_WaWaBiUp` | 娃娃币提升 | 2 |
| `get_MoShiKuTiLiUp` | 模式库体力提升 | 2 |
| `get_MoShiTiLiKuCunUp` | 模式体力库存提升 | 3 |
| `get_MoShiKuXingDongUp` | 模式库行动提升 | 1 |
| `get_PaiQianCiShuJiaCheng` | 派遣次数加成 | 1 |

```js
const K = cls("ShengMingShuDate");
K.method("get_ZiYuanChanLiang").implementation = () => 999;
K.method("get_ZhuaBuNengLi").implementation = () => 99.0;
```

这些 getter 返回值多为 `float`/`int`，hook 时注意类型（float 要返回 float）。

---

## 七、存档层：`SaveManager` 用的是 ES3

```csharp
public class SaveManager        // dump.cs:251899, TypeDefIndex 2846
{
    private static SaveManager instance;
    private ES3Settings setting;              // ★ Easy Save 3

    public static SaveManager Instance { get; }
    public bool IsCunZai(string key);
    public void Save<T>(string key, T value);          // 泛型, 7 个实例化
    public T    Load<T>(string key);
    public void DeleteData(string key);
    public void LoadInto<T>(string key, T t);
    public void SaveImage(Texture2D texture, string imageName);
    public Texture2D LoadImage(string imageName);
    public void Clear();
}
```

`Save<T>` 的泛型实例化（RVA 明确给出）：

| 类型 | RVA |
|---|---|
| `Save<bool>` | 0x1D18184 |
| `Save<Color>` | 0x1D1824C |
| `Save<int>` | 0x1D18338 |
| `Save<long>` | 0x1D18400 |
| `Save<object>` | 0x1D184C8 |
| `Save<float>` | 0x1D18594 |
| `Save<__Il2CppFullySharedGenericType>` | 0x1D1865C |

`Load<T>` 同理，RVA 从 0x1D17EF0 起，每个间隔 0x40。

**含义**：真正落盘的存档不是游戏里那个 `playerDate_XX` TextAsset（那是出厂样本/配置），
而是 ES3 把每个 key 单独序列化成文件（`.es3` 后缀，可能在
`/data/data/game.taptap.HQGAMES.TapDemons/files/` 下）。

**要观察真实 key 名**：hook `SaveManager.Save<T>`，把 `key` 和 `value` 打出来。
这是最快摸清存档结构的手段。

---

## 八、架构限制说明

| 项 | 值 | 影响 |
|---|---|---|
| Unity 版本 | 5.2 | — |
| 脚本后端 | **IL2CPP** | 改代码需要 Frida/补丁，不能直接反编译出 C# |
| ABI | arm64-v8a, armeabi-v7a, x86_64, x86 | 多架构, 改 so 需分别处理 |
| 加密 | **无**（`libil2cpp.so` 是干净 ELF，`global-metadata.dat` 带 UnityFS 头但完整） | dump 顺利 |
| 存档保护 | 无 HMAC/CRC/签名 | 可随意改 |
| 反调试 | 未见 | — |

`libil2cpp.so` 直接 `file` 显示为 `ELF 64-bit LSB shared object`，没有 Section header
被剥离、没有加密段。`global-metadata.dat` 前 4 字节是 `UnityFS`（说明打包过），
但 Il2CppDumper 仍成功解析出完整元数据。

---

## 九、环境准备清单

要在真机上执行本手册，需要：

1. **一台能 adb 的安卓手机**（已 root 或能跑 Frida gadget）
2. **adb**（本机当前没有，需安装 platform-tools）
3. **Frida server**（arm64 版，推到 `/data/local/tmp/` 并 `chmod 755`）
4. **宿主 frida + frida-il2cpp-bridge**
   ```bash
   pip install frida-tools
   npm i frida-il2cpp-bridge
   ```
5. **执行脚本**
   ```bash
   frida -U -f game.taptap.HQGAMES.TapDemons -l TapDemons.js
   ```

脚本已写好：`scripts`
其中 18 个方法名已逐一对照 dump.cs 验证存在。

---

## 十、优先级建议

如果只能做一件事，按这个顺序：

1. **`ShengMingShuDate` 的 global bonus hook** —— 一个 hook 改 16 个数值，性价比最高
2. **`ChongWuPool.OpenAllChongWu()`** —— 一行调用全开宠物
3. **`AddBaoShiSuiPian(999999)`** —— 一行加满碎片
4. **黄金树** —— 需要配合 PlayerPrefs 才能真正持久化

---

## 附：关键 RVA 速查

| 方法 | RVA |
|---|---|
| `ShengMingShuDate.JiHuoShengMingShu` | 0x18A6354 |
| `ShengMingShuDate.JiHuoHuangJinShu` | 0x18A65CC |
| `ShengMingShuDate.JiHuoShu(bool,bool)` | 0x18A6360 |
| `ShengMingShuDate.UpHuangJinShu` | 0x18A65E8 |
| `ShengMingShuDate.ShengMingShuXuMing` | 0x18A66FC |
| `ShengMingShuDate.IsGuoQi` | 0x18A689C |
| `ShengMingShuDate.get_GuoQiDay` | 0x18A50FC |
| `ShengMingShuDate.Load` | 0x18A51EC |
| `ShengMingShuDate.GetIntance` | 0x18A6948 |
| `ChongWuPool.SaveAllChongWu` | 0x18521BC |
| `ChongWuPool.OpenAllChongWu` | 0x1858800 |
| `JiaMi.Encrypt_New` | 0x188CCA8 |

> RVA = 相对 `libil2cpp.so` 基址的偏移。用 IDA/Ghidra 打开
> `lib/arm64-v8a/libil2cpp.so`，跳转到 `0x18A65CC` 即是 `JiHuoHuangJinShu` 的机器码。
