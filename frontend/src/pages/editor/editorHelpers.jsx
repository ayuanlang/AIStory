import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Video } from 'lucide-react';
import { BASE_URL, ASSET_BASE_URL } from '../../config';
import { createEntity, regenerateScene, batchSupplementMissingEntities } from '../../services/api';
import { normalizeEntityToken, entityTokenMatchesName, extractEntityRawNamesFromPrompt } from '../../lib/entityToken';

const normalizeExternalMediaUrl = (rawUrl) => {
    const stable = String(rawUrl || '').trim();
    if (!stable) return '';

    // Handle host-only URLs like: tcn2obdg8.hn-bkt.clouddn.com/aistory/...
    if (/^[A-Za-z0-9.-]+\.(clouddn\.com|qiniucs\.com)\//i.test(stable)) {
        return `https://${stable}`;
    }

    if (/^http:\/\//i.test(stable) && /(clouddn\.com|qiniucs\.com)/i.test(stable)) {
        return stable.replace(/^http:\/\//i, 'https://');
    }

    return stable;
};

const shouldProxyExternalMediaUrl = (rawUrl) => {
    const stable = String(rawUrl || '').trim();
    if (!stable || !/^https?:\/\//i.test(stable)) return false;
    if (stable.includes('/api/v1/assets/proxy?url=')) return false;

    try {
        const parsed = new URL(stable);
        const host = String(parsed.hostname || '').trim().toLowerCase();
        const backendHost = (() => {
            try {
                return String(new URL(String(BASE_URL || ''), window.location.origin).hostname || '').trim().toLowerCase();
            } catch {
                return '';
            }
        })();
        const isLocalHost = host === 'localhost' || host === '127.0.0.1';
        if (!host || isLocalHost) return false;
        if (backendHost && host === backendHost) return false;

        // Any cross-origin media that fails direct browser access can fall back to the backend proxy.
        return true;
    } catch {
        return false;
    }
};

const buildAssetProxyUrl = (rawUrl) => {
    const stable = String(rawUrl || '').trim();
    if (!stable) return '';
    const resolvedBase = String(BASE_URL || '').trim().replace(/\/+$/, '');
    if (!resolvedBase) return stable;
    return `${resolvedBase}/api/v1/assets/proxy?url=${encodeURIComponent(stable)}`;
};

// Helper to handle relative URLs
export const getFullUrl = (url) => {
    if (!url) return '';
    const normalizedExternal = normalizeExternalMediaUrl(url);
    if (normalizedExternal.startsWith('http') || normalizedExternal.startsWith('blob:') || normalizedExternal.startsWith('data:')) return normalizedExternal;
    // If it's a relative path starting with /, append BASE_URL
    if (normalizedExternal.startsWith('/')) {
        const resolvedAssetBase = String(ASSET_BASE_URL || BASE_URL || '').trim();
        // Avoid double slash if base URL ends with /
        const base = resolvedAssetBase.endsWith('/') ? resolvedAssetBase.slice(0, -1) : resolvedAssetBase;
        return `${base}${normalizedExternal}`;
    }
    return normalizedExternal;
};

export const getThumbUrl = (url) => {
    if (!url) return '';
    const raw = normalizeExternalMediaUrl(url);
    if (raw.startsWith('blob:') || raw.startsWith('data:')) return raw;

    if (raw.startsWith('http')) {
        const isAliyun = raw.includes('aliyuncs.com');
        const isTencent = raw.includes('myqcloud.com');
        const isQiniu = raw.includes('clouddn.com') || raw.includes('qiniucs.com');
        
        if (isAliyun && !raw.includes('x-oss-process')) {
            const sep = raw.includes('?') ? '&' : '?';
            return `${raw}${sep}x-oss-process=image/resize,m_lfit,w_256/quality,q_80/format,webp`;
        }
        if (isTencent && !raw.includes('imageMogr2')) {
            const sep = raw.includes('?') ? '&' : '?';
            return `${raw}${sep}imageMogr2/thumbnail/256x/format/webp/quality/80`;
        }
        if (isQiniu && !raw.includes('imageMogr2')) {
            const sep = raw.includes('?') ? '&' : '?';
            return `${raw}${sep}imageMogr2/thumbnail/256x/format/webp/quality/80`;
        }
        return raw;
    }

    let normalizedPath = raw;
    if (normalizedPath.startsWith('/uploads/')) {
        normalizedPath = normalizedPath.replace('/uploads/', '');
    } else if (normalizedPath.startsWith('/')) {
        normalizedPath = normalizedPath.slice(1);
    }
    const resolvedAssetBase = String(ASSET_BASE_URL || BASE_URL || '').trim();
    const base = resolvedAssetBase.endsWith('/') ? resolvedAssetBase.slice(0, -1) : resolvedAssetBase;
    return `${base}/api/v1/assets/thumb/${normalizedPath}`;
};

export const canFallbackToAssetProxy = (url) => {
    return shouldProxyExternalMediaUrl(normalizeExternalMediaUrl(url));
};

export const getMediaUrlWithFallback = (url, useProxy = false) => {
    const normalized = normalizeExternalMediaUrl(url);
    if (!normalized) return '';
    if (useProxy && canFallbackToAssetProxy(normalized)) {
        return buildAssetProxyUrl(normalized);
    }
    return getFullUrl(normalized);
};

export const createInitialFrameTrimState = () => ({
    open: false,
    type: 'start',
    sourceUrl: '',
    topPct: 0,
    rightPct: 0,
    bottomPct: 0,
    leftPct: 0,
    saving: false,
});

export const clampFrameTrimPercent = (value) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 0;
    return Math.max(0, Math.min(45, numeric));
};

export const normalizeFrameTrimMargins = (draft) => {
    const topPct = clampFrameTrimPercent(draft?.topPct);
    const rightPct = clampFrameTrimPercent(draft?.rightPct);
    const bottomPct = clampFrameTrimPercent(draft?.bottomPct);
    const leftPct = clampFrameTrimPercent(draft?.leftPct);
    const widthPct = Math.max(1, 100 - leftPct - rightPct);
    const heightPct = Math.max(1, 100 - topPct - bottomPct);
    return {
        topPct,
        rightPct,
        bottomPct,
        leftPct,
        widthPct,
        heightPct,
    };
};

export const brokenMediaUrls = new Set();
export const brokenSceneImageUrls = new Set();
export const warmMediaUrls = new Set();
const brokenMediaUrlTs = new Map();
const SIGNED_URL_BROKEN_TTL_MS = 10 * 60 * 1000;
const DEFAULT_BROKEN_TTL_MS = 6 * 60 * 60 * 1000;

const isLikelySignedMediaUrl = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return false;
    const lowered = raw.toLowerCase();
    if (lowered.includes('x-amz-signature=') || lowered.includes('x-amz-algorithm=')) return true;
    if (lowered.includes('rh-comfy-auth=')) return true;
    if (lowered.includes('token=') && lowered.includes('e=')) return true;
    return false;
};

const getBrokenUrlTtlMs = (url) => (isLikelySignedMediaUrl(url) ? SIGNED_URL_BROKEN_TTL_MS : DEFAULT_BROKEN_TTL_MS);

const purgeExpiredBrokenMediaUrl = (url) => {
    const normalized = String(url || '').trim();
    if (!normalized) return;
    const ts = Number(brokenMediaUrlTs.get(normalized) || 0);
    if (!Number.isFinite(ts) || ts <= 0) return;
    const ttl = getBrokenUrlTtlMs(normalized);
    if ((Date.now() - ts) < ttl) return;
    brokenMediaUrlTs.delete(normalized);
    brokenMediaUrls.delete(normalized);
};

export const clearBrokenMediaUrl = (url) => {
    const normalized = String(url || '').trim();
    if (!normalized) return;
    brokenMediaUrlTs.delete(normalized);
    brokenMediaUrls.delete(normalized);
};

export const shouldBypassBrokenMediaCache = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return false;
    if (raw.startsWith('/uploads/')) return true;
    try {
        const parsed = new URL(raw, BASE_URL || window.location.origin);
        return parsed.pathname.startsWith('/uploads/');
    } catch {
        return false;
    }
};

export const rememberBrokenMediaUrl = (url) => {
    const normalized = String(url || '').trim();
    if (!normalized) return;
    if (shouldBypassBrokenMediaCache(normalized)) return;
    brokenMediaUrlTs.set(normalized, Date.now());
    brokenMediaUrls.add(normalized);
};

export const isBrokenMediaUrl = (url) => {
    if (shouldBypassBrokenMediaCache(url)) return false;
    const normalized = String(url || '').trim();
    purgeExpiredBrokenMediaUrl(normalized);
    return brokenMediaUrls.has(normalized);
};

export const rememberWarmMediaUrl = (url) => {
    const normalized = String(url || '').trim();
    if (!normalized) return;
    clearBrokenMediaUrl(normalized);
    warmMediaUrls.add(normalized);
};

export const isWarmMediaUrl = (url) => {
    const normalized = String(url || '').trim();
    if (!normalized) return false;
    return warmMediaUrls.has(normalized);
};

export const getSafeMediaUrl = (url) => {
    const raw = String(url || '').trim();
    if (!raw || isBrokenMediaUrl(raw)) return '';
    return getFullUrl(raw);
};

export const extractImageJobResultUrl = (statusResp) => {
    const result = (statusResp?.result && typeof statusResp.result === 'object') ? statusResp.result : {};
    const candidates = [
        result?.url,
        result?.image_url,
        result?.imageUrl,
        result?.generated_url,
        statusResp?.url,
        statusResp?.image_url,
        statusResp?.imageUrl,
    ];
    for (const value of candidates) {
        const stable = String(value || '').trim();
        if (stable) return stable;
    }
    return '';
};

export const rememberBrokenSceneImageUrl = (url) => {
    const normalized = String(url || '').trim();
    if (!normalized) return;
    brokenSceneImageUrls.add(normalized);
    rememberBrokenMediaUrl(normalized);
};

export const isBrokenSceneImageUrl = (url) => {
    return brokenSceneImageUrls.has(String(url || '').trim());
};

export const normalizeBatchParallelLimit = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 3;
    return Math.min(12, Math.max(1, Math.trunc(parsed)));
};

