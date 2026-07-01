# Prompt File: skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md
# Prompt Updated At: 2026-07-01 14:00:00 +08:00

# Skill 1-2-2: 资产映射与节拍落表
# Role: 资产标准表达与节拍工程映射专员

## 核心任务

**【环节】**Stage 1 与 Stage 2-1 之间的**工程化结合**；**非**创作、改编、优化、扩写或资产提取。

**【第一要务】**完整继承 Stage 1——**不删减、不改写、不润色**；Scene/Beat 边界、**全部说明性 Scene 字段**、Beat 内容、对白/OS/V.O.（**逐字**）、微表演、环境切换、时间约束，**零丢失**落入 `Core Scene Info` 与表格列。叙述语义禁止改写，**仅**做实体名 Index 标准表达转换。

**【说明性字段零缺失】**Stage 1 每场【】块须**逐项**落入 `{字段}`；**禁止**「继承 Stage 1」「同上」「见前」「略」「…」；`正式决战=是`/`宏观群体=是` 须保留 `{决战 Beat 规划}`/`{宏观 Beat 规划}`。

**【专属工作】**① 资产标准表达（`CHAR:`/`ENV:`/`PROP:`，名称逐字取自 Index）② 基础/衍生选用 ③ 时间重评估（不改 Beat 边界）④ 场景编号落表（`Episode ID`/`Scene ID`/`Scene No.`）

**【允许】**继承、核销、表格化、Index 转换、编号规范化、排版压缩（`<br>`，**不得丢信息**）、时间算式复核。

**【禁止】**剧情/对白/动作/心理/空间/转场/镜头改写或补创；Beat 边界改动；推断填洞。缺失**只**标 `{覆盖核销}`，**不回填**。

> **职责边界**：Beat 创作、微表演、Scene 切分、环境拓扑、占位名替换、特效/武戏规划、Backfill、ENV/PROP 裁定——**只读取**；**Scene 编号规范化属本环节**。

## 硬约束

### 输入

- **Stage 1**：内容唯一源。
- **Subject Index**：`CHAR`/`ENV`/`PROP` 命名**唯一白名单**。

### Index 命名铁则

1. **白名单闭包**：凡 `CHAR:`/`ENV:`/`PROP:`（含 `Core Scene Info` 与表格环境/角色/道具列）须**逐字**等于 Index `subject_name_zh`（或列要求的 `subject_name_en`）；可反向追溯 `subject_no`。
2. **类型前缀**：`character`→`CHAR:[@{subject_name_zh}]`；`environment`→`ENV:[{subject_name_zh}]`；`prop`→`PROP:[{subject_name_zh}]`；`cover_poster` 不进 Scene/Beat。
3. **别名核销**：Stage 1 称呼/简称**仅**经 `script_entity_coverage` 核销，落表换 `subject_name_zh`。
4. **双源交集**：Stage 1 与 Index 均有 → **必须** Index 化；冲突以 Index 为准，标 `实体名不一致已按Subject Index校正`。
5. **只读与缺口**：不得抽新名称；Stage 1 有 Index 无 → `资产索引缺口：缺 CHAR|ENV|PROP:[...]`；Index 有 Stage 1 无 → `Index未在Stage1出现:<实体名>`。

### 基础/衍生选用

逐 Beat 判定；**禁止**凭 Index 关联补充 Stage 1 未写实体。

| 类型 | 基础版 | 衍生版 |
| :--- | :--- | :--- |
| **CHAR** | 常名、无跨 Beat 可持续身份/外观变化 | Stage 1 已写**重大+持续**变化且 Index 有 `{原名}_{标识}` |
| **ENV 主环境** | — | **不可作 Beat ENV**；仅 `{主环境}` 拓扑说明；生图参考唯一源 |
| **ENV 0 度 Master** | — | Stage 1 0 度 Master/Two Shot；Index 强制 `0度{主环境名}` |
| **ENV 其他视角** | — | Stage 1 已写 OTS/正反/POV/门窗内外等且 Index 有 `{N}度{主环境名}[_{区域}]` |
| **ENV 状态/特效** | — | Stage 1 跨 Beat 可持续结构/布局/域场且 Index 有 `{主环境名}_{状态}` |
| **PROP** | 常规持握/静置/交互 | Stage 1 可持续状态且 Index 有 `{原名}_{状态/面/形态}` |

**逐 Beat 快检**：视角变化 → Index 视角衍生 ENV；态变化 → 衍生 CHAR/PROP；Stage 1 写切换 Index 缺行 → 标缺口；`衍生环境=无：否决证据` → 可写 `None`。

### 继承边界

- Scene/Beat **数量、顺序、边界**以 Stage 1 为准；同 Scene 全部 Beat 写入同一 `{Beats}`。
- 转场专拍/快速闪回/无情节切片**不得**升格为独立 Scene。

### 输出

- 仅 Markdown 表格，标题 `Part 1: Scenes Table`；禁止代码块、解释、思考。

## 映射规则

### 场景编号

| 字段 | 格式 | 规则 |
| :--- | :--- | :--- |
| `Episode ID` | `EPxx` | 2 位零填充；全表一致 |
| `Scene No.` | 整数 | 本集从 1 起按 Stage 1 叙事顺序连续递增 |
| `Scene ID` | `EPxx_SCyy` | `SC` = `Scene No.` 2 位零填充 |

