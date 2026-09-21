import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    AlertTriangle,
    Image as ImageIcon,
    Library,
    Loader2,
    Pencil,
    Plus,
    RefreshCw,
    Sparkles,
    Trash2,
    Upload,
    Wand2,
    X,
} from 'lucide-react';
import { getFullUrl } from '../editorHelpers';
import {
    fetchPromoBrands,
    fetchPromoCatalogAssets,
    fetchPromoEnterprises,
    fetchPromoProducts,
    analyzePromoProjectAsset,
    generateProjectPromoPlanner,
    saveProjectPromoPlannerInput,
    saveProjectPromoPlannerResult,
    uploadAsset,
} from '../../../services/api';
import { formatProviderModelEndpointError } from '../editorConfig';
import { writePromoCatalogFocus } from '../../PromoCatalogManager';

const PROMO_IMAGE_MAX_MB = 20;
const PROMO_VIDEO_MAX_MB = 80;
const PROMO_IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov';
const PROMO_IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'webp'];
const PROMO_VIDEO_EXTS = ['mp4', 'webm', 'mov'];

const PROMO_PLATFORMS = ['抖音', '小红书', 'B站', '视频号', '知乎', '快手'];
const PROMO_DURATIONS = ['15s以内', '15-30s', '30-60s', '60-90s', '1-3min', '3min以上'];
const PROMO_DURATION_DEFS = {
    '15s以内': { zh: '8–15 秒。每段 1 个主画面，口播各不超过一句。', en: '8–15s. One hero beat per stage; one short line each.' },
    '15-30s': { zh: '15–30 秒。每段 1–2 个主画面，信息点克制；镜头由编剧拆。', en: '15–30s. One or two hero beats per stage; writer breaks shots.' },
    '30-60s': { zh: '30–60 秒。每段 2–4 个主画面，价值段讲清一个效果；镜头由编剧拆。', en: '30–60s. Two to four hero beats per stage; one clear payoff. Writer breaks shots.' },
    '60-90s': { zh: '60–90 秒。信息可分层，仍只四段。', en: '60–90s. Layer information, still four stages.' },
    '1-3min': { zh: '1–3 分钟。每段可展开，禁止写成第五段故事。', en: '1–3 min. Expand stages, do not invent a fifth act.' },
    '3min以上': { zh: '3 分钟以上。价值段可再分层，阶段名仍是四段。', en: '3+ min. Value can layer, names stay four stages.' },
};
const PROMO_UNIFIED_RHYTHM = '吸睛-共鸣-价值-收口';
const PROMO_STAGE_KEYS = [
    { key: 'hook', name: '吸睛' },
    { key: 'empathy', name: '共鸣' },
    { key: 'value', name: '价值' },
    { key: 'close', name: '收口' },
];
const PROMO_GOAL_TYPES = [
    '企业品牌宣传（情绪种草）',
    '即时转化（引流获客）',
    '建立信任（权威，客户证言）',
    '产品使用与原理（产品测评，技术科普，使用指南）',
    '招商合作（招商，招聘，年会，加盟）',
];
const PROMO_NARRATIVE_MODELS = [PROMO_UNIFIED_RHYTHM];
const PROMO_PRESENTATION_FORMS = [
    '真人口播', '实景演绎', '纪实跟拍', '产品静物实拍', 'MG动画', '三维CG动画', '手绘动画',
    '屏幕录屏演示', '素材混剪', '图文轮播', '虚拟数字人口播', '航拍大场面', 'AI生成影像',
];
const PROMO_CUSTOM = '__custom__';

const LEGACY_GOAL_MAP = {
    '品牌形象片': '企业品牌宣传（情绪种草）',
    '企业形象片': '企业品牌宣传（情绪种草）',
    '公益社会责任片': '企业品牌宣传（情绪种草）',
    '思想领导力片': '企业品牌宣传（情绪种草）',
    '上市融资路演片': '企业品牌宣传（情绪种草）',
    '引流获客片': '即时转化（引流获客）',
    '即使转化': '即时转化（引流获客）',
    '即使转化（引流获客）': '即时转化（引流获客）',
    '电商带货片': '即时转化（引流获客）',
    '门店到店转化片': '即时转化（引流获客）',
    '新品发布片': '即时转化（引流获客）',
    '产品卖点片': '即时转化（引流获客）',
    '活动节点片': '即时转化（引流获客）',
    '客户案例证言片': '建立信任（权威，客户证言）',
    '售后服务口碑片': '建立信任（权威，客户证言）',
    '功能演示片': '产品使用与原理（产品测评，技术科普，使用指南）',
    '招商渠道片': '招商合作（招商，招聘，年会，加盟）',
    '招聘雇主品牌片': '招商合作（招商，招聘，年会，加盟）',
};

const normalizePromoGoalType = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (PROMO_GOAL_TYPES.includes(raw)) return raw;
    if (LEGACY_GOAL_MAP[raw]) return LEGACY_GOAL_MAP[raw];
    if (/即使转化|即时转化|引流|带货|到店|卖点/.test(raw)) return '即时转化（引流获客）';
    if (/证言|信任|权威|口碑/.test(raw)) return '建立信任（权威，客户证言）';
    if (/测评|科普|使用指南|功能演示|原理/.test(raw)) return '产品使用与原理（产品测评，技术科普，使用指南）';
    if (/招商|招聘|年会|加盟/.test(raw)) return '招商合作（招商，招聘，年会，加盟）';
    if (/品牌宣传|情绪种草|企业形象|品牌形象/.test(raw)) return '企业品牌宣传（情绪种草）';
    return raw;
};

const PROMO_GOAL_TYPE_DEFS = {
    '企业品牌宣传（情绪种草）': { zh: '建立气质、向往与记忆，不主推当场成交。前三段禁口播介绍，花字可点产品/Logo。', en: 'Build aura and memory. Early VO does not introduce the company; flower text may name product or logo.' },
    '即时转化（引流获客）': { zh: '用钩子换关注、留资、到店或下单。', en: 'Turn a hook into follow, lead, visit or order.' },
    '建立信任（权威，客户证言）': { zh: '权威背书与客户证言，降低怀疑。', en: 'Authority and testimonials to reduce doubt.' },
    '产品使用与原理（产品测评，技术科普，使用指南）': { zh: '讲清怎么用、为什么有效。', en: 'Show how it works and why it works.' },
    '招商合作（招商，招聘，年会，加盟）': { zh: '面向合作、人才、年会或加盟决策。', en: 'For partnership, hiring, annual meeting or franchise.' },
};

const PROMO_NARRATIVE_DEFS = {
    [PROMO_UNIFIED_RHYTHM]: { zh: '全片统一四段：吸睛（美感/震撼+一句话钩子）→ 共鸣（客户代入，可适当叠救猫咪式可亲动作）→ 价值（企业/品牌/产品解决方案）→ 收口（记忆点+清晰 CTA）。', en: 'Hook → empathy (with a Save-the-Cat likable beat) → value → close. Locked for every promo.' },
};

const PROMO_PRESENTATION_DEFS = {
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

const PROMO_PLATFORM_DEFS = {
    '抖音': { zh: '信息流竖屏，前3秒强钩子，15-30s优先，口播与CTA都可以硬。', en: 'Vertical feed; hook in 3s; 15–30s; strong CTA ok.' },
    '小红书': { zh: '生活方式与质感优先，钩子偏软，封面友好，CTA不要太推销。', en: 'Lifestyle and texture; softer hook and CTA; cover-first.' },
    'B站': { zh: '可更长更完整，允许讲解密度，适合原理、测评与世界观。', en: 'Longer, denser explainers and reviews.' },
    '视频号': { zh: '熟人社交与信任感，钩子清楚但不油，适合到店与留资。', en: 'Trusted social graph; clear but not oily; good for visits/leads.' },
    '知乎': { zh: '问题钩子+证据，适合功能、案例与思想领导力。', en: 'Question + evidence; good for features and thought leadership.' },
    '快手': { zh: '接地气、强结果、强CTA，少炫技，适合下沉与效果承诺。', en: 'Down-to-earth, result-first, strong CTA.' },
};
const PROMO_IMAGE_TYPES = [
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
    basic_intro: '',
    target_audience: '',
    market_and_competitors: '',
    goal_type: '',
    narrative_model: PROMO_UNIFIED_RHYTHM,
    presentation_form: '',
    platform: [],
    expect_duration: '15-30s',
    existing_material: '',
    constraint: '',
    cta: '',
    episodes_count: 1,
});

const EXISTING_MATERIAL_ANALYSIS_MARK = '【素材解析】';

const selectedAssetKeys = (assets = []) => {
    const ids = new Set();
    const urls = new Set();
    const names = new Set();
    (Array.isArray(assets) ? assets : []).forEach((item) => {
        const imageId = String(item?.image_id || '').trim();
        const url = String(item?.img_url || item?.file_url || '').trim();
        const name = String(item?.object_name || '').trim();
        if (imageId) ids.add(imageId);
        if (url) urls.add(url);
        if (name) names.add(name);
    });
    return { ids, urls, names };
};

const rowMatchesSelectedAssets = (row, keys) => {
    const imageId = String(row?.image_id || '').trim();
    const url = String(row?.img_url || row?.file_url || '').trim();
    const name = String(row?.object_name || row?.reference_name || row?.name_for_script || '').trim();
    if (imageId && keys.ids.has(imageId)) return true;
    if (url && keys.urls.has(url)) return true;
    if (name && keys.names.has(name)) return true;
    const sourceIds = Array.isArray(row?.source_image_ids)
        ? row.source_image_ids.map((value) => String(value || '').trim()).filter(Boolean)
        : [];
    return sourceIds.some((sourceId) => keys.ids.has(sourceId));
};

const filterAnalysisToSelectedAssets = (analysis, assets) => {
    const data = analysis && typeof analysis === 'object' ? { ...analysis } : {};
    if (!Array.isArray(assets)) return data;
    const keys = selectedAssetKeys(assets);
    if (!keys.ids.size && !keys.urls.size && !keys.names.size) {
        return { ...data, image_list: [], rebuild_subjects: [], global_visual_summary: '' };
    }
    const imageList = (Array.isArray(data.image_list) ? data.image_list : []).filter((row) => rowMatchesSelectedAssets(row, keys));
    const subjects = (Array.isArray(data.rebuild_subjects) ? data.rebuild_subjects : []).filter((row) => rowMatchesSelectedAssets(row, keys));
    const narrowed = imageList.length !== (Array.isArray(data.image_list) ? data.image_list.length : 0)
        || subjects.length !== (Array.isArray(data.rebuild_subjects) ? data.rebuild_subjects.length : 0);
    return {
        ...data,
        image_list: imageList,
        rebuild_subjects: subjects,
        global_visual_summary: narrowed ? '' : data.global_visual_summary,
    };
};

const materialRowKeys = (item) => {
    const keys = [];
    ['image_id', 'object_name', 'reference_name', 'name_for_script', 'img_url', 'file_url'].forEach((field) => {
        const value = String(item?.[field] || '').trim();
        if (value && !keys.includes(value)) keys.push(value);
    });
    (Array.isArray(item?.source_image_ids) ? item.source_image_ids : []).forEach((value) => {
        const text = String(value || '').trim();
        if (text && !keys.includes(text)) keys.push(text);
    });
    return keys;
};

const mergeMaterialRow = (target, source) => {
    const next = { ...target };
    Object.entries(source || {}).forEach(([key, value]) => {
        if (key === 'source_image_ids') {
            const merged = [];
            [...(Array.isArray(next.source_image_ids) ? next.source_image_ids : []), ...(Array.isArray(value) ? value : [])].forEach((item) => {
                const text = String(item || '').trim();
                if (text && !merged.includes(text)) merged.push(text);
            });
            if (merged.length) next.source_image_ids = merged;
            return;
        }
        if (String(next[key] || '').trim()) return;
        if (value !== undefined && value !== null && value !== '') next[key] = value;
    });
    return next;
};

