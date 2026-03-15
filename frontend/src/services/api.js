import axios from 'axios';
import { API_URL, BASE_URL, FALLBACK_API_URL } from '../config';
import { normalizeEntityToken } from '../lib/entityToken';

// Use API_URL from config which supports production env vars
export const api = axios.create({
  baseURL: API_URL,
  timeout: 600000, // 10 minutes timeout for long LLM generation tasks
});

const shouldRetryWithFallback = (error) => {
    const status = Number(error?.response?.status || 0);
    const code = String(error?.code || '');
    const message = String(error?.message || '').toLowerCase();
    const payload = error?.response?.data;
    const payloadText = typeof payload === 'string' ? payload.toLowerCase() : '';

    if (code === 'ERR_NETWORK') return true;
    // Only retry on gateway errors (502/504), NOT on 500/503 which are meaningful responses
    if (status === 502 || status === 504) return true;

    if (status === 404 && payloadText.includes('cannot get /api/')) {
        return true;
    }

    return message.includes('network error');
};

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalConfig = error?.config || {};
        if (!FALLBACK_API_URL || originalConfig.__fallbackRetried) {
            return Promise.reject(error);
        }

        if (!shouldRetryWithFallback(error)) {
            return Promise.reject(error);
        }

        const retryConfig = {
            ...originalConfig,
            __fallbackRetried: true,
            baseURL: FALLBACK_API_URL,
        };

        return api.request(retryConfig);
    }
);

// Merge duplicate concurrent requests (single-flight) for hot Settings endpoints.
const inFlightRequestMap = new Map();

const buildSingleFlightKey = (prefix, params = null) => {
    if (params === null || params === undefined) return prefix;
    if (typeof params === 'string') return `${prefix}|${params}`;
    try {
        if (Array.isArray(params)) {
            return `${prefix}|${JSON.stringify(params)}`;
        }
        if (typeof params === 'object') {
            const sorted = Object.keys(params)
                .sort((a, b) => a.localeCompare(b))
                .reduce((acc, key) => {
                    acc[key] = params[key];
                    return acc;
                }, {});
            return `${prefix}|${JSON.stringify(sorted)}`;
        }
    } catch (_) {
        // Ignore serialization failures and fall back to prefix-only key.
    }
    return prefix;
};

const runSingleFlight = (key, producer) => {
    const existing = inFlightRequestMap.get(key);
    if (existing) return existing;

    const task = (async () => {
        try {
            return await producer();
        } finally {
            inFlightRequestMap.delete(key);
        }
    })();

    inFlightRequestMap.set(key, task);
    return task;
};

// ── Async LLM task polling utilities ────────────────────────────────────
// Backend LLM endpoints accept ?async=1 and return { task_id, async: true }.
// pollTask() polls GET /tasks/{task_id} until completed or failed.

const LLM_POLL_INTERVAL = 2500;   // ms between polls
const LLM_POLL_TIMEOUT  = 600000; // 10 min max wait
const LLM_TASK_NOT_FOUND_GRACE_MS = 12000; // tolerate short eventual-consistency lag

const isTaskNotFoundPollingError = (error) => {
        const status = Number(error?.response?.status || 0);
        if (status !== 404) return false;
        const detail = String(error?.response?.data?.detail || '').trim().toLowerCase();
        return detail.includes('task not found');
};

async function pollTask(taskId, {
    interval = LLM_POLL_INTERVAL,
    timeout = LLM_POLL_TIMEOUT,
    baseURL = undefined,
    notFoundGraceMs = LLM_TASK_NOT_FOUND_GRACE_MS,
} = {}) {
  const deadline = Date.now() + timeout;
    let notFoundSince = 0;
  while (Date.now() < deadline) {
        try {
            const reqConfig = {
                ...(baseURL ? { baseURL } : {}),
                // Prevent proxy/browser stale-cache from pinning task status at "running".
                params: { _ts: Date.now() },
                headers: {
                    'Cache-Control': 'no-cache, no-store, max-age=0',
                    Pragma: 'no-cache',
                },
            };
            const res = await api.get(`/tasks/${taskId}`, reqConfig);
            notFoundSince = 0;
            const info = res.data;
            if (info.status === 'completed') return info.result;
            if (info.status === 'failed') {
                const err = new Error(info.error || 'Task failed');
                err.errorCode = info.error_code || 500;
                err.response = { status: info.error_code || 500, data: { detail: info.error } };
                throw err;
            }
            if (info.status === 'canceled' || info.status === 'cancelled') {
                const err = new Error(info.error || 'Task canceled');
                err.errorCode = info.error_code || 499;
                err.isCanceled = true;
                err.response = { status: info.error_code || 499, data: { detail: info.error || 'Task canceled' } };
                throw err;
            }
            await new Promise(r => setTimeout(r, interval));
        } catch (error) {
            if (isTaskNotFoundPollingError(error)) {
                const now = Date.now();
                if (!notFoundSince) notFoundSince = now;
                if ((now - notFoundSince) <= Math.max(0, Number(notFoundGraceMs || 0))) {
                    await new Promise(r => setTimeout(r, Math.min(interval, 1500)));
                    continue;
                }
            }
            throw error;
    }
  }
  throw new Error('LLM task polling timed out');
}

/**
 * Wrapper: POST to an LLM endpoint with ?async=1, then poll for result.
 * Falls back to direct response if backend doesn't return task_id (backward compat).
 */
async function asyncLLMPost(url, data, config = {}) {
  const sep = url.includes('?') ? '&' : '?';
  const res = await api.post(`${url}${sep}async_mode=1`, data, config);
  if (res.data && res.data.task_id && res.data.async) {
        if (typeof config.onTaskCreated === 'function') {
            try {
                config.onTaskCreated(res.data.task_id, { baseURL: res?.config?.baseURL || api.defaults.baseURL });
            } catch (_) {
                // Ignore callback errors to avoid breaking normal request flow.
            }
        }
        const submitBaseURL = res?.config?.baseURL || api.defaults.baseURL;
        return await pollTask(res.data.task_id, {
            ...(config.pollOptions || {}),
            // Keep polling on the same backend host that created the task.
            baseURL: (config.pollOptions && config.pollOptions.baseURL) || submitBaseURL,
        });
  }
  return res.data;
}

export const waitForAsyncTask = async (taskId, pollOptions = {}) => {
    if (!taskId) throw new Error('Missing taskId');
    return await pollTask(taskId, pollOptions || {});
};

export const stopAsyncTask = async (taskId) => {
    if (!taskId) throw new Error('Missing taskId');
    const response = await api.post(`/tasks/${taskId}/cancel`);
    return response.data;
};

const VIDEO_JOB_TIMEOUT_MS_DEFAULT = (() => {
    const parsed = Number(import.meta?.env?.VITE_VIDEO_JOB_TIMEOUT_MS || 10 * 60 * 1000);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        return 10 * 60 * 1000;
    }
    return Math.min(10 * 60 * 1000, Math.max(60 * 1000, parsed));
})();

const VIDEO_STATUS_MAX_CONCURRENT = (() => {
    const parsed = Number(import.meta?.env?.VITE_VIDEO_STATUS_MAX_CONCURRENT || 2);
    if (!Number.isFinite(parsed)) return 2;
    return Math.max(1, Math.min(4, Math.floor(parsed)));
})();

let videoStatusInFlight = 0;
const videoStatusWaitQueue = [];
const videoStatusSingleFlight = new Map();

const acquireVideoStatusSlot = async () => {
    if (videoStatusInFlight < VIDEO_STATUS_MAX_CONCURRENT) {
        videoStatusInFlight += 1;
        return;
    }
    await new Promise((resolve) => {
        videoStatusWaitQueue.push(resolve);
    });
    videoStatusInFlight += 1;
};

const releaseVideoStatusSlot = () => {
    videoStatusInFlight = Math.max(0, videoStatusInFlight - 1);
    const next = videoStatusWaitQueue.shift();
    if (typeof next === 'function') {
        next();
    }
};

const fetchVideoJobStatusLimited = async (jobId, { baseURL } = {}) => {
    const stableJobId = String(jobId || '').trim();
    if (!stableJobId) {
        throw new Error('Missing video job id');
    }

    const singleFlightKey = `${String(baseURL || '')}::${stableJobId}`;
    const existing = videoStatusSingleFlight.get(singleFlightKey);
    if (existing) {
        return existing;
    }

    const pending = (async () => {
        await acquireVideoStatusSlot();
        try {
            const response = await api.get(
                `/generate/video/jobs/${stableJobId}`,
                baseURL ? { baseURL } : undefined
            );
            return response?.data || {};
        } finally {
            releaseVideoStatusSlot();
        }
    })();

    videoStatusSingleFlight.set(singleFlightKey, pending);
    try {
        return await pending;
    } finally {
        videoStatusSingleFlight.delete(singleFlightKey);
    }
};

const normalizeVideoJobTimeoutMs = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        return VIDEO_JOB_TIMEOUT_MS_DEFAULT;
    }
    return Math.min(10 * 60 * 1000, Math.max(60 * 1000, parsed));
};

