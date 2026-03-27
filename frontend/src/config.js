// Resolve API base URL with safe production fallback.
// Priority:
// 1) VITE_API_BASE_URL (explicit override)
// 2) Render frontend: prefer same-origin Node proxy, fallback to direct backend only if enabled
// 3) Local/dev: same-origin
const RAW_BASE_URL = String(import.meta?.env?.VITE_API_BASE_URL || '').trim();
const PREFER_DIRECT_BACKEND = String(import.meta?.env?.VITE_PREFER_DIRECT_BACKEND || '0') === '1';
const isRenderFrontend = typeof window !== 'undefined' && /\.onrender\.com$/i.test(window.location.hostname || '');
const RENDER_BACKEND_FALLBACK = 'https://aistory-backend-xggg.onrender.com';

let resolvedBaseUrl = '';
let resolvedFallbackBaseUrl = '';
if (RAW_BASE_URL) {
	resolvedBaseUrl = RAW_BASE_URL;
} else if (isRenderFrontend) {
	if (PREFER_DIRECT_BACKEND) {
		resolvedBaseUrl = RENDER_BACKEND_FALLBACK;
		resolvedFallbackBaseUrl = '';
	} else {
		resolvedBaseUrl = '';
		resolvedFallbackBaseUrl = RENDER_BACKEND_FALLBACK;
	}
}

export const BASE_URL = resolvedBaseUrl;
export const FALLBACK_BASE_URL = resolvedFallbackBaseUrl;
export const API_URL = `${BASE_URL}/api/v1`;
export const FALLBACK_API_URL = FALLBACK_BASE_URL ? `${FALLBACK_BASE_URL}/api/v1` : '';
