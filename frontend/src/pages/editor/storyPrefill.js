/** Structured prefill: McKee + three-act concept, Egri character, Save the Cat 15 beats. */

export const SAVE_THE_CAT_ACTS = [
    {
        id: 'act1',
        zh: '第一幕 · 建置',
        en: 'Act I · Setup',
        beats: [
            {
                id: 'stc_01_opening_image',
                no: '01',
                zh: '开场画面',
                en: 'Opening Image',
                hintZh: '终场之前的世界缩影。一个能看见的状态，事后要和终场画面对上。',
                hintEn: 'A visible snapshot of the world before the change. It must rhyme with the final image.',
            },
            {
                id: 'stc_02_theme_stated',
                no: '02',
                zh: '主题呈现',
                en: 'Theme Stated',
                hintZh: '有人说出或做出主控思想。主角这时听不进去。',
                hintEn: 'Someone states or enacts the controlling idea. The hero does not take it in yet.',
            },
            {
                id: 'stc_03_setup',
                no: '03',
                zh: '铺垫',
                en: 'Set-up',
                hintZh: '催化剂之前，亮出缺陷、欲望、赌注和日常关系。',
                hintEn: 'Before the catalyst: flaw, desire, stakes, and the relationships of ordinary life.',
            },
            {
                id: 'stc_04_catalyst',
                no: '04',
                zh: '催化剂',
                en: 'Catalyst',
                hintZh: '打破平衡的那一件事。发生之后，回不到原来的生活。',
                hintEn: 'The event that upsets the balance. After it, the old life is gone.',
            },
            {
                id: 'stc_05_debate',
                no: '05',
                zh: '争执',
                en: 'Debate',
                hintZh: '进不进去。恐惧、拒绝，最后被逼到必须选。',
                hintEn: 'Whether to step in. Fear and refusal, until a choice is forced.',
            },
        ],
    },
    {
        id: 'act2a',
        zh: '第二幕上 · 对抗',
        en: 'Act II-A · Confrontation',
        beats: [
            {
                id: 'stc_06_break_into_two',
                no: '06',
                zh: '进入第二幕',
                en: 'Break into Two',
                hintZh: '主角主动跨过门槛。旧办法从此作废。',
                hintEn: 'The hero crosses the threshold on purpose. The old method stops working.',
            },
            {
                id: 'stc_07_b_story',
                no: '07',
                zh: 'B故事',
                en: 'B Story',
                hintZh: '另一条关系线。通常拿来照主题，也给主角一面镜子。',
                hintEn: 'The relationship line that carries the theme and mirrors the hero.',
            },
            {
                id: 'stc_08_fun_and_games',
                no: '08',
                zh: '游戏时间',
                en: 'Fun and Games',
                hintZh: '预告片里承诺的类型乐趣。表面上升，或一次假顺。',
                hintEn: 'The promise of the premise: the fun, the rise, or the false smooth stretch.',
            },
        ],
    },
    {
        id: 'act2b',
        zh: '第二幕下 · 加压',
        en: 'Act II-B · Pressure',
        beats: [
            {
                id: 'stc_09_midpoint',
                no: '09',
                zh: '中点',
                en: 'Midpoint',
                hintZh: '假胜利或假失败。赌注公开，时钟开始倒。',
                hintEn: 'False victory or false defeat. Stakes go public and the clock starts.',
            },
            {
                id: 'stc_10_bad_guys_close_in',
                no: '10',
                zh: '反派逼近',
                en: 'Bad Guys Close In',
                hintZh: '内外压力收紧。队伍裂开，主角的办法开始失效。',
                hintEn: 'External and internal pressure tighten. The team cracks; the old plan fails.',
            },
            {
                id: 'stc_11_all_is_lost',
                no: '11',
                zh: '一无所有',
                en: 'All Is Lost',
                hintZh: '看起来失败的死亡拍：希望、关系、计划，或字面上的死。',
                hintEn: 'The whiff of death: hope, a relationship, a plan, or a literal death.',
            },
            {
                id: 'stc_12_dark_night',
                no: '12',
                zh: '灵魂黑夜',
                en: 'Dark Night of the Soul',
                hintZh: '最低处面对 Need。旧信念在这里撑不住。',
                hintEn: 'At the bottom the hero faces the Need. The old belief cannot hold.',
            },
        ],
    },
    {
        id: 'act3',
        zh: '第三幕 · 结局',
        en: 'Act III · Resolution',
        beats: [
            {
                id: 'stc_13_break_into_three',
                no: '13',
                zh: '进入第三幕',
                en: 'Break into Three',
                hintZh: '从灵魂黑夜里长出新办法。A 故事和 B 故事在这里合上。',
                hintEn: 'A new method grows out of the dark night. A story and B story join.',
            },
            {
                id: 'stc_14_finale',
                no: '14',
                zh: '终场',
                en: 'Finale',
                hintZh: '用新信念打最后一仗。危机抉择在这里兑现，证明主控思想。',
                hintEn: 'The last fight under the new belief. The crisis choice proves the controlling idea.',
            },
            {
                id: 'stc_15_final_image',
                no: '15',
                zh: '终场画面',
                en: 'Final Image',
                hintZh: '和开场对位的新平衡。观众能看出弧光已经发生。',
                hintEn: 'The new equilibrium, rhymed with the opening. The arc is visible.',
            },
        ],
    },
];