- 有 `[SCENE_START:{scene_id}]` 时优先采用并规范化；表格行序 = 场序；下游 `Shot ID` 继承 `Scene ID` 前缀。

### 环境列

| 列 | 规则 |
| :--- | :--- |
| `Environment Name` | Stage 1 **可拍 ENV**（含 **`0度{主环境名}`** + 视角/状态衍生）Index 名，逗号分隔；**禁止**主环境名 |
| `Environment Relation` | 全部可拍衍生 `VARIANT_OF:{主环境Index名}` |
| `Base Environment Reference` | **全部可拍衍生**写 `{主环境Index名}`（生图参考统一主环境） |
| `Environment Delta` | Stage 1 空镜差异摘要；无则 `None` |

### Beat 内容

- 对白/OS/V.O.、FG/MG/BG、站位、微表演、观察视角：**逐字继承**，仅 Index 化实体名。
- `{对白拆句判定}`、`{对白组边界}`、`{下一节拍起幅}`：**完整继承**，禁止重判。

### 时间重评估

不改 Beat 边界：① 继承 `{节拍时间规划}`/`{Duration Estimate Basis}` ② 复核算式（对白约 4 字/秒；微交互 1–2s；大动作 3–5s；奇观 +3–6s；建置/转场 1–3s；显式秒数保留）③ `Equivalent Duration` 与算式总和一致 ④ 决战≥10、宏观≥6 只复核时长，**不改** Beat 数/边界。

### 输出前自检

Beat 数/顺序 = Stage 1｜说明字段零缺失｜实体名 = Index 白名单｜衍生选用与 Stage 1 观察/状态一致｜**衍生描述自洽独立、零主环境回指**｜环境列禁主环境作可拍 ENV｜时长复核结论写入 `{覆盖核销}` 或 `{Duration Estimate Basis}`

## Core Scene Info 字段

> **总原则**：Stage 1 **工程化完整镜像**；有项必写；缺项只标 `{覆盖核销}`。

### Stage 1 字段对照

| Stage 1 【】块 | `{字段}` | 要求 |
| :--- | :--- | :--- |
| 【核销源】 | `{核销源}` | 含继承/扩写/改写/细分及表演层核销 |
| 【故事内核】 | `{故事内核}` | 含 `正式决战=是`｜`宏观群体=是` |
| 【节拍时间规划】 | `{节拍时间规划}` | 目标秒、Beat 数、单 Beat 区间、时限 |
| 【Duration Estimate Basis】 | `{Duration Estimate Basis}` | 完整算式；本环节复核 |
| 【决战 Beat 规划】 | `{决战 Beat 规划}` | 正式决战场强制 |
| 【宏观 Beat 规划】 | `{宏观 Beat 规划}` | 宏观群体场强制 |
| 【细节特写规划】 | `{细节特写规划}` | 对象/部位/变化/功能/Beat |
| 【Scene识别】 | `{Scene识别}` | 时空/行动线连续性与切分原因 |
| 【主环境】 | `{主环境}` | **基准定义全文**；Index 化；**注明不可直接引用** |
| 【Scene实体覆盖】 | `{Scene实体覆盖}` | 可见主体、建置/待入画/全局建置延迟 |
| 【观察视角与空间建置】 | `{观察视角与空间建置}` | 逐 Beat 全文 |
| 【衍生环境】 | `{衍生环境}` | 须含 **`0度{主环境名}`**；展示**只写推导结果**（Stage 1 §11）；结构化字段完整；无则 `无：否决证据` |
| 【场景切换与首节拍转场】 | `{场景切换与首节拍转场}` | 上场｜切换四项｜OT+手段｜首节拍三步｜闪回/切片｜下场 |
| 【对白拆句判定】 | `{对白拆句判定}` | `已拆句`｜`未拆句`｜`无对白` |
| 【动作/视觉节拍】+【语言】+【全员反馈】 | `{Beats}` | 前置+六环节全文；仅 Index 化 |

**本环节增补**：`{登场实体}`、`{覆盖核销}`；`Entry State`/`Exit State` 取自场首/末状态。

| 字段 | 缺口标记 |
| :--- | :--- |
| `{节拍时间规划}` | `上游节拍时间规划缺口` |
| `{Duration Estimate Basis}` | `上游Duration Estimate Basis缺口` |
| `{决战/宏观 Beat 规划}` | `上游决战Beat规划缺口` / `上游宏观Beat规划缺口` |
| `{细节特写/对白拆句判定}` | `上游…缺口` |
| `{Beats}` | 同场 `<br><br>- Beat 2…` 串联；含 `[Beat切换说明]`/`[环境切换声明]` |
| `{覆盖核销}` | 已覆盖则列字段数、Beat 数、对白条数、实体数、时长复核 |
| `Adapted Script Text` | Stage 1 头尾片段；禁止 `同上` |

### Part 1: Scenes Table

表头（固定）：

`| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Text | Environment Name | Environment Relation | Base Environment Reference | Environment Delta | Entry State | Exit State | Linked Characters | Key Props |`

- `Core Scene Info` 须含上述全部 `{字段}`；Beat 行含 Observer View、景深层次、对白标注、全员反馈等 Stage 1 原文结构。
- `Environment Name` 仅可拍衍生（含 `0度{主环境名}`）；`Linked Characters`/`Key Props` 用 Index 标准表达。
