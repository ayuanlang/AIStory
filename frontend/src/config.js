// Resolve API base URL.
// Since the frontend proxy is bypassed, we always enforce the direct backend URL on render.
const RAW_BASE_URL = String(import.meta?.env?.VITE_API_BASE_URL || '').trim();
const isRenderFrontend = typeof window !== 'undefined' && /\.onrender\.com$/i.test(window.location.hostname || '');        
const RENDER_BACKEND_FALLBACK = 'https://aistory-backend-xggg.onrender.com';

let resolvedBaseUrl = '';
if (isRenderFrontend) {
        resolvedBaseUrl = RENDER_BACKEND_FALLBACK;
} else if (RAW_BASE_URL) {
        resolvedBaseUrl = RAW_BASE_URL;
}

export const BASE_URL = resolvedBaseUrl;
export const FALLBACK_BASE_URL = RENDER_BACKEND_FALLBACK;
// For media assets (e.g. /uploads/*), use the backend host heavily.
export const ASSET_BASE_URL = BASE_URL || FALLBACK_BASE_URL;
export const API_URL = `${BASE_URL}/api/v1`;
export const FALLBACK_API_URL = `${FALLBACK_BASE_URL}/api/v1`;
