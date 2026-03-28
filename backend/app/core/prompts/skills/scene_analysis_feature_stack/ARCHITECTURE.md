# Scene Analysis Feature-Skill Architecture

## Goal

为 `analyze_scene` 提供两条并行主路径：

- `classic` 继续使用 `scene_analysis.txt`。
- `feature_stack / decision_engine` 使用新的 routed base prompt 作为底座。
- 按项目输入特征自动选择并注入不同的 feature skills。
- 保持最终输出协议不变：Markdown 表格、JSON 结构、字段契约与原链路保持兼容。

## New Runtime Mode

- `classic`
  - 只使用原始 `scene_analysis.txt`。
- `feature_stack`
   - 使用 `scene_analysis_routed_base.txt`。
   - 通过显式 slot 渲染注入命中的 feature skills。
- `decision_engine`
    - 使用 `scene_analysis_routed_base.txt`。
   - 先基于项目信息 + 显式输入 + 剧情文本做维度分析。
    - 再路由到：`matched dimension skills + combo skills`。

## High-Level Flow

1. Frontend / caller 提交：
   - `project_metadata`
   - `scene_analysis_mode`
   - `scene_analysis_features`（可选，显式覆盖）
2. 后端读取 `registry.json`。
3. 先归一化输入特征。
4. 若是 `decision_engine`，再结合剧情文本做维度推断。
5. 按维度匹配特征 skill。
6. 按组合规则匹配 combo skills。
7. 将命中的全局/局部 skill 片段映射到 routed slots。
8. 用显式 slot 替换渲染 routed base prompt。
9. 最终仍保持与原链路一致的输出协议。

## Module Boundaries

### 1. Request Layer

File: `app/schemas/agent.py`

新增字段：

- `scene_analysis_mode`
- `scene_analysis_features`

职责：

- 接收模式开关。
- 接收显式特征覆盖。

### 2. Feature Registry Layer

File: `app/core/prompts/skills/scene_analysis_feature_stack/registry.json`

职责：

- 定义模式。
- 定义可枚举特征维度。
- 定义每个维度的候选值、别名、说明、prompt 偏置。

优点：

- 可前后端共享。
- 可配置化扩展，不需要每次改 Python 逻辑。

### 3. Feature Resolver Layer

File: `app/core/prompts/scene_analysis_feature_skills.py`

职责：

- 加载 registry。
- 归一化 `project_metadata` 与 `scene_analysis_features`。
- 解析模式。
- 执行维度分析与文本推断。
- 生成选中的 skill 列表。
- 生成组合 skill 命中结果。
- 生成最终 slot blocks，并按 slot 渲染 routed prompt。
- 输出给接口层用于调试和前端枚举展示的 catalog。

### 4. Prompt Assembly Layer

File: `app/api/endpoints.py`

职责：

- 在 `analyze_scene` 中调用 feature resolver。
- 在 non-classic 模式下加载 routed base prompt。
- 把命中的维度 skill / combo skill 渲染到显式 slot 中。
- 保持 inventory 注入、attention notes 注入、主模板加载逻辑不变。

### Atomic Registry Fragments

registry 中的 value/rule 现在可选声明更细粒度片段，而不是只给一段粗 prompt：

- `global_prompt`
- `environment_prompt`
- `character_prompt`
- `prop_prompt`
- `character_goal_alignment_prompt`

resolver 会优先使用这些显式局部片段；若缺失，才退回到旧的自动 scope 展开。

combo 规则中的 `environment_prompt / character_prompt / prop_prompt` 现在会进入专用 combo local slots，避免再复用 `project_type` 局部槽位造成语义混杂。

### 5. Discovery Layer

File: `app/api/endpoints.py`

新增接口：

- `GET /api/v1/prompts/scene-analysis/features`
- `POST /api/v1/prompts/scene-analysis/route-preview`

职责：

- 给前端或调试工具返回 modes + dimensions + enum values。
- 用于 UI 做下拉、单选、自动补全、默认值建议。
- 用于调试“当前输入为什么命中了哪些 skills”。

## Feature Dimensions

当前已实现并可运行的维度：

1. `project_type`
   - `live_action`
   - `anime`
   - `stylized_3d`
   - `illustrated`

2. `project_language`
   - `zh_cn`
   - `en`
   - `multilingual`

3. `base_positioning`
   - `emotional_drama`
   - `costume_period`
   - `romance`
   - `suspense_thriller`
   - `comedy`
   - `fantasy_sci_fi`

4. `expected_model_family`
   - `midjourney_flux_image`
   - `sdxl_open`
   - `dalle_imagen_firefly`
   - `veo_runway_video`
   - `kling_seedance_wan_video`

5. `era_setting`
   - `contemporary`
   - `near_future`
   - `republic_era`
   - `ancient`
   - `fantasy_period`

