// Use VITE_API_BASE_URL if set (production), otherwise fallback to relative path (dev/proxy)
// Note: In Vite, env vars must start with VITE_ to be exposed
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
export const API_URL = `${BASE_URL}/api/v1`;
