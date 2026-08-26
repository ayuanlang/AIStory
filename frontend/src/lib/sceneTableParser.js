export function splitMarkdownTableRow(line) {
    let s = String(line || '').trim();
    if (!s) return [];
    if (s.startsWith('|')) s = s.slice(1);
    if (s.endsWith('|')) s = s.slice(0, -1);

    const cells = [];
    let buf = [];
    let escaped = false;
    for (const ch of s) {
        if (escaped) {
            buf.push(ch);
            escaped = false;
            continue;
        }
        if (ch === '\\') {
            escaped = true;
            continue;
        }
        if (ch === '|') {
            cells.push(buf.join('').trim());
            buf = [];
            continue;
        }
        buf.push(ch);
    }
    if (escaped) buf.push('\\');
    cells.push(buf.join('').trim());
    return cells;
}

export function cleanMarkdownTableCells(line) {
    return splitMarkdownTableRow(line).map((cell) => String(cell || '')
        .replace(/\\\|/g, '|')
        .replace(/<br\s*\/?>/gi, '\n'));
}

export function normalizeSceneTableHeaderKey(header) {
    return String(header || '').toLowerCase().replace(/[\s_\-./()]/g, '');
}

/** EP01_SC01A-style split scenes share a numeric SC index but must stay distinct in import. */
export function sceneIdHasLetterSuffix(sceneId) {
    return /^EP\d+_SC\d+[A-Za-z]+$/i.test(String(sceneId || '').trim());
}

export function deriveNumericSceneOrderFromSceneId(sceneId) {
    const sid = String(sceneId || '').trim();
    if (!sid) return null;
    const suffixMatch = sid.match(/^EP\d+_SC(\d+)[A-Za-z]+$/i);
    if (suffixMatch) {
        const order = Number(suffixMatch[1]);
        return Number.isFinite(order) && order > 0 ? order : null;
    }
    const canonicalMatch = sid.match(/^EP\d+_SC(\d+)$/i);
    if (canonicalMatch) {
        const order = Number(canonicalMatch[1]);
        return Number.isFinite(order) && order > 0 ? order : null;
    }
    const scMatch = sid.match(/(?:^|[_\-])sc(?:ene)?\s*0*([0-9]{1,4})(?:$|[_\-])/i);
    if (scMatch?.[1]) {
        const order = Number.parseInt(scMatch[1], 10);
        return Number.isFinite(order) && order > 0 ? order : null;
    }
    if (/^\d+$/.test(sid)) {
        const order = Number(sid);
        return Number.isFinite(order) && order > 0 ? order : null;
    }
    return null;
}

/** scene_no is the DB upsert key — letter-suffix scenes must use full Scene ID. */
export function resolveImportSceneNo({ sceneId, sceneNo } = {}) {
    const sceneIdVal = String(sceneId || '').trim();
    const sceneNoVal = String(sceneNo || '').trim();
    if (sceneIdHasLetterSuffix(sceneIdVal)) {
        return sceneIdVal;
    }
    const derivedOrder = deriveNumericSceneOrderFromSceneId(sceneIdVal);
    if (Number.isFinite(derivedOrder) && derivedOrder > 0) {
        return String(derivedOrder);
    }
    if (sceneNoVal) {
        return sceneNoVal;
    }
    if (sceneIdVal) {
        return sceneIdVal;
    }
    return '';
}

export function reconcileSceneTableRowCells(cells, headers) {
    const headerCount = Array.isArray(headers) ? headers.length : 0;
    if (!headerCount) return Array.isArray(cells) ? [...cells] : [];

    let row = Array.isArray(cells) ? [...cells] : [];
    while (row.length < headerCount) row.push('');
    if (row.length === headerCount) {
        return row.slice(0, headerCount);
    }

    const coreInfoIdx = headers.findIndex((header) => {
        const normalized = normalizeSceneTableHeaderKey(header);
        return normalized.includes('coresceneinfo') || normalized.includes('核心场景信息');
    });
    const mergeStartIdx = coreInfoIdx >= 0 ? coreInfoIdx : Math.min(5, headerCount - 1);
    const overflow = row.length - headerCount;
    const mergeEndIdx = mergeStartIdx + overflow + 1;
    const merged = [
        ...row.slice(0, mergeStartIdx),
        row.slice(mergeStartIdx, mergeEndIdx).join('|'),
        ...row.slice(mergeEndIdx),
    ];
    while (merged.length < headerCount) merged.push('');
    if (merged.length > headerCount) {
        const tailCount = headerCount - mergeStartIdx - 1;
        return [
            ...merged.slice(0, mergeStartIdx),
            merged.slice(mergeStartIdx, merged.length - tailCount).join('|'),
            ...merged.slice(merged.length - tailCount),
        ].slice(0, headerCount);
    }
    return merged.slice(0, headerCount);
}

