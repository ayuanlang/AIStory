import { entityTokenMatchesName, normalizeEntityToken } from '../../lib/entityToken.js';

const TYPED_REF_RE = /(CHAR|ENV|PROP)\s*:\s*\[@?([^\]]+)\]/gi;

const typeForKind = (kind) => {
    if (kind === 'CHAR') return 'character';
    if (kind === 'ENV') return 'environment';
    return 'prop';
};

/** Typed CHAR / ENV / PROP names in prompt order. Untyped brackets are ignored. */
export function extractOrderedTypedEntityRefs(text) {
    const source = String(text || '');
    const refs = [];
    const seen = new Set();
    const re = new RegExp(TYPED_REF_RE.source, 'gi');
    let match;
    while ((match = re.exec(source)) !== null) {
        const kind = String(match[1] || '').toUpperCase();
        const name = String(match[2] || '').trim().replace(/^@+/, '').trim();
        if (!name || name.length > 80) continue;
        if (/(?:CHAR|ENV|PROP)\s*:/i.test(name)) continue;
        const key = normalizeEntityToken(name);
        if (!key || seen.has(key)) continue;
        seen.add(key);
        refs.push({ name, type: typeForKind(kind), key });
    }
    return refs;
}

function findEntityForTypedName(entityPool, name, preferredEpisodeId) {
    const entities = Array.isArray(entityPool) ? entityPool : [];
    const matches = entities.filter((item) => entityTokenMatchesName(item, name));
    if (!matches.length) return null;
    const preferred = String(preferredEpisodeId || '').trim();
    if (preferred) {
        const episodeMatch = matches.find((item) => String(item?.episode_id || '').trim() === preferred);
        if (episodeMatch) return episodeMatch;
        const globalMatch = matches.find((item) => !String(item?.episode_id || '').trim());
        if (globalMatch) return globalMatch;
    }
    return matches[0];
}

/**
 * Prompt names that have no asset row at all.
 * An existing row with an empty image is not included; that case already
 * keeps a slot from the matched entity.
 */
export function unmatchedTypedEntityRefs({
    promptText = '',
    associatedEntities = '',
    includeAssociatedEntities = true,
    entityPool = [],
    preferredEpisodeId = null,
} = {}) {
    const texts = [];
    if (includeAssociatedEntities && associatedEntities) texts.push(associatedEntities);
    if (promptText) texts.push(promptText);
    const seen = new Set();
    const missing = [];
    texts.forEach((text) => {
        extractOrderedTypedEntityRefs(text).forEach((ref) => {
            if (seen.has(ref.key)) return;
            seen.add(ref.key);
            if (findEntityForTypedName(entityPool, ref.name, preferredEpisodeId)) return;
            missing.push(ref);
        });
    });
    return missing;
}