export const SAVE_THE_CAT_BEATS = SAVE_THE_CAT_ACTS.flatMap((act) => act.beats);

/** Emotion-driven prefill: Egri's Art of Dramatic Writing. Independent of the 15 beats. */
export const EMOTION_DRIVEN_SCRIPT_MODE = '情绪驱动类 / Emotion-Driven';

export function isEmotionDrivenScriptMode(value) {
    const raw = String(value || '').trim().toLowerCase();
    return raw.includes('情绪驱动') || raw.includes('emotion-driven') || raw.includes('emotion driven');
}

export const EGRI_CONCEPT_FIELDS = [
    {
        id: 'logline',
        labelZh: '一句话',
        labelEn: 'One Sentence',
        hintZh: '谁被什么冲突逼到必须选，选错会失去什么。这是故事，不是前提公式，也不是节拍表。',
        hintEn: 'Who is forced to choose, by what conflict, and what they lose if they choose wrong. The story, not the premise formula.',
        rows: 2,
    },
    {
        id: 'egri_premise',
        labelZh: '前提',
        labelEn: 'Premise',
        hintZh: '埃格里：这种性格，经过这场冲突，会证明什么结局。终局的选择必须能证明这句。',
        hintEn: 'Egri: this trait, through this conflict, proves this ending. The final choice must prove the sentence.',
        rows: 2,
    },
    {
        id: 'egri_pivotal',
        labelZh: '关键人物与攻击点',
        labelEn: 'Pivotal Character · Point of Attack',
        hintZh: '谁逼出变化。故事从哪一刀已经在进行的冲突切入，不从平静日常铺起。',
        hintEn: 'Who forces the change, and which already-moving conflict the story cuts into.',
        rows: 3,
    },
    {
        id: 'egri_unity',
        labelZh: '统一的对立面',
        labelEn: 'Unity of Opposites',
        hintZh: '双方各一句不肯让的信念。谁赢，都要拆掉对方的前提。中途退出等于放弃自己的前提。',
        hintEn: 'Each side has one belief they will not yield. Winning breaks the other premise. Leaving means giving up your own.',
        rows: 3,
    },
    {
        id: 'egri_dimensions',
        labelZh: '三维与编排',
        labelEn: 'Three Dimensions · Orchestration',
        hintZh: '生理只在它改变选择时写。社会是阶层、制度和群体里的位置。心理是那句信念。其他人每人只对照主角的一极。',
        hintEn: 'Physiology only if it changes a choice. Sociology is place in class and institution. Psychology is the belief. Each other person contrasts one pole.',
        rows: 5,
    },
    {
        id: 'egri_social',
        labelZh: '社会与人性',
        labelEn: 'Society · Human Nature',
        hintZh: '制度、阶层、舆论，或怕、愧、执念、责任，怎样把这一次选择变贵。抽掉这一层，代价变轻，就不合格。',
        hintEn: 'How institution, class, opinion, or fear, guilt, fixation, and duty make the choice costly. If removing the layer cheapens it, it is not landed.',
        rows: 3,
    },
    {
        id: 'egri_transition',
        labelZh: '过渡',
        labelEn: 'Transition',
        hintZh: '从哪一极走到哪一极。中间是哪一次冲突把旧信念逼裂。证明落在哪一阶。',
        hintEn: 'From which pole to which pole, which collision cracks the old belief, and which step proves it.',
        rows: 3,
    },
];