6. `region_culture`
   - `mainland_cn_urban`
   - `greater_china_hk_tw`
   - `north_america`
   - `european`
   - `southeast_asia`

7. `generation_workflow`
   - `pure_text_to_image`
   - `image_to_video`
   - `multi_reference`
   - `lora_controlnet_private`
   - `platform_closed_loop`

8. `primary_goal`
   - `script_optimization`
   - `character_creation`
   - `storyboard_previs`
   - `marketing_cover`

9. `secondary_goal`
   - `script_optimization`
   - `character_creation`
   - `storyboard_previs`
   - `marketing_cover`

10. `character_emphasis`
   - `lead_priority`
   - `ensemble_priority`
   - `villain_priority`
   - `supporting_priority`

11. `narrative_density`
   - `dialogue_driven`
   - `action_driven`
   - `mood_driven`
   - `mixed_dense`

12. `commercial_constraint`
   - `short_drama_retention`
   - `longform_storytelling`
   - `ad_conversion`
   - `overseas_social`

13. `modality_focus`
   - `image_first`
   - `video_first`
   - `hybrid`

14. `continuity_priority`
   - `high_character_consistency`
   - `high_space_continuity`

15. `safety_broadcast_level`
   - `general_broadcast`
   - `strict_platform_safe`
   - `youth_friendly`
   - `adult_non_explicit`

## Recommended Future Dimensions

下面这些暂时未全部放进运行时 registry，但从剧本优化 / 人物创作角度很有价值，建议下一轮继续扩展：

1. `visual_complexity`
   - 极简
   - 标准
   - 高奇观
   - 高资产复用

2. `audience_distribution_target`
   - 短剧投流
   - 平台长剧
   - 广告转化
   - 海外社媒

3. `performance_intensity`
   - 内敛微表情
   - 标准情绪
   - 高爆发情绪
   - 风格化夸张

## Feature Source Priority

优先级固定为：

1. `scene_analysis_features` 显式输入
2. `project_metadata`
3. registry 默认行为

即：

- 前端显式指定的值，覆盖 `project_metadata`。
- `project_metadata` 作为自动推断来源。
- `decision_engine` 模式下，若前两者缺失，可结合剧情文本做保守推断。
- 仍未命中时只保留 generic skill，不强行乱注入。

## Decision Engine Routing

当前决策引擎不是自由生成式推理，而是“规则驱动 + 文本提示命中”的路由方式：

1. 显式输入命中
2. project metadata 命中
3. 剧情文本关键提示词推断
4. 维度 skills 生成
5. combo rules 二次命中

目前已适合承载的判断类型：

1. 项目类型判断
2. 语言与文化语境判断
3. 时代设定判断
4. 基础定位判断
5. 预期模型与工作流判断
6. 叙事密度判断
7. 商业投放约束判断
8. 人物重心判断
9. 主目标/次目标双目标组合判断
10. 合规安全等级判断
11. 连续性优先级判断

## Dual-Goal Strategy

当前已支持 `primary_goal + secondary_goal` 的双目标策略，适用于：

1. 剧本优化为主，但人物创作必须同步成立
2. 人物创作为主，但必须反向校验剧情承载能力

设计原则：

1. 角色设计不被视为独立外观包装任务
2. 角色锚点必须回扣剧情功能、关系位置和场景作用
3. 若角色设定无法解释剧情行为，应优先回到剧本分析而非继续加视觉标签

这样做的目的：

1. 可解释
2. 可调试
3. 可灰度验证
4. 不破坏现有主 prompt 的稳定性

## Why Atomic Skills Instead Of Hard-Coded Combination Prompts

原因：

1. 组合维度会指数爆炸。
2. 维度拆开后更容易前端枚举和回显。
3. 便于灰度测试某一个 skill 是否带来收益。
4. 便于日志追踪：可以看到究竟是哪个 skill 被命中。
5. 更适合逐步扩展，不用改一份超大 prompt 总串。

## Output Contract

此架构有一个硬约束：

- feature skill 只能改变“分析侧重点”和“信息强调顺序”。
- 不能改变 `scene_analysis.txt` 的 section order、Markdown 表格格式、Part 2 JSON 结构、字段命名和下游兼容约束。

## Logging And Debugging

建议每次记录：

- mode
- normalized features
- selected skill ids
- feature source（explicit / project_metadata）

这样可以快速判断：

- 为什么某个项目走了某套分析偏置。
- 为什么某个项目没有命中特定 skill。
- 某个 skill 是否导致结果偏移。

## Extension Rule

新增 skill 时优先改 `registry.json`，只有在以下情况才改 Python：

1. 新维度需要新的归一化逻辑。
2. 新来源需要解析嵌套 metadata。
3. 需要改变模式切换策略。

其它普通扩展都应保持为纯配置更新。