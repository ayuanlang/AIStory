import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    AlertTriangle,
    Image as ImageIcon,
    Loader2,
    Pencil,
    Plus,
    Sparkles,
    Trash2,
    Upload,
    Wand2,
    X,
} from 'lucide-react';
import { getFullUrl } from '../editorHelpers';
import {
    fetchPromoBrands,
    fetchPromoEnterprises,
    fetchPromoProducts,
    generateProjectPromoPlanner,
    saveProjectPromoPlannerInput,
    saveProjectPromoPlannerResult,
    uploadAsset,
} from '../../../services/api';
import { formatProviderModelEndpointError } from '../editorConfig';
import { writePromoCatalogFocus } from '../../PromoCatalogManager';

export const PROMO_IMAGE_MAX_MB = 20;
export const PROMO_IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp';
const PROMO_IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'webp'];

export const PROMO_PLATFORMS = ['抖音', '小红书', 'B站', '视频号', '知乎', '快手'];
export const PROMO_DURATIONS = ['15s以内', '15-30s', '30-60s', '60-90s', '1-3min', '3min以上'];
export const PROMO_GOAL_TYPES = [
    '品牌形象片', '产品卖点片', '引流获客片', '招商渠道片', '功能演示片', '活动节点片', '客户案例证言片',
    '企业形象片', '新品发布片', '电商带货片', '门店到店转化片', '招聘雇主品牌片', '上市融资路演片',
    '公益社会责任片', '售后服务口碑片', '思想领导力片',
];
export const PROMO_NARRATIVE_MODELS = [
    '四段式（钩子-共鸣-价值爆发-收口）', '反差对比模型', '感受旅程模型', '微型人物小传模型',
    '一句话锚定模型', '承诺兑现模型', '时间切片模型', '设问递进模型', '权威背书模型',
    '证据递进模型', '内心矛盾化解模型', '问题解决模型', '前后对比蜕变模型', '场景代入模型',
    '悬念揭晓模型', '清单盘点模型',
];
export const PROMO_PRESENTATION_FORMS = [
    '真人口播', '实景演绎', '纪实跟拍', '产品静物实拍', 'MG动画', '三维CG动画', '手绘动画',
    '屏幕录屏演示', '素材混剪', '图文轮播', '虚拟数字人口播', '航拍大场面', 'AI生成影像',
];
const PROMO_CUSTOM = '__custom__';

export const PROMO_GOAL_TYPE_DEFS = {
    '品牌形象片': { zh: '建立品牌气质与信任，不主推单品成交，强调“我们是谁、为何值得信赖”。', en: 'Build brand aura and trust, not a single-SKU hard sell.' },
    '产品卖点片': { zh: '围绕核心卖点讲清“买它的理由”，适合转化与对比竞品。', en: 'Explain why to buy this product; good for conversion and comparison.' },
    '引流获客片': { zh: '用强钩子换关注、留资或私信，目标是把流量变成线索。', en: 'Use a strong hook to get follows, leads, or DMs.' },
    '招商渠道片': { zh: '面向经销商/加盟商，讲利润模型、支持政策与合作门槛。', en: 'For dealers/franchisees: profit model, support, and entry terms.' },
    '功能演示片': { zh: '把产品怎么用、解决什么问题演示清楚，适合工具、软件、设备。', en: 'Show how it works and what problem it solves.' },
    '活动节点片': { zh: '绑定大促、发布会、节日等时间窗口，强调此刻行动。', en: 'Tied to a sale, launch, or festival; urge action now.' },
    '客户案例证言片': { zh: '用真实客户前后变化或口述背书，降低观望与怀疑。', en: 'Real customer proof or testimonials to reduce doubt.' },
    '企业形象片': { zh: '展示公司实力、文化与社会责任，偏对公、对投资人、对政府。', en: 'Show company strength and culture for B2B, investors, or government.' },
    '新品发布片': { zh: '宣布新品上市，突出新鲜感、首发权益与期待管理。', en: 'Announce a launch; highlight novelty and first-drop perks.' },
    '电商带货片': { zh: '短视频货架逻辑：卖点、价格锚、库存/时效与下单指令。', en: 'Shoppertainment: benefits, price anchor, urgency, and CTA to buy.' },
    '门店到店转化片': { zh: '把线上兴趣变成到店，强调距离、体验与到店礼遇。', en: 'Turn online interest into store visits.' },
    '招聘雇主品牌片': { zh: '吸引人才投递，讲团队氛围、成长与岗位真实感。', en: 'Attract talent with culture, growth, and role honesty.' },
    '上市融资路演片': { zh: '面向资本讲赛道、增长与护城河，信息密度高、证据优先。', en: 'For capital: market, growth, and moat with evidence.' },
    '公益社会责任片': { zh: '呈现公益行动或ESG，重价值认同，忌过度营销感。', en: 'ESG/charity story; value first, avoid hard selling.' },
    '售后服务口碑片': { zh: '展示服务响应、质保与用户安心，适合复购与转介绍。', en: 'Show after-sales care to drive repurchase and referrals.' },
    '思想领导力片': { zh: '输出行业判断或方法论，把品牌做成“懂行的人”。', en: 'Share industry insight so the brand looks like a thought leader.' },
};

export const PROMO_NARRATIVE_DEFS = {
    '四段式（钩子-共鸣-价值爆发-收口）': { zh: '前3秒钩住 → 痛点共鸣 → 给出核心价值 → CTA/记忆点收口。最通用。', en: 'Hook → empathy → value burst → close. The most general structure.' },
    '反差对比模型': { zh: '用前后、对错、竞品对比制造张力，适合卖点与效果可视化。', en: 'Before/after or vs-competitor contrast to make the benefit obvious.' },
    '感受旅程模型': { zh: '跟着人物一天/一次体验走完情绪弧，适合生活方式与服务。', en: 'Follow a felt journey through a day or experience.' },
    '微型人物小传模型': { zh: '用一个人的小故事承载品牌，适合雇主品牌、案例与人文调性。', en: 'A short character portrait that carries the brand.' },
    '一句话锚定模型': { zh: '全片只守一句主张，反复视觉化，适合口号清晰的品牌。', en: 'One line, visualized again and again.' },
    '承诺兑现模型': { zh: '先立一个可感知承诺，再当场兑现或证明，适合功能与效果。', en: 'Make a promise, then prove it on camera.' },
    '时间切片模型': { zh: '用几个时间切片（3秒/3天/3年）压缩变化，适合成长与效率。', en: 'Time slices that compress change.' },
    '设问递进模型': { zh: '连续抛问题并层层作答，适合原理讲解与知乎/B站长一点的片。', en: 'Stack questions and answers; good for explainer videos.' },
    '权威背书模型': { zh: '专家、数据、认证或大客户站台，适合高客单与对公信任。', en: 'Expert, data, cert, or logo proof for high-trust sells.' },
    '证据递进模型': { zh: '从现象到数据到案例层层加码，适合理性决策型受众。', en: 'Stack evidence from claim → data → case.' },
    '内心矛盾化解模型': { zh: '先说出用户“想买又怕”的纠结，再逐条化解，适合观望期转化。', en: 'Name the hesitation, then dissolve it.' },
    '问题解决模型': { zh: '问题出现 → 尝试失败 → 本品入场解决，适合功能演示。', en: 'Problem → failed attempts → this product solves it.' },
    '前后对比蜕变模型': { zh: '强调使用前的糟与使用后的好，适合医美、培训、效率工具。', en: 'Ugly-before / wow-after transformation.' },
    '场景代入模型': { zh: '把观众直接放进目标使用场景，少讲解多沉浸。', en: 'Drop the viewer into the use-scene with little lecture.' },
    '悬念揭晓模型': { zh: '先藏结果再揭晓，适合开箱、测评与发布会预热。', en: 'Hide the reveal, then pay it off.' },
    '清单盘点模型': { zh: '“N个理由/N个功能”条目化，信息密度高，适合卖点多的产品。', en: 'A numbered list of reasons or features.' },
};

export const PROMO_PRESENTATION_DEFS = {
    '真人口播': { zh: '出镜人或达人面对镜头讲，信任感强、制作快，适合种草与讲解。', en: 'Talking-head to camera; fast and trustworthy.' },
    '实景演绎': { zh: '演员按剧本演戏，情绪与情节完整，适合故事型和品牌片。', en: 'Scripted live-action performance.' },
    '纪实跟拍': { zh: '跟拍真实工作/制作/服务过程，真实感强，适合工厂、餐饮、服务。', en: 'Documentary follow-cam of real work.' },
    '产品静物实拍': { zh: '产品特写、材质与光影，少或不出口播，适合美妆、3C、食品质感。', en: 'Hero product stills and texture shots.' },
    'MG动画': { zh: '平面动效讲逻辑或数据，信息清晰、改稿快，适合原理与政策。', en: 'Motion graphics for logic and data.' },
    '三维CG动画': { zh: '三维拆解内部结构或做不到实拍的场面，适合工业、汽车、空间。', en: '3D CG for internals or impossible shots.' },
    '手绘动画': { zh: '手绘/插画运动，温度高、差异化强，适合人文与儿童向。', en: 'Hand-drawn warmth and differentiation.' },
    '屏幕录屏演示': { zh: '录软件/后台/操作路径，最适合 SaaS 与功能演示。', en: 'Screen recording of the actual product UI.' },
    '素材混剪': { zh: '已有成片/库存素材快剪，周期短，适合活动节点与多平台改版。', en: 'Fast recut of existing footage.' },
    '图文轮播': { zh: '多帧图+字幕卡，制作成本最低，适合小红书封面友好内容。', en: 'Image-and-caption carousel; cheapest to make.' },
    '虚拟数字人口播': { zh: '数字人出镜口播，可规模化换语言/形象，需注意“假人感”。', en: 'Virtual presenter; scalable, watch the uncanny valley.' },
    '航拍大场面': { zh: '无人机/大远景建立格局，适合园区、地产、文旅与企业实力。', en: 'Aerial scale for parks, real estate, tourism, or campus.' },
    'AI生成影像': { zh: '用生成画面补实拍缺口，适合概念、奇观或预算不足；需标注风格并控一致性。', en: 'Gen-AI visuals for concepts or missing footage; keep style consistent.' },
};

export const PROMO_PLATFORM_DEFS = {
    '抖音': { zh: '信息流竖屏，前3秒强钩子，15-30s优先，口播与CTA都可以硬。', en: 'Vertical feed; hook in 3s; 15–30s; strong CTA ok.' },
    '小红书': { zh: '生活方式与质感优先，钩子偏软，封面友好，CTA不要太推销。', en: 'Lifestyle and texture; softer hook and CTA; cover-first.' },
    'B站': { zh: '可更长更完整，允许讲解密度，适合原理、测评与世界观。', en: 'Longer, denser explainers and reviews.' },
    '视频号': { zh: '熟人社交与信任感，钩子清楚但不油，适合到店与留资。', en: 'Trusted social graph; clear but not oily; good for visits/leads.' },
    '知乎': { zh: '问题钩子+证据，适合功能、案例与思想领导力。', en: 'Question + evidence; good for features and thought leadership.' },
    '快手': { zh: '接地气、强结果、强CTA，少炫技，适合下沉与效果承诺。', en: 'Down-to-earth, result-first, strong CTA.' },
};
export const PROMO_IMAGE_TYPES = [
    { value: 'product', zh: '产品', en: 'Product' },
    { value: 'character', zh: '角色', en: 'Character' },
    { value: 'scene', zh: '场景', en: 'Scene' },
    { value: 'prop', zh: '道具', en: 'Prop' },
];