export const normalizeAsciiSubjectSeparatorsForDeps = (value) => {
    return String(value || '').replace(/[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+/g, (matched) => {
        return matched.replace(/[_-]+/g, ' ');
    });
};

export const normalizeSubjectNameForDeps = (value) => {
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

export const normalizeSubjectKeyForDeps = (value) => {
    const stable = normalizeSubjectNameForDeps(value);
    if (!stable) return '';
    return normalizeEntityToken(stable)
        .replace(/[^\p{L}\p{N}\u4e00-\u9fff]/gu, '');
};

export const normalizeAsciiSubjectSeparators = normalizeAsciiSubjectSeparatorsForDeps;
export const normalizeSubjectName = normalizeSubjectNameForDeps;
export const normalizeSubjectKey = normalizeSubjectKeyForDeps;
export const normalizeImportSubjectKey = normalizeSubjectKeyForDeps;
export const IMG_PLACEHOLDER_SRC = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

export const parseVisualDependencies = (value) => {
    let candidates = [];

    if (Array.isArray(value)) {
        candidates = value;
    } else if (typeof value === 'string') {
        const raw = String(value || '').trim();
        if (!raw) return [];

        if ((raw.startsWith('[') && raw.endsWith(']')) || (raw.startsWith('{') && raw.endsWith('}'))) {
            try {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    candidates = parsed;
                } else if (typeof parsed === 'string') {
                    candidates = [parsed];
                }
            } catch (_) {
                candidates = [];
            }
        }

        if (candidates.length === 0) {
            candidates = raw.split(/[\n,，;；|]/);
        }
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

export const SafeImage = ({ src, alt = '', className = '', fallback = null, ...imgProps }) => {
    const rawSrc = String(src || '').trim();
    const containerRef = useRef(null);
    const requestedLoading = String(imgProps.loading || '').trim().toLowerCase();
    const eagerLoad = requestedLoading === 'eager' || requestedLoading === 'auto';
    const [shouldLoad, setShouldLoad] = useState(() => eagerLoad || isWarmMediaUrl(rawSrc));
    const [failed, setFailed] = useState(() => !rawSrc || isBrokenMediaUrl(rawSrc));
    const [isLoaded, setIsLoaded] = useState(() => isWarmMediaUrl(rawSrc));
    const [useProxy, setUseProxy] = useState(false);
    const [retryToken, setRetryToken] = useState(0);
    const retryAttemptRef = useRef(0);
    const retryTimerRef = useRef(null);

    const { onLoad: userOnLoad, onError: userOnError, retryOnError = false, retryDelays = null, ...restImgProps } = imgProps;
    const retryDelayList = Array.isArray(retryDelays) && retryDelays.length > 0
        ? retryDelays.map((value) => Math.max(250, Number(value) || 0)).filter(Boolean)
        : [1000, 2500, 5000, 9000];

    useEffect(() => {
        if (retryTimerRef.current) {
            clearTimeout(retryTimerRef.current);
            retryTimerRef.current = null;
        }
        retryAttemptRef.current = 0;
        setRetryToken(0);
        setFailed(!rawSrc || isBrokenMediaUrl(rawSrc));
        setIsLoaded(isWarmMediaUrl(rawSrc));
        setUseProxy(false);
        if (isWarmMediaUrl(rawSrc)) {
            setShouldLoad(true);
        }
        return () => {
            if (retryTimerRef.current) {
                clearTimeout(retryTimerRef.current);
                retryTimerRef.current = null;
            }
        };
    }, [rawSrc]);

    useEffect(() => {
        if (eagerLoad) {
            setShouldLoad(true);
            return;
        }
        const node = containerRef.current;
        if (!node || shouldLoad || !rawSrc || failed) return;

        if (typeof IntersectionObserver === 'undefined') {
            setShouldLoad(true);
            return;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setShouldLoad(true);
                    }
                });
            },
            {
                rootMargin: '320px 0px',
                threshold: 0.01,
            }
        );

        observer.observe(node);
        return () => observer.disconnect();
    }, [eagerLoad, shouldLoad, rawSrc, failed]);

    const resolvedSrc = failed ? '' : getMediaUrlWithFallback(rawSrc, useProxy);
    const thumbSrc = getThumbUrl(rawSrc);
    if (!resolvedSrc) return fallback || null;

    return (
        <div ref={containerRef} className={`relative flex items-center justify-center overflow-hidden bg-[#151515] ${className ? className.replace('object-cover', '').replace('object-contain', '').replace('max-w-full', 'w-full').replace('max-h-full', 'h-full') : ''}`}>
            {!isLoaded && !failed && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                    <Loader2 className="w-5 h-5 animate-spin text-white/40 drop-shadow-md" />
                </div>
            )}
            {!isLoaded && !failed && shouldLoad && thumbSrc && (
                <img
                    src={thumbSrc}
                    alt={`${alt} thumbnail`}
                    className={`absolute inset-0 w-full h-full blur-[8px] scale-110 object-cover opacity-60 z-0 transition-opacity duration-300`}
                />
            )}
            <img
                key={`${rawSrc}:${useProxy ? 'proxy' : 'direct'}:${retryToken}`}
                src={shouldLoad ? resolvedSrc : IMG_PLACEHOLDER_SRC}
                alt={alt}
                className={`absolute inset-0 w-full h-full transition-all duration-700 z-10 ${(className || '').includes('object-contain') ? 'object-contain' : 'object-cover'} ${
                    isLoaded ? 'opacity-100 blur-0 scale-100 bg-transparent' : 'opacity-0 blur-[10px] scale-110 bg-transparent'
                }`}
                loading={imgProps.loading || 'lazy'}
                decoding={imgProps.decoding || 'async'}
                fetchpriority={imgProps.fetchPriority || 'low'}
                onLoad={(e) => {
                    if (e.target.src === IMG_PLACEHOLDER_SRC) return;
                    retryAttemptRef.current = 0;
                    rememberWarmMediaUrl(rawSrc);
                    setIsLoaded(true);
                    if (typeof userOnLoad === 'function') userOnLoad();
                }}
                onError={() => {
                    if (!shouldLoad) {
                        setShouldLoad(true);
                        if (typeof userOnError === 'function') userOnError();
                        return;
                    }
                    if (!useProxy && canFallbackToAssetProxy(rawSrc)) {
                        setUseProxy(true);
                        if (typeof userOnError === 'function') userOnError();
                        return;
                    }
                    if (retryOnError && retryAttemptRef.current < retryDelayList.length) {
                        const retryDelay = retryDelayList[retryAttemptRef.current];
                        retryAttemptRef.current += 1;
                        setShouldLoad(false);
                        setIsLoaded(false);
                        retryTimerRef.current = setTimeout(() => {
                            retryTimerRef.current = null;
                            setFailed(false);
                            setShouldLoad(true);
                            setRetryToken((value) => value + 1);
                        }, retryDelay);
                        if (typeof userOnError === 'function') userOnError();
                        return;
                    }
                    rememberBrokenMediaUrl(rawSrc);
                    setFailed(true);
                    if (typeof userOnError === 'function') userOnError();
                }}
                {...restImgProps}
            />
        </div>
    );
};

export const SafeAudio = ({ src, fallback = null, ...audioProps }) => {
    const rawSrc = String(src || '').trim();
    const [failed, setFailed] = useState(() => !rawSrc || isBrokenMediaUrl(rawSrc));
    const [useProxy, setUseProxy] = useState(false);

    useEffect(() => {
        setFailed(!rawSrc || isBrokenMediaUrl(rawSrc));
        setUseProxy(false);
    }, [rawSrc]);

    const resolvedSrc = failed ? '' : getMediaUrlWithFallback(rawSrc, useProxy);
    if (!resolvedSrc) return fallback || null;

    return (
        <audio
            src={resolvedSrc}
            onError={() => {
                if (!useProxy && canFallbackToAssetProxy(rawSrc)) {
                    setUseProxy(true);
                    return;
                }
                rememberBrokenMediaUrl(rawSrc);
                setFailed(true);
            }}
            {...audioProps}
        />
    );
};

export const normalizeMediaRefList = (items) => {
    if (!Array.isArray(items)) return [];
    return [...new Set(
        items
            .map((item) => String(item || '').trim())
            .filter(Boolean)
    )];
};

export const areMediaRefListsEqual = (left, right) => {
    const a = normalizeMediaRefList(left);
    const b = normalizeMediaRefList(right);
    if (a.length !== b.length) return false;
    return a.every((item, idx) => item === b[idx]);
};

export const collectMatchedEntitiesFromPrompt = ({
    promptText = '',
    associatedEntities = '',
    entityPool = [],
    includeAssociatedEntities = true,
}) => {
    const entities = Array.isArray(entityPool) ? entityPool : [];
    if (!entities.length) return [];

    const rawMatches = [];
    if (includeAssociatedEntities && associatedEntities) {
        rawMatches.push(...extractEntityRawNamesFromPrompt(associatedEntities));
    }

    rawMatches.push(...extractEntityRawNamesFromPrompt(promptText));

    const candidates = new Set();
    rawMatches
        .map((value) => String(value || '').trim())
        .filter(Boolean)
        .forEach((raw) => {
            const normalized = normalizeEntityToken(raw);
            if (normalized) candidates.add(normalized);
        });

    return entities.filter((entity) => {
        return Array.from(candidates).some((candidate) => entityTokenMatchesName(entity, candidate));
    });
};

export const buildShotVideoRefPromptText = (shot = {}, techObj = {}) => {
    const tech = techObj && typeof techObj === 'object' ? techObj : {};
    const parts = [
        String(shot?.video_content || shot?.prompt || '').trim(),
        String(tech?.video_prompt_cn || '').trim(),
        String(shot?.start_frame || '').trim(),
        String(shot?.end_frame || '').trim(),
    ];
    return parts.filter(Boolean).join('\n');
};

export const collectMatchedEntityImageUrlsFromPrompt = ({
    promptText = '',
    associatedEntities = '',
    entityPool = [],
    includeAssociatedEntities = true,
}) => {
    return normalizeMediaRefList(
        collectMatchedEntitiesFromPrompt({
            promptText,
            associatedEntities,
            entityPool,
            includeAssociatedEntities,
        }).map((entity) => entity?.image_url)
    );
};

export const buildShotVideoEntityRefSlots = ({
    promptText = '',
    associatedEntities = '',
    entityPool = [],
    includeAssociatedEntities = true,
} = {}) => {
    return collectMatchedEntitiesFromPrompt({
        promptText,
        associatedEntities,
        entityPool,
        includeAssociatedEntities,
    }).map((entity) => {
        const imageUrl = String(entity?.image_url || '').trim();
        return {
            entityId: entity?.id,
            name: String(entity?.name || entity?.name_en || '').trim(),
            nameEn: String(entity?.name_en || '').trim(),
            type: String(entity?.type || entity?.entity_type || '').trim(),
            imageUrl: imageUrl || null,
            missing: !imageUrl,
            entity,
        };
    });
};

export const getMissingShotVideoEntityRefSlots = (slots = []) => (
    Array.isArray(slots) ? slots.filter((slot) => slot?.missing) : []
);

export const buildShotVideoRefDisplayItems = ({
    activeRefs = [],
    promptText = '',
    associatedEntities = '',
    entityPool = [],
    includeAssociatedEntities = true,
    includeEntityPlaceholders = true,
} = {}) => {
    const refs = normalizeMediaRefList(activeRefs);
    const matchedEntities = collectMatchedEntitiesFromPrompt({
        promptText,
        associatedEntities,
        entityPool,
        includeAssociatedEntities,
    });
    const items = [];
    const usedUrls = new Set();

    matchedEntities.forEach((entity) => {
        const imageUrl = String(entity?.image_url || '').trim();
        if (imageUrl) {
            usedUrls.add(imageUrl);
            items.push({
                key: `entity-${entity?.id || entity?.name || imageUrl}`,
                kind: 'image',
                entity,
                url: imageUrl,
                label: String(entity?.name || entity?.name_en || '').trim(),
            });
            return;
        }
        if (!includeEntityPlaceholders) return;
        items.push({
            key: `entity-missing-${entity?.id || entity?.name || items.length}`,
            kind: 'placeholder',
            entity,
            url: null,
            label: String(entity?.name || entity?.name_en || '').trim(),
        });
    });

    refs.forEach((url, idx) => {
        if (usedUrls.has(url)) return;
        items.push({
            key: `ref-${url}-${idx}`,
            kind: 'image',
            entity: null,
            url,
            label: '',
        });
    });

    return items;
};

export const SCENE_SUBJECT_TYPE_LABELS = {
    character: 'Character',
    prop: 'Prop',
    environment: 'Environment',
};

export const getSceneSubjectStatusKey = (scene) => String(scene?.id || scene?.scene_no || scene?.scene_name || '');

export const splitSceneSubjectNames = (value) => {
    return String(value || '')
        .split(/[\n,，;；]/)
        .map((item) => String(item || '').trim())
        .filter(Boolean);
};

