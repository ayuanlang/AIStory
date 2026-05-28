# entity_design_character.md

## 二、 角色与人物专项规范 (Character Design & Prompts)

### 2.1 角色专属防同质化规范
- **角色默认主角化美学基线 (Protagonist Aesthetic Defaults)**：对有具体姓名且承担主要叙事的成年角色，必须主动补全为“现代、高级、镜头友好”的主角级设计（除非剧情明确要求落魄/低配），并围绕以下维度强制落地精准描述。**该基线在真人写实剧中仍然成立**：允许并鼓励对主角进行相貌美化、身材比例优化、妆发完成度提升和镜头友好化处理，但必须把“美化”控制在真人可拍、真实演员可成立的范围内，表现为更优越的骨相组织、更干净利落的轮廓、更上镜的比例和更成熟的造型控制，而不是假脸、滤镜脸、网红脸或脱离现实的二次元化夸张：
  - **身材与比例**：必须显式写出黄金分割身体比例数值（如身高、约 `1:9` 头身比）。下半身视觉长度强制约占 `0.62-0.65`，确保双腿修长协调。女性优先落成高挑修长、肩颈舒展（`1:9 - 1:9.5` 长腿观感）；男性优先健壮挺拔、肩背舒展。
  - **皮肤与肤色**：肤色默认可落在白净、明亮的上镜区间，但必须写明可拍的真实物理肤质段位（如冷白、暖白、浅蜜色、健康麦色等），严格匹配职业、语境与日晒程度，确保肤色的个体差异化。
  - **发型结构**：必须写透可被镜头稳定识别的物理层特征（如分线方式、刘海形态、发长区间、直卷关系、厚薄蓬贴、束发方式及发尾轮廓），确保具备具体的造型感。
  - **服饰与穿搭 / 同类差异凸显规则**：优先显式勾勒出肩、腰、腿线的合体修身剪裁（女性主角利用高腰切分或短装方案突显躯干）。提供具有设计感和辨识度的着装方案（确保拥有至少1个独特版型识别点、1个材质或配色方向，及稳定的专属鞋履/配饰收尾）。**同类服饰差异化 (Anchor 规则)**：在 `anchor_description` 中，若当前场景多人均穿同类服饰（西装、校服、白大褂、工装等），必须采用更具区分度的脸型、发型轮廓、独立配件、鞋型及局部剪裁特征来定位和表达该个体。
  - **成人向/大尺度项目性感着装规则 (Adult-Oriented Styling)**：如果 `Project Context` 或剧情明确指示项目为“成人向”、“大尺度”或存在性感要求，在设计女性或其他适用角色的服饰时，必须主动向性感、高暴露度的方向设计。必须显式写入凸显身材曲线与局部暴露的剪裁（如：深V、高开叉、半透材质等），着重展现胸部轮廓与大腿线条，展现强烈的视觉诱惑力。
- **角色类型与反同质化矩阵 (Archetype & Differentiation Base)**：设计角色时，必须按以下逻辑进行深度塑造，确保具备个体独特性：
  1. **先锚定人物流派**：如未限制，必须先基于剧情推断角色的阶段、阶级与系统，主动将其分流至具备辨识度的流派（如：高知、老钱、功能主义等）。
  2. **绝对差异化优先级**：当出现多名角色时，必须按“骨相轮廓 > 发型体态 > 肤质肤色 > 服装版型与配饰”的优先级拉开差距。（即便全员穿制服，也必须利用尺码内搭、穿着习惯与仪态建立可见的区隔度）。
  3. **细化五官特征**：必须为每位主要角色赋予**至少 3 处**明确的独有五官/骨相物理特征（如：下颌转折、眉骨起伏、鼻梁走势）；确保相貌特征切实可呈现。