const emptyEnterprise = () => ({
    enterprise_name: '',
    enterprise_intro: '',
    brand_name: '',
    brand_intro: '',
    product_name: '',
    product_info: '',
    core_selling_points: [],
    differentiation: '',
    target_user: '',
    pain_points: [],
    competitor_problem: '',
    image_assets: [],
});

const applyCatalogToEnterprise = (enterpriseRow, productRow, fallback = {}, brandRow = null) => ({
    ...emptyEnterprise(),
    ...fallback,
    enterprise_name: enterpriseRow ? (enterpriseRow.name || '') : (fallback.enterprise_name || ''),
    enterprise_intro: enterpriseRow ? (enterpriseRow.intro || '') : (fallback.enterprise_intro || ''),
    brand_name: brandRow ? (brandRow.name || '') : (fallback.brand_name || ''),
    brand_intro: brandRow ? (brandRow.intro || '') : (fallback.brand_intro || ''),
    product_name: productRow?.name || fallback.product_name || '',
    product_info: productRow?.product_info || fallback.product_info || '',
    core_selling_points: Array.isArray(productRow?.core_selling_points)
        ? productRow.core_selling_points
        : (fallback.core_selling_points || []),
    differentiation: productRow?.differentiation || fallback.differentiation || '',
    target_user: productRow?.target_user || fallback.target_user || '',
    pain_points: Array.isArray(productRow?.pain_points) ? productRow.pain_points : (fallback.pain_points || []),
    competitor_problem: productRow?.competitor_problem || fallback.competitor_problem || '',
    image_assets: [],
});

const emptyCampaign = () => ({
    user_raw_text: '',
    goal_type: '',
    narrative_model: '',
    presentation_form: '',
    platform: [],
    expect_duration: '15-30s',
    existing_material: '',
    constraint: '',
    cta: '',
    episodes_count: 1,
});

const emptyColorPalette = () => ({
    main_color: '',
    secondary_colors: [],
    accent_color: '',
    color_tone_description: '',
});

export const emptyPromoPlannerResult = () => ({
    overall_scheme: {
        title: '',
        one_liner: '',
        combination_mode: '',
        main_goal_type: '',
        series_logic: '',
        success_metric: '',
    },
    content_mode: {
        primary_mode: '',
        mode_definition: '',
        outline: [],
        backup_mode: '',
        backup_reason: '',
    },
    video_positioning: {
        goal_type: '',
        communication_goal: '',
        platforms: [],
        duration: '',
        rationale: '',
    },
    narrative_plan: {
        primary_model: '',
        backup_model: '',
        adaptation_reason: '',
    },
    presentation_plan: {
        primary_form: '',
        form_definition: '',
        combo_forms: [],
        combo_rationale: '',
        production_advice: '',
    },
    platform_strategies: [],
    series_schemes: [],
    four_dimension_evaluation: {
        goal_score: 0,
        narrative_score: 0,
        presentation_score: 0,
        platform_score: 0,
        overall_score: 0,
        score_note: '',
        optimization_suggestions: [],
    },
    benchmark_analysis: {
        visual_asset_match_level: '',
        premium_benchmarks: [],
        viral_benchmarks: [],
        pitfalls: [],
        customized_improvement: '',
    },
    structured_business_info: {
        brand_intro: '',
        product_info: '',
        core_selling_points: { primary: '', secondary: [] },
        differentiation: '',
        target_user: '',
        pain_points: [],
        competitor_problem: '',
        communication_goal: '',
        suggested_cta: '',
        image_assets: [],
    },
    missing_info_diagnosis: {
        text_gaps: [],
        visual_gaps: [],
    },
    image_asset_analysis: {
        global_visual_summary: '',
        global_color_palette: emptyColorPalette(),
        image_list: [],
        analysis_warnings: [],
    },
    visual_spec: {
        color_palette: emptyColorPalette(),
        lighting_reference: '',
        composition_advice: '',
        color_grading: '',
        unity_constraints: [],
    },
    material_list: [],
    script_preview: {
        logline: '',
        beats: [],
    },
    warnings: [],
});

const newImageId = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return `img_${Date.now()}_${Math.random().toString(16).slice(2)}`;
};

const linesToList = (text) => String(text || '').split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
const listToLines = (list) => (Array.isArray(list) ? list : []).join('\n');

const deepMerge = (base, incoming) => {
    if (Array.isArray(base) && incoming == null) return base;
    if (base && typeof base === 'object' && !Array.isArray(base) && incoming && typeof incoming === 'object' && !Array.isArray(incoming)) {
        const out = { ...base };
        Object.keys(incoming).forEach((key) => {
            out[key] = deepMerge(base[key], incoming[key]);
        });
        return out;
    }
    return incoming == null ? base : incoming;
};

export const migrateLegacyPromoInput = (legacy = {}) => {
    const src = legacy && typeof legacy === 'object' ? legacy : {};
    const platformText = String(src.channel_context || '');
    const platforms = PROMO_PLATFORMS.filter((name) => platformText.includes(name));
    return {
        enterprise_info: {
            ...emptyEnterprise(),
            target_user: src.target_audience || '',
            product_info: src.core_highlights || '',
            differentiation: src.credibility_proof || '',
            core_selling_points: src.key_message ? [src.key_message] : [],
        },
        campaign_demand: {
            ...emptyCampaign(),
            user_raw_text: src.campaign_objective || '',
            platform: platforms,
            constraint: src.constraints || '',
            cta: src.conversion_cta || '',
            episodes_count: Number(src.episodes_count || 1) || 1,
        },
    };
};

const ChoiceChips = ({ options, value, onChange, disabled, allowCustom = true, customPlaceholder, definitions = {}, t }) => {
    const [hovered, setHovered] = useState('');
    const preset = options.includes(value) ? value : (value ? PROMO_CUSTOM : '');
    const hintKey = hovered || (preset === PROMO_CUSTOM ? '' : preset);
    const hint = hintKey && definitions[hintKey] ? t(definitions[hintKey].zh, definitions[hintKey].en) : '';
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
                {options.map((name) => {
                    const active = preset === name;
                    const tip = definitions[name] ? t(definitions[name].zh, definitions[name].en) : name;
                    return (
                        <button
                            key={name}
                            type="button"
                            disabled={disabled}
                            title={tip}
                            onMouseEnter={() => setHovered(name)}
                            onMouseLeave={() => setHovered('')}
                            onFocus={() => setHovered(name)}
                            onBlur={() => setHovered('')}
                            onClick={() => onChange(active ? '' : name)}
                            className={`px-3 py-1.5 rounded-md text-xs font-bold ${active ? 'bg-white text-black' : 'bg-white/10 text-white/80 hover:bg-white/20'} disabled:opacity-40`}
                        >
                            {name}
                        </button>
                    );
                })}
                {allowCustom ? (
                    <button
                        type="button"
                        disabled={disabled}
                        title={t('不在清单里时，自己写一种类型', 'Write your own type if it is not listed')}
                        onMouseEnter={() => setHovered('')}
                        onClick={() => onChange(preset === PROMO_CUSTOM ? '' : (options.includes(value) ? PROMO_CUSTOM : (value || PROMO_CUSTOM)))}
                        className={`px-3 py-1.5 rounded-md text-xs font-bold ${preset === PROMO_CUSTOM ? 'bg-white text-black' : 'bg-white/10 text-white/80 hover:bg-white/20'} disabled:opacity-40`}
                    >
                        {t('其他', 'Other')}
                    </button>
                ) : null}
            </div>
            {hint ? (
                <div className="text-xs leading-relaxed text-amber-100/90 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                    <span className="font-semibold text-amber-50">{hintKey}：</span>{hint}
                </div>
            ) : (
                <div className="text-[11px] text-white/35">
                    {t('悬停或选中选项，可查看该类型定义。', 'Hover or select an option to see its definition.')}
                </div>
            )}
            {allowCustom && preset === PROMO_CUSTOM ? (
                <input
                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                    value={options.includes(value) ? '' : (value === PROMO_CUSTOM ? '' : (value || ''))}
                    onChange={(e) => onChange(e.target.value || PROMO_CUSTOM)}
                    placeholder={customPlaceholder}
                    disabled={disabled}
                />
            ) : null}
        </div>
    );
};

const PlatformChips = ({ options, values, onToggle, disabled, definitions = {}, t }) => {
    const [hovered, setHovered] = useState('');
    const selected = Array.isArray(values) ? values : [];
    const hintKey = hovered || selected[selected.length - 1] || '';
    const hint = hintKey && definitions[hintKey] ? t(definitions[hintKey].zh, definitions[hintKey].en) : '';
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
                {options.map((name) => {
                    const active = selected.includes(name);
                    const tip = definitions[name] ? t(definitions[name].zh, definitions[name].en) : name;
                    return (
                        <button
                            key={name}
                            type="button"
                            disabled={disabled}
                            title={tip}
                            onMouseEnter={() => setHovered(name)}
                            onMouseLeave={() => setHovered('')}
                            onFocus={() => setHovered(name)}
                            onBlur={() => setHovered('')}
                            onClick={() => onToggle(name)}
                            className={`px-3 py-1.5 rounded-md text-xs font-bold ${active ? 'bg-white text-black' : 'bg-white/10 text-white/80 hover:bg-white/20'} disabled:opacity-40`}
                        >
                            {name}
                        </button>
                    );
                })}
            </div>
            {hint ? (
                <div className="text-xs leading-relaxed text-amber-100/90 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                    <span className="font-semibold text-amber-50">{hintKey}：</span>{hint}
                </div>
            ) : (
                <div className="text-[11px] text-white/35">
                    {t('悬停或选中平台，可查看适配说明。', 'Hover or select a platform to see the fit note.')}
                </div>
            )}
        </div>
    );
};

const FieldLabel = ({ children, hint }) => (
    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">
        {children}
        {hint ? <span className="ml-2 normal-case font-normal text-[11px] text-muted-foreground/80">{hint}</span> : null}
    </label>
);