export const normalizeSceneSubjectDefaultType = (value) => {
    const stable = String(value || '').trim().toLowerCase();
    if (stable === 'char') return 'character';
    if (stable === 'characters') return 'character';
    if (stable === 'props') return 'prop';
    if (stable === 'env') return 'environment';
    if (stable === 'environments') return 'environment';
    return stable;
};

export const parseTypedSceneSubjectToken = (rawToken, defaultType) => {
    const stableDefaultType = normalizeSceneSubjectDefaultType(defaultType) || 'character';
    const tokenText = String(rawToken || '').trim().replace(/^`+|`+$/g, '').trim();
    if (!tokenText) {
        return {
            type: stableDefaultType,
            name: '',
        };
    }

    const typedMatch = tokenText.match(/^\s*(CHAR|PROP|ENV|VEFX|SFX)\s*:\s*\[\s*([^\]]+?)\s*\]\s*$/i);
    if (!typedMatch) {
        return {
            type: stableDefaultType,
            name: tokenText,
        };
    }

    const rawType = String(typedMatch[1] || '').trim().toLowerCase();
    let resolvedType = stableDefaultType;
    if (rawType === 'char') resolvedType = 'character';
    else if (rawType === 'prop' || rawType === 'vefx' || rawType === 'sfx') resolvedType = 'prop';
    else if (rawType === 'env') resolvedType = 'environment';

    let cleanName = String(typedMatch[2] || '').trim();
    if (resolvedType === 'character') {
        cleanName = cleanName.replace(/^@+/, '').trim();
    }

    return {
        type: resolvedType,
        name: cleanName,
    };
};

export const extractSceneSubjectRefsFromField = (value, defaultType, sourceField) => {
    const stableDefaultType = normalizeSceneSubjectDefaultType(defaultType) || 'character';
    return splitSceneSubjectNames(value)
        .map((token) => {
            const parsed = parseTypedSceneSubjectToken(token, stableDefaultType);
            return {
                type: parsed.type || stableDefaultType,
                name: parsed.name,
                sourceField,
            };
        })
        .filter((item) => {
            const name = String(item?.name || '').trim();
            if (!name) return false;
            const lowerName = name.toLowerCase().replace(/^[()[\]{}]+|[()[\]{}]+$/g, '');
            if (lowerName === 'none' || lowerName === 'null' || lowerName === '无' || lowerName === 'nil' || lowerName === 'not applicable' || lowerName === 'n/a') {
                return false;
            }
            return true;
        });
};

export const buildSceneSubjectNameCandidates = (rawName) => {
    const source = String(rawName || '').trim();
    const candidates = new Set();

    const pushCandidate = (value) => {
        const normalized = normalizeEntityToken(value || '');
        if (normalized) candidates.add(normalized);
    };

    pushCandidate(source);

    // Split common bilingual separators so CN/EN either side can match.
    source
        .split(/\s*[\/|｜]|\s+-\s+|\s+–\s+|\s+—\s+|\s*\(\s*|\s*\)\s*/)
        .map((part) => String(part || '').trim())
        .filter(Boolean)
        .forEach(pushCandidate);

    return Array.from(candidates);
};

export const extractSceneSubjectRefs = (scene) => {
    const refs = [
        ...extractSceneSubjectRefsFromField(scene?.environment_name, 'environment', 'environment_name'),
        ...extractSceneSubjectRefsFromField(scene?.linked_characters, 'character', 'linked_characters'),
        ...extractSceneSubjectRefsFromField(scene?.key_props, 'prop', 'key_props'),
    ];

    const deduped = [];
    const seen = new Set();
    for (const ref of refs) {
        const normalizedName = normalizeEntityToken(ref?.name || '');
        if (!normalizedName) continue;
        const key = `${String(ref?.type || '').trim().toLowerCase()}::${normalizedName}`;
        if (seen.has(key)) continue;
        seen.add(key);
        deduped.push({
            ...ref,
            normalizedName,
        });
    }
    return deduped;
};

export const findMatchingEntityByType = (entities, type, rawName) => {
    const normalizedType = String(type || '').trim().toLowerCase();
    const nameCandidates = buildSceneSubjectNameCandidates(rawName);
    if (!normalizedType || nameCandidates.length === 0) return null;
    return (Array.isArray(entities) ? entities : []).find((entity) => {
        if (String(entity?.type || '').trim().toLowerCase() !== normalizedType) return false;
        return nameCandidates.some((candidate) => entityTokenMatchesName(entity, candidate));
    }) || null;
};

export const findMissingSceneSubjectRefs = (scene, entities) => {
    return extractSceneSubjectRefs(scene).filter((ref) => !findMatchingEntityByType(entities, ref.type, ref.name));
};

export const findCrossTypeEntityMatches = (entities, rawName, expectedType) => {
    const nameCandidates = buildSceneSubjectNameCandidates(rawName);
    const stableType = String(expectedType || '').trim().toLowerCase();
    if (!nameCandidates.length) return [];
    return (Array.isArray(entities) ? entities : []).filter((entity) => {
        const entityType = String(entity?.type || '').trim().toLowerCase();
        if (!entityType || entityType === stableType) return false;
        return nameCandidates.some((candidate) => entityTokenMatchesName(entity, candidate));
    });
};

export const buildSceneSubjectPlaceholderPayload = (scene, ref) => {
    const sourceSceneLabel = String(scene?.scene_no || scene?.scene_name || scene?.id || '').trim();
    const sourceSceneName = String(scene?.scene_name || '').trim();
    const sourceEnv = String(scene?.environment_name || '').trim();
    const coreInfo = String(scene?.core_scene_info || '').trim();
    const originalScript = String(scene?.original_script_text || '').trim();
    const typeLabel = SCENE_SUBJECT_TYPE_LABELS[String(ref?.type || '').trim().toLowerCase()] || 'Subject';
    const descriptionLines = [
        `Auto-created placeholder from scene subject reference.`,
        `Subject Type: ${typeLabel}`,
        sourceSceneLabel ? `Source Scene: ${sourceSceneLabel}` : '',
        sourceSceneName ? `Source Scene Name: ${sourceSceneName}` : '',
        sourceEnv ? `Scene Environment: ${sourceEnv}` : '',
        ref?.sourceField ? `Source Field: ${ref.sourceField}` : '',
        coreInfo ? `Core Scene Info: ${coreInfo}` : '',
        originalScript ? `Original Script Text: ${originalScript}` : '',
    ].filter(Boolean);

    return {
        name: String(ref?.name || '').trim(),
        type: String(ref?.type || '').trim().toLowerCase() || 'character',
        description: descriptionLines.join('\n\n'),
        anchor_description: sourceEnv || sourceSceneName || sourceSceneLabel || '',
        custom_attributes: {
            auto_placeholder_from_scene_subject: true,
            source_scene_id: Number(scene?.id || 0) || null,
            source_scene_no: String(scene?.scene_no || '').trim(),
            source_scene_name: sourceSceneName,
            source_field: String(ref?.sourceField || '').trim(),
        },
    };
};

export const createMissingSceneSubjectPlaceholders = async ({ projectId, sceneRows = [], existingEntities = [], onLog = null }) => {
    if (!projectId) {
        return {
            createdItems: [],
            skippedItems: [],
            failedItems: [],
            sceneReports: [],
            countsByType: { character: 0, prop: 0, environment: 0 },
            entities: Array.isArray(existingEntities) ? existingEntities : [],
        };
    }

    const knownEntities = Array.isArray(existingEntities) ? [...existingEntities] : [];
    const createdItems = [];
    const skippedItems = [];
    const failedItems = [];
    const sceneReports = [];
    const countsByType = { character: 0, prop: 0, environment: 0 };
    
    // We collect all the requested scenes that have missing refs so we just submit one batch request.
    const pendingScenes = [];
    const allRefsToProcess = [];

    for (const scene of (sceneRows || [])) {
        const missingRefs = findMissingSceneSubjectRefs(scene, knownEntities);
        if (missingRefs.length === 0) continue;

        const sceneReport = {
            sceneId: Number(scene?.id || 0) || null,
            sceneNo: String(scene?.scene_no || '').trim(),
            sceneName: String(scene?.scene_name || '').trim(),
            missing: missingRefs,
            created: [],
            skipped: [],
            failed: [],
        };

        const refsToProcess = missingRefs.filter(ref => {
            const existing = findMatchingEntityByType(knownEntities, ref.type, ref.name);
            if (existing?.id) {
                const skipped = { ...ref, id: existing.id };
                skippedItems.push(skipped);
                sceneReport.skipped.push(skipped);
                return false;
            }
            return true;
        });

        if (refsToProcess.length > 0) {
            if (sceneReport.sceneId) {
                pendingScenes.push(sceneReport.sceneId);
            }
            for (const r of refsToProcess) {
                // simple dedup within the pending array
                const key = `${r.type}::${r.name}`;
                if (!allRefsToProcess.some(existing => `${existing.type}::${existing.name}` === key)) {
                    allRefsToProcess.push(r);
                }
            }
        }
        sceneReports.push(sceneReport);
    }

    if (pendingScenes.length > 0) {
        try {
            onLog?.(`Multiple scenes are missing subjects. Submitting batch request to LLM to recover entities...`, 'process');
            const res = await batchSupplementMissingEntities(projectId, {
                scene_ids: pendingScenes,
                user_requirements: 'Auto supplement missing entities from script text based on the Editor prompt requirements.'
            });
            
            const addedCount = res?.added_count || {};
            const subjectsJson = res?.subjects_json || {};

            for (const ref of allRefsToProcess) {
                // Mocks
                const createdItem = { ...ref, id: `auto-${Date.now()}` };
                createdItems.push(createdItem);
                countsByType[ref.type] = Number(countsByType[ref.type] || 0) + 1;
                // Add to report
                for (const sr of sceneReports) {
                    if (sr.missing.some(m => m.name === ref.name && m.type === ref.type)) {
                        sr.created.push(createdItem);
                    }
                }
            }
            if (addedCount.characters || addedCount.props || addedCount.environments) {
                 onLog?.(`LLM entity batch supplement finished successfully. Generated and inserted to DB.`, 'success');
            } else {
                 onLog?.(`LLM entity batch supplement finished, but no items inserted or returned.`, 'warning');
            }
        } catch (error) {
            const errStr = String(error?.response?.data?.detail || error?.message || error || 'LLM supplement failed');
            onLog?.(`Scene LLM batch supplement failed: ${errStr}`, 'error');
            
            for (const ref of allRefsToProcess) {
                const failedItem = { ...ref, error: errStr };
                failedItems.push(failedItem);
                for (const sr of sceneReports) {
                    if (sr.missing.some(m => m.name === ref.name && m.type === ref.type)) {
                        sr.failed.push(failedItem);
                    }
                }
            }
        }
    }

    return {
        createdItems,
        skippedItems,
        failedItems,
        sceneReports,
        countsByType,
        entities: knownEntities,
    };
};

export const collectMatchedSubjectImageUrlsFromPrompt = ({
    promptText = '',
    entityPool = [],
}) => {
    return normalizeMediaRefList(
        collectMatchedEntitiesFromPrompt({
            promptText,
            associatedEntities: '',
            entityPool,
            includeAssociatedEntities: false,
        })
            .filter((entity) => {
                const entityType = String(entity?.type || '').trim().toLowerCase();
                return entityType === 'subject' || entityType === 'character' || entityType === 'char';
            })
            .map((entity) => entity?.image_url)
    );
};

export const resolveUnifiedVideoMode = (techObj = {}) => {
    const rawMode = String(techObj?.video_mode_unified || techObj?.video_ref_submit_mode || techObj?.video_gen_mode || 'entity_refs').trim().toLowerCase();
    if (rawMode === 'refs_video' || rawMode === 'entity_refs') return 'entity_refs';
    if (rawMode === 'entity_refs_start_end') return 'entity_refs_start_end';
    if (rawMode === 'keyframes_entity_refs' || rawMode === 'keyframe_entity_refs') return 'keyframes_entity_refs';
    return rawMode || 'entity_refs';
};