export function findSceneTableColIdx(normalizedHeaders, aliases) {
    const aliasSet = new Set((aliases || []).map((alias) => normalizeSceneTableHeaderKey(alias)));
    return normalizedHeaders.findIndex((header) => {
        const normalized = normalizeSceneTableHeaderKey(header);
        return Array.from(aliasSet).some((alias) => alias && (normalized.includes(alias) || alias.includes(normalized)));
    });
}

export function buildSceneTableHeaderMap(headers) {
    const headerMap = {};
    (headers || []).forEach((header, idx) => {
        const normalized = normalizeSceneTableHeaderKey(header);
        if (!normalized) return;
        if (normalized.includes('episodeid') || normalized.includes('集id')) headerMap.episode_id = idx;
        else if ((normalized.includes('sceneid') && !normalized.includes('sceneno')) || normalized.includes('场景id')) headerMap.scene_id = idx;
        if (normalized.includes('sceneno') || normalized.includes('场次')) headerMap.scene_no = idx;
        else if (normalized.includes('scenename') || normalized === 'title') headerMap.scene_name = idx;
        else if (normalized.includes('equivalentduration')) headerMap.equivalent_duration = idx;
        else if (normalized.includes('coresceneinfo') || normalized.includes('coregoal')) headerMap.core_scene_info = idx;
        else if (
            normalized.includes('originalscripttext')
            || normalized.includes('adaptedscripttext')
            || normalized.includes('改编剧本')
            || normalized.includes('description')
        ) headerMap.original_script_text = idx;
        else if (normalized.includes('environmentname')) headerMap.environment_name = idx;
        else if (normalized.includes('environmentrelation')) headerMap.environment_relation = idx;
        else if (normalized.includes('baseenvironmentreference')) headerMap.base_environment_reference = idx;
        else if (normalized.includes('environmentdelta')) headerMap.environment_delta = idx;
        else if (normalized.includes('entrystate')) headerMap.entry_state = idx;
        else if (normalized.includes('exitstate')) headerMap.exit_state = idx;
        else if (normalized.includes('linkedcharacters')) headerMap.linked_characters = idx;
        else if (normalized.includes('keyprops')) headerMap.key_props = idx;
    });
    return headerMap;
}

function cleanSceneCell(value) {
    return value ? String(value).replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
}

export function getSceneTableFallbackIndices(colsLength, headerMap) {
    const hasExtendedEnvCols = headerMap.base_environment_reference !== undefined
        || colsLength >= 15;
    const isNewFormat = colsLength >= 13
        || headerMap.episode_id !== undefined
        || headerMap.scene_id !== undefined
        || headerMap.environment_relation !== undefined;

    if (hasExtendedEnvCols) {
        return {
            scene_no: 2,
            scene_name: 3,
            equivalent_duration: 4,
            core_scene_info: 5,
            original_script_text: 6,
            environment_name: 7,
            environment_relation: 8,
            base_environment_reference: 9,
            environment_delta: 10,
            entry_state: 11,
            exit_state: 12,
            linked_characters: 13,
            key_props: 14,
        };
    }

    if (isNewFormat) {
        return {
            scene_no: 2,
            scene_name: 3,
            equivalent_duration: 4,
            core_scene_info: 5,
            original_script_text: 6,
            environment_name: 7,
            environment_relation: 8,
            entry_state: 9,
            exit_state: 10,
            linked_characters: 11,
            key_props: 12,
        };
    }

    return {
        scene_no: 0,
        scene_name: 1,
        equivalent_duration: 2,
        core_scene_info: 3,
        original_script_text: 4,
        environment_name: 5,
        linked_characters: 6,
        key_props: 7,
    };
}

