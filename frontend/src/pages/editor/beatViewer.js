const NODE_KEYS = ['drama', 'combat', 'framing', 'staging'];

const STEP_FROM_PIPELINE = {
    drama: 'drama',
    combat: 'combat',
    vfx: 'combat',
    xian: 'combat',
    derived_framing: 'framing',
    framing: 'framing',
    staging: 'staging',
};

const BEAT_START_RE = /`?\[BEAT_START(?::([^\s\]]+))?\]`?/gi;
const BEAT_END_RE = /`?\[BEAT_END(?::([^\s\]]+))?\]`?/gi;
const LEGACY_BEAT_RE = /^\s*[-~]\s*Beat\s+(\d+)\b/gm;

export const BEAT_VIEWER_NODES = [
    { key: 'drama', zh: '文戏增强', en: 'Drama enhancement' },
    { key: 'combat', zh: '武戏增强', en: 'Action enhancement' },
    { key: 'framing', zh: '现场编排', en: 'Floor staging' },
    { key: 'staging', zh: '建置与入戏', en: 'Blocking' },
];

export const WHOLE_NODE_BEAT_ID = '__all__';

export const normalizeBeatId = (raw, fallback = '') => {
    const text = String(raw || '').trim();
    if (!text) return String(fallback || '');
    if (/^\d+$/.test(text)) {
        const asInt = Number.parseInt(text, 10);
        return Number.isFinite(asInt) ? String(asInt) : text;
    }
    return text;
};

const sceneOrderFromId = (sceneId) => {
    const sid = String(sceneId || '').trim();
    const match = sid.match(/SC(\d+)/i) || sid.match(/(\d+)\s*$/);
    if (!match) return null;
    const order = Number(match[1]);
    return Number.isFinite(order) && order > 0 ? order : null;
};

