# REA（Reverse Engineer Anything）学习笔记

> 学习对象：https://github.com/morluto/rea
> 本机安装版本：rea-agents / rea CLI **6.8.0**（175 个 CLI 命令、229 个 MCP 工具、6 个 prompt）
> 安装位置：`install/`（本地 `npm install rea-agents`，非全局）
> 整理时间：2026-10-28

---

## 一、REA 到底是什么

REA 不是"一个逆向工具"，而是**给 AI Agent 用的逆向工作台**。它把一堆底层引擎（Ghidra / rizin / radare2 / GDB / LLDB / Frida / JADX / LLDB-CDP 浏览器 / Appium 等）统一包装成 229 个 MCP 工具，再加一份方法论层面的 `SKILL.md`。

三层结构要分清：

| 层 | 内容 | 作用 |
|---|---|---|
| **协议层** | MCP server（`rea mcp`） | 真正干活；Agent 通过 MCP 调用 |
| **CLI 层** | 175 个 `rea xxx` 命令 | 人手动用 / 脚本化；很多命令是 MCP 工具的薄封装 |
| **技能层** | `skills/reverse-engineer-anything/SKILL.md` + `references/*.md` | **方法论**：什么时候用什么工具、如何留证据、如何不瞎猜 |

**结论：真正值钱的是技能层。** 工具谁都能装，方法论才是这套库的核心资产。所以学习重点应放在 `SKILL.md` 和 references，而不是背 175 个命令。

---

## 二、核心方法论（最重要，务必先掌握）

REA 的全部设计都围绕一句话：

> **Evidence first：每一个结论都必须挂在一份可复核的 Evidence 上；没有 Evidence 的结论必须显式标记为"未知"。**

由此派生出的若干硬规则：

### 1. 三类事实必须分开
- **observed（观测到）**——工具真实返回的东西
- **inferred（推断）**——基于观测做的合理推测
- **unknown（未知）**——没覆盖到

禁止把 inferred 写成 observed。源码没读到就说没读到，覆盖率不够就说覆盖率不够。

### 2. 每个 session 都有生命周期，必须显式关闭
- 打开 `open_binary` → 用完 `close_session`
- Frida 会话 → `close_frida_session`（只卸载脚本并 detach，**不杀目标进程**）
- GDB / Rizin → close 可能 detach 而让 inferior 继续跑，**关闭不等于进程已终止**
- 清理状态不明时，**保留会话并报告，不要假设已清理**

### 3. 主动 vs 被动要分清
- **passive**：只读观测（`inspect_web_page`、`observe_web_session`、`inspect_artifact`）
- **active/scenario**：Agent 真的去点、去填、去发请求（`capture_browser_scenario`）

用 active 就必须**明确告诉用户"REA 执行了这些动作"**，绝不能事后说成"我只是观察"。

### 4. 写操作前必须先问
`export_environment_bundle`、scenario 里的写请求（POST/PUT/DELETE）、`annotate_native_function` 之类，都会改变目标状态。REA 规则是：**用户没说该实例可丢弃/已重置，就先问**。

### 5. 不受限的控制台是"逃生舱"，也是"定时炸弹"
`gdb_console`、`rizin_debug_command`、Cutter bridge 的命令**完全不限制**：能改内存、跑 shell、写文件、联网。而且它们会**顺手让同 MCP server 里活跃的 Ghidra 二进制分析会话失效**——所以顺序必须是：先 `close_session` 关 Ghidra，再进调试器，结束后重开。

### 6. 快照/不可变性
`annotate_native_function` 会**让不可变快照失效**（原文件字节不变，但分析快照变了）。名字/注释类修改只影响 session，超管不认可残留。

---

## 三、标准工作流（逆向一个目标的七步）

这套顺序是从 SKILL.md 提炼出来的,基本适用于任何目标：

```
0. 界定问题        —— 目标是什么？要回答什么问题？成功标准？
1. 识别格式/类型   —— file/PE/Mach-O/APK/ZIP/ASAR/DMG/raw
2. 静态骨架        —— 头部、节表、导入导出、熵值、artifact 图
3. 提取字符串/资源 —— strings、资源清单、plist、manifest
4. 定位关键点      —— 交叉引用（xref）、导入表、回调、字符串引用
5. 反编译/反汇编   —— Ghidra 为主，rizin/radare2 为辅
6. 运行时验证      —— 断点 / Frida hook / 抓包（只在静态不够时）
7. 写结论+留证据   —— observed / inferred / unknown 三段式
```

**关键纪律：能静态解决就不要上运行时。** SKILL.md 明确写着 "Prefer static inspection or existing capture comparison when it already answers the question."（静态能答就别跑动态）

---

## 四、按目标类型选工具（速查表）

