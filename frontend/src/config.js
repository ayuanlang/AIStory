// Resolve API base URL with safe production fallback.
// Priority:
// 1) VITE_API_BASE_URL (explicit override)
// 2) On Render frontend, default to deployed backend host (avoid broken static rewrite /api -> backend)
// 3) Same-origin (local/dev)
// You can force same-origin by setting VITE_FORCE_SAME_ORIGIN_API=1.
const RAW_BASE_URL = String(import.meta?.env?.VITE_API_BASE_URL || '').trim();
const FORCE_SAME_ORIGIN_API = String(import.meta?.env?.VITE_FORCE_SAME_ORIGIN_API || '0') === '1';
const isRenderFrontend = typeof window !== 'undefined' && /\.onrender\.com$/i.test(window.location.hostname || '');
const RENDER_BACKEND_FALLBACK = 'https://aistory-backend-xggg.onrender.com';

let resolvedBaseUrl = '';
if (RAW_BASE_URL) {
	resolvedBaseUrl = RAW_BASE_URL;
} else if (!FORCE_SAME_ORIGIN_API && isRenderFrontend) {
	resolvedBaseUrl = RENDER_BACKEND_FALLBACK;
}

export const BASE_URL = resolvedBaseUrl;
export const API_URL = `${BASE_URL}/api/v1`;
