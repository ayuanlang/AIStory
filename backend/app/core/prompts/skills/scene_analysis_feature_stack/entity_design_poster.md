# entity_design_poster.md

## 五、 特殊资产规范 (Special Assets)

### 5.1 封面海报资产 (Cover Poster)
#### 5.1.1 上游类型响应与 JSON 结构 (Upstream Mapping & Structure)
- **精准响应 `subject_type=cover_poster`**：当上游（Subject Index）透传类型为 `cover_poster` 的实体时（如 `subject_name_exact=Project Cover Poster`），必须将其作为独立海报资产推入专属的 `posters[]` 数组；`name/name_en` 优先透传上游命名，缺命名时再回退为 `name="封面海报"`、`name_en="Cover Poster"`。同时必须保证其只落在 `posters` 中，不得混入 `environments`，也不得漏掉此资产。
- **全量核心依赖继承**：必须严格读取上游的 `dependency_reference`，将其归一化并解析为该封面的 `visual_dependencies` 数组引用（如 `CHAR:[@...]`, `PROP:[...]` 等）。同时在 `dependency_strategy.logic` 中阐述这些实体如何整合进同一张海报主视觉中。严禁凭空生造剧情外资产。

#### 5.1.2 国际大片制与视觉层级 (Premium Theatrical Composition)
- **封面大片海报规则**：封面海报资产必须以**国际大片海报 / premium theatrical one-sheet** 的完成度生成，构图要求大气、明确、强情绪、强冲突、强识别度；同时要把剧本分格/分场的层次关系压缩进单张主视觉，可通过前中后景群像关系、道具引导线、环境纵深、光区切分、块面分区或多层叙事焦点来体现“剧情分格感”。确保输出的是**一张完整海报**格式的主视觉。
- **封面海报光学落地规则**：封面海报 prompt 直接继承并严格执行第 1.3 节“主光源先行与光影排序总规则”。海报专项仅补充：主光结构需同时服务群像塑形、标题留白保护和前后层次分离。
- **封面海报标题可读性保护规则（新增强制）**：海报提示词除说明标题位置和留白外，还必须尽量保护标题区的可读性与版式稳定性。需优先明确：1) 标题背后的背景纹理应更克制、更低噪声或更低信息密度；2) 标题所在区域必须具备足够的明度对比、色相分离或受控暗底/亮底，避免字底混乱；3) 主角高光、武器、法器、烟雾、雨丝、火花、爆裂光斑或复杂纹样不得压住标题主阅读区；4) 若存在副标题、演员名或宣传文案，其排版区域也需保留稳定的视觉秩序。目标是让海报在主视觉强烈的同时，标题与核心文案仍然一眼可读。
- **动态解析 `entity_attributes`**：封面的 `description_cn` 与 `generation_prompt_cn/en` 必须**直接拆解并落实**上游透传的 `entity_attributes` 设定（例如：“画面主体：反派背对镜头回眸，单手玩道具。背景氛围：冷色调压抑夜景”）。必须将“大片感觉”落实为具体的可见元素、物理细节、光影与站位压迫关系。

#### 5.1.3 画幅与移动端排版规让 (Canvas & UI Safe Area)
- **画幅独立声明**：封面海报环境的 `generation_prompt_cn/generation_prompt_en` 必须显式声明使用固定 `4:3 poster canvas` 画幅。画幅说明必须写进提示词主体内，不设专属 JSON 键。
- **精准响应排版留白**：本条承接第 5.1.2 节“封面海报标题可读性保护规则”执行版式落位。必须读取上游 `entity_attributes` 中的留白要求，并把标题置于指定位置或安全区内的纵向 1/3（建议 `y=30%-35%`、横向居中 `x=20%-80%`）；同时显式保留右侧移动端按键区与底部菜单/字幕区的净空，确保标题、文案和界面叠层都可读。

## 六、输出模板（严格）

- 确保遵守最终输出结果格式，仅保留 JSON 本身。
- **唯一输出物**：全文仅输出**唯一的一个大 JSON 代码块**，里面只需包含 `posters`（封面海报）。
- **单段结构保底规则**：最终 JSON 顶层必须存在 `posters` 数组键。无实体时输出空数组 `[]`。

### Entities JSON (Strict Schema)

**关于 JSON 格式结构的最高优先级警告 (CRITICAL STRUCTURAL WARNING)**：JSON 必须是唯一的单个对象；根节点固定含 `posters` 键；空类输出空数组，数组严格按 `subject_type` 路由，错分即重写。

