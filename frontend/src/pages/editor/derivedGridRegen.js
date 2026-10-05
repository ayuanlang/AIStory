/**
 * Derived-environment image regen: slice one cell out of the main environment
 * four-grid prompt, then correct that cell instead of cropping it.
 *
 * Degree layout matches `resolve_grid_for_angle` / `extract_grid_cell_prompt`
 * in derived_env_ingest.py.
 */

const QUAD_POS_ORDER = ['左上', '右上', '左下', '右下'];
const LOCKED_QUAD_DEGREES = { 左上: 0, 右上: 90, 左下: 180, 右下: 270 };
const PANEL_TITLE_RE = /\[(0|90|180|270)度格[-－—](左上|右上|右下|左下)/g;
const QUAD_LINE_RE = /四宫度数\s*[=：:]\s*([^。\n]+)/;
const QUAD_PAIR_RE = /(左上|右上|左下|右下)\s*[=：:]?\s*(0|90|180|270)\s*度/g;

export const DERIVED_GRID_REGEN_NEGATIVE = [
    'people',
    'person',
    'human',
    'dutch angle',
    'tilted horizon',
    'looking into a room corner',
    'new room',
    'different building',
    'different location',
    'four-panel grid lines',
    '2x2 collage seams',
    'panel borders',
    'quadrant labels',
    'split-screen divider',
    'degree badge',
    'compass rose',
].join(', ');

const readAttrs = (entity) => {
    const raw = entity?.custom_attributes ?? entity?.customAttributes;
    if (!raw) return {};
    if (typeof raw === 'string') {
        try {
            const parsed = JSON.parse(raw);
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch {
            return {};
        }
    }
    return typeof raw === 'object' ? raw : {};
};

const normName = (value) => String(value || '')
    .trim()
    .replace(/^(?:ENV|CHAR|PROP)\s*[:：]\s*/i, '')
    .replace(/^\[+|\]+$/g, '')
    .trim()
    .toLowerCase();

export function isEnvironmentEntity(entity) {
    const type = String(entity?.type || '').trim().toLowerCase();
    if (!type) return false;
    return type === 'environment' || type === 'env' || type.includes('environment') || type.includes('环境');
}

const isAngledName = (value) => /^(?:\d+|[０-９]+)\s*(?:度|°|º|deg(?:ree)?s?\b)/i.test(String(value || '').trim());

export function isMainEnvironmentEntity(entity) {
    if (!entity || entity.is_deleted) return false;
    if (!isEnvironmentEntity(entity)) return false;
    if (isAngledName(entity.name) || isAngledName(entity.name_en)) return false;
    const attrs = readAttrs(entity);
    if (attrs.source === 'programmatic_derived_framing') return false;
    if (attrs.derived_kind) return false;
    return true;
}

export function parseQuadDegreesFromPrompt(prompt) {
    const text = String(prompt || '');
    const line = text.match(QUAD_LINE_RE);
    if (line) {
        const mapping = {};
        const pairRe = new RegExp(QUAD_PAIR_RE.source, 'g');
        let match = pairRe.exec(line[1]);
        while (match) {
            mapping[match[1]] = Number(match[2]);
            match = pairRe.exec(line[1]);
        }
        const degrees = new Set(Object.values(mapping));
        if (QUAD_POS_ORDER.every((pos) => Object.prototype.hasOwnProperty.call(mapping, pos)) && degrees.size === 4) {
            return mapping;
        }
    }
    const fromTitles = {};
    const titleRe = new RegExp(PANEL_TITLE_RE.source, 'g');
    let title = titleRe.exec(text);
    while (title) {
        fromTitles[title[2]] = Number(title[1]);
        title = titleRe.exec(text);
    }
    const titleDegrees = new Set(Object.values(fromTitles));
    if (QUAD_POS_ORDER.every((pos) => Object.prototype.hasOwnProperty.call(fromTitles, pos)) && titleDegrees.size === 4) {
        return fromTitles;
    }
    return { ...LOCKED_QUAD_DEGREES };
}

export function resolveGridForAngle(angle, mainPrompt = '') {
    const mapping = mainPrompt ? parseQuadDegreesFromPrompt(mainPrompt) : { ...LOCKED_QUAD_DEGREES };
    const angleToPos = {};
    Object.entries(mapping).forEach(([pos, deg]) => {
        angleToPos[Number(deg)] = pos;
    });
    const resolved = [0, 90, 180, 270].includes(Number(angle)) ? Number(angle) : 0;
    const position = angleToPos[resolved] || QUAD_POS_ORDER.find((pos) => LOCKED_QUAD_DEGREES[pos] === resolved) || '左上';
    const quadLine = `四宫度数=${QUAD_POS_ORDER.map((pos) => `${pos}${Number(mapping[pos])}度`).join('｜')}`;
    return {
        grid: `${position}${resolved}度格`,
        token: `${position}${resolved}度`,
        quadLine,
        position,
        angle: String(resolved),
    };
}

export function listPanelTitles(prompt) {
    const text = String(prompt || '');
    const titles = [];
    const titleRe = new RegExp(PANEL_TITLE_RE.source, 'g');
    let match = titleRe.exec(text);
    while (match) {
        titles.push({
            index: match.index,
            angle: Number(match[1]),
            position: match[2],
        });
        match = titleRe.exec(text);
    }
    return titles;
}

export function extractGridCellPrompt(mainPrompt, angle) {
    const crop = resolveGridForAngle(angle, mainPrompt);
    const text = String(mainPrompt || '');
    const titles = listPanelTitles(text);
    const targetAngle = Number(crop.angle);
    const chosen = titles.find((item) => item.angle === targetAngle && item.position === crop.position)
        || titles.find((item) => item.angle === targetAngle)
        || null;
    let cellPrompt = '';
    if (chosen) {
        const later = titles.filter((item) => item.index > chosen.index).map((item) => item.index);
        const end = later.length ? Math.min(...later) : text.length;
        cellPrompt = text.slice(chosen.index, end).trim();
    }
    return { ...crop, cellPrompt };
}

export function gridCellBody(cellPrompt) {
    return String(cellPrompt || '').replace(/^\[[^\]]*\]\s*/, '').trim();
}

export function gridCropPixels(width, height, position) {
    const sourceWidth = Math.max(0, Math.round(Number(width) || 0));
    const sourceHeight = Math.max(0, Math.round(Number(height) || 0));
    const cropWidth = Math.max(1, Math.round(sourceWidth / 2));
    const cropHeight = Math.max(1, Math.round(sourceHeight / 2));
    const right = position === '右上' || position === '右下';
    const bottom = position === '左下' || position === '右下';
    return {
        x: right ? Math.max(0, sourceWidth - cropWidth) : 0,
        y: bottom ? Math.max(0, sourceHeight - cropHeight) : 0,
        width: Math.min(cropWidth, sourceWidth || cropWidth),
        height: Math.min(cropHeight, sourceHeight || cropHeight),
    };
}

export function resolveDerivedViewAngle(entity) {
    const attrs = readAttrs(entity);
    const fromAttr = Number(attrs.view_angle_from_main);
    if ([0, 90, 180, 270].includes(fromAttr)) return fromAttr;
    const prompt = String(entity?.generation_prompt_cn || '');
    const key = prompt.match(/angle_key=[^|｜\n]*[|｜]\s*(0|90|180|270)/);
    if (key) return Number(key[1]);
    const token = prompt.match(/截取宫格=\s*(?:左上|右上|左下|右下)?\s*(0|90|180|270)/);
    if (token) return Number(token[1]);
    const nameMatch = String(entity?.name || '').match(/(?:^|[^\d])(0|90|180|270)\s*度/);
    if (nameMatch) return Number(nameMatch[1]);
    return null;
}

export function isGridCropDerivedEntity(entity) {
    if (!isEnvironmentEntity(entity)) return false;
    const attrs = readAttrs(entity);
    const kind = String(attrs.derived_kind || '').trim();
    if (kind === 'state') return false;
    if (kind === 'first_cut') return true;
    return String(entity?.generation_prompt_cn || '').includes('只切割');
}

const dependencyNames = (entity) => {
    const raw = entity?.visual_dependencies ?? entity?.visualDependencies;
    let list = raw;
    if (typeof raw === 'string') {
        const text = raw.trim();
        if (!text) return [];
        try {
            list = JSON.parse(text);
        } catch {
            list = text.split(/[,，;；\n]+/);
        }
    }
    if (!Array.isArray(list)) return [];
    return list.map((item) => normName(item)).filter(Boolean);
};

const mainNameCandidates = (entity) => {
    const attrs = readAttrs(entity);
    const names = [];
    ['main_environment', 'main_environment_name', '所属主环境', 'owning_main_environment'].forEach((key) => {
        const value = normName(attrs[key]);
        if (value) names.push(value);
    });
    const stripped = String(entity?.name || '')
        .trim()
        .replace(/^(?:\d+|[０-９]+)\s*(?:度|°|º|deg(?:ree)?s?\b)\s*/i, '')
        .trim();
    const fromName = normName(stripped);
    if (fromName && fromName !== normName(entity?.name)) names.push(fromName);
    dependencyNames(entity).forEach((name) => names.push(name));
    return names;
};

const findOwningMainEnvironment = (entity, entities) => {
    const wanted = new Set(mainNameCandidates(entity));
    if (!wanted.size) return null;
    const matches = (Array.isArray(entities) ? entities : []).filter((candidate) => {
        if (!isMainEnvironmentEntity(candidate)) return false;
        return wanted.has(normName(candidate?.name)) || wanted.has(normName(candidate?.name_en));
    });
    if (!matches.length) return null;
    const episodeId = String(entity?.episode_id || '').trim();
    const scored = matches.map((candidate) => {
        let score = 0;
        if (episodeId && String(candidate?.episode_id || '').trim() === episodeId) score += 4;
        if (String(candidate?.generation_prompt_cn || '').trim()) score += 2;
        if (String(candidate?.image_url || '').trim()) score += 1;
        return { candidate, score };
    });
    scored.sort((left, right) => right.score - left.score);
    return scored[0]?.candidate || null;
};

export const GRID_REGEN_PROMPT_ATTR = 'grid_regen_prompt';

export function readSavedGridRegenPrompt(entity) {
    const raw = entity?.custom_attributes ?? entity?.customAttributes;
    let attrs = {};
    if (typeof raw === 'string') {
        try {
            const parsed = JSON.parse(raw);
            attrs = parsed && typeof parsed === 'object' ? parsed : {};
        } catch {
            attrs = {};
        }
    } else if (raw && typeof raw === 'object') {
        attrs = raw;
    }
    return String(attrs[GRID_REGEN_PROMPT_ATTR] || '').trim();
}

export const DERIVED_GRID_REGEN_APPEARANCE_LOCK = '画面中所有主体的大小、形状、细节、色泽、风格都必须与这张主环境参考图完全一致，只能调整摆位、朝向、走向和位置。禁止改大小、改形状、改细节、改色泽或改风格。';

export function ensureDerivedGridRegenAppearanceLock(text) {
    const value = String(text || '').trim();
    if (!value || value.includes(DERIVED_GRID_REGEN_APPEARANCE_LOCK)) return value;
    return `${DERIVED_GRID_REGEN_APPEARANCE_LOCK}\n${value}`;
}

export function resolveSubmittedGridRegenPrompt(entity, plan, draft) {
    let text = '';
    if (typeof draft === 'string') text = draft.trim();
    else {
        const saved = readSavedGridRegenPrompt(entity);
        text = saved || String(plan?.regenPrompt || '').trim();
    }
    return ensureDerivedGridRegenAppearanceLock(stripOpeningWorldFromRegenPrompt(text));
}

function markedSection(text, name) {
    const source = String(text || '');
    const start = source.indexOf(`【${name}】`);
    if (start < 0) return '';
    const rest = source.slice(start + `【${name}】`.length);
    const next = rest.search(/【(?:定位|主体外形|六面一次|北壁|东壁|南壁|西壁|中区|光学说明|色彩说明|构图|四向拼图)】/);
    const body = next < 0 ? rest : rest.slice(0, next);
    return `【${name}】${body}`.trim();
}

export function quadImagePrompt(text) {
    const raw = stripMainEnvironmentDraftWrapper(text);
    const index = raw.indexOf('【四向拼图】');
    if (index < 0) return raw.trim();
    const style = raw.slice(0, index).match(/\[Global Style\]\([^)]*\)\.?/);
    const prefix = style ? style[0].trim() : '';
    const quad = raw.slice(index).trim();
    const kept = [prefix, markedSection(raw, '定位'), markedSection(raw, '主体外形'), quad]
        .map((part) => String(part || '').trim())
        .filter(Boolean);
    return kept.join('\n\n');
}

