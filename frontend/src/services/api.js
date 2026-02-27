import axios from 'axios';
import { API_URL, BASE_URL } from '../config';

// Use API_URL from config which supports production env vars
export const api = axios.create({
  baseURL: API_URL,
  timeout: 300000, // 5 minutes timeout for long generation tasks
});

const buildApiErrorMessage = (error) => {
    const responseData = error?.response?.data;
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
        provider: String(payload?.provider || '').trim(),
        model: String(payload?.model || '').trim(),
        ref_image_url: normalizeRefImageValue(payload?.ref_image_url),
        project_id: payload?.project_id ?? null,
        shot_id: payload?.shot_id ?? null,
        shot_number: payload?.shot_number ?? null,
        shot_name: payload?.shot_name ?? null,
        entity_name: payload?.entity_name ?? null,
        subject_name: payload?.subject_name ?? null,
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
    const response = await api.post('/agent/command', {
        query,
        context,
        history
    });
    return response.data;
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
    const response = await api.post(`/projects/${projectId}/story_generator/global`, payload);
    return response.data;
}

export const analyzeProjectNovel = async (projectId, payload) => {
    const response = await api.post(`/projects/${projectId}/story_generator/analyze_novel`, payload);
    return response.data;
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

// Episodes
export const fetchEpisodes = async (projectId) => {
    const response = await api.get(`/projects/${projectId}/episodes`);
    return response.data;
}

export const createEpisode = async (projectId, data) => {
    const response = await api.post(`/projects/${projectId}/episodes`, data);
    return response.data;
}

export const updateEpisode = async (episodeId, data) => {
    const response = await api.put(`/episodes/${episodeId}`, data);
    return response.data;
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

export const generateSceneShots = async (sceneId, promptData = null) => {
    // This now returns the Staging result (timestamp, content=[]), not the applied shots
    const payloadMeta = {
        hasUserPrompt: Boolean(promptData?.user_prompt),
        hasSystemPrompt: Boolean(promptData?.system_prompt),
        userPromptLen: String(promptData?.user_prompt || '').length,
        systemPromptLen: String(promptData?.system_prompt || '').length,
    };
    try {
        const response = await api.post(`/scenes/${sceneId}/ai_generate_shots`, promptData);
        const data = response?.data;
        return data;
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
    const response = await api.post(`/episodes/${episodeId}/character_profiles/generate`, payload);
    return response.data;
}

// Project Character Canon (Overview)
export const generateProjectCharacterProfile = async (projectId, payload) => {
    const response = await api.post(`/projects/${projectId}/character_profiles/generate`, payload);
    return response.data;
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

// Episode Story Generator (Global/Episode)
export const generateEpisodeStory = async (episodeId, payload) => {
    const response = await api.post(`/episodes/${episodeId}/story_generator`, payload);
    return response.data;
}

// Episode Story Generator draft input persistence (no LLM call)
export const saveEpisodeStoryGeneratorInput = async (episodeId, payload) => {
    const response = await api.put(`/episodes/${episodeId}/story_generator/input`, payload);
    return response.data;
}

export const generateEpisodeScenes = async (episodeId, payload) => {
    const response = await api.post(`/episodes/${episodeId}/script_generator/scenes`, payload);
    return response.data;
}

// Project Script Generator (Episodes -> Script drafts)
export const generateProjectEpisodeScripts = async (projectId, payload) => {
    const response = await api.post(
        `/projects/${projectId}/script_generator/episodes/scripts`,
        payload,
        { timeout: 30 * 60 * 1000 }
    );
    return response.data;
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


// Generation
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const shouldAutoDownloadByUserSetting = () => {
    try {
        const raw = localStorage.getItem('generationConfig');
        if (!raw) return true;
        const parsed = JSON.parse(raw);
        if (parsed && Object.prototype.hasOwnProperty.call(parsed, 'autoDownloadLocal')) {
            return !!parsed.autoDownloadLocal;
        }
    } catch {
        // ignore parsing issues and fallback to default enabled behavior
    }
    return true;
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

const pollImageJobUntilDone = async (jobId, { timeoutMs = 10 * 60 * 1000, pollIntervalMs = 2000 } = {}) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        const response = await api.get(`/generate/image/jobs/${jobId}`);
        const data = response?.data || {};
        const status = String(data.status || '').toLowerCase();

        if (status === 'succeeded') {
            return data.result || {};
        }
        if (status === 'failed') {
            throw new Error(data.error || 'Image generation job failed');
        }

        await sleep(pollIntervalMs);
    }

    throw new Error('Image generation timed out while polling job status');
};

export const generateImage = async (prompt, provider = null, ref_image_url = null, options = {}) => {
    const payload = { prompt, provider, ref_image_url, ...options };
    const idempotencyKey = getOrCreateImageSubmitIdempotencyKey(payload, options?.idempotency_key);
    const autoDownloadLocal = Object.prototype.hasOwnProperty.call(options || {}, 'auto_download_local')
        ? options?.auto_download_local !== false
        : shouldAutoDownloadByUserSetting();

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
        if (autoDownloadLocal && response?.data?.url) {
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

    const result = await pollImageJobUntilDone(jobId, {
        timeoutMs: Number(options?.job_timeout_ms || 10 * 60 * 1000),
        pollIntervalMs: Number(options?.job_poll_interval_ms || 2000),
    });

    if (autoDownloadLocal && result?.url) {
        try {
            await downloadMediaToLocal(result.url, `generated_image_${Date.now()}.png`);
        } catch (downloadError) {
            console.warn('[generateImage] auto local download failed:', downloadError);
        }
    }

    return result;
}

export const generateVideo = async (prompt, provider = null, ref_image_url = null, last_frame_url = null, duration = 5, options = {}, keyframes = []) => {
    const response = await api.post('/generate/video', { prompt, provider, ref_image_url, last_frame_url, duration, keyframes, ...options });
    const autoDownloadLocal = Object.prototype.hasOwnProperty.call(options || {}, 'auto_download_local')
        ? options?.auto_download_local !== false
        : shouldAutoDownloadByUserSetting();
    if (autoDownloadLocal && response?.data?.url) {
        try {
            await downloadMediaToLocal(response.data.url, `generated_video_${Date.now()}.mp4`);
        } catch (downloadError) {
            console.warn('[generateVideo] auto local download failed:', downloadError);
        }
    }
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
    const response = await api.get('/settings');
    return response.data;
}

export const getSettingDefaults = async () => {
    const response = await api.get('/settings/defaults');
    return response.data;
}

export const getSystemSettings = async () => {
    const response = await api.get('/settings/system');
    return response.data;
}

export const getSystemSettingsCatalog = async () => {
    const response = await api.get('/settings/system/catalog');
    return response.data;
}

export const selectSystemSetting = async (setting_id) => {
    const response = await api.post('/settings/system/select', { setting_id });
    return response.data;
}

export const getSystemSettingsManage = async () => {
    const response = await api.get('/settings/system/manage');
    return response.data;
}

export const createSystemSettingManage = async (data) => {
    const response = await api.post('/settings/system/manage', data);
    return response.data;
}

export const updateSystemSettingManage = async (settingId, data) => {
    const response = await api.post(`/settings/system/manage/${settingId}`, data);
    return response.data;
}

export const deleteSystemSettingManage = async (settingId) => {
    const response = await api.delete(`/settings/system/manage/${settingId}`);
    return response.data;
}

export const exportSystemSettingsManage = async () => {
    const response = await api.get('/settings/system/manage/export');
    return response.data;
}

export const importSystemSettingsManage = async (payload) => {
    const response = await api.post('/settings/system/manage/import', payload);
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

export const getAdminStorageUsage = async () => {
    const response = await api.get('/admin/storage-usage');
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
    const response = await api.post('/tools/translate', { q, from_lang, to_lang });
    return response.data;
};

export const refinePrompt = async (original_prompt, instruction, type = 'image') => {
    const response = await api.post('/tools/refine_prompt', { original_prompt, instruction, type });
    return response.data;
};

export const analyzeScene = async (scriptText, systemPrompt = null, projectMetadata = null, episodeId = null, analysisAttentionNotes = null, reuseSubjectAssets = null) => {
    const payload = { 
        text: scriptText,
        system_prompt: systemPrompt
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
    const response = await api.post('/analyze_scene', payload);
    return response.data;
};

export const fetchPrompt = async (filename) => {
    const response = await api.get(`/prompts/${filename}`);
    return response.data;
};

export const fetchMe = async () => {
    const response = await api.get('/users/me');
    return response.data;
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

    const normalizeEntityToken = (value) => {
        return String(value || '')
            .replace(/[（【〔［]/g, '(')
            .replace(/[）】〕］]/g, ')')
            .replace(/[“”"'‘’]/g, '')
            .replace(/^[\[\{【｛\(\s]+|[\]\}】｝\)\s]+$/g, '')
            .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
            .replace(/^@+/, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    };

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
export const getPricingRules = async () => (await api.get('/billing/rules')).data;
export const createPricingRule = async (data) => (await api.post('/billing/rules', data)).data;
export const syncPricingRules = async () => (await api.post('/billing/rules/sync')).data;
export const getBillingOptions = async () => (await api.get('/billing/options')).data;
export const updatePricingRule = async (id, data) => (await api.put(`/billing/rules/${id}`, data)).data;
export const deletePricingRule = async (id) => (await api.delete(`/billing/rules/${id}`)).data;
export const getTransactions = async (limit=100, userId=null) => {
    let url = `/billing/transactions?limit=${limit}`;
    if (userId) url += `&user_id=${userId}`;
    return (await api.get(url)).data;
};
export const updateUserCredits = async (userId, credits, mode='set') => (await api.post(`/billing/users/${userId}/credits`, { amount: credits, mode })).data;