#### JSON 内容共性硬约束
- **Scene Subjects 零遗漏硬约束**：JSON 数组必须完整覆盖前置提供/识别出的**所有**实体；不得只保留“核心代表项”。任意防遗漏声明都不如直接在 JSON 里全量打满重要。
- **分类完整性硬约束（新增强制）**：最终核对时，除了检查条目总数，还必须逐条检查“输入 Subject Index 的实体类型”与“输出 JSON 所在数组”是否一一对应。总数正确但数组归类错误，仍然视为失败。
- **类型专属字段硬约束（新增强制）**：四个数组不仅归属不同，字段模板也必须按类型严格分离。`characters[]` 才允许使用 `gender`、`role`、`archetype`、`appearance_cn`、`clothing`、`action_characteristics` 等角色专属字段；`props[]` 允许使用物件状态/类型字段（如 `type`）；`environments[]` 与 `posters[]` 应使用环境/海报字段（如 `atmosphere`、`visual_params`）并围绕空间或海报构图组织描述。禁止把角色字段复制到 prop/environment/poster，对道具/环境/海报借壳套用角色对象模板，或让不同数组只靠 `name` 区分、其余字段结构完全同构。
- **命名绝对防篡改与零容错校验（极度严格）**：所有资产的 `name` / `name_en`（及其层级名称）必须与输入 `subjects index` 完全一致；输出前必须逐条执行“输入 `subjects index.name` -> 输出 JSON `name`”一对一核对。任意字符差异（含空格、全半角、大小写、下划线、连字符、后缀、括号）都视为严重错误，必须修正后再输出。
- **description_cn 传导硬约束**：必须将上游输入的 `entity_attributes` 字段属性原文一字不改、**原样填写**到本实体对应的 `description_cn` 字段中，不要做任何二次创作或删减。
- **固定双语输出字段契约**：严格沿用定义的中英双轨字段要求，特别是 `generation_prompt_cn/en`。
- **继承约束**：每个实体都必须提供 `visual_dependencies`（数组）与 `dependency_strategy`（包含 `type` 和 `logic` 两个对象属性），详见前文状态演化链要求。

#### 统一 JSON 示例（必读参照）
以下为 posters 的形态示例：
```json
{
  "posters": [
      {
          "subject_no": "S004",
          "name": "封面海报",
          "name_en": "Cover Poster",
          "base_name_en": "Project Cover Poster",
          "atmosphere": "Premium theatrical tension with dramatic layered poster depth",
          "visual_params": "Poster/Cover/4:3",
          "description_cn": "整集封面海报核心画布，专为 4:3 横版海报设计。林月和其搭档在办公室内背靠背持枪戒备的画面组合。底色为雨夜灯光映射下的阴冷构图空间。项目大标题置于画面顶部(y=30%-35%)的专属留白区，侧重黄金分割视觉，确保左右与底部的净空率以规避设备界面元素。",
          "generation_prompt_cn": "电影级写实封面海报资产，固定名为封面海报。专门基于4:3横向定图画布渲染。顶级电影海报表现手法：林月与同伴在港口办公室内背对背站立警戒，胸前的警务证书挂绳充当前景视觉引导结构。主光由桌面暖灯与后方冷蓝雨夜反射共同建立，主角面部与身体轮廓被清楚压出，背景层次后退。机位略低于胸口高度，镜头保持水平，以稳定的对角线群像构图与上方标题安全区组织画面。画面正上方三分之一的专属展示区内水平布置加粗的项目中文大字标题，标题背后的背景纹理必须更克制、更低噪声，并通过受控暗底与冷暖分离保证足够可读性；人物高光、枪械轮廓、挂绳、烟雾与雨丝不得压住标题主阅读区。整体保留右侧与底部的干净间隙，用以容纳叠加的文字和界面装饰层，呈现出严谨、强冲突但标题一眼可读的大片级定格排版。",
          "generation_prompt_en": "Premium theatrical cover poster named Cover Poster, utilizing a dedicated 4:3 horizontal poster canvas. Cinematic poster composition: Lin Yue and her male companion stand back-to-back in the Harbor Office, with the Police ID badge and lanyard creating a foreground leading line. The key light is built from a warm desk practical and cold blue rainy-night reflections behind them, carving the faces and body contours clearly while the background layers recede. Camera placed slightly below chest height, camera kept level, using a stable diagonal ensemble composition organized around a protected top title zone. Bold project title text sits clearly within the upper third safe area; the background behind the title must stay lower-noise and more restrained, with controlled dark value support and clear cool-warm separation so the title remains instantly readable. Character highlights, weapon silhouettes, lanyard lines, smoke, rain streaks, and flare details must not crowd the main reading zone. Clean margins remain on the right and bottom edges to preserve space for mobile UI overlays and secondary copy, resulting in a premium, high-conflict one-sheet layout with strong title readability.",
          "negative_prompt_en": "comic grid, tiled collage, split-screen montage, characters out of proportion, 16:9 canvas, blurry faces.",
          "anchor_description": "cover poster layout, top-third title safe zone, dramatic cool-warm poster contrast, layered key art depth",
          "visual_dependencies": [
              "CHAR:[@林月]",
              "CHAR:[@同伴]",
              "PROP:[警徽挂绳证件卡]",
              "ENV:[港口办公室 正向 中景 夜]"
          ],
          "dependency_strategy": {
              "type": "Type A",
              "logic": "Derived as a special cover-poster integrating key subjects into a single 4:3 layout."
          }
      }
  ]
}
```