const CatalogPickRow = ({
    t,
    label,
    value,
    options,
    disabled,
    onChange,
    onCreate,
    onEdit,
    createDisabled,
    editDisabled,
    emptyOption,
}) => (
    <div>
        <FieldLabel>{label}</FieldLabel>
        <div className="flex flex-col sm:flex-row gap-2">
            <select
                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none flex-1"
                value={value || ''}
                disabled={disabled}
                onChange={(e) => onChange(e.target.value)}
            >
                <option value="">{emptyOption}</option>
                {(options || []).map((item) => (
                    <option key={`${label}-${item.id}`} value={String(item.id)}>{item.name}</option>
                ))}
            </select>
            <div className="flex gap-2">
                <button
                    type="button"
                    onClick={onEdit}
                    disabled={editDisabled}
                    className="px-3 py-2 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 disabled:opacity-40 whitespace-nowrap flex items-center gap-1"
                >
                    <Pencil className="w-3 h-3" /> {t('编辑', 'Edit')}
                </button>
                <button
                    type="button"
                    onClick={onCreate}
                    disabled={createDisabled}
                    className="px-3 py-2 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 disabled:opacity-40 whitespace-nowrap flex items-center gap-1"
                >
                    <Plus className="w-3 h-3" /> {t('新增', 'New')}
                </button>
            </div>
        </div>
    </div>
);

const TextArea = ({ value, onChange, rows = 3, placeholder, disabled }) => (
    <textarea
        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-y placeholder:text-white/25"
        style={{ minHeight: `${Math.max(rows, 2) * 1.6}rem` }}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
    />
);

const TextInput = ({ value, onChange, placeholder, disabled }) => (
    <input
        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full placeholder:text-white/25"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
    />
);

const SectionCard = ({ title, children, extra }) => (
    <div className="bg-black/20 border border-white/10 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-white">{title}</h4>
            {extra}
        </div>
        {children}
    </div>
);

const isAcceptedImage = (file) => {
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    const type = String(file?.type || '').toLowerCase();
    return PROMO_IMAGE_EXTS.includes(ext) || type === 'image/jpeg' || type === 'image/png' || type === 'image/webp';
};

const pickPlannerState = (source) => {
    const gi = source?.global_info && typeof source.global_info === 'object' ? source.global_info : {};
    return {
        promo_planner_input: source?.promo_planner_input || gi.promo_planner_input,
        promo_planner_result: source?.promo_planner_result || gi.promo_planner_result,
        promo_dna_global_md: source?.promo_dna_global_md || gi.promo_dna_global_md,
        promo_generator_input: source?.promo_generator_input || gi.promo_generator_input,
    };
};