export const EGRI_STEPS = [
    {
        id: 'egri_01_attack',
        no: '01',
        zh: '攻击点',
        en: 'Point of Attack',
        hintZh: '冲突已经在进行。旧办法从这一刀起不可用。',
        hintEn: 'The conflict is already moving. The old method stops working from this cut.',
    },
    {
        id: 'egri_02_counter',
        no: '02',
        zh: '反攻',
        en: 'Counterattack',
        hintZh: '对立面用相反信念顶回来。代价比上一刀更贵。',
        hintEn: 'The opposite belief hits back, and the cost is higher than the last cut.',
    },
    {
        id: 'egri_03_lock',
        no: '03',
        zh: '锁死',
        en: 'Lock',
        hintZh: '谁退出，谁就放弃自己的前提。两边都不能走。',
        hintEn: 'Leaving means abandoning your premise. Neither side can walk away.',
    },
    {
        id: 'egri_04_orchestrate',
        no: '04',
        zh: '编排',
        en: 'Orchestration',
        hintZh: '另一个人从另一极把前提再辩一次，逼主角选边。',
        hintEn: 'Another person argues the premise from another pole and forces a side.',
    },
    {
        id: 'egri_05_transition',
        no: '05',
        zh: '过渡',
        en: 'Transition',
        hintZh: '旧信念裂开，新信念还没站稳。',
        hintEn: 'The old belief cracks. The new one has not taken hold.',
    },
    {
        id: 'egri_06_crisis',
        no: '06',
        zh: '危机',
        en: 'Crisis',
        hintZh: '两个都贵的选项。必须让出一个前提。',
        hintEn: 'Both options are costly. One premise has to be given up.',
    },
    {
        id: 'egri_07_proof',
        no: '07',
        zh: '证明',
        en: 'Proof',
        hintZh: '带代价的选择证明前提。这是高潮。',
        hintEn: 'A choice with a cost proves the premise. This is the climax.',
    },
    {
        id: 'egri_08_conclusion',
        no: '08',
        zh: '结局',
        en: 'Conclusion',
        hintZh: '新平衡。人已经不是攻击点上的那个人。',
        hintEn: 'The new balance. The person is no longer who they were at the attack.',
    },
];

export const EGRI_ONLY_KEYS = [
    ...EGRI_CONCEPT_FIELDS.map((field) => field.id).filter((id) => id !== 'logline'),
    ...EGRI_STEPS.map((step) => step.id),
    'story_circle',
];

const BEAT_IDS = SAVE_THE_CAT_BEATS.map((beat) => beat.id);

const ACT1_IDS = ['stc_01_opening_image', 'stc_02_theme_stated', 'stc_03_setup', 'stc_04_catalyst', 'stc_05_debate'];
const ACT2A_IDS = ['stc_06_break_into_two', 'stc_07_b_story', 'stc_08_fun_and_games'];
const ACT2B_IDS = ['stc_09_midpoint', 'stc_10_bad_guys_close_in', 'stc_11_all_is_lost', 'stc_12_dark_night'];
const FINALE_IDS = ['stc_13_break_into_three', 'stc_14_finale'];
const FINAL_IMAGE_IDS = ['stc_15_final_image'];

