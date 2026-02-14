import React, { createContext, useState, useEffect } from 'react';
import { getSettings } from '../services/api';

export const StoreContext = createContext();

export const StoreProvider = ({ children }) => {
    // LLM Config
    const [llmConfig, setLLMConfig] = useState(() => {
        try {
            const saved = localStorage.getItem('llmConfig');
            return saved ? JSON.parse(saved) : null;
        } catch { return null; }
    });

    // Saved Provider Configs (map of provider -> config)
    const [savedConfigs, setSavedConfigs] = useState(() => {
        try {
            const saved = localStorage.getItem('savedProviderConfigs');
            return saved ? JSON.parse(saved) : {};
        } catch { return {}; }
    });

    // Generation Config
    const [generationConfig, setGenerationConfigState] = useState(() => {
        try {
            const saved = localStorage.getItem('generationConfig');
            return saved ? JSON.parse(saved) : null;
        } catch { return null; }
    });

    // Saved Tool Configs
    const [savedToolConfigs, setSavedToolConfigs] = useState(() => {
        try {
            const saved = localStorage.getItem('savedToolConfigs');
            return saved ? JSON.parse(saved) : {};
        } catch { return {}; }
    });

    useEffect(() => {
        localStorage.setItem('llmConfig', JSON.stringify(llmConfig));
    }, [llmConfig]);

    useEffect(() => {
        localStorage.setItem('savedProviderConfigs', JSON.stringify(savedConfigs));
    }, [savedConfigs]);

    useEffect(() => {
        localStorage.setItem('generationConfig', JSON.stringify(generationConfig));
    }, [generationConfig]);

    useEffect(() => {
        localStorage.setItem('savedToolConfigs', JSON.stringify(savedToolConfigs));
    }, [savedToolConfigs]);

    const refreshSettings = async () => {
        try {
            const token = localStorage.getItem('token');
            if (!token) return;

            const settings = await getSettings();
            if (!settings || !Array.isArray(settings)) return;

            const newSavedConfigs = { ...savedConfigs };
            const newSavedToolConfigs = { ...savedToolConfigs };
            
            let activeLLMConfig = null;
            let activeImageModel = null;
            let activeVideoModel = null;
            let activeVisionModel = null;

            settings.forEach(s => {
                const prov = s.provider ? s.provider.toLowerCase() : "";
                const cat = s.category;

                if (cat === 'LLM') {
                    // Map to savedConfigs
                    // Specific mapping for providers if needed, otherwise use prov as key
                    if (['openai', 'doubao', 'ollama', 'deepseek', 'grsai'].includes(prov)) {
                        newSavedConfigs[prov] = {
                            apiKey: s.api_key,
                            endpoint: s.base_url,
                            model: s.model
                        };
                        
                        if (s.is_active) {
                            activeLLMConfig = {
                                provider: prov,
                                apiKey: s.api_key,
                                endpoint: s.base_url,
                                model: s.model
                            };
                        }
                    }
                } else if (cat === 'Image' || cat === 'Video' || cat === 'Vision') {
                    // Map to savedToolConfigs using Tool Name
                    let toolName = null;
                    if (cat === 'Image') {
                        if (prov === 'stability') toolName = "Stable Diffusion";
                        else if (prov === 'midjourney') toolName = "Midjourney";
                        else if (prov === 'openai') toolName = "DALL-E 3";
                        else if (prov === 'doubao') toolName = "Doubao";
                        else if (prov === 'tencent') toolName = "Tencent Hunyuan";
                        else if (prov === 'grsai') toolName = "Grsai-Image";
                    } else if (cat === 'Video') {
                        if (prov === 'runway') toolName = "Runway";
                        else if (prov === 'wanxiang') toolName = "Wanxiang";
                        else if (prov === 'doubao') toolName = "Doubao Video";
                        else if (prov === 'vidu') toolName = "Vidu (Video)";
                        else if (prov === 'grsai') toolName = "Grsai-Video";
                    } else if (cat === 'Vision') {
                        if (prov === 'grsai') toolName = "Grsai-Vision";
                    }

                    if (toolName) {
                        newSavedToolConfigs[toolName] = {
                            apiKey: s.api_key,
                            endpoint: s.base_url,
                            model: s.model,
                            webHook: s.config?.webHook,
                            width: s.config?.width,
                            height: s.config?.height
                        };
                        
                        if (s.is_active) {
                            if (cat === 'Image') activeImageModel = toolName;
                            if (cat === 'Video') activeVideoModel = toolName;
                            if (cat === 'Vision') activeVisionModel = toolName;
                        }
                    }
                }
            });

            console.log("Refreshed settings from backend");
            setSavedConfigs(newSavedConfigs);
            setSavedToolConfigs(newSavedToolConfigs);
            
            // Restore active LLM
            if (activeLLMConfig) {
                setLLMConfig(activeLLMConfig);
            }
            
            // Restore active Generation Models
            if (activeImageModel || activeVideoModel || activeVisionModel) {
                setGenerationConfigState(prev => ({
                    ...(prev || {}),
                    imageModel: activeImageModel || (prev?.imageModel || "Midjourney"),
                    videoModel: activeVideoModel || (prev?.videoModel || "Runway"),
                    visionModel: activeVisionModel || (prev?.visionModel || "Grsai-Vision")
                }));
            }

        } catch (e) {
            console.warn("Failed to refresh settings from backend (may be offline or logged out)", e);
        }
    };

    // Auto-refresh logic: Run once on mount to try to sync if token exists
    useEffect(() => {
        refreshSettings();
    }, []);

    const saveProviderConfig = (provider, config) => {
        setSavedConfigs(prev => ({
            ...prev,
            [provider]: config
        }));
    };

    const setGenerationConfig = (config) => {
        setGenerationConfigState(config);
    };

    const saveToolConfig = (toolName, config) => {
        setSavedToolConfigs(prev => ({
            ...prev,
            [toolName]: config
        }));
    };

    return (
        <StoreContext.Provider value={{
            llmConfig, setLLMConfig,
            savedConfigs, saveProviderConfig,
            generationConfig, setGenerationConfig,
            savedToolConfigs, saveToolConfig,
            refreshSettings
        }}>
            {children}
        </StoreContext.Provider>
    );
};