const uniqueMaterialRows = (data, assets = []) => {
    const rows = [];
    const indexBy = new Map();
    const add = (raw) => {
        const item = raw && typeof raw === 'object' ? raw : {};
        const keys = materialRowKeys(item);
        if (!keys.length) return;
        const hit = keys.map((key) => indexBy.get(key)).find((idx) => idx !== undefined);
        if (hit !== undefined) {
            rows[hit] = mergeMaterialRow(rows[hit], item);
            keys.forEach((key) => indexBy.set(key, hit));
            return;
        }
        rows.push({ ...item });
        keys.forEach((key) => indexBy.set(key, rows.length - 1));
    };
    (Array.isArray(assets) ? assets : []).forEach(add);
    (Array.isArray(data.image_list) ? data.image_list : []).forEach(add);
    (Array.isArray(data.rebuild_subjects) ? data.rebuild_subjects : []).forEach(add);
    return rows;
};

const typeLabelOf = (value) => {
    const raw = String(value || '').trim().toLowerCase();
    if (raw === 'character' || raw === '角色') return '角色';
    if (raw === 'scene' || raw === 'environment' || raw === '场景') return '场景';
    if (raw === 'prop' || raw === '道具') return '道具';
    return '产品';
};

const formatOneMaterialLine = (item) => {
    const name = String(item?.object_name || item?.name_for_script || item?.reference_name || item?.image_id || '').trim();
    if (!name) return '';
    const imageType = String(item?.image_type || item?.asset_type || item?.kind || 'product');
    const media = String(item?.media_kind || 'image');
    const bits = [`名称=${name}｜类型=${typeLabelOf(imageType)}｜媒介=${media === 'video' ? '视频' : '图片'}`];
    const seen = new Set([name]);
    const remark = String(item?.user_remark || '').trim();
    if (remark) {
        bits.push(`说明=${remark}`);
        seen.add(remark);
    }
    const pairs = [
        ['content_desc', '内容'],
        ['rebuild_brief', '外形'],
        ['appearance', '外形'],
        ['space_layout', '空间'],
        ['environment_detail', '场景'],
        ['clothing_or_material', '材质'],
        ['scale_and_shape', '形态'],
        ['color_and_markings', '标识'],
        ['prop_detail', '道具'],
        ['character_detail', '人物'],
        ['lighting', '光色'],
        ['light_info', '光影'],
        ['video_motion', '视频动作'],
        ['motion_from_video', '视频动作'],
        ['style_desc', '风格'],
    ].filter(([key]) => typeLabelOf(imageType) !== '场景' || !['prop_detail', 'character_detail'].includes(key));
    const usedLabels = new Set();
    pairs.forEach(([key, label]) => {
        const value = String(item?.[key] || '').trim();
        if (!value || value === '无' || value === '未见' || seen.has(value) || usedLabels.has(label)) return;
        bits.push(`${label}=${value}`);
        seen.add(value);
        usedLabels.add(label);
    });
    return bits.join('；');
};

const formatExistingMaterialFromAnalysis = (analysis, assets = []) => {
    const data = filterAnalysisToSelectedAssets(analysis, Array.isArray(assets) ? assets : []);
    const lines = [];
    const summary = String(data.global_visual_summary || '').trim();
    if (summary) lines.push(`综合视觉=${summary}`);
    uniqueMaterialRows(data, Array.isArray(assets) ? assets : []).forEach((item) => {
        const line = formatOneMaterialLine(item);
        if (line) lines.push(`- ${line}`);
    });
    return lines.join('\n').trim();
};

const existingMaterialUserNotes = (current) => {
    const currentText = String(current || '');
    if (!currentText.includes(EXISTING_MATERIAL_ANALYSIS_MARK)) return currentText.trim();
    return currentText.split(EXISTING_MATERIAL_ANALYSIS_MARK)[0].trim();
};

const mergeExistingMaterialWithAnalysis = (current, analysis, assets = []) => {
    const generated = formatExistingMaterialFromAnalysis(analysis, assets);
    const prefix = existingMaterialUserNotes(current);
    if (!generated) return prefix;
    const block = `${EXISTING_MATERIAL_ANALYSIS_MARK}\n${generated}`;
    return prefix ? `${prefix}\n\n${block}` : block;
};

const analysisSignature = (analysis) => {
    if (!analysis || typeof analysis !== 'object') return '';
    try {
        return JSON.stringify({
            summary: analysis.global_visual_summary || '',
            subjects: analysis.rebuild_subjects || [],
            list: analysis.image_list || [],
        });
    } catch {
        return '';
    }
};

const ANALYSIS_STATUS_PENDING = 'pending';
const ANALYSIS_STATUS_SUCCESS = 'success';
const ANALYSIS_STATUS_FAILED = 'failed';
const ANALYSIS_STATUS_ANALYZING = 'analyzing';

const normalizeAnalysisStatus = (value, fallback = ANALYSIS_STATUS_PENDING) => {
    const raw = String(value || '').trim().toLowerCase();
    if (raw === ANALYSIS_STATUS_SUCCESS || raw === 'ok' || raw === 'done') return ANALYSIS_STATUS_SUCCESS;
    if (raw === ANALYSIS_STATUS_FAILED || raw === 'error' || raw === 'fail') return ANALYSIS_STATUS_FAILED;
    if (raw === ANALYSIS_STATUS_ANALYZING || raw === 'running') return ANALYSIS_STATUS_ANALYZING;
    if (raw === ANALYSIS_STATUS_PENDING || raw === 'unparsed' || raw === '未解析') return ANALYSIS_STATUS_PENDING;
    return fallback;
};

const analysisRowForAsset = (analysis, asset) => {
    const imageId = String(asset?.image_id || '').trim();
    const list = Array.isArray(analysis?.image_list) ? analysis.image_list : [];
    return list.find((row) => String(row?.image_id || '').trim() === imageId) || null;
};

const deriveAssetAnalysisStatus = (asset, analysis) => {
    const direct = normalizeAnalysisStatus(asset?.analysis_status, '');
    if (direct === ANALYSIS_STATUS_ANALYZING) return { status: ANALYSIS_STATUS_ANALYZING, error: '' };
    const row = analysisRowForAsset(analysis, asset);
    const rowStatus = normalizeAnalysisStatus(row?.analysis_status, '');
    if (direct === ANALYSIS_STATUS_SUCCESS || rowStatus === ANALYSIS_STATUS_SUCCESS) {
        return { status: ANALYSIS_STATUS_SUCCESS, error: '' };
    }
    const error = String(asset?.analysis_error || row?.analysis_error || '').trim();
    if (direct === ANALYSIS_STATUS_FAILED || rowStatus === ANALYSIS_STATUS_FAILED || error) {
        const desc = String(row?.content_desc || '').trim();
        return { status: ANALYSIS_STATUS_FAILED, error: error || desc };
    }
    return { status: ANALYSIS_STATUS_PENDING, error: '' };
};

const serializeAssetForApi = (item) => ({
    image_id: item.image_id,
    img_url: item.img_url,
    image_type: item.image_type,
    media_kind: item.media_kind || 'image',
    object_name: item.object_name,
    user_remark: item.user_remark,
    owner_kind: item.owner_kind || 'project',
    owner_entity_id: item.owner_entity_id || null,
    catalog_asset_id: item.catalog_asset_id || null,
    analysis_status: item.analysis_status || ANALYSIS_STATUS_PENDING,
    analysis_error: item.analysis_error || '',
});

const assetIdentityKey = (item) => {
    const catalogId = item?.catalog_asset_id || (item?.owner_kind && item.owner_kind !== 'project' ? item.id : '');
    const imageId = String(item?.image_id || '').trim();
    const url = String(item?.img_url || item?.file_url || '').trim();
    return String(catalogId || imageId || url);
};

const toPlannerAsset = (item, analysis) => {
    const derived = deriveAssetAnalysisStatus(item, analysis);
    const url = item.img_url || item.file_url || '';
    return {
        image_id: item.image_id || newImageId(),
        img_url: url,
        image_type: item.image_type || item.asset_type || 'product',
        media_kind: item.media_kind || 'image',
        object_name: item.object_name || '',
        user_remark: item.user_remark || '',
        preview_url: url,
        upload_status: url ? 'ready' : 'failed',
        analysis_status: derived.status,
        analysis_error: derived.error,
        owner_kind: item.owner_kind || 'project',
        owner_entity_id: item.owner_entity_id || null,
        catalog_asset_id: item.catalog_asset_id || (item.owner_kind && item.owner_kind !== 'project' ? item.id : null),
        image_asset_analysis: item.image_asset_analysis || analysis || null,
    };
};

const catalogOwnerLabel = (kind, t) => {
    if (kind === 'enterprise') return t('企业素材', 'Enterprise');
    if (kind === 'brand') return t('品牌素材', 'Brand');
    if (kind === 'offering') return t('产品素材', 'Offering');
    return t('本片上传', 'This film');
};

const catalogStillValid = (item, enterpriseId, brandId, productId) => {
    const kind = item.owner_kind || 'project';
    if (kind === 'project') return true;
    if (kind === 'enterprise') return String(item.owner_entity_id || '') === String(enterpriseId || '');
    if (kind === 'brand') return String(item.owner_entity_id || '') === String(brandId || '');
    if (kind === 'offering') return String(item.owner_entity_id || '') === String(productId || '');
    return false;
};

const analysisStatusLabel = (status, t) => {
    if (status === ANALYSIS_STATUS_SUCCESS) return t('成功', 'Success');
    if (status === ANALYSIS_STATUS_FAILED) return t('失败', 'Failed');
    if (status === ANALYSIS_STATUS_ANALYZING) return t('解析中', 'Analyzing');
    return t('未解析', 'Unparsed');
};

const analysisStatusClass = (status) => {
    if (status === ANALYSIS_STATUS_SUCCESS) return 'bg-emerald-500/20 text-emerald-200';
    if (status === ANALYSIS_STATUS_FAILED) return 'bg-red-500/20 text-red-200';
    if (status === ANALYSIS_STATUS_ANALYZING) return 'bg-sky-500/20 text-sky-100';
    return 'bg-white/10 text-white/70';
};

const emptyFlowerTextSpec = () => ({
    font: '',
    weight: '',
    body_size: '中',
    emphasis_size: '大',
    color: '',
    accent_color: '',
    stroke: '',
    body_position: '画面中部',
    emphasis_position: '画面中部',
    align: '居中',
    max_line_chars: '12',
    mid_display: '中部必须艺术化组合设计，不限于印章/古体/英文小字/颜色',
    cut_fusion: '优先段末切镜或段首开镜，不与动作抢镜；可黑屏专镜或字卡专镜；有旁白则无花字',
    cta_hold: 'CTA可较长停留',
    vo_xor: '有旁白时不出花字，花字低于旁白，禁同步以免分心',
    glyph_lock: '引号内逐字成形；含「X家」须见家，禁漏家、禁复写邻字、禁何乐乐享；店号/热线不进难认印章',
    seal_clear: '印=句外旁侧｜压字=禁｜替字=禁｜字印留空，禁止印面盖住任一花字',
    card_shot: '店号/品牌/热线走字卡专镜：企业场景底+字层先合成一张静帧，本镜Static Hold按静帧原样上屏；禁手写；禁双参考图分喂；字卡不是CHAR/PROP/ENV',
    unity: '全片同套字形与字色字重；禁底部避字幕；每段最多一条花字；一个动作最多一条；有旁白时不出花字，花字低于旁白，禁同步；优先段末/段首切镜或黑屏专镜，不与动作抢镜；CTA可较长停留；中部必须艺术化组合（不限于印章/古体/英文小字/颜色），只改字级、落位与艺术手段',
    spec_line: '',
});

const emptyStageBlock = (name) => ({
    name,
    duration: '',
    sensory: '',
    content: '',
    copy: '',
    flower_text: '',
    cta: '',
    technique_assoc: '',
});

const emptyStagePlan = () => Object.fromEntries(PROMO_STAGE_KEYS.map(({ key, name }) => [key, emptyStageBlock(name)]));

const dropStageShots = (row, name) => {
    const next = { ...(row || emptyStageBlock(name)) };
    delete next.shots;
    return next;
};

