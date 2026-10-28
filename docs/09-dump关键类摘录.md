# dump.cs 关键类摘录

> 源文件：`dump\dump.cs`（Il2CppDumper 输出，22 MB / 666763 行）
> 原文行号为完整 dump.cs 中的行号，可用 Il2CppDumper 重新生成后对照。


## 关键方法索引（RVA -> dump.cs 行号）

| RVA | dump.cs 行 | 签名 |
|---|---|---|
| `0x175226C` | 563937 | `public void .ctor(ES3.EncryptionType encryptionType, string encryptionPassword) { }` |
| `0x1751F88` | 563944 | `public void .ctor(bool applyDefaults) { }` |
| `0x1782D44` | 577436 | `public override void Encrypt(Stream input, Stream output, string password, int bufferSize) { }` |
| `0x178329C` | 577439 | `public override void Decrypt(Stream input, Stream output, string password, int bufferSize) { }` |
| `0x17A64D8` | 251988 | `public void .ctor() { }` |
| `0x17A5D84` | 251910 | `public static SaveManager get_Instance() { }` |
| `0x17A55B0` | 251913 | `public bool IsCunZai(string key) { }` |
| `0x18A7034` | 262820 | `public void SaveGame() { }` |
| `0x18A9374` | 262838 | `public void LoadGame() { }` |
| `0x18A8A68` | 262876 | `private string Encrypt(string SourceText, string key) { }` |
| `0x27A87E0` | 79554 | `public void .ctor(string password, byte[] salt, int iterations) { }` |
| `0x27A89D8` | 79563 | `public override byte[] GetBytes(int cb) { }` |
| `0x27A9300` | 79739 | `public void .ctor(Stream stream, ICryptoTransform transform, CryptoStreamMode mode) { }` |

> 注：`dump.cs` 的 `RVA` 与文件偏移 `Offset` **不相等**（ELF 段间有 0x4000 / 0x8000 差值）。
> hook 用 `RVA`；静态读文件用 `Offset`。

---
## SaveManager  (line 251899-252000)

```csharp
public class SaveManager // TypeDefIndex: 2846
{
	// Fields
	private static SaveManager instance; // 0x0
	private ES3Settings setting; // 0x10

	// Properties
	public static SaveManager Instance { get; }

	// Methods

	// RVA: 0x17A5D84 Offset: 0x17A1D84 VA: 0x17A5D84
	public static SaveManager get_Instance() { }

	// RVA: 0x17A55B0 Offset: 0x17A15B0 VA: 0x17A55B0
	public bool IsCunZai(string key) { }

	// RVA: -1 Offset: -1
	public void Save<T>(string key, T value) { }
	/* GenericInstMethod :
	|
	|-RVA: 0x1D18184 Offset: 0x1D14184 VA: 0x1D18184
	|-SaveManager.Save<bool>
	|
	|-RVA: 0x1D1824C Offset: 0x1D1424C VA: 0x1D1824C
	|-SaveManager.Save<Color>
	|
	|-RVA: 0x1D18338 Offset: 0x1D14338 VA: 0x1D18338
	|-SaveManager.Save<int>
	|
	|-RVA: 0x1D18400 Offset: 0x1D14400 VA: 0x1D18400
	|-SaveManager.Save<long>
	|
	|-RVA: 0x1D184C8 Offset: 0x1D144C8 VA: 0x1D184C8
	|-SaveManager.Save<object>
	|
	|-RVA: 0x1D18594 Offset: 0x1D14594 VA: 0x1D18594
	|-SaveManager.Save<float>
	|
	|-RVA: 0x1D1865C Offset: 0x1D1465C VA: 0x1D1865C
	|-SaveManager.Save<__Il2CppFullySharedGenericType>
	*/

	// RVA: -1 Offset: -1
	public T Load<T>(string key) { }
	/* GenericInstMethod :
	|
	|-RVA: 0x1D17EF0 Offset: 0x1D13EF0 VA: 0x1D17EF0
	|-SaveManager.Load<bool>
	|
	|-RVA: 0x1D17F30 Offset: 0x1D13F30 VA: 0x1D17F30
	|-SaveManager.Load<Color>
	|
	|-RVA: 0x1D17F70 Offset: 0x1D13F70 VA: 0x1D17F70
	|-SaveManager.Load<int>
	|
	|-RVA: 0x1D17FB0 Offset: 0x1D13FB0 VA: 0x1D17FB0
	|-SaveManager.Load<long>
	|
	|-RVA: 0x1D17FF0 Offset: 0x1D13FF0 VA: 0x1D17FF0
	|-SaveManager.Load<object>
	|
	|-RVA: 0x1D18030 Offset: 0x1D14030 VA: 0x1D18030
	|-SaveManager.Load<float>
	|
	|-RVA: 0x1D18070 Offset: 0x1D14070 VA: 0x1D18070
	|-SaveManager.Load<__Il2CppFullySharedGenericType>
	*/

	// RVA: 0x17A6568 Offset: 0x17A2568 VA: 0x17A6568
	public void DeleteData(string key) { }

	// RVA: -1 Offset: -1
	public void LoadInto<T>(string key, T t) { }
	/* GenericInstMethod :
	|
	|-RVA: 0x1D18134 Offset: 0x1D14134 VA: 0x1D18134
	|-SaveManager.LoadInto<object>
	*/

	// RVA: 0x17A65B4 Offset: 0x17A25B4 VA: 0x17A65B4
	public void SaveImage(Texture2D texture, string imageName) { }

	// RVA: 0x17A65CC Offset: 0x17A25CC VA: 0x17A65CC
	public Texture2D LoadImage(string imageName) { }

	// RVA: 0x17A65E0 Offset: 0x17A25E0 VA: 0x17A65E0
	public void Clear() { }

	// RVA: 0x17A64D8 Offset: 0x17A24D8 VA: 0x17A64D8
	public void .ctor() { }
}

// Namespace: 
public class LoadSceneManager : MonoBehaviour // TypeDefIndex: 2847
{
	// Fields
	private string _currentSceneName; // 0x20
	private Action<float> _currentAction; // 0x28
	private AsyncOperation _operation; // 0x30
	[CompilerGenerated]
	private static LoadSceneManager <Instance>k__BackingField; // 0x0
```