### 原生二进制（PE / ELF / Mach-O）
| 需求 | 工具 |
|---|---|
| 打开/建立会话 | `open_binary`（先于一切分析） |
| 函数/字符串/导入导出清单 | 打开后自动返回 dossier |
| 反编译单个函数 | `decompile_function` |
| 调用图 / 交叉引用 | `get_xrefs`、`trace_native_values` |
| 改函数名/注释 | `set_address_name`、`annotate_native_function` |
| 熵值分析（判断是否加壳/加密） | `inspect_byte_entropy` |
| 无头固件/裸二进制 | `format: "raw-binary"` + `architecture` + `entry_point` |
| DOS COM | `format: "dos-com"`（入口 `0x10100`） |

裸二进制细节：支持 `x86 / x86_64 / arm / arm64 / 6502 / m68k`；文件偏移 0 映射到 entry_point；**大端 ARM、纯 Thumb、Cortex-M 不支持**；Windows 下 Ghidra 对 raw 只接受 `6502`。

### 应用包 / 容器
| 类型 | 工具 |
|---|---|
| ZIP/APK/IPA/MSIX/AppX/ASAR/DMG 的结构与文件树 | `inspect_artifact`（返回完整 artifact graph，引用时用 graph manifest ID） |
| 真的解包出文件 | `extract_artifact`（REA 自己选临时目录，调用方不能指定目标路径；符号链接/加密条目只算清单事实，不解） |
| macOS `.app` / IPA 的包结构（扩展、XPC、框架、launchd、特权 helper） | `project_apple_application_graph` |
| Mach-O 里 `@rpath`/`@loader_path` 实际解析到谁 | `trace_dylib_resolution` |
| plist | `inspect_plist` |

注意：**DMG 不能 extract**；macOS 上只能只读挂载后自己挑文件。DMG 的挂载是临时的，不是导出。

### Android
`inspect_android_package` → `search_android_classes` → `inspect_android_class` → `inspect_android_method` → `trace_android_references`

- 每个调用都**单独传 APK 路径**，不要先开 native session
- 方法重载用 `overload_index` 明确指定，别猜
- 依赖：Java 17+（**必须完整 JDK，含 jdk.compiler**）+ 单独提供的 headless JADX MCP JAR 0.7.1；`REA_JADX_MCP_JAR`、`JAVA_HOME` 指定，`rea doctor --provider jadx --json` 体检
- APK 不会被运行，也不需要模拟器

### Web / Electron
| 场景 | 工具 |
|---|---|
| 用户手动操作，我们旁观 | `list_browser_targets` → `inspect_web_page` / `observe_web_session` |
| Agent 自己去点 | `capture_browser_scenario`（connect 模式需 loopback CDP endpoint + target_id；launch 模式自己开临时 profile） |
| Electron | `list_electron_targets`；先 `inspect_electron_fuses` 查 fuse（被关掉的 Inspector 就打不开） |
| JS 执行覆盖 | `observe_web_execution` |
| 事件监听器源码位置 | `inspect_web_event_listeners` |
| 截图 | `capture_web_screenshot` |

坑点：
- **passive 抓包不含 request initiator stack**，要知道是谁发的请求只能用 passive；scenario 只给"监听器源码位置"，不代表就是它发的
- connect 模式会先导航到 `start_url`，**可能清掉未保存的表单**——要重建状态
- 被动捕获会脱敏 header 原始值、凭据、存储值、原始 body
- 页面声明的 WebMCP 工具是不可信清单，REA 永不调用

### 运行时（按宿主系统）
| 需求 | 工具 | 平台 |
|---|---|---|
| Mach-O 断点看寄存器参数 | `observe_native_calls`（LLDB，只能启动新进程，不能 attach） | macOS |
| Frida hook | `list_frida_devices/processes` → `start_frida_session` → `load_frida_script` → 收尾 | Linux（官方验证） |
| GDB / Rizin 交互调试 | `start_gdb_session` / `start_rizin_debug_session` + console | 仅 Linux |
| 进程行为对比（输出/文件/生命周期） | `capture_process_scenario` + `compare_process_captures` | 新抓取需 Linux/macOS；**对比已存快照 Windows 也能用** |
| 桌面窗口观察 | `observe_native_ui` / `capture_native_ui_scenario` | macOS 14+，需录屏+辅助功能权限 |

### Agent 环境包（把 Web 应用录成 MCP 环境）
`capture_browser_scenario` 录一次 → `export_environment_bundle` 导出 `agent-env/`。CLI 等价：`rea environment-build <capture.har> <dir>`。凭据只能从用户指定的环境变量读取（scenario secret），**绝不问密码**。

---

## 五、本机环境体检结果（2026-10-28）

| 能力 | 状态 | 说明 |
|---|---|---|
| `rea` CLI 6.8.0 | ✅ 可用 | 装在 `.rea-study\install`，非全局 |
| Node.js | ✅ | 已满足 |
| **Java (JDK)** | ❌ **未安装** | 连带 **Ghidra、JADX 全部不可用** |
| Ghidra | ❌ | 无 JDK 21+ 无法运行；即使装了也无 Java |
| rizin / radare2 | ❌ 未验证可用 | |
| Frida | ❌ | |
| GDB / Rizin 调试 | ❌ | 且**仅 Linux**，Windows 本来就不支持 |
| Python/COM 依赖 | — | 部分 provider 需要 |