export function parseScenesFromMarkdownTable(text, options = {}) {
    const normalizeOriginalScriptText = typeof options.normalizeOriginalScriptText === 'function'
        ? options.normalizeOriginalScriptText
        : (value) => String(value || '').trim();

    if (!text) return [];

    const lines = String(text).split('\n').filter((line) => String(line || '').trim().includes('|'));
    const headerIdx = lines.findIndex((line) => {
        const normalized = normalizeSceneTableHeaderKey(line);
        return normalized.includes('sceneno')
            || normalized.includes('sceneid')
            || normalized.includes('场次')
            || normalized.includes('title');
    });
    if (headerIdx < 0) return [];

    const headers = cleanMarkdownTableCells(lines[headerIdx]);
    if (headers.length < 4) return [];

    const normalizedHeaders = headers.map((header) => normalizeSceneTableHeaderKey(header));
    const headerMap = buildSceneTableHeaderMap(headers);
    const isSeparatorLine = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);

    const rows = [];
    let inShotTable = false;

    for (let i = headerIdx + 1; i < lines.length; i += 1) {
        const line = lines[i];
        if (line.includes('Shot ID') || line.includes('镜头ID')) {
            inShotTable = true;
            continue;
        }
        if (line.includes('Scene No') || line.includes('场次序号')) {
            inShotTable = false;
            continue;
        }
        if (inShotTable || isSeparatorLine(line)) continue;

        const cols = reconcileSceneTableRowCells(cleanMarkdownTableCells(line), headers);
        if (cols.length < 2) continue;

        const fallback = getSceneTableFallbackIndices(cols.length, headerMap);
        const getVal = (key) => {
            const idx = headerMap[key] !== undefined ? headerMap[key] : fallback[key];
            return idx !== undefined && idx < cols.length ? cleanSceneCell(cols[idx]) : '';
        };

        rows.push({
            scene_no: getVal('scene_no'),
            scene_name: getVal('scene_name'),
            equivalent_duration: getVal('equivalent_duration'),
            core_scene_info: getVal('core_scene_info'),
            original_script_text: normalizeOriginalScriptText(getVal('original_script_text')),
            environment_name: getVal('environment_name'),
            environment_relation: getVal('environment_relation'),
            entry_state: getVal('entry_state'),
            exit_state: getVal('exit_state'),
            linked_characters: getVal('linked_characters'),
            key_props: getVal('key_props'),
        });
    }

    return rows;
}

const SHOT_PIPE_MERGE_HEADER_ALIASES = [
    ['shot logic (cn)', 'shot_logic_cn', '镜头逻辑', '镜头逻辑（中文）'],
    ['video content (cn)', 'video_prompt_cn', '视频内容（中文）'],
    ['start frame (cn)', 'start_frame_cn', '起始帧（中文）'],
    ['keyframes (cn)', 'keyframes_cn', '关键帧（中文）'],
    ['end frame (cn)', 'end_frame_cn', '结束帧（中文）'],
];

export function normalizeShotTableHeaderKey(header) {
    return String(header || '').toLowerCase().replace(/[\s_\-./()（）:：]/g, '');
}

const SHOT_VIDEO_ANCHOR_RE = /全局动态风格|运镜与动作流|动态连续光影|光线连动弧光|人物面部稳定不变形/;
const SHOT_LOGIC_ANCHOR_RE = /Beat-Shot映射|节奏需求|镜头逻辑总规划|场结果|光影锚定|摄影综合表达|P段时序链|^节奏:|^光影:|^运镜:|^取景:|^衔接:|^实体:|^P链:/;

export function stripShotLogicPrefixFromVideoPrompt(text) {
    const value = String(text || '').trim();
    if (!value) return '';
    if (SHOT_VIDEO_ANCHOR_RE.test(value.slice(0, 40))) return value;
    const head = value.slice(0, 200);
    const isLogicHead = SHOT_LOGIC_ANCHOR_RE.test(head)
        || ((head.match(/｜/g) || []).length >= 3 && head.includes(':'));
    if (!isLogicHead) return value;
    const match = value.match(SHOT_VIDEO_ANCHOR_RE);
    if (!match || match.index == null || match.index <= 0) return '';
    return value.slice(match.index).trim();
}

export function findShotTableColIdx(headers, aliases) {
    const normalizedHeaders = (headers || []).map((header) => normalizeShotTableHeaderKey(header));
    const aliasList = (aliases || []).map((alias) => normalizeShotTableHeaderKey(alias)).filter(Boolean);
    for (let idx = 0; idx < normalizedHeaders.length; idx += 1) {
        const normalized = normalizedHeaders[idx];
        if (aliasList.includes(normalized)) return idx;
    }
    for (let idx = 0; idx < normalizedHeaders.length; idx += 1) {
        const normalized = normalizedHeaders[idx];
        for (const alias of aliasList) {
            if (normalized.includes(alias) || alias.includes(normalized)) {
                return idx;
            }
        }
    }
    return -1;
}