- **真人写实角色真实性门禁（新增强制）**：执行口径直接继承上文“角色默认主角化美学基线”与 Node 1 的“真人写实硬约束”。本条仅补充结论：允许主角上镜美化，但必须落在真人可拍范围；真实性优先落在相貌层（骨相组织、肤质纹理、毛孔与细节），禁止滤镜脸、塑胶感、网红模板脸和二次元比例失真；服装与站姿等其余维度保持基本可信即可。
- 角色特征落地规则：`appearance`、`description`、`clothing`、`anchor_description`、`generation_prompt_cn/en` 之间必须共享同一套识别锚点，且这些锚点要落到可被镜头稳定识别的具体元素；确保将泛化形容词转译为具体的视觉实体。每个主要角色至少要有 4 个以上稳定的正向识别点，其中至少 1 个来自轮廓/体态，至少 1 个来自服装结构或鞋履，至少 1 个来自发型结构，至少 1 个来自肤色/配饰/材质细节。
- 资产命名正向传承（强制）：命名规则统一继承第 1.1 节“实体命名一致性最高原则（权威源）”，本节不再重复扩写。
- **全局视觉舒适度与模型服务商政策合规边界规则（适用于所有描述及锚点，极度严格）**：所有涉及资产外观设计的提示词，必须充分注意避免违反各AI模型提供商（如Midjourney、OpenAI、Stable Diffusion等）的内容安全审查政策。各实体的 `description`、`appearance`、`generation_prompt_cn/en` 及其他描述必须采用完全安全、可播出、非血腥、非恶心、非强视觉不适的温和表达。**绝对禁止描述任何血腥、断肢、内脏、严重伤痕、肉体变异、令人作呕的污物或任何可能触发平台封禁的涉暴/涉黄/猎奇词汇**。如因剧情强烈需要表现“受伤/战损/战后”，必须改写为完全非图形化、极度克制且意向化的描述（如“轻微擦痕”、“衣服破损”、“灰头土脸”、“疲惫的神态”），严禁描写具体的伤口形态或流血量。此规则同样严格适用于 `anchor_description`，锚点仅许可稳定且安全的身份识别点（脸型/发型/服装板型/配色/非图形化小痕迹）。此条款优先于一切“写实需求”。

### 2.2 Character Prompt Template (Prompt 构建机制)
- **专属字段回写契约**：需严格落实全局回写，将 `gender/role/archetype/appearance_cn/clothing/action_characteristics` 的抽象设定全部转化为可见画面的自然语言描述，严禁使用“具有主角感”等不可见画面词。
- **角色气质与题材耦合规则（新增强制）**：角色设计必须跟随上游题材定位统一落地到脸部状态、发型整理度、服装版型、材质精细度、主辅配色和人物布光。喜剧/治愈/情感向人物优先避免阴鸷、病态、过分惨淡的造型与光色；仙侠人物可加强飘逸轮廓、灵气材质和超现实洁净感；写实人物强调真实生活来源与功能逻辑；恐怖/惊悚人物才允许更明显的失血色、压迫阴影、异常轮廓或不安气息，但仍需保持身份可读与设计控制。
- **角色光学落地规则**：角色 prompt 直接继承并严格执行第 1.3 节“主光源先行与光影排序总规则”。角色专项仅补充两点：1) 主光需明确优先塑形脸部与肩颈，并说明全身受光范围；2) 暗部托举方式（补光/反弹/环境光）与轮廓分离必须写实可执行，不得用空泛“电影感”替代。
- **角色礼法身份外显规则（新增强制）**：若角色处于有明确制度与等级秩序的历史或地域语境中，角色外观必须让观众一眼看出其身份系统与文化归属。需要主动把官阶、门第、婚配状态、职业身份、族群习惯、宗教禁忌、地区气候与审美传统写回到发式、妆容、服装结构、配饰数量、用色分配、织绣等级和仪态完整度中。高礼制角色应更整饬、克制、规整，体现受制度约束的穿着与姿态；民间或边地角色则可更生活化，但依旧要符合当地真实风貌与文化习惯。
- **信息组织层级（语法流）**：
  - 默认顺序结构：`身份定位与功能 -> 主光源与光影结构 -> 全面外貌（需融合2.1基线比例） -> 服装与鞋履 -> 动作特征 -> 构图机位/补充光色要求`。
- **特定字段转化规范（从概念到画面）**：
  - `description_cn`：将输入Subjects Index的 entity_attributes 属性原文直接填写到此处。
  - `archetype`：将输入Subjects Index的Action Characteristics属性原文直接填写到此处。
  - `gender` / `role`：不可只停留在 JSON 标签，必须转化为具体的画面语义（如特定的职业装束起势、眼神状态）。
  - `appearance_cn` / `clothing`：具体版型、材质与配色必须全部进入 Prompt。
  - `action_characteristics`：仅保留静态姿态表现（如“重心稳定、轻微侧身”），剔除一切心理动作。
