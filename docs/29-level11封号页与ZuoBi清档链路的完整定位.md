# 29 - 封号页 level11 与 ZuoBi 清档链路的完整定位

> 本轮目标：回答「`level11` 是怎么被加载的」。
>
> **结论：`level11` 就是 `Assets/Scenes/Level_ZuoBi.unity`，是一张独立的封号场景。
> `ZuoBi` 组件挂在它的 `Main Camera` 上，场景一加载就无条件执行清档三连
> （删存档 / 删 PlayerPrefs / 删宠物池）。
> 触发它的是 `XianShiNiCheng` 里对服务器返回字符串的等值判断。**
>
> 本文只写**有证据支撑**的部分，推断与未知单列一节（§七），不与结论混写。

---

## 一、`level11` 的真实身份

### 1.1 BuildSettings 场景列表（`work/old/data557.unity3d`）

| 索引 | 场景 | 说明 |
|---|---|---|
| 0 | `Assets/Scenes/Level.unity` | |
| 1 | `Assets/Scenes/Level_00.unity` | |
| 2 | `Assets/Scenes/Level_GuanKa.unity` | 关卡界面 |
| 3 | `Assets/Scenes/Level_01.unity` | |
| 4 | `Assets/Scenes/Level_BaMao.unity` | 拔毛 |
| 5 | `Assets/Scenes/Level_BaYa.unity` | 拔牙 |
| 6 | `Assets/Scenes/Level_WaBao.unity` | 挖宝 |
| 7 | `Assets/Scenes/Level_ChongWu.unity` | **抓宠小游戏** |
| 8 | `Assets/Scenes/Level_Loading.unity` | 加载页 |
| 9 | `Assets/Scenes/Level_MoShiKu.unity` | 魔石窟 |
| 10 | `Assets/Scenes/Level_ZhuanPan.unity` | 转盘 |
| **11** | **`Assets/Scenes/Level_ZuoBi.unity`** | **封号页** |
| 12 | `Assets/Scenes/Level_CaiBaoXiang.unity` | 财宝箱 |

`level11` 这个文件名来自 `data.unity3d` 内部的 asset 文件名，与 BuildSettings 的
**索引 11** 严格对应 —— 两者不是巧合。

### 1.2 `level11` 的全部内容（5 个 GameObject / 6 个 MonoBehaviour）

```
Image(pid 1) / Main Camera(pid 2) / TiShi_Text(pid 3) / Canvas(pid 4) / Image_Loading(pid 5)
```

| MonoBehaviour pid | 类 | 备注 |
|---|---|---|
| 22 | `Image` | 136 字节 |
| **23** | **`ZuoBi`** | **32 字节** |
| 24 | `Text` | 304 字节，含红屏文案 |
| 25 | `GraphicRaycaster` | |
| 26 | `CanvasScaler` | |
| 27 | `Image` | |

### 1.3 `ZuoBi` 挂在 `Main Camera` 上且启用

`ZuoBi` 的 MonoBehaviour raw 32 字节：

```
00000000  02000000 00000000 01000000 01000000 b9020000 00000000 00000000
```

| 字段 | 偏移 | 值 |
|---|---|---|
| `m_GameObject.PPtr` | 0 | fileID 0 / **pathID 2 = `Main Camera`** |
| `m_Enabled` | 16 | **1** |
| `m_Script` | 20 | fileID 1 / pathID 697（`MonoScript` 类名 = `ZuoBi`） |

**结论：`level11` 一加载，`ZuoBi.Start()` 必定执行。**

### 1.4 红屏文案就在这个场景里

`TiShi_Text` 的 `Text.m_Text`（MonoBehaviour pid 24，raw 从 `+0x094` 起，
长度前缀 `9C 00 00 00` = 156 字节 UTF-8）：

```
你的作弊行为触动了魔王的底线
魔王很生气，后果很严重
你将得到应有的惩罚！！！
忠告：请按照游戏规则进行游戏
```

**这就是 `docs/14` / `docs/25` 里那张红屏的完整文案。它不在 metadata 里，
是场景资源里的静态字符串** —— 这也解释了为什么搜 `封锁`/`黑名单`/`底线`/`惩罚`/`忠告`
在 metadata 里全是 0 命中。

---

## 二、`ZuoBi` 的破坏性行为

### 2.1 `ZuoBi.Start @ 0x3D0F10`

