# entity_design_prop.md

## 四、 道具专项规范 (Prop Design & Prompts)

### 4.1 Prop Prompt Template
#### 4.1.1 基础原则与信息架构 (Base Structure & Fields)
- **专属字段回写契约**：严格落实全局回写，不仅要写基础形态，还必须明确该物体是什么、属于手持还是静置、当前处于何种单一物理状态特征（如磨损/氧化/裂痕/液位/开合）。必须全部转译进 prompt 主体段落。
- **道具纯白底硬约束（新增强制）**：所有道具（prop）的 `generation_prompt_cn/en` 必须显式要求道具四视图生成在**绝对纯白、无杂色、无灰底、无米白、无渐变、无阴影脏污残留**的统一背景画板上。白底不是“接近白”或“干净背景”，而是标准纯白底；四个视角必须共同落在同一整块连续纯白画布中，禁止出现摄影棚灰底、柔灰无缝纸、奶油白、暖白、冷灰白、环境反色污染或任何背景色偏。
- **道具题材适配规则（新增强制）**：道具的造型语言、材质、颜色、磨损、装饰复杂度必须服从上游项目的总体定位，并始终跟随剧本风格。喜剧、治愈、浪漫向优先整洁、亲和、明快、可读；情感剧强调真实生活温度与细腻使用痕迹；仙侠可加入法器感、玉石金属木作纹样、灵光和礼制秩序；写实与真人剧默认强调真实材质、可信结构、功能痕迹与自然老化；恐怖惊悚题材才允许强化陈旧斑驳、不安污迹、冷硬反光和异常质感，但不可无依据地把普通题材道具设计成阴森破败。
- **道具光学落地规则**：道具 prompt 直接继承并严格执行第 1.3 节“主光源先行与光影排序总规则”。道具专项仅补充：主光必须优先揭示体块与材质锚点，且在白底条件下写清边缘分离与暗部细节托举方式。
- **历史器物与礼制道具规则（新增强制）**：若上游存在明确年代、地域与文化背景，道具必须符合当时当地真实或可信同源的器物体系，体现材质来源、工艺技术、使用礼序与身份象征。宫廷、官署、豪门、宗教仪式相关道具要明确区分礼器、陈设器、日用器、文书器、兵仪器等类别，并通过纹样、做工、摆放方式和保存状态体现等级与制度；不得把现代审美化的装饰件、错误时代的金属结构、错置图案或跨地域混搭器物塞入历史场景。
- 手机支架强制补全规则 (Standalone Phone Bracket Rule)：如果 Subject Index 提供的道具定位为“手机”或“直播手机”，且前置描述中未明确说明其置于支架上，可在**同一 Subject 的描述层**补充“该手机安装在手机支架上 (mounted on a phone stand/tripod)”的设定，确保其作为独立静物展现，避免因暗含持握动作带来手部残留风险。
- **道具关联补齐与成套规则 (Prop Correlation & Completion Rule)**：在设计道具时，必须进行常识性的强关联检查，以确保道具在视觉与功能上的完整性。允许在**同一 Subject 的描述层**补足其已存在的成套关系（如“桌+椅”为同一上游组合实体时补全其搭配关系写法）。
- **道具补齐边界统一口径**：若任一道具补齐动作会产生新的独立 Subject，统一回到本节开头 Node 4 的“上游清单只读与缺口回流”主规则处理。
- **真人写实道具真实性门禁（新增强制）**：若项目属于真人写实剧，本条在上文题材适配基础上继续加严：道具必须符合真实生产、采购、使用与维护逻辑，优先写出真实材质、连接结构、受力位置、握持/摆放习惯、边角磨损、清洁状态和功能痕迹；职业道具还必须与具体行业匹配，避免落成概念设计款、伪专业物件或过度奢侈化展示模型。

#### 4.1.2 道具锚点只读机制 (Prop Anchor)
- **只读锚点提取**：每个关键道具必须提供 2-3 个不可变识别结构作为短语锚点（如 `worn brass police badge`）。绝不使用瞬态特征。

---

  

## 六、输出模板（严格）

- 确保遵守最终输出结果格式，仅保留 JSON 本身。
- **唯一输出物**：全文仅输出**唯一的一个大 JSON 代码块**，里面只需包含 `props`（道具）。
- **单段结构保底规则**：最终 JSON 顶层必须存在 `props` 数组键。无实体时输出空数组 `[]`。

### Entities JSON (Strict Schema)

**关于 JSON 格式结构的最高优先级警告 (CRITICAL STRUCTURAL WARNING)**：JSON 必须是唯一的单个对象；根节点固定含 `props` 键；空类输出空数组，数组严格按 `subject_type` 路由，错分即重写。