export const STORY_PREFILL_KEYS = [
    'logline',
    'theme',
    'core_conflict',
    'three_act',
    'background',
    'plot_background',
    'story_lines',
    'time_nodes',
    'professional_domains',
    'places_and_props',
    'characters',
    ...BEAT_IDS,
    'suspense',
    'foreshadowing',
    'classic_framework',
    'ai_vfx_strategy',
    'extra_notes',
];

export function emptyStoryPrefillFields() {
    const fields = {};
    STORY_PREFILL_KEYS.forEach((key) => {
        fields[key] = '';
    });
    EGRI_ONLY_KEYS.forEach((key) => {
        fields[key] = '';
    });
    fields.setup = '';
    fields.development = '';
    fields.turning_points = '';
    fields.climax = '';
    fields.resolution = '';
    return fields;
}

function joined(input, ids) {
    return ids
        .map((id) => String(input?.[id] || '').trim())
        .filter(Boolean)
        .join('\n');
}

export function hasSaveTheCatBeats(input) {
    return BEAT_IDS.some((id) => String(input?.[id] || '').trim());
}

export function rollupSaveTheCat(input) {
    const src = input || {};
    if (!hasSaveTheCatBeats(src)) {
        return {
            setup: String(src.setup || ''),
            development: String(src.development || ''),
            turning_points: String(src.turning_points || ''),
            climax: String(src.climax || ''),
            resolution: String(src.resolution || ''),
        };
    }
    return {
        setup: joined(src, ACT1_IDS),
        development: joined(src, ACT2A_IDS),
        turning_points: joined(src, ACT2B_IDS),
        climax: joined(src, FINALE_IDS),
        resolution: joined(src, FINAL_IMAGE_IDS),
    };
}

/** Old I6/I7 buckets stay readable inside the beat sheet until the user reruns prefill. */
export function migrateLegacyPlotToBeats(input) {
    const next = { ...(input || {}) };
    if (hasSaveTheCatBeats(next)) return next;
    const copy = (beatId, legacyKey) => {
        const legacy = String(next[legacyKey] || '').trim();
        if (legacy && !String(next[beatId] || '').trim()) next[beatId] = legacy;
    };
    copy('stc_03_setup', 'setup');
    copy('stc_08_fun_and_games', 'development');
    copy('stc_09_midpoint', 'turning_points');
    copy('stc_14_finale', 'climax');
    copy('stc_15_final_image', 'resolution');
    return next;
}

export const SERIES_IP_SCRIPT_MODE = '系列剧（IP模式） / Series IP';

export function isSeriesIpScriptMode(value) {
    const raw = String(value || '').trim().toLowerCase();
    return raw.includes('ip模式') || raw.includes('series ip') || raw.includes('ip mode');
}

const REGISTRY_FIELD_ALIASES = {
    plot_background: ['plot_background', '剧情背景'],
    story_lines: ['story_lines', '故事线'],
    time_nodes: ['time_nodes', '时间节点'],
    professional_domains: ['professional_domains', '专业领域'],
    places_and_props: ['places_and_props', '场景与道具'],
};

function registryText(value) {
    if (value == null) return '';
    if (typeof value === 'string') return value.trim();
    if (Array.isArray(value)) return value.map(registryText).filter(Boolean).join('\n');
    if (typeof value === 'object') {
        const lines = Object.entries(value)
            .map(([key, item]) => {
                const text = registryText(item);
                return text ? `${key}=${text}` : '';
            })
            .filter(Boolean);
        return lines.join('｜');
    }
    return String(value).trim();
}