const syncStagePlanToPreview = (result) => {
    const next = result && typeof result === 'object' ? result : emptyPromoPlannerResult();
    const plan = next.stage_plan && typeof next.stage_plan === 'object' ? next.stage_plan : emptyStagePlan();
    next.stage_plan = Object.fromEntries(PROMO_STAGE_KEYS.map(({ key, name }) => [key, dropStageShots(plan[key], name)]));
    const beats = PROMO_STAGE_KEYS.map(({ key, name }) => {
        const row = next.stage_plan[key] || emptyStageBlock(name);
        return {
            name: row.name || name,
            duration: row.duration || '',
            shot: row.sensory || '',
            copy: row.copy || '',
            flower_text: row.flower_text || '',
            cta: row.cta || '',
            technique: row.technique_assoc || '',
        };
    });
    const preview = next.script_preview && typeof next.script_preview === 'object' ? next.script_preview : { logline: '', beats: [] };
    next.script_preview = {
        ...preview,
        logline: preview.logline || next.overall_scheme?.one_liner || '',
        beats,
    };
    return next;
};

const emptyVisualBackfill = () => ({
    Global_Style: '',
    style_mode: '',
    style_inheritance: '',
    borrowed_films: [],
    borrowed_films_note: '',
    borrowed_films_scene_refs: [],
    tone: '',
    lighting: '',
    color_palette: '',
    color_spectrum: '',
    plot_summary: '',
    comprehensive_plot: '',
    comprehensive_assets: '',
    music_recommendation: '',
    voiceover_style: '',
    sfx_style: '',
    flower_text_spec: emptyFlowerTextSpec(),
});

const emptyColorPalette = () => ({
    main_color: '',
    secondary_colors: [],
    accent_color: '',
    color_tone_description: '',
});

