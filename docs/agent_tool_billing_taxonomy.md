# AI Agent 工具调用与计费分类基线（AIStory）

> 目的：统一“系统功能分类”“Agent 调用工具分组”“计费 task_type”三套口径，作为后续工具路由、计费规则与后台运营配置的共同依据。

## 1. 系统功能域分组（全局视图）

1. **系统 API 设置与密钥治理**：共享/个人 API 配置、系统目录、导入导出、deprecated 管理。
2. **Agent 与通用工具**：Agent 指令编排、翻译、提示词润色。
3. **项目与协作管理**：项目 CRUD、共享协作、全局元数据。
4. **剧情策划（Project 级）**：全局故事设定、小说解析、全局导入导出。
5. **剧集与脚本生产（Episode 级）**：集级剧情生成、场景脚本批处理。
6. **场景生命周期**：场景 CRUD、重生成、AI 结果应用。
7. **镜头与拆镜**：镜头 CRUD、AI 拆镜、批量任务。
8. **实体管理**：角色/物体实体 CRUD、实体分析、角色生成。
9. **媒体生成与任务队列**：图片/视频同步与异步生成、任务池管理。
10. **资产库治理**：素材上传、查询、删除、重绑定、分析。
11. **身份认证与用户中心**：注册登录、邮箱验证、密码、用户资料。
12. **计费充值与后台运维**：充值、规则、交易、调账、运行诊断。

---

## 2. 当前 Agent 已实现工具（代码实装）

- `generate_project_asset`
- `generate_image_text_to_image`
- `generate_image_image_to_image`
- `generate_video_text_to_video`
- `generate_video_image_to_video`
- `create_project`
- `analyze_script`

说明：以上来自 `backend/app/services/agent_service.py` 的工具执行分支。

---

## 3. 当前计费 task_type 基线（代码实装）

### 3.1 消费类

- `llm_chat`：对话/文本生成、故事脚本生成链路。
- `analysis`：通用分析（场景分析、资产分析等）。
- `analysis_character`：实体/角色视觉分析（支持回退到 `analysis`、`llm_chat`）。
- `image_gen`：图片生成。
- `video_gen`：视频生成。

### 3.2 账务类（非消费）

- `recharge`：充值入账。
- `admin_adjustment`：管理员调账。

说明：`billing_service` 存在 task_type 回退链：`analysis_character -> analysis -> llm_chat`。

---

## 4. 统一映射规则（建议落地口径）

| tool_group | 适用功能 | default_task_type | source_categories | billable |
|---|---|---|---|---|
| `agent_llm_ops` | Agent 文本推理、翻译、剧情脚本生成 | `llm_chat` | `LLM` | true |
| `vision_analysis` | 场景/资产视觉分析 | `analysis` | `Vision`,`LLM` | true |
| `entity_vision_analysis` | 实体分析 | `analysis_character` | `Vision`,`LLM` | true |
| `image_generation` | 图片生成（T2I/I2I） | `image_gen` | `Image` | true |
| `video_generation` | 视频生成（T2V/I2V） | `video_gen` | `Video` | true |
| `billing_recharge` | 充值链路 | `recharge` | `System_Payment` | false |
| `billing_admin_ops` | 管理员调账 | `admin_adjustment` | `admin` | false |
| `config_management` | 设置与密钥治理 | *(none)* | `LLM`,`Vision`,`Image`,`Video`,`Tools`,`Voice`,`System_Payment` | false |

---

## 5. 高频接口映射（用于工具路由与计费）

- `POST /agent/command` -> `agent_llm_ops`（主）+ 可能触发 `image_generation`/`video_generation`（子工具）。
- `POST /tools/translate` -> `agent_llm_ops` / `llm_chat`。
- `POST /analyze_scene` -> `vision_analysis` / `analysis`。
- `POST /assets/analyze` -> `vision_analysis` / `analysis`。
- `POST /entities/{entity_id}/analyze` -> `entity_vision_analysis` / `analysis_character`。
- `POST /generate/image` -> `image_generation` / `image_gen`。
- `POST /generate/video` -> `video_generation` / `video_gen`。
- `POST /billing/recharge/*` -> `billing_recharge` / `recharge`（非消费）。
- `POST /billing/users/{user_id}/credits` -> `billing_admin_ops` / `admin_adjustment`（非消费）。

---

## 6. 使用建议（实施优先级）

1. **统一配置源**：以 `backend/app/data/agent_tool_billing_baseline.json` 作为单一事实源（SSOT）。
2. **Agent 调用前置检查**：按 `tool_group -> default_task_type` 执行余额预检查/预冻结。
3. **结算一致性**：所有成功调用写入统一 `task_type`，失败走 `log_failed_transaction`。
4. **运营对齐**：`/billing/options` 与后台定价 UI 读取同一 task_type 枚举。
5. **渐进扩展**：新增工具必须先补 baseline（key、group、task_type、billable）再上线。