export const buildAutoVideoRefList = (shotLike = {}, techObj = {}, explicitMode = null, entityRefUrls = []) => {
    const mode = String(explicitMode || resolveUnifiedVideoMode(techObj) || 'entity_refs').trim().toLowerCase();
    const refs = [];
    const startRef = String(shotLike?.image_url || '').trim();
    const endRef = String(techObj?.end_frame_url || '').trim();
    const keyframes = normalizeMediaRefList(techObj?.keyframes || []);

    // In reference-image mode, only keep subject references from prompt matches.
    if (mode === 'entity_refs') {
        return normalizeMediaRefList(entityRefUrls);
    }

    if (mode === 'entity_refs_start_end') {
        const combined = [...(entityRefUrls || [])];
        if (startRef && !combined.includes(startRef)) combined.push(startRef);
        if (endRef && !combined.includes(endRef)) combined.push(endRef);
        return normalizeMediaRefList(combined);
    }

    if (mode === 'keyframes_entity_refs') {
        const combined = [...keyframes, ...(entityRefUrls || [])];
        if (combined.length === 0 && startRef) combined.push(startRef);
        return normalizeMediaRefList(combined);
    }

    if (mode === 'end') {
        if (endRef) refs.push(endRef);
        return normalizeMediaRefList(refs);
    }

    if (startRef) refs.push(startRef);

    if (mode === 'start_end' && endRef) {
        refs.push(endRef);
    }

    return normalizeMediaRefList(refs);
};

export const resolveShotVideoPosterUrl = (shotLike = {}) => {
    let techObj = {};
    try {
        techObj = JSON.parse(shotLike?.technical_notes || '{}');
    } catch {
        techObj = {};
    }

    return [
        techObj?.video_poster_url,
        techObj?.video_preview_url,
        techObj?.video_thumbnail_url,
        techObj?.poster_url,
        techObj?.thumbnail_url,
        techObj?.preview_image_url,
        techObj?.cover_url,
    ].map((value) => String(value || '').trim()).find(Boolean) || '';
};

export const LazyHoverVideo = ({
    src,
    poster = '',
    className = '',
    mediaClassName = 'w-full h-full object-cover',
    playOnHover = false,
    resetOnLeave = false,
    preload = 'auto',
    ...videoProps
}) => {
    const containerRef = useRef(null);
    const videoRef = useRef(null);
    const [shouldLoad, setShouldLoad] = useState(() => isWarmMediaUrl(src));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));
    const [isVideoLoaded, setIsVideoLoaded] = useState(() => isWarmMediaUrl(src));
    const [videoUseProxy, setVideoUseProxy] = useState(false);

    useEffect(() => {
        setVideoFailed(!src || isBrokenMediaUrl(src));
        setVideoUseProxy(false);
        if (isWarmMediaUrl(src)) {
            setShouldLoad(true);
            setIsVideoLoaded(true);
        }
    }, [src]);

    useEffect(() => {
        setPosterFailed(!poster || isBrokenMediaUrl(poster));
    }, [poster]);

    useEffect(() => {
        const node = containerRef.current;
        if (!node || shouldLoad || !src || videoFailed) return undefined;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setShouldLoad(true);
                    }
                });
            },
            {
                rootMargin: '240px 0px',
                threshold: 0.01,
            }
        );

        observer.observe(node);
        return () => observer.disconnect();
    }, [shouldLoad, src, videoFailed]);

    const handleMouseEnter = async () => {
        if (!playOnHover) return;
        if (!shouldLoad) {
            setShouldLoad(true);
            return;
        }
        const video = videoRef.current;
        if (!video) return;
        try {
            await video.play();
        } catch {
            // Ignore autoplay blocking for hover previews.
        }
    };

    const handleMouseLeave = () => {
        if (!playOnHover) return;
        const video = videoRef.current;
        if (!video) return;
        video.pause();
        if (resetOnLeave) {
            video.currentTime = 0;
        }
    };

    return (
        <div
            ref={containerRef}
            className={`relative flex items-center justify-center overflow-hidden bg-[#151515] ${className ? className.replace('relative', '') : ''}`}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            {!isVideoLoaded && !videoFailed && !poster && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
                    <Loader2 className="w-5 h-5 animate-spin text-white/20" />
                </div>
            )}
            
            {!posterFailed && poster && (
                <div className={`absolute inset-0 z-0 transition-opacity duration-700 ${isVideoLoaded ? 'opacity-0 delay-300' : 'opacity-100'}`}>
                    <SafeImage src={poster} className="absolute inset-0 w-full h-full object-cover" />
                </div>
            )}

            <video
                ref={videoRef}
                src={shouldLoad && !videoFailed ? getMediaUrlWithFallback(src, videoUseProxy) : undefined}
                preload={shouldLoad ? preload : 'none'}
                className={`z-10 relative transition-all duration-700 ${mediaClassName} ${isVideoLoaded ? 'opacity-100 blur-0 scale-100 bg-transparent' : 'opacity-0 blur-[10px] scale-105 bg-[#151515]'}`}
                onLoadedData={() => {
                    setIsVideoLoaded(true);
                    rememberWarmMediaUrl(src);
                    if (poster) rememberWarmMediaUrl(poster);
                }}
                onError={() => {
                    if (!videoUseProxy && canFallbackToAssetProxy(src)) {
                        setVideoUseProxy(true);
                        return;
                    }
                    if (src) rememberBrokenMediaUrl(src);
                    setVideoFailed(true);
                    if (poster) {
                        rememberBrokenMediaUrl(poster);
                        setPosterFailed(true);
                    }
                }}
                {...videoProps}
            />
        </div>
    );
};

export const InViewVideo = ({
    src,
    poster = '',
    className = '',
    preload = 'metadata',
    rootMargin = '360px 0px',
    visibleDelayMs = 120,
    fallback = null,
    ...videoProps
}) => {
    const containerRef = useRef(null);
    const visibleTimerRef = useRef(null);
    const [isInView, setIsInView] = useState(false);
    const [shouldLoad, setShouldLoad] = useState(() => isWarmMediaUrl(src));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));
    const [videoUseProxy, setVideoUseProxy] = useState(false);
    const [posterUseProxy, setPosterUseProxy] = useState(false);

    useEffect(() => {
        setVideoFailed(!src || isBrokenMediaUrl(src));
        setVideoUseProxy(false);
        if (isWarmMediaUrl(src)) {
            setShouldLoad(true);
        }
    }, [src]);

    useEffect(() => {
        setPosterFailed(!poster || isBrokenMediaUrl(poster));
        setPosterUseProxy(false);
    }, [poster]);

    useEffect(() => {
        const node = containerRef.current;
        if (!node || !src || videoFailed) return undefined;

        if (typeof IntersectionObserver === 'undefined') {
            setIsInView(true);
            return undefined;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setIsInView(true);
                    }
                });
            },
            {
                rootMargin,
                threshold: 0.01,
            }
        );

        observer.observe(node);
        return () => observer.disconnect();
    }, [rootMargin, src, videoFailed]);

    useEffect(() => {
        if (shouldLoad || !isInView || !src || videoFailed) return undefined;
        const delay = Math.max(0, Number(visibleDelayMs) || 0);
        visibleTimerRef.current = setTimeout(() => {
            setShouldLoad(true);
        }, delay);
        return () => {
            if (visibleTimerRef.current) {
                clearTimeout(visibleTimerRef.current);
                visibleTimerRef.current = null;
            }
        };
    }, [isInView, shouldLoad, src, videoFailed, visibleDelayMs]);

    useEffect(() => {
        return () => {
            if (visibleTimerRef.current) {
                clearTimeout(visibleTimerRef.current);
                visibleTimerRef.current = null;
            }
        };
    }, []);

    if (!src || videoFailed) {
        return fallback || null;
    }

    return (
        <div ref={containerRef} className="contents">
            <video
                src={shouldLoad ? getMediaUrlWithFallback(src, videoUseProxy) : undefined}
                poster={!posterFailed && poster ? getMediaUrlWithFallback(poster, posterUseProxy) : undefined}
                className={className}
                preload={shouldLoad ? preload : 'none'}
                onLoadedData={() => {
                    rememberWarmMediaUrl(src);
                    if (poster) rememberWarmMediaUrl(poster);
                }}
                onError={() => {
                    if (!videoUseProxy && canFallbackToAssetProxy(src)) {
                        setVideoUseProxy(true);
                        return;
                    }
                    if (poster && !posterUseProxy && canFallbackToAssetProxy(poster)) {
                        setPosterUseProxy(true);
                        return;
                    }
                    rememberBrokenMediaUrl(src);
                    setVideoFailed(true);
                    if (poster) {
                        rememberBrokenMediaUrl(poster);
                        setPosterFailed(true);
                    }
                }}
                {...videoProps}
            />
        </div>
    );
};

export const ManagedVideoPlayer = ({
    src,
    poster = '',
    className = '',
    wrapperClassName = '',
    controls = true,
    autoPlay = false,
    muted = false,
    loop = false,
    playsInline = true,
    preload = 'metadata',
    suspend = false,
    uiLang = 'zh',
    onClick,
    hideBusyOverlay = false,
}) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [loadState, setLoadState] = useState(() => (src && !suspend ? 'loading' : 'idle'));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));
    const [videoUseProxy, setVideoUseProxy] = useState(false);
    const [posterUseProxy, setPosterUseProxy] = useState(false);

    useEffect(() => {
        setVideoFailed(!src || isBrokenMediaUrl(src));
        setVideoUseProxy(false);
    }, [src]);

    useEffect(() => {
        setPosterFailed(!poster || isBrokenMediaUrl(poster));
        setPosterUseProxy(false);
    }, [poster]);

    useEffect(() => {
        if (!src || suspend || videoFailed) {
            setLoadState('idle');
            return;
        }
        setLoadState('loading');
    }, [src, suspend, videoFailed]);

    const isBusy = loadState === 'loading' || loadState === 'buffering';
    const busyText = loadState === 'buffering'
        ? t('视频缓冲中...', 'Buffering video...')
        : t('视频下载中...', 'Downloading video...');
    const centeredWrapperClassName = `relative flex items-center justify-center overflow-hidden ${wrapperClassName}`.trim();
    const centeredMediaClassName = `block ${className}`.trim();

    if (!src || videoFailed) {
        return (
            <div className={centeredWrapperClassName} onClick={onClick}>
                <div className={`absolute inset-0 flex items-center justify-center opacity-20 ${centeredMediaClassName}`.trim()}>
                    <Video className="w-8 h-8" />
                </div>
            </div>
        );
    }

    return (
        <div className={centeredWrapperClassName} onClick={onClick}>
            {!suspend ? (
                <video
                    key={src}
                    src={getMediaUrlWithFallback(src, videoUseProxy)}
                    poster={!posterFailed && poster ? getMediaUrlWithFallback(poster, posterUseProxy) : undefined}
                    className={centeredMediaClassName}
                    controls={controls}
                    autoPlay={autoPlay}
                    muted={muted}
                    loop={loop}
                    playsInline={playsInline}
                    preload={preload}
                    onLoadStart={() => setLoadState('loading')}
                    onLoadedData={() => setLoadState('ready')}
                    onCanPlay={() => setLoadState('ready')}
                    onPlaying={() => setLoadState('ready')}
                    onWaiting={() => setLoadState('buffering')}
                    onStalled={() => setLoadState('buffering')}
                    onSeeking={() => setLoadState('buffering')}
                    onSeeked={() => setLoadState('ready')}
                    onSuspend={() => setLoadState((prev) => (prev === 'loading' ? 'ready' : prev))}
                    onError={() => {
                        if (!videoUseProxy && canFallbackToAssetProxy(src)) {
                            setVideoUseProxy(true);
                            return;
                        }
                        if (poster && !posterUseProxy && canFallbackToAssetProxy(poster)) {
                            setPosterUseProxy(true);
                            return;
                        }
                        rememberBrokenMediaUrl(src);
                        setVideoFailed(true);
                        setLoadState('idle');
                    }}
                />
            ) : poster && !posterFailed ? (
                <SafeImage
                    src={poster}
                    className={centeredMediaClassName}
                    alt="video-poster"
                    onError={() => {
                        rememberBrokenMediaUrl(poster);
                        setPosterFailed(true);
                    }}
                />
            ) : (
                <div className={`absolute inset-0 flex items-center justify-center opacity-20 ${centeredMediaClassName}`.trim()}>
                    <Video className="w-8 h-8" />
                </div>
            )}

            {isBusy && !suspend && !hideBusyOverlay && (
                <div className="absolute inset-0 z-10 bg-black/55 flex items-center justify-center flex-col gap-2 pointer-events-none">
                    <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    <span className="text-xs text-white/80">{busyText}</span>
                </div>
            )}
        </div>
    );
};

