# entity_design_environment.md

## 三、 环境专项规范 (Environment Design & Prompts)

### 3.1 Environment Prompt Template
#### 3.1.1 基础原则与信息架构 (Base Structure & Fields)
- **专属字段回写契约**：严格落实全局回写，`name/name_en` 中蕴含的场所属性、级别、方向、早晚必须转译进提示词语义。必须写清 FG/MG/BG，并明示 Primary/Secondary Subject。严禁只有构图没有空间物理身份。

#### 3.1.2 舞台构筑与空间实体化 (Stage & Spatial Routing)
- {Stage} 中心写作规则：Environment 的 generation_prompt_cn/generation_prompt_en 必须围绕上游已定义的 `{Stage}`（核心舞台）组织描述，确保该区域清晰可见、距离镜头视角适中，并优先放在中景 (MG) 承载核心表演。先把承载表演的核心空间和其固定实体写清，再展开 FG/MG/BG、光照、材质与 Delta，禁止只写空泛场所词而不说明舞台由哪些可见实体构成。
- `{Stage}实体回写规则`：必须把上游已标准化的舞台边界、关键界面、主要固定物和可通行路径转译成可见物体与空间结构，例如门框、窗沿、桌边通道、柜台内外分界、台阶起点、栏杆转角等；重点是把上游结构化输入转成可生成的空间语言，而不是重新发明边界。
- **空间可达与动作支持**：Environment prompt 必须服务 `{Beats}` 的动作空间。若上游 Beat 已要求穿门、绕桌、切换内外或跨越阈值，环境提示词必须显式保留对应的通行净空、界面两侧结构和视线通廊，让下游动作有明确落点。
- **环境构图简洁有序规则（新增强制）**：所有环境提示词都必须明确写出主导构图方式，并优先保持简洁、有序、层级清楚的画面组织，避免主体过多、视觉中心漂移或陈设堆砌导致的杂乱。默认至少明确一种主要构图策略，如：`三分法构图`、`对称构图`、`前景框景 + 中景主舞台 + 背景收束`。允许存在辅助构图手段，但禁止在同一场景里无节制混用多个互相争抢的构图中心。主舞台、次级主体、引导线、留白区与通行动线必须服从同一个构图秩序，让观者一眼读出视觉重心和观看路径。
- **环境构图控杂规则（新增强制）**：环境 prompt 在描述陈设、结构和前景元素时，必须主动控制信息密度，只保留服务主构图、主舞台和题材气质的关键物件。前景框景、门窗、柱列、栏杆、屏风、桌角、灯具、树枝或帘幕等元素可以用来建立框架感和纵深，但不得把它们写成平均抢戏的装饰堆。若选择对称、黄金分割或三分法构图，必须进一步说明主要主体位于何处、次级主体如何陪衬、空白区域如何稳定画面；若选择框架式构图，必须说明由什么结构形成框景以及框景如何把视线压向主舞台。核心目标是让环境画面整洁、稳定、秩序清晰，而不是“元素很多所以显得丰富”。

#### 3.1.3 光学语境与美学强化 (Optical Context & Aesthetic Reinforcement)
- **光学语境总领优先级声明（新增最高优先级）**：环境光学语境是空间成立、角色承接和题材表达的前置总控。必须先定亮度基线、可见度层级、主光/辅光/轮廓光关系、色温方向与空气透视，再写陈设风格与局部氛围；若“氛围感”和“可读、可拍、可演”的基础光学条件冲突，始终优先后者。
- **环境光学与色彩执行清单（整合）**：环境 prompt 先写主光、补光与色彩层次，再写陈设；必须明确 FG/MG/BG、题材对应的明亮/压暗基线、至少三项色彩参数，以及空间深度和材质反射层次。
- **统一氛围质感落点规则（新增强制）**：光线、色彩、材质与空间层次写完后，必须收束到明确且可执行的氛围质感词，如“通透、厚重、柔和、清冽、温润、冷峻、朦胧、肃穆、轻盈、凝练”，并让该词与前文光源、对比、反射和空气感形成闭环。若题材无特别要求，默认至少补入“通透度”或“柔和度”；若题材强调权力、奇观、历史重量或压迫感，则必须明确“厚重感、肃穆感或压强感”。

