import { useState, useEffect } from 'react';
import { useStore } from '@/lib/store';
import { Save, Info } from 'lucide-react';
import { API_URL } from '@/config';
import { updateSetting, getSettings } from '../services/api';

const Settings = () => {
    const { llmConfig, setLLMConfig, savedConfigs, saveProviderConfig, addLog, generationConfig, setGenerationConfig, savedToolConfigs, saveToolConfig } = useStore();
    
    // Internal state for form
    const [provider, setProvider] = useState("openai");
    const [apiKey, setApiKey] = useState("");
    const [endpoint, setEndpoint] = useState("");
    const [model, setModel] = useState("");

    // State for generation supplements
    const [charSupplements, setCharSupplements] = useState("");
    const [sceneSupplements, setSceneSupplements] = useState("");

    // State for generation models
    const [imageModel, setImageModel] = useState("Midjourney");
    const [videoModel, setVideoModel] = useState("Runway");
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
    
    // WebHooks
    const [imgToolWebHook, setImgToolWebHook] = useState("");
    const [vidToolWebHook, setVidToolWebHook] = useState("");

    // State for Baidu Translation
    const [baiduToken, setBaiduToken] = useState("");

    // State for tabs
    const [activeTab, setActiveTab] = useState('api');

    // UI Notification State
    const [notification, setNotification] = useState(null);

    const showNotification = (message, type = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
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
             // Fallback: try loading current provider from saved if main config is null
             const saved = savedConfigs[provider];
             if (saved) {
                 setApiKey(saved.apiKey || "");
                 setEndpoint(saved.endpoint || "");
                 setModel(saved.model || "");
             }
        }
    }, [llmConfig, savedConfigs, provider]);

    // Initialize generation config & handle saved tool configs updates
    useEffect(() => {
        if (generationConfig) {
            setCharSupplements(generationConfig.characterSupplements || "");
            setSceneSupplements(generationConfig.sceneSupplements || "");
            setPromptLanguage(generationConfig.prompt_language || "mixed");
            
            const iModel = generationConfig.imageModel || "Midjourney";
            const vModel = generationConfig.videoModel || "Runway";
            
            setImageModel(iModel);
            setVideoModel(vModel);
            
            // Load saved tool configs
            loadToolConfig(iModel, 'image');
            loadToolConfig(vModel, 'video');
        } else {
             // Even if no generationConfig, we might have defaults set in state (e.g. Midjourney/Runway)
             // and we should load their configs if savedToolConfigs updates
             loadToolConfig(imageModel, 'image');
             loadToolConfig(videoModel, 'video');
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
        } else {
             if (saved) {
                setVidToolKey(saved.apiKey || "");
                // Auto-correct legacy Grsai endpoint
                let ep = saved.endpoint || "";
                if (toolName === "Grsai-Video" && (ep.includes("api.grsai.com") || ep.includes("grsai.com"))) {
                     ep = "https://grsai.dakka.com.cn";
                }
                setVidToolEndpoint(ep);

                setVidToolModel(saved.model || "");
                setVidToolWebHook(saved.webHook || "");
             } else {
                 if (toolName === "Doubao Video") {
                    setVidToolKey("");
                    setVidToolEndpoint("https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks");
                    setVidToolModel("doubao-seedance-1-5-pro-251215");
                    setVidToolWebHook("");
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
                 }
             }
        }
    }

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
                    webHook: configData.webHook
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
            videoModel
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
            webHook: vidToolWebHook
        };
        saveToolConfig(videoModel, videoConfig);
        
        // Sync Video to Backend
        syncToBackend("Video", videoModel, videoConfig);

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
                                <option className="bg-zinc-900" value="gemini-3-flash">Gemini 3 Flash</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</option>
                                <option className="bg-zinc-900" value="gemini-2.5-pro">Gemini 2.5 Pro</option>
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
        <div className="max-w-4xl space-y-8 h-full overflow-y-auto p-1 flex flex-col text-white relative">
            {/* Notification Toast */}
            {notification && (
                <div className={`fixed top-10 left-1/2 transform -translate-x-1/2 z-[200] px-6 py-3 rounded-lg shadow-2xl border font-bold flex items-center gap-2 animate-in slide-in-from-top-4 fade-in duration-300 ${
                    notification.type === 'success' ? 'bg-green-500/90 text-white border-green-400' : 'bg-red-500/90 text-white border-red-400'
                }`}>
                    {notification.type === 'success' ? <Save size={18} /> : <Info size={18} />}
                    {notification.message}
                </div>
            )}
            <header className="flex justify-between items-center bg-card p-4 rounded-xl border border-white/10 shadow-sm bg-black/20">
                <h1 className="text-3xl font-bold">Settings</h1>
                <div className="flex bg-white/5 p-1 rounded-lg">
                    <button 
                        onClick={() => setActiveTab('api')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'api' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                    >
                        API Configuration
                    </button>
                    <button 
                         onClick={() => setActiveTab('prompts')}
                         className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'prompts' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                    >
                        Prompt Optimizers
                    </button>
                </div>
            </header>
            
            {activeTab === 'api' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">Core LLM Configuration</h2>
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

                                <div className="grid grid-cols-1 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in">
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
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                        <p className="text-[10px] text-muted-foreground">
                                            Requires 'machine_translation' or equivalent capability enabled on Baidu Cloud. 
                                            Enter the Access Token (starts with '24.').
                                        </p>
                                    </div>
                                    <div>
                                        <button 
                                            onClick={handleSaveTranslation}
                                            className="text-xs bg-primary/10 text-primary hover:bg-primary/20 px-3 py-2 rounded transition-colors w-full"
                                        >
                                            Save Translation Token
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            {/* Image Tool Section */}
                            <div className="space-y-4 border-b border-white/10 pb-6">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-blue-400">Image Generation Tool</label>
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
                                    <label className="text-sm font-medium text-orange-400">Video Generation Tool</label>
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
                                            onChange={(e) => setVidToolEndpoint(e.target.value)}
                                            placeholder="Optional"
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Model ID</label>
                                        {(videoModel === "Grsai-Video" || videoModel === "Grsai-Video (Upload)") ? (
                                            <select 
                                                value={vidToolModel}
                                                onChange={(e) => setVidToolModel(e.target.value)}
                                                className="w-full p-2 text-sm rounded-md bg-zinc-900 border border-white/10 text-white" 
                                            >
                                                <option className="bg-zinc-900" value="sora-2">Sora 2</option>
                                                <option className="bg-zinc-900" value="veo3.1-pro">Veo 3.1 Pro</option>
                                                <option className="bg-zinc-900" value="veo3.1-fast">Veo 3.1 Fast</option>
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
                                                    onChange={(e) => setVidToolModel(e.target.value)}
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
                                                onChange={(e) => setVidToolModel(e.target.value)}
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
                                    </div>                                </div>
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
