import {
    PROJECT_SCENE_ANALYSIS_ERA_OPTIONS,
    PROJECT_SCENE_ANALYSIS_REGION_OPTIONS,
    PROJECT_SCENE_ANALYSIS_MODEL_FAMILY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_WORKFLOW_OPTIONS,
    PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS,
    PROJECT_SCENE_ANALYSIS_CHARACTER_EMPHASIS_OPTIONS,
    PROJECT_SCENE_ANALYSIS_NARRATIVE_DENSITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_COMMERCIAL_CONSTRAINT_OPTIONS,
    PROJECT_SCENE_ANALYSIS_MODALITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_CONTINUITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS
} from './projectOptionConfig';

export const CANON_TAG_STORAGE_KEY = 'aistory_character_canon_tag_categories_v1';
export const CANON_IDENTITY_STORAGE_KEY = 'aistory_character_canon_identity_categories_v1';
export const PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS = [
    { key: 'primary_goal', labelZh: '主要目标', labelEn: 'Primary Goal', options: PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS },
    { key: 'secondary_goal', labelZh: '次级目标', labelEn: 'Secondary Goal', options: PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS },
    { key: 'expected_model_family', labelZh: '预期模型族', labelEn: 'Expected Model Family', options: PROJECT_SCENE_ANALYSIS_MODEL_FAMILY_OPTIONS },
    { key: 'generation_workflow', labelZh: '生成工作流', labelEn: 'Generation Workflow', options: PROJECT_SCENE_ANALYSIS_WORKFLOW_OPTIONS },
    { key: 'era_setting', labelZh: '时代设定', labelEn: 'Era Setting', options: PROJECT_SCENE_ANALYSIS_ERA_OPTIONS },
    { key: 'region_culture', labelZh: '地域文化语境', labelEn: 'Region / Culture', options: PROJECT_SCENE_ANALYSIS_REGION_OPTIONS },
    { key: 'character_emphasis', labelZh: '人物侧重点', labelEn: 'Character Emphasis', options: PROJECT_SCENE_ANALYSIS_CHARACTER_EMPHASIS_OPTIONS },
    { key: 'narrative_density', labelZh: '叙事密度', labelEn: 'Narrative Density', options: PROJECT_SCENE_ANALYSIS_NARRATIVE_DENSITY_OPTIONS },
    { key: 'commercial_constraint', labelZh: '商业约束', labelEn: 'Commercial Constraint', options: PROJECT_SCENE_ANALYSIS_COMMERCIAL_CONSTRAINT_OPTIONS },
    { key: 'modality_focus', labelZh: '模态侧重', labelEn: 'Modality Focus', options: PROJECT_SCENE_ANALYSIS_MODALITY_OPTIONS },
    { key: 'continuity_priority', labelZh: '连续性优先级', labelEn: 'Continuity Priority', options: PROJECT_SCENE_ANALYSIS_CONTINUITY_OPTIONS },
    { key: 'safety_broadcast_level', labelZh: '播出安全等级', labelEn: 'Safety / Broadcast Level', options: PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS },
];