const emptyPromoPlannerResult = () => ({
    overall_scheme: {
        title: '',
        one_liner: '',
        combination_mode: '',
        main_goal_type: '',
        target_duration: '',
        duration_budget: '',
        series_logic: '',
        success_metric: '',
        promo_focus: '',
        selling_points: '',
        visual_core: '',
    },
    characteristic_analysis: {
        enterprise: '',
        brand: '',
        product: '',
        audience_insight: '',
    },
    benchmark_films: [],
    stage_plan: emptyStagePlan(),
    project_visual_backfill: emptyVisualBackfill(),
    supplement_suggestions: [],
    content_mode: {
        primary_mode: PROMO_UNIFIED_RHYTHM,
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
        rebuild_subjects: [],
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

const migrateLegacyPromoInput = (legacy = {}) => {
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
            basic_intro: src.campaign_objective || '',
            target_audience: src.target_audience || '',
            market_and_competitors: src.competitor_problem || '',
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

const detectMediaKind = (file) => {
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    const type = String(file?.type || '').toLowerCase();
    if (PROMO_VIDEO_EXTS.includes(ext) || type.startsWith('video/')) return 'video';
    return 'image';
};

const isAcceptedImage = (file) => {
    const kind = detectMediaKind(file);
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    const type = String(file?.type || '').toLowerCase();
    if (kind === 'video') {
        return PROMO_VIDEO_EXTS.includes(ext) || type.startsWith('video/');
    }
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

const serializePlannerResult = (value) => {
    try {
        return JSON.stringify(value || {});
    } catch {
        return '';
    }
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
    const [catalogAssets, setCatalogAssets] = useState([]);
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
    const lastSavedResultRef = useRef('');
    const resultSaveEpochRef = useRef(0);
    const resultSaveInFlightRef = useRef(null);
    const inputSaveEpochRef = useRef(0);
    const inputSaveInFlightRef = useRef(null);
    const lastMaterialAnalysisRef = useRef('');
    const generatingRef = useRef(false);
    const setInfoRef = useRef(setInfo);
    const resultRef = useRef(result);
    const assetsRef = useRef(assets);
    useEffect(() => {
        assetsRef.current = assets;
    }, [assets]);
    useEffect(() => {
        resultRef.current = result;
    }, [result]);
    useEffect(() => {
        setInfoRef.current = setInfo;
    }, [setInfo]);
    useEffect(() => {
        hydratedRef.current = false;
        lastSavedResultRef.current = '';
        lastMaterialAnalysisRef.current = '';
        resultSaveEpochRef.current += 1;
        inputSaveEpochRef.current += 1;
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
            goal_type: normalizePromoGoalType(saved.campaign_demand?.goal_type),
            basic_intro: saved.campaign_demand?.basic_intro || saved.campaign_demand?.user_raw_text || '',
            target_audience: saved.campaign_demand?.target_audience || saved.enterprise_info?.target_user || '',
            market_and_competitors: saved.campaign_demand?.market_and_competitors || saved.enterprise_info?.competitor_problem || '',
            expect_duration: saved.campaign_demand?.expect_duration || '15-30s',
            narrative_model: PROMO_UNIFIED_RHYTHM,
            platform: Array.isArray(saved.campaign_demand?.platform)
                ? saved.campaign_demand.platform
                : String(saved.campaign_demand?.platform || '')
                    .split(/[\/,、\s]+/)
                    .map((s) => s.trim())
                    .filter((s) => PROMO_PLATFORMS.includes(s)),
        };
        const hydratedResult = gi.promo_planner_result && typeof gi.promo_planner_result === 'object' ? gi.promo_planner_result : null;
        nextCampaign.existing_material = mergeExistingMaterialWithAnalysis(
            hydratedResult?.existing_material || nextCampaign.existing_material,
            hydratedResult?.image_asset_analysis,
            saved.enterprise_info?.image_assets,
        ) || nextCampaign.existing_material;
        const rawAssets = Array.isArray(saved.enterprise_info?.image_assets) ? saved.enterprise_info.image_assets : [];
        const analysis = hydratedResult?.image_asset_analysis;
        setEnterprise(nextEnterprise);
        setCampaign(nextCampaign);
        setAssets(rawAssets.map((item) => toPlannerAsset(item, analysis)));
        if (gi.promo_planner_result && typeof gi.promo_planner_result === 'object') {
            const nextResult = deepMerge(emptyPromoPlannerResult(), gi.promo_planner_result);
            lastSavedResultRef.current = serializePlannerResult(nextResult);
            lastMaterialAnalysisRef.current = analysisSignature(nextResult.image_asset_analysis);
            setResult(nextResult);
        } else {
            lastSavedResultRef.current = '';
            lastMaterialAnalysisRef.current = '';
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

    const loadSubjectAssets = useCallback(async (enterpriseId = selectedEnterpriseId, brandId = selectedBrandId, productId = selectedProductId) => {
        if (!enterpriseId && !brandId && !productId) {
            setCatalogAssets([]);
            return;
        }
        try {
            const requests = [];
            if (enterpriseId) requests.push(fetchPromoCatalogAssets({ owner_kind: 'enterprise', owner_entity_id: Number(enterpriseId) }));
            if (brandId) requests.push(fetchPromoCatalogAssets({ owner_kind: 'brand', owner_entity_id: Number(brandId) }));
            if (productId) requests.push(fetchPromoCatalogAssets({ owner_kind: 'offering', owner_entity_id: Number(productId) }));
            const parts = await Promise.all(requests.map((item) => item.catch(() => [])));
            const seen = new Set();
            const rows = [];
            parts.flat().forEach((item) => {
                const key = assetIdentityKey(item);
                if (!key || seen.has(key)) return;
                seen.add(key);
                rows.push(item);
            });
            setCatalogAssets(rows);
        } catch (err) {
            console.error('[PromoPlanner] subject assets load failed', err);
            setCatalogAssets([]);
        }
    }, [selectedBrandId, selectedEnterpriseId, selectedProductId]);

    useEffect(() => {
        loadSubjectAssets();
    }, [loadSubjectAssets]);

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
        setAssets((prev) => prev.filter((item) => catalogStillValid(item, enterpriseId, nextBrand?.id, nextProduct?.id)));
        loadSubjectAssets(enterpriseId, nextBrand?.id, nextProduct?.id);
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
        setAssets((prev) => prev.filter((item) => catalogStillValid(item, row?.enterprise_id || selectedEnterpriseId, row?.id, nextProduct?.id)));
        loadSubjectAssets(row?.enterprise_id || selectedEnterpriseId, row?.id, nextProduct?.id);
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
        setAssets((prev) => prev.filter((item) => catalogStillValid(item, row?.enterprise_id || selectedEnterpriseId, row?.brand_id || selectedBrandId, row?.id)));
        loadSubjectAssets(row?.enterprise_id || selectedEnterpriseId, row?.brand_id || selectedBrandId, row?.id);
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
    const catalogIsSelected = useCallback((item) => {
        const key = assetIdentityKey(item);
        const url = String(item.img_url || item.file_url || '').trim();
        return assets.some((asset) => {
            const assetKey = assetIdentityKey(asset);
            const assetUrl = String(asset.img_url || '').trim();
            return (key && assetKey && key === assetKey) || (url && assetUrl && url === assetUrl);
        });
    }, [assets]);

    const buildInputPayload = useCallback(() => ({
        enterprise_id: Number(selectedEnterpriseId) || null,
        brand_id: Number(selectedBrandId) || null,
        product_id: Number(selectedProductId) || null,
        enterprise_info: {
            ...enterprise,
            core_selling_points: Array.isArray(enterprise.core_selling_points) ? enterprise.core_selling_points : linesToList(enterprise.core_selling_points),
            pain_points: Array.isArray(enterprise.pain_points) ? enterprise.pain_points : linesToList(enterprise.pain_points),
            image_assets: readyAssets.map((item) => serializeAssetForApi(item)),
        },
        campaign_demand: {
            ...campaign,
            goal_type: normalizePromoGoalType(campaign.goal_type),
            basic_intro: String(campaign.basic_intro || campaign.user_raw_text || '').trim(),
            user_raw_text: String(campaign.basic_intro || campaign.user_raw_text || '').trim(),
            target_audience: String(campaign.target_audience || '').trim(),
            market_and_competitors: String(campaign.market_and_competitors || '').trim(),
            expect_duration: campaign.expect_duration === PROMO_CUSTOM ? '' : String(campaign.expect_duration || '').trim(),
            narrative_model: PROMO_UNIFIED_RHYTHM,
            presentation_form: campaign.presentation_form === PROMO_CUSTOM ? '' : String(campaign.presentation_form || '').trim(),
            platform: campaign.platform,
            episodes_count: Number(campaign.episodes_count || 1) || 1,
        },
    }), [assets, campaign, enterprise, readyAssets, selectedBrandId, selectedEnterpriseId, selectedProductId]);

    useEffect(() => {
        onEpisodesCountChange?.(Number(campaign.episodes_count || 1) || 1);
    }, [campaign.episodes_count, onEpisodesCountChange]);

    useEffect(() => {
        if (!hydratedRef.current) return;
        const analysis = result?.image_asset_analysis;
        setCampaign((prev) => {
            const filled = mergeExistingMaterialWithAnalysis(prev.existing_material, analysis, assets) || '';
            if (filled === (prev.existing_material || '')) return prev;
            return { ...prev, existing_material: filled };
        });
    }, [result, assets]);

    useEffect(() => {
        if (!projectId || !hydratedRef.current) return;
        if (skipInputSaveRef.current) {
            skipInputSaveRef.current = false;
            return;
        }
        if (isGenerating || generatingRef.current) return;
        if (inputTimerRef.current) clearTimeout(inputTimerRef.current);
        const epoch = inputSaveEpochRef.current;
        inputTimerRef.current = setTimeout(async () => {
            if (epoch !== inputSaveEpochRef.current || generatingRef.current) return;
            try {
                const payload = buildInputPayload();
                if (!String(payload.campaign_demand?.existing_material || '').trim()) {
                    const filled = mergeExistingMaterialWithAnalysis(
                        '',
                        result?.image_asset_analysis,
                        payload.enterprise_info?.image_assets,
                    );
                    if (filled) payload.campaign_demand.existing_material = filled;
                }
                const pending = saveProjectPromoPlannerInput(projectId, payload);
                inputSaveInFlightRef.current = pending;
                const updated = await pending;
                if (epoch !== inputSaveEpochRef.current) return;
                const gi = pickPlannerState(updated);
                setInfo?.((prev) => ({
                    ...prev,
                    ...gi,
                    promo_planner_input: gi.promo_planner_input || payload,
                }));
            } catch (err) {
                console.error('[PromoPlanner] input autosave failed', err);
            } finally {
                if (inputSaveInFlightRef.current && epoch === inputSaveEpochRef.current) {
                    inputSaveInFlightRef.current = null;
                }
            }
        }, 900);
        return () => {
            if (inputTimerRef.current) clearTimeout(inputTimerRef.current);
        };
    }, [buildInputPayload, isGenerating, projectId, result?.image_asset_analysis]);

    useEffect(() => {
        if (!projectId || !result || !hydratedRef.current) return;
        const serialized = serializePlannerResult(result);
        if (skipResultSaveRef.current) {
            skipResultSaveRef.current = false;
            lastSavedResultRef.current = serialized;
            return;
        }
        if (isGenerating) return;
        if (serialized && serialized === lastSavedResultRef.current) return;
        if (resultTimerRef.current) clearTimeout(resultTimerRef.current);
        const epoch = resultSaveEpochRef.current;
        resultTimerRef.current = setTimeout(async () => {
            if (epoch !== resultSaveEpochRef.current) return;
            const latest = serializePlannerResult(result);
            if (latest && latest === lastSavedResultRef.current) return;
            const pending = saveProjectPromoPlannerResult(projectId, { promo_planner_result: result });
            resultSaveInFlightRef.current = pending;
            try {
                const updated = await pending;
                if (epoch !== resultSaveEpochRef.current) return;
                lastSavedResultRef.current = latest;
                const gi = pickPlannerState(updated);
                setInfoRef.current?.((prev) => ({
                    ...prev,
                    ...gi,
                    promo_planner_result: gi.promo_planner_result || result,
                    promo_dna_global_md: gi.promo_dna_global_md || prev.promo_dna_global_md,
                }));
            } catch (err) {
                console.error('[PromoPlanner] result autosave failed', err);
            } finally {
                if (resultSaveInFlightRef.current === pending) {
                    resultSaveInFlightRef.current = null;
                }
            }
        }, 1200);
        return () => {
            if (resultTimerRef.current) clearTimeout(resultTimerRef.current);
        };
    }, [isGenerating, projectId, result]);

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
            if (path.startsWith('stage_plan.') || path === 'overall_scheme.one_liner') {
                return syncStagePlanToPreview(next);
            }
            return next;
        });
    };

    const analyzeOne = async (imageId) => {
        if (!projectId || !imageId) return;
        const current = (assetsRef.current || []).find((item) => item.image_id === imageId);
        if (!current || current.upload_status !== 'ready' || !current.img_url) return;
        if (current.analysis_status === ANALYSIS_STATUS_ANALYZING) return;
        setAssets((prev) => prev.map((item) => (
            item.image_id === imageId
                ? { ...item, analysis_status: ANALYSIS_STATUS_ANALYZING, analysis_error: '' }
                : item
        )));
        try {
            const data = await analyzePromoProjectAsset(projectId, {
                asset: serializeAssetForApi({ ...current, analysis_status: ANALYSIS_STATUS_ANALYZING }),
                enterprise_id: Number(selectedEnterpriseId) || null,
                brand_id: Number(selectedBrandId) || null,
                product_id: Number(selectedProductId) || null,
                image_asset_analysis: resultRef.current?.image_asset_analysis,
            });
            const nextAnalysis = data?.image_asset_analysis;
            const status = normalizeAnalysisStatus(data?.analysis_status, ANALYSIS_STATUS_FAILED);
            const error = String(data?.analysis_error || '').trim();
            setAssets((prev) => prev.map((item) => (
                item.image_id === imageId
                    ? { ...item, analysis_status: status, analysis_error: error }
                    : item
            )));
            if (nextAnalysis && typeof nextAnalysis === 'object') {
                skipResultSaveRef.current = true;
                setResult((prev) => {
                    const next = deepMerge(emptyPromoPlannerResult(), prev || {});
                    next.image_asset_analysis = nextAnalysis;
                    return next;
                });
                lastMaterialAnalysisRef.current = analysisSignature(nextAnalysis);
                setCampaign((prev) => ({
                    ...prev,
                    existing_material: mergeExistingMaterialWithAnalysis(
                        prev.existing_material,
                        nextAnalysis,
                        assetsRef.current,
                    ) || prev.existing_material,
                }));
            }
            if (data?.project) {
                const gi = pickPlannerState(data.project);
                setInfo?.((prev) => ({
                    ...prev,
                    ...gi,
                    promo_planner_input: gi.promo_planner_input || prev?.promo_planner_input,
                    promo_planner_result: gi.promo_planner_result || prev?.promo_planner_result,
                }));
            }
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || t('解析失败', 'Analysis failed');
            setAssets((prev) => prev.map((item) => (
                item.image_id === imageId
                    ? { ...item, analysis_status: ANALYSIS_STATUS_FAILED, analysis_error: String(message) }
                    : item
            )));
        }
    };

    const analyzePendingAssets = async () => {
        const targets = (assetsRef.current || []).filter((item) => (
            item.upload_status === 'ready'
            && item.img_url
            && item.analysis_status !== ANALYSIS_STATUS_SUCCESS
            && item.analysis_status !== ANALYSIS_STATUS_ANALYZING
        ));
        await Promise.all(targets.map((item) => analyzeOne(item.image_id)));
    };

    const uploadOne = async (file, existingId = null) => {
        const imageId = existingId || newImageId();
        const preview = URL.createObjectURL(file);
        const mediaKind = detectMediaKind(file);
        const draft = {
            image_id: imageId,
            img_url: '',
            image_type: 'product',
            media_kind: mediaKind,
            object_name: file.name.replace(/\.[^.]+$/, ''),
            user_remark: '',
            owner_kind: 'project',
            owner_entity_id: selectedEnterpriseId ? Number(selectedEnterpriseId) : null,
            preview_url: preview,
            upload_status: 'uploading',
            analysis_status: ANALYSIS_STATUS_PENDING,
            analysis_error: '',
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
                throw new Error(t('仅支持 jpg / png / webp / mp4 / webm / mov', 'Only jpg / png / webp / mp4 / webm / mov'));
            }
            const maxMb = mediaKind === 'video' ? PROMO_VIDEO_MAX_MB : PROMO_IMAGE_MAX_MB;
            if (file.size > maxMb * 1024 * 1024) {
                throw new Error(t(`单个文件不超过 ${maxMb}MB`, `Max ${maxMb}MB per file`));
            }
            const uploaded = await uploadAsset(file, {
                project_id: String(projectId || ''),
                type: mediaKind === 'video' ? 'video' : 'image',
                asset_type: 'promo_image_asset',
                remark: `promo_asset:${imageId}`,
            });
            const url = String(uploaded?.url || '').trim();
            if (!url) throw new Error(t('上传成功但未返回地址', 'Upload succeeded but no URL returned'));
            const readyItem = {
                image_id: imageId,
                img_url: url,
                preview_url: url,
                upload_status: 'ready',
                upload_error: '',
                analysis_status: ANALYSIS_STATUS_PENDING,
                analysis_error: '',
                owner_kind: 'project',
                owner_entity_id: selectedEnterpriseId ? Number(selectedEnterpriseId) : null,
            };
            let nextAssets = [];
            setAssets((prev) => {
                nextAssets = prev.map((item) => (item.image_id === imageId ? { ...item, ...readyItem } : item));
                assetsRef.current = nextAssets;
                return nextAssets;
            });
            if (selectedEnterpriseId && projectId) {
                const latestReady = nextAssets.filter((item) => item.upload_status === 'ready' && item.img_url);
                try {
                    await saveProjectPromoPlannerInput(projectId, {
                        ...buildInputPayload(),
                        enterprise_info: {
                            ...buildInputPayload().enterprise_info,
                            image_assets: latestReady.map((item) => serializeAssetForApi(item)),
                        },
                    });
                    loadSubjectAssets(selectedEnterpriseId, selectedBrandId, selectedProductId);
                } catch (shareErr) {
                    console.error('[PromoPlanner] share upload to enterprise failed', shareErr);
                }
            }
            analyzeOne(imageId);
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

    const addCatalogAsset = (row) => {
        const catalogAnalysis = row.image_asset_analysis || row.extra_info?.image_asset_analysis || null;
        const next = toPlannerAsset({
            ...row,
            owner_kind: row.owner_kind || 'enterprise',
            owner_entity_id: row.owner_entity_id,
            catalog_asset_id: row.id || row.catalog_asset_id,
            img_url: row.img_url || row.file_url,
            image_asset_analysis: catalogAnalysis,
        }, catalogAnalysis);
        setAssets((prev) => {
            if (prev.some((item) => assetIdentityKey(item) === assetIdentityKey(next) || (item.img_url && item.img_url === next.img_url))) {
                return prev;
            }
            const merged = [...prev, next];
            assetsRef.current = merged;
            return merged;
        });
        if (catalogAnalysis && next.analysis_status === ANALYSIS_STATUS_SUCCESS) {
            skipResultSaveRef.current = true;
            setResult((prev) => {
                const current = deepMerge(emptyPromoPlannerResult(), prev || {});
                current.image_asset_analysis = deepMerge(current.image_asset_analysis || {}, catalogAnalysis);
                return current;
            });
            return;
        }
        if (next.image_id) analyzeOne(next.image_id);
    };

    const toggleCatalogAsset = (row) => {
        if (catalogIsSelected(row)) {
            const key = assetIdentityKey(row);
            const url = String(row.img_url || row.file_url || '').trim();
            setAssets((prev) => {
                const next = prev.filter((item) => {
                    const itemKey = assetIdentityKey(item);
                    const itemUrl = String(item.img_url || '').trim();
                    if (key && itemKey && key === itemKey) return false;
                    if (url && itemUrl && url === itemUrl) return false;
                    return true;
                });
                assetsRef.current = next;
                return next;
            });
            return;
        }
        addCatalogAsset(row);
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

    const waitForAnalyses = async () => {
        const started = Date.now();
        while (Date.now() - started < 120000) {
            const pending = (assetsRef.current || []).some((item) => item.analysis_status === ANALYSIS_STATUS_ANALYZING);
            if (!pending) return;
            await new Promise((resolve) => setTimeout(resolve, 300));
        }
    };

    const handleGenerate = async () => {
        if (isGenerating) return;
        const resolvedGoal = normalizePromoGoalType(campaign.goal_type);
        if (!resolvedGoal || !PROMO_GOAL_TYPES.includes(resolvedGoal)) {
            alert(t('请先选择核心诉求（必填）', 'Please select a core appeal first (required).'));
            return;
        }
        const resolvedDuration = campaign.expect_duration === PROMO_CUSTOM ? '' : String(campaign.expect_duration || '').trim();
        if (!resolvedDuration) {
            alert(t('请先选择预期时长（必填）', 'Please select an expected duration first (required).'));
            return;
        }
        if (!selectedEnterpriseId && !String(enterprise.enterprise_name || '').trim()) {
            alert(t('请先选定企业', 'Please select an enterprise first.'));
            return;
        }
        generatingRef.current = true;
        setIsGenerating(true);
        resultSaveEpochRef.current += 1;
        inputSaveEpochRef.current += 1;
        if (resultTimerRef.current) {
            clearTimeout(resultTimerRef.current);
            resultTimerRef.current = null;
        }
        if (inputTimerRef.current) {
            clearTimeout(inputTimerRef.current);
            inputTimerRef.current = null;
        }
        if (resultSaveInFlightRef.current) {
            try {
                await resultSaveInFlightRef.current;
            } catch (_) {
                // Ignore a superseded autosave; generate writes the authoritative result.
            }
        }
        if (inputSaveInFlightRef.current) {
            try {
                await inputSaveInFlightRef.current;
            } catch (_) {
                // Ignore a superseded input autosave; generate rewrites material analysis.
            }
        }
        try {
            await waitForUploads();
            await waitForAnalyses();
            const latestReady = (assetsRef.current || []).filter((item) => item.upload_status === 'ready' && item.img_url);
            const payload = {
                ...buildInputPayload(),
                enterprise_info: {
                    ...buildInputPayload().enterprise_info,
                    image_assets: latestReady.map((item) => serializeAssetForApi(item)),
                },
                campaign_demand: {
                    ...buildInputPayload().campaign_demand,
                    goal_type: resolvedGoal,
                    expect_duration: resolvedDuration,
                    narrative_model: PROMO_UNIFIED_RHYTHM,
                    existing_material: existingMaterialUserNotes(campaign.existing_material),
                },
                image_asset_analysis: resultRef.current?.image_asset_analysis || result?.image_asset_analysis || null,
                force_reanalyze: false,
            };
            const hasText = [
                payload.enterprise_info.enterprise_name,
                payload.enterprise_info.enterprise_intro,
                payload.enterprise_info.brand_name,
                payload.enterprise_info.brand_intro,
                payload.enterprise_info.product_name,
                payload.enterprise_info.product_info,
                payload.campaign_demand.basic_intro,
                payload.campaign_demand.user_raw_text,
            ].some((item) => String(item || '').trim());
            if (!hasText) {
                alert(t('请先选定企业并填写介绍信息', 'Select an enterprise and fill the intro first.'));
                return;
            }
            const updated = await generateProjectPromoPlanner(projectId, buildScriptAnalysisApiPayload ? buildScriptAnalysisApiPayload(payload) : payload);
            setProject?.(updated);
            const gi = pickPlannerState(updated);
            skipNextAutosaveRef && (skipNextAutosaveRef.current = true);
            skipResultSaveRef.current = true;
            skipInputSaveRef.current = true;
            const nextResult = gi.promo_planner_result
                ? deepMerge(emptyPromoPlannerResult(), gi.promo_planner_result)
                : null;
            if (nextResult) {
                lastSavedResultRef.current = serializePlannerResult(nextResult);
                setResult(nextResult);
            }
            const nextCampaign = gi.promo_planner_input?.campaign_demand;
            const analysis = nextResult?.image_asset_analysis || (gi.promo_planner_result || {}).image_asset_analysis;
            lastMaterialAnalysisRef.current = analysisSignature(analysis);
            const filledMaterial = mergeExistingMaterialWithAnalysis(
                existingMaterialUserNotes(
                    (gi.promo_planner_result || {}).existing_material
                        || nextCampaign?.existing_material
                        || campaign.existing_material,
                ),
                analysis,
                latestReady,
            ) || existingMaterialUserNotes(campaign.existing_material);
            if (nextCampaign && typeof nextCampaign === 'object') {
                setCampaign((prev) => ({
                    ...emptyCampaign(),
                    ...prev,
                    ...nextCampaign,
                    goal_type: normalizePromoGoalType(nextCampaign.goal_type || prev.goal_type),
                    basic_intro: nextCampaign.basic_intro || nextCampaign.user_raw_text || prev.basic_intro,
                    narrative_model: PROMO_UNIFIED_RHYTHM,
                    platform: Array.isArray(nextCampaign.platform) ? nextCampaign.platform : (prev.platform || []),
                    existing_material: filledMaterial || nextCampaign.existing_material || prev.existing_material,
                }));
            } else if (filledMaterial) {
                setCampaign((prev) => ({ ...prev, existing_material: filledMaterial }));
            }
            loadSubjectAssets(selectedEnterpriseId, selectedBrandId, selectedProductId);
            const inputAssets = gi.promo_planner_input?.enterprise_info?.image_assets;
            setAssets((prev) => prev.map((item) => {
                const saved = Array.isArray(inputAssets)
                    ? inputAssets.find((row) => String(row?.image_id) === String(item.image_id))
                    : null;
                const derived = deriveAssetAnalysisStatus({ ...item, ...saved }, analysis);
                return { ...item, analysis_status: derived.status, analysis_error: derived.error };
            }));
            setInfo?.((prev) => ({
                ...prev,
                ...gi,
                promo_planner_input: gi.promo_planner_input || payload,
                promo_planner_result: gi.promo_planner_result || prev.promo_planner_result,
                promo_dna_global_md: gi.promo_dna_global_md || prev.promo_dna_global_md,
            }));
        } catch (err) {
            console.error(err);
            alert(`${t('策划方案生成失败', 'Failed to generate promo plan')}:\n${formatProviderModelEndpointError(err)}`);
        } finally {
            inputSaveEpochRef.current += 1;
            generatingRef.current = false;
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
        || result.characteristic_analysis?.enterprise
        || (Array.isArray(result.benchmark_films) && result.benchmark_films.length)
        || result.stage_plan?.hook?.content
        || result.project_visual_backfill?.Global_Style
        || result.video_positioning?.goal_type
        || result.script_preview?.logline
        || result.material_list?.length
    ));

    return (
        <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6 xl:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-semibold text-primary">{t('商业宣传片策划', 'Commercial Promo Planner')}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                        {t('选定企业/品牌/产品（产品可无）→ 锁定核心诉求 → 填写介绍；从主体素材库勾选本项目要用的素材。无选中素材时剧情可全新构思。', 'Pick enterprise / brand / product (product optional), lock the core appeal, add intro, then pick assets for this project. With none selected the plot can be newly invented.')}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={handleGenerate}
                        disabled={busy || !PROMO_GOAL_TYPES.includes(normalizePromoGoalType(campaign.goal_type)) || !String(campaign.expect_duration || '').trim() || campaign.expect_duration === PROMO_CUSTOM}
                        className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${busy || !PROMO_GOAL_TYPES.includes(normalizePromoGoalType(campaign.goal_type)) || !String(campaign.expect_duration || '').trim() || campaign.expect_duration === PROMO_CUSTOM ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary text-black hover:opacity-90'}`}
                    >
                        {isGenerating ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成策划方案', 'Generate Plan')}</>}
                    </button>
                </div>
            </div>

            <SectionCard title={t('📄 宣传主体', '📄 Catalog')}>
                <div className="space-y-3">
                    <p className="text-xs text-white/55">
                        {t('先选定企业与品牌；产品可无。点击编辑或新增会进入宣传主体界面。', 'Select enterprise and brand first; product is optional. Edit or create them in Promo Catalog.')}
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
                        emptyOption={t('无产品（可选）', 'No product (optional)')}
                        onChange={(nextId) => applyProductSelection(nextId)}
                        onEdit={() => openCatalog('offering', 'edit')}
                        onCreate={() => openCatalog('offering', 'create')}
                        editDisabled={busy || !selectedProductId}
                        createDisabled={busy || !selectedBrandId}
                    />
                    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5">
                        <div className="text-xs text-white/55">
                            {selectedEnterpriseId
                                ? t(`主体素材库共 ${catalogAssets.length} 条，本项目已选 ${readyAssets.length} 条。项目内只用已选项。`, `Subject library: ${catalogAssets.length}. Selected for this project: ${readyAssets.length}.`)
                                : t('先选定企业后，可从主体素材库勾选本项目要用的素材。', 'Select an enterprise first, then pick assets for this project.')}
                        </div>
                        <button
                            type="button"
                            disabled={busy || !selectedEnterpriseId}
                            onClick={() => openCatalog('enterprise', 'edit')}
                            className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40"
                        >
                            {t('管理主体素材库', 'Manage subject library')}
                        </button>
                    </div>
                </div>
            </SectionCard>

            <SectionCard title={t('📦 项目素材库', '📦 Project library')}>
                <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                        <h5 className="text-sm font-semibold text-white">{t('🖼️ 本项目已选素材', '🖼️ Selected for this project')}</h5>
                        <div className="flex items-center gap-2">
                            {assets.some((item) => item.upload_status === 'ready' && item.img_url && item.analysis_status !== ANALYSIS_STATUS_SUCCESS && item.analysis_status !== ANALYSIS_STATUS_ANALYZING) ? (
                                <button
                                    type="button"
                                    onClick={analyzePendingAssets}
                                    disabled={busy}
                                    className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                                >
                                    <RefreshCw className="w-3 h-3" /> {t('解析未解析/失败', 'Retry unparsed / failed')}
                                </button>
                            ) : null}
                            {selectedAssetIds.length > 0 ? (
                                <button type="button" onClick={() => removeAssets(selectedAssetIds)} className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-200 hover:bg-red-500/30 flex items-center gap-1">
                                    <Trash2 className="w-3 h-3" /> {t('批量删除', 'Delete selected')}
                                </button>
                            ) : null}
                        </div>
                    </div>
                    <div className="flex items-start gap-2 text-[11px] text-amber-200/90 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                        <span>{t('主体素材库是全部素材；下面只勾选本项目要用的。策划与成片只用已选项。本片新上传会同时写入主体库，供之后项目再选。无选中素材时策划会新构思剧情。', 'The subject library holds every asset. Check only what this project needs — planning uses that subset. New uploads also go into the subject library. With none selected, the plan invents the plot.')}</span>
                    </div>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                            <h6 className="text-xs font-semibold text-white/80 flex items-center gap-1">
                                <Library className="w-3.5 h-3.5" /> {t('从主体素材库勾选', 'Pick from subject library')}
                            </h6>
                            <button
                                type="button"
                                onClick={() => loadSubjectAssets()}
                                disabled={busy || !selectedEnterpriseId}
                                className="text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40"
                            >
                                {t('刷新库', 'Refresh library')}
                            </button>
                        </div>
                        {!selectedEnterpriseId ? (
                            <div className="text-xs text-white/40">{t('请先选定企业，才能从主体素材库勾选。', 'Select an enterprise first to pick from its library.')}</div>
                        ) : catalogAssets.length > 0 ? (
                            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-2">
                                {catalogAssets.map((item) => {
                                    const url = getFullUrl(item.img_url || item.file_url);
                                    const isVideo = String(item.media_kind || '') === 'video';
                                    const selected = catalogIsSelected(item);
                                    return (
                                        <button
                                            key={item.id || item.image_id}
                                            type="button"
                                            disabled={busy}
                                            onClick={() => toggleCatalogAsset(item)}
                                            className={`text-left bg-black/30 rounded-lg overflow-hidden disabled:opacity-40 ${selected ? 'border border-primary/70' : 'border border-white/10 hover:border-primary/40'}`}
                                        >
                                            <div className="h-20 bg-black/40 relative">
                                                {url && !isVideo ? <img src={url} alt={item.object_name || 'asset'} className="w-full h-full object-cover" /> : null}
                                                {url && isVideo ? <video src={url} className="w-full h-full object-cover" muted /> : null}
                                                {!url ? <div className="w-full h-full flex items-center justify-center text-white/30"><ImageIcon className="w-5 h-5" /></div> : null}
                                                <div className="absolute top-1.5 left-1.5">
                                                    <input type="checkbox" readOnly checked={selected} />
                                                </div>
                                            </div>
                                            <div className="px-2 py-1.5 space-y-0.5">
                                                <div className="text-[10px] text-primary/80">{catalogOwnerLabel(item.owner_kind, t)}</div>
                                                <div className="text-[11px] text-white truncate">{item.object_name || t('未命名', 'Untitled')}</div>
                                                <div className="text-[10px] text-white/50">{selected ? t('已选入本项目', 'In this project') : t('未选', 'Not selected')}</div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="text-xs text-muted-foreground">{t('主体素材库还没有素材。可在「管理主体素材库」上传，或在下方直接上传（同时写入主体库）。', 'Subject library is empty. Upload there, or upload below — new files also go into the subject library.')}</div>
                        )}
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
                        <div className="text-sm text-white/80">{t('拖拽或点击上传图片 / 视频，支持批量多选', 'Drop or click to upload images or videos.')}</div>
                        <div className="text-[11px] text-muted-foreground mt-1">{t(`图片 ${PROMO_IMAGE_MAX_MB}MB / 视频 ${PROMO_VIDEO_MAX_MB}MB`, `Images ${PROMO_IMAGE_MAX_MB}MB / videos ${PROMO_VIDEO_MAX_MB}MB`)}</div>
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
                                            asset.media_kind === 'video' ? (
                                                <video src={getFullUrl(asset.preview_url || asset.img_url)} className="w-full h-full object-cover" muted playsInline onClick={() => setPreviewImage(asset)} />
                                            ) : (
                                                <img src={getFullUrl(asset.preview_url || asset.img_url)} alt={asset.object_name || 'asset'} className="w-full h-full object-cover cursor-zoom-in" onClick={() => setPreviewImage(asset)} />
                                            )
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-white/30"><ImageIcon className="w-8 h-8" /></div>
                                        )}
                                        <label className="absolute top-2 left-2">
                                            <input type="checkbox" checked={selectedAssetIds.includes(asset.image_id)} onChange={(e) => setSelectedAssetIds((prev) => e.target.checked ? [...prev, asset.image_id] : prev.filter((id) => id !== asset.image_id))} />
                                        </label>
                                        <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                                            <div className="text-[10px] px-1.5 py-0.5 rounded bg-black/60">
                                                {catalogOwnerLabel(asset.owner_kind, t)}
                                            </div>
                                            <div className="text-[10px] px-1.5 py-0.5 rounded bg-black/60">
                                                {asset.upload_status === 'uploading' ? t('上传中', 'Uploading') : asset.upload_status === 'failed' ? t('上传失败', 'Upload failed') : t('已选用', 'In use')}
                                            </div>
                                            <div className={`text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1 ${analysisStatusClass(asset.analysis_status)}`}>
                                                {asset.analysis_status === ANALYSIS_STATUS_ANALYZING ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                                {analysisStatusLabel(asset.analysis_status, t)}
                                            </div>
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
                                        <TextInput value={asset.user_remark} onChange={(v) => updateAsset(asset.image_id, { user_remark: v })} placeholder={t('资产介绍（建议填写）', 'Asset caption (recommended)')} disabled={busy} />
                                        <div className="flex items-center justify-between gap-2 text-[11px]">
                                            <span className={`px-1.5 py-0.5 rounded ${analysisStatusClass(asset.analysis_status)}`}>
                                                {t('解析', 'Analysis')}：{analysisStatusLabel(asset.analysis_status, t)}
                                            </span>
                                        </div>
                                        {asset.upload_error ? <div className="text-[11px] text-red-300">{asset.upload_error}</div> : null}
                                        {asset.analysis_status === ANALYSIS_STATUS_FAILED && asset.analysis_error ? (
                                            <div className="text-[11px] text-red-300 break-words">{asset.analysis_error}</div>
                                        ) : null}
                                        <div className="flex gap-2">
                                            {(asset.owner_kind || 'project') === 'project' ? (
                                                <button type="button" className="flex-1 text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20" onClick={() => { replaceTargetIdRef.current = asset.image_id; replaceInputRef.current?.click(); }}>{t('替换', 'Replace')}</button>
                                            ) : null}
                                            <button
                                                type="button"
                                                className="flex-1 text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center justify-center gap-1"
                                                disabled={busy || asset.upload_status !== 'ready' || !asset.img_url || asset.analysis_status === ANALYSIS_STATUS_ANALYZING}
                                                onClick={() => analyzeOne(asset.image_id)}
                                            >
                                                {asset.analysis_status === ANALYSIS_STATUS_ANALYZING ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                                {t('重新解析', 'Re-analyze')}
                                            </button>
                                            <button type="button" className="flex-1 text-xs px-2 py-1 rounded bg-red-500/20 text-red-200 hover:bg-red-500/30" onClick={() => removeAssets([asset.image_id])}>{(asset.owner_kind || 'project') === 'project' ? t('删除', 'Delete') : t('移出本片', 'Remove from film')}</button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-muted-foreground">{t('无素材也可生成策划案：剧情可全新考虑，角色/场景后续补充上传或由 AI 生成。有资产时请写每条介绍。', 'No assets needed — the plot can be newly invented; characters and scenes can be uploaded later or generated by AI. If you upload any, add a caption for each.')}</div>
                    )}
                </div>
            </SectionCard>

            <SectionCard title={t('🎯 核心诉求与介绍信息', '🎯 Core appeal and intro')}>
                <div className="space-y-3">
                    <div>
                        <FieldLabel hint={t('必填，五选一', 'required, pick one')}>{t('核心诉求', 'Core Appeal')}</FieldLabel>
                        <ChoiceChips
                            t={t}
                            options={PROMO_GOAL_TYPES}
                            definitions={PROMO_GOAL_TYPE_DEFS}
                            value={campaign.goal_type}
                            onChange={(v) => patchCampaign('goal_type', normalizePromoGoalType(v))}
                            disabled={busy}
                            allowCustom={false}
                        />
                    </div>
                    <div>
                        <FieldLabel hint={t('必填，规划按此时长写', 'required; the plan must fit')}>{t('预期时长', 'Expected duration')}</FieldLabel>
                        <ChoiceChips
                            t={t}
                            options={PROMO_DURATIONS}
                            definitions={PROMO_DURATION_DEFS}
                            value={campaign.expect_duration}
                            onChange={(v) => patchCampaign('expect_duration', v)}
                            disabled={busy}
                            allowCustom
                            customPlaceholder={t('自定义，如 45s', 'Custom, e.g. 45s')}
                        />
                    </div>
                    <div className="text-xs text-white/55 bg-white/5 border border-white/10 rounded-md px-3 py-2">
                        {t('统一节奏：吸睛 → 共鸣 → 价值 → 收口。共鸣可适当融合救猫咪式节拍（一次小而可亲的主动作，加强代入），不是第五段。各段秒数、口播与花字密度必须合计落入所选预期时长；镜头由编剧按四段内容拆镜并逐字核销。', 'Rhythm is locked: hook → empathy → value → close. Empathy may fold in a Save-the-Cat likable beat. Stage seconds, copy and flower-text must fit the duration. The script writer breaks shots and checks each stage verbatim.')}
                    </div>
                    <div>
                        <FieldLabel>{t('基本介绍', 'Basic intro')}</FieldLabel>
                        <TextArea
                            value={campaign.basic_intro}
                            onChange={(v) => setCampaign((prev) => ({ ...prev, basic_intro: v, user_raw_text: v }))}
                            rows={4}
                            disabled={busy}
                            placeholder={t('企业、品牌、产品或本次宣传的基本情况', 'Basic intro of the enterprise, brand, product or this campaign')}
                        />
                    </div>
                    <div>
                        <FieldLabel>{t('目标客群', 'Target audience')}</FieldLabel>
                        <TextArea value={campaign.target_audience} onChange={(v) => patchCampaign('target_audience', v)} rows={2} disabled={busy} placeholder={t('谁会看、他们在意什么', 'Who watches and what they care about')} />
                    </div>
                    <div>
                        <FieldLabel>{t('竞品与市场', 'Competitors and market')}</FieldLabel>
                        <TextArea value={campaign.market_and_competitors} onChange={(v) => patchCampaign('market_and_competitors', v)} rows={2} disabled={busy} placeholder={t('市场位置、竞品差异、常见误区', 'Market position, competitor gaps, common pitfalls')} />
                    </div>
                    <div>
                        <FieldLabel>{t('CTA 行动召唤', 'CTA')}</FieldLabel>
                        <TextInput value={campaign.cta} onChange={(v) => patchCampaign('cta', v)} disabled={busy} placeholder={t('例如：预约到店 / 领取试吃 / 咨询加盟', 'e.g. Book a visit / Claim a trial / Ask about franchise')} />
                    </div>
                    <div>
                        <FieldLabel>{t('已有素材资源描述', 'Existing Materials')}</FieldLabel>
                        <TextArea
                            value={campaign.existing_material}
                            onChange={(v) => patchCampaign('existing_material', v)}
                            rows={8}
                            disabled={busy}
                            placeholder={t('可先手写备注。解析只回填项目素材库已选项；未勾选进本项目的主体库素材不会写入这里。', 'Optional notes first. Analysis only fills assets selected in this project library — unselected subject-library items stay out.')}
                        />
                    </div>
                    <div>
                        <FieldLabel>{t('制作约束 / 禁止内容', 'Constraints / Forbidden')}</FieldLabel>
                        <TextArea value={campaign.constraint} onChange={(v) => patchCampaign('constraint', v)} rows={2} disabled={busy} />
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
                    <h3 className="text-base font-semibold text-primary">{t('策划案（全部可编辑回写）', 'Plan (all editable write-back)')}</h3>
                    <OverallSchemeEditor result={result} patchResult={patchResult} t={t} />
                    <CharacteristicEditor result={result} patchResult={patchResult} t={t} />
                    <BenchmarkFilmsEditor result={result} setResult={setResult} t={t} />
                    <StagePlanEditor
                        result={result}
                        patchResult={patchResult}
                        t={t}
                        expectDuration={campaign.expect_duration}
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
                                await saveProjectPromoPlannerResult(projectId, { promo_planner_result: syncStagePlanToPreview(deepMerge(emptyPromoPlannerResult(), result || {})) });
                            } catch (err) {
                                console.error('[PromoPlanner] flush result before script generate failed', err);
                            }
                            await onGenerateActualScript({ result });
                        }}
                    />
                    <VisualBackfillEditor result={result} patchResult={patchResult} t={t} />
                    <SupplementEditor result={result} setResult={setResult} t={t} />
                </div>
            ) : (
                <div className="text-sm text-muted-foreground bg-black/20 border border-white/10 rounded-xl px-4 py-8 text-center">
                        {t('选定企业、锁定核心诉求并填写介绍后点击「生成策划方案」。将回写对标片、四段规划（即成片脚本方向）、基调风格与建议补充内容。', 'Select an enterprise, lock the core appeal, fill the intro, then generate. The page writes back benchmarks, four-stage plan (also the script direction), visual tone and supplement suggestions.')}
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
                        {previewImage.media_kind === 'video' ? (
                            <video src={getFullUrl(previewImage.preview_url || previewImage.img_url)} className="w-full max-h-[80vh] object-contain rounded-lg" controls />
                        ) : (
                            <img src={getFullUrl(previewImage.preview_url || previewImage.img_url)} alt={previewImage.object_name || ''} className="w-full max-h-[80vh] object-contain rounded-lg" />
                        )}
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
                <div className="md:col-span-2"><FieldLabel>{t('本次宣传要点（先对基本介绍；无则按核心诉求从主体抽取）', 'Promo focus')}</FieldLabel><TextArea value={data.promo_focus} onChange={(v) => patchResult('overall_scheme.promo_focus', v)} rows={2} placeholder={t('要点=…｜来源=基本介绍|主体抽取｜依据=…', 'Focus=… | Source=intro')} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('主要卖点（美食 / 美景 / 美物 / 美人 / 工艺 / 文化 / 高科技 / 历史沉淀）', 'Selling points')}</FieldLabel><TextArea value={data.selling_points} onChange={(v) => patchResult('overall_scheme.selling_points', v)} rows={2} placeholder={t('主=美食｜次=文化,工艺｜展现=吸睛…；价值…', 'Primary=food | Secondary=culture')} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('画面核（跟主卖点同核；美食 / 美景 / 美人 / 科技 / 产品；有 Logo、slogan 须标识特写。种草禁口播介绍，花字可点名）', 'Visual core')}</FieldLabel><TextArea value={data.visual_core} onChange={(v) => patchResult('overall_scheme.visual_core', v)} rows={2} placeholder={t('核=产品｜加码=充分特写｜依据=已锁主卖点', 'Core=product | Boost=close-up')} /></div>
                <div><FieldLabel>{t('核心诉求', 'Core appeal')}</FieldLabel><TextInput value={data.main_goal_type} onChange={(v) => patchResult('overall_scheme.main_goal_type', v)} /></div>
                <div><FieldLabel>{t('预期时长', 'Target duration')}</FieldLabel><TextInput value={data.target_duration} onChange={(v) => patchResult('overall_scheme.target_duration', v)} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('统一节奏', 'Rhythm')}</FieldLabel><TextInput value={PROMO_UNIFIED_RHYTHM} onChange={() => {}} disabled /></div>
                <div className="md:col-span-2"><FieldLabel>{t('时长分配', 'Duration budget')}</FieldLabel><TextArea value={data.duration_budget} onChange={(v) => patchResult('overall_scheme.duration_budget', v)} rows={2} /></div>
                <div className="md:col-span-2"><FieldLabel>{t('成功标准', 'Success metric')}</FieldLabel><TextArea value={data.success_metric} onChange={(v) => patchResult('overall_scheme.success_metric', v)} rows={2} /></div>
            </div>
        </SectionCard>
    );
}

function CharacteristicEditor({ result, patchResult, t }) {
    const data = result.characteristic_analysis || {};
    return (
        <SectionCard title={t('1. 企业 / 品牌 / 产品特性', '1. Characteristics')}>
            <div className="space-y-3">
                <div><FieldLabel>{t('企业特性', 'Enterprise')}</FieldLabel><TextArea value={data.enterprise} onChange={(v) => patchResult('characteristic_analysis.enterprise', v)} rows={3} /></div>
                <div><FieldLabel>{t('品牌特性', 'Brand')}</FieldLabel><TextArea value={data.brand} onChange={(v) => patchResult('characteristic_analysis.brand', v)} rows={3} /></div>
                <div><FieldLabel>{t('产品特性', 'Product')}</FieldLabel><TextArea value={data.product} onChange={(v) => patchResult('characteristic_analysis.product', v)} rows={3} /></div>
                <div><FieldLabel>{t('客群洞察', 'Audience insight')}</FieldLabel><TextArea value={data.audience_insight} onChange={(v) => patchResult('characteristic_analysis.audience_insight', v)} rows={3} /></div>
            </div>
        </SectionCard>
    );
}

function BenchmarkFilmsEditor({ result, setResult, t }) {
    const rows = Array.isArray(result.benchmark_films) ? result.benchmark_films : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), benchmark_films: next }));
    const fields = [
        ['title', t('片名', 'Title')],
        ['why_picked', t('为何对标', 'Why picked')],
        ['techniques', t('可借鉴技术', 'Techniques')],
        ['content_borrow', t('可借鉴内容', 'Content to borrow')],
        ['do_not_copy', t('禁止照搬（仅商标等）', 'Do not copy (trademarks only)')],
    ];
    return (
        <SectionCard
            title={t('2. 对标经典片（至少 3 部）', '2. Benchmark films (min. 3)')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update([...rows, { title: '', why_picked: '', techniques: '', content_borrow: '', do_not_copy: '' }])}><Plus className="w-3 h-3 inline" /> {t('添加对标', 'Add film')}</button>}
        >
            <p className="text-[11px] text-white/55">
                {t('情节、配色、拍摄与剪辑技巧均可借鉴。「禁止照搬」只写对方商标、Logo、吉祥物、注册口号等易混淆标识。', 'Plot, color and camera craft can be borrowed. “Do not copy” is only trademarks, logos, mascots or registered slogans.')}
            </p>
            <div className="space-y-3">
                {rows.map((row, idx) => (
                    <div key={`film-${idx}`} className="bg-black/20 p-3 rounded-md space-y-2">
                        {fields.map(([field, label]) => (
                            field === 'title' ? (
                                <div key={field}><FieldLabel>{label}</FieldLabel><TextInput value={row[field]} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, [field]: v } : item))} /></div>
                            ) : (
                                <div key={field}><FieldLabel>{label}</FieldLabel><TextArea value={row[field]} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, [field]: v } : item))} rows={2} /></div>
                            )
                        ))}
                        <button type="button" className="text-xs text-red-200" onClick={() => update(rows.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
                    </div>
                ))}
            </div>
        </SectionCard>
    );
}