## ChongWuClass  (line 255347-255460)

```csharp
public class ChongWuClass : MonoBehaviour // TypeDefIndex: 2934
{
	// Fields
	[SerializeField]
	protected int chongWuID; // 0x20
	protected ChongWu chongWuData; // 0x28
	protected string[] chongWuname; // 0x30
	protected JiNeng xieDaiJiNeng; // 0x38
	protected int maoXianWeiZhi; // 0x3C
	protected bool isMaoXian; // 0x40
	protected XiYouDu xiYouDu; // 0x44
	protected int level; // 0x48
	protected int jinJie; // 0x4C
	protected int jinHua; // 0x50
	protected int xieDai; // 0x54
	protected ShuXing shuXing; // 0x58
	protected Sprite shuXingSprite; // 0x60
	protected long damegeUp; // 0x68
	protected long hPUp; // 0x70

	// Properties
	public int ChongWuID { get; }
	public string[] ChongWuName { get; }
	public string CWName { get; }
	public string ChongWuHuaShi { get; }
	public bool IsXianLiangBool { get; }
	public bool IsKeZhuaBool { get; }
	public bool IsHeChengSuCaiBool { get; }
	public bool IsHeChengBool { get; }
	public bool IsZhanDou { get; }
	public JiNeng XieDaiJiNeng { get; }
	public float HitCD { get; }
	public float JiNengCD { get; }
	public int GongJiFanWei { get; }
	public int MaoXianWeiZhi { get; }
	public bool IsMaoXian { get; }
	public XiYouDu XiYouDu { get; }
	public string XiYouDu_String { get; }
	public int Level { get; }
	public int LevelMax { get; }
	public long NeedEXP { get; }
	public long NeedMuCai { get; }
	public long NeedKuangShi { get; }
	public int NeedSiLiao { get; }
	public int NeedZuanShi { get; }
	public long Damage { get; }
	public ulong ZhanDouLi { get; }
	public int JinJie { get; }
	public int JinHua { get; }
	public int XieDai { get; }
	public Sprite JingLingTu { get; }
	public Sprite TouXiang { get; }
	public long Hp { get; }
	public ShuXing ShuXing { get; }
	public string ShuXing_String { get; }
	public Sprite ShuXingSprite { get; }
	public virtual long DamageUp { get; }
	public long DamageUpJiChu { get; }
	public virtual long HPUp { get; }
	public long HPUpJiChu { get; }
	public float SpeedUp { get; }
	public float SpellSpeedUp { get; }
	public float DuoBiUp { get; }
	public float SpellDuoBiUp { get; }
	public float BaoJiUp { get; }
	public float BossSpeedDown { get; }
	public float BossSpellSpeedDown { get; }
	public float BossDuoBiDown { get; }
	public float BossSpellDuoBiDown { get; }
	public float BossDiaoLuoUp { get; }
	public float WaBaoShiUp { get; }
	public float BaoShiLevelUpUp { get; }
	public float NeedBaoShiSuiPianDown { get; }
	public float ChuanShuoBaoShiUp { get; }
	public float YuanGuBaoShiUp { get; }
	public float QunDiWeiUp { get; }

	// Methods

	// RVA: 0x1851874 Offset: 0x184D874 VA: 0x1851874
	public int get_ChongWuID() { }

	// RVA: 0x185187C Offset: 0x184D87C VA: 0x185187C Slot: 4
	protected virtual void Init() { }

	// RVA: 0x1851CA4 Offset: 0x184DCA4 VA: 0x1851CA4
	public string[] get_ChongWuName() { }

	// RVA: 0x18476F4 Offset: 0x18436F4 VA: 0x18476F4
	public string get_CWName() { }

	// RVA: 0x1851CAC Offset: 0x184DCAC VA: 0x1851CAC
	public string get_ChongWuHuaShi() { }

	// RVA: 0x1851CC8 Offset: 0x184DCC8 VA: 0x1851CC8
	public bool get_IsXianLiangBool() { }

	// RVA: 0x1851CEC Offset: 0x184DCEC VA: 0x1851CEC
	public bool get_IsKeZhuaBool() { }

	// RVA: 0x1851D10 Offset: 0x184DD10 VA: 0x1851D10
	public bool get_IsHeChengSuCaiBool() { }

	// RVA: 0x1851D34 Offset: 0x184DD34 VA: 0x1851D34
	public bool get_IsHeChengBool() { }

	// RVA: 0x1851D58 Offset: 0x184DD58 VA: 0x1851D58
	public bool get_IsZhanDou() { }

	// RVA: 0x1851D7C Offset: 0x184DD7C VA: 0x1851D7C
	public JiNeng get_XieDaiJiNeng() { }

	// RVA: 0x1851D84 Offset: 0x184DD84 VA: 0x1851D84
	public float get_HitCD() { }
```