```asm
0x3d0f6c  ldr  r0, [pc, #0x5c]     ; 字面量池 [0x3D0FD0] = 0xE446F8
0x3d0f70  ldr  r0, [pc, r0]        ; 元数据槽 [0x1215670] = 0x011FB428（运行时填）
0x3d0f74  ldr  r0, [r0]            ; → ShuJuDate.<Instance>
0x3d0f78  ldr  r0, [r0, #0x5c]
0x3d0f7c  ldr  r5, [r0]
0x3d0f80  cmp  r5, #0
0x3d0f84  bne  #0x3d0f8c
0x3d0f88  bl   #0x283fc8           ; 抛 NullReferenceException
0x3d0f8c  ldr  r0, [pc, #0x34]
0x3d0f90  ldr  r0, [pc, r0]
0x3d0f94  bl   #0x7b8b4c           ; ShuJuDate.get_PlayerZhangHao()
0x3d0fa8  bl   #0x3d0fd8           ; JiaRuHeiMingDan(qingQiuID常量, 上者)
0x3d0fbc  b    #0x4a3b10           ; MonoBehaviour.StartCoroutine()
```

与新版 v5.9.2 的差异：新版 `0x18b3810 cbz x0, 0x18b3844`（空值直接跳过），
**旧版没有空值保护**。

### 2.2 `ZuoBi.<JiaRuHeiMingDan>d__1.MoveNext @ 0xE8E99C`

状态 0 —— 发请求：

```asm
0x00e8ea3c  bl  #0xe95a0c    ; new WWWForm()
0x00e8ea40  ldr r6, [r4, #0x10]   ; this.qingQiuID
0x00e8ea68  bl  #0xe95bb8    ; form.AddField("qingQiuID", 值)
0x00e8ea6c  ldr r6, [r4, #0x14]   ; this.playerID
0x00e8ea94  bl  #0xe95bb8    ; form.AddField("playerID", 值)
0x00e8eaac  bl  #0xe93e0c    ; UnityWebRequest.Post(".../heiMingDan.asp", form)
0x00e8eab8  str r0, [r4, #0x18]   ; this.<uwr>
0x00e8eacc  bl  #0xe92710    ; uwr.SendWebRequest()
0x00e8ead4  str r5, [r4, #8]      ; state = 1
```

状态 1 —— 判结果，**读出的内容直接丢弃**：

```asm
0x00e8eb00  bl  #0xe92d94    ; uwr.get_result()
0x00e8eb04  cmp r0, #3             ; ProtocolError
0x00e8eb08  beq #0xe8eb68
0x00e8eb24  bl  #0xe92d94
0x00e8eb28  cmp r0, #2             ; ConnectionError
0x00e8eb2c  beq #0xe8eb68
0x00e8eb48  bl  #0xe92608    ; uwr.get_downloadHandler()
0x00e8eb64  bl  #0xe9147c    ; dh.text → r0（★之后不再使用）
```

收尾 `0xE8EB68` —— **无条件执行**：

```asm
0x00e8ebb8  bl  #0x7bdef8    ; ShuJuDate.QingDang()        ← 清档
0x00e8ebc0  bl  #0x4aa75c    ; PlayerPrefs.DeleteAll()     ← 删账号名
0x00e8ec18  bl  #0x7f4590    ; ChongWuPool.DeleteSave()    ← 删宠物池
```

RVA 交叉确认：`0x7BDEF8` = `ShuJuDate.QingDang`、`0x4AA75C` = `PlayerPrefs.DeleteAll`、
`0x7F4590` = `ChongWuPool.DeleteSave`、`0xE93E0C` = `UnityWebRequest.Post`、
`0xE95A0C` = `WWWForm..ctor`、`0xE95BB8` = `WWWForm.AddField`、
`0xE92710` = `SendWebRequest`、`0xE92D94` = `get_result`、
`0xE92608` = `get_downloadHandler`、`0xE9147C` = `DownloadHandler.get_text`。

> `UnityWebRequest.Result` 枚举实际值：`Success=1 / ConnectionError=2 /
> ProtocolError=3 / DataProcessingError=4`。**不是** DataProcessingError=3。

**关键：不管服务器返回什么、不管是否断网，只要 `level11` 被加载，这三个清档调用都会执行。
`ZuoBi` 不需要「判断」，它本身就是一个破坏动作。**

---

## 三、谁加载了 `level11`

### 3.1 搜 `SceneManager.LoadScene(string) @ 0x6A4C90` 的全部调用点

用 `python tools/find_calls_arm32.py 0x6A4C90`（ARM32 扫 `bl` 指令）得到 10 处：