export const DEFAULT_CANON_TAG_CATEGORIES = [
    {
        key: 'beauty',
        title: '颜值/美貌（主角塑造）',
        options: [
            { id: 'beauty_1', label: '绝美', detail: '五官精致、比例高级、镜头感强' },
            { id: 'beauty_2', label: '冷艳', detail: '表情克制、眼神有压迫感、气场强' },
            { id: 'beauty_3', label: '甜美', detail: '笑容干净、亲和力强、少年感/少女感' },
            { id: 'beauty_4', label: '高级感', detail: '皮肤质感干净、妆容克制、整体贵气' },
            { id: 'beauty_5', label: '狐狸系', detail: '眼尾上挑、神情慵懒、带一点挑衅感' },
            { id: 'beauty_m1', label: '硬朗帅', detail: '下颌线清晰、骨相立体、眼神坚决' },
            { id: 'beauty_m2', label: '禁欲系', detail: '克制冷淡、距离感强、越看越上头' },
            { id: 'beauty_m3', label: '痞帅', detail: '微挑眉、嘴角不经意上扬、危险又迷人' },
            { id: 'beauty_m4', label: '温柔系', detail: '眼神温和、说话慢半拍、可靠感强' },
        ],
    },
    {
        key: 'skin_tone',
        title: '肤色/质感（常用标签）',
        options: [
            { id: 'skin_1', label: '冷白皮', detail: '冷调白皙，通透干净' },
            { id: 'skin_2', label: '暖白皮', detail: '暖调白皙，亲和柔和' },
            { id: 'skin_3', label: '健康小麦', detail: '小麦色/日晒感，活力与性感' },
            { id: 'skin_4', label: '古铜', detail: '更深一档的日晒肤色，张力强' },
            { id: 'skin_5', label: '奶油肌', detail: '细腻柔光质感，显贵气' },
            { id: 'skin_6', label: '冷感瓷肌', detail: '干净无瑕，光泽克制' },
        ],
    },
    {
        key: 'eye_color',
        title: '眼睛颜色（常用标签）',
        options: [
            { id: 'eye_1', label: '深棕', detail: '沉稳、温柔、耐看' },
            { id: 'eye_2', label: '浅棕/琥珀', detail: '更亮、更抓镜头' },
            { id: 'eye_3', label: '黑色', detail: '压迫感强、眼神锋利' },
            { id: 'eye_4', label: '灰色', detail: '冷感、高级、距离感' },
            { id: 'eye_5', label: '蓝色', detail: '清冷或少年感，辨识度高' },
            { id: 'eye_6', label: '绿色', detail: '稀有感、神秘感强' },
        ],
    },
    {
        key: 'hair_style',
        title: '发型（常用标签）',
        options: [
            { id: 'hair_1', label: '长直发', detail: '干净利落，发丝有光泽' },
            { id: 'hair_2', label: '长卷发', detail: '松弛性感，层次丰富' },
            { id: 'hair_3', label: '高马尾', detail: '利落、青春、行动感' },
            { id: 'hair_4', label: '低马尾', detail: '克制、优雅、职场感' },
            { id: 'hair_5', label: '丸子头', detail: '露出颈部线条，清爽' },
            { id: 'hair_6', label: '短发波波', detail: '轮廓利落，强调脸部线条' },
            { id: 'hair_7', label: '寸头/短寸', detail: '干净硬朗，突出眉骨与眼神' },
            { id: 'hair_8', label: '背头', detail: '成熟强势，精英气场' },
        ],
    },
    {
        key: 'hair_color',
        title: '发色（常用标签）',
        options: [
            { id: 'hcol_1', label: '自然黑', detail: '干净利落，东方感强' },
            { id: 'hcol_2', label: '深棕', detail: '更柔和、更显质感' },
            { id: 'hcol_3', label: '栗棕', detail: '温柔氛围感，显白' },
            { id: 'hcol_4', label: '巧克力棕', detail: '成熟高级，适配职场' },
            { id: 'hcol_5', label: '亚麻棕', detail: '更轻盈的时髦感（可偏冷/偏暖）' },
            { id: 'hcol_6', label: '金发', detail: '辨识度高，镜头更亮' },
            { id: 'hcol_7', label: '银灰', detail: '冷感高级，未来感/神秘感' },
            { id: 'hcol_8', label: '红棕', detail: '热烈、强存在感' },
        ],
    },
    {
        key: 'sexy',
        title: '性感',
        options: [
            { id: 'sexy_shoulder_1', label: '露肩/一字肩', detail: '突出肩线与颈部线条，镜头更“高级性感”' },
            { id: 'sexy_collar_1', label: '露锁骨', detail: '领口略开，锁骨清晰，胸口肌肤少量可见（尺度克制）' },
            { id: 'sexy_collar_2', label: '开领/解一两颗扣', detail: '衬衫/外套微敞，若隐若现' },
            { id: 'sexy_collar_3', label: '露锁骨与胸口（开领/浅V）', detail: '开领或浅V领，视觉聚焦颈胸区域（尺度克制）' },
            { id: 'sexy_arm_1', label: '无袖/吊带（露手臂）', detail: '露出上臂线条，更轻熟、更利落' },
            { id: 'sexy_arm_2', label: '挽袖/卷袖（露前臂）', detail: '随性、克制，有一点禁欲张力' },
            { id: 'sexy_leg_1', label: '短裙/短裤（露腿）', detail: '腿部比例更突出（注意尺度克制）' },
            { id: 'sexy_leg_2', label: '开衩裙（露腿）', detail: '走动时若隐若现，更“贵气”的性感' },
        ],
    },
    {
        key: 'gender',
        title: '性别（设定）',
        options: [
            { id: 'gender_f', label: '女', detail: '女性角色（可用于镜头与造型提示）' },
            { id: 'gender_m', label: '男', detail: '男性角色（可用于镜头与造型提示）' },
            { id: 'gender_none', label: '无性别/性别不明', detail: '不以性别定义角色，或刻意模糊' },
        ],
    },
    {
        key: 'body',
        title: '身材/比例（主角塑造）',
        options: [
            { id: 'body_1', label: '好身材', detail: '9头身，修长腿' },
            { id: 'body_2', label: '肩颈线', detail: '锁骨清晰，肩线利落' },
            { id: 'body_3', label: '体态', detail: '站姿挺拔，走路带节奏感' },
            { id: 'body_4', label: '肌肉线条', detail: '紧致不夸张，轮廓清晰' },
            { id: 'body_h1', label: '身高：娇小', detail: '约150–160cm，比例更显可爱/脆弱感' },
            { id: 'body_h2', label: '身高：中等', detail: '约160–170cm，日常感强、适配多数场景' },
            { id: 'body_h3', label: '身高：高挑', detail: '约170–180cm，镜头更有存在感与气场' },
            { id: 'body_h4', label: '身高：很高', detail: '约180cm+，压迫感/保护感更强' },
            { id: 'body_shape_1', label: '纤细/骨感', detail: '骨点清晰、线条冷感，适合疏离气质' },
            { id: 'body_shape_2', label: '匀称/健康', detail: '比例自然、肌肉薄而紧，运动感' },
            { id: 'body_shape_3', label: '微肉/丰润', detail: '柔软曲线、亲和力强' },
            { id: 'body_shape_4', label: '健身型', detail: '肩背与核心发达，动作干净有力量' },
            { id: 'body_shape_5', label: '厚实/壮硕', detail: '骨架大、存在感强，近景更有压迫' },
            { id: 'body_prop_1', label: '腿长', detail: '视觉比例拉长，走路带风' },
            { id: 'body_prop_2', label: '腰线高', detail: '上短下长，镜头更显修长' },
            { id: 'body_prop_3', label: '腰臀比突出', detail: '曲线更明显' },
            { id: 'body_m1', label: '宽肩窄腰', detail: '倒三角轮廓明显，西装很好看' },
            { id: 'body_m2', label: '力量感', detail: '动作不多但很稳，抬手就有压迫感' },
        ],
    },
    {
        key: 'age',
        title: '年龄/阶段（设定）',
        options: [
            { id: 'age_1', label: '少年/少女（16–19）', detail: '青春感强，情绪外露，成长线明显' },
            { id: 'age_2', label: '青年（20–25）', detail: '锐气与试错期，冲劲足' },
            { id: 'age_3', label: '轻熟（26–32）', detail: '自洽、边界感更强，魅力更稳定' },
            { id: 'age_4', label: '成熟（33–40）', detail: '经验与压迫感/掌控感更强' },
            { id: 'age_5', label: '中年（41–55）', detail: '沉稳、城府/担当更明显' },
            { id: 'age_6', label: '长者（56+）', detail: '威望、阅历，气场不靠外放' },
            { id: 'age_7', label: '年龄不详/看不出', detail: '刻意模糊年龄，神秘感与距离感更强' },
        ],
    },
];