export default function PromoPlanner({
    projectId,
    t,
    project,
    info,
    setInfo,
    setProject,
    onProjectUpdate,
    buildScriptAnalysisApiPayload,
    isGenerating,
    setIsGenerating,
    skipNextAutosaveRef,
    standalone = true,
    onEpisodesCountChange,
    onGenerateEpisodeScripts,
    episodeScriptsRunning,
    isStoppingEpisodeScripts,
    targetEpisodeNumberForGen,
    setTargetEpisodeNumberForGen,
    episodeGuidance,
    setEpisodeGuidance,
    onOpenCatalog,
    onGenerateActualScript,
    isGeneratingScript = false,
    hasScript = false,
    onOpenScriptTab,
}) {
    const [enterprise, setEnterprise] = useState(emptyEnterprise);
    const [campaign, setCampaign] = useState(emptyCampaign);
    const [enterprises, setEnterprises] = useState([]);
    const [brands, setBrands] = useState([]);
    const [products, setProducts] = useState([]);
    const [selectedEnterpriseId, setSelectedEnterpriseId] = useState('');
    const [selectedBrandId, setSelectedBrandId] = useState('');
    const [selectedProductId, setSelectedProductId] = useState('');
    const [assets, setAssets] = useState([]);
    const [result, setResult] = useState(null);
    const [previewImage, setPreviewImage] = useState(null);
    const [selectedAssetIds, setSelectedAssetIds] = useState([]);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef(null);
    const replaceInputRef = useRef(null);
    const replaceTargetIdRef = useRef(null);
    const hydratedRef = useRef(false);
    const inputTimerRef = useRef(null);
    const resultTimerRef = useRef(null);
    const skipInputSaveRef = useRef(true);
    const skipResultSaveRef = useRef(true);
    const assetsRef = useRef(assets);
    useEffect(() => {
        assetsRef.current = assets;
    }, [assets]);
    useEffect(() => {
        hydratedRef.current = false;
    }, [projectId]);

    const busy = isGenerating || isGeneratingScript || (!standalone && (episodeScriptsRunning || isStoppingEpisodeScripts));

    const hydrateFromProject = useCallback((source) => {
        const gi = pickPlannerState(source);
        const saved = gi.promo_planner_input && typeof gi.promo_planner_input === 'object'
            ? gi.promo_planner_input
            : migrateLegacyPromoInput(gi.promo_generator_input);
        const nextEnterprise = applyCatalogToEnterprise(
            source?.enterprise,
            source?.product,
            saved.enterprise_info || {},
            source?.brand,
        );
        setSelectedEnterpriseId(source?.enterprise_id ? String(source.enterprise_id) : '');
        setSelectedBrandId(source?.brand_id ? String(source.brand_id) : '');
        setSelectedProductId(source?.product_id ? String(source.product_id) : '');
        const nextCampaign = {
            ...emptyCampaign(),
            ...(saved.campaign_demand || {}),
            platform: Array.isArray(saved.campaign_demand?.platform)
                ? saved.campaign_demand.platform
                : String(saved.campaign_demand?.platform || '')
                    .split(/[\/,、\s]+/)
                    .map((s) => s.trim())
                    .filter((s) => PROMO_PLATFORMS.includes(s)),
        };
        const rawAssets = Array.isArray(saved.enterprise_info?.image_assets) ? saved.enterprise_info.image_assets : [];
        setEnterprise(nextEnterprise);
        setCampaign(nextCampaign);
        setAssets(rawAssets.filter((item) => !item.owner_kind || item.owner_kind === 'project').map((item) => ({
            image_id: item.image_id || newImageId(),
            img_url: item.img_url || '',
            image_type: item.image_type || 'product',
            object_name: item.object_name || '',
            user_remark: item.user_remark || '',
            preview_url: item.img_url || '',
            upload_status: item.img_url ? 'ready' : 'failed',
        })));
        if (gi.promo_planner_result && typeof gi.promo_planner_result === 'object') {
            setResult(deepMerge(emptyPromoPlannerResult(), gi.promo_planner_result));
        } else {
            setResult(null);
        }
        onEpisodesCountChange?.(Number(nextCampaign.episodes_count || 1) || 1);
    }, [onEpisodesCountChange]);

    useEffect(() => {
        if (hydratedRef.current) return;
        if (!project && !info) return;
        skipInputSaveRef.current = true;
        skipResultSaveRef.current = true;
        hydrateFromProject(project || info);
        hydratedRef.current = true;
    }, [hydrateFromProject, info, project]);

    const loadCatalog = useCallback(async (enterpriseId = selectedEnterpriseId, brandId = selectedBrandId) => {
        try {
            const [enterpriseRows, brandRows, productRows] = await Promise.all([
                fetchPromoEnterprises().catch(() => []),
                fetchPromoBrands(enterpriseId ? { enterprise_id: Number(enterpriseId) } : {}).catch(() => []),
                fetchPromoProducts(brandId ? { brand_id: Number(brandId) } : (enterpriseId ? { enterprise_id: Number(enterpriseId) } : {})).catch(() => []),
            ]);
            setEnterprises(Array.isArray(enterpriseRows) ? enterpriseRows : []);
            setBrands(Array.isArray(brandRows) ? brandRows : []);
            setProducts(Array.isArray(productRows) ? productRows : []);
        } catch (err) {
            console.error('[PromoPlanner] catalog load failed', err);
        }
    }, [selectedBrandId, selectedEnterpriseId]);

    useEffect(() => {
        loadCatalog();
    }, [loadCatalog]);

    const selectedEnterprise = useMemo(
        () => enterprises.find((item) => String(item.id) === String(selectedEnterpriseId)) || null,
        [enterprises, selectedEnterpriseId]
    );
    const selectedBrand = useMemo(
        () => brands.find((item) => String(item.id) === String(selectedBrandId)) || null,
        [brands, selectedBrandId]
    );
    const selectedProduct = useMemo(
        () => products.find((item) => String(item.id) === String(selectedProductId)) || null,
        [products, selectedProductId]
    );

    const applyEnterpriseSelection = (enterpriseId, nextBrands = brands, nextProducts = products) => {
        const row = enterprises.find((item) => String(item.id) === String(enterpriseId)) || null;
        setSelectedEnterpriseId(enterpriseId ? String(enterpriseId) : '');
        const keepBrand = nextBrands.find((item) => String(item.id) === String(selectedBrandId) && String(item.enterprise_id) === String(enterpriseId));
        const nextBrand = keepBrand || null;
        setSelectedBrandId(nextBrand ? String(nextBrand.id) : '');
        const keepProduct = nextProducts.find((item) => String(item.id) === String(selectedProductId) && String(item.enterprise_id) === String(enterpriseId) && (!nextBrand || String(item.brand_id) === String(nextBrand.id)));
        const nextProduct = keepProduct || null;
        setSelectedProductId(nextProduct ? String(nextProduct.id) : '');
        setEnterprise((prev) => applyCatalogToEnterprise(row, nextProduct, prev, nextBrand));
    };

    const applyBrandSelection = (brandId, nextProducts = products) => {
        const row = brands.find((item) => String(item.id) === String(brandId)) || null;
        setSelectedBrandId(row ? String(row.id) : '');
        if (row && String(row.enterprise_id) !== String(selectedEnterpriseId)) {
            setSelectedEnterpriseId(String(row.enterprise_id));
        }
        const keepProduct = nextProducts.find((item) => String(item.id) === String(selectedProductId) && String(item.brand_id) === String(brandId));
        const nextProduct = keepProduct || null;
        setSelectedProductId(nextProduct ? String(nextProduct.id) : '');
        const enterpriseRow = enterprises.find((item) => String(item.id) === String(row?.enterprise_id || selectedEnterpriseId)) || selectedEnterprise;
        setEnterprise((prev) => applyCatalogToEnterprise(enterpriseRow, nextProduct, prev, row));
    };

    const applyProductSelection = (productId, nextProducts = products) => {
        const row = nextProducts.find((item) => String(item.id) === String(productId)) || null;
        setSelectedProductId(row ? String(row.id) : '');
        if (row && row.brand_id && String(row.brand_id) !== String(selectedBrandId)) {
            setSelectedBrandId(String(row.brand_id));
        }
        if (row && String(row.enterprise_id) !== String(selectedEnterpriseId)) {
            setSelectedEnterpriseId(String(row.enterprise_id));
        }
        const enterpriseRow = enterprises.find((item) => String(item.id) === String(row?.enterprise_id || selectedEnterpriseId)) || selectedEnterprise;
        const brandRow = brands.find((item) => String(item.id) === String(row?.brand_id || selectedBrandId)) || selectedBrand;
        setEnterprise((prev) => applyCatalogToEnterprise(enterpriseRow, row, prev, brandRow));
    };

    const openCatalog = (kind, action) => {
        const focus = {
            enterpriseId: selectedEnterpriseId,
            brandId: selectedBrandId,
            productId: selectedProductId,
            kind,
            action,
        };
        if (typeof onOpenCatalog === 'function') {
            onOpenCatalog(focus);
            return;
        }
        writePromoCatalogFocus({
            ...focus,
            key: Date.now(),
            returnPath: typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : '',
            returnProjectId: projectId,
        });
        if (typeof window !== 'undefined') {
            window.location.assign('/projects');
        }
    };

    const readyAssets = useMemo(
        () => assets.filter((item) => item.upload_status === 'ready' && item.img_url),
        [assets]
    );

    const buildInputPayload = useCallback(() => ({
        enterprise_id: Number(selectedEnterpriseId) || null,
        brand_id: Number(selectedBrandId) || null,
        product_id: Number(selectedProductId) || null,
        enterprise_info: {
            ...enterprise,
            core_selling_points: Array.isArray(enterprise.core_selling_points) ? enterprise.core_selling_points : linesToList(enterprise.core_selling_points),
            pain_points: Array.isArray(enterprise.pain_points) ? enterprise.pain_points : linesToList(enterprise.pain_points),
            image_assets: readyAssets.map((item) => ({
                image_id: item.image_id,
                img_url: item.img_url,
                image_type: item.image_type,
                object_name: item.object_name,
                user_remark: item.user_remark,
                owner_kind: 'project',
            })),
        },
        campaign_demand: {
            ...campaign,
            goal_type: campaign.goal_type === PROMO_CUSTOM ? '' : String(campaign.goal_type || '').trim(),
            narrative_model: campaign.narrative_model === PROMO_CUSTOM ? '' : String(campaign.narrative_model || '').trim(),
            presentation_form: campaign.presentation_form === PROMO_CUSTOM ? '' : String(campaign.presentation_form || '').trim(),
            platform: campaign.platform,
            episodes_count: Number(campaign.episodes_count || 1) || 1,
        },
    }), [assets, campaign, enterprise, readyAssets, selectedBrandId, selectedEnterpriseId, selectedProductId]);

    useEffect(() => {
        onEpisodesCountChange?.(Number(campaign.episodes_count || 1) || 1);
    }, [campaign.episodes_count, onEpisodesCountChange]);

    useEffect(() => {
        if (!projectId || !hydratedRef.current) return;
        if (skipInputSaveRef.current) {
            skipInputSaveRef.current = false;
            return;
        }
        if (isGenerating) return;
        if (inputTimerRef.current) clearTimeout(inputTimerRef.current);
        inputTimerRef.current = setTimeout(async () => {
            try {
                const payload = buildInputPayload();
                await saveProjectPromoPlannerInput(projectId, payload);
                setInfo?.((prev) => ({
                    ...prev,
                    promo_planner_input: payload,
                }));
            } catch (err) {
                console.error('[PromoPlanner] input autosave failed', err);
            }
        }, 900);
        return () => {
            if (inputTimerRef.current) clearTimeout(inputTimerRef.current);
        };
    }, [buildInputPayload, isGenerating, projectId]);

    useEffect(() => {
        if (!projectId || !result || !hydratedRef.current) return;
        if (skipResultSaveRef.current) {
            skipResultSaveRef.current = false;
            return;
        }
        if (isGenerating) return;
        if (resultTimerRef.current) clearTimeout(resultTimerRef.current);
        resultTimerRef.current = setTimeout(async () => {
            try {
                const updated = await saveProjectPromoPlannerResult(projectId, { promo_planner_result: result });
                const gi = pickPlannerState(updated);
                setInfo?.((prev) => ({
                    ...prev,
                    ...gi,
                    promo_planner_result: gi.promo_planner_result || result,
                    promo_dna_global_md: gi.promo_dna_global_md || prev.promo_dna_global_md,
                }));
                if (updated) setProject?.(updated);
            } catch (err) {
                console.error('[PromoPlanner] result autosave failed', err);
            }
        }, 1200);
        return () => {
            if (resultTimerRef.current) clearTimeout(resultTimerRef.current);
        };
    }, [isGenerating, projectId, result, setInfo]);

    const patchCampaign = (key, value) => setCampaign((prev) => ({ ...prev, [key]: value }));
    const patchResult = (path, value) => {
        setResult((prev) => {
            const next = deepMerge(emptyPromoPlannerResult(), prev || {});
            const parts = path.split('.');
            let cursor = next;
            for (let i = 0; i < parts.length - 1; i += 1) {
                const key = parts[i];
                cursor[key] = Array.isArray(cursor[key]) ? [...cursor[key]] : { ...(cursor[key] || {}) };
                cursor = cursor[key];
            }
            cursor[parts[parts.length - 1]] = value;
            return next;
        });
    };

    const uploadOne = async (file, existingId = null) => {
        const imageId = existingId || newImageId();
        const preview = URL.createObjectURL(file);
        const draft = {
            image_id: imageId,
            img_url: '',
            image_type: 'product',
            object_name: file.name.replace(/\.[^.]+$/, ''),
            user_remark: '',
            preview_url: preview,
            upload_status: 'uploading',
            file,
        };
        setAssets((prev) => {
            const exists = prev.some((item) => item.image_id === imageId);
            if (exists) {
                return prev.map((item) => (item.image_id === imageId ? { ...item, ...draft, image_type: item.image_type, object_name: item.object_name, user_remark: item.user_remark } : item));
            }
            return [...prev, draft];
        });
        try {
            if (!isAcceptedImage(file)) {
                throw new Error(t('仅支持 jpg / png / webp', 'Only jpg / png / webp'));
            }
            if (file.size > PROMO_IMAGE_MAX_MB * 1024 * 1024) {
                throw new Error(t(`单图不超过 ${PROMO_IMAGE_MAX_MB}MB`, `Max ${PROMO_IMAGE_MAX_MB}MB per image`));
            }
            const uploaded = await uploadAsset(file, {
                project_id: String(projectId || ''),
                type: 'image',
                asset_type: 'promo_image_asset',
                remark: `promo_asset:${imageId}`,
            });
            const url = String(uploaded?.url || '').trim();
            if (!url) throw new Error(t('上传成功但未返回地址', 'Upload succeeded but no URL returned'));
            setAssets((prev) => prev.map((item) => (
                item.image_id === imageId
                    ? { ...item, img_url: url, preview_url: url, upload_status: 'ready', upload_error: '' }
                    : item
            )));
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || t('上传失败', 'Upload failed');
            setAssets((prev) => prev.map((item) => (
                item.image_id === imageId
                    ? { ...item, upload_status: 'failed', upload_error: String(message) }
                    : item
            )));
        }
    };

    const handleFiles = async (fileList) => {
        const files = Array.from(fileList || []);
        await Promise.all(files.map((file) => uploadOne(file)));
    };

    const removeAssets = (ids) => {
        const idSet = new Set(ids);
        setAssets((prev) => prev.filter((item) => !idSet.has(item.image_id)));
        setSelectedAssetIds((prev) => prev.filter((id) => !idSet.has(id)));
    };

    const waitForUploads = async () => {
        const started = Date.now();
        while (Date.now() - started < 20000) {
            const pending = (assetsRef.current || []).some((item) => item.upload_status === 'uploading');
            if (!pending) return;
            await new Promise((resolve) => setTimeout(resolve, 200));
        }
    };

    const handleGenerate = async () => {
        if (isGenerating) return;
        const resolvedGoal = String(campaign.goal_type || '').trim();
        if (!resolvedGoal || resolvedGoal === PROMO_CUSTOM) {
            alert(t('请先选择宣传目标类型（必填）', 'Please select a promo goal type first (required).'));
            return;
        }
        setIsGenerating(true);
        try {
            await waitForUploads();
            const latestReady = (assetsRef.current || []).filter((item) => item.upload_status === 'ready' && item.img_url);
            const payload = {
                ...buildInputPayload(),
                enterprise_info: {
                    ...buildInputPayload().enterprise_info,
                    image_assets: latestReady.map((item) => ({
                        image_id: item.image_id,
                        img_url: item.img_url,
                        image_type: item.image_type,
                        object_name: item.object_name,
                        user_remark: item.user_remark,
                    })),
                },
                campaign_demand: {
                    ...buildInputPayload().campaign_demand,
                    goal_type: resolvedGoal,
                    narrative_model: String(campaign.narrative_model || '').trim() === PROMO_CUSTOM ? '' : String(campaign.narrative_model || '').trim(),
                    presentation_form: String(campaign.presentation_form || '').trim() === PROMO_CUSTOM ? '' : String(campaign.presentation_form || '').trim(),
                },
            };
            const hasText = [
                payload.enterprise_info.enterprise_name,
                payload.enterprise_info.enterprise_intro,
                payload.enterprise_info.brand_name,
                payload.enterprise_info.brand_intro,
                payload.enterprise_info.product_name,
                payload.enterprise_info.product_info,
                payload.campaign_demand.user_raw_text,
            ].some((item) => String(item || '').trim());
            if (!hasText) {
                alert(t('请先选择宣传主体，或填写宣传诉求', 'Select a catalog subject, or fill campaign demand first.'));
                return;
            }
            const updated = await generateProjectPromoPlanner(projectId, buildScriptAnalysisApiPayload ? buildScriptAnalysisApiPayload(payload) : payload);
            setProject?.(updated);
            const gi = pickPlannerState(updated);
            skipNextAutosaveRef && (skipNextAutosaveRef.current = true);
            skipResultSaveRef.current = true;
            skipInputSaveRef.current = true;
            if (gi.promo_planner_result) {
                setResult(deepMerge(emptyPromoPlannerResult(), gi.promo_planner_result));
            }
            const nextCampaign = gi.promo_planner_input?.campaign_demand;
            if (nextCampaign && typeof nextCampaign === 'object') {
                setCampaign((prev) => ({
                    ...emptyCampaign(),
                    ...prev,
                    ...nextCampaign,
                    platform: Array.isArray(nextCampaign.platform) ? nextCampaign.platform : (prev.platform || []),
                }));
            }
            setInfo?.((prev) => ({
                ...prev,
                ...gi,
                promo_planner_input: gi.promo_planner_input || payload,
                promo_planner_result: gi.promo_planner_result || prev.promo_planner_result,
                promo_dna_global_md: gi.promo_dna_global_md || prev.promo_dna_global_md,
            }));
            onProjectUpdate?.();
        } catch (err) {
            console.error(err);
            alert(`${t('策划方案生成失败', 'Failed to generate promo plan')}:\n${formatProviderModelEndpointError(err)}`);
        } finally {
            setIsGenerating(false);
        }
    };

    const togglePlatform = (name) => {
        const current = Array.isArray(campaign.platform) ? campaign.platform : [];
        patchCampaign(
            'platform',
            current.includes(name) ? current.filter((item) => item !== name) : [...current, name]
        );
    };

    const updateAsset = (imageId, patch) => {
        setAssets((prev) => prev.map((item) => (item.image_id === imageId ? { ...item, ...patch } : item)));
    };

    const resultReady = !!(result && (
        result.overall_scheme?.title
        || result.overall_scheme?.one_liner
        || result.content_mode?.primary_mode
        || result.video_positioning?.goal_type
        || result.script_preview?.logline
        || (Array.isArray(result.platform_strategies) && result.platform_strategies.length)
        || (Array.isArray(result.series_schemes) && result.series_schemes.length)
        || result.material_list?.length
    ));

    return (
        <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6 xl:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-semibold text-primary">{t('商业宣传片智能策划', 'Commercial Promo Planner')}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                        {t('提交后由独立策划 skill 给出整体方案：内容模式与大纲、表现形式、各平台策略，以及单片或系列组合。企业/品牌/产品在宣传主体维护。', 'A standalone planner skill returns the overall scheme: content mode and outline, presentation, per-platform strategy, and single-film or series combinations. Catalog lives in Promo Catalog.')}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={handleGenerate}
                        disabled={busy || !String(campaign.goal_type || '').trim() || campaign.goal_type === PROMO_CUSTOM}
                        className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${busy || !String(campaign.goal_type || '').trim() || campaign.goal_type === PROMO_CUSTOM ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary text-black hover:opacity-90'}`}
                    >
                        {isGenerating ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成策划方案', 'Generate Plan')}</>}
                    </button>
                </div>
            </div>

            <SectionCard title={t('📄 宣传主体', '📄 Catalog')}>
                <div className="space-y-3">
                    <p className="text-xs text-white/55">
                        {t('只选择本片要用的企业、品牌、产品与服务。点击编辑或新增会进入宣传主体界面。', 'Select the enterprise, brand and offering for this campaign. Edit or create them in Promo Catalog.')}
                    </p>
                    <CatalogPickRow
                        t={t}
                        label={t('企业', 'Enterprise')}
                        value={selectedEnterpriseId}
                        options={enterprises}
                        disabled={busy}
                        emptyOption={t('未选择企业', 'No enterprise selected')}
                        onChange={async (nextId) => {
                            const [brandRows, productRows] = await Promise.all([
                                fetchPromoBrands(nextId ? { enterprise_id: Number(nextId) } : {}).catch(() => []),
                                fetchPromoProducts(nextId ? { enterprise_id: Number(nextId) } : {}).catch(() => []),
                            ]);
                            setBrands(Array.isArray(brandRows) ? brandRows : []);
                            setProducts(Array.isArray(productRows) ? productRows : []);
                            applyEnterpriseSelection(nextId, Array.isArray(brandRows) ? brandRows : [], Array.isArray(productRows) ? productRows : []);
                        }}
                        onEdit={() => openCatalog('enterprise', 'edit')}
                        onCreate={() => openCatalog('enterprise', 'create')}
                        editDisabled={busy || !selectedEnterpriseId}
                        createDisabled={busy}
                    />
                    <CatalogPickRow
                        t={t}
                        label={t('品牌（归属当前企业）', 'Brand (belongs to enterprise)')}
                        value={selectedBrandId}
                        options={brands}
                        disabled={busy || !selectedEnterpriseId}
                        emptyOption={t('未选择品牌', 'No brand selected')}
                        onChange={async (nextId) => {
                            const rows = await fetchPromoProducts(nextId ? { brand_id: Number(nextId) } : (selectedEnterpriseId ? { enterprise_id: Number(selectedEnterpriseId) } : {})).catch(() => []);
                            setProducts(Array.isArray(rows) ? rows : []);
                            applyBrandSelection(nextId, Array.isArray(rows) ? rows : []);
                        }}
                        onEdit={() => openCatalog('brand', 'edit')}
                        onCreate={() => openCatalog('brand', 'create')}
                        editDisabled={busy || !selectedBrandId}
                        createDisabled={busy || !selectedEnterpriseId}
                    />
                    <CatalogPickRow
                        t={t}
                        label={t('产品与服务（归属当前品牌）', 'Product / service (belongs to brand)')}
                        value={selectedProductId}
                        options={products}
                        disabled={busy || !selectedBrandId}
                        emptyOption={t('未选择产品', 'No product selected')}
                        onChange={(nextId) => applyProductSelection(nextId)}
                        onEdit={() => openCatalog('offering', 'edit')}
                        onCreate={() => openCatalog('offering', 'create')}
                        editDisabled={busy || !selectedProductId}
                        createDisabled={busy || !selectedBrandId}
                    />
                </div>
            </SectionCard>

            <SectionCard title={t('📦 本片补充素材', '📦 Campaign assets')}>
                <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                        <h5 className="text-sm font-semibold text-white">{t('🖼️ 本片补充素材', '🖼️ Campaign-only assets')}</h5>
                        {selectedAssetIds.length > 0 ? (
                            <button type="button" onClick={() => removeAssets(selectedAssetIds)} className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-200 hover:bg-red-500/30 flex items-center gap-1">
                                <Trash2 className="w-3 h-3" /> {t('批量删除', 'Delete selected')}
                            </button>
                        ) : null}
                    </div>
                    <div className="flex items-start gap-2 text-[11px] text-amber-200/90 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                        <span>{t('图片仅作视觉参考。系统不做版权、产品真实性校验，请确保你拥有使用权。', 'Images are visual references only. The system does not check copyright or product authenticity.')}</span>
                    </div>
                    <div
                        className={`border border-dashed rounded-lg px-4 py-6 text-center cursor-pointer transition-colors ${dragOver ? 'border-primary bg-primary/10' : 'border-white/15 hover:border-white/30'}`}
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={(e) => {
                            e.preventDefault();
                            setDragOver(false);
                            handleFiles(e.dataTransfer.files);
                        }}
                    >
                        <Upload className="w-5 h-5 mx-auto mb-2 text-white/70" />
                        <div className="text-sm text-white/80">{t('拖拽或点击上传图片，支持批量多选', 'Drop or click to upload. Multiple images supported.')}</div>
                        <div className="text-[11px] text-muted-foreground mt-1">{t(`jpg / png / webp，单图不超过 ${PROMO_IMAGE_MAX_MB}MB`, `jpg / png / webp, max ${PROMO_IMAGE_MAX_MB}MB each`)}</div>
                    </div>
                    <input ref={fileInputRef} type="file" accept={PROMO_IMAGE_ACCEPT} multiple className="hidden" onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }} />
                    <input
                        ref={replaceInputRef}
                        type="file"
                        accept={PROMO_IMAGE_ACCEPT}
                        className="hidden"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file && replaceTargetIdRef.current) uploadOne(file, replaceTargetIdRef.current);
                            e.target.value = '';
                        }}
                    />
                    {assets.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                            {assets.map((asset) => (
                                <div key={asset.image_id} className="bg-black/30 border border-white/10 rounded-lg overflow-hidden">
                                    <div className="relative h-36 bg-black/40">
                                        {asset.preview_url || asset.img_url ? (
                                            <img src={getFullUrl(asset.preview_url || asset.img_url)} alt={asset.object_name || 'asset'} className="w-full h-full object-cover cursor-zoom-in" onClick={() => setPreviewImage(asset)} />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-white/30"><ImageIcon className="w-8 h-8" /></div>
                                        )}
                                        <label className="absolute top-2 left-2">
                                            <input type="checkbox" checked={selectedAssetIds.includes(asset.image_id)} onChange={(e) => setSelectedAssetIds((prev) => e.target.checked ? [...prev, asset.image_id] : prev.filter((id) => id !== asset.image_id))} />
                                        </label>
                                        <div className="absolute top-2 right-2 text-[10px] px-1.5 py-0.5 rounded bg-black/60">
                                            {asset.upload_status === 'uploading' ? t('上传中', 'Uploading') : asset.upload_status === 'failed' ? t('失败', 'Failed') : t('已上传', 'Ready')}
                                        </div>
                                    </div>
                                    <div className="p-3 space-y-2">
                                        <select
                                            className="w-full bg-black/30 border border-white/10 rounded-md px-2 py-1.5 text-sm"
                                            value={asset.image_type}
                                            onChange={(e) => updateAsset(asset.image_id, { image_type: e.target.value })}
                                        >
                                            {PROMO_IMAGE_TYPES.map((opt) => (
                                                <option key={opt.value} value={opt.value}>{t(opt.zh, opt.en)}</option>
                                            ))}
                                        </select>
                                        <TextInput value={asset.object_name} onChange={(v) => updateAsset(asset.image_id, { object_name: v })} placeholder={t('自定义命名，如厨师', 'Name, e.g. Chef')} disabled={busy} />
                                        <TextInput value={asset.user_remark} onChange={(v) => updateAsset(asset.image_id, { user_remark: v })} placeholder={t('可选备注', 'Optional remark')} disabled={busy} />
                                        {asset.upload_error ? <div className="text-[11px] text-red-300">{asset.upload_error}</div> : null}
                                        <div className="flex gap-2">
                                            <button type="button" className="flex-1 text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20" onClick={() => { replaceTargetIdRef.current = asset.image_id; replaceInputRef.current?.click(); }}>{t('替换', 'Replace')}</button>
                                            <button type="button" className="flex-1 text-xs px-2 py-1 rounded bg-red-500/20 text-red-200 hover:bg-red-500/30" onClick={() => removeAssets([asset.image_id])}>{t('删除', 'Delete')}</button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-muted-foreground">{t('无图片也可生成方案，image_assets 将为空数组。', 'Images are optional. The plan still generates when image_assets is empty.')}</div>
                    )}
                </div>
            </SectionCard>

            <SectionCard title={t('🎯 本次宣传诉求', '🎯 Campaign Demand')}>
                <div className="space-y-3">
                    <div>
                        <FieldLabel hint={t('必填', 'required')}>{t('宣传目标类型', 'Goal Type')}</FieldLabel>
                        <ChoiceChips
                            t={t}
                            options={PROMO_GOAL_TYPES}
                            definitions={PROMO_GOAL_TYPE_DEFS}
                            value={campaign.goal_type}
                            onChange={(v) => patchCampaign('goal_type', v)}
                            disabled={busy}
                            customPlaceholder={t('自定义目标类型，如经销商大会片', 'Custom goal type')}
                        />
                    </div>
                    <div>
                        <FieldLabel hint={t('可选，未选则由模型回填', 'optional; model fills if empty')}>{t('内容类型', 'Narrative Model')}</FieldLabel>
                        <ChoiceChips
                            t={t}
                            options={PROMO_NARRATIVE_MODELS}
                            definitions={PROMO_NARRATIVE_DEFS}
                            value={campaign.narrative_model}
                            onChange={(v) => patchCampaign('narrative_model', v)}
                            disabled={busy}
                            customPlaceholder={t('自定义内容类型', 'Custom narrative model')}
                        />
                    </div>
                    <div>
                        <FieldLabel hint={t('可选，未选则由模型回填', 'optional; model fills if empty')}>{t('视频表现形式', 'Presentation Form')}</FieldLabel>
                        <ChoiceChips
                            t={t}
                            options={PROMO_PRESENTATION_FORMS}
                            definitions={PROMO_PRESENTATION_DEFS}
                            value={campaign.presentation_form}
                            onChange={(v) => patchCampaign('presentation_form', v)}
                            disabled={busy}
                            customPlaceholder={t('自定义表现形式', 'Custom presentation form')}
                        />
                    </div>
                    <div>
                        <FieldLabel>{t('用户原始诉求', 'Raw Brief')}</FieldLabel>
                        <TextArea value={campaign.user_raw_text} onChange={(v) => patchCampaign('user_raw_text', v)} rows={4} disabled={busy} placeholder={t('描述本次宣传要达成的目标、场景与禁忌', 'Describe the goal, context and constraints')} />
                    </div>
                    <div>
                        <FieldLabel hint={t('可选，未选则由模型回填', 'optional; model fills if empty')}>{t('投放平台（多选）', 'Platforms')}</FieldLabel>
                        <PlatformChips
                            t={t}
                            options={PROMO_PLATFORMS}
                            definitions={PROMO_PLATFORM_DEFS}
                            values={campaign.platform || []}
                            onToggle={togglePlatform}
                            disabled={busy}
                        />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <FieldLabel>{t('期望视频时长', 'Expected Duration')}</FieldLabel>
                            <select className="w-full bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm" value={campaign.expect_duration} onChange={(e) => patchCampaign('expect_duration', e.target.value)}>
                                {PROMO_DURATIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                            </select>
                        </div>
                        <div>
                            <FieldLabel>{t('下游分集数（可选）', 'Downstream episodes (optional)')}</FieldLabel>
                            <input type="number" min="1" className="w-full bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm" value={campaign.episodes_count || 1} onChange={(e) => patchCampaign('episodes_count', Number(e.target.value || 1) || 1)} disabled={busy} />
                        </div>
                    </div>
                    <div>
                        <FieldLabel>{t('已有素材资源描述', 'Existing Materials')}</FieldLabel>
                        <TextArea value={campaign.existing_material} onChange={(v) => patchCampaign('existing_material', v)} rows={2} disabled={busy} />
                    </div>
                    <div>
                        <FieldLabel>{t('制作约束 / 禁止内容', 'Constraints / Forbidden')}</FieldLabel>
                        <TextArea value={campaign.constraint} onChange={(v) => patchCampaign('constraint', v)} rows={2} disabled={busy} />
                    </div>
                    <div>
                        <FieldLabel>{t('期望 CTA 行动指令', 'Desired CTA')}</FieldLabel>
                        <TextInput value={campaign.cta} onChange={(v) => patchCampaign('cta', v)} disabled={busy} placeholder={t('例如：预约到店 / 领取试吃', 'e.g. Book a visit / Claim a trial')} />
                    </div>
                </div>
            </SectionCard>

            {Array.isArray(result?.warnings) && result.warnings.length > 0 ? (
                <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                    {result.warnings.join('；')}
                </div>
            ) : null}

            {resultReady ? (
                <div className="space-y-4">
                    <h3 className="text-base font-semibold text-primary">{t('整体方案（全部可编辑）', 'Overall Scheme (all editable)')}</h3>
                    <OverallSchemeEditor result={result} patchResult={patchResult} t={t} />
                    <ContentModeEditor result={result} setResult={setResult} patchResult={patchResult} t={t} />
                    <PositioningEditor result={result} patchResult={patchResult} t={t} />
                    <NarrativeEditor result={result} patchResult={patchResult} t={t} />
                    <PresentationEditor result={result} patchResult={patchResult} t={t} />
                    <PlatformStrategyEditor result={result} setResult={setResult} t={t} />
                    <SeriesSchemeEditor result={result} setResult={setResult} t={t} />
                    <EvalEditor result={result} patchResult={patchResult} t={t} />
                    <BenchmarkEditor result={result} patchResult={patchResult} t={t} />
                    <BusinessInfoEditor result={result} patchResult={patchResult} assets={readyAssets} t={t} />
                    <DiagnosisEditor result={result} patchResult={patchResult} t={t} />
                    <VisualEditor result={result} patchResult={patchResult} t={t} />
                    <MaterialEditor result={result} setResult={setResult} t={t} />
                    <ScriptPreviewEditor
                        result={result}
                        setResult={setResult}
                        t={t}
                        busy={busy}
                        isGeneratingScript={isGeneratingScript}
                        hasScript={hasScript}
                        onOpenScriptTab={onOpenScriptTab}
                        onGenerateActualScript={async () => {
                            if (typeof onGenerateActualScript !== 'function') return;
                            if (resultTimerRef.current) {
                                clearTimeout(resultTimerRef.current);
                                resultTimerRef.current = null;
                            }
                            try {
                                await saveProjectPromoPlannerResult(projectId, { promo_planner_result: result });
                            } catch (err) {
                                console.error('[PromoPlanner] flush result before script generate failed', err);
                            }
                            await onGenerateActualScript({ result });
                        }}
                    />
                </div>
            ) : (
                <div className="text-sm text-muted-foreground bg-black/20 border border-white/10 rounded-xl px-4 py-8 text-center">
                        {t('选择宣传主体与目标类型后点击「生成策划方案」。将输出内容模式、大纲、表现形式、各平台策略与系列组合。无图片也可生成。', 'Select catalog and goal type, then generate. You will get content mode, outline, presentation, per-platform strategy and series combinations. Images are optional.')}
                </div>
            )}

            {!standalone ? (
            <SectionCard
                title={t('下游：分集脚本（二期衔接）', 'Downstream: Episode Scripts')}
                extra={
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => onGenerateEpisodeScripts?.()}
                            disabled={busy || !resultReady}
                            className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1.5 ${(busy || !resultReady) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                        >
                            {episodeScriptsRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                            {t('全量生成分集', 'Generate All')}
                        </button>
                        <div className="flex items-center bg-white/5 rounded-md overflow-hidden border border-white/10">
                            <input type="number" min="1" className="w-14 px-2 py-1.5 bg-transparent text-xs text-center outline-none" value={targetEpisodeNumberForGen} onChange={(e) => setTargetEpisodeNumberForGen(e.target.value)} disabled={busy} />
                            <button type="button" onClick={() => onGenerateEpisodeScripts?.({ specificEpisode: targetEpisodeNumberForGen })} disabled={!targetEpisodeNumberForGen || busy || !resultReady} className="px-2 py-1.5 text-xs font-bold bg-white/10">{t('单集', 'Single')}</button>
                        </div>
                    </div>
                }
            >
                <FieldLabel>{t('本集生成指导（仅单集生成）', 'Single-episode guidance')}</FieldLabel>
                <TextArea value={episodeGuidance || ''} onChange={setEpisodeGuidance} rows={3} disabled={busy} placeholder={t('仅单集生成时注入', 'Injected only for single-episode generation')} />
            </SectionCard>
            ) : null}

            {previewImage ? (
                <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={() => setPreviewImage(null)}>
                    <div className="relative max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
                        <button type="button" className="absolute -top-10 right-0 text-white/80" onClick={() => setPreviewImage(null)}><X /></button>
                        <img src={getFullUrl(previewImage.preview_url || previewImage.img_url)} alt={previewImage.object_name || ''} className="w-full max-h-[80vh] object-contain rounded-lg" />
                        <div className="text-sm text-white/80 mt-2">{previewImage.object_name} · {previewImage.image_type}</div>
                    </div>
                </div>
            ) : null}
        </div>
    );
}

function OverallSchemeEditor({ result, patchResult, t }) {
    const data = result.overall_scheme || {};
    return (
        <SectionCard title={t('0. 整体方案', '0. Overall Scheme')}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="md:col-span-2"><FieldLabel>{t('方案名称', 'Title')}</FieldLabel><TextInput value={data.title} onChange={(v) => patchResult('overall_scheme.title', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('一句话总策略', 'One-liner')}</FieldLabel><TextArea value={data.one_liner} onChange={(v) => patchResult('overall_scheme.one_liner', v)} rows={2} /></div>
                <div><FieldLabel>{t('组合模式', 'Combination mode')}</FieldLabel><TextInput value={data.combination_mode} onChange={(v) => patchResult('overall_scheme.combination_mode', v)} placeholder={t('单片全案 / 主片+平台改编 / 系列组合', 'Single / master+adapt / series')} /></div>
                <div><FieldLabel>{t('主片目标类型', 'Main goal type')}</FieldLabel><TextInput value={data.main_goal_type} onChange={(v) => patchResult('overall_scheme.main_goal_type', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('系列/改编逻辑', 'Series logic')}</FieldLabel><TextArea value={data.series_logic} onChange={(v) => patchResult('overall_scheme.series_logic', v)} rows={3} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('成功标准', 'Success metric')}</FieldLabel><TextArea value={data.success_metric} onChange={(v) => patchResult('overall_scheme.success_metric', v)} rows={2} /></div>
            </div>
        </SectionCard>
    );
}

function ContentModeEditor({ result, setResult, patchResult, t }) {
    const data = result.content_mode || {};
    const outline = Array.isArray(data.outline) ? data.outline : [];
    const updateOutline = (next) => setResult((prev) => ({
        ...deepMerge(emptyPromoPlannerResult(), prev || {}),
        content_mode: { ...deepMerge(emptyPromoPlannerResult().content_mode, prev?.content_mode || {}), outline: next },
    }));
    return (
        <SectionCard
            title={t('0.1 内容模式与大纲', '0.1 Content Mode & Outline')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => updateOutline([...outline, { section: '', duration: '', purpose: '', content: '', copy_hint: '' }])}><Plus className="w-3 h-3 inline" /> {t('添加段落', 'Add section')}</button>}
        >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div><FieldLabel>{t('主内容模式', 'Primary mode')}</FieldLabel><TextInput value={data.primary_mode} onChange={(v) => patchResult('content_mode.primary_mode', v)} /></div>
                <div><FieldLabel>{t('备选模式', 'Backup mode')}</FieldLabel><TextInput value={data.backup_mode} onChange={(v) => patchResult('content_mode.backup_mode', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('模式定义', 'Mode definition')}</FieldLabel><TextArea value={data.mode_definition} onChange={(v) => patchResult('content_mode.mode_definition', v)} rows={2} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('备选理由', 'Backup reason')}</FieldLabel><TextArea value={data.backup_reason} onChange={(v) => patchResult('content_mode.backup_reason', v)} rows={2} /></div>
            </div>
            <div className="space-y-3 pt-2">
                {outline.map((row, idx) => (
                    <div key={`outline-${idx}`} className="bg-black/20 p-3 rounded-md space-y-2">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <TextInput value={row.section} onChange={(v) => updateOutline(outline.map((item, i) => i === idx ? { ...item, section: v } : item))} placeholder={t('段落名，如开场钩子', 'Section, e.g. Hook')} />
                            <TextInput value={row.duration} onChange={(v) => updateOutline(outline.map((item, i) => i === idx ? { ...item, duration: v } : item))} placeholder={t('时长', 'Duration')} />
                        </div>
                        <TextArea value={row.purpose} onChange={(v) => updateOutline(outline.map((item, i) => i === idx ? { ...item, purpose: v } : item))} rows={2} placeholder={t('目的', 'Purpose')} />
                        <TextArea value={row.content} onChange={(v) => updateOutline(outline.map((item, i) => i === idx ? { ...item, content: v } : item))} rows={2} placeholder={t('具体讲什么/拍什么', 'What to say / shoot')} />
                        <div className="flex items-center gap-2">
                            <TextInput value={row.copy_hint} onChange={(v) => updateOutline(outline.map((item, i) => i === idx ? { ...item, copy_hint: v } : item))} placeholder={t('文案方向', 'Copy hint')} />
                            <button type="button" className="text-xs text-red-200 shrink-0" onClick={() => updateOutline(outline.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
                        </div>
                    </div>
                ))}
            </div>
        </SectionCard>
    );
}

function PlatformStrategyEditor({ result, setResult, t }) {
    const rows = Array.isArray(result.platform_strategies) ? result.platform_strategies : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), platform_strategies: next }));
    const fields = ['platform', 'role', 'duration', 'hook', 'rhythm', 'copy_cta', 'cover_or_title', 'adaptation'];
    const labels = {
        platform: t('平台', 'Platform'),
        role: t('角色（主投放/辅投放）', 'Role'),
        duration: t('时长', 'Duration'),
        hook: t('前3秒钩子', 'Hook'),
        rhythm: t('节奏/剪辑', 'Rhythm'),
        copy_cta: t('文案与 CTA', 'Copy & CTA'),
        cover_or_title: t('封面/标题', 'Cover / title'),
        adaptation: t('相对主片如何改编', 'Adaptation vs master'),
    };
    return (
        <SectionCard
            title={t('3.1 各平台策略', '3.1 Platform Strategies')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update([...rows, Object.fromEntries(fields.map((f) => [f, '']))])}><Plus className="w-3 h-3 inline" /> {t('添加平台', 'Add platform')}</button>}
        >
            <div className="space-y-3">
                {rows.map((row, idx) => (
                    <div key={`plat-${idx}`} className="grid grid-cols-1 md:grid-cols-2 gap-2 bg-black/20 p-3 rounded-md">
                        {fields.map((field) => (
                            field === 'platform' || field === 'role' || field === 'duration' ? (
                                <TextInput key={field} value={row[field]} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, [field]: v } : item))} placeholder={labels[field]} />
                            ) : (
                                <div key={field} className="md:col-span-2">
                                    <FieldLabel>{labels[field]}</FieldLabel>
                                    <TextArea value={row[field]} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, [field]: v } : item))} rows={2} />
                                </div>
                            )
                        ))}
                        <button type="button" className="text-xs text-red-200 text-left" onClick={() => update(rows.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
                    </div>
                ))}
            </div>
        </SectionCard>
    );
}