/** Pull the five framework fields out of a task result, including Chinese keys and one nested object. */
export function liftStructuredPrefill(payload) {
    let data = payload;
    if (typeof data === 'string') {
        const text = data.trim();
        if (!text) return {};
        try {
            data = JSON.parse(text);
        } catch {
            return {};
        }
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
    let source = data;
    for (const key of ['result', 'data', 'fields', 'structured', '全局登记']) {
        const child = data[key];
        if (!child || typeof child !== 'object' || Array.isArray(child)) continue;
        if (child.logline || child.plot_background || child['剧情背景'] || child.places_and_props || child['场景与道具']) {
            source = { ...data, ...child };
            break;
        }
    }
    const next = { ...source };
    Object.entries(REGISTRY_FIELD_ALIASES).forEach(([english, aliases]) => {
        if (registryText(next[english])) return;
        for (const alias of aliases) {
            const text = registryText(next[alias]);
            if (text) {
                next[english] = text;
                break;
            }
        }
    });
    return next;
}

export function applyStructuredPrefill(prev, structured, emotionDriven) {
    structured = liftStructuredPrefill(structured);
    const next = { ...(prev || {}), wild_creative_notes: prev?.wild_creative_notes };
    if (emotionDriven) {
        const keys = [
            ...STORY_PREFILL_KEYS.filter((key) => !key.startsWith('stc_')),
            ...EGRI_ONLY_KEYS,
        ];
        keys.forEach((key) => {
            next[key] = String(structured?.[key] ?? '').trim();
        });
        SAVE_THE_CAT_BEATS.forEach((beat) => {
            next[beat.id] = '';
        });
        next.setup = '';
        next.development = '';
        next.turning_points = '';
        next.climax = '';
        next.resolution = '';
        return next;
    }
    STORY_PREFILL_KEYS.forEach((key) => {
        next[key] = String(structured?.[key] ?? '').trim();
    });
    EGRI_ONLY_KEYS.forEach((key) => {
        next[key] = '';
    });
    return { ...next, ...rollupSaveTheCat(next) };
}

export function composeSeriesIpEpisodeGuidance(input) {
    const src = input || {};
    const plot = String(src.ip_episode_plot || '').trim();
    const conflict = String(src.ip_episode_conflict || '').trim();
    const highlights = String(src.ip_episode_highlights || '').trim();
    const reference = String(src.ip_episode_reference || '').trim();
    const lines = [];
    if (plot) lines.push(`基本剧情：${plot}`);
    if (conflict) lines.push(`要体现的冲突：${conflict}`);
    if (highlights) lines.push(`重要亮点：${highlights}`);
    if (reference) lines.push(`对标参考（可参考剧情；须符合本集背景和主题，按本集因果融合，不能硬拼）：${reference}`);
    return lines.join('\n');
}

export function episodeOutlineProgress(markdown, episodesCount) {
    const text = String(markdown || '');
    const closed = new Set();
    const endRe = /\[\s*EPISODE_BLOCK_END\s*:\s*EP(\d+)\s*\]/gi;
    let match = endRe.exec(text);
    while (match) {
        closed.add(Number(match[1]));
        match = endRe.exec(text);
    }
    const complete = new Set();
    const startRe = /\[\s*EPISODE_BLOCK_START\s*:\s*EP(\d+)\s*\]/gi;
    match = startRe.exec(text);
    while (match) {
        const number = Number(match[1]);
        if (closed.has(number)) complete.add(number);
        match = startRe.exec(text);
    }
    const planned = Number(episodesCount) || 0;
    const missing = [];
    for (let number = 1; number <= planned; number += 1) {
        if (!complete.has(number)) missing.push(number);
    }
    return {
        completeCount: complete.size,
        missing,
        canResume: complete.size > 0 && missing.length > 0,
    };
}

export function storyPrefillPayloadFields(input) {
    const src = input || {};
    const fields = {};
    STORY_PREFILL_KEYS.forEach((key) => {
        fields[key] = String(src[key] ?? '');
    });
    EGRI_ONLY_KEYS.forEach((key) => {
        fields[key] = String(src[key] ?? '');
    });
    return {
        ...fields,
        ...rollupSaveTheCat(src),
        wild_creative_notes: String(src.wild_creative_notes ?? ''),
        extra_notes: String(src.extra_notes ?? ''),
        episode_generation_guidance: String(src.episode_generation_guidance ?? ''),
        ip_episode_plot: String(src.ip_episode_plot ?? ''),
        ip_episode_conflict: String(src.ip_episode_conflict ?? ''),
        ip_episode_highlights: String(src.ip_episode_highlights ?? ''),
        ip_episode_reference: String(src.ip_episode_reference ?? ''),
    };
}