export function findShotPipeMergeColumnIndices(headers) {
    const indices = [];
    for (const aliases of SHOT_PIPE_MERGE_HEADER_ALIASES) {
        const idx = findShotTableColIdx(headers, aliases);
        if (idx >= 0 && !indices.includes(idx)) indices.push(idx);
    }
    return indices.length > 0 ? indices : [3];
}

export function reconcileShotTableRowCells(cells, headers) {
    const headerCount = Array.isArray(headers) ? headers.length : 0;
    if (!headerCount) return Array.isArray(cells) ? [...cells] : [];

    let row = Array.isArray(cells) ? cells.map((cell) => String(cell || '').trim()) : [];
    const mergeIndices = findShotPipeMergeColumnIndices(headers);

    while (row.length > headerCount) {
        const overflow = row.length - headerCount;
        const mergeIdx = Math.max(0, Math.min(mergeIndices[0] ?? headerCount - 1, headerCount - 1));
        const mergeEnd = Math.min(row.length, mergeIdx + overflow + 1);
        const merged = row.slice(mergeIdx, mergeEnd).join('|');
        row = [...row.slice(0, mergeIdx), merged, ...row.slice(mergeEnd)];
        if (row.length > headerCount) {
            if (mergeIndices.length > 1) {
                mergeIndices.shift();
                continue;
            }
            const tail = row.slice(headerCount - 1).join(' | ');
            row = [...row.slice(0, headerCount - 1), tail];
        }
    }

    while (row.length < headerCount) row.push('');
    row = row.slice(0, headerCount);

    const logicIdx = findShotTableColIdx(headers, ['shot logic (cn)', 'shot_logic_cn', '镜头逻辑']);
    const videoIdx = findShotTableColIdx(headers, ['video content (cn)', 'video_prompt_cn', '视频内容（中文）']);
    if (logicIdx >= 0 && videoIdx >= 0 && logicIdx < row.length && videoIdx < row.length) {
        const rawVideo = String(row[videoIdx] || '').trim();
        const extractedVideo = stripShotLogicPrefixFromVideoPrompt(rawVideo);
        if (extractedVideo && extractedVideo !== rawVideo) {
            const prefix = rawVideo.slice(0, rawVideo.indexOf(extractedVideo)).trim();
            row[videoIdx] = extractedVideo;
            if (prefix) {
                const existingLogic = String(row[logicIdx] || '').trim();
                row[logicIdx] = existingLogic && !prefix.includes(existingLogic)
                    ? `${existingLogic}\n${prefix}`
                    : (prefix || existingLogic);
            }
        } else if (!extractedVideo && rawVideo && SHOT_LOGIC_ANCHOR_RE.test(rawVideo.slice(0, 200))) {
            const fromLogic = stripShotLogicPrefixFromVideoPrompt(String(row[logicIdx] || ''));
            if (!String(row[logicIdx] || '').trim()) row[logicIdx] = rawVideo;
            row[videoIdx] = fromLogic;
        } else if (!rawVideo) {
            const logicText = String(row[logicIdx] || '');
            const fromLogic = stripShotLogicPrefixFromVideoPrompt(logicText);
            if (fromLogic) {
                row[videoIdx] = fromLogic;
                const cut = logicText.indexOf(fromLogic);
                if (cut > 0) row[logicIdx] = logicText.slice(0, cut).trim();
            }
        }
    }

    return row;
}

export function buildShotTableHeaderMap(headers) {
    const map = {};
    (headers || []).forEach((header, idx) => {
        const key = normalizeShotTableHeaderKey(header);
        if (key) map[key] = idx;
    });
    return map;
}

function isMarkdownTableSeparatorLine(line) {
    const cols = splitMarkdownTableRow(line);
    if (!cols.length) return false;
    return cols.every((col) => {
        const token = String(col || '').replace(/\s/g, '').replace(/^:+|:+$/g, '');
        return token.length >= 3 && /^-+$/.test(token);
    });
}

function looksLikeShotMarkdownTableRow(line) {
    const text = String(line || '').trim();
    if (!text) return false;
    if (text.startsWith('|')) return true;
    return (text.match(/\|/g) || []).length >= 2;
}