function SeriesSchemeEditor({ result, setResult, t }) {
    const rows = Array.isArray(result.series_schemes) ? result.series_schemes : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), series_schemes: next }));
    return (
        <SectionCard
            title={t('3.2 系列方案组合', '3.2 Series Combinations')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update([...rows, { episode_name: '', goal_type: '', content_mode: '', outline: '', presentation_form: '', platforms: [], duration: '', cta: '', relation: '' }])}><Plus className="w-3 h-3 inline" /> {t('添加一支', 'Add episode')}</button>}
        >
            <div className="space-y-3">
                {rows.map((row, idx) => (
                    <div key={`series-${idx}`} className="grid grid-cols-1 md:grid-cols-2 gap-2 bg-black/20 p-3 rounded-md">
                        <TextInput value={row.episode_name} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, episode_name: v } : item))} placeholder={t('支片名', 'Episode name')} />
                        <TextInput value={row.goal_type} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, goal_type: v } : item))} placeholder={t('目标类型', 'Goal type')} />
                        <TextInput value={row.content_mode} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, content_mode: v } : item))} placeholder={t('内容模式', 'Content mode')} />
                        <TextInput value={row.presentation_form} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, presentation_form: v } : item))} placeholder={t('表现形式', 'Presentation')} />
                        <TextInput value={Array.isArray(row.platforms) ? row.platforms.join('、') : (row.platforms || '')} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, platforms: linesToList(v.replace(/、/g, '\n')) } : item))} placeholder={t('平台，顿号分隔', 'Platforms')} />
                        <TextInput value={row.duration} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, duration: v } : item))} placeholder={t('时长', 'Duration')} />
                        <div className="md:col-span-2"><FieldLabel>{t('大纲', 'Outline')}</FieldLabel><TextArea value={row.outline} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, outline: v } : item))} rows={3} /></div>
                        <TextInput value={row.cta} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, cta: v } : item))} placeholder="CTA" />
                        <TextInput value={row.relation} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, relation: v } : item))} placeholder={t('在组合中的角色', 'Role in series')} />
                        <button type="button" className="text-xs text-red-200 text-left" onClick={() => update(rows.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
                    </div>
                ))}
            </div>
        </SectionCard>
    );
}