const buildApiErrorMessage = (error) => {
    const extractMessageFromPayload = (payload) => {
        if (payload == null) return '';

        if (typeof payload === 'string') {
            const trimmed = payload.trim();
            if (!trimmed) return '';
            try {
                const parsed = JSON.parse(trimmed);
                return extractMessageFromPayload(parsed) || trimmed;
            } catch {
                return trimmed;
            }
        }

        if (Array.isArray(payload)) {
            const joined = payload
                .map((item) => extractMessageFromPayload(item))
                .filter(Boolean)
                .join('; ');
            return joined;
        }

        if (typeof payload !== 'object') {
            return String(payload || '').trim();
        }

        if (Array.isArray(payload.detail)) {
            const joined = payload.detail
                .map((item) => {
                    if (!item) return '';
                    if (typeof item === 'string') return item;
                    const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
                    const msg = item.msg || item.message || '';
                    return loc ? `${loc}: ${msg}` : msg;
                })
                .filter(Boolean)
                .join('; ');
            if (joined) return joined;
        }

        const candidates = [
            payload.detail,
            payload.message,
            payload.error,
            payload.reason,
            payload.msg,
            payload.description,
        ];

        for (const candidate of candidates) {
            const text = extractMessageFromPayload(candidate);
            if (text) return text;
        }

        return '';
    };

    const responseData = error?.response?.data;
    const extractedFromResponse = extractMessageFromPayload(responseData);
    if (extractedFromResponse) {
        return extractedFromResponse;
    }

    const detail = responseData?.detail;

    if (Array.isArray(detail)) {
        const joined = detail
            .map((item) => {
                if (!item) return '';
                if (typeof item === 'string') return item;
                const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
                const msg = item.msg || item.message || '';
                return loc ? `${loc}: ${msg}` : msg;
            })
            .filter(Boolean)
            .join('; ');
        if (joined) return joined;
    }

    if (typeof detail === 'string' && detail.trim()) {
        return detail.trim();
    }

    if (detail && typeof detail === 'object') {
        const fallback = detail.message || detail.error || detail.reason;
        if (typeof fallback === 'string' && fallback.trim()) return fallback.trim();
        try {
            return JSON.stringify(detail);
        } catch {
            // no-op
        }
    }

    if (typeof responseData === 'string' && responseData.trim()) {
        return responseData.trim();
    }

    if (responseData && typeof responseData === 'object') {
        const fallback = responseData.message || responseData.error || responseData.reason;
        if (typeof fallback === 'string' && fallback.trim()) return fallback.trim();
    }

    if (error?.code === 'ECONNABORTED') {
        return 'Request timeout. Please try again.';
    }

    const rawResponseText = error?.request?.responseText;
    const extractedFromRawResponse = extractMessageFromPayload(rawResponseText);
    if (extractedFromRawResponse) {
        return extractedFromRawResponse;
    }

    if (!error?.response) {
        return 'Network error. Please check your connection and backend service.';
    }

    return error?.message || 'Request failed';
};

const IMAGE_SUBMIT_IDEMPOTENCY_WINDOW_MS = 30 * 1000;
const imageSubmitIdempotencyCache = new Map();

const normalizeRefImageValue = (value) => {
    if (Array.isArray(value)) {
        return value
            .map((item) => String(item || '').trim())
            .filter(Boolean);
    }
    const raw = String(value || '').trim();
    return raw ? [raw] : [];
};

const buildImageSubmitSignature = (payload) => {
    const signatureSource = {
        prompt: String(payload?.prompt || '').trim(),
        negative_prompt: String(payload?.negative_prompt || '').trim(),
        provider: String(payload?.provider || '').trim(),
        model: String(payload?.model || '').trim(),
        seed: payload?.seed ?? null,
        cfg: payload?.cfg ?? null,
        mode: payload?.mode ?? null,
        ref_image_url: normalizeRefImageValue(payload?.ref_image_url),
        project_id: payload?.project_id ?? null,
        shot_id: payload?.shot_id ?? null,
        shot_number: payload?.shot_number ?? null,
        shot_name: payload?.shot_name ?? null,
        entity_id: payload?.entity_id ?? null,
        entity_name: payload?.entity_name ?? null,
        subject_name: payload?.subject_name ?? null,
        subject_type: payload?.subject_type ?? null,
        entity_type: payload?.entity_type ?? null,
        asset_type: payload?.asset_type ?? null,
    };
    return JSON.stringify(signatureSource);
};

const getOrCreateImageSubmitIdempotencyKey = (payload, explicitKey = null) => {
    const custom = String(explicitKey || '').trim();
    if (custom) return custom;

    const now = Date.now();
    for (const [signature, info] of imageSubmitIdempotencyCache.entries()) {
        if (!info || (now - Number(info.createdAt || 0)) > IMAGE_SUBMIT_IDEMPOTENCY_WINDOW_MS) {
            imageSubmitIdempotencyCache.delete(signature);
        }
    }

    const signature = buildImageSubmitSignature(payload);
    const cached = imageSubmitIdempotencyCache.get(signature);
    if (cached && (now - Number(cached.createdAt || 0)) <= IMAGE_SUBMIT_IDEMPOTENCY_WINDOW_MS) {
        return cached.key;
    }

    const key = `img-${now}-${Math.random().toString(36).slice(2, 12)}`;
    imageSubmitIdempotencyCache.set(signature, {
        key,
        createdAt: now,
    });
    return key;
};

// Add a request interceptor to include the token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Add a response interceptor to handle 401 errors
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const normalizedMessage = buildApiErrorMessage(error);
        if (normalizedMessage) {
            error.message = normalizedMessage;
            error.userMessage = normalizedMessage;
            error.detail = normalizedMessage;
        }

        if (error.response) {
            if (error.response.status === 401) {
                localStorage.removeItem('token');
                window.location.href = '/auth';
            } else if (error.response.status === 402) {
                // Dispatch event for UI to handle (Show Recharge Modal)
                window.dispatchEvent(new Event('SHOW_RECHARGE_MODAL'));
            }
        }
        return Promise.reject(error);
    }
);

export const sendAgentCommand = async (query, context = {}, history = []) => {
    return await asyncLLMPost('/agent/command', {
        query,
        context,
        history
    });
};

export const sendSystemManagementAgentCommand = async (query, context = {}, history = []) => {
    return await asyncLLMPost('/agent/system-management/command', {
        query,
        context,
        history,
    });
};

// ── SSE Streaming Agent Commands ────────────────────────────────────────

/**
 * Stream an agent command via SSE (Server-Sent Events).
 * @param {string} url - API path (e.g. '/agent/command/stream')
 * @param {object} body - Request body {query, context, history}
 * @param {object} callbacks - { onToken(text), onToolStart(tool,params), onToolResult(tool,status,result), onDone(result), onError(msg) }
 * @returns {Promise<object>} The final "done" payload
 */
async function streamSSE(url, body, callbacks = {}) {
    const token = localStorage.getItem('token');
    const baseURL = api.defaults.baseURL || '';
    const fullURL = `${baseURL}${url}`;

    const response = await fetch(fullURL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const errJson = await response.json();
            detail = errJson.detail || detail;
        } catch (_) { /* ignore */ }
        const err = new Error(detail);
        err.response = { status: response.status, data: { detail } };
        throw err;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResult = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line in buffer

        let currentEventType = 'message';
        for (const line of lines) {
            if (line.startsWith('event:')) {
                currentEventType = line.slice(6).trim();
                continue;
            }
            if (line.startsWith('data:')) {
                const dataStr = line.slice(5).trim();
                if (!dataStr) continue;
                try {
                    const event = JSON.parse(dataStr);
                    const type = event.type || currentEventType;

                    if (type === 'token' && callbacks.onToken) {
                        callbacks.onToken(event.content || '');
                    } else if (type === 'tool_start' && callbacks.onToolStart) {
                        callbacks.onToolStart(event.tool, event.parameters);
                    } else if (type === 'tool_result' && callbacks.onToolResult) {
                        callbacks.onToolResult(event.tool, event.status, event.result);
                    } else if (type === 'done') {
                        finalResult = event;
                        if (callbacks.onDone) callbacks.onDone(event);
                    } else if (type === 'error') {
                        if (callbacks.onError) callbacks.onError(event.message || 'Unknown error');
                    }
                } catch (_) { /* ignore malformed JSON */ }
            }
            if (line === '') {
                currentEventType = 'message'; // reset after blank line
            }
        }
    }

    return finalResult || {};
}

export const streamAgentCommand = async (query, context = {}, history = [], callbacks = {}) => {
    return await streamSSE('/agent/command/stream', { query, context, history }, callbacks);
};

export const streamSystemManagementAgentCommand = async (query, context = {}, history = [], callbacks = {}) => {
    return await streamSSE('/agent/system-management/command/stream', { query, context, history }, callbacks);
};

export const fetchProjects = async () => {
    const response = await api.get('/projects/');
    return response.data;
}

export const createProject = async (data) => {
    const response = await api.post('/projects/', data);
    return response.data;
}

export const fetchProjectShares = async (projectId) => {
    const response = await api.get(`/projects/${projectId}/shares`);
    return response.data;
}

export const createProjectShare = async (projectId, target_user) => {
    const response = await api.post(`/projects/${projectId}/shares`, { target_user });
    return response.data;
}

export const deleteProjectShare = async (projectId, sharedUserId) => {
    const response = await api.delete(`/projects/${projectId}/shares/${sharedUserId}`);
    return response.data;
}


export const fetchSystemLogs = async (skip = 0, limit = 100) => {
    const response = await api.get(`/system/logs?skip=${skip}&limit=${limit}`);
    return response.data;
}

export const recordSystemLogAction = async (payload = {}) => {
    try {
        const response = await api.post('/system/logs/action', payload || {});
        return response.data;
    } catch {
        return null;
    }
}

export const fetchProject = async (id) => {
    const response = await api.get(`/projects/${id}`);
    return response.data;
}

export const updateProject = async (id, data) => {
    const response = await api.put(`/projects/${id}`, data);
    return response.data;
}

export const generateProjectStoryGlobal = async (projectId, payload) => {
    return await asyncLLMPost(`/projects/${projectId}/story_generator/global`, payload);
}

export const analyzeProjectNovel = async (projectId, payload) => {
    return await asyncLLMPost(`/projects/${projectId}/story_generator/analyze_novel`, payload);
}

// Project Story Generator (Global/Project) draft input persistence (no LLM call)
export const saveProjectStoryGeneratorGlobalInput = async (projectId, payload) => {
    const response = await api.put(`/projects/${projectId}/story_generator/global/input`, payload);
    return response.data;
}

export const exportProjectStoryGlobalPackage = async (projectId) => {
    const response = await api.get(`/projects/${projectId}/story_generator/global/export`);
    return response.data;
}

export const importProjectStoryGlobalPackage = async (projectId, payload) => {
    const response = await api.put(`/projects/${projectId}/story_generator/global/import`, payload);
    return response.data;
}

const sanitizeEpisodePayload = (episode) => {
    if (!episode || typeof episode !== 'object') return episode;
    return {
        ...episode,
        episode_info: {},
    };
};