- **题材特设规则**
- **仙侠构图想象力豁免规则（新增强制）**：若项目属于仙侠、东方幻想、神话传奇、修真奇观或强神性世界观，环境构图不得被“现实建筑必须这样搭”“镜头必须像真实场地拍摄”这类写实约束锁死。此类题材应主动允许更高等级的视觉想象与空间重组，包括但不限于：悬空平台、云上宫阙、非现实比例门洞、层叠山门、深渊与天光同框、法阵在地面与空中双重展开、桥廊在雾中断续消失、巨物与人物形成神性尺度差、前中后景跨越常规物理距离却仍保持视觉秩序。这里的要求不是胡乱夸张，而是让构图、空间、景深和尺度服务“仙”“灵”“势”“界”的表达；只要画面主体清楚、重心稳定、层次分明，就应优先保留这种超现实的展现力。
- **仙侠色彩特设规则**：在继承第 1.3 节“双主干色系 + 过渡色层”总规则前提下，仙侠题材可采用月白-青碧、苍蓝-冷金、黛青-玉绿等双主干，并扩展法阵辉光、灵泉雾气、神木微光等超现实色源；关键是色彩需服务“仙气、灵性、威仪、神性尺度”，避免退回普通古风写实用色。
- **仙侠祥瑞生灵与异观增益规则（新增强制）**：若题材属于仙侠、东方幻想、神话传奇或修真奇观，环境在不破坏主舞台可读性与构图秩序的前提下，可适度加入能够强化世界灵性的仙鸟、灵兽、异草、祥瑞云气、灵蝶、符光游丝、护山神禽、远空神兽剪影、灵木花雨、灵泉光粒、瑞光垂落等元素，作为空间气口、尺度参照、气运征兆或宗门气质强化点。但这些元素必须满足四条约束：1) 只作为环境奇观与氛围设计的一部分，不得喧宾夺主抢走主舞台；2) 必须明确其所处景别、尺度、数量和发光/受光逻辑，避免变成无来源乱飞的廉价特效；3) 优先服务仙气、威仪、祥瑞、宿命感或天地异象表达，而不是机械堆砌“热闹元素”；4) 若出现灵兽或仙鸟，应更偏远景、侧景、剪影、盘旋轨迹或守护姿态，除非上游明确要求其为主主体，否则不得把环境资产写成“神兽角色海报”。
- **仙侠反俗套水墨化规则（新增强制）**：仙侠题材在色彩处理上，原则上**禁止**默认使用水墨黑白灰、淡墨、烟灰、素纸黑这类去色彩化方案作为主导基调，也不得把“黑白灰水墨感”或“大面积灰蓝墨色”误当成仙侠高级感的唯一解。除非上游明确要求水墨、写意、卷轴画、丹青幻境、古画入境、黑白法界或特定泼墨审美，否则仙侠环境不得主动收敛到黑白灰水墨体系。默认应优先追求更鲜活、更有灵气流动感、更具宝石感或法器感的色彩组织，让青碧、玉绿、月白、冷金、灵银、雾紫、赤焰朱砂等颜色在控制好的比例内形成层次与光泽。重点是避免把仙侠一律做成寡淡、发灰、失彩的“古风水墨模板”。

- **规则实现示例（新增强制参考）**：以下示例不是固定场景模板，而是展示可执行的最小写法：
  - **通用句式模板**：`主光源先建立主舞台受光与半影 -> 辅光/反射托起暗部 -> 用 FG/MG/BG 分层拉开纵深 -> 将主辅色与过渡色绑定到具体材质与距离层 -> 最后落到题材一致的氛围词。`
  - **都市情感简式示例**：`窗天光打底，室内暖灯托起中景；暖中性主色配少量冷反射，保持通透、温润、可读。`
  - **写实悬疑简式示例**：`台灯锁定主舞台，远处冷街光压后层；暗部保留细节与过渡，形成紧张但不失真的纵深。`
  - **仙侠奇观简式示例**：`冷天光定主调，法器/结界作次级光源；青碧与冷金分层递进，空间可超现实但主体清楚。`