## JiaMi  (line 260470-260560)

```csharp
public static class JiaMi // TypeDefIndex: 3029
{
	// Methods

	// RVA: 0x188CCA8 Offset: 0x1888CA8 VA: 0x188CCA8
	public static string Encrypt_New(string SourceText, string key) { }
}

// Namespace: 
public sealed class DESEncrypt // TypeDefIndex: 3030
{
	// Fields
	private static string key; // 0x0

	// Properties
	public static string Key { get; set; }

	// Methods

	// RVA: 0x189506C Offset: 0x189106C VA: 0x189506C
	private void .ctor() { }

	// RVA: 0x1895074 Offset: 0x1891074 VA: 0x1895074
	public static string get_Key() { }

	// RVA: 0x18950CC Offset: 0x18910CC VA: 0x18950CC
	public static void set_Key(string value) { }

	// RVA: 0x1895134 Offset: 0x1891134 VA: 0x1895134
	private static void .cctor() { }
}

// Namespace: 
public class MinGanCiGuoLu : MonoBehaviour // TypeDefIndex: 3031
{
	// Fields
	public TextAsset txt; // 0x20
	public InputField inputField; // 0x28

	// Methods

	// RVA: 0x18951A0 Offset: 0x18911A0 VA: 0x18951A0
	private void Awake() { }

	// RVA: 0x189525C Offset: 0x189125C VA: 0x189525C
	public bool PanDuanHeFa() { }

	// RVA: 0x1895288 Offset: 0x1891288 VA: 0x1895288
	public static bool CheckStringValid(string value, bool ignoreSpecialCharac = False) { }

	// RVA: 0x18952CC Offset: 0x18912CC VA: 0x18952CC
	public static bool ValidCheckSpecialChara(string value) { }

	// RVA: 0x1895378 Offset: 0x1891378 VA: 0x1895378
	public void .ctor() { }
}

// Namespace: 
public class NeiGouButton : MonoBehaviour // TypeDefIndex: 3032
{
	// Fields
	[Tooltip("内购按钮的ID，第一个是0")]
	[SerializeField]
	private int id; // 0x20
	[SerializeField]
	[Tooltip("单位是分")]
	private int jiaGe; // 0x24
	[SerializeField]
	private ZuanShiShop zuanShiShop; // 0x28
	private Button myButton; // 0x30
	[SerializeField]
	private Text buttonText; // 0x38

	// Methods

	// RVA: 0x1895380 Offset: 0x1891380 VA: 0x1895380
	private void Start() { }

	// RVA: 0x18954BC Offset: 0x18914BC VA: 0x18954BC
	private void GouMai() { }

	// RVA: 0x1895584 Offset: 0x1891584 VA: 0x1895584
	private void GouMaiChengGong() { }

	// RVA: 0x1895694 Offset: 0x1891694 VA: 0x1895694
	public void .ctor() { }
}

// Namespace: 
[CompilerGenerated]
private sealed class NeiGouManager.<GetNeiGouHuoDongXinXi>d__11 : IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 3033
```

