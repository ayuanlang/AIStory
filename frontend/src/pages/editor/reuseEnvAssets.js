/**
 * Global-assets dropdown helpers (pure JS — avoid editorHelpers.jsx HMR issues).
 */

const normalizeKey = (value) => String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\u4e00-\u9fff]/gu, '');

/** `0度…` / `0°…` / `180 Deg …` angle derivative names. */
export const isAngleDerivativeEnvironmentName = (envName) => {
    const raw = String(envName || '').trim();
    if (!raw) return false;
    if (/^(?:\d+|[０-９]+)\s*(?:度|°|º|deg(?:ree)?s?\b)/i.test(raw)) return true;
    if (/(?:^|[_\s\-/\.])(?:\d+|[０-９]+)\s*(?:度|°|º|deg(?:ree)?s?\b)/i.test(raw)) return true;
    return false;
};

export const isEnvironmentAssetType = (typeValue) => {
    const typeKey = String(typeValue || '').trim().toLowerCase();
    if (!typeKey) return false;
    return (
        typeKey === 'environment'
        || typeKey === 'env'
        || typeKey.includes('environment')
        || typeKey.includes('env')
        || typeKey.includes('环境')
        || typeKey.includes('场景')
    );
};

const parseDependencyStrategyType = (value) => {
    let dep = value;
    if (typeof dep === 'string') {
        const raw = dep.trim();
        if (!raw) return '';
        try {
            dep = JSON.parse(raw);
        } catch (_) {
            return raw;
        }
    }
    if (!dep || typeof dep !== 'object') return '';
    return String(dep.type || '').trim();
};

/**
 * Only main/baseline ENV for Global Assets dropdown.
 * Hide angle derivatives (`0度云渊仙境`) and Type A/B derivatives.
 */
const readCustomAttributes = (asset) => {
    const raw = asset?.custom_attributes ?? asset?.customAttributes ?? asset?.extra;
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw;
    if (typeof raw === 'string') {
        try {
            const parsed = JSON.parse(raw);
            return (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : {};
        } catch (_) {
            return {};
        }
    }
    return {};
};

const environmentHasEnvDependency = (asset) => {
    let deps = asset?.visual_dependencies ?? asset?.visualDependencies;
    if (typeof deps === 'string') {
        try {
            deps = JSON.parse(deps);
        } catch (_) {
            deps = String(deps || '').split(/[,，;；\n]+/);
        }
    }
    return (Array.isArray(deps) ? deps : []).some((item) => (
        /^ENV\s*[:：[]/i.test(String(item || '').trim())
    ));
};

export const isReusableMainEnvironmentAsset = (asset) => {
    if (!asset) return false;
    if (!isEnvironmentAssetType(asset?.type)) return false;

    const attrs = readCustomAttributes(asset);
    if (
        attrs.source === 'programmatic_derived_framing'
        || attrs.derived_kind
        || attrs['所属主环境']
        || attrs.owning_main_environment
    ) {
        return false;
    }

    const nameCandidates = [
        asset?.name,
        asset?.name_en,
        asset?.name_zh,
        asset?.subject_name,
        asset?.subject_name_exact,
    ];
    if (nameCandidates.some((value) => isAngleDerivativeEnvironmentName(value))) {
        return false;
    }

    const depType = parseDependencyStrategyType(asset?.dependency_strategy);
    if (/^baseline\s*definition$/i.test(depType)) return true;
    if (/^type\s*[ab]$/i.test(depType)) return false;
    if (environmentHasEnvDependency(asset) && !/^style\s*reference$/i.test(depType)) {
        return false;
    }
    return true;
};

/** Angle / look-up / state derivative ENV names (`0度港口`, `0度港口_仰天`). */
export const isDerivedEnvironmentName = (envName) => {
    const raw = String(envName || '').trim();
    if (!raw) return false;
    return isAngleDerivativeEnvironmentName(raw);
};

export const isDerivedEnvironmentAsset = (asset) => (
    Boolean(asset)
    && isEnvironmentAssetType(asset?.type)
    && !isReusableMainEnvironmentAsset(asset)
);

/**
 * Extract location names from script:
 * - `{location=云渊仙境(Cloud Abyss)}`
 * - `location=云渊仙境(Cloud Abyss)` (no braces)
 */
export const extractScriptLocationEnvNames = (scriptText) => {
    const text = String(scriptText || '');
    if (!text) return [];
    const found = [];
    const seen = new Set();

    const pushLocation = (rawValue) => {
        let raw = String(rawValue || '').trim();
        if (!raw) return;
        // Trim trailing scene-header junk after the location token (keep bilingual parens).
        raw = raw.split(/\s*\/\s*/)[0].trim();
        raw = raw.replace(/[}\]]+$/g, '').trim();
        if (!raw) return;

        let zh = '';
        let en = '';
        const bilingual = raw.match(/^(.+?)\s*[\(（]\s*([^\)）]+?)\s*[\)）]\s*$/);
        if (bilingual) {
            zh = String(bilingual[1] || '').trim();
            en = String(bilingual[2] || '').trim();
        } else if (/[\u4e00-\u9fff]/.test(raw)) {
            zh = raw;
        } else {
            en = raw;
        }

        const key = `${normalizeKey(zh)}|${normalizeKey(en)}|${normalizeKey(raw)}`;
        if (!key || key === '||' || seen.has(key)) return;
        seen.add(key);
        found.push({ zh, en, raw });
    };

    // Prefer strict `{location=…}` first (stops at `}` so bilingual parens stay intact).
    const strictBracedRe = /\{\s*location\s*[=：:＝]\s*([^}]+)\s*\}/gi;
    let match;
    while ((match = strictBracedRe.exec(text)) !== null) {
        pushLocation(match[1]);
    }
    // Fallback: bare `location=…` up to newline / pipe / slash.
    const bareRe = /(?:^|[^\w{])location\s*[=：:＝]\s*([^\}\n|/]+)/gi;
    while ((match = bareRe.exec(text)) !== null) {
        pushLocation(match[1]);
    }

    return found;
};