- **焦距与空间感塑造 (Focal Length & Spatial Shaping)**：提示词应包含对镜头焦距的描述，以控制画面的空间感和透视关系。广角镜头（如 16-35mm）可用于展现环境的宏大与开阔，或在近距离拍摄时产生戏剧性的畸变；标准镜头（如 50mm）提供自然的视角；长焦镜头（如 85-200mm）则可以压缩空间，创造出一种疏离或窥视感，并将背景与主体紧密地结合在一起。
- **亮度映射与角色发展共鸣规则 (Brightness Mapping & Character Arc Resonance)**：场景设计作为剧情的必要组成部分，其亮度与光学配置必须与角色的发展阶段、情感弧线相互呼应和强化，形成视觉与叙事的完整闭环。必须遵循以下原则：
  - **默认明亮取向（与全局规则一致） (Default Brightness Forward)**：除非题材/剧情明确要求低照度，默认保持可读、通透、主体清晰；夜景只改光源组织，不取消舞台可见度。
  - **光线与角色弧线协同规则 (Lighting-Arc Coordination)**：主要角色所处的演员区域，其光照配置必须直接响应该角色在当前场景中的情感阶段、动作推进与剧情地位。角色处于上升阶段、关键决定时刻或情感突破时，光线应主动趋向更聚焦、更清晰、更明亮，以强化其主动性与存在感；角色处于困境、迷茫或被动阶段时，光线可采用半影区、柔和阴影或定向约束来表现内心冲突，但绝不应让关键演员彻底陷入不可见的黑暗。同时，主光、辅光与轮廓光应像“表演参与者”一样，跟随关键台词、走位与动作转折调整可见度和视觉优先级；角色的关键走位路径应被稳定照亮，背景人群与次要物体则应主动后退或淡化，确保主角的展开始终处于视觉中心。

- **风格后置表达**：环境风格（如奢华、复古、工业）应优先通过 `BG` 的材质、光照、色温、体块与纹理节奏来表达，保留动作通道区域为空旷清晰状态。
- **仙侠题材构图实现示例（新增强制参考）**：若题材为仙侠或东方幻想，可按“前景引导 + 中景法阵/山门主舞台 + 远景云海/宫阙收束”的三层结构写入，并允许仰视广角、斜轴或俯瞰等镜头强化神性尺度；重点是奇观与秩序并存，不退回普通写实古风室内外。
- **环境深度显性写法规则（新增强制）**：本条是对上文“环境光学与色彩执行清单”第 4 项的写法提醒。环境 prompt 必须直接把空间深度写出来，优先采用“前景框景/遮挡 + 中景主舞台受光 + 背景远层收束”的句式，并把门框、柱列、屏风、雾层、远窗、灯带、反光地面或远端结构写成明确纵深标记。
- **环境色谱显性写法规则（新增强制）**：本条是对上文“环境光学与色彩执行清单”第 3、5 项的写法提醒。环境 prompt 至少要出现一组可直接生成理解的综合色谱表达，并把综合色拆到具体表面、光源与距离层，例如“墙面冷灰打底、木作中棕过渡、金属局部暖高光”。
- **环境礼制与阶层秩序规则（新增强制）**：若环境属于宫廷、王府、府邸、豪门宅院、宗祠、官署、厅堂、祭祀或其他强制度空间，必须把礼法秩序写成可见的空间结构：明确中轴或主次空间、座次逻辑、门窗尺度、屏风帷幔关系、器物陈列层级、动线约束、对称性与维护程度。宫廷与豪门空间默认应井然有序、富丽堂皇、尊卑分区清楚、贵重材质使用有节制但有分量，避免写成杂乱无章的“漂亮古风室内”。若是民居、市井、边塞、乡野等空间，则需依据当地生活方式、气候与工艺传统构建更朴素但可信的结构秩序。
- **真人写实场景真实性门禁（新增强制）**：若项目属于真人写实剧，环境必须像真实可拍摄场地，而不是样板间或概念图。必须优先交代真实空间尺度、真实建筑/装修层级、现实中会出现的收纳方式、通行动线、老化位置、清洁程度和灯具来源。禁止无依据地把普通住宅、办公室、医院、学校、派出所、餐馆等空间设计成过度高级、过度空旷、过度对称、过度戏剧化打光的摄影棚展示间；除非上游明确指定，默认保留适量真实生活痕迹与功能性杂项。