| 调用点 | 所属方法 | 与封号相关 |
|---|---|---|
| `0x33BDC4` | `BaoShiXiangQianUI.SetUINeiRong` | 否 |
| **`0x3EDB48`** | **`XianShiNiCheng.<GetBaoName>d__17.MoveNext`** | **★ 是** |
| `0x4392C8` | `PlayerData.RemoveJingYan` | 否 |
| `0x53816C` | `LiBaoChongWu.SetLiBaoLingQu` | 否 |
| `0x53B7FC` | `LiBaoPool.OpenLiBao` | 否 |
| `0x53D8C0` | `LiBaoShu.SetLiBaoLingQu` | 否 |
| `0x7B89C4` | `ShengMingZhiShuUI.Update` | 否 |
| `0x8B4FA0` | `MoShiKuManager.RemoveMoShiShuLiang` | 否 |
| `0x8B7300` | `MoShiKuManager.RemoveMoWuSuiPian` | 否 |
| `0xED1960` | `DiXiaChengUIManager.GengXinTiLi` | 否 |

**只有 `XianShiNiCheng.<GetBaoName>d__17.MoveNext` 在封号链路上。**

### 3.2 `GetBaoName` 里的调用上下文（`0x3EDAFC` 附近）

```asm
0x3edafc  bl   #0x9ac598           ; String.op_Equality(服务器返回串, 常量B)
0x3edb00  cmp  r0, #0
0x3edb04  beq  #0x3edb4c           ; 不等 → return false（不切场景）

0x3edb0c  ldr  r0, [pc, #0xc4]     ; 元数据槽 A
0x3edb10  ldr  r0, [pc, r0]
0x3edb14  ldr  r0, [r0]
0x3edb18  ldrb r1, [r0, #0xbb]     ; 读某标志位
0x3edb1c  tst  r1, #2
0x3edb20  beq  #0x3edb34
0x3edb24  ldr  r1, [r0, #0x74]
0x3edb28  cmp  r1, #0
0x3edb2c  bne  #0x3edb34
0x3edb30  bl   #0x283fa4           ; 抛异常（成员访问未初始化）
0x3edb34  ldr  r0, [pc, #0xa0]     ; 元数据槽 B = 场景名
0x3edb38  mov  r1, #0
0x3edb3c  mov  r5, #0
0x3edb40  ldr  r0, [pc, r0]
0x3edb44  ldr  r0, [r0]
0x3edb48  bl   #0x6a4c90           ; ★ SceneManager.LoadScene(场景名)
0x3edb4c  mov  r0, r5              ; return false
```

**`GetBaoName` 的语义：拿到服务器返回串，与某个常量做等值比较，相等就 `LoadScene`。**

### 3.3 `level11` 的加载链路（已确认的部分）

```
XianShiNiCheng.<GetBaoName>d__17.MoveNext
  └─ String.op_Equality(服务器返回, 常量)   ← 命中才继续
      └─ SceneManager.LoadScene(<场景名>)   ← 0x6A4C90
          └─ level11 (Level_ZuoBi.unity) 加载
              └─ ZuoBi.Start() 执行
                  └─ JiaRuHeiMingDan 协程
                      └─ 收尾无条件执行：
                          ShuJuDate.QingDang()
                          PlayerPrefs.DeleteAll()
                          ChongWuPool.DeleteSave()
```

---

## 四、另一条判定路径：`XianShiNiCheng.HeiMingDan`

`XianShiNiCheng` 同时还有 `<HeiMingDan>d__16` 协程（`MoveNext @ 0x3EEF3C`）。
它的状态 1 分支（`0x3EF0A4` 起）语义如下：

```asm
0x3ef0cc  bl  #0xe92d94        ; uwr.get_result()
0x3ef0d0  cmp r0, #3
0x3ef0d4  beq #0x3ef764        ; ProtocolError → 直接结束
0x3ef0f4  bl  #0xe92d94
0x3ef0f8  cmp r0, #2
0x3ef0fc  beq #0x3ef764        ; ConnectionError → 直接结束
0x3ef134  bl  #0xe9147c        ; dh.text
0x3ef148  bl  #0x9ac598        ; String.op_Equality(text, 常量)
0x3ef14c  cmp r0, #0
0x3ef150  beq #0x3ef2c0        ; 不等 → 正常分支

; ── 相等：封号 ──
0x3ef160  ldr r4, [sb, #0x20]  ; XianShiNiCheng.FengHaoUI (offset 0x20)
0x3ef180  bl  #0x4957dc        ; FengHaoUI.SetActive(true)  ← 显红屏
0x3ef1b8  ldr r4, [r0]
0x3ef1d0  bl  #0x7bdef8        ; ShuJuDate.QingDang()       ← 清档
```

