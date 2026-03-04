// Prefer same-origin API path on Render static hosting to avoid CORS issues.
// Set VITE_FORCE_CROSS_ORIGIN_API=1 only when you explicitly need direct backend-domain calls.
const RAW_BASE_URL = String(import.meta?.env?.VITE_API_BASE_URL || '').trim();
const FORCE_CROSS_ORIGIN_API = String(import.meta?.env?.VITE_FORCE_CROSS_ORIGIN_API || '0') === '1';
const isRenderFrontend = typeof window !== 'undefined' && /\.onrender\.com$/i.test(window.location.hostname || '');

export const BASE_URL = (!FORCE_CROSS_ORIGIN_API && isRenderFrontend) ? '' : RAW_BASE_URL;
export const API_URL = `${BASE_URL}/api/v1`;