## ShuJuDate  (line 262478-262800)

```csharp
private sealed class ShuJuDate.<GetDateXinXi>d__94 : IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 3047
{
	// Fields
	private int <>1__state; // 0x10
	private object <>2__current; // 0x18
	public string playerID; // 0x20
	public string playerMiMa; // 0x28
	public ShuJuDate <>4__this; // 0x30
	private UnityWebRequest <uwr>5__2; // 0x38

	// Properties
	private object System.Collections.Generic.IEnumerator<System.Object>.Current { get; }
	private object System.Collections.IEnumerator.Current { get; }

	// Methods

	[DebuggerHidden]
	// RVA: 0x18AB0BC Offset: 0x18A70BC VA: 0x18AB0BC
	public void .ctor(int <>1__state) { }

	[DebuggerHidden]
	// RVA: 0x18AB80C Offset: 0x18A780C VA: 0x18AB80C Slot: 5
	private void System.IDisposable.Dispose() { }

	// RVA: 0x18AB810 Offset: 0x18A7810 VA: 0x18AB810 Slot: 6
	private bool MoveNext() { }

	[DebuggerHidden]
	// RVA: 0x18ABB28 Offset: 0x18A7B28 VA: 0x18ABB28 Slot: 4
	private object System.Collections.Generic.IEnumerator<System.Object>.get_Current() { }

	[DebuggerHidden]
	// RVA: 0x18ABB30 Offset: 0x18A7B30 VA: 0x18ABB30 Slot: 8
	private void System.Collections.IEnumerator.Reset() { }

	[DebuggerHidden]
	// RVA: 0x18ABB68 Offset: 0x18A7B68 VA: 0x18ABB68 Slot: 7
	private object System.Collections.IEnumerator.get_Current() { }
}

// Namespace: 
[CompilerGenerated]
private sealed class ShuJuDate.<ShangChuanDate>d__95 : IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 3048
{
	// Fields
	private int <>1__state; // 0x10
	private object <>2__current; // 0x18
	public ShuJuDate <>4__this; // 0x20
	public string playerID; // 0x28
	public string playerMiMa; // 0x30
	public string playerDate; // 0x38
	private UnityWebRequest <uwr>5__2; // 0x40

	// Properties
	private object System.Collections.Generic.IEnumerator<System.Object>.Current { get; }
	private object System.Collections.IEnumerator.Current { get; }

	// Methods

	[DebuggerHidden]
	// RVA: 0x18AB0E4 Offset: 0x18A70E4 VA: 0x18AB0E4
	public void .ctor(int <>1__state) { }

	[DebuggerHidden]
	// RVA: 0x18ABB70 Offset: 0x18A7B70 VA: 0x18ABB70 Slot: 5
	private void System.IDisposable.Dispose() { }

	// RVA: 0x18ABB74 Offset: 0x18A7B74 VA: 0x18ABB74 Slot: 6
	private bool MoveNext() { }

	[DebuggerHidden]
	// RVA: 0x18ABD4C Offset: 0x18A7D4C VA: 0x18ABD4C Slot: 4
	private object System.Collections.Generic.IEnumerator<System.Object>.get_Current() { }

	[DebuggerHidden]
	// RVA: 0x18ABD54 Offset: 0x18A7D54 VA: 0x18ABD54 Slot: 8
	private void System.Collections.IEnumerator.Reset() { }

	[DebuggerHidden]
	// RVA: 0x18ABD8C Offset: 0x18A7D8C VA: 0x18ABD8C Slot: 7
	private object System.Collections.IEnumerator.get_Current() { }
}

// Namespace: 
[CompilerGenerated]
private sealed class ShuJuDate.<ShangChuanDate_PT>d__96 : IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 3049
{
	// Fields
	private int <>1__state; // 0x10
	private object <>2__current; // 0x18
	public string playerID; // 0x20
	public string playerMiMa; // 0x28
	public string playerDate; // 0x30
	public string diZhi; // 0x38
	public ShuJuDate <>4__this; // 0x40
	private UnityWebRequest <uwr>5__2; // 0x48

	// Properties
	private object System.Collections.Generic.IEnumerator<System.Object>.Current { get; }
	private object System.Collections.IEnumerator.Current { get; }

	// Methods

	[DebuggerHidden]
	// RVA: 0x18AB1D8 Offset: 0x18A71D8 VA: 0x18AB1D8
	public void .ctor(int <>1__state) { }

	[DebuggerHidden]
	// RVA: 0x18ABD94 Offset: 0x18A7D94 VA: 0x18ABD94 Slot: 5
	private void System.IDisposable.Dispose() { }

	// RVA: 0x18ABD98 Offset: 0x18A7D98 VA: 0x18ABD98 Slot: 6
	private bool MoveNext() { }

	[DebuggerHidden]
	// RVA: 0x18AC3EC Offset: 0x18A83EC VA: 0x18AC3EC Slot: 4
	private object System.Collections.Generic.IEnumerator<System.Object>.get_Current() { }

	[DebuggerHidden]
	// RVA: 0x18AC3F4 Offset: 0x18A83F4 VA: 0x18AC3F4 Slot: 8
	private void System.Collections.IEnumerator.Reset() { }

	[DebuggerHidden]
	// RVA: 0x18AC42C Offset: 0x18A842C VA: 0x18AC42C Slot: 7
	private object System.Collections.IEnumerator.get_Current() { }
}

// Namespace: 
[CompilerGenerated]
private sealed class ShuJuDate.<ShangChuanHeroDate>d__97 : IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 3050
{
	// Fields
	private int <>1__state; // 0x10
	private object <>2__current; // 0x18
	public string playerID; // 0x20
	public string playerMiMa; // 0x28
	public string heroID; // 0x30
	public string playerDate; // 0x38
	public string diZhi; // 0x40
	private UnityWebRequest <uwr>5__2; // 0x48

	// Properties
	private object System.Collections.Generic.IEnumerator<System.Object>.Current { get; }
	private object System.Collections.IEnumerator.Current { get; }

	// Methods

	[DebuggerHidden]
	// RVA: 0x18AB2CC Offset: 0x18A72CC VA: 0x18AB2CC
	public void .ctor(int <>1__state) { }

	[DebuggerHidden]
	// RVA: 0x18AC434 Offset: 0x18A8434 VA: 0x18AC434 Slot: 5
	private void System.IDisposable.Dispose() { }

	// RVA: 0x18AC438 Offset: 0x18A8438 VA: 0x18AC438 Slot: 6
	private bool MoveNext() { }

	[DebuggerHidden]
	// RVA: 0x18AC854 Offset: 0x18A8854 VA: 0x18AC854 Slot: 4
	private object System.Collections.Generic.IEnumerator<System.Object>.get_Current() { }

	[DebuggerHidden]
	// RVA: 0x18AC85C Offset: 0x18A885C VA: 0x18AC85C Slot: 8
	private void System.Collections.IEnumerator.Reset() { }

	[DebuggerHidden]
	// RVA: 0x18AC894 Offset: 0x18A8894 VA: 0x18AC894 Slot: 7
	private object System.Collections.IEnumerator.get_Current() { }
}

// Namespace: 
[CompilerGenerated]
private sealed class ShuJuDate.<XiaZaiDate>d__98 : IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 3051
{
	// Fields
	private int <>1__state; // 0x10
	private object <>2__current; // 0x18
	public string playerID; // 0x20
	public string playerMiMa; // 0x28
	public ShuJuDate <>4__this; // 0x30
	private UnityWebRequest <uwr>5__2; // 0x38

	// Properties
	private object System.Collections.Generic.IEnumerator<System.Object>.Current { get; }
	private object System.Collections.IEnumerator.Current { get; }

	// Methods

	[DebuggerHidden]
	// RVA: 0x18AB2F4 Offset: 0x18A72F4 VA: 0x18AB2F4
	public void .ctor(int <>1__state) { }

	[DebuggerHidden]
	// RVA: 0x18AC89C Offset: 0x18A889C VA: 0x18AC89C Slot: 5
	private void System.IDisposable.Dispose() { }

	// RVA: 0x18AC8A0 Offset: 0x18A88A0 VA: 0x18AC8A0 Slot: 6
	private bool MoveNext() { }

	[DebuggerHidden]
	// RVA: 0x18ACD00 Offset: 0x18A8D00 VA: 0x18ACD00 Slot: 4
	private object System.Collections.Generic.IEnumerator<System.Object>.get_Current() { }

	[DebuggerHidden]
	// RVA: 0x18ACD08 Offset: 0x18A8D08 VA: 0x18ACD08 Slot: 8
	private void System.Collections.IEnumerator.Reset() { }

	[DebuggerHidden]
	// RVA: 0x18ACD40 Offset: 0x18A8D40 VA: 0x18ACD40 Slot: 7
	private object System.Collections.IEnumerator.get_Current() { }
}

// Namespace: 
public class ShuJuDate : MonoBehaviour // TypeDefIndex: 3052
{
	// Fields
	private const string MIMA = "PJSQJ678";
	private bool IsZuDang; // 0x20
	private string playerZhangHao; // 0x28
	private const string zhangHaoKey = "UJHJKOikhS";
	private string playerMiMa; // 0x30
	private const string miMaKey = "TSHYUJKSds";
	private GameDate gameDate; // 0x38
	private string gameDateStr; // 0x40
	[SerializeField]
	private Date_Player zhuJiaoDate; // 0x48
	[SerializeField]
	private Date_Heros herosDate; // 0x50
	[SerializeField]
	private Date_ZiYuan ziYuanDate; // 0x58
	[SerializeField]
	private Date_QianDao qianDaoDate; // 0x60
	[SerializeField]
	private Date_ChengJiu chengJiuDate; // 0x68
	[SerializeField]
	private Date_DaoZeiBaoZang daoZeiBaoZangDate; // 0x70
	[SerializeField]
	private Date_ChongWu chongWuDate; // 0x78
	private Date_QiQiuShop qiQiuShopDate; // 0x80
	[SerializeField]
	private Date_Level guanKaLevelDate; // 0x88
	[SerializeField]
	private Date_BaoShiDong baoShiDongDate; // 0x90
	[SerializeField]
	private Date_MoShiKu moShiKuDate; // 0x98
	[SerializeField]
	private Date_ShengMingShu shengMingShuDate; // 0xA0
	[SerializeField]
	private Date_FuLiLevel fuLiGuanKaDate; // 0xA8
	[SerializeField]
	private Date_TongJi tongJiDate; // 0xB0
	[CompilerGenerated]
	private static ShuJuDate <Instance>k__BackingField; // 0x0
	private int shangChuanCiShu; // 0xB8
	private int xiaZaiCiShu; // 0xBC
	private string shangChuanTimeStr; // 0xC0
	private string xiaZaiTimeStr; // 0xC8
	private const float ziDongSaveTime = 180;
	private bool isZiDongSave; // 0xD0
	private bool IsYanShiSave; // 0xD1
	private const float YanShiTime = 6;
	private float saveTime; // 0xD4
	private float yanShiSaveTime; // 0xD8

	// Properties
	public string PlayerZhangHao { get; }
	public string PlayerMiMa { get; }
	public Date_Player ZhuJiaoDate { get; }
	public Date_Heros HerosDate { get; }
	public Date_ZiYuan ZiYuanDate { get; }
	public Date_QianDao QianDaoDate { get; }
	public Date_ChengJiu ChengJiuDate { get; }
	public Date_DaoZeiBaoZang DaoZeiBaoZangDate { get; }
	public Date_ChongWu ChongWuDate { get; }
	public Date_QiQiuShop QiQiuShopDate { get; }
	public Date_Level GuanKaLevelDate { get; }
	public Date_BaoShiDong BaoShiDongDate { get; }
	public Date_MoShiKu MoShiKuDate { get; }
	public Date_ShengMingShu ShengMingShuDateShuJu { get; }
	public Date_FuLiLevel FuLiGuanKaDate { get; }
	public Date_TongJi TongJiDate { get; }
	public static ShuJuDate Instance { get; set; }
	public int ShangChuanCiShu { get; }
	public int XiaZaiCiShu { get; }
	public string ShangChuanTimeStr { get; }
	public string XiaZaiTimeStr { get; }
	public bool IsZiDongSave { get; }

	// Methods

	// RVA: 0x18A6E98 Offset: 0x18A2E98 VA: 0x18A6E98
	public string get_PlayerZhangHao() { }

	// RVA: 0x18A6F10 Offset: 0x18A2F10 VA: 0x18A6F10
	public string get_PlayerMiMa() { }

	// RVA: 0x18A6F18 Offset: 0x18A2F18 VA: 0x18A6F18
	public void SetZhangHao(string z, string m) { }

	// RVA: 0x18A6FC4 Offset: 0x18A2FC4 VA: 0x18A6FC4
	public Date_Player get_ZhuJiaoDate() { }

	// RVA: 0x18A6FCC Offset: 0x18A2FCC VA: 0x18A6FCC
	public Date_Heros get_HerosDate() { }

	// RVA: 0x18A6FD4 Offset: 0x18A2FD4 VA: 0x18A6FD4
	public Date_ZiYuan get_ZiYuanDate() { }

	// RVA: 0x18A6FDC Offset: 0x18A2FDC VA: 0x18A6FDC
	public Date_QianDao get_QianDaoDate() { }

	// RVA: 0x18A6FE4 Offset: 0x18A2FE4 VA: 0x18A6FE4
	public Date_ChengJiu get_ChengJiuDate() { }

	// RVA: 0x18A6FEC Offset: 0x18A2FEC VA: 0x18A6FEC
	public Date_DaoZeiBaoZang get_DaoZeiBaoZangDate() { }

	// RVA: 0x18A6FF4 Offset: 0x18A2FF4 VA: 0x18A6FF4
	public Date_ChongWu get_ChongWuDate() { }

	// RVA: 0x18A6FFC Offset: 0x18A2FFC VA: 0x18A6FFC
	public Date_QiQiuShop get_QiQiuShopDate() { }
```

## ShenQiBaoShiClass  (line 263021-263300)

```csharp
public class ShenQiBaoShiClass // TypeDefIndex: 3057
{
	// Fields
	public ulong baoShiID; // 0x10
	public uint baoShiLevel; // 0x18
	public uint baoShiZhuanShuID; // 0x1C
	public uint baoShiPinJie; // 0x20
	public BaoShiXiYouDu baoShiXiYouDu; // 0x24
	public bool isZhuangBei; // 0x28
	public int[] zhuangBeiID; // 0x30

	// Methods

	// RVA: 0x18ACD48 Offset: 0x18A8D48 VA: 0x18ACD48
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class ZhuangBeiDate // TypeDefIndex: 3058
{
	// Fields
	public uint ZhuangBeiID; // 0x10
	public uint ZhuangBeiLevel; // 0x14
	public uint ZhuangBeiLevelMax; // 0x18
	public ulong[] XiangQianBaoShiID; // 0x20

	// Methods

	// RVA: 0x18AA99C Offset: 0x18A699C VA: 0x18AA99C
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class MoShiJiNengDate // TypeDefIndex: 3059
{
	// Fields
	public int MoShiJNXuanZe; // 0x10
	public uint MoShiJiNengLevel; // 0x14

	// Methods

	// RVA: 0x18AA9A4 Offset: 0x18A69A4 VA: 0x18AA9A4
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_ZiYuan // TypeDefIndex: 3060
{
	// Fields
	public uint DateID; // 0x10
	public uint JiaYuanLevel; // 0x14
	public uint JiaYuanRenKou; // 0x18
	public uint FaMuChangLevel; // 0x1C
	public uint FaMuChangRenKou; // 0x20
	public ulong MuCaiShuLiang; // 0x28
	public ulong MuCaiShuLiang_LiXianKu; // 0x30
	public uint KuangShiChangLevel; // 0x38
	public uint KuangShiChangRenKou; // 0x3C
	public ulong KuangShiShuLiang; // 0x40
	public ulong KuangShiShuLiang_LiXianKu; // 0x48
	public long ZiYuanLiXianTime; // 0x50
	public uint PaiQianZongCiShu; // 0x58
	public uint PaiQianZhuangTai; // 0x5C
	public ulong PaiQianOverTime; // 0x60
	public uint PaiQianGuanKaID; // 0x68
	public uint PaiQianNanDu; // 0x6C
	public uint PaiQianCiShu; // 0x70
	public int[] ZiDongDuanZaoID; // 0x78

	// Methods

	// RVA: 0x18AB7AC Offset: 0x18A77AC VA: 0x18AB7AC
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_QianDao // TypeDefIndex: 3061
{
	// Fields
	public uint DateID; // 0x10
	public uint QianDaoLevel; // 0x14
	public uint QianDaoJinDu; // 0x18
	public ulong QianDaoGuoQiTime; // 0x20
	public uint QianDaoIsWanCheng; // 0x28
	public uint QianDaoTianShu; // 0x2C
	public uint QianDaoZongShu; // 0x30

	// Methods

	// RVA: 0x18AB7B4 Offset: 0x18A77B4 VA: 0x18AB7B4
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_ChengJiu // TypeDefIndex: 3062
{
	// Fields
	public uint DateID; // 0x10
	public ChengJiuDate[] SuoYouChengJiu; // 0x18

	// Methods

	// RVA: 0x18AB7BC Offset: 0x18A77BC VA: 0x18AB7BC
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class ChengJiuDate // TypeDefIndex: 3063
{
	// Fields
	public uint ChengJiuID; // 0x10
	public uint ChengJiuLevel; // 0x14

	// Methods

	// RVA: 0x18AA9AC Offset: 0x18A69AC VA: 0x18AA9AC
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_DaoZeiBaoZang // TypeDefIndex: 3064
{
	// Fields
	public uint DateID; // 0x10
	public uint DaoZeiYaoShi; // 0x14
	public uint KaiXiangCiShu; // 0x18
	public uint[] BaoXiangIsOpen; // 0x20
	public uint[] BaoXiangLeiXingInt; // 0x28
	public ulong ChongZhiTime; // 0x30

	// Methods

	// RVA: 0x18AB7C4 Offset: 0x18A77C4 VA: 0x18AB7C4
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_ChongWu // TypeDefIndex: 3065
{
	// Fields
	public uint DateID; // 0x10
	public ChongWuDate[] SuoYouChongWuDate; // 0x18
	public uint ChongWuIsZiDongJiNeng; // 0x20
	public uint ZhuaChongZongShu; // 0x24
	public uint ZhuaChongShiBaiShu; // 0x28
	public uint HeChengChongWuCiShu; // 0x2C
	public uint ChongWuSiLiao; // 0x30
	public uint DangTianZhuaChongShu; // 0x34
	public ulong CaoCongChongZhiTime; // 0x38
	public uint[] DianIsOpen; // 0x40
	public ulong ZaDanChongZhiTime; // 0x48
	public uint JinHuaShi_Feng; // 0x50
	public uint JinHuaShi_Huo; // 0x54
	public uint JinHuaShi_Shui; // 0x58
	public uint JinHuaShi_Di; // 0x5C
	public uint JinHuaShi_Guang; // 0x60
	public uint JinHuaShi_An; // 0x64

	// Methods

	// RVA: 0x18AB7CC Offset: 0x18A77CC VA: 0x18AB7CC
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class ChongWuDate // TypeDefIndex: 3066
{
	// Fields
	public uint ChongWuID; // 0x10
	public uint ChongWuLevel; // 0x14
	public uint ChongWuJinHua; // 0x18
	public uint ChongWuJinJie; // 0x1C
	public ulong ChongWuYongJiu_HP; // 0x20
	public ulong ChongWuYongJiu_Damage; // 0x28
	public uint IsXieDai; // 0x30
	public int IsMaoXian; // 0x34

	// Methods

	// RVA: 0x18AA9B4 Offset: 0x18A69B4 VA: 0x18AA9B4
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_QiQiuShop // TypeDefIndex: 3067
{
	// Fields
	public uint DateID; // 0x10
	public uint[] ShangPinKuCunXiaoHaos; // 0x18
	public uint SuiJiShangPinID; // 0x20
	public uint QiQiuGouMaiCiShu; // 0x24
	public ulong ChongZhiTime; // 0x28

	// Methods

	// RVA: 0x18AB7D4 Offset: 0x18A77D4 VA: 0x18AB7D4
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_Level // TypeDefIndex: 3068
{
	// Fields
	public uint DateID; // 0x10
	public uint GuanKaLevel; // 0x14
	public uint IsGameOver; // 0x18
	public uint GuanKaLoad; // 0x1C
	public uint GuanKaNaDu; // 0x20
	public MoWangDate[] GuanKaSuTongTimes; // 0x28
	public ulong GuanKaShengYuHP; // 0x30
	public uint GuanKaShengYuXueTiaoShu; // 0x38
	public float GuanKaJinXingTime; // 0x3C

	// Methods

	// RVA: 0x18AB7DC Offset: 0x18A77DC VA: 0x18AB7DC
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class MoWangDate // TypeDefIndex: 3069
{
	// Fields
	public float[] SuTongTimes; // 0x10

	// Methods

	// RVA: 0x18AA9BC Offset: 0x18A69BC VA: 0x18AA9BC
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class Date_BaoShiDong // TypeDefIndex: 3070
{
	// Fields
	public uint DateID; // 0x10
	public uint DangQianTiLi; // 0x14
	public uint DangQianCengJi; // 0x18
	public string XianJiName; // 0x20
	public ulong ChongZhiTime; // 0x28
	public ulong BaoShiSuiPian; // 0x30
	public BaoShiTongJi SuoYouBaoShiTongJi; // 0x38

	// Methods

	// RVA: 0x18AB7E4 Offset: 0x18A77E4 VA: 0x18AB7E4
	public void .ctor() { }
}

// Namespace: 
[Serializable]
public class BaoShiTongJi // TypeDefIndex: 3071
{
	// Fields
	public ulong baoShiZongShu; // 0x10
	public ulong baoShiShu_Hong; // 0x18
	public ulong baoShiShu_Lv; // 0x20
	public ulong baoShiShu_lan; // 0x28
	public ulong baoShiShu_Huang; // 0x30
	public ulong baoShiShu_Zi; // 0x38
	public ulong baoShiShu_Zuan; // 0x40
	public ulong baoShiShuJie_01; // 0x48
	public ulong baoShiShuJie_02; // 0x50
	public ulong baoShiShuJie_03; // 0x58
	public ulong baoShiShuJie_04; // 0x60
	public ulong baoShiShuJie_05; // 0x68
	public ulong baoShiShuJie_06; // 0x70
```