// Episodes
export const fetchEpisodes = async (projectId) => {
    const response = await api.get(`/projects/${projectId}/episodes`);
    const rows = Array.isArray(response.data) ? response.data : [];
    return rows.map(sanitizeEpisodePayload);
}

export const createEpisode = async (projectId, data) => {
    const payload = { ...(data || {}) };
    delete payload.episode_info;
    const response = await api.post(`/projects/${projectId}/episodes`, payload);
    return sanitizeEpisodePayload(response.data);
}

export const updateEpisode = async (episodeId, data) => {
    const payload = { ...(data || {}) };
    delete payload.episode_info;
    const response = await api.put(`/episodes/${episodeId}`, payload);
    return sanitizeEpisodePayload(response.data);
}

export const updateEpisodeSegments = async (episodeId, segments) => {
    const response = await api.put(`/episodes/${episodeId}/segments`, segments);
    return response.data;
}

export const deleteEpisode = async (episodeId) => {
    const response = await api.delete(`/episodes/${episodeId}`);
    return response.data;
}

// Scenes
export const fetchScenes = async (episodeId, params = {}) => {
    const response = await api.get(`/episodes/${episodeId}/scenes`, { params });
    return response.data;
}

export const createScene = async (episodeId, data) => {
    const response = await api.post(`/episodes/${episodeId}/scenes`, data);
    return response.data;
}

export const updateScene = async (sceneId, data) => {
    const response = await api.put(`/scenes/${sceneId}`, data);
    return response.data;
}

export const deleteScene = async (sceneId) => {
    const response = await api.delete(`/scenes/${sceneId}`);
    return response.data;
}

export const regenerateScene = async (sceneId, payload) => {
    return await asyncLLMPost(`/scenes/${sceneId}/regenerate`, payload || {});
}

// Shots
export const fetchEpisodeShots = async (episodeId, params = {}) => {
    const response = await api.get(`/episodes/${episodeId}/shots`, { params });
    return response.data;
}

export const fetchShots = async (sceneId) => {
    const response = await api.get(`/scenes/${sceneId}/shots`);
    return response.data;
}

export const createShot = async (sceneId, data) => {
    const response = await api.post(`/scenes/${sceneId}/shots`, data);
    return response.data;
}

export const updateShot = async (shotId, data) => {
    const response = await api.put(`/shots/${shotId}`, data);
    return response.data;
}

export const deleteShot = async (shotId) => {
    const response = await api.delete(`/shots/${shotId}`);
    return response.data;
}

export const fetchSceneShotsPrompt = async (sceneId) => {
    const response = await api.get(`/scenes/${sceneId}/ai_prompt_preview`);
    return response.data;
}

export const generateSceneShots = async (sceneId, promptData = null, runtimeHooks = {}) => {
    // This now returns the Staging result (timestamp, content=[]), not the applied shots
    const payloadMeta = {
        hasUserPrompt: Boolean(promptData?.user_prompt),
        hasSystemPrompt: Boolean(promptData?.system_prompt),
        userPromptLen: String(promptData?.user_prompt || '').length,
        systemPromptLen: String(promptData?.system_prompt || '').length,
    };
    try {
        return await asyncLLMPost(`/scenes/${sceneId}/ai_generate_shots`, promptData, {
            onTaskCreated: runtimeHooks?.onTaskCreated,
            pollOptions: runtimeHooks?.pollOptions,
        });
    } catch (error) {
        console.error('[API] generateSceneShots failed', {
            sceneId,
            status: error?.response?.status,
            detail: error?.response?.data?.detail,
            responseData: error?.response?.data,
            message: error?.message,
        });
        throw error;
    }
}

export const getSceneLatestAIResult = async (sceneId) => {
    const response = await api.get(`/scenes/${sceneId}/latest_ai_result`);
    return response.data;
}

export const updateSceneLatestAIResult = async (sceneId, content) => {
    const response = await api.put(`/scenes/${sceneId}/latest_ai_result`, { content });
    return response.data;
}

export const applySceneAIResult = async (sceneId, data = null) => {
    // data is optional { content: [] } to override stored
    const response = await api.post(`/scenes/${sceneId}/apply_ai_result`, data);
    return response.data;
}

// Episode Character Canon
export const generateEpisodeCharacterProfile = async (episodeId, payload) => {
    return await asyncLLMPost(`/episodes/${episodeId}/character_profiles/generate`, payload);
}

// Project Character Canon (Overview)
export const generateProjectCharacterProfile = async (projectId, payload) => {
    return await asyncLLMPost(`/projects/${projectId}/character_profiles/generate`, payload);
}

// Project Character Canon draft input persistence (no LLM call)
export const saveProjectCharacterCanonInput = async (projectId, payload) => {
    const response = await api.put(`/projects/${projectId}/character_canon/input`, payload);
    return response.data;
}

export const saveProjectCharacterCanonCategories = async (projectId, payload) => {
    const response = await api.put(`/projects/${projectId}/character_canon/categories`, payload);
    return response.data;
}

export const fetchEpisodeCharacterProfiles = async (episodeId) => {
    const response = await api.get(`/episodes/${episodeId}/character_profiles`);
    return response.data;
}

export const fetchProjectCharacterProfiles = async (projectId) => {
    const response = await api.get(`/projects/${projectId}/character_profiles`);
    return response.data;
}

export const updateEpisodeCharacterProfiles = async (episodeId, character_profiles) => {
    const response = await api.put(`/episodes/${episodeId}/character_profiles`, { character_profiles });
    return response.data;
}

export const updateProjectCharacterProfiles = async (projectId, character_profiles) => {
    const response = await api.put(`/projects/${projectId}/character_profiles`, { character_profiles });
    return response.data;
}

export const generateEpisodeScenes = async (episodeId, payload) => {
    return await asyncLLMPost(`/episodes/${episodeId}/script_generator/scenes`, payload);
}

// Project Script Generator (Episodes -> Script drafts)
export const generateProjectEpisodeScripts = async (projectId, payload) => {
    return await asyncLLMPost(
        `/projects/${projectId}/script_generator/episodes/scripts`,
        payload,
        { pollOptions: { timeout: 30 * 60 * 1000 } }
    );
}

export const getProjectEpisodeScriptsStatus = async (projectId) => {
    const response = await api.get(`/projects/${projectId}/script_generator/episodes/scripts/status`);
    return response.data;
}

export const stopProjectEpisodeScripts = async (projectId) => {
    const response = await api.post(`/projects/${projectId}/script_generator/episodes/scripts/stop`);
    return response.data;
}

export const startSceneAiShotsBatch = async (episodeId, payload = {}) => {
    const response = await api.post(`/episodes/${episodeId}/scenes/ai_shots/batch/start`, payload);
    return response.data;
}

export const getSceneAiShotsBatchStatus = async (episodeId) => {
    const response = await api.get(`/episodes/${episodeId}/scenes/ai_shots/batch/status`);
    return response.data;
}

export const stopSceneAiShotsBatch = async (episodeId) => {
    const response = await api.post(`/episodes/${episodeId}/scenes/ai_shots/batch/stop`);
    return response.data;
}

export const startEpisodeScenesGeneration = async (episodeId, payload) => {
    const response = await api.post(`/episodes/${episodeId}/script_generator/scenes/start`, payload);
    return response.data;
}

export const getEpisodeScenesGenerationStatus = async (episodeId) => {
    const response = await api.get(`/episodes/${episodeId}/script_generator/scenes/status`);
    return response.data;
}

export const stopEpisodeScenesGeneration = async (episodeId) => {
    const response = await api.post(`/episodes/${episodeId}/script_generator/scenes/stop`);
    return response.data;
}

export const startShotMediaBatch = async (episodeId, payload) => {
    const response = await api.post(`/episodes/${episodeId}/shots/batch-media/start`, payload);
    return response.data;
}

export const getShotMediaBatchStatus = async (episodeId) => {
    const response = await api.get(`/episodes/${episodeId}/shots/batch-media/status`);
    return response.data;
}

export const stopShotMediaBatch = async (episodeId) => {
    const response = await api.post(`/episodes/${episodeId}/shots/batch-media/stop`);
    return response.data;
}

// Entities
export const fetchEntities = async (projectId, type = null) => {
    const params = type ? { type } : {};
    const response = await api.get(`/projects/${projectId}/entities`, { params });
    return response.data;
}

export const createEntity = async (projectId, data) => {
    const response = await api.post(`/projects/${projectId}/entities`, data);
    return response.data;
}

export const updateEntity = async (entityId, data) => {
    const response = await api.put(`/entities/${entityId}`, data);
    return response.data;
}

export const deleteEntity = async (entityId) => {
    const response = await api.delete(`/entities/${entityId}`);
    return response.data;
}

export const deleteAllEntities = async (projectId) => {
    const response = await api.delete(`/projects/${projectId}/entities`);
    return response.data;
}

export const cloneEntityWithLLM = async (projectId, entityId, payload = {}) => {
    const response = await api.post(`/projects/${projectId}/entities/${entityId}/clone_with_llm`, payload || {});
    return response.data;
}


// Generation
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const AUTO_DOWNLOAD_PREF_KEY_PREFIX = 'aistory.autoDownloadLocal';
const PROMPT_SUBMIT_LANG_PREF_KEY_PREFIX = 'aistory.promptSubmitLang';
const USER_PREFERENCES_CACHE_KEY_PREFIX = 'aistory.userPreferences';

const DEFAULT_USER_PREFERENCES = {
    prompt_submit_language: 'en',
    auto_download_local: false,
    generation: {},
    advanced_model: {
        temperature: 0.7,
        seed: null,
        cfg: null,
        reasoning_effort: 'high',
    },
};

const decodeJwtPayload = (token) => {
    try {
        const parts = String(token || '').split('.');
        if (parts.length < 2) return null;
        const base64Url = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const padded = base64Url.padEnd(Math.ceil(base64Url.length / 4) * 4, '=');
        return JSON.parse(atob(padded));
    } catch {
        return null;
    }
};

