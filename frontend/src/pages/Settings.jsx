import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useStore } from '@/lib/store';
import { Save, Info, Upload, Download, Coins, History } from 'lucide-react';
import { API_URL } from '@/config';
import { updateSetting, getSettings, getTransactions, fetchMe } from '../services/api';
import RechargeModal from '../components/RechargeModal'; // Import RechargeModal

const Settings = () => {
    const location = useLocation();
    const { llmConfig, setLLMConfig, savedConfigs, saveProviderConfig, addLog, generationConfig, setGenerationConfig, savedToolConfigs, saveToolConfig } = useStore();
    
    // Internal state for form
    const [provider, setProvider] = useState("openai");
    const [apiKey, setApiKey] = useState("");
    const [endpoint, setEndpoint] = useState("");
    const [model, setModel] = useState("");
    
    // Hidden file input ref
    const fileInputRef = useRef(null);

    // State for generation supplements
    const [charSupplements, setCharSupplements] = useState("");
    const [sceneSupplements, setSceneSupplements] = useState("");

    // State for generation models
    const [imageModel, setImageModel] = useState("Midjourney");
    const [videoModel, setVideoModel] = useState("Runway");
    const [visionModel, setVisionModel] = useState("Grsai-Vision"); // New Vision Model State
    const [promptLanguage, setPromptLanguage] = useState("mixed");

    // State for Tool Configs (Active inputs)
    const [imgToolKey, setImgToolKey] = useState("");
    const [imgToolEndpoint, setImgToolEndpoint] = useState("");
    const [imgToolModel, setImgToolModel] = useState("");
    const [imgToolWidth, setImgToolWidth] = useState("");
    const [imgToolHeight, setImgToolHeight] = useState("");

    const [vidToolKey, setVidToolKey] = useState("");
    const [vidToolEndpoint, setVidToolEndpoint] = useState("");
    const [vidToolModel, setVidToolModel] = useState("");
    const [vidEndpointMap, setVidEndpointMap] = useState({}); // Model-specific endpoints

    const [visToolKey, setVisToolKey] = useState(""); // Vision Tool Key
    const [visToolEndpoint, setVisToolEndpoint] = useState(""); // Vision Tool Endpoint
    const [visToolModel, setVisToolModel] = useState(""); // Vision Tool Model
    
    // WebHooks
    const [imgToolWebHook, setImgToolWebHook] = useState("");
    const [vidToolWebHook, setVidToolWebHook] = useState("");
    const [vidToolDraft, setVidToolDraft] = useState(false);

    // State for Baidu Translation
    const [baiduToken, setBaiduToken] = useState("");

    // State for tabs
    const [activeTab, setActiveTab] = useState('api');
    
    // Billing State
    const [userCredits, setUserCredits] = useState(0);
    const [transactions, setTransactions] = useState([]);
    const [isBillingLoading, setIsBillingLoading] = useState(false);
    const [showRecharge, setShowRecharge] = useState(false); // Recharge Modal State

    // Unified Top Up entry: support /settings?tab=billing and cross-app 402 redirects.
    useEffect(() => {
        const params = new URLSearchParams(location.search || '');
        const tab = params.get('tab');
        if (tab === 'billing') {
            setActiveTab('billing');
        }

        // If we navigated here due to insufficient credits, auto-open the modal.
        let shouldOpen = false;
        try {
            shouldOpen = sessionStorage.getItem('OPEN_RECHARGE_MODAL') === '1';
            if (shouldOpen) sessionStorage.removeItem('OPEN_RECHARGE_MODAL');
        } catch {
            // ignore
        }

        if (shouldOpen) {
            setActiveTab('billing');
            setShowRecharge(true);
        }
    }, [location.search]);

    useEffect(() => {
        const fn = () => {
            setActiveTab('billing');
            setShowRecharge(true);
        };
        window.addEventListener('SHOW_RECHARGE_MODAL', fn);
        return () => window.removeEventListener('SHOW_RECHARGE_MODAL', fn);
    }, []);

    // Helper: Refresh Billing Data
    const refreshBilling = () => {
        setIsBillingLoading(true);
        Promise.all([fetchMe(), getTransactions()]).then(([userRes, transRes]) => {
            if (userRes && userRes.credits !== undefined) {
                 setUserCredits(userRes.credits);
            }
            if (transRes) {
                 // Ensure sorted by ID desc to show recent first
                 const sorted = [...transRes].sort((a, b) => b.id - a.id);
                 setTransactions(sorted);
            }
        }).catch(err => {
            console.error("Failed to load billing data", err);
        }).finally(() => setIsBillingLoading(false));
    };

    useEffect(() => {
        if (activeTab === 'billing') {
            refreshBilling();
        } else {
             // For non-billing tabs, we still want to load general settings
             // ... existing logic ...
        }
    }, [activeTab]);

    // UI Notification State
    const [notification, setNotification] = useState(null);

    const showNotification = (message, type = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    };

    // --- Import / Export Handlers ---
    const handleExportSettings = async () => {
        try {
            const data = await getSettings();
            if (!data) {
                showNotification("No settings to export.", "error");
                return;
            }
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `aistory_settings_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            window.URL.revokeObjectURL(url);
            showNotification("Settings exported successfully!", "success");
        } catch (e) {
            console.error("Export failed", e);
            showNotification("Failed to export settings", "error");
        }
    };

    const handleImportClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const json = JSON.parse(event.target.result);
                if (!Array.isArray(json)) {
                    showNotification("Invalid settings file format (must be array).", "error");
                    return;
                }

                addLog("Starting settings import...", "process");
                
                let successCount = 0;
                for (const item of json) {
                    if (item.provider && item.category) {
                        // 1. Update Backend
                        await updateSetting({
                            ...item,
                            id: undefined // Create or update logic handled by backend usually, but here updateSetting relies on provider matching often
                        });

                        // 2. Update Local Store (Sync)
                        // Map backend item back to local format
                        const configData = {
                            apiKey: item.api_key || "",
                            endpoint: item.base_url || item.config?.endpoint || "",
                            model: item.model || "",
                            width: item.config?.width,
                            height: item.config?.height,
                            webHook: item.config?.webHook
                        };

                        // Store logic
                        if (item.category === 'LLM') {
                            // Map backend provider back to frontend if needed
                            // (Simplified: assuming mapped names match or are close enough for now)
                            saveProviderConfig(item.provider, configData);
                        } else if (item.category === 'Image' || item.category === 'Video') {
                            // For tools, we use the display name as key mostly? 
                            // This is tricky because backend stores "grsai" but frontend uses "Grsai-Image"
                            // We might need to rely on the backend provider + category to map back.
                            // Or just rely on the user refreshing/re-selecting. 
                            
                            // Best effort mapping: 
                            // If user sets "Grsai-Image", backend sees provider="grsai", category="Image"
                            // So we can try to save to "Grsai-Image" if we know the mapping?
                            // Actually, let's just update the Backend for now to ensure functional correctness.
                            // The sync downstream is a bonus.
                        }
                        successCount++;
                    }
                }

                showNotification(`Successfully imported settings!`, "success");
                addLog(`Imported ${successCount} settings items.`, "success");
                
                // Refresh local view data (Baidu token etc)
                const fresh = await getSettings();
                const baidu = fresh.find(s => s.provider === 'baidu_translate' || s.provider === 'baidu');
                if (baidu) setBaiduToken(baidu.api_key || "");
                
                // Re-trigger load for LLM if it matches current
                // (Optional refinement)

            } catch (err) {
                console.error("Import parsing failed", err);
                showNotification("Failed to parse settings file.", "error");
            }
            // Reset input
            if (fileInputRef.current) fileInputRef.current.value = "";
        };
        reader.readAsText(file);
    };
    
    // Load backend settings
    useEffect(() => {
        const fetchSettings = async () => {
             try {
                const data = await getSettings();
                if (data) {
                    // Find existing Baidu Translation setting
                    const baiduSetting = data.find(s => s.provider === 'baidu_translate' || s.provider === 'baidu');
                    if (baiduSetting) {
                        setBaiduToken(baiduSetting.api_key || "");
                    }
                }
             } catch (e) {
                 console.error("Failed to load backend settings", e);
             }
        }
        fetchSettings();
    }, []);

    const handleSaveTranslation = async () => {
         try {
            // 1. Get List to find ID (if exists)
            const listData = await getSettings();
            let existingId = undefined;
            if (listData) {
                const existing = listData.find(s => s.provider === 'baidu_translate' || s.provider === 'baidu');
                if (existing) existingId = existing.id;
            }

            // 2. Post Update/Create
            const payload = {
                id: existingId,
                provider: 'baidu_translate',
                category: 'Tools',
                api_key: baiduToken,
                is_active: true
            };

            await updateSetting(payload);
            addLog("Translation settings saved", "success");
            showNotification("Translation settings saved successfully!", "success");
         } catch (e) {
             console.error(e);
             addLog("Error saving translation settings", "warning");
             showNotification("Error saving translation settings", "error");
         }
    };

    // Initialize from the currently active config or saved configs
    useEffect(() => {
        if (llmConfig) {
            setProvider(llmConfig.provider || "openai");
            setApiKey(llmConfig.apiKey || "");
            setEndpoint(llmConfig.endpoint || "");
            setModel(llmConfig.model || "");
        } else {
             // Fallback: use default provider snapshot when active config is not present
             const fallbackProvider = "openai";
             setProvider(fallbackProvider);
             const saved = savedConfigs[fallbackProvider];
             if (saved) {
                 setApiKey(saved.apiKey || "");
                 setEndpoint(saved.endpoint || "");
                 setModel(saved.model || "");
             } else {
                 setApiKey("");
                 setEndpoint("https://api.openai.com/v1");
                 setModel("");
             }
        }
    }, [llmConfig, savedConfigs]);

    // Initialize generation config & handle saved tool configs updates
    useEffect(() => {
        if (generationConfig) {
            setCharSupplements(generationConfig.characterSupplements || "");
            setSceneSupplements(generationConfig.sceneSupplements || "");
            setPromptLanguage(generationConfig.prompt_language || "mixed");
            
            const iModel = generationConfig.imageModel || "Midjourney";
            const vModel = generationConfig.videoModel || "Runway";
            const visModel = generationConfig.visionModel || "Grsai-Vision";

            setImageModel(iModel);
            setVideoModel(vModel);
            setVisionModel(visModel);
            
            // Load saved tool configs
            loadToolConfig(iModel, 'image');
            loadToolConfig(vModel, 'video');
            loadToolConfig(visModel, 'vision');
        } else {
             // Even if no generationConfig, we might have defaults set in state (e.g. Midjourney/Runway)
             // and we should load their configs if savedToolConfigs updates
             loadToolConfig(imageModel, 'image');
             loadToolConfig(videoModel, 'video');
             loadToolConfig(visionModel || "Grsai-Vision", 'vision');
        }
    }, [generationConfig, savedToolConfigs]);

    const loadToolConfig = (toolName, type) => {
        const saved = savedToolConfigs[toolName];
        if (type === 'image') {
            if (saved) {
                setImgToolKey(saved.apiKey || "");
                // Auto-correct legacy Grsai endpoint
                let ep = saved.endpoint || "";
                if (toolName === "Grsai-Image" && (ep.includes("api.grsai.com") || ep.includes("grsai.com"))) {
                     ep = "https://grsai.dakka.com.cn";
                }
                setImgToolEndpoint(ep);
                
                setImgToolModel(saved.model || "");
                setImgToolWidth(saved.width || "1024");
                setImgToolHeight(saved.height || "1024");
                setImgToolWebHook(saved.webHook || "");
            } else {
                 // Defaults for known tools
                 if (toolName === "Doubao") {
                     setImgToolKey("");
                     setImgToolEndpoint("https://ark.cn-beijing.volces.com/api/v3");
                     setImgToolModel("doubao-seedream-4-5-251128");
                     setImgToolWidth("1024");
                     setImgToolHeight("1024");
                     setImgToolWebHook("");
                 } else if (toolName === "Stable Diffusion") {
                     setImgToolKey("");
                     setImgToolEndpoint("https://api.stability.ai");
                     setImgToolModel("stable-diffusion-xl-1024-v1-0");
                     setImgToolWidth("1024");
                     setImgToolHeight("1024");
                     setImgToolWebHook("");
                 } else if (toolName === "Grsai-Image") {
                     setImgToolKey("");
                     setImgToolEndpoint("https://grsai.dakka.com.cn");
                     setImgToolModel("sora-image");
                     setImgToolWidth("1024");
                     setImgToolHeight("1024");
                     setImgToolWebHook("-1");
                 } else if (toolName === "Tencent Hunyuan") {
                     setImgToolKey("");
                     setImgToolEndpoint("https://aiart.tencentcloudapi.com");
                     setImgToolModel("201"); // Default Style ID
                     setImgToolWidth("1024");
                     setImgToolHeight("768");
                 } else {
                     setImgToolKey("");
                     setImgToolEndpoint("");
                     setImgToolModel("");
                     setImgToolWidth("");
                     setImgToolHeight("");
                     setImgToolWebHook("");
                 }
            }
        } else if (type === 'video') {
             if (saved) {
                setVidToolKey(saved.apiKey || "");
                
                const epMap = saved.endpointMap || {};
                setVidEndpointMap(epMap);

                // Auto-correct legacy Grsai endpoint
                let ep = saved.endpoint || "";
                if (toolName === "Grsai-Video" && (ep.includes("api.grsai.com") || ep.includes("grsai.com"))) {
                     ep = "https://grsai.dakka.com.cn";
                }
                
                // Use mapped endpoint if available
                if (saved.model && epMap[saved.model]) {
                    ep = epMap[saved.model];
                }
                
                setVidToolEndpoint(ep);

                setVidToolModel(saved.model || "");
                setVidToolWebHook(saved.webHook || "");
                setVidToolDraft(saved.draft || false);
             } else {
                 setVidEndpointMap({});
                 if (toolName === "Doubao Video") {
                    setVidToolKey("");
                    setVidToolEndpoint("https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks");
                    setVidToolModel("doubao-seedance-1-5-pro-251215");
                    setVidToolWebHook("");
                    setVidToolDraft(false);
                 } else if (toolName === "Wanxiang") {
                     setVidToolKey("");
                     setVidToolEndpoint("https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis");
                     setVidToolModel("wanx2.1-kf2v-plus");
                     setVidToolWebHook("");
                 } else if (toolName === "Grsai-Video") {
                    setVidToolKey("");
                    setVidToolEndpoint("https://grsai.dakka.com.cn");
                    setVidToolModel("sora-2");
                    setVidToolWebHook("-1");
                 } else if (toolName === "Vidu (Video)") {
                    setVidToolKey("");
                    setVidToolEndpoint("https://api.vidu.studio/open/v1/creation");
                    setVidToolModel("vidu2.0");
                    setVidToolWebHook("");
                 } else if (toolName === "Grsai-Video (Upload)") {
                    setVidToolKey("");
                    setVidToolEndpoint("https://grsai.dakka.com.cn/api/v1/video/generate/upload");
                    setVidToolModel("sora-2");
                    setVidToolWebHook("");
                 } else {
                    setVidToolKey("");
                    setVidToolEndpoint("");
                    setVidToolModel("");
                    setVidToolWebHook("");
                    setVidToolDraft(false);
                 }
             }
        } else if (type === 'vision') {
             if (saved) {
                setVisToolKey(saved.apiKey || "");
                setVisToolEndpoint(saved.endpoint || "");
                setVisToolModel(saved.model || "");
                // Defaults for Grsai-Vision if specific fields missing (migration)
                 if (toolName === "Grsai-Vision" && !saved.endpoint) {
                     setVisToolEndpoint("https://grsaiapi.com/v1/chat/completions");
                 }
                 if (toolName === "Grsai-Vision" && !saved.model) {
                     setVisToolModel("gemini-3-pro");
                 }
            } else {
                if (toolName === "Grsai-Vision") {
                     setVisToolKey("");
                     setVisToolEndpoint("https://grsaiapi.com/v1/chat/completions");
                     setVisToolModel("gemini-3-pro");
                }
            }
        }
    }

    const handleVidSubModelChange = (newModel) => {
        setVidToolModel(newModel);
        // If we have a stored endpoint for this model, switch to it, otherwise keep current (or reset? user likely wants stickiness)
        // Better: if map has it, use it. If not, maybe keep current base endpoint?
        // Let's assume user wants to reuse current endpoint if not overridden.
        if (vidEndpointMap[newModel]) {
            setVidToolEndpoint(vidEndpointMap[newModel]);
        }
    };

    const handleVidEndpointChange = (newEndpoint) => {
        setVidToolEndpoint(newEndpoint);
        if (vidToolModel) {
            setVidEndpointMap(prev => ({
                ...prev,
                [vidToolModel]: newEndpoint
            }));
        }
    };

    const handleImageToolChange = (newTool) => {
        setImageModel(newTool);
        loadToolConfig(newTool, 'image');
    }

    const handleVideoToolChange = (newTool) => {
        setVideoModel(newTool);
        loadToolConfig(newTool, 'video');
    }

    const handleProviderChange = (newProvider) => {
        setProvider(newProvider);
        
        // Load saved config for this provider
        const saved = savedConfigs[newProvider];
        if (saved) {
            setApiKey(saved.apiKey || "");
            
            // Auto-correct legacy Grsai endpoint for LLM
            let ep = saved.endpoint || "";
            if (newProvider === "grsai" && (ep.includes("api.grsai.com") || ep.includes("grsai.com"))) {
                    ep = "https://grsai.dakka.com.cn";
            }
            setEndpoint(ep);
            
            setModel(saved.model || "");
        } else {
            // Defaults based on provider
            setApiKey("");
            setModel("");
            if (newProvider === "openai") {
                 setEndpoint("https://api.openai.com/v1");
            } else if (newProvider === "ollama") {
                 setEndpoint("http://localhost:11434");
                 setModel("llama3");
            } else if (newProvider === "grsai") {
                 setEndpoint("https://grsai.dakka.com.cn");
                 setModel("gemini-3-pro");
            } else if (newProvider === "doubao") {
                 setEndpoint("https://ark.cn-beijing.volces.com/api/v3");
                 setModel("doubao-pro-32k");
             } else {
                 setEndpoint("");
            }
        }
    };

    const syncToBackend = async (category, frontendProviderName, configData) => {
        try {
            // Map frontend name to backend provider
            let backendProvider = frontendProviderName.toLowerCase();
            if (frontendProviderName.includes("Grsai")) backendProvider = "grsai";
            else if (frontendProviderName === "Stable Diffusion") backendProvider = "stability";
            else if (frontendProviderName === "Doubao Video") backendProvider = "doubao";
            else if (frontendProviderName === "Wanxiang") backendProvider = "wanxiang";
            else if (frontendProviderName === "Vidu (Video)") backendProvider = "vidu";
            else if (frontendProviderName === "Tencent Hunyuan") backendProvider = "tencent";
            else if (frontendProviderName === "Midjourney") backendProvider = "midjourney";
            else if (frontendProviderName === "DALL-E 3") backendProvider = "openai";

            // Get existing to find ID
            const allSettings = await getSettings();
            const existing = allSettings.find(s => 
                s.provider.toLowerCase() === backendProvider && 
                s.category === category
            );

            // Construct payload
            const payload = {
                id: existing ? existing.id : undefined,
                provider: backendProvider,
                category: category,
                api_key: configData.apiKey || "",
                base_url: configData.endpoint || "",
                model: configData.model || "",
                config: {
                    endpoint: configData.endpoint, // Redundant but config often used for extra
                    width: configData.width,
                    height: configData.height,
                    webHook: configData.webHook,
                    endpointMap: configData.endpointMap,
                    draft: configData.draft
                },
                is_active: true
            };

            await updateSetting(payload);
            console.log(`Synced ${category}/${backendProvider} to backend. Model: ${configData.model}`);
        } catch (e) {
            console.error(`Failed to sync ${category} setting to backend`, e);
        }
    };

    const handleSave = () => {
        // 1. Save specific provider config
        const configToSave = { apiKey, endpoint, model };
        saveProviderConfig(provider, configToSave);

        // 2. Set as active global LLM config
        setLLMConfig({
            provider,
            ...configToSave
        });

        // 3. Sync to Backend
        syncToBackend("LLM", provider, configToSave);
        showNotification(`Settings for ${provider} saved and activated`, "success");
        
        addLog(`Settings for ${provider} saved and activated`, "success");
    };

    const handleSaveGeneration = () => {
        setGenerationConfig({
            characterSupplements: charSupplements,
            sceneSupplements: sceneSupplements,
            prompt_language: promptLanguage,
            imageModel,
            videoModel,
            visionModel
        });

        // Save tool credentials locally
        const imgConfig = { 
            apiKey: imgToolKey, 
            endpoint: imgToolEndpoint, 
            model: imgToolModel,
            width: imgToolWidth,
            height: imgToolHeight,
            webHook: imgToolWebHook
        };
        saveToolConfig(imageModel, imgConfig);
        
        // Sync Image to Backend
        syncToBackend("Image", imageModel, imgConfig);

        const videoConfig = { 
            apiKey: vidToolKey, 
            endpoint: vidToolEndpoint, 
            model: vidToolModel,
            webHook: vidToolWebHook,
            endpointMap: vidEndpointMap,
            draft: vidToolDraft
        };
        saveToolConfig(videoModel, videoConfig);
        
        // Sync Video to Backend
        syncToBackend("Video", videoModel, videoConfig);

        const visConfig = {
            apiKey: visToolKey,
            endpoint: visToolEndpoint,
            model: visToolModel
        };
        saveToolConfig(visionModel, visConfig);

        // Sync Vision to Backend
        syncToBackend("Vision", visionModel, visConfig);

        showNotification("Generation settings & credentials saved", "success");
        addLog("Generation settings & credentials saved", "success");
    };

    const renderFields = () => {
        switch (provider) {
            case 'ollama':
                return (
                    <>
                        <div className="space-y-2">
                            <div className="flex justify-between">
                                <label className="text-sm font-medium">Base URL</label>
                                <span className="text-xs text-muted-foreground">Default: http://localhost:11434</span>
                            </div>
                            <input 
                                type="text" 
                                value={endpoint}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder="http://localhost:11434"
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Model Name</label>
                            <input 
                                type="text" 
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                placeholder="llama3, mistral..."
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                    </>
                );
            case 'doubao':
                return (
                    <>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">API Key</label>
                            <input 
                                type="password" 
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="sk-..."
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Model / Endpoint ID (Required)</label>
                            <input 
                                type="text" 
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                placeholder="ep-2024... (The deployment endpoint ID)"
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Base URL (Optional)</label>
                            <input 
                                type="text" 
                                value={endpoint}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder="https://ark.cn-beijing.volces.com/api/v3"
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                    </>
                );
            case 'grsai':
                return (
                    <>
                         <div className="space-y-2">
                            <label className="text-sm font-medium">API Key</label>
                            <input 
                                type="password" 
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="sk-..."
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                         <div className="space-y-2">
                            <label className="text-sm font-medium">Model Name</label>
                            <select 
                                value={model} 
                                onChange={(e) => setModel(e.target.value)}
                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                            >
                                <option className="bg-zinc-900" value="gemini-3-pro">Gemini 3 Pro</option>
                                <option className="bg-zinc-900" value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                                <option className="bg-zinc-900" value="gemini-3-flash">Gemini 3 Flash</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash-think">Gemini 2.5 Flash Think</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Base URL</label>
                            <input 
                                type="text" 
                                value={endpoint || "https://grsai.dakka.com.cn"}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder="https://grsai.dakka.com.cn"
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                    </>
                );
            case 'openai':
            default:
                return (
                    <>
                         <div className="space-y-2">
                            <label className="text-sm font-medium">API Key</label>
                            <input 
                                type="password" 
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="sk-..."
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                         <div className="space-y-2">
                            <label className="text-sm font-medium">Model Name (Optional)</label>
                            <input 
                                type="text" 
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                placeholder="gpt-4o, gpt-4-turbo..."
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <div className="flex gap-2 items-center">
                                <label className="text-sm font-medium">Endpoint URL (Optional)</label>
                                <div className="group relative">
                                    <Info size={12} className="text-muted-foreground cursor-help" />
                                    <div className="absolute left-0 bottom-full mb-2 w-48 p-2 bg-black text-white text-xs rounded border border-white/10 hidden group-hover:block z-50">
                                        Use this for compatible proxies like OneAPI
                                    </div>
                                </div>
                            </div>
                            <input 
                                type="text" 
                                value={endpoint}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder="https://api.openai.com/v1"
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                    </>
                );
        }
    };

    return (
        <div className="w-full max-w-7xl mx-auto space-y-6 h-full overflow-y-auto p-4 flex flex-col text-white relative">
            {/* Notification Toast */}
            {notification && (
                <div className={`fixed top-10 left-1/2 transform -translate-x-1/2 z-[200] px-6 py-3 rounded-lg shadow-2xl border font-bold flex items-center gap-2 animate-in slide-in-from-top-4 fade-in duration-300 ${
                    notification.type === 'success' ? 'bg-green-500/90 text-white border-green-400' : 'bg-red-500/90 text-white border-red-400'
                }`}>
                    {notification.type === 'success' ? <Save size={18} /> : <Info size={18} />}
                    {notification.message}
                </div>
            )}
            <header className="flex flex-col md:flex-row justify-between items-center gap-4 bg-card p-4 rounded-xl border border-white/10 shadow-sm bg-black/20">
                <div className="flex items-center gap-6 overflow-x-auto w-full md:w-auto no-scrollbar">
                    <div className="flex bg-white/5 p-1 rounded-lg shrink-0">
                        <button 
                            onClick={() => setActiveTab('api')}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'api' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                        >
                            General
                        </button>
                        <button 
                             onClick={() => setActiveTab('prompts')}
                             className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'prompts' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                        >
                            Prompt Optimizers
                        </button>
                        <button 
                             onClick={() => setActiveTab('billing')}
                             className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'billing' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                        >
                            <span className="flex items-center gap-2"><Coins size={14}/> Usage</span>
                        </button>
                    </div>
                </div>

                <div className="flex gap-2 shrink-0">
                    <button 
                        onClick={handleImportClick}
                        className="flex items-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors"
                        title="Import Settings JSON"
                    >
                        <Upload size={14} />
                        <span>Import</span>
                    </button>
                    <button 
                        onClick={handleExportSettings}
                        className="flex items-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors"
                        title="Export Settings JSON"
                    >
                        <Download size={14} />
                        <span>Export</span>
                    </button>
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        className="hidden" 
                        accept=".json" 
                        onChange={handleFileChange} 
                    />
                </div>
            </header>
            
            {activeTab === 'billing' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="grid grid-cols-1 gap-6">
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 shadow-sm flex flex-col items-center justify-center text-center relative">
                             <div className="absolute top-4 right-4">
                                <button
                                    onClick={() => setShowRecharge(true)}
                                    className="bg-green-500 hover:bg-green-600 text-white font-medium py-1.5 px-3 rounded-lg transition-colors flex items-center justify-center gap-1 text-xs shadow-lg shadow-green-500/20"
                                >
                                    <Coins size={14} />
                                    Top Up
                                </button>
                             </div>
                             <Coins className="w-12 h-12 text-yellow-400 mb-4 mt-2" />
                             <h3 className="text-muted-foreground font-medium">Available Credits</h3>
                             <p className="text-4xl font-bold text-white mt-2">{userCredits}</p>
                             <p className="text-xs text-muted-foreground mt-2 mb-4">Credits are deducted for generation tasks.</p>
                             <button
                                onClick={() => setShowRecharge(true)}
                                className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm"
                             >
                                <Coins size={14} />
                                Recharge Bundle
                             </button>
                        </div>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 shadow-sm">
                             <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                <History className="w-5 h-5" /> Recent Transactions
                             </h3>
                             {isBillingLoading ? (
                                <div className="text-center py-10 text-muted-foreground">Loading history...</div>
                             ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse text-sm">
                                        <thead>
                                            <tr className="border-b border-white/10 text-muted-foreground">
                                                <th className="p-3">Time</th>
                                                <th className="p-3">Type</th>
                                                <th className="p-3">Details</th>
                                                <th className="p-3 text-right">Amount</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {transactions.length === 0 ? (
                                                <tr><td colSpan="4" className="text-center p-8 text-muted-foreground">No transactions found</td></tr>
                                            ) : transactions.map(t => (
                                                <tr key={t.id} className="hover:bg-white/[0.02]">
                                                    <td className="p-3 text-muted-foreground">
                                                        {new Date(t.created_at.endsWith('Z') ? t.created_at : t.created_at + 'Z').toLocaleString()}
                                                    </td>
                                                    <td className="p-3">
                                                        <span className="bg-white/5 px-2 py-0.5 rounded text-xs uppercase border border-white/10">{t.task_type}</span>
                                                    </td>
                                                    <td className="p-3 text-xs opacity-70">
                                                        <div className="max-h-[120px] overflow-y-auto whitespace-pre-wrap break-all w-[300px] bg-black/20 p-2 rounded border border-white/10 font-mono text-[10px]">
                                                            {JSON.stringify(t.details, null, 2)}
                                                        </div>
                                                    </td>
                                                    <td className={`p-3 text-right font-mono font-bold ${t.amount < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                                        {t.amount > 0 ? '+' : ''}{t.amount}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                             )}
                        </div>
                    </div>

                    {showRecharge && (
                        <RechargeModal 
                            onClose={() => setShowRecharge(false)} 
                            onSuccess={() => {
                                refreshBilling();
                                showNotification("Recharge successful!", "success");
                            }}
                        />                                
                    )}
                </div>
            ) : activeTab === 'api' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">
                            Core LLM Configuration
                            <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full border border-primary/30 font-mono">Task: llm_chat</span>
                        </h2>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Text Model Provider</label>
                                <select 
                                    value={provider} 
                                    onChange={(e) => handleProviderChange(e.target.value)}
                                    className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                >
                                    <option className="bg-zinc-900" value="openai">OpenAI / Compatible</option>
                                    <option className="bg-zinc-900" value="doubao">Doubao (Volcengine)</option>
                                    <option className="bg-zinc-900" value="ollama">Ollama (Local)</option>
                                    <option className="bg-zinc-900" value="deepseek">DeepSeek</option>
                                    <option className="bg-zinc-900" value="grsai">Grsai (Aggregation)</option>
                                </select>
                            </div>
                            
                            <div className="pt-2 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300" key={provider}>
                                {renderFields()}
                            </div>

                            <button 
                                onClick={handleSave}
                                className="mt-6 w-full flex items-center justify-center space-x-2 bg-primary text-black px-4 py-3 rounded-lg hover:opacity-90 transition-opacity font-medium font-bold"
                            >
                                <Save size={18} />
                                <span>Save & Activate Configuration</span>
                            </button>
                            
                            <p className="text-xs text-center text-muted-foreground mt-2">
                                Parameters are saved automatically for each provider.
                            </p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold">Image & Video Tools API</h2>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-6 shadow-sm">
                            {/* Translation Tool Section */}
                            <div className="space-y-4 border-b border-white/10 pb-6">
                                <h3 className="text-base font-medium flex items-center gap-2">
                                    Translation Service (Baidu)
                                </h3>
                                <p className="text-xs text-muted-foreground">Configure Baidu Translate API to enable prompt translation features.</p>

                                <form 
                                    onSubmit={(e) => { e.preventDefault(); handleSaveTranslation(); }}
                                    className="grid grid-cols-1 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in"
                                >
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground flex items-center justify-between">
                                            <span>Access Token</span>
                                            <a href="https://console.bce.baidu.com/ai/#/ai/machine_learning/overview/index" target="_blank" rel="noreferrer" className="text-[10px] text-blue-400 hover:underline">Get Token</a>
                                        </label>
                                        <input 
                                            type="password" 
                                            value={baiduToken}
                                            onChange={(e) => setBaiduToken(e.target.value)}
                                            placeholder="Paste Baidu AI Access Token..."
                                            autoComplete="new-password"
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                        <p className="text-[10px] text-muted-foreground">
                                            Requires 'machine_translation' or equivalent capability enabled on Baidu Cloud. 
                                            Enter the Access Token (starts with '24.').
                                        </p>
                                    </div>
                                    <div>
                                        <button 
                                            type="submit"
                                            className="text-xs bg-primary/10 text-primary hover:bg-primary/20 px-3 py-2 rounded transition-colors w-full"
                                        >
                                            Save Translation Token
                                        </button>
                                    </div>
                                </form>
                            </div>
                            
                            {/* Image Tool Section */}
                            <div className="space-y-4 border-b border-white/10 pb-6">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-blue-400 flex items-center gap-2">
                                        Image Generation Tool
                                        <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded border border-blue-500/30 font-mono">Task: image_gen</span>
                                    </label>
                                    <select 
                                        value={imageModel}
                                        onChange={(e) => handleImageToolChange(e.target.value)}
                                        className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                    >
                                        <option className="bg-zinc-900" value="Midjourney">Midjourney</option>
                                        <option className="bg-zinc-900" value="Doubao">Doubao (豆包 - Volcengine)</option>
                                        <option className="bg-zinc-900" value="Grsai-Image">Grsai (Aggregation)</option>
                                        <option className="bg-zinc-900" value="DALL-E 3">DALL-E 3</option>
                                        <option className="bg-zinc-900" value="Stable Diffusion">Stable Diffusion (SDXL/Pony)</option>
                                        <option className="bg-zinc-900" value="Flux">Flux.1</option>
                                        <option className="bg-zinc-900" value="Tencent Hunyuan">Tencent Hunyuan (腾讯混元)</option>
                                    </select>
                                    <p className="text-xs text-muted-foreground">Select tool to configure credentials and prompt optimization.</p>
                                </div>
                                
                                {/* Dynamic fields for Image Tool */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in">
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">API Key</label>
                                        <input 
                                            type="password" 
                                            value={imgToolKey}
                                            onChange={(e) => setImgToolKey(e.target.value)}
                                            placeholder={
                                                imageModel === "Midjourney" ? "Not required for web use" : 
                                                imageModel === "Tencent Hunyuan" ? "SecretId:SecretKey" :
                                                "sk-..."
                                            }
                                            disabled={imageModel === "Midjourney"}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Endpoint URL</label>
                                        <input 
                                            type="text" 
                                            value={imgToolEndpoint}
                                            onChange={(e) => setImgToolEndpoint(e.target.value)}
                                            placeholder="https://api..."
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Model ID</label>
                                        {imageModel === "Grsai-Image" ? (
                                            <select 
                                                value={imgToolModel}
                                                onChange={(e) => setImgToolModel(e.target.value)}
                                                className="w-full p-2 text-sm rounded-md bg-zinc-900 border border-white/10 text-white" 
                                            >
                                                <option className="bg-zinc-900" value="sora-image">Sora Image</option>
                                                <option className="bg-zinc-900" value="gpt-image-1.5">GPT Image 1.5</option>
                                                <option className="bg-zinc-900" value="sora-create-character">Sora Create Character</option>
                                                <option className="bg-zinc-900" value="sora-upload-character">Sora Upload Character</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro">Nano Banana Pro</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-vt">Nano Banana Pro VT</option>
                                                <option className="bg-zinc-900" value="nano-banana-fast">Nano Banana Fast</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-cl">Nano Banana Pro CL</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-vip">Nano Banana Pro VIP</option>
                                                <option className="bg-zinc-900" value="nano-banana">Nano Banana</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-4k-vip">Nano Banana Pro 4K VIP</option>
                                            </select>
                                        ) : (
                                            <input  
                                                type="text" 
                                                value={imgToolModel}
                                                onChange={(e) => setImgToolModel(e.target.value)}
                                                placeholder="e.g. doubao-seedream-4-5-251128"
                                                className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                            />
                                        )}
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Width (px)</label>
                                        <input 
                                            type="number" 
                                            value={imgToolWidth}
                                            onChange={(e) => setImgToolWidth(e.target.value)}
                                            placeholder="1024"
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Height (px)</label>
                                        <input 
                                            type="number" 
                                            value={imgToolHeight}
                                            onChange={(e) => setImgToolHeight(e.target.value)}
                                            placeholder="1024"
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">WebHook URL</label>
                                        <input 
                                            type="text" 
                                            value={imgToolWebHook}
                                            onChange={(e) => setImgToolWebHook(e.target.value)}
                                            placeholder="https://your-callback.com/..."
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Video Tool Section */}
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-orange-400 flex items-center gap-2">
                                        Video Generation Tool
                                        <span className="text-[10px] bg-orange-500/20 text-orange-300 px-1.5 py-0.5 rounded border border-orange-500/30 font-mono">Task: video_gen</span>
                                    </label>
                                    <select 
                                        value={videoModel}
                                        onChange={(e) => handleVideoToolChange(e.target.value)}
                                        className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                    >
                                        <option className="bg-zinc-900" value="Runway">Runway Gen-2/Gen-3</option>
                                        <option className="bg-zinc-900" value="Luma">Luma Dream Machine</option>
                                        <option className="bg-zinc-900" value="Kling">Kling AI (可灵)</option>
                                        <option className="bg-zinc-900" value="Sora">Sora (OpenAI)</option>
                                        <option className="bg-zinc-900" value="Grsai-Video">Grsai (Standard)</option>
                                        <option className="bg-zinc-900" value="Grsai-Video (Upload)">Grsai (File Upload)</option>
                                        <option className="bg-zinc-900" value="Stable Video">Stable Video Component</option>
                                        <option className="bg-zinc-900" value="Doubao Video">Doubao (豆包 - Volcengine)</option>
                                        <option className="bg-zinc-900" value="Wanxiang">Wanxiang (通义万相 - Aliyun)</option>
                                        <option className="bg-zinc-900" value="Vidu (Video)">Vidu (Shengshu)</option>
                                    </select>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in">
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">API Key</label>
                                        <input 
                                            type="password" 
                                            value={vidToolKey}
                                            onChange={(e) => setVidToolKey(e.target.value)}
                                            placeholder="Key..."
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Endpoint</label>
                                        <input 
                                            type="text" 
                                            value={vidToolEndpoint}
                                            onChange={(e) => handleVidEndpointChange(e.target.value)}
                                            placeholder="Optional"
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Model ID</label>
                                        {(videoModel === "Grsai-Video" || videoModel === "Grsai-Video (Upload)") ? (
                                            <select 
                                                value={vidToolModel}
                                                onChange={(e) => handleVidSubModelChange(e.target.value)}
                                                className="w-full p-2 text-sm rounded-md bg-zinc-900 border border-white/10 text-white" 
                                            >
                                                <option className="bg-zinc-900" value="sora-2">Sora 2</option>
                                                <option className="bg-zinc-900" value="veo3.1-pro">Veo 3.1 Pro</option>
                                                <option className="bg-zinc-900" value="veo3.1-fast">Veo 3.1 Fast</option>
                                                <option className="bg-zinc-900" value="veo3.1-pro-1080p">Veo 3.1 Pro 1080p</option>
                                                <option className="bg-zinc-900" value="veo3.1-pro-4k">Veo 3.1 Pro 4K</option>
                                                <option className="bg-zinc-900" value="veo3.1-fast-1080p">Veo 3.1 Fast 1080p</option>
                                                <option className="bg-zinc-900" value="veo3.1-fast-4k">Veo 3.1 Fast 4K</option>
                                                
                                                <option className="bg-zinc-900" value="nano-banana-pro">Nano Banana Pro</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-vt">Nano Banana Pro VT</option>
                                                <option className="bg-zinc-900" value="nano-banana-fast">Nano Banana Fast</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-cl">Nano Banana Pro CL</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-vip">Nano Banana Pro VIP</option>
                                                <option className="bg-zinc-900" value="nano-banana">Nano Banana</option>
                                                <option className="bg-zinc-900" value="nano-banana-pro-4k-vip">Nano Banana Pro 4K VIP</option>
                                            </select>
                                        ) : (videoModel === "Vidu (Video)") ? (
                                            <>
                                                <input 
                                                    list="vidu-models"
                                                    type="text" 
                                                    value={vidToolModel}
                                                    onChange={(e) => handleVidSubModelChange(e.target.value)}
                                                    placeholder="e.g. vidu2.0 or select from list"
                                                    className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                                />
                                                <datalist id="vidu-models">
                                                    <option value="vidu2.0" />
                                                    <option value="viduq2-pro" />
                                                    <option value="viduq2-pro-fast" />
                                                    <option value="viduq2-turbo" />
                                                    <option value="viduq1" />
                                                    <option value="viduq1-classic" />
                                                </datalist>
                                                <p className="text-[10px] text-muted-foreground mt-1">Select or type custom model ID</p>
                                            </>
                                        ) : (
                                            <input 
                                                type="text" 
                                                value={vidToolModel}
                                                onChange={(e) => handleVidSubModelChange(e.target.value)}
                                                placeholder="e.g. doubao-seedance-1-5-pro-251215"
                                                className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                            />
                                        )}
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">WebHook URL</label>
                                        <input 
                                            type="text" 
                                            value={vidToolWebHook}
                                            onChange={(e) => setVidToolWebHook(e.target.value)}
                                            placeholder="https://your-callback.com/..."
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    {videoModel === "Doubao Video" && (
                                        <div className="col-span-2 flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-white/10">
                                            <input
                                                type="checkbox"
                                                id="draftMode"
                                                checked={vidToolDraft}
                                                onChange={(e) => setVidToolDraft(e.target.checked)}
                                                className="mt-1 w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                                            />
                                            <div className="flex flex-col gap-1">
                                                <label htmlFor="draftMode" className="text-sm font-medium text-white cursor-pointer select-none">
                                                    Draft Mode (Sample Mode)
                                                </label>
                                                <span className="text-[10px] text-muted-foreground leading-tight">
                                                    Only Seedance 1.5 pro supports controlling whether to enable sample mode.<br/>
                                                    True: Indicates that the sample mode is turned on, allowing for the generation of a highly consistent 5s video.<br/>
                                                    False: Normal generation mode.
                                                </span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Vision Tool Section */}
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-pink-400 flex items-center gap-2">
                                        Vision / Image Recognition Tool
                                        <span className="text-[10px] bg-pink-500/20 text-pink-300 px-1.5 py-0.5 rounded border border-pink-500/30 font-mono">Task: analysis</span>
                                    </label>
                                    <select 
                                        value={visionModel}
                                        onChange={(e) => setVisionModel(e.target.value)}
                                        className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                    >
                                        <option className="bg-zinc-900" value="Grsai-Vision">Grsai (Vision Capability)</option>
                                    </select>
                                    <p className="text-xs text-muted-foreground">
                                        Used for Scene Analysis from Image, Image to Text, etc. Compatible with OpenAI Vision API format.
                                    </p>
                                </div>
                                
                                {visionModel === "Grsai-Vision" && (
                                    <div className="space-y-2 pl-4 border-l-2 border-pink-400/30">
                                         <div className="space-y-1">
                                            <label className="text-xs font-medium text-muted-foreground">API Key</label>
                                            <input 
                                                type="password" 
                                                value={visToolKey}
                                                onChange={(e) => setVisToolKey(e.target.value)}
                                                placeholder="sk-..."
                                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white text-sm"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium text-muted-foreground">Endpoint URL</label>
                                            <input 
                                                type="text" 
                                                value={visToolEndpoint}
                                                onChange={(e) => setVisToolEndpoint(e.target.value)}
                                                placeholder="https://grsaiapi.com/v1/chat/completions"
                                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white text-sm"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium text-muted-foreground">Model Name (ID)</label>
                                            <input 
                                                type="text" 
                                                value={visToolModel}
                                                onChange={(e) => setVisToolModel(e.target.value)}
                                                placeholder="gemini-3-pro, gemini-2.5-pro, etc."
                                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white text-sm"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <button 
                                onClick={handleSaveGeneration}
                                className="w-full flex items-center justify-center space-x-2 bg-white/10 text-white border border-white/10 px-4 py-3 rounded-lg hover:bg-white/20 transition-colors font-medium font-bold"
                            >
                                <Save size={18} />
                                <span>Save Tool Credentials</span>

                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <h2 className="text-xl font-semibold">Generation Prompt Settings</h2>
                    <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                        
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Language Strategy</label>
                            <select 
                                value={promptLanguage} 
                                onChange={(e) => setPromptLanguage(e.target.value)}
                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                            >
                                <option className="bg-zinc-900" value="mixed">Mixed (Chinese Names/Dialogue + English Descriptions)</option>
                                <option className="bg-zinc-900" value="en">Pure English (Force Translate All)</option>
                            </select>
                            <p className="text-xs text-muted-foreground">
                                Controls how Chinese elements (Names, Dialogues) are handled in the generated English prompts.
                            </p>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium">Character Generation Supplementary Prompts</label>
                            <p className="text-xs text-muted-foreground">Additional instructions appended when generating character descriptions.</p>
                            <textarea 
                                value={charSupplements} 
                                onChange={(e) => setCharSupplements(e.target.value)}
                                placeholder="e.g. Always emphasize eastern features..."
                                className="w-full p-4 h-32 rounded-md bg-white/10 border border-white/10 resize-none text-white"
                            />
                        </div>
                        
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Scene Generation Supplementary Prompts</label>
                            <p className="text-xs text-muted-foreground">Additional instructions appended when generating scene visuals/beats.</p>
                            <textarea 
                                value={sceneSupplements} 
                                onChange={(e) => setSceneSupplements(e.target.value)}
                                placeholder="e.g. Maintain a dark, cinematic tone..."
                                className="w-full p-4 h-32 rounded-md bg-white/10 border border-white/10 resize-none text-white"
                            />
                        </div>

                        <button 
                            onClick={handleSaveGeneration}
                            className="mt-6 w-full flex items-center justify-center space-x-2 bg-primary text-black border border-primary px-4 py-3 rounded-lg hover:opacity-90 transition-opacity font-medium font-bold"
                        >
                            <Save size={18} />
                            <span>Save Prompt Settings</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}

export default Settings;