function PositioningEditor({ result, patchResult, t }) {
    const data = result.video_positioning || {};
    return (
        <SectionCard title={t('1. 视频定位结论', '1. Video Positioning')}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div><FieldLabel>{t('目标类型', 'Goal Type')}</FieldLabel><TextInput value={data.goal_type} onChange={(v) => patchResult('video_positioning.goal_type', v)} /></div>
                <div><FieldLabel>{t('建议时长', 'Duration')}</FieldLabel><TextInput value={data.duration} onChange={(v) => patchResult('video_positioning.duration', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('传播目标', 'Communication Goal')}</FieldLabel><TextArea value={data.communication_goal} onChange={(v) => patchResult('video_positioning.communication_goal', v)} rows={2} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('适配平台', 'Platforms')}</FieldLabel><TextInput value={(data.platforms || []).join('、')} onChange={(v) => patchResult('video_positioning.platforms', linesToList(v.replace(/、/g, '\n')))} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('判定依据', 'Rationale')}</FieldLabel><TextArea value={data.rationale} onChange={(v) => patchResult('video_positioning.rationale', v)} rows={2} /></div>
            </div>
        </SectionCard>
    );
}

function NarrativeEditor({ result, patchResult, t }) {
    const data = result.narrative_plan || {};
    return (
        <SectionCard title={t('2. 叙事方案', '2. Narrative Plan')}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div><FieldLabel>{t('首选模型', 'Primary')}</FieldLabel><TextInput value={data.primary_model} onChange={(v) => patchResult('narrative_plan.primary_model', v)} /></div>
                <div><FieldLabel>{t('备选模型', 'Backup')}</FieldLabel><TextInput value={data.backup_model} onChange={(v) => patchResult('narrative_plan.backup_model', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('适配理由', 'Why it fits')}</FieldLabel><TextArea value={data.adaptation_reason} onChange={(v) => patchResult('narrative_plan.adaptation_reason', v)} rows={3} /></div>
            </div>
        </SectionCard>
    );
}

function PresentationEditor({ result, patchResult, t }) {
    const data = result.presentation_plan || {};
    return (
        <SectionCard title={t('3. 表现形式方案', '3. Presentation')}>
            <div className="space-y-3">
                <div><FieldLabel>{t('主形式', 'Primary Form')}</FieldLabel><TextInput value={data.primary_form} onChange={(v) => patchResult('presentation_plan.primary_form', v)} /></div>
                <div><FieldLabel>{t('形式定义与适用条件', 'Form definition')}</FieldLabel><TextArea value={data.form_definition} onChange={(v) => patchResult('presentation_plan.form_definition', v)} rows={2} /></div>
                <div><FieldLabel>{t('组合形式', 'Combo Forms')}</FieldLabel><TextInput value={(data.combo_forms || []).join('、')} onChange={(v) => patchResult('presentation_plan.combo_forms', linesToList(v.replace(/、/g, '\n')))} /></div>
                <div><FieldLabel>{t('组合理由', 'Combo rationale')}</FieldLabel><TextArea value={data.combo_rationale} onChange={(v) => patchResult('presentation_plan.combo_rationale', v)} rows={2} /></div>
                <div><FieldLabel>{t('制作建议', 'Production Advice')}</FieldLabel><TextArea value={data.production_advice} onChange={(v) => patchResult('presentation_plan.production_advice', v)} rows={3} /></div>
            </div>
        </SectionCard>
    );
}

function EvalEditor({ result, patchResult, t }) {
    const data = result.four_dimension_evaluation || {};
    return (
        <SectionCard title={t('4. 四维适配评估', '4. Four-Dimension Fit')}>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[
                    ['goal_score', t('类型', 'Goal')],
                    ['narrative_score', t('叙事', 'Narrative')],
                    ['presentation_score', t('表现', 'Form')],
                    ['platform_score', t('平台', 'Platform')],
                    ['overall_score', t('综合', 'Overall')],
                ].map(([key, label]) => (
                    <div key={key}>
                        <FieldLabel>{label}</FieldLabel>
                        <input type="number" min="0" max="100" className="w-full bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm" value={data[key] || 0} onChange={(e) => patchResult(`four_dimension_evaluation.${key}`, Number(e.target.value || 0))} />
                    </div>
                ))}
            </div>
            <TextArea value={data.score_note} onChange={(v) => patchResult('four_dimension_evaluation.score_note', v)} rows={2} />
            <TextArea value={listToLines(data.optimization_suggestions)} onChange={(v) => patchResult('four_dimension_evaluation.optimization_suggestions', linesToList(v))} rows={3} />
        </SectionCard>
    );
}