- **角色表情默认规则（强制）**：角色设定图生成阶段必须默认保持“正常表情/自然中性表情（neutral, relaxed face）”，禁止无依据地加入夸张喜怒、狰狞、惊恐、痛苦、媚态或过强情绪化表情。仅当上游 `entity_attributes` 或剧情上下文明确要求特定情绪时，才可定向覆盖该默认值。
- **角色姿态默认规则（强制）**：角色设定图生成阶段必须默认采用站姿（standing pose）为主，优先使用稳定直立、重心清晰、全身可读的静态站立姿态。除非上游 `entity_attributes` 或剧情上下文明确指定坐姿、蹲姿、躺姿或特定动作姿态，否则不得擅自改为非站姿主体。
- **构图与机审硬规则**：
  - **全图连贯可见**：主资产必须采用 `full-body framing` / `shoes fully visible`，人物从头到脚完整入镜。
  - **安全去重**：全局合规已生效，角色 Prompt 内部严禁复读 `NSFW`, `explicit`, `色情` 等词。
- **锚点提取与只读 (Anchor Rules)**：`anchor_description` 优先使用“身份 + 相貌/轮廓 + 核心服饰识别点”的短语组合（2-3个坚实特征）。该字段为不可变锚点（immutable），下游必须逐字符继承，发生冲突时宁降风格化也不改锚点。禁用瞬时表情或暂态光影作锚点。

## 六、输出模板（严格）

- 确保遵守最终输出结果格式，仅保留 JSON 本身。
- **唯一输出物**：全文仅输出**唯一的一个大 JSON 代码块**，里面只需包含 `characters`（角色）。
- **单段结构保底规则**：最终 JSON 顶层必须存在 `characters` 数组键。无实体时输出空数组 `[]`。

### Entities JSON (Strict Schema)

**关于 JSON 格式结构的最高优先级警告 (CRITICAL STRUCTURAL WARNING)**：JSON 必须是唯一的单个对象；根节点固定含 `characters` 键；空类输出空数组，数组严格按 `subject_type` 路由，错分即重写。

#### JSON 内容共性硬约束
- **Scene Subjects 零遗漏硬约束**：JSON 数组必须完整覆盖前置提供/识别出的**所有**实体；不得只保留“核心代表项”。任意防遗漏声明都不如直接在 JSON 里全量打满重要。
- **分类完整性硬约束（新增强制）**：最终核对时，除了检查条目总数，还必须逐条检查“输入 Subject Index 的实体类型”与“输出 JSON 所在数组”是否一一对应。总数正确但数组归类错误，仍然视为失败。
- **类型专属字段硬约束（新增强制）**：四个数组不仅归属不同，字段模板也必须按类型严格分离。`characters[]` 才允许使用 `gender`、`role`、`archetype`、`appearance_cn`、`clothing`、`action_characteristics` 等角色专属字段；`props[]` 允许使用物件状态/类型字段（如 `type`）；`environments[]` 与 `posters[]` 应使用环境/海报字段（如 `atmosphere`、`visual_params`）并围绕空间或海报构图组织描述。禁止把角色字段复制到 prop/environment/poster，对道具/环境/海报借壳套用角色对象模板，或让不同数组只靠 `name` 区分、其余字段结构完全同构。
- **命名绝对防篡改与零容错校验（极度严格）**：所有资产的 `name` / `name_en`（及其层级名称）必须与输入 `subjects index` 完全一致；输出前必须逐条执行“输入 `subjects index.name` -> 输出 JSON `name`”一对一核对。任意字符差异（含空格、全半角、大小写、下划线、连字符、后缀、括号）都视为严重错误，必须修正后再输出。
- **description_cn 传导硬约束**：必须将上游输入的 `entity_attributes` 字段属性原文一字不改、**原样填写**到本实体对应的 `description_cn` 字段中，不要做任何二次创作或删减。
- **固定双语输出字段契约**：严格沿用定义的中英双轨字段要求，特别是 `generation_prompt_cn/en`。
- **继承约束**：每个实体都必须提供 `visual_dependencies`（数组）与 `dependency_strategy`（包含 `type` 和 `logic` 两个对象属性），详见前文状态演化链要求。**绝对禁止在 `visual_dependencies` 中填入 `S001`、`E001` 等 `subject_no`，实体名引用必须逐字符一致 (如 `CHAR:[@...]` 等)！**

