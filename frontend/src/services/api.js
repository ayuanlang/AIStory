import axios from 'axios';
import { API_URL } from '../config';

console.log("Initializing API Helper with Base URL:", API_URL);

// Use API_URL from config which supports production env vars
export const api = axios.create({
  baseURL: API_URL,
  timeout: 300000, // 5 minutes timeout for long generation tasks
});

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

// Project Story Generator (Global/Project) draft input persistence (no LLM call)
export const saveProjectStoryGeneratorGlobalInput = async (projectId, payload) => {
    const response = await api.put(`/projects/${projectId}/story_generator/global/input`, payload);
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
export const fetchScenes = async (episodeId) => {
    const response = await api.get(`/episodes/${episodeId}/scenes`);
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

// Shots
export const fetchEpisodeShots = async (episodeId) => {
    const response = await api.get(`/episodes/${episodeId}/shots`);
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
    const response = await api.post(`/scenes/${sceneId}/ai_generate_shots`, promptData);
    return response.data;
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

export const analyzeScene = async (scriptText, systemPrompt = null, projectMetadata = null, episodeId = null) => {
    console.log("[API] analyzeScene called", { hasMetadata: !!projectMetadata, episodeId });
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
    let modified = false;
    let text = prompt;
    
    // Regular expression to find {Name} pattern
    const regex = /\{([^}]+)\}/g;
    
    text = text.replace(regex, (match, name) => {
        const entity = entities.find(e => 
            (e.name && e.name.toLowerCase() === name.toLowerCase()) || 
            (e.name_en && e.name_en.toLowerCase() === name.toLowerCase())
        );

        if (entity && entity.description) {
            modified = true;
            // Return format: {Name}(description)
            // Or just inject description? 
            // Usually we want to keep the name for reference but add description.
            // Let's use standard round bracket injection: {Name}(visual description)
            
            // Clean description to avoid nested brackets issues or newlines
            const cleanDesc = entity.description.replace(/[\r\n]+/g, ' ').substring(0, 300); // Limit length
            return `{${name}}(${cleanDesc})`;
        }
        return match; // No change if not found
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