const firstContentLine = (text) => {
    const line = String(text || '')
        .split('\n')
        .map((item) => item.trim())
        .find((item) => item && !/^\[(?:BEAT_|SCENE_|STAGING_)/i.test(item));
    return String(line || '').replace(/\s+/g, ' ').trim();
};

export const beatPreview = (body, beatId) => {
    const line = firstContentLine(body);
    if (!line) return `Beat ${beatId || ''}`.trim();
    return line.length > 72 ? `${line.slice(0, 72)}…` : line;
};

const parseLegacyBeats = (source) => {
    const matches = [];
    const re = new RegExp(LEGACY_BEAT_RE.source, 'gm');
    let match;
    while ((match = re.exec(source)) !== null) {
        matches.push({ index: match.index, id: match[1] });
    }
    if (!matches.length) return [];
    return matches.map((item, idx) => {
        const end = idx + 1 < matches.length ? matches[idx + 1].index : source.length;
        const body = source.slice(item.index, end).trim();
        const id = normalizeBeatId(item.id, String(idx + 1));
        return { id, title: beatPreview(body, id), body };
    }).filter((beat) => beat.body);
};

export const parseNodeBeats = (text) => {
    const source = String(text || '').replace(/\r\n/g, '\n');
    if (!source.trim()) return [];
    const starts = [];
    const startRe = new RegExp(BEAT_START_RE.source, 'gi');
    let match;
    while ((match = startRe.exec(source)) !== null) {
        starts.push({
            index: match.index,
            endPos: match.index + match[0].length,
            id: String(match[1] || '').trim(),
        });
    }
    if (!starts.length) return parseLegacyBeats(source);
    const endRe = new RegExp(BEAT_END_RE.source, 'gi');
    return starts.map((start, idx) => {
        const nextStart = idx + 1 < starts.length ? starts[idx + 1].index : source.length;
        endRe.lastIndex = start.endPos;
        const endMatch = endRe.exec(source);
        const bodyEnd = (endMatch && endMatch.index <= nextStart) ? endMatch.index : nextStart;
        const body = source.slice(start.endPos, bodyEnd).trim();
        const id = normalizeBeatId(start.id, String(idx + 1));
        return { id, title: beatPreview(body, id), body };
    }).filter((beat) => beat.id);
};

const sectionIndex = (text, name) => {
    const re = new RegExp(
        `(?:^|\\n)[ \\t]*(?:─{2,}|-{2,})?[ \\t]*【[ \\t]*${name}[ \\t]*】[ \\t]*(?:─{2,}|-{2,})?`,
        'i',
    );
    const match = re.exec(String(text || ''));
    if (!match) return -1;
    return match.index + (match[0].startsWith('\n') ? 1 : 0);
};

const sliceFrom = (text, start, end) => {
    if (start < 0) return '';
    const stop = end > start ? end : text.length;
    return String(text.slice(start, stop) || '').trim();
};

export const splitStagingBeat = (body) => {
    const text = String(body || '').replace(/\r\n/g, '\n');
    const setupAt = sectionIndex(text, '建置');
    const playAt = sectionIndex(text, '入戏');
    const notesAt = sectionIndex(text, '场记分析');
    const notesEndAt = sectionIndex(text, '场记分析结束');
    const setupEnd = [playAt, notesAt].filter((index) => index > setupAt).sort((a, b) => a - b)[0];
    const playEnd = [notesAt, notesEndAt].filter((index) => index > playAt).sort((a, b) => a - b)[0];
    const notesEnd = notesEndAt > notesAt ? notesEndAt : text.length;
    return {
        setup: sliceFrom(text, setupAt, setupEnd),
        play: sliceFrom(text, playAt, playEnd),
        notes: sliceFrom(text, notesAt, notesEnd),
    };
};

const extractSceneName = (nodes) => {
    for (const key of NODE_KEYS) {
        const match = /【场景名称】\s*([^\r\n]+)/.exec(String(nodes?.[key]?.text || ''));
        if (!match) continue;
        const name = String(match[1] || '')
            .replace(/[|｜]/g, '·')
            .replace(/\s+/g, ' ')
            .trim();
        if (name) return name;
    }
    return '';
};

const unionBeatIds = (nodes) => {
    const ids = [];
    const seen = new Set();
    NODE_KEYS.forEach((key) => {
        (nodes?.[key]?.beats || []).forEach((beat) => {
            const id = normalizeBeatId(beat?.id);
            if (!id || seen.has(id)) return;
            seen.add(id);
            ids.push(id);
        });
    });
    ids.sort((left, right) => {
        const leftNum = /^\d+$/.test(left) ? Number(left) : NaN;
        const rightNum = /^\d+$/.test(right) ? Number(right) : NaN;
        if (Number.isFinite(leftNum) && Number.isFinite(rightNum)) return leftNum - rightNum;
        if (Number.isFinite(leftNum)) return -1;
        if (Number.isFinite(rightNum)) return 1;
        return left.localeCompare(right);
    });
    return ids;
};

const emptyNodes = () => ({
    drama: { text: '', beats: [] },
    combat: { text: '', beats: [] },
    framing: { text: '', beats: [] },
    staging: { text: '', beats: [] },
});

export const parseSceneSubskillResultsObject = (raw) => {
    const text = String(raw || '').trim();
    if (!text) return {};
    try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
    } catch (_) {}
    return {};
};

const sceneKeysMatch = (left, right) => {
    const leftToken = compactSceneToken(left);
    const rightToken = compactSceneToken(right);
    if (!leftToken || !rightToken) return false;
    if (leftToken === rightToken) return true;
    if (/sc\d+[a-z]/i.test(String(left || '')) || /sc\d+[a-z]/i.test(String(right || ''))) return false;
    const leftOrder = sceneOrderToken(left);
    const rightOrder = sceneOrderToken(right);
    return leftOrder != null && leftOrder === rightOrder;
};

const preferSceneId = (left, right) => {
    const score = (sceneId) => (/_SC\d/i.test(sceneId) ? 2 : 0) + (/^EP/i.test(sceneId) ? 1 : 0);
    return score(String(right || '')) > score(String(left || '')) ? right : left;
};

export const coalesceSceneStepMaps = (resultsMap) => {
    const groups = [];
    Object.entries(resultsMap && typeof resultsMap === 'object' ? resultsMap : {}).forEach(([sceneId, steps]) => {
        const id = String(sceneId || '').trim();
        if (!id || !steps || typeof steps !== 'object' || Array.isArray(steps)) return;
        const hit = groups.find((group) => sceneKeysMatch(group.sceneId, id));
        if (!hit) {
            groups.push({ sceneId: id, steps: { ...steps } });
            return;
        }
        hit.sceneId = preferSceneId(hit.sceneId, id);
        Object.entries(steps).forEach(([key, value]) => {
            if (!String(value || '').trim()) return;
            if (!String(hit.steps[key] || '').trim()) hit.steps[key] = value;
        });
    });
    return Object.fromEntries(groups.map((group) => [group.sceneId, group.steps]));
};