export const environmentAssetMatchesScriptLocations = (asset, locations) => {
    if (!asset || !Array.isArray(locations) || locations.length === 0) return false;
    const assetKeys = [
        asset?.name,
        asset?.name_zh,
        asset?.name_en,
        asset?.subject_name_exact,
        asset?.subject_name,
    ]
        .map((value) => normalizeKey(value))
        .filter(Boolean);
    if (!assetKeys.length) return false;
    const assetKeySet = new Set(assetKeys);
    for (const loc of locations) {
        const candidates = [loc?.zh, loc?.en, loc?.raw]
            .map((value) => normalizeKey(value))
            .filter(Boolean);
        if (candidates.some((key) => assetKeySet.has(key))) return true;
    }
    return false;
};

/** Hard ban for any asset whose display name is an angle derivative (type-agnostic). */
export const assetHasAngleDerivativeName = (asset) => (
    [asset?.name, asset?.name_en, asset?.name_zh, asset?.subject_name]
        .some((value) => isAngleDerivativeEnvironmentName(value))
);

/** True when the asset belongs to the given episode (not reusable as "global"). */
export const isAssetFromEpisode = (asset, episodeId) => {
    const wanted = String(episodeId || '').trim();
    if (!wanted) return false;
    const assetEpisodeId = String(asset?.episode_id ?? '').trim();
    return Boolean(assetEpisodeId) && assetEpisodeId === wanted;
};

/**
 * Dropdown list filter: keep non-ENV; for ENV keep mains only.
 * Always hide assets that belong to `excludeEpisodeId` (current episode).
 */
export const filterGlobalReuseDropdownAssets = (
    assets,
    typeFilter = 'all',
    keyword = '',
    excludeEpisodeId = null,
) => {
    const normalizedKeyword = String(keyword || '').trim().toLowerCase();
    const typeFilterValue = String(typeFilter || 'all').trim();
    return (Array.isArray(assets) ? assets : []).filter((asset) => {
        // Global Assets = reuse from other episodes / project-level only.
        if (isAssetFromEpisode(asset, excludeEpisodeId)) return false;

        // Absolute: never list `0度…` / `180 Deg…` rows in this dropdown.
        if (assetHasAngleDerivativeName(asset)) return false;

        const typeValue = String(asset?.type || '').trim();
        const passType = typeFilterValue === 'all' || typeValue === typeFilterValue
            || (typeFilterValue.toLowerCase() === 'environment' && isEnvironmentAssetType(typeValue));
        if (!passType) return false;

        if (isEnvironmentAssetType(typeValue) && !isReusableMainEnvironmentAsset(asset)) {
            return false;
        }

        if (!normalizedKeyword) return true;
        const haystack = [
            asset?.name,
            asset?.name_en,
            asset?.description,
            asset?.narrative_description,
            asset?.anchor_description,
            asset?.type,
        ]
            .map((v) => String(v || '').toLowerCase())
            .join(' ');
        return haystack.includes(normalizedKeyword);
    });
};