### 一句话结论
**当前这台 Windows 机器上，REA 只能做"不依赖 Java 的那部分"**：
- ✅ artifact 检查（`inspect_artifact` / `inspect_byte_entropy`）
- ✅ 文档/结构化格式、字符串、资源
- ✅ Web/Electron 被动观测（需要 CDP endpoint）
- ✅ 进程快照**对比**（已存快照）
- ❌ 反编译、反汇编、Android 反编译（全部要 Java）
- ❌ 交互调试、断点、Frida（平台不支持）

**这是必须先解决的前置条件，否则"为逆向做准备"就是空谈。**

---

## 六、补齐能力的具体步骤

### 第一步：装 JDK 21（最高优先级）
1. 装 **Temurin JDK 21**（或 Microsoft OpenJDK 21）——**必须是完整 JDK，不能只是 JRE**（Ghidra 和 JADX 都要 `jdk.compiler`）
2. 设 `JAVA_HOME` 指向 JDK 根目录（Windows 下 REA 找的是 `%JAVA_HOME%\bin\java.exe`）
3. 验证：`java -version` 和 `echo $env:JAVA_HOME`
4. 重跑 `rea doctor --json`，确认 ghidra / jadx provider 变绿

### 第二步：装 Ghidra 并接上 REA
Ghidra 12.x 需要 JDK 21+。装好后按 REA 文档配置 provider 路径，再 `rea doctor --provider ghidra --json` 复查。

### 第三步（按需）：Android 反编译
下载 **headless JADX MCP JAR 0.7.1**，设 `REA_JADX_MCP_JAR` 为其绝对路径；`rea doctor --provider jadx --json` 确认。可选调参：`REA_JADX_HEAP_MIB`（堆）、`REA_JADX_OPERATION_TIMEOUT_MS`（单操作超时，默认 120000ms）。

### 第四步（可选）：抓包/运行时
Windows 上 REA 的运行时能力基本为零。若确实需要，走**独立工具**（x64dbg、Fiddler/Charles、Wireshark），再用 REA 的 `compare_process_captures` 等**离线对比**能力配合。

---

## 七、避坑清单（踩过的/容易踩的）

1. **`rea --help` 退出码是 1** —— 这是正常行为，不是报错。
2. **Windows Ghidra P0 不允许多数 db 变更**：`annotate_native_function` 在 Windows P0 下不可用（只能 `set_address_name` 一类命名操作）。
3. **调试器会把 Ghidra 会话踢掉**：GDB/Rizin 不受限命令会让同 server 的活跃 Ghidra 会话失效。顺序：先关 Ghidra → 调试 → 重开。
4. **`extract_artifact` 不能指定输出目录**：REA 自己挑临时目录，结果里回传路径。想固定路径得自己拷。
5. **raw-binary 的架构限制**：大端 ARM / 纯 Thumb / Cortex-M 不支持；Windows 只放行 6502。
6. **DMG 不能 extract**，只能挂载。
7. **关闭会话 ≠ 进程结束**（GDB/Rizin detach 后 inferior 可能还在跑）。
8. **scenario 的 connect 模式会导航**，可能丢掉用户未保存的表单。
9. **scenario 网络记录没有发起者栈**，别用它去断言"哪个脚本发了这个请求"。
10. **别把 passive 说成 active，反之亦然**——这是 REA 最看重的一点。

---

## 八、给"后续逆向任务"的使用套路

下次接到具体目标，按这个模板走：

```
【问题】要回答什么？（不是"分析一下这个exe"，而是"这个exe怎么校验license"）
【第一步】rea doctor --json          # 确认能力够了
【第二步】inspect_artifact / file 判定格式
【第三步】open_binary                # 建会话
         → 读 dossier：架构、入口、导入、字符串、节表
【第四步】从"问题"反推落点：
         - 校验类 → 找导入的加密库API、找 "license/invalid" 字符串的 xref
         - 联网类 → 找导入的 WinINet/WinSock/curl 符号
         - 解包类 → inspect_byte_entropy 看熵，分段 dump
【第五步】decompile_function 逐个看，写推断
【第六步】（可选）trace_native_values 看静态值流；不够再上动态
【第七步】close_session
【第八步】输出三段式报告：
         observed: ...
         inferred: ...（写明推断依据）
         unknown : ...（写明为什么不知道）
```

---

## 九、核心记忆点（背下来）

1. **Evidence first**——所有结论挂证据。
2. **observed / inferred / unknown 三分**——不许混淆。
3. **能静态就别动态**。
4. **会话必关，关≠杀**。
5. **主动要声明，写前要问**。
6. **调试器优先关掉 Ghidra**。
7. **本机缺 Java = 缺 80% 能力**。