export const readSubskillResultsContent = (raw) => {
    const text = String(raw || '').trim();
    if (!text) return '';
    try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            const nested = parsed?.stages?.stage1?.outputs?.scene_subskill_results?.content;
            if (typeof nested === 'string') return nested;
            if (nested && typeof nested === 'object') return JSON.stringify(nested);
        }
    } catch (_) {}
    return text;
};

const resultsMapText = (raw) => {
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        try {
            return readSubskillResultsContent(JSON.stringify(raw));
        } catch (_) {
            return '';
        }
    }
    return readSubskillResultsContent(raw);
};

export const mergeSubskillResultMaps = (baseRaw, overlayRaw) => {
    const base = parseSceneSubskillResultsObject(resultsMapText(baseRaw));
    const overlay = parseSceneSubskillResultsObject(resultsMapText(overlayRaw));
    const next = { ...base };
    Object.entries(overlay).forEach(([sceneId, steps]) => {
        if (!steps || typeof steps !== 'object' || Array.isArray(steps)) return;
        const scene = {
            ...(next[sceneId] && typeof next[sceneId] === 'object' && !Array.isArray(next[sceneId]) ? next[sceneId] : {}),
        };
        Object.entries(steps).forEach(([key, value]) => {
            if (String(value || '').trim()) scene[key] = value;
        });
        next[sceneId] = scene;
    });
    return next;
};

export const mergePipelineSceneBlocks = (resultsMap, pipelineNodes) => {
    const next = {};
    Object.entries(resultsMap && typeof resultsMap === 'object' ? resultsMap : {}).forEach(([sceneId, steps]) => {
        if (!steps || typeof steps !== 'object' || Array.isArray(steps)) return;
        next[String(sceneId || '').trim()] = { ...steps };
    });
    (Array.isArray(pipelineNodes) ? pipelineNodes : []).forEach((node) => {
        if (String(node?.node_name || '').trim() !== 'scene_subskill_scene') return;
        const sceneId = String(node?.scene_id || '').trim();
        const block = String(node?.runtime_meta?.scene_block || '').trim();
        if (!sceneId || !block) return;
        const called = Array.isArray(node?.runtime_meta?.called_subskills)
            ? node.runtime_meta.called_subskills
            : [];
        const stepName = String(node?.runtime_meta?.current_step || called[called.length - 1] || '').trim();
        const key = STEP_FROM_PIPELINE[stepName];
        if (!key) return;
        const scene = (next[sceneId] && typeof next[sceneId] === 'object' && !Array.isArray(next[sceneId]))
            ? { ...next[sceneId] }
            : {};
        if (String(scene[key] || '').trim()) return;
        scene[key] = block;
        next[sceneId] = scene;
    });
    return next;
};

export const buildBeatViewerScenes = (resultsMap) => {
    const map = coalesceSceneStepMaps(resultsMap);
    const scenes = Object.entries(map).map(([sceneId, steps]) => {
        const id = String(sceneId || '').trim();
        const record = steps && typeof steps === 'object' && !Array.isArray(steps) ? steps : {};
        const nodes = emptyNodes();
        NODE_KEYS.forEach((key) => {
            const text = String(record[key] || '').trim();
            nodes[key] = { text, beats: parseNodeBeats(text) };
        });
        let beatIds = unionBeatIds(nodes);
        const hasText = NODE_KEYS.some((key) => nodes[key].text);
        if (!beatIds.length && hasText) beatIds = [WHOLE_NODE_BEAT_ID];
        return {
            sceneId: id,
            name: extractSceneName(nodes),
            order: sceneOrderFromId(id),
            nodes,
            beatIds,
        };
    }).filter((scene) => scene.sceneId && (scene.beatIds.length > 0));
    scenes.sort((left, right) => (
        (left.order ?? 9999) - (right.order ?? 9999)
        || left.sceneId.localeCompare(right.sceneId)
    ));
    return scenes;
};

