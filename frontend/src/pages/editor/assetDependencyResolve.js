import { normalizeEntityToken } from '../../lib/entityToken.js';

// Name and episode-title parsing matches editorHelpers. Kept here so this module
// does not import the JSX helper file.

const normalizeAsciiSubjectSeparatorsForDeps = (value) => {
    return String(value || '').replace(/[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+/g, (matched) => {
        return matched.replace(/[_-]+/g, ' ');
    });
};

const normalizeSubjectNameForDeps = (value) => {
    let text = String(value || '').trim();
    if (!text) return '';
    text = text
        .replace(/[（【〔［]/g, '(')
        .replace(/[）】〕］]/g, ')')
        .replace(/[“”'"‘’`]/g, '')
        .replace(/[\u2010-\u2015]/g, '-');
    text = text.replace(/^CHAR:\s*/i, '');
    text = text.replace(/^PROP:\s*/i, '');
    text = text.replace(/^ENV:\s*/i, '');
    text = text.replace(/^\[/, '').replace(/\]$/, '');
    text = text.replace(/^@/, '').trim();
    text = normalizeAsciiSubjectSeparatorsForDeps(text)
        .replace(/\s+/g, ' ')
        .trim();
    return text;
};

const normalizeSubjectKeyForDeps = (value) => {
    const stable = normalizeSubjectNameForDeps(value);
    if (!stable) return '';
    return normalizeEntityToken(stable)
        .replace(/[^\p{L}\p{N}\u4e00-\u9fff]/gu, '');
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

const parseVisualDependencies = (value) => {
    let candidates = [];
    if (Array.isArray(value)) {
        candidates = value;
    } else if (typeof value === 'string') {
        const raw = String(value || '').trim();
        if (!raw) return [];
        if ((raw.startsWith('[') && raw.endsWith(']')) || (raw.startsWith('{') && raw.endsWith('}'))) {
            try {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) candidates = parsed;
                else if (typeof parsed === 'string') candidates = [parsed];
            } catch {
                candidates = [];
            }
        }
        if (candidates.length === 0) candidates = raw.split(/[\n,，;；|]/);
    } else if (value != null) {
        candidates = [value];
    }
    const out = [];
    const seen = new Set();
    for (const item of candidates) {
        const normalized = normalizeSubjectNameForDeps(item);
        const key = normalizeSubjectKeyForDeps(normalized);
        if (!normalized || !key || seen.has(key)) continue;
        seen.add(key);
        out.push(normalized);
    }
    return out;
};

const isDirectImageRefToken = (value) => /^(https?:\/\/|\/uploads\/|\/static\/|data:image\/)/i.test(String(value || '').trim());

const parseDependencyEntityId = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (/^\d+$/.test(raw)) return raw;
    const prefixedIdMatch = raw.match(/^(?:existing[_ \s]*id|entity[_ \s]*id|id)\s*[:#=]\s*(\d+)$/i);
    if (prefixedIdMatch) return String(prefixedIdMatch[1] || '').trim();
    return '';
};

const entityNameKeySet = (entity) => {
    const keys = new Set();
    [entity?.name, entity?.name_en].forEach((value) => {
        const key = normalizeSubjectKeyForDeps(value);
        if (key) keys.add(key);
    });
    return keys;
};

const nameKeysHit = (left, right) => {
    for (const key of left) {
        if (right.has(key)) return true;
    }
    return false;
};

const preferImagedRow = (next, prev) => {
    const nextImage = String(next?.image_url || '').trim() ? 1 : 0;
    const prevImage = String(prev?.image_url || '').trim() ? 1 : 0;
    if (nextImage !== prevImage) return nextImage > prevImage ? next : prev;
    return (Number(next?.id) || 0) >= (Number(prev?.id) || 0) ? next : prev;
};

/**
 * Episode display number.
 * The first four keys follow the backend episode sort, so the previous-episode
 * pick is the same row the asset registration uses.
 * Returns null when the row has no number and no list index was given.
 */
export function episodeSortNumber(episode, epIndex = -1) {
    if (!episode) return null;
    const info = episode?.episode_info && typeof episode.episode_info === 'object'
        ? episode.episode_info
        : {};
    const nestedGlobal = info?.e_global_info && typeof info.e_global_info === 'object'
        ? info.e_global_info
        : {};
    const candidates = [
        info?.episode_script_episode_number,
        info?.story_dna_episode_number,
        info?.episode_number,
        episode?.episode_number,
        info?.index,
        nestedGlobal?.episode_script_episode_number,
        nestedGlobal?.story_dna_episode_number,
        nestedGlobal?.episode_number,
        parseEpisodeNumberFromText(episode?.title),
        parseEpisodeNumberFromText(info?.script_title),
        epIndex >= 0 ? epIndex + 1 : null,
    ];
    for (const candidate of candidates) {
        const parsed = Number(candidate);
        if (Number.isFinite(parsed) && parsed > 0) return parsed;
    }
    return null;
}

export function episodeNumberFromList(episodes, episodeId) {
    const id = String(episodeId || '').trim();
    if (!id) return null;
    const list = Array.isArray(episodes) ? episodes : [];
    const idx = list.findIndex((ep) => String(ep?.id || '').trim() === id);
    if (idx < 0) return 0;
    const ep = list[idx];
    if (!ep || ep.is_deleted) return 0;
    return episodeSortNumber(ep, idx);
}

/**
 * Resolve one visual-dependency token to an entity row.
 * The host episode's row is the dependency graph.
 * If that episode has no row, use the nearest earlier episode only.
 * A later episode is not a dependency source.
 */
export function resolveDependencyEntity(dependencyToken, entities, preferredEpisodeId = null, episodeNumberOf = null) {
    const rawToken = String(dependencyToken || '').trim();
    if (!rawToken) return null;

    const normalizedToken = normalizeEntityToken(rawToken);
    const resolvedEntityId = parseDependencyEntityId(rawToken);
    const matches = (Array.isArray(entities) ? entities : []).filter((entity) => {
        if (!entity || entity?.is_deleted) return false;

        const entityId = String(entity.id || '').trim();
        const entityName = normalizeEntityToken(entity.name || '');
        const entityNameEn = normalizeEntityToken(entity.name_en || '');

        if (resolvedEntityId && entityId && entityId === resolvedEntityId) return true;
        if (entityId && entityId === rawToken) return true;
        if (normalizedToken && entityName && entityName === normalizedToken) return true;
        if (normalizedToken && entityNameEn && entityNameEn === normalizedToken) return true;
        return false;
    });
    if (!matches.length) return null;

    if (resolvedEntityId) {
        const exact = matches.find((entity) => String(entity.id || '').trim() === resolvedEntityId);
        if (exact) return exact;
    }
    if (/^\d+$/.test(rawToken)) {
        const rawIdHit = matches.find((entity) => String(entity.id || '').trim() === rawToken);
        if (rawIdHit) return rawIdHit;
    }

    const preferred = String(preferredEpisodeId || '').trim();
    if (preferred) {
        const episodeMatch = matches.find((entity) => String(entity?.episode_id || '').trim() === preferred);
        if (episodeMatch) return episodeMatch;
    }

    if (typeof episodeNumberOf !== 'function' || !preferred) {
        return matches[0];
    }
    const rawHost = episodeNumberOf(preferred);
    const hostNumber = Number(rawHost);
    if (rawHost === 0) return null;
    if (!Number.isFinite(hostNumber) || hostNumber <= 0) return matches[0];

    const episodeState = (episodeId) => {
        const id = String(episodeId || '').trim();
        if (!id) return { kind: 'unnumbered' };
        const raw = episodeNumberOf(id);
        const number = Number(raw);
        if (raw === null || raw === undefined || raw === '') return { kind: 'unnumbered' };
        if (!Number.isFinite(number) || number <= 0) return { kind: 'skip' };
        return { kind: 'numbered', number };
    };

    let prior = null;
    let priorDistance = 0;
    matches.forEach((entity) => {
        const episodeId = String(entity?.episode_id || '').trim();
        if (!episodeId || episodeId === preferred) return;
        const state = episodeState(episodeId);
        if (state.kind !== 'numbered' || state.number >= hostNumber) return;
        const distance = hostNumber - state.number;
        if (!prior || distance < priorDistance || (distance === priorDistance && preferImagedRow(entity, prior) === entity)) {
            prior = entity;
            priorDistance = distance;
        }
    });
    if (prior) return prior;

    const unnumbered = matches.filter((entity) => episodeState(entity?.episode_id).kind === 'unnumbered');
    if (!unnumbered.length) return null;
    return unnumbered.reduce((best, entity) => preferImagedRow(entity, best));
}

/**
 * Image to copy onto a subject from an earlier episode.
 * The subject must already name an asset dependency.
 * The source is the same-named subject in the nearest earlier episode,
 * not the dependency row and not a later episode.
 */
export function pickNearestEpisodeSameNameReuseSource(entity, entityPool, episodeNumberOf, isReusableSource) {
    const hostId = String(entity?.id || '').trim();
    const hostEpisodeId = String(entity?.episode_id || '').trim();
    const hostEpisodeNumber = Number(episodeNumberOf?.(hostEpisodeId) || 0);
    const hostType = String(entity?.type || '').trim().toLowerCase();
    if (!hostEpisodeNumber) return null;

    const dependencyTokens = parseVisualDependencies(entity?.visual_dependencies)
        .filter((token) => !isDirectImageRefToken(token));
    if (!dependencyTokens.length) return null;

    const hostKeys = entityNameKeySet(entity);
    if (!hostKeys.size) return null;

    let best = null;
    let bestDistance = 0;
    (entityPool || []).forEach((candidate) => {
        if (!candidate || candidate.is_deleted) return;
        const candidateId = String(candidate?.id || '').trim();
        if (!candidateId || candidateId === hostId) return;
        const candidateEpisodeId = String(candidate?.episode_id || '').trim();
        if (!candidateEpisodeId || candidateEpisodeId === hostEpisodeId) return;
        const candidateType = String(candidate?.type || '').trim().toLowerCase();
        if (hostType && candidateType && candidateType !== hostType) return;
        if (!nameKeysHit(hostKeys, entityNameKeySet(candidate))) return;
        if (typeof isReusableSource === 'function' && !isReusableSource(candidate)) return;
        const candidateEpisodeNumber = Number(episodeNumberOf?.(candidateEpisodeId) || 0);
        if (!candidateEpisodeNumber || candidateEpisodeNumber >= hostEpisodeNumber) return;
        const distance = hostEpisodeNumber - candidateEpisodeNumber;
        const better = !best
            || distance < bestDistance
            || (distance === bestDistance && (Number(candidate.id) || 0) > (Number(best.id) || 0));
        if (better) {
            best = candidate;
            bestDistance = distance;
        }
    });
    return best;
}