function StagePlanEditor({
    result,
    patchResult,
    t,
    expectDuration,
    busy,
    isGeneratingScript,
    hasScript,
    onGenerateActualScript,
    onOpenScriptTab,
}) {
    const plan = result.stage_plan || emptyStagePlan();
    const target = expectDuration || result?.overall_scheme?.target_duration || '';
    const preview = result.script_preview || { logline: '', beats: [] };
    const logline = preview.logline || result?.overall_scheme?.one_liner || '';
    const canGenerate = Boolean(String(logline || '').trim() || PROMO_STAGE_KEYS.some(({ key, name }) => {
        const row = plan[key] || emptyStageBlock(name);
        return row.content || row.sensory || row.copy;
    }));
    return (
        <SectionCard
            title={t('3. 各阶段内容规划（成片脚本方向）', '3. Stage plan (script direction)')}
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
                </div>
            }
        >
            <p className="text-xs text-white/50">
                {t('四段即成片脚本方向，不再另开预览。改这里会同步给生成实际脚本。生成后可在剧本页继续优化、做资产与分镜。', 'These four stages are the script direction — no separate preview. Edits here feed Generate script. After that, continue in the Script workspace.')}
            </p>
            {target ? (
                <div className="text-xs text-amber-100/90 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                    {t(`按预期时长 ${target} 分配四段秒数与口播密度。`, `Fit copy density to the locked duration ${target}.`)}
                </div>
            ) : null}
            <div>
                <FieldLabel>{t('一句话方向', 'Logline')}</FieldLabel>
                <TextArea
                    value={logline}
                    onChange={(v) => patchResult('script_preview.logline', v)}
                    rows={2}
                    placeholder={t('全片一句话方向，可与总策略同核', 'One-line direction; may match the one-liner')}
                />
            </div>
            <div className="space-y-4">
                {PROMO_STAGE_KEYS.map(({ key, name }) => {
                    const row = plan[key] || emptyStageBlock(name);
                    const prefix = `stage_plan.${key}`;
                    return (
                        <div key={key} className="bg-black/20 p-3 rounded-md space-y-2">
                            <div className="text-sm font-semibold text-primary">{name}</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <div>
                                    <FieldLabel>{t('建议秒数', 'Duration')}</FieldLabel>
                                    <TextInput value={row.duration} onChange={(v) => patchResult(`${prefix}.duration`, v)} placeholder={t('如 4s', 'e.g. 4s')} />
                                </div>
                                <div>
                                    <FieldLabel>{t('本段 CTA', 'Stage CTA')}</FieldLabel>
                                    <TextInput value={row.cta} onChange={(v) => patchResult(`${prefix}.cta`, v)} placeholder={key === 'close' ? t('收口行动句', 'Close action') : t('可空', 'Optional')} />
                                </div>
                            </div>
                            <div>
                                <FieldLabel>{t('感官：必须看见什么', 'Sensory: what must be seen')}</FieldLabel>
                                <TextArea value={row.sensory} onChange={(v) => patchResult(`${prefix}.sensory`, v)} rows={2} placeholder={t('光、材质、体量、特写或宏观的看见结果，不写镜头表', 'What must be seen — not a shot list')} />
                            </div>
                            <div>
                                <FieldLabel>{t('内容（编剧逐字核销）', 'Content (script writer checks verbatim)')}</FieldLabel>
                                <TextArea value={row.content} onChange={(v) => patchResult(`${prefix}.content`, v)} rows={2} placeholder={t('本段要讲清的信息原文，生成脚本时逐字核销并可视化', 'Locked copy for verbatim visual checkout')} />
                            </div>
                            <div>
                                <FieldLabel>{t('口播', 'Voiceover')}</FieldLabel>
                                <TextArea value={row.copy} onChange={(v) => patchResult(`${prefix}.copy`, v)} rows={2} placeholder={t('可听口播，不等于花字；与花字不得同拍同步', 'Spoken line, not flower text; never same beat')} />
                            </div>
                            <div>
                                <FieldLabel>{t('花字', 'Flower text')}</FieldLabel>
                                <TextArea
                                    value={row.flower_text || ''}
                                    onChange={(v) => patchResult(`${prefix}.flower_text`, v)}
                                    rows={2}
                                    placeholder={key === 'close'
                                        ? t('文案=「有韵味的收口句」｜位置=中｜字级=大｜上屏=段末切镜|黑屏专镜|字卡专镜｜停留=长｜听=无｜艺术=A+B｜逐字=…', 'Copy | mid | large | end-cut, black card or title card | silent | hold long | glyph lock')
                                        : t('文案=「上屏短句」｜位置=中｜字级=中｜上屏=段末切镜|段首开镜|黑屏专镜|字卡专镜｜停留=短｜听=无｜艺术=A+B｜逐字=…', 'Copy | mid | medium | open/end cut, black or title card | silent | short | glyph lock')}
                                />
                            </div>
                            <div>
                                <FieldLabel>{t('技法联想', 'Technique')}</FieldLabel>
                                <TextArea value={row.technique_assoc || ''} onChange={(v) => patchResult(`${prefix}.technique_assoc`, v)} rows={2} placeholder={t('内容核=｜感官核=｜对标=｜创新=｜落地=', 'content | sensory | benchmark | craft')} />
                            </div>
                        </div>
                    );
                })}
            </div>
        </SectionCard>
    );
}

