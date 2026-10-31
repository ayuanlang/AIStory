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

export function isDerivedMainEnvironmentEntity(entity) {
    if (!entity || entity.is_deleted) return false;
    if (!isEnvironmentEntity(entity)) return false;
    if (isAngledName(entity.name) || isAngledName(entity.name_en)) return false;
    return String(readAttrs(entity).derived_kind || '').trim() === 'derived_main';
}

const headEnvironmentName = (value) => String(value || '').trim().split(/[｜|]/)[0].trim();

const labeledDerivedField = (text, label) => {
    const match = String(text || '').match(new RegExp(`${label}\\s*[=＝:：]\\s*([^。\\n]+)`));
    const value = String(match?.[1] || '').trim();
    if (!value || value === '无') return '';
    return value;
};

const strategyLogic = (entity) => {
    const raw = entity?.dependency_strategy;
    if (!raw) return '';
    if (typeof raw === 'string') return raw;
    return String(raw.logic || '');
};

/**
 * Identity for regenerating one derived main.
 * The design prompt stays the delta, and the source main's four-grid is the dependency.
 */
export function derivedMainRegenHint(entity, entities) {
    if (!entity || !isEnvironmentEntity(entity)) return null;
    const name = headEnvironmentName(entity.name || entity.name_en);
    if (!name || isAngledName(name)) return null;
    const attrs = readAttrs(entity);
    const labeledText = `${entity.generation_prompt_cn || ''}\n${strategyLogic(entity)}`;
    let source = String(attrs.source_main_environment || '').trim();
    const mainEnv = String(attrs.main_environment || '').trim();
    if (!source && mainEnv && mainEnv !== name) source = mainEnv;
    if (!source) source = labeledDerivedField(labeledText, '被依赖主环境');
    let delta = String(attrs.state_delta || '').trim() || labeledDerivedField(labeledText, '状态Delta');
    if (String(attrs.derived_kind || '').trim() === 'derived_main' && source && source !== name) {
        return { name, source, delta };
    }
    const children = (Array.isArray(entities) ? entities : []).filter((row) => {
        if (!row || row === entity) return false;
        const child = readAttrs(row);
        if (String(child.derived_main_environment || '').trim() !== name) return false;
        return isAngledName(row.name) || isAngledName(row.name_en) || Boolean(child.derived_from_state);
    });
    if (children.length) {
        const sources = [];
        const deltas = [];
        children.forEach((row) => {
            const child = readAttrs(row);
            const childSource = String(child.source_main_environment || '').trim();
            const childDelta = String(child.state_delta || '').trim();
            if (childSource && !sources.includes(childSource)) sources.push(childSource);
            if (childDelta && childDelta !== '无' && !deltas.includes(childDelta)) deltas.push(childDelta);
        });
        const picked = sources[0] || source;
        if (picked && picked !== name) {
            return { name, source: picked, delta: deltas.join('；') || delta };
        }
    }
    const mainNames = (Array.isArray(entities) ? entities : [])
        .filter((row) => (
            row
            && row !== entity
            && isEnvironmentEntity(row)
            && !isAngledName(row.name)
            && !isAngledName(row.name_en)
            && !isDerivedMainEnvironmentEntity(row)
        ))
        .map((row) => headEnvironmentName(row.name || row.name_en))
        .filter(Boolean)
        .sort((left, right) => right.length - left.length);
    const prefix = mainNames.find((main) => name.startsWith(`${main}_`) && name.length > main.length + 1) || '';
    if (prefix) return { name, source: prefix, delta };
    const derivedName = labeledDerivedField(labeledText, '衍生主环境');
    if (source && derivedName && derivedName !== source) {
        return { name: derivedName, source, delta };
    }
    return null;
}

export const PENDING_DERIVED_PROMPT = '待生成';

export function promptForDerivedGeneration(entity, prompt) {
    const text = String(prompt || '').trim();
    if (text) return text;
    if (!isEnvironmentEntity(entity) || isMainEnvironmentEntity(entity)) return text;
    return PENDING_DERIVED_PROMPT;
}

/** Derived environments take style from the main-environment asset, not project info. */
export function omitsProjectStyleInjection(entity) {
    if (!isEnvironmentEntity(entity)) return false;
    if (isDerivedMainEnvironmentEntity(entity)) return true;
    return !isMainEnvironmentEntity(entity);
}

