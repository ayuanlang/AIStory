
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../lib/store';
import LogPanel from '../components/LogPanel';
import AgentChat from '../components/AgentChat';
import { MessageSquare, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL } from '../config';
import { setUiLang as setGlobalUiLang } from '../lib/uiLang';

// Helper to handle relative URLs
const getFullUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('blob:') || url.startsWith('data:')) return url;
    // If it's a relative path starting with /, append BASE_URL
    if (url.startsWith('/')) {
        // Avoid double slash if BASE_URL ends with /
        const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
        return `${base}${url}`;
    }
    return url;
};

const parseEpisodeNumberFromText = (value) => {
    const text = String(value || '').trim();
    if (!text) return null;

    const patterns = [
        /^episode\s*0*(\d+)\b/i,
        /^ep\s*0*(\d+)\b/i,
        /^第\s*0*(\d+)\s*集/i,
        /^0*(\d+)\s*(?:-|:|：)/,
    ];

    for (const pattern of patterns) {
        const matched = text.match(pattern);
        if (matched && matched[1]) {
            const parsed = Number(matched[1]);
            if (Number.isFinite(parsed) && parsed > 0) return parsed;
        }
    }

    return null;
};

const normalizeEpisodeTitleForDisplay = (rawTitle) => {
    const text = String(rawTitle || '').trim();
    if (!text) return '';

    return text
        .replace(/^episode\s*\d+\s*(?:-|:|：)?\s*/i, '')
        .replace(/^ep\s*\d+\s*(?:-|:|：)?\s*/i, '')
        .replace(/^第\s*\d+\s*集\s*(?:-|:|：)?\s*/i, '')
        .replace(/^\d+\s*(?:-|:|：)\s*/, '')
        .trim();
};

const buildEpisodeDisplayLabel = ({ episodeNumber, title, fallbackNumber } = {}) => {
    const directNumber = Number(episodeNumber);
    const fallback = Number(fallbackNumber);
    const inferred = parseEpisodeNumberFromText(title);
    const resolvedNumber = Number.isFinite(directNumber) && directNumber > 0
        ? directNumber
        : (Number.isFinite(fallback) && fallback > 0 ? fallback : inferred);

    const normalizedTitle = normalizeEpisodeTitleForDisplay(title);
    if (resolvedNumber) {
        const resolvedTitle = normalizedTitle || `Episode ${resolvedNumber}`;
        return `${resolvedNumber}-${resolvedTitle}`;
    }

    return normalizedTitle || 'Untitled Episode';
};

import { 
    fetchProject, 
    updateProject,
    generateProjectStoryGlobal,
    analyzeProjectNovel,
    generateProjectCharacterProfile,
    fetchEpisodes, 
    createEpisode, 
    updateEpisode,
    updateEpisodeSegments,
    deleteEpisode,
    fetchScenes, 
    createScene,
    updateScene, 
    deleteScene,
    fetchShots,
    fetchEpisodeShots,
    createShot,
    updateShot,
    deleteShot,
    fetchEntities, 
    createEntity,
    updateEntity,
    deleteEntity,
    deleteAllEntities,
    generateImage,
    generateVideo,
    fetchAssets, 
    generateSceneShots,
    fetchSceneShotsPrompt,
    createAsset,
    uploadAsset,
    getSettings,
    translateText,
    refinePrompt,
    analyzeScene,
    fetchPrompt,
    fetchMe,
    analyzeEntityImage,
    applySceneAIResult,
    updateSceneLatestAIResult,
    getSceneLatestAIResult,
    generateEpisodeCharacterProfile,
    generateEpisodeStory,
    saveEpisodeStoryGeneratorInput,
    generateEpisodeScenes,
    generateProjectEpisodeScripts,
    getProjectEpisodeScriptsStatus,
    saveProjectStoryGeneratorGlobalInput,
    exportProjectStoryGlobalPackage,
    importProjectStoryGlobalPackage,
    saveProjectCharacterCanonInput,
    saveProjectCharacterCanonCategories,
    updateProjectCharacterProfiles,
    recordSystemLogAction,
} from '../services/api';

import RefineControl from '../components/RefineControl.jsx';
import VideoStudio from '../components/VideoStudio';
import InputGroup from './editor/components/InputGroup';
import MarkdownCell from './editor/components/MarkdownCell';
import TranslateControl from './editor/components/TranslateControl';
import {
    PROVIDER_LABELS,
    MODEL_OPTIONS,
    getSettingSourceByCategory,
    sourceBadgeClass,
    sourceBadgeText,
    formatProviderModelEndpointError,
} from './editor/editorConfig';

// RefineControl moved to components/RefineControl.jsx
import { processPrompt } from '../lib/promptUtils';
import SettingsPage from './Settings';
import { confirmUiMessage, promptUiMessage } from '../lib/uiMessage';

// Character Canon (Authoritative) generator (shared)
const CANON_TAG_STORAGE_KEY = 'aistory_character_canon_tag_categories_v1';
const CANON_IDENTITY_STORAGE_KEY = 'aistory_character_canon_identity_categories_v1';

const DEFAULT_CANON_TAG_CATEGORIES = [
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
    {
        key: 'wardrobe',
        title: '穿搭/造型（主角塑造）',
        options: [
            { id: 'wardrobe_1', label: '干练', detail: '收腰西装或衬衫+长裤，剪裁利落' },
            { id: 'wardrobe_2', label: '优雅', detail: '简洁连衣裙或套装，配饰克制' },
            { id: 'wardrobe_3', label: '都市时髦', detail: '大衣/风衣+高跟或短靴，层次感' },
            { id: 'wardrobe_4', label: '禁欲风', detail: '高领/长袖/长裤，颜色克制但极有气场' },
            { id: 'wardrobe_5', label: '轻奢', detail: '面料有质感，细节讲究，不浮夸' },
            { id: 'wardrobe_m1', label: '绅士', detail: '合身西装/大衣，领带或领结点到为止' },
            { id: 'wardrobe_m2', label: '冷酷街头', detail: '黑色夹克/皮衣+短靴，线条硬' },
            { id: 'wardrobe_m3', label: '少年感男主', detail: '白衬衫/针织衫/运动外套，干净清爽' },
        ],
    },
    {
        key: 'clothing_items',
        title: '衣着/单品（常用标签）',
        options: [
            { id: 'cloth_1', label: '白衬衫', detail: '干净克制，越简单越高级' },
            { id: 'cloth_2', label: '黑高领', detail: '禁欲、冷感、气场强' },
            { id: 'cloth_3', label: '西装', detail: '合身剪裁，肩线清晰' },
            { id: 'cloth_4', label: '大衣/风衣', detail: '压气场，走路带风' },
            { id: 'cloth_5', label: '丝质/缎面', detail: '微光泽，性感但不露骨' },
            { id: 'cloth_6', label: '皮衣/夹克', detail: '硬朗、叛逆、酷感' },
            { id: 'cloth_7', label: '短裙/开衩', detail: '腿部线条更突出（注意尺度克制）' },
            { id: 'cloth_8', label: '高跟鞋', detail: '气场与身材比例拉长' },
            { id: 'cloth_9', label: '短靴', detail: '利落、都市、行动感' },
            { id: 'cloth_10', label: '配饰克制', detail: '少而精，提升高级感' },
        ],
    },
    {
        key: 'combat_wear',
        title: '战斗服装/战甲（服饰）',
        options: [
            { id: 'cwear_1', label: '战甲/盔甲', detail: '金属/皮革甲胄，防护与威慑感' },
            { id: 'cwear_2', label: '轻甲', detail: '更灵活，线条更贴身、利落' },
            { id: 'cwear_3', label: '战术背心/防弹衣', detail: '现代作战感，功能性口袋与模块' },
            { id: 'cwear_4', label: '制服/作战服', detail: '军警/特勤气质，纪律与专业' },
            { id: 'cwear_5', label: '披风/斗篷', detail: '英雄感/隐匿感，镜头层次更强' },
            { id: 'cwear_6', label: '护臂/护腕', detail: '近战细节，硬朗质感' },
            { id: 'cwear_7', label: '护膝/护腿', detail: '实战磨损感更真实' },
            { id: 'cwear_8', label: '作战靴', detail: '落地更稳，压迫感与行动感兼具' },
            { id: 'cwear_9', label: '战术腰带/枪套', detail: '装备挂载，专业度更高' },
        ],
    },
    {
        key: 'ancient_wear',
        title: '古装服装/服饰',
        options: [
            { id: 'awear_1', label: '汉服（襦裙/交领）', detail: '飘逸层次，古风气质' },
            { id: 'awear_2', label: '长袍/直裾', detail: '文人/谋士感，克制内敛' },
            { id: 'awear_3', label: '官服/朝服', detail: '礼制等级与权力感更明确' },
            { id: 'awear_4', label: '锦衣/华服', detail: '贵气、纹样精致、用料讲究' },
            { id: 'awear_5', label: '夜行衣', detail: '暗色贴身，隐秘与危险感（不强调动作）' },
            { id: 'awear_6', label: '甲胄（古代战甲）', detail: '甲片/扎甲，历史质感强' },
            { id: 'awear_7', label: '披风/披肩', detail: '身份感与镜头层次' },
            { id: 'awear_8', label: '发冠/发簪', detail: '阶层与礼制体现' },
            { id: 'awear_9', label: '腰带/玉佩', detail: '点明身份与品味' },
            { id: 'awear_10', label: '绣鞋/靴', detail: '细节完成度更高，时代感更真' },
        ],
    },
    {
        key: 'hair_makeup',
        title: '妆发/细节（主角塑造）',
        options: [
            { id: 'hm_1', label: '红唇', detail: '饱和但干净的红，气场拉满' },
            { id: 'hm_2', label: '淡妆', detail: '伪素颜，重点是皮肤干净与眼神' },
            { id: 'hm_3', label: '眼妆', detail: '眼尾微上扬，强调眼神锋利/勾人' },
            { id: 'hm_4', label: '长发', detail: '发丝有光泽，发型不凌乱' },
            { id: 'hm_5', label: '短发', detail: '轮廓利落，露出颈部线条' },
            { id: 'hm_m1', label: '寸头/短寸', detail: '干净利落，突出眉骨与眼神' },
            { id: 'hm_m2', label: '胡渣', detail: '微微胡渣，成熟感与危险感' },
        ],
    },
    {
        key: 'vibe',
        title: '气质/表现（主角塑造）',
        options: [
            { id: 'vibe_1', label: '神秘', detail: '信息不一次说完，表情留白' },
            { id: 'vibe_2', label: '冷峻', detail: '少笑，语气短，目光锐利' },
            { id: 'vibe_3', label: '阳光', detail: '笑意自然，语气轻快，亲和力强' },
            { id: 'vibe_4', label: '专业感', detail: '用词准确，动作克制，目标导向' },
            { id: 'vibe_5', label: '强势', detail: '话语有控制力，场面压得住' },
            { id: 'vibe_6', label: '脆弱感', detail: '瞬间的停顿/回避眼神，让人心软' },
        ],
    },
    {
        key: 'nation',
        title: '国籍/地区（设定）',
        options: [
            { id: 'nation_1', label: '中国', detail: '可细分：北方/南方口音与习惯' },
            { id: 'nation_2', label: '日本', detail: '克制礼貌、边界感明显' },
            { id: 'nation_3', label: '韩国', detail: '时尚敏感、表达更直接' },
            { id: 'nation_4', label: '美国', detail: '表达直接、个人主义、行动优先' },
            { id: 'nation_5', label: '英国', detail: '措辞克制、礼貌疏离、幽默冷' },
            { id: 'nation_6', label: '法国', detail: '松弛浪漫、审美挑剔、有锋芒' },
            { id: 'nation_7', label: '意大利', detail: '热情外放、注重衣着与手势' },
        ],
    },
    {
        key: 'ethnicity',
        title: '人种/族裔（设定）',
        options: [
            { id: 'eth_1', label: '东亚', detail: '例如：中/日/韩常见审美与轮廓特点' },
            { id: 'eth_2', label: '白人/欧洲裔', detail: '骨相立体、肤色与发色范围更广' },
            { id: 'eth_3', label: '黑人/非洲裔', detail: '五官张力强、体态与气场更突出' },
            { id: 'eth_4', label: '拉丁裔', detail: '热烈、自信、风格表达更强' },
            { id: 'eth_5', label: '南亚裔', detail: '深邃眼神、配饰审美更鲜明' },
            { id: 'eth_6', label: '中东/阿拉伯裔', detail: '浓眉深眼、轮廓强、气场浓烈' },
            { id: 'eth_7', label: '混血', detail: '特征融合，辨识度高' },
        ],
    },
];

const DEFAULT_CANON_IDENTITY_CATEGORIES = [
    {
        key: 'lead_role',
        title: '主角定位/戏份',
        options: [
            { id: 'lead_f', label: '女主角', detail: '故事核心视角/情感主线' },
            { id: 'lead_m', label: '男主角', detail: '故事核心视角/推动行动线' },
            { id: 'lead_2', label: '第二主角', detail: '重要支线/关键转折' },
            { id: 'antagonist', label: '反派/对立面', detail: '推进冲突与悬念' },
        ],
    },
    {
        key: 'occupation',
        title: '职业/身份',
        options: [
            { id: 'occ_ceo', label: 'CEO/总裁', detail: '强掌控、决策快、社交资源丰富' },
            { id: 'occ_police', label: '刑警/警探', detail: '行动派、观察力强、压力承受高' },
            { id: 'occ_lawyer', label: '律师', detail: '逻辑强、措辞锋利、擅长博弈' },
            { id: 'occ_doctor', label: '医生', detail: '专业冷静、情绪克制、同理心' },
            { id: 'occ_artist', label: '艺术家', detail: '审美敏感、情绪浓、反差感' },
            { id: 'occ_student', label: '大学生', detail: '成长线明显、少年感/少女感' },
            { id: 'occ_model', label: '模特/艺人', detail: '镜头感强、曝光与舆论压力' },
        ],
    },
    {
        key: 'combat_identity',
        title: '战斗身份/背景',
        options: [
            { id: 'cid_1', label: '军人/士兵', detail: '训练有素，服从命令，纪律感强' },
            { id: 'cid_2', label: '特勤/特种', detail: '高压任务，处事克制专业' },
            { id: 'cid_3', label: '雇佣兵', detail: '利益驱动，实战经验丰富' },
            { id: 'cid_4', label: '杀手/刺客', detail: '隐秘、冷静、边界感强' },
            { id: 'cid_5', label: '保镖/护卫', detail: '保护优先，风险评估与站位意识强' },
            { id: 'cid_6', label: '武术家', detail: '以技服人，克制与底线清晰' },
            { id: 'cid_7', label: '赏金猎人', detail: '规则感强，灰色地带的执行者' },
            { id: 'cid_8', label: '黑帮打手', detail: '狠劲、街头经验与威慑' },
        ],
    },
    {
        key: 'ancient_identity',
        title: '古装身份/阵营',
        options: [
            { id: 'aid_1', label: '将军/统帅', detail: '威望与军纪，杀伐果断' },
            { id: 'aid_2', label: '侍卫/禁军', detail: '守护要员/皇权，纪律严' },
            { id: 'aid_3', label: '捕快/衙役', detail: '基层执法，江湖味更浓' },
            { id: 'aid_4', label: '县令/官员', detail: '规则执行者，权力与人情博弈' },
            { id: 'aid_5', label: '世家公子/小姐', detail: '礼制与家族利益牵引，克制体面' },
            { id: 'aid_6', label: '王爷/皇子', detail: '权力中心，处处试探与算计' },
            { id: 'aid_7', label: '宫女/太监', detail: '宫廷生态，信息与生存技巧' },
            { id: 'aid_8', label: '门派弟子/修行者', detail: '师门规矩、江湖恩怨、阵营牵连' },
            { id: 'aid_9', label: '侠客/游侠', detail: '行走江湖，讲义气也有底线' },
        ],
    },
    {
        key: 'status',
        title: '社会身份/阶层',
        options: [
            { id: 'st_elite', label: '上层精英', detail: '资源多、社交圈高、习惯克制' },
            { id: 'st_middle', label: '中产专业人士', detail: '稳健务实、重效率与边界' },
            { id: 'st_grass', label: '草根逆袭', detail: '韧性强、行动强、野心明确' },
            { id: 'st_mysterious', label: '身份成谜', detail: '信息分层揭示，悬念强' },
        ],
    },
    {
        key: 'personality_arc',
        title: '主角弧光/关键词',
        options: [
            { id: 'arc_redemption', label: '救赎', detail: '背负过去，逐步修复与和解' },
            { id: 'arc_growth', label: '成长', detail: '从稚嫩到成熟的可见变化' },
            { id: 'arc_revenge', label: '复仇', detail: '目标明确，情绪压抑与爆发' },
            { id: 'arc_power', label: '权力', detail: '争夺与控制、规则博弈' },
        ],
    },
];

const canonOptionValue = (opt) => `${opt.label}：${opt.detail}`;

const normalizeCanonTagCategories = (raw) => {
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

// Mock Data / Placeholders for Tabs
const ProjectOverview = ({ id, onProjectUpdate, onJumpToEpisode, episodes = [], uiLang = 'en' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [project, setProject] = useState(null);
    const { addLog } = useLog();
    const [info, setInfo] = useState({
        script_title: "",
        series_episode: "",
        base_positioning: "Modern Workplace",
        type: "Live Action (Realism/Cinematic 8K)",
        Global_Style: "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
        tech_params: {
            visual_standard: {
                horizontal_resolution: "1080",
                vertical_resolution: "1920",
                frame_rate: "24",
                aspect_ratio: "9:16",
                quality: "Ultra High"
            }
        },
        tone: "Skin Tone Optimized, Dreamy",
        lighting: "Butterfly Light, Soft Light",
        language: "English",
        borrowed_films: [],
        character_relationships: "",
        notes: "",
        story_dna_global_md: "",
        story_generator_global_input: {
            episodes_count: 12,
            background: "",
            setup: "",
            development: "",
            turning_points: "",
            climax: "",
            resolution: "",
            suspense: "",
            foreshadowing: "",
            extra_notes: "",
        },
        character_profiles: [],
        character_canon_md: "",
        character_canon_input: {
            name: "",
            selected_tag_ids: [],
            selected_identity_ids: [],
            custom_identity: "",
            body_features: "",
            custom_style_tags: "",
            extra_notes: "",
        },
    });

    const [globalStoryInput, setGlobalStoryInput] = useState({
        episodes_count: 12,
        background: "",
        setup: "",
        development: "",
        turning_points: "",
        climax: "",
        resolution: "",
        suspense: "",
        foreshadowing: "",
        extra_notes: "",
    });
    const [isGeneratingGlobalStory, setIsGeneratingGlobalStory] = useState(false);
    const [isGeneratingEpisodeScripts, setIsGeneratingEpisodeScripts] = useState(false);
    const [episodeScriptsProgress, setEpisodeScriptsProgress] = useState(null);
    const [showEpisodeScriptsProgressModal, setShowEpisodeScriptsProgressModal] = useState(false);
    const [isAnalyzingNovel, setIsAnalyzingNovel] = useState(false);
    const [isImportingStoryPackage, setIsImportingStoryPackage] = useState(false);
    const [novelImportText, setNovelImportText] = useState('');
    const [showGlobalStoryGuide, setShowGlobalStoryGuide] = useState(false);
    const storyPackageFileInputRef = useRef(null);
    const episodeScriptsStatusTimerRef = useRef(null);
    const globalStoryAutosaveTimerRef = useRef(null);
    const skipNextGlobalStoryAutosaveRef = useRef(true);

    const pollEpisodeScriptsStatus = useCallback(async () => {
        if (!id) return null;
        try {
            const status = await getProjectEpisodeScriptsStatus(id);
            if (status && typeof status === 'object') {
                setEpisodeScriptsProgress(status);
                return status;
            }
        } catch (e) {
            // Ignore transient polling errors
        }
        return null;
    }, [id]);

    useEffect(() => {
        return () => {
            if (episodeScriptsStatusTimerRef.current) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        if (!id) return;
        let cancelled = false;

        const hydrateEpisodeScriptsStatus = async () => {
            const status = await pollEpisodeScriptsStatus();
            if (cancelled || !status || typeof status !== 'object') return;
            if (status.running) {
                setShowEpisodeScriptsProgressModal(true);
                if (!episodeScriptsStatusTimerRef.current) {
                    episodeScriptsStatusTimerRef.current = setInterval(pollEpisodeScriptsStatus, 1500);
                }
            } else if (episodeScriptsStatusTimerRef.current && !isGeneratingEpisodeScripts) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
        };

        hydrateEpisodeScriptsStatus();

        return () => {
            cancelled = true;
        };
    }, [id, pollEpisodeScriptsStatus, isGeneratingEpisodeScripts]);

    // Project-level Character Canon (keep original tag-selection UX)
    const [canonName, setCanonName] = useState('');
    const [canonIdentityCategories, setCanonIdentityCategories] = useState(DEFAULT_CANON_IDENTITY_CATEGORIES);
    const [canonSelectedIdentityIds, setCanonSelectedIdentityIds] = useState([]);
    const [canonCustomIdentity, setCanonCustomIdentity] = useState('');
    const [canonBody, setCanonBody] = useState('');
    const [canonExtra, setCanonExtra] = useState('');
    const [canonCustomTags, setCanonCustomTags] = useState('');
    const [canonTagCategories, setCanonTagCategories] = useState(DEFAULT_CANON_TAG_CATEGORIES);
    const [canonTagEditMode, setCanonTagEditMode] = useState(false);
    const [canonSelectedTagIds, setCanonSelectedTagIds] = useState([]);
    const [isGeneratingCanon, setIsGeneratingCanon] = useState(false);
    const [showCanonModal, setShowCanonModal] = useState(false);

    const renderCanonMarkdownFromProfiles = (profiles) => {
        const items = Array.isArray(profiles) ? profiles : [];
        const blocks = [];
        for (const it of items) {
            if (!it || typeof it !== 'object') continue;
            const nm = String(it.name || '').trim();
            if (!nm) continue;
            const md = String(it.description_md || '').trim();
            if (md) {
                blocks.push(md);
            } else {
                blocks.push(`### ${nm} (Canonical)\n- Identity: ${it.identity || ''}\n`);
            }
        }
        return blocks.join('\n\n').trim();
    };

    const handleDeleteCanonCharacter = async (characterName) => {
        const name = String(characterName || '').trim();
        if (!id || !name) return;
        const ok = await confirmUiMessage(`Delete "${name}" from Character Canon? You can re-generate it later.`);
        if (!ok) return;

        try {
            const current = Array.isArray(info.character_profiles) ? info.character_profiles : [];
            const nextProfiles = current.filter(p => (p && typeof p === 'object' ? String(p.name || '').trim() !== name : true));
            await updateProjectCharacterProfiles(id, nextProfiles);
            setInfo(prev => {
                const merged = { ...prev };
                merged.character_profiles = nextProfiles;
                merged.character_canon_md = renderCanonMarkdownFromProfiles(nextProfiles);
                return merged;
            });
        } catch (e) {
            console.error('[Character Canon] Delete failed:', e);
            alert(`Delete failed: ${e?.message || 'Unknown error'}`);
        }
    };

    const canonAutosaveTimerRef = useRef(null);
    const skipNextCanonAutosaveRef = useRef(true);
    const canonCategoriesAutosaveTimerRef = useRef(null);
    const skipNextCanonCategoriesAutosaveRef = useRef(true);

    const persistCanonTagCategories = (categories) => {
        try {
            const normalized = normalizeCanonTagCategories(categories);
            if (!normalized) return false;
            localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(normalized));
            return true;
        } catch (e) {
            return false;
        }
    };

    const persistCanonIdentityCategories = (categories) => {
        try {
            const normalized = normalizeCanonTagCategories(categories);
            if (!normalized) return false;
            localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(normalized));
            return true;
        } catch (e) {
            return false;
        }
    };

    useEffect(() => {
        try {
            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);
            const LEGACY_SEXY_OPTION_IDS = new Set([
                'sexy_1',
                'sexy_2',
                'sexy_3',
                'sexy_4',
                'sexy_m1',
                'sexy_m2',
            ]);

            const mergeCategoriesByKey = (savedCats, defaultCats) => {
                const byKey = new Map();
                for (const c of (savedCats || [])) {
                    if (!c?.key) continue;
                    if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                    byKey.set(c.key, c);
                }

                const mergeOne = (savedCat, defCat) => {
                    if (!savedCat) return defCat;
                    const categoryKey = savedCat.key || defCat?.key;
                    let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                    if (categoryKey === 'sexy') {
                        savedOptions = savedOptions.filter(o => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
                    }
                    const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                    const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                    const mergedOptions = [...savedOptions];
                    for (const opt of defOptions) {
                        if (!opt?.id) continue;
                        if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                    }
                    return {
                        ...savedCat,
                        key: savedCat.key || defCat?.key,
                        title: savedCat.title || defCat?.title,
                        options: mergedOptions,
                    };
                };

                const merged = [];
                for (const def of (defaultCats || [])) {
                    const saved = byKey.get(def.key);
                    merged.push(mergeOne(saved, def));
                    byKey.delete(def.key);
                }
                for (const rest of byKey.values()) {
                    if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                    merged.push(rest);
                }
                return merged;
            };

            const savedTags = localStorage.getItem(CANON_TAG_STORAGE_KEY);
            if (savedTags) {
                const parsed = JSON.parse(savedTags);
                const normalized = normalizeCanonTagCategories(parsed);
                if (normalized) {
                    setCanonTagCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES));
                } else {
                    setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
                }
            } else {
                setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
            }

            const savedIdentity = localStorage.getItem(CANON_IDENTITY_STORAGE_KEY);
            if (savedIdentity) {
                const parsed = JSON.parse(savedIdentity);
                const normalized = normalizeCanonTagCategories(parsed);
                if (normalized) {
                    setCanonIdentityCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES));
                }
            }
        } catch (e) {
            setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
            setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const toggleCanonTagId = (tagId) => {
        setCanonSelectedTagIds(prev => (
            prev.includes(tagId) ? prev.filter(t => t !== tagId) : [...prev, tagId]
        ));
    };

    const toggleCanonIdentityId = (identityId) => {
        setCanonSelectedIdentityIds(prev => (
            prev.includes(identityId) ? prev.filter(t => t !== identityId) : [...prev, identityId]
        ));
    };

    const canonSelectedTagStrings = () => {
        const selected = [];
        for (const cat of (canonTagCategories || [])) {
            for (const opt of (cat.options || [])) {
                if (canonSelectedTagIds.includes(opt.id)) {
                    selected.push(canonOptionValue(opt));
                }
            }
        }
        return selected;
    };

    const canonSelectedIdentityStrings = () => {
        const selected = [];
        for (const cat of (canonIdentityCategories || [])) {
            for (const opt of (cat.options || [])) {
                if (canonSelectedIdentityIds.includes(opt.id)) {
                    selected.push(canonOptionValue(opt));
                }
            }
        }
        return selected;
    };

    const newCanonOptionId = (prefix = 'opt') => `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;

    const updateCanonCategoryTitle = (catKey, title) => {
        setCanonTagCategories(prev => (prev || []).map(c => (c.key === catKey ? { ...c, title } : c)));
    };
    const updateCanonOption = (catKey, optId, patch) => {
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return {
                ...c,
                options: (c.options || []).map(o => (o.id === optId ? { ...o, ...patch } : o)),
            };
        }));
    };
    const addCanonOption = (catKey) => {
        const newId = newCanonOptionId(catKey);
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id: newId, label: '新标签', detail: '细节描述' }] };
        }));
    };
    const removeCanonOption = (catKey, optId) => {
        setCanonSelectedTagIds(prev => prev.filter(id2 => id2 !== optId));
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
    };

    const updateIdentityCategoryTitle = (catKey, title) => {
        setCanonIdentityCategories(prev => (prev || []).map(c => (c.key === catKey ? { ...c, title } : c)));
    };
    const updateIdentityOption = (catKey, optId, patch) => {
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return {
                ...c,
                options: (c.options || []).map(o => (o.id === optId ? { ...o, ...patch } : o)),
            };
        }));
    };
    const addIdentityOption = (catKey) => {
        const newId = newCanonOptionId(catKey);
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id: newId, label: '新身份', detail: '细节描述' }] };
        }));
    };
    const removeIdentityOption = (catKey, optId) => {
        setCanonSelectedIdentityIds(prev => prev.filter(id2 => id2 !== optId));
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
    };

    const closeCanonModal = () => {
        if (canonTagEditMode) {
            persistCanonTagCategories(canonTagCategories);
            persistCanonIdentityCategories(canonIdentityCategories);
        }
        setCanonTagEditMode(false);
        setShowCanonModal(false);
    };

    useEffect(() => {
    // ... no changes to rest

        const load = async () => {
            try {
                const data = await fetchProject(id);
                setProject(data);
                if (data.global_info) {
                     // Merger with defaults to ensure structure
                     const merged = {
                         ...info,
                         ...data.global_info,
                         tech_params: {
                             visual_standard: {
                                 ...info.tech_params.visual_standard,
                                 ...(data.global_info.tech_params?.visual_standard || {})
                             }
                         }
                     };

                     // Default Script Title to project.title when empty
                     if (!merged.script_title || String(merged.script_title).trim().length === 0) {
                         if (data?.title && String(data.title).trim().length > 0) {
                             merged.script_title = String(data.title).trim();
                         }
                     }
                     setInfo(merged);

                     // Restore Story Generator draft inputs (if previously saved)
                     if (merged.story_generator_global_input && typeof merged.story_generator_global_input === 'object') {
                         setGlobalStoryInput(prev => ({
                             ...prev,
                             ...merged.story_generator_global_input,
                         }));
                     }

                     // Avoid immediately auto-saving right after hydration
                     skipNextGlobalStoryAutosaveRef.current = true;

                     // Restore Character Canon draft inputs (if previously saved)
                     const canonDraft = merged.character_canon_input;
                     if (canonDraft && typeof canonDraft === 'object') {
                         if (typeof canonDraft.name === 'string') setCanonName(canonDraft.name);
                         if (Array.isArray(canonDraft.selected_identity_ids)) setCanonSelectedIdentityIds(canonDraft.selected_identity_ids);
                         if (Array.isArray(canonDraft.selected_tag_ids)) setCanonSelectedTagIds(canonDraft.selected_tag_ids);
                         if (typeof canonDraft.custom_identity === 'string') setCanonCustomIdentity(canonDraft.custom_identity);
                         if (typeof canonDraft.body_features === 'string') setCanonBody(canonDraft.body_features);
                         if (typeof canonDraft.custom_style_tags === 'string') setCanonCustomTags(canonDraft.custom_style_tags);
                         if (typeof canonDraft.extra_notes === 'string') setCanonExtra(canonDraft.extra_notes);
                     }

                     // Restore Character Canon tag/identity categories from DB (cross-device)
                     if (merged.character_canon_tag_categories) {
                         const normalized = normalizeCanonTagCategories(merged.character_canon_tag_categories);
                         if (normalized) {
                            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);
                            const LEGACY_SEXY_OPTION_IDS = new Set([
                                'sexy_1',
                                'sexy_2',
                                'sexy_3',
                                'sexy_4',
                                'sexy_m1',
                                'sexy_m2',
                            ]);

                             const mergeCategoriesByKey = (savedCats, defaultCats) => {
                                 const byKey = new Map();
                                 for (const c of (savedCats || [])) {
                                     if (!c?.key) continue;
                                     if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                                     byKey.set(c.key, c);
                                 }

                                 const mergeOne = (savedCat, defCat) => {
                                     if (!savedCat) return defCat;
                                     const categoryKey = savedCat.key || defCat?.key;
                                     let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                                     if (categoryKey === 'sexy') {
                                         savedOptions = savedOptions.filter(o => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
                                     }
                                     const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                                     const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                                     const mergedOptions = [...savedOptions];
                                     for (const opt of defOptions) {
                                         if (!opt?.id) continue;
                                         if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                                     }
                                     return {
                                         ...savedCat,
                                         key: savedCat.key || defCat?.key,
                                         title: savedCat.title || defCat?.title,
                                         options: mergedOptions,
                                     };
                                 };

                                 const mergedCats = [];
                                 for (const def of (defaultCats || [])) {
                                     const saved = byKey.get(def.key);
                                     mergedCats.push(mergeOne(saved, def));
                                     byKey.delete(def.key);
                                 }
                                 for (const rest of byKey.values()) {
                                     if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                                     mergedCats.push(rest);
                                 }
                                 return mergedCats;
                             };

                             const mergedCats = mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES);
                             setCanonTagCategories(mergedCats);
                             try { localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(mergedCats)); } catch {}
                         }
                     }
                     if (merged.character_canon_identity_categories) {
                         const normalized = normalizeCanonTagCategories(merged.character_canon_identity_categories);
                         if (normalized) {
                            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);

                             const mergeCategoriesByKey = (savedCats, defaultCats) => {
                                 const byKey = new Map();
                                 for (const c of (savedCats || [])) {
                                     if (!c?.key) continue;
                                     if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                                     byKey.set(c.key, c);
                                 }

                                 const mergeOne = (savedCat, defCat) => {
                                     if (!savedCat) return defCat;
                                     const savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                                     const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                                     const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                                     const mergedOptions = [...savedOptions];
                                     for (const opt of defOptions) {
                                         if (!opt?.id) continue;
                                         if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                                     }
                                     return {
                                         ...savedCat,
                                         key: savedCat.key || defCat?.key,
                                         title: savedCat.title || defCat?.title,
                                         options: mergedOptions,
                                     };
                                 };

                                 const mergedCats = [];
                                 for (const def of (defaultCats || [])) {
                                     const saved = byKey.get(def.key);
                                     mergedCats.push(mergeOne(saved, def));
                                     byKey.delete(def.key);
                                 }
                                 for (const rest of byKey.values()) {
                                     if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                                     mergedCats.push(rest);
                                 }
                                 return mergedCats;
                             };

                             const mergedCats = mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES);
                             setCanonIdentityCategories(mergedCats);
                             try { localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(mergedCats)); } catch {}
                         }
                     }

                     // Avoid immediately auto-saving right after hydration
                     skipNextCanonAutosaveRef.current = true;
                     skipNextCanonCategoriesAutosaveRef.current = true;
                }
            } catch (e) {
                console.error("Failed to load project", e);
            }
        };
        load();
    }, [id]);

    // Auto-save Character Canon tag/identity categories (debounced) when in edit mode
    useEffect(() => {
        if (!id) return;
        if (!canonTagEditMode) return;

        if (skipNextCanonCategoriesAutosaveRef.current) {
            skipNextCanonCategoriesAutosaveRef.current = false;
            return;
        }

        if (canonCategoriesAutosaveTimerRef.current) {
            clearTimeout(canonCategoriesAutosaveTimerRef.current);
        }

        canonCategoriesAutosaveTimerRef.current = setTimeout(async () => {
            try {
                const normalizedTags = normalizeCanonTagCategories(canonTagCategories);
                const normalizedIdentity = normalizeCanonTagCategories(canonIdentityCategories);
                if (!normalizedTags || !normalizedIdentity) return;
                await saveProjectCharacterCanonCategories(id, {
                    tag_categories: normalizedTags,
                    identity_categories: normalizedIdentity,
                });
                try { localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(normalizedTags)); } catch {}
                try { localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(normalizedIdentity)); } catch {}
            } catch (e) {
                console.error('[Character Canon Categories] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (canonCategoriesAutosaveTimerRef.current) {
                clearTimeout(canonCategoriesAutosaveTimerRef.current);
            }
        };
    }, [id, canonTagEditMode, canonTagCategories, canonIdentityCategories]);

    // Auto-save Project Character Canon draft inputs (debounced)
    useEffect(() => {
        if (!id) return;
        if (isGeneratingCanon) return;

        if (skipNextCanonAutosaveRef.current) {
            skipNextCanonAutosaveRef.current = false;
            return;
        }

        if (canonAutosaveTimerRef.current) {
            clearTimeout(canonAutosaveTimerRef.current);
        }

        canonAutosaveTimerRef.current = setTimeout(async () => {
            try {
                const payload = {
                    name: canonName || '',
                    selected_tag_ids: Array.isArray(canonSelectedTagIds) ? canonSelectedTagIds : [],
                    selected_identity_ids: Array.isArray(canonSelectedIdentityIds) ? canonSelectedIdentityIds : [],
                    custom_identity: canonCustomIdentity || '',
                    body_features: canonBody || '',
                    custom_style_tags: canonCustomTags || '',
                    extra_notes: canonExtra || '',
                };
                await saveProjectCharacterCanonInput(id, payload);
            } catch (e) {
                console.error('[Character Canon] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (canonAutosaveTimerRef.current) {
                clearTimeout(canonAutosaveTimerRef.current);
            }
        };
    }, [
        id,
        isGeneratingCanon,
        canonName,
        canonSelectedTagIds,
        canonSelectedIdentityIds,
        canonCustomIdentity,
        canonBody,
        canonCustomTags,
        canonExtra,
    ]);

    // Auto-save Story Generator (Global/Project) draft inputs (debounced)
    useEffect(() => {
        if (!id) return;
        if (isGeneratingGlobalStory) return;

        if (skipNextGlobalStoryAutosaveRef.current) {
            skipNextGlobalStoryAutosaveRef.current = false;
            return;
        }

        if (globalStoryAutosaveTimerRef.current) {
            clearTimeout(globalStoryAutosaveTimerRef.current);
        }

        globalStoryAutosaveTimerRef.current = setTimeout(async () => {
            try {
                const payload = {
                    mode: 'global',
                    episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
                    background: globalStoryInput.background,
                    setup: globalStoryInput.setup,
                    development: globalStoryInput.development,
                    turning_points: globalStoryInput.turning_points,
                    climax: globalStoryInput.climax,
                    resolution: globalStoryInput.resolution,
                    suspense: globalStoryInput.suspense,
                    foreshadowing: globalStoryInput.foreshadowing,
                    extra_notes: globalStoryInput.extra_notes,
                };
                await saveProjectStoryGeneratorGlobalInput(id, payload);
            } catch (e) {
                console.error('[Global Story Generator] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (globalStoryAutosaveTimerRef.current) {
                clearTimeout(globalStoryAutosaveTimerRef.current);
            }
        };
    }, [id, globalStoryInput, isGeneratingGlobalStory]);

    const handleSave = async () => {
        try {
            const global_info = {
                ...info,
                story_generator_global_input: {
                    ...globalStoryInput,
                    episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
                },
                character_canon_input: {
                    name: canonName || '',
                    selected_tag_ids: Array.isArray(canonSelectedTagIds) ? canonSelectedTagIds : [],
                    selected_identity_ids: Array.isArray(canonSelectedIdentityIds) ? canonSelectedIdentityIds : [],
                    custom_identity: canonCustomIdentity || '',
                    body_features: canonBody || '',
                    custom_style_tags: canonCustomTags || '',
                    extra_notes: canonExtra || '',
                },
            };
            await updateProject(id, { global_info });
            alert("Project info saved!");
            if (onProjectUpdate) onProjectUpdate();
        } catch (e) {
            console.error("Failed to save", e);
            alert(`Failed to save: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleGenerateGlobalStory = async () => {
        setIsGeneratingGlobalStory(true);
        try {
            const payload = {
                mode: 'global',
                episodes_count: Number(globalStoryInput.episodes_count || 0),
                // Project Overview / Basic Information (forward to LLM)
                script_title: info.script_title,
                type: info.type,
                language: info.language,
                base_positioning: info.base_positioning,
                Global_Style: info.Global_Style,
                background: globalStoryInput.background,
                setup: globalStoryInput.setup,
                development: globalStoryInput.development,
                turning_points: globalStoryInput.turning_points,
                climax: globalStoryInput.climax,
                resolution: globalStoryInput.resolution,
                suspense: globalStoryInput.suspense,
                foreshadowing: globalStoryInput.foreshadowing,
                extra_notes: globalStoryInput.extra_notes,
            };
            const updated = await generateProjectStoryGlobal(id, payload);
            setProject(updated);
            if (updated?.global_info) {
                const merged = {
                    ...info,
                    ...updated.global_info,
                    tech_params: {
                        visual_standard: {
                            ...info.tech_params.visual_standard,
                            ...(updated.global_info.tech_params?.visual_standard || {})
                        }
                    }
                };
                setInfo(merged);
            }
            alert('Global story framework generated and saved to Overview.');
        } catch (e) {
            console.error(e);
            const readable = formatProviderModelEndpointError(e);
            alert(`Failed to generate global story:\n${readable}`);
        } finally {
            setIsGeneratingGlobalStory(false);
        }
    };

    const handleAnalyzeNovelToGlobalStory = async () => {
        const text = String(novelImportText || '').trim();
        if (!text) {
            alert('Please paste novel/script text first.');
            return;
        }

        setIsAnalyzingNovel(true);
        try {
            const analyzed = await analyzeProjectNovel(id, { novel_text: text });
            const mergedStoryInput = {
                ...globalStoryInput,
                background: analyzed?.background || '',
                setup: analyzed?.setup || '',
                development: analyzed?.development || '',
                turning_points: analyzed?.turning_points || '',
                climax: analyzed?.climax || '',
                resolution: analyzed?.resolution || '',
                suspense: analyzed?.suspense || '',
                foreshadowing: analyzed?.foreshadowing || '',
            };

            // We persist immediately so users don't rely only on debounced autosave.
            skipNextGlobalStoryAutosaveRef.current = true;
            setGlobalStoryInput(mergedStoryInput);
            await saveProjectStoryGeneratorGlobalInput(id, {
                mode: 'global',
                episodes_count: Number(mergedStoryInput.episodes_count || 0) || 0,
                background: mergedStoryInput.background,
                setup: mergedStoryInput.setup,
                development: mergedStoryInput.development,
                turning_points: mergedStoryInput.turning_points,
                climax: mergedStoryInput.climax,
                resolution: mergedStoryInput.resolution,
                suspense: mergedStoryInput.suspense,
                foreshadowing: mergedStoryInput.foreshadowing,
                extra_notes: mergedStoryInput.extra_notes,
            });

            alert('Imported text analyzed, fields auto-filled, and draft saved.');
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || String(e);
            alert(`Failed to analyze imported text: ${detail}`);
        } finally {
            setIsAnalyzingNovel(false);
        }
    };

    const handleExportStoryGeneratorPackage = async () => {
        try {
            const pkg = await exportProjectStoryGlobalPackage(id);
            const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const safeName = String(project?.title || `project_${id}`)
                .replace(/[\\/:*?"<>|]+/g, '_')
                .replace(/\s+/g, '_')
                .slice(0, 60);
            a.href = url;
            a.download = `${safeName}_story_generator_global_export.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || String(e);
            alert(`Failed to export Story Generator package: ${detail}`);
        }
    };

    const handleOpenImportStoryGeneratorPackage = () => {
        if (!storyPackageFileInputRef.current) return;
        storyPackageFileInputRef.current.value = '';
        storyPackageFileInputRef.current.click();
    };

    const handleImportStoryGeneratorPackageFile = async (event) => {
        const file = event?.target?.files?.[0];
        if (!file) return;

        setIsImportingStoryPackage(true);
        try {
            const raw = await file.text();
            let parsed;
            try {
                parsed = JSON.parse(raw);
            } catch {
                throw new Error('Invalid JSON file.');
            }

            const payload = {
                project_overview: parsed?.project_overview || {},
                basic_information: parsed?.basic_information || {},
                character_canon_project: parsed?.character_canon_project || {},
                story_generator_global_project: parsed?.story_generator_global_project || {},
                story_generator_global_structured: parsed?.story_generator_global_structured || {},
                story_generator_global_input: parsed?.story_generator_global_input || {},
                story_dna_global_md: parsed?.story_dna_global_md || '',
                global_style_constraints: parsed?.global_style_constraints || {},
            };

            const updated = await importProjectStoryGlobalPackage(id, payload);
            setProject(updated);
            if (updated?.global_info) {
                const merged = {
                    ...info,
                    ...updated.global_info,
                    tech_params: {
                        visual_standard: {
                            ...info.tech_params.visual_standard,
                            ...(updated.global_info.tech_params?.visual_standard || {})
                        }
                    }
                };
                setInfo(merged);

                if (updated.global_info.story_generator_global_input && typeof updated.global_info.story_generator_global_input === 'object') {
                    skipNextGlobalStoryAutosaveRef.current = true;
                    setGlobalStoryInput(prev => ({
                        ...prev,
                        ...updated.global_info.story_generator_global_input,
                    }));
                }

                // Restore Character Canon draft inputs/categories immediately after package import
                const importedCanonDraft = updated.global_info.character_canon_input;
                if (importedCanonDraft && typeof importedCanonDraft === 'object') {
                    if (typeof importedCanonDraft.name === 'string') setCanonName(importedCanonDraft.name);
                    if (Array.isArray(importedCanonDraft.selected_identity_ids)) setCanonSelectedIdentityIds(importedCanonDraft.selected_identity_ids);
                    if (Array.isArray(importedCanonDraft.selected_tag_ids)) setCanonSelectedTagIds(importedCanonDraft.selected_tag_ids);
                    if (typeof importedCanonDraft.custom_identity === 'string') setCanonCustomIdentity(importedCanonDraft.custom_identity);
                    if (typeof importedCanonDraft.body_features === 'string') setCanonBody(importedCanonDraft.body_features);
                    if (typeof importedCanonDraft.custom_style_tags === 'string') setCanonCustomTags(importedCanonDraft.custom_style_tags);
                    if (typeof importedCanonDraft.extra_notes === 'string') setCanonExtra(importedCanonDraft.extra_notes);
                }

                if (Array.isArray(updated.global_info.character_canon_tag_categories)) {
                    const normalizedTags = normalizeCanonTagCategories(updated.global_info.character_canon_tag_categories);
                    if (normalizedTags) setCanonTagCategories(normalizedTags);
                }

                if (Array.isArray(updated.global_info.character_canon_identity_categories)) {
                    const normalizedIdentities = normalizeCanonTagCategories(updated.global_info.character_canon_identity_categories);
                    if (normalizedIdentities) setCanonIdentityCategories(normalizedIdentities);
                }
            }

            alert('Story Generator package imported and saved to this project.');
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || String(e);
            alert(`Failed to import Story Generator package: ${detail}`);
        } finally {
            setIsImportingStoryPackage(false);
        }
    };

    const handleGenerateEpisodeScripts = async ({ retryFailedOnly = false, forceStart = false } = {}) => {
        if (!id) {
            addLog?.('Cannot generate episode scripts: missing project id.', 'error');
            alert('Cannot generate episode scripts: missing project id.');
            return;
        }
        const n = Number(globalStoryInput.episodes_count || 0);
        if (!n || Number.isNaN(n) || n <= 0) {
            alert('Please set a valid Episodes Count first.');
            return;
        }

        setIsGeneratingEpisodeScripts(true);
        setEpisodeScriptsProgress(null);
        setShowEpisodeScriptsProgressModal(true);

        if (episodeScriptsStatusTimerRef.current) {
            clearInterval(episodeScriptsStatusTimerRef.current);
            episodeScriptsStatusTimerRef.current = null;
        }

        episodeScriptsStatusTimerRef.current = setInterval(pollEpisodeScriptsStatus, 1500);
        pollEpisodeScriptsStatus();

        try {
            const overwriteExisting = Boolean(forceStart);
            const modeLabel = retryFailedOnly
                ? 'retry-failed-only'
                : (overwriteExisting ? 'force-generate-all' : 'generate-missing-only');

            if (overwriteExisting) {
                const ok = await confirmUiMessage('Force Start will overwrite existing episode scripts for all target episodes. Continue?');
                if (!ok) {
                    addLog?.('Force Start canceled.', 'warning');
                    return;
                }
            }

            addLog?.(`Generating episode scripts (${modeLabel}, target 1..${n})... (This may take several minutes)`, 'process');
            addLog?.(
                `[DEBUG][Before API] Generate Episode Scripts payload: ${JSON.stringify({ episodes_count: n, overwrite_existing: overwriteExisting, retry_failed_only: retryFailedOnly })}`,
                'info'
            );
            const res = await generateProjectEpisodeScripts(id, {
                episodes_count: n,
                overwrite_existing: overwriteExisting,
                retry_failed_only: retryFailedOnly,
            });

            await pollEpisodeScriptsStatus();
            addLog?.(
                `[DEBUG][After API] response summary: ${JSON.stringify({
                    project_id: res?.project_id,
                    episodes_target: res?.episodes_target,
                    episodes_created: res?.episodes_created,
                    results_count: Array.isArray(res?.results) ? res.results.length : 0,
                    errors_count: Array.isArray(res?.errors) ? res.errors.length : 0,
                })}`,
                'info'
            );

            const dbg = res?.debug_context || {};
            addLog?.(
                `[DEBUG][Input Confirm] Global Style & Constraints imported: ${dbg.has_global_style_constraints ? 'YES' : 'NO'}; ` +
                `Character relationships imported: ${dbg.has_character_relationships ? 'YES' : 'NO'}; ` +
                `Character source: ${dbg.character_canon_source || 'unknown'}; ` +
                `Global DNA len: ${dbg.global_story_dna_length ?? 0}; Character canon len: ${dbg.character_canon_length ?? 0}`,
                'info'
            );
            const created = Number(res?.episodes_created ?? 0);
            const errors = Array.isArray(res?.errors) ? res.errors : [];
            const results = Array.isArray(res?.results) ? res.results : [];
            const generated = results.filter(r => r?.generated === true).length;
            const skipped = results.filter(r => r?.skipped === true).length;
            const summary = `Generated: ${generated}, Skipped: ${skipped}, Created Episodes: ${created}, Errors: ${errors.length}`;
            if (errors.length > 0) {
                addLog?.(`Episode script generation finished. ${summary}`, 'warning');
                alert(`Episode script generation finished. ${summary}`);
            } else {
                addLog?.(`Episode script generation finished. ${summary}`, 'success');
                alert(`Episode script generation finished. ${summary}`);
            }
            // Refresh project + episodes from parent (ProjectOverview does not own episode state)
            if (onProjectUpdate) {
                await onProjectUpdate();
            }
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.response?.data?.message || e?.message || String(e);
            addLog?.(`Episode script generation failed: ${detail}`, 'error');
            alert(`Failed to generate episode scripts: ${detail}`);
        } finally {
            if (episodeScriptsStatusTimerRef.current) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
            setIsGeneratingEpisodeScripts(false);
        }
    };

    const handleGenerateProjectCanon = async () => {
        const name = (canonName || '').trim();
        if (!name) {
            alert('请输入角色名称');
            return;
        }

        const custom = (canonCustomTags || '')
            .split(/[,，\n]/)
            .map(t => t.trim())
            .filter(Boolean);
        const selectedStrings = canonSelectedTagStrings();
        const style_tags = Array.from(new Set([...(selectedStrings || []), ...custom]));

        const identityCustom = (canonCustomIdentity || '')
            .split(/[,，\n]/)
            .map(t => t.trim())
            .filter(Boolean);
        const identityStrings = canonSelectedIdentityStrings();
        const identityMerged = Array.from(new Set([...(identityStrings || []), ...identityCustom]));
        const identity = identityMerged.join(' / ');

        setIsGeneratingCanon(true);
        try {
            const updated = await generateProjectCharacterProfile(id, {
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
            });
            setProject(updated);
            if (updated?.global_info) {
                const merged = {
                    ...info,
                    ...updated.global_info,
                    tech_params: {
                        visual_standard: {
                            ...info.tech_params.visual_standard,
                            ...(updated.global_info.tech_params?.visual_standard || {})
                        }
                    }
                };
                setInfo(merged);
            }
            setShowCanonModal(false);
            alert('Character Canon generated and appended in Overview.');
        } catch (e) {
            console.error(e);
            alert(`Failed to generate Character Canon: ${e.message}`);
        } finally {
            setIsGeneratingCanon(false);
        }
    };

    const updateField = (key, value) => {
        setInfo(prev => ({ ...prev, [key]: value }));
    };

    const updateTech = (key, value) => {
        setInfo(prev => ({
            ...prev,
            tech_params: {
                ...prev.tech_params,
                visual_standard: {
                    ...prev.tech_params.visual_standard,
                    [key]: value
                }
            }
        }));
    };

    const handleBorrowedFilmsChange = (str) => {
        // Simple comma separated handling
        const arr = str.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        setInfo(prev => ({ ...prev, borrowed_films: arr }));
    };

    const episodeScriptResults = Array.isArray(episodeScriptsProgress?.results) ? episodeScriptsProgress.results : [];
    const episodesInRun = Number(episodeScriptsProgress?.episodes_in_run || 0);
    const processedCount = Number(episodeScriptsProgress?.processed || 0);
    const progressPercent = episodesInRun > 0 ? Math.min(100, Math.round((processedCount / episodesInRun) * 100)) : 0;

    const episodeTitleByNumber = useMemo(() => {
        const titleMap = new Map();
        (Array.isArray(episodes) ? episodes : []).forEach((ep, index) => {
            const parsedNumber = Number(ep?.episode_number) > 0
                ? Number(ep?.episode_number)
                : (parseEpisodeNumberFromText(ep?.title) || (index + 1));
            if (!parsedNumber || titleMap.has(parsedNumber)) return;
            titleMap.set(parsedNumber, String(ep?.title || '').trim());
        });
        return titleMap;
    }, [episodes]);

    const episodeResultRows = useMemo(() => {
        if (!episodeScriptsProgress || episodesInRun <= 0) return [];
        const byEpisodeNumber = new Map();
        for (const item of episodeScriptResults) {
            const num = Number(item?.episode_number || 0);
            if (!num) continue;
            byEpisodeNumber.set(num, item);
        }

        const rows = [];
        for (let i = 1; i <= episodesInRun; i++) {
            const row = byEpisodeNumber.get(i);
            const knownTitle = episodeTitleByNumber.get(i);
            if (row) {
                rows.push({
                    episode_number: i,
                    episode_id: row?.episode_id,
                    episode_title: row?.episode_title || knownTitle || t(`第 ${i} 集`, `Episode ${i}`),
                    status: row?.status || (row?.generated ? 'generated' : row?.skipped ? 'skipped' : row?.error ? 'failed' : 'unknown'),
                    output_chars: row?.output_chars,
                    error: row?.error,
                    reason: row?.reason,
                });
            } else {
                rows.push({
                    episode_number: i,
                    episode_title: knownTitle || t(`第 ${i} 集`, `Episode ${i}`),
                    status: 'pending',
                });
            }
        }
        return rows;
    }, [episodeScriptsProgress, episodeScriptResults, episodesInRun, episodeTitleByNumber]);

    const failedEpisodeRows = episodeResultRows.filter(item => item?.status === 'failed' && item?.episode_id);

    if (!project) return <div className="p-8 text-muted-foreground">{t('加载中...', 'Loading...')}</div>;

    const prefix = "proj-";

    return (
        <div className="p-4 sm:p-6 lg:p-8 w-full h-full overflow-y-auto">
            <div className="flex justify-between items-center mb-8">
                <h2 className="text-2xl font-bold">{t('项目总览', 'Project Overview')}</h2>
                <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                    <SettingsIcon className="w-4 h-4" /> {t('保存修改', 'Save Changes')}
                </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 w-full">
                {/* Basic Info */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">{t('基本信息', 'Basic Information')}</h3>
                    
                    <div className="grid grid-cols-1 gap-4">
                        <InputGroup idPrefix={prefix} label={t('剧本标题', 'Script Title')} value={info.script_title} onChange={v => updateField('script_title', v)} placeholder={t('例如：我的科幻史诗', 'e.g. My Sci-Fi Epic')} />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('类型', 'Type')} 
                            value={info.type} 
                            onChange={v => updateField('type', v)} 
                            list={[
                                "Live Action", 
                                "Live Action (Realism/Cinematic 8K)",
                                "2D Animation", 
                                "3D Animation", 
                                "Stop Motion", 
                                "Tokusatsu", 
                                "Stage Play", 
                                "CG Animation", 
                                "Mixed Media", 
                                "Documentary"
                            ]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label={t('语言', 'Language')} 
                            value={info.language} 
                            onChange={v => updateField('language', v)} 
                            list={["Chinese", "English", "Bilingual (CN/EN)", "Japanese", "Korean", "French", "Spanish", "German", "Other"]} 
                        />
                    </div>
                    
                    <InputGroup idPrefix={prefix}
                        label={t('基础定位', 'Base Positioning')} 
                        value={info.base_positioning} 
                        onChange={v => updateField('base_positioning', v)} 
                        list={["Urban Romance", "Sci-Fi Adventure", "Mystery / Thriller", "Period / Wuxia", "Fantasy Epic", "Modern Workplace", "High School / Youth", "Cyberpunk", "Horror", "Comedy", "Drama", "Action", "Historical"]}
                        placeholder={t('例如：都市爱情 / 科幻', 'e.g. Urban Romance / Sci-Fi')}
                    />

                    <InputGroup idPrefix={prefix}
                        label={t('全局风格', 'Global Style')} 
                        value={info.Global_Style} 
                        onChange={v => updateField('Global_Style', v)} 
                        multi={true}
                        list={[
                            "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
                            "Hyperrealistic Portrait, RAW Photo, Ultra Detailed",
                            "Cyberpunk", 
                            "Minimalist", 
                            "Photorealistic", 
                            "Disney Style", 
                            "Ghibli Style", 
                            "Film Noir", 
                            "Steampunk", 
                            "Watercolor", 
                            "Oil Painting", 
                            "Pixel Art", 
                            "Vaporwave", 
                            "Gothic", 
                            "Surrealism"
                        ]} 
                    />

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('借鉴影片（参考）', 'Borrowed Films (Ref)')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={info.borrowed_films.join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder={t('用逗号分隔，例如：银翼杀手, 黑客帝国', 'Use commas to separate, e.g. Blade Runner, Matrix')}
                        />
                    </div>
                </div>

                {/* Technical & Visual Params */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">{t('技术与视觉参数', 'Technical & Visual Parameters')}</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('横向分辨率', 'H. Resolution')} 
                            value={info.tech_params?.visual_standard?.horizontal_resolution} 
                            onChange={v => updateTech('horizontal_resolution', v)} 
                            placeholder="1080"
                            list={["720", "1080", "1920", "3840"]}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('纵向分辨率', 'V. Resolution')} 
                            value={info.tech_params?.visual_standard?.vertical_resolution} 
                            onChange={v => updateTech('vertical_resolution', v)} 
                            placeholder="2160"
                            list={["2160", "1920", "1080", "720"]}
                        />
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('帧率', 'Frame Rate')} 
                            value={info.tech_params?.visual_standard?.frame_rate} 
                            onChange={v => updateTech('frame_rate', v)} 
                            list={["24", "30", "60"]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label={t('画幅比例', 'Aspect Ratio')} 
                            value={info.tech_params?.visual_standard?.aspect_ratio} 
                            onChange={v => updateTech('aspect_ratio', v)} 
                            list={["16:9", "2.35:1", "4:3", "9:16"]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label={t('质量等级', 'Quality')} 
                            value={info.tech_params?.visual_standard?.quality} 
                            onChange={v => updateTech('quality', v)} 
                            list={["Ultra High", "High", "Medium", "Low", "Draft"]} 
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('色调', 'Tone')} 
                            value={info.tone} 
                            onChange={v => updateField('tone', v)} 
                            multi={true}
                            list={[
                                "Cool", 
                                "Warm", 
                                "Neutral", 
                                "High Contrast", 
                                "Dark / Moody", 
                                "Dreamy", 
                                "Vibrant", 
                                "Desaturated", 
                                "Pastel", 
                                "Gritty",
                                "Skin Tone Optimized",
                                "Film Presence", 
                                "Muted Tones",
                                "Skin Tone Optimized, Dreamy",
                                "Film Presence, Muted Tones",
                                "Neutral, High Contrast",
                                "Dark / Moody, Gritty",
                                "Vibrant, High Contrast"
                            ]} 
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('光照', 'Lighting')} 
                            value={info.lighting} 
                            onChange={v => updateField('lighting', v)} 
                            multi={true}
                            list={[
                                "Natural Light", 
                                "Soft Light", 
                                "Hard Light", 
                                "Rim Light", 
                                "Rembrandt", 
                                "Neon / Cyber", 
                                "Cinematic", 
                                "Low Key", 
                                "High Key", 
                                "Volumetric",
                                "Butterfly Light",
                                "Studio Light",
                                "Golden Hour", 
                                "Window Light", 
                                "Split Light",
                                "Butterfly Light, Soft Light",
                                "Rembrandt, Volumetric",
                                "Cinematic, Rim Light, Volumetric",
                                "Studio Light, Hard Light",
                                "Natural Light, Window Light"
                            ]} 
                        />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('补充说明', 'Additional Notes')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={info.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder={t('其他需要补充的重要信息...', 'Any other important information...')}
                        />
                    </div>
                </div>

                {/* Story Generator (Global) */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('故事生成器（全局 / 项目）', 'Story Generator (Global / Project)')}</h3>
                        <div className="flex items-center gap-2">
                            <input
                                ref={storyPackageFileInputRef}
                                type="file"
                                accept="application/json,.json"
                                className="hidden"
                                onChange={handleImportStoryGeneratorPackageFile}
                            />
                            <button
                                onClick={handleOpenImportStoryGeneratorPackage}
                                disabled={isImportingStoryPackage || isGeneratingGlobalStory || isGeneratingEpisodeScripts || isAnalyzingNovel}
                                className={`px-3 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(isImportingStoryPackage || isGeneratingGlobalStory || isGeneratingEpisodeScripts || isAnalyzingNovel) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('从其他项目导入 Story Generator 包 JSON', 'Import Story Generator package JSON from another project')}
                            >
                                {isImportingStoryPackage ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('导入中...', 'Importing...')}</> : <><Upload className="w-4 h-4" /> {t('导入包', 'Import Package')}</>}
                            </button>
                            <button
                                onClick={handleExportStoryGeneratorPackage}
                                disabled={isGeneratingGlobalStory || isGeneratingEpisodeScripts || isAnalyzingNovel || isImportingStoryPackage}
                                className={`px-3 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(isGeneratingGlobalStory || isGeneratingEpisodeScripts || isAnalyzingNovel || isImportingStoryPackage) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('导出 Story Generator 包 JSON 用于导入其他项目', 'Export Story Generator package JSON for import into another project')}
                            >
                                <Download className="w-4 h-4" /> {t('导出包', 'Export Package')}
                            </button>
                            <button
                                onClick={() => setShowGlobalStoryGuide(v => !v)}
                                className="px-3 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                title={t('创作指引', 'Writing Guide')}
                            >
                                <Info className="w-4 h-4" /> {t('创作指引', 'Writing Guide')}
                            </button>
                            <button
                                onClick={handleGenerateGlobalStory}
                                disabled={isGeneratingGlobalStory}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingGlobalStory ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('生成国际化爆款故事框架并保存到项目总览', 'Generate an international-blockbuster story framework and store it in project Overview')}
                            >
                                {isGeneratingGlobalStory ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成全局框架', 'Generate Global Framework')}</>}
                            </button>

                            <button
                                onClick={handleGenerateEpisodeScripts}
                                disabled={isGeneratingEpisodeScripts || isGeneratingGlobalStory}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(isGeneratingEpisodeScripts || isGeneratingGlobalStory) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('从全局框架 + 项目角色设定生成分集剧本，自动创建缺失分集并写入对应分集', 'Generate episode scripts from Global Framework + Project Character Canon, create missing episodes, and save each script into its episode')}
                            >
                                {isGeneratingEpisodeScripts ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Wand2 className="w-4 h-4" /> {t('生成分集剧本', 'Generate Episode Scripts')}</>}
                            </button>
                            <button
                                onClick={() => handleGenerateEpisodeScripts({ forceStart: true })}
                                disabled={isGeneratingEpisodeScripts || isGeneratingGlobalStory}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(isGeneratingEpisodeScripts || isGeneratingGlobalStory) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('强制启动所有目标分集并覆盖已有剧本', 'Force start generation for all target episodes and overwrite existing scripts')}
                            >
                                {isGeneratingEpisodeScripts ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('执行中...', 'Running...')}</> : <><RefreshCw className="w-4 h-4" /> {t('强制启动剧本', 'Force Start Scripts')}</>}
                            </button>
                            <button
                                onClick={() => handleGenerateEpisodeScripts({ retryFailedOnly: true })}
                                disabled={isGeneratingEpisodeScripts || isGeneratingGlobalStory}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(isGeneratingEpisodeScripts || isGeneratingGlobalStory) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('仅重试上次运行失败的分集', 'Retry only failed episodes from the last run')}
                            >
                                {isGeneratingEpisodeScripts ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('执行中...', 'Running...')}</> : <><RefreshCw className="w-4 h-4" /> {t('重试失败分集', 'Retry Failed Episodes')}</>}
                            </button>
                        </div>
                    </div>

                    {episodeScriptsProgress && (
                        <div className="border border-white/10 rounded-lg p-3 bg-black/20 space-y-2">
                            <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('分集剧本进度快照', 'Episode Scripts Progress Snapshot')}</div>
                            <div className="h-2 rounded bg-white/10 overflow-hidden">
                                <div
                                    className="h-2 bg-primary"
                                    style={{ width: `${progressPercent}%` }}
                                />
                            </div>
                            <div className="text-sm text-white flex flex-wrap gap-x-4 gap-y-1">
                                <span>{t('状态', 'Status')}: <b>{episodeScriptsProgress.running ? t('运行中', 'Running') : t('空闲', 'Idle')}</b></span>
                                <span>{t('已处理', 'Processed')}: <b>{processedCount}</b> / <b>{episodesInRun}</b></span>
                                <span>{t('已生成', 'Generated')}: <b>{episodeScriptsProgress.generated || 0}</b></span>
                                <span>{t('失败', 'Failed')}: <b>{episodeScriptsProgress.failed || 0}</b></span>
                                <span>{t('跳过', 'Skipped')}: <b>{episodeScriptsProgress.skipped || 0}</b></span>
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                                <button
                                    onClick={() => setShowEpisodeScriptsProgressModal(true)}
                                    className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20"
                                >
                                    {t('查看详情', 'View Details')}
                                </button>
                                <button
                                    onClick={pollEpisodeScriptsStatus}
                                    className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-1.5"
                                >
                                    <RefreshCw className="w-3.5 h-3.5" /> {t('刷新', 'Refresh')}
                                </button>
                            </div>
                        </div>
                    )}

                    {showGlobalStoryGuide && (
                        <div className="border border-white/10 rounded-xl p-4 bg-white/[0.02] space-y-3">
                            <div className="text-sm font-semibold text-white">创作指引 / Writing Guide</div>
                            <div className="text-xs text-muted-foreground">
                                中文：按“从世界观 → 角色关系 → 冲突升级 → 关键转折 → 结局回收”的顺序填写；每个字段尽量写“可拍的具体信息”。
                                <br />
                                English: Fill in order “World → Character dynamics → Escalation → Turning points → Payoffs”. Prefer concrete, filmable details.
                            </div>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">流程介绍 / Workflow</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>
                                        中文（建议流程）：
                                        <ol className="list-decimal ml-4 mt-1 space-y-1">
                                            <li>先写 Background / World：世界规则、时代地点、核心矛盾来源。</li>
                                            <li>再写 Setup：开场钩子 + 诱因事件 + 主角做出不可逆选择。</li>
                                            <li>Development：障碍升级、信息揭露、情感推进，形成“必须继续”的链条。</li>
                                            <li>Turning Points：低谷/背叛/反转 + 最终策略（怎么打、付出什么代价）。</li>
                                            <li>Climax/Resolution：终极对决与代价、关系收束、伏笔回收。</li>
                                        </ol>
                                    </div>
                                    <div>
                                        English (suggested):
                                        <ol className="list-decimal ml-4 mt-1 space-y-1">
                                            <li>Background/World: rules, era, place, source of conflict.</li>
                                            <li>Setup: hook + inciting incident + irreversible choice.</li>
                                            <li>Development: escalating obstacles, reveals, emotional progression.</li>
                                            <li>Turning Points: lowest point + reversal + final plan (and cost).</li>
                                            <li>Climax/Resolution: final confrontation, payoff, new normal.</li>
                                        </ol>
                                    </div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Episodes Count（集数）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：你想要的总集数/章节数。短剧常见 10–24 集；越短越需要强钩子与快节奏升级。</div>
                                    <div>English: Total number of episodes/chapters. Shorter seasons need stronger hooks and faster escalation.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：12</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Foreshadowing / Payoffs（伏笔/回收）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：列出你想“提前埋下、后期回收”的清单：道具、秘密、旧伤、承诺、规则漏洞、未说出口的真相。</div>
                                    <div>English: A checklist of seeds to plant early and pay off later (props, secrets, promises, rule loopholes, hidden truths).</div>
                                    <div className="text-xs text-muted-foreground">
                                        样例 / Example：
                                        <br />1) 女主手腕旧伤 → 第6集搏斗触发失手
                                        <br />2) 男主从不喝酒 → 结局为她破例象征和解
                                    </div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Background / World（世界观/背景）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：写清楚“世界规则 + 时代地点 + 这个世界为什么会产生冲突”。最好包含：规则、资源、禁忌、权力结构。</div>
                                    <div>English: Define rules, time/place, and why conflict exists. Include constraints, resources, taboos, and power structure.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：近未来都市，记忆可交易；黑市记忆改写引发连环案与身份危机。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Setup (Hook / Inciting Incident)（开场/诱因）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：观众为什么要继续看？写“开场钩子 + 诱因事件 + 主角必须做选择”。</div>
                                    <div>English: Why keep watching? Give hook + inciting incident + forced choice.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：女主醒来发现记忆被卖掉；警方认定她是凶手，她只能追查买家。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Development (Escalation / Midpoint)（发展/升级）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：障碍如何升级？关系如何变化？中点给一个重大揭露或立场反转。</div>
                                    <div>English: How do obstacles escalate and relationships change? Add a midpoint reveal or reversal.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：发现买家是男主；他却在保护她，因为她记忆里藏着更大的真相。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Turning Points (Low Point / Strategy)（转折/低谷/策略）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：主角遭遇“最糟时刻”（失败/背叛/代价），然后提出最终策略：怎么赢、要牺牲什么。</div>
                                    <div>English: The lowest point, then the final strategy—how to win and what it costs.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：男主身份暴露被追杀；二人决定用公开直播交换证据，逼幕后现身。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Climax（高潮）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：终极对抗发生在哪里？关键选择是什么？代价是什么？尽量写“可拍”的动作与情绪爆点。</div>
                                    <div>English: Where is the final confrontation, what is the key choice, and what is the cost? Keep it filmable.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：天台对峙；女主选择公开真相毁掉自己名誉换取他人安全。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Resolution（结局/回收）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：冲突如何收束？关系如何落点？哪些伏笔被回收？最后留什么余味/下一季种子（可选）。</div>
                                    <div>English: How does conflict close, what’s the relationship end-state, which seeds are paid off, and what lingering hook remains?</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：真相曝光，黑市被清剿；女主保留一段空白记忆，暗示更深阴谋未完。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Suspense / Cliffhanger Engine（悬念引擎）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：用一句话描述“每集结束怎么让观众点下一集”：秘密、误会、延迟危险、倒计时、身份揭露。</div>
                                    <div>English: The mechanism that pushes viewers to the next episode: secrets, delayed danger, countdowns, reveals.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：每集末尾解锁一段新记忆，指向下一个嫌疑人。</div>
                                </div>
                            </details>

                            <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                <summary className="cursor-pointer text-sm text-white font-semibold">Extra Notes（额外偏好/约束）</summary>
                                <div className="mt-2 text-xs text-white/80 space-y-2">
                                    <div>中文：风格偏好、禁忌清单、尺度、镜头语言、叙事节奏、想要的反转类型。</div>
                                    <div>English: Preferences and constraints: tone, taboos, rating boundaries, visual language, pacing, twist style.</div>
                                    <div className="text-xs text-muted-foreground">样例 / Example：节奏快、每集至少一个反转；情感线克制但高张力；避免血腥描写。</div>
                                </div>
                            </details>
                        </div>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('导入小说 / 剧本文本', 'Import Novel / Script Text')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-32 resize-y"
                                value={novelImportText}
                                onChange={(e) => setNovelImportText(e.target.value)}
                                placeholder={t('将小说/剧本文本粘贴到这里，然后点击“分析并填充”自动补全全局故事字段。', 'Paste novel/script text here, then click Analyze & Fill to auto-complete Global Story fields.')}
                            />
                            <div className="mt-2 flex items-center justify-end">
                                <button
                                    onClick={handleAnalyzeNovelToGlobalStory}
                                    disabled={isAnalyzingNovel || isGeneratingGlobalStory}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(isAnalyzingNovel || isGeneratingGlobalStory) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                    title={t('用 LLM 分析导入文本并自动填充故事生成字段', 'Analyze imported text with LLM and auto-fill Story Generator fields')}
                                >
                                    {isAnalyzingNovel ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('分析中...', 'Analyzing...')}</> : <><Upload className="w-4 h-4" /> {t('分析并填充', 'Analyze & Fill')}</>}
                                </button>
                            </div>
                        </div>

                        <div>
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('集数', 'Episodes Count')}</label>
                            <input
                                type="number"
                                min="1"
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                value={globalStoryInput.episodes_count}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, episodes_count: e.target.value }))}
                                placeholder={t('例如：12', 'e.g. 12')}
                            />
                        </div>
                        <div>
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('伏笔 / 回收', 'Foreshadowing / Payoffs')}</label>
                            <input
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                value={globalStoryInput.foreshadowing}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, foreshadowing: e.target.value }))}
                                placeholder={t('伏笔、揭示与回收目标', 'Seeds, reveals, payoff targets')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('背景 / 世界观', 'Background / World')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.background}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, background: e.target.value }))}
                                placeholder={t('世界规则、时代地点、驱动冲突的背景设定', 'World rules, era, location, backstory that drives conflict')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('开场（钩子 / 诱因事件）', 'Setup (Hook / Inciting Incident)')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.setup}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, setup: e.target.value }))}
                                placeholder={t('开场钩子、诱因事件、不可回头的选择', 'Opening hook, inciting incident, point-of-no-return decision')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('发展（升级 / 中点）', 'Development (Escalation / Midpoint)')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.development}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, development: e.target.value }))}
                                placeholder={t('障碍升级、信息揭示、中点反转', 'Obstacle escalation, reveals, midpoint reversal')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('转折点（低谷 / 策略）', 'Turning Points (Low Point / Strategy)')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.turning_points}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, turning_points: e.target.value }))}
                                placeholder={t('第二次重大转折、至暗时刻、最终计划', 'Second major turn, all-is-lost, final plan')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('高潮', 'Climax')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.climax}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, climax: e.target.value }))}
                                placeholder={t('最终对抗、关键选择、代价', 'Final confrontation, key choice, cost')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('结局回收', 'Resolution')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.resolution}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, resolution: e.target.value }))}
                                placeholder={t('结局收束与新常态', 'Denouement, new normal')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('悬念 / 钩子引擎', 'Suspense / Cliffhanger Engine')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.suspense}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, suspense: e.target.value }))}
                                placeholder={t('谜团/秘密、延迟危险、结尾钩子、季级伏笔', 'Mystery/secret, delayed danger, end hooks, season seeds')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('额外说明', 'Extra Notes')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={globalStoryInput.extra_notes}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, extra_notes: e.target.value }))}
                                placeholder={t('风格、约束、禁忌清单、反转类型、节奏偏好', 'Tone, constraints, taboo list, twist style, pacing preference')}
                            />
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('已生成全局框架（Markdown）', 'Generated Global Framework (Markdown)')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-48 resize-none"
                            value={info.story_dna_global_md || ''}
                            onChange={(e) => updateField('story_dna_global_md', e.target.value)}
                            placeholder={t('（生成后，全局框架会显示在这里。你可以编辑后保存修改。）', '(After generation, the global framework will appear here. You can edit it and Save Changes.)')}
                        />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('全局风格与约束（提取结果）', 'Global Style & Constraints (Extracted)')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white w-full h-40 resize-none"
                            value={info.global_style_constraints ? JSON.stringify(info.global_style_constraints, null, 2) : ''}
                            readOnly
                            placeholder={t('（生成后，这里会显示提取出的全局风格与硬性约束。）', '(After generation, extracted global style & hard constraints will appear here.)')}
                        />
                    </div>
                </div>

                {/* Character Canon (Project) */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('角色设定集（项目）', 'Character Canon (Project)')}</h3>
                        <button
                            onClick={() => setShowCanonModal(true)}
                            disabled={isGeneratingCanon}
                            className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingCanon ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                            title={t('生成权威角色档案并追加到项目级角色设定集', 'Generate an authoritative character profile and append it to the project-level canon')}
                        >
                            {isGeneratingCanon ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成并追加', 'Generate & Append')}</>}
                        </button>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('设定集输出（Markdown）', 'Canon Output (Markdown)')}</label>
                        <div className="space-y-3">
                            {Array.isArray(info.character_profiles) && info.character_profiles.length > 0 ? (
                                info.character_profiles.map((p, idx) => {
                                    const name = String(p?.name || '').trim() || `${t('角色', 'Character')} ${idx + 1}`;
                                    const md = String(p?.description_md || '').trim();
                                    const updatedAt = String(p?.updated_at || '').trim();
                                    return (
                                        <div key={`${name}-${idx}`} className="bg-black/20 border border-white/10 rounded-lg p-3 space-y-2">
                                            <div className="flex items-center justify-between gap-3">
                                                <div>
                                                    <div className="text-sm font-bold text-white">{name}</div>
                                                    {updatedAt ? (
                                                        <div className="text-xs text-muted-foreground">{t('更新时间', 'Updated')}: {updatedAt}</div>
                                                    ) : null}
                                                </div>
                                                {String(p?.name || '').trim() ? (
                                                    <button
                                                        onClick={() => handleDeleteCanonCharacter(String(p.name))}
                                                        className="px-2 py-1 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                                        title={t('从设定集中删除该角色', 'Delete this character from canon')}
                                                    >
                                                        <Trash2 size={14} /> {t('删除', 'Delete')}
                                                    </button>
                                                ) : null}
                                            </div>
                                            <textarea
                                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white w-full h-40 resize-none"
                                                value={md || ''}
                                                readOnly
                                                placeholder={t('（生成后，该角色的设定 Markdown 会显示在这里。）', "(This character's canonical markdown will appear here after generation.)")}
                                            />
                                        </div>
                                    );
                                })
                            ) : (
                                <textarea
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white w-full h-28 resize-none"
                                    value={''}
                                    readOnly
                                    placeholder={t('（暂无角色。点击“生成并追加”创建首个角色设定。）', '(No characters yet. Click Generate & Append to create the first canon profile.)')}
                                />
                            )}
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('角色关系（纯文本）', 'Character Relationships (Plain Text)')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-28 resize-none"
                            value={info.character_relationships || ''}
                            onChange={(e) => updateField('character_relationships', e.target.value)}
                            placeholder={t('示例：A 是 B 的上司；B 暗恋 C；C 是 A 的对手...', "Example: A is B's boss; B secretly loves C; C is A's rival...")}
                        />
                    </div>
                </div>
            </div>

            {showEpisodeScriptsProgressModal && (
                <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setShowEpisodeScriptsProgressModal(false)}>
                    <div className="bg-[#0f0f10] border border-white/10 rounded-xl w-full max-w-6xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
                        <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between gap-3">
                            <div>
                                <h3 className="text-lg font-semibold text-primary">{t('分集剧本进度中心', 'Episode Scripts Progress Center')}</h3>
                                <div className="text-xs text-muted-foreground">
                                    {t('实时跟踪每个分集并查看生成结果。', 'Track each episode in real time and review generation results.')}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={pollEpisodeScriptsStatus}
                                    className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-1.5"
                                >
                                    <RefreshCw className="w-3.5 h-3.5" /> {t('刷新', 'Refresh')}
                                </button>
                                <button
                                    className="p-2 rounded-md hover:bg-white/10 text-white/80"
                                    onClick={() => setShowEpisodeScriptsProgressModal(false)}
                                    title={t('关闭', 'Close')}
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        <div className="p-5 space-y-4 overflow-y-auto max-h-[calc(90vh-80px)]">
                            {episodeScriptsProgress ? (
                                <>
                                    <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-sm">
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('模式', 'Mode')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.mode || 'full'}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('状态', 'Status')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.running ? t('运行中', 'Running') : t('空闲', 'Idle')}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('已处理', 'Processed')}</div>
                                            <div className="font-bold text-white">{processedCount} / {episodesInRun}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('已生成', 'Generated')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.generated || 0}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('失败', 'Failed')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.failed || 0}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('跳过', 'Skipped')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.skipped || 0}</div>
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                                            <span>{t('总体进度', 'Overall Progress')}</span>
                                            <span>{progressPercent}%</span>
                                        </div>
                                        <div className="h-2 rounded bg-white/10 overflow-hidden">
                                            <div className="h-2 bg-primary" style={{ width: `${progressPercent}%` }} />
                                        </div>
                                    </div>

                                    {failedEpisodeRows.length > 0 && (
                                        <div className="border border-red-500/30 rounded-lg p-3 bg-red-500/10">
                                            <div className="text-xs text-red-200 mb-2">{t('失败分集（点击跳转）', 'Failed Episodes (click to jump)')}</div>
                                            <div className="flex flex-wrap gap-2">
                                                {failedEpisodeRows.map((item, idx) => (
                                                    <button
                                                        key={`${item.episode_id}_${idx}`}
                                                        onClick={() => {
                                                            if (onJumpToEpisode && item.episode_id) onJumpToEpisode(item.episode_id);
                                                        }}
                                                        className="px-2 py-1 rounded text-xs bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-100"
                                                        title={item.error || t('跳转到分集', 'Jump to episode')}
                                                    >
                                                        {buildEpisodeDisplayLabel({
                                                            episodeNumber: item?.episode_number,
                                                            title: item?.episode_title,
                                                            fallbackNumber: Number(item?.episode_number || 0) || null,
                                                        })}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <div className="border border-white/10 rounded-lg overflow-hidden">
                                        <div className="grid grid-cols-12 bg-white/5 text-xs text-muted-foreground px-3 py-2">
                                            <div className="col-span-1">#</div>
                                            <div className="col-span-4">{t('分集', 'Episode')}</div>
                                            <div className="col-span-2">{t('状态', 'Status')}</div>
                                            <div className="col-span-3">{t('结果', 'Result')}</div>
                                            <div className="col-span-2 text-right">{t('操作', 'Action')}</div>
                                        </div>
                                        <div className="max-h-[38vh] overflow-y-auto">
                                            {episodeResultRows.length > 0 ? episodeResultRows.map((row, idx) => {
                                                const status = String(row?.status || 'pending');
                                                const statusClass =
                                                    status === 'generated'
                                                        ? 'bg-green-500/20 text-green-200 border-green-500/30'
                                                        : status === 'failed'
                                                            ? 'bg-red-500/20 text-red-200 border-red-500/30'
                                                            : status === 'skipped'
                                                                ? 'bg-yellow-500/20 text-yellow-200 border-yellow-500/30'
                                                                : 'bg-white/10 text-white/80 border-white/20';
                                                const resultText = row?.error || row?.reason || (row?.output_chars ? `${row.output_chars} ${t('字符', 'chars')}` : (status === 'pending' ? t('等待中', 'Waiting') : '-'));
                                                const statusLabel =
                                                    status === 'generated'
                                                        ? t('已生成', 'Generated')
                                                        : status === 'failed'
                                                            ? t('失败', 'Failed')
                                                            : status === 'skipped'
                                                                ? t('跳过', 'Skipped')
                                                                : status === 'pending'
                                                                    ? t('待处理', 'Pending')
                                                                    : status;
                                                return (
                                                    <div key={`${row?.episode_number || idx}_${idx}`} className="grid grid-cols-12 px-3 py-2 text-sm border-t border-white/5 items-center">
                                                        <div className="col-span-1 text-white/90">{row?.episode_number || '-'}</div>
                                                        <div
                                                            className="col-span-4 text-white/90 truncate"
                                                            title={buildEpisodeDisplayLabel({
                                                                episodeNumber: row?.episode_number,
                                                                title: row?.episode_title,
                                                                fallbackNumber: Number(row?.episode_number || 0) || null,
                                                            })}
                                                        >
                                                            {buildEpisodeDisplayLabel({
                                                                episodeNumber: row?.episode_number,
                                                                title: row?.episode_title,
                                                                fallbackNumber: Number(row?.episode_number || 0) || null,
                                                            })}
                                                        </div>
                                                        <div className="col-span-2">
                                                            <span className={`px-2 py-0.5 rounded text-xs border ${statusClass}`}>{statusLabel}</span>
                                                        </div>
                                                        <div className="col-span-3 text-xs text-white/70 truncate" title={resultText}>{resultText}</div>
                                                        <div className="col-span-2 text-right">
                                                            {row?.episode_id ? (
                                                                <button
                                                                    onClick={() => onJumpToEpisode && onJumpToEpisode(row.episode_id)}
                                                                    className="px-2 py-1 rounded text-xs bg-white/10 text-white hover:bg-white/20"
                                                                >
                                                                    {t('打开', 'Open')}
                                                                </button>
                                                            ) : (
                                                                <span className="text-xs text-white/40">-</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            }) : (
                                                <div className="px-3 py-6 text-center text-sm text-muted-foreground">{t('暂无分集运行记录。', 'No episode run records yet.')}</div>
                                            )}
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="text-sm text-muted-foreground py-10 text-center">
                                    {t('暂无生成状态。点击“生成分集剧本”开始跟踪。', 'No generation status yet. Start “Generate Episode Scripts” to begin tracking.')}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {showCanonModal && (
                <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
                    <div className="bg-[#0f0f10] border border-white/10 rounded-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto custom-scrollbar">
                        <div className="p-6 space-y-5">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-semibold text-primary">{t('角色设定集（项目）', 'Character Canon (Project)')}</h3>
                                    <div className="text-xs text-muted-foreground">选择身份标签 + 外观/风格标签，生成后会追加到项目 Canon。</div>
                                </div>
                                <button
                                    className="p-2 rounded-md hover:bg-white/10 text-white/80"
                                    onClick={closeCanonModal}
                                    title={t('关闭', 'Close')}
                                >
                                    <X size={18} />
                                </button>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">角色名称</label>
                                    <input
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                        value={canonName}
                                        onChange={(e) => setCanonName(e.target.value)}
                                        placeholder="例如：林娜 / Lina"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">自定义身份（可选，逗号/换行分隔）</label>
                                    <input
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                        value={canonCustomIdentity}
                                        onChange={(e) => setCanonCustomIdentity(e.target.value)}
                                        placeholder="例如：失忆 / 黑客 / 继承人"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">身材/体态/身体特征（可选）</label>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-16 resize-none"
                                        value={canonBody}
                                        onChange={(e) => setCanonBody(e.target.value)}
                                        placeholder="例如：高挑、肩颈线清晰、走路很稳、短发…"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">自定义风格标签（可选，逗号/换行分隔）</label>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-16 resize-none"
                                        value={canonCustomTags}
                                        onChange={(e) => setCanonCustomTags(e.target.value)}
                                        placeholder="例如：冷艳、黑西装、琥珀眼、雨夜霓虹…"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">额外备注（可选）</label>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                        value={canonExtra}
                                        onChange={(e) => setCanonExtra(e.target.value)}
                                        placeholder="例如：镜头表现、禁忌、语气/动作习惯…"
                                    />
                                </div>
                            </div>

                            <div className="flex items-center justify-between gap-3">
                                <div className="text-sm text-white/80">身份标签</div>
                                <button
                                    className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-2 ${canonTagEditMode ? 'bg-primary text-black' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                    onClick={() => setCanonTagEditMode(v => !v)}
                                    title={t('切换分类编辑模式', 'Toggle edit mode for categories')}
                                >
                                    <Edit3 className="w-3.5 h-3.5" /> {canonTagEditMode ? '编辑中' : '编辑标签'}
                                </button>
                            </div>

                            <div className="space-y-4">
                                {(canonIdentityCategories || []).map(cat => (
                                    <div key={cat.key} className="border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        <div className="flex items-center justify-between gap-3 mb-3">
                                            {canonTagEditMode ? (
                                                <input
                                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                    value={cat.title}
                                                    onChange={(e) => updateIdentityCategoryTitle(cat.key, e.target.value)}
                                                />
                                            ) : (
                                                <div className="text-sm font-semibold text-white">{cat.title}</div>
                                            )}
                                            {canonTagEditMode && (
                                                <button
                                                    className="px-3 py-2 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                                    onClick={() => addIdentityOption(cat.key)}
                                                >
                                                    <Plus size={14} /> 新增
                                                </button>
                                            )}
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {(cat.options || []).map(opt => {
                                                const selected = canonSelectedIdentityIds.includes(opt.id);
                                                return (
                                                    <div key={opt.id} className={`border rounded-lg p-3 flex gap-3 ${selected ? 'border-primary/60 bg-primary/10' : 'border-white/10 bg-black/20'}`}>
                                                        <button
                                                            className="flex-1 text-left"
                                                            onClick={() => !canonTagEditMode && toggleCanonIdentityId(opt.id)}
                                                            title={canonTagEditMode ? '编辑模式下不可选择' : '点击选择'}
                                                        >
                                                            {canonTagEditMode ? (
                                                                <div className="space-y-2">
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.label}
                                                                        onChange={(e) => updateIdentityOption(cat.key, opt.id, { label: e.target.value })}
                                                                    />
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs text-white/90 focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.detail}
                                                                        onChange={(e) => updateIdentityOption(cat.key, opt.id, { detail: e.target.value })}
                                                                    />
                                                                </div>
                                                            ) : (
                                                                <>
                                                                    <div className="text-sm font-semibold text-white flex items-center gap-2">
                                                                        {selected ? <Check size={16} className="text-primary" /> : <span className="w-4" />}
                                                                        {opt.label}
                                                                    </div>
                                                                    <div className="text-xs text-white/60 mt-1">{opt.detail}</div>
                                                                </>
                                                            )}
                                                        </button>

                                                        {canonTagEditMode && (
                                                            <button
                                                                className="p-2 rounded-md hover:bg-white/10 text-white/70"
                                                                onClick={() => removeIdentityOption(cat.key, opt.id)}
                                                                title={t('删除', 'Delete')}
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="text-sm text-white/80">外观/风格标签</div>

                            <div className="space-y-4">
                                {(canonTagCategories || []).map(cat => (
                                    <div key={cat.key} className="border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        <div className="flex items-center justify-between gap-3 mb-3">
                                            {canonTagEditMode ? (
                                                <input
                                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                    value={cat.title}
                                                    onChange={(e) => updateCanonCategoryTitle(cat.key, e.target.value)}
                                                />
                                            ) : (
                                                <div className="text-sm font-semibold text-white">{cat.title}</div>
                                            )}
                                            {canonTagEditMode && (
                                                <button
                                                    className="px-3 py-2 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                                    onClick={() => addCanonOption(cat.key)}
                                                >
                                                    <Plus size={14} /> 新增
                                                </button>
                                            )}
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {(cat.options || []).map(opt => {
                                                const selected = canonSelectedTagIds.includes(opt.id);
                                                return (
                                                    <div key={opt.id} className={`border rounded-lg p-3 flex gap-3 ${selected ? 'border-primary/60 bg-primary/10' : 'border-white/10 bg-black/20'}`}>
                                                        <button
                                                            className="flex-1 text-left"
                                                            onClick={() => !canonTagEditMode && toggleCanonTagId(opt.id)}
                                                            title={canonTagEditMode ? '编辑模式下不可选择' : '点击选择'}
                                                        >
                                                            {canonTagEditMode ? (
                                                                <div className="space-y-2">
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.label}
                                                                        onChange={(e) => updateCanonOption(cat.key, opt.id, { label: e.target.value })}
                                                                    />
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs text-white/90 focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.detail}
                                                                        onChange={(e) => updateCanonOption(cat.key, opt.id, { detail: e.target.value })}
                                                                    />
                                                                </div>
                                                            ) : (
                                                                <>
                                                                    <div className="text-sm font-semibold text-white flex items-center gap-2">
                                                                        {selected ? <Check size={16} className="text-primary" /> : <span className="w-4" />}
                                                                        {opt.label}
                                                                    </div>
                                                                    <div className="text-xs text-white/60 mt-1">{opt.detail}</div>
                                                                </>
                                                            )}
                                                        </button>
                                                        {canonTagEditMode && (
                                                            <button
                                                                className="p-2 rounded-md hover:bg-white/10 text-white/70"
                                                                onClick={() => removeCanonOption(cat.key, opt.id)}
                                                                title={t('删除', 'Delete')}
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="flex items-center justify-end gap-2 pt-2">
                                {canonTagEditMode && (
                                    <button
                                        className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20"
                                        onClick={async () => {
                                            const normalizedTags = normalizeCanonTagCategories(canonTagCategories);
                                            const normalizedIdentity = normalizeCanonTagCategories(canonIdentityCategories);
                                            const ok1 = normalizedTags ? persistCanonTagCategories(normalizedTags) : false;
                                            const ok2 = normalizedIdentity ? persistCanonIdentityCategories(normalizedIdentity) : false;
                                            let okDb = true;
                                            try {
                                                if (!id) throw new Error('Missing project id');
                                                if (!normalizedTags || !normalizedIdentity) throw new Error('Invalid categories');
                                                await saveProjectCharacterCanonCategories(id, {
                                                    tag_categories: normalizedTags,
                                                    identity_categories: normalizedIdentity,
                                                });
                                            } catch (e) {
                                                okDb = false;
                                                console.error('[Character Canon Categories] Save failed:', e);
                                            }
                                            alert(ok1 && ok2 && okDb ? t('已保存标签配置（数据库+localStorage）', 'Tag configuration saved (database + localStorage)') : t('保存失败', 'Save failed'));
                                        }}
                                    >
                                        <Save className="w-4 h-4 inline-block mr-2" /> {t('保存标签配置', 'Save Tag Configuration')}
                                    </button>
                                )}
                                <button
                                    className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20"
                                    onClick={closeCanonModal}
                                    disabled={isGeneratingCanon}
                                >
                                    {t('关闭', 'Close')}
                                </button>
                                <button
                                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingCanon ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary text-black hover:bg-primary/90'}`}
                                    onClick={handleGenerateProjectCanon}
                                    disabled={isGeneratingCanon}
                                >
                                    {isGeneratingCanon ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成并追加', 'Generate & Append')}</>}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};



const EpisodeInfo = ({ episode, onUpdate, project, projectId, uiLang = 'en' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [info, setInfo] = useState({
        e_global_info: {
            script_title: "",
            series_episode: "",
            base_positioning: "Modern Workplace",
            type: "Live Action (Realism/Cinematic 8K)",
            Global_Style: "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
            tech_params: {
                visual_standard: {
                    horizontal_resolution: "3840",
                    vertical_resolution: "2160",
                    frame_rate: "24",
                    aspect_ratio: "9:16",
                    quality: "Ultra High"
                }
            },
            tone: "Skin Tone Optimized, Dreamy",
            lighting: "",
            language: "English",
            borrowed_films: ["King Kong (2005)", "Joker (2019)", "The Truman Show"],
            notes: ""
        },
        story_dna_episode_md: "",
        story_dna_episode_number: 1,
    });

    const [episodeStoryInput, setEpisodeStoryInput] = useState({
        episode_number: 1,
        background: "",
        setup: "",
        development: "",
        turning_points: "",
        climax: "",
        resolution: "",
        suspense: "",
        foreshadowing: "",
        extra_notes: "",
    });
    const [isGeneratingEpisodeStory, setIsGeneratingEpisodeStory] = useState(false);
    const episodeStoryAutosaveTimerRef = useRef(null);
    const skipNextEpisodeStoryAutosaveRef = useRef(true);

    useEffect(() => {
        if (episode) {
             const loaded = episode.episode_info || {};
             
             // Ensure structure exists even if loaded data is partial
             const merged = {
                 e_global_info: {
                     ...info.e_global_info, // default structure
                     ...(loaded.e_global_info || {}), // loaded data
                 }
                 ,
                 story_dna_episode_md: loaded.story_dna_episode_md || info.story_dna_episode_md || "",
                 story_dna_episode_number: loaded.story_dna_episode_number || info.story_dna_episode_number || 1,
             };

             // Deep merge tech_params if they exist
             if (loaded.e_global_info?.tech_params?.visual_standard) {
                 merged.e_global_info.tech_params = {
                     ...merged.e_global_info.tech_params,
                     visual_standard: {
                         ...merged.e_global_info.tech_params.visual_standard,
                         ...loaded.e_global_info.tech_params.visual_standard
                     }
                 };
             }
             
             setInfo(merged);

             // Restore Story Generator (Episode) draft inputs (if previously saved)
             if (loaded.story_generator_episode_input && typeof loaded.story_generator_episode_input === 'object') {
                 const draft = loaded.story_generator_episode_input;
                 const draftEpisodeNumber = draft.episode_number ?? loaded.story_dna_episode_number ?? 1;
                 setEpisodeStoryInput(prev => ({
                     ...prev,
                     ...draft,
                     episode_number: draftEpisodeNumber,
                 }));
             } else {
                 // best-effort default for generator episode_number from stored field
                 const epNum = loaded.story_dna_episode_number || 1;
                 setEpisodeStoryInput(prev => ({ ...prev, episode_number: epNum }));
             }

             // Avoid immediately auto-saving right after hydration
             skipNextEpisodeStoryAutosaveRef.current = true;
        }
    }, [episode]);

    // Auto-save Episode Story Generator draft inputs (debounced)
    useEffect(() => {
        if (!episode?.id) return;

        if (skipNextEpisodeStoryAutosaveRef.current) {
            skipNextEpisodeStoryAutosaveRef.current = false;
            return;
        }

        if (episodeStoryAutosaveTimerRef.current) {
            clearTimeout(episodeStoryAutosaveTimerRef.current);
        }

        episodeStoryAutosaveTimerRef.current = setTimeout(async () => {
            try {
                const payload = {
                    mode: 'episode',
                    episode_number: Number(episodeStoryInput.episode_number || 0) || undefined,
                    background: episodeStoryInput.background,
                    setup: episodeStoryInput.setup,
                    development: episodeStoryInput.development,
                    turning_points: episodeStoryInput.turning_points,
                    climax: episodeStoryInput.climax,
                    resolution: episodeStoryInput.resolution,
                    suspense: episodeStoryInput.suspense,
                    foreshadowing: episodeStoryInput.foreshadowing,
                    extra_notes: episodeStoryInput.extra_notes,
                };
                await saveEpisodeStoryGeneratorInput(episode.id, payload);
            } catch (e) {
                // Silent failure: avoid interrupting typing UX
                console.error('[Episode Story Generator] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (episodeStoryAutosaveTimerRef.current) {
                clearTimeout(episodeStoryAutosaveTimerRef.current);
            }
        };
    }, [episode?.id, episodeStoryInput]);

    const handleGenerateEpisodeStory = async () => {
        if (!episode?.id) return;
        setIsGeneratingEpisodeStory(true);
        try {
            const payload = {
                mode: 'episode',
                episode_number: Number(episodeStoryInput.episode_number || 0),
                background: episodeStoryInput.background,
                setup: episodeStoryInput.setup,
                development: episodeStoryInput.development,
                turning_points: episodeStoryInput.turning_points,
                climax: episodeStoryInput.climax,
                resolution: episodeStoryInput.resolution,
                suspense: episodeStoryInput.suspense,
                foreshadowing: episodeStoryInput.foreshadowing,
                extra_notes: episodeStoryInput.extra_notes,
            };
            const updatedEpisode = await generateEpisodeStory(episode.id, payload);
            const updatedInfo = updatedEpisode?.episode_info || {};
            setInfo(prev => ({
                ...prev,
                story_dna_episode_md: updatedInfo.story_dna_episode_md || prev.story_dna_episode_md,
                story_dna_episode_number: updatedInfo.story_dna_episode_number || prev.story_dna_episode_number,
            }));
            alert('Episode story outline generated and saved to Ep. Info.');
        } catch (e) {
            console.error(e);
            alert(`Failed to generate episode story: ${e.message}`);
        } finally {
            setIsGeneratingEpisodeStory(false);
        }
    };

    const handleSave = async () => {
        try {
            await onUpdate(episode.id, { episode_info: info });
            alert("Episode global info saved!");
        } catch (e) {
            console.error("Failed to save", e);
            alert(`Failed to save: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleSyncFromProjectOverview = async () => {
        const isNonEmptyValue = (value) => {
            if (value === null || value === undefined) return false;
            if (typeof value === 'string') return value.trim() !== '';
            if (Array.isArray(value)) return value.length > 0;
            if (typeof value === 'object') return Object.keys(value).length > 0;
            return true;
        };

        const keepNonEmptyFields = (obj = {}) => {
            return Object.fromEntries(
                Object.entries(obj).filter(([_, value]) => isNonEmptyValue(value))
            );
        };

        let source = project?.global_info;
        if (projectId) {
            try {
                const latestProject = await fetchProject(projectId);
                if (latestProject?.global_info && typeof latestProject.global_info === 'object') {
                    source = latestProject.global_info;
                }
            } catch (e) {
                console.warn('Failed to fetch latest project before sync, using local project cache.', e);
            }
        }

        if (!source || typeof source !== 'object') {
            alert("No Project Overview data found to sync.");
            return;
        }

        const sourceTechParams = source.tech_params && typeof source.tech_params === 'object'
            ? source.tech_params
            : {};
        const sourceVisualStandard = sourceTechParams.visual_standard && typeof sourceTechParams.visual_standard === 'object'
            ? sourceTechParams.visual_standard
            : {};

        const sourceGlobalInfo = keepNonEmptyFields(source);
        const sourceTechParamsNonEmpty = keepNonEmptyFields(sourceTechParams);
        const sourceVisualStandardNonEmpty = keepNonEmptyFields(sourceVisualStandard);

        const mappedVisualStandard = keepNonEmptyFields({
            horizontal_resolution: sourceVisualStandardNonEmpty.horizontal_resolution ?? source.horizontal_resolution,
            vertical_resolution: sourceVisualStandardNonEmpty.vertical_resolution ?? source.vertical_resolution,
            frame_rate: sourceVisualStandardNonEmpty.frame_rate ?? source.frame_rate,
            aspect_ratio: sourceVisualStandardNonEmpty.aspect_ratio ?? source.aspect_ratio,
            quality: sourceVisualStandardNonEmpty.quality ?? source.quality,
        });

        const mappedTone = isNonEmptyValue(source.tone)
            ? source.tone
            : (isNonEmptyValue(source.mood) ? source.mood : undefined);
        const mappedLighting = isNonEmptyValue(source.lighting)
            ? source.lighting
            : (isNonEmptyValue(source.light) ? source.light : undefined);

        const nextGlobalInfo = {
            ...info.e_global_info,
            ...sourceGlobalInfo,
            ...(mappedTone !== undefined ? { tone: mappedTone } : {}),
            ...(mappedLighting !== undefined ? { lighting: mappedLighting } : {}),
            tech_params: {
                ...info.e_global_info.tech_params,
                ...sourceTechParamsNonEmpty,
                visual_standard: {
                    ...info.e_global_info.tech_params?.visual_standard,
                    ...sourceVisualStandardNonEmpty,
                    ...mappedVisualStandard,
                },
            },
        };

        const nextInfo = {
            ...info,
            e_global_info: nextGlobalInfo,
        };

        setInfo(nextInfo);

        try {
            await onUpdate(episode.id, { episode_info: nextInfo });
            alert("Synced from Project Overview.");
        } catch (e) {
            console.error("Failed to sync from project overview", e);
            alert("Sync failed. Please try again.");
        }
    };

    const updateField = (key, value) => {
        setInfo(prev => ({
            ...prev,
            e_global_info: {
                ...prev.e_global_info,
                [key]: value
            }
        }));
    };

    const updateTech = (key, value) => {
        setInfo(prev => ({
            ...prev,
            e_global_info: {
                ...prev.e_global_info,
                tech_params: {
                    ...prev.e_global_info.tech_params,
                    visual_standard: {
                        ...prev.e_global_info.tech_params.visual_standard,
                        [key]: value
                    }
                }
            }
        }));
    };
    
    const handleBorrowedFilmsChange = (str) => {
        const arr = str.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        updateField('borrowed_films', arr);
    };

    if (!episode) return <div className="p-8 text-muted-foreground">{t('请选择分集以查看信息。', 'Select an episode to view info.')}</div>;

    const data = info.e_global_info;
    const prefix = "ep-";

    return (
        <div className="p-4 sm:p-6 lg:p-8 w-full h-full overflow-y-auto">
             <div className="flex justify-between items-center mb-8">
                <h2 className="text-2xl font-bold">{t('分集全局信息', 'Episode Global Info')}</h2>
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleSyncFromProjectOverview}
                        className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={!projectId && !project?.global_info}
                    >
                        <RefreshCw className="w-4 h-4" /> {t('从项目总览同步', 'Sync from Project Overview')}
                    </button>
                    <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                        <SettingsIcon className="w-4 h-4" /> {t('保存修改', 'Save Changes')}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 w-full">
                 {/* Basic Info */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">{t('基本信息', 'Basic Information')}</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix} label={t('剧本标题', 'Script Title')} value={data.script_title} onChange={v => updateField('script_title', v)} placeholder={t('分集剧本标题', 'Episode Script Title')} />
                        <InputGroup idPrefix={prefix} label={t('系列/分集', 'Series/Episode')} value={data.series_episode} onChange={v => updateField('series_episode', v)} placeholder={t('例如：S01E01', 'e.g. S01E01')} />
                    </div>

                    <InputGroup idPrefix={prefix}
                        label={t('基础定位', 'Base Positioning')} 
                        value={data.base_positioning} 
                        onChange={v => updateField('base_positioning', v)} 
                        list={["Urban Romance", "Sci-Fi Adventure", "Mystery / Thriller", "Period / Wuxia", "Fantasy Epic", "Modern Workplace", "High School / Youth", "Cyberpunk", "Horror", "Comedy", "Drama", "Action", "Historical"]}
                        placeholder={t('例如：悬疑 / 惊悚', 'e.g. Mystery / Thriller')}
                    />
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('类型', 'Type')} 
                            value={data.type} 
                            onChange={v => updateField('type', v)} 
                            list={[
                                "Live Action", 
                                "Live Action (Realism/Cinematic 8K)",
                                "2D Animation", 
                                "3D Animation", 
                                "Stop Motion", 
                                "Tokusatsu", 
                                "Stage Play", 
                                "CG Animation", 
                                "Mixed Media", 
                                "Documentary"
                            ]} 
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('语言', 'Language')} 
                            value={data.language} 
                            onChange={v => updateField('language', v)} 
                            list={["Chinese", "English", "Bilingual (CN/EN)", "Japanese", "Korean", "French", "Spanish", "German", "Other"]} 
                        />
                    </div>
                    
                    <InputGroup idPrefix={prefix}
                        label={t('全局风格', 'Global Style')} 
                        value={data.Global_Style} 
                        onChange={v => updateField('Global_Style', v)} 
                        multi={true}
                        list={[
                            "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
                            "Hyperrealistic Portrait, RAW Photo, Ultra Detailed",
                            "Cyberpunk", 
                            "Minimalist", 
                            "Photorealistic", 
                            "Disney Style", 
                            "Ghibli Style", 
                            "Film Noir", 
                            "Steampunk", 
                            "Watercolor", 
                            "Oil Painting", 
                            "Pixel Art", 
                            "Vaporwave", 
                            "Gothic", 
                            "Surrealism"
                        ]}
                        placeholder={t('例如：赛博朋克', 'e.g. Cyberpunk')}
                    />

                     <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('借鉴影片', 'Borrowed Films')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={(data.borrowed_films || []).join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder={t('例如：消失的爱人, 小丑', 'e.g. Gone Girl, Joker')}
                        />
                    </div>
                </div>

                {/* Tech Params */}
                 <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">{t('技术与氛围', 'Technical & Mood')}</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                         <InputGroup idPrefix={prefix} label={t('横向分辨率', 'H. Resolution')} value={data.tech_params?.visual_standard?.horizontal_resolution} onChange={v => updateTech('horizontal_resolution', v)} placeholder="3840" list={["3840", "1920", "1280", "1080"]}/>
                         <InputGroup idPrefix={prefix} label={t('纵向分辨率', 'V. Resolution')} value={data.tech_params?.visual_standard?.vertical_resolution} onChange={v => updateTech('vertical_resolution', v)} placeholder="2160" list={["2160", "1920", "1080", "720"]}/>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4">
                         <InputGroup idPrefix={prefix} label={t('帧率', 'Frame Rate')} value={data.tech_params?.visual_standard?.frame_rate} onChange={v => updateTech('frame_rate', v)} list={["24", "30", "60"]} />
                         <InputGroup idPrefix={prefix} label={t('画幅比例', 'Aspect Ratio')} value={data.tech_params?.visual_standard?.aspect_ratio} onChange={v => updateTech('aspect_ratio', v)} list={["16:9", "2.35:1", "4:3", "9:16", "1:1"]} />
                         <InputGroup idPrefix={prefix} label={t('质量等级', 'Quality')} value={data.tech_params?.visual_standard?.quality} onChange={v => updateTech('quality', v)} list={["Ultra High", "High", "Medium", "Low", "Draft"]} />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                         <InputGroup idPrefix={prefix}
                            label={t('色调', 'Tone')} 
                            value={data.tone} 
                            onChange={v => updateField('tone', v)} 
                            multi={true}
                            list={[
                                "Cool", 
                                "Warm", 
                                "Neutral", 
                                "High Contrast", 
                                "Dark / Moody", 
                                "Dreamy", 
                                "Vibrant", 
                                "Desaturated", 
                                "Pastel", 
                                "Gritty",
                                "Skin Tone Optimized",
                                "Film Presence", 
                                "Muted Tones",
                                "Skin Tone Optimized, Dreamy",
                                "Film Presence, Muted Tones",
                                "Neutral, High Contrast",
                                "Dark / Moody, Gritty",
                                "Vibrant, High Contrast"
                            ]}
                         />
                         <InputGroup idPrefix={prefix}
                            label={t('光照', 'Lighting')} 
                            value={data.lighting} 
                            onChange={v => updateField('lighting', v)} 
                            multi={true}
                            list={[
                                "Natural Light", 
                                "Soft Light", 
                                "Hard Light", 
                                "Rim Light", 
                                "Rembrandt", 
                                "Neon / Cyber", 
                                "Cinematic", 
                                "Low Key", 
                                "High Key", 
                                "Volumetric",
                                "Butterfly Light",
                                "Studio Light",
                                "Golden Hour", 
                                "Window Light", 
                                "Split Light",
                                "Butterfly Light, Soft Light",
                                "Rembrandt, Volumetric",
                                "Cinematic, Rim Light, Volumetric",
                                "Studio Light, Hard Light",
                                "Natural Light, Window Light"
                            ]}
                         />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('备注', 'Notes')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={data.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder={t('补充风格说明...', 'Additional Style Notes...')}
                        />
                    </div>
                 </div>

                 {/* Story Generator (Episode) */}
                 <div className="bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('故事生成器（分集 / Ep. Info）', 'Story Generator (Episode / Ep. Info)')}</h3>
                        <button
                            onClick={handleGenerateEpisodeStory}
                            disabled={isGeneratingEpisodeStory}
                            className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingEpisodeStory ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                            title={t('生成分集大纲（开场/发展/转折/高潮/结局/悬念）', 'Generate an episode outline (setup/development/turning points/climax/resolution/suspense)')}
                        >
                            {isGeneratingEpisodeStory ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成分集大纲', 'Generate Episode Outline')}</>}
                        </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('分集编号', 'Episode Number')}</label>
                            <input
                                type="number"
                                min="1"
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                value={episodeStoryInput.episode_number}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, episode_number: e.target.value }))}
                                placeholder={t('例如：1', 'e.g. 1')}
                            />
                        </div>
                        <div>
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('伏笔 / 回收', 'Foreshadowing / Payoffs')}</label>
                            <input
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                value={episodeStoryInput.foreshadowing}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, foreshadowing: e.target.value }))}
                                placeholder={t('伏笔、揭示与回收目标', 'Seeds, reveals, payoff targets')}
                            />
                        </div>

                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('背景 / 世界观（本集聚焦）', 'Background / World (Episode focus)')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.background}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, background: e.target.value }))}
                                placeholder={t('本集最关键的世界与背景信息', 'Context that matters specifically for this episode')}
                            />
                        </div>

                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('开场', 'Setup')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.setup}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, setup: e.target.value }))}
                                placeholder={t('预告/开场钩子、诱因事件、不可回头点', 'Teaser/opening hook, inciting incident, point-of-no-return')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('发展', 'Development')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.development}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, development: e.target.value }))}
                                placeholder={t('升级、揭示、中点反转', 'Escalation, reveals, midpoint reversal')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('转折点', 'Turning Points')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.turning_points}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, turning_points: e.target.value }))}
                                placeholder={t('第二转折、低谷、最终计划', 'Second turn, low point, final plan')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('高潮', 'Climax')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.climax}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, climax: e.target.value }))}
                                placeholder={t('对抗、关键选择、代价', 'Confrontation, key choice, cost')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('结局回收', 'Resolution')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.resolution}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, resolution: e.target.value }))}
                                placeholder={t('收束、角色状态变化', 'Wrap-up, character state change')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('悬念 / 结尾钩子', 'Suspense / End Hook')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.suspense}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, suspense: e.target.value }))}
                                placeholder={t('悬念点、新问题、下一集威胁', 'Cliffhanger, new question, next-episode threat')}
                            />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('额外说明', 'Extra Notes')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                value={episodeStoryInput.extra_notes}
                                onChange={(e) => setEpisodeStoryInput(prev => ({ ...prev, extra_notes: e.target.value }))}
                                placeholder={t('约束、反转偏好、节奏', 'Constraints, twist preference, pacing')}
                            />
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('已生成分集大纲（Markdown）', 'Generated Episode Outline (Markdown)')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-48 resize-none"
                            value={info.story_dna_episode_md || ''}
                            onChange={(e) => setInfo(prev => ({ ...prev, story_dna_episode_md: e.target.value }))}
                            placeholder={t('（生成后，分集大纲会显示在这里。你可以编辑后保存修改。）', '(After generation, the episode outline will appear here. You can edit it and Save Changes.)')}
                        />
                    </div>
                 </div>
            </div>
        </div>
    );
};


const ScriptEditor = ({ activeEpisode, projectId, project, onUpdateScript, onUpdateEpisodeInfo, onLog, onImportText, onSwitchToScenes, uiLang = 'zh' }) => {
    const navigate = useNavigate();
    const [segments, setSegments] = useState([]);
    const [showMerged, setShowMerged] = useState(false);
    const [mergedContent, setMergedContent] = useState('');
    const [rawContent, setRawContent] = useState('');
    const [llmResultContent, setLlmResultContent] = useState('');
    const [isRawMode, setIsRawMode] = useState(false);
    const [analysisAttentionNotes, setAnalysisAttentionNotes] = useState('');
    const [isSavingAnalysisAttentionNotes, setIsSavingAnalysisAttentionNotes] = useState(false);
    const [availableSubjectAssets, setAvailableSubjectAssets] = useState([]);
    const [selectedReuseSubjectIds, setSelectedReuseSubjectIds] = useState([]);
    const [reuseSubjectTypeFilter, setReuseSubjectTypeFilter] = useState('all');
    const [reuseSubjectKeyword, setReuseSubjectKeyword] = useState('');
    const [isLoadingSubjectAssets, setIsLoadingSubjectAssets] = useState(false);
    const [isSavingReuseSubjects, setIsSavingReuseSubjects] = useState(false);
    const [analysisFlowStatus, setAnalysisFlowStatus] = useState({ phase: 'idle', message: '' });
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);

    const isEpisodeOnePage = useMemo(() => {
        const title = String(activeEpisode?.title || '').trim().toLowerCase();
        if (!title) return false;
        return /episode\s*1\b/.test(title) || /第\s*1\s*集/.test(title);
    }, [activeEpisode?.title]);

    const extractJsonFromLlmText = (text) => {
        if (!text || typeof text !== 'string') return '';

        const tryParse = (candidate) => {
            if (!candidate || typeof candidate !== 'string') return null;
            const s = candidate.trim();
            if (!s) return null;
            try {
                return JSON.parse(s);
            } catch {
                return null;
            }
        };

        const trimmed = text.trim();

        // Case 1: whole response is JSON
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            const obj = tryParse(trimmed);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        // Case 2: fenced code block ```json ... ```
        const fenceRe = /```(?:json)?\s*([\s\S]*?)```/gi;
        let match;
        while ((match = fenceRe.exec(text)) !== null) {
            const candidate = (match[1] || '').trim();
            if (!candidate) continue;
            const obj = tryParse(candidate);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        // Case 3: heuristic substring between outermost braces/brackets
        const braceStart = trimmed.indexOf('{');
        const braceEnd = trimmed.lastIndexOf('}');
        if (braceStart !== -1 && braceEnd > braceStart) {
            const candidate = trimmed.slice(braceStart, braceEnd + 1);
            const obj = tryParse(candidate);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        const bracketStart = trimmed.indexOf('[');
        const bracketEnd = trimmed.lastIndexOf(']');
        if (bracketStart !== -1 && bracketEnd > bracketStart) {
            const candidate = trimmed.slice(bracketStart, bracketEnd + 1);
            const obj = tryParse(candidate);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        return '';
    };

    const llmJsonResultContent = useMemo(() => extractJsonFromLlmText(llmResultContent), [llmResultContent]);

    const extractJsonObjectsFromText = (text) => {
        if (!text || typeof text !== 'string') return [];

        const objs = [];

        const tryPush = (candidate) => {
            if (!candidate || typeof candidate !== 'string') return;
            const s = candidate.trim();
            if (!s) return;
            try {
                objs.push(JSON.parse(s));
            } catch {
                // ignore
            }
        };

        const trimmed = text.trim();

        // Whole text JSON
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            tryPush(trimmed);
        }

        // Fenced blocks (prefer these)
        const fenceRe = /```(?:json)?\s*([\s\S]*?)```/gi;
        let match;
        while ((match = fenceRe.exec(text)) !== null) {
            tryPush(match[1]);
        }

        // If we didn't get anything, do a simple brace-scan for objects.
        if (objs.length === 0) {
            let braceCount = 0;
            let startIndex = -1;
            let inString = false;

            for (let i = 0; i < text.length; i++) {
                const ch = text[i];
                const prev = i > 0 ? text[i - 1] : '';

                if (ch === '"' && prev !== '\\') {
                    inString = !inString;
                }
                if (inString) continue;

                if (ch === '{') {
                    if (braceCount === 0) startIndex = i;
                    braceCount++;
                } else if (ch === '}') {
                    braceCount--;
                    if (braceCount === 0 && startIndex !== -1) {
                        const candidate = text.slice(startIndex, i + 1);
                        tryPush(candidate);
                        startIndex = -1;
                    }
                }
            }
        }

        // De-dupe by JSON string
        const seen = new Set();
        const unique = [];
        for (const o of objs) {
            try {
                const k = JSON.stringify(o);
                if (!seen.has(k)) {
                    seen.add(k);
                    unique.push(o);
                }
            } catch {
                // ignore
            }
        }
        return unique;
    };

    const getEGlobalInfoPayloadFromJsonText = (jsonText) => {
        const objects = extractJsonObjectsFromText(jsonText);
        for (const obj of objects) {
            if (obj && typeof obj === 'object' && obj.e_global_info) {
                return { e_global_info: obj.e_global_info };
            }
        }
        return null;
    };

    const getEntitiesPayloadFromJsonText = (jsonText) => {
        const objects = extractJsonObjectsFromText(jsonText);
        for (const obj of objects) {
            if (!obj || typeof obj !== 'object') continue;
            const hasAny = !!(obj.characters || obj.props || obj.environments);
            if (hasAny) {
                return {
                    characters: Array.isArray(obj.characters) ? obj.characters : [],
                    props: Array.isArray(obj.props) ? obj.props : [],
                    environments: Array.isArray(obj.environments) ? obj.environments : [],
                };
            }
        }
        return null;
    };

    const doImportText = async (text, importType = 'auto') => {
        if (typeof onImportText !== 'function') {
            if (onLog) onLog('Import is not available in this context.', 'warning');
            return;
        }
        try {
            await onImportText(text || '', importType);
        } catch (e) {
            if (onLog) onLog(`Import failed: ${e.message}`, 'error');
        }
    };

    const runAutoImportAndSwitchToScenes = async (analyzedText) => {
        if (typeof onImportText !== 'function') {
            if (onLog) onLog('Import is not available in this context.', 'warning');
            setAnalysisFlowStatus({
                phase: 'completed',
                message: t('分析完成（当前上下文不支持自动导入）', 'Analysis completed (auto import is not available in this context)'),
            });
            return;
        }

        setAnalysisFlowStatus({
            phase: 'importing',
            message: t('LLM 已返回，正在自动导入...', 'LLM response received, auto-importing...'),
        });

        if (onLog) onLog('Auto-importing analysis result...', 'process');
        await onImportText(analyzedText || '', 'auto');
        if (onLog) onLog('Auto-import finished.', 'success');

        if (typeof onSwitchToScenes === 'function') {
            onSwitchToScenes();
        }

        setAnalysisFlowStatus({
            phase: 'completed',
            message: t('分析与导入已完成，已切换到 Scenes。', 'Analysis and import completed, switched to Scenes.'),
        });
    };

    const parseMarkdownTable = (text) => {
        if (!text || typeof text !== 'string') return null;
        const lines = text
            .split('\n')
            .map(l => l.trim())
            .filter(l => l.startsWith('|') && l.includes('|'));

        if (lines.length < 2) return null;

        const cleanCells = (line) => {
            let cols = line.split('|').map(c => c.trim());
            if (cols.length > 0 && cols[0] === "") cols.shift();
            if (cols.length > 0 && cols[cols.length - 1] === "") cols.pop();

            return cols.map(c => (c || '')
                .replace(/\\\|/g, '|')
                .replace(/<br\s*\/?>/gi, '\n')
            );
        };

        const isSeparatorLine = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);

        const headerLine = lines[0];
        const sepLine = lines[1];
        if (isSeparatorLine(headerLine) || !isSeparatorLine(sepLine)) return null;

        const headers = cleanCells(headerLine);
        if (headers.length === 0) return null;

        const rows = [];
        for (let i = 2; i < lines.length; i++) {
            const line = lines[i];
            if (isSeparatorLine(line)) continue;
            const cells = cleanCells(line);
            if (cells.length === 0) continue;
            while (cells.length < headers.length) cells.push('');
            rows.push(cells.slice(0, headers.length));
        }

        return { headers, rows };
    };

    const buildMarkdownTable = (headers, rows) => {
        const esc = (val) => (val || '')
            .replace(/\|/g, '\\|')
            .replace(/\n/g, '<br>');

        const headerLine = `| ${headers.map(esc).join(' | ')} |`;
        const sepLine = `| ${headers.map(() => '---').join(' | ')} |`;
        const rowLines = (rows || []).map(r => {
            const safe = [...r];
            while (safe.length < headers.length) safe.push('');
            return `| ${safe.slice(0, headers.length).map(esc).join(' | ')} |`;
        });
        return [headerLine, sepLine, ...rowLines].join('\n');
    };

    const handleMerge = () => {
        const fullText = segments
            .map(seg => seg.content || '')
            .filter(t => t.trim().length > 0)
            .join('\n\n');
        setMergedContent(fullText);
        setShowMerged(true);
    };

    useEffect(() => {
        if (activeEpisode?.script_content) {
            setRawContent(activeEpisode.script_content);
        } else {
            setRawContent('');
        }

        setAnalysisAttentionNotes(String(activeEpisode?.episode_info?.analysis_attention_notes || ''));
        const persistedIds = activeEpisode?.episode_info?.reuse_subject_asset_ids;
        if (Array.isArray(persistedIds)) {
            setSelectedReuseSubjectIds(persistedIds.map(x => String(x)));
        } else {
            setSelectedReuseSubjectIds([]);
        }

        const storedNewField = activeEpisode?.ai_scene_analysis_result;
        const storedLegacy = activeEpisode?.episode_info?.llm_scene_analysis_result;
        const stored = (typeof storedNewField === 'string' && storedNewField.length > 0)
            ? storedNewField
            : (typeof storedLegacy === 'string' ? storedLegacy : (storedLegacy ? JSON.stringify(storedLegacy, null, 2) : ''));
        setLlmResultContent(typeof stored === 'string' ? stored : '');

        if (!activeEpisode?.script_content) {
            setSegments([]);
            setIsRawMode(true);
            return;
        }

        const content = activeEpisode.script_content;
        
        // Mode 1: Markdown Table parser
        const hasTableStructure = /\|\s*Paragraph ID\s*\|/.test(content) || /\|\s*Content \(Revised\)\s*\|/.test(content);
        
        if (hasTableStructure) {
             const lines = content.split('\n').map(l => l.trim()).filter(l => l.includes('|'));
             const parsed = [];
             
             const headerIdx = lines.findIndex(l => l.includes("Paragraph ID") || l.includes("Content (Revised)"));
             if (headerIdx === -1) {
                 setSegments([]);
                 setIsRawMode(true);
                 return;
             }

             for (let i = headerIdx + 1; i < lines.length; i++) {
                 const line = lines[i];
                 if (line.includes('---')) continue; 
                 
                 let cols = line.split('|').map(c => c.trim());
                 if (cols.length > 0 && cols[0] === "") cols.shift();
                 if (cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                 
                 if (cols.length >= 6) {
                      parsed.push({
                         id: cols[0],
                         title: cols[1],
                         content: cols[2].replace(/<br\s*\/?>/gi, '\n'),
                         original: cols[3].replace(/<br\s*\/?>/gi, '\n'),
                         narrative_role: cols[4].replace(/<br\s*\/?>/gi, '\n'),
                         analysis: cols[5].replace(/<br\s*\/?>/gi, '\n')
                      });
                 }
             }
             if (parsed.length > 0) {
                 setSegments(parsed);
                 setIsRawMode(false);
             } else {
                 setSegments([]);
                 setIsRawMode(true);
             }
             return;
        }

        // Mode 2: Legacy parser
        const chunks = content.split(/## Segment (\d+)/).filter(Boolean);
        const parsed = [];
        
        // Basic heuristic to check if it matches legacy format at all
        let isLegacy = false;
        
        for (let i = 0; i < chunks.length; i += 2) {
            const id = chunks[i];
            const body = chunks[i+1] || "";
            if (!/^\d+$/.test(id)) continue;

            isLegacy = true; 
            const roleMatch = body.match(/\*\*Narrative Role:\*\*\s*([\s\S]*?)(?=\*\*Analysis:|\n##|$)/);
            const analysisMatch = body.match(/\*\*Analysis:\*\*\s*([\s\S]*?)(?=$)/);
            
            let narratives = roleMatch ? roleMatch[1].trim() : "";
            let analysis = analysisMatch ? analysisMatch[1].trim() : "";
            
            let mainContent = body;
            if (roleMatch) mainContent = mainContent.replace(roleMatch[0], '');
            if (analysisMatch) mainContent = mainContent.replace(analysisMatch[0], '');
            
            mainContent = mainContent.trim();
            const lines = mainContent.split('\n').filter(l => l.trim().length > 0);
            
            const title = (lines.length > 0 && lines[0].length < 50) ? lines[0] : "Untitled Segment";
            const textBody = (lines.length > 0 && lines[0].length < 50) ? lines.slice(1).join('\n') : lines.join('\n');

            parsed.push({ 
                id, 
                title, 
                content: textBody, 
                original: '',
                narrative_role: narratives, 
                analysis: analysis 
            });
        }
        
        if (isLegacy && parsed.length > 0) {
            setSegments(parsed);
            setIsRawMode(false);
        } else {
            setSegments([]);
            setIsRawMode(true);
        }
    }, [activeEpisode]);

    useEffect(() => {
        let mounted = true;
        const loadAssets = async () => {
            if (!isEpisodeOnePage || !projectId) {
                if (mounted) setAvailableSubjectAssets([]);
                return;
            }
            setIsLoadingSubjectAssets(true);
            try {
                const entities = await fetchEntities(projectId);
                if (!mounted) return;
                setAvailableSubjectAssets(Array.isArray(entities) ? entities : []);
            } catch (e) {
                console.error(e);
                if (mounted) setAvailableSubjectAssets([]);
            } finally {
                if (mounted) setIsLoadingSubjectAssets(false);
            }
        };
        loadAssets();
        return () => { mounted = false; };
    }, [isEpisodeOnePage, projectId]);

    const selectedReuseSubjectAssets = useMemo(() => {
        if (!Array.isArray(availableSubjectAssets) || availableSubjectAssets.length === 0) return [];
        const selected = new Set((selectedReuseSubjectIds || []).map(v => String(v)));
        return availableSubjectAssets
            .filter(asset => selected.has(String(asset.id)))
            .map(asset => ({
                id: asset.id,
                name: asset.name || '',
                type: asset.type || '',
                description: asset.description || asset.narrative_description || '',
                anchor_description: asset.anchor_description || '',
            }));
    }, [availableSubjectAssets, selectedReuseSubjectIds]);

    const reuseSubjectTypeOptions = useMemo(() => {
        const types = new Set();
        for (const asset of availableSubjectAssets || []) {
            const t = String(asset?.type || '').trim();
            if (t) types.add(t);
        }
        return Array.from(types).sort((a, b) => a.localeCompare(b));
    }, [availableSubjectAssets]);

    const filteredSubjectAssets = useMemo(() => {
        const normalizedKeyword = String(reuseSubjectKeyword || '').trim().toLowerCase();
        return (availableSubjectAssets || []).filter(asset => {
            const typeValue = String(asset?.type || '').trim();
            const passType = reuseSubjectTypeFilter === 'all' || typeValue === reuseSubjectTypeFilter;
            if (!passType) return false;

            if (!normalizedKeyword) return true;

            const haystack = [
                asset?.name,
                asset?.description,
                asset?.narrative_description,
                asset?.anchor_description,
                asset?.type,
            ]
                .map(v => String(v || '').toLowerCase())
                .join(' ');

            return haystack.includes(normalizedKeyword);
        });
    }, [availableSubjectAssets, reuseSubjectKeyword, reuseSubjectTypeFilter]);

    const hasActiveReuseSubjectFilters = useMemo(() => {
        return reuseSubjectTypeFilter !== 'all' || String(reuseSubjectKeyword || '').trim().length > 0;
    }, [reuseSubjectTypeFilter, reuseSubjectKeyword]);

    const toggleReuseSubject = (assetId) => {
        const key = String(assetId);
        setSelectedReuseSubjectIds(prev => {
            const has = prev.includes(key);
            if (has) return prev.filter(v => v !== key);
            return [...prev, key];
        });
    };

    const clearReuseSubjectFilters = () => {
        setReuseSubjectTypeFilter('all');
        setReuseSubjectKeyword('');
    };

    const handleSaveReuseSubjects = async () => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        setIsSavingReuseSubjects(true);
        try {
            const mergedEpisodeInfo = {
                ...(activeEpisode?.episode_info || {}),
                reuse_subject_asset_ids: selectedReuseSubjectIds,
            };
            await onUpdateEpisodeInfo(activeEpisode.id, { episode_info: mergedEpisodeInfo });
            if (onLog) onLog('Episode 1 reusable subject assets saved.', 'success');
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Failed to save reusable subjects: ${e.message}`, 'error');
        } finally {
            setIsSavingReuseSubjects(false);
        }
    };

    const persistLlmResultContent = async (content) => {
        if (!activeEpisode?.id) return;
        if (!onUpdateEpisodeInfo) return;

        try {
            await onUpdateEpisodeInfo(activeEpisode.id, { ai_scene_analysis_result: content || '' });
        } catch (e) {
            console.error("Failed to persist LLM result", e);
            if (onLog) onLog(`Failed to save LLM result: ${e.message}`, "error");
        }
    };

    // Keep the "LLM 返回结果" box in sync with DB-saved ai_scene_analysis_result.
    // Important: don't clobber local edits while user is typing.
    const lastLoadedAnalysisRef = useRef(null);
    const refreshAnalysisFromDB = useCallback(async () => {
        if (!projectId || !activeEpisode?.id) return;
        try {
            const eps = await fetchEpisodes(projectId);
            const fresh = (eps || []).find(e => e.id === activeEpisode.id);
            const dbText = fresh?.ai_scene_analysis_result || '';

            // Only update if user hasn't diverged from last loaded content.
            const current = llmResultContent || '';
            const lastLoaded = lastLoadedAnalysisRef.current;
            const userHasEdited = lastLoaded !== null && current !== lastLoaded;

            if (!userHasEdited) {
                if (dbText && dbText !== current) {
                    setLlmResultContent(dbText);
                }
                lastLoadedAnalysisRef.current = dbText;
            }
        } catch (e) {
            // non-fatal
            console.warn('[ScriptEditor] Failed to refresh analysis from DB', e);
        }
    }, [projectId, activeEpisode?.id, llmResultContent]);

    useEffect(() => {
        // On episode change/remount, prefer parent-provided field; fallback to DB refresh.
        const initial = activeEpisode?.ai_scene_analysis_result || '';
        setLlmResultContent(initial);
        lastLoadedAnalysisRef.current = initial;
        if (!initial) {
            refreshAnalysisFromDB();
        }
    }, [activeEpisode?.id]);

    const handleLlmCellChange = (rowIdx, colIdx, value) => {
        const parsed = parseMarkdownTable(llmResultContent);
        if (!parsed) {
            setLlmResultContent(value);
            return;
        }

        const nextRows = parsed.rows.map(r => [...r]);
        if (!nextRows[rowIdx]) return;
        nextRows[rowIdx][colIdx] = value;
        const nextText = buildMarkdownTable(parsed.headers, nextRows);
        setLlmResultContent(nextText);
    };

    const handleSegmentChange = (idx, field, value) => {
        const newSegments = [...segments];
        newSegments[idx] = { ...newSegments[idx], [field]: value };
        setSegments(newSegments);
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        if (onLog) onLog("Saving Script...", "process");

        let fullContent = rawContent;

        if (!isRawMode && segments.length > 0) {
            const header = `| Paragraph ID | Title | Content (Revised) | Content (Original) | Narrative Function | Analysis & Adaptation Notes |\n|---|---|---|---|---|---|`;
            const rows = segments.map(seg => {
                const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
                return `| ${seg.id} | ${clean(seg.title)} | ${clean(seg.content)} | ${clean(seg.original)} | ${clean(seg.narrative_role)} | ${clean(seg.analysis)} |`;
            }).join('\n');
            fullContent = header + '\n' + rows;
        }
        
        // console.log("Saving Content:", fullContent.substring(0, 100) + "...");

        try {
            await onUpdateScript(activeEpisode.id, fullContent);
            if (onLog) onLog(`Script saved. Length: ${fullContent.length}`, "success");
            // If we just saved from Raw Mode, keep it in sync but don't force parse unless user wants to
            // Actually the Effect will trigger on activeEpisode update if we parent updates it? 
            // Usually onUpdateScript updates parent state? If so, useEffect runs. 
            // If raw text saved, it will probably stay in Raw Mode (parsing fails).
            alert("Script saved successfully!");
        } catch (e) {
             console.error(e);
             if (onLog) onLog(`Script Save Failed: ${e.message}`, "error");
             alert(`Failed to save script: ${e.message}`);
        }
    };
    
    // AI Analysis Handler
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [systemPrompt, setSystemPrompt] = useState("");
    const [userPrompt, setUserPrompt] = useState("");
    const [isSuperuser, setIsSuperuser] = useState(false);

    // Character Canon (Authoritative) generator
    const CANON_TAG_STORAGE_KEY = 'aistory_character_canon_tag_categories_v1';
    const CANON_IDENTITY_STORAGE_KEY = 'aistory_character_canon_identity_categories_v1';
    const DEFAULT_CANON_TAG_CATEGORIES = [
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
            title: '性感（不露骨，主角塑造）',
            options: [
                { id: 'sexy_shoulder_1', label: '露肩/一字肩', detail: '突出肩线与颈部线条，镜头更“高级性感”' },
                { id: 'sexy_collar_1', label: '露锁骨', detail: '领口略开，锁骨清晰（尺度克制）' },
                { id: 'sexy_collar_2', label: '开领/解一两颗扣', detail: '衬衫/外套微敞，若隐若现但不露骨' },
                { id: 'sexy_collar_3', label: '露锁骨与胸口（开领/浅V）', detail: '开领或浅V领，视觉聚焦颈胸区域（尺度克制）' },
                { id: 'sexy_arm_1', label: '无袖/吊带（露手臂）', detail: '露出上臂线条，更轻熟、更利落' },
                { id: 'sexy_arm_2', label: '挽袖/卷袖（露前臂）', detail: '随性、克制，有一点禁欲张力' },
                { id: 'sexy_leg_1', label: '短裙/短裤（露腿）', detail: '腿部比例突出（注意尺度克制）' },
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
                { id: 'body_shape_3', label: '微肉/丰润', detail: '柔软曲线、亲和力强（尺度克制）' },
                { id: 'body_shape_4', label: '健身型', detail: '肩背与核心发达，动作干净有力量' },
                { id: 'body_shape_5', label: '厚实/壮硕', detail: '骨架大、存在感强，近景更有压迫' },
                { id: 'body_prop_1', label: '腿长', detail: '视觉比例拉长，走路带风' },
                { id: 'body_prop_2', label: '腰线高', detail: '上短下长，镜头更显修长' },
                { id: 'body_prop_3', label: '腰臀比突出', detail: '曲线更明显（不露骨）' },
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
        {
            key: 'wardrobe',
            title: '穿搭/造型（主角塑造）',
            options: [
                { id: 'wardrobe_1', label: '干练', detail: '收腰西装或衬衫+长裤，剪裁利落' },
                { id: 'wardrobe_2', label: '优雅', detail: '简洁连衣裙或套装，配饰克制' },
                { id: 'wardrobe_3', label: '都市时髦', detail: '大衣/风衣+高跟或短靴，层次感' },
                { id: 'wardrobe_4', label: '禁欲风', detail: '高领/长袖/长裤，颜色克制但极有气场' },
                { id: 'wardrobe_5', label: '轻奢', detail: '面料有质感，细节讲究，不浮夸' },
                { id: 'wardrobe_m1', label: '绅士', detail: '合身西装/大衣，领带或领结点到为止' },
                { id: 'wardrobe_m2', label: '冷酷街头', detail: '黑色夹克/皮衣+短靴，线条硬' },
                { id: 'wardrobe_m3', label: '少年感男主', detail: '白衬衫/针织衫/运动外套，干净清爽' },
            ],
        },
        {
            key: 'clothing_items',
            title: '衣着/单品（常用标签）',
            options: [
                { id: 'cloth_1', label: '白衬衫', detail: '干净克制，越简单越高级' },
                { id: 'cloth_2', label: '黑高领', detail: '禁欲、冷感、气场强' },
                { id: 'cloth_3', label: '西装', detail: '合身剪裁，肩线清晰' },
                { id: 'cloth_4', label: '大衣/风衣', detail: '压气场，走路带风' },
                { id: 'cloth_5', label: '丝质/缎面', detail: '微光泽，性感但不露骨' },
                { id: 'cloth_6', label: '皮衣/夹克', detail: '硬朗、叛逆、酷感' },
                { id: 'cloth_7', label: '短裙/开衩', detail: '腿部线条更突出（注意尺度克制）' },
                { id: 'cloth_8', label: '高跟鞋', detail: '气场与身材比例拉长' },
                { id: 'cloth_9', label: '短靴', detail: '利落、都市、行动感' },
                { id: 'cloth_10', label: '配饰克制', detail: '少而精，提升高级感' },
            ],
        },
        {
            key: 'combat_wear',
            title: '战斗服装/战甲（服饰）',
            options: [
                { id: 'cwear_1', label: '战甲/盔甲', detail: '金属/皮革甲胄，防护与威慑感' },
                { id: 'cwear_2', label: '轻甲', detail: '更灵活，线条更贴身、利落' },
                { id: 'cwear_3', label: '战术背心/防弹衣', detail: '现代作战感，功能性口袋与模块' },
                { id: 'cwear_4', label: '制服/作战服', detail: '军警/特勤气质，纪律与专业' },
                { id: 'cwear_5', label: '披风/斗篷', detail: '英雄感/隐匿感，镜头层次更强' },
                { id: 'cwear_6', label: '护臂/护腕', detail: '近战细节，硬朗质感' },
                { id: 'cwear_7', label: '护膝/护腿', detail: '实战磨损感更真实' },
                { id: 'cwear_8', label: '作战靴', detail: '落地更稳，压迫感与行动感兼具' },
                { id: 'cwear_9', label: '战术腰带/枪套', detail: '装备挂载，专业度更高' },
            ],
        },
        {
            key: 'ancient_wear',
            title: '古装服装/服饰',
            options: [
                { id: 'awear_1', label: '汉服（襦裙/交领）', detail: '飘逸层次，古风气质' },
                { id: 'awear_2', label: '长袍/直裾', detail: '文人/谋士感，克制内敛' },
                { id: 'awear_3', label: '官服/朝服', detail: '礼制等级与权力感更明确' },
                { id: 'awear_4', label: '锦衣/华服', detail: '贵气、纹样精致、用料讲究' },
                { id: 'awear_5', label: '夜行衣', detail: '暗色贴身，隐秘与危险感（不强调动作）' },
                { id: 'awear_6', label: '甲胄（古代战甲）', detail: '甲片/扎甲，历史质感强' },
                { id: 'awear_7', label: '披风/披肩', detail: '身份感与镜头层次' },
                { id: 'awear_8', label: '发冠/发簪', detail: '阶层与礼制体现' },
                { id: 'awear_9', label: '腰带/玉佩', detail: '点明身份与品味' },
                { id: 'awear_10', label: '绣鞋/靴', detail: '细节完成度更高，时代感更真' },
            ],
        },
        {
            key: 'hair_makeup',
            title: '妆发/细节（主角塑造）',
            options: [
                { id: 'hm_1', label: '红唇', detail: '饱和但干净的红，气场拉满' },
                { id: 'hm_2', label: '淡妆', detail: '伪素颜，重点是皮肤干净与眼神' },
                { id: 'hm_3', label: '眼妆', detail: '眼尾微上扬，强调眼神锋利/勾人' },
                { id: 'hm_4', label: '长发', detail: '发丝有光泽，发型不凌乱' },
                { id: 'hm_5', label: '短发', detail: '轮廓利落，露出颈部线条' },
                { id: 'hm_m1', label: '寸头/短寸', detail: '干净利落，突出眉骨与眼神' },
                { id: 'hm_m2', label: '胡渣', detail: '微微胡渣，成熟感与危险感' },
            ],
        },
        {
            key: 'vibe',
            title: '气质/表现（主角塑造）',
            options: [
                { id: 'vibe_1', label: '神秘', detail: '信息不一次说完，表情留白' },
                { id: 'vibe_2', label: '冷峻', detail: '少笑，语气短，目光锐利' },
                { id: 'vibe_3', label: '阳光', detail: '笑意自然，语气轻快，亲和力强' },
                { id: 'vibe_4', label: '专业感', detail: '用词准确，动作克制，目标导向' },
                { id: 'vibe_5', label: '强势', detail: '话语有控制力，场面压得住' },
                { id: 'vibe_6', label: '脆弱感', detail: '瞬间的停顿/回避眼神，让人心软' },
            ],
        },
        {
            key: 'nation',
            title: '国籍/地区（设定）',
            options: [
                { id: 'nation_1', label: '中国', detail: '可细分：北方/南方口音与习惯' },
                { id: 'nation_2', label: '日本', detail: '克制礼貌、边界感明显' },
                { id: 'nation_3', label: '韩国', detail: '时尚敏感、表达更直接' },
                { id: 'nation_4', label: '美国', detail: '表达直接、个人主义、行动优先' },
                { id: 'nation_5', label: '英国', detail: '措辞克制、礼貌疏离、幽默冷' },
                { id: 'nation_6', label: '法国', detail: '松弛浪漫、审美挑剔、有锋芒' },
                { id: 'nation_7', label: '意大利', detail: '热情外放、注重衣着与手势' },
            ],
        },
        {
            key: 'ethnicity',
            title: '人种/族裔（设定）',
            options: [
                { id: 'eth_1', label: '东亚', detail: '例如：中/日/韩常见审美与轮廓特点' },
                { id: 'eth_2', label: '白人/欧洲裔', detail: '骨相立体、肤色与发色范围更广' },
                { id: 'eth_3', label: '黑人/非洲裔', detail: '五官张力强、体态与气场更突出' },
                { id: 'eth_4', label: '拉丁裔', detail: '热烈、自信、风格表达更强' },
                { id: 'eth_5', label: '南亚裔', detail: '深邃眼神、配饰审美更鲜明' },
                { id: 'eth_6', label: '中东/阿拉伯裔', detail: '浓眉深眼、轮廓强、气场浓烈' },
                { id: 'eth_7', label: '混血', detail: '特征融合，辨识度高' },
            ],
        },
    ];

    const DEFAULT_CANON_IDENTITY_CATEGORIES = [
        {
            key: 'lead_role',
            title: '主角定位/戏份',
            options: [
                { id: 'lead_f', label: '女主角', detail: '故事核心视角/情感主线' },
                { id: 'lead_m', label: '男主角', detail: '故事核心视角/推动行动线' },
                { id: 'lead_2', label: '第二主角', detail: '重要支线/关键转折' },
                { id: 'antagonist', label: '反派/对立面', detail: '推进冲突与悬念' },
            ],
        },
        {
            key: 'occupation',
            title: '职业/身份',
            options: [
                { id: 'occ_ceo', label: 'CEO/总裁', detail: '强掌控、决策快、社交资源丰富' },
                { id: 'occ_police', label: '刑警/警探', detail: '行动派、观察力强、压力承受高' },
                { id: 'occ_lawyer', label: '律师', detail: '逻辑强、措辞锋利、擅长博弈' },
                { id: 'occ_doctor', label: '医生', detail: '专业冷静、情绪克制、同理心' },
                { id: 'occ_artist', label: '艺术家', detail: '审美敏感、情绪浓、反差感' },
                { id: 'occ_student', label: '大学生', detail: '成长线明显、少年感/少女感' },
                { id: 'occ_model', label: '模特/艺人', detail: '镜头感强、曝光与舆论压力' },
            ],
        },
        {
            key: 'combat_identity',
            title: '战斗身份/背景',
            options: [
                { id: 'cid_1', label: '军人/士兵', detail: '训练有素，服从命令，纪律感强' },
                { id: 'cid_2', label: '特勤/特种', detail: '高压任务，处事克制专业' },
                { id: 'cid_3', label: '雇佣兵', detail: '利益驱动，实战经验丰富' },
                { id: 'cid_4', label: '杀手/刺客', detail: '隐秘、冷静、边界感强' },
                { id: 'cid_5', label: '保镖/护卫', detail: '保护优先，风险评估与站位意识强' },
                { id: 'cid_6', label: '武术家', detail: '以技服人，克制与底线清晰' },
                { id: 'cid_7', label: '赏金猎人', detail: '规则感强，灰色地带的执行者' },
                { id: 'cid_8', label: '黑帮打手', detail: '狠劲、街头经验与威慑' },
            ],
        },
        {
            key: 'ancient_identity',
            title: '古装身份/阵营',
            options: [
                { id: 'aid_1', label: '将军/统帅', detail: '威望与军纪，杀伐果断' },
                { id: 'aid_2', label: '侍卫/禁军', detail: '守护要员/皇权，纪律严' },
                { id: 'aid_3', label: '捕快/衙役', detail: '基层执法，江湖味更浓' },
                { id: 'aid_4', label: '县令/官员', detail: '规则执行者，权力与人情博弈' },
                { id: 'aid_5', label: '世家公子/小姐', detail: '礼制与家族利益牵引，克制体面' },
                { id: 'aid_6', label: '王爷/皇子', detail: '权力中心，处处试探与算计' },
                { id: 'aid_7', label: '宫女/太监', detail: '宫廷生态，信息与生存技巧' },
                { id: 'aid_8', label: '门派弟子/修行者', detail: '师门规矩、江湖恩怨、阵营牵连' },
                { id: 'aid_9', label: '侠客/游侠', detail: '行走江湖，讲义气也有底线' },
            ],
        },
        {
            key: 'status',
            title: '社会身份/阶层',
            options: [
                { id: 'st_elite', label: '上层精英', detail: '资源多、社交圈高、习惯克制' },
                { id: 'st_middle', label: '中产专业人士', detail: '稳健务实、重效率与边界' },
                { id: 'st_grass', label: '草根逆袭', detail: '韧性强、行动强、野心明确' },
                { id: 'st_mysterious', label: '身份成谜', detail: '信息分层揭示，悬念强' },
            ],
        },
        {
            key: 'personality_arc',
            title: '主角弧光/关键词',
            options: [
                { id: 'arc_redemption', label: '救赎', detail: '背负过去，逐步修复与和解' },
                { id: 'arc_growth', label: '成长', detail: '从稚嫩到成熟的可见变化' },
                { id: 'arc_revenge', label: '复仇', detail: '目标明确，情绪压抑与爆发' },
                { id: 'arc_power', label: '权力', detail: '争夺与控制、规则博弈' },
            ],
        },
    ];
    const [canonName, setCanonName] = useState('');
    const [canonIdentityCategories, setCanonIdentityCategories] = useState(DEFAULT_CANON_IDENTITY_CATEGORIES);
    const [canonSelectedIdentityIds, setCanonSelectedIdentityIds] = useState([]);
    const [canonCustomIdentity, setCanonCustomIdentity] = useState('');
    const [canonBody, setCanonBody] = useState('');
    const [canonExtra, setCanonExtra] = useState('');
    const [canonCustomTags, setCanonCustomTags] = useState('');
    const [canonTagCategories, setCanonTagCategories] = useState(DEFAULT_CANON_TAG_CATEGORIES);
    const [canonTagEditMode, setCanonTagEditMode] = useState(false);
    const [canonSelectedTagIds, setCanonSelectedTagIds] = useState([]);
    const [canonGenerating, setCanonGenerating] = useState(false);
    const [showCanonModal, setShowCanonModal] = useState(false);

    // Script Generator (Scenes)
    const [showSceneGenPanel, setShowSceneGenPanel] = useState(false);
    const [sceneGenCount, setSceneGenCount] = useState(10);
    const [sceneGenNotes, setSceneGenNotes] = useState('');
    const [sceneGenReplaceExisting, setSceneGenReplaceExisting] = useState(true);
    const [sceneGenGenerating, setSceneGenGenerating] = useState(false);

    const canonOptionValue = (opt) => `${opt.label}：${opt.detail}`;

    const normalizeCanonTagCategories = (raw) => {
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

    const persistCanonTagCategories = (categories) => {
        try {
            const normalized = normalizeCanonTagCategories(categories);
            if (!normalized) return false;
            localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(normalized));
            return true;
        } catch (e) {
            return false;
        }
    };

    useEffect(() => {
        try {
            const saved = localStorage.getItem(CANON_TAG_STORAGE_KEY);
            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);
            const LEGACY_SEXY_OPTION_IDS = new Set([
                'sexy_1',
                'sexy_2',
                'sexy_3',
                'sexy_4',
                'sexy_m1',
                'sexy_m2',
            ]);

            const mergeCategoriesByKey = (savedCats, defaultCats) => {
                const byKey = new Map();
                for (const c of (savedCats || [])) {
                    if (!c?.key) continue;
                    if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                    byKey.set(c.key, c);
                }

                const mergeOne = (savedCat, defCat) => {
                    if (!savedCat) return defCat;
                    const categoryKey = savedCat.key || defCat?.key;
                    let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                    if (categoryKey === 'sexy') {
                        savedOptions = savedOptions.filter(o => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
                    }
                    const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                    const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                    const mergedOptions = [...savedOptions];
                    for (const opt of defOptions) {
                        if (!opt?.id) continue;
                        if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                    }
                    return {
                        ...savedCat,
                        key: savedCat.key || defCat?.key,
                        title: savedCat.title || defCat?.title,
                        options: mergedOptions,
                    };
                };

                const mergedCats = [];
                for (const def of (defaultCats || [])) {
                    const saved = byKey.get(def.key);
                    mergedCats.push(mergeOne(saved, def));
                    byKey.delete(def.key);
                }
                for (const rest of byKey.values()) {
                    if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                    mergedCats.push(rest);
                }
                return mergedCats;
            };

            if (saved) {
                const parsed = JSON.parse(saved);
                const normalized = normalizeCanonTagCategories(parsed);
                if (normalized) {
                    setCanonTagCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES));
                    return;
                }
            }
            // No saved or invalid saved -> ensure defaults are used
            setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
        } catch (e) {
            // ignore
            setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        try {
            const saved = localStorage.getItem(CANON_IDENTITY_STORAGE_KEY);
            if (!saved) {
                setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
                return;
            }

            const parsed = JSON.parse(saved);
            const normalized = normalizeCanonTagCategories(parsed);

            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);
            const mergeCategoriesByKey = (savedCats, defaultCats) => {
                const byKey = new Map();
                for (const c of (savedCats || [])) {
                    if (!c?.key) continue;
                    if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                    byKey.set(c.key, c);
                }

                const mergeOne = (savedCat, defCat) => {
                    if (!savedCat) return defCat;
                    const savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                    const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                    const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                    const mergedOptions = [...savedOptions];
                    for (const opt of defOptions) {
                        if (!opt?.id) continue;
                        if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                    }
                    return {
                        ...savedCat,
                        key: savedCat.key || defCat?.key,
                        title: savedCat.title || defCat?.title,
                        options: mergedOptions,
                    };
                };

                const mergedCats = [];
                for (const def of (defaultCats || [])) {
                    const saved = byKey.get(def.key);
                    mergedCats.push(mergeOne(saved, def));
                    byKey.delete(def.key);
                }
                for (const rest of byKey.values()) {
                    if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                    mergedCats.push(rest);
                }
                return mergedCats;
            };

            if (normalized) {
                setCanonIdentityCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES));
            } else {
                setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
            }
        } catch (e) {
            // ignore
            setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const canonSelectedTagStrings = () => {
        const selected = [];
        for (const cat of (canonTagCategories || [])) {
            for (const opt of (cat.options || [])) {
                if (canonSelectedTagIds.includes(opt.id)) {
                    selected.push(canonOptionValue(opt));
                }
            }
        }
        return selected;
    };

    const canonSelectedIdentityStrings = () => {
        const selected = [];
        for (const cat of (canonIdentityCategories || [])) {
            for (const opt of (cat.options || [])) {
                if (canonSelectedIdentityIds.includes(opt.id)) {
                    selected.push(canonOptionValue(opt));
                }
            }
        }
        return selected;
    };

    const toggleCanonTagId = (id) => {
        setCanonSelectedTagIds(prev => (
            prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
        ));
    };

    const toggleCanonIdentityId = (id) => {
        setCanonSelectedIdentityIds(prev => (
            prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
        ));
    };

    const newCanonOptionId = (prefix = 'opt') => `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const updateCanonCategoryTitle = (catKey, title) => {
        setCanonTagCategories(prev => (prev || []).map(c => (c.key === catKey ? { ...c, title } : c)));
    };
    const updateCanonOption = (catKey, optId, patch) => {
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return {
                ...c,
                options: (c.options || []).map(o => (o.id === optId ? { ...o, ...patch } : o)),
            };
        }));
    };
    const addCanonOption = (catKey) => {
        const id = newCanonOptionId(catKey);
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id, label: '新标签', detail: '细节描述' }] };
        }));
    };
    const removeCanonOption = (catKey, optId) => {
        setCanonSelectedTagIds(prev => prev.filter(id => id !== optId));
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
    };

    const updateIdentityCategoryTitle = (catKey, title) => {
        setCanonIdentityCategories(prev => (prev || []).map(c => (c.key === catKey ? { ...c, title } : c)));
    };
    const updateIdentityOption = (catKey, optId, patch) => {
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return {
                ...c,
                options: (c.options || []).map(o => (o.id === optId ? { ...o, ...patch } : o)),
            };
        }));
    };
    const addIdentityOption = (catKey) => {
        const id = newCanonOptionId(catKey);
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id, label: '新身份', detail: '细节描述' }] };
        }));
    };
    const removeIdentityOption = (catKey, optId) => {
        setCanonSelectedIdentityIds(prev => prev.filter(id => id !== optId));
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
    };

    const persistCanonIdentityCategories = (categories) => {
        try {
            const normalized = normalizeCanonTagCategories(categories);
            if (!normalized) return false;
            localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(normalized));
            return true;
        } catch (e) {
            return false;
        }
    };

    const closeCanonModal = () => {
        // Best-effort autosave if user was editing tags
        if (canonTagEditMode) {
            const ok = persistCanonTagCategories(canonTagCategories);
            if (ok && onLog) onLog('已保存标签配置（JSON）', 'success');
            const ok2 = persistCanonIdentityCategories(canonIdentityCategories);
            if (ok2 && onLog) onLog('已保存身份标签配置（JSON）', 'success');
        }
        setCanonTagEditMode(false);
        setShowCanonModal(false);
    };

    const handleGenerateScenes = async () => {
        if (!activeEpisode?.id) return;
        const n = Number(sceneGenCount);
        if (Number.isNaN(n) || n <= 0) {
            alert('Please enter a valid scene count.');
            return;
        }
        setSceneGenGenerating(true);
        try {
            if (onLog) onLog(`Generating scenes for episode (target: ${n})`, 'process');
            const res = await generateEpisodeScenes(activeEpisode.id, {
                scene_count: n,
                extra_notes: sceneGenNotes,
                replace_existing_scenes: !!sceneGenReplaceExisting,
            });
            if (onLog) onLog(`Scenes generated: ${res?.scenes_created ?? 0}`, 'success');
            alert(`Scenes generated: ${res?.scenes_created ?? 0}. Open the Scenes tab to view them.`);
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Scene generation failed: ${e.message}`, 'error');
            alert(`Generation failed: ${e.message}`);
        } finally {
            setSceneGenGenerating(false);
        }
    };

    const handleGenerateCanon = async () => {
        if (!activeEpisode?.id) return;
        const name = (canonName || '').trim();
        if (!name) {
            alert('请输入角色名称');
            return;
        }

        const custom = (canonCustomTags || '')
            .split(/[,，\n]/)
            .map(t => t.trim())
            .filter(Boolean);
        const selectedStrings = canonSelectedTagStrings();
        const style_tags = Array.from(new Set([...(selectedStrings || []), ...custom]));

        const identityCustom = (canonCustomIdentity || '')
            .split(/[,，\n]/)
            .map(t => t.trim())
            .filter(Boolean);
        const identityStrings = canonSelectedIdentityStrings();
        const identityMerged = Array.from(new Set([...(identityStrings || []), ...identityCustom]));
        const identity = identityMerged.join(' / ');

        setCanonGenerating(true);
        try {
            if (onLog) onLog(`Generating Character Canon for: ${name}`, 'process');
            const updatedEpisode = await generateEpisodeCharacterProfile(activeEpisode.id, {
                name,
                identity,
                body_features: canonBody,
                style_tags,
                extra_notes: canonExtra,
            });

            if (updatedEpisode?.script_content != null) {
                setRawContent(updatedEpisode.script_content);
            }
            if (onLog) onLog(`Character Canon saved & inserted into script: ${name}`, 'success');
            setShowCanonModal(false);
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Character Canon generation failed: ${e.message}`, 'error');
            alert(`生成失败: ${e.message}`);
        } finally {
            setCanonGenerating(false);
        }
    };

    // Check user role on mount
    useEffect(() => {
        fetchMe().then(user => {
            if (user && user.is_superuser) {
                setIsSuperuser(true);
            }
        }).catch(() => {});
    }, []);

    const handleAnalysisClick = async () => {
        if (!rawContent || rawContent.trim().length < 10) {
            alert("Script content is too short for analysis.");
            return;
        }

        if (isSuperuser) {
            // Fetch default prompt
            try {
                const res = await fetchPrompt("scene_analysis.txt");
                setSystemPrompt(res.content);
                
                // Construct full user prompt with metadata visible
                let fullContent = rawContent;
                if (project?.global_info) {
                     const info = project.global_info;
                     const metaParts = ["Project Overview Context:"];
                     if (info.script_title) metaParts.push(`Title: ${info.script_title}`);
                     if (info.type) metaParts.push(`Type: ${info.type}`);
                     if (info.tone) metaParts.push(`Tone: ${info.tone}`);
                     if (info.Global_Style) metaParts.push(`Global Style: ${info.Global_Style}`);
                     if (info.base_positioning) metaParts.push(`Base Positioning: ${info.base_positioning}`);
                     if (info.lighting) metaParts.push(`Lighting: ${info.lighting}`);
                     if (info.series_episode) metaParts.push(`Episode: ${info.series_episode}`);
                     
                     if (metaParts.length > 1) {
                        fullContent = `${metaParts.join('\n')}\n\nScript to Analyze:\n\n${rawContent}`;
                     }
                }
                
                setUserPrompt(fullContent);
                setShowAnalysisModal(true);
            } catch (e) {
                console.error("Failed to fetch system prompt", e);
                // Fallback if fails
                setSystemPrompt("Error loading system prompt.");
                setUserPrompt(rawContent);
                setShowAnalysisModal(true);
            }
        } else {
             // Normal user flow
            executeAnalysis(rawContent);
        }
    };

    const executeAnalysis = async (content, customSystemPrompt = null, skipMetadata = false) => {
        setIsAnalyzing(true);
        setAnalysisFlowStatus({
            phase: 'analyzing',
            message: t('AI Scene Analysis 进行中...', 'AI Scene Analysis in progress...'),
        });
        if (onLog) onLog("Starting AI Scene Analysis...", "start");

        try {
            // Include project metadata if available, unless skipped (baked in)
            const metadata = skipMetadata ? null : (project?.global_info || null);
            
            const result = await analyzeScene(
                content,
                customSystemPrompt,
                metadata,
                activeEpisode?.id || null,
                analysisAttentionNotes,
                selectedReuseSubjectAssets
            );
            const analyzedText = result.result || result.analysis || (typeof result === 'string' ? result : JSON.stringify(result, null, 2));

            if (result && result.meta) {
                try {
                    const m = result.meta;
                    const usage = m.usage || {};
                    if (onLog) onLog(
                        `AI Analysis meta: sys_chars=${m.system_prompt_chars} user_chars=${m.user_prompt_chars} ` +
                        `est_in=${m.est_input_tokens ?? ''} est_out=${m.est_output_tokens ?? ''} ` +
                        `max_tokens=${m.config_max_tokens_effective ?? m.config_max_tokens ?? ''} ` +
                        `finish=${m.finish_reason ?? ''} output_chars=${m.output_chars ?? ''} ` +
                        `episode_id=${m.request_episode_id ?? ''} saved=${m.saved_to_episode ?? ''} ` +
                        `usage_prompt=${usage.prompt_tokens ?? usage.input_tokens ?? ''} ` +
                        `usage_completion=${usage.completion_tokens ?? usage.output_tokens ?? ''} ` +
                        `usage_total=${usage.total_tokens ?? ''}`,
                        "info"
                    );
                } catch (e) {
                    // ignore meta logging errors
                }
            }

            // Store the raw LLM output separately for viewing/editing (JSON or Markdown table)
            setLlmResultContent(analyzedText);
            lastLoadedAnalysisRef.current = analyzedText;

            // Persist LLM raw output into dedicated DB field (DO NOT overwrite script_content)
            // If backend already saved it (via episode_id), skip the extra PUT to avoid large payload twice.
            const savedByBackend = !!(result?.meta?.saved_to_episode);
            if (!savedByBackend) {
                if (onLog) onLog("Analysis complete. Saving LLM result (separate field)...", "process");
                await persistLlmResultContent(analyzedText);
            } else {
                if (onLog) onLog("Analysis complete. Saved to DB by backend.", "success");
                // Parent episode state may be stale; re-load from DB so the Script tab stays consistent
                // across tab switches/remounts.
                await refreshAnalysisFromDB();
            }
            
            await runAutoImportAndSwitchToScenes(analyzedText);
            if (onLog) onLog("AI Analysis applied and saved.", "success");
            setShowAnalysisModal(false);
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Analysis Failed: ${e.message}`, "error");
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`分析失败：${e.message}`, `Analysis failed: ${e.message}`),
            });
            alert(`Analysis failed: ${e.message}`);
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleSaveAnalysisAttentionNotes = async () => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        setIsSavingAnalysisAttentionNotes(true);
        try {
            const mergedEpisodeInfo = {
                ...(activeEpisode?.episode_info || {}),
                analysis_attention_notes: analysisAttentionNotes || '',
            };
            await onUpdateEpisodeInfo(activeEpisode.id, { episode_info: mergedEpisodeInfo });
            if (onLog) onLog('Episode 1 analysis attention notes saved.', 'success');
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Failed to save analysis attention notes: ${e.message}`, 'error');
        } finally {
            setIsSavingAnalysisAttentionNotes(false);
        }
    };

    const executeAdvancedAnalysis = async (userInput, customSystemPrompt) => {
        if (!activeEpisode?.id) {
            alert("No active episode selected.");
            return;
        }

        setIsAnalyzing(true);
        setAnalysisFlowStatus({
            phase: 'analyzing',
            message: t('AI Scene Analysis 进行中...', 'AI Scene Analysis in progress...'),
        });
        if (onLog) onLog("Starting Advanced AI Analysis (Superuser)...", "start");

        try {
            const result = await analyzeScene(
                userInput,
                customSystemPrompt,
                null,
                activeEpisode?.id || null,
                analysisAttentionNotes,
                selectedReuseSubjectAssets
            );
            const analyzedText = result.result || result.analysis || (typeof result === 'string' ? result : JSON.stringify(result));

            if (result && result.meta) {
                try {
                    const m = result.meta;
                    const usage = m.usage || {};
                    if (onLog) onLog(
                        `AI Analysis meta: sys_chars=${m.system_prompt_chars} user_chars=${m.user_prompt_chars} ` +
                        `est_in=${m.est_input_tokens ?? ''} est_out=${m.est_output_tokens ?? ''} ` +
                        `max_tokens=${m.config_max_tokens_effective ?? m.config_max_tokens ?? ''} ` +
                        `finish=${m.finish_reason ?? ''} output_chars=${m.output_chars ?? ''} ` +
                        `episode_id=${m.request_episode_id ?? ''} saved=${m.saved_to_episode ?? ''} ` +
                        `usage_prompt=${usage.prompt_tokens ?? usage.input_tokens ?? ''} ` +
                        `usage_completion=${usage.completion_tokens ?? usage.output_tokens ?? ''} ` +
                        `usage_total=${usage.total_tokens ?? ''}`,
                        "info"
                    );
                } catch (e) {
                    // ignore meta logging errors
                }
            }

            // Fill Script tab's "LLM 返回结果" immediately
            setLlmResultContent(analyzedText || "");
            lastLoadedAnalysisRef.current = analyzedText || "";

            // Persist the LLM output into dedicated DB field (unless backend already saved it)
            const savedByBackend = !!(result?.meta?.saved_to_episode);
            if (!savedByBackend) {
                if (onLog) onLog("Advanced analysis complete. Saving LLM result (separate field)...", "process");
                await persistLlmResultContent(analyzedText || "");
            } else {
                if (onLog) onLog("Advanced analysis complete. Saved to DB by backend.", "success");
                await refreshAnalysisFromDB();
            }

            await runAutoImportAndSwitchToScenes(analyzedText || "");

            setShowAnalysisModal(false);
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Advanced analysis failed: ${e.message}`, "error");
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`分析失败：${e.message}`, `Analysis failed: ${e.message}`),
            });
            alert(`Analysis failed: ${e.message}`);
        } finally {
            setIsAnalyzing(false);
        }
    };

    if (!activeEpisode) return <div className="p-8 text-muted-foreground">{t('请选择或创建一个分集开始写作。', 'Select or create an episode to start writing.')}</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    {buildEpisodeDisplayLabel({
                        episodeNumber: activeEpisode?.episode_number,
                        title: activeEpisode?.title,
                    })}
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">
                        {isRawMode ? t('原始编辑器', 'Raw Editor') : `${segments.length} ${t('段', 'Segments')}`}
                    </span>
                </h2>
                <div className="flex items-center gap-2">
                    {segments.length > 0 && (
                        <button 
                            onClick={() => setIsRawMode(!isRawMode)} 
                            className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20"
                        >
                            {isRawMode ? t('切换到表格视图', 'Switch to Table View') : t('编辑原始文本', 'Edit Raw Text')}
                        </button>
                    )}
                    {isRawMode && (
                        <button 
                            onClick={handleAnalysisClick} 
                            disabled={isAnalyzing}
                            className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isAnalyzing ? 'bg-purple-900/50 text-purple-200 cursor-not-allowed' : 'bg-purple-600 text-white hover:bg-purple-500'}`}
                            title={t('分析原始剧本并生成结构', 'Analyze raw script to generate structure')}
                        >
                            {isAnalyzing ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" /> {t('分析中...', 'Analyzing...')}
                                </>
                            ) : (
                                <>
                                    <Wand2 className="w-4 h-4" /> {t('AI 场景分析', 'AI Scene Analysis')}
                                </>
                            )}
                        </button>
                    )}
                    {!isRawMode && (
                        <button 
                            onClick={handleMerge} 
                            className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20 flex items-center gap-2"
                            title={t('将所有分段合并为单一剧本', 'Merge all segments into a single script')}
                        >
                            <LayoutList className="w-4 h-4" />
                            {t('合并剧本', 'Merge Script')}
                        </button>
                    )}
                    <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90">{t('保存修改', 'Save Changes')}</button>
                </div>
            </div>

            {analysisFlowStatus.phase !== 'idle' && (
                <div className={`mb-4 rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm ${
                    analysisFlowStatus.phase === 'failed'
                        ? 'border-red-500/30 bg-red-500/10 text-red-200'
                        : analysisFlowStatus.phase === 'completed'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                            : 'border-purple-500/30 bg-purple-500/10 text-purple-100'
                }`}>
                    {analysisFlowStatus.phase === 'completed' ? (
                        <CheckCircle className="w-4 h-4" />
                    ) : analysisFlowStatus.phase === 'failed' ? (
                        <X className="w-4 h-4" />
                    ) : (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    )}
                    <span>{analysisFlowStatus.message}</span>
                </div>
            )}

            <div className="flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col">
                <div className="flex-1 overflow-hidden">
                    {isRawMode ? (
                        <div className="h-full w-full flex flex-col overflow-hidden">
                            <div className="px-6 py-3 border-b border-white/10 bg-black/10 flex items-center justify-between">
                                <div className="text-sm text-primary uppercase font-extrabold tracking-wide">{t('输入脚本（Input）', 'Script Input')}</div>
                                <div className="text-[10px] text-muted-foreground">{(rawContent || '').length} {t('字符', 'chars')}</div>
                            </div>
                            <textarea 
                                className="w-full flex-1 min-h-[420px] p-6 bg-transparent text-white/90 font-mono text-sm leading-relaxed focus:outline-none custom-scrollbar resize-none"
                                placeholder={t('在这里粘贴或输入你的剧本...', 'Paste or type your script here...')}
                                value={rawContent}
                                onChange={(e) => setRawContent(e.target.value)}
                            />

                            {isEpisodeOnePage && (
                                <div className="border-t border-white/10 px-6 py-4 bg-black/10">
                                    <div className="text-xs font-semibold uppercase text-muted-foreground">Episode 1 · 必复用 Subject 资产（可为空）</div>
                                    <div className="text-[11px] text-muted-foreground mt-1 mb-2">
                                        勾选后会将选中 Subject 的名称和描述一并发送给 AI Scene Analysis，作为必须复用资产（不重新生成）。
                                    </div>
                                    <div className="mb-2 grid grid-cols-1 md:grid-cols-2 gap-2">
                                        <select
                                            value={reuseSubjectTypeFilter}
                                            onChange={(e) => setReuseSubjectTypeFilter(e.target.value)}
                                            className="w-full bg-black/30 border border-white/10 rounded-md px-3 py-2 text-xs text-white/90 focus:outline-none focus:border-primary/50"
                                        >
                                            <option value="all">{t('全部类型', 'All Types')}</option>
                                            {reuseSubjectTypeOptions.map((type) => (
                                                <option key={type} value={type}>{type}</option>
                                            ))}
                                        </select>
                                        <input
                                            type="text"
                                            value={reuseSubjectKeyword}
                                            onChange={(e) => setReuseSubjectKeyword(e.target.value)}
                                            placeholder={t('搜索名称 / 描述 / 锚点', 'Search name / description / anchor')}
                                            className="w-full bg-black/30 border border-white/10 rounded-md px-3 py-2 text-xs text-white/90 focus:outline-none focus:border-primary/50"
                                        />
                                    </div>
                                    <div className="mb-2 flex justify-end">
                                        <button
                                            type="button"
                                            onClick={clearReuseSubjectFilters}
                                            disabled={!hasActiveReuseSubjectFilters}
                                            className={`px-2.5 py-1.5 rounded-md text-[11px] font-semibold ${hasActiveReuseSubjectFilters ? 'bg-white/10 hover:bg-white/20 text-white' : 'bg-white/5 text-muted-foreground cursor-not-allowed'}`}
                                        >
                                            {t('清除筛选', 'Clear Filters')}
                                        </button>
                                    </div>
                                    {isLoadingSubjectAssets ? (
                                        <div className="text-xs text-muted-foreground">{t('正在加载 subject 资产...', 'Loading subject assets...')}</div>
                                    ) : availableSubjectAssets.length === 0 ? (
                                        <div className="text-xs text-muted-foreground">{t('当前项目未找到 subject 资产。', 'No subject assets found in this project.')}</div>
                                    ) : filteredSubjectAssets.length === 0 ? (
                                        <div className="text-xs text-muted-foreground">{t('没有匹配当前筛选条件的 subject 资产。', 'No subject assets match current filters.')}</div>
                                    ) : (
                                        <div className="max-h-40 overflow-auto custom-scrollbar border border-white/10 rounded-md bg-black/20 p-2 space-y-1">
                                            {filteredSubjectAssets.map(asset => {
                                                const checked = selectedReuseSubjectIds.includes(String(asset.id));
                                                return (
                                                    <label key={asset.id} className="flex items-start gap-2 text-xs text-white/90 p-1.5 rounded hover:bg-white/5 cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            className="mt-0.5 accent-primary"
                                                            checked={checked}
                                                            onChange={() => toggleReuseSubject(asset.id)}
                                                        />
                                                        <span>
                                                            <span className="font-semibold">[{asset.type || 'subject'}] {asset.name || `ID ${asset.id}`}</span>
                                                            <span className="text-muted-foreground block line-clamp-2">{asset.description || asset.narrative_description || asset.anchor_description || t('无描述', 'No description')}</span>
                                                        </span>
                                                    </label>
                                                );
                                            })}
                                        </div>
                                    )}
                                    <div className="mt-2 flex items-center justify-between">
                                                <div className="text-[11px] text-muted-foreground">{t('显示', 'Showing')} {filteredSubjectAssets.length}/{availableSubjectAssets.length} {t('个，已选择', ', selected')} {selectedReuseSubjectAssets.length} {t('个 subject 作为必须复用资产', 'subjects as required reuse assets')}</div>
                                        <button
                                            onClick={handleSaveReuseSubjects}
                                            disabled={isSavingReuseSubjects}
                                            className={`px-3 py-2 rounded-md text-xs font-bold ${isSavingReuseSubjects ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                                        >
                                            {isSavingReuseSubjects ? t('保存中...', 'Saving...') : t('保存复用 Subject', 'Save Reuse Subjects')}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {isEpisodeOnePage && (
                                <div className="border-t border-white/10 px-6 py-4 bg-black/10">
                                    <div className="text-xs font-semibold uppercase text-muted-foreground">Episode 1 · AI Scene Analysis 补充说明（可为空）</div>
                                    <div className="text-[11px] text-muted-foreground mt-1 mb-2">
                                        该项可为空。补充要求通常用于特别强调资产生成或关键执行要求；点击 AI Scene Analysis 时会作为高优先级约束注入。
                                    </div>
                                    <textarea
                                        value={analysisAttentionNotes}
                                        onChange={(e) => setAnalysisAttentionNotes(e.target.value)}
                                        placeholder="可留空；例如：必须严格按轴线拆分、保留关键道具锚点、避免漏掉反应镜头、环境命名必须 Front/Reverse。"
                                        className="w-full h-24 bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white/90 focus:outline-none focus:border-primary/50 custom-scrollbar resize-none"
                                    />
                                    <div className="mt-2 flex justify-end">
                                        <button
                                            onClick={handleSaveAnalysisAttentionNotes}
                                            disabled={isSavingAnalysisAttentionNotes}
                                            className={`px-3 py-2 rounded-md text-xs font-bold ${isSavingAnalysisAttentionNotes ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                                        >
                                            {isSavingAnalysisAttentionNotes ? t('保存中...', 'Saving...') : t('保存补充说明', 'Save Attention Notes')}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="overflow-auto custom-scrollbar h-full w-full">
                            <table className="w-full text-left border-collapse text-sm">
                                <thead className="bg-white/5 sticky top-0 z-10 backdrop-blur-md">
                                    <tr>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-16">ID</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-48">Title</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground min-w-[300px]">Content (Revised)</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground min-w-[300px]">Content (Original)</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-48">Narrative Function</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-64">Analysis & Adaptation Notes</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {segments.map((seg, idx) => (
                                        <tr key={idx} className="hover:bg-white/5 transition-colors group">
                                            <td className="p-4 align-top font-mono text-xs text-muted-foreground">{seg.id}</td>
                                            <td className="p-4 align-top font-bold text-primary">
                                                {seg.title}
                                            </td>
                                            <td className="p-4 align-top">
                                                <textarea 
                                                    className="w-full bg-transparent border-none text-white/90 leading-relaxed font-serif focus:outline-none focus:ring-0 resize-none overflow-hidden"
                                                    style={{ minHeight: '60px' }}
                                                    ref={(el) => {
                                                        if (el) {
                                                            el.style.height = 'auto';
                                                            el.style.height = el.scrollHeight + 'px';
                                                        }
                                                    }}
                                                    onInput={(e) => {
                                                        e.target.style.height = 'auto';
                                                        e.target.style.height = e.target.scrollHeight + 'px';
                                                    }}
                                                    value={seg.content || ''}
                                                    onChange={(e) => handleSegmentChange(idx, 'content', e.target.value)}
                                                />
                                            </td>
                                            <td className="p-4 align-top whitespace-pre-wrap text-muted-foreground leading-relaxed text-xs italic">
                                                {seg.original}
                                            </td>
                                            <td className="p-4 align-top text-xs text-muted-foreground whitespace-pre-wrap">
                                                {seg.narrative_role}
                                            </td>
                                            <td className="p-4 align-top text-xs text-indigo-300/80 bg-white/5 group-hover:bg-white/10 whitespace-pre-wrap">
                                                {seg.analysis}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                <div className="border-t border-white/10 bg-black/10 shrink-0">
                    <div className="px-6 py-3 border-b border-white/10">
                        <div className="text-sm text-primary uppercase font-extrabold tracking-wide">{t('分析输出工作区（Output Workspace）', 'Analysis Output Workspace')}</div>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
                        <div className="border-b lg:border-b-0 lg:border-r border-white/10">
                            <div className="px-6 py-3 flex items-center justify-between">
                                <div className="text-sm text-white uppercase font-bold tracking-wide">{t('LLM 返回结果', 'LLM Result')}</div>
                                <button
                                    onClick={() => doImportText(llmResultContent, 'auto')}
                                    className="px-3 py-1.5 rounded-md text-[10px] font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-white/80"
                                    title={t('从 LLM markdown/table 结果导入', 'Import from LLM markdown/table result')}
                                >
                                    {t('导入 LLM 返回结果', 'Import LLM Result')}
                                </button>
                            </div>
                            <textarea
                                className="w-full h-44 px-6 pb-6 bg-transparent text-white/90 font-mono text-xs leading-relaxed focus:outline-none custom-scrollbar resize-none"
                                placeholder={t('在这里粘贴或编辑 LLM 结果（支持 Markdown/表格/JSON 混合）。', 'Paste or edit the LLM result here (Markdown/table/JSON mixed is ok).')}
                                value={llmResultContent}
                                onChange={(e) => setLlmResultContent(e.target.value)}
                                onBlur={() => persistLlmResultContent(llmResultContent)}
                            />
                        </div>

                        <div>
                            <div className="px-6 py-3 flex items-center justify-between">
                                <div className="text-sm text-white uppercase font-bold tracking-wide">{t('JSON 返回结果', 'JSON Result')}</div>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => {
                                            const payload = getEGlobalInfoPayloadFromJsonText(llmResultContent);
                                            if (!payload) {
                                                if (onLog) onLog('No e_global_info found in JSON.', 'warning');
                                                return;
                                            }
                                            doImportText(JSON.stringify(payload, null, 2), 'json');
                                        }}
                                        className="px-2.5 py-1.5 rounded-md text-[10px] font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-white/80"
                                        title={t('导入第 1 部分：e_global_info', 'Import Part 1: e_global_info')}
                                    >
                                        {t('导入 e_global_info', 'Import e_global_info')}
                                    </button>
                                    <button
                                        onClick={() => {
                                            const payload = getEntitiesPayloadFromJsonText(llmResultContent);
                                            if (!payload) {
                                                if (onLog) onLog('No entities JSON (characters/props/environments) found.', 'warning');
                                                return;
                                            }
                                            doImportText(JSON.stringify(payload, null, 2), 'json');
                                        }}
                                        className="px-2.5 py-1.5 rounded-md text-[10px] font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-white/80"
                                        title={t('导入第 3 部分：实体 JSON', 'Import Part 3: entities JSON')}
                                    >
                                        {t('导入实体', 'Import Entities')}
                                    </button>
                                </div>
                            </div>
                            <textarea
                                className="w-full h-44 px-6 pb-6 bg-transparent text-white/90 font-mono text-xs leading-relaxed focus:outline-none custom-scrollbar resize-none"
                                placeholder="未检测到可解析的 JSON（如果 LLM 返回了 ```json ...``` 或纯 JSON，这里会显示）。"
                                value={llmJsonResultContent}
                                readOnly
                            />
                        </div>
                    </div>
                </div>

            </div>

            {showAnalysisModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setShowAnalysisModal(false)}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-6xl h-[90vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Wand2 className="w-5 h-5 text-purple-500" />
                                Advanced AI Analysis (Superuser)
                            </h3>
                            <button onClick={() => setShowAnalysisModal(false)} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        
                        <div className="flex-1 p-6 grid grid-cols-2 gap-6 overflow-hidden">
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    System Prompt
                                    <span className="text-xs font-normal opacity-70">Define the AI persona & rules</span>
                                </label>
                                <textarea
                                    className="flex-1 w-full bg-black/30 border border-white/10 text-white/90 p-3 font-mono text-xs leading-relaxed rounded-lg focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                    value={systemPrompt}
                                    onChange={(e) => setSystemPrompt(e.target.value)}
                                    spellCheck={false}
                                />
                            </div>
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    User Input (Script)
                                    <span className="text-xs font-normal opacity-70">The content to act upon</span>
                                </label>
                                <textarea
                                    className="flex-1 w-full bg-black/30 border border-white/10 text-white/90 p-3 font-mono text-sm leading-relaxed rounded-lg focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                    value={userPrompt}
                                    onChange={(e) => setUserPrompt(e.target.value)}
                                    spellCheck={false}
                                />
                            </div>
                        </div>
                        
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                             <button
                                onClick={() => {
                                    const fullText = `[System Instruction]\n${systemPrompt}\n\n[User Input]\n${userPrompt}`;
                                    navigator.clipboard.writeText(fullText);
                                    if(onLog) onLog(t('完整提示词已复制到剪贴板。', 'Copied full prompt to clipboard.'), "success");
                                    alert(t('完整提示词已复制！', 'Full prompt copied!'));
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg font-medium transition-colors text-white border border-white/10"
                             >
                                <Copy className="w-4 h-4" /> {t('复制完整提示词', 'Copy Full Prompt')}
                             </button>
                             <button 
                                          onClick={() => executeAdvancedAnalysis(userPrompt, systemPrompt)}
                                disabled={isAnalyzing}
                                className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                             >
                                {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                                          {t('运行分析', 'Run Analysis')}
                             </button>
                        </div>
                    </div>
                </div>
            )}

            {showMerged && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setShowMerged(false)}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <ScrollText className="w-5 h-5 text-primary" />
                                Merged Script
                            </h3>
                            <button onClick={() => setShowMerged(false)} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="flex-1 p-6 overflow-hidden">
                            <textarea
                                className="w-full h-full bg-black/30 border border-white/10 text-white p-4 font-serif text-lg leading-relaxed rounded-lg focus:outline-none focus:border-primary/50 resize-none custom-scrollbar"
                                value={mergedContent}
                                readOnly
                            />
                        </div>
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                             <button 
                                onClick={() => {
                                    navigator.clipboard.writeText(mergedContent);
                                    alert("Script copied to clipboard!");
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors text-white"
                             >
                                <Copy className="w-4 h-4" /> Copy to Clipboard
                             </button>
                             <button 
                                onClick={() => setShowMerged(false)}
                                className="px-4 py-2 bg-primary text-black rounded-lg font-bold hover:bg-primary/90"
                             >
                                Close
                             </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};


const MediaDetailModal = ({ media, onClose }) => {
    if (!media) return null;

    return (
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8" onClick={onClose}>
             <div className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden max-w-6xl w-full max-h-[90vh] flex shadow-2xl" onClick={e => e.stopPropagation()}>
                {/* Media Area */}
                <div className="flex-1 bg-black/50 flex items-center justify-center p-4 relative group/modal min-h-[400px]">
                    {media.type === 'video' ? (
                        <video src={getFullUrl(media.url)} controls autoPlay className="max-w-full max-h-full shadow-lg rounded" />
                    ) : (
                        <img src={getFullUrl(media.url)} className="max-w-full max-h-full object-contain shadow-lg rounded" alt="Detail" />
                    )}
                    
                    <button 
                        className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full hover:bg-white/20 transition-colors"
                        onClick={onClose}
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Metadata Sidebar */}
                <div className="w-80 bg-[#151515] border-l border-white/10 p-6 flex flex-col gap-4 overflow-y-auto shrink-0">
                    <div>
                        <h3 className="text-xl font-bold text-white mb-1 truncate" title={media.title || 'Media Details'}>{media.title || 'Media Details'}</h3>
                        <div className="text-xs text-muted-foreground uppercase font-bold">{media.type || 'Image'} Asset</div>
                    </div>

                    <div className="space-y-4">
                        {media.prompt && (
                             <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                <span className="text-[10px] uppercase font-bold text-primary/70 block mb-1">Prompt / Description</span>
                                <p className="text-xs text-gray-300 leading-relaxed font-mono">
                                    {media.prompt}
                                </p>
                            </div>
                        )}
                        
                        <div className="grid grid-cols-2 gap-2">
                             <div className="bg-white/5 p-2 rounded border border-white/5">
                                <span className="text-[10px] uppercase text-gray-500 block">Resolution</span>
                                <span className="text-xs text-gray-300">{media.resolution || 'Unknown'}</span>
                            </div>
                             <div className="bg-white/5 p-2 rounded border border-white/5">
                                <span className="text-[10px] uppercase text-gray-500 block">Source</span>
                                <span className="text-xs text-gray-300">{media.source || 'Generated'}</span>
                            </div>
                        </div>

                         {/* JSON Metadata */}
                         {media.metadata && (
                            <div className="space-y-1">
                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Technical Metadata</h4>
                                <div className="p-2 bg-black/40 rounded border border-white/5 text-[10px] font-mono text-gray-400 overflow-x-auto whitespace-pre-wrap">
                                    {typeof media.metadata === 'string' ? media.metadata : JSON.stringify(media.metadata, null, 2)}
                                </div>
                            </div>
                         )}

                         <div className="mt-auto pt-4 border-t border-white/10">
                            <a href={media.url} download target="_blank" rel="noopener noreferrer" className="w-full py-2 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded flex items-center justify-center gap-2 text-sm font-medium transition-colors">
                                <Download size={16}/> Download Original
                            </a>
                         </div>
                    </div>
                </div>
             </div>
        </div>
    );
};

const MediaPickerModal = ({ isOpen, onClose, onSelect, projectId, context = {}, entities = [], episodeId = null, uiLang = 'zh' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [tab, setTab] = useState('assets');
    const [assets, setAssets] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); // Detail/Preview Mode
    
    // Filters
    const [filterScope, setFilterScope] = useState('project'); // 'project', 'subject', 'shot', 'type'
    const [filterType, setFilterType] = useState('all'); // 'all', 'image', 'video'
    const [filterValue, setFilterValue] = useState(''); // entity_id or shot_id or entity_type
    
    const [availableShots, setAvailableShots] = useState([]);

    useEffect(() => {
        if (isOpen) {
             setSelectedAsset(null); // Reset detail view on open
        }
        if (isOpen && tab === 'assets') {
             // Reset filters if context is provided?
             // If context has entityId, maybe default to subject?
             if (context.entityId && filterScope === 'project') {
                 setFilterScope('subject');
                 setFilterValue(context.entityId);
             } else if (context.shotId && filterScope === 'project') {
                 // setFilterScope('shot'); // Optional: heuristic
                 // setFilterValue(context.shotId);
             }
        }
    }, [isOpen]);

    useEffect(() => {
         // Load shots if needed
         if (filterScope === 'shot' && episodeId && availableShots.length === 0) {
             fetchEpisodeShots(episodeId).then(data => {
                 setAvailableShots(data.sort((a,b) => {
                      // simple sort by shot_id alphanumeric
                      return a.shot_id.localeCompare(b.shot_id, undefined, { numeric: true });
                 }));
             }).catch(console.error);
         }
    }, [filterScope, episodeId]);

    useEffect(() => {
        if (isOpen && tab === 'assets') {
            loadAssets();
        }
    }, [isOpen, tab, filterScope, filterType, filterValue]);

    const loadAssets = () => {
        setLoading(true);
        const params = {};
        if (filterType !== 'all') params.type = filterType;
        
        // Base scope is Project
        if (projectId) params.project_id = projectId;
        
        // Refine scope
        let clientSideFilterIds = null; // If set, filter by these entity IDs locally

        if (filterScope === 'subject' && filterValue) {
            params.entity_id = filterValue;
        } else if (filterScope === 'shot' && filterValue) {
            params.shot_id = filterValue;
        } else if (filterScope === 'type' && filterValue) {
            // "By Type" strategy: Fetch project assets, then filter by entity_id belonging to that type
            // Find all entities of this type
            const targetEntities = entities.filter(e => (e.type || 'prop').toLowerCase() === filterValue.toLowerCase());
            clientSideFilterIds = new Set(targetEntities.map(e => e.id));
        }
        
        fetchAssets(params).then(data => {
            let res = data || [];
            
            // Client-side filtering for Entity Type logic (if backend doesn't support recursive type filtering)
            if (clientSideFilterIds) {
                res = res.filter(a => {
                    const eid = a.meta_info?.entity_id;
                    return eid && clientSideFilterIds.has(Number(eid));
                });
            }

            setAssets(res);
        }).catch(console.error).finally(() => setLoading(false));
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true);
        try {
            // Attach context to upload
            const meta = {};
            if (projectId) meta.project_id = projectId;
            if (context.entityId) meta.entity_id = context.entityId;
            if (context.shotId) meta.shot_id = context.shotId;

            const asset = await uploadAsset(file, meta); 
            if (asset && asset.url) {
                onSelect(asset.url, asset.type || (file.type.startsWith('video') ? 'video' : 'image'));
            }
            if (tab === 'assets') loadAssets();
        } catch (e) {
            console.error("Upload failed", e);
            alert("Upload failed: " + e.message);
        } finally {
            setUploading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[110] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
             <div className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-2xl h-[600px] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/20">
                    <h3 className="font-bold text-md">Select Media</h3>
                    <button onClick={onClose} className="text-white/50 hover:text-white"><X size={20} /></button>
                </div>

                <div className="flex border-b border-white/10">
                    {['assets', 'upload', 'url'].map(t => (
                        <button
                            key={t}
                            onClick={() => setTab(t)}
                            className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${tab === t ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'}`}
                        >
                            {t.charAt(0).toUpperCase() + t.slice(1)}
                        </button>
                    ))}
                </div>

                {/* Filters Bar */}
                {tab === 'assets' && (
                    <div className="flex items-center gap-2 p-3 bg-black/10 border-b border-white/5 flex-wrap">
                        <select 
                            value={filterScope}
                            onChange={(e) => {
                                setFilterScope(e.target.value);
                                setFilterValue('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="project">All Project Assets</option>
                            <option value="type">By Subject Type</option>
                            <option value="subject">By Exact Subject</option>
                            <option value="shot">By Storyboard (Shot)</option>
                        </select>

                        {/* Refinement Selector */}
                        {filterScope === 'type' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">Select Type...</option>
                                <option value="character">Characters</option>
                                <option value="prop">Props</option>
                                <option value="environment">Environments</option>
                            </select>
                        )}

                        {filterScope === 'subject' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">Select Subject...</option>
                                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                            </select>
                        )}

                        {filterScope === 'shot' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">{t('选择镜头...', 'Select Shot...')}</option>
                                {availableShots.map(s => <option key={s.id} value={s.id}>{s.shot_id} - {s.shot_name || t('未命名', 'Untitled')}</option>)}
                            </select>
                        )}

                        <select 
                            value={filterType}
                            onChange={(e) => setFilterType(e.target.value)}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="all">All Types</option>
                            <option value="image">Images Only</option>
                            <option value="video">Videos Only</option>
                        </select>
                        
                        <div className="ml-auto text-[10px] text-muted-foreground">
                            {assets.length} results
                        </div>
                    </div>
                )}

                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#151515]">
                    {tab === 'assets' && (
                        loading ? <div className="flex items-center justify-center h-full"><RefreshCw className="animate-spin text-muted-foreground"/></div> :
                        <div className="grid grid-cols-4 gap-3">
                            {assets.map(asset => (
                                <div 
                                    key={asset.id} 
                                    onClick={() => setSelectedAsset(asset)}
                                    className="aspect-square bg-black/40 rounded overflow-hidden border border-white/5 hover:border-primary/50 cursor-pointer group relative"
                                >
                                    {asset.type === 'video' ? (
                                        <div className="w-full h-full flex items-center justify-center bg-black">
                                            <Video className="text-white/50 group-hover:text-primary transition-colors"/>
                                        </div>
                                    ) : (
                                        <img src={getFullUrl(asset.url)} alt="asset" className="w-full h-full object-cover" />
                                    )}
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                    <div className="absolute bottom-0 inset-x-0 p-1 bg-black/60 text-[9px] truncate text-white/70">
                                        {asset.name}
                                    </div>
                                    {/* Quick Select Button on Hover */}
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); onSelect(asset.url, asset.type); }}
                                        className="absolute top-1 right-1 bg-primary text-black p-1 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:scale-110 shadow-lg"
                                        title={t('快速选择', 'Quick Select')}
                                    >
                                        <Check size={12} strokeWidth={3} />
                                    </button>
                                </div>
                            ))}
                            {assets.length === 0 && <div className="col-span-4 text-center text-muted-foreground py-8">{t('未找到素材', 'No assets found')}</div>}
                        </div>
                    )}
                    
                    {/* Asset Detail Overlay */}
                    {selectedAsset && (
                        <div className="absolute inset-0 bg-[#1e1e1e] z-20 flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-200">
                             <div className="flex justify-between items-center p-3 border-b border-white/10 bg-black/20">
                                <h4 className="font-bold text-sm flex items-center gap-2">
                                    <button onClick={() => setSelectedAsset(null)} className="hover:bg-white/10 p-1 rounded"><ArrowLeft size={16}/></button>
                                    {t('素材详情', 'Asset Details')}
                                </h4>
                                <div className="flex gap-2">
                                     <button 
                                        onClick={() => { onSelect(selectedAsset.url, selectedAsset.type); }}
                                        className="bg-primary text-black text-xs font-bold px-3 py-1.5 rounded hover:opacity-90 flex items-center gap-1"
                                     >
                                        <Check size={14}/> Select This Asset
                                     </button>
                                </div>
                            </div>
                            <div className="flex-1 overflow-hidden flex">
                                <div className="flex-1 bg-black/40 flex items-center justify-center p-4">
                                     {selectedAsset.type === 'video' ? (
                                        <video src={getFullUrl(selectedAsset.url)} controls className="max-w-full max-h-full rounded shadow-lg"/>
                                     ) : (
                                        <img src={getFullUrl(selectedAsset.url)} className="max-w-full max-h-full object-contain rounded shadow-lg"/>
                                     )}
                                </div>
                                <div className="w-80 bg-[#151515] border-l border-white/10 p-4 overflow-y-auto space-y-4">
                                    <div>
                                        <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('名称', 'Name')}</label>
                                        <div className="text-sm font-medium">{selectedAsset.name || t('未命名', 'Untitled')}</div>
                                    </div>
                                    
                                    {selectedAsset.meta_info?.entity_id && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">Linked Entity</label>
                                            <div className="text-xs bg-white/5 p-2 rounded border border-white/5 mt-1">
                                                {entities.find(e => e.id === Number(selectedAsset.meta_info.entity_id))?.name || `Entity #${selectedAsset.meta_info.entity_id}`}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {selectedAsset.meta_info?.shot_id && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">Source Shot</label>
                                            <div className="text-xs bg-white/5 p-2 rounded border border-white/5 mt-1">
                                                {availableShots.find(s => s.id === Number(selectedAsset.meta_info.shot_id))?.shot_id || `Shot #${selectedAsset.meta_info.shot_id}`}
                                            </div>
                                        </div>
                                    )}

                                    {selectedAsset.meta_info?.prompt && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">Prompt</label>
                                            <div className="text-xs text-gray-400 bg-white/5 p-2 rounded border border-white/5 mt-1 max-h-[150px] overflow-y-auto custom-scrollbar">
                                                {selectedAsset.meta_info.prompt}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {/* Detailed Technical Metadata */}
                                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/5">
                                         {selectedAsset.meta_info?.resolution && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Resolution</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.resolution}</div>
                                            </div>
                                         )}
                                         {selectedAsset.meta_info?.size && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Size</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.size}</div>
                                            </div>
                                         )}
                                          {selectedAsset.meta_info?.format && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Format</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.format}</div>
                                            </div>
                                         )}
                                          {selectedAsset.meta_info?.duration && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Duration</label>
                                                <div className="text-xs text-gray-300">{/* Normalize 5.0 to 5s */}
                                                {String(selectedAsset.meta_info.duration).endsWith('.0') ? parseInt(selectedAsset.meta_info.duration) : selectedAsset.meta_info.duration}s
                                                </div>
                                            </div>
                                         )}
                                    </div>

                                    <div className="text-[10px] text-muted-foreground pt-4 border-t border-white/5">
                                        {t('文件', 'File')}: {selectedAsset.url.split('/').pop()} <br/>
                                        {t('创建时间', 'Created')}: {new Date(selectedAsset.created_at).toLocaleString()}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {tab === 'upload' && (
                        <div className="flex flex-col items-center justify-center h-full space-y-4">
                            <div className="p-8 border-2 border-dashed border-white/10 rounded-xl bg-black/20 hover:border-primary/50 hover:bg-primary/5 transition-all w-full max-w-sm flex flex-col items-center justify-center cursor-pointer relative">
                                <input 
                                    type="file" 
                                    accept="image/*,video/*" 
                                    onChange={handleUpload}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                    disabled={uploading} 
                                />
                                {uploading ? <RefreshCw className="animate-spin text-primary mb-2" size={32} /> : <Upload className="text-muted-foreground mb-2" size={32} />}
                                <span className="text-sm font-medium text-muted-foreground">
                                    {uploading ? t('上传中...', 'Uploading...') : t('点击或拖拽文件到此处', 'Click or drop file here')}
                                </span>
                            </div>
                        </div>
                    )}

                    {tab === 'url' && (
                         <div className="flex flex-col items-center justify-center h-full">
                            <div className="w-full max-w-sm space-y-4">
                                <div>
                                    <label className="text-xs font-bold uppercase text-muted-foreground mb-1 block">{t('图片 / 视频 URL', 'Image / Video URL')}</label>
                                    <input 
                                        type="text" 
                                        id="media-url-input"
                                        placeholder="https://..." 
                                        className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:border-primary/50 outline-none"
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') onSelect(e.target.value, 'image'); // Default to image on enter, user can correct contexts usually know
                                        }}
                                    />
                                </div>
                                <button 
                                    onClick={() => {
                                        const val = document.getElementById('media-url-input').value;
                                        if (val) onSelect(val, 'image');
                                    }}
                                    className="w-full py-2 bg-primary text-black font-bold rounded hover:opacity-90"
                                >
                                    Confirm
                                </button>
                            </div>
                        </div>
                    )}
                </div>
             </div>
        </div>
    );
};

const ReferenceManager = ({ shot, entities, onUpdate, title = "Reference Images", promptText = "", onPickMedia = null, useSequenceLogic = false, storageKey = "ref_image_urls", additionalAutoRefs = [], strictPromptOnly = false, onFindPrevFrame = null, uiLang = 'zh' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [selectedImage, setSelectedImage] = useState(null);

    // 1. Parsing Entities Logic
    const getEntityMatches = () => {
        if (!shot || !entities.length) return [];
        
        // 1. Collect Raw Strings
        const rawMatches = [];
        
        // Source 1: Associated Entities (if allowed)
        if (!strictPromptOnly && shot.associated_entities) {
            rawMatches.push(...shot.associated_entities.split(/[,，]/));
        }
        
        // Source 2: Prompt Text - Extract content inside [], {}, 【】, ｛｝ and standalone @Name
        // Use [\s\S]+? to capture anything (including newlines) until the first closing bracket.
        // This is robust against strange characters and newlines.
        const regexes = [
            /\[([\s\S]+?)\]/g,    // [...]
            /\{([\s\S]+?)\}/g,    // {...}
            /【([\s\S]+?)】/g,     // 【...】
            /｛([\s\S]+?)｝/g,      // ｛...｝ (Full-width braces)
            /(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)/g // standalone @Name
        ];

        if (promptText) {
            regexes.forEach(regex => {
                let match;
                regex.lastIndex = 0;
                while ((match = regex.exec(promptText)) !== null) {
                    if (match[1]) rawMatches.push(match[1]);
                }
            });
        }
        
        // Manual override for tricky nested cases or if regex fails:
        // Try to find specific pattern {Entity (...)}
        const complexRegex = /\{([^\}]+?)\}\(/g; // Look for } followed by (
        // Actually the main regex should catch {Entity...} fine.
        
        const uniqueRaws = [...new Set(rawMatches.map(s => s.trim()).filter(Boolean))];
        
        // Helper to normalize punctuation while preserving full name semantics
        const normalize = (str) => {
            return (str || '')
                .replace(/[（【〔［]/g, '(')
                .replace(/[）】〕］]/g, ')')
                .replace(/[“”"']/g, '') // Remove quotes
                .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
                .replace(/^@+/, '')
                .replace(/\s+/g, ' ')   // Collapse spaces
                .trim()
                .toLowerCase();
        };

        // 2. Generate Search Candidates
        const candidates = new Set();
        uniqueRaws.forEach(raw => {
            // Remove outer brackets [] {} first
            const content = raw.replace(/[\[\]\{\}【】｛｝]/g, '');
            
            // Strict mode: only keep full normalized token (no parenthesis/content stripping)
            const base = normalize(content);
            if (base) candidates.add(base);
        });

        // 3. Match against Entities
        return entities.filter(e => {
            const cn = normalize(e.name);
            const en = normalize(e.name_en);
            
            // Skip empty entities
            if (!cn && !en) return false;

            // Check if ANY candidate matches this entity
            const isMatch = Array.from(candidates).some(cand => {
                // Algorithm: 
                // 1. Exact Match (Highest Priority) - Reference content vs Entity Name
                // User Requirement: Strict Name Matching. NO partial match allowed between candidates and Entity Name.
                // e.g. "Isabella (脏污)" != "Isabella (精致妆容)"
                // BUT "Isabella" candidate should match "Isabella" entity.
                
                // IMPORTANT: The `candidates` set contains BOTH raw strings (e.g. "isabella(dirty)") 
                // without stripped variants, to enforce full-name matching.
                
                // So we just need to ensure that the candidate string IS EXACTLY equal to the entity name.
                // We should NOT do .includes() checks anymore per request.

                if (cn && cand === cn) return true;
                if (en && cand === en) return true;

                return false;
            });
            // Optional: Log Failures for target specific debugging
            // if (e.name.includes("动物园")) console.log(`Checking Entity [${e.name}] (norm: ${cn}) against`, Array.from(candidates), isMatch);
            
            return isMatch;
        });
    };

    let activeRefs = [];
    const tech = JSON.parse(shot.technical_notes || '{}');
    
    // Normal Mode vs Sequence Mode
    if (useSequenceLogic) {
        // Force Order: [Start Frame, ...Keyframes, End Frame]
        if (shot.image_url) activeRefs.push(shot.image_url);
        if (tech.keyframes && Array.isArray(tech.keyframes)) {
            activeRefs.push(...tech.keyframes);
        }
        if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
        // Deduplicate while preserving order if needed, but for sequence, duplicates might differ by position technically
        // but image url same means same image. Let's uniq by URL to avoid UI keys issues
        activeRefs = [...new Set(activeRefs)];
    } else {
        // Standard entity/manual ref logic
        const isManualMode = tech[storageKey] && Array.isArray(tech[storageKey]);
           const userEditedKey = `${storageKey}_user_edited`;
           const isUserEdited = Boolean(tech[userEditedKey]);
           const isLockedManual = isManualMode && isUserEdited;
        
        // User Request: Refs (Video) should NOT do entity identification (only start/end/keyframes).
        const shouldDetectEntities = storageKey !== 'video_ref_image_urls';
        const autoMatches = shouldDetectEntities ? getEntityMatches().map(e => e.image_url).filter(Boolean) : [];

           if (isLockedManual) {
               // 用户已手动调整后：完全以用户列表为准，不再自动匹配/注入
               activeRefs = [...tech[storageKey]];
           } else if (isManualMode) {
             // Manual Mode: Use saved list
             // User Request: "Detected in Prompt" should be directly visible in Refs even in Manual Mode
             // Logic: Merge saved refs with auto-detected matches, unless they are explicitly deleted.
             const savedRefs = [...tech[storageKey]];
             const deletedRefs = tech.deleted_ref_urls || [];
             
             // Identify auto matches that are NOT in saved list AND NOT in deleted list
             const newAutoMatches = autoMatches.filter(url => 
                !savedRefs.includes(url) && !deletedRefs.includes(url)
             );

             activeRefs = [...savedRefs, ...newAutoMatches];
        } else {
             // Auto Mode: Visualize what will be used by default (since nothing saved yet)
             activeRefs = [...autoMatches];

            // --- GLOBAL INJECTION RULES (Apply only in Auto Mode to allow manual overrides) ---
            
            // 1. Inject Additional Auto Refs (e.g. Previous Shot End Frame for Start Refs)
            if (additionalAutoRefs && additionalAutoRefs.length > 0) {
                // Iterate in reverse to keep order when unshifting
                for (let i = additionalAutoRefs.length - 1; i >= 0; i--) {
                    const ref = additionalAutoRefs[i];
                    if (!activeRefs.includes(ref)) {
                        activeRefs.unshift(ref);
                    }
                }
            }
        }
        
        // 2. Special Logic for End Refs: Always include Start Frame (Global Injection to ensure Realtime Updates)
        if (!isLockedManual && storageKey === 'end_ref_image_urls' && shot.image_url) {
            // Check if explicitly deleted
            const deleted = tech.deleted_ref_urls || [];
            const isExplicitlyDeleted = deleted.includes(shot.image_url);

            if (!activeRefs.includes(shot.image_url) && !isExplicitlyDeleted) {
                activeRefs.unshift(shot.image_url); // Prepend Start Frame for context
            }
        }
        
        // 3. Special Logic for Video Refs: Only visual assets
        if (storageKey === 'video_ref_image_urls') {
             // For video, we largely ignore user manual list if it contradicts the generated assets flow?
             // Actually, if user customized it, we should respect it?
             // But the code previously cleared it in Auto mode.
             // Let's keep logic simple: If Video Mode, we assume strict structural refs.
             // But if user manually added strict refs, we keep them?
             // Reverting to previous strict logic for video mode seems safer to avoid "entity pollution".
                 if (!tech[storageKey] && !isLockedManual) {
                activeRefs = [];
                if (shot.image_url) activeRefs.push(shot.image_url);
                if (tech.keyframes && Array.isArray(tech.keyframes)) activeRefs.push(...tech.keyframes);
                if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
                 } else if (!isLockedManual && isManualMode && shot.image_url && !activeRefs.includes(shot.image_url)) {
                // Ensure Start Frame is visible even in Manual Mode if user didn't explicitly remove it? 
                // Wait - logic above says inject into Auto Only. 
                // If Manual Mode, we trust the list.
                // However user says: "Refs (End)引用首帧时不能实时更新，但Refs (Video)可以"
                // This means when shot.image_url changes, it doesn't show up in Refs(End) if it was already in Manual Mode or Auto Mode didn't catch it?
                
                // If in Auto Mode, the `shot.image_url` is added via Rule #2.
                // If in Manual Mode, `activeRefs` comes from `tech[storageKey]`.
                // If `shot.image_url` changes, `tech[storageKey]` is STALE.
                
                // We must Inject/Update Start Frame in Manual Mode too if it's missing or different?
                // But we don't know if user DELETED it.
                // Compromise: If Start Frame exists, we PREPEND it visually if likely candidates match, 
                // OR we just rely on the fact that if it's "Start Frame", it should always be there for End Gen context.
             }
        }
        
        // FIX FOR REFS (END) NOT UPDATING:
        // Refs (Video) works because we likely force it or it's using a different path.
        // Actually, looking at "Refs (Video)" logic above (lines 1190+), if no manual list, it rebuilds completely including `shot.image_url`.
        // "Refs (End)" logic (line 1175): Only injects `shot.image_url` IF `!activeRefs.includes`.
        
        // Critical Issue: `activeRefs` in Auto Mode comes from `getEntityMatches()` (entity images). 
        // Then we unshift `shot.image_url`.
        // If `shot.image_url` changes, the component re-renders. 
        // `activeRefs` is rebuilt. `shot.image_url` is new. It gets pushed.
        
        // HOWEVER, if Manual Mode (`end_ref_image_urls` exists):
        // `activeRefs` = loaded from DB.
        // If DB has OLD start frame url, and `shot.image_url` is NEW, 
        // `!activeRefs.includes(shot.image_url)` is TRUE.
        // So we unshift the NEW url. 
        // But the OLD url is still there? 
        // Yes, duplicate if old one is just a string.
        
        // User complaint: "Can't realtime update". 
        // Maybe because `ReferenceManager` is memozied or `shot` prop isn't triggering deep update?
        // No, `shot` is passed new object.
        
        // Let's force ensure Start Frame is present for End Refs, similar to Video Refs logic?
        // Actually, the issue might be that we only apply Rule #2 in the `else` (Auto Mode) block from my previous edit.
        // I moved the injection rules INSIDE the `else` block to fix the "Delete" issue.
        // But this broke the "Realtime Update" for manual mode? 
        // If I generate a new Start Frame, I enter Manual Mode? No, generating keeps it in whatever mode.
        // But if I ever saved the list (e.g. by deleting something), I am in Manual Mode.
        // And in Manual Mode, I explicitly REMOVED the injection logic to support deletion.
        
        // Logic Conflict:
        // 1. User wants to DELETE items (requires Manual Mode where we don't Force-Inject).
        // 2. User wants REALTIME UPDATE of Start Frame (requires Force-Injection whenever it changes).
        
        // Resolution:
        // We should identify the "Start Frame" in the list and REPLACE it if it changes, rather than blindly injecting.
        // OR: We only auto-inject into Manual Mode IF the list doesn't contain the *current* start frame.
        // BUT if user deleted it, we re-inject it? That creates the Zombie bug again.
        
        // Correct Approach for "Refs (End)" (Contextual Refs):
        // The Start Frame is a *Dependency*, not just a suggestion.
        // For End Frame generation, you almost ALWAYS want the Start Frame.
        // If the Start Frame updates, the Ref list *should* update to reflect the new reality.
        
        // What if we separate "Hard Dependencies" (Start Frame) from "Soft References" (Style/Entities)?
        // In the UI, we could show Start Frame as a pinned item?
        
        // Current quick fix:
        // Re-enable Injection for Manual Mode but be smarter?
        // OR: Just move the Rule #2 OUT of the `else` block (make it Global again) but check for *stale* versions?
        // For End Refs, the "Start Frame" is key.
        // If I move Rule #2 back out, deleting it becomes impossible because it re-injects.
        
        // Maybe we just allow Deleting it -> adds to an "Ignore List"? Too complex.
        
        // Let's look at "Refs (Video)".
        // It has logic: `if (!tech[storageKey]) { ...rebuild... }`
        // If Manual Mode, it uses `tech[storageKey]`.
        // Does "Refs (Video)" update start frame in Manual Mode?
        // If I have manual video refs, and I update start frame, does it update?
        // If logic is same, it shouldn't.
        // User says "Refs (Video) works". 
        // Maybe because they haven't triggered Manual Mode for Video yet?
        
        // Let's Apply the "Update Logic" specifically for Start Frame replacement.
        // If we find an item in `activeRefs` that LOOKS like a start frame (maybe check previous `shot` state? We don't have it).
        
        // Alternative:
        // We assume `shot.image_url` IS the single truth for the Start Frame dependency.
        // We simply render it as a "System Pinned" reference that cannot be removed? 
        // No, user wants to remove "Start" from "Refs (Start)" previously.
        // But for "Refs (End)", Start Frame is external context.
        
        // Let's try moving Rule #2 back to Global Scope (apply to Manual too), 
        // BUT make `ReferenceManager` smart enough to not resurrect it if *explicitly removed* in this session?
        // Hard to track session.
        
        // Let's strictly follow the request: "Refs (End) ... Refs (Video) worked".
        // Let's see if I can simply enable the injection for Manual Mode ONLY IF it's "Refs (End)" or "Refs (Video)" (for start frame).
        // And accept that Deleting it might be tricky?
        // Or better: Allow Deleting, but if a *New* Start Frame is generated, it comes back?
        // That happens naturally if `shot.image_url` changes value.
        
        // Let's try:
        // Move the Injection Rule for `end_ref_image_urls` + `shot.image_url` OUTSIDE the else block.
        // To prevent "Cannot Delete" Zombie bug:
        // The user was likely complaining about "Refs (Start)" (Start Frame generation refs).
        // "Refs (End)" (End Frame generation refs) *needs* the Start Frame.
        // The previous Zombie bug report was "Refs (Start) delete button invalid". 
        // "Refs (Start)" uses `additionalAutoRefs` (Previous Shot End Frame).
        // It does NOT use `shot.image_url` as a ref (it IS the result).
        
        // So:
        // Rule 1 (Additional Auto Refs - e.g. Prev Shot): Kept inside `else` (Auto only). Fixes "Refs (Start)" delete bug.
        // Rule 2 (Start Frame for End/Video Refs): Move OUTSIDE `else` (Global). 
        // This ensures Start Frame always appears in End/Video refs, updating in real-time.
        // Does this prevent deletion of Start Frame from End Refs? Yes.
        // Is that acceptable? Usually yes, Start Frame is the anchor for End Frame.
        // If user wants to generate End Frame *without* Start Frame context... that's rare?
        // If they really want to, they might struggle. But this fixes the "Update" issue.
        
        // Let's move Rule 2 out.
        
        // 3. Special Logic for Video Refs: Only visual assets
        if (storageKey === 'video_ref_image_urls') {
             // For video, we largely ignore user manual list if it contradicts the generated assets flow?
             // Actually, if user customized it, we should respect it?
             // But the code previously cleared it in Auto mode.
             // Let's keep logic simple: If Video Mode, we assume strict structural refs.
             // But if user manually added strict refs, we keep them?
             // Reverting to previous strict logic for video mode seems safer to avoid "entity pollution".
                 if (!tech[storageKey] && !isLockedManual) {
                activeRefs = [];
                if (shot.image_url) activeRefs.push(shot.image_url);
                if (tech.keyframes && Array.isArray(tech.keyframes)) activeRefs.push(...tech.keyframes);
                if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
             }
        }
        
        // Deduplicate
        activeRefs = [...new Set(activeRefs)];
    }
    
    // Filter matches that are NOT already active to display as suggestions (Standard Mode Only)
    // USER REQUEST: Show detected entities as suggestions even if in Manual Mode, so user can add them.
    // UPDATE: Detected entities are now auto-merged into activeRefs (unless deleted), so availableMatches logic is minimized.
    // Note: Video Refs totally skip entity matching.
    const entityMatches = (useSequenceLogic || storageKey === 'video_ref_image_urls') ? [] : getEntityMatches();
    const availableMatches = entityMatches.filter(e => {
        // Technically these are items that matched but are NOT in activeRefs.
        // This only happens if they have no image OR were explicitly deleted.
        return !!e.image_url && !activeRefs.includes(e.image_url);
    });

    const handleAdd = (url) => {
        if (!url || activeRefs.includes(url)) return;
        const newRefList = [...activeRefs, url];
        // If sequential, do we save back to ref_image_urls? 
        // User request implies the LOGIC for getting pics is fixed. 
        // So for "Refs (Video)", maybe we don't save to 'ref_image_urls' necessarily, 
        // OR we overwrite 'ref_image_urls' with this sequence so backend uses it?
        // Let's assume we update the standard field so backend picks it up easily.
        const userEditedKey = `${storageKey}_user_edited`;
        const newTech = { ...tech, [storageKey]: newRefList, [userEditedKey]: true };
        onUpdate({ technical_notes: JSON.stringify(newTech) });
    };

    const handleRemove = (url) => {
        if (useSequenceLogic) return; // Cannot remove derived items in this view
        
        // Track deletions to prevent zombie resurrection by auto-injection
        let deleted = tech.deleted_ref_urls || [];
        if (!deleted.includes(url)) {
            deleted = [...deleted, url];
        }

        const newRefs = activeRefs.filter(u => u !== url);
        const userEditedKey = `${storageKey}_user_edited`;
        const newTech = { ...tech, [storageKey]: newRefs, deleted_ref_urls: deleted, [userEditedKey]: true };
        onUpdate({ technical_notes: JSON.stringify(newTech) });
    };

    const getEntityInfo = (url) => {
        return entities.find(e => e.image_url === url);
    };

    // Modal Content
    const renderModal = () => {
        if (!selectedImage) return null;
        
        const entity = getEntityInfo(selectedImage);
        
        return (
            <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8" onClick={() => setSelectedImage(null)}>
                 <div className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden max-w-5xl w-full max-h-[90vh] flex shadow-2xl" onClick={e => e.stopPropagation()}>
                    {/* Image Area */}
                    <div className="flex-1 bg-black/50 flex items-center justify-center p-4 relative group/modal">
                        <img src={getFullUrl(selectedImage)} className="max-w-full max-h-full object-contain shadow-lg rounded" alt="Detail" />
                        <button 
                            className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full hover:bg-white/20 transition-colors"
                            onClick={() => setSelectedImage(null)}
                        >
                            <X size={24} />
                        </button>
                    </div>

                    {/* Metadata Sidebar */}
                    <div className="w-80 bg-[#151515] border-l border-white/10 p-6 flex flex-col gap-4 overflow-y-auto">
                        <div>
                            <h3 className="text-xl font-bold text-white mb-1">{entity?.name || 'External Image'}</h3>
                            {entity?.name_en && <div className="text-sm text-muted-foreground">{entity.name_en}</div>}
                        </div>

                        <div className="space-y-4">
                            {entity ? (
                                <>
                                    <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                        <span className="text-[10px] uppercase font-bold text-primary/70 block mb-1">Description</span>
                                        <p className="text-sm text-gray-300 leading-relaxed max-h-[200px] overflow-y-auto custom-scrollbar">
                                            {entity.description || 'No description available.'}
                                        </p>
                                    </div>
                                    
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="bg-white/5 p-2 rounded border border-white/5">
                                            <span className="text-[10px] uppercase text-gray-500 block">Type</span>
                                            <span className="text-xs text-gray-300">{entity.type || 'Unknown'}</span>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="text-sm text-muted-foreground italic">
                                    This image was added via URL or is external to the entity library. Metadata is unavailable.
                                </div>
                            )}

                            {/* Actions */}
                            <div className="pt-4 mt-auto border-t border-white/10 flex flex-col gap-2">
                                {activeRefs.includes(selectedImage) ? (
                                    <button 
                                        onClick={() => { handleRemove(selectedImage); setSelectedImage(null); }}
                                        className="w-full py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded flex items-center justify-center gap-2 hover:bg-red-500/20 text-sm font-medium"
                                    >
                                        <Trash2 size={16} /> Remove Reference
                                    </button>
                                ) : (
                                     <button 
                                        onClick={() => { handleAdd(selectedImage); }} // Update status, keep modal open to show it's active now
                                        className="w-full py-2 bg-primary/10 text-primary border border-primary/30 rounded flex items-center justify-center gap-2 hover:bg-primary/20 text-sm font-medium"
                                    >
                                        <Plus size={16} /> Add to References
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                 </div>
            </div>
        )
    }

    return (
        <>
            {renderModal()}
            <div className="space-y-2 pb-4 border-b border-white/10 mb-4">
                <div className="flex items-center justify-between">
                     <h4 className="text-xs font-bold text-muted-foreground uppercase flex items-center gap-2">
                        {title}
                        {onFindPrevFrame && (
                            <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    const url = onFindPrevFrame();
                                    if (url) handleAdd(url);
                                }}
                                className="p-1 bg-white/5 hover:bg-primary/20 text-white/70 hover:text-primary rounded transition-colors"
                                title={t('获取上一镜头结束帧', 'Fetch Previous Shot End Frame')}
                            >
                                <ArrowUp className="w-3 h-3" />
                            </button>
                        )}
                    </h4>
                    <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-white/50">Used by AI: {activeRefs.length}</span>
                </div>
                
                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar min-h-[90px]">
                    {/* 1. Active Refs (Selected) */}
                    {activeRefs.map((url, idx) => (
                        <div key={url + idx} className="relative group shrink-0 w-[140px] aspect-video bg-black/40 rounded border border-primary/50 overflow-hidden shadow-[0_0_10px_rgba(0,0,0,0.5)] cursor-zoom-in" onClick={() => setSelectedImage(url)}>
                            {(url.toLowerCase().endsWith('.mp4') || url.toLowerCase().endsWith('.webm')) ? (
                                <video src={getFullUrl(url)} className="w-full h-full object-cover" muted loop onMouseEnter={e=>e.target.play()} onMouseLeave={e=>{e.target.pause();e.target.currentTime=0;}} />
                            ) : (
                                <img src={getFullUrl(url)} className="w-full h-full object-cover" alt="ref" />
                            )}
                            {!useSequenceLogic && (
                                <button 
                                    onClick={(e) => { e.stopPropagation(); handleRemove(url); }}
                                    className="absolute top-1 right-1 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 z-10"
                                >
                                    <X className="w-3 h-3"/>
                                </button>
                            )}
                        </div>
                    ))}
                    
                    {/* Add Button */}
                    {!useSequenceLogic && onPickMedia && (
                        <button 
                            onClick={() => onPickMedia((url) => handleAdd(url), { shotId: shot?.id })}
                            className="shrink-0 w-[50px] aspect-video bg-white/5 hover:bg-white/10 border border-white/10 border-dashed rounded flex flex-col items-center justify-center gap-1 text-muted-foreground hover:text-white transition-colors"
                            title={t('从素材中选择', 'Pick from Assets')}
                        >
                            <Plus className="w-5 h-5"/>
                        </button>
                    )}
                </div>
            </div>
        </>
    )
};

const SceneCard = ({ scene, entities, onClick, onGenerateShots, onDelete, selected = false, onToggleSelect, uiLang = 'zh' }) => {
    const [images, setImages] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isGenerating, setIsGenerating] = useState(false);
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);

    useEffect(() => {
        // Parse logic
        const sourceText = scene.environment_name || scene.location || '';
        let anchors = [];
        const bracketMatches = sourceText.match(/\[(.*?)\]/g);
        if (bracketMatches && bracketMatches.length > 0) {
            anchors = bracketMatches.map(m => m.replace(/[\[\]\*]/g, '').trim());
        } else {
            anchors = sourceText.split(/[,，]/).map(s => s.replace(/[\*]/g, '').trim()).filter(Boolean);
        }

        const validUrls = [];
        // Updated cleaner: Removes whitespace to handle "主视角" vs "主视角 " mismatch
        const cleanForMatch = (str) => (str || '').replace(/[（\(\)）\s]/g, '').toLowerCase();

        anchors.forEach(rawLoc => {
            const targetName = cleanForMatch(rawLoc);
            if (!targetName) return;

             // Logic extracted from getSceneImages
            let match = entities.find(e => {
                const cn = cleanForMatch(e.name);
                let en = (e.name_en || '').toLowerCase();
                if (!en && e.description) {
                    const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                    if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                }
                const enClean = cleanForMatch(en);
                return cn === targetName || enClean === targetName;
            });

            if (!match) {
                 match = entities.find(e => {
                    const cn = cleanForMatch(e.name);
                    let en = (e.name_en || '').toLowerCase();
                    if (!en && e.description) {
                        const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                        if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                    }
                    const enClean = cleanForMatch(en);
                    return (cn && (cn.includes(targetName) || targetName.includes(cn))) ||
                           (enClean && (enClean.includes(targetName) || targetName.includes(enClean)));
                 });
            }
            if (match && match.image_url) validUrls.push(match.image_url);
        });

        // Use Set to remove duplicates
        setImages([...new Set(validUrls)]);
        setCurrentIndex(0);
    }, [scene, entities]);

    useEffect(() => {
        if (images.length <= 1) return;
        const interval = setInterval(() => {
            setCurrentIndex(prev => (prev + 1) % images.length);
        }, 3000);
        return () => clearInterval(interval);
    }, [images]);

    const handleGenerate = async (e) => {
        e.stopPropagation();
        if (isGenerating) return;
        
        setIsGenerating(true);
        if (onGenerateShots) {
            await onGenerateShots(scene.id);
        }
        setIsGenerating(false);
    };

    const handleDelete = async (e) => {
        e.stopPropagation();
        if (!onDelete || !scene?.id) return;
        await onDelete(scene);
    };

    const handleToggleSelect = (e) => {
        e.stopPropagation();
        if (typeof onToggleSelect === 'function') onToggleSelect(scene);
    };

    const imgUrl = images.length > 0 ? images[currentIndex] : null;

    return (
        <div 
            className="bg-card/80 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden group hover:border-primary/50 transition-all cursor-pointer relative"
            onClick={onClick}
        >
            <div className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden">
                {imgUrl ? (
                    <motion.img 
                        key={imgUrl}
                        src={getFullUrl(imgUrl)} 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5 }}
                        className="w-full h-full object-cover absolute inset-0" 
                        alt={scene.scene_name}
                    />
                ) : (
                    <div className="flex flex-col items-center gap-2 opacity-50">
                        <ImageIcon className="w-8 h-8" />
                        <span className="text-xs">{t('无环境图', 'No Env Image')}</span>
                    </div>
                )}
                
                {/* Dots indicator for multiple images */}
                {images.length > 1 && (
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1 z-10">
                        {images.map((_, idx) => (
                            <div key={idx} className={`w-1.5 h-1.5 rounded-full ${idx === currentIndex ? 'bg-primary' : 'bg-white/50'}`} />
                        ))}
                    </div>
                )}

                <label
                    className="absolute top-2 left-2 z-30 flex items-center justify-center w-6 h-6 rounded bg-black/60 border border-white/20 cursor-pointer"
                    title={t('选择场景', 'Select scene')}
                >
                    <input
                        type="checkbox"
                        checked={!!selected}
                        onChange={handleToggleSelect}
                        className="accent-primary"
                    />
                </label>

                <div className="absolute top-2 left-10 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 z-10 max-w-[70%] truncate">
                    {scene.scene_no || scene.id}
                </div>
                <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="flex items-center gap-1">
                        <button
                            onClick={handleDelete}
                            className="bg-red-500/90 hover:bg-red-500 text-white px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg"
                            title={t('删除场景', 'Delete Scene')}
                        >
                            <Trash2 className="w-3 h-3"/>
                            {t('删除', 'Delete')}
                        </button>
                        <button 
                            onClick={handleGenerate}
                            disabled={isGenerating}
                            className="bg-primary/90 hover:bg-primary text-black px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg"
                            title={t('AI 生成镜头列表', 'AI Generate Shot List')}
                        >
                            {isGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                            {t('AI 镜头', 'AI Shots')}
                        </button>
                    </div>
                </div>
                <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold z-10">
                    {scene.equivalent_duration || '0m'}
                </div>
            </div>
            
            <div className="p-4 space-y-2.5">
                <h3 className="font-bold text-sm text-white line-clamp-1" title={scene.scene_name}>{scene.scene_name || t('未命名场景', 'Untitled Scene')}</h3>
                
                <div className="text-xs text-muted-foreground space-y-2">
                    {/* Core Info - handled to prevent layout chaos with Markdown */}
                    <div className="bg-white/5 p-2 rounded border border-white/5 relative group/info">
                        <span className="font-bold text-white/50 block text-[10px] uppercase mb-1">Core Info</span>
                        <div className="max-h-[4.5em] overflow-hidden text-white/80 leading-normal prose prose-invert prose-p:my-0 prose-p:leading-normal prose-headings:my-0 prose-ul:my-0 prose-li:my-0 text-[11px]">
                             <ReactMarkdown components={{
                                 p: ({node, ...props}) => <p className="mb-1" {...props} />
                             }}>{scene.core_scene_info || 'No core info'}</ReactMarkdown>
                        </div>
                         {/* Hover expand could be cool, but simplistic for now */}
                    </div>

                    {/* Linked Characters & Key Props */}
                    <div className="space-y-1.5">
                        {(scene.linked_characters || scene.key_props) ? (
                            <>
                            {scene.linked_characters && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="font-bold text-white/40 text-[9px] uppercase">Cast</span>
                                    <div className="flex flex-wrap gap-1">
                                        {scene.linked_characters.split(/[，,]/).filter(Boolean).map((char, i) => (
                                            <span key={i} className="inline-block bg-indigo-500/20 text-indigo-200 border border-indigo-500/30 px-1.5 py-0.5 rounded text-[10px]">
                                                {char.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {scene.key_props && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="font-bold text-white/40 text-[9px] uppercase">Props</span>
                                    <div className="flex flex-wrap gap-1">
                                        {scene.key_props.split(/[，,]/).filter(Boolean).map((prop, i) => (
                                            <span key={i} className="inline-block bg-emerald-500/20 text-emerald-200 border border-emerald-500/30 px-1.5 py-0.5 rounded text-[10px]">
                                                {prop.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            </>
                        ) : (
                             <div className="line-clamp-2 opacity-50 italic">
                                {scene.original_script_text || 'No description'}
                            </div>
                        )}
                    </div>
                </div>
                
                <div className="pt-2 border-t border-white/5 text-[10px] text-gray-400 mt-auto flex justify-between items-center">
                    <div className="flex items-center gap-1 max-w-[70%] truncate">
                        <span className="opacity-50">Env:</span>
                        <span className="text-white/70" title={scene.environment_name}>{scene.environment_name || '-'}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

const SceneManager = ({ activeEpisode, projectId, project, onLog, onSwitchToShots, uiLang = 'zh' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [scenes, setScenes] = useState([]);
    const [selectedSceneKeys, setSelectedSceneKeys] = useState([]);
    const [entities, setEntities] = useState([]);
    const [isSuperuser, setIsSuperuser] = useState(false);
    const [sceneHierarchyFilter, setSceneHierarchyFilter] = useState('');
    const [sceneKeywordFilter, setSceneKeywordFilter] = useState('');
    const [editingScene, setEditingScene] = useState(null);
    const [shotPromptModal, setShotPromptModal] = useState({ open: false, sceneId: null, data: null, loading: false });
    const [aiShotsFlowStatus, setAiShotsFlowStatus] = useState({ phase: 'idle', message: '', sceneId: null });
    const [batchAiShotsProgress, setBatchAiShotsProgress] = useState({
        running: false,
        total: 0,
        completed: 0,
        success: 0,
        failed: 0,
        currentSceneLabel: '',
        message: '',
        errors: [],
    });
    const [aiShotsStaging, setAiShotsStaging] = useState({
        loading: false,
        sceneId: null,
        content: [],
        rawText: '',
        usage: null,
        timestamp: null,
        error: null,
        saving: false,
        applying: false,
    });
    const [aiShotRowEditor, setAiShotRowEditor] = useState({
        open: false,
        index: -1,
        data: null,
    });

    const sceneFilterStorageKey = useMemo(() => {
        if (!activeEpisode?.id) return '';
        return `aistory.sceneFilters.${activeEpisode.id}`;
    }, [activeEpisode?.id]);

    useEffect(() => {
        if (!sceneFilterStorageKey) return;
        try {
            const raw = localStorage.getItem(sceneFilterStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                setSceneHierarchyFilter(String(parsed.sceneHierarchyFilter || ''));
                setSceneKeywordFilter(String(parsed.sceneKeywordFilter || ''));
            }
        } catch (e) {
            console.warn('Failed to restore scene filters', e);
        }
    }, [sceneFilterStorageKey]);

    useEffect(() => {
        if (!sceneFilterStorageKey) return;
        try {
            localStorage.setItem(sceneFilterStorageKey, JSON.stringify({
                sceneHierarchyFilter,
                sceneKeywordFilter,
            }));
        } catch (e) {
            console.warn('Failed to persist scene filters', e);
        }
    }, [sceneFilterStorageKey, sceneHierarchyFilter, sceneKeywordFilter]);

    const getSceneSelectionKey = (scene) => {
        if (scene?.id) return `id:${scene.id}`;
        return `draft:${scene?.scene_no || ''}|${scene?.scene_name || ''}|${scene?.environment_name || ''}|${scene?.original_script_text || ''}`;
    };

    const filteredScenes = useMemo(() => {
        const hierarchy = String(sceneHierarchyFilter || '').trim().toLowerCase();
        const keyword = String(sceneKeywordFilter || '').trim().toLowerCase();
        const episodeKeywordLabel = buildEpisodeDisplayLabel({
            episodeNumber: activeEpisode?.episode_number,
            title: activeEpisode?.title,
        }).toLowerCase();

        return (scenes || []).filter((scene) => {
            const sceneCode = String(scene?.scene_id || scene?.scene_no || '').trim().toLowerCase();
            const hierarchyPass = !hierarchy || sceneCode.includes(hierarchy);
            if (!hierarchyPass) return false;

            if (!keyword) return true;
            const text = [
                scene?.scene_name,
                scene?.environment_name,
                scene?.linked_characters,
                scene?.key_props,
                scene?.core_scene_info,
                activeEpisode?.title,
                episodeKeywordLabel,
            ].map(v => String(v || '').toLowerCase()).join(' ');
            return text.includes(keyword);
        });
    }, [scenes, sceneHierarchyFilter, sceneKeywordFilter, activeEpisode?.title, activeEpisode?.episode_number]);

    useEffect(() => {
        const validKeys = new Set((scenes || []).map(getSceneSelectionKey));
        setSelectedSceneKeys((prev) => prev.filter((key) => validKeys.has(key)));
    }, [scenes]);

    const selectedSceneKeySet = useMemo(() => new Set(selectedSceneKeys), [selectedSceneKeys]);
    const filteredSceneKeys = useMemo(() => (filteredScenes || []).map(getSceneSelectionKey), [filteredScenes]);
    const selectedFilteredCount = useMemo(
        () => filteredSceneKeys.filter((key) => selectedSceneKeySet.has(key)).length,
        [filteredSceneKeys, selectedSceneKeySet]
    );
    const allFilteredSelected = filteredSceneKeys.length > 0 && selectedFilteredCount === filteredSceneKeys.length;

    const toggleSceneSelected = (scene) => {
        const key = getSceneSelectionKey(scene);
        setSelectedSceneKeys((prev) => (
            prev.includes(key)
                ? prev.filter((k) => k !== key)
                : [...prev, key]
        ));
    };

    const toggleSelectAllFiltered = () => {
        if (!filteredSceneKeys.length) return;
        setSelectedSceneKeys((prev) => {
            const prevSet = new Set(prev);
            if (allFilteredSelected) {
                return prev.filter((key) => !filteredSceneKeys.includes(key));
            }
            filteredSceneKeys.forEach((key) => prevSet.add(key));
            return Array.from(prevSet);
        });
    };

    const getStagingShotField = (shot, field) => {
        if (!shot) return '';
        const map = {
            shot_id: ['Shot ID', 'shot_id'],
            shot_name: ['Shot Name', 'shot_name'],
            scene_id: ['Scene ID', 'scene_id'],
            start_frame: ['Start Frame', 'start_frame'],
            video_content: ['Video Content', 'video_content'],
            duration: ['Duration (s)', 'duration'],
            end_frame: ['End Frame', 'end_frame'],
            associated_entities: ['Associated Entities', 'associated_entities'],
            shot_logic_cn: ['Shot Logic (CN)', 'shot_logic_cn'],
            keyframes: ['Keyframes', 'keyframes'],
        };
        const keys = map[field] || [];
        for (const key of keys) {
            const value = shot[key];
            if (value !== undefined && value !== null) return String(value);
        }
        return '';
    };

    const openAiShotRowEditor = (shot, idx) => {
        setAiShotRowEditor({
            open: true,
            index: idx,
            data: {
                shot_id: getStagingShotField(shot, 'shot_id'),
                shot_name: getStagingShotField(shot, 'shot_name'),
                scene_id: getStagingShotField(shot, 'scene_id'),
                start_frame: getStagingShotField(shot, 'start_frame'),
                video_content: getStagingShotField(shot, 'video_content'),
                duration: getStagingShotField(shot, 'duration'),
                end_frame: getStagingShotField(shot, 'end_frame'),
                associated_entities: getStagingShotField(shot, 'associated_entities'),
                shot_logic_cn: getStagingShotField(shot, 'shot_logic_cn'),
                keyframes: getStagingShotField(shot, 'keyframes'),
            },
        });
    };

    const saveAiShotRowEditor = () => {
        if (!aiShotRowEditor.open || aiShotRowEditor.index < 0) return;
        const currentRows = [...(aiShotsStaging.content || [])];
        const current = currentRows[aiShotRowEditor.index] || {};
        const edited = aiShotRowEditor.data || {};

        currentRows[aiShotRowEditor.index] = {
            ...current,
            'Shot ID': edited.shot_id || '',
            'Shot Name': edited.shot_name || '',
            'Scene ID': edited.scene_id || '',
            'Start Frame': edited.start_frame || '',
            'Video Content': edited.video_content || '',
            'Duration (s)': edited.duration || '',
            'End Frame': edited.end_frame || '',
            'Associated Entities': edited.associated_entities || '',
            'Shot Logic (CN)': edited.shot_logic_cn || '',
            'Keyframes': edited.keyframes || '',
        };

        setAiShotsStaging(prev => ({ ...prev, content: currentRows }));
        setAiShotRowEditor({ open: false, index: -1, data: null });
    };

    useEffect(() => {
        fetchMe().then((user) => {
            setIsSuperuser(!!user?.is_superuser);
        }).catch(() => {
            setIsSuperuser(false);
        });
    }, []);

    // Fetch Entities (Environment) for image matching
    useEffect(() => {
        // Shared Parsing Logic
        const parseScenesFromText = (text) => {
             if (!text) return [];
             const lines = text.split('\n').filter(l => l.trim().includes('|'));
             const headerIdx = lines.findIndex(l => 
                (l.includes("Scene No") || l.includes("场次序号") || l.includes("Scene ID") || l.includes("场次") || l.includes("Title"))
             );
             
             if (headerIdx === -1) return [];
             
             // Parse Headers
             const headerLine = lines[headerIdx];
             let headers = headerLine.split('|').map(c => c.trim());
             if (headers.length > 0 && headers[0] === "") headers.shift();
             if (headers.length > 0 && headers[headers.length-1] === "") headers.pop();
             
             const normalizeHeader = (h) => h.toLowerCase().replace(/[\.\s]/g, '');
             const headerMap = {};
             headers.forEach((h, idx) => {
                 const n = normalizeHeader(h);
                 if (n.includes("episodeid") || n.includes("集id")) headerMap['episode_id'] = idx;
                 else if ((n.includes("sceneid") && !n.includes("sceneno")) || n.includes("场景id")) headerMap['scene_id'] = idx;
                 if(n.includes("sceneno") || n.includes("场次")) headerMap['scene_no'] = idx;
                 else if(n.includes("scenename") || n.includes("title")) headerMap['scene_name'] = idx;
                 else if(n.includes("equivalentduration")) headerMap['equivalent_duration'] = idx;
                 else if(n.includes("coresceneinfo") || n.includes("coregoal")) headerMap['core_scene_info'] = idx;
                 else if(n.includes("originalscripttext") || n.includes("description")) headerMap['original_script_text'] = idx;
                 else if(n.includes("environmentname") || n.includes("environment")) headerMap['environment_name'] = idx;
                 else if(n.includes("environmentrelation")) headerMap['environment_relation'] = idx;
                 else if(n.includes("entrystate")) headerMap['entry_state'] = idx;
                 else if(n.includes("exitstate")) headerMap['exit_state'] = idx;
                 else if(n.includes("linkedcharacters")) headerMap['linked_characters'] = idx;
                 else if(n.includes("keyprops")) headerMap['key_props'] = idx;
             });

             const rows = [];
             let inShotTable = false;

             for (let i = headerIdx + 1; i < lines.length; i++) {
                const line = lines[i];
                if (line.includes("Shot ID") || line.includes("镜头ID")) {
                    inShotTable = true;
                    continue;
                }
                if (line.includes("Scene No") || line.includes("场次序号")) {
                    inShotTable = false;
                    continue;
                }
                if (inShotTable) continue;
                if (line.includes('---')) continue;
                
                let cols = line.split('|').map(c => c.trim());
                if (cols.length > 0 && cols[0] === "") cols.shift();
                if (cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                
                if (cols.length >= 2) {
                    const cleanCol = (txt) => txt ? txt.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
                    
                    // Helper to get by mapped index, defaulting to hardcoded fallback if map fails (legacy support)
                    const getVal = (key, fallbackIdx) => {
                        const idx = headerMap[key] !== undefined ? headerMap[key] : fallbackIdx;
                        return cols[idx] ? cleanCol(cols[idx]) : '';
                    };

                    const isNewFormat = cols.length >= 13 || headerMap['episode_id'] !== undefined || headerMap['scene_id'] !== undefined;
                    const fallback = isNewFormat
                        ? {
                            scene_no: 2,
                            scene_name: 3,
                            equivalent_duration: 4,
                            core_scene_info: 5,
                            original_script_text: 6,
                            environment_name: 7,
                            linked_characters: 11,
                            key_props: 12,
                        }
                        : {
                            scene_no: 0,
                            scene_name: 1,
                            equivalent_duration: 2,
                            core_scene_info: 3,
                            original_script_text: 4,
                            environment_name: 5,
                            linked_characters: 6,
                            key_props: 7,
                        };

                    rows.push({
                        scene_no: getVal('scene_no', fallback.scene_no),
                        scene_name: getVal('scene_name', fallback.scene_name),
                        equivalent_duration: getVal('equivalent_duration', fallback.equivalent_duration),
                        core_scene_info: getVal('core_scene_info', fallback.core_scene_info),
                        original_script_text: getVal('original_script_text', fallback.original_script_text),
                        environment_name: getVal('environment_name', fallback.environment_name),
                        linked_characters: getVal('linked_characters', fallback.linked_characters),
                        key_props: getVal('key_props', fallback.key_props)
                    });
                }
             }
             return rows;
        };

        const loadScenes = async () => {
             if (activeEpisode?.id) {
                 try {
                     const dbScenes = await fetchScenes(activeEpisode.id);
                     if (dbScenes && dbScenes.length > 0) {
                         // Check for incomplete data (Schema Update Backfill)
                         const inContent = activeEpisode.scene_content;
                         if (inContent && dbScenes.some(s => !s.linked_characters && !s.key_props)) {
                             const parsed = parseScenesFromText(inContent);
                             if (parsed.length > 0) {
                                 const merged = dbScenes.map(dbS => {
                                     // Match by Scene Number
                                     const match = parsed.find(p => p.scene_no === dbS.scene_no);
                                     if (match) {
                                         return {
                                             ...dbS,
                                             linked_characters: dbS.linked_characters || match.linked_characters,
                                             key_props: dbS.key_props || match.key_props,
                                             environment_name: dbS.environment_name || match.environment_name,
                                             core_scene_info: dbS.core_scene_info || match.core_scene_info
                                         };
                                     }
                                     return dbS;
                                 });
                                 setScenes(merged);
                                 return;
                             }
                         }
                         setScenes(dbScenes);
                     } else {
                         // Only parse if DB is empty
                         setScenes(parseScenesFromText(activeEpisode?.scene_content));
                     }
                 } catch(e) {
                     console.error("Failed to load scenes from DB", e);
                     const parsedFallback = parseScenesFromText(activeEpisode?.scene_content);
                     setScenes(parsedFallback);
                 }
             }
        };

        if (projectId) fetchEntities(projectId).then(setEntities).catch(console.error);
        loadScenes();
    }, [activeEpisode, projectId]);

    const handleSceneUpdate = (updatedScene) => {
        setScenes(prev => prev.map(s => s.id === updatedScene.id ? updatedScene : s));
        if (editingScene && editingScene.id === updatedScene.id) {
            setEditingScene(updatedScene);
        }
    };

    const buildSceneContentMarkdown = (sceneRows = []) => {
        if (!activeEpisode) return '';
        const contextInfo = `Project: ${project?.title || 'Unknown'} | Episode: ${activeEpisode?.title || 'Unknown'}\n`;
        const header = `| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Original Script Text | Environment Name | Environment Relation | Entry State | Exit State | Linked Characters | Key Props |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|`;
        const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
        const content = (sceneRows || []).map((s) => (
            `| ${clean(activeEpisode?.id)} | ${clean(s.id)} | ${clean(s.scene_no)} | ${clean(s.scene_name)} | ${clean(s.equivalent_duration)} | ${clean(s.core_scene_info)} | ${clean(s.original_script_text)} | ${clean(s.environment_name)} | ${clean(s.environment_relation || '')} | ${clean(s.entry_state || '')} | ${clean(s.exit_state || '')} | ${clean(s.linked_characters)} | ${clean(s.key_props)} |`
        )).join('\n');
        return `${contextInfo}${header}\n${content}`;
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        
        onLog?.('SceneManager: Saving content...', 'info');
        
        try {
            // Update scenes in DB (Create if missing ID, Update if exists)
            const savePromises = scenes.map(async (s) => {
                const payload = {
                    scene_no: s.scene_no,
                    scene_name: s.scene_name,
                    equivalent_duration: s.equivalent_duration,
                    core_scene_info: s.core_scene_info,
                    original_script_text: s.original_script_text,
                    environment_name: s.environment_name,
                    linked_characters: s.linked_characters,
                    key_props: s.key_props
                };

                if (s.id) {
                    await updateScene(s.id, payload);
                    return s;
                } else {
                    const created = await createScene(activeEpisode.id, payload);
                    return { ...s, id: created.id };
                }
            });

            const savedScenes = await Promise.all(savePromises);
            setScenes(savedScenes);

            await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(savedScenes) });
            onLog?.('SceneManager: Saved successfully.', 'success');
        } catch(e) {
            console.error(e);
            onLog?.(`SceneManager: Save failed - ${e.message}`, 'error');
            alert(`Failed to save scenes: ${e?.message || 'Unknown error'}`);
        }
    };

    const getSceneImage = (scene) => {
        // Use environment_name as requested, cleaning markdown ** and []
        const sourceText = scene.environment_name || scene.location || '';
        const rawLoc = sourceText.replace(/[\[\]\*]/g, '').trim().toLowerCase();
        
        if (!rawLoc) return null;
        
        const cleanForMatch = (str) => (str || '').replace(/[（\(\)）]/g, '').trim().toLowerCase();
        const targetName = cleanForMatch(rawLoc);

        // Try exact match first
        let match = entities.find(e => {
            const cn = cleanForMatch(e.name);
            let en = (e.name_en || '').toLowerCase();
            
            // Fallback EN extract
            if (!en && e.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
            }
            const enClean = cleanForMatch(en);

            const isMatch = cn === targetName || enClean === targetName;
            
            return isMatch;
        });

        // Try fuzzy match if exact fails
        if (!match) {
             match = entities.find(e => {
                const cn = cleanForMatch(e.name);
                let en = (e.name_en || '').toLowerCase();
                // Fallback EN extract
                if (!en && e.description) {
                    const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                    if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                }
                const enClean = cleanForMatch(en);

                if (cn && (cn.includes(targetName) || targetName.includes(cn))) {
                    return true;
                }
                if (enClean && (enClean.includes(targetName) || targetName.includes(enClean))) {
                    return true;
                }
                return false;
             });
        }

        return match ? match.image_url : null;
    };

    const executeGenerateShots = async ({ sceneId, promptData }) => {
        setAiShotsFlowStatus({
            phase: 'generating',
            sceneId,
            message: t('AI Shots 生成中...', 'AI Shots generating...'),
        });
        onLog?.(`SceneManager: Generating shots for Scene ${sceneId}...`, 'info');

        try {
            const result = await generateSceneShots(sceneId, {
                user_prompt: promptData?.user_prompt,
                system_prompt: promptData?.system_prompt,
            });

            const generatedRows = Array.isArray(result?.content) ? result.content : [];
            const generatedRaw = String(result?.raw_text || '').trim();
            if (generatedRows.length === 0) {
                if (generatedRaw) {
                    const rawPreview = generatedRaw.replace(/\s+/g, ' ').slice(0, 300);
                    onLog?.(`SceneManager: Generate Shots returned 0 parsed rows. Raw preview: ${rawPreview}`, 'warning');
                    console.warn('[SceneManager] Generate Shots parse-empty with raw_text preview', {
                        sceneId,
                        rawLen: generatedRaw.length,
                        rawPreview,
                    });
                    throw new Error(`Generate Shots returned 0 parsed rows; raw preview: ${rawPreview}`);
                }
                throw new Error('Generate Shots returned empty result (no rows and no raw text)');
            }

            onLog?.(`SceneManager: Shot list generated for Scene ${sceneId}.`, 'success');
            setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });

            const sceneObj = scenes.find(s => s.id === sceneId) || { id: sceneId, scene_no: sceneId };
            setEditingScene(sceneObj);
            setAiShotsStaging(prev => ({
                ...prev,
                sceneId,
                content: generatedRows,
                rawText: result?.raw_text || '',
                usage: result?.usage || null,
                timestamp: result?.timestamp || null,
                loading: false,
                error: null,
            }));

            setAiShotsFlowStatus({
                phase: 'importing',
                sceneId,
                message: t('生成完成，正在自动导入 Shots...', 'Generated. Auto-importing into Shots...'),
            });
            onLog?.(`SceneManager: Auto-importing shots for Scene ${sceneId}...`, 'info');

            await applySceneAIResult(sceneId, { content: generatedRows });

            onLog?.(`SceneManager: Auto-import finished for Scene ${sceneId}.`, 'success');
            if (typeof onSwitchToShots === 'function') {
                onSwitchToShots();
            }
            setAiShotsFlowStatus({
                phase: 'completed',
                sceneId,
                message: t('AI Shots 已导入，已切换到 Shots 页面。', 'AI Shots imported. Switched to Shots page.'),
            });
        } catch (e) {
            console.error(e);
            onLog?.(`SceneManager: Failed to generate/apply shots - ${e.message}`, 'error');
            setAiShotsFlowStatus({
                phase: 'failed',
                sceneId,
                message: t(`AI Shots 失败：${e.message}`, `AI Shots failed: ${e.message}`),
            });
            alert("Failed to generate shots: " + e.message);
            setShotPromptModal(prev => ({ ...prev, loading: false }));
        }
    };

    const handleGenerateShots = async (sceneId) => {
        if (!sceneId) {
            alert("Please save the scene list first to create database records before generating shots.");
            return;
        }

        if (isSuperuser) {
            setShotPromptModal({ open: true, sceneId: sceneId, data: null, loading: true });
            try {
                const data = await fetchSceneShotsPrompt(sceneId);
                setShotPromptModal({ open: true, sceneId: sceneId, data: data, loading: false });
            } catch (e) {
                onLog?.(`SceneManager: Failed to fetch prompt preview - ${e.message}`, 'error');
                setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
            }
            return;
        }

        try {
            setAiShotsFlowStatus({
                phase: 'preparing',
                sceneId,
                message: t('正在准备 AI Shots 请求...', 'Preparing AI Shots request...'),
            });
            const data = await fetchSceneShotsPrompt(sceneId);
            await executeGenerateShots({ sceneId, promptData: data });
        } catch (e) {
            onLog?.(`SceneManager: Failed to prepare AI shots - ${e.message}`, 'error');
            setAiShotsFlowStatus({
                phase: 'failed',
                sceneId,
                message: t(`AI Shots 失败：${e.message}`, `AI Shots failed: ${e.message}`),
            });
            alert(`Failed to prepare AI shots: ${e.message}`);
        }
    };

    const handleDeleteScene = async (scene) => {
        if (!scene?.id) {
            const remaining = scenes.filter(s => s !== scene);
            setScenes(remaining);
            if (activeEpisode?.id) {
                try {
                    await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(remaining) });
                } catch (e) {
                    console.warn('Failed to sync scene_content after local scene removal', e);
                }
            }
            return;
        }
        const label = scene.scene_no || scene.scene_name || `#${scene.id}`;
        if (!await confirmUiMessage(`Delete scene ${label}?`)) return;

        try {
            await deleteScene(scene.id);
            const remaining = scenes.filter(s => s.id !== scene.id);
            setScenes(remaining);
            if (editingScene?.id === scene.id) {
                setEditingScene(null);
            }
            if (activeEpisode?.id) {
                await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(remaining) });
            }
            onLog?.(`Scene deleted: ${label}`, 'success');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'Failed to delete scene';
            onLog?.(`Scene delete failed: ${detail}`, 'error');
            alert(`Failed to delete scene: ${detail}`);
        }
    };

    const runBatchGenerateAiShotsForAllScenes = async () => {
        const allScenes = Array.isArray(scenes) ? scenes : [];
        const targets = allScenes.filter((scene) => !!scene?.id);
        const skipped = allScenes.length - targets.length;

        if (targets.length === 0) {
            alert(t('没有可执行 AI Shots 的已保存场景。', 'No saved scenes available for AI Shots batch run.'));
            return;
        }

        const confirmText = t(
            `确认后台批量执行 AI Shots？将处理 ${targets.length} 个场景${skipped > 0 ? `（跳过 ${skipped} 个未保存场景）` : ''}。`,
            `Run AI Shots in background for ${targets.length} scenes${skipped > 0 ? ` (skip ${skipped} unsaved scenes)` : ''}?`
        );
        if (!await confirmUiMessage(confirmText)) return;

        setBatchAiShotsProgress({
            running: true,
            total: targets.length,
            completed: 0,
            success: 0,
            failed: 0,
            currentSceneLabel: '',
            message: t('批量任务已启动...', 'Batch task started...'),
            errors: [],
        });

        onLog?.(`SceneManager: Batch AI Shots started. total=${targets.length}, skipped_unsaved=${skipped}`, 'info');

        let completed = 0;
        let success = 0;
        let failed = 0;
        const errors = [];

        for (const scene of targets) {
            const label = scene?.scene_no || scene?.scene_name || `#${scene?.id}`;
            setBatchAiShotsProgress((prev) => ({
                ...prev,
                currentSceneLabel: label,
                message: t(`正在处理：${label}`, `Processing: ${label}`),
            }));

            try {
                const promptData = await fetchSceneShotsPrompt(scene.id);
                const result = await generateSceneShots(scene.id, {
                    user_prompt: promptData?.user_prompt,
                    system_prompt: promptData?.system_prompt,
                });

                const generatedRows = Array.isArray(result?.content) ? result.content : [];
                const generatedRaw = String(result?.raw_text || '').trim();
                if (generatedRows.length === 0) {
                    if (generatedRaw) {
                        const rawPreview = generatedRaw.replace(/\s+/g, ' ').slice(0, 180);
                        throw new Error(`No parsed rows. Raw preview: ${rawPreview}`);
                    }
                    throw new Error('No parsed rows returned');
                }

                await applySceneAIResult(scene.id, { content: generatedRows });
                success += 1;
                onLog?.(`SceneManager: Batch AI Shots success for ${label}`, 'success');
            } catch (e) {
                failed += 1;
                const detail = e?.response?.data?.detail || e?.message || 'Unknown error';
                errors.push(`${label}: ${detail}`);
                onLog?.(`SceneManager: Batch AI Shots failed for ${label} - ${detail}`, 'error');
            } finally {
                completed += 1;
                setBatchAiShotsProgress((prev) => ({
                    ...prev,
                    completed,
                    success,
                    failed,
                    errors,
                    message: t(
                        `进度 ${completed}/${targets.length}（成功 ${success}，失败 ${failed}）`,
                        `Progress ${completed}/${targets.length} (success ${success}, failed ${failed})`
                    ),
                }));
            }
        }

        setBatchAiShotsProgress((prev) => ({
            ...prev,
            running: false,
            message: t(
                `批量完成：成功 ${success}，失败 ${failed}${skipped > 0 ? `，跳过 ${skipped}` : ''}`,
                `Batch done: success ${success}, failed ${failed}${skipped > 0 ? `, skipped ${skipped}` : ''}`
            ),
        }));

        onLog?.(`SceneManager: Batch AI Shots finished. success=${success}, failed=${failed}, skipped=${skipped}`, failed > 0 ? 'warning' : 'success');

        if (typeof onSwitchToShots === 'function') {
            onSwitchToShots();
        }
    };

    const deleteSceneBatch = async (targetScenes, modeLabel = 'selected') => {
        const targets = Array.isArray(targetScenes) ? targetScenes : [];
        if (targets.length === 0) return;

        const confirmText = modeLabel === 'filtered'
            ? t(`确认删除当前筛选的 ${targets.length} 个场景？`, `Delete all ${targets.length} currently filtered scenes?`)
            : t(`确认删除已选中的 ${targets.length} 个场景？`, `Delete ${targets.length} selected scenes?`);
        if (!await confirmUiMessage(confirmText)) return;

        const deletableKeys = new Set();
        const failedLabels = [];

        for (const scene of targets) {
            const key = getSceneSelectionKey(scene);
            const label = scene?.scene_no || scene?.scene_name || (scene?.id ? `#${scene.id}` : t('未命名场景', 'Untitled Scene'));
            if (!scene?.id) {
                deletableKeys.add(key);
                continue;
            }
            try {
                await deleteScene(scene.id);
                deletableKeys.add(key);
            } catch (e) {
                failedLabels.push(`${label}: ${e?.response?.data?.detail || e?.message || 'delete failed'}`);
            }
        }

        if (deletableKeys.size === 0 && failedLabels.length > 0) {
            onLog?.(t('批量删除失败。', 'Bulk delete failed.'), 'error');
            alert(failedLabels.slice(0, 5).join('\n'));
            return;
        }

        const remaining = (scenes || []).filter((scene) => !deletableKeys.has(getSceneSelectionKey(scene)));
        setScenes(remaining);
        setSelectedSceneKeys((prev) => prev.filter((key) => !deletableKeys.has(key)));

        if (editingScene && deletableKeys.has(getSceneSelectionKey(editingScene))) {
            setEditingScene(null);
        }

        if (activeEpisode?.id) {
            try {
                await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(remaining) });
            } catch (e) {
                console.warn('Failed to sync scene_content after batch delete', e);
            }
        }

        onLog?.(
            t(`批量删除完成：删除 ${deletableKeys.size} 个场景。`, `Bulk delete completed: removed ${deletableKeys.size} scenes.`),
            'success'
        );

        if (failedLabels.length > 0) {
            onLog?.(t(`有 ${failedLabels.length} 个场景删除失败。`, `${failedLabels.length} scenes failed to delete.`), 'warning');
            alert(failedLabels.slice(0, 5).join('\n'));
        }
    };

    const handleDeleteSelectedScenes = async () => {
        const targets = (filteredScenes || []).filter((scene) => selectedSceneKeySet.has(getSceneSelectionKey(scene)));
        await deleteSceneBatch(targets, 'selected');
    };

    const handleDeleteFilteredScenes = async () => {
        await deleteSceneBatch(filteredScenes || [], 'filtered');
    };

    const loadLatestAIShotsStaging = async (sceneId) => {
        if (!sceneId) {
            setAiShotsStaging(prev => ({
                ...prev,
                sceneId: null,
                content: [],
                rawText: '',
                usage: null,
                timestamp: null,
                error: null,
                loading: false,
            }));
            return;
        }

        setAiShotsStaging(prev => ({
            ...prev,
            loading: true,
            error: null,
            sceneId,
        }));

        try {
            const latest = await getSceneLatestAIResult(sceneId);
            setAiShotsStaging(prev => ({
                ...prev,
                loading: false,
                sceneId,
                content: Array.isArray(latest?.content) ? latest.content : [],
                rawText: latest?.raw_text || '',
                usage: latest?.usage || null,
                timestamp: latest?.timestamp || null,
            }));
        } catch (e) {
            console.error(e);
            // If there's no staging yet, treat as empty (avoid blocking UX)
            const status = e?.response?.status;
            if (status === 404) {
                setAiShotsStaging(prev => ({
                    ...prev,
                    loading: false,
                    sceneId,
                    content: [],
                    rawText: '',
                    usage: null,
                    timestamp: null,
                    error: null,
                }));
                return;
            }
            setAiShotsStaging(prev => ({
                ...prev,
                loading: false,
                error: e?.response?.data?.detail || e?.message || 'Failed to load latest AI shots result',
            }));
        }
    };

    useEffect(() => {
        if (editingScene?.id) {
            loadLatestAIShotsStaging(editingScene.id);
        } else {
            // Reset when closing or opening an unsaved scene
            setAiShotsStaging(prev => ({
                ...prev,
                loading: false,
                sceneId: null,
                content: [],
                rawText: '',
                usage: null,
                timestamp: null,
                error: null,
                saving: false,
                applying: false,
            }));
            setAiShotRowEditor({ open: false, index: -1, data: null });
        }
    }, [editingScene?.id]);

    const handleConfirmGenerateShots = async () => {
         const { sceneId, data } = shotPromptModal;
         if (!await confirmUiMessage("This will overwrite existing shots for this scene. Continue?")) return;

         setShotPromptModal(prev => ({ ...prev, loading: true }));
         await executeGenerateShots({ sceneId, promptData: data });
    };

    if (!activeEpisode) return <div className="p-6 text-muted-foreground">{t('请选择分集以管理场景。', 'Select an episode to manage scenes.')}</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
             <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    {t('场景', 'Scenes')}
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">{filteredScenes.length}/{scenes.length} {t('场景', 'Scenes')}</span>
                </h2>
                <div className="flex gap-2">
                    <button
                        onClick={runBatchGenerateAiShotsForAllScenes}
                        disabled={batchAiShotsProgress.running || scenes.length === 0}
                        className="px-4 py-2 bg-blue-600/90 text-white rounded-lg text-sm font-bold hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        title={t('后台批量对当前分集所有场景执行 AI Shots 并自动导入', 'Run AI Shots in background for all scenes in this episode and auto-apply')}
                    >
                        {batchAiShotsProgress.running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                        {batchAiShotsProgress.running ? t('批量执行中...', 'Batch Running...') : t('批量 AI Shots（全部）', 'Batch AI Shots (All)')}
                    </button>
                     <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" />
                        {t('保存修改', 'Save Changes')}
                     </button>
                </div>
            </div>

            {(batchAiShotsProgress.running || batchAiShotsProgress.total > 0) && (
                <div className={`mb-4 rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm shrink-0 ${
                    batchAiShotsProgress.running
                        ? 'border-blue-500/30 bg-blue-500/10 text-blue-100'
                        : batchAiShotsProgress.failed > 0
                            ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-100'
                            : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                }`}>
                    {batchAiShotsProgress.running ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    <span>
                        {batchAiShotsProgress.message}
                        {batchAiShotsProgress.currentSceneLabel ? ` · ${t('当前', 'Current')}: ${batchAiShotsProgress.currentSceneLabel}` : ''}
                    </span>
                </div>
            )}

            <div className="mb-4 grid grid-cols-1 md:grid-cols-3 gap-2 shrink-0">
                <input
                    type="text"
                    value={sceneHierarchyFilter}
                    onChange={(e) => setSceneHierarchyFilter(e.target.value)}
                    placeholder={t('筛选场景ID / 场次号（例如 EP01_SC03）', 'Filter Scene ID / Scene No (e.g. EP01_SC03)')}
                    className="bg-black/40 border border-white/20 rounded px-3 py-2 text-sm text-white"
                />
                <input
                    type="text"
                    value={sceneKeywordFilter}
                    onChange={(e) => setSceneKeywordFilter(e.target.value)}
                    placeholder={t('按名称 / 环境 / 角色 / 道具 / 分集筛选', 'Filter by name / env / cast / props / episode')}
                    className="bg-black/40 border border-white/20 rounded px-3 py-2 text-sm text-white"
                />
                <button
                    onClick={() => { setSceneHierarchyFilter(''); setSceneKeywordFilter(''); }}
                    className="px-3 py-2 bg-white/10 hover:bg-white/20 rounded text-xs text-white border border-white/10"
                >
                    {t('清除场景筛选', 'Clear Scene Filters')}
                </button>
            </div>

            <div className="mb-4 flex flex-wrap items-center gap-2 shrink-0">
                <label className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded text-xs text-white">
                    <input
                        type="checkbox"
                        checked={allFilteredSelected}
                        onChange={toggleSelectAllFiltered}
                        disabled={filteredScenes.length === 0}
                        className="accent-primary"
                    />
                    <span>{t('全选当前筛选', 'Select All Filtered')}</span>
                </label>

                <div className="text-xs text-muted-foreground px-2">
                    {t('已选', 'Selected')} {selectedFilteredCount} / {filteredScenes.length}
                </div>

                <button
                    onClick={handleDeleteSelectedScenes}
                    disabled={selectedFilteredCount === 0}
                    className="px-3 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 rounded text-xs text-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {t('删除已选', 'Delete Selected')}
                </button>

                <button
                    onClick={handleDeleteFilteredScenes}
                    disabled={filteredScenes.length === 0}
                    className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded text-xs text-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {t('删除当前筛选全部', 'Delete All Filtered')}
                </button>
            </div>

            {aiShotsFlowStatus.phase !== 'idle' && (
                <div className={`mb-4 rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm shrink-0 ${
                    aiShotsFlowStatus.phase === 'failed'
                        ? 'border-red-500/30 bg-red-500/10 text-red-200'
                        : aiShotsFlowStatus.phase === 'completed'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                            : 'border-primary/30 bg-primary/10 text-primary'
                }`}>
                    {aiShotsFlowStatus.phase === 'completed' ? (
                        <CheckCircle className="w-4 h-4" />
                    ) : aiShotsFlowStatus.phase === 'failed' ? (
                        <X className="w-4 h-4" />
                    ) : (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    )}
                    <span>{aiShotsFlowStatus.message}</span>
                </div>
            )}

            <div className="flex-1 overflow-auto custom-scrollbar pb-20">
                    {filteredScenes.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                        <Clapperboard className="w-12 h-12 mb-4 opacity-20" />
                        <p>{scenes.length === 0 ? t('未找到场景。', 'No scenes found.') : t('没有符合当前筛选的场景。', 'No scenes match current filters.')}</p>
                        <p className="text-xs mt-2 opacity-50">{scenes.length === 0 ? t('可在导入中粘贴 Markdown 表格，或先生成内容。', 'Paste a Markdown table in Import or generate content.') : t('请调整场景ID/关键词筛选后重试。', 'Adjust Scene ID/keyword filters and try again.')}</p>
                    </div>
                    ) : (
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6">
                        {filteredScenes.map((scene, idx) => {
                            const sceneKey = getSceneSelectionKey(scene);
                            return (
                                <SceneCard 
                                    key={idx} 
                                    scene={scene} 
                                    entities={entities} 
                                    uiLang={uiLang}
                                    selected={selectedSceneKeySet.has(sceneKey)}
                                    onToggleSelect={toggleSceneSelected}
                                    onClick={() => setEditingScene(scene)} 
                                    onGenerateShots={handleGenerateShots}
                                    onDelete={handleDeleteScene}
                                />
                            );
                        })}
                    </div>
                    )}
            </div>
            
            <AnimatePresence>
                {editingScene && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setEditingScene(null)}>
                        <motion.div 
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-[#09090b] border border-white/10 rounded-xl w-full max-w-5xl h-[90vh] shadow-2xl flex flex-col overflow-hidden"
                        >
                             <div className="p-4 border-b border-white/10 flex items-center justify-between bg-[#09090b]">
                                <h3 className="font-bold text-lg">{t('编辑场景', 'Edit Scene')} {editingScene.scene_no || editingScene.id}</h3>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => handleDeleteScene(editingScene)}
                                        disabled={!editingScene?.id}
                                        className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/20 rounded text-xs flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={editingScene?.id ? t('删除该场景', 'Delete this scene') : t('请先保存场景', 'Save scene first')}
                                    >
                                        <Trash2 className="w-3 h-3"/> {t('删除', 'Delete')}
                                    </button>
                                    <button
                                        onClick={() => editingScene?.id && handleGenerateShots(editingScene.id)}
                                        disabled={!editingScene?.id}
                                        className="px-3 py-1.5 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/20 rounded text-xs flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={editingScene?.id ? t('为该场景生成 AI 镜头', 'Generate AI shots for this scene') : t('请先保存场景再生成 AI 镜头', 'Save scene first to generate AI shots')}
                                    >
                                        <Wand2 className="w-3 h-3"/> AI Shots
                                    </button>
                                    <button onClick={() => setEditingScene(null)} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                                </div>
                            </div>
                            
                            <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                                <div className="space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-4">
                                            <div className="grid grid-cols-2 gap-4">
                                                <InputGroup label={t('场次号', 'Scene No')} value={editingScene.scene_no || editingScene.id} onChange={v => handleSceneUpdate({...editingScene, scene_no: v})} />
                                                <InputGroup label={t('时长', 'Duration')} value={editingScene.equivalent_duration} onChange={v => handleSceneUpdate({...editingScene, equivalent_duration: v})} />
                                            </div>
                                                <InputGroup label={t('场景名称', 'Scene Name')} value={editingScene.scene_name} onChange={v => handleSceneUpdate({...editingScene, scene_name: v})} />
                                                <InputGroup label={t('环境锚点', 'Environment Anchor')} value={editingScene.environment_name} onChange={v => handleSceneUpdate({...editingScene, environment_name: v})} />
                                                <InputGroup label={t('关联角色（逗号分隔）', 'Linked Characters (Comma separated)')} value={editingScene.linked_characters} onChange={v => handleSceneUpdate({...editingScene, linked_characters: v})} />
                                                <InputGroup label={t('关键道具', 'Key Props')} value={editingScene.key_props} onChange={v => handleSceneUpdate({...editingScene, key_props: v})} />
                                        </div>

                                        <div className="flex flex-col h-full"> 
                                            <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block">{t('原始剧本文本', 'Original Script Text')}</label>
                                            <MarkdownCell value={editingScene.original_script_text} onChange={v => handleSceneUpdate({...editingScene, original_script_text: v})} className="flex-1 min-h-[200px]" />
                                        </div>
                                    </div>
                                    
                                    <div className="pt-4 border-t border-white/5 h-full flex flex-col">
                                         <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block text-primary/80">{t('核心场景信息（视觉指导）', 'Core Scene Info (Visual Direction)')}</label>
                                         <textarea 
                                            className="w-full flex-1 bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-none custom-scrollbar font-mono leading-relaxed min-h-[400px]"
                                            value={editingScene.core_scene_info || ''}
                                            onChange={e => handleSceneUpdate({...editingScene, core_scene_info: e.target.value})}
                                            placeholder={t('输入视觉指导、光照、情绪、构图等...', 'Enter visual direction, lighting, mood, composition...')}
                                        />
                                    </div>

                                    <div className="pt-4 border-t border-white/5">
                                        <div className="flex items-center justify-between gap-3 mb-2">
                                            <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider block text-primary/80">AI Shots (Staging)</label>
                                            <div className="text-[10px] text-muted-foreground">双击任意行可弹窗编辑并保存更新</div>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={async () => {
                                                        if (!editingScene.id) return;
                                                        setAiShotsStaging(prev => ({ ...prev, saving: true }));
                                                        try {
                                                            await updateSceneLatestAIResult(editingScene.id, aiShotsStaging.content || []);
                                                            onLog?.('Staged draft saved.', 'success');
                                                        } catch (e) {
                                                            onLog?.('Failed to save draft: ' + (e?.response?.data?.detail || e?.message), 'error');
                                                        } finally {
                                                            setAiShotsStaging(prev => ({ ...prev, saving: false }));
                                                        }
                                                    }}
                                                    disabled={!editingScene.id || aiShotsStaging.saving}
                                                    className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-md text-xs font-bold text-white disabled:opacity-50"
                                                    title={t('将编辑后的暂存表保存回 scenes.ai_shots_result', 'Save the edited staging table back into scenes.ai_shots_result')}
                                                >
                                                    {aiShotsStaging.saving ? t('保存中…', 'Saving…') : t('保存草稿', 'Save Draft')}
                                                </button>
                                                <button
                                                    onClick={async () => {
                                                        if (!editingScene.id) return;
                                                        if (!await confirmUiMessage(t('应用这些镜头吗？这会替换现有镜头。', 'Apply these shots? This will replace existing shots.'))) return;
                                                        setAiShotsStaging(prev => ({ ...prev, applying: true }));
                                                        try {
                                                            await applySceneAIResult(editingScene.id, { content: aiShotsStaging.content || [] });
                                                            onLog?.(t('镜头已应用到数据库。', 'Shots applied to database.'), 'success');
                                                        } catch (e) {
                                                            onLog?.(t('应用镜头失败: ', 'Failed to apply shots: ') + (e?.response?.data?.detail || e?.message), 'error');
                                                        } finally {
                                                            setAiShotsStaging(prev => ({ ...prev, applying: false }));
                                                        }
                                                    }}
                                                    disabled={!editingScene.id || aiShotsStaging.applying}
                                                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 rounded-md text-xs font-bold text-white disabled:opacity-50"
                                                    title={t('将暂存镜头导入/应用到 shots 表', 'Import/apply the staged shots into the shots table')}
                                                >
                                                    {aiShotsStaging.applying ? t('应用中…', 'Applying…') : t('应用到场景', 'Apply to Scene')}
                                                </button>
                                            </div>
                                        </div>

                                        {!editingScene.id ? (
                                            <div className="text-xs text-muted-foreground bg-white/5 border border-white/10 rounded p-3">
                                                {t('请先保存当前场景，以创建数据库记录后再加载或应用 AI 镜头。', 'Save this Scene first to create a DB record before loading or applying AI shots.')}
                                            </div>
                                        ) : aiShotsStaging.error ? (
                                            <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded p-3">
                                                {aiShotsStaging.error}
                                            </div>
                                        ) : aiShotsStaging.loading ? (
                                            <div className="flex items-center justify-center h-24"><Loader2 className="animate-spin text-primary" size={24}/></div>
                                        ) : (aiShotsStaging.content || []).length === 0 ? (
                                            <div className="text-xs text-muted-foreground bg-white/5 border border-white/10 rounded p-3">
                                                {t('暂无暂存 AI 镜头。请先为该场景生成 AI 镜头。', 'No staged AI shots yet. Generate AI shots for this scene first.')}
                                            </div>
                                        ) : (
                                            <div className="bg-black/30 border border-white/10 rounded-md overflow-hidden">
                                                <div className="max-h-[320px] overflow-auto custom-scrollbar">
                                                    <table className="w-full text-xs text-left border-collapse">
                                                        <thead className="sticky top-0 bg-[#252525] z-10 shadow-md">
                                                            <tr>
                                                                {['Shot ID', 'Shot Name', 'Scene ID', 'Shot Logic (CN)', 'Start Frame', 'Video Content', 'Duration (s)', 'Keyframes', 'End Frame', 'Associated Entities'].map(h => (
                                                                    <th key={h} className="p-2 border-b border-white/10 font-bold text-white/70">{h}</th>
                                                                ))}
                                                                <th className="p-2 border-b border-white/10 w-10"></th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-white/5">
                                                            {(aiShotsStaging.content || []).map((shot, idx) => (
                                                                <tr
                                                                    key={idx}
                                                                    className="hover:bg-white/5 group cursor-pointer"
                                                                    onDoubleClick={() => openAiShotRowEditor(shot, idx)}
                                                                    title={t('双击可在弹窗中编辑该行', 'Double click to edit this row in popup')}
                                                                >
                                                                    <td className="p-1">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Shot ID'] || shot.shot_id || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Shot ID': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Shot Name'] || shot.shot_name || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Shot Name': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Scene ID'] || shot.scene_id || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Scene ID': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Shot Logic (CN)'] || shot.shot_logic_cn || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Shot Logic (CN)': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <textarea
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded resize-y min-h-[40px]"
                                                                            value={shot['Start Frame'] || shot.start_frame || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Start Frame': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <textarea
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded resize-y min-h-[40px]"
                                                                            value={shot['Video Content'] || shot.video_content || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Video Content': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1 w-20">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Duration (s)'] || shot.duration || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Duration (s)': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Keyframes'] || shot.keyframes || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Keyframes': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <textarea
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded resize-y min-h-[40px]"
                                                                            value={shot['End Frame'] || shot.end_frame || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'End Frame': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1">
                                                                        <input
                                                                            className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                            value={shot['Associated Entities'] || shot.associated_entities || ''}
                                                                            onChange={e => {
                                                                                const newData = [...(aiShotsStaging.content || [])];
                                                                                newData[idx] = { ...shot, 'Associated Entities': e.target.value };
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                        />
                                                                    </td>
                                                                    <td className="p-1 text-center">
                                                                        <button
                                                                            onClick={() => {
                                                                                const newData = (aiShotsStaging.content || []).filter((_, i) => i !== idx);
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                            className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500"
                                                                            title={t('删除行', 'Delete row')}
                                                                        >
                                                                            <Trash2 size={14}/>
                                                                        </button>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                                <div className="p-2 border-t border-white/10 flex items-center justify-between">
                                                    <button
                                                        onClick={() => {
                                                            const newData = [...(aiShotsStaging.content || []), { 'Shot ID': (aiShotsStaging.content?.length || 0) + 1, 'Video Content': '' }];
                                                            setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                        }}
                                                        className="px-3 py-1 bg-white/5 hover:bg-white/10 rounded flex items-center gap-2 text-xs"
                                                    >
                                                        <Plus size={14}/> {t('新增一行', 'Add Row')}
                                                    </button>
                                                    {(aiShotsStaging.timestamp || aiShotsStaging.usage) && (
                                                        <div className="text-[10px] text-muted-foreground">
                                                            {aiShotsStaging.timestamp ? `Updated: ${aiShotsStaging.timestamp}` : ''}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {editingScene.id && aiShotsStaging.rawText ? (
                                            <div className="mt-3">
                                                <label className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('原始 LLM 文本（只读）', 'Raw LLM Text (Read-only)')}</label>
                                                <textarea
                                                    readOnly
                                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white/80 text-xs focus:outline-none resize-y custom-scrollbar font-mono leading-relaxed min-h-[120px]"
                                                    value={aiShotsStaging.rawText}
                                                />
                                            </div>
                                        ) : null}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
            
            {shotPromptModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary"/> Generate AI Shots</h3>
                            <button onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {shotPromptModal.loading && !shotPromptModal.data ? (
                                <div className="flex items-center justify-center h-40"><Loader2 className="animate-spin text-primary" size={32}/></div>
                            ) : (
                                <>
                                    <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-xs text-blue-200 flex items-start gap-2">
                                        <Info size={14} className="shrink-0 mt-0.5" />
                                        Review and edit the prompt before generation. Only the User Prompt (scenario context) is typically edited.
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">User Prompt (Scenario content)</label>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono h-64 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.user_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, user_prompt: e.target.value}}))}
                                        />
                                    </div>
                                    
                                     <div className="flex flex-col gap-2">
                                         <div className="flex items-center justify-between">
                                              <label className="text-xs font-bold text-muted-foreground uppercase">System Prompt (Instructions)</label>
                                              <span className="text-xs text-muted-foreground px-2 py-1 bg-white/5 rounded">Default/Template</span>
                                         </div>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono h-32 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.system_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, system_prompt: e.target.value}}))}
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                        
                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button 
                                onClick={() => {
                                    const full = (shotPromptModal.data?.system_prompt || '') + "\n\n" + (shotPromptModal.data?.user_prompt || '');
                                    navigator.clipboard.writeText(full);
                                    onLog?.(t('完整提示词已复制到剪贴板', 'Full prompt copied to clipboard'), "success");
                                }}
                                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-medium flex items-center gap-2 mr-auto"
                            >
                                <Copy size={16}/> {t('复制完整提示词', 'Copy Full Prompt')}
                            </button>
                            <button 
                                onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button 
                                onClick={handleConfirmGenerateShots}
                                disabled={shotPromptModal.loading}
                                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotPromptModal.loading ? <Loader2 className="animate-spin" size={16}/> : <Wand2 size={16}/>}
                                {shotPromptModal.loading ? t('生成中...', 'Generating...') : t('生成镜头', 'Generate Shots')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {aiShotRowEditor.open && (
                <div className="fixed inset-0 z-[60] bg-black/85 flex items-center justify-center p-4" onClick={() => setAiShotRowEditor({ open: false, index: -1, data: null })}>
                    <div className="bg-[#1b1b1b] border border-white/10 rounded-xl w-full max-w-3xl max-h-[88vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
                        <div className="p-4 border-b border-white/10 flex items-center justify-between">
                            <h3 className="font-bold text-white">{t('编辑 AI 镜头行', 'Edit AI Shot Row')} #{aiShotRowEditor.index + 1}</h3>
                            <button onClick={() => setAiShotRowEditor({ open: false, index: -1, data: null })} className="p-1 hover:bg-white/10 rounded"><X size={18}/></button>
                        </div>
                        <div className="p-4 space-y-3 overflow-y-auto custom-scrollbar max-h-[68vh]">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <InputGroup label={t('镜头 ID', 'Shot ID')} value={aiShotRowEditor.data?.shot_id || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), shot_id: v } }))} />
                                <InputGroup label={t('镜头名称', 'Shot Name')} value={aiShotRowEditor.data?.shot_name || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), shot_name: v } }))} />
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <InputGroup label={t('场景 ID', 'Scene ID')} value={aiShotRowEditor.data?.scene_id || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), scene_id: v } }))} />
                                <InputGroup label={t('时长（秒）', 'Duration (s)')} value={aiShotRowEditor.data?.duration || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), duration: v } }))} />
                            </div>
                            <InputGroup label={t('镜头逻辑（中文）', 'Shot Logic (CN)')} value={aiShotRowEditor.data?.shot_logic_cn || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), shot_logic_cn: v } }))} />
                            <InputGroup label={t('关联实体', 'Associated Entities')} value={aiShotRowEditor.data?.associated_entities || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), associated_entities: v } }))} />
                            <InputGroup label={t('关键帧', 'Keyframes')} value={aiShotRowEditor.data?.keyframes || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), keyframes: v } }))} />
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('起始帧', 'Start Frame')}</label>
                                <textarea
                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y custom-scrollbar font-mono leading-relaxed min-h-[120px]"
                                    value={aiShotRowEditor.data?.start_frame || ''}
                                    onChange={e => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), start_frame: e.target.value } }))}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('视频内容', 'Video Content')}</label>
                                <textarea
                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y custom-scrollbar font-mono leading-relaxed min-h-[180px]"
                                    value={aiShotRowEditor.data?.video_content || ''}
                                    onChange={e => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), video_content: e.target.value } }))}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('结束帧', 'End Frame')}</label>
                                <textarea
                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y custom-scrollbar font-mono leading-relaxed min-h-[120px]"
                                    value={aiShotRowEditor.data?.end_frame || ''}
                                    onChange={e => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), end_frame: e.target.value } }))}
                                />
                            </div>
                        </div>
                        <div className="p-4 border-t border-white/10 flex justify-end gap-2 bg-black/20">
                            <button onClick={() => setAiShotRowEditor({ open: false, index: -1, data: null })} className="px-4 py-2 rounded hover:bg-white/10 text-sm">{t('取消', 'Cancel')}</button>
                            <button onClick={saveAiShotRowEditor} className="px-5 py-2 bg-primary text-black rounded font-bold text-sm hover:bg-primary/90">{t('保存行', 'Save Row')}</button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
};

const SubjectLibrary = ({ projectId, currentEpisode, uiLang = 'zh' }) => {
    const { addLog: onLog } = useLog();
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [subTab, setSubTab] = useState('character');
    const [entities, setEntities] = useState([]);
    const [allEntities, setAllEntities] = useState([]); // Store ALL entities for cross-reference
    const [selectedEntity, setSelectedEntity] = useState(null);
    const [showImageModal, setShowImageModal] = useState(false);
    const [imageModalTab, setImageModalTab] = useState('library'); // library, upload, generate
    const [generating, setGenerating] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [prompt, setPrompt] = useState('');
    const [provider, setProvider] = useState('');
    const [refImage, setRefImage] = useState(null);
    const [refSelectionMode, setRefSelectionMode] = useState(null); // 'assets'
    const [assets, setAssets] = useState([]);
    const [availableProviders, setAvailableProviders] = useState([]);
    const [activeSourceImage, setActiveSourceImage] = useState('unset');
    const [viewingEntity, setViewingEntity] = useState(null);
    const [isBatchGeneratingEntities, setIsBatchGeneratingEntities] = useState(false);
    const [batchEntityProgress, setBatchEntityProgress] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });

    const openMediaPicker = (callback, context = {}) => {
        setPickerConfig({ isOpen: true, callback, context });
    };

    // Load active providers
    useEffect(() => {
        const loadProviders = async () => {
            try {
                const settings = await getSettings();
                // Filter for Image provider that are active
                // Ensure unique providers if multiple keys exist for same provider? 
                // DB structure seems to be one entry per provider config.
                // But let's verify what 'settings' looks like. 
                // APISetting schema: provider, api_key, category, is_active...
                const imageProviders = settings.filter(s => s.category === 'Image' && s.is_active);
                setAvailableProviders(imageProviders);
                setActiveSourceImage(getSettingSourceByCategory(settings, 'Image'));
            } catch (e) {
                console.error("Failed to load providers", e);
            }
        };
        loadProviders();
    }, []);
    
    // Load entities - NOW FETCHES ALL and filters locally
    const loadEntities = useCallback(async () => {
        if (!projectId) return;
        try {
            const data = await fetchEntities(projectId); // Fetch ALL types
            setAllEntities(data);
        } catch (e) {
            console.error(e);
        }
    }, [projectId]);

    useEffect(() => {
        loadEntities();
    }, [loadEntities]);

    // Local Filtering based on subTab
    useEffect(() => {
        setEntities(allEntities.filter(e => e.type === subTab));
    }, [allEntities, subTab]);

    // Create Entity
    const [isAnalyzingEntity, setIsAnalyzingEntity] = useState(false);

    const handleAnalyzeEntity = async (entity) => {
        if (!entity || !entity.id || !entity.image_url) {
            alert("No entity or image selected.");
            return;
        }
        
        setIsAnalyzingEntity(true);
        if (onLog) onLog(`Analyzing image for subject ${entity.name}...`, "process");
        
        try {
            const updated = await analyzeEntityImage(entity.id);
            setViewingEntity(updated);
            setEntities(prev => prev.map(e => e.id === updated.id ? updated : e));
            if (onLog) onLog("Subject updated from analysis.", "success");
        } catch (e) {
            console.error(e);
            alert("Analysis failed: " + (e.response?.data?.detail || e.message));
            if (onLog) onLog("Analysis failed.", "error");
        } finally {
            setIsAnalyzingEntity(false);
        }
    };

    const handleCreate = async () => {
        // Create a temporary "New Entity" state to open the modal in "Create Mode"
        // We use a special ID 'new' to signal that this is not yet in DB
        setViewingEntity({
            id: 'new',
            name: '',
            type: subTab,
            description: '',
            anchor_description: '',
            generation_prompt_en: '',
            appearance_cn: '',
            clothing: '',
            visual_params: '',
            atmosphere: '',
            narrative_description: '',
            name_en: '',
            role: '',
            archetype: '',
            gender: ''
        });
    };

    // Helper: Update Field (Sync to DB if not new)
    const handleFieldUpdate = (field, value) => {
        if (!viewingEntity) return;
        
        // Always update local viewing state
        setViewingEntity(prev => ({ ...prev, [field]: value }));

        // Only sync to server if it's an existing entity
        if (viewingEntity.id !== 'new') {
            const updated = { ...viewingEntity, [field]: value };
            
            // Optimistic Update
            setEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
            setAllEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
            
            updateEntity(updated.id, { [field]: value }).catch(console.error);
        }
    };

    // Helper: Commit Create (Save manually)
    const handleCommitCreate = async () => {
        if (!viewingEntity || !viewingEntity.name) {
            alert("Name is required");
            return;
        }
        try {
            // Must clone and remove the 'new' ID
            const payload = { ...viewingEntity };
            delete payload.id; 
            
            const newEnt = await createEntity(projectId, payload);
            
            // Update local state with real object (and real ID)
            setAllEntities(prev => [...prev, newEnt]);
            
            // If current tab matches, show it
            if (newEnt.type === subTab) {
                setEntities(prev => [...prev, newEnt]);
            }
            
            // Switch view to the real entity (no longer 'new')
            setViewingEntity(newEnt);
            alert("Subject Created Successfully!");
        } catch (e) {
            console.error(e);
            alert("Failed to create subject: " + e.message);
        }
    };


    // Delete Entity
    const handleDeleteEntity = async (e, entity) => {
        e.stopPropagation();
        if (!await confirmUiMessage(`Are you sure you want to delete ${entity.name}?`)) return;
        try {
            await deleteEntity(entity.id);
            loadEntities();
            if (viewingEntity?.id === entity.id) setViewingEntity(null);
        } catch (e) {
            console.error(e);
            alert(`Failed to delete entity: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleDeleteAllEntities = async () => {
        if (!await confirmUiMessage("WARNING: This will delete ALL subjects/entities in this library. This action cannot be undone. Are you sure?")) return;
        try {
            await deleteAllEntities(projectId);
            loadEntities();
            setViewingEntity(null);
        } catch (e) {
            console.error(e);
            alert(`Failed to delete all entities: ${e?.message || 'Unknown error'}`);
        }
    };
    
    // Open Image Modal
    const handleOpenImageModal = (entity, defaultTab = 'library') => {
        setSelectedEntity(entity);
        setImageModalTab(defaultTab); // This might cause render before prompt is set?
        
        // Prefill prompt with processed template
        let rawPrompt = entity.generation_prompt_en || '';
        
        // Fallback: Try to extract from description if available (for legacy imports)
        if (!rawPrompt && entity.description) {
            const match = entity.description.match(/Prompt:\s*(.*)/);
            if (match && match[1]) {
                rawPrompt = match[1].trim();
            }
        }

        const epInfo = currentEpisode?.episode_info || {};
        
        // If undefined, ensure we pass empty object to avoid crash in utils
        // Use allEntities for resolution to ensure cross-type references work
        let processed = processPrompt(rawPrompt, epInfo, allEntities) || ''; 

        // Append Type, Lighting, Quality from Episode Global Info
        const infoSource = epInfo.e_global_info || epInfo;
        const type = infoSource.type;
        const lighting = infoSource.lighting;
        const quality = infoSource.tech_params?.visual_standard?.quality;
        
        const suffixes = [type, lighting, quality].filter(Boolean);
        if (suffixes.length > 0) {
            processed += ", " + suffixes.join(", ");
        }

        setPrompt(processed);
        setShowImageModal(true); // Show AFTER setting everything

        setRefImage(null);
        
        // Default to active provider if available, otherwise system default
        if (availableProviders && availableProviders.length > 0) {
            setProvider(availableProviders[0].provider);
        } else {
            setProvider('');
        }
        setRefSelectionMode(null); 
        loadAssets();
    };

    // Load Assets
    const loadAssets = async () => {
        try {
            const data = await fetchAssets();
            setAssets(data.filter(a => a.type === 'image'));
        } catch (e) {
            console.error(e);
        }
    };

    // Image Handlers
    const  handleSelectAsset = async (asset) => {
        await updateEntityImage(asset.url);
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true);
        try {
            const asset = await uploadAsset(file);
            await updateEntityImage(asset.url);
        } catch (e) {
            console.error(e);
        } finally {
            setUploading(false);
        }
    };

    const handleGenerate = async () => {
        if (!prompt) return;
        setGenerating(true);

        // Use shared utility for prompt processing
        const epInfo = currentEpisode?.episode_info || {};
        // prompt likely already has suffixes appended from initialization, 
        // but we run processPrompt again in case user added new variables.
        // Use allEntities for resolution
        const finalPrompt = processPrompt(prompt, epInfo, allEntities);
        
        // Update UI to show processed prompt (in case var replacement happened)
        setPrompt(finalPrompt);

        try {
            // Resolve Visual Dependencies
            const depUrls = [];
            if (selectedEntity && selectedEntity.visual_dependencies) {
                 const deps = Array.isArray(selectedEntity.visual_dependencies) ? selectedEntity.visual_dependencies : [];
                 deps.forEach(dep => {
                     // dep can be name or id
                     const startDep = String(dep).trim();
                     if (!startDep) return;
                     const startDepLower = startDep.toLowerCase();
                     
                     // Use allEntities for resolution with case-insensitive match
                     const target = allEntities.find(e => {
                         if (!e) return false;
                         if (String(e.id) === startDep) return true;
                         if (e.name && e.name.trim().toLowerCase() === startDepLower) return true;
                         if (e.name_en && e.name_en.trim().toLowerCase() === startDepLower) return true;
                         return false;
                     });

                     if (target && target.image_url) {
                         depUrls.push(target.image_url);
                     }
                 });
            }

            // Combine manual ref and auto-refs
            const allRefs = [];
            if (refImage?.url) allRefs.push(refImage.url);
            if (depUrls.length > 0) allRefs.push(...depUrls);
            
            // Deduplicate
            const uniqueRefs = [...new Set(allRefs)];

            const asset = await generateImage(finalPrompt, provider || null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                project_id: projectId,
                entity_name: selectedEntity?.name || selectedEntity?.name_en,
                subject_name: selectedEntity?.name || selectedEntity?.name_en,
                asset_type: 'subject'
            });
            await updateEntityImage(asset.url);
        } catch (e) {
            console.error(e);
            alert("Generation Failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setGenerating(false);
        }
    };

    const handleRefUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
             // We reuse uploadAsset but don't assign to entity yet, just set as refImage
             const asset = await uploadAsset(file);
             setRefImage(asset);
        } catch (e) {
            console.error(e);
        }
    };

    const updateEntityImage = async (url) => {
        if (!selectedEntity) return;
        try {
            await updateEntity(selectedEntity.id, { image_url: url });
            setShowImageModal(false);
            loadEntities();
        } catch (e) {
            console.error(e);
        }
    };

    const handleBatchGenerateEntities = async () => {
        const toGenerate = allEntities.filter(e => !e.image_url);
        if (toGenerate.length === 0) {
            alert("All entities already have images!");
            return;
        }

        if (!await confirmUiMessage(`Batch generate images for ${toGenerate.length} entities? This will respect dependency order.`)) return;

        setBatchEntityProgress({ current: 0, total: toGenerate.length, status: 'Initializing...' });
        setIsBatchGeneratingEntities(true);

        // Determine Dependency Map
        const nameMap = new Map();
        allEntities.forEach(e => {
            if (e.name) nameMap.set(e.name.trim().toLowerCase(), e);
            if (e.name_en) nameMap.set(e.name_en.trim().toLowerCase(), e);
        });

        // Current status of images (starts with existing)
        // We use a mutable URL map to track latest URLs during the batch process
        const urlMap = new Map();
        allEntities.forEach(e => {
            if (e.image_url) urlMap.set(e.id, e.image_url);
        });

        let queue = [...toGenerate];
        let processedCount = 0;
        
        // Helper to check if entity is ready (all its deps have images)
        const isReady = (ent) => {
            const deps = Array.isArray(ent.visual_dependencies) ? ent.visual_dependencies : [];
            if (deps.length === 0) return true;
            
            return deps.every(depRaw => {
                const dep = String(depRaw).trim().toLowerCase();
                let target = null;
                 if (allEntities.find(e => String(e.id) === dep)) {
                     target = allEntities.find(e => String(e.id) === dep);
                 } else {
                     target = nameMap.get(dep);
                 }

                if (!target) return true; // External/Unknown dep doesn't block
                return urlMap.has(target.id);
            });
        };

        try {
            while (queue.length > 0) {
                // Find all entities that are ready
                const readyBatch = queue.filter(e => isReady(e));
                
                let batch = [];
                if (readyBatch.length > 0) {
                    batch = readyBatch;
                } else {
                    // Cycle or blocked -> Force proceed with one
                    batch = [queue[0]];
                }

                for (const entity of batch) {
                    const idx = processedCount + 1;
                    setBatchEntityProgress({ current: idx, total: toGenerate.length, status: `Generating ${entity.name}...` });
                    
                    try {
                        // 1. Prepare Prompt
                        const epInfo = currentEpisode?.episode_info || {};
                        let basePrompt = entity.generation_prompt_en || 
                                         entity.description || 
                                         `A ${entity.type} named ${entity.name}.`;
                        
                        if (!basePrompt || basePrompt.trim().length < 2) {
                             basePrompt = `${entity.type} ${entity.name}`;
                        }

                        // We pass 'allEntities' so [Reference] replacement works
                        // Note: processPrompt uses allEntities to find values. 
                        // It reads entity.description usually.
                        const finalPrompt = processPrompt(basePrompt, epInfo, allEntities);
                        
                        // 2. Resolve Dependencies (Build Ref URLs FROM LATEST MAP)
                        const depUrls = [];
                         const deps = Array.isArray(entity.visual_dependencies) ? entity.visual_dependencies : [];
                         deps.forEach(dep => {
                             const startDep = String(dep).trim();
                             const startDepLower = startDep.toLowerCase();
                             
                             let target = allEntities.find(e => {
                                 if (!e) return false;
                                 if (String(e.id) === startDep) return true;
                                 if (e.name && e.name.trim().toLowerCase() === startDepLower) return true;
                                 if (e.name_en && e.name_en.trim().toLowerCase() === startDepLower) return true;
                                 return false;
                             });

                             // Use urlMap to get the LATEST url (since target object might be stale in allEntities closure vs real-time updates)
                             if (target && urlMap.has(target.id)) {
                                 depUrls.push(urlMap.get(target.id));
                             }
                        });
                        const uniqueRefs = [...new Set(depUrls)];
                        
                        // 3. Generate
                        const res = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                            project_id: projectId,
                            entity_name: entity?.name || entity?.name_en,
                            subject_name: entity?.name || entity?.name_en,
                            asset_type: 'subject'
                        });
                        
                        if (res && res.url) {
                            // 4. Update
                            await updateEntity(entity.id, { image_url: res.url });
                            
                            // Update local tracking
                            urlMap.set(entity.id, res.url);
                            
                            const updatedEnt = { ...entity, image_url: res.url };
                            
                            // Update Master List
                            setAllEntities(prev => prev.map(e => e.id === entity.id ? updatedEnt : e));
                            
                            // Update Current View (Force Refresh)
                            setEntities(prev => {
                                if (prev.some(p => p.id === entity.id)) {
                                    return prev.map(e => e.id === entity.id ? updatedEnt : e);
                                }
                                return prev;
                            });

                            // Update Modal if open
                            if (viewingEntity && viewingEntity.id === entity.id) {
                                setViewingEntity(updatedEnt);
                            }
                        }

                    } catch(e) {
                         console.error(`Batch Gen Error for ${entity.name}`, e);
                    }

                    queue = queue.filter(q => q.id !== entity.id);
                    processedCount++;
                }
            }
            alert("Batch Generation Complete!");
        } catch (e) {
            console.error(e);
            alert("Batch Generation Failed: " + e.message);
        } finally {
            setIsBatchGeneratingEntities(false);
            setBatchEntityProgress(null);
        }
    };

    return (
        <div className="p-6 h-full flex flex-col w-full relative">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold">{t('角色资产库', 'Subjects Library')}</h2>
                <div className="flex items-center gap-4">
                     <button 
                        onClick={handleDeleteAllEntities}
                        className="p-2 text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded-md transition-colors"
                    title={t('删除全部角色资产', 'Delete All Subjects')}
                    >
                        <Trash2 size={16} />
                    </button>
                     <button 
                        onClick={handleBatchGenerateEntities}
                        disabled={isBatchGeneratingEntities}
                        className="px-3 py-2 text-xs font-bold uppercase rounded-md bg-white/10 hover:bg-white/20 text-white flex items-center gap-2 disabled:opacity-50 transition-all border border-white/10"
                        title={t('批量生成全部实体（遵循依赖）', 'Batch Generate All Entities (Respects Dependencies)')}
                    >
                         {isBatchGeneratingEntities ? (
                             <>
                                 <RefreshCw className="animate-spin" size={12} /> 
                                 {t('批处理中', 'Batching')} {batchEntityProgress ? `${batchEntityProgress.current}/${batchEntityProgress.total}` : '...'}
                             </>
                         ) : (
                             <>
                                <Wand2 size={12} /> {t('自动补全全部图片', 'Auto-Fill All Images')}
                             </>
                         )}
                    </button>

                    <div className="flex space-x-1 bg-card border border-white/10 p-1 rounded-lg">
                        {['character', 'environment', 'prop'].map(t => (
                            <button 
                                key={t}
                                onClick={() => setSubTab(t)}
                                className={`px-4 py-2 text-xs font-bold uppercase rounded-md transition-all ${subTab === t ? 'bg-primary text-black' : 'hover:bg-white/5 text-muted-foreground'}`}
                            >
                                {t}s
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            
            {/* Batch Status Bar */}
            {isBatchGeneratingEntities && batchEntityProgress && (
                <div className="mb-4 bg-primary/10 border border-primary/20 rounded-lg p-3 flex items-center justify-between text-xs text-primary">
                    <span className="font-bold flex items-center gap-2">
                         <RefreshCw className="animate-spin" size={12} />
                         {batchEntityProgress.status}
                    </span>
                    <span className="font-mono">{Math.round((batchEntityProgress.current / batchEntityProgress.total) * 100)}%</span>
                </div>
            )}
            
            <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-6 w-full">
                <div 
                    onClick={handleCreate}
                    className="aspect-[3/4] border-2 border-dashed border-white/10 rounded-xl flex flex-col items-center justify-center text-muted-foreground hover:border-primary/50 hover:text-primary cursor-pointer transition-all bg-black/20 w-full">
                    <span className="text-4xl mb-2"><Plus /></span>
                    <span className="text-xs uppercase font-bold">{t('新建', 'New')} {subTab}</span>
                </div>
                
                {entities.map(entity => (
                    <div 
                        key={entity.id} 
                        onClick={() => setViewingEntity(entity)}
                        className="aspect-[3/4] bg-card border border-white/10 rounded-xl overflow-hidden relative group w-full cursor-pointer hover:border-primary/50 transition-all"
                    >
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent z-10 pointer-events-none"></div>
                        {entity.image_url ? (
                            <img src={getFullUrl(entity.image_url)} alt={entity.name} className="absolute inset-0 object-cover w-full h-full" />
                        ) : (
                            <div className="absolute inset-0 flex items-center justify-center bg-white/5">
                                <Users className="text-white/20" size={48} />
                            </div>
                        )}
                        
                        <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                            <button 
                                onClick={(e) => { e.stopPropagation(); handleOpenImageModal(entity, 'library'); }}
                                className="p-2 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md"
                                title={t('更换图片（素材库/上传）', 'Change Image (Library/Upload)')}
                            >
                                <ImageIcon size={16} />
                            </button>
                            <button 
                                onClick={(e) => { e.stopPropagation(); handleOpenImageModal(entity, 'generate'); }}
                                className="p-2 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md"
                                title={t('生成 AI 图片', 'Generate AI Image')}
                            >
                                <Wand2 size={16} />
                            </button>
                            <button 
                                onClick={(e) => handleDeleteEntity(e, entity)}
                                className="p-2 bg-red-500/80 hover:bg-red-600 rounded-full text-white backdrop-blur-md"
                                title={t('删除实体', 'Delete Entity')}
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>

                        <div className="absolute bottom-3 left-3 z-20 pointer-events-none">
                            <div className="font-bold text-white capitalize">{entity.name}</div>
                            <div className="text-[10px] text-white/60">{entity.description?.substring(0, 30)}...</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Entity Detail Modal */}
            <AnimatePresence>
                {viewingEntity && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-8" onClick={() => setViewingEntity(null)}>
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-[#1e1e1e] border border-white/10 rounded-2xl w-full max-w-5xl h-[80vh] flex shadow-2xl overflow-hidden"
                        >
                            {/* Left: Image */}
                            <div className="w-1/2 bg-black relative flex items-center justify-center">
                                {viewingEntity.image_url ? (
                                    <img src={getFullUrl(viewingEntity.image_url)} alt={viewingEntity.name} className="max-w-full max-h-full object-contain" />
                                ) : (
                                    <div className="flex flex-col items-center justify-center text-white/20">
                                        <Users size={64} />
                                        <span className="mt-4 text-sm font-bold uppercase">{t('无图片', 'No Image')}</span>
                                    </div>
                                )}
                                
                                {viewingEntity.id !== 'new' && (
                                    <div className="absolute top-4 left-4 flex gap-2">
                                         <button 
                                            onClick={() => { setViewingEntity(null); handleOpenImageModal(viewingEntity, 'library'); }}
                                            className="p-3 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md transition-colors"
                                                          title={t('更换图片', 'Change Image')}
                                         >
                                             <ImageIcon size={20} />
                                         </button>
                                         <button 
                                            onClick={(e) => { e.stopPropagation(); handleAnalyzeEntity(viewingEntity); }}
                                            disabled={isAnalyzingEntity}
                                            className="p-3 bg-indigo-500/80 hover:bg-indigo-500 text-white rounded-full backdrop-blur-md transition-colors disabled:opacity-50 shadow-lg border border-white/10"
                                                          title={t('分析图片并优化主体信息（生成新的提示词文件）', 'Analyze Image & Refine Subject Info (Generates new prompt file)')}
                                         >
                                             {isAnalyzingEntity ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />}
                                         </button>
                                    </div>
                                )}
                            </div>
                            
                            {/* Right: Info */}
                            <div className="w-1/2 flex flex-col h-full bg-[#1e1e1e]">
                                <div className="p-6 border-b border-white/10 flex justify-between items-start">
                                    <div className="flex-1 mr-4">
                                        <input 
                                            value={viewingEntity.name || ''}
                                            onChange={(e) => {
                                                const val = e.target.value;
                                                setViewingEntity(prev => ({ ...prev, name: val }));
                                            }}
                                            onBlur={(e) => handleFieldUpdate('name', e.target.value)}
                                            className="text-3xl font-bold font-serif mb-1 bg-transparent border-b border-transparent hover:border-white/10 focus:border-primary outline-none w-full transition-colors truncate"
                                            placeholder="Entity Name"
                                        />
                                        <input 
                                            value={viewingEntity.name_en || ''} 
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, name_en: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('name_en', e.target.value)}
                                            className="text-lg text-muted-foreground font-mono bg-transparent border-b border-transparent hover:border-white/10 focus:border-primary outline-none w-full transition-colors"
                                            placeholder="English Name"
                                        />
                                    </div>
                                    <button 
                                        onClick={() => setViewingEntity(null)}
                                        className="p-2 hover:bg-white/10 rounded-full text-muted-foreground hover:text-white transition-colors"
                                    >
                                        <X size={24} />
                                    </button>
                                </div>
                                
                                <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                                    {/* Role & Archetype Tags */}
                                    <div className="flex flex-wrap gap-2">
                                        {['role', 'archetype', 'gender'].map(field => (
                                            <input
                                                key={field}
                                                value={viewingEntity[field] || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, [field]: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate(field, e.target.value)}
                                                placeholder={field}
                                                className="px-3 py-1 bg-white/5 text-xs font-bold uppercase tracking-wider rounded-full border border-transparent focus:border-primary outline-none text-center min-w-[60px]"
                                            />
                                        ))}
                                    </div>

                                    {/* Description */}
                                    <div className="space-y-2">
                                        <h4 className="text-xs font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <FileText size={12} /> Description
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.description || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, description: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('description', e.target.value)}
                                            className="w-full text-sm leading-relaxed text-white/80 bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none transition-colors"
                                            placeholder="Enter description..."
                                        />
                                    </div>

                                    {/* Environment Details */}
                                    {viewingEntity.type === 'environment' && (
                                        <div className="space-y-4 p-4 bg-white/5 rounded-lg border border-white/5">
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Atmosphere</h4>
                                                 <input 
                                                    value={viewingEntity.atmosphere || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, atmosphere: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('atmosphere', e.target.value)}
                                                    className="w-full text-sm bg-transparent border-b border-white/10 hover:border-white/30 focus:border-primary p-2 outline-none transition-colors"
                                                    placeholder="Atmosphere (e.g. Dark, Cozy)"
                                                />
                                            </div>
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Visual Params</h4>
                                                <textarea 
                                                    value={viewingEntity.visual_params || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, visual_params: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('visual_params', e.target.value)}
                                                    className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none"
                                                    placeholder="Visual parameters..."
                                                />
                                            </div>
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Narrative Description</h4>
                                                <textarea 
                                                    value={viewingEntity.narrative_description || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, narrative_description: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('narrative_description', e.target.value)}
                                                    className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none"
                                                    placeholder="Detailed narrative (Description field)..."
                                                />
                                            </div>
                                        </div>
                                    )}

                                    {/* Appearance Details */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Appearance</h4>
                                            <textarea 
                                                value={viewingEntity.appearance_cn || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, appearance_cn: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate('appearance_cn', e.target.value)}
                                                className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-20 resize-none"
                                                placeholder="Appearance details..."
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Clothing</h4>
                                            <textarea 
                                                value={viewingEntity.clothing || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, clothing: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate('clothing', e.target.value)}
                                                className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-20 resize-none"
                                                placeholder="Clothing details..."
                                            />
                                        </div>
                                    </div>
                                    
                                    {/* Technical / Prompt */}
                                    <div className="space-y-2">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <Wand2 size={10} /> Generation Prompt
                                        </h4>
                                        <textarea
                                            value={viewingEntity.generation_prompt_en || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, generation_prompt_en: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('generation_prompt_en', e.target.value)}
                                            className="w-full p-4 bg-black/20 rounded-lg border border-white/5 text-xs font-mono text-white/60 focus:text-white/90 focus:border-primary outline-none min-h-[100px] resize-y"
                                            placeholder="Enter generation prompt..."
                                        />
                                    </div>

                                    {/* Action Characteristics */}
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <Clapperboard size={10} /> Action Characteristics
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.action_characteristics || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, action_characteristics: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('action_characteristics', e.target.value)}
                                            className="w-full text-sm p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 focus:border-primary outline-none resize-y min-h-[60px]"
                                            placeholder="Action characteristics..."
                                        />
                                    </div>

                                    {/* Anchor Description */}
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <LinkIcon size={10} /> Anchor Description
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.anchor_description || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, anchor_description: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('anchor_description', e.target.value)}
                                            className="w-full text-sm p-3 bg-white/5 rounded-lg border border-white/5 font-mono text-xs hover:border-white/10 focus:border-primary outline-none resize-y min-h-[60px]"
                                            placeholder="Anchor description..."
                                        />
                                    </div>

                                    {/* Dependency Strategy */}
                                    {viewingEntity.dependency_strategy && (viewingEntity.dependency_strategy.type || viewingEntity.dependency_strategy.logic) && (
                                        <div className="space-y-1 pt-2 border-t border-white/5">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                                <Settings2 size={10} /> Dependency Strategy
                                            </h4>
                                            <div className="bg-white/5 rounded-lg border border-white/5 p-3 text-xs space-y-1">
                                                {viewingEntity.dependency_strategy.type && (
                                                    <div className="flex gap-2">
                                                        <span className="text-muted-foreground">Type:</span>
                                                        <span className="font-bold text-primary">{viewingEntity.dependency_strategy.type}</span>
                                                    </div>
                                                )}
                                                {viewingEntity.dependency_strategy.logic && (
                                                    <div className="flex gap-2 flex-col sm:flex-row sm:items-baseline">
                                                        <span className="text-muted-foreground whitespace-nowrap">Logic:</span>
                                                        <span className="text-white/80 italic">{viewingEntity.dependency_strategy.logic}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {/* Visual Dependencies (Editable) */}
                                    <div className="space-y-2 pt-2 border-t border-white/5">
                                         <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Visual Dependencies</h4>
                                         <p className="text-[10px] text-white/40 mb-1">Add entity names to use their images as reference when generating this entity.</p>
                                         <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                                             <div className="flex flex-wrap gap-2 mb-2">
                                                 {(Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : []).map((dep, i) => (
                                                     <div key={i} className="px-2 py-1 bg-primary/20 text-primary border border-primary/20 rounded text-xs flex items-center gap-2 group">
                                                         <span className="font-bold">{typeof dep === 'string' ? dep : JSON.stringify(dep)}</span>
                                                         <button 
                                                            onClick={() => {
                                                                 const current = Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : [];
                                                                 const newDeps = current.filter(d => d !== dep);
                                                                 handleFieldUpdate('visual_dependencies', newDeps);
                                                            }} 
                                                            className="hover:text-white opacity-50 group-hover:opacity-100"
                                                        >
                                                            <X size={10}/>
                                                        </button>
                                                     </div>
                                                 ))}
                                             </div>
                                             
                                             <div className="relative flex items-center gap-2">
                                                 <input 
                                                     type="text" 
                                                     placeholder="Type Entity Name & Enter..." 
                                                     className="w-full bg-transparent text-xs outline-none text-white/90 placeholder:text-white/20"
                                                     id="dep-input"
                                                     onKeyDown={(e) => {
                                                         if (e.key === 'Enter') {
                                                             const val = e.currentTarget.value.trim();
                                                             if(val) {
                                                                const current = Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : [];
                                                                if(!current.includes(val)) {
                                                                     handleFieldUpdate('visual_dependencies', [...current, val]);
                                                                }
                                                                e.currentTarget.value = '';
                                                             }
                                                         }
                                                     }}
                                                 />
                                                 <Plus className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-white" onClick={() => {
                                                     const input = document.getElementById('dep-input');
                                                     if (!input) return;
                                                     const val = input.value.trim();
                                                     if (val) {
                                                         const current = Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : [];
                                                         if(!current.includes(val)) {
                                                             handleFieldUpdate('visual_dependencies', [...current, val]);
                                                         }
                                                         input.value = '';
                                                     }
                                                 }}/>
                                             </div>
                                         </div>
                                    </div>
                                    {/* Create Mode Actions */}
                                    {viewingEntity.id === 'new' && (
                                        <div className="mt-8 pt-4 border-t border-white/10 flex justify-end gap-3 sticky bottom-0 bg-[#1e1e1e] pb-2 z-10">
                                            <button 
                                                onClick={() => setViewingEntity(null)}
                                                className="px-4 py-2 rounded-lg font-bold text-xs text-muted-foreground hover:bg-white/10 transition-colors uppercase"
                                            >
                                                {t('取消', 'Cancel')}
                                            </button>
                                            <button 
                                                onClick={handleCommitCreate}
                                                className="px-6 py-2 rounded-lg font-bold text-xs bg-primary text-black hover:brightness-110 flex items-center gap-2 uppercase tracking-wide shadow-lg shadow-primary/20 transition-all active:scale-95"
                                            >
                                                <Plus size={14} strokeWidth={3} /> {t('创建主体', 'Create Subject')}
                                            </button>
                                        </div>
                                    )}

                                    {/* Attributes Display - Show ALL fields except the ones already shown above */
                                    (() => {
                                        const hiddenFields = ['id', 'project_id', 'image_url', 'created_at', 'updated_at', 'name', 'name_en', 'description', 
                                            'author_id', 'role', 'archetype', 'gender', 'appearance_cn', 'clothing', 'generation_prompt_en', 'visual_dependencies', 'type', 'project', 'dependency_strategy', 'action_characteristics', 'anchor_description', 'custom_attributes'];
                                        
                                        // Flatten custom_attributes into the view if they exist
                                        let mergedSource = { ...viewingEntity };
                                        if (viewingEntity.custom_attributes && typeof viewingEntity.custom_attributes === 'object') {
                                            mergedSource = { ...viewingEntity.custom_attributes, ...mergedSource };
                                        }

                                        // Merge known extra fields with potentially new ones, excluding standard
                                        const extraFields = Object.entries(mergedSource).filter(([key, val]) => 
                                            !hiddenFields.includes(key) && 
                                            val !== null && 
                                            val !== undefined
                                        );

                                        return (
                                            <div className="space-y-2 pt-4 border-t border-white/5">
                                                <div className="flex justify-between items-center">
                                                    <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Other Attributes</h4>
                                                    <button 
                                                        onClick={async () => {
                                                            const key = await promptUiMessage("Enter new attribute name:", {
                                                                title: 'Add Attribute',
                                                                confirmText: 'Add',
                                                                cancelText: 'Cancel',
                                                                placeholder: 'attribute_key',
                                                            });
                                                            if (key && !viewingEntity[key] && !hiddenFields.includes(key)) {
                                                                setViewingEntity(prev => ({...prev, [key]: "New Value"}));
                                                                // Auto save? Maybe wait for value edit.
                                                            }
                                                        }}
                                                        className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-white"
                                                    >
                                                        + Add
                                                    </button>
                                                </div>
                                                <div className="grid grid-cols-1 gap-2">
                                                    {extraFields.map(([key, value]) => (
                                                        <div key={key} className="p-3 bg-white/5 rounded-lg text-xs space-y-1 group relative">
                                                            <div className="flex justify-between">
                                                                <span className="opacity-50 font-mono uppercase text-[10px] break-all">{key.replace(/_/g, ' ')}</span>
                                                                <button 
                                                                    onClick={async () => {
                                                                        if(!await confirmUiMessage(`Delete attribute ${key}?`)) return;
                                                                        const updated = { ...viewingEntity };
                                                                        delete updated[key];
                                                                        setViewingEntity(updated);
                                                                        setEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                        setAllEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                        // For API, we might need to send null or special flag if backend handles it, 
                                                                        // but typically PUT replaces. If PATCH, we might need to set to null.
                                                                        // Assuming partial update, set to null to delete? Or backend ignores missing?
                                                                        // If backend is SQLModel/Pydantic with extra=ignore, it might persist.
                                                                        // Let's assume we send null to clear.
                                                                        updateEntity(updated.id, { [key]: null }); 
                                                                    }}
                                                                    className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-400 p-1"
                                                                >
                                                                    <Trash2 size={12} />
                                                                </button>
                                                            </div>
                                                            <textarea
                                                                value={typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                                                onChange={(e) => {
                                                                    setViewingEntity(prev => ({ ...prev, [key]: e.target.value }));
                                                                }}
                                                                onBlur={(e) => {
                                                                    let val = e.target.value;
                                                                    // Try to parse JSON if it looks like object
                                                                    if (val.trim().startsWith('{') || val.trim().startsWith('[')) {
                                                                        try { val = JSON.parse(val); } catch(err) {} 
                                                                    }
                                                                    const updated = { ...viewingEntity, [key]: val };
                                                                    setEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                    setAllEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                    updateEntity(updated.id, { [key]: val });
                                                                }}
                                                                className="w-full bg-transparent border-none focus:bg-black/20 focus:ring-1 focus:ring-primary rounded p-1 outline-none font-mono resize-y min-h-[40px]" 
                                                            />
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })()}

                                </div>
                                
                                <div className="p-4 border-t border-white/10 bg-black/20 flex justify-end gap-3">
                                    <button 
                                        onClick={(e) => handleDeleteEntity(e, viewingEntity)}
                                        className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-md text-sm font-bold transition-colors flex items-center gap-2"
                                    >
                                        <Trash2 size={16} /> Delete
                                    </button>
                                    <button 
                                        onClick={() => { setViewingEntity(null); handleOpenImageModal(viewingEntity, 'generate'); }}
                                        className="px-4 py-2 bg-primary hover:bg-primary/90 text-black rounded-md text-sm font-bold transition-colors flex items-center gap-2"
                                    >
                                        <Wand2 size={16} /> Generate Image
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>

            {/* Image Selection Modal */}
            <AnimatePresence>
                {showImageModal && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-2xl h-[650px] flex flex-col shadow-2xl overflow-hidden"
                        >
                            <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/20">
                                <h3 className="font-bold text-lg">Select Image for {selectedEntity?.name}</h3>
                                <button onClick={() => setShowImageModal(false)} className="text-white/50 hover:text-white">
                                    <X size={20} />
                                </button>
                            </div>

                            <div className="flex border-b border-white/10">
                                {['library', 'upload', 'generate', 'advanced'].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setImageModalTab(tab)}
                                        className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${imageModalTab === tab ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'}`}
                                    >
                                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                                    </button>
                                ))}
                            </div>

                            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                                {imageModalTab === 'library' && (
                                    <div className="grid grid-cols-4 gap-4">
                                        {assets.map(asset => (
                                            <div 
                                                key={asset.id} 
                                                onClick={() => handleSelectAsset(asset)}
                                                className="aspect-square bg-black/40 rounded-lg overflow-hidden border border-white/5 hover:border-primary/50 cursor-pointer group relative"
                                            >
                                                <img src={asset.url} alt="asset" className="w-full h-full object-cover" />
                                                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                            </div>
                                        ))}
                                        {assets.length === 0 && (
                                            <div className="col-span-4 py-12 text-center text-muted-foreground">
                                                {t('素材库中未找到图片', 'No images found in library')}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {imageModalTab === 'upload' && (
                                    <div className="flex flex-col items-center justify-center h-full space-y-4">
                                        <div className="p-8 border-2 border-dashed border-white/10 rounded-xl bg-black/20 hover:border-primary/50 hover:bg-primary/5 transition-all w-full max-w-sm flex flex-col items-center justify-center cursor-pointer relative">
                                            <input 
                                                type="file" 
                                                accept="image/*" 
                                                onChange={handleUpload}
                                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                                disabled={uploading} 
                                            />
                                            {uploading ? (
                                                <RefreshCw className="animate-spin text-primary mb-2" size={32} />
                                            ) : (
                                                <Upload className="text-muted-foreground mb-2" size={32} />
                                            )}
                                            <span className="text-sm font-medium text-muted-foreground">
                                                {uploading ? t('上传中...', 'Uploading...') : t('点击或拖拽图片到此处', 'Click or drop image here')}
                                            </span>
                                        </div>
                                        
                                        <div className="w-full max-w-sm mt-8">
                                             <div className="text-xs text-muted-foreground mb-2 uppercase font-bold tracking-wider">{t('或通过 URL 导入', 'Or import from URL')}</div>
                                             <div className="flex gap-2">
                                                <input 
                                                    type="text" 
                                                    placeholder={t('请输入图片链接（https://...）', 'Enter image URL (https://...)')} 
                                                    className="flex-1 bg-black/40 border border-white/10 rounded-md px-3 py-2 text-sm focus:border-primary/50 outline-none"
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') updateEntityImage(e.target.value);
                                                    }}
                                                />
                                                <button className="p-2 bg-white/10 hover:bg-white/20 rounded-md">
                                                    <LinkIcon size={18} />
                                                </button>
                                             </div>
                                        </div>
                                    </div>
                                )}

                                {imageModalTab === 'advanced' && (
                                    <div className="flex flex-col h-full">
                                        <div className="mb-4">
                                            <h4 className="text-xs font-bold uppercase text-muted-foreground mb-2">Advanced Refinement</h4>
                                            <p className="text-[10px] text-white/50 mb-4">
                                                Use AI to refine or modify the image with step-by-step instructions.
                                            </p>
                                        </div>
                                        <div className="flex-1">
                                            <RefineControl 
                                                originalText={selectedEntity?.generation_prompt_en || ""}
                                                onUpdate={(txt) => setPrompt(txt)}
                                                currentImage={selectedEntity?.image_url}
                                                onImageUpdate={updateEntityImage}
                                                projectId={projectId}
                                                featureInjector={(text) => {
                                                    const epInfo = currentEpisode?.episode_info || {};
                                                    const processed = processPrompt(text, epInfo, allEntities);
                                                    return { text: processed, modified: processed !== text };
                                                }}
                                                onPickMedia={(cb) => openMediaPicker(cb, { entityId: selectedEntity?.id })}
                                                type="image"
                                            />
                                        </div>
                                    </div>
                                )}

                                {imageModalTab === 'generate' && (
                                    <div className="flex flex-col h-full">
                                        <textarea
                                            value={prompt}
                                            onChange={(e) => setPrompt(e.target.value)}
                                            placeholder="Describe the image you want to generate. Use [Global Style] for episode style. Prefer CHAR:[@Name] (or [@Name]) to reference subjects."
                                            className="w-full h-32 bg-black/40 border border-white/10 rounded-lg p-4 text-sm focus:border-primary/50 outline-none resize-none mb-4"
                                        />
                                        
                                        {/* Auto-detected Visual Dependencies */}
                                        {selectedEntity?.visual_dependencies && selectedEntity.visual_dependencies.length > 0 && (
                                            <div className="mb-4">
                                                <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">Visual Dependencies (Auto-Used)</label>
                                                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                                                    {(Array.isArray(selectedEntity.visual_dependencies) ? selectedEntity.visual_dependencies : []).map((dep, idx) => {
                                                        const startDep = String(dep).trim();
                                                        const startDepLower = startDep.toLowerCase();
                                                        
                                                        const depEntity = allEntities.find(e => {
                                                            if (!e) return false;
                                                            if (String(e.id) === startDep) return true;
                                                            if (e.name && e.name.trim().toLowerCase() === startDepLower) return true;
                                                            if (e.name_en && e.name_en.trim().toLowerCase() === startDepLower) return true;
                                                            return false;
                                                        });
                                                        
                                                        return (
                                                            <div key={idx} className="flex-shrink-0 w-24 bg-black/40 border border-white/10 rounded-lg p-1.5 flex flex-col gap-1 relative group">
                                                                <div className="aspect-square bg-black rounded overflow-hidden">
                                                                     {depEntity?.image_url ? (
                                                                         <img src={getFullUrl(depEntity.image_url)} alt={dep} className="w-full h-full object-cover" />
                                                                     ) : (
                                                                         <div className="w-full h-full flex items-center justify-center bg-white/5">
                                                                             <Users size={16} className="text-white/20"/>
                                                                         </div>
                                                                     )}
                                                                </div>
                                                                <div className="text-[10px] truncate font-bold text-white px-0.5" title={dep}>
                                                                    {depEntity ? depEntity.name : dep}
                                                                </div>
                                                                {!depEntity && <div className="text-[8px] text-red-400 px-0.5">Not Found</div>}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                        
                                        {/* Configuration Row */}
                                        <div className="flex items-center gap-4 mb-4">
                                            {/* Provider Select */}
                                            <div className="flex-1">
                                                <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 flex items-center gap-2">
                                                    Provider
                                                    <span className={`text-[9px] px-1.5 py-0.5 rounded border font-mono normal-case ${sourceBadgeClass(activeSourceImage)}`}>
                                                        Source: {sourceBadgeText(activeSourceImage)}
                                                    </span>
                                                </label>
                                                <select 
                                                    value={provider} 
                                                    onChange={e => setProvider(e.target.value)}
                                                    className="w-full bg-black/40 border border-white/10 rounded-md px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                >
                                                    <option value="">Default (System)</option>
                                                    {availableProviders.map(p => (
                                                        <option key={p.provider} value={p.provider}>
                                                           {p.provider ? (p.provider.charAt(0).toUpperCase() + p.provider.slice(1)) : 'Unknown'}
                                                        </option>
                                                    ))}
                                                </select>
                                            </div>
                                            
                                            {/* Reference Image Select */}
                                            <div className="flex-[2] relative">
                                                 <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">Ref Image (Optional)</label>
                                                 
                                                 {!refImage ? (
                                                     <div className="flex gap-2 items-center">
                                                          <div className="flex-1 flex gap-2">
                                                              {/* Selection Buttons */}
                                                              <button 
                                                                onClick={() => setRefSelectionMode(refSelectionMode === 'assets' ? null : 'assets')}
                                                                className={`p-2 rounded border border-white/10 text-xs font-bold hover:bg-white/10 flex items-center gap-1 ${refSelectionMode === 'assets' ? 'bg-primary/20 text-primary border-primary/50' : 'bg-black/40 text-muted-foreground'}`}
                                                              >
                                                                  <FolderOpen size={14} /> Assets
                                                              </button>
                                                              <div className="relative overflow-hidden w-24">
                                                                  <button className="w-full p-2 bg-black/40 border border-white/10 rounded text-xs font-bold hover:bg-white/10 text-muted-foreground flex items-center gap-1 justify-center">
                                                                    <Upload size={14} /> Upload
                                                                  </button>
                                                                  <input 
                                                                    type="file" 
                                                                    className="absolute inset-0 opacity-0 cursor-pointer" 
                                                                    accept="image/*"
                                                                    onChange={handleRefUpload}
                                                                  />
                                                              </div>
                                                          </div>
                                                          
                                                          {/* URL Input (Fallback) */}
                                                          <div className="w-1/3 relative">
                                                              <input 
                                                                  type="text" 
                                                                  placeholder="URL..." 
                                                                  onBlur={(e) => {
                                                                      if (e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                  }}
                                                                  onKeyDown={(e) => {
                                                                        if (e.key === 'Enter' && e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                  }}
                                                                  className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-white focus:border-primary/50 outline-none"
                                                              />
                                                          </div>
                                                     </div>
                                                 ) : (
                                                     // Selected Preview State
                                                     <div className="flex gap-3 bg-black/40 border border-white/10 rounded-lg p-2 items-center relative group">
                                                         <div className="w-10 h-10 bg-black rounded overflow-hidden flex-shrink-0 border border-white/5">
                                                             <img src={getFullUrl(refImage.url)} alt="ref" className="w-full h-full object-cover" />
                                                         </div>
                                                         <div className="flex-1 overflow-hidden">
                                                             <div className="text-xs font-bold text-white truncate">{refImage.name || 'Reference Image'}</div>
                                                             <div className="text-[10px] text-muted-foreground flex gap-2">
                                                                 <span>{refImage.dimensions || 'Unknown Size'}</span>
                                                                 {refImage.type && <span className="uppercase">{refImage.type}</span>}
                                                             </div>
                                                         </div>
                                                         <button 
                                                             onClick={() => setRefImage(null)}
                                                             className="p-1 hover:bg-white/10 rounded-md text-white/50 hover:text-white"
                                                         >
                                                             <X size={14} />
                                                         </button>
                                                     </div>
                                                 )}

                                                 {/* Asset Picker Popover */}
                                                 {refSelectionMode === 'assets' && !refImage && (
                                                     <div className="absolute top-full left-0 right-0 mt-2 z-10 bg-[#09090b] border border-white/10 rounded-xl shadow-2xl h-64 overflow-hidden flex flex-col">
                                                         <div className="p-2 border-b border-white/10 flex justify-between items-center bg-black/20">
                                                             <span className="text-xs font-bold text-muted-foreground ml-2">Select from Assets</span>
                                                             <button onClick={() => setRefSelectionMode(null)}><X size={14} className="text-white/50 hover:text-white"/></button>
                                                         </div>
                                                         <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
                                                             <div className="grid grid-cols-4 gap-2">
                                                                 {assets.map(asset => (
                                                                     <div 
                                                                         key={asset.id} 
                                                                         onClick={() => {
                                                                             setRefImage(asset);
                                                                             setRefSelectionMode(null);
                                                                         }}
                                                                         className="aspect-square bg-black/40 rounded border border-white/5 hover:border-primary/50 cursor-pointer overflow-hidden relative group"
                                                                     >
                                                                         <img src={getFullUrl(asset.url)} alt={asset.name} className="w-full h-full object-cover" />
                                                                         <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                                                     </div>
                                                                 ))}
                                                                 {assets.length === 0 && (
                                                                     <div className="col-span-4 py-8 text-center text-xs text-muted-foreground">{t('未找到素材', 'No assets found')}</div>
                                                                 )}
                                                             </div>
                                                         </div>
                                                     </div>
                                                 )}
                                            </div>
                                        </div>

                                        <div className="flex justify-end">
                                            <button 
                                                onClick={handleGenerate}
                                                disabled={generating || !prompt}
                                                className="flex items-center space-x-2 bg-primary text-black px-6 py-2 rounded-lg font-bold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                            >
                                                {generating ? (
                                                    <RefreshCw className="animate-spin" size={18} />
                                                ) : (
                                                    <Wand2 size={18} />
                                                )}
                                                <span>{generating ? 'Generating...' : 'Generate Image'}</span>
                                            </button>
                                        </div>
                                        
                                        <div className="mt-6">
                                            <h4 className="text-xs font-bold uppercase text-muted-foreground mb-3">Prompt Variables</h4>
                                            <ul className="text-xs text-white/60 space-y-2 list-disc pl-4">
                                                <li><code className="bg-white/10 px-1 rounded text-primary">[Global Style]</code>: Injects current episode style.</li>
                                                <li><code className="bg-white/10 px-1 rounded text-primary">CHAR:[@Name]</code> / <code className="bg-white/10 px-1 rounded text-primary">[@Name]</code>: Injects matched Entity anchor description.</li>
                                            </ul>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
            
            <MediaPickerModal 
                isOpen={pickerConfig.isOpen}
                onClose={() => setPickerConfig(prev => ({ ...prev, isOpen: false }))}
                onSelect={(url, type) => {
                    if (pickerConfig.callback) pickerConfig.callback(url, type);
                    setPickerConfig(prev => ({ ...prev, isOpen: false }));
                }}
                projectId={projectId}
                context={pickerConfig.context}
                entities={allEntities}
                episodeId={currentEpisode?.id}
                uiLang={uiLang}
            />
        </div>
    );
};

const ShotsView = ({ activeEpisode, projectId, project, onLog, editingShot, setEditingShot, uiLang = 'zh' }) => {
    const { generationConfig, saveToolConfig, savedToolConfigs, llmConfig } = useStore();
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [scenes, setScenes] = useState([]);
    const [selectedSceneId, setSelectedSceneId] = useState('all');
    const [sceneCodeFilter, setSceneCodeFilter] = useState('');
    const [shotIdFilter, setShotIdFilter] = useState('');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [shots, setShots] = useState([]);
    const [isImportOpen, setIsImportOpen] = useState(false);
    // const [editingShot, setEditingShot] = useState(null); // Lifted state
    const [entities, setEntities] = useState([]);
    
    // NEW: Abort Controller Ref for retries
    const abortGenerationRef = useRef(false);

    // Local Notification for ShotsView (Edit Dialog)
    const [notification, setNotification] = useState(null);
    const showNotification = (message, type = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    };

    useEffect(() => {
        if (projectId) {
            fetchEntities(projectId).then(setEntities).catch(console.error);
        }
    }, [projectId]);


    // Note: Provider selection functionality removed (defaults to Backend Active Settings)
    // Code for local state imageProvider/videoProvider removed.


    // AI Prompt Preview Modal State
    const [shotPromptModal, setShotPromptModal] = useState({ open: false, sceneId: null, data: null, loading: false });
    const [shotReviewModal, setShotReviewModal] = useState({ open: false, sceneId: null, data: null, loading: false });

    // Media Handling
    const [viewMedia, setViewMedia] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });
    const [generatingStateByShot, setGeneratingStateByShot] = useState({});
    const [isBatchGenerating, setIsBatchGenerating] = useState(false);
    const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, status: '' }); // Progress tracking
    const [activeSources, setActiveSources] = useState({ Image: 'unset', Video: 'unset' });

    const setShotGeneratingState = useCallback((shotId, key, value) => {
        if (!shotId) return;
        setGeneratingStateByShot(prev => {
            const prevState = prev[shotId] || { start: false, end: false, video: false };
            const nextState = { ...prevState, [key]: value };
            if (!nextState.start && !nextState.end && !nextState.video) {
                const { [shotId]: _, ...rest } = prev;
                return rest;
            }
            return { ...prev, [shotId]: nextState };
        });
    }, []);

    const currentGeneratingState = editingShot?.id
        ? (generatingStateByShot[editingShot.id] || { start: false, end: false, video: false })
        : { start: false, end: false, video: false };

    const [assetDetailModal, setAssetDetailModal] = useState({ open: false, type: 'start', keyframeIndex: -1 });
    const [detailTranslateLoading, setDetailTranslateLoading] = useState({});
    const [detailOptimizeLoading, setDetailOptimizeLoading] = useState({});

    const openAssetDetailModal = (type, keyframeIndex = -1) => {
        setAssetDetailModal({ open: true, type, keyframeIndex });
    };

    const closeAssetDetailModal = () => {
        setAssetDetailModal({ open: false, type: 'start', keyframeIndex: -1 });
    };

    const overwriteShotField = useCallback((field, value, extra = {}) => {
        const nextValue = String(value ?? '');
        setEditingShot(prev => ({ ...(prev || {}), [field]: nextValue, ...extra }));
    }, []);

    const overwriteTechField = useCallback((key, value) => {
        const nextValue = String(value ?? '');
        setEditingShot(prev => {
            const current = prev || {};
            let techObj = {};
            try { techObj = JSON.parse(current.technical_notes || '{}'); } catch (e) {}
            techObj[key] = nextValue;
            return { ...current, technical_notes: JSON.stringify(techObj) };
        });
    }, []);

    const overwriteKeyframeCnMap = useCallback((timeKey, value) => {
        if (!timeKey) return;
        const nextValue = String(value ?? '');
        setEditingShot(prev => {
            const current = prev || {};
            let techObj = {};
            try { techObj = JSON.parse(current.technical_notes || '{}'); } catch (e) {}
            const nextMap = { ...(techObj.keyframe_prompt_cn_map || {}) };
            nextMap[timeKey] = nextValue;
            techObj.keyframe_prompt_cn_map = nextMap;
            return { ...current, technical_notes: JSON.stringify(techObj) };
        });
    }, []);

    const extractTranslatedText = (res) => {
        if (!res) return '';
        if (typeof res?.translated_text === 'string' && res.translated_text.trim()) {
            return res.translated_text.trim();
        }

        const nestedList = res?.result?.trans_result;
        if (Array.isArray(nestedList) && nestedList.length > 0) {
            const joined = nestedList
                .map(item => (typeof item?.dst === 'string' ? item.dst.trim() : ''))
                .filter(Boolean)
                .join('\n');
            if (joined) return joined;
        }

        const flatList = res?.trans_result;
        if (Array.isArray(flatList) && flatList.length > 0) {
            const joined = flatList
                .map(item => (typeof item?.dst === 'string' ? item.dst.trim() : ''))
                .filter(Boolean)
                .join('\n');
            if (joined) return joined;
        }

        if (typeof res?.data === 'string' && res.data.trim()) {
            return res.data.trim();
        }

        return '';
    };

    const runDetailTranslate = async ({ text, from, to, onResult, loadingKey }) => {
        const raw = String(text || '').trim();
        if (!raw) {
            showNotification(t('没有可翻译内容', 'No text to translate'), 'warning');
            return;
        }
        setDetailTranslateLoading(prev => ({ ...prev, [loadingKey]: true }));
        try {
            const res = await translateText(raw, from, to);
            const translated = extractTranslatedText(res);
            if (!translated) throw new Error('No translation returned');
            onResult?.(translated);
            showNotification(t('翻译完成', 'Translation completed'), 'success');
        } catch (e) {
            const msg = e?.response?.data?.detail || e?.message || 'Translate failed';
            onLog?.(`Detail translate failed: ${msg}`, 'error');
            showNotification(t('翻译失败', 'Translation failed'), 'error');
        } finally {
            setDetailTranslateLoading(prev => ({ ...prev, [loadingKey]: false }));
        }
    };

    const runBilingualOptimize = async ({
        enText,
        cnText,
        optimizeType = 'image',
        loadingKey,
        onEnUpdate,
        onCnUpdate,
    }) => {
        const baseEn = String(enText || '').trim();
        const baseCn = String(cnText || '').trim();
        if (!baseEn && !baseCn) {
            showNotification(t('没有可优化内容', 'No prompt to optimize'), 'warning');
            return;
        }

        setDetailOptimizeLoading(prev => ({ ...prev, [loadingKey]: true }));
        try {
            let sourceEn = baseEn;
            if (!sourceEn && baseCn) {
                const trans = await translateText(baseCn, 'zh', 'en');
                sourceEn = extractTranslatedText(trans);
            }
            if (!sourceEn) throw new Error('No EN source for optimization');

            const refined = await refinePrompt(
                sourceEn,
                'Polish this prompt for better visual quality while preserving original intent and entities.',
                optimizeType
            );
            const nextEn = String(refined?.refined_prompt || refined?.optimized_prompt || sourceEn).trim();
            if (!nextEn) throw new Error('No optimized prompt returned');
            onEnUpdate?.(nextEn);

            const zh = await translateText(nextEn, 'en', 'zh');
            const nextCn = extractTranslatedText(zh);
            if (nextCn) onCnUpdate?.(nextCn);

            showNotification(t('中英提示词已同步优化', 'CN/EN prompts optimized'), 'success');
        } catch (e) {
            const msg = e?.response?.data?.detail || e?.message || 'Optimize failed';
            onLog?.(`Bilingual optimize failed: ${msg}`, 'error');
            showNotification(t('提示词优化失败', 'Prompt optimization failed'), 'error');
        } finally {
            setDetailOptimizeLoading(prev => ({ ...prev, [loadingKey]: false }));
        }
    };

    const shotFilterStorageKey = useMemo(() => {
        if (!activeEpisode?.id) return '';
        return `aistory.shotFilters.${activeEpisode.id}`;
    }, [activeEpisode?.id]);

    useEffect(() => {
        if (!shotFilterStorageKey) return;
        try {
            const raw = localStorage.getItem(shotFilterStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                setSelectedSceneId(String(parsed.selectedSceneId || 'all'));
                setSceneCodeFilter(String(parsed.sceneCodeFilter || ''));
                setShotIdFilter(String(parsed.shotIdFilter || ''));
            }
        } catch (e) {
            console.warn('Failed to restore shot filters', e);
        }
    }, [shotFilterStorageKey]);

    useEffect(() => {
        if (!shotFilterStorageKey) return;
        try {
            localStorage.setItem(shotFilterStorageKey, JSON.stringify({
                selectedSceneId,
                sceneCodeFilter,
                shotIdFilter,
            }));
        } catch (e) {
            console.warn('Failed to persist shot filters', e);
        }
    }, [shotFilterStorageKey, selectedSceneId, sceneCodeFilter, shotIdFilter]);

    // Helper: Construct Global Context String from Episode Info
    const getGlobalContextStr = () => {
        const info = activeEpisode?.episode_info?.e_global_info;
        if (!info) return "";
        const parts = [];
        // Append explicit labels so the model understands the context
        if (info.Global_Style) parts.push(`Style: ${info.Global_Style}`);
        if (info.tone) parts.push(`Tone: ${info.tone}`);
        if (info.lighting) parts.push(`Lighting: ${info.lighting}`);
        
        return parts.length > 0 ? " | " + parts.join(", ") : "";
    };

    const openMediaPicker = (callback, context = {}) => {
        setPickerConfig({ isOpen: true, callback, context });
    };

    const refreshActiveSources = useCallback(async () => {
        try {
            const settings = await getSettings();
            setActiveSources({
                Image: getSettingSourceByCategory(settings, 'Image'),
                Video: getSettingSourceByCategory(settings, 'Video'),
            });
        } catch (e) {
            console.error('Failed to load active setting sources in ShotsView', e);
        }
    }, []);

    useEffect(() => {
        if (editingShot) {
            refreshActiveSources();
        }
    }, [editingShot?.id, refreshActiveSources]);

    useEffect(() => {
        if (!isSettingsOpen) {
            refreshActiveSources();
        }
    }, [isSettingsOpen, refreshActiveSources]);

    const onUpdateShot = async (shotId, changes) => {
        try {
            // Fix 422 Error: Backend requires 'shot_number' and 'description'
            // We must merge with existing shot data to ensure these fields exist
            const currentShot = shots.find(s => s.id === shotId);
            if (!currentShot) return;

            const payload = {
                ...currentShot,
                ...changes
            };
            
            // Explicitly ensure required keys are present if they were somehow missing in object
            // (though spread of currentShot should handle it)
            if (!payload.shot_number) payload.shot_number = "1"; 
            if (!payload.description) payload.description = "";

            await updateShot(shotId, payload);
            setShots(prev => prev.map(s => s.id === shotId ? { ...s, ...changes } : s));

            // Sync editingShot safely
            setEditingShot(prev => {
                if (prev && prev.id === shotId) {
                    return { ...prev, ...changes };
                }
                return prev;
            });
        } catch(e) { 
            console.error("Update Shot Failed", e); 
            onLog?.("Failed to save changes", "error");
        }
    }

    const handleGenerateShots = async (sceneId) => {
        if (sceneId === 'all') {
            onLog?.("Please select a specific scene to generate shots.", "warning");
            return;
        }
        setShotPromptModal({ open: true, sceneId: sceneId, data: null, loading: true });
        try {
            const data = await fetchSceneShotsPrompt(sceneId);
            setShotPromptModal({ open: true, sceneId: sceneId, data: data, loading: false });
        } catch (e) {
             onLog?.(`Failed to fetch prompt preview - ${e.message}`, 'error');
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
        }
    };

    const handleConfirmGenerateShots = async () => {
         const { sceneId, data } = shotPromptModal;
         if (!await confirmUiMessage("This will overwrite existing shots for this scene. Continue?")) return;
         
         setShotPromptModal(prev => ({ ...prev, loading: true }));
         onLog?.(`Generating shots for Scene ${sceneId}...`, 'info');
         try {
             // Now returns { content: [], timestamp }
             const result = await generateSceneShots(sceneId, { 
                 user_prompt: data.user_prompt,
                 system_prompt: data.system_prompt 
             });
             const generatedRows = Array.isArray(result?.content) ? result.content : [];
             const generatedRaw = String(result?.raw_text || '').trim();
             if (generatedRows.length === 0) {
                 if (generatedRaw) {
                     const rawPreview = generatedRaw.replace(/\s+/g, ' ').slice(0, 300);
                     onLog?.(`Generate Shots returned 0 parsed rows. Raw preview: ${rawPreview}`, 'warning');
                     console.warn('[ShotsView] Generate Shots parse-empty with raw_text preview', {
                         sceneId,
                         rawLen: generatedRaw.length,
                         rawPreview,
                     });
                     throw new Error(`Generate Shots returned 0 parsed rows; raw preview: ${rawPreview}`);
                 }
                 throw new Error('Generate Shots returned empty result (no rows and no raw text)');
             }
             onLog?.(`Shot list generated for Scene ${sceneId}. Please Review/Apply.`, 'success');
             
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
             
             // Open Review
             setShotReviewModal({
                 open: true,
                 sceneId: sceneId,
                 data: generatedRows,
                 loading: false
             });

             // Auto-import/apply immediately after generation
             try {
                 onLog?.(`Auto-importing shots for Scene ${sceneId}...`, 'info');
                 await applySceneAIResult(sceneId, { content: generatedRows });
                 onLog?.(`Auto-import finished for Scene ${sceneId}.`, 'success');
             } catch (e) {
                 onLog?.(`Auto-import failed - ${(e?.response?.data?.detail || e?.message)}`, 'error');
             }
             
         } catch (e) {
             console.error(e);
             onLog?.(`Failed to generate shots - ${e.message}`, 'error');
             alert("Failed to generate shots: " + e.message);
             setShotPromptModal(prev => ({ ...prev, loading: false }));
         }
    };

    const handleMediaSelect = (url, type) => {
        if (pickerConfig.callback) {
            pickerConfig.callback(url, type);
        }
        setPickerConfig({ isOpen: false, callback: null });
    };

    useEffect(() => {
        if (activeEpisode?.project_id) {
            // console.log("Fetching Entities for Project:", activeEpisode.project_id);
            fetchEntities(activeEpisode.project_id)
                .then(data => {
                    // console.log("Entities Loaded:", data.length);
                    setEntities(data);
                })
                .catch(console.error);
        } else {
            console.warn("ShotsView: No activeEpisode or project_id to fetch entities.");
        }
    }, [activeEpisode]);

    const refreshShots = useCallback(async () => {
        if (!selectedSceneId || !activeEpisode?.id) return;

        const getSceneCodeFromShot = (shot) => {
            const explicit = String(shot?.scene_code || '').trim();
            if (explicit) return explicit.toUpperCase();
            const shotId = String(shot?.shot_id || '').trim().toUpperCase();
            const m = shotId.match(/^(EP\d{2}_SC\d{2})/);
            return m ? m[1] : '';
        };
        
        try {
            const normalizedSceneCode = String(sceneCodeFilter || '').trim().toUpperCase();
            const normalizedShotId = String(shotIdFilter || '').trim().toUpperCase();

            // Optimized: Fetch all shots for the EPISODE.
            // This satisfies the requirement to select based on Project/Episode, and associate via Scene ID locally.
            // Also fixes issues where unlinked shots or imports were hidden.
            const allShots = await fetchEpisodeShots(activeEpisode.id, {
                scene_code: normalizedSceneCode || undefined,
                shot_id: normalizedShotId || undefined,
            });

            let filtered = selectedSceneId === 'all'
                ? allShots
                : allShots.filter(s => String(s.scene_id) === String(selectedSceneId));

            if (normalizedSceneCode) {
                filtered = filtered.filter((shot) => {
                    const sceneCode = getSceneCodeFromShot(shot);
                    return sceneCode.includes(normalizedSceneCode);
                });
            }

            if (normalizedShotId) {
                filtered = filtered.filter((shot) => String(shot?.shot_id || '').toUpperCase().includes(normalizedShotId));
            }

            setShots(filtered);

                // Legacy Auto-Sync Check (Optional, but kept for script-to-shot workflow convenience)
                if (filtered.length === 0 && (activeEpisode?.scene_content || activeEpisode?.shot_content)) {
                     // Only if we truly have 0 matching shots, maybe try to parses content
                     // Check if we haven't already synced (prevent loops)
                     // Here we just log or optionally call sync. 
                     // We'll keep it simple for now as user asked to remove "sync logic".
                     // But if user relies on auto-generation... 
                     // Let's assume 'remove sync logic' refers to the strict scene_code matching.
                }
        } catch (e) {
            console.error("Failed to refresh shots", e);
        }
    }, [activeEpisode?.id, selectedSceneId, sceneCodeFilter, shotIdFilter]);

    useEffect(() => {
        if(activeEpisode?.id) {
            fetchScenes(activeEpisode.id).then((data) => {
                setScenes(data);
                // If previously 'all' but couldn't load due to empty scenes, this will re-trigger refreshShots via useEffect[selectedSceneId, refreshShots]
                // because refreshShots depends on 'scenes' if selectedSceneId is 'all'
            }).catch(e => console.error(e));
        }
    }, [activeEpisode]);

    useEffect(() => {
        refreshShots();
    }, [refreshShots]);


    const handleDeleteAllShots = async () => {
        if (shots.length === 0) return;
        if (!await confirmUiMessage(`Are you sure you want to delete all ${shots.length} shots displayed here? This cannot be undone.`)) return;

        onLog?.("Deleting all shots...", "process");
        try {
            await Promise.all(shots.map(s => deleteShot(s.id)));
            onLog?.(`Successfully deleted ${shots.length} shots.`, "success");
            setShots([]);
        } catch (e) {
            console.error(e);
            onLog?.("Error deleting shots", "error");
            refreshShots();
        }
    };

    const handleSyncScenes = async (onlyForSceneId = null) => {
        // Support pulling from scene_content OR shot_content
        const contentSources = [];
        if (activeEpisode?.scene_content) contentSources.push(activeEpisode.scene_content);
        if (activeEpisode?.shot_content) contentSources.push(activeEpisode.shot_content);

        if (contentSources.length === 0) {
            onLog?.("No scene/shot content to sync from source text.", "warning");
            return;
        }
        
        onLog?.(onlyForSceneId ? "Syncing Logic (Smart Refresh)..." : "Syncing Scenes & Shots...", "process");
        
        // Merge lines from both sources
        let allLines = [];
        contentSources.forEach(txt => {
            allLines = allLines.concat(txt.split('\n'));
        });
        
        const lines = allLines;
        
        // Cache to avoid duplicates and redundant calls
        const sceneShotsCache = {};
        let countShots = 0;

        // 1. Fetch ALL existing scenes from DB first
        let dbScenes = [];
        try { 
            dbScenes = await fetchScenes(activeEpisode.id); 
            // Update UI with fresh scenes immediately to avoid "Missing Scenes" visual
            if (!onlyForSceneId) setScenes(dbScenes);
        } catch(e) { console.error(e); }
        
        // Map: "1" -> SceneObj, "01" -> SceneObj
        const getSceneKey = (num) => String(num).replace(/^0+/, '').replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
        const sceneMap = {};
        dbScenes.forEach(s => { 
            if(s.scene_no) sceneMap[getSceneKey(s.scene_no)] = s; 
        });

        let defaultSceneId = null; // Track created default scene

        // 2. Iterate text lines looking ONLY for Shots
        for (let line of lines) {
             const trimmed = line.trim();
             if (!trimmed.includes('|')) continue;
             if (trimmed.includes('Shot No') || trimmed.includes('Shot ID') || trimmed.includes('镜头ID') || trimmed.includes('---')) continue;
             
             const cols = trimmed.split('|').map(c => c.trim());
             if (cols.length > 0 && cols[0] === '') cols.shift();
             if (cols.length > 0 && cols[cols.length-1] === '') cols.pop();
             if (cols.length < 2) continue; // Not a valid row
             
             const clean = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
             const shotNumRaw = clean(cols[0]); // e.g. "1-1", "1A-1"
             
             // 3. Determine Target Scene from Shot Number Prefix
             // "1-12" -> Scene "1"
             // "1A-5" -> Scene "1A"
             // "2"    -> Scene "2" (if loose)
             let targetSceneId = null;
             
             // Strategy: Look for "-" separator
             const parts = shotNumRaw.split(/[-_]/);
             const scenePrefix = parts.length > 1 ? parts[0] : null; 
             
             if (scenePrefix) {
                 const key = getSceneKey(scenePrefix);
                 if (sceneMap[key]) {
                     targetSceneId = sceneMap[key].id;
                 }
             }

             // Fallback: If no prefix match, try selectedSceneId (if not 'all')
             if (!targetSceneId && selectedSceneId && selectedSceneId !== 'all') {
                 targetSceneId = parseInt(selectedSceneId);
             }

             // Auto-Create Default Scene if Orphaned
             if (!targetSceneId) {
                 if (defaultSceneId) {
                     targetSceneId = defaultSceneId;
                 } else {
                     // Check existing "Default Scene"
                     const existingDefault = dbScenes.find(s => s.scene_name === "Default Scene" || s.scene_no === "DEFAULT");
                     if (existingDefault) {
                         targetSceneId = existingDefault.id;
                         defaultSceneId = existingDefault.id;
                     } else if (dbScenes.length === 0) {
                         // Only create if NO scenes exist (assuming shot-only import)
                         try {
                              // We need to await inside loop, but it's only once
                              // eslint-disable-next-line no-await-in-loop
                              const newScene = await createScene(activeEpisode.id, {
                                  scene_number: "DEFAULT",
                                  title: "Default Scene",
                                  description: "Auto-generated for imported shots",
                                  location: "Unknown",
                                  time_of_day: "Unknown"
                              });
                              dbScenes.push(newScene);
                              setScenes(prev => [...prev, newScene]);
                              targetSceneId = newScene.id;
                              defaultSceneId = newScene.id;
                         } catch(e) {
                             console.error("Failed to create default scene", e);
                         }
                     }
                 }
             }

             // If still no scene, we verify if the USER wants us to create shots purely based on sequence? 
             // Current strict mode: If we can't link, we skip.
             if (!targetSceneId) continue;
             
             // Smart Filter for partial updates
             if (onlyForSceneId && targetSceneId !== onlyForSceneId) continue;

             // 4. Create/Sync Shot
             const currentSceneId = targetSceneId;
             
             // IDEMPOTENCY CHECK
             if (!sceneShotsCache[currentSceneId]) {
                 try {
                     sceneShotsCache[currentSceneId] = await fetchShots(currentSceneId);
                 } catch(e) { sceneShotsCache[currentSceneId] = []; }
             }
             
             const shotData = {
                 shot_id: shotNumRaw.replace(/\*\*/g, ''),
                 shot_name: clean(cols[1]),
                 start_frame: clean(cols[2]),
                 end_frame: clean(cols[3]),
                 video_content: clean(cols[4]),
                 duration: clean(cols[5]),
                 associated_entities: clean(cols[6])
             };
             
             // Duplication Check
             const existingShots = sceneShotsCache[currentSceneId];
             const alreadyExists = existingShots.find(s => {
                 const sNum = String(s.shot_id || '').replace(/\*\*/g, '').replace(/Shot\s*/i, '').trim();
                 const tNum = String(shotData.shot_id || '').replace('Shot', '').trim();
                 return sNum === tNum;
             });
             
             if (!alreadyExists) {
                try {
                    const newShot = await createShot(currentSceneId, shotData);
                    existingShots.push(newShot); 
                    countShots++;
                } catch(e) { console.error("Sync Shot Error", e); }
             }
        }
        
        if (countShots > 0) {
            onLog?.(`Synced ${countShots} shots to ${Object.keys(sceneShotsCache).length} scenes.`, "success");
        } else if (!onlyForSceneId) {
             onLog?.("No new shots found to sync.", "info");
        }

        // Force Refresh UI
        if (!onlyForSceneId) {
            // Re-fetch all scenes to update lists
            try {
                 const currentScenes = await fetchScenes(activeEpisode.id);
                 setScenes(currentScenes);
            } catch(e) { console.error(e); }

            // Using unified refresh logic
            refreshShots();
        }
    };

    const handleImport = async (text) => {
        if (!selectedSceneId) {
             onLog?.("Please select a scene first.", "error");
             return;
        }
        
        onLog?.("Processing Shot Import...", "process");
        const lines = text.split('\n');
        
        const currentScene = scenes.find(s => s.id == selectedSceneId);
        
        const parsedShots = [];
        let headerFound = false;
        let headerMap = {}; // Map normalized header string to column index

        for (let line of lines) {
             // Skip context header (Project | Episode)
             if (line.includes('Project:') && line.includes('Episode:')) continue;
             
             // Check for possible header row by keywords
             const normLine = line.toLowerCase();
             const isHeader = line.includes('|') && (
                 normLine.includes('shot no') || normLine.includes('shot id') || normLine.includes('镜头id') || normLine.includes('scene id')
             );
             
             // Process Row splitting logic consistently for Header and Data
             if (line.includes('|') && !line.includes('---')) {
                 const cols = line.split('|').map(c => c.trim());
                 if (cols.length > 0 && cols[0] === '') cols.shift();
                 if (cols.length > 0 && cols[cols.length-1] === '') cols.pop();

                 if (isHeader) {
                     headerFound = true;
                     cols.forEach((col, idx) => {
                         // Normalize header key: remove special chars, lowercase
                         const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                         headerMap[key] = idx;
                     });
                     onLog?.("Parsed Headers: " + Object.keys(headerMap).join(", "), "info");
                     continue;
                 }
                 
                 if (headerFound) {
                     const clean = (t) => t ? t.replace(/<br\/?>/gi, '\n') : '';
                     
                     // Helper to get value by possible keys
                     const getVal = (keys, defaultIdx) => {
                         for (const k of keys) {
                             if (headerMap[k] !== undefined && headerMap[k] < cols.length) {
                                 return clean(cols[headerMap[k]]); 
                             }
                         }
                         // Fallback to default index if map logic fails or specific column not found
                         // Only fallback if we don't have a reliable map (e.g. maybe map is empty?)
                         if (Object.keys(headerMap).length === 0 && defaultIdx < cols.length) {
                             return clean(cols[defaultIdx]);
                         }
                         return ''; 
                     };

                     // Determine fallback offset based on column count if map failed (legacy logic)
                     // But if we have map, we rely on it.
                     const useMap = Object.keys(headerMap).length > 0;
                     
                     // Legacy offset logic for fallback
                     let colStart = 2; 
                     let legacySceneCode = '';
                     if (!useMap) {
                        if (cols.length >= 8) {
                            legacySceneCode = clean(cols[2]);
                            colStart = 3;
                        }
                     }
                     
                     let extractedSceneCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                     // Ensure scene_code is populated if import misses it
                     if (!extractedSceneCode && currentScene) {
                         extractedSceneCode = currentScene.scene_no;
                     }

                     const shotData = {
                         shot_id: useMap ? getVal(['shotid', 'shotno', '镜头id', 'id'], 0) : clean(cols[0]),
                         shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                         
                         scene_code: extractedSceneCode,
                         
                         start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                         end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                         video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                         duration: useMap ? getVal(['duration', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                         associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                         shot_logic_cn: (() => {
                             const val = useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)'], 7) : '';
                             return val;
                         })(),
                         keyframes: useMap ? getVal(['keyframes', 'key frames', '关键帧', 'kf'], 8) : '',

                         // Clear unused
                         shot_type: '',
                         lens: '',
                         framing: '',
                         dialogue: '',
                         technical_notes: ''
                     };
                     
                     // Only push valid rows
                     if (shotData.shot_id && String(shotData.shot_id).trim() !== '') {
                        parsedShots.push(shotData);
                     }
                 }
             }
        }

        if (parsedShots.length > 0) {
            let shouldOverwrite = false;
            // Removed redundant currentScene fetch here
            
            // Check if import sceneCode matches selected scene
            if (currentScene && currentScene.scene_no) {
                const importCode = parsedShots[0].scene_code;
                if (importCode && String(importCode).trim() === String(currentScene.scene_no).trim()) {
                    shouldOverwrite = true;
                }
            }
            
            if (shouldOverwrite && shots.length > 0) {
                 onLog?.(`Scene Code matched (${parsedShots[0].scene_code}). Overwriting existing shots...`, 'warning');
                 try {
                     await Promise.all(shots.map(s => deleteShot(s.id)));
                     setShots([]); 
                 } catch(e) {
                     console.error("Failed to delete existing shots", e);
                     onLog?.("Failed to clear shots. Appending...", "error");
                 }
            }

            let count = 0;
            // Create shots sequentially
            // Use 'selectedSceneId' for physical relationship, but 's.scene_code' ensures logical grouping
            // Note: If s.scene_code is missing, endpoints.py might hide the shot!
            for (const s of parsedShots) {
                 try {
                    // Ensure the shot object has scene_code
                    if (!s.scene_code && currentScene) s.scene_code = currentScene.scene_no;
                    
                    if (count === 0) {
                        if (!s.shot_logic_cn) {
                             onLog?.("Warning: 'Shot Logic (CN)' is empty in the parsed data.", "warning");
                        }
                    }

                    await createShot(selectedSceneId, s);
                    count++;
                 } catch(e) {
                     console.error("Failed to create shot", e);
                     onLog?.(`Failed to create shot ${s.shot_id || 'unknown'}: ${e.message}`, "error");
                 }
            }

            if (count > 0) {
                onLog?.(`Imported ${count} shots successfully. Refreshing view...`, 'success');
                setIsImportOpen(false);
                
                // FORCE REFRESH: Fetch specifically for current scene to ensure we have data immediately
                // Try refreshing both full episode list and specific scene
                await refreshShots(); 
                
                try {
                    const sceneSpecific = await fetchShots(selectedSceneId);
                    if (sceneSpecific && sceneSpecific.length > 0) {
                        setShots(sceneSpecific);
                    }
                } catch(e) { console.error("Post-import fetch failed", e); }

            } else {
                 onLog?.('Import completed but no shots created.', 'warning');
            }
        } else {
             onLog?.('No valid shots data found.', 'warning');
        }
    };

    // --- Helper: Parsing Entities matches ---
    // Updated Logic: Matches both [Name] and {Name}, allowing specific text source
    const getSuggestedRefImages = useCallback((shot, sourceText = null, strictMode = false) => {
        if (!shot) return [];
        // In ShotsView, 'entities' contains ALL entities (fetched by project)
        const entList = entities;
        
        if (!entList.length) {
            return [];
        }


        // Updated Logic: Matches both [Name] and {Name}, allowing specific text source
        // Now synchronized with ReferenceManager logic for consistent robust matching
        const normalizeName = (s) => (s || '')
            .replace(/[（【〔［]/g, '(')
            .replace(/[）】〕］]/g, ')')
            .replace(/[“”"'‘’]/g, '')
            .replace(/[\[\]\{\}【】｛｝]/g, '')
            .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
            .replace(/^@+/, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
        
        // Associated Entities (Included unless strictMode is true)
        const rawNames1 = strictMode ? [] : (shot.associated_entities || '').split(/[,，]/);
        
        // Prompt Search logic - Unified Regexes from ReferenceManager
        const regexes = [
            /\[([\s\S]+?)\]/g,    // [...]
            /\{([\s\S]+?)\}/g,    // {...}
            /【([\s\S]+?)】/g,     // 【...】
            /｛([\s\S]+?)｝/g,      // ｛...｝
            /(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)/g, // standalone @Name
            // Also keep legacy simple regex for cases without full brackets if needed? 
            // The legacy regex was: /[\[【\{]([^\]】\}\(]+)[\]】\}\(]/g; which was too restrictive.
        ];
        
        // If sourceText is provided, use it. Otherwise use shot fields EXCLUDING description (as per user request)
        let textToScan = sourceText;
        if (!textToScan) {
            const parts = [];
            if (shot.start_frame) parts.push(shot.start_frame);
            if (shot.end_frame) parts.push(shot.end_frame);
            if (shot.video_content) parts.push(shot.video_content);
            if (shot.prompt) parts.push(shot.prompt);
            textToScan = parts.join(' ');
        }

        const rawNames2 = [];
        if (textToScan) {
            regexes.forEach(regex => {
                let match;
                regex.lastIndex = 0;
                while ((match = regex.exec(textToScan)) !== null) {
                    if (match[1] && match[1].trim()) rawNames2.push(match[1]);
                }
            });
            // Legacy Fallback for simple "CharacterName" without brackets? No, usually enforced by [] 
        }
        
        // 3. Match Logic
        const candidates = [...rawNames1, ...rawNames2];
        const normalizedCandidates = candidates.map(normalizeName).filter(Boolean);

        let refs = entList.filter(e => {
            const cn = normalizeName(e.name || '');
            const en = normalizeName(e.name_en || '');
            
            // 3b. English Name extraction from Description (Legacy)
             if (!en && e.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) {
                    const complexEn = enMatch[1];
                    const rawEn = complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0]; 
                    // We don't redefine 'en' here as it's const, use local var if needed or just skip
                }
            }

            // Strict full-name exact check only
            const isMatch = normalizedCandidates.some(n => n === cn || (en && n === en));
            return isMatch;
        }).map(e => e.image_url).filter(Boolean);
        
        return [...new Set(refs)];
    }, [entities]);

    // Initialize Reference Images in technical_notes if empty
    // Also perform Entity Feature Injection (Auto-Expand) on load
    useEffect(() => {
        if (editingShot && entities.length > 0) {
            let updates = {};
            let hasUpdates = false;

            // 1. Ref Images Init
            try {
                const tech = JSON.parse(editingShot.technical_notes || '{}');
                if (tech.ref_image_urls === undefined) {
                    // Initialize strictly with Start Frame Prompt (camera_position)
                    const suggested = getSuggestedRefImages(editingShot, editingShot.start_frame);
                    if (suggested.length > 0) {
                        tech.ref_image_urls = suggested;
                        updates.technical_notes = JSON.stringify(tech);
                        hasUpdates = true;
                    }
                }
            } catch (e) { console.error("Error init ref images", e); }

            // 2. Feature Injection (Start Frame)
            const startPrompt = editingShot.start_frame || '';
            const { text: newStart, modified: modStart } = injectEntityFeatures(startPrompt);
            if (modStart) {
                updates.start_frame = newStart;
                hasUpdates = true;
            }

            // 3. Feature Injection (End Frame)
            const endPrompt = editingShot.end_frame || '';
            const { text: newEnd, modified: modEnd } = injectEntityFeatures(endPrompt);
            if (modEnd) {
                updates.end_frame = newEnd;
                hasUpdates = true;
            }

            // 4. Feature Injection (Video Prompt)
            const videoPrompt = editingShot.prompt || editingShot.video_content || '';
            const { text: newVideo, modified: modVideo } = injectEntityFeatures(videoPrompt);
            if (modVideo) {
                updates.prompt = newVideo;
                hasUpdates = true;
            }

            if (hasUpdates) {
                setEditingShot(prev => ({ ...prev, ...updates }));
            }
        }
    }, [editingShot?.id, entities]); // Only run when shot ID changes or entities load

    // Keyframe State Management
    const [localKeyframes, setLocalKeyframes] = useState([]);
    
    // Parse keyframes from shot text + technical_notes images
    useEffect(() => {
        if (!editingShot) return;

        const rawText = editingShot.keyframes || "";
        const tech = JSON.parse(editingShot.technical_notes || '{}');
        const legacyUrls = tech.keyframes || [];
        const mappedImages = tech.keyframe_images || {}; // Map: "1.5s": url

        let parsed = [];
        
        // 1. Parse Text Prompts
        if (rawText && rawText !== "NO" && rawText.length > 5) {
            // Regex to find [Time: XX] blocks
            // Assumption: keyframes are separated by [Time: ...]
            // Example: [Time: 1.5s] Desc... [Time: 2.0s] Desc...
            // Or newlines.
            const parts = rawText.split(/\[Time:\s*/i).filter(p => p.trim().length > 0);
            
            parts.forEach((p, idx) => {
                // p will be "1.5s] Description..."
                const closeBracket = p.indexOf(']');
                let time = `KF${idx+1}`;
                let prompt = p;
                
                if (closeBracket > -1) {
                    time = p.substring(0, closeBracket).trim();
                    prompt = p.substring(closeBracket+1).trim();
                } else {
                    // Fallback
                    prompt = "[Time: " + p; 
                }
                
                // Find image
                // Try map first
                let url = mappedImages[time];
                
                // Fallback to legacy array if index matches and no map entry
                if (!url && idx < legacyUrls.length) {
                    url = legacyUrls[idx];
                }

                parsed.push({ id: idx, time, prompt, url });
            });
        }
        
        // 2. Append extra legacy images that didn't match validation text
        if (legacyUrls.length > parsed.length) {
            for (let i = parsed.length; i < legacyUrls.length; i++) {
                parsed.push({ 
                    id: i, 
                    time: `Legacy ${i+1}`, 
                    prompt: "Legacy Keyframe (Image Only)", 
                    url: legacyUrls[i],
                    isLegacy: true
                });
            }
        }
        
        // If empty and not "NO", maybe init one? No, let user add.
        setLocalKeyframes(parsed);
        
    }, [editingShot?.id, editingShot?.keyframes, editingShot?.technical_notes]);

    const handleUpdateKeyframePrompt = (idx, newText) => {
        const updated = [...localKeyframes];
        updated[idx].prompt = newText;
        setLocalKeyframes(updated);
        // Debounced save or save on blur is better, but here we can just wait for a "Save" action or similar
        // Or reconstruct immediately. Reconstructing immediately is safer for consistency.
        reconstructKeyframes(updated);
    };
    
    const reconstructKeyframes = async (currentList, newTechOverride = null) => {
         // Rebuild shot.keyframes String
         // Format: [Time: time] prompt ...
         
         const textParts = currentList
            .filter(k => !k.isLegacy) // Legacy items don't go into text unless converted
            .map(k => `[Time: ${k.time}] ${k.prompt}`);
         
         const newKeyframesText = textParts.length > 0 ? textParts.join('\n') : "NO";
         
         // Rebuild Technical Notes
         const tech = JSON.parse(editingShot.technical_notes || '{}');
         
         // 1. Legacy Array (keep for safety, but sync with list)
         const urls = currentList.map(k => k.url).filter(Boolean);
         tech.keyframes = urls;
         
         // 2. Map (Preferred)
         const imgMap = {};
         currentList.forEach(k => {
             if (k.url) imgMap[k.time] = k.url;
         });
         tech.keyframe_images = imgMap;
         
         if (newTechOverride) {
             Object.assign(tech, newTechOverride);
         }
         
         // Update Local Logic (Optimistic)
         // We don't setLocalKeyframes here because that would trigger re-render loop if we are not careful
         // But we need to update 'editingShot' to trigger persistence
         
         const newData = {
             keyframes: newKeyframesText,
             technical_notes: JSON.stringify(tech)
         };
         
         // Update parent
         await onUpdateShot(editingShot.id, newData);
         // setEditingShot handled by onUpdateShot's internal state update wrapper if we used one, 
         // but local setEditingShot is raw.
         // onUpdateShot does: setShots ... and setEditingShot ...
         // So this will trigger useEffect parse again.
         // This might cause cursor jump in textarea. 
         // Strategy: Only update 'editingShot' if we are sure? 
         // Or rely on the fact that we are editing 'localKeyframes' state for text, and only syncing on Blur?
    };

    const translateCnPromptToEn = async (cnText, label = 'Prompt') => {
        const raw = String(cnText || '').trim();
        if (!raw) {
            showNotification(`${label} CN is empty`, 'warning');
            return null;
        }
        try {
            const res = await translateText(raw, 'zh', 'en');
            const translated = extractTranslatedText(res);
            if (!translated) throw new Error('No translation returned');
            return translated;
        } catch (e) {
            const msg = e?.response?.data?.detail || e?.message || 'Translate failed';
            onLog?.(`Translate CN->EN failed: ${msg}`, 'error');
            showNotification(`Translate failed: ${msg}`, 'error');
            return null;
        }
    };

    const generateAssetWithLang = async (assetType, lang = 'en', keyframeIndex = -1) => {
        if (!editingShot) return;
        const tech = JSON.parse(editingShot.technical_notes || '{}');

        if (assetType === 'start') {
            if (lang === 'zh') {
                const translated = await translateCnPromptToEn(tech.start_frame_cn, 'Start Frame');
                if (!translated) return;
                setEditingShot(prev => ({ ...(prev || {}), start_frame: translated }));
                await handleGenerateStartFrame(translated);
                return;
            }
            await handleGenerateStartFrame();
            return;
        }

        if (assetType === 'end') {
            if (lang === 'zh') {
                const translated = await translateCnPromptToEn(tech.end_frame_cn, 'End Frame');
                if (!translated) return;
                setEditingShot(prev => ({ ...(prev || {}), end_frame: translated }));
                await handleGenerateEndFrame(translated);
                return;
            }
            await handleGenerateEndFrame();
            return;
        }

        if (assetType === 'video') {
            if (lang === 'zh') {
                const translated = await translateCnPromptToEn(tech.video_prompt_cn, 'Video Prompt');
                if (!translated) return;
                setEditingShot(prev => ({ ...(prev || {}), prompt: translated }));
                await handleGenerateVideo(translated);
                return;
            }
            await handleGenerateVideo();
            return;
        }

        if (assetType === 'keyframe') {
            const kf = localKeyframes[keyframeIndex];
            if (!kf) return;
            if (lang === 'zh') {
                const cnMap = tech.keyframe_prompt_cn_map || {};
                const translated = await translateCnPromptToEn(cnMap[kf.time], `Keyframe ${kf.time}`);
                if (!translated) return;
                const updated = [...localKeyframes];
                if (!updated[keyframeIndex]) return;
                updated[keyframeIndex].prompt = translated;
                setLocalKeyframes(updated);
                await handleGenerateKeyframe(keyframeIndex, translated);
                return;
            }
            await handleGenerateKeyframe(keyframeIndex);
        }
    };

    // Helper for Generating Keyframe
    const handleGenerateKeyframe = async (kfIndex, promptOverride = null) => {
        const kf = localKeyframes[kfIndex];
        if (!kf) return;
        
        // UI Loading State (Local)
        const updated = [...localKeyframes];
        updated[kfIndex].loading = true;
        setLocalKeyframes(updated); // Show spinner
        
        onLog?.(`Generating Keyframe for T=${kf.time}...`, 'info');
        
        try {
            // Prompt Construction
            const globalCtx = getGlobalContextStr();
            const promptToUse = promptOverride || kf.prompt;
            const fullPrompt = promptToUse + globalCtx;
            
            // Generate
            const res = await generateImage(fullPrompt, null, null, {
                project_id: projectId,
                shot_id: editingShot.id,
                shot_number: `${editingShot.shot_id}_KF_${kf.time}`,
                shot_name: editingShot.shot_name,
                asset_type: 'keyframe'
            });
            
            if (res && res.url) {
                updated[kfIndex].url = res.url;
                if (promptOverride) {
                    updated[kfIndex].prompt = promptOverride;
                }
                updated[kfIndex].loading = false;
                
                // Save
                setLocalKeyframes([...updated]); // Force re-render with image
                await reconstructKeyframes(updated);
                onLog?.(`Keyframe T=${kf.time} Generated.`, 'success');
            }
        } catch(e) {
            console.error(e);
            onLog?.(`Keyframe Gen Failed: ${e.message}`, 'error');
            updated[kfIndex].loading = false;
            setLocalKeyframes(updated);
        }
    };
    
    const normalizeEntityToken = (value) => {
        return String(value || '')
            .replace(/[（【〔［]/g, '(')
            .replace(/[）】〕］]/g, ')')
            .replace(/[“”"'‘’]/g, '')
            .replace(/^[\[\{【｛\(\s]+|[\]\}】｝\)\s]+$/g, '')
            .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
            .replace(/^@+/, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    };

    // --- Entity Injection Helper ---
    // Injects anchor description while keeping original entity token shape.
    const injectEntityFeatures = (text) => {
        if (!text) return { text, modified: false };
        
        // In ShotsView, 'entities' contains ALL entities.
        const entList = entities;

        const regex = /[\[【](.*?)[\]】]/g;
        let newText = text;
        let modified = false;

        newText = newText.replace(regex, (match, name, offset, string) => {
            const cleanKey = normalizeEntityToken(name);

            if (!cleanKey) return match;

            // Check if followed by 's (possessive) -> Skip injection
            const tail = string.slice(offset + match.length);
            if (/^['’]s\b/i.test(tail)) {
                return match;
            }

            // Already injected once: [Token](...)
            if (/^\s*[\(（]/.test(tail)) {
                return match;
            }

            // 1. Global Style Injection
            if (cleanKey === 'global style' || cleanKey === 'global_style') {
                const style = activeEpisode?.episode_info?.e_global_info?.Global_Style;
                if (style) {
                    modified = true;
                    return `${match}(${style})`;
                }
                return match; 
            }

            // 2. Entity Injection
            if (entList.length > 0) {
                const entity = entList.find(e => {
                    const cn = normalizeEntityToken(e.name || '');
                    const en = normalizeEntityToken(e.name_en || '');
                    
                    let fallbackEn = '';
                    if (!en && e.description) {
                        const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                        if (enMatch && enMatch[1]) {
                            fallbackEn = normalizeEntityToken(enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0]);
                        }
                    }
                    return (cn === cleanKey) || (en === cleanKey) || (fallbackEn === cleanKey);
                });

                if (entity) {
                    modified = true;
                    const anchor = entity.anchor_description || entity.description || '';
                    return `${match}(${anchor})`;
                }
            }

            return match; 
        });

        return { text: newText, modified };
    };

    const isStartFrameInheritPrompt = (value) => {
        const token = String(value || '').trim().toUpperCase();
        return token === 'SAME' || token === 'SAP';
    };

    const findPrevShotEndFrameUrl = (shotId) => {
        const currentIdx = shots.findIndex(s => s.id === shotId);
        if (currentIdx <= 0) return null;
        try {
            const prevShot = shots[currentIdx - 1];
            const prevTech = JSON.parse(prevShot.technical_notes || '{}');
            return prevTech.end_frame_url || null;
        } catch (e) {
            return null;
        }
    };

    // --- Generation Handlers ---
    const handleGenerateStartFrame = async (promptOverride = null) => {
        if (!editingShot) return;
        const targetShotId = editingShot.id;

        // Check inherit logic - Inherit from previous End Frame
        const currentPrompt = String(promptOverride || editingShot.start_frame || '').trim();
        if (isStartFrameInheritPrompt(currentPrompt)) {
            const prevEndUrl = findPrevShotEndFrameUrl(editingShot.id);

            if (prevEndUrl) {
                try {
                    onLog?.('Inheriting Start Frame from previous shot...', 'info');
                    const newData = { image_url: prevEndUrl };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev));
                    onLog?.('Start Frame inherited successfully', 'success');
                    showNotification('Start Frame inherited from previous shot', 'success');
                    return; // Exit, do not generate
                } catch (err) {
                    console.error("Error inheriting frame", err);
                    showNotification(`Failed to inherit frame: ${err?.message || 'Unknown error'}`, "error");
                }
            } else {
                const noPrevMsg = shots.findIndex(s => s.id === editingShot.id) <= 0
                    ? 'No previous shot to inherit from'
                    : 'Previous shot has no End Frame to inherit';
                showNotification(noPrevMsg, 'warning');
                return;
            }
        }

        setShotGeneratingState(targetShotId, 'start', true);
        abortGenerationRef.current = false; 

        // 1. Feature Injection
        let prompt = promptOverride || editingShot.start_frame || editingShot.video_content || "A cinematic shot";
        
        // Apply injection logic
        const { text: injectedPrompt, modified } = injectEntityFeatures(prompt);
        if (modified) {
            // Update local State & use new prompt
            setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, start_frame: injectedPrompt } : prev));
            prompt = injectedPrompt; // Use for generation
        }

        onLog?.('Generating Start Frame...', 'info');
        
        let success = false;
        let attempts = 0;
        const maxAttempts = 3; // Reduced from 10

        while (!success && attempts < maxAttempts) {
             if (abortGenerationRef.current) {
                 onLog?.('Start Frame generation stopped by user.', 'warning');
                 break;
             }

             attempts++;
             if (attempts > 1) {
                 onLog?.(`Retrying Start Frame (Attempt ${attempts}/${maxAttempts})...`, 'warning');
                 showNotification(`Retrying Start Frame (Attempt ${attempts}/${maxAttempts})...`, 'info');
             }

             try {
                // Refs Logic for Start Frame (updated):
                // 1. If user has manually edited the Refs list (it exists in tech notes), respect it 100% (handling deletions/inactive).
                // 2. If list is undefined (never touched), auto-populate strictly from Subjects (latest entity images).
                // 3. Filter out any null/empty strings just in case.
                
                let refs = [];
                try {
                    const noteStr = editingShot.technical_notes || '{}';
                    const tech = JSON.parse(noteStr);
                    
                    // Always calculate auto-suggested refs first (with new robust logic)
                    const autoMatches = getSuggestedRefImages(editingShot, prompt, true);

                    if (Array.isArray(tech.ref_image_urls)) {
                        // Manual Mode: Merge saved list with NEW auto-matches (respecting deletions)
                        const savedRefs = tech.ref_image_urls;
                        const deletedRefs = tech.deleted_ref_urls || [];
                        
                        const newAutoMatches = autoMatches.filter(url => 
                            !savedRefs.includes(url) && !deletedRefs.includes(url)
                        );
                        
                        refs = [...savedRefs, ...newAutoMatches];
                    } else {
                        // Auto-populate mode
                        refs = autoMatches;
                        
                        try {
                            const currentIdx = shots.findIndex(s => s.id === editingShot.id);
                            if (currentIdx > 0) {
                                const prevShot = shots[currentIdx - 1];
                                const prevTech = JSON.parse(prevShot.technical_notes || '{}');
                                if (prevTech.end_frame_url && !refs.includes(prevTech.end_frame_url)) {
                                    refs.unshift(prevTech.end_frame_url);
                                }
                            }
                        } catch(err) { console.error("Prev shot lookup failed", err); }
                        
                        // Deduplicate only in Auto Mode
                        refs = [...new Set(refs)];
                    }
                } catch(e) { console.error("Error determining refs:", e); }
                
                // Final clean
                refs = refs.filter(Boolean);

                // NEW: Inject Global Context
                const globalCtx = getGlobalContextStr();
                const finalPrompt = prompt + globalCtx;

                const res = await generateImage(finalPrompt, null, refs.length > 0 ? refs : null, {
                    project_id: projectId,
                    shot_id: targetShotId,
                    shot_number: editingShot.shot_id,
                    shot_name: editingShot.shot_name,
                    asset_type: 'start_frame',
                });
                if (res && res.url) {
                    // Save original prompt to DB (user view), but image was generated with context
                    const newData = { image_url: res.url, start_frame: prompt };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev)); 
                    onLog?.('Start Frame Generated', 'success');
                    showNotification('Start Frame Generated', 'success');
                    success = true;
                } else {
                    throw new Error("No image URL returned");
                }
            } catch (e) {
                console.error(`Attempt ${attempts} failed:`, e);
                if (attempts >= maxAttempts) {
                    onLog?.(`Generation failed after ${maxAttempts} attempts: ${e.message}`, 'error');
                    showNotification(`Generation failed: ${e.message}`, 'error');
                }
            }
        }
        setShotGeneratingState(targetShotId, 'start', false);
    };

    const handleGenerateEndFrame = async (promptOverride = null) => {
        if (!editingShot) return;
        const targetShotId = editingShot.id;
        setShotGeneratingState(targetShotId, 'end', true);
        abortGenerationRef.current = false;

        // 1. Feature Injection for End Frame
        let prompt = promptOverride || editingShot.end_frame || "End frame";
        const { text: injectedPrompt, modified } = injectEntityFeatures(prompt);
        if (modified) {
            setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, end_frame: injectedPrompt } : prev));
            prompt = injectedPrompt;
        }

        onLog?.('Generating End Frame...', 'info');

        let success = false;
        let attempts = 0;
        const maxAttempts = 3; // Reduced from 10

        while (!success && attempts < maxAttempts) {
             if (abortGenerationRef.current) {
                 onLog?.('End Frame generation stopped by user.', 'warning');
                 break;
             }

             attempts++;
             if (attempts > 1) {
                 onLog?.(`Retrying End Frame (Attempt ${attempts}/${maxAttempts})...`, 'warning');
                 showNotification(`Retrying End Frame (Attempt ${attempts}/${maxAttempts})...`, 'info');
             }

             try {
                // Include Entity Refs + Manual Refs
                const tech = JSON.parse(editingShot.technical_notes || '{}');
                // Use End Refs specifically
                const refs = [];
                
                if (Array.isArray(tech.end_ref_image_urls)) {
                    refs.push(...tech.end_ref_image_urls);
                } else {
                    const suggested = getSuggestedRefImages(editingShot, prompt, true);
                    refs.push(...suggested);
                }
                
                const deletedRefs = Array.isArray(tech.deleted_ref_urls) ? tech.deleted_ref_urls : [];
                const isDeleted = deletedRefs.includes(editingShot.image_url);
                
                if (editingShot.image_url && !refs.includes(editingShot.image_url) && !isDeleted) {
                    refs.unshift(editingShot.image_url);
                }
                
                const uniqueRefs = [...new Set(refs)].filter(Boolean);
                
                // NEW: Inject Global Context
                const globalCtx = getGlobalContextStr();
                const finalPrompt = prompt + globalCtx;

                const res = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                    project_id: projectId,
                    shot_id: targetShotId,
                    shot_number: editingShot.shot_id,
                    shot_name: editingShot.shot_name,
                    asset_type: 'end_frame',
                });
                if (res && res.url) {
                    tech.end_frame_url = res.url;
                    tech.video_gen_mode = 'start_end'; // Auto-switch to Start+End
                    const newData = { technical_notes: JSON.stringify(tech), end_frame: prompt };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev));
                    onLog?.('End Frame Generated', 'success');
                    showNotification('End Frame Generated', 'success');
                    success = true;
                } else {
                     throw new Error("No image URL returned");
                }
            } catch (e) {
                console.error(`Attempt ${attempts} failed:`, e);
                if (attempts >= maxAttempts) {
                    onLog?.(`Generation failed after ${maxAttempts} attempts: ${e.message}`, 'error');
                    showNotification(`Generation failed: ${e.message}`, 'error');
                }
            }
        }
        setShotGeneratingState(targetShotId, 'end', false);
    };

    const handleGenerateVideo = async (promptOverride = null) => {
        if (!editingShot) return;
        const targetShotId = editingShot.id;
        const targetGeneratingState = generatingStateByShot[targetShotId] || { start: false, end: false, video: false };
        if (targetGeneratingState.video) {
             return; 
        }

        setShotGeneratingState(targetShotId, 'video', true);

        // 1. Feature Injection for Video Prompt
        let prompt = promptOverride || editingShot.prompt || editingShot.video_content || "Video motion";
        const { text: injectedPrompt, modified } = injectEntityFeatures(prompt);
        if (modified) {
            setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, prompt: injectedPrompt } : prev));
            prompt = injectedPrompt;
        }

        onLog?.('Generating Video...', 'info');
        try {
            const tech = JSON.parse(editingShot.technical_notes || '{}');
            const keyframes = tech.keyframes || [];

            const resolveVideoMode = (t) => {
                if (t?.video_mode_unified) return t.video_mode_unified;
                if (t?.video_ref_submit_mode === 'refs_video') return 'refs_video';
                return t?.video_gen_mode || 'start';
            };
            const videoMode = resolveVideoMode(tech);
            const videoRefSubmitMode = videoMode === 'refs_video' ? 'refs_video' : 'auto';
            
            const refs = [];
            // 1. Video Ref Selection Strategy
            // Shot-Specific Mode from technical_notes (default: start)
            // USER REQUEST: Default to 'start' only (Start Only) unless specified
            let shotMode = tech.video_gen_mode;
            
            // Logic: Default is Start+End IF End Frame URL exists.
            // NEW REQ: If end_frame prompt length < 3 -> Start Only
            if (!shotMode) {
                 const endPrompt = editingShot.end_frame || ""; // End Frame text
                 const endPromptLen = endPrompt.trim().length;
                 
                 if (tech.end_frame_url && endPromptLen >= 3) {
                     shotMode = 'start_end';
                 } else {
                     shotMode = 'start';
                 }
            }
            
            // Check if user has explicitly managed video refs
            if (videoRefSubmitMode === 'refs_video') {
                if (tech.video_ref_image_urls && Array.isArray(tech.video_ref_image_urls)) {
                    refs.push(...tech.video_ref_image_urls);
                }
            } else if (tech.video_ref_image_urls && Array.isArray(tech.video_ref_image_urls)) {
                // Manual Mode: Use strictly what's in the list
                refs.push(...tech.video_ref_image_urls);
            } else {
                // Auto Mode respecting shotMode ('start_end' | 'start' | 'end')
                
                // A. Start Frame (Skip if 'end' mode)
                if (shotMode !== 'end' && editingShot.image_url) {
                    refs.push(editingShot.image_url);
                }
                
                // B. Keyframes
                if (keyframes && keyframes.length) refs.push(...keyframes);
                
                // C. End Frame as Ref (Only in Start+End mode)
                if (shotMode === 'start_end' && tech.end_frame_url) {
                    refs.push(tech.end_frame_url);
                }

                // D. Entity Refs from Video Prompt -> REMOVED per user request strictness
                // "Only take from Refs (Video)". The UI for Refs (Video) excludes entity prompts by default now.
                // const entityRefs = getSuggestedRefImages(editingShot, prompt, true);
                // refs.push(...entityRefs);
            }
            
            const uniqueRefs = [...new Set(refs)];
            
            // Last Frame Argument logic
            
            // Refined Strategy: "Final Video取首尾帧要从Refs (Video)按序获取，第一个和最后一个"
            
            let finalStartRef = null;
            let finalEndRef = null;
            
            if (videoRefSubmitMode === 'refs_video') {
                // Submit Refs (Video) as reference images without requiring Start/End frames.
                finalStartRef = uniqueRefs.length > 0 ? uniqueRefs[0] : null;
                finalEndRef = null;
            } else if (uniqueRefs.length > 0) {
                finalStartRef = uniqueRefs[0];
                // Take the last item as End Frame if there is more than 1 item
                if (uniqueRefs.length > 1) {
                    finalEndRef = uniqueRefs[uniqueRefs.length - 1];
                }
            }
            
            // Duration Logic: Use Shot Duration (s) if valid, else default to 5
            const durParam = parseFloat(editingShot.duration) || 5;

            // NEW: Inject Global Context
            const globalCtx = getGlobalContextStr();
            const finalPrompt = prompt + globalCtx;

            const res = await generateVideo(finalPrompt, null, finalStartRef, finalEndRef, durParam, {
                project_id: projectId,
                shot_id: targetShotId,
                shot_number: editingShot.shot_id,
                shot_name: editingShot.shot_name,
                asset_type: 'video',
            }, keyframes);
            if (res && res.url) {
                const newData = { video_url: res.url, prompt: prompt };
                
                // 1. Force Local State Update IMMEDIATELY (Optimistic/Local)
                setEditingShot(prev => {
                         if (!prev || prev.id !== targetShotId) return prev;
                   return { ...prev, ...newData };
                });
                
                onLog?.('Video Generated', 'success');
                showNotification('Video Generated', 'success');

                // 2. Update Server & Master List (Async persistence)
                try {
                    await onUpdateShot(targetShotId, newData);
                } catch (updateErr) {
                    console.error("Failed to save shot update to backend:", updateErr);
                    // We don't block the UI - the video is here.
                }
            }
        } catch (e) {
             onLog?.(`Generation failed: ${e.message}`, 'error');
             showNotification(`Generation failed: ${e.message}`, 'error');
        } finally {
            setShotGeneratingState(targetShotId, 'video', false);
        }
    };

    const handleBatchGenerate = async () => {
        if (shots.length === 0) return;
        if (!await confirmUiMessage(`Generate missing Start/End frames for all ${shots.length} shots? This may take a while.`)) return;

        setIsBatchGenerating(true);
        setBatchProgress({ current: 0, total: shots.length, status: 'Starting...' });
        onLog?.("Starting Batch Generation...", "process");

        let generatedCount = 0;
        let processedCount = 0;

        // Iterate sequentially
        for (const shot of shots) {
             // Update progress UI
             processedCount++;
             const statusBase = `Processing Shot ${shot.shot_id}`;
             setBatchProgress({ current: processedCount, total: shots.length, status: statusBase });

             // 1. Check Start Frame
            if (!shot.image_url) {
                try {
                    setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Start Frame...` });
                    let prompt = shot.start_frame || shot.video_content || "A cinematic shot";

                    if (isStartFrameInheritPrompt(prompt)) {
                        const prevEndUrl = findPrevShotEndFrameUrl(shot.id);
                        if (prevEndUrl) {
                            const inheritData = { image_url: prevEndUrl };
                            await onUpdateShot(shot.id, inheritData);
                            shot.image_url = prevEndUrl;
                            generatedCount++;
                            onLog?.(`[Batch ${processedCount}/${shots.length}] Inherited Start for Shot ${shot.shot_id} via SAP/SAME`, 'success');
                        } else {
                            onLog?.(`[Batch ${processedCount}/${shots.length}] Skip Start for Shot ${shot.shot_id}: SAP/SAME but previous End Frame missing`, 'warning');
                        }
                        continue;
                    }

                    const { text: injectedPrompt } = injectEntityFeatures(prompt);
                    
                    let refs = [];
                    try {
                        const noteStr = shot.technical_notes || '{}';
                        const tech = JSON.parse(noteStr);
                        if (Array.isArray(tech.ref_image_urls)) {
                            refs = [...tech.ref_image_urls];
                        } else {
                            refs = getSuggestedRefImages(shot, injectedPrompt, true);
                        }

                        // UNIVERSAL INJECTION: Previous Shot End Frame (Batch)
                        try {
                            const idx = shots.findIndex(s => s.id === shot.id);
                            if (idx > 0) {
                                const prevShot = shots[idx - 1];
                                const prevTech = JSON.parse(prevShot.technical_notes || '{}');
                                if (prevTech.end_frame_url && !refs.includes(prevTech.end_frame_url)) {
                                     refs.unshift(prevTech.end_frame_url);
                                }
                            }
                        } catch(e) {}
                    } catch(e) {}
                    refs = [...new Set(refs)].filter(Boolean);

                    onLog?.(`[Batch ${processedCount}/${shots.length}] Generating Start for Shot ${shot.shot_id}...`, "info");
                    
                    // NEW: Inject Global Context
                    const globalCtx = getGlobalContextStr();
                    const finalPrompt = injectedPrompt + globalCtx; 

                    const res = await generateImage(finalPrompt, null, refs.length > 0 ? refs : null, {
                        project_id: projectId,
                        shot_id: shot.id,
                        shot_number: shot.shot_id,
                        shot_name: shot.shot_name,
                        asset_type: 'start_frame'
                    });

                    if (res && res.url) {
                        const newData = { image_url: res.url, start_frame: injectedPrompt };
                        await onUpdateShot(shot.id, newData); // This triggers UI update
                        generatedCount++;
                    }
                } catch(e) {
                    console.error(`Batch Start Gen Error (Shot ${shot.id}):`, e);
                }
            }
            
            // 2. Check End Frame
            let tech = {};
            try { tech = JSON.parse(shot.technical_notes || '{}'); } catch(e){}
            
            if (!tech.end_frame_url) {
                 try {
                     let prompt = shot.end_frame || "End frame";
                     const { text: injectedPrompt } = injectEntityFeatures(prompt);
                     
                     let refs = [];
                     
                     // 1. Manual List
                     if (Array.isArray(tech.end_ref_image_urls)) {
                         refs.push(...tech.end_ref_image_urls);
                     } else {
                         // 2. Auto Entities
                         const suggested = getSuggestedRefImages(shot, injectedPrompt, true);
                         refs.push(...suggested);
                     }
                     
                     // UNIVERSAL INJECTION: Start Frame (Batch)
                     if (shot.image_url && !refs.includes(shot.image_url)) {
                         refs.unshift(shot.image_url);
                     }
                     
                     const uniqueRefs = [...new Set(refs)].filter(Boolean);

                     onLog?.(`[Batch ${processedCount}/${shots.length}] Generating End for Shot ${shot.shot_id}...`, "info");
                     setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: End Frame...` });
                     const res = await generateImage(injectedPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                        project_id: projectId,
                        shot_id: shot.id,
                        shot_number: shot.shot_id,
                                shot_name: shot.shot_name,
                        asset_type: 'end_frame'
                    });

                    if (res && res.url) {
                        tech.end_frame_url = res.url;
                        const newData = { technical_notes: JSON.stringify(tech), end_frame: injectedPrompt };
                        await onUpdateShot(shot.id, newData); // This triggers UI update
                        generatedCount++;
                    }
                 } catch(e) {
                      console.error(`Batch End Gen Error (Shot ${shot.id}):`, e);
                 }
            }
        }

        setIsBatchGenerating(false);
        setBatchProgress({ current: 0, total: 0, status: '' });
        onLog?.(`Batch Generation Complete. Generated ${generatedCount} new keyframes.`, "success");
        refreshShots();
    };

    const handleBatchGenerateVideo = async () => {
        if (shots.length === 0) return;
        if (!await confirmUiMessage(`Generate Videos for all ${shots.length} shots? This will AUTO-GENERATE any missing Start/End frames first.`)) return;

        setIsBatchGenerating(true);
        setBatchProgress({ current: 0, total: shots.length, status: 'Starting Video Batch...' });
        onLog?.("Starting Batch Video Generation...", "process");

        let generatedCount = 0;
        let processedCount = 0;

        for (const shot of shots) {
            processedCount++;
            const statusBase = `Shot ${shot.shot_id}`;
            
            // Optimization: If video exists, skip everything for this shot
            if (shot.video_url) {
                // Optional: Update progress or log if needed, but 'continue' is faster
                continue; 
            }

            setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Checking...` });
            
            // We use a local updated copy to carry forward image urls generated in step 1/2 to step 3
            let currentShot = { ...shot }; 
            let shotTech = {};
            try { shotTech = JSON.parse(currentShot.technical_notes || '{}'); } catch(e){}

            const resolveVideoMode = (t) => {
                if (t?.video_mode_unified) return t.video_mode_unified;
                if (t?.video_ref_submit_mode === 'refs_video') return 'refs_video';
                return t?.video_gen_mode || 'start';
            };
            const resolvedCurrentMode = resolveVideoMode(shotTech);
            const currentShotMode = shotTech.video_gen_mode || 'start'; // Default: Start Only
            const currentVideoRefSubmitMode = resolvedCurrentMode === 'refs_video' ? 'refs_video' : 'auto';

            try {
                // 1. Ensure Start Frame
                if (currentVideoRefSubmitMode !== 'refs_video' && currentShotMode !== 'end' && !currentShot.image_url) {
                    try {
                        setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Start Frame...` });
                        let prompt = currentShot.start_frame || currentShot.video_content || "A cinematic shot";
                        const isInheritPrompt = isStartFrameInheritPrompt(prompt);

                        if (isInheritPrompt) {
                            const prevEndUrl = findPrevShotEndFrameUrl(currentShot.id);
                            if (prevEndUrl) {
                                const inheritData = { image_url: prevEndUrl };
                                await onUpdateShot(currentShot.id, inheritData);
                                currentShot.image_url = prevEndUrl;
                                onLog?.(`Inherited Start Frame for Shot ${currentShot.shot_id} via SAP/SAME`, 'success');
                            } else {
                                onLog?.(`Skip inheriting Start Frame for Shot ${currentShot.shot_id}: previous End Frame missing`, 'warning');
                                // SAP/SAME without previous End Frame should not trigger image generation
                                continue;
                            }
                            // continue to next steps (End/Video) using currentShot.image_url if inherited
                        }

                        const { text: injectedPrompt } = injectEntityFeatures(prompt);
                        
                        let refs = [];
                        try {
                            const noteStr = currentShot.technical_notes || '{}';
                            const tech = JSON.parse(noteStr);
                            if (Array.isArray(tech.ref_image_urls)) {
                                refs = tech.ref_image_urls;
                            } else {
                                // Auto Logic used during Manual as well
                                refs = getSuggestedRefImages(currentShot, injectedPrompt, true);
                            }
                        } catch(e) {}
                        refs = [...new Set(refs)].filter(Boolean);

                        if (!isInheritPrompt || !currentShot.image_url) {
                            const res = await generateImage(injectedPrompt, null, refs.length > 0 ? refs : null, {
                                project_id: projectId,
                                shot_id: currentShot.id,
                                shot_number: currentShot.shot_id,
                                shot_name: currentShot.shot_name,
                                asset_type: 'start_frame'
                            });

                            if (res && res.url) {
                                const newData = { image_url: res.url, start_frame: injectedPrompt };
                                await onUpdateShot(currentShot.id, newData);
                                currentShot.image_url = res.url; // Update local for video step
                                onLog?.(`Generated Start Frame for Shot ${currentShot.shot_id}`, "success");
                            }
                        }
                    } catch(e) { console.error("Batch Start Gen Error", e); }
                }

                // 2. Ensure End Frame
                let tech = {};
                try { tech = JSON.parse(currentShot.technical_notes || '{}'); } catch(e){}
                
                // Determine Shot Mode (default start)
                const shotMode = tech.video_gen_mode || 'start';

                if (currentVideoRefSubmitMode !== 'refs_video' && shotMode !== 'start' && !tech.end_frame_url) {
                    try {
                        setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: End Frame...` });
                        let prompt = currentShot.end_frame || "End frame";
                        const { text: injectedPrompt } = injectEntityFeatures(prompt);
                        
                        let refs = [];
                        if (Array.isArray(tech.end_ref_image_urls)) {
                            refs.push(...tech.end_ref_image_urls);
                        } else {
                            if (currentShot.image_url) refs.push(currentShot.image_url);
                            const suggested = getSuggestedRefImages(currentShot, injectedPrompt, true);
                            refs.push(...suggested);
                        }
                        const uniqueRefs = [...new Set(refs)].filter(Boolean);

                        const res = await generateImage(injectedPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                            project_id: projectId,
                            shot_id: currentShot.id,
                            shot_number: currentShot.shot_id,
                            shot_name: currentShot.shot_name,
                            asset_type: 'end_frame'
                        });

                        if (res && res.url) {
                            tech.end_frame_url = res.url;
                            const newData = { technical_notes: JSON.stringify(tech), end_frame: injectedPrompt };
                            await onUpdateShot(currentShot.id, newData);
                            currentShot.technical_notes = JSON.stringify(tech); // Update local
                            onLog?.(`Generated End Frame for Shot ${currentShot.shot_id}`, "success");
                        }
                    } catch(e) { console.error("Batch End Gen Error", e); }
                }

                // 3. Generate Video
                if (!currentShot.video_url) {
                    try {
                        setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Generating Video...` });
                        const prompt = currentShot.video_content || currentShot.video_content || currentShot.prompt || "Video motion";
                        const { text: injectedPrompt } = injectEntityFeatures(prompt);
                        
                        // Refs: Strategy based on shot specific mode
                        let refs = [];
                        let tech2 = {};
                        try { tech2 = JSON.parse(currentShot.technical_notes || '{}'); } catch(e){}
                        const shotMode2 = tech2.video_gen_mode || 'start'; // Default: Start Only
                        const resolvedMode2 = resolveVideoMode(tech2);
                        const shotVideoRefSubmitMode = resolvedMode2 === 'refs_video' ? 'refs_video' : 'auto';

                        if (shotVideoRefSubmitMode === 'refs_video') {
                            if (tech2.video_ref_image_urls && Array.isArray(tech2.video_ref_image_urls)) {
                                refs.push(...tech2.video_ref_image_urls);
                            }
                        } else if (tech2.video_ref_image_urls && Array.isArray(tech2.video_ref_image_urls)) {
                            refs.push(...tech2.video_ref_image_urls);
                        } else {
                            // Auto Mode respecting shotMode
                            if (shotMode2 !== 'end' && currentShot.image_url) refs.push(currentShot.image_url);
                            if (tech2.keyframes && Array.isArray(tech2.keyframes)) refs.push(...tech2.keyframes);
                            if (shotMode2 === 'start_end' && tech2.end_frame_url) refs.push(tech2.end_frame_url);

                            // Retrieve entity keywords -> REMOVED strict logic
                            // refs.push(...getSuggestedRefImages(currentShot, injectedPrompt));
                        }

                        const uniqueRefs = [...new Set(refs)].filter(Boolean);
                        
                        let lastFrame = null;
                        if (shotVideoRefSubmitMode !== 'refs_video' && (shotMode2 === 'start_end' || shotMode2 === 'end')) {
                            lastFrame = tech2.end_frame_url || null;
                        }

                        onLog?.(`[Batch ${processedCount}/${shots.length}] Generating Video for Shot ${currentShot.shot_id}...`, "info");
                        
                        const durParam = parseFloat(currentShot.duration) || 5;

                        const res = await generateVideo(injectedPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, lastFrame, durParam, {
                            project_id: projectId,
                            shot_id: currentShot.id,
                            shot_number: currentShot.shot_id,
                            shot_name: currentShot.shot_name,
                            asset_type: 'video'
                        });

                        if (res && res.url) {
                            const newData = { video_url: res.url, prompt: injectedPrompt };
                            await onUpdateShot(currentShot.id, newData);
                            generatedCount++;
                            // No need to update currentShot.video_url unless we do something else later
                        }
                    } catch(e) {
                        onLog?.(`Batch Video Error (Shot ${currentShot.shot_id}): ${e.message}`, "error");
                    }
                }
            } catch(e) { console.error("Batch Loop Fatal Error", e); }
        }

        setIsBatchGenerating(false);
        setBatchProgress({ current: 0, total: 0, status: '' });
        onLog?.(`Batch Video Generation Complete. Generated ${generatedCount} videos.`, "success");
        refreshShots();
    };


    // Save to shot_content (similar to SceneManager)
    const handleSaveList = async () => {
        if (!activeEpisode) return;
        
        onLog?.('ShotsView: Saving content...', 'info');

        const contextInfo = `Project: ${project?.title || 'Unknown'} | Episode: ${activeEpisode?.title || 'Unknown'}\n`;
        const header = `| Shot No | Title | Start Frame | End Frame | Video Content | Duration | Associated Entities |\n|---|---|---|---|---|---|---|`;
        
        // Map current state to markdown table
        const content = shots.map(s => {
             const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
             return `| ${clean(s.shot_id)} | ${clean(s.shot_name)} | ${clean(s.start_frame)} | ${clean(s.end_frame)} | ${clean(s.video_content || s.video_content)} | ${clean(s.duration)} | ${clean(s.associated_entities)} |`;
        }).join('\n');
        
        try {
            await updateEpisode(activeEpisode.id, { shot_content: contextInfo + header + '\n' + content });
            onLog?.(`Saved Shot List (${shots.length} items) to text content.`, 'success');
        } catch(e) {
            console.error(e);
            onLog?.('Failed to save shot list.', 'error');
        }
    };

    return (
        <div className="flex flex-col h-full w-full p-6 overflow-hidden">
             {/* Header / Toolbar */}
             <div className="flex justify-between items-center mb-6 shrink-0">
                <div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        {t('镜头管理', 'Shot Manager')}
                        <span className="text-sm font-normal text-muted-foreground ml-2">({shots.length})</span>
                    </h2>
                    {/* Add Save Button */}
                    <button 
                         onClick={handleSaveList}
                         className="px-3 py-1.5 bg-white/5 text-white hover:bg-white/10 rounded-lg text-sm font-medium flex items-center gap-2 border border-white/10"
                        title={t('将当前列表保存到 Shot Content（文本）', 'Save current list to Shot Content (Text)')}
                    >
                        <Save className="w-4 h-4" /> {t('保存列表', 'Save List')}
                    </button>
                    <div className="relative">
                         <select 
                            className="bg-black/40 border border-white/20 rounded px-3 py-1.5 text-sm min-w-[200px] text-white"
                            value={selectedSceneId || ''}
                            onChange={(e) => setSelectedSceneId(e.target.value)}
                         >
                            <option value="">{t('选择场景...', 'Select a Scene...')}</option>
                            <option value="all">{t('全部场景', 'All Scenes')}</option>
                        {scenes.map(s => (
                                <option key={s.id} value={s.id}>{s.scene_no} - {s.scene_name || t('未命名', 'Untitled')}</option>
                            ))}
                         </select>
                         {selectedSceneId && selectedSceneId !== 'all' && (
                             <button
                                 onClick={() => handleGenerateShots(selectedSceneId)}
                                 className="ml-2 px-3 py-1.5 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/20 rounded text-xs flex items-center gap-1"
                                 title={t('根据 AI 提示生成镜头', 'Generate Shots from AI Prompt')}
                             >
                                 <Wand2 className="w-3 h-3"/> {t('AI 镜头', 'AI Shots')}
                             </button>
                         )}
                         <button 
                            onClick={() => handleSyncScenes()}
                            className="ml-2 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded text-xs text-white border border-white/10"
                            title={t('从文本剧本同步场景与镜头', 'Sync Scenes & Shots from Text Script')}
                        >
                            <RefreshCw className="w-3 h-3"/>
                        </button>
                        <button 
                            onClick={handleDeleteAllShots}
                            className="ml-2 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded text-xs border border-red-500/20"
                            title={t('删除当前显示的全部镜头', 'Delete All Displayed Shots')}
                        >
                            <Trash2 className="w-3 h-3"/>
                        </button>
                        <div className="relative inline-flex items-center ml-2 border border-white/20 rounded overflow-hidden">
                             <button 
                                onClick={handleBatchGenerate}
                                disabled={isBatchGenerating}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 ${isBatchGenerating ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title={t('批量生成缺失的起始/结束帧', 'Batch Generate Missing Start/End Frames')}
                            >
                                {isBatchGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                            </button>
                            <button 
                                onClick={handleBatchGenerateVideo}
                                disabled={isBatchGenerating}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all ${isBatchGenerating ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title={t('批量生成视频（会先自动生成图片）', 'Batch Generate Videos (Auto-creates images first)')}
                            >
                                {isBatchGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>}
                            </button>
                        </div>

                        {/* Progress Indicator - Moved outside overflow-hidden container */}
                        {isBatchGenerating && batchProgress.total > 0 && (
                            <div className="absolute left-full top-0 ml-2 z-50 bg-black/80 px-3 py-2 rounded-md border border-primary/20 backdrop-blur-md shadow-xl min-w-[180px]">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-[10px] font-bold text-primary">{t('批处理进度', 'Batch Processing')}</span>
                                    <span className="text-[10px] text-white font-mono">{Math.round((batchProgress.current / batchProgress.total) * 100)}%</span>
                                </div>
                                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-1.5">
                                    <div 
                                        className="h-full bg-primary transition-all duration-300 ease-out"
                                        style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                                    ></div>
                                </div>
                                {batchProgress.status && (
                                    <div className="text-[9px] text-muted-foreground truncate max-w-[160px]" title={batchProgress.status}>
                                        {batchProgress.status}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                     {/* Settings Button Moved to Edit Shot View */}
                </div>
            </div>

             {/* Progress Bar for Batch */}
             <div className="px-4">
                 <div className={`transition-all duration-300 overflow-hidden ${isBatchGenerating ? 'h-6 mt-2' : 'h-0'}`}>
                    <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-1.5">
                        <div 
                            className="h-full bg-primary transition-all duration-300 ease-out"
                            style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                        ></div>
                    </div>
                </div>
            </div>

            {/* Sub-header Actions */}
            <div className="px-4 pb-2 flex justify-end">
                {selectedSceneId && selectedSceneId !== 'all' && (
                    <button 
                        onClick={() => setIsImportOpen(true)}
                        className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2"
                    >
                        <Upload className="w-4 h-4"/> {t('导入镜头', 'Import Shots')}
                    </button>
                )}
             </div>
             
             {/* Main Content */}
             <div className="flex-1 overflow-auto custom-scrollbar">
                 {selectedSceneId ? (
                     <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6 pb-20">
                        {shots.map((shot, idx) => (
                            <div 
                                key={shot.id} 
                                className="bg-card/80 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden group hover:border-primary/50 transition-all cursor-pointer relative"
                                onClick={() => setEditingShot(shot)}
                            >
                                {/* Image / Thumbnail */}
                                <div className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden">
                                    {shot.video_url ? (
                                        <video 
                                            key={shot.video_url}
                                            src={getFullUrl(shot.video_url)} 
                                            className="w-full h-full object-cover" 
                                            muted 
                                            loop
                                            playsInline
                                            poster={getFullUrl(shot.image_url)}
                                            onMouseEnter={e => e.target.play().catch(() => {})}
                                            onMouseLeave={e => { e.target.pause(); e.target.currentTime = 0; }}
                                        />
                                    ) : shot.image_url ? (
                                        <img src={getFullUrl(shot.image_url)} alt={shot.shot_name} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="flex flex-col items-center gap-2 opacity-50">
                                            <ImageIcon className="w-8 h-8" />
                                            <span className="text-xs">{t('无图片', 'No Image')}</span>
                                        </div>
                                    )}
                                    <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 pointer-events-none">
                                        {shot.shot_id}
                                    </div>
                                    {shot.video_url && (
                                        <div className="absolute top-2 right-2 bg-black/60 p-1.5 rounded-full text-white border border-white/10 pointer-events-none">
                                            <Video className="w-3 h-3" />
                                        </div>
                                    )}
                                    <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold pointer-events-none">
                                        {shot.duration || '0s'}
                                    </div>
                                </div>
                                
                                {/* Info - Simplified */}
                                <div className="p-3">
                                    <div className="flex justify-between items-center">
                                        <h3 className="font-bold text-sm text-white line-clamp-2" title={shot.shot_name}>
                                            <span className="text-primary mr-2 font-mono">{shot.shot_id}</span>
                                            {shot.shot_name || t('未命名', 'Untitled')}
                                        </h3>
                                        {/* Optional: Show duration if available, keep it minimal */}
                                        {shot.duration && (
                                            <span className="text-[10px] text-muted-foreground bg-white/5 px-1.5 py-0.5 rounded ml-2 whitespace-nowrap">
                                                {shot.duration}
                                            </span>
                                        )}
                                    </div>
                                    
                                    {/* Display Shot Logic (CN) Preview */}
                                    {shot.shot_logic_cn && (
                                        <div className="mt-2 text-xs text-muted-foreground bg-white/5 p-2 rounded line-clamp-3 overflow-hidden text-ellipsis">
                                            {shot.shot_logic_cn}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {shots.length === 0 && (
                            <div className="col-span-full h-64 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-white/10 rounded-xl">
                                <Film className="w-12 h-12 mb-4 opacity-20" />
                                <p>{t('该场景暂无镜头。', 'No shots in this scene.')}</p>
                                <button className="text-primary text-sm hover:underline mt-2" onClick={() => setIsImportOpen(true)}>{t('导入镜头表', 'Import Shots Table')}</button>
                            </div>
                        )}
                     </div>
                 ) : (
                     <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                         <Clapperboard className="w-16 h-16 mb-4 opacity-20" />
                         <p className="text-lg font-medium">{t('选择一个场景来管理镜头', 'Select a Scene to manage shots')}</p>
                         <p className="text-sm opacity-50 max-w-md text-center mt-2">
                            Available scenes are loaded from the database. <br/>
                            If your list is empty, make sure you have created scenes in the "Scenes" tab.
                         </p>
                     </div>
                 )}
             </div>

             {/* Import Modal */}
             <ImportModal 
                isOpen={isImportOpen} 
                onClose={() => setIsImportOpen(false)} 
                onImport={handleImport}
                     defaultType="shot"
                     uiLang={uiLang}
             />

             {/* Media Modals */}
             {viewMedia && <MediaDetailModal media={viewMedia} onClose={() => setViewMedia(null)} />}
             <MediaPickerModal 
                isOpen={pickerConfig.isOpen} 
                onClose={() => setPickerConfig({ ...pickerConfig, isOpen: false })} 
                onSelect={handleMediaSelect} 
                projectId={projectId}
                context={pickerConfig.context}
                entities={entities}
                episodeId={activeEpisode?.id}
                uiLang={uiLang}
            />

             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (
                    <motion.div 
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        className="absolute top-0 right-0 w-full h-full bg-[#09090b] border-l border-white/10 z-50 overflow-y-auto shadow-2xl flex flex-col"
                    >
                        {/* Notification Toast for Edit Shot */}
                        {notification && (
                            <div className={`fixed top-4 left-1/2 transform -translate-x-1/2 z-[200] px-6 py-3 rounded-lg shadow-2xl border font-bold flex items-center gap-2 animate-in slide-in-from-top-4 fade-in duration-300 ${
                                notification.type === 'success' ? 'bg-green-500/90 text-white border-green-400' : 'bg-red-500/90 text-white border-red-400'
                            }`}>
                                {notification.type === 'success' ? <CheckCircle size={18} /> : <Info size={18} />}
                                {notification.message}
                            </div>
                        )}

                        <div className="p-4 border-b border-white/10 flex items-center justify-between sticky top-0 bg-[#09090b] z-10">
                            <h3 className="font-bold text-lg flex items-center gap-2">
                                {t('编辑镜头', 'Edit Shot')} {editingShot.shot_id}
                                {editingShot.shot_name && <span className="text-base font-normal text-muted-foreground">- {editingShot.shot_name}</span>}
                            </h3>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => {
                                        const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
                                        window.location.assign(`/settings?tab=api-settings&return_to=${returnTo}`);
                                    }}
                                    className="p-2 hover:bg-white/10 text-white rounded-lg border border-white/10 transition-colors"
                                    title={t('打开生成设置', 'Open Generation Settings')}
                                >
                                    <SettingsIcon className="w-5 h-5" />
                                </button>
                                <button onClick={() => setEditingShot(null)} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                            </div>
                        </div>
                        <div className="p-6 space-y-6">

                            <div>
                                <label className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">{t('镜头逻辑（中文）', 'Shot Logic (CN)')}</label>
                                <textarea 
                                    className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs text-white/80 h-20 focus:outline-none focus:border-primary/50"
                                    value={editingShot.shot_logic_cn || ''}
                                    onChange={(e) => setEditingShot({...editingShot, shot_logic_cn: e.target.value})}
                                    placeholder={t('镜头逻辑描述（中文）...', 'Shot logic description (Chinese)...')}
                                />
                            </div>
                            
                            {/* 1. Workflow / Media Assets */}
                            <div className="space-y-6">
                                
                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-3 gap-4">
                                    {/* Start Frame */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('起始帧', 'Start Frame')}
                                                <span className={`text-[9px] px-1.5 py-0.5 rounded border font-mono normal-case ${sourceBadgeClass(activeSources.Image)}`}>
                                                    {t('来源', 'Source')}: {sourceBadgeText(activeSources.Image)}
                                                </span>
                                            </div>
                                            <div className="flex gap-1">
                                                <button
                                                    onClick={() => openAssetDetailModal('start')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={async () => {
                                                        openMediaPicker(async (url) => {
                                                            const newData = { image_url: url };
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            // Auto-save user selection to ensure it counts as "latest selected"
                                                            await onUpdateShot(editingShot.id, newData);
                                                            onLog?.('Start Frame Image set', 'success');
                                                        }, { shotId: editingShot.id });
                                                    }}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1"
                                                >
                                                    <ImageIcon className="w-3 h-3"/> {t('设置', 'Set')}
                                                </button>
                                                {currentGeneratingState.start ? (
                                                    <button 
                                                        onClick={() => abortGenerationRef.current = true}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title={t('停止重试循环', 'Stop Retry Loop')}
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        {t('停止', 'Stop')}
                                                    </button>
                                                ) : (
                                                    <>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('start', 'zh')} 
                                                            className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
                                                        >
                                                            <Wand2 className="w-3 h-3"/>
                                                            Gen(CN)
                                                        </button>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('start', 'en')} 
                                                            className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-sky-500/20 text-sky-300 hover:bg-sky-500/30"
                                                        >
                                                            <Wand2 className="w-3 h-3"/>
                                                            Gen(EN)
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        <div className="aspect-video bg-black/40 rounded border border-white/10 relative group overflow-hidden cursor-pointer" onClick={() => openAssetDetailModal('start')}>
                                            {currentGeneratingState.start && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">{t('正在生成图片...', 'Generating Image...')}</span>
                                                </div>
                                            )}
                                            {editingShot.image_url ? (
                                                <>
                                                    <img 
                                                        src={getFullUrl(editingShot.image_url)} 
                                                        className="w-full h-full object-cover cursor-pointer hover:opacity-90 transition-opacity" 
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            openAssetDetailModal('start');
                                                        }}
                                                        alt={t('起始帧', 'Start Frame')}
                                                    />
                                                    <button 
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
                                                            if(!await confirmUiMessage("Delete Start Frame image?")) return;
                                                            const newData = { image_url: "" };
                                                            await onUpdateShot(editingShot.id, newData);
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            onLog?.('Start Frame Image removed', 'info');
                                                        }}
                                                        className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20"
                                                        title={t('删除起始帧', 'Delete Start Frame')}
                                                    >
                                                        <Trash2 className="w-3 h-3"/>
                                                    </button>
                                                </>
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>
                                            )}
                                        </div>
                                        <textarea
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder={t('起始帧提示词...', 'Start Frame Prompt...')}
                                            value={editingShot.start_frame || ''} 
                                            onChange={(e) => setEditingShot({...editingShot, start_frame: e.target.value})}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} 
                                            title={t('参考图（起始帧）', 'Refs (Start)')}
                                            promptText={editingShot.start_frame || ''}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="ref_image_urls"
                                            strictPromptOnly={true}
                                            additionalAutoRefs={(() => {
                                                if (!isStartFrameInheritPrompt(editingShot.start_frame || '')) {
                                                    return [];
                                                }
                                                // Find previous shot's End Frame (Automatic)
                                                // Kept for backward compatibility or auto-suggestion
                                                const idx = shots.findIndex(s => s.id === editingShot.id);
                                                if (idx > 0) {
                                                     try {
                                                         const prev = shots[idx-1];
                                                         const t = JSON.parse(prev.technical_notes || '{}');
                                                         return t.end_frame_url ? [t.end_frame_url] : [];
                                                     } catch(e) { return []; }
                                                }
                                                return [];
                                            })()}
                                            onFindPrevFrame={() => {
                                                // Logic to find PREVIOUS shot end frame
                                                const idx = shots.findIndex(s => s.id === editingShot.id);
                                                if (idx > 0) {
                                                    try {
                                                        const prev = shots[idx-1];
                                                        const t = JSON.parse(prev.technical_notes || '{}');
                                                        const url = t.end_frame_url || prev.video_url || prev.image_url;
                                                        if (url) {
                                                            onLog?.("Found previous shot frame: " + prev.shot_id, "success");
                                                            return url;
                                                        } else {
                                                            onLog?.("Previous shot has no media.", "warning");
                                                            return null;
                                                        }
                                                    } catch(e) { return null; }
                                                } else {
                                                    onLog?.("This is the first shot.", "info");
                                                    return null;
                                                }
                                            }}
                                        />
                                    </div>


                                    {/* End Frame */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('结束帧', 'End Frame')}
                                                <span className={`text-[9px] px-1.5 py-0.5 rounded border font-mono normal-case ${sourceBadgeClass(activeSources.Image)}`}>
                                                    {t('来源', 'Source')}: {sourceBadgeText(activeSources.Image)}
                                                </span>
                                            </div>
                                            <div className="flex gap-1">
                                                <button
                                                    onClick={() => openAssetDetailModal('end')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={() => openMediaPicker((url) => {
                                                        const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                        tech.end_frame_url = url;
                                                        setEditingShot({...editingShot, technical_notes: JSON.stringify(tech)});
                                                    }, { shotId: editingShot.id })}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1"
                                                >
                                                    <ImageIcon className="w-3 h-3"/> {t('设置', 'Set')}
                                                </button>
                                                {currentGeneratingState.end ? (
                                                    <button 
                                                        onClick={() => abortGenerationRef.current = true}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title={t('停止重试循环', 'Stop Retry Loop')}
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        {t('停止', 'Stop')}
                                                    </button>
                                                ) : (
                                                    <>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('end', 'zh')} 
                                                            className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
                                                        >
                                                            <Wand2 className="w-3 h-3"/>
                                                            Gen(CN)
                                                        </button>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('end', 'en')} 
                                                            className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-sky-500/20 text-sky-300 hover:bg-sky-500/30"
                                                        >
                                                            <Wand2 className="w-3 h-3"/>
                                                            Gen(EN)
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        <div className="aspect-video bg-black/40 rounded border border-white/10 relative group overflow-hidden cursor-pointer" onClick={() => openAssetDetailModal('end')}>
                                            {currentGeneratingState.end && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">{t('正在生成结束帧...', 'Generating End Frame...')}</span>
                                                </div>
                                            )}
                                            {(() => {
                                                // Logic: If prompt words < 5, treat as empty -> show Start Frame
                                                const prompt = editingShot.end_frame || '';
                                                const wordCount = prompt.trim().split(/\s+/).filter(w => w.length > 0).length;
                                                const isSameAsStart = wordCount < 5;

                                                let endUrl = null;
                                                try { endUrl = JSON.parse(editingShot.technical_notes || '{}').end_frame_url; } catch(e){}

                                                if (isSameAsStart && editingShot.image_url) {
                                                     return (
                                                        <div className="relative w-full h-full group/mirror">
                                                            <img 
                                                                src={getFullUrl(editingShot.image_url)} 
                                                                className="w-full h-full object-cover opacity-60 group-hover/mirror:opacity-100 transition-opacity cursor-pointer"
                                                                title={t('与起始帧相同（提示词少于 5 个词）', 'Same as Start Frame (Prompt < 5 words)')}
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openAssetDetailModal('end');
                                                                }}
                                                            />
                                                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30 group-hover/mirror:opacity-0 transition-opacity">
                                                                <span className="bg-black/50 text-white text-[9px] px-2 py-1 rounded">{t('与起始帧相同', 'SAME AS START')}</span>
                                                            </div>
                                                        </div>
                                                     )
                                                }

                                                if (endUrl) {
                                                    return (
                                                        <>
                                                            <img 
                                                                src={getFullUrl(endUrl)} 
                                                                className="w-full h-full object-cover cursor-pointer hover:opacity-90 transition-opacity"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openAssetDetailModal('end');
                                                                }}
                                                            />
                                                            <button 
                                                                onClick={async (e) => {
                                                                    e.stopPropagation();
                                                                    if(!await confirmUiMessage("Delete End Frame image?")) return;
                                                                    const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                                    tech.end_frame_url = "";
                                                                    // We also track explicit deletion to avoid auto-regenerating from Start Frame immediately if user doesn't want it
                                                                    if (!tech.deleted_ref_urls) tech.deleted_ref_urls = [];
                                                                    tech.deleted_ref_urls.push(endUrl);
                                                                    
                                                                    const newData = { technical_notes: JSON.stringify(tech) };
                                                                    await onUpdateShot(editingShot.id, newData);
                                                                    setEditingShot(prev => ({...prev, ...newData}));
                                                                    onLog?.('End Frame Image removed', 'info');
                                                                }}
                                                                className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20"
                                                                title={t('删除结束帧', 'Delete End Frame')}
                                                            >
                                                                <Trash2 className="w-3 h-3"/>
                                                            </button>
                                                        </>
                                                    );
                                                }

                                                return <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>;
                                            })()}
                                        </div>
                                        
                                        <textarea
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder={t('结束帧提示词...', 'End Frame Prompt...')}
                                            value={editingShot.end_frame || ''} 
                                            onChange={(e) => setEditingShot({...editingShot, end_frame: e.target.value})}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} 
                                            title={t('参考图（结束帧）', 'Refs (End)')}
                                            promptText={editingShot.end_frame || ''}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="end_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                    </div>

                                    {/* Final Video Output (Moved Here) */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('最终视频', 'Final Video')}
                                                <span className={`text-[9px] px-1.5 py-0.5 rounded border font-mono normal-case ${sourceBadgeClass(activeSources.Video)}`}>
                                                    {t('来源', 'Source')}: {sourceBadgeText(activeSources.Video)}
                                                </span>
                                            </div>
                                            
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => openAssetDetailModal('video')}
                                                    className="bg-white/10 hover:bg-white/20 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={() => openMediaPicker((url) => {
                                                        const changes = { video_url: url };
                                                        onUpdateShot(editingShot.id, changes);
                                                    }, { type: 'video' })}
                                                    className="bg-white/10 hover:bg-white/20 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
                                                    title={t('选择或上传视频', 'Select or Upload Video')}
                                                >
                                                    <Upload size={10} /> {t('设置', 'Set')}
                                                </button>

                                                {/* Shot-specific Final Video Mode */}
                                                <select
                                                    value={(() => {
                                                        try {
                                                            const t = JSON.parse(editingShot.technical_notes || '{}');
                                                            if (t.video_mode_unified) return t.video_mode_unified;
                                                            if (t.video_ref_submit_mode === 'refs_video') return 'refs_video';
                                                            return t.video_gen_mode || 'start';
                                                        } catch(e) { return 'start'; }
                                                    })()}
                                                    onChange={(e) => {
                                                        const mode = e.target.value;
                                                        try {
                                                            const t = JSON.parse(editingShot.technical_notes || '{}');
                                                            t.video_mode_unified = mode;
                                                            if (mode === 'refs_video') {
                                                                t.video_ref_submit_mode = 'refs_video';
                                                            } else {
                                                                t.video_gen_mode = mode;
                                                                t.video_ref_submit_mode = 'auto';
                                                            }
                                                            setEditingShot(prev => ({ ...prev, technical_notes: JSON.stringify(t) }));
                                                            // Auto-save happens on blur or next action usually, but we might want to trigger update if needed
                                                            // onUpdateShot(editingShot.id, { technical_notes: JSON.stringify(t) }); // Optional: immediate save
                                                        } catch(e) {}
                                                    }}
                                                    className="bg-black/40 border border-white/20 text-[10px] rounded px-1 py-0.5 text-white/70 outline-none hover:bg-white/5"
                                                    title={t('最终视频生成模式', 'Final Video Generation Mode')}
                                                >
                                                    <option value="start_end">{t('起始+结束', 'Start+End')}</option>
                                                    <option value="start">{t('仅起始', 'Start Only')}</option>
                                                    <option value="end">{t('仅结束', 'End Only')}</option>
                                                    <option value="refs_video">{t('视频参考图模式', 'Refs (Video) As Ref')}</option>
                                                </select>

                                                <button 
                                                    onClick={() => generateAssetWithLang('video', 'zh')} 
                                                    disabled={currentGeneratingState.video}
                                                    className={`text-[10px] font-bold px-3 py-0.5 rounded flex items-center gap-1 ${currentGeneratingState.video ? 'bg-primary/50 text-black/50 cursor-wait' : 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30' }`}
                                                >
                                                    {currentGeneratingState.video ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>} 
                                                    {currentGeneratingState.video ? t('生成中...', 'Generating...') : 'Gen(CN)'}
                                                </button>
                                                <button 
                                                    onClick={() => generateAssetWithLang('video', 'en')} 
                                                    disabled={currentGeneratingState.video}
                                                    className={`text-[10px] font-bold px-3 py-0.5 rounded flex items-center gap-1 ${currentGeneratingState.video ? 'bg-primary/50 text-black/50 cursor-wait' : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500/30' }`}
                                                >
                                                    {currentGeneratingState.video ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>} 
                                                    {currentGeneratingState.video ? t('生成中...', 'Generating...') : 'Gen(EN)'}
                                                </button>
                                            </div>
                                        </div>
                                        
                                        <div 
                                            className="aspect-video bg-black/40 rounded border border-white/10 relative group overflow-hidden cursor-pointer"
                                            onClick={() => openAssetDetailModal('video')}
                                        >
                                            {currentGeneratingState.video && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">{t('正在生成视频...', 'Generating Video...')}</span>
                                                </div>
                                            )}
                                            {(editingShot.video_url) ? (
                                                <video 
                                                    key={editingShot.video_url}
                                                    src={getFullUrl(editingShot.video_url)} 
                                                    className="w-full h-full object-cover" 
                                                    onClick={(e) => e.preventDefault()} 
                                                    controls
                                                />
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20 flex-col gap-2">
                                                    <Video className="w-10 h-10"/>
                                                    <span className="text-xs">{t('暂无视频', 'No Video')}</span>
                                                </div>
                                            )}
                                             {(editingShot.video_url) && <div className="absolute inset-0 flex items-center justify-center pointer-events-none group-hover:bg-black/10"><Maximize2 className="text-white opacity-0 group-hover:opacity-100 drop-shadow-md"/></div>}
                                        </div>

                                        <textarea
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder={t('动作 / 运动提示词...', 'Action / Motion Prompt...')}
                                            value={editingShot.prompt || editingShot.video_content || ''}
                                            onChange={(e) => setEditingShot({...editingShot, prompt: e.target.value})}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} 
                                            title={t('参考图（视频）', 'Refs (Video)')}
                                            promptText={editingShot.prompt || editingShot.video_content || ''}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="video_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}
                                <div className="space-y-4 border-t border-white/10 pt-4">
                                     <div className="flex justify-between items-center">
                                        <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                            {t('关键帧（时间线）', 'Keyframes (Timeline)')}
                                            <span className="bg-white/10 text-white px-1.5 rounded-full text-[9px]">
                                                {localKeyframes.length}
                                            </span>
                                        </div>
                                        <button 
                                            onClick={() => {
                                                const newTime = `${(localKeyframes.length + 1) * 1.0}s`;
                                                const newKf = { 
                                                    id: Date.now(), 
                                                    time: newTime, 
                                                    prompt: "[Global Style] ...", 
                                                    url: "" 
                                                };
                                                const newList = [...localKeyframes, newKf];
                                                setLocalKeyframes(newList);
                                                // Trigger save logic? Maybe wait for edit?
                                                // auto-save structure
                                                // reconstructKeyframes(newList); // Optional, maybe let user edit first
                                            }}
                                            className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded flex items-center gap-1"
                                        >
                                            <Plus className="w-3 h-3"/> {t('新增关键帧', 'Add Keyframe')}
                                        </button>
                                    </div>
                                    
                                    <div className="flex gap-4 overflow-x-auto pb-4 min-h-[160px] snap-x">
                                        {localKeyframes.length === 0 && (
                                            <div className="text-xs text-muted-foreground italic p-2 w-full text-center border-dashed border border-white/10 rounded">
                                                {t('尚未定义关键帧。新增一个以开始复杂运动规划。', 'No keyframes defined. Add one to start complex motion planning.')}
                                            </div>
                                        )}
                                        {localKeyframes.map((kf, idx) => (
                                            <div key={idx} className="relative w-[280px] flex-shrink-0 bg-black/20 rounded border border-white/10 p-2 space-y-2 snap-center group">
                                                {/* Header */}
                                                <div className="flex justify-between items-center text-[10px]">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-muted-foreground font-bold">T=</span>
                                                        <input 
                                                            className="bg-transparent border-b border-white/10 w-12 text-center focus:border-primary outline-none text-white"
                                                            value={kf.time}
                                                            onChange={(e) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].time = e.target.value;
                                                                setLocalKeyframes(updated);
                                                            }}
                                                            onBlur={() => reconstructKeyframes(localKeyframes)}
                                                        />
                                                    </div>
                                                    <div className="flex gap-1">
                                                        <button
                                                            onClick={() => openAssetDetailModal('keyframe', idx)}
                                                            className="px-1.5 py-0.5 bg-white/10 hover:bg-white/20 text-white rounded"
                                                        >
                                                            {t('详情', 'Detail')}
                                                        </button>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('keyframe', 'zh', idx)} 
                                                            className="px-1.5 py-0.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 rounded flex items-center gap-1"
                                                            disabled={kf.loading}
                                                        >
                                                            {kf.loading ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                            Gen(CN)
                                                        </button>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('keyframe', 'en', idx)} 
                                                            className="px-1.5 py-0.5 bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 rounded flex items-center gap-1"
                                                            disabled={kf.loading}
                                                        >
                                                            {kf.loading ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                            Gen(EN)
                                                        </button>
                                                        <button 
                                                            onClick={() => {
                                                                const updated = [...localKeyframes];
                                                                updated.splice(idx, 1);
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }}
                                                            className="p-1 hover:bg-red-500/20 text-muted-foreground hover:text-red-500 rounded transition-colors"
                                                        >
                                                            <Trash2 className="w-3 h-3"/>
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Image Area */}
                                                <div className="aspect-video bg-black/40 rounded border border-white/10 relative overflow-hidden group/image cursor-pointer" onClick={() => openAssetDetailModal('keyframe', idx)}>
                                                    {kf.url ? (
                                                        <>
                                                            <img 
                                                                src={getFullUrl(kf.url)} 
                                                                className="w-full h-full object-cover cursor-pointer hover:opacity-90"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openAssetDetailModal('keyframe', idx);
                                                                }}
                                                            />
                                                            <button 
                                                                onClick={async (e) => {
                                                                    e.stopPropagation();
                                                                    if(!await confirmUiMessage("Remove image?")) return;
                                                                    const updated = [...localKeyframes];
                                                                    updated[idx].url = "";
                                                                    setLocalKeyframes(updated);
                                                                    reconstructKeyframes(updated);
                                                                }}
                                                                className="absolute top-1 right-1 bg-black/60 text-white p-1 rounded opacity-0 group-hover/image:opacity-100 transition-opacity"
                                                            >
                                                                <Trash2 className="w-3 h-3"/>
                                                            </button>
                                                        </>
                                                    ) : (
                                                        <div className="absolute inset-0 flex items-center justify-center opacity-20">
                                                            <ImageIcon className="w-6 h-6"/>
                                                        </div>
                                                    )}
                                                    
                                                    {/* Quick Set Button Overlay */}
                                                    <div className="absolute bottom-1 right-1 opacity-0 group-hover/image:opacity-100 transition-opacity">
                                                        <button 
                                                            onClick={() => openMediaPicker((url) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].url = url;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            })}
                                                            className="bg-black/60 hover:bg-white/20 text-white text-[9px] px-1.5 py-0.5 rounded flex items-center gap-1 backdrop-blur-sm"
                                                        >
                                                            <Upload className="w-2.5 h-2.5"/> Set
                                                        </button>
                                                    </div>

                                                    {kf.loading && (
                                                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-10">
                                                            <Loader2 className="w-5 h-5 animate-spin text-primary"/>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Prompt Area */}
                                                <textarea 
                                                    className="w-full bg-black/20 border border-white/10 rounded p-1.5 text-[10px] h-[60px] focus:border-primary/50 outline-none resize-none"
                                                    placeholder={t('关键帧描述...', 'Keyframe Description...')}
                                                    value={kf.prompt}
                                                    onChange={(e) => {
                                                        const updated = [...localKeyframes];
                                                        updated[idx].prompt = e.target.value;
                                                        setLocalKeyframes(updated);
                                                    }}
                                                    onBlur={() => reconstructKeyframes(localKeyframes)}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>


                                {/* Video Result - REMOVED from here, moved up */}
                            </div>


                            {/* 3. Associated Entities */}
                            <div className="space-y-3 pt-4 border-t border-white/10">
                                <h4 className="text-sm font-bold text-primary flex items-center gap-2"><Users className="w-4 h-4"/> Associated Entities</h4>
                                <div className="bg-black/20 border border-white/10 rounded-xl p-4 flex gap-4 overflow-x-auto min-h-[100px] items-center">
                                    {(() => {
                                        const cleanName = (s) => String(s || '')
                                            .replace(/[\[\]【】"''“”‘’]/g, '')
                                            .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
                                            .replace(/^@+/, '')
                                            .trim();
                                        const normalizeForMatch = (s) => cleanName(s)
                                            .replace(/[_\-]+/g, ' ')
                                            .replace(/\s+/g, ' ')
                                            .trim()
                                            .toLowerCase();
                                        const rawNames = (editingShot.associated_entities || '').split(/[,，]/);
                                        const names = rawNames.map(cleanName).filter(Boolean);
                                        const normalizedNames = names.map(normalizeForMatch).filter(Boolean);
                                        
                                        // Match entity names (English or Chinese)
                                        const matches = entities.filter(e => normalizedNames.some(n => {
                                            const cn = normalizeForMatch(e.name || '');
                                            let en = normalizeForMatch(e.name_en || '');

                                            // Fallback: Try to extract English name from description if name_en is empty
                                            if (!en && e.description) {
                                                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                                if (enMatch && enMatch[1]) {
                                                    const complexEn = enMatch[1].trim();
                                                    en = normalizeForMatch(complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0]); 
                                                }
                                            }

                                            // Exact match check first for better precision
                                            if (cn === n || en === n) return true;
                                            
                                            // Check CN name match (both directions)
                                            if (cn && (cn.includes(n) || n.includes(cn))) return true;
                                            // Check EN name match (both directions)
                                            if (en && (en.includes(n) || n.includes(en))) return true;
                                            return false;
                                        }));

                                        // New Feature: Scene Environment Matching
                                        // Attempt to find current scene environment/location and add to matches if not already there
                                        let envMatches = [];
                                        if (selectedSceneId && selectedSceneId !== 'all') {
                                            // Find current scene from user selection
                                            const currentScene = scenes.find(s => s.id == selectedSceneId);
                                            if (currentScene) {
                                                // Extract location from scene (e.g., "[废弃展区内部 (主视角)]")
                                                // Clean brackets like [ ]
                                                const rawLoc = cleanName((currentScene.location || currentScene.environment_name || '').replace(/[\[\]]/g, ''));
                                                const rawLocNorm = normalizeForMatch(rawLoc);
                                                
                                                if (rawLocNorm) {
                                                    // console.log("Matching Env:", rawLoc);
                                                    const envs = entities.filter(e => {
                                                        // Filter for Environment type entities primarily, but allow others
                                                        // if (e.type !== 'environment') return false; 
                                                        
                                                        const cn = normalizeForMatch(e.name || '');
                                                        let en = normalizeForMatch(e.name_en || '');
                                                        // Fallback EN extract
                                                        if (!en && e.description) {
                                                            const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                                            if (enMatch && enMatch[1]) en = normalizeForMatch(enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0]); 
                                                        }

                                                        // Use looser matching for descriptions/anchors
                                                        // Is the Location string contained in Entity Name? or vice versa?
                                                        if (cn && (cn.includes(rawLocNorm) || rawLocNorm.includes(cn))) return true;
                                                        if (en && (en.includes(rawLocNorm) || rawLocNorm.includes(en))) return true;
                                                        
                                                        return false;
                                                    });
                                                    // console.log("Found Envs:", envs);
                                                    envMatches = envs.filter(env => !matches.find(m => m.id === env.id)); // Dedup
                                                }
                                            }
                                        }

                                        const allMatches = [...matches, ...envMatches];
                                        
                                        if (allMatches.length === 0) return (
                                            <div className="text-xs text-muted-foreground w-full text-center break-words p-2">
                                                No entities matched tags: "{names.join(', ')}". 
                                                <br/>
                                                <span className="opacity-50 text-[10px] block mt-1">
                                                    Available({entities.length}): {entities.map(e => `${e.name}${e.name_en ? `/${e.name_en}` : ''}`).slice(0, 15).join(', ')}
                                                </span>
                                            </div>
                                        );
                                        
                                        return allMatches.map((e, idx) => (
                                            <div key={e.id} className="flex flex-col items-center gap-2 min-w-[70px]">
                                                <div className="w-14 h-14 rounded-full overflow-hidden border border-white/20 bg-black/50 relative">
                                                    {e.image_url ? <img src={getFullUrl(e.image_url)} className="w-full h-full object-cover" /> : <Users className="w-6 h-6 m-auto absolute inset-0 text-muted-foreground opacity-50"/>}
                                                </div>
                                                <span className="text-[10px] text-center line-clamp-1 w-full opacity-80">{e.name}</span>
                                            </div>
                                        ));
                                    })()}
                                </div>
                                {/* Association Tags Input Removed as requested */}
                            </div>

                            {/* Metadata */}
                            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/10 text-xs text-muted-foreground">
                                <InputGroup label="Shot Number" value={editingShot.shot_id} onChange={(v) => { setEditingShot({...editingShot, shot_id: v}) }} />
                                <InputGroup label="Duration (s)" value={editingShot.duration} onChange={v => setEditingShot({...editingShot, duration: v})} />
                            </div>

                            <button 
                                onClick={async () => {
                                    try {
                                        await updateShot(editingShot.id, editingShot);
                                        setShots(shots.map(s => s.id === editingShot.id ? editingShot : s));
                                        setEditingShot(null);
                                        onLog?.("Shot updated.", "success");
                                    } catch(e) {
                                        onLog?.("Update failed.", "error");
                                    }
                                }}
                                className="w-full py-4 bg-primary text-black font-bold rounded-lg hover:bg-primary/90 mt-4"
                            >
                                Save Changes
                            </button>

                            {assetDetailModal.open && (
                                <div className="fixed inset-0 z-[120] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
                                    <div className="w-full max-w-7xl h-[94vh] bg-[#09090b] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden">
                                        <div className="p-4 border-b border-white/10 flex items-center justify-between">
                                            <h4 className="font-bold text-white flex items-center gap-2">
                                                <Info className="w-4 h-4 text-primary" />
                                                {assetDetailModal.type === 'start' && t('起始帧详情', 'Start Frame Detail')}
                                                {assetDetailModal.type === 'end' && t('结束帧详情', 'End Frame Detail')}
                                                {assetDetailModal.type === 'video' && t('视频详情', 'Video Detail')}
                                                {assetDetailModal.type === 'keyframe' && t('关键帧详情', 'Keyframe Detail')}
                                            </h4>
                                            <button onClick={closeAssetDetailModal} className="p-2 hover:bg-white/10 rounded-full"><X className="w-4 h-4"/></button>
                                        </div>

                                        <div className="flex-1 overflow-auto p-4">
                                            {(() => {
                                                let tech = {};
                                                try { tech = JSON.parse(editingShot.technical_notes || '{}'); } catch (e) {}
                                                const updateTechField = (key, value) => {
                                                    const nextTech = { ...tech, [key]: value };
                                                    setEditingShot(prev => ({ ...(prev || {}), technical_notes: JSON.stringify(nextTech) }));
                                                };
                                                const modalType = assetDetailModal.type;
                                                const keyframe = modalType === 'keyframe' ? localKeyframes[assetDetailModal.keyframeIndex] : null;

                                                if (modalType === 'start') {
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                            <div className="space-y-3">
                                                                <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex items-center justify-center">
                                                                    {editingShot.image_url ? <img src={getFullUrl(editingShot.image_url)} className="w-full h-full object-cover"/> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('图片 URL', 'Image URL')}: {editingShot.image_url || '-'}</div>
                                                                <div className="text-xs text-muted-foreground">{t('参考图数量', 'Ref Count')}: {(Array.isArray(tech.ref_image_urls) ? tech.ref_image_urls.length : 0)}</div>
                                                            </div>
                                                            <div className="space-y-3">
                                                                <div className="flex items-center gap-2">
                                                                    <TranslateControl text={editingShot.start_frame || ''} onUpdate={(v) => setEditingShot({...editingShot, start_frame: v})} />
                                                                    <button onClick={() => generateAssetWithLang('start', 'zh')} className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30">Gen(CN)</button>
                                                                    <button onClick={() => generateAssetWithLang('start', 'en')} className="text-xs px-2 py-1 rounded bg-sky-500/20 text-sky-300 hover:bg-sky-500/30">Gen(EN)</button>
                                                                </div>
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('英文提示词', 'Prompt (EN)')}</div>
                                                                    <button
                                                                        onClick={() => runDetailTranslate({
                                                                            text: tech.start_frame_cn || '',
                                                                            from: 'zh',
                                                                            to: 'en',
                                                                            loadingKey: 'start_cn2en',
                                                                            onResult: (v) => overwriteShotField('start_frame', v),
                                                                        })}
                                                                        disabled={!!detailTranslateLoading.start_cn2en}
                                                                        className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                    >
                                                                        {detailTranslateLoading.start_cn2en ? t('翻译中...', 'Translating...') : t('中→英', 'CN→EN')}
                                                                    </button>
                                                                </div>
                                                                <textarea className="w-full h-48 bg-black/30 border border-white/10 rounded p-2 text-sm" value={editingShot.start_frame || ''} onChange={(e) => setEditingShot({...editingShot, start_frame: e.target.value})} />
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('中文对照提示词', 'Prompt (CN)')}</div>
                                                                    <button
                                                                        onClick={() => runDetailTranslate({
                                                                            text: editingShot.start_frame || '',
                                                                            from: 'en',
                                                                            to: 'zh',
                                                                            loadingKey: 'start_en2cn',
                                                                            onResult: (v) => overwriteTechField('start_frame_cn', v),
                                                                        })}
                                                                        disabled={!!detailTranslateLoading.start_en2cn}
                                                                        className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                    >
                                                                        {detailTranslateLoading.start_en2cn ? t('翻译中...', 'Translating...') : t('英→中', 'EN→CN')}
                                                                    </button>
                                                                </div>
                                                                <textarea
                                                                    className="w-full h-40 bg-black/30 border border-white/10 rounded p-2 text-sm"
                                                                    value={tech.start_frame_cn || ''}
                                                                    onChange={(e) => updateTechField('start_frame_cn', e.target.value)}
                                                                    placeholder={t('填写起始帧中文对照提示词...', 'Add Chinese counterpart prompt for start frame...')}
                                                                />
                                                                <RefineControl originalText={editingShot.start_frame || ''} onUpdate={(v) => setEditingShot({...editingShot, start_frame: v})} type="image" currentImage={editingShot.image_url} onImageUpdate={async (url) => {
                                                                    const newData = { image_url: url };
                                                                    await onUpdateShot(editingShot.id, newData);
                                                                    setEditingShot(prev => ({...prev, ...newData}));
                                                                }} projectId={projectId} shotId={editingShot.id} assetType="start_frame" featureInjector={injectEntityFeatures} onPickMedia={openMediaPicker} />
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} title={t('参考图（起始帧）', 'Refs (Start)')} promptText={editingShot.start_frame || ''} uiLang={uiLang} onPickMedia={openMediaPicker} storageKey="ref_image_urls" strictPromptOnly={true} />
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                if (modalType === 'end') {
                                                    const endFrameUrl = tech.end_frame_url || '';
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                            <div className="space-y-3">
                                                                <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex items-center justify-center">
                                                                    {endFrameUrl ? <img src={getFullUrl(endFrameUrl)} className="w-full h-full object-cover"/> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('结束帧 URL', 'End Frame URL')}: {endFrameUrl || '-'}</div>
                                                                <div className="text-xs text-muted-foreground">{t('参考图数量', 'Ref Count')}: {(Array.isArray(tech.end_ref_image_urls) ? tech.end_ref_image_urls.length : 0)}</div>
                                                            </div>
                                                            <div className="space-y-3">
                                                                <div className="flex items-center gap-2">
                                                                    <TranslateControl text={editingShot.end_frame || ''} onUpdate={(v) => setEditingShot({...editingShot, end_frame: v})} />
                                                                    <button onClick={() => generateAssetWithLang('end', 'zh')} className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30">Gen(CN)</button>
                                                                    <button onClick={() => generateAssetWithLang('end', 'en')} className="text-xs px-2 py-1 rounded bg-sky-500/20 text-sky-300 hover:bg-sky-500/30">Gen(EN)</button>
                                                                </div>
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('英文提示词', 'Prompt (EN)')}</div>
                                                                    <button
                                                                        onClick={() => runDetailTranslate({
                                                                            text: tech.end_frame_cn || '',
                                                                            from: 'zh',
                                                                            to: 'en',
                                                                            loadingKey: 'end_cn2en',
                                                                            onResult: (v) => overwriteShotField('end_frame', v),
                                                                        })}
                                                                        disabled={!!detailTranslateLoading.end_cn2en}
                                                                        className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                    >
                                                                        {detailTranslateLoading.end_cn2en ? t('翻译中...', 'Translating...') : t('中→英', 'CN→EN')}
                                                                    </button>
                                                                </div>
                                                                <textarea className="w-full h-48 bg-black/30 border border-white/10 rounded p-2 text-sm" value={editingShot.end_frame || ''} onChange={(e) => setEditingShot({...editingShot, end_frame: e.target.value})} />
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('中文对照提示词', 'Prompt (CN)')}</div>
                                                                    <button
                                                                        onClick={() => runDetailTranslate({
                                                                            text: editingShot.end_frame || '',
                                                                            from: 'en',
                                                                            to: 'zh',
                                                                            loadingKey: 'end_en2cn',
                                                                            onResult: (v) => overwriteTechField('end_frame_cn', v),
                                                                        })}
                                                                        disabled={!!detailTranslateLoading.end_en2cn}
                                                                        className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                    >
                                                                        {detailTranslateLoading.end_en2cn ? t('翻译中...', 'Translating...') : t('英→中', 'EN→CN')}
                                                                    </button>
                                                                </div>
                                                                <textarea
                                                                    className="w-full h-40 bg-black/30 border border-white/10 rounded p-2 text-sm"
                                                                    value={tech.end_frame_cn || ''}
                                                                    onChange={(e) => updateTechField('end_frame_cn', e.target.value)}
                                                                    placeholder={t('填写结束帧中文对照提示词...', 'Add Chinese counterpart prompt for end frame...')}
                                                                />
                                                                <RefineControl originalText={editingShot.end_frame || ''} onUpdate={(v) => setEditingShot({...editingShot, end_frame: v})} type="image" currentImage={endFrameUrl} onImageUpdate={async (url) => {
                                                                    const nextTech = { ...tech, end_frame_url: url, video_gen_mode: 'start_end' };
                                                                    const newData = { technical_notes: JSON.stringify(nextTech) };
                                                                    await onUpdateShot(editingShot.id, newData);
                                                                    setEditingShot(prev => ({...prev, ...newData}));
                                                                }} projectId={projectId} shotId={editingShot.id} assetType="end_frame" featureInjector={injectEntityFeatures} onPickMedia={openMediaPicker} />
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} title={t('参考图（结束帧）', 'Refs (End)')} promptText={editingShot.end_frame || ''} uiLang={uiLang} onPickMedia={openMediaPicker} storageKey="end_ref_image_urls" strictPromptOnly={true} />
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                if (modalType === 'video') {
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                            <div className="space-y-3">
                                                                <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex items-center justify-center">
                                                                    {editingShot.video_url ? <video src={getFullUrl(editingShot.video_url)} controls className="w-full h-full object-cover" /> : <Video className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('视频 URL', 'Video URL')}: {editingShot.video_url || '-'}</div>
                                                                <div className="text-xs text-muted-foreground">{t('时长', 'Duration')}: {editingShot.duration || '5'}</div>
                                                                <div className="text-xs text-muted-foreground">{t('模式', 'Mode')}: {tech.video_mode_unified || tech.video_gen_mode || 'start'}</div>
                                                            </div>
                                                            <div className="space-y-3">
                                                                <div className="flex items-center gap-2">
                                                                    <TranslateControl text={editingShot.prompt || editingShot.video_content || ''} onUpdate={(v) => setEditingShot({...editingShot, prompt: v})} />
                                                                    <button onClick={() => generateAssetWithLang('video', 'zh')} className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30">Gen(CN)</button>
                                                                    <button onClick={() => generateAssetWithLang('video', 'en')} className="text-xs px-2 py-1 rounded bg-sky-500/20 text-sky-300 hover:bg-sky-500/30">Gen(EN)</button>
                                                                </div>
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('英文提示词', 'Prompt (EN)')}</div>
                                                                    <button
                                                                        onClick={() => runDetailTranslate({
                                                                            text: tech.video_prompt_cn || '',
                                                                            from: 'zh',
                                                                            to: 'en',
                                                                            loadingKey: 'video_cn2en',
                                                                            onResult: (v) => overwriteShotField('prompt', v, { video_content: '' }),
                                                                        })}
                                                                        disabled={!!detailTranslateLoading.video_cn2en}
                                                                        className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                    >
                                                                        {detailTranslateLoading.video_cn2en ? t('翻译中...', 'Translating...') : t('中→英', 'CN→EN')}
                                                                    </button>
                                                                </div>
                                                                <textarea className="w-full h-48 bg-black/30 border border-white/10 rounded p-2 text-sm" value={editingShot.prompt || editingShot.video_content || ''} onChange={(e) => setEditingShot({...editingShot, prompt: e.target.value})} />
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('中文对照提示词', 'Prompt (CN)')}</div>
                                                                    <button
                                                                        onClick={() => runDetailTranslate({
                                                                            text: editingShot.prompt || editingShot.video_content || '',
                                                                            from: 'en',
                                                                            to: 'zh',
                                                                            loadingKey: 'video_en2cn',
                                                                            onResult: (v) => overwriteTechField('video_prompt_cn', v),
                                                                        })}
                                                                        disabled={!!detailTranslateLoading.video_en2cn}
                                                                        className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                    >
                                                                        {detailTranslateLoading.video_en2cn ? t('翻译中...', 'Translating...') : t('英→中', 'EN→CN')}
                                                                    </button>
                                                                </div>
                                                                <textarea
                                                                    className="w-full h-40 bg-black/30 border border-white/10 rounded p-2 text-sm"
                                                                    value={tech.video_prompt_cn || ''}
                                                                    onChange={(e) => updateTechField('video_prompt_cn', e.target.value)}
                                                                    placeholder={t('填写视频中文对照提示词...', 'Add Chinese counterpart prompt for video...')}
                                                                />
                                                                <RefineControl originalText={editingShot.prompt || editingShot.video_content || ''} onUpdate={(v) => setEditingShot({...editingShot, prompt: v})} type="video" />
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} title={t('参考图（视频）', 'Refs (Video)')} promptText={editingShot.prompt || editingShot.video_content || ''} uiLang={uiLang} onPickMedia={openMediaPicker} storageKey="video_ref_image_urls" strictPromptOnly={true} />
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                return (
                                                    <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                        <div className="space-y-3">
                                                            <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex items-center justify-center">
                                                                {keyframe?.url ? <img src={getFullUrl(keyframe.url)} className="w-full h-full object-cover"/> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                            </div>
                                                            <div className="text-xs text-muted-foreground break-all">{t('关键帧 URL', 'Keyframe URL')}: {keyframe?.url || '-'}</div>
                                                        </div>
                                                        <div className="space-y-3">
                                                            <div className="flex items-center gap-2">
                                                                <input className="bg-black/30 border border-white/10 rounded px-2 py-1 text-xs w-20" value={keyframe?.time || ''} onChange={(e) => {
                                                                    const updated = [...localKeyframes];
                                                                    if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                    updated[assetDetailModal.keyframeIndex].time = e.target.value;
                                                                    setLocalKeyframes(updated);
                                                                }} />
                                                                <TranslateControl text={keyframe?.prompt || ''} onUpdate={(v) => {
                                                                    const updated = [...localKeyframes];
                                                                    if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                    updated[assetDetailModal.keyframeIndex].prompt = v;
                                                                    setLocalKeyframes(updated);
                                                                }} />
                                                                <button onClick={() => generateAssetWithLang('keyframe', 'zh', assetDetailModal.keyframeIndex)} className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30">Gen(CN)</button>
                                                                <button onClick={() => generateAssetWithLang('keyframe', 'en', assetDetailModal.keyframeIndex)} className="text-xs px-2 py-1 rounded bg-sky-500/20 text-sky-300 hover:bg-sky-500/30">Gen(EN)</button>
                                                            </div>
                                                            <div className="flex items-center justify-between">
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('英文提示词', 'Prompt (EN)')}</div>
                                                                <button
                                                                    onClick={() => runDetailTranslate({
                                                                        text: (tech.keyframe_prompt_cn_map && keyframe?.time) ? (tech.keyframe_prompt_cn_map[keyframe.time] || '') : '',
                                                                        from: 'zh',
                                                                        to: 'en',
                                                                        loadingKey: `kf_cn2en_${assetDetailModal.keyframeIndex}`,
                                                                        onResult: (v) => {
                                                                            const updated = [...localKeyframes];
                                                                            if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                            updated[assetDetailModal.keyframeIndex].prompt = v;
                                                                            setLocalKeyframes(updated);
                                                                        },
                                                                    })}
                                                                    disabled={!!detailTranslateLoading[`kf_cn2en_${assetDetailModal.keyframeIndex}`]}
                                                                    className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                >
                                                                    {detailTranslateLoading[`kf_cn2en_${assetDetailModal.keyframeIndex}`] ? t('翻译中...', 'Translating...') : t('中→英', 'CN→EN')}
                                                                </button>
                                                            </div>
                                                            <textarea className="w-full h-48 bg-black/30 border border-white/10 rounded p-2 text-sm" value={keyframe?.prompt || ''} onChange={(e) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].prompt = e.target.value;
                                                                setLocalKeyframes(updated);
                                                            }} />
                                                            <div className="flex items-center justify-between">
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('中文对照提示词', 'Prompt (CN)')}</div>
                                                                <button
                                                                    onClick={() => runDetailTranslate({
                                                                        text: keyframe?.prompt || '',
                                                                        from: 'en',
                                                                        to: 'zh',
                                                                        loadingKey: `kf_en2cn_${assetDetailModal.keyframeIndex}`,
                                                                        onResult: (v) => overwriteKeyframeCnMap(keyframe?.time, v),
                                                                    })}
                                                                    disabled={!!detailTranslateLoading[`kf_en2cn_${assetDetailModal.keyframeIndex}`]}
                                                                    className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/80"
                                                                >
                                                                    {detailTranslateLoading[`kf_en2cn_${assetDetailModal.keyframeIndex}`] ? t('翻译中...', 'Translating...') : t('英→中', 'EN→CN')}
                                                                </button>
                                                            </div>
                                                            <textarea
                                                                className="w-full h-40 bg-black/30 border border-white/10 rounded p-2 text-sm"
                                                                value={(tech.keyframe_prompt_cn_map && keyframe?.time) ? (tech.keyframe_prompt_cn_map[keyframe.time] || '') : ''}
                                                                onChange={(e) => {
                                                                    const nextMap = { ...(tech.keyframe_prompt_cn_map || {}) };
                                                                    if (keyframe?.time) nextMap[keyframe.time] = e.target.value;
                                                                    updateTechField('keyframe_prompt_cn_map', nextMap);
                                                                }}
                                                                placeholder={t('填写关键帧中文对照提示词...', 'Add Chinese counterpart prompt for keyframe...')}
                                                            />
                                                            <RefineControl originalText={keyframe?.prompt || ''} onUpdate={(v) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].prompt = v;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }} type="image" currentImage={keyframe?.url || ''} onImageUpdate={(url) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].url = url;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }} projectId={projectId} shotId={editingShot.id} assetType={`keyframe_${assetDetailModal.keyframeIndex}`} featureInjector={injectEntityFeatures} onPickMedia={openMediaPicker} />
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>

                                        <div className="p-4 border-t border-white/10 flex items-center justify-end gap-2 bg-black/20">
                                            <button onClick={closeAssetDetailModal} className="px-4 py-2 rounded hover:bg-white/10 text-sm">{t('关闭', 'Close')}</button>
                                            <button
                                                onClick={async () => {
                                                    try {
                                                        if (assetDetailModal.type === 'keyframe') {
                                                            await reconstructKeyframes(localKeyframes);
                                                        } else {
                                                            await onUpdateShot(editingShot.id, editingShot);
                                                        }
                                                        onLog?.(t('详情修改已保存', 'Detail changes saved'), 'success');
                                                        closeAssetDetailModal();
                                                    } catch (e) {
                                                        onLog?.(t('保存失败', 'Save failed'), 'error');
                                                    }
                                                }}
                                                className="px-4 py-2 rounded bg-primary text-black font-bold hover:bg-primary/90 text-sm"
                                            >
                                                {t('保存', 'Save')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
             </AnimatePresence>

             {shotPromptModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary"/> Generate AI Shots</h3>
                            <button onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {shotPromptModal.loading && !shotPromptModal.data ? (
                                <div className="flex items-center justify-center h-40"><Loader2 className="animate-spin text-primary" size={32}/></div>
                            ) : (
                                <>
                                    <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-xs text-blue-200 flex items-start gap-2">
                                        <Info size={14} className="shrink-0 mt-0.5" />
                                        Review and edit the prompt before generation. Only the User Prompt (scenario context) is typically edited.
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">User Prompt (Scenario content)</label>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono h-64 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.user_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, user_prompt: e.target.value}}))}
                                        />
                                    </div>
                                    
                                     <div className="flex flex-col gap-2">
                                         <div className="flex items-center justify-between">
                                              <label className="text-xs font-bold text-muted-foreground uppercase">System Prompt (Instructions)</label>
                                              <span className="text-xs text-muted-foreground px-2 py-1 bg-white/5 rounded">Default/Template</span>
                                         </div>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono h-32 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.system_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, system_prompt: e.target.value}}))}
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                        
                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button 
                                onClick={() => {
                                    const full = (shotPromptModal.data?.system_prompt || '') + "\n\n" + (shotPromptModal.data?.user_prompt || '');
                                    navigator.clipboard.writeText(full);
                                    onLog?.(t('完整提示词已复制到剪贴板', 'Full prompt copied to clipboard'), "success");
                                }}
                                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-medium flex items-center gap-2 mr-auto"
                            >
                                <Copy size={16}/> {t('复制完整提示词', 'Copy Full Prompt')}
                            </button>
                            <button 
                                onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button 
                                onClick={handleConfirmGenerateShots}
                                disabled={shotPromptModal.loading}
                                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotPromptModal.loading ? <Loader2 className="animate-spin" size={16}/> : <Wand2 size={16}/>}
                                {shotPromptModal.loading ? t('生成中...', 'Generating...') : t('生成镜头', 'Generate Shots')}
                            </button>
                        </div>

                        <div className="mt-2 flex items-center gap-2">
                            <input
                                type="text"
                                value={sceneCodeFilter}
                                onChange={(e) => setSceneCodeFilter(e.target.value)}
                                placeholder={t('筛选场景编码（EPxx_SCyy）', 'Filter Scene Code (EPxx_SCyy)')}
                                className="bg-black/40 border border-white/20 rounded px-2.5 py-1.5 text-xs min-w-[200px] text-white"
                            />
                            <input
                                type="text"
                                value={shotIdFilter}
                                onChange={(e) => setShotIdFilter(e.target.value)}
                                placeholder={t('筛选镜头ID（EPxx_SCyy_SHzz）', 'Filter Shot ID (EPxx_SCyy_SHzz)')}
                                className="bg-black/40 border border-white/20 rounded px-2.5 py-1.5 text-xs min-w-[220px] text-white"
                            />
                            <button
                                onClick={() => { setSceneCodeFilter(''); setShotIdFilter(''); }}
                                className="px-2.5 py-1.5 bg-white/10 hover:bg-white/20 rounded text-[11px] text-white border border-white/10"
                            >
                                {t('清除镜头筛选', 'Clear Shot Filters')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {shotReviewModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-[90vw] h-[90vh] flex flex-col shadow-2xl">
                         <div className="p-4 border-b border-white/10 flex justify-between items-center bg-black/40">
                            <h3 className="font-bold flex items-center gap-2"><TableIcon size={16} className="text-primary"/> {t('审核 AI 生成镜头', 'Review AI Generated Shots')}</h3>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground bg-yellow-500/10 text-yellow-500 px-2 py-1 rounded">{t('暂存区', 'Staging Area')}</span>
                                <button onClick={() => setShotReviewModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                            </div>
                        </div>
                        
                        <div className="flex-1 overflow-hidden relative bg-[#121212]">
                            <div className="absolute inset-0 overflow-auto p-4 custom-scrollbar">
                                <table className="w-full text-xs text-left border-collapse">
                                    <thead className="sticky top-0 bg-[#252525] z-10 shadow-md">
                                        <tr>
                                            {[
                                                t('镜头 ID', 'Shot ID'),
                                                t('镜头名称', 'Shot Name'),
                                                t('内容', 'Content'),
                                                t('时长', 'Duration'),
                                                t('关联实体', 'Entities'),
                                                t('逻辑', 'Logic'),
                                                t('关键帧', 'Keyframes')
                                            ].map(h => (
                                                <th key={h} className="p-2 border-b border-white/10 font-bold text-white/70">{h}</th>
                                            ))}
                                            <th className="p-2 border-b border-white/10 w-10"></th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {(shotReviewModal.data || []).map((shot, idx) => (
                                            <tr key={idx} className="hover:bg-white/5 group">
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Shot ID"] || shot.shot_id || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot ID": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Shot Name"] || shot.shot_name || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot Name": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><textarea className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded resize-y min-h-[40px]" value={shot["Video Content"] || shot.video_content || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Video Content": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1 w-20"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Duration (s)"] || shot.duration || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Duration (s)": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Associated Entities"] || shot.associated_entities || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Associated Entities": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Shot Logic (CN)"] || shot.shot_logic_cn || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot Logic (CN)": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Keyframes"] || shot.keyframes || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Keyframes": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1 text-center">
                                                    <button onClick={() => {
                                                        const newData = shotReviewModal.data.filter((_, i) => i !== idx);
                                                        setShotReviewModal(prev => ({...prev, data: newData}));
                                                    }} className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500"><Trash2 size={14}/></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                <button onClick={() => {
                                     const newData = [...(shotReviewModal.data || []), { "Shot ID": (shotReviewModal.data?.length||0)+1, "Video Content": "" }];
                                     setShotReviewModal(prev => ({...prev, data: newData}));
                                }} className="mt-4 px-3 py-1 bg-white/5 hover:bg-white/10 rounded flex items-center gap-2 text-xs">
                                    <Plus size={14}/> {t('新增一行', 'Add Row')}
                                </button>
                            </div>
                        </div>

                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                             <button
                                onClick={async () => {
                                    try {
                                        await updateSceneLatestAIResult(shotReviewModal.sceneId, shotReviewModal.data);
                                        onLog?.(t('暂存草稿已保存。', 'Staged draft saved.'), "success");
                                    } catch(e) {
                                        onLog?.(t('保存草稿失败。', 'Failed to save draft.'), "error");
                                    }
                                }}
                                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm font-medium"
                            >
                                {t('保存草稿', 'Save Draft')}
                            </button>
                             <button 
                                onClick={async () => {
                                    if(!await confirmUiMessage(t('应用这些镜头吗？这会替换现有镜头。', 'Apply these shots? This will replace existing shots.'))) return;
                                    setShotReviewModal(prev => ({...prev, loading: true}));
                                    try {
                                        await applySceneAIResult(shotReviewModal.sceneId, { content: shotReviewModal.data });
                                        onLog?.(t('镜头已应用到数据库。', 'Shots applied to database.'), "success");
                                        setShotReviewModal({open: false, sceneId: null, data: null, loading: false});
                                        if (typeof refreshShots === 'function') refreshShots();
                                    } catch(e) {
                                        onLog?.(t('应用镜头失败: ', 'Failed to apply shots: ') + e.message, "error");
                                        setShotReviewModal(prev => ({...prev, loading: false}));
                                    }
                                }}
                                disabled={shotReviewModal.loading}
                                className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotReviewModal.loading ? <Loader2 className="animate-spin" size={16}/> : <CheckCircle size={16}/>}
                                {t('应用到场景', 'Apply to Scene')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isSettingsOpen && (
                 <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8">
                     <div className="bg-[#09090b] w-full max-w-6xl h-[90vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col relative overflow-hidden">
                          <button 
                             onClick={() => setIsSettingsOpen(false)}
                             className="absolute top-4 right-4 z-50 p-2 bg-black/60 rounded-full hover:bg-white/10 text-white border border-white/10"
                             title={t('关闭设置', 'Close Settings')}
                         >
                             <X size={20}/>
                         </button>
                         <div className="flex-1 overflow-auto custom-scrollbar">
                             <SettingsPage />
                         </div>
                     </div>
                 </div>
             )}
        </div>
    );
};

const ImportModal = ({ isOpen, onClose, onImport, defaultType = 'auto', project, uiLang = 'zh' }) => {
    const [text, setText] = useState('');
    const [importType, setImportType] = useState(defaultType); // auto, json, script, scene, shot
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    
    // Reset type when modal opens
    useEffect(() => {
        if (isOpen) setImportType(defaultType);
    }, [isOpen, defaultType]);

    if (!isOpen) return null;
    
    const handleImportClick = () => {
        onImport(text, importType);
    };

    const handleAIAnalysis = async () => {
        if (!text.trim()) return;
        setIsAnalyzing(true);
        try {
            const token = localStorage.getItem('token');
            const body = { 
                text: text,
                prompt_file: "scene_analysis.txt"
            };
            if (project?.global_info) {
                body.project_metadata = project.global_info;
            }

            const res = await fetch(`${API_BASE_URL}/analyze_scene`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(body)
            });
            
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || t('分析失败', 'Analysis Failed'));
            }
            
            const data = await res.json();
            setText(data.result); // Replace content with analysis result
            alert(t('AI 分析完成！请查看下方生成的 markdown。', 'AI Analysis Complete! Review the generated markdown below.'));
        } catch (e) {
            alert(`${t('分析错误', 'Analysis Error')}: ${e.message}`);
            console.error(e);
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="bg-[#09090b] border border-white/20 rounded-xl p-6 w-[800px] shadow-2xl flex flex-col max-h-[90vh]">
                <div className="flex justify-between items-center mb-4 shrink-0">
                     <h3 className="font-bold text-white flex items-center gap-2"><Upload className="w-5 h-5 text-primary"/> {t('导入与 AI 分析', 'Import & AI Analysis')}</h3>
                     <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground hover:text-white"/></button>
                </div>
                
                {/* Type Selection */}
                <div className="flex gap-4 mb-4 text-xs font-semibold text-gray-400 shrink-0">
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="auto" checked={importType === 'auto'} onChange={e => setImportType(e.target.value)} />
                        {t('自动识别（兼容）', 'Auto-Detect (Legacy)')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="json" checked={importType === 'json'} onChange={e => setImportType(e.target.value)} />
                        {t('JSON（项目/设置）', 'JSON (Project/Settings)')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="script" checked={importType === 'script'} onChange={e => setImportType(e.target.value)} />
                        {t('剧本表格', 'Script Table')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer text-white">
                        <input type="radio" name="itype" value="scene" checked={importType === 'scene'} onChange={e => setImportType(e.target.value)} />
                        {t('仅场景', 'Scenes Only')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer text-white">
                        <input type="radio" name="itype" value="shot" checked={importType === 'shot'} onChange={e => setImportType(e.target.value)} />
                        {t('仅镜头', 'Shots Only')}
                    </label>
                </div>

                <div className="text-xs text-gray-400 mb-2 shrink-0">
                   {t('可粘贴原始剧本文本进行 AI 分析，或粘贴格式化 JSON/表格进行导入。', 'Paste raw script text for AI Analysis, or paste formatted JSON/Table for Import.')}
                </div>
                <textarea 
                    className="flex-1 bg-black/40 border border-white/10 rounded-lg p-4 text-xs text-white font-mono focus:border-primary/60 outline-none resize-none mb-4 custom-scrollbar"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={t('在此粘贴剧本或数据...', 'Paste script or data here...')}
                />
                <div className="flex justify-between gap-2 shrink-0">
                    <button 
                        onClick={handleAIAnalysis}
                        disabled={!text.trim() || isAnalyzing}
                        className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 border border-purple-500/30 text-purple-200 hover:bg-purple-500/20 transition-all ${isAnalyzing ? 'opacity-50' : ''}`}
                    >
                        <Sparkles className={`w-3 h-3 ${isAnalyzing ? 'animate-spin' : ''}`} />
                        {isAnalyzing ? t('正在分析场景...', 'Analyzing Scene...') : t('AI 场景分析', 'AI Scene Analysis')}
                    </button>
                    
                    <div className="flex gap-2">
                        <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:bg-white/5">{t('取消', 'Cancel')}</button>
                        <button 
                            onClick={handleImportClick} 
                            disabled={!text.trim()}
                            className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 disabled:opacity-50"
                        >
                            {t('导入数据', 'Import Data')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )

};

const Editor = ({ projectId, onClose }) => {
    const params = useParams();
    const id = projectId || params.id;
    const navigate = useNavigate();

    const [project, setProject] = useState(null);
    const [episodes, setEpisodes] = useState([]);
    const [activeEpisodeId, setActiveEpisodeId] = useState(null);
    const [isEpisodeMenuOpen, setIsEpisodeMenuOpen] = useState(false);
    const [isAgentOpen, setIsAgentOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('overview');
    const [isImportOpen, setIsImportOpen] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0);
    const [editingShot, setEditingShot] = useState(null);
    const [uiLang, setUiLang] = useState(() => {
        try {
            const saved = localStorage.getItem('aistory.ui.lang');
            if (saved === 'zh' || saved === 'en') return saved;
        } catch (e) {}
        const navLang = (typeof navigator !== 'undefined' && navigator.language) ? navigator.language : 'en';
        return navLang.toLowerCase().startsWith('zh') ? 'zh' : 'en';
    });
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);

    // Global Logging Context
    const { addLog } = useLog();

    useEffect(() => {
        loadProjectData();
    }, [id]);

    useEffect(() => {
        try {
            setGlobalUiLang(uiLang);
        } catch (e) {}
    }, [uiLang]);

    const loadProjectData = async () => {
         if (!id) return;
         try {
            const p = await fetchProject(id);
            setProject(p);
         } catch (e) {
            console.error("Failed to fetch project title", e);
         }
            await loadEpisodes();
    };

    const loadEpisodes = async () => {
        if (!id) return;
        try {
            const data = await fetchEpisodes(id);
            setEpisodes(data);
            if (data.length > 0 && !activeEpisodeId) {
                setActiveEpisodeId(data[0].id);
            } else if (data.length === 0) {
                 // Auto create Ep 1 if none
                 const newEp = await createEpisode(id, { title: "Episode 1" });
                 setEpisodes([newEp]);
                 setActiveEpisodeId(newEp.id);
            }
        } catch (e) {
            console.error("Failed to load episodes", e);
        }
    };

    const handleUpdateScript = async (epId, content) => {
        try {
            const updatedEp = await updateEpisode(epId, { script_content: content });
            // Verify content length
            if (updatedEp.script_content && updatedEp.script_content.length !== content.length) {
                console.warn("Warning: Saved content length differs from local content.");
            }
            // Update local state to reflect content change
            setEpisodes(prev => prev.map(e => e.id === epId ? { ...e, script_content: content } : e));
            return updatedEp;
        } catch (e) {
            console.error("Update Script Failed in Parent:", e);
            throw e;
        }
    };

    const handleUpdateEpisodeInfo = async (epId, data) => {
        try {
            const updatedEp = await updateEpisode(epId, data);
            setEpisodes(prev => prev.map(e => e.id === epId ? updatedEp : e));
            return updatedEp;
        } catch (e) {
            console.error("Episode Info Update Failed:", e);
            throw e;
        }
    };

    const handleCreateEpisode = async () => {
        const title = await promptUiMessage("Enter Episode Title (e.g., Episode 2):", {
            title: 'Create Episode',
            confirmText: 'Create',
            cancelText: 'Cancel',
            placeholder: 'Episode 2',
        });
        if (!title) return;
        try {
            const newEp = await createEpisode(id, { title });
            setEpisodes(prev => [...prev, newEp]);
            setActiveEpisodeId(newEp.id);
            setIsEpisodeMenuOpen(false);
        } catch (e) {
            console.error(e);
        }
    };

    const handleDeleteEpisode = async (e, epId) => {
        e.stopPropagation();
        if (!await confirmUiMessage("Delete this episode? This will delete all script content and scenes within it.")) return;
         try {
            await deleteEpisode(epId);
            const remaining = episodes.filter(ep => ep.id !== epId);
            setEpisodes(remaining);
            if (activeEpisodeId === epId) {
                setActiveEpisodeId(remaining.length > 0 ? remaining[0].id : null);
            }
        } catch (err) {
            console.error(err);
        }
    };

    // Helper to repair common JSON syntax errors like unquoted strings
    const repairJSON = (jsonStr) => {
        try {
            return JSON.parse(jsonStr);
        } catch (e) {
            // Regex to match "key": value where value is unquoted
            // 1. "([^"]+)" matches key
            // 2. \s*:\s* matches colon
            // 3. ([^\s"{\[][\s\S]*?) matches value starting with non-quote/brace/bracket
            // 4. (?=\s*[,}\]]) lookahead for end of value (comma or brace/bracket)
            let repaired = jsonStr.replace(
                /"([^"]+)"\s*:\s*([^\s"{\[][\s\S]*?)(?=\s*[,}\]])/g, 
                (match, key, value) => {
                    const trimmedValue = value.trim();
                    if (!trimmedValue) return match;
                    
                    // Allow valid JSON primitives (numbers, bools, null)
                    if (/^(true|false|null)$/.test(trimmedValue)) return match;
                    if (!isNaN(parseFloat(trimmedValue)) && isFinite(trimmedValue)) return match;
                    
                    // Quote the string, escaping quotes and newlines
                    const safeValue = trimmedValue
                        .replace(/\\/g, '\\\\') // Escape backslashes first
                        .replace(/"/g, '\\"')
                        .replace(/\n/g, '\\n')
                        .replace(/\r/g, '');
                    return `"${key}": "${safeValue}"`;
                }
            );
            
            // Fix trailing commas
            repaired = repaired.replace(/,\s*([}\]])/g, '$1');
            
            return JSON.parse(repaired);
        }
    };

    // Helper to extract multiple JSON blocks from mixed text
    const extractJSONBlocks = (text) => {
        const results = [];
        let braceCount = 0;
        let startIndex = -1;
        
        let i = 0;
        while (i < text.length) {
            const char = text[i];
            
            // Skip strings to avoid counting braces inside them
            if (char === '"') {
                i++;
                while (i < text.length) {
                    if (text[i] === '"' && text[i-1] !== '\\') break;
                    if (text[i] === '\n') break;
                    i++;
                }
            } else if (char === '{') {
                if (braceCount === 0) startIndex = i;
                braceCount++;
            } else if (char === '}') {
                braceCount--;
                if (braceCount === 0 && startIndex !== -1) {
                    const jsonStr = text.substring(startIndex, i + 1);
                    try {
                        const obj = repairJSON(jsonStr);
                        results.push(obj);
                    } catch (e) {
                        console.warn("Failed to parse/repair block starting at " + startIndex, e);
                        // Optional: Could try to fuzzy find the end if brace counting was off
                    }
                    startIndex = -1;
                }
            }
            i++;
        }
        return results;
    }

    const handleImport = async (text, importType = 'auto') => {
        addLog(`Starting Import Analysis (${importType})...`, "process");
        
        // --- 1. JSON Processing (Only if 'auto' or 'json') ---
        const jsonBlocks = (importType === 'auto' || importType === 'json') ? extractJSONBlocks(text) : [];
        if (jsonBlocks.length > 0) {
             addLog(`Found ${jsonBlocks.length} JSON blocks to process.`, "info");
             // Process JSON Loop (same as before)
             // ... existing JSON processing code will run below ...
        }

        // Feature Flags based on Type
        // If specific type selected, FORCE recognition of that type and IGNORE others logic
        const canScript = importType === 'auto' || importType === 'script';
        const canScene = importType === 'auto' || importType === 'scene';
        const canShot = importType === 'auto' || importType === 'shot';

        // Strict: If explicit type, don't require specific headers if possible, OR just bypass strict header check?
        // Actually, existing logic relies on headers to parse columns. We still need headers.
        // But we won't misidentify Scene table as Shot table if we force one.
        
        const hasScriptTable = canScript && text.includes('|') && (text.includes('Paragraph ID') || text.includes('Paragraph Title'));
        
        // Scene header detection (Relaxed if forced scene type?)
        const sceneHeaderMarkers = ['Scene No', '场次序号', 'Scene ID', '场次'];
        let hasSceneTable = canScene && text.includes('|') && sceneHeaderMarkers.some(m => text.includes(m));
        
        // Shot header detection
        const shotHeaderMarkers = ['Shot ID', '镜头ID', 'Shot No'];
        let hasShotTable = canShot && text.includes('|') && shotHeaderMarkers.some(m => text.includes(m));

        // If explicit type is set but markers are missing, try to help user?
        if (importType === 'scene' && !hasSceneTable && text.includes('|')) {
            // Fallback: If strict mode, maybe assume the first row with | is header? 
            // Warning user is safer.
            addLog("Warning: 'Scenes' type selected, but specific Scene headers not found. Attempting to parse anyway if table exists.", "warning");
            hasSceneTable = true;
        }
        if (importType === 'shot' && !hasShotTable && text.includes('|')) {
             addLog("Warning: 'Shots' type selected, but specific Shot headers not found. Attempting to parse anyway if table exists.", "warning");
             hasShotTable = true;
        }

        addLog(`Import Flags: Script=${hasScriptTable}, Scene=${hasSceneTable}, Shot=${hasShotTable}`, "info");

        if (jsonBlocks.length === 0 && !hasScriptTable && !hasSceneTable && !hasShotTable) {

            addLog("No recognizable markers found.", "error");
            alert("No supported format detected. Please check your markers.");
            return;
        }

        let changesMade = false;
        let reloadRequired = false;

        // Process all found JSON blocks
        for (const data of jsonBlocks) {
            // 2. Process Global Info (JSON)
            if (data.global_info) {
                try {
                    await updateProject(id, { global_info: data.global_info });
                    addLog("Project Global Info updated.", "success");
                    changesMade = true;
                    reloadRequired = true;
                } catch (e) {
                    addLog(`Global Info Update Failed: ${e.message}`, "error");
                }
            }

            // 2b. Process Episode Global Info (JSON)
            if (data.e_global_info) {
                if (!activeEpisodeId) {
                    addLog("Skipping Episode Info: No Active Episode selected.", "warning");
                } else {
                    try {
                        await updateEpisode(activeEpisodeId, { 
                            episode_info: { e_global_info: data.e_global_info } 
                        });
                        addLog("Episode Global Info updated.", "success");
                        changesMade = true;
                    } catch (e) {
                        addLog(`Episode Info Update Failed: ${e.message}`, "error");
                    }
                }
            }

            // 2c. Process Entities (JSON)
            // Can be { characters: [] } or { props: [] } etc
            if (data.characters || data.props || data.environments) {
                try {
                    addLog("Processing Entities block...", "process");
                    let count = 0;

                    // Characters
                    if (data.characters && Array.isArray(data.characters)) {
                        for (const char of data.characters) {
                            const desc = [
                                `Name (EN): ${char.name_en}`,
                                `Role: ${char.role}`,
                                `Archetype: ${char.archetype}`,
                                `Appearance: ${char.appearance_cn}`,
                                `Clothing: ${char.clothing}`,
                                `Action: ${char.action_characteristics}`,
                                `Prompt: ${char.generation_prompt_en}`
                            ].join('\n\n');
                            
                            await createEntity(id, {
                                name: char.name,
                                type: 'character',
                                description: desc,
                                generation_prompt_en: char.generation_prompt_en || '',
                                anchor_description: char.anchor_description || '',
                                
                                name_en: char.name_en,
                                gender: char.gender,
                                role: char.role,
                                archetype: char.archetype,
                                appearance_cn: char.appearance_cn,
                                clothing: char.clothing,
                                action_characteristics: char.action_characteristics,
                                visual_dependencies: char.visual_dependencies || [],
                                dependency_strategy: char.dependency_strategy || {}
                            });
                            count++;
                        }
                    }

                    // Props
                    if (data.props && Array.isArray(data.props)) {
                        for (const prop of data.props) {
                             const desc = [
                                `Name (EN): ${prop.name_en}`,
                                `Type: ${prop.type}`, // inner type from JSON
                                `Description: ${prop.description_cn}`,
                                `Prompt: ${prop.generation_prompt_en}`,
                                prop.dependency_strategy?.logic ? `Dependency: ${prop.dependency_strategy.logic}` : ''
                            ].filter(Boolean).join('\n\n');

                            await createEntity(id, {
                                name: prop.name,
                                type: 'prop',
                                description: desc,
                                generation_prompt_en: prop.generation_prompt_en || '',
                                anchor_description: prop.anchor_description || '',
                                
                                name_en: prop.name_en,
                                visual_dependencies: prop.visual_dependencies || [],
                                dependency_strategy: prop.dependency_strategy || {}
                            });
                            count++;
                        }
                    }

                    // Environments
                    if (data.environments && Array.isArray(data.environments)) {
                        for (const env of data.environments) {
                             const desc = [
                                `Name (EN): ${env.name_en}`,
                                `Atmosphere: ${env.atmosphere}`,
                                `Visual Params: ${env.visual_params}`,
                                `Description: ${env.description_cn}`,
                                `Prompt: ${env.generation_prompt_en}`
                            ].join('\n\n');

                            await createEntity(id, {
                                name: env.name,
                                type: 'environment',
                                description: desc,
                                generation_prompt_en: env.generation_prompt_en || '',
                                anchor_description: env.anchor_description || '',
                                
                                name_en: env.name_en,
                                atmosphere: env.atmosphere,
                                visual_params: env.visual_params,
                                narrative_description: env.description_cn,

                                visual_dependencies: env.visual_dependencies || [],
                                dependency_strategy: env.dependency_strategy || {}
                            });
                            count++;
                        }
                    }
                    
                    if (count > 0) {
                        addLog(`Imported ${count} entities from block.`, "success");
                        changesMade = true;
                    }
                } catch (e) {
                    addLog(`Entity Import Failed: ${e.message}`, "error");
                    console.error(e);
                }
            }
        }

        // Check episode selection for Script/Scene import
        if ((hasScriptTable || hasSceneTable) && !activeEpisodeId) {
             addLog("Detection: Script/Scene content found but NO Active Episode selected.", "error");
             alert("Please create or select an episode before importing Script or Scene content.");
             return; 
        }

        // 3. Process Script Content
        if (hasScriptTable && activeEpisodeId) {
            try {
                addLog(`Processing Script Table for Episode ${activeEpisodeId}...`, "process");
                const lines = text.split('\n');
                let scriptLines = [];
                let capturing = false;

                for (let line of lines) {
                    // Start marker
                    if (line.includes('|') && (line.includes('Paragraph ID') || line.includes('Paragraph Title'))) {
                        capturing = true;
                        addLog("Found Script Header.", "info");
                    }
                    
                    if (capturing) {
                        if (line.trim().startsWith('|')) {
                            // Validate column count roughly to avoid bad lines? optional.
                            scriptLines.push(line);
                        } else if (scriptLines.length > 2 && !line.trim().startsWith('|')) {
                            capturing = false;
                            addLog("End of Script Table.", "info");
                        }
                    }
                }

                if (scriptLines.length > 0) {
                    const content = scriptLines.join('\n');
                    await updateEpisode(activeEpisodeId, { script_content: content });
                    addLog(`Imported ${scriptLines.length} lines of Script content.`, "success");
                    changesMade = true;
                } else {
                    addLog("Script markers found but no lines extracted.", "error");
                }
            } catch (e) {
                addLog(`Script Import Failed: ${e.message}`, "error");
            }
        }

        // 4. Process Scene Content (and interleaved Shots)
        if ((hasSceneTable || hasShotTable) && activeEpisodeId) {
             try {
                addLog(`Processing Scene/Shot Tables for Episode ${activeEpisodeId}...`, "process");
                const lines = text.split('\n');
                let sceneLines = [];
                let shotLines = [];
                
                // DB Sync State
                let existingScenes = [];
                try { existingScenes = await fetchScenes(activeEpisodeId); } catch(e) {}
                let currentSceneDbId = null;
                
    const processImportText = async (text) => {
        // ... (Existing implementation of handleProjectImport logic extracted here or just use inline)
        // Note: The user code seen via read_file seems to be inside a large function "handleProjectImport" or similar.
    
        // ... previous extraction logic ...
    }; // (Dummy closer for context)

    // ... (Inside the actual big loop)
    
                // State flags
                let inShotTable = false;
                let inSceneTable = false;
                let shotHeaderMap = {};
                let sceneHeaderMap = {};

                for (let line of lines) {
                    const trimmed = line.trim();
                    let isTableRow = trimmed.startsWith('|');
                    
                    // Robustness: Allow internal rows without leading pipe
                    if (!isTableRow && (inSceneTable || inShotTable) && trimmed.includes('|')) isTableRow = true;
                    
                    let cols = [];
                    if (isTableRow || trimmed.includes('|')) { 
                        cols = line.split('|').map(c => c.trim());
                        if (trimmed.startsWith('|') && cols.length > 0 && cols[0] === "") cols.shift();
                        if (trimmed.endsWith('|') && cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                    }

                    // 1. Header Detection (Relaxed)
                    const isShotKey = (isTableRow || line.includes('|')) && (line.includes("Shot ID") || line.includes("镜头ID") || line.includes("Shot Name") || line.includes("Shot No"));
                    const isSceneKey = (isTableRow || line.includes('|')) && (line.includes('Scene No') || line.includes('场次序号') || (line.includes('Scene ID') && !line.includes('Shot ID')));

                    // Enter Shot Table Mode
                    if (canShot && !inSceneTable && (isShotKey || (importType === 'shot' && !inShotTable && isTableRow && cols.length > 2))) {
                        inShotTable = true;
                        inSceneTable = false;
                        addLog("Found Shot Header (or Forced Type).", "info");
                        shotLines.push(line); 
                        
                        // Parse Header Map
                        const curCols = line.split('|').map(c => c.trim());
                        // ... (same as original code)
                        if (curCols.length > 0 && curCols[0] === "") curCols.shift();
                        if (curCols.length > 0 && curCols[curCols.length-1] === "") curCols.pop();
                        
                        shotHeaderMap = {};
                        curCols.forEach((col, idx) => {
                             const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                             shotHeaderMap[key] = idx;
                        });
                        continue;
                    }
                    else if (canScene && !inShotTable && (isSceneKey || (importType === 'scene' && !inSceneTable && line.includes('|') && cols.length > 2))) {
                        inSceneTable = true;
                        inShotTable = false;
                        addLog("Found Scene Header (or Forced Type).", "info");
                        sceneLines.push(line);

                        const curCols = line.split('|').map(c => c.trim());
                        if (curCols.length > 0 && curCols[0] === "") curCols.shift();
                        if (curCols.length > 0 && curCols[curCols.length-1] === "") curCols.pop();

                        sceneHeaderMap = {};
                        curCols.forEach((col, idx) => {
                            const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                            sceneHeaderMap[key] = idx;
                        });
                        continue;
                    }

                    // 2. Data Line Processing
                    if (isTableRow) {
                         // cols already parsed and cleaned at top of loop
                         // Only skip if strict separator line. 
                         // Check only for regex match of '---|---' style or '---' in cells (handling :--- for alignment)
                         const isSeparator = /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);
                         const isEmptyRow = cols.every(c => c === "");

                         if (cols.length < 2 || isSeparator || isEmptyRow) {
                             if (inSceneTable) sceneLines.push(line);
                             if (inShotTable) shotLines.push(line);
                             continue; 
                         }
                         
                         const clean = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';

                         // A. Handle Scene Row
                         if (inSceneTable) {
                             sceneLines.push(line);
                             
                             try {
                                const getSceneVal = (keys, fallbackIdx) => {
                                    for (const k of keys) {
                                        if (sceneHeaderMap[k] !== undefined && sceneHeaderMap[k] < cols.length) {
                                            return clean(cols[sceneHeaderMap[k]]);
                                        }
                                    }
                                    return fallbackIdx < cols.length ? clean(cols[fallbackIdx]) : '';
                                };

                                const isNewSceneFormat = cols.length >= 13 || sceneHeaderMap['episodeid'] !== undefined || sceneHeaderMap['sceneid'] !== undefined;

                                const scData = {
                                    scene_no: getSceneVal(['sceneno', 'scene_no', '场次序号', '场次'], isNewSceneFormat ? 2 : 0),
                                    scene_name: getSceneVal(['scenename', 'title', 'scene_name', '场景名称'], isNewSceneFormat ? 3 : 1),
                                    equivalent_duration: getSceneVal(['equivalentduration', 'duration', 'equivalent_duration'], isNewSceneFormat ? 4 : 2),
                                    core_scene_info: getSceneVal(['coresceneinfo', 'coregoal', 'core_scene_info'], isNewSceneFormat ? 5 : 3),
                                    original_script_text: getSceneVal(['originalscripttext', 'description', 'original_script_text'], isNewSceneFormat ? 6 : 4),
                                    environment_name: getSceneVal(['environmentname', 'environment', 'environment_name'], isNewSceneFormat ? 7 : 5),
                                    linked_characters: getSceneVal(['linkedcharacters', 'linked_characters'], isNewSceneFormat ? 11 : 6),
                                    key_props: getSceneVal(['keyprops', 'key_props'], isNewSceneFormat ? 12 : 7)
                                };
                                
                                if (!scData.scene_no || String(scData.scene_no).trim().length === 0) {
                                    // addLog("Skipping empty Scene row", "info"); // Optional log
                                    continue;
                                }

                                addLog(`Processing Scene Row: No=${scData.scene_no} Name=${(scData.scene_name || '').substring(0, 20)}...`, "info");

                                const match = existingScenes.find(s => String(s.scene_no) === String(scData.scene_no));
                                if (match) {
                                    await updateScene(match.id, scData); 
                                    currentSceneDbId = match.id;
                                    addLog(`Updated Scene ${scData.scene_no}`, "success");
                                } else {
                                    const newScene = await createScene(activeEpisodeId, scData);
                                    currentSceneDbId = newScene.id;
                                    existingScenes.push(newScene); 
                                    addLog(`Created Scene ${scData.scene_no}`, "success");
                                }
                             } catch (rowErr) {
                                 console.error("Row Error", rowErr);
                                 addLog(`Row Processing Failed: ${rowErr.message}`, "error");
                             }
                         }
                         
                         // B. Handle Shot Row
                         else if (inShotTable) {
                             shotLines.push(line);
                             
                             const useMap = Object.keys(shotHeaderMap).length > 0;
                             
                             const getVal = (keys, defaultIdx) => {
                                 for (const k of keys) {
                                     if (shotHeaderMap[k] !== undefined && shotHeaderMap[k] < cols.length) return clean(cols[shotHeaderMap[k]]);
                                 }
                                 if (!useMap && defaultIdx < cols.length) return clean(cols[defaultIdx]);
                                 return '';
                             };
                             
                             // Legacy offset logic
                             let colStart = 2; 
                             let legacySceneCode = '';
                             if (!useMap) {
                                if (cols.length >= 8) {
                                    legacySceneCode = clean(cols[2]);
                                    colStart = 3;
                                }
                             }

                             const rawShotId = useMap ? getVal(['shotid', 'shotno', '镜头id', 'id'], 0) : clean(cols[0]);
                             
                             if (!rawShotId || String(rawShotId).trim().length === 0) {
                                 continue; 
                             }

                             // Infer Scene from Shot ID if needed (e.g. 1-1)
                             if (!currentSceneDbId) {
                                 // Try to find scene code column first
                                let tempCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                                if (!tempCode) {
                                     // Check if shot ID has implicit scene number (e.g. 1-1A)
                                     const parts = rawShotId.split(/[-_]/);
                                     if (parts.length > 1) tempCode = parts[0];
                                }
                                
                                if (tempCode) {
                                     // Look up Scene ID by Scene No
                                     const match = existingScenes.find(s => {
                                         const dbNo = String(s.scene_no).replace(/[\*\s]/g, '');
                                         const targetNo = String(tempCode).replace(/[\*\s]/g, '');
                                         return dbNo === targetNo;
                                     });
                                     if (match) currentSceneDbId = match.id;
                                     else {
                                         // Auto-create scene if strict mode not enforced?
                                         // User asked for "strict separation", implying we shouldn't guess wild things. 
                                         // But if we can't find scene, we can't link.
                                         // Maybe we should create proper scene if missing?
                                         // For now, let's just log.
                                     }
                                }
                             }

                             
                             // !!! KEY FIX: Ensure scene_code is sent to creation !!!
                             let sceneCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                             if (!sceneCode && currentSceneDbId) {
                                 const sObj = existingScenes.find(s => s.id === currentSceneDbId);
                                 if (sObj) sceneCode = sObj.scene_no;
                             }

                             if (currentSceneDbId) {
                                 const shotData = {
                                     shot_id: rawShotId,
                                     shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                                     scene_code: sceneCode, 
                                     start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                                     end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                                     video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                                     duration: useMap ? getVal(['duration', 'durations', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                                     associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                                     shot_logic_cn: useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)', 'shot logic (cn)', 'logic(cn)'], 7) : ''
                                 };
                                 
                                 addLog(`Creating Shot ${shotData.shot_id} for Scene ID ${currentSceneDbId}...`, "info");
                                 try {
                                     await createShot(currentSceneDbId, shotData);
                                 } catch (shotErr) {
                                      console.error("Shot DB Sync Error", shotErr);
                                      addLog(`Failed to create shot ${shotData.shot_id}: ${shotErr.message}`, "error");
                                 }
                             } else {
                                 addLog(`Skipped Shot ${rawShotId}: No matching Scene found for code '${sceneCode}'`, "warning");
                             }
                         }

                    } else if (sceneLines.length > 2 && inSceneTable && !trimmed.startsWith('|') && trimmed !== '') {
                         inSceneTable = false;
                    } else if (shotLines.length > 2 && inShotTable && !trimmed.startsWith('|') && trimmed !== '') {
                         inShotTable = false;
                    }
                }

                // Update contents separately
                // Removed legacy scene_content/shot_content updates as they are deprecated in backend
                /* 
                const updatePayload = {};
                if (sceneLines.length > 0) { ... }
                */
                
                // Just force refresh
                if (sceneLines.length > 0 || shotLines.length > 0) {
                    changesMade = true;
                    reloadRequired = true;
                }
             } catch (e) {
                 addLog(`Scene Import Failed: ${e.message}`, "error");
             }
        }

        if (changesMade) {
            setIsImportOpen(false);
            
            // Always refresh episodes to show new scripts/scenes
            const fresh = await fetchEpisodes(id);
            setEpisodes(fresh);

            if (reloadRequired) {
                // Force Overview refresh if needed
                setRefreshKey(prev => prev + 1);
                addLog("Project Settings updated. Refreshing views...", "info");
                alert("Import Successful! Project settings and content have been updated.");
                
                // Force reload of scenes if the active episode was affected
                if (activeEpisodeId) {
                    try {
                        const newScenes = await fetchScenes(activeEpisodeId);
                        // Accessing SceneManager via ref or forcing a global refresh is intricate.
                        // Ideally, we just update the 'activeEpisode' reference which triggers SceneManager useEffect.
                        // But activeEpisode is derived from 'episodes'. 'setEpisodes(fresh)' does that.
                        // HOWEVER, SceneManager uses [activeEpisode, projectId] dependency.
                        // If 'fresh' episode object is identical (by reference or value), it might not trigger.
                        // Let's force a window reload as a last resort fallback, or better:
                        // window.location.reload(); // Removed to prevent full page reload navigating away
                    } catch(e) { console.error(e); }
                }
            } else {
                alert("Import Successful!");
            }
        }
    };

    const handleExport = async () => {
        addLog("Preparing project export...", "process");
        try {
            // 1. Fetch latest project data
            const projectData = await fetchProject(id);
            // 2. Fetch all episodes
            const episodesData = await fetchEpisodes(id);

            const exportData = {
                project: projectData,
                episodes: episodesData,
                export_date: new Date().toISOString(),
                version: "1.0"
            };

            const jsonString = JSON.stringify(exportData, null, 2);
            const blob = new Blob([jsonString], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `Project_${(projectData.title || id).replace(/[^a-z0-9]/gi, '_')}_Export.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            addLog("Project exported to local disk.", "success");
        } catch (e) {
            console.error(e);
            addLog(`Export failed: ${e.message}`, "error");
            alert(`Failed to export project: ${e?.message || 'Unknown error'}`);
        }
    };

    const activeEpisode = episodes.find(e => e.id === activeEpisodeId);
    const activeEpisodeIndex = activeEpisode ? episodes.findIndex((episode) => episode.id === activeEpisode.id) : -1;
    const activeEpisodeLabel = activeEpisode
        ? buildEpisodeDisplayLabel({
            episodeNumber: activeEpisode?.episode_number,
            title: activeEpisode?.title,
            fallbackNumber: activeEpisodeIndex >= 0 ? activeEpisodeIndex + 1 : null,
        })
        : t('选择剧集', 'Select Episode');

    const MENU_ITEMS = [
        { id: 'overview', label: t('总览', 'Overview'), icon: LayoutDashboard },
        { id: 'ep_info', label: t('分集信息', 'Ep. Info'), icon: Info },
        { id: 'script', label: t('剧本', 'Script'), icon: FileText },
        { id: 'subjects', label: t('角色资产', 'Subjects'), icon: Users },
        { id: 'scenes', label: t('场景', 'Scenes'), icon: Clapperboard },
        { id: 'shots', label: t('镜头', 'Shots'), icon: Film },
        { id: 'montage', label: t('剪辑', 'Montage'), icon: Video },
    ];

    const trackMenuAction = (menuKey, menuLabel, actionFn) => {
        const page = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        void recordSystemLogAction({
            action: 'MENU_CLICK',
            menu_key: menuKey,
            menu_label: menuLabel,
            page,
        });

        try {
            const actionResult = actionFn?.();
            if (actionResult && typeof actionResult.then === 'function') {
                actionResult
                    .then(() => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'success',
                        });
                    })
                    .catch((error) => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'failed',
                            details: error?.message || 'unknown error',
                        });
                    });
                return;
            }

            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'success',
            });
        } catch (error) {
            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'failed',
                details: error?.message || 'unknown error',
            });
            throw error;
        }
    };

    return (
        <div className="flex flex-col h-screen w-full bg-background overflow-hidden relative text-foreground">
            {/* Top Navigation Bar - Compact */}
            <div className="h-12 px-4 border-b border-white/10 bg-[#09090b] flex items-center justify-between shrink-0 z-40 relative">
                {/* Left: Project Info & Episode Selector */}
                <div className="flex items-center gap-4">
                     {/* Back Button if in embedded mode */}
                     {onClose && (
                                <button onClick={() => trackMenuAction('editor.back.embedded', t('返回项目', 'Back to Projects'), onClose)} className="p-1.5 hover:bg-white/10 rounded-md text-muted-foreground hover:text-white transition-colors mr-2">
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                     )}
                     <div className="flex items-center gap-4">
                        <h1 className="font-bold text-sm tracking-wide text-white flex items-center gap-2">
                            <span className="text-primary hover:underline cursor-pointer">{project ? project.title : `Project #${id}`}</span>
                        </h1>
                        
                        {/* Episode Dropdown */}
                        <div className="relative">
                            <button 
                                onClick={() => trackMenuAction('editor.episode.dropdown_toggle', t('剧集菜单', 'Episode Menu'), () => setIsEpisodeMenuOpen(!isEpisodeMenuOpen))}
                                className="w-[260px] flex items-center justify-between gap-2 px-3 py-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-md text-xs font-medium text-white transition-colors"
                            >
                                <span className="truncate text-left">{activeEpisodeLabel}</span>
                                <ChevronDown className="w-3 h-3 text-muted-foreground" />
                            </button>

                            {/* Dropdown Menu */}
                            {isEpisodeMenuOpen && (
                                <div className="absolute top-full left-0 mt-2 w-[320px] bg-[#09090b] border border-white/10 rounded-lg shadow-xl py-1 z-50">
                                    {episodes.map((ep, index) => (
                                        <div 
                                            key={ep.id}
                                            className={`px-3 py-2 text-xs flex justify-between items-center group cursor-pointer ${activeEpisodeId === ep.id ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:bg-white/5 hover:text-white'}`}
                                            onClick={() => {
                                                trackMenuAction('editor.episode.select', buildEpisodeDisplayLabel({ episodeNumber: ep?.episode_number, title: ep?.title, fallbackNumber: index + 1 }), () => {
                                                    setActiveEpisodeId(ep.id);
                                                    setIsEpisodeMenuOpen(false);
                                                });
                                            }}
                                        >
                                            <span className="truncate flex-1 pr-2" title={buildEpisodeDisplayLabel({ episodeNumber: ep?.episode_number, title: ep?.title, fallbackNumber: index + 1 })}>
                                                {buildEpisodeDisplayLabel({ episodeNumber: ep?.episode_number, title: ep?.title, fallbackNumber: index + 1 })}
                                            </span>
                                            <button 
                                                onClick={(e) => handleDeleteEpisode(e, ep.id)}
                                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 hover:text-red-500 rounded"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    ))}
                                    <div className="border-t border-white/10 mt-1 pt-1 px-1">
                                         <button 
                                            onClick={() => trackMenuAction('editor.episode.create', t('新建分集', 'New Episode'), handleCreateEpisode)}
                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground hover:text-white hover:bg-white/5 rounded transition-colors"
                                        >
                                            <Plus className="w-3 h-3" /> {t('新建分集', 'New Episode')}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                     </div>
                </div>

                {/* Center: Navigation Menu */}
                <div className="flex items-center bg-transparent">
                    {MENU_ITEMS.map(item => {
                        const Icon = item.icon;
                        const isActive = activeTab === item.id;
                        return (
                            <button
                                key={item.id}
                                onClick={() => {
                                    trackMenuAction(`editor.top_menu.${item.id}`, item.label, () => {
                                        setActiveTab(item.id);
                                        if (item.id === 'shots') setEditingShot(null);
                                    });
                                }}
                                className={`flex items-center gap-2 px-4 py-1.5 text-xs font-bold transition-all relative ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-white'}`}
                            >
                                <Icon className="w-3.5 h-3.5" />
                                {item.label}
                                {isActive && <div className="absolute bottom-[-13px] left-0 right-0 h-[2px] bg-primary shadow-[0_0_10px_rgba(255,255,255,0.5)]"></div>}
                            </button>
                        )
                    })}
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => trackMenuAction('editor.ui_language.toggle', t('切换界面语言', 'Toggle UI Language'), () => setUiLang(prev => prev === 'zh' ? 'en' : 'zh'))}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5"
                        title={t('切换到英文界面', 'Switch to Chinese UI')}
                    >
                        <Languages className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{uiLang === 'zh' ? '中文' : 'EN'}</span>
                    </button>
                    <button
                        onClick={() => {
                            trackMenuAction('editor.back.projects', t('返回项目', 'Back to Projects'), () => {
                                if (onClose) {
                                    onClose();
                                    return;
                                }
                                navigate('/projects');
                            });
                        }}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5"
                        title={t('返回项目列表', 'Back to Projects')}
                    >
                        <ArrowLeft className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('返回项目', 'Back to Projects')}</span>
                    </button>
                    <button 
                        onClick={() => trackMenuAction('editor.action.import', t('导入内容', 'Import Content'), () => setIsImportOpen(true))}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5" 
                        title={t('导入内容', 'Import Content')}
                    >
                        <Upload className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('导入', 'Import')}</span>
                    </button>
                    <button 
                        onClick={() => trackMenuAction('editor.action.export', t('导出项目', 'Export Project'), handleExport)}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5" 
                        title={t('导出项目', 'Export Project')}
                    >
                        <Download className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('导出', 'Export')}</span>
                    </button>
                    <button
                        onClick={() => {
                            trackMenuAction('editor.action.settings', t('设置', 'Settings'), () => {
                                const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
                                window.location.assign(`/settings?tab=api-settings&return_to=${returnTo}`);
                            });
                        }}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors"
                        title={t('设置', 'Settings')}
                    >
                        <SettingsIcon className="w-4 h-4" />
                    </button>
                    <button 
                        onClick={() => trackMenuAction('editor.action.ai_agent', t('AI 助手', 'AI Agent'), () => setIsAgentOpen(!isAgentOpen))}
                        className={`flex items-center gap-2 px-3 py-1 rounded-md text-xs font-bold transition-colors ${isAgentOpen ? 'bg-secondary text-white' : 'bg-primary text-black'}`}
                    >
                        <MessageSquare className="w-3.5 h-3.5" />
                        {t('AI 助手', 'AI Agent')}
                        {/* Status Dot */}
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse ml-1 opacity-50"></div>
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-hidden relative bg-background">
                <div className="h-full overflow-y-auto custom-scrollbar p-0">
                    <div className="animate-in fade-in duration-300 min-h-full">
                        {activeTab === 'overview' && (
                            <ProjectOverview
                                id={id}
                                key={refreshKey}
                                episodes={episodes}
                                uiLang={uiLang}
                                onProjectUpdate={loadProjectData}
                                onJumpToEpisode={(episodeId) => {
                                    setActiveEpisodeId(episodeId);
                                    setActiveTab('script');
                                }}
                            />
                        )}
                        {activeTab === 'ep_info' && <EpisodeInfo episode={activeEpisode} onUpdate={handleUpdateEpisodeInfo} project={project} projectId={id} uiLang={uiLang} />}
                        {activeTab === 'script' && <ScriptEditor activeEpisode={activeEpisode} projectId={id} project={project} onUpdateScript={handleUpdateScript} onUpdateEpisodeInfo={handleUpdateEpisodeInfo} onLog={addLog} onImportText={handleImport} onSwitchToScenes={() => setActiveTab('scenes')} uiLang={uiLang} />}
                        {activeTab === 'subjects' && <SubjectLibrary projectId={id} currentEpisode={activeEpisode} uiLang={uiLang} />}
                        {activeTab === 'scenes' && <SceneManager activeEpisode={activeEpisode} projectId={id} project={project} onLog={addLog} onSwitchToShots={() => setActiveTab('shots')} uiLang={uiLang} />}
                        {activeTab === 'shots' && <ShotsView activeEpisode={activeEpisode} projectId={id} project={project} onLog={addLog} editingShot={editingShot} setEditingShot={setEditingShot} uiLang={uiLang} />}
                        {activeTab === 'montage' && <VideoStudio activeEpisode={activeEpisode} projectId={id} onLog={addLog} />}
                    </div>
                </div>
            </div>

            {/* Agent Sidebar (Slide-over) */}
            <AnimatePresence>
                {isAgentOpen && (
                    <motion.div 
                        initial={{ x: "100%", opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: "100%", opacity: 0 }}
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        className="absolute right-0 top-12 bottom-0 w-[450px] border-l border-white/10 bg-[#09090b]/95 backdrop-blur-xl z-50 flex flex-col shadow-[-20px_0_50px_rgba(0,0,0,0.5)]"
                    >
                        <AgentChat context={{ projectId: id }} onClose={() => setIsAgentOpen(false)} />
                    </motion.div>
                )}
            </AnimatePresence>

            <ImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} onImport={handleImport} project={project} uiLang={uiLang} />

            {/* Log Panel */}
            <LogPanel />

        </div>
    );
};

export default Editor;