export const findNodeBeat = (node, beatId) => {
    const id = String(beatId || '').trim();
    if (!id) return null;
    const text = String(node?.text || '').trim();
    const beats = Array.isArray(node?.beats) ? node.beats : [];
    if (id === WHOLE_NODE_BEAT_ID || (text && beats.length === 0)) {
        if (!text) return null;
        return { id, title: '整段', body: text };
    }
    const target = normalizeBeatId(id);
    return beats.find((beat) => normalizeBeatId(beat?.id) === target) || null;
};

export const beatOptionLabel = (scene, beatId) => {
    if (beatId === WHOLE_NODE_BEAT_ID) return '整段（未切拍）';
    for (const key of NODE_KEYS) {
        const hit = findNodeBeat(scene?.nodes?.[key], beatId);
        if (hit?.title) return `B${beatId} · ${hit.title}`;
    }
    return `B${beatId}`;
};

const compactSceneToken = (value) => String(value || '').trim().toLowerCase().replace(/[\s_\-./]+/g, '');

const sceneOrderToken = (value) => {
    const text = String(value || '').trim();
    if (!text || /sc\d+[a-z]/i.test(text)) return null;
    const sc = text.match(/sc(\d+)/i);
    if (sc) return Number(sc[1]);
    if (/^\d+$/.test(text)) return Number(text);
    return null;
};

export const matchWorkspaceScene = (scenes, sceneId) => {
    const rows = Array.isArray(scenes) ? scenes : [];
    const token = compactSceneToken(sceneId);
    if (!token) return null;
    const exact = rows.find((row) => (
        [row?.scene_no, row?.scene_id, row?.scene_code]
            .some((raw) => compactSceneToken(raw) === token)
    ));
    if (exact) return exact;
    if (/sc\d+[a-z]/i.test(String(sceneId || ''))) return null;
    const order = sceneOrderToken(sceneId);
    if (!order) return null;
    return rows.find((row) => (
        [row?.scene_no, row?.scene_id, row?.scene_code].some((raw) => {
            if (/sc\d+[a-z]/i.test(String(raw || ''))) return false;
            return sceneOrderToken(raw) === order;
        })
    )) || null;
};

export const parseMergedBeatIds = (logicText) => {
    const source = String(logicText || '').replace(/<br\s*\/?>/gi, '\n');
    const match = /合镜\s*Beat\s*=\s*([^\n｜|]+)/i.exec(source)
        || /合镜\s*=\s*([^\n｜|]+)/i.exec(source)
        || /单\s*Beat\s*=\s*([^\n｜|]+)/i.exec(source);
    if (!match) return [];
    const ids = [];
    const re = /Beat\s*(\d+)|\bB(\d+)\b/gi;
    let hit;
    while ((hit = re.exec(match[1])) !== null) {
        const id = normalizeBeatId(hit[1] || hit[2]);
        if (id && !ids.includes(id)) ids.push(id);
    }
    return ids;
};

const shotSortKey = (shotId, index) => {
    const match = String(shotId || '').match(/(\d+)\s*$/);
    return match ? Number(match[1]) : index + 10000;
};

export const normalizeStoryboardShots = (rawShots) => {
    const list = (Array.isArray(rawShots) ? rawShots : []).map((shot, index) => {
        const logic = String(shot?.shot_logic_cn || shot?.logic || '').trim();
        const video = String(shot?.video_content || shot?.prompt || '').trim();
        const shotId = String(shot?.shot_id || '').trim() || `SH${index + 1}`;
        return {
            key: `${shot?.id || index}:${shotId}`,
            shotId,
            name: String(shot?.shot_name || '').trim(),
            duration: String(shot?.duration || '').trim(),
            logic,
            video,
            beatIds: parseMergedBeatIds(logic),
            order: shotSortKey(shotId, index),
        };
    }).filter((shot) => shot.shotId || shot.logic || shot.video);
    list.sort((left, right) => left.order - right.order || left.shotId.localeCompare(right.shotId));
    return list;
};

export const shotsCoveringBeat = (shots, beatId) => {
    const id = normalizeBeatId(beatId);
    if (!id || id === WHOLE_NODE_BEAT_ID) return [];
    return (Array.isArray(shots) ? shots : []).filter((shot) => (shot?.beatIds || []).includes(id));
};

export const shotOptionLabel = (shot) => {
    const name = shot?.name ? ` · ${shot.name}` : '';
    const beats = shot?.beatIds?.length ? ` · Beat ${shot.beatIds.join('+')}` : '';
    return `${shot?.shotId || 'SH'}${name}${beats}`;
};