#### 3.1.4 变体与正反环境逻辑 (Variations & OTS Logic)
- **环境组裂变传承规则**：如果上游传递的是基于同一环境组的衍生环境（如正反、内外或状态差异），Stage 3 必须保留其宏观共性，并只放大该视角真正需要的差异化物理要素，确保同组环境看起来仍属于同一空间系统，而不是被设计成互不相关的新场景。
- **依赖关系显式交代规则**：当 environment 存在 `dependency_strategy` 时，`generation_prompt_cn/en` 必须明确写出其继承的 base environment 共性锚点，以及当前新增的视角差异、状态差异或构图差异。变体写作坚持 Delta-only，不重新改写 Base 已经确定的主体结构。

#### 3.1.5 纯净去剧情角色化与门禁自检 (Clean Plate Gatekeeping)
- **落实全局 Clean Plate 规则**：环境只写空间、材质、灯光、空气感和匿名非情节群演；任何已进入 Subject Index 的角色实体都不得进入 `environments`。
- **非情节群演允许边界与占位符自检**：如果上游环境语义需要群众、路人、观众、香客、侍从、守卫或办公人群来建立空间规模、时代语境或生活气息，环境资产端可以保留这类匿名群演，但必须同时满足：1) 只能成组或稀疏分布地作为背景氛围存在，不得成为单独主体；2) 必须保持远景、低信息量、不可识别、不可复用，不得形成明确脸部、造型锚点或身份特征；3) 必须明确数量、密度、分布和景别，且其服饰、肤色倾向、发式、体态与活动方式必须随项目已给出的年代、地域、国家、族群/人种与阶层信息同步调整，避免泛泛写成“有人在那儿”；4) 严禁把任何角色实体伪装成群众氛围。提交前必须逐项扫描并清除：主角/配角残影、可识别人脸、特定服装轮廓、镜中或窗面反射人影、舞台占位人形等误判信号。若需要强化“有人活动过”的感觉，也可优先改写为非人格化痕迹，例如座椅位置、杯盏余温、脚印、水痕、翻开的卷册、未熄的灯火、未关的门、风动帷幔等。

### 3.2 对话正反打与 OTS (Clean Plate Logic)
- **OTS 同场双环境规则**：当 OTS/正反打在同一 Scene 内执行时，变体 `ENV:[..._OTS_A]` 与 `ENV:[..._OTS_B]` 仅负责交替呈现正反方位的物理对立结构。
- **绝对隔离**：执行口径继承 3.1.5 的 Clean Plate 主规则；OTS 变体同样严禁前景肩膀或人影残留。

## 六、输出模板（严格）

- 确保遵守最终输出结果格式，仅保留 JSON 本身。
- **唯一输出物**：全文仅输出**唯一的一个大 JSON 代码块**，里面只需包含 `environments`（场景）。
- **单段结构保底规则**：最终 JSON 顶层必须存在 `environments` 数组键。无实体时输出空数组 `[]`。

### Entities JSON (Strict Schema)

**关于 JSON 格式结构的最高优先级警告 (CRITICAL STRUCTURAL WARNING)**：JSON 必须是唯一的单个对象；根节点固定含 `environments` 键；空类输出空数组，数组严格按 `subject_type` 路由，错分即重写。

