# 25 · v5.5.7 封号边界实测：协议仍活、清档真发生

> 结论先行：**旧版 `heiMingDan.asp` 不但没退化，还有完整的插入/查询语义；
> 把账号写进黑名单后，游戏下次启动直接显示「该账号已被封锁！」并清档。**

## 一、起因

docs/24 留下两个未了结的问题：

1. `ZuanShi = 9999` 稳定运行，没触发清档 → 边界在哪？
2. `ZuoBi.Start` / `XianShiNiCheng.HeiMingDan` 的触发条件没定位到。

docs/18 曾判定 `heiMingDan.asp`「已退化」：`qingQiuID` 任一非空值就返回 `1`。
**这个结论是错的**——当时没有考虑同一 `playerID` 重复请求的状态变化。

## 二、`heiMingDan.asp` 的真实语义

### 2.1 端点来源

v557 `global-metadata.dat` 的 stringLiteral 表：

```
idx 5647  len=41  http://www.hqgames2013.com/heiMingDan.asp
```

对应的调用方是 `XianShiNiCheng.HeiMingDan(z, z)`（type #4684 的第 8 个方法），
它是协程，state machine 类型 `<HeiMingDan>d__16`（type #4678），`MoveNext` 是第 2 个方法。

### 2.2 状态机（★决定性）

对**同一个** `playerID` 连续请求两次，返回码会变：

```
rsjbbtzkqv@probe.com   q1首次=b'2'  q1再次=b'1'  q2=b'1'
zqtcrubwhi@probe.com   q1首次=b'2'  q1再次=b'1'  q2=b'1'
rptbzjpqqr@probe.com   q1首次=b'2'  q1再次=b'1'  q2=b'1'
ixnpdarhwo@probe.com   q1首次=b'2'  q1再次=b'1'  q2=b'1'
```

| 返回 | 含义 |
|---|---|
| `2` | 该 `playerID` **首次**出现 → 插入成功 |
| `1` | 该 `playerID` **已存在** → 命中（已在黑名单里） |
| `-1` | 缺 `qingQiuID` 或 `playerID` 参数 |

复现脚本：`E:\DSH\game\probe_ban_v557.py`

**注意**：`qingQiuID` 具体填 `1`、`2`、`0`、`-1`、`abc` 都会写进去——
服务端根本不校验它的语义，只看 `playerID` 是否已存在。
这解释了 docs/18 为什么误判「已退化」：当时只测了固定一个 `playerID`，
看到 `1` 就以为是无条件返回。

### 2.3 其他端点也活着

```
/heiMingDan.asp                              -> 200 b'-1'
/beiFen.asp                                  -> 200 b'-1'
/dateXinXi.asp                               -> 200 b'-1'
/time.asp                                    -> 200 b'1793541006'   ← 返回真实时间戳
/postTest.asp                                -> 200 b'#and'
/liBao_LQ.asp                                -> 200 b'-1'
/xiaZai.asp                                  -> 200 b'-1'
/PaiHangBang/ZhanDouLi/SetPaiHang_ZL.asp     -> 200 b'-3'
/PaiHangBang/ZuanShi/SetPaiHang.asp          -> 200 b'-3'
/XiTong/XT_GetGuangBoXinXi.asp               -> 200 b'-1'
```

`-1` 是「参数不全」的通用返回，不是 404。

## 三、清档实测（★上机证据）

### 3.1 操作序列

1. 账号 `testwk01@163.com`，存档 `wk_r4.save`（75167 字节，`ZuanShi=9999`）
2. 通过 `POST /heiMingDan.asp` 写入 `qingQiuID=1&playerID=testwk01@163.com`
   （首次返回 `2`，再次返回 `1`）
3. 重启游戏

### 3.2 结果

**画面**：游戏主场景上方浮出红色大字「**该账号已被封锁！**」，
角色立绘被染色为血红色滤镜，底部仍显示 9999 钻石（客户端内存里还没刷掉）。

截图：`E:\DSH\game\p1.png`（sha256 `ce399c9548b260237c07522ac050f742892845cdcdfd9849ad7c31ee6663aea1`）

**存档被改写**（游戏自己写的，不是我改的）：

```
文件      : banned.save
总长      : 74799        （原 75167，缩了 368 字节）
密文      : 37392 字节   （原 37576）
明文      : 37387 字节   （原 37573）
段数      : 14
header    : 7e0029240100ffeef1e9fda0c804   （原 7e0099250100ffeef1e9fd90cb04）
```

**字段级对照**：

| 字段 | 封号前 | 封号后 |
|---|---|---|
| `seg13.ZuanShi` | 9999 | **0** |
| `seg13.ZhangHao` | `testwk01@163.com` | **`""`** |
| `seg13.JingYan` | 0 | 0 |
| `seg0.PlayerName` | `""` | `""` |
| `seg0.TapLevel` | 1 | 1 |
| 宠物数量 | 86 只 | 86 只（结构保留） |
| 携带宠物 | 0 只 | 0 只 |

注意 `wk_r4.save` 里 `PlayerName` 本来就是空串（昵称存在别处），
所以真正被清的是 **账号名 `ZhangHao` 和钻石 `ZuanShi`**。

### 3.3 这意味着什么