function BenchmarkEditor({ result, patchResult, t }) {
    const data = result.benchmark_analysis || {};
    return (
        <SectionCard title={t('5. 行业对标方案', '5. Benchmarks')}>
            <FieldLabel>{t('视觉资产匹配等级', 'Visual asset match')}</FieldLabel>
            <TextInput value={data.visual_asset_match_level} onChange={(v) => patchResult('benchmark_analysis.visual_asset_match_level', v)} />
            <FieldLabel>{t('对标改良方案', 'Customized improvement')}</FieldLabel>
            <TextArea value={data.customized_improvement} onChange={(v) => patchResult('benchmark_analysis.customized_improvement', v)} rows={3} />
            <JsonListEditor
                title={t('顶级标杆', 'Premium')}
                rows={data.premium_benchmarks}
                fields={['name', 'film_traits', 'borrow', 'do_not_copy']}
                onChange={(rows) => patchResult('benchmark_analysis.premium_benchmarks', rows)}
            />
            <JsonListEditor
                title={t('行业爆款', 'Viral')}
                rows={data.viral_benchmarks}
                fields={['name', 'hook_3s', 'narrative', 'shot_rules', 'copy_pattern', 'cta_position']}
                onChange={(rows) => patchResult('benchmark_analysis.viral_benchmarks', rows)}
            />
            <JsonListEditor
                title={t('避坑清单', 'Pitfalls')}
                rows={data.pitfalls}
                fields={['case', 'avoid_strategy']}
                onChange={(rows) => patchResult('benchmark_analysis.pitfalls', rows)}
            />
        </SectionCard>
    );
}

