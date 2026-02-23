import axios from 'axios';
import { API_URL } from '../config';

console.log("Initializing API Helper with Base URL:", API_URL);

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


export const fetchSystemLogs = async (skip = 0, limit = 100) => {
    const response = await api.get(`/system/logs?skip=${skip}&limit=${limit}`);
    return response.data;
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
    console.log(`[API] updateShot ${shotId} payload:`, JSON.stringify(data, null, 2));
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
    console.log('[API] generateSceneShots request', { sceneId, payloadMeta });
    try {
        const response = await api.post(`/scenes/${sceneId}/ai_generate_shots`, promptData);
        const data = response?.data;
        console.log('[API] generateSceneShots response', {
            sceneId,
            status: response?.status,
            dataType: typeof data,
            keys: data && typeof data === 'object' ? Object.keys(data) : [],
            contentCount: Array.isArray(data?.content) ? data.content.length : null,
            hasRawText: Boolean(data?.raw_text),
            hasTimestamp: Boolean(data?.timestamp),
        });
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
export const generateImage = async (prompt, provider = null, ref_image_url = null, options = {}) => {
    const response = await api.post('/generate/image', { prompt, provider, ref_image_url, ...options });
    return response.data;
}

export const generateVideo = async (prompt, provider = null, ref_image_url = null, last_frame_url = null, duration = 5, options = {}, keyframes = []) => {
    console.log("[DEBUG API] generateVideo Prompt:", prompt);
    const response = await api.post('/generate/video', { prompt, provider, ref_image_url, last_frame_url, duration, keyframes, ...options });
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

export const apiLogin = async (username, password) => {
    console.log("Logging in via JSON endpoint (apiLogin)...");
    const response = await api.post('/login', {
        username,
        password
    });
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
    console.log(`[API CALL] analyzeEntityImage for ${entityId}`);
    try {
        const response = await api.post(`/entities/${entityId}/analyze`);
        console.log(`[API SUCCESS] analyzeEntityImage response:`, response);
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

export const translateText = async (q, from_lang = 'en', to_lang = 'zh') => {
    const response = await api.post('/tools/translate', { q, from_lang, to_lang });
    return response.data;
};

export const refinePrompt = async (original_prompt, instruction, type = 'image') => {
    const response = await api.post('/tools/refine_prompt', { original_prompt, instruction, type });
    return response.data;
};

export const analyzeScene = async (scriptText, systemPrompt = null, projectMetadata = null, episodeId = null, analysisAttentionNotes = null, reuseSubjectAssets = null) => {
    console.log("[API] analyzeScene called", { hasMetadata: !!projectMetadata, episodeId, hasAttentionNotes: !!analysisAttentionNotes, reuseSubjectCount: Array.isArray(reuseSubjectAssets) ? reuseSubjectAssets.length : 0 });
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