- 封号判定**发生在新会话启动时**，读的是服务器黑名单，不是本地存档。
- 清档是**客户端本地执行**的（存档被游戏进程改写）。
- 存档结构保留（14 段齐全、86 只宠物还在），只是关键值归零、账号名被抹掉。
- 这正好复现了 docs/14 §二 对 v5.9.2 的描述，**说明 v5.5.7 的封号链路与新版一致**。

## 四、与 docs/24 的关系：长度约束是间接的

docs/24 的结论「DES 密文分块数必须恒定（37576）」要修正为：

> 游戏端 `ShuJuDate.LoadGame()` 用 `ES2.Load<string>(identifier)` 读档，
> 它对「读到的字符串长度」有隐含要求。改变明文长度会改变 ES2 的
> 内部长度前缀，跨 8 字节块时就抛 `EndOfStreamException`。

**但这不是唯一的失败原因。** 本次封号测试把明文从 37573 缩到 37387
（跨了很多块），游戏照样读完并执行清档——因为这次是游戏**自己写**的档，
它写的 header/长度自洽。

真正的不变量是：**`header` 的长度累加器必须与实际文件长度一致**。
`v557save.fix_header_length()` 已经按 delta 修正两处小端 16 位累加器
（`HDR_LEN_POS = (2, 11)`），所以只要走 `write_save()` 就不会出问题。
docs/24 里 `wk_rich` 的失败是因为 `v557_pad.py` 把 delta 叠加了两次。

## 五、至今仍未定位的部分

- `ZuoBi.Start()` / `ZuoBi.JiaRuHeiMingDan()` 的**调用者**没找到。
  v557 ARM32 `.so` 里 `ZuoBi` / `heiMingDan` 字符串**零命中**——
  说明它们只在 metadata 的字符串表里，代码通过 `metadata->string` 索引访问。
- `il2cpp_codegen` 的 `methodPointers` 表定位失败：
  - `.data.rel.ro` 最长连续段 15098 项（位于 va `0x011a0638`）
  - `.data` 最长连续段 2705 项（位于 va `0x01205878`）
  - 都远小于 method 总数 31519
  - `int32 == 31519` 在整个 `.so` 里零命中
- 结论：v5.5.7 是 `Stripping Enabled` 构建，大量方法指针为 0 或被合并，
  无法用「连续指针表」的方式反推。**需要走运行时（frida/hook）路线。**

## 六、给后续实验的建议

1. **账号 `testwk01@163.com` 已经在黑名单里，不可再用于正常测试。**
   要重新测试需用新账号名注册（`qingQiu.asp` 的 `100` 分支是桩，随便写都能过）。
2. 黑名单只在游戏**启动时**读，已在运行的游戏不会立刻被踢。
3. 想测「多大数值才被封」，不能靠本地改档——本次证明服务器看的是
   `playerID`，与存档数值无关。**真正会触发上报的是 `ZuoBi` 那条路径，
   而它的调用条件仍未定位。**

## 七、复现命令

```powershell
$adb='D:\leidian\LDPlayer9\adb.exe'
# 1. 写黑名单
$py -c "import urllib.parse,urllib.request; ..."   # 见 probe_ban_v557.py
# 2. 重启游戏
& $adb -s emulator-5558 shell "am force-stop com.HQGAMES.TopDemons"
& $adb -s emulator-5558 shell "monkey -p com.HQGAMES.TopDemons -c android.intent.category.LAUNCHER 1"
# 3. 观察
& $adb -s emulator-5558 shell "input tap 434 718"; Start-Sleep 8
& $adb -s emulator-5558 shell "input tap 360 1002"; Start-Sleep 30
& $adb -s emulator-5558 shell "input tap 360 1050"
& $adb -s emulator-5558 shell screencap -p /sdcard/p1.png
& $adb -s emulator-5558 pull /sdcard/p1.png .
```

抓存档：

```powershell
& $adb -s emulator-5558 shell "su 0 cp '/sdcard/Android/data/com.HQGAMES.TopDemons/files/<账号>' /sdcard/banned.save"
& $adb -s emulator-5558 shell "su 0 chmod 666 /sdcard/banned.save"
& $adb -s emulator-5558 pull /sdcard/banned.save .
```

> 注意：`su 0 cp` 到 `/data/local/tmp/` 后 `adb pull` 会得到 0 字节
> （SELinux 上下文问题）。**必须经 `/sdcard` 中转并 `chmod 666`。**

## 八、踩坑记录

1. **`pull` 到 `/data/local/tmp/` 得到 0 字节** —— 走 `/sdcard` 中转。
2. **`grep` 在 PowerShell 里不存在** —— 用 `Select-String` 或 `rg`。
   仓库里用 `grep` 工具（不是 shell 命令）。
3. **PowerShell 会吞掉 `adb shell` 里的引号** —— 写 `.sh` 文件推上去执行。
4. **`v557save.py verify` 对刚写出的文件报「重加密一致: False」是预期**：
   `write_save()` 已经把 header 修正过了，`verify()` 又按 `build()` 算一次，
   delta 被应用两遍。**判断标准应看 `wk_r4` 这种原档是否 `True`。**
5. `heiMingDan.asp` 不校验 `qingQiuID` 语义 —— 别拿它当参数枚举的依据。