function VisualBackfillEditor({ result, patchResult, t }) {
    const data = result.project_visual_backfill || emptyVisualBackfill();
    const listField = (value) => (Array.isArray(value) ? value.join('\n') : String(value || ''));
    return (
        <SectionCard title={t('4. 基调与整体风格（project_visual_backfill）', '4. Tone and style (project_visual_backfill)')}>
            <div className="space-y-3">
                <div><FieldLabel>{t('视觉基调 Global_Style', 'Global_Style')}</FieldLabel><TextArea value={data.Global_Style} onChange={(v) => patchResult('project_visual_backfill.Global_Style', v)} rows={2} /></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div><FieldLabel>{t('风格模式', 'Style mode')}</FieldLabel><TextInput value={data.style_mode} onChange={(v) => patchResult('project_visual_backfill.style_mode', v)} /></div>
                    <div><FieldLabel>{t('基调 tone', 'Tone')}</FieldLabel><TextInput value={data.tone} onChange={(v) => patchResult('project_visual_backfill.tone', v)} placeholder={t('乡村 / 都市 / 古典…', 'Rural / urban / classical…')} /></div>
                </div>
                <div><FieldLabel>{t('光线 / 光学', 'Lighting / optics')}</FieldLabel><TextArea value={data.lighting} onChange={(v) => patchResult('project_visual_backfill.lighting', v)} rows={2} /></div>
                <div><FieldLabel>{t('色卡 color_palette', 'Color palette')}</FieldLabel><TextArea value={data.color_palette} onChange={(v) => patchResult('project_visual_backfill.color_palette', v)} rows={2} /></div>
                <div><FieldLabel>{t('色调倾向', 'Color spectrum')}</FieldLabel><TextInput value={data.color_spectrum} onChange={(v) => patchResult('project_visual_backfill.color_spectrum', v)} /></div>
                <div><FieldLabel>{t('配乐（须并重够响）', 'Music (foreground, loud)')}</FieldLabel><TextArea value={data.music_recommendation} onChange={(v) => patchResult('project_visual_backfill.music_recommendation', v)} rows={2} placeholder={t('乐器=…｜风格=…｜音量=并重｜权重=配乐主轴', 'instruments | style | volume=foreground | weight=score')} /></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div><FieldLabel>{t('配音风格', 'Voiceover')}</FieldLabel><TextArea value={data.voiceover_style} onChange={(v) => patchResult('project_visual_backfill.voiceover_style', v)} rows={2} /></div>
                    <div><FieldLabel>{t('音效风格', 'SFX style')}</FieldLabel><TextArea value={data.sfx_style} onChange={(v) => patchResult('project_visual_backfill.sfx_style', v)} rows={2} /></div>
                </div>
                <div className="space-y-2">
                    <FieldLabel>{t('花字规范（全片统一）', 'Flower-text spec (unified)')}</FieldLabel>
                    <p className="text-xs text-white/45">
                        {t('片内图形花字，不是对白硬字幕。有旁白时不出花字，花字低于旁白，禁止同步上屏以免分心。禁止底部落位，以免与字幕重合。各段最多一条。优先无声的段首开镜或段末切镜，不与动作抢镜；也可单独一拍黑屏专镜。CTA 可较长停留。默认中部中号，收口中部大号。中部花字须字少味厚并艺术化组合。字体字色全片同一套。', 'On-screen graphic titles, not dialogue captions. Never appear with voiceover—flower text yields to narration. Never sit on the bottom. One line per stage. Prefer a silent open or end cut; a black-screen card is allowed. CTA may hold longer. Mid-screen titles stay short and art-directed.')}
                    </p>
                    {(() => {
                        const spec = data.flower_text_spec || emptyFlowerTextSpec();
                        const patchSpec = (key, value) => patchResult(`project_visual_backfill.flower_text_spec.${key}`, value);
                        return (
                            <>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                    <TextInput value={spec.font} onChange={(v) => patchSpec('font', v)} placeholder={t('字体（黑/宋/无衬线…）', 'Font')} />
                                    <TextInput value={spec.weight} onChange={(v) => patchSpec('weight', v)} placeholder={t('字重', 'Weight')} />
                                    <TextInput value={spec.color} onChange={(v) => patchSpec('color', v)} placeholder={t('字色', 'Color')} />
                                    <TextInput value={spec.accent_color} onChange={(v) => patchSpec('accent_color', v)} placeholder={t('点缀色', 'Accent')} />
                                    <TextInput value={spec.stroke} onChange={(v) => patchSpec('stroke', v)} placeholder={t('描边', 'Stroke')} />
                                    <TextInput value={spec.align} onChange={(v) => patchSpec('align', v)} placeholder={t('对齐', 'Align')} />
                                    <TextInput value={spec.body_size} onChange={(v) => patchSpec('body_size', v)} placeholder={t('正文级=中', 'Body size')} />
                                    <TextInput value={spec.emphasis_size} onChange={(v) => patchSpec('emphasis_size', v)} placeholder={t('收口级=大', 'Close size')} />
                                    <TextInput value={spec.max_line_chars} onChange={(v) => patchSpec('max_line_chars', v)} placeholder={t('单行字数', 'Max chars')} />
                                    <TextInput value={spec.body_position} onChange={(v) => patchSpec('body_position', v)} placeholder={t('正文位=画面中部', 'Body position')} />
                                    <TextInput value={spec.emphasis_position} onChange={(v) => patchSpec('emphasis_position', v)} placeholder={t('收口位=画面中部', 'Close position')} />
                                    <TextInput value={spec.mid_display} onChange={(v) => patchSpec('mid_display', v)} placeholder={t('中屏展示=艺术化组合', 'Mid-screen art combo')} />
                                    <TextInput value={spec.cut_fusion} onChange={(v) => patchSpec('cut_fusion', v)} placeholder={t('切镜融合=段末/段首或黑屏专镜', 'Cut fusion')} />
                                    <TextInput value={spec.cta_hold} onChange={(v) => patchSpec('cta_hold', v)} placeholder={t('CTA停留=长', 'CTA hold')} />
                                    <TextInput value={spec.vo_xor} onChange={(v) => patchSpec('vo_xor', v)} placeholder={t('旁白优先=有旁白时不出花字', 'VO first: no flower text with narration')} />
                                    <TextInput value={spec.glyph_lock} onChange={(v) => patchSpec('glyph_lock', v)} placeholder={t('逐字锁=含X家须见家，禁何乐乐享', 'Glyph lock: keep 家, no dropped or doubled characters')} />
                                    <TextInput value={spec.seal_clear} onChange={(v) => patchSpec('seal_clear', v)} placeholder={t('印章不压字=印句外旁侧，压字=禁', 'Seal stays outside the letters')} />
                                    <TextInput value={spec.card_shot} onChange={(v) => patchSpec('card_shot', v)} placeholder={t('字卡专镜=场景底+字层，手写=禁', 'Title card: scene still + type layer')} />
                                    <TextInput value={spec.unity} onChange={(v) => patchSpec('unity', v)} placeholder={t('统一说明', 'Unity')} />
                                </div>
                                <TextArea value={spec.spec_line} onChange={(v) => patchSpec('spec_line', v)} rows={2} placeholder={t('规范一行：字体=…｜字色=…｜正文级=中｜收口级=大｜正文位=画面中部｜收口位=画面中部｜禁底部避字幕', 'One-line spec')} />
                            </>
                        );
                    })()}
                </div>
                <div><FieldLabel>{t('对标片名（与上节同核）', 'Borrowed films')}</FieldLabel><TextArea value={listField(data.borrowed_films)} onChange={(v) => patchResult('project_visual_backfill.borrowed_films', linesToList(v))} rows={3} /></div>
                <div><FieldLabel>{t('对标转译说明', 'Borrowed films note')}</FieldLabel><TextArea value={data.borrowed_films_note} onChange={(v) => patchResult('project_visual_backfill.borrowed_films_note', v)} rows={2} /></div>
            </div>
        </SectionCard>
    );
}

