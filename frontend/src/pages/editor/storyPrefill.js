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
    'characters',
    ...BEAT_IDS,
    'suspense',
    'foreshadowing',
    'classic_framework',
    'extra_notes',
];

export function emptyStoryPrefillFields() {
    const fields = {};
    STORY_PREFILL_KEYS.forEach((key) => {
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

export function storyPrefillPayloadFields(input) {
    const src = input || {};
    const fields = {};
    STORY_PREFILL_KEYS.forEach((key) => {
        fields[key] = String(src[key] ?? '');
    });
    return {
        ...fields,
        ...rollupSaveTheCat(src),
        wild_creative_notes: String(src.wild_creative_notes ?? ''),
        extra_notes: String(src.extra_notes ?? ''),
        episode_generation_guidance: String(src.episode_generation_guidance ?? ''),
    };
}