export function parseShotsFromMarkdownTable(text) {
    const lines = String(text || '').split(/\r?\n/);
    let headerIdx = -1;
    let separatorIdx = -1;

    for (let i = 0; i < lines.length - 1; i += 1) {
        const headerLine = String(lines[i] || '').trim();
        const sepLine = String(lines[i + 1] || '').trim();
        if (!looksLikeShotMarkdownTableRow(headerLine)) continue;
        if (splitMarkdownTableRow(headerLine).length < 2) continue;
        if (isMarkdownTableSeparatorLine(sepLine)) {
            headerIdx = i;
            separatorIdx = i + 1;
            break;
        }
    }

    if (headerIdx < 0 || separatorIdx < 0) {
        return { headers: [], rows: [], tableLineCount: 0 };
    }

    const headers = splitMarkdownTableRow(lines[headerIdx].trim()).map(
        (header) => String(header || '').replace(/[*_]/g, '').trim()
    );
    const headerCount = headers.length;
    if (!headerCount) {
        return { headers: [], rows: [], tableLineCount: 0 };
    }

    const rows = [];
    let tableLineCount = 0;
    let rowCells = [];

    const flushRow = () => {
        if (!rowCells.length || rowCells.every((cell) => !String(cell || '').trim())) {
            rowCells = [];
            return;
        }
        const normalized = reconcileShotTableRowCells(rowCells, headers);
        const row = {};
        headers.forEach((header, idx) => {
            row[header] = String(normalized[idx] || '')
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/\\n/g, '\n')
                .trim();
        });
        rows.push(row);
        rowCells = [];
    };

    for (let i = separatorIdx + 1; i < lines.length; i += 1) {
        const stripped = String(lines[i] || '').trim();
        if (!stripped) continue;
        if (stripped.startsWith('#')) break;

        if (looksLikeShotMarkdownTableRow(stripped)) {
            if (isMarkdownTableSeparatorLine(stripped)) continue;
            tableLineCount += 1;
            const cells = splitMarkdownTableRow(stripped);
            if (!cells.length) continue;

            if (!rowCells.length) {
                rowCells = [...cells];
            } else if (rowCells.length >= headerCount) {
                flushRow();
                rowCells = [...cells];
            } else {
                rowCells.push(...cells);
            }

            if (rowCells.length >= headerCount) flushRow();
            continue;
        }

        if (rowCells.length > 0) {
            const lastIdx = rowCells.length - 1;
            rowCells[lastIdx] = `${rowCells[lastIdx]}\n${stripped}`.trim();
        }
    }

    flushRow();
    return { headers, rows, tableLineCount };
}

export function normalizeShotBusinessId(value) {
    return String(value || '')
        .replace(/\*\*/g, '')
        .replace(/^shot\s*/i, '')
        .trim()
        .toUpperCase();
}

export function dedupeShotRowsForImport(rows, { sceneId = null } = {}) {
    if (!Array.isArray(rows) || rows.length === 0) return { rows: [], warnings: [] };

    const deduped = [];
    const indexByKey = new Map();
    const warnings = [];
    const stableSceneId = sceneId != null ? String(sceneId) : '';

    rows.forEach((row, zeroIdx) => {
        if (!row || typeof row !== 'object') return;
        const idx = zeroIdx + 1;
        const rawShotId = row['Shot ID'] ?? row.shot_id ?? row['镜头ID'] ?? '';
        const businessId = normalizeShotBusinessId(rawShotId) || `__row_${idx}`;
        const dedupKey = `${stableSceneId}::${businessId}`;
        if (indexByKey.has(dedupKey)) {
            const prevIdx = indexByKey.get(dedupKey);
            warnings.push(`duplicate Shot ID '${businessId}' at rows ${prevIdx} and ${idx}; kept row ${idx}`);
            deduped[prevIdx - 1] = row;
            return;
        }
        indexByKey.set(dedupKey, idx);
        deduped.push(row);
    });

    return { rows: deduped, warnings };
}

export function dedupeShotsForDisplay(shots, { sceneId = null } = {}) {
    if (!Array.isArray(shots) || shots.length === 0) return [];

    const orderedKeys = [];
    const bestByKey = new Map();

    for (const shot of shots) {
        if (!shot) continue;
        const sid = sceneId != null ? String(sceneId) : String(shot.scene_id || '');
        const businessId = normalizeShotBusinessId(shot.shot_id);
        const key = businessId ? `${sid}::${businessId}` : `${sid}::__db_${shot.id}`;
        if (!bestByKey.has(key)) orderedKeys.push(key);
        const prev = bestByKey.get(key);
        const curId = Number(shot.id || 0);
        const prevId = Number(prev?.id || 0);
        if (!prev || curId >= prevId) bestByKey.set(key, shot);
    }

    return orderedKeys.map((key) => bestByKey.get(key)).filter(Boolean);
}