function SupplementEditor({ result, setResult, t }) {
    const rows = Array.isArray(result.supplement_suggestions) ? result.supplement_suggestions : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), supplement_suggestions: next }));
    return (
        <SectionCard
            title={t('5. 建议补充的内容', '5. Suggested supplements')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update([...rows, { item: '', reason: '', suggestion: '' }])}><Plus className="w-3 h-3 inline" /> {t('添加', 'Add')}</button>}
        >
            <div className="space-y-3">
                {rows.map((row, idx) => (
                    <div key={`sup-${idx}`} className="bg-black/20 p-3 rounded-md space-y-2">
                        <TextInput value={row.item} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, item: v } : item))} placeholder={t('补充项', 'Item')} />
                        <TextArea value={row.reason} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, reason: v } : item))} rows={2} placeholder={t('原因', 'Reason')} />
                        <TextArea value={row.suggestion} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, suggestion: v } : item))} rows={2} placeholder={t('怎么补', 'How to fill')} />
                        <button type="button" className="text-xs text-red-200" onClick={() => update(rows.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
                    </div>
                ))}
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
    const rebuilds = Array.isArray(analysis.rebuild_subjects) ? analysis.rebuild_subjects : [];
    const imageList = Array.isArray(analysis.image_list) ? analysis.image_list : [];
    const patchRebuild = (next) => patchResult('image_asset_analysis.rebuild_subjects', next);
    const patchImageList = (next) => patchResult('image_asset_analysis.image_list', next);
    return (
        <SectionCard title={t('8. 图片/视频解析 & 成片视觉规范', '8. Image/Video Analysis & Visual Spec')}>
            <p className="text-xs text-white/50">
                {t('有上传素材时，场景与道具细节会写入剧本「视觉还原」，供下游重新生成资产。可在此改稿。', 'Uploaded scene/prop details go into the script visual-rebuild block for later asset regeneration. You can edit them here.')}
            </p>
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
            {rebuilds.length > 0 ? (
                <div className="space-y-3 pt-2">
                    <div className="text-xs text-muted-foreground uppercase font-bold">{t('可重生主体（场景/道具/角色）', 'Rebuild subjects (scene / prop / character)')}</div>
                    {rebuilds.map((row, idx) => (
                        <div key={`${row.object_name}-${idx}`} className="bg-black/20 p-3 rounded-md space-y-2">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <TextInput value={row.kind} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, kind: v } : item))} placeholder={t('类型：character / prop / environment / product', 'kind')} />
                                <TextInput value={row.object_name} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, object_name: v, name_for_script: v } : item))} placeholder={t('object_name', 'object_name')} />
                            </div>
                            <TextArea value={row.rebuild_brief} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, rebuild_brief: v } : item))} rows={6} placeholder={t('重生全文：说明/外形/材质/空间/光色，将整段抄进剧本视觉还原', 'Full rebuild text copied into the script')} />
                            <TextArea value={row.appearance} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, appearance: v } : item))} rows={3} placeholder={t('外形', 'Appearance')} />
                            <TextArea value={row.clothing_or_material} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, clothing_or_material: v } : item))} rows={2} placeholder={t('衣着或材质', 'Clothing or material')} />
                            <TextArea value={row.color_and_markings} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, color_and_markings: v } : item))} rows={2} placeholder={t('主辅色/标识/可见文字', 'Color and markings')} />
                            <TextArea value={row.scale_and_shape} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, scale_and_shape: v } : item))} rows={2} placeholder={t('体量与形制', 'Scale and shape')} />
                            <TextArea value={row.space_layout} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, space_layout: v } : item))} rows={3} placeholder={t('环境空间（非环境可空）', 'Space layout')} />
                            <TextArea value={row.lighting} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, lighting: v } : item))} rows={2} placeholder={t('光色', 'Lighting')} />
                            <TextArea value={row.motion_from_video} onChange={(v) => patchRebuild(rebuilds.map((item, i) => i === idx ? { ...item, motion_from_video: v } : item))} rows={2} placeholder={t('视频动作', 'Video motion')} />
                        </div>
                    ))}
                </div>
            ) : null}
            {imageList.length > 0 ? (
                <div className="space-y-3 pt-2">
                    <div className="text-xs text-muted-foreground uppercase font-bold">{t('逐条素材细节', 'Per-asset details')}</div>
                    {imageList.map((row, idx) => (
                        <div key={`${row.image_id}-${idx}`} className="bg-black/20 p-3 rounded-md space-y-2">
                            <div className="text-xs text-white/70">{row.object_name || row.image_id} · {row.media_kind || 'image'} · {row.image_type}</div>
                            <TextArea value={row.rebuild_brief} onChange={(v) => patchImageList(imageList.map((item, i) => i === idx ? { ...item, rebuild_brief: v } : item))} rows={4} placeholder={t('本条重生全文', 'This asset rebuild text')} />
                            <TextArea value={row.environment_detail} onChange={(v) => patchImageList(imageList.map((item, i) => i === idx ? { ...item, environment_detail: v } : item))} rows={3} placeholder={t('场景细节', 'Scene detail')} />
                            <TextArea value={row.prop_detail} onChange={(v) => patchImageList(imageList.map((item, i) => i === idx ? { ...item, prop_detail: v } : item))} rows={3} placeholder={t('道具细节', 'Prop detail')} />
                            <TextArea value={row.character_detail} onChange={(v) => patchImageList(imageList.map((item, i) => i === idx ? { ...item, character_detail: v } : item))} rows={3} placeholder={t('人物细节', 'Character detail')} />
                            <TextArea value={row.video_motion} onChange={(v) => patchImageList(imageList.map((item, i) => i === idx ? { ...item, video_motion: v } : item))} rows={2} placeholder={t('视频动作（图片可空）', 'Video motion')} />
                        </div>
                    ))}
                </div>
            ) : null}
        </SectionCard>
    );
}