const resolveCurrentUserStorageScope = () => {
    const token = localStorage.getItem('token');
    if (!token) return 'anonymous';
    const payload = decodeJwtPayload(token);
    const rawUser = payload?.sub ?? payload?.user_id ?? payload?.id ?? payload?.email ?? payload?.username;
    const scope = String(rawUser || '').trim();
    return scope || 'anonymous';
};

const autoDownloadPreferenceStorageKey = () => `${AUTO_DOWNLOAD_PREF_KEY_PREFIX}:${resolveCurrentUserStorageScope()}`;
const promptSubmitLanguageStorageKey = () => `${PROMPT_SUBMIT_LANG_PREF_KEY_PREFIX}:${resolveCurrentUserStorageScope()}`;
const userPreferencesStorageKey = () => `${USER_PREFERENCES_CACHE_KEY_PREFIX}:${resolveCurrentUserStorageScope()}`;

const normalizeReasoningEffort = (value) => {
    const raw = String(value || '').trim().toLowerCase();
    return ['low', 'medium', 'high'].includes(raw) ? raw : 'high';
};

export const normalizeUserPreferences = (value) => {
    const raw = value && typeof value === 'object' ? value : {};
    const generation = raw.generation && typeof raw.generation === 'object' ? raw.generation : {};
    const advanced = raw.advanced_model && typeof raw.advanced_model === 'object' ? raw.advanced_model : {};
    const temperatureNum = Number(advanced.temperature);
    const cfgNum = Number(advanced.cfg);
    const seedNum = Number(advanced.seed);

    return {
        prompt_submit_language: normalizePromptSubmitLanguagePreference(raw.prompt_submit_language),
        auto_download_local: !!raw.auto_download_local,
        generation,
        advanced_model: {
            temperature: Number.isFinite(temperatureNum) ? Math.max(0, Math.min(2, temperatureNum)) : 0.7,
            seed: Number.isFinite(seedNum) && seedNum > 0 ? Math.trunc(seedNum) : null,
            cfg: Number.isFinite(cfgNum) && cfgNum > 0 ? cfgNum : null,
            reasoning_effort: normalizeReasoningEffort(advanced.reasoning_effort),
        },
    };
};

const getCachedUserPreferences = () => {
    try {
        const raw = localStorage.getItem(userPreferencesStorageKey());
        if (!raw) return null;
        return normalizeUserPreferences(JSON.parse(raw));
    } catch {
        return null;
    }
};

const setCachedUserPreferences = (next) => {
    try {
        const normalized = normalizeUserPreferences(next);
        localStorage.setItem(userPreferencesStorageKey(), JSON.stringify(normalized));
        return normalized;
    } catch {
        return normalizeUserPreferences(next);
    }
};

export const getUserPreferences = async () => {
    const response = await api.get('/settings/preferences');
    return setCachedUserPreferences(response?.data || {});
};

export const updateUserPreferences = async (payload = {}) => {
    const response = await api.put('/settings/preferences', payload || {});
    return setCachedUserPreferences(response?.data || {});
};

export const normalizePromptSubmitLanguagePreference = (value) => {
    const raw = String(value || '').trim().toLowerCase();
    if (raw === 'auto') return 'auto';
    if (raw === 'cn' || raw === 'zh' || raw === 'zh-cn') return 'cn';
    return 'en';
};

export const getAutoDownloadLocalPreference = () => {
    const cached = getCachedUserPreferences();
    if (cached && typeof cached.auto_download_local === 'boolean') {
        return cached.auto_download_local;
    }
    try {
        const raw = localStorage.getItem(autoDownloadPreferenceStorageKey());
        if (raw === '1') return true;
        if (raw === '0') return false;
    } catch {
        // ignore
    }
    return null;
};

export const setAutoDownloadLocalPreference = (enabled) => {
    try {
        localStorage.setItem(autoDownloadPreferenceStorageKey(), enabled ? '1' : '0');
        const current = getCachedUserPreferences() || DEFAULT_USER_PREFERENCES;
        setCachedUserPreferences({
            ...current,
            auto_download_local: !!enabled,
        });
    } catch {
        // ignore storage failures
    }
};

export const getPromptSubmitLanguagePreference = () => {
    const cached = getCachedUserPreferences();
    if (cached && cached.prompt_submit_language) {
        return normalizePromptSubmitLanguagePreference(cached.prompt_submit_language);
    }
    try {
        const raw = localStorage.getItem(promptSubmitLanguageStorageKey());
        if (!raw) return 'en';
        return normalizePromptSubmitLanguagePreference(raw);
    } catch {
        return 'en';
    }
};

export const setPromptSubmitLanguagePreference = (value) => {
    try {
        const normalized = normalizePromptSubmitLanguagePreference(value);
        localStorage.setItem(promptSubmitLanguageStorageKey(), normalized);
        const current = getCachedUserPreferences() || DEFAULT_USER_PREFERENCES;
        setCachedUserPreferences({
            ...current,
            prompt_submit_language: normalized,
        });
    } catch {
        // ignore storage failures
    }
};

export const resolvePromptSubmitLanguage = (uiLang = 'en', preference = null) => {
    const normalized = normalizePromptSubmitLanguagePreference(
        preference == null ? getPromptSubmitLanguagePreference() : preference
    );
    if (normalized === 'cn' || normalized === 'en') return normalized;
    return String(uiLang || '').toLowerCase().startsWith('zh') ? 'cn' : 'en';
};

const shouldAutoDownloadByUserSetting = () => {
    const explicitUserPref = getAutoDownloadLocalPreference();
    if (explicitUserPref !== null) {
        return explicitUserPref;
    }
    try {
        const raw = localStorage.getItem('generationConfig');
        if (!raw) return false;
        const parsed = JSON.parse(raw);
        if (parsed && Object.prototype.hasOwnProperty.call(parsed, 'autoDownloadLocal')) {
            return !!parsed.autoDownloadLocal;
        }
    } catch {
        // ignore parsing issues and fallback to default disabled behavior
    }
    return false;
};

const shouldAutoDownloadForRequest = (options = {}) => {
    if (Object.prototype.hasOwnProperty.call(options || {}, 'auto_download_local')) {
        return options?.auto_download_local !== false;
    }
    return shouldAutoDownloadByUserSetting();
};

const resolveMediaDownloadUrl = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return '';
    if (/^https?:\/\//i.test(raw)) return raw;
    if (raw.startsWith('/')) {
        const prefix = String(BASE_URL || '').trim();
        if (prefix) {
            return `${prefix}${raw}`;
        }
        return `${window.location.origin}${raw}`;
    }
    return raw;
};

const inferFilenameFromUrl = (url, fallbackName) => {
    try {
        const pathname = new URL(url).pathname || '';
        const name = pathname.split('/').pop();
        if (name && name.includes('.')) return name;
    } catch {
        // ignore
    }
    return fallbackName;
};

const downloadMediaToLocal = async (url, fallbackName) => {
    const downloadUrl = resolveMediaDownloadUrl(url);
    if (!downloadUrl) return;
    const response = await fetch(downloadUrl, { credentials: 'include' });
    if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = inferFilenameFromUrl(downloadUrl, fallbackName);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
};

const isTransientPollingError = (error) => {
    const status = Number(error?.response?.status || 0);
    if (status === 408 || status === 409 || status === 429) return true;
    if (status >= 500 && status < 600) return true;
    const code = String(error?.code || '').toUpperCase();
    return code === 'ECONNABORTED' || code === 'ERR_NETWORK';
};

const isLocalLikeHostname = (hostname) => {
    const host = String(hostname || '').trim().toLowerCase();
    if (!host) return false;
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1') return true;
    if (host.endsWith('.local')) return true;
    if (host.startsWith('10.')) return true;
    if (host.startsWith('192.168.')) return true;
    if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(host)) return true;
    return false;
};

const isLocalDeployment = () => {
    try {
        const apiHost = new URL(String(API_URL || ''), window.location.origin).hostname;
        if (isLocalLikeHostname(apiHost)) return true;
    } catch {
        // ignore
    }

    try {
        if (isLocalLikeHostname(window.location.hostname)) return true;
    } catch {
        // ignore
    }

    return false;
};

const resolveDefaultCallbackPollingEnabled = () => {
    const explicit = String(import.meta?.env?.VITE_GENERATION_CALLBACK_POLLING || '').trim().toLowerCase();
    if (explicit === '1' || explicit === 'true' || explicit === 'yes' || explicit === 'on') {
        return true;
    }
    if (explicit === '0' || explicit === 'false' || explicit === 'no' || explicit === 'off') {
        return false;
    }
    return !isLocalDeployment();
};

const DEFAULT_CALLBACK_POLLING_ENABLED = resolveDefaultCallbackPollingEnabled();

const createGenerationCallbackTicket = (kind = 'gen') => {
    const now = Date.now();
    const rand = Math.random().toString(36).slice(2, 10);
    return `${kind}-${now}-${rand}`;
};

const buildGenerationCallbackUrl = (ticket) => {
    const stableTicket = String(ticket || '').trim();
    if (!stableTicket) return '';
    const base = String(API_URL || '').trim().replace(/\/$/, '');
    if (!base) return '';
    return `${base}/generate/callback/${encodeURIComponent(stableTicket)}`;
};

const pollGenerationCallbackUntilDone = async (
    ticket,
    { timeoutMs = 10 * 60 * 1000, pollIntervalMs = 2000, kind = 'generation', cancelledRef } = {}
) => {
    const stableTicket = String(ticket || '').trim();
    if (!stableTicket) throw new Error('Missing callback ticket');

    const start = Date.now();
    let intervalMs = Math.max(1500, Number(pollIntervalMs || 2000));
    const maxIntervalMs = 3500;

    while (Date.now() - start < timeoutMs) {
        if (cancelledRef?.current) throw new Error(`${kind} callback polling cancelled`);
        try {
            const response = await api.get(`/generate/callback/${encodeURIComponent(stableTicket)}`);
            const data = response?.data || {};
            const received = !!data?.received;

            if (received) {
                const payload = (data?.payload && typeof data.payload === 'object') ? data.payload : {};
                const status = String(payload?.status || '').toLowerCase();

                if (status === 'succeeded') {
                    return payload?.result || {};
                }
                if (status === 'failed' || status === 'canceled' || status === 'cancelled') {
                    throw new Error(payload?.error || `${kind} callback returned ${status}`);
                }
            }

            await sleep(intervalMs);
            intervalMs = Math.min(maxIntervalMs, Math.round(intervalMs * 1.1));
        } catch (error) {
            if (cancelledRef?.current) throw new Error(`${kind} callback polling cancelled`);
            if (!isTransientPollingError(error)) {
                throw error;
            }
            await sleep(Math.min(maxIntervalMs, Math.round(intervalMs * 1.3)));
            intervalMs = Math.min(maxIntervalMs, Math.round(intervalMs * 1.3));
        }
    }

    throw new Error(`${kind} generation timed out while waiting callback result`);
};