#### JSON 内容共性硬约束
- **Scene Subjects 零遗漏硬约束**：JSON 数组必须完整覆盖前置提供/识别出的**所有**实体；不得只保留“核心代表项”。任意防遗漏声明都不如直接在 JSON 里全量打满重要。
- **分类完整性硬约束（新增强制）**：最终核对时，除了检查条目总数，还必须逐条检查“输入 Subject Index 的实体类型”与“输出 JSON 所在数组”是否一一对应。总数正确但数组归类错误，仍然视为失败。
- **类型专属字段硬约束（新增强制）**：四个数组不仅归属不同，字段模板也必须按类型严格分离。`characters[]` 才允许使用 `gender`、`role`、`archetype`、`appearance_cn`、`clothing`、`action_characteristics` 等角色专属字段；`props[]` 允许使用物件状态/类型字段（如 `type`）；`environments[]` 与 `posters[]` 应使用环境/海报字段（如 `atmosphere`、`visual_params`）并围绕空间或海报构图组织描述。禁止把角色字段复制到 prop/environment/poster，对道具/环境/海报借壳套用角色对象模板，或让不同数组只靠 `name` 区分、其余字段结构完全同构。
- **命名绝对防篡改与零容错校验（极度严格）**：所有资产的 `name` / `name_en`（及其层级名称）必须与输入 `subjects index` 完全一致；输出前必须逐条执行“输入 `subjects index.name` -> 输出 JSON `name`”一对一核对。任意字符差异（含空格、全半角、大小写、下划线、连字符、后缀、括号）都视为严重错误，必须修正后再输出。
- **description_cn 传导硬约束**：必须将上游输入的 `entity_attributes` 字段属性原文一字不改、**原样填写**到本实体对应的 `description_cn` 字段中，不要做任何二次创作或删减。
- **固定双语输出字段契约**：严格沿用定义的中英双轨字段要求，特别是 `generation_prompt_cn/en`。
- **继承约束**：每个实体都必须提供 `visual_dependencies`（数组）与 `dependency_strategy`（包含 `type` 和 `logic` 两个对象属性），详见前文状态演化链要求。