`XianShiNiCheng` 类字段（`dump.cs:213402`，TypeDefIndex 4684）：

```csharp
public Text       niChengText;     // 0xC
public Text       dengJiText;      // 0x10
public Image      touXiangImage;   // 0x14
private Button    touXiangButton;  // 0x18
public GameObject niChengUI;       // 0x1C
public GameObject FengHaoUI;       // 0x20   ← 封号覆盖层
private int       clickCiShu;      // 0x24
```

**所以旧版有两条封号表现，共用同一组清档调用：**

| 路径 | 表现 | 触发点 |
|---|---|---|
| `XianShiNiCheng.HeiMingDan` | **主菜单上的红屏覆盖层**（`FengHaoUI.SetActive(true)`） | 服务器返回串 == 常量 |
| `XianShiNiCheng.GetBaoName` → `LoadScene` | **切到 `level11` 全屏红字场景** | 服务器返回串 == 另一常量 |

`level11` 那条更彻底：`ZuoBi` 还会把账号名再上报一次 `heiMingDan.asp`。

---

## 五、`XianShiNiCheng.OnClick` —— 连点头像 15 次的隐藏入口

```asm
0x41a314  ldr  r0, [r4, #0x24]   ; clickCiShu
0x41a318  add  r0, r0, #1
0x41a31c  str  r0, [r4, #0x24]   ; clickCiShu++
0x41a320  cmp  r0, #0xf          ; == 15 ?
0x41a324  poplt {r4, r5, fp, pc} ; 未到 15 次 → 返回
0x41a328  bl  #0x430958          ; PlayerData.GetInstance()
0x41a358  bl  #0x9ac598          ; String.IsNullOrEmpty(某字段)
0x41a35c  cmp r0, #0
0x41a360  beq #0x41a374          ; 为空 → 返回
0x41a364  str r5, [r4, #0x24]    ; clickCiShu = 0
0x41a370  b   #0x41a088          ; OpenSetNiChengUI()  ← 打开改名界面
```

**与封号无关，是一个彩蛋式的改名入口。** 记在这里是因为它容易被误认成调试后门。

---

## 六、顺带纠正：旧版的宠物入口是**场景切换**，不是 UI 面板

`docs/26` 的结论「旧版宠物 UI 无入口、数据层可控」需要补充：

### 6.1 `Level_ChongWu.unity`（`level7`）的内容

886 个对象 / 255 个 MonoBehaviour，类分布：

| 类 | 数量 |
|---|---|
| `Image` | 120 |
| `Text` | 47 |
| `Shadow` | 27 |
| `Button` | 18 |
| `Outline` | 17 |
| **`ChongWuManager`** | **1** |
| **`ChongWuJiaoXue`** | **1** |
| `HRController` | 1 |
| `HRSlider` | 1 |
| `XinTiaoSheng` | 1 |
| `TiShiManager` | 1 |
| `JiaYuanManager` | 1 |
| `HRHotRect` | 1 |
| 其余（`ScrollRect`/`Mask`/`CanvasScaler`/`EventSystem` 等） | 各 1~2 |

**`ChongWuManager` + `HRController` + `HRSlider` + `XinTiaoSheng`（心跳声）
= 就是 `docs/05` 记录的抓宠小游戏**（`MiMa = "HYTGBFRO"`、`KaiShiZhuaPu()`）。

### 6.2 入口

主地图（`level2`）上的草丛由 `ShuaChongWuDian` 管理，点草丛 →
`SceneManager.LoadScene("Level_ChongWu")` → 进抓宠小游戏。

**这跟 TapTap 版（v5.9.2）的「同伴 tab → 我的同伴面板」是完全不同的两套实现。**
旧版没有「同伴」tab 是对的，但「没有宠物入口」不准确。

### 6.3 `MonoScript` 的类名解析位置（工具坑）

`MonoScript` 的 `m_Name` 在 **raw 偏移 0**，不是 8：

```
+000  0C 00 00 00  "CanvasScaler"          ← m_Name（int32 长度 + 字节）
+010  00 00 00 00 + 16 字节 hash           ← 填充 + m_Assembly
+030  0C 00 00 00  "CanvasScaler"          ← m_ClassName
+040  0E 00 00 00  "UnityEngine.UI"        ← m_Namespace
+04C  12 00 00 00  "UnityEngine.UI.dll"    ← m_AssemblyName
```

按「偏移 8」解会读出 `None`（因为偏移 8 的 int32 是 `m_Name` 的尾对齐填充或 hash 段）。

---

## 七、推断与未知（与上面的结论严格分开）

