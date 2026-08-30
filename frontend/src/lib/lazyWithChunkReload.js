import { lazy } from 'react';

const CHUNK_RELOAD_KEY = 'aistory:stale-chunk-reload';
const CHUNK_RELOAD_GUARD_MS = 20000;

export const isStaleChunkError = (error) => {
    const name = String(error?.name || '');
    const message = String(error?.message || error || '');
    return name === 'ChunkLoadError'
        || /Failed to fetch dynamically imported module/i.test(message)
        || /error loading dynamically imported module/i.test(message)
        || /Importing a module script failed/i.test(message)
        || /Loading chunk [\w.-]+ failed/i.test(message);
};

export const isRecentStaleChunkReload = () => {
    if (typeof window === 'undefined') return false;
    try {
        const last = Number(window.sessionStorage.getItem(CHUNK_RELOAD_KEY) || 0);
        return Number.isFinite(last) && last > 0 && (Date.now() - last) < CHUNK_RELOAD_GUARD_MS;
    } catch {
        return false;
    }
};

export const reloadOnceForStaleChunk = () => {
    if (typeof window === 'undefined') return false;
    if (isRecentStaleChunkReload()) return false;
    try {
        window.sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
    } catch {
        // sessionStorage may be blocked; still try a single reload.
    }
    window.location.reload();
    return true;
};

export const importWithChunkReload = (importer) => (
    Promise.resolve()
        .then(importer)
        .catch(async (error) => {
            if (!isStaleChunkError(error)) throw error;
            try {
                return await importer();
            } catch (retryError) {
                if (isStaleChunkError(retryError) && reloadOnceForStaleChunk()) {
                    return new Promise(() => {});
                }
                throw retryError;
            }
        })
);

export const lazyWithChunkReload = (importer) => lazy(() => importWithChunkReload(importer));