export const parseEpisodeNumberFromText = (value) => {
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

export const normalizeEpisodeTitleForDisplay = (rawTitle) => {
    const text = String(rawTitle || '').trim();
    if (!text) return '';

    return text
        .replace(/^episode\s*\d+\s*(?:-|:|：)?\s*/i, '')
        .replace(/^ep\s*\d+\s*(?:-|:|：)?\s*/i, '')
        .replace(/^第\s*\d+\s*集\s*(?:-|:|：)?\s*/i, '')
        .replace(/^\d+\s*(?:-|:|：)\s*/, '')
        .trim();
};

export function buildEntityNegativePrompt(sourceText = '', primaryEntity = null, entityPool = []) {
    const pool = Array.isArray(entityPool) ? entityPool : [];
    const negatives = [];

    const pushNegative = (value) => {
        const text = String(value || '').trim();
        if (!text) return;
        if (!negatives.includes(text)) negatives.push(text);
    };

    if (primaryEntity?.negative_prompt_en) {
        pushNegative(primaryEntity.negative_prompt_en);
    }

    const resolveEntity = (tokenValue) => {
        const raw = String(tokenValue || '').trim();
        const norm = normalizeEntityToken(raw);
        if (!norm) return null;

        return pool.find((item) => {
            if (!item) return false;
            if (String(item?.id || '').trim() === raw) return true;
            if (normalizeEntityToken(item?.name || '') === norm) return true;
            if (normalizeEntityToken(item?.name_en || '') === norm) return true;
            return false;
        }) || null;
    };

    const tokenMatches = String(sourceText || '').match(/[\[【](.*?)[\]】]/g) || [];
    tokenMatches.forEach((wrapped) => {
        const inner = String(wrapped || '').replace(/^[\[【]\s*/, '').replace(/[\]】]\s*$/, '');
        const entity = resolveEntity(inner);
        if (entity?.negative_prompt_en) {
            pushNegative(entity.negative_prompt_en);
        }
    });

    return negatives.join(', ');
}

export function normalizeImageSizeOption(value) {
    const raw = String(value || '').trim().toUpperCase().replace(/\s+/g, '');
    if (!raw) return '';
    if (raw === '0.5K' || raw === '1K' || raw === '2K' || raw === '4K') return raw;
    return '';
}

export function normalizeAspectRatioOption(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (['16:9', '9:16', '4:3', '2.35:1', '1:1'].includes(raw)) return raw;
    return '';
}

export function parseAspectRatioParts(value) {
    const raw = String(value || '').trim();
    if (!raw) return null;
    const matched = raw.match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
    if (!matched) return null;
    const widthPart = Number(matched[1]);
    const heightPart = Number(matched[2]);
    if (!Number.isFinite(widthPart) || !Number.isFinite(heightPart) || widthPart <= 0 || heightPart <= 0) {
        return null;
    }
    return { widthPart, heightPart };
}

export function parseAspectRatioValue(value) {
    const parts = parseAspectRatioParts(value);
    if (!parts) return null;
    return parts.widthPart / parts.heightPart;
}

export function reduceAspectRatioParts(widthPart, heightPart) {
    const widthNum = Number(widthPart);
    const heightNum = Number(heightPart);
    if (!Number.isFinite(widthNum) || !Number.isFinite(heightNum) || widthNum <= 0 || heightNum <= 0) {
        return null;
    }

    const scale = 1000;
    let scaledWidth = Math.round(widthNum * scale);
    let scaledHeight = Math.round(heightNum * scale);

    const gcd = (a, b) => {
        let x = Math.abs(Math.round(a));
        let y = Math.abs(Math.round(b));
        while (y) {
            const temp = y;
            y = x % y;
            x = temp;
        }
        return x || 1;
    };

    const divisor = gcd(scaledWidth, scaledHeight);
    scaledWidth = Math.max(1, Math.round(scaledWidth / divisor));
    scaledHeight = Math.max(1, Math.round(scaledHeight / divisor));
    return { widthPart: scaledWidth, heightPart: scaledHeight };
}

export function buildAspectRatioString(widthPart, heightPart) {
    const reduced = reduceAspectRatioParts(widthPart, heightPart);
    if (!reduced) return '';
    return `${reduced.widthPart}:${reduced.heightPart}`;
}

export function inferImageSizeFromResolution(width, height) {
    const w = Number(width);
    const h = Number(height);
    if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return '';
    const maxSide = Math.max(w, h);
    if (maxSide >= 3200) return '4K';
    if (maxSide >= 1900) return '2K';
    if (maxSide >= 900) return '1K';
    return '0.5K';
}

export function getEpisodePreferredImageSize(episodeInfoLike) {
    const root = (episodeInfoLike && typeof episodeInfoLike === 'object' && episodeInfoLike.e_global_info)
        ? episodeInfoLike.e_global_info
        : (episodeInfoLike || {});
    const visual = root?.tech_params?.visual_standard || {};

    const explicit = normalizeImageSizeOption(
        visual?.image_size || visual?.imageSize || root?.image_size || root?.imageSize
    );
    if (explicit) return explicit;

    const width = visual?.horizontal_resolution || visual?.h_resolution || visual?.width;
    const height = visual?.vertical_resolution || visual?.v_resolution || visual?.height;
    return inferImageSizeFromResolution(width, height);
}

export function getEpisodePreferredAspectRatio(episodeInfoLike) {
    const root = (episodeInfoLike && typeof episodeInfoLike === 'object' && episodeInfoLike.e_global_info)
        ? episodeInfoLike.e_global_info
        : (episodeInfoLike || {});
    const visual = root?.tech_params?.visual_standard || {};

    return normalizeAspectRatioOption(
        visual?.aspect_ratio || visual?.aspectRatio || root?.aspect_ratio || root?.aspectRatio
    );
}

export function getProjectPreferredImageSize(projectInfoLike, episodeInfoLike) {
    return getEpisodePreferredImageSize(projectInfoLike)
        || getEpisodePreferredImageSize(episodeInfoLike);
}

export function getProjectPreferredAspectRatio(projectInfoLike, episodeInfoLike) {
    return getEpisodePreferredAspectRatio(projectInfoLike)
        || getEpisodePreferredAspectRatio(episodeInfoLike);
}

export function buildShotDiptychPlan(aspectRatio) {
    const parts = parseAspectRatioParts(aspectRatio || '16:9') || { widthPart: 16, heightPart: 9 };
    const ratioValue = parts.widthPart / parts.heightPart;

    // Keep the two-panel canvas close to square after a single split:
    // wide targets stack top-bottom, tall targets sit left-right.
    const layout = ratioValue >= 1 ? 'vertical' : 'horizontal';
    
    // Instead scale the exact ratio component and build precisely.
    // If the premise of padding is forcing a 1:1 API generation parameter, then exact combined 
    // aspect ratio that drives the request must be 1:1.
    const exactCombinedAspectRatio = '1:1';

    return {
        layout,
        targetAspectRatio: buildAspectRatioString(parts.widthPart, parts.heightPart) || '16:9',
        exactCombinedAspectRatio: exactCombinedAspectRatio,
        ratioValue,
    };
}

export function getShotDiptychLayoutLabel(layout, language = 'en') {
    if (language === 'cn') {
        return layout === 'horizontal' ? '左右并排' : '上下并排';
    }
    return layout === 'horizontal' ? 'left-to-right' : 'top-to-bottom';
}

export function buildShotDiptychLayoutInstruction(diptychPlan, language = 'en') {
    const layoutLabel = getShotDiptychLayoutLabel(diptychPlan?.layout, language);
    const paddingLabel = diptychPlan?.layout === 'horizontal' ? '边缘(上下)' : '边缘(左右)';
    const paddingLabelEn = diptychPlan?.layout === 'horizontal' ? 'minimal top/bottom edges' : 'minimal left/right edges';

    if (language === 'cn') {
        return `两宫格必须采用${layoutLabel}排布。请尽量让画面主体撑满格子，${paddingLabel}仅留出极窄的空白或直接画满，不要留出粗大的白边。`;
    }

    return `The diptych must be arranged ${layoutLabel}. Draw the subjects fully scaled to fit their grid. Keep ${paddingLabelEn} as thin as possible or draw edge-to-edge; do not leave large blank spaces.`;
}

export function buildShotDiptychAspectContract(diptychPlan, language = 'en') {
    const panelAspectRatio = String(diptychPlan?.targetAspectRatio || '16:9').trim();
    const combinedAspectRatio = String(
        diptychPlan?.exactCombinedAspectRatio || '1:1'
    ).trim();

    if (language === 'cn') {
        return `生图时总画幅必须采用 1:1 正方形比例 (${combinedAspectRatio})，生图后将平分为两格，每一格截取为 ${panelAspectRatio}。重要要求：必须极其饱满地作画，画面需要贴边！两格必须严格满铺相等的空间 (50/50平分)。`;
    }

    return `The raw generated canvas must be exactly ${combinedAspectRatio} (1:1 square), which will be equally split into two ${panelAspectRatio} panels. IMPORTANT: Paint fully edge-to-edge. Do not leave heavy white boxes around the art. Both panels must be equal-size with a 50/50 split.`;
}

export function getShotDiptychSeamTrimPx(layout, sourceWidth, sourceHeight) {
    const seamSourceSpan = layout === 'horizontal' ? sourceWidth : sourceHeight;
    if (!Number.isFinite(seamSourceSpan) || seamSourceSpan <= 0) return 2;
    return Math.max(2, Math.min(12, Math.round(seamSourceSpan / 208)));
}

export function getShotDiptychSeamBiasPx(layout, sourceWidth, sourceHeight) {
    const seamSourceSpan = layout === 'horizontal' ? sourceWidth : sourceHeight;
    if (!Number.isFinite(seamSourceSpan) || seamSourceSpan <= 0) return 1;
    return Math.max(1, Math.min(10, Math.round(seamSourceSpan / 320)));
}

export function getShotDiptychFallbackCropPx(layout, sourceWidth, sourceHeight, targetAspectRatio, frameRole = 'start') {
    const seamSourceSpan = layout === 'horizontal' ? sourceWidth : sourceHeight;
    if (!Number.isFinite(seamSourceSpan) || seamSourceSpan <= 0) {
        return { seamExtraPx: 1, outerTrimPx: 0 };
    }

    const ratioValue = parseAspectRatioValue(targetAspectRatio) || 1;
    const isExtremeAspect = ratioValue >= 1.7 || ratioValue <= 0.58;
    const isStrongAspect = ratioValue >= 1.3 || ratioValue <= 0.78;
    const frameBoost = frameRole === 'end' ? 1 : 0;

    const seamDivisor = isExtremeAspect ? 320 : (isStrongAspect ? 360 : 420);
    const outerDivisor = isExtremeAspect ? 900 : 1100;

    return {
        seamExtraPx: Math.max(1, Math.min(8, Math.round(seamSourceSpan / seamDivisor) + frameBoost)),
        outerTrimPx: Math.max(0, Math.min(4, Math.round(seamSourceSpan / outerDivisor))),
    };
}

export const JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION = '20260324a';
export const SHOT_FRAME_ASSET_UPLOAD_VERSION = '20260325a';

export function hashStableText(value) {
    const raw = String(value || '');
    let hash = 0;
    for (let index = 0; index < raw.length; index += 1) {
        hash = ((hash * 31) + raw.charCodeAt(index)) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
}

export function buildJointShotDiptychUploadIdempotencyKey({
    shotId,
    frameRole,
    compositeUrl,
    layout,
    targetAspectRatio,
    exportSize,
}) {
    const compositeToken = String(compositeUrl || '').trim().split('?')[0].split('#')[0];
    const signature = [
        JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION,
        String(shotId || '').trim(),
        String(frameRole || '').trim(),
        compositeToken,
        String(layout || '').trim(),
        String(targetAspectRatio || '').trim(),
        Number(exportSize?.width || 0),
        Number(exportSize?.height || 0),
    ].join('|');
    return `joint-diptych:${hashStableText(signature)}`;
}

export function buildShotFrameAssetUploadIdempotencyKey({
    operation,
    shotId,
    frameRole,
    sourceUrl,
    margins,
}) {
    const sourceToken = String(sourceUrl || '').trim().split('?')[0].split('#')[0];
    const normalizedMargins = margins && typeof margins === 'object'
        ? [
            Number(margins.topPct || 0).toFixed(3),
            Number(margins.rightPct || 0).toFixed(3),
            Number(margins.bottomPct || 0).toFixed(3),
            Number(margins.leftPct || 0).toFixed(3),
        ].join('|')
        : '';
    const signature = [
        SHOT_FRAME_ASSET_UPLOAD_VERSION,
        String(operation || '').trim(),
        String(shotId || '').trim(),
        String(frameRole || '').trim(),
        sourceToken,
        normalizedMargins,
    ].join('|');
    return `shot-frame:${hashStableText(signature)}`;
}

export function collectSupportedAspectRatioOptions(values) {
    const out = [];
    const seen = new Set();
    (Array.isArray(values) ? values : []).forEach((value) => {
        const normalized = normalizeAspectRatioOption(value);
        if (!normalized) return;
        if (seen.has(normalized)) return;
        seen.add(normalized);
        out.push(normalized);
    });
    return out;
}

export function collectSupportedImageSizeOptions(values) {
    const out = [];
    const seen = new Set();
    (Array.isArray(values) ? values : []).forEach((value) => {
        const normalized = normalizeImageSizeOption(value);
        if (!normalized) return;
        if (seen.has(normalized)) return;
        seen.add(normalized);
        out.push(normalized);
    });
    return out;
}

export function selectBestShotDiptychRequestAspectRatio({ diptychPlan, allowedAspectRatios }) {
    const fallback = normalizeAspectRatioOption(diptychPlan?.exactCombinedAspectRatio)
        || (diptychPlan?.layout === 'horizontal' ? '16:9' : '9:16');
    const supported = collectSupportedAspectRatioOptions(allowedAspectRatios);
    if (supported.length === 0) return fallback;

    const targetRatio = parseAspectRatioValue(diptychPlan?.targetAspectRatio);
    const preferHorizontalSplit = diptychPlan?.layout === 'horizontal';
    const exactRatio = parseAspectRatioValue(diptychPlan?.exactCombinedAspectRatio)
        || (preferHorizontalSplit ? (16 / 9) : (9 / 16));

    const orientationMatched = supported.filter((value) => {
        const ratio = parseAspectRatioValue(value);
        if (ratio == null) return false;
        return preferHorizontalSplit ? ratio >= 1 : ratio <= 1;
    });
    const candidatePool = orientationMatched.length > 0 ? orientationMatched : supported;

    const scoreAspect = (value) => {
        const overallRatio = parseAspectRatioValue(value);
        if (overallRatio == null) return Number.POSITIVE_INFINITY;
        const derivedPanelRatio = preferHorizontalSplit
            ? (overallRatio / 2)
            : (overallRatio * 2);
        
        // Exact 1:1 score bypass, otherwise panel closeness starts driving the score wild
        if (value === '1:1' && targetRatio != null && Math.abs(targetRatio - 1) > 0.1) {
            // When combined canvas is 1:1, derived Panel Ratio is 2:1 or 1:2
            // This is horrible if the user actually wanted 16:9 or 9:16 target...
            // UNLESS the previous code explicitly allowed 1:1 to be the EXACT combined aspect ratio
            // so we shouldn't artificially suppress it here if we want full canvas fallback.
        }

        const panelCloseness = targetRatio != null
            ? Math.abs(derivedPanelRatio - targetRatio)
            : Number.POSITIVE_INFINITY;
        const combinedCloseness = exactRatio != null
            ? Math.abs(overallRatio - exactRatio)
            : Number.POSITIVE_INFINITY;
        // Heavy penalty for wrong orientation
        const orientationPenalty = preferHorizontalSplit
            ? (overallRatio < 1 ? 1000 : 0)
            : (overallRatio > 1 ? 1000 : 0);

        // Make panel closeness the primary driver of selection, combined closeness secondary
        // The goal is to get a generated panel that correctly fits the target shot cropping layout
        return orientationPenalty + (panelCloseness * 100) + (combinedCloseness * 10);
    };

    return [...candidatePool].sort((left, right) => scoreAspect(left) - scoreAspect(right))[0] || fallback;
}

export function selectBestSupportedImageSize(preferredImageSize, allowedImageSizes) {
    const fallback = normalizeImageSizeOption(preferredImageSize) || '1K';
    const supported = collectSupportedImageSizeOptions(allowedImageSizes);
    if (supported.length === 0) return fallback;

    const rankedSizes = ['0.5K', '1K', '2K', '4K'];
    const fallbackRank = rankedSizes.indexOf(fallback);
    if (fallbackRank < 0) return supported[0] || fallback;

    return [...supported].sort((left, right) => {
        const leftRank = rankedSizes.indexOf(left);
        const rightRank = rankedSizes.indexOf(right);
        const leftDistance = leftRank < 0 ? Number.POSITIVE_INFINITY : Math.abs(leftRank - fallbackRank);
        const rightDistance = rightRank < 0 ? Number.POSITIVE_INFINITY : Math.abs(rightRank - fallbackRank);
        if (leftDistance !== rightDistance) return leftDistance - rightDistance;
        return rightRank - leftRank;
    })[0] || fallback;
}

export function resolveShotPanelExportResolution(aspectRatio, imageSize) {
    const preset = getResolutionByAspectAndImageSize(aspectRatio, imageSize);
    if (!preset) return null;
    const width = Number(preset.width);
    const height = Number(preset.height);
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
    return { width, height };
}

export function resolveShotDiptychRequestResolution(diptychPlan, panelExportSize) {
    const panelWidth = Number(panelExportSize?.width);
    const panelHeight = Number(panelExportSize?.height);
    if (!Number.isFinite(panelWidth) || !Number.isFinite(panelHeight) || panelWidth <= 0 || panelHeight <= 0) {
        return null;
    }

    if (diptychPlan?.layout === 'horizontal') {
        const layoutSize = Math.max(panelWidth * 2, panelHeight);
        return { width: layoutSize, height: layoutSize };
    }

    const layoutSize = Math.max(panelWidth, panelHeight * 2);
    return { width: layoutSize, height: layoutSize };
}

export function getResolutionByAspectAndImageSize(aspectRatio, imageSize) {
    const ratio = String(aspectRatio || '').trim();
    const size = normalizeImageSizeOption(imageSize) || '2K';
    const key = `${ratio}|${size}`;
    const presets = {
        '16:9|0.5K': { width: '960', height: '540' },
        '16:9|1K': { width: '1920', height: '1080' },
        '16:9|2K': { width: '2560', height: '1440' },
        '16:9|4K': { width: '3840', height: '2160' },
        '9:16|0.5K': { width: '540', height: '960' },
        '9:16|1K': { width: '1080', height: '1920' },
        '9:16|2K': { width: '1440', height: '2560' },
        '9:16|4K': { width: '2160', height: '3840' },
        '4:3|0.5K': { width: '960', height: '720' },
        '4:3|1K': { width: '1440', height: '1080' },
        '4:3|2K': { width: '2048', height: '1536' },
        '4:3|4K': { width: '2880', height: '2160' },
        '2.35:1|0.5K': { width: '960', height: '409' },
        '2.35:1|1K': { width: '1920', height: '817' },
        '2.35:1|2K': { width: '2560', height: '1089' },
        '2.35:1|4K': { width: '3840', height: '1634' },
        '1:1|0.5K': { width: '720', height: '720' },
        '1:1|1K': { width: '1080', height: '1080' },
        '1:1|2K': { width: '2048', height: '2048' },
        '1:1|4K': { width: '4096', height: '4096' },
    };
    return presets[key] || null;
}

export const SHOT_IMAGE_CFG_MIN = 1;
export const SHOT_IMAGE_CFG_MAX = 15;
export const SHOT_IMAGE_CFG_STEP = 0.5;
export const SHOT_IMAGE_CFG_FALLBACK = 7;

export function clampShotImageCfg(value, fallback = SHOT_IMAGE_CFG_FALLBACK) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return fallback;
    const clamped = Math.min(SHOT_IMAGE_CFG_MAX, Math.max(SHOT_IMAGE_CFG_MIN, numeric));
    return Math.round(clamped / SHOT_IMAGE_CFG_STEP) * SHOT_IMAGE_CFG_STEP;
}

export function resolveShotImageCfgDefault(preferences) {
    const numeric = Number(preferences?.advanced_model?.cfg);
    if (!Number.isFinite(numeric) || numeric <= 0) {
        return SHOT_IMAGE_CFG_FALLBACK;
    }
    return clampShotImageCfg(numeric);
}

export function extractDialogueOnlyFromPrompt(value) {
    const raw = String(value || '').replace(/\r\n/g, '\n').trim();
    if (!raw) return '';

    const picked = [];
    const seen = new Set();
    const actionNarrativeHints = [
        /向后|向前|转身|冲向|走向|跑向|扑向|跌倒|摔倒|倒地|抓起|扔|推开|拉住|退回|冲进|冲出|掏出|举起|放下|拿起/i,
        /camera|镜头|画面|特写|远景|中景|俯拍|仰拍|切到|切换|运镜/i,
        /背景|场景|环境|光线|氛围|动作|表情|神态/i,
    ];

    const isLikelySpokenLine = (text) => {
        const stable = String(text || '').replace(/\s+/g, ' ').trim();
        if (!stable) return false;
        if (/^[\[(（【].*[\])）】]$/.test(stable)) return false;
        if (stable.length < 2) return false;

        // Quoted segments are strong speech signals.
        if (/["“”'‘’「」『』]/.test(stable)) return true;

        // Filter obvious narrative/action description lines.
        if (actionNarrativeHints.some((pattern) => pattern.test(stable))) {
            // Allow if line still looks like direct speech sentence.
            if (!/[!?！？]$/.test(stable) && !/我|你|他|她|它|我们|你们|他们|她们/.test(stable)) {
                return false;
            }
        }

        // Spoken text commonly ends with sentence punctuation.
        if (/[。.!?！？]$/.test(stable)) return true;

        // Imperative/interjection style short lines.
        if (stable.length <= 40 && /快|别|不要|住手|滚|闭嘴|听着|救命|该死|停下/.test(stable)) return true;

        return false;
    };

    const pushSegment = (segment) => {
        const text = String(segment || '').replace(/\s+/g, ' ').trim();
        if (!text) return;
        if (!isLikelySpokenLine(text)) return;
        const key = text.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        picked.push(text);
    };

    const quotePatterns = [
        /"([^"\n]{1,400})"/g,
        /“([^”\n]{1,400})”/g,
        /‘([^’\n]{1,400})’/g,
        /「([^」\n]{1,400})」/g,
        /『([^』\n]{1,400})』/g,
    ];
    quotePatterns.forEach((pattern) => {
        let match;
        while ((match = pattern.exec(raw)) !== null) {
            pushSegment(match[1]);
        }
    });

    const lines = raw.split('\n').map((line) => String(line || '').trim()).filter(Boolean);
    lines.forEach((line) => {
        const tagged = line.match(/(?:^|\s)(?:dialogue|line|lines|对白|台词)\s*[:：]\s*(.+)$/i);
        if (tagged && tagged[1]) {
            pushSegment(tagged[1]);
            return;
        }

        const speakerLine = line.match(/^[^:：\n]{1,30}[:：]\s*(.+)$/);
        if (speakerLine && speakerLine[1]) {
            pushSegment(speakerLine[1]);
        }
    });

    return picked.join('\n');
}

export function inferLanguageCodeFromProjectLanguage(value, uiLang = 'en') {
    const raw = String(value || '').trim().toLowerCase();
    if (!raw) {
        return String(uiLang || '').toLowerCase().startsWith('zh') ? 'zh' : 'en';
    }
    if (/中文|汉语|汉语普通话|mandarin|chinese|\bzh\b/.test(raw)) return 'zh';
    if (/english|英文|英语|\ben\b/.test(raw)) return 'en';
    if (/japanese|日语|日本语|\bja\b/.test(raw)) return 'ja';
    if (/korean|韩语|한국어|\bko\b/.test(raw)) return 'ko';
    if (/spanish|espa[ñn]ol|西班牙语|\bes\b/.test(raw)) return 'es';
    if (/french|fran[çc]ais|法语|\bfr\b/.test(raw)) return 'fr';
    if (/german|deutsch|德语|\bde\b/.test(raw)) return 'de';
    if (/italian|italiano|意大利语|\bit\b/.test(raw)) return 'it';
    if (/portuguese|portugu[eê]s|葡萄牙语|\bpt\b/.test(raw)) return 'pt';
    if (/russian|русский|俄语|\bru\b/.test(raw)) return 'ru';
    if (/arabic|العربية|阿拉伯语|\bar\b/.test(raw)) return 'ar';
    if (/hindi|हिन्दी|印地语|\bhi\b/.test(raw)) return 'hi';
    return String(uiLang || '').toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

export function buildVoicePromptWithEntityContext(videoPrompt, entityList = [], projectLanguage = '', uiLang = 'en') {
    const dialogueOnly = extractDialogueOnlyFromPrompt(videoPrompt);
    if (!dialogueOnly) {
        return {
            dialogueOnly: '',
            voicePrompt: '',
            matchedEntities: [],
            languageCode: inferLanguageCodeFromProjectLanguage(projectLanguage, uiLang),
        };
    }

    const sourceText = String(videoPrompt || '');
    const tokens = new Set();

    const addToken = (value) => {
        const token = normalizeEntityToken(value);
        if (!token) return;
        tokens.add(token);
    };

    [
        /\[([\s\S]+?)\]/g,
        /\{([\s\S]+?)\}/g,
        /【([\s\S]+?)】/g,
        /｛([\s\S]+?)｝/g,
        /(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)/g,
    ].forEach((regex) => {
        regex.lastIndex = 0;
        let matched;
        while ((matched = regex.exec(sourceText)) !== null) {
            addToken(matched?.[1] || '');
        }
    });

    const speakerRegex = /^[^:：\n]{1,30}[:：]\s*/;
    sourceText
        .split(/\r?\n/)
        .map((line) => String(line || '').trim())
        .forEach((line) => {
            const matched = line.match(speakerRegex);
            if (matched) {
                addToken(String(matched[0] || '').replace(/[:：]\s*$/, ''));
            }
        });

    dialogueOnly
        .split(/\r?\n/)
        .map((line) => String(line || '').trim())
        .forEach((line) => {
            const matched = line.match(speakerRegex);
            if (matched) {
                addToken(String(matched[0] || '').replace(/[:：]\s*$/, ''));
            }
        });

    const matchedEntities = [];
    const seenEntityIds = new Set();
    (Array.isArray(entityList) ? entityList : []).forEach((entity) => {
        const id = String(entity?.id || '').trim();
        const explicitMatched = Array.from(tokens).some((token) => entityTokenMatchesName(entity, token));
        const fuzzyMatched = !explicitMatched && entityNameAppearsInText(entity, sourceText);

        if (!explicitMatched && !fuzzyMatched) return;
        if (id && seenEntityIds.has(id)) return;

        if (id) seenEntityIds.add(id);
        matchedEntities.push(entity);
    });

    if (matchedEntities.length === 0) {
        const languageCode = inferLanguageCodeFromProjectLanguage(projectLanguage, uiLang);
        const languageHint = String(projectLanguage || '').trim() || languageCode;
        return {
            dialogueOnly,
            voicePrompt: [
                '[Dialogue Candidate]',
                dialogueOnly,
                '[Project Language]',
                `project_language: ${languageHint}`,
                `language_code_hint: ${languageCode}`,
            ].join('\n'),
            matchedEntities: [],
            languageCode,
        };
    }

    const contextLines = matchedEntities.map((entity, idx) => {
        const displayName = String(entity?.name_en || entity?.name || `Character ${idx + 1}`).trim();
        const promptEn = String(entity?.generation_prompt_en || entity?.generation_prompt_cn || '').trim();
        if (promptEn) {
            return `Character ${idx + 1}: ${displayName} | Prompt EN: ${promptEn}`;
        }
        return `Character ${idx + 1}: ${displayName}`;
    });

    const languageCode = inferLanguageCodeFromProjectLanguage(projectLanguage, uiLang);
    const languageHint = String(projectLanguage || '').trim() || languageCode;

    const voicePrompt = [
        '[Dialogue Candidate]',
        dialogueOnly,
        '[Project Language]',
        `project_language: ${languageHint}`,
        `language_code_hint: ${languageCode}`,
        '[Character Voice Context]',
        ...contextLines,
    ].join('\n');

    return {
        dialogueOnly,
        voicePrompt,
        matchedEntities,
        languageCode,
    };
}

export const buildEpisodeDisplayLabel = ({ episodeNumber, title, fallbackNumber } = {}) => {
    const directNumber = Number(episodeNumber);
    const fallback = Number(fallbackNumber);
    const inferred = parseEpisodeNumberFromText(title);
    const resolvedNumber = Number.isFinite(directNumber) && directNumber > 0
        ? directNumber
        : (Number.isFinite(fallback) && fallback > 0 ? fallback : inferred);

    const normalizedTitle = normalizeEpisodeTitleForDisplay(title);
    if (resolvedNumber) {
        const resolvedTitle = normalizedTitle || `Episode ${resolvedNumber}`;
        return `${resolvedNumber}-${resolvedTitle}`;
    }

    return normalizedTitle || 'Untitled Episode';
};


export const mergeEntityPoolWithSubjectIndex = (entities, subjectText) => { return entities || []; };

const EPHEMERAL_PROVIDER_HOST_PATTERNS = [
    /^file\d*\.aitohumanize\.com$/i,
    /(^|.+\.)aiquickdraw\.com$/i,
    /(^|.+\.)volces\.com$/i,
];

const EPHEMERAL_PROVIDER_QUERY_MARKERS = [
    'x-tos-algorithm',
    'x-tos-signature',
    'x-tos-credential',
    'x-amz-algorithm',
    'x-amz-signature',
    'x-amz-credential',
];

let ossActiveUrlSignaturesCache = null;
let ossActiveUrlSignaturesPromise = null;

const normalizeOssUrlSignatures = (payload) => {
    const data = payload && typeof payload === 'object' ? payload : {};
    return {
        oss_enabled: Boolean(data.oss_enabled),
        pool_count: Number(data.pool_count || 0),
        providers: Array.isArray(data.providers) ? data.providers.map((item) => String(item || '').trim()).filter(Boolean) : [],
        public_base_urls: Array.isArray(data.public_base_urls)
            ? data.public_base_urls.map((item) => String(item || '').trim().replace(/\/+$/, '')).filter(Boolean)
            : [],
        hostnames: Array.isArray(data.hostnames)
            ? data.hostnames.map((item) => String(item || '').trim().toLowerCase()).filter(Boolean)
            : [],
    };
};

export const getOssActiveUrlSignatures = () => ossActiveUrlSignaturesCache;

export const setOssActiveUrlSignatures = (payload) => {
    ossActiveUrlSignaturesCache = normalizeOssUrlSignatures(payload);
    return ossActiveUrlSignaturesCache;
};

export const preloadOssActiveUrlSignatures = async (fetcher) => {
    if (ossActiveUrlSignaturesCache) return ossActiveUrlSignaturesCache;
    if (!ossActiveUrlSignaturesPromise) {
        ossActiveUrlSignaturesPromise = Promise.resolve()
            .then(async () => {
                if (typeof fetcher !== 'function') return setOssActiveUrlSignatures({ oss_enabled: false });
                const payload = await fetcher();
                return setOssActiveUrlSignatures(payload);
            })
            .catch(() => setOssActiveUrlSignatures({ oss_enabled: false }))
            .finally(() => {
                ossActiveUrlSignaturesPromise = null;
            });
    }
    return ossActiveUrlSignaturesPromise;
};

const legacyDurableMediaUrl = (raw) => {
    const lower = String(raw || '').trim().toLowerCase();
    return /qiniu|clouddn\.com|backblaze|\.bkt\.|aistory|woola\.fun|qiniucs\.com/.test(lower);
};

export const urlMatchesConfiguredOss = (url, metadata = null, signatures = null) => {
    const raw = String(url || '').trim();
    if (!raw || isEphemeralProviderMediaUrl(raw)) return false;

    const meta = metadata && typeof metadata === 'object' ? metadata : {};
    const activeSignatures = signatures || ossActiveUrlSignaturesCache;

    if (activeSignatures?.oss_enabled) {
        if (raw.startsWith('/uploads/') || (raw.startsWith('/') && !raw.startsWith('//'))) {
            return false;
        }
    } else if (raw.startsWith('/uploads/') || (raw.startsWith('/') && !raw.startsWith('//'))) {
        return true;
    }

    if (!raw.toLowerCase().startsWith('http://') && !raw.toLowerCase().startsWith('https://')) {
        return false;
    }

    if (activeSignatures?.oss_enabled) {
        let hostname = '';
        try {
            hostname = String(new URL(raw).hostname || '').trim().toLowerCase();
        } catch {
            hostname = '';
        }
        const allowedHosts = new Set(activeSignatures.hostnames || []);
        if (hostname && allowedHosts.has(hostname)) {
            return true;
        }
        for (const base of activeSignatures.public_base_urls || []) {
            const normalizedBase = String(base || '').trim().replace(/\/+$/, '');
            if (normalizedBase && (raw === normalizedBase || raw.startsWith(`${normalizedBase}/`))) {
                return true;
            }
        }
        const ossMeta = meta.oss && typeof meta.oss === 'object' ? meta.oss : null;
        if (ossMeta?.key && (hostname && allowedHosts.has(hostname))) {
            return true;
        }
        if (meta.provider_direct_oss_url || meta.providerDirectOssUrl) {
            const provider = String(meta.provider || '').trim().toLowerCase();
            const configuredProviders = new Set(
                (activeSignatures.providers || []).map((item) => String(item || '').trim().toLowerCase()).filter(Boolean),
            );
            if (provider && configuredProviders.has(provider)) {
                return true;
            }
        }
        return false;
    }

    if (meta.provider_direct_oss_url || meta.providerDirectOssUrl) return true;
    if (meta.oss && typeof meta.oss === 'object') return true;
    return legacyDurableMediaUrl(raw);
};

export const isEphemeralProviderMediaUrl = (url) => {
    const raw = String(url || '').trim();
    if (!raw || raw.startsWith('/') || raw.startsWith('data:')) return false;
    try {
        const parsed = new URL(raw, window.location.origin);
        const host = String(parsed.hostname || '').trim();
        if (EPHEMERAL_PROVIDER_HOST_PATTERNS.some((pattern) => pattern.test(host))) {
            return true;
        }
        const query = String(parsed.search || '').toLowerCase();
        if (query && EPHEMERAL_PROVIDER_QUERY_MARKERS.some((marker) => query.includes(marker))) {
            return true;
        }
    } catch {
        return false;
    }
    return false;
};

export const isDurablePersistedMediaUrl = (url, metadata = null) => {
    const raw = String(url || '').trim();
    if (!raw) return false;
    if (isEphemeralProviderMediaUrl(raw)) return false;
    if (urlMatchesConfiguredOss(raw, metadata)) return true;
    return legacyDurableMediaUrl(raw);
};

export const parseShotTechnicalNotes = (rawNotes) => {
    if (rawNotes && typeof rawNotes === 'object') return rawNotes;
    try {
        const parsed = JSON.parse(String(rawNotes || '{}'));
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
        return {};
    }
};

export const EPHEMERAL_MEDIA_PERSIST_GRACE_MS = 30_000;

export const parseMediaBoundAtMs = (metadata, fallbackMs = null) => {
    const meta = metadata && typeof metadata === 'object' ? metadata : {};
    const raw = meta.media_bound_at || meta.bound_at;
    if (raw) {
        const parsed = Date.parse(String(raw));
        if (Number.isFinite(parsed)) return parsed;
    }
    return Number.isFinite(fallbackMs) ? fallbackMs : null;
};

export const parseShotMediaUpdatedAtMs = (shot) => {
    const candidate = shot?.updated_at || shot?.updatedAt || shot?.modified_at || shot?.modifiedAt || shot?.created_at || shot?.createdAt;
    if (!candidate) return null;
    const parsed = Date.parse(String(candidate));
    return Number.isFinite(parsed) ? parsed : null;
};

export const isWithinMediaPersistGracePeriod = (metadata, options = {}) => {
    const graceMs = Number(options?.graceMs) > 0 ? Number(options.graceMs) : EPHEMERAL_MEDIA_PERSIST_GRACE_MS;
    const boundMs = parseMediaBoundAtMs(metadata, options?.generatedAtMs ?? null);
    if (!boundMs) return false;
    return (Date.now() - boundMs) < graceMs;
};

export const getMediaPersistGraceRemainingMs = (metadata, options = {}) => {
    const graceMs = Number(options?.graceMs) > 0 ? Number(options.graceMs) : EPHEMERAL_MEDIA_PERSIST_GRACE_MS;
    const boundMs = parseMediaBoundAtMs(metadata, options?.generatedAtMs ?? null);
    if (!boundMs) return 0;
    return Math.max(0, graceMs - (Date.now() - boundMs));
};

export const mediaUrlNeedsOssPersist = (url, options = {}) => {
    const rawUrl = String(url || '').trim();
    if (!rawUrl) return false;

    const metadata = options?.metadata && typeof options.metadata === 'object' ? options.metadata : {};

    // URL is already on managed OSS — stale ephemeral metadata must not keep the temp badge.
    if (isDurablePersistedMediaUrl(rawUrl, metadata)) {
        return false;
    }

    // Freshly generated media: give OSS upload/retry a short window before warning UI.
    if (isWithinMediaPersistGracePeriod(metadata, options)) {
        return false;
    }

    const ossUploadedFlag = options?.ossUploadedFlag;
    if (ossUploadedFlag === false) {
        return true;
    }
    if (metadata.needs_persistence_retry || metadata.ephemeral_binding || metadata.remote_localization_failed) {
        return true;
    }
    if (metadata.oss_uploaded_success === false) return true;
    return true;
};

export const resolveShotMediaSlotUrl = (shot, slot = 'video') => {
    const normalizedSlot = String(slot || 'video').trim().toLowerCase();
    const tech = parseShotTechnicalNotes(shot?.technical_notes);
    if (normalizedSlot === 'start' || normalizedSlot === 'start_frame') {
        return String(shot?.image_url || '').trim();
    }
    if (normalizedSlot === 'end' || normalizedSlot === 'end_frame') {
        return String(tech?.end_frame_url || '').trim();
    }
    return String(shot?.video_url || '').trim();
};

export const shotStartFrameNeedsOssPersist = (shot) => {
    const imageUrl = resolveShotMediaSlotUrl(shot, 'start');
    if (!imageUrl) return false;
    const tech = parseShotTechnicalNotes(shot?.technical_notes);
    const meta = tech?.start_frame_metadata && typeof tech.start_frame_metadata === 'object'
        ? tech.start_frame_metadata
        : {};
    return mediaUrlNeedsOssPersist(imageUrl, {
        metadata: meta,
        ossUploadedFlag: tech.start_frame_oss_uploaded,
        generatedAtMs: parseShotMediaUpdatedAtMs(shot),
    });
};

export const shotEndFrameNeedsOssPersist = (shot) => {
    const endUrl = resolveShotMediaSlotUrl(shot, 'end');
    if (!endUrl) return false;
    const tech = parseShotTechnicalNotes(shot?.technical_notes);
    const meta = tech?.end_frame_metadata && typeof tech.end_frame_metadata === 'object'
        ? tech.end_frame_metadata
        : {};
    return mediaUrlNeedsOssPersist(endUrl, {
        metadata: meta,
        ossUploadedFlag: tech.end_frame_oss_uploaded,
        generatedAtMs: parseShotMediaUpdatedAtMs(shot),
    });
};

export const shotVideoNeedsOssPersist = (shot) => {
    const videoUrl = resolveShotMediaSlotUrl(shot, 'video');
    if (!videoUrl) return false;
    const tech = parseShotTechnicalNotes(shot?.technical_notes);
    const meta = tech?.video_metadata && typeof tech.video_metadata === 'object' ? tech.video_metadata : {};
    return mediaUrlNeedsOssPersist(videoUrl, {
        metadata: meta,
        ossUploadedFlag: tech.video_oss_uploaded,
        generatedAtMs: parseShotMediaUpdatedAtMs(shot),
    });
};

export const shotNeedsAnyOssPersist = (shot) => (
    shotStartFrameNeedsOssPersist(shot)
    || shotEndFrameNeedsOssPersist(shot)
    || shotVideoNeedsOssPersist(shot)
);

export const shotNeedsAnyOssPersistGraceWaitMs = (shot) => {
    if (!shot) return 0;
    const tech = parseShotTechnicalNotes(shot?.technical_notes);
    const updatedMs = parseShotMediaUpdatedAtMs(shot);
    const waits = [];

    const videoUrl = resolveShotMediaSlotUrl(shot, 'video');
    if (videoUrl && !isDurablePersistedMediaUrl(videoUrl, tech?.video_metadata || {})) {
        waits.push(getMediaPersistGraceRemainingMs(tech?.video_metadata || {}, { generatedAtMs: updatedMs }));
    }
    const startUrl = resolveShotMediaSlotUrl(shot, 'start');
    if (startUrl && !isDurablePersistedMediaUrl(startUrl, tech?.start_frame_metadata || {})) {
        waits.push(getMediaPersistGraceRemainingMs(tech?.start_frame_metadata || {}, { generatedAtMs: updatedMs }));
    }
    const endUrl = resolveShotMediaSlotUrl(shot, 'end');
    if (endUrl && !isDurablePersistedMediaUrl(endUrl, tech?.end_frame_metadata || {})) {
        waits.push(getMediaPersistGraceRemainingMs(tech?.end_frame_metadata || {}, { generatedAtMs: updatedMs }));
    }

    const active = waits.filter((ms) => ms > 0);
    return active.length ? Math.min(...active) : 0;
};

export const EPHEMERAL_VIDEO_OSS_SYNC_MAX_MS = 120_000;
export const EPHEMERAL_VIDEO_OSS_SYNC_INTERVAL_MS = 2500;

export const extractVideoJobResultUrl = (statusPayload) => {
    const root = statusPayload && typeof statusPayload === 'object' ? statusPayload : {};
    const nested = root.result && typeof root.result === 'object' ? root.result : {};
    return String(
        nested.url
        || nested.video_url
        || nested.videoUrl
        || root.url
        || root.video_url
        || root.videoUrl
        || ''
    ).trim();
};

export const mergeShotVideoOssPersistState = (shotLike, patch = {}) => {
    const merged = { ...(shotLike && typeof shotLike === 'object' ? shotLike : {}) };
    const videoUrl = String(patch.videoUrl || patch.video_url || merged.video_url || '').trim();
    if (videoUrl) merged.video_url = videoUrl;

    const tech = parseShotTechnicalNotes(
        patch.technicalNotes !== undefined
            ? patch.technicalNotes
            : (patch.technical_notes !== undefined ? patch.technical_notes : merged.technical_notes)
    );

    const ossUploaded = patch.ossUploaded !== false && patch.oss_uploaded !== false;
    if (ossUploaded) {
        tech.video_oss_uploaded = true;
        const meta = tech.video_metadata && typeof tech.video_metadata === 'object'
            ? { ...tech.video_metadata }
            : {};
        delete meta.ephemeral_binding;
        delete meta.needs_persistence_retry;
        delete meta.remote_localization_failed;
        meta.oss_uploaded_success = true;
        tech.video_metadata = meta;
    }

    if (patch.technicalNotes !== undefined && patch.technicalNotes && typeof patch.technicalNotes === 'object') {
        merged.technical_notes = patch.technicalNotes;
    } else if (patch.technical_notes !== undefined) {
        merged.technical_notes = patch.technical_notes;
    } else {
        merged.technical_notes = JSON.stringify(tech);
    }

    return merged;
};

export const isShotVideoOssPersistComplete = (shotLike) => !shotVideoNeedsOssPersist(shotLike);

export const parseEntityCustomAttributes = (rawAttrs) => {
    if (rawAttrs && typeof rawAttrs === 'object') return rawAttrs;
    try {
        const parsed = JSON.parse(String(rawAttrs || '{}'));
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
        return {};
    }
};

export const entityImageNeedsOssPersist = (entity) => {
    const imageUrl = String(entity?.image_url || '').trim();
    if (!imageUrl) return false;
    const attrs = parseEntityCustomAttributes(entity?.custom_attributes);
    return mediaUrlNeedsOssPersist(imageUrl, {
        metadata: attrs,
        ossUploadedFlag: attrs.oss_uploaded_success,
        generatedAtMs: parseShotMediaUpdatedAtMs(entity),
    });
};