#### JSON 内容共性硬约束
- **Scene Subjects 零遗漏硬约束**：JSON 数组必须完整覆盖前置提供/识别出的**所有**实体；不得只保留“核心代表项”。任意防遗漏声明都不如直接在 JSON 里全量打满重要。
- **分类完整性硬约束（新增强制）**：最终核对时，除了检查条目总数，还必须逐条检查“输入 Subject Index 的实体类型”与“输出 JSON 所在数组”是否一一对应。总数正确但数组归类错误，仍然视为失败。
- **类型专属字段硬约束（新增强制）**：四个数组不仅归属不同，字段模板也必须按类型严格分离。`characters[]` 才允许使用 `gender`、`role`、`archetype`、`appearance_cn`、`clothing`、`action_characteristics` 等角色专属字段；`props[]` 允许使用物件状态/类型字段（如 `type`）；`environments[]` 与 `posters[]` 应使用环境/海报字段（如 `atmosphere`、`visual_params`）并围绕空间或海报构图组织描述。禁止把角色字段复制到 prop/environment/poster，对道具/环境/海报借壳套用角色对象模板，或让不同数组只靠 `name` 区分、其余字段结构完全同构。
- **命名绝对防篡改与零容错校验（极度严格）**：所有资产的 `name` / `name_en`（及其层级名称）必须与输入 `subjects index` 完全一致；输出前必须逐条执行“输入 `subjects index.name` -> 输出 JSON `name`”一对一核对。任意字符差异（含空格、全半角、大小写、下划线、连字符、后缀、括号）都视为严重错误，必须修正后再输出。
- **description_cn 传导硬约束**：必须将上游输入的 `entity_attributes` 字段属性原文一字不改、**原样填写**到本实体对应的 `description_cn` 字段中，不要做任何二次创作或删减。
- **固定双语输出字段契约**：严格沿用定义的中英双轨字段要求，特别是 `generation_prompt_cn/en`。
- **继承约束**：每个实体都必须提供 `visual_dependencies`（数组）与 `dependency_strategy`（包含 `type` 和 `logic` 两个对象属性），详见前文状态演化链要求。

#### 统一 JSON 示例（必读参照）
以下为 props 的形态示例：
```json
{
  "props": [
      {
          "subject_no": "S102",
          "name": "警徽挂绳证件卡",
          "name_en": "Police ID Badge Lanyard",
          "base_name_en": "Police ID Badge Lanyard",
          "type": "held/static",
          "description_cn": "英文项目警探日常使用的身份挂绳。其组成包含：顶部深蓝色编制尼龙长绳、带有使用痕迹的硬质全透明亚克力卡套、前端带有老旧黄铜拉丝质感的五角星警徽以及英文排版的文字ID卡面。",
          "generation_prompt_cn": "写实英文项目道具四视图：警徽挂绳证件卡。固定于16:9横向单画布。居中转台相机视角。该道具呈现深蓝尼龙织带、边缘磨损的硬体宽卡套、划痕做旧的铜表面警徽及英文证件图文。视图呈现为四个视角面格并排，横向宽度明确分配：第一宫微距特写，占整体画布横向宽度的35%，特写主体纵向居中于该宫格内，重点展现金属划痕与纤维细节；第二宫正面视图、第三宫侧面视图、第四宫背面视图共享剩余65%，且四格必须严格只在同一横排完整铺开，禁止第二排、换行、错层或2x2拼贴。侧重打光材质厚度，顶部柔和关键光源分离轮廓深度。四个面板均保持边缘清楚、材质纹理可读、清晰度一致，不允许某一格明显发虚。静物单体展示，四个视角的静物共同生长在同一块纯净连续的单一全白背景画布中，自然留白并呈现完美的平面整体性。",
          "generation_prompt_en": "Photoreal prop sheet for a Police ID Badge Lanyard on a 16:9 horizontal canvas. Centered turntable view. Exactly four views laid out side-by-side with clear horizontal width allocation: Close-up panel (highlighting brass badge scratches, acrylic texture, and nylon fibers) occupies 35% of the total canvas width with the subject centered vertically; Front, Side, and Back panels share the remaining 65%. The layout must remain one and only one horizontal row, with no second row, no line break, no staggered stacking, and no 2x2 arrangement. Display navy woven strap, worn brass clip and badge, rigid clear acrylic holder, and English layout ID card. Soft top-angle key light with clean rim separation to emphasize material depth and wear. All four panels remain crisp and evenly readable, with clear edges and consistent material sharpness across the sheet. All four angles naturally share a single continuous, pure white background canvas, forming a cohesive and unified image plane.",
          "negative_prompt_en": "human hands, fingers, holding, Chinese text, toy-like plastic, 3D render, fewer than 4 panels, more than 4 panels, comic lines.",
          "anchor_description": "navy woven lanyard, rigid clear badge holder, worn brass police badge, English ID",
          "visual_dependencies": [],
          "dependency_strategy": {
              "type": "Original",
              "logic": "Original English/Chinese-project prop."
          }
      }
  ]
}
```