### 7.1 已确认（有反汇编或资源证据）

- `level11` == `Level_ZuoBi.unity`（BuildSettings 索引 11）
- `ZuoBi` 挂在 `level11` 的 `Main Camera` 上，`m_Enabled = 1`
- `ZuoBi.JiaRuHeiMingDan` 的收尾三连无条件执行
- 红屏文案是 `level11` 里 `Text` 组件的静态字符串
- `GetBaoName` 里调 `LoadScene`，条件是「服务器返回 == 常量」
- `HeiMingDan` 里显 `FengHaoUI` 并 `QingDang()`，条件同上，但比较对象是另一个常量
- 旧版宠物是 `level7` 场景切换

### 7.2 未确证（**不要在后续工作中当作事实**）

1. **那两个「常量」的字面值**。静态推到了元数据槽（`0x1215804` 等），
   值是运行时由 `il2cpp_codegen_initialize_method` 填的指针，静态读不出来。
   按 `docs/25` 观察到的 `heiMingDan.asp` 返回值域（`2`/`1`/`-1`），
   最可能是 `"1"`，但**没有直接证据**。
2. **`GetBaoName` 请求的是哪个 URL**。它是「 BaoName」，
   怀疑是 `beiFen.asp` 系列或另一个 `PanDuan` 接口，未定位。
3. **`docs/24` 的「密文分块数必须恒定 37576」归因是否正确**。
   静态只能证明 `ES2Reader` 用的是 `BinaryReader`，
   `BinaryReader.ReadString()` 在长度前缀与实际字节不符时抛 `EndOfStreamException`。
   我们改明文长度后**是否同步改了 ES2 的长度前缀，没有验证过**。
4. **`ShuJuDate + 0x5C` 的语义**。`dump.cs` 说是 `xiaZaiCiShu`（int），
   但 `ZuoBi.Start` 里 `ldr r5, [r0]` 对它做了解引用。
   `get_PlayerZhangHao @ 0x7B8B4C` 的结尾 `ldr r0, [r4, #0x10]` 证明
   `dump.cs` 偏移与实际布局一致，所以这个矛盾**尚未解释**。

### 7.3 因此，`docs/24` §4.3 的归因已加补正

见 `docs/24` §4.3 开头的「⚠ 已由 docs/29 修正归因」块。
该块明确写了：原文把失败归因为「DES 分块数」，**而真实机制尚未动态验证**，
调查者应把 4.3 的结论当作**未定**，而不是定论。

---

## 八、可复用的方法

### 8.1 找「谁调用了某个托管方法」（ARM32）

```bash
python tools/find_calls_arm32.py 0x6A4C90          # 直接搜 bl 到该 RVA
python tools/find_calls_arm32.py --list-plt Load   # 列 PLT 符号
python tools/find_calls_arm32.py --plt LoadScene   # 搜 PLT 桩的调用点
```

原理：ARM32 下 `file_offset == RVA`，`bl` 指令编码 `0xEBxxxxxx`，
高 8 位是 cond=AL + 1011，低 24 位是相对偏移（`target = pc + 8 + (imm << 2)`）。

### 8.2 还原场景里有哪些类

```bash
python tools/unity_scene_classes.py level7 level11
```

流程：遍历 `MonoBehaviour` → raw 偏移 20 的 int32 是 `m_Script.pathID` →
用 `MonoScript` 表反查类名（**`m_Name` 在 raw 偏移 0**）。

### 8.3 从字面量内容反查引用位置

```bash
python scripts/meta_literal.py find heiMingDan    # 得到 [索引]
# 哨兵 = 0xA0000000 | ((索引 << 1) | 1)，再在 .so 里搜该 4 字节小端值
```

`Level_ZuoBi` = `[2625]` → 哨兵 `0xA0001483` → 全文件只出现 1 次（`0x11FE7EC`，
位于连续哨兵表中，与 `Level_BaYa`/`Level_CaiBaoXiang`/`Level_ChongWu`/`Level_GuanKa`/`Level_Loading` 相邻）。

---

## 九、一句话总结

**`level11` 不是「加载页」，而是 `Level_ZuoBi` 这张**封号专用场景**；
`ZuoBi` 组件挂在它的 `Main Camera` 上，场景一加载就无条件清档三连。
它的加载条件是 `XianShiNiCheng.GetBaoName` 收到某个服务器返回字符串；
而 `XianShiNiCheng.HeiMingDan` 则是同一判定的「轻量版」——
只在主菜单上盖一层红屏，也会调 `QingDang()`。
两者比较的常量值都还未能静态读出，是下一步的目标。**
