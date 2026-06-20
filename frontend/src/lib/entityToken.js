const normalizeAsciiWordSeparators = (value) => {
    return String(value || '').replace(/[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+/g, (matched) => {
        return matched.replace(/[_-]+/g, ' ');
    });
};

export const normalizeEntityToken = (value) => {
    let text = String(value || '')
        .replace(/[（【〔［]/g, '(')
        .replace(/[）】〕］]/g, ')')
        .replace(/[“”"'‘’`]/g, '')
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

export const normalizeEntityComparableToken = (value) => {
    const normalized = normalizeEntityToken(value);
    if (!normalized) return '';
    return normalized
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
};

const TYPED_ENTITY_REF_REGEX = /CHAR\s*:\s*\[@([^\]]+)\]|ENV\s*:\s*\[([^\]]+)\]|PROP\s*:\s*\[([^\]]+)\]/gi;

export const extractTypedEntityRawNames = (text) => {
    const source = String(text || '');
    if (!source) return [];

    const names = [];
    let match;
    TYPED_ENTITY_REF_REGEX.lastIndex = 0;
    while ((match = TYPED_ENTITY_REF_REGEX.exec(source)) !== null) {
        const name = String(match[1] || match[2] || match[3] || '').trim();
        if (name) names.push(name);
    }
    return names;
};

const isPollutedEntityCapture = (name) => {
    const text = String(name || '').trim();
    if (!text) return true;
    if (/^(CHAR|ENV|PROP)\s*:\s*\[[^\]]+\]\s+\S/i.test(text)) return true;
    if (text.length > 80) return true;
    return false;
};

export const extractEntityRawNamesFromPrompt = (text) => {
    const source = String(text || '');
    if (!source) return [];

    const rawNames = [...extractTypedEntityRawNames(source)];
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
        while ((match = regex.exec(source)) !== null) {
            const captured = String(match[1] || '').trim();
            if (!captured || isPollutedEntityCapture(captured)) continue;
            rawNames.push(captured);
        }
    });

    const seen = new Set();
    const unique = [];
    rawNames.forEach((name) => {
        const key = normalizeEntityToken(name);
        if (!key || seen.has(key)) return;
        seen.add(key);
        unique.push(String(name || '').trim());
    });
    return unique.filter(Boolean);
};

export const getEntityFallbackEnglishName = (entityOrDescription) => {
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

export const entityTokenMatchesName = (entity, rawToken) => {
    const strictToken = normalizeEntityToken(rawToken);
    const comparableToken = normalizeEntityComparableToken(rawToken);
    if (!strictToken && !comparableToken) return false;

    const names = collectEntityRawNames(entity);

    // Exact match passes first
    if (names.some((name) => {
        const strictName = normalizeEntityToken(name);
        if (strictName && strictToken && strictName === strictToken) return true;

        const comparableName = normalizeEntityComparableToken(name);
        return Boolean(comparableName && comparableToken && comparableName === comparableToken);
    })) {
        return true;
    }

    // Fallback: Strip parentheses from the rawToken (e.g. "行李箱(大型)" -> "行李箱")
    const baseRawToken = strictToken.split('(')[0].trim();
    if (!baseRawToken) return false;
    const baseComparableToken = normalizeEntityComparableToken(baseRawToken);

    return names.some((name) => {
        const strictName = normalizeEntityToken(name).split('(')[0].trim();
        if (strictName && strictName === baseRawToken) return true;
        const comparableName = normalizeEntityComparableToken(name.split('(')[0].trim());
        return Boolean(comparableName && baseComparableToken && comparableName === baseComparableToken);
    });
};

export const entityNameAppearsInText = (entity, sourceText) => {
    const text = String(sourceText || '');
    if (!text.trim()) return false;

    return collectEntityRawNames(entity).some((name) => {
        const pattern = buildComparableEntityPattern(name);
        if (!pattern) return false;

        let match;
        pattern.lastIndex = 0;
        while ((match = pattern.exec(text)) !== null) {
            const prefix = String(match[1] || '');
            const matchedBody = String(match[2] || '');
            const tail = text.slice(match.index + prefix.length + matchedBody.length);
            if (/^(?:$|\s*[\]\[\)\(\}\{,.;:!?"'，。；：！、]|\s*['’]s\b)/u.test(tail)) {
                return true;
            }
            if (!pattern.global) break;
        }
        return false;
    });
};