export function stripMainEnvironmentDraftWrapper(text) {
    return String(text || '').replace(/^【\/?主环境设计稿】[^\n]*\n?/gm, '').trim();
}

function openingBeforeQuad(value) {
    const text = stripMainEnvironmentDraftWrapper(value);
    const index = text.indexOf('【四向拼图】');
    if (index < 0) return text;
    return text.slice(0, index).trim();
}

export function mainEnvironmentOpeningDraft(entity) {
    const attrs = readAttrs(entity);
    return openingBeforeQuad(attrs.main_environment_opening || '')
        || openingBeforeQuad(entity?.generation_prompt_cn || entity?.prompt || '');
}

export function assetCardIntro(entity) {
    const raw = String(entity?.generation_prompt_cn || entity?.description || '');
    if (isMainEnvironmentEntity(entity) && raw.includes('【四向拼图】')) {
        return quadImagePrompt(raw);
    }
    return stripMainEnvironmentDraftWrapper(raw);
}

export function stripOpeningWorldFromRegenPrompt(text) {
    const openingSection = /【(?:定位|六面一次|北壁|东壁|南壁|西壁|中区|光学说明|色彩说明|构图|本角开篇可见面|主体材质一次)】[\s\S]*?(?=【(?:定位|六面一次|北壁|东壁|南壁|西壁|中区|光学说明|色彩说明|构图|本角开篇可见面|主体材质一次)】|\[(?:0|90|180|270)度格|$)/g;
    return String(text || '')
        .replace(openingSection, '')
        .replace(/\[(0|90|180|270)度格[-－—](左上|右上|右下|左下)·[北东南西]\]/g, '[$1度格-$2]')
        .replace(/^\s*角标=.*$/gm, '')
        .replace(/[ \t]*角标=[^。\n]*[。]?/g, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

export function buildDerivedGridRegenPrompt({ mainName, grid, cellPrompt }) {
    const cell = stripOpeningWorldFromRegenPrompt(cellPrompt);
    return [
        `参照这张参考图。它是主环境「${mainName}」四向拼图中的${grid}，作为该格画面参照。`,
        '按下面这一格提示词修正生成一张16:9单镜头成片。',
        DERIVED_GRID_REGEN_APPEARANCE_LOCK,
        '成片去掉宫格分割线、角标、格标、度数标和拼缝，仍是这一格里的同一处空间，单张完整镜头。',
        '光学、结构和摆位以这一格画面句为准。',
        '',
        cell,
    ].join('\n');
}

export function planDerivedGridRegen(entity, entities) {
    if (!isGridCropDerivedEntity(entity)) return { ok: false, errorCode: 'not_grid_crop' };
    const angle = resolveDerivedViewAngle(entity);
    if (angle == null) return { ok: false, errorCode: 'missing_angle' };
    const mainEntity = findOwningMainEnvironment(entity, entities);
    if (!mainEntity) return { ok: false, errorCode: 'missing_main' };
    const mainPrompt = String(mainEntity.generation_prompt_cn || '').trim();
    if (!mainPrompt) return { ok: false, errorCode: 'missing_main_prompt', mainEntity, mainName: mainEntity.name || '' };
    const extracted = extractGridCellPrompt(mainPrompt, angle);
    if (!gridCellBody(extracted.cellPrompt)) {
        return {
            ok: false,
            errorCode: 'missing_cell',
            mainEntity,
            mainName: mainEntity.name || '',
            ...extracted,
        };
    }
    if (!String(mainEntity.image_url || '').trim()) {
        return {
            ok: false,
            errorCode: 'missing_main_image',
            mainEntity,
            mainName: mainEntity.name || '',
            ...extracted,
        };
    }
    return {
        ok: true,
        errorCode: '',
        mainEntity,
        mainName: String(mainEntity.name || mainEntity.name_en || '').trim(),
        ...extracted,
        regenPrompt: buildDerivedGridRegenPrompt({
            mainName: String(mainEntity.name || mainEntity.name_en || '').trim(),
            grid: extracted.grid,
            cellPrompt: extracted.cellPrompt,
        }),
    };
}