export const DEFAULT_CANON_IDENTITY_CATEGORIES = [];

export const canonOptionValue = (opt) => `${opt.label}：${opt.detail}`;

export const normalizeCanonTagCategories = (raw) => {
    if (!Array.isArray(raw)) return null;
    const normalized = raw
        .filter(Boolean)
        .map((cat) => {
            const key = String(cat?.key || '').trim();
            const title = String(cat?.title || '').trim();
            const options = Array.isArray(cat?.options) ? cat.options : [];
            if (!key || !title) return null;
            const normalizedOptions = options
                .filter(Boolean)
                .map((opt) => {
                    const id = String(opt?.id || '').trim();
                    const label = String(opt?.label || '').trim();
                    const detail = String(opt?.detail || '').trim();
                    if (!id || !label || !detail) return null;
                    return { id, label, detail };
                })
                .filter(Boolean);
            return { key, title, options: normalizedOptions };
        })
        .filter(Boolean);
    return normalized.length > 0 ? normalized : null;
};

export const normalizeUserListValues = (value) => {
    const rawItems = Array.isArray(value) ? value : String(value || '').split(/[;,\n\r]+/);
    const out = [];
    const seen = new Set();
    rawItems.forEach((item) => {
        const parsed = String(item || '').trim();
        if (!parsed) return;
        const dedupeKey = parsed.toLowerCase();
        if (seen.has(dedupeKey)) return;
        seen.add(dedupeKey);
        out.push(parsed);
    });
    return out;
};

export const formatUserListForTextarea = (value) => normalizeUserListValues(value).join('\n');

export const formatManagedUserHint = (value, t) => {
    const count = normalizeUserListValues(value).length;
    return count > 0
        ? t(`已解析 ${count} 个用户，保存时会校验是否存在`, `Parsed ${count} users. Existence will be validated on save`)
        : t('留空即可，保存时才会校验输入的用户', 'Leave empty if unused. Entered users will be validated on save');
};