function BusinessInfoEditor({ result, patchResult, assets, t }) {
    const data = result.structured_business_info || {};
    const points = data.core_selling_points || {};
    return (
        <SectionCard title={t('6. 结构化商业信息库', '6. Structured Business Info')}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="md:col-span-2"><FieldLabel>{t('品牌简介', 'Brand Intro')}</FieldLabel><TextArea value={data.brand_intro} onChange={(v) => patchResult('structured_business_info.brand_intro', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('产品/服务', 'Product')}</FieldLabel><TextArea value={data.product_info} onChange={(v) => patchResult('structured_business_info.product_info', v)} /></div>
                <div><FieldLabel>{t('主卖点', 'Primary point')}</FieldLabel><TextInput value={points.primary} onChange={(v) => patchResult('structured_business_info.core_selling_points', { ...points, primary: v })} /></div>
                <div><FieldLabel>{t('次要卖点', 'Secondary')}</FieldLabel><TextArea value={listToLines(points.secondary)} onChange={(v) => patchResult('structured_business_info.core_selling_points', { ...points, secondary: linesToList(v) })} rows={2} /></div>
                <div><FieldLabel>{t('差异化', 'Differentiation')}</FieldLabel><TextArea value={data.differentiation} onChange={(v) => patchResult('structured_business_info.differentiation', v)} rows={2} /></div>
                <div><FieldLabel>{t('目标人群', 'Audience')}</FieldLabel><TextArea value={data.target_user} onChange={(v) => patchResult('structured_business_info.target_user', v)} rows={2} /></div>
                <div><FieldLabel>{t('痛点', 'Pain points')}</FieldLabel><TextArea value={listToLines(data.pain_points)} onChange={(v) => patchResult('structured_business_info.pain_points', linesToList(v))} rows={2} /></div>
                <div><FieldLabel>{t('竞品问题', 'Competitor gaps')}</FieldLabel><TextArea value={data.competitor_problem} onChange={(v) => patchResult('structured_business_info.competitor_problem', v)} rows={2} /></div>
                <div><FieldLabel>{t('传播目标', 'Goal')}</FieldLabel><TextInput value={data.communication_goal} onChange={(v) => patchResult('structured_business_info.communication_goal', v)} /></div>
                <div><FieldLabel>{t('建议 CTA', 'Suggested CTA')}</FieldLabel><TextInput value={data.suggested_cta} onChange={(v) => patchResult('structured_business_info.suggested_cta', v)} /></div>
            </div>
            {assets.length > 0 ? (
                <div className="flex flex-wrap gap-2 pt-2">
                    {assets.map((asset) => (
                        <div key={asset.image_id} className="w-20">
                            <img src={getFullUrl(asset.img_url)} alt={asset.object_name} className="w-20 h-16 object-cover rounded border border-white/10" />
                            <div className="text-[10px] text-white/70 truncate mt-1">{asset.object_name || asset.image_type}</div>
                        </div>
                    ))}
                </div>
            ) : null}
        </SectionCard>
    );
}

function DiagnosisEditor({ result, patchResult, t }) {
    const data = result.missing_info_diagnosis || {};
    return (
        <SectionCard title={t('7. 信息补齐诊断', '7. Missing Info Diagnosis')}>
            <JsonListEditor title={t('文本缺口', 'Text gaps')} rows={data.text_gaps} fields={['item', 'suggestion']} onChange={(rows) => patchResult('missing_info_diagnosis.text_gaps', rows)} />
            <JsonListEditor title={t('视觉缺口', 'Visual gaps')} rows={data.visual_gaps} fields={['item', 'suggestion']} onChange={(rows) => patchResult('missing_info_diagnosis.visual_gaps', rows)} />
        </SectionCard>
    );
}

function VisualEditor({ result, patchResult, t }) {
    const analysis = result.image_asset_analysis || {};
    const spec = result.visual_spec || {};
    const palette = spec.color_palette || {};
    return (
        <SectionCard title={t('8. 图片资产解析 & 成片视觉规范', '8. Image Analysis & Visual Spec')}>
            <FieldLabel>{t('全局视觉总结', 'Global visual summary')}</FieldLabel>
            <TextArea value={analysis.global_visual_summary} onChange={(v) => patchResult('image_asset_analysis.global_visual_summary', v)} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div><FieldLabel>{t('主色', 'Main color')}</FieldLabel><TextInput value={palette.main_color} onChange={(v) => patchResult('visual_spec.color_palette', { ...palette, main_color: v })} /></div>
                <div><FieldLabel>{t('点缀色', 'Accent')}</FieldLabel><TextInput value={palette.accent_color} onChange={(v) => patchResult('visual_spec.color_palette', { ...palette, accent_color: v })} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('色调描述', 'Tone')}</FieldLabel><TextInput value={palette.color_tone_description} onChange={(v) => patchResult('visual_spec.color_palette', { ...palette, color_tone_description: v })} /></div>
            </div>
            <FieldLabel>{t('光影参考', 'Lighting')}</FieldLabel>
            <TextArea value={spec.lighting_reference} onChange={(v) => patchResult('visual_spec.lighting_reference', v)} rows={2} />
            <FieldLabel>{t('构图建议', 'Composition')}</FieldLabel>
            <TextArea value={spec.composition_advice} onChange={(v) => patchResult('visual_spec.composition_advice', v)} rows={2} />
            <FieldLabel>{t('后期调色', 'Color grading')}</FieldLabel>
            <TextArea value={spec.color_grading} onChange={(v) => patchResult('visual_spec.color_grading', v)} rows={2} />
            <FieldLabel>{t('视觉统一约束', 'Unity constraints')}</FieldLabel>
            <TextArea value={listToLines(spec.unity_constraints)} onChange={(v) => patchResult('visual_spec.unity_constraints', linesToList(v))} rows={2} />
        </SectionCard>
    );
}

function MaterialEditor({ result, setResult, t }) {
    const rows = Array.isArray(result.material_list) ? result.material_list : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), material_list: next }));
    return (
        <SectionCard
            title={t('9. 素材拍摄清单', '9. Material List')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update([...rows, { name: '', category: 'scene', description: '', reference_asset_name: '', reuse_advice: '需要实拍' }])}><Plus className="w-3 h-3 inline" /> {t('添加', 'Add')}</button>}
        >
            <div className="space-y-3">
                {rows.map((row, idx) => (
                    <div key={`${row.name}-${idx}`} className="grid grid-cols-1 md:grid-cols-2 gap-2 bg-black/20 p-3 rounded-md">
                        <TextInput value={row.name} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, name: v } : item))} placeholder={t('素材名', 'Name')} />
                        <TextInput value={row.reference_asset_name} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, reference_asset_name: v } : item))} placeholder={t('引用 object_name', 'object_name')} />
                        <TextArea value={row.description} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, description: v } : item))} rows={2} />
                        <div className="space-y-2">
                            <TextInput value={row.reuse_advice} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, reuse_advice: v } : item))} placeholder={t('复用建议', 'Reuse advice')} />
                            <button type="button" className="text-xs text-red-200" onClick={() => update(rows.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
                        </div>
                    </div>
                ))}
            </div>
        </SectionCard>
    );
}

function ScriptPreviewEditor({ result, setResult, t, busy, isGeneratingScript, hasScript, onGenerateActualScript, onOpenScriptTab }) {
    const preview = result.script_preview || { logline: '', beats: [] };
    const beats = Array.isArray(preview.beats) ? preview.beats : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), script_preview: next }));
    const canGenerate = Boolean(String(preview.logline || '').trim() || beats.length);
    return (
        <SectionCard
            title={t('10. 成片脚本方向预览', '10. Script Direction')}
            extra={
                <div className="flex items-center gap-2">
                    {hasScript && typeof onOpenScriptTab === 'function' ? (
                        <button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => onOpenScriptTab()}>
                            {t('打开剧本页', 'Open script')}
                        </button>
                    ) : null}
                    {typeof onGenerateActualScript === 'function' ? (
                        <button
                            type="button"
                            className={`text-xs px-2 py-1 rounded font-bold flex items-center gap-1 ${(busy || !canGenerate) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary text-black'}`}
                            disabled={busy || !canGenerate}
                            onClick={() => onGenerateActualScript()}
                        >
                            {isGeneratingScript ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                            {hasScript ? t('重新生成实际脚本', 'Regenerate script') : t('生成实际脚本', 'Generate script')}
                        </button>
                    ) : null}
                    <button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update({ ...preview, beats: [...beats, { name: '', duration: '', shot: '', copy: '', cta: '' }] })}><Plus className="w-3 h-3 inline" /> {t('添加镜头', 'Add beat')}</button>
                </div>
            }
        >
            <p className="text-xs text-white/50">
                {t('生成实际脚本后，可在剧本页继续 AI 优化剧本、生成资产与生成分镜，流程与剧本项目相同。', 'After generating the script, continue AI script optimization, asset generation and shot generation in the Script workspace — same pipeline as a story project.')}
            </p>
            <FieldLabel>{t('一句话方向', 'Logline')}</FieldLabel>
            <TextArea value={preview.logline} onChange={(v) => update({ ...preview, logline: v })} rows={2} />
            <div className="space-y-3">
                {beats.map((beat, idx) => (
                    <div key={`${beat.name}-${idx}`} className="bg-black/20 p-3 rounded-md space-y-2">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <TextInput value={beat.name} onChange={(v) => update({ ...preview, beats: beats.map((item, i) => i === idx ? { ...item, name: v } : item) })} placeholder={t('段落名', 'Beat name')} />
                            <TextInput value={beat.duration} onChange={(v) => update({ ...preview, beats: beats.map((item, i) => i === idx ? { ...item, duration: v } : item) })} placeholder={t('时长', 'Duration')} />
                        </div>
                        <TextArea value={beat.shot} onChange={(v) => update({ ...preview, beats: beats.map((item, i) => i === idx ? { ...item, shot: v } : item) })} rows={2} placeholder={t('镜头描述，引用 object_name', 'Shot, cite object_name')} />
                        <TextArea value={beat.copy} onChange={(v) => update({ ...preview, beats: beats.map((item, i) => i === idx ? { ...item, copy: v } : item) })} rows={2} placeholder={t('文案/口播', 'Copy')} />
                        <div className="flex items-center gap-2">
                            <TextInput value={beat.cta} onChange={(v) => update({ ...preview, beats: beats.map((item, i) => i === idx ? { ...item, cta: v } : item) })} placeholder="CTA" />
                            <button type="button" className="text-xs text-red-200 shrink-0" onClick={() => update({ ...preview, beats: beats.filter((_, i) => i !== idx) })}>{t('删除', 'Delete')}</button>
                        </div>
                    </div>
                ))}
            </div>
        </SectionCard>
    );
}

function JsonListEditor({ title, rows, fields, onChange }) {
    const list = Array.isArray(rows) ? rows : [];
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground uppercase font-bold">{title}</div>
                <button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => onChange([...list, Object.fromEntries(fields.map((f) => [f, '']))])}>+ </button>
            </div>
            {list.map((row, idx) => (
                <div key={`${title}-${idx}`} className="grid grid-cols-1 gap-2 bg-black/20 p-3 rounded-md">
                    {fields.map((field) => (
                        <TextArea
                            key={field}
                            rows={2}
                            value={row?.[field] || ''}
                            onChange={(v) => onChange(list.map((item, i) => i === idx ? { ...item, [field]: v } : item))}
                            placeholder={field}
                        />
                    ))}
                    <button type="button" className="text-xs text-red-200 text-left" onClick={() => onChange(list.filter((_, i) => i !== idx))}>Delete</button>
                </div>
            ))}
        </div>
    );
}