const pollImageJobUntilDone = async (
    jobId,
    { timeoutMs = 10 * 60 * 1000, pollIntervalMs = 2000, cancelledRef, baseURL } = {}
) => {
    const start = Date.now();
    let intervalMs = Math.max(1500, Number(pollIntervalMs || 2000));
    const maxIntervalMs = 3000;
    while (Date.now() - start < timeoutMs) {
        if (cancelledRef?.current) throw new Error('Image job polling cancelled');
        try {
            const response = await api.get(
                `/generate/image/jobs/${jobId}`,
                baseURL ? { baseURL } : undefined
            );
            const data = response?.data || {};
            const status = String(data.status || '').toLowerCase();

            if (status === 'succeeded') {
                return data.result || {};
            }
            if (status === 'failed') {
                throw new Error(data.error || 'Image generation job failed');
            }

            await sleep(intervalMs);
            intervalMs = Math.min(maxIntervalMs, Math.round(intervalMs * 1.1));
        } catch (error) {
            if (cancelledRef?.current) throw new Error('Image job polling cancelled');
            if (!isTransientPollingError(error)) {
                throw error;
            }
            await sleep(Math.min(maxIntervalMs, Math.round(intervalMs * 1.3)));
            intervalMs = Math.min(maxIntervalMs, Math.round(intervalMs * 1.3));
        }
    }

    throw new Error('Image generation timed out while polling job status');
};

const pollVideoJobUntilDone = async (
    jobId,
    { timeoutMs = VIDEO_JOB_TIMEOUT_MS_DEFAULT, pollIntervalMs = 2500, cancelledRef, baseURL } = {}
) => {
    const start = Date.now();
    let intervalMs = Math.max(2000, Number(pollIntervalMs || 2500));
    const maxIntervalMs = 5000;
    while (Date.now() - start < timeoutMs) {
        if (cancelledRef?.current) throw new Error('Video job polling cancelled');
        try {
            const data = await fetchVideoJobStatusLimited(jobId, { baseURL });
            const status = String(data.status || '').toLowerCase();

            if (status === 'succeeded') {
                return data.result || {};
            }
            if (status === 'failed') {
                throw new Error(data.error || 'Video generation job failed');
            }

            await sleep(intervalMs);
            intervalMs = Math.min(maxIntervalMs, Math.round(intervalMs * 1.1));
        } catch (error) {
            if (cancelledRef?.current) throw new Error('Video job polling cancelled');
            if (!isTransientPollingError(error)) {
                throw error;
            }
            await sleep(Math.min(maxIntervalMs, Math.round(intervalMs * 1.3)));
            intervalMs = Math.min(maxIntervalMs, Math.round(intervalMs * 1.3));
        }
    }

    throw new Error('Video generation timed out while polling job status');
};

export const getVideoGenerationJobStatus = async (jobId, options = {}) => {
    return await fetchVideoJobStatusLimited(jobId, options);
};

export const getGenerationJobPool = async (params = {}) => {
    const response = await api.get('/generate/jobs/pool', { params });
    return response?.data || {};
};

export const stopGenerationJob = async (kind, jobId, { force = false } = {}) => {
    const response = await api.post(`/generate/jobs/${kind}/${jobId}/stop`, null, {
        params: force ? { force: true } : undefined,
    });
    return response?.data || {};
};

export const deleteGenerationJob = async (kind, jobId) => {
    const response = await api.delete(`/generate/jobs/${kind}/${jobId}`);
    return response?.data || {};
};

export const stopAllGenerationJobs = async (kind = 'all', { force = false } = {}) => {
    const response = await api.post('/generate/jobs/stop-all', null, {
        params: force ? { kind, force: true } : { kind },
    });
    return response?.data || {};
};

export const generateImage = async (prompt, provider = null, ref_image_url = null, options = {}, negative_prompt = null) => {
    const {
        job_timeout_ms,
        job_poll_interval_ms,
        on_job_created,
        ...requestOptions
    } = options || {};

    const effectiveRequestOptions = { ...(requestOptions || {}) };
    const userPrefs = getCachedUserPreferences() || DEFAULT_USER_PREFERENCES;
    const advanced = userPrefs?.advanced_model && typeof userPrefs.advanced_model === 'object'
        ? userPrefs.advanced_model
        : {};
    if (!Object.prototype.hasOwnProperty.call(effectiveRequestOptions, 'seed')) {
        const seedNum = Number(advanced.seed);
        if (Number.isFinite(seedNum) && seedNum > 0) {
            effectiveRequestOptions.seed = Math.trunc(seedNum);
        }
    }
    if (!Object.prototype.hasOwnProperty.call(effectiveRequestOptions, 'cfg')) {
        const cfgNum = Number(advanced.cfg);
        if (Number.isFinite(cfgNum) && cfgNum > 0) {
            effectiveRequestOptions.cfg = cfgNum;
        }
    }

    const effectiveNegativePrompt = String(negative_prompt ?? options?.negative_prompt ?? '').trim();
    const callbackPollingEnabled = Object.prototype.hasOwnProperty.call(options || {}, 'callback_polling')
        ? options?.callback_polling !== false
        : DEFAULT_CALLBACK_POLLING_ENABLED;
    const callbackTicket = callbackPollingEnabled ? createGenerationCallbackTicket('img') : '';
    const callbackUrl = callbackPollingEnabled ? buildGenerationCallbackUrl(callbackTicket) : '';
    const payload = {
        prompt,
        provider,
        ref_image_url,
        ...effectiveRequestOptions,
        ...(effectiveNegativePrompt ? { negative_prompt: effectiveNegativePrompt } : {}),
        ...(callbackUrl ? { callback_url: callbackUrl } : {}),
    };
    const idempotencyKey = getOrCreateImageSubmitIdempotencyKey(payload, options?.idempotency_key);

    let submitResp;
    try {
        submitResp = await api.post('/generate/image/submit', payload, {
            headers: {
                'X-Idempotency-Key': idempotencyKey,
            },
        });
    } catch (error) {
        const status = Number(error?.response?.status || 0);
        const shouldFallback = status === 404 || status === 405 || status === 501;
        if (!shouldFallback) {
            throw error;
        }

        const response = await api.post('/generate/image', payload);
        if (shouldAutoDownloadForRequest(options) && response?.data?.url) {
            try {
                await downloadMediaToLocal(response.data.url, `generated_image_${Date.now()}.png`);
            } catch (downloadError) {
                console.warn('[generateImage] auto local download failed:', downloadError);
            }
        }
        return response.data;
    }

    const jobId = submitResp?.data?.job_id;
    if (!jobId) {
        throw new Error('Missing image job_id from submit response');
    }
    const submitBaseURL = submitResp?.config?.baseURL || api.defaults.baseURL;
    if (typeof on_job_created === 'function') {
        try {
            on_job_created(jobId);
        } catch {
            // ignore callback errors
        }
    }

    let result;
    if (callbackUrl && callbackTicket) {
        const cancelledRef = { current: false };
        const effectiveTimeoutMs = Number(job_timeout_ms || 10 * 60 * 1000);
        const effectivePollMs = Number(job_poll_interval_ms || 2000);
        const wrap = (p) => p.catch(err => {
            if (cancelledRef.current) throw err;
            throw err;
        }).finally(() => { cancelledRef.current = true; });
        try {
            result = await Promise.any([
                wrap(pollGenerationCallbackUntilDone(callbackTicket, {
                    timeoutMs: effectiveTimeoutMs,
                    pollIntervalMs: effectivePollMs,
                    kind: 'image',
                    cancelledRef,
                })),
                wrap(pollImageJobUntilDone(jobId, {
                    timeoutMs: effectiveTimeoutMs,
                    pollIntervalMs: effectivePollMs,
                    cancelledRef,
                    baseURL: submitBaseURL,
                })),
            ]);
        } catch (anyErr) {
            const real = anyErr?.errors?.find(e => !/polling cancelled/i.test(e?.message));
            throw real || anyErr;
        }
    } else {
        result = await pollImageJobUntilDone(jobId, {
            timeoutMs: Number(job_timeout_ms || 10 * 60 * 1000),
            pollIntervalMs: Number(job_poll_interval_ms || 2000),
            baseURL: submitBaseURL,
        });
    }

    if (shouldAutoDownloadForRequest(options) && result?.url) {
        try {
            await downloadMediaToLocal(result.url, `generated_image_${Date.now()}.png`);
        } catch (downloadError) {
            console.warn('[generateImage] auto local download failed:', downloadError);
        }
    }

    return result;
}

export const submitImageGenerationJob = async (prompt, provider = null, ref_image_url = null, options = {}, negative_prompt = null) => {
    const effectiveNegativePrompt = String(negative_prompt ?? options?.negative_prompt ?? '').trim();
    const payload = {
        prompt,
        provider,
        ref_image_url,
        ...(options || {}),
        ...(effectiveNegativePrompt ? { negative_prompt: effectiveNegativePrompt } : {}),
    };
    const response = await api.post('/generate/image/submit', payload);
    return response.data;
};

export const getImageGenerationJobStatus = async (jobId) => {
    const response = await api.get(`/generate/image/jobs/${jobId}`);
    return response.data;
};

