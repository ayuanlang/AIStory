const fs = require('fs');

const normalizeAsciiWordSeparators = (value) => {
    return String(value || '').replace(/[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+/g, (matched) => {
        return matched.replace(/[_-]+/g, ' ');
    });
};

const normalizeEntityToken = (value) => {
    let text = String(value || '')
        .replace(/[（【〔［]/g, '(')
        .replace(/[）】〕］]/g, ')')
        .replace(/[“”'‘’`]/g, '')
        .replace(/[\u2010-\u2015]/g, '-')
        .replace(/\s+/g, ' ')
        .trim();

    text = text.replace(/^(CHAR|ENV|PROP|VEFX|SFX|角色|人物|环境|场景|道具|物件|特效|视觉特效|音效|声音特效)\s*[:：]\s*/i, '').trim();

    for (let i = 0; i < 3; i += 1) {
        const next = text
            .replace(/^[\[\{【｛\(\s]+|[\]\}】｝\)\s]+$/g, '')
            .replace(/^@+/, '')
            .trim();
        if (next === text) break;
        text = next;
    }

    text = normalizeAsciiWordSeparators(text)
        .replace(/\s+/g, ' ')
        .trim();

    return text.toLowerCase();
};

const normalizeEntityComparableToken = (value) => {
    const normalized = normalizeEntityToken(value);
    if (!normalized) return '';
    return normalized
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
};

const getEntityFallbackEnglishName = (entityOrDescription) => {
    const description = typeof entityOrDescription === 'string'
        ? entityOrDescription
        : entityOrDescription?.description;
    if (!description) return '';

    const match = String(description).match(/Name \(EN\):\s*([^\n\r]+)/i);
    if (!match?.[1]) return '';

    return String(match[1])
        .trim()
        .split(/(?:\s+role:|\n|,)/)[0]
        .trim();
};

const collectEntityRawNames = (entity) => {
    const values = [
        entity?.name,
        entity?.name_zh,
        entity?.name_en,
        entity?.subject_name_exact,
        entity?.subject_name,
        getEntityFallbackEnglishName(entity),
    ];
    return Array.from(new Set(values
        .map((value) => String(value || '').trim())
        .filter(Boolean)));
};

const escapeRegExp = (value) => String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const buildComparableEntityPattern = (value) => {
    const comparable = normalizeEntityComparableToken(value);
    if (!comparable) return null;

    const segments = comparable.split(' ').filter(Boolean).map(escapeRegExp);
    if (!segments.length) return null;

    const body = segments.join('[\\s_-]+');
    return new RegExp(`(^|[^\\p{L}\\p{N}])(${body})(?=$|[^\\p{L}\\p{N}])`, 'iu');
};

const entityTokenMatchesName = (entity, rawToken) => {
    const strictToken = normalizeEntityToken(rawToken);
    const comparableToken = normalizeEntityComparableToken(rawToken);
    if (!strictToken && !comparableToken) return false;

    return collectEntityRawNames(entity).some((name) => {
        const strictName = normalizeEntityToken(name);
        if (strictName && strictName === strictToken) return true;

        const comparableName = normalizeEntityComparableToken(name);
        if (comparableName && comparableName === comparableToken) return true;

        const pattern = buildComparableEntityPattern(rawToken);
        if (pattern && pattern.test(String(name || ''))) return true;

        return false;
    });
};

const collectMatchedEntitiesFromPrompt = (source, entities) => {
    const rawMatches = [];
    const sourceText = source;

    const regexes = [
        /\[([\s\S]+?)\]/g,
        /\{([\s\S]+?)\}/g,
        /【([\s\S]+?)】/g,
        /｛([\s\S]+?)｝/g,
        /(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)/g,
    ];

    regexes.forEach((regex) => {
        regex.lastIndex = 0;
        let match;
        while ((match = regex.exec(sourceText)) !== null) {
            if (match[1]) rawMatches.push(match[1]);
        }
    });

    const typedRefRegex = /(CHAR\s*:\s*\[@([^\]]+)\])|(ENV\s*:\s*\[([^\]]+)\])|(PROP\s*:\s*\[([^\]]+)\])/gi;
    let typedMatch;
    typedRefRegex.lastIndex = 0;
    while ((typedMatch = typedRefRegex.exec(sourceText)) !== null) {
        rawMatches.push(typedMatch[2] || typedMatch[4] || typedMatch[6] || '');
    }

    const candidates = new Set();
    rawMatches
        .map((value) => String(value || '').trim())
        .filter(Boolean)
        .forEach((raw) => {
            const content = raw.replace(/[\[\]\{\}【】｛｝]/g, '');
            const normalized = normalizeEntityToken(content);
            if (normalized) candidates.add(normalized);
        });

    return entities.filter((entity) => {
        return Array.from(candidates).some((candidate) => entityTokenMatchesName(entity, candidate));
    });
};

const entities = [
    { name: 'Villa Dining Room', image_url: 'http://env1' },
    { name: '@慕依若', image_url: 'http://char1' },
    { name: '尹老爷子', image_url: 'http://char2' },
];

const sourceText = "对视频@Video1进行延长续写，根据用户提示重新生成后续内容，确保主体连续性，并自然过渡到新的场景或动作。 \n严格按以下提示词重新开始续写新视频：\n@Image1 CHAR:[@慕依若] \n@Image2 CHAR:[尹老爷子] \n镜头从门外的视角拍摄，镜头向左慢慢移动\n\n位于ENV:[Villa Dining Room](luxury dining room with a long dining table, chandelier, exquisite tableware, large floor-to-ceiling windows) 的 餐厅\n\n尹老爷子，老爷爷，穿着唐装，威严地坐在主位，手里拿着茶杯。慕依若，美少女，穿着白色连衣裙，战战兢兢地站在尹老爷子旁边，低着头，神情紧张。";
const res = collectMatchedEntitiesFromPrompt(sourceText, entities);

console.log('Matches:', res.map(e => e.name));