function MaterialEditor({ result, setResult, t }) {
    const rows = Array.isArray(result.material_list) ? result.material_list : [];
    const update = (next) => setResult((prev) => ({ ...deepMerge(emptyPromoPlannerResult(), prev || {}), material_list: next }));
    return (
        <SectionCard
            title={t('9. 素材拍摄清单', '9. Material List')}
            extra={<button type="button" className="text-xs px-2 py-1 rounded bg-white/10" onClick={() => update([...rows, { name: '', category: 'scene', description: '', reference_asset_name: '', source: '后续补充或AI生成', reuse_advice: '后续补充或AI生成' }])}><Plus className="w-3 h-3 inline" /> {t('添加', 'Add')}</button>}
        >
            <div className="space-y-3">
                {rows.map((row, idx) => (
                    <div key={`${row.name}-${idx}`} className="grid grid-cols-1 md:grid-cols-2 gap-2 bg-black/20 p-3 rounded-md">
                        <TextInput value={row.name} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, name: v } : item))} placeholder={t('素材名', 'Name')} />
                        <TextInput value={row.reference_asset_name} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, reference_asset_name: v } : item))} placeholder={t('引用 object_name（无素材可空）', 'object_name (optional)')} />
                        <TextArea value={row.description} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, description: v } : item))} rows={2} />
                        <div className="space-y-2">
                            <TextInput value={row.source} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, source: v } : item))} placeholder={t('来源：已有素材 / 后续补充 / AI生成', 'Source: existing / later upload / AI')} />
                            <TextInput value={row.reuse_advice} onChange={(v) => update(rows.map((item, i) => i === idx ? { ...item, reuse_advice: v } : item))} placeholder={t('怎么拍、补传或生成', 'How to shoot, upload later, or generate')} />
                            <button type="button" className="text-xs text-red-200" onClick={() => update(rows.filter((_, i) => i !== idx))}>{t('删除', 'Delete')}</button>
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