export const generateVideo = async (prompt, provider = null, ref_image_url = null, last_frame_url = null, duration = 5, options = {}, keyframes = [], negative_prompt = null) => {
    const effectiveNegativePrompt = String(negative_prompt ?? options?.negative_prompt ?? '').trim();
    const {
        job_timeout_ms,
        job_poll_interval_ms,
        on_job_created,
        ...requestOptions
    } = options || {};
    const callbackPollingEnabled = Object.prototype.hasOwnProperty.call(options || {}, 'callback_polling')
        ? options?.callback_polling !== false
        : DEFAULT_CALLBACK_POLLING_ENABLED;
    const callbackTicket = callbackPollingEnabled ? createGenerationCallbackTicket('vid') : '';
    const callbackUrl = callbackPollingEnabled ? buildGenerationCallbackUrl(callbackTicket) : '';
    const payload = {
        prompt,
        duration,
        ...requestOptions,
        ...(callbackUrl ? { callback_url: callbackUrl } : {}),
        ...(provider ? { provider } : {}),
        ...(ref_image_url !== null && ref_image_url !== undefined && ref_image_url !== '' ? { ref_image_url } : {}),
        ...(last_frame_url !== null && last_frame_url !== undefined && last_frame_url !== '' ? { last_frame_url } : {}),
        ...(Array.isArray(keyframes) && keyframes.length > 0 ? { keyframes } : {}),
        ...(effectiveNegativePrompt ? { negative_prompt: effectiveNegativePrompt } : {}),
    };

    const idempotencyKey = `vid-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;

    let submitResp;
    try {
        submitResp = await api.post('/generate/video/submit', payload, {
            headers: {
                'X-Idempotency-Key': idempotencyKey,
            },
        });
    } catch (error) {
        const status = Number(error?.response?.status || 0);
        const shouldFallback = status === 404 || status === 405 || status === 501;
        if (!shouldFallback) {
            throw error;
        }

        const response = await api.post('/generate/video', payload);
        if (shouldAutoDownloadForRequest(options) && response?.data?.url) {
            try {
                await downloadMediaToLocal(response.data.url, `generated_video_${Date.now()}.mp4`);
            } catch (downloadError) {
                console.warn('[generateVideo] auto local download failed:', downloadError);
            }
        }
        return response.data;
    }

    const jobId = submitResp?.data?.job_id;
    if (!jobId) {
        throw new Error('Missing video job_id from submit response');
    }
    const submitBaseURL = submitResp?.config?.baseURL || api.defaults.baseURL;
    if (typeof on_job_created === 'function') {
        try {
            on_job_created(jobId);
        } catch {
            // ignore callback errors
        }
    }

    let result;
    if (callbackUrl && callbackTicket) {
        const cancelledRef = { current: false };
        const effectiveTimeoutMs = normalizeVideoJobTimeoutMs(job_timeout_ms);
        const effectivePollMs = Number(job_poll_interval_ms || 2500);
        const wrap = (p) => p.catch(err => {
            if (cancelledRef.current) throw err;
            throw err;
        }).finally(() => { cancelledRef.current = true; });
        try {
            result = await Promise.any([
                wrap(pollGenerationCallbackUntilDone(callbackTicket, {
                    timeoutMs: effectiveTimeoutMs,
                    pollIntervalMs: effectivePollMs,
                    kind: 'video',
                    cancelledRef,
                })),
                wrap(pollVideoJobUntilDone(jobId, {
                    timeoutMs: effectiveTimeoutMs,
                    pollIntervalMs: effectivePollMs,
                    cancelledRef,
                    baseURL: submitBaseURL,
                })),
            ]);
        } catch (anyErr) {
            const real = anyErr?.errors?.find(e => !/polling cancelled/i.test(e?.message));
            throw real || anyErr;
        }
    } else {
        result = await pollVideoJobUntilDone(jobId, {
            timeoutMs: normalizeVideoJobTimeoutMs(job_timeout_ms),
            pollIntervalMs: Number(job_poll_interval_ms || 2500),
            baseURL: submitBaseURL,
        });
    }

    if (shouldAutoDownloadForRequest(options) && result?.url) {
        try {
            await downloadMediaToLocal(result.url, `generated_video_${Date.now()}.mp4`);
        } catch (downloadError) {
            console.warn('[generateVideo] auto local download failed:', downloadError);
        }
    }
    return result;
}

export const generateVoice = async (prompt, provider = null, model = null, options = {}) => {
    const payload = {
        prompt,
        ...options,
        ...(provider ? { provider } : {}),
        ...(model ? { model } : {}),
    };
    const response = await api.post('/generate/voice', payload);
    return response.data;
}

export const deleteProject = async (projectId) => {
    const response = await api.delete(`/projects/${projectId}`);
    return response.data;
}

export const registerUser = async (data) => {
    // data: { username, email, password, full_name }
    const response = await api.post('/users/', data);
    return response.data;
}

export const sendEmailVerificationCode = async (email) => {
    const response = await api.post('/users/verification/send', { email });
    return response.data;
}

export const confirmEmailVerificationCode = async (email, code) => {
    const response = await api.post('/users/verification/confirm', { email, code });
    return response.data;
}

export const apiLogin = async (username, password) => {
    const response = await api.post('/login', {
        username,
        password
    });
    return response.data;
}

export const forgotPassword = async (email) => {
    const response = await api.post('/password/forgot', { email });
    return response.data;
}

export const resetPassword = async (token, new_password) => {
    const response = await api.post('/password/reset', { token, new_password });
    return response.data;
}

export const getSettings = async () => {
    return runSingleFlight('GET:/settings', async () => {
        const response = await api.get('/settings');
        return response.data;
    });
}

export const getSettingDefaults = async () => {
    const response = await api.get('/settings/defaults');
    return response.data;
}

export const getSystemSettings = async () => {
    return runSingleFlight('GET:/settings/system', async () => {
        const response = await api.get('/settings/system', {
            params: { _ts: Date.now() },
            headers: {
                'Cache-Control': 'no-cache',
                Pragma: 'no-cache',
            },
        });
        return response.data;
    });
}

export const getSystemSettingsCatalog = async () => {
    return runSingleFlight('GET:/settings/system/catalog', async () => {
        const response = await api.get('/settings/system/catalog');
        return response.data;
    });
}

export const selectSystemSetting = async (setting_id, api_strategy = 'smart_default', mode = null) => {
    const payload = { setting_id, api_strategy };
    const modeText = String(mode == null ? '' : mode).trim();
    if (modeText) {
        payload.mode = modeText;
    }
    const response = await api.post('/settings/system/select', payload);
    return response.data;
}

export const getSystemSettingsManage = async () => {
    return runSingleFlight('GET:/settings/system/manage', async () => {
        const response = await api.get('/settings/system/manage', {
            params: { _ts: Date.now() },
            headers: {
                'Cache-Control': 'no-cache',
                Pragma: 'no-cache',
            },
        });
        return response.data;
    });
}

export const getSystemApisMissingBillingRulesManage = async () => {
    // Compatibility-first implementation:
    // derive "missing billing rules" from stable endpoints to avoid noisy 405/422
    // in mixed deployments where /missing-billing-rules is not consistently routable.
    const [settingsRes, rulesRes] = await Promise.all([
        api.get('/settings/system/manage', {
            params: { _ts: Date.now() },
            headers: {
                'Cache-Control': 'no-cache',
                Pragma: 'no-cache',
            },
        }),
        api.get('/settings/system/manage/billing-rules', {
            params: { _ts: Date.now() },
            headers: {
                'Cache-Control': 'no-cache',
                Pragma: 'no-cache',
            },
        }),
    ]);

    const settings = Array.isArray(settingsRes?.data) ? settingsRes.data : [];
    const groupedRules = (rulesRes?.data && typeof rulesRes.data === 'object') ? rulesRes.data : {};

    const billedApiIds = new Set(
        Object.keys(groupedRules)
            .map((x) => Number(x || 0))
            .filter((id) => Number.isFinite(id) && id > 0)
    );

    return settings
        .filter((row) => {
            const id = Number(row?.id || 0);
            if (!Number.isFinite(id) || id <= 0) return false;
            if (Boolean(row?.deprecated)) return false;
            if (!Boolean(row?.is_active)) return false;
            return !billedApiIds.has(id);
        })
        .map((row) => ({
            id: Number(row?.id || 0),
            name: row?.name || null,
            category: row?.category || '',
            provider: row?.provider || '',
            model: row?.model || null,
            base_model: row?.base_model || null,
            deprecated: Boolean(row?.deprecated),
            is_active: Boolean(row?.is_active),
        }));
}

export const createSystemSettingManage = async (data) => {
    const response = await api.post('/settings/system/manage', data);
    return response.data;
}

export const updateSystemSettingManage = async (settingId, data) => {
    const response = await api.post(`/settings/system/manage/${settingId}`, data);
    return response.data;
}

export const toggleSystemSettingDeprecatedManage = async (settingId, deprecated = null) => {
    const payload = deprecated === null || deprecated === undefined ? {} : { deprecated: !!deprecated };
    const response = await api.post(`/settings/system/manage/${settingId}/deprecated`, payload);
    return response.data;
}

export const toggleSystemSettingDeprecatedByKeyManage = async ({ provider, category, model = null, setting_id = null, deprecated = null }) => {
    const payload = {
        provider,
        category,
        ...(model !== null && model !== undefined ? { model } : {}),
        ...(setting_id !== null && setting_id !== undefined ? { setting_id } : {}),
        ...(deprecated === null || deprecated === undefined ? {} : { deprecated: !!deprecated }),
    };
    if (setting_id !== null && setting_id !== undefined) {
        const fallbackPayload = deprecated === null || deprecated === undefined ? {} : { deprecated: !!deprecated };
        const fallback = await api.post(`/settings/system/manage/${Number(setting_id)}/deprecated`, fallbackPayload);
        return fallback.data;
    }
    try {
        const response = await api.post('/settings/system/manage/deprecated/by-key', payload);
        return response.data;
    } catch (error) {
        const status = Number(error?.response?.status || 0);
        if (status === 404) return null;
        throw error;
    }
}

export const batchToggleSystemProviderDeprecatedManage = async (provider, deprecated, category = null) => {
    const payload = {
        deprecated: !!deprecated,
        ...(category ? { category } : {}),
    };
    const response = await api.post(`/settings/system/manage/provider/${encodeURIComponent(provider)}/deprecated`, payload);
    return response.data;
}

export const getSystemProviderKeysManage = async (provider) => {
    const response = await api.get(`/settings/system/manage/provider/${encodeURIComponent(provider)}/keys`);
    return response.data;
}

export const setSystemProviderKeysManage = async (provider, keys = [], strategy = null, weights = null) => {
    const payload = {
        keys,
        ...(strategy ? { strategy } : {}),
        ...(Array.isArray(weights) ? { weights } : {}),
    };
    const response = await api.post(`/settings/system/manage/provider/${encodeURIComponent(provider)}/keys`, payload);
    return response.data;
}

export const deleteSystemSettingManage = async (settingId) => {
    const response = await api.delete(`/settings/system/manage/${settingId}`);
    return response.data;
}

export const listTaskDefaultApisManage = async () => {
    const response = await api.get('/settings/system/manage/task-default-apis');
    return response.data;
}

export const createTaskDefaultApiManage = async (payload) => {
    const response = await api.post('/settings/system/manage/task-default-apis', payload || {});
    return response.data;
}

export const updateTaskDefaultApiManage = async (taskCategory, payload) => {
    const response = await api.post(`/settings/system/manage/task-default-apis/${encodeURIComponent(taskCategory)}`, payload || {});
    return response.data;
}

export const deleteTaskDefaultApiManage = async (taskCategory) => {
    const response = await api.delete(`/settings/system/manage/task-default-apis/${encodeURIComponent(taskCategory)}`);
    return response.data;
}

export const listSystemApiBillingRulesManage = async (systemApiId) => {
    const response = await api.get(`/settings/system/manage/${systemApiId}/billing-rules`, {
        params: { _ts: Date.now() },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const listSystemApiBillingRulesBatchManage = async (systemApiIds = []) => {
    const ids = (Array.isArray(systemApiIds) ? systemApiIds : [])
        .map((id) => Number(id || 0))
        .filter((id) => Number.isFinite(id) && id > 0);
    const key = buildSingleFlightKey('GET:/settings/system/manage/billing-rules', {
        system_api_ids: ids.join(',') || '',
    });
    return runSingleFlight(key, async () => {
        const response = await api.get('/settings/system/manage/billing-rules', {
            params: {
                ...(ids.length ? { system_api_ids: ids.join(',') } : {}),
                _ts: Date.now(),
            },
            headers: {
                'Cache-Control': 'no-cache',
                Pragma: 'no-cache',
            },
        });
        return response.data;
    });
}

export const createSystemApiBillingRuleManage = async (systemApiId, payload) => {
    const response = await api.post(`/settings/system/manage/${systemApiId}/billing-rules`, payload);
    return response.data;
}

export const updateSystemApiBillingRuleManage = async (ruleId, payload) => {
    const response = await api.post(`/settings/system/manage/billing-rules/${ruleId}`, payload);
    return response.data;
}

export const deleteSystemApiBillingRuleManage = async (ruleId) => {
    const response = await api.delete(`/settings/system/manage/billing-rules/${ruleId}`);
    return response.data;
}

export const deleteSystemApiBillingRulesBatchManage = async (ruleIds = []) => {
    const ids = (Array.isArray(ruleIds) ? ruleIds : [])
        .map((id) => Number(id || 0))
        .filter((id) => Number.isFinite(id) && id > 0);
    if (!ids.length) {
        return { ok: true, deleted_count: 0, deleted_ids: [], missing_ids: [] };
    }
    const response = await api.delete('/settings/system/manage/billing-rules', {
        params: {
            rule_ids: ids.join(','),
        },
    });
    return response.data;
}

export const resetSystemApiBillingRuleChargeMultipliersManage = async (payload = {}) => {
    const response = await api.post('/settings/system/manage/billing-rules/reset-charge-multiplier', payload || {});
    return response.data;
}

export const recomputeSystemApiPriceCacheManage = async (systemApiIds = []) => {
    const ids = (Array.isArray(systemApiIds) ? systemApiIds : [])
        .map((id) => Number(id || 0))
        .filter((id) => Number.isFinite(id) && id > 0);
    const response = await api.post('/settings/system/manage/price-cache/recompute', null, {
        params: {
            ...(ids.length ? { system_api_ids: ids.join(',') } : {}),
        },
    });
    return response.data;
}

// provider_key_pool CRUD
export const listProviderKeyPools = async () => {
    const response = await api.get('/settings/system/manage/provider-key-pools');
    return response.data;
}

export const createProviderKeyPool = async (payload) => {
    const response = await api.post('/settings/system/manage/provider-key-pools', payload);
    return response.data;
}

export const updateProviderKeyPool = async (poolId, payload) => {
    const response = await api.post(`/settings/system/manage/provider-key-pools/${poolId}`, payload);
    return response.data;
}

export const deleteProviderKeyPool = async (poolId) => {
    const response = await api.delete(`/settings/system/manage/provider-key-pools/${poolId}`);
    return response.data;
}

export const listKieStandardValuesManage = async (params = {}) => {
    const response = await api.get('/settings/system/manage/kie-standard-values', {
        params: {
            ...params,
            _ts: Date.now(),
        },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const getKieStandardValueOptions = async (params = {}) => {
    const response = await api.get('/settings/system/kie-standard-values/options', {
        params: {
            ...params,
            _ts: Date.now(),
        },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const listKieStandardMappingsManage = async (params = {}) => {
    const response = await api.get('/settings/system/manage/kie-standard-mappings', {
        params: {
            ...params,
            _ts: Date.now(),
        },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const createKieStandardMappingManage = async (payload) => {
    const response = await api.post('/settings/system/manage/kie-standard-mappings', payload || {});
    return response.data;
}

export const updateKieStandardMappingManage = async (mappingId, payload) => {
    const response = await api.post(`/settings/system/manage/kie-standard-mappings/${mappingId}`, payload || {});
    return response.data;
}

export const deleteKieStandardMappingManage = async (mappingId) => {
    const response = await api.delete(`/settings/system/manage/kie-standard-mappings/${mappingId}`);
    return response.data;
}

export const inferKieStandardMappingBillingRelatedManage = async (provider = 'kie') => {
    const response = await api.post('/settings/system/manage/kie-standard-mappings/infer-billing-related', null, {
        params: { provider },
    });
    return response.data;
}

export const exportKieDataDictionaryMappings = async (params = {}) => {
    const response = await api.get('/kie/data-dictionary/mappings/export', {
        params: {
            provider: 'kie',
            include_csv: true,
            ...params,
            _ts: Date.now(),
        },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const importKieDataDictionaryMappings = async (payload) => {
    const response = await api.post('/kie/data-dictionary/mappings/import', payload || {});
    return response.data;
}

export const exportKieDataDictionaryValues = async (params = {}) => {
    const response = await api.get('/kie/data-dictionary/values/export', {
        params: {
            include_csv: true,
            ...params,
            _ts: Date.now(),
        },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const importKieDataDictionaryValues = async (payload) => {
    const response = await api.post('/kie/data-dictionary/values/import', payload || {});
    return response.data;
}

export const exportKieDataDictionaryBundle = async (params = {}) => {
    const response = await api.get('/kie/data-dictionary/bundle/export', {
        params: {
            include_csv: true,
            ...params,
            _ts: Date.now(),
        },
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
}

export const importKieDataDictionaryBundle = async (payload) => {
    const response = await api.post('/kie/data-dictionary/bundle/import', payload || {});
    return response.data;
}

export const exportSystemSettingsManage = async () => {
    const response = await api.get('/settings/system/manage/export');
    return response.data;
}

export const exportSystemSettingsToSeed = async () => {
    const response = await api.post('/settings/system/manage/export-seed');
    return response.data;
}

export const importSystemSettingsManage = async (payload) => {
    const response = await api.post('/settings/system/manage/import', payload);
    return response.data;
}

export const exportSystemProviderBundleManage = async () => {
    const response = await api.get('/settings/system/manage/provider-bundle/export');
    return response.data;
}

export const importSystemProviderBundleManage = async (payload) => {
    const response = await api.post('/settings/system/manage/provider-bundle/import', payload);
    return response.data;
}

export const validateSystemProviderBundleManage = async (payload) => {
    const response = await api.post('/settings/system/manage/provider-bundle/validate', payload);
    return response.data;
};

export const exportSystemConfigSyncBundleManage = async () => {
    const response = await api.get('/settings/system/manage/sync/export');
    return response.data;
}

export const importSystemConfigSyncBundleManage = async (payload) => {
    const response = await api.post('/settings/system/manage/sync/import', payload);
    return response.data;
}

export const getAdminLlmLogFiles = async () => {
    const response = await api.get('/admin/llm-logs/files');
    return response.data;
}

export const getAdminLlmLogView = async (params = {}) => {
    const response = await api.get('/admin/llm-logs/view', { params });
    return response.data;
}

export const getAdminRuntimeLogFiles = async () => {
    const response = await api.get('/admin/runtime-logs/files');
    return response.data;
}

export const getAdminRuntimeLogView = async (params = {}) => {
    const response = await api.get('/admin/runtime-logs/view', { params });
    return response.data;
}

export const getAdminStorageUsage = async () => {
    const response = await api.get('/admin/storage-usage');
    return response.data;
};

export const getAdminMaintenanceConfig = async () => {
    const response = await api.get('/admin/maintenance-config');
    return response.data;
};

export const updateAdminMaintenanceConfig = async (payload = {}) => {
    const response = await api.post('/admin/maintenance-config', payload || {});
    return response.data;
};

export const getMaintenanceStatus = async () => {
    const response = await api.get('/admin/maintenance-status', {
        headers: {
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
        },
    });
    return response.data;
};

export const fetchUnreferencedAssetIds = async () => {
    const response = await api.get('/assets/unreferenced-ids');
    return response.data;
}

export const getEffectiveSettingSnapshot = async (params = {}) => {
    const response = await api.get('/settings/effective', { params });
    return response.data;
}

export const updateSetting = async (data) => {
    const response = await api.post('/settings', data);
    return response.data;
}

export const deleteSetting = async (id) => {
    const response = await api.delete(`/settings/${id}`);
    return response.data;
}

export const analyzeEntityImage = async (entityId) => {
    try {
        const response = await api.post(`/entities/${entityId}/analyze`);
        return response.data;
    } catch (e) {
        console.error(`[API FAIL] analyzeEntityImage failed:`, e);
        throw e;
    }
}

export default api;


// --- Assets ---
export const fetchAssets = async (params = {}) => {
    const config = {};
    if (typeof params === 'string') {
        config.params = { type: params };
    } else {
        config.params = params;
    }
    const response = await api.get('/assets/', config);
    return response.data;
};

export const createAsset = async (data) => {
    const response = await api.post('/assets/', data);
    return response.data;
};

export const uploadAsset = async (data, optionalData = {}) => {
    let payload = data;
    // Auto-wrap File object in FormData
    if (data instanceof File) {
        payload = new FormData();
        payload.append('file', data);
        // Append optional metadata
        Object.keys(optionalData).forEach(key => {
            if (optionalData[key]) payload.append(key, optionalData[key]);
        });
    }
    const response = await api.post('/assets/upload', payload);
    return response.data;
};

export const deleteAsset = async (id) => {
    const response = await api.delete(`/assets/${id}`);
    return response.data;
};

export const deleteAssetsBatch = async (ids) => {
    const response = await api.post('/assets/batch-delete', ids);
    return response.data;
};

export const updateAsset = async (id, data) => {
    const response = await api.put(`/assets/${id}`, data);
    return response.data;
};

export const analyzeAssetImage = async (asset_id) => {
    const response = await api.post('/assets/analyze', { asset_id });
    return response.data;
};

export const rebindShotMediaAssets = async (payload = {}) => {
    const response = await api.post('/assets/rebind-shot-media', payload);
    return response.data;
};

export const translateText = async (q, from_lang = 'en', to_lang = 'zh') => {
    return await asyncLLMPost('/tools/translate', { q, from_lang, to_lang });
};

export const refinePrompt = async (original_prompt, instruction, type = 'image') => {
    return await asyncLLMPost('/tools/refine_prompt', { original_prompt, instruction, type });
};

export const analyzeScene = async (scriptText, systemPrompt = null, projectMetadata = null, episodeId = null, analysisAttentionNotes = null, reuseSubjectAssets = null, runtimeHooks = null) => {
    const payload = { 
        text: scriptText,
        system_prompt: systemPrompt,
        include_negative_prompt: true,
    };
    if (episodeId) {
        payload.episode_id = episodeId;
    }
    if (projectMetadata) {
        payload.project_metadata = projectMetadata;
    }
    if (analysisAttentionNotes && String(analysisAttentionNotes).trim()) {
        payload.analysis_attention_notes = String(analysisAttentionNotes).trim();
    }
    if (Array.isArray(reuseSubjectAssets) && reuseSubjectAssets.length > 0) {
        payload.reuse_subject_assets = reuseSubjectAssets;
    }
    const submitTimeoutRaw = Number(import.meta?.env?.VITE_ANALYZE_SCENE_SUBMIT_TIMEOUT_MS || 45000);
    const submitTimeout = Number.isFinite(submitTimeoutRaw)
        ? Math.max(15000, Math.min(180000, Math.floor(submitTimeoutRaw)))
        : 45000;

    let data = {};
    try {
        data = (await asyncLLMPost('/analyze_scene', payload, {
            timeout: submitTimeout,
            onTaskCreated: runtimeHooks?.onTaskCreated,
            pollOptions: {
                interval: 1200,
                timeout: LLM_POLL_TIMEOUT,
            },
        })) ?? {};
    } catch (error) {
        const noResponse = !error?.response;
        const timeout = String(error?.code || '') === 'ECONNABORTED';
        const detail = buildApiErrorMessage(error);

        if (timeout || noResponse) {
            throw new Error(`AI Scene Analysis submit/poll no response (${submitTimeout}ms): ${detail}`);
        }
        throw new Error(detail || 'Scene analysis failed');
    }

    const explicitSuccess = typeof data?.success === 'boolean' ? data.success : null;
    const statusText = String(data?.status || '').trim().toLowerCase();
    const statusIndicatesError = statusText === 'error' || statusText === 'failed' || statusText === 'fail';

    if (explicitSuccess === false || statusIndicatesError) {
        const detail =
            data?.detail
            || data?.message
            || data?.error
            || data?.reason
            || 'Scene analysis failed';
        throw new Error(String(detail));
    }

    return data;
};

export const fetchPrompt = async (filename) => {
    const response = await api.get(`/prompts/${filename}`);
    return response.data;
};

export const fetchPromptSkills = async () => {
    const response = await api.get('/prompts/skills');
    return response.data;
};

export const fetchPromptSkillDetail = async (skillId) => {
    const response = await api.get(`/prompts/skills/${encodeURIComponent(skillId)}`);
    return response.data;
};

export const fetchMe = async () => {
    return runSingleFlight('GET:/users/me', async () => {
        const response = await api.get('/users/me');
        return response.data;
    });
};

export const updateMyProfile = async (payload) => {
    const response = await api.put('/users/me/profile', payload || {});
    return response.data;
};

export const updateMyPassword = async (payload) => {
    const response = await api.put('/users/me/password', payload || {});
    return response.data;
};

export const uploadMyAvatar = async (file) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post('/users/me/avatar', form, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

// Prompt Helper Export
export const injectEntityFeatures = (prompt, entities = []) => {
    let text = prompt || '';

    const regex = /[\[【\{｛]([\s\S]*?)[\]】\}｝]/g;

    text = text.replace(regex, (match, name, offset, source) => {
        const cleanKey = normalizeEntityToken(name);
        if (!cleanKey) return match;

        const tail = source.slice(offset + match.length);
        if (/^['’]s\b/i.test(tail)) return match;
        if (/^\s*[\(（]/.test(tail)) return match;

        const safeEntities = Array.isArray(entities) ? entities : [];
        const entity = safeEntities.find(e => {
            const cn = normalizeEntityToken(e?.name || '');
            const en = normalizeEntityToken(e?.name_en || '');

            let fallbackEn = '';
            if (!en && e?.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) {
                    fallbackEn = normalizeEntityToken(enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0]);
                }
            }

            return cn === cleanKey || en === cleanKey || fallbackEn === cleanKey;
        });

        if (!entity) return match;

        const rawDesc = entity.anchor_description || entity.description || '';
        const cleanDesc = String(rawDesc).replace(/[\r\n]+/g, ' ').trim().substring(0, 300);
        return cleanDesc ? `${match}(${cleanDesc})` : match;
    });

    return text;
};

// Billing API
export const getBillingOptions = async () => (await api.get('/billing/options')).data;
export const getBillingFeaturePricing = async () => (await api.get('/billing/feature-pricing')).data;
export const updateBillingFeaturePricing = async (featurePricing) => (await api.put('/billing/feature-pricing', { feature_pricing: featurePricing || {} })).data;
export const getBillingDefaultApiPricing = async () => (await api.get('/billing/default-api-pricing')).data;
export const updateBillingDefaultApiPricing = async (defaultApiPricing, contentFallbackPricing) => {
    const payload = { default_api_pricing: defaultApiPricing || {} };
    if (contentFallbackPricing !== undefined) {
        payload.content_fallback_pricing = contentFallbackPricing;
    }
    return (await api.put('/billing/default-api-pricing', payload)).data;
};
export const getAdminUsersPage = async (page = 1, pageSize = 20) => (
    await api.get(`/users/page?page=${encodeURIComponent(page)}&page_size=${encodeURIComponent(pageSize)}`)
).data;
export const getAgentToolPolicy = async () => (await api.get('/settings/system/agent/tools-policy')).data;
export const updateAgentToolPolicy = async (payload = {}) => (await api.put('/settings/system/agent/tools-policy', payload || {})).data;
export const getBillingRuleResetConfigManage = async () => (await api.get('/settings/system/manage/billing-rules/reset-config')).data;
export const updateBillingRuleResetConfigManage = async (payload = {}) => (await api.put('/settings/system/manage/billing-rules/reset-config', payload || {})).data;
export const getSystemAIAssistantAnalyze = async (payload = {}) => (await api.post('/settings/system/ai-assistant/analyze', payload || {})).data;
export const getSystemAIAssistantApply = async (payload = {}) => (await api.post('/settings/system/ai-assistant/apply', payload || {})).data;
export const aiAssistantExchangeRate = async (payload = {}) => (await api.post('/settings/system/ai-assistant/tools/exchange-rate', payload || {})).data;
export const aiAssistantFetchPricing = async (payload = {}) => (await api.post('/settings/system/ai-assistant/tools/fetch-pricing', payload || {})).data;
export const aiAssistantAnalyzeSupplierFeatures = async (payload = {}) => (await api.post('/settings/system/ai-assistant/tools/analyze-supplier-features', payload || {})).data;
export const aiAssistantApplySupplierFeatures = async (payload = {}) => (await api.post('/settings/system/ai-assistant/tools/apply-supplier-features', payload || {})).data;
export const fetchKiePricingManage = async (payload = {}) => (await api.post('/settings/system/manage/kie-pricing/fetch', payload || {})).data;
export const generateKiePricingRulesManage = async (payload = {}) => (await api.post('/settings/system/manage/kie-pricing/generate', payload || {})).data;
export const applyKiePricingRulesManage = async (payload = {}) => (await api.post('/settings/system/manage/kie-pricing/apply', payload || {})).data;
export const getTransactions = async (limit=100, userId=null) => {
    let url = `/billing/transactions?limit=${limit}`;
    if (userId) url += `&user_id=${userId}`;
    const key = buildSingleFlightKey('GET:/billing/transactions', { limit, userId: userId || '' });
    return runSingleFlight(key, async () => (await api.get(url)).data);
};
export const updateUserCredits = async (userId, credits, mode='set') => (await api.post(`/billing/users/${userId}/credits`, { amount: credits, mode })).data;