#### 统一 JSON 示例（必读参照）
以下为 characters 的形态示例：
```json
{
  "characters": [
      {
          "subject_no": "S001",
          "name": "林月",
          "name_en": "Lin Yue",
          "base_name_en": "Lin Yue",
          "description_cn": "调查记者，28岁。冷静、警觉且在危机中追求真相的克制型人物。下颌线清晰利落，具有观察者的深邃眼神。",
          "gender": "F",
          "role": "Investigative Reporter",
          "archetype": "习惯有0.5秒的停滞停顿等动作特征原文",
          "appearance_cn": "28岁，东亚女性，身高178cm，头身比1:9.3，腰线明显上提，下半身视觉占比约63%，上半身约37%，呈现出修长且接近黄金分割的比例。面部核心特征：1) 略带单眼皮质感的内双眼型，瞳孔呈深琥珀色且睫毛自然；2) 鼻梁挺直、鼻翼偏窄且线条紧致；3) 额骨到下巴的轮廓线利落。皮肤真实，带有皮肤微瑕细纹、微弱斑点与肤质高光质感。黑色齐肩短发，右侧习惯性挽在耳后。",
          "clothing": "当前服装：深海军蓝修身截短款机能风夹克，内搭浅灰色垂坠感真丝衬衫，下身穿高腰黑色修身阔腿短裤与及膝平底皮靴。时尚对标：角色定位=都市调查记者；当代风格参考=实用机能风（Techwear）与高级极简主义；版型/材质/配色关键词=高腰修身、利落实用、深蓝与冷灰渐变、防水冲锋衣哑光材质。其他剧本衣着描述：无。",
          "action_characteristics": "动作极度克制，重心下沉且稳定，观察事物前习惯有0.5秒的停滞停顿。",
          "generation_prompt_cn": "电影级写实真人设定四视图，16:9横向资产画布。项目类型为实拍写实，由于强调真实质感，展示真实肤色微斑点、细小毛孔与自然光泽。28岁东亚女性，林月。身高178cm，头身比1:9.3，高腰线，长腿比例下半身占63%。深琥珀色内双眼睛，挺直鼻梁，清晰下颌线。黑色齐肩短发。四个面板严格同一身份、服装与比例，四宫格横向宽度分配：第一宫面部特写占整体画布横向宽度的35%，特写主体纵向居中于该宫格内；第二宫正面全身、第三宫侧面全身、第四宫背面全身共享剩余65%，且四格必须严格只在同一横排完整展开，不允许出现第二排、换行、错层或2x2拼贴，鞋子完全可见。机位保持平视，镜头保持水平，垂直线稳定，不做夸张透视拉伸。穿着深海军蓝截短机能夹克，浅灰内衬，高腰黑短裤，及膝黑皮靴。呈现重心下沉且稳定的静态站姿。电影棚拍柔和贝壳光加极细边缘轮廓光，四个面板主体边缘清楚、纹理可读、清晰度一致，采用设定图级全清晰策略。四个人像置于一整块单独、连续且统一的纯白布景画板中，各自分配充分且自然的呼吸留白，视觉上呈现出完整的平面整体。",
          "generation_prompt_en": "Photoreal character sheet for Lin Yue on a 16:9 horizontal canvas. Live Action project type highlighting skin pores, fine texture, and realistic features. 28yo East Asian woman, 178cm, 1:9.3 head-to-body proportion, elevated waistline, lower body ~63% with long legs. Deep amber inner-double monolid eyes, straight nose bridge, sharp jawline, shoulder-length black bob tucked behind her right ear. Strict four panels in a single row with explicit horizontal width allocation: Panel 1 is a facial Close-up occupying exactly 35% of the total canvas width, with the close-up subject centered vertically within that panel; Panels 2 (Front), 3 (Side), and 4 (Back) share the remaining 65%. The sheet must stay as one and only one horizontal row, with no second row, no line break, no staggered layout, and no 2x2 arrangement. Shoes completely visible in full body shots. Eye-level camera, camera kept level, stable verticals, no exaggerated perspective stretch. Wardrobe: fitted cropped navy techwear jacket, draped light grey inner top, high-waist black shorts, knee-high flat leather boots. Stable static standing pose with a lowered center of gravity. Soft clamshell key light with sharp rim light. All four panels remain crisp and evenly readable, with clear edges, readable texture, and a deep-focus presentation strategy for the full sheet. All four figures are presented together within a single, continuous, and unified pure white backdrop canvas, with natural breathing space blending them horizontally.",
          "negative_prompt_en": "beauty-filter skin, plastic face, CGI look, waxy skin, anime illustration, oversized clothing, 1:1 body split, incorrect panel order, fewer than 4 panels, cropped shoes, split-screen comic.",
          "anchor_description": "female investigative reporter, shoulder-length black bob, sharp jawline, cropped navy techwear jacket, knee-high boots",
          "visual_dependencies": [],
          "dependency_strategy": {
              "type": "Original",
              "logic": "Original Chinese/English-project character."
          }
      }
  ]
}
```