export function stripProjectStyleInjection(text) {
    return String(text || '')
        .replace(/\[Global Style\]\s*(?:\([^)]*\))?\.?\s*/gi, '')
        .replace(/[\[【]\s*global_style\s*[\]】]\s*(?:\([^)]*\))?\.?\s*/gi, '')
        .trim();
}

export function isMainEnvironmentEntity(entity) {
    if (!entity || entity.is_deleted) return false;
    if (!isEnvironmentEntity(entity)) return false;
    if (isDerivedMainEnvironmentEntity(entity)) return true;
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

export const QUAD_CELL_POSITIONS = ['左上', '右上', '左下', '右下'];
export const QUAD_CELL_IMAGES_ATTR = 'quad_cell_images';

const parseJsonRecord = (value) => {
    if (!value) return null;
    if (typeof value === 'string') {
        const text = value.trim();
        if (!text.startsWith('{') && !text.startsWith('[')) return null;
        try {
            return parseJsonRecord(JSON.parse(text));
        } catch {
            return null;
        }
    }
    return typeof value === 'object' ? value : null;
};

const COLLIDING_GRID_CELL_NAME = /^grid-cell-(?:左上|右上|左下|右下|cell)\.jpe?g$/i;

export function isCollidingGridCellUrl(url) {
    const text = String(url || '').trim();
    if (!text) return false;
    const path = text.split('?')[0].split('#')[0];
    let decoded = path;
    try {
        decoded = decodeURIComponent(path);
    } catch {
        decoded = path;
    }
    const base = decoded.split('/').pop() || '';
    return COLLIDING_GRID_CELL_NAME.test(base);
}

const cellImageUrl = (value) => {
    if (!value) return '';
    if (typeof value === 'string') {
        const text = value.trim();
        const nested = parseJsonRecord(text);
        if (nested) return cellImageUrl(nested.url || nested.image_url || nested.href || '');
        if (isCollidingGridCellUrl(text)) return '';
        return /^https?:\/\//i.test(text) || text.startsWith('/') ? text : '';
    }
    const record = parseJsonRecord(value);
    if (!record || Array.isArray(record)) return '';
    return cellImageUrl(record.url || record.image_url || record.href || '');
};

export function mediaPathname(url) {
    const text = String(url || '').trim();
    if (!text) return '';
    try {
        return decodeURIComponent(new URL(text, 'https://local.invalid').pathname || '');
    } catch {
        return text.split('#')[0].split('?')[0];
    }
}

export function sameMediaUrl(left, right) {
    const a = String(left || '').trim();
    const b = String(right || '').trim();
    if (!a || !b) return false;
    if (a === b) return true;
    const leftPath = mediaPathname(a);
    const rightPath = mediaPathname(b);
    return Boolean(leftPath) && leftPath === rightPath;
}

export function readQuadCellImages(entity, sourceUrl = '', options = {}) {
    const allowStale = Boolean(options.allowStale);
    const record = parseJsonRecord(readAttrs(entity)[QUAD_CELL_IMAGES_ATTR]);
    if (!record || Array.isArray(record)) return null;
    const storedSource = String(record.source_url || record.sourceUrl || '').trim();
    const wanted = String(sourceUrl || '').trim();
    if (!allowStale && wanted && storedSource && !sameMediaUrl(storedSource, wanted)) return null;
    const cells = parseJsonRecord(record.cells);
    if (!cells || Array.isArray(cells)) return null;
    const saved = {};
    QUAD_CELL_POSITIONS.forEach((position) => {
        const url = cellImageUrl(cells[position]);
        if (url) saved[position] = url;
    });
    return Object.keys(saved).length ? saved : null;
}

const QUAD_EDIT_LOCKS = [
    '只改这一格里点名的这一处。另外三格、格线、角标、没有点名的主体、光色和构图都保持原图不动。不要重画整张四宫。',
    '其余格子、格线、角标、没有点名的主体、光色和构图都保持原图不动。不要重画整张四宫。',
];

export function singleCellEditInstruction(instruction) {
    let text = String(instruction || '').trim();
    QUAD_EDIT_LOCKS.forEach((lock) => {
        text = text.split(lock).join('');
    });
    text = text.replace(/\n{3,}/g, '\n\n').trim();
    if (!text) return '';
    const prefix = '这张参考图是已经裁出的单格画面，不是四宫整图。只改这一张图里点名的地方，其余保持原图。不要把另外三格画回来。';
    if (text.includes('已经裁出的单格画面')) return text;
    return `${prefix}\n${text}`;
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

export function isStateDerivedEntity(entity) {
    if (!isEnvironmentEntity(entity)) return false;
    const kind = String(readAttrs(entity).derived_kind || '').trim();
    if (kind === 'state') return true;
    const prompt = String(entity?.generation_prompt_cn || '');
    return prompt.includes('以已切割的同角衍生') || prompt.includes('以同角衍生「') || prompt.includes('不要重切宫格');
}

export function isGridCropDerivedEntity(entity) {
    if (!isEnvironmentEntity(entity) || isStateDerivedEntity(entity)) return false;
    const kind = String(readAttrs(entity).derived_kind || '').trim();
    if (kind === 'first_cut') return true;
    return String(entity?.generation_prompt_cn || '').includes('只切割');
}

/** Angle derivatives take one cropped cell. A derived main still uses the whole four-grid. */
export function usesCroppedCellReference(entity) {
    if (!isEnvironmentEntity(entity) || isDerivedMainEnvironmentEntity(entity)) return false;
    if (isMainEnvironmentEntity(entity)) return false;
    if (isGridCropDerivedEntity(entity)) return true;
    return isStateDerivedEntity(entity) && resolveDerivedViewAngle(entity) != null;
}

export function mainQuadCellAddresses(entity) {
    if (!isMainEnvironmentEntity(entity)) return [];
    const sourceUrl = String(entity?.image_url || '').trim();
    const cells = readQuadCellImages(entity, sourceUrl, { allowStale: true });
    if (!cells) return [];
    const mapping = parseQuadDegreesFromPrompt(entity?.generation_prompt_cn || '');
    return QUAD_CELL_POSITIONS.map((position) => ({
        position,
        degree: mapping[position],
        url: String(cells[position] || '').trim(),
    })).filter((row) => row.url);
}

export function derivedCellReference(entity, entities) {
    if (!isGridCropDerivedEntity(entity)) return null;
    const plan = planDerivedGridCell(entity, entities);
    if (!plan?.mainEntity || !plan.position) return null;
    const sourceUrl = String(plan.mainEntity.image_url || '').trim();
    const cells = readQuadCellImages(plan.mainEntity, sourceUrl) || {};
    return {
        mainId: String(plan.mainEntity.id || ''),
        position: plan.position,
        degree: plan.angle,
        url: String(cells[plan.position] || '').trim(),
    };
}

function savedQuadCellUrl(quad, position) {
    const sourceUrl = String(quad?.image_url || '').trim();
    const cells = readQuadCellImages(quad, sourceUrl) || {};
    return String(cells[position] || '').trim();
}

export function derivedDependencyImageUrl(owner, depEntity, entities) {
    const fallback = String(depEntity?.image_url || '').trim();
    if (!owner || !usesCroppedCellReference(owner)) return fallback;
    const plan = planDerivedCellReference(owner, entities);
    let quad = plan?.mainEntity && isMainEnvironmentEntity(plan.mainEntity) ? plan.mainEntity : null;
    let position = String(plan?.position || '').trim();
    const depIsQuad = isMainEnvironmentEntity(depEntity);
    if (!quad && depIsQuad) {
        const angle = resolveDerivedViewAngle(owner);
        if (angle == null) return '';
        const crop = resolveGridForAngle(angle, depEntity?.generation_prompt_cn || '');
        quad = depEntity;
        position = crop.position;
    }
    if (!quad || !position) return fallback;
    if (depEntity && !depIsQuad && String(depEntity.id || '') !== String(quad.id || '')) return fallback;
    return savedQuadCellUrl(quad, position);
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

const SPECIAL_DEGREE_SUFFIXES = new Set(['仰天', '变形', '屋顶']);

const degreeStrippedName = (entity) => {
    const raw = headEnvironmentName(entity?.name || '');
    const stripped = raw.replace(/^(?:\d+|[０-９]+)\s*(?:度|°|º|deg(?:ree)?s?\b)\s*/i, '').trim();
    if (!stripped || normName(stripped) === normName(raw)) return '';
    return stripped;
};

const scoreEnvironmentCandidate = (candidate, episodeId) => {
    let score = 0;
    if (episodeId && String(candidate?.episode_id || '').trim() === episodeId) score += 4;
    if (String(candidate?.generation_prompt_cn || '').trim()) score += 2;
    if (String(candidate?.image_url || '').trim()) score += 1;
    return score;
};

const findEnvironmentByExactName = (name, entities, self) => {
    const wanted = normName(headEnvironmentName(name));
    if (!wanted) return null;
    const matches = (Array.isArray(entities) ? entities : []).filter((candidate) => {
        if (!candidate || candidate === self || candidate.is_deleted) return false;
        if (!isEnvironmentEntity(candidate)) return false;
        if (isAngledName(candidate.name) || isAngledName(candidate.name_en)) return false;
        return normName(headEnvironmentName(candidate.name)) === wanted
            || normName(headEnvironmentName(candidate.name_en)) === wanted;
    });
    if (!matches.length) return null;
    if (matches.length === 1) return matches[0];
    const episodeId = String(self?.episode_id || '').trim();
    const scored = matches.map((candidate) => ({
        candidate,
        score: scoreEnvironmentCandidate(candidate, episodeId),
    }));
    scored.sort((left, right) => right.score - left.score);
    return scored[0]?.candidate || null;
};

const findOwningMainEnvironment = (entity, entities) => {
    const stripped = degreeStrippedName(entity);
    if (stripped) {
        const exact = findEnvironmentByExactName(stripped, entities, entity);
        if (exact) return exact;
        const suffix = stripped.includes('_') ? stripped.slice(stripped.lastIndexOf('_') + 1) : '';
        if (suffix && !SPECIAL_DEGREE_SUFFIXES.has(suffix)) return null;
    }
    const attrs = readAttrs(entity);
    const derivedMain = normName(attrs.derived_main_environment);
    const sourceMain = normName(attrs.source_main_environment);
    const declaredMain = normName(attrs.main_environment || attrs['所属主环境']);
    const fromDerivedMain = Boolean(attrs.derived_from_state)
        || Boolean(derivedMain)
        || Boolean(sourceMain && declaredMain && declaredMain !== sourceMain);
    let wantedNames = mainNameCandidates(entity);
    if (fromDerivedMain && (derivedMain || declaredMain)) {
        wantedNames = [derivedMain || declaredMain];
    } else if (fromDerivedMain && sourceMain) {
        wantedNames = wantedNames.filter((name) => name !== sourceMain);
    }
    const wanted = new Set(wantedNames);
    if (!wanted.size) return null;
    const matches = (Array.isArray(entities) ? entities : []).filter((candidate) => {
        if (!isMainEnvironmentEntity(candidate)) return false;
        return wanted.has(normName(candidate?.name)) || wanted.has(normName(candidate?.name_en));
    });
    if (!matches.length) return null;
    const episodeId = String(entity?.episode_id || '').trim();
    const scored = matches.map((candidate) => ({
        candidate,
        score: scoreEnvironmentCandidate(candidate, episodeId),
    }));
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

const BRACKET_SUBJECT_RE = /\[@([^\]]+)\]/g;

export function bracketSubjectNames(text) {
    const names = [];
    const seen = new Set();
    const re = new RegExp(BRACKET_SUBJECT_RE.source, 'g');
    let match = re.exec(String(text || ''));
    while (match) {
        const name = String(match[1] || '').trim();
        if (name && !seen.has(name)) {
            seen.add(name);
            names.push(name);
        }
        match = re.exec(String(text || ''));
    }
    return names;
}

export function filterSubjectAppearanceSection(section, names) {
    const source = String(section || '').trim();
    const wanted = new Set((names || []).map((name) => String(name || '').trim()).filter(Boolean));
    if (!source || !wanted.size) return '';
    const lines = source.split(/\r?\n/);
    const kept = lines.filter((line) => {
        const match = line.match(/\[@([^\]]+)\]/);
        return Boolean(match) && wanted.has(String(match[1] || '').trim());
    });
    if (!kept.length) return '';
    return ['【主体外形】', ...kept].join('\n').trim();
}

export function quadSharedHeader(mainPrompt) {
    const raw = String(mainPrompt || '');
    const quadAt = raw.indexOf('【四向拼图】');
    if (quadAt < 0) return '';
    const titles = listPanelTitles(raw).filter((item) => item.index >= quadAt);
    const end = titles.length ? titles[0].index : raw.length;
    return raw.slice(quadAt, end).trim();
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
    const kept = [prefix, markedSection(raw, '定位'), markedSection(raw, '主体外形'), markedSection(raw, '色彩说明'), quad]
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

const FULL_OPENING_MARKS = ['【六面一次】', '【北壁】', '【光学说明】', '【构图】'];

function looksLikeFullDesignOpening(text) {
    const body = openingBeforeQuad(text);
    return Boolean(body) && FULL_OPENING_MARKS.some((mark) => body.includes(mark));
}

function quadFailureClause(detail, label) {
    const text = String(detail || '');
    const start = text.indexOf(label);
    if (start < 0) return '';
    const body = text.slice(start + label.length);
    const end = body.search(/[。\n]/);
    return (end < 0 ? body : body.slice(0, end)).trim();
}

function pushQuadFailureName(names, name) {
    const stable = String(name || '').trim();
    if (!stable || names.includes(stable)) return;
    names.push(stable);
}

/**
 * Names a four-grid failure already spelled out.
 * names are the environments to rerun. unmatched are library rows that do not
 * exist, so another prompt call cannot write them. truncated means the sentence
 * itself said some names were omitted.
 */
const QUAD_CELL_MARKERS = ['【四向拼图】', '[0度格-左上', '[90度格-右上', '[180度格-左下', '[270度格-右下'];

export function foldEnvironmentName(value) {
    return String(value || '')
        .trim()
        .split(/[｜|]/)[0]
        .replace(/[\s_*`'\"“”‘’]+/g, '')
        .toLowerCase();
}

export function quadCellsPromptReady(prompt) {
    const text = String(prompt || '');
    return QUAD_CELL_MARKERS.every((marker) => text.includes(marker));
}

/**
 * Requested drafts whose returned prompt is not a finished four-grid.
 * One request and one ready prompt cover each other even if the model renamed it.
 */
export function quadNamesMissingFromResult(parsed, names) {
    const requested = (Array.isArray(names) ? names : [])
        .map((name) => String(name || '').trim())
        .filter(Boolean);
    const returned = Array.isArray(parsed?.environments) ? parsed.environments : [];
    const ready = returned.filter((row) => quadCellsPromptReady(row?.generation_prompt_cn));
    if (requested.length === 1 && ready.length === 1) return [];
    return requested.filter((name) => !ready.some((row) => {
        const returnedName = String(row?.name || '').trim();
        if (!returnedName) return false;
        if (returnedName === name || returnedName.toLowerCase() === name.toLowerCase()) return true;
        return foldEnvironmentName(returnedName) === foldEnvironmentName(name);
    }));
}

export function quadFailureEnvironmentNames(detail) {
    const text = String(detail || '');
    const names = [];
    const unmatched = [];
    let truncated = false;
    const takeNames = (clause, bucket) => {
        let body = String(clause || '').trim();
        if (!body) return;
        const tail = body.match(/等(\d+)条\s*$/);
        if (tail) {
            const listed = body.slice(0, tail.index).split(/[、,，]/).map((item) => item.trim()).filter(Boolean);
            if (Number(tail[1]) > listed.length) truncated = true;
            body = body.slice(0, tail.index);
        }
        body.split(/[、,，]/).map((item) => item.trim()).filter(Boolean).forEach((name) => {
            pushQuadFailureName(bucket, name);
        });
    };
    const takeMarkers = (clause) => {
        let body = String(clause || '').trim();
        if (!body) return;
        const tail = body.match(/[；;]?\s*另有(\d+)条\s*$/);
        if (tail) {
            truncated = true;
            body = body.slice(0, tail.index);
        }
        body.split(/[；;]/).forEach((part) => {
            const piece = String(part || '').trim();
            if (!piece) return;
            const splitAt = piece.search(/缺(?=【|\[)/);
            if (splitAt >= 0) pushQuadFailureName(names, piece.slice(0, splitAt));
        });
    };
    takeNames(quadFailureClause(text, '请求里的设计稿未一次写回：'), names);
    takeNames(quadFailureClause(text, '已找到但未写入：'), names);
    takeMarkers(quadFailureClause(text, '提示词缺标记：'));
    takeNames(quadFailureClause(text, '四宫格未一次写满：'), names);
    takeNames(quadFailureClause(text, '四宫格未写满：'), names);
    takeNames(quadFailureClause(text, '库中无同名环境：'), unmatched);
    return { names, unmatched, truncated };
}

export function mainEnvironmentOpeningDraft(entity) {
    const attrs = readAttrs(entity);
    const fromPrompt = openingBeforeQuad(entity?.generation_prompt_cn || entity?.prompt || '');
    const fromAttr = openingBeforeQuad(attrs.main_environment_opening || '');
    // A new environment design writes the full opening into the prompt.
    // The saved attribute is the opening frozen by the previous four-grid.
    if (looksLikeFullDesignOpening(fromPrompt)) return fromPrompt;
    return fromAttr || fromPrompt;
}

export function withMainEnvironmentOpening(entity, opening) {
    const attrs = readAttrs(entity);
    return {
        ...entity,
        description: opening,
        custom_attributes: { ...attrs, main_environment_opening: opening },
    };
}

export function mainEnvironmentDesignDescription(entity) {
    const attrs = readAttrs(entity);
    const saved = openingBeforeQuad(attrs.main_environment_opening || '');
    const description = openingBeforeQuad(entity?.description || '');
    const prompt = openingBeforeQuad(entity?.generation_prompt_cn || entity?.prompt || '');
    for (const candidate of [saved, description, prompt]) {
        if (looksLikeFullDesignOpening(candidate)) return candidate;
    }
    if (description && !String(entity?.description || '').includes('【四向拼图】')) return description;
    return saved;
}

export function assetCardIntro(entity) {
    const raw = String(entity?.generation_prompt_cn || entity?.description || '');
    if (isMainEnvironmentEntity(entity) && raw.includes('【四向拼图】')) {
        return quadImagePrompt(raw);
    }
    return stripMainEnvironmentDraftWrapper(raw);
}

export function stripOpeningWorldFromRegenPrompt(text) {
    const openingSection = /【(?:六面一次|北壁|东壁|南壁|西壁|中区|光学说明|构图|本角开篇可见面|主体材质一次)】[\s\S]*?(?=【(?:定位|主体外形|六面一次|北壁|东壁|南壁|西壁|中区|光学说明|色彩说明|构图|四向拼图|本角开篇可见面|主体材质一次)】|\[(?:0|90|180|270)度格|$)/g;
    return String(text || '')
        .replace(openingSection, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

export function buildDerivedGridRegenPrompt({ mainName, grid, cellPrompt, mainPrompt }) {
    const cell = String(cellPrompt || '').trim();
    const names = bracketSubjectNames(cell);
    const locating = markedSection(mainPrompt, '定位');
    const subjects = filterSubjectAppearanceSection(markedSection(mainPrompt, '主体外形'), names);
    const color = markedSection(mainPrompt, '色彩说明');
    const quad = [quadSharedHeader(mainPrompt), cell].filter(Boolean).join('\n\n');
    return [
        `参照这张参考图。它是主环境「${mainName}」四向拼图中的${grid}，作为该格画面参照。`,
        '按下面抽出的定位、主体外形、色彩说明和这一格修正生成一张16:9单镜头成片。',
        DERIVED_GRID_REGEN_APPEARANCE_LOCK,
        '成片去掉宫格分割线、角标、格标、度数标和拼缝，仍是这一格里的同一处空间，单张完整镜头。',
        '光学、结构和摆位以这一格画面句为准。',
        '',
        [locating, subjects, color, quad].filter(Boolean).join('\n\n'),
    ].join('\n');
}

function planOwningCell(entity, entities) {
    const angle = resolveDerivedViewAngle(entity);
    if (angle == null) return { ok: false, errorCode: 'missing_angle' };
    const mainEntity = findOwningMainEnvironment(entity, entities);
    if (!mainEntity) return { ok: false, errorCode: 'missing_main' };
    const crop = resolveGridForAngle(angle, mainEntity.generation_prompt_cn || '');
    const mainName = String(mainEntity.name || mainEntity.name_en || '').trim();
    if (!String(mainEntity.image_url || '').trim()) {
        return {
            ok: false,
            errorCode: 'missing_main_image',
            mainEntity,
            mainName,
            ...crop,
        };
    }
    return {
        ok: true,
        errorCode: '',
        mainEntity,
        mainName,
        ...crop,
    };
}

export function planDerivedGridCell(entity, entities) {
    if (!isGridCropDerivedEntity(entity)) return { ok: false, errorCode: 'not_grid_crop' };
    return planOwningCell(entity, entities);
}

export function planDerivedCellReference(entity, entities) {
    if (!usesCroppedCellReference(entity)) return { ok: false, errorCode: 'not_grid_crop' };
    return planOwningCell(entity, entities);
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
            mainPrompt,
        }),
    };
}
