// Resolve API base URL.
// Since the frontend proxy is bypassed, we always enforce the direct backend URL on render.
const RAW_BASE_URL = String(import.meta?.env?.VITE_API_BASE_URL || '').trim();
const isRenderFrontend = typeof window !== 'undefined' && /\.onrender\.com$/i.test(window.location.hostname || '');        
const isLocalFrontend = typeof window !== 'undefined' && /^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname || '');
const RENDER_BACKEND_FALLBACK = 'https://aistory-backend-xggg.onrender.com';
const LOCAL_BACKEND_FALLBACK = 'http://127.0.0.1:8000';

let resolvedBaseUrl = RAW_BASE_URL;
if (!resolvedBaseUrl) {
    if (isLocalFrontend) {
        resolvedBaseUrl = LOCAL_BACKEND_FALLBACK;
    } else {
        resolvedBaseUrl = RENDER_BACKEND_FALLBACK;
    }
}

export const BASE_URL = resolvedBaseUrl;
export const FALLBACK_BASE_URL = RENDER_BACKEND_FALLBACK;
// For media assets (e.g. /uploads/*), use the backend host heavily.
// When accessed from the unified FastAPI origin, empty strings ('') route to the current origin.
export const ASSET_BASE_URL = BASE_URL;
export const API_URL = `${BASE_URL}/api/v1`;
export const FALLBACK_API_URL = `${FALLBACK_BASE_URL}/api/v1`;