#### 统一 JSON 示例（必读参照）
以下为 environments 的形态示例：
```json
{
  "environments": [
      {
          "subject_no": "S003",
          "name": "港口办公室 正向 中景 夜",
          "name_en": "Harbor Office Front Mid Night",
          "base_name_en": "Harbor Office",
          "atmosphere": "Rainy tense night with restrained noir contrast and highly structured staging",
          "visual_params": "Mid/Interior/Night",
          "description_cn": "港口办公区夜景，呈现纯粹的物理实景结构。从门外走廊向内看去的一条深邃视线。老旧木桌与后方百叶窗拉伸出空间透视，一盏金属色桌灯照亮桌面。窗体玻璃倒映街角路灯夜雨斑驳。静谧的环境空镜状态，后景允许少量不构成角色实体的匿名深夜办公群演，用于建立九十年代夜班氛围。",
          "generation_prompt_cn": "电影级写实剧情环境，港口办公室正向中景夜景版本。采用35mm广角镜头拍摄，机位保持胸口高度附近并略低于视线，镜头保持水平，垂直线稳定，以三分法结合前景框景的构图组织画面，确保主舞台、通道与后层视线秩序清楚。静物空镜环境展现。从半开的实木门框内侧这一视点锚点正向径直看入室内办公区，观看方向直指空间纵深。前景：左侧厚重的门框木纹作为框景。中景：一张边缘起皮的实木办公桌和两把空置的转椅，作为主要主体。后景：紧闭的金属百叶窗墙和透出夜雨反光的大扇玻璃，作为次级主体。室内依靠办公桌上一盏老式黄铜长臂台灯发出暖黄灯光作为主光源，与窗外散射进来的冷蓝色街灯形成冷暖对照；桌面、文件堆、椅背外沿和桌前地面应形成清楚的主受光面、半影面与落地投影，桌子侧面再以微弱的辅助光补足暗部细节，同时窗框边缘有锐利的轮廓光勾勒，百叶片与雨痕玻璃后方保留轻薄空气散射，把背景从主舞台里切开。整体采用中等景深，主舞台与桌面道具保持足够锐度，后景略微退软。色彩结构原则上以旧木褐系与煤灰蓝系作为主辅两大色系，琥珀暖光、橄榄灰过渡和雨痕玻璃上的冷白反射围绕这两大色系展开；整体对比度中高，局部对比度集中在桌面与灯下区域，暗部密度受控但保留木纹、墙面与地面反射信息，高光保持一定通透度，远中近景对比度逐级递减。最终落到冷夜中厚重、克制但仍可读、且具有明确体积起伏的港口办公室气压。纯净写实的物理空间呈现，桌边通道区域开阔明朗。环境背景氛围：后景深处可保留2到3个稀疏分布的匿名深夜办公群演，用于建立九十年代北美港口夜班氛围；他们必须停留在远景低信息量层级，不得形成清晰面部、可识别造型、可复用服装锚点或任何特定角色联想，更不得承担主舞台功能或充当角色占位符。",
          "generation_prompt_en": "Cinematic photoreal drama environment for Harbor Office Front Mid Night, shot on a 35mm wide-angle lens with a chest-level camera placed slightly below eye height, camera kept level, and stable vertical lines. The composition uses a rule-of-thirds layout with a foreground frame element so the main stage, walkable lane, and background recession stay clean and orderly. Clean plate composition. From the inner edge of the open solid wooden door frame (Viewpoint Anchor), facing directly inward toward the office depth (Viewing Direction). FG: solid wooden texture of the door edge on the left acting as a framing element. MG: a worn solid wood desk and two empty rolling office chairs acting as the Primary Subject. BG: wall obscured by metal blinds and rain-streaked glass pushing cold blue streetlights inside, acting as Secondary Subject. A vintage brass desk lamp emits warm yellow light as the key source, creating a cool-warm contrast with the cold blue streetlights from outside; the desk surface, file stack, outer chair edges, and floor in front of the desk should show clear key-lit planes, half-shadow planes, and grounded cast shadows. Soft fill light on the side of the desk reveals detail in the dark wood and wall texture, while sharp rim light outlines the window frame, and a thin layer of atmospheric scatter behind the blinds and rain-streaked glass separates the background from the main stage. Use a moderate depth of field, keeping the main stage and desktop props sufficiently sharp while the far background falls slightly softer. Color structure should principally be organized around two main color families: old wood brown as the primary family and coal blue as the secondary family, with amber practical light, olive-grey transitions, and cool white rain-glass reflections unfolding around that main-secondary backbone; overall contrast is medium-high, local contrast is concentrated around the desk and lamp pool, shadow density stays controlled while preserving material detail, highlights retain some transparency, and contrast gently recedes from foreground to background. The final atmosphere feels weighty, restrained, readable, and spatially dimensional within a cold harbor night office. Static environment focus, clear walkable lanes past the desk. Background atmosphere only: allow 2 to 3 sparse anonymous late-night office extras in the deep background to establish a 90s North American harbor-night mood; they must remain distant, low-information, non-reusable, and unidentifiable, with no clear faces, no distinctive costume anchors, no hero placement, and no resemblance to any known character entity or placeholder human stand-in.",
          "negative_prompt_en": "specific characters, named people, recognizable character entities, hero foreground extras, clear faces, reusable costume anchors, placeholder humans for known roles, main character outfits, messy clutter blocking paths, bright flat lighting, CG rendering.",
          "anchor_description": "solid wood desk, vintage brass desk lamp, wall with metal blinds, rain-streaked glass window",
          "visual_dependencies": [],
          "dependency_strategy": {
              "type": "Original",
              "logic": "Original Chinese/English-project environment."
          }
      }
  ]
}
```
