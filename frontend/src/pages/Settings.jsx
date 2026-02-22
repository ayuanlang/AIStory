import { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useStore } from '@/lib/store';
import { Save, Info, Upload, Download, Coins, History } from 'lucide-react';
import { API_URL } from '@/config';
import { updateSetting, getSettings, getTransactions, fetchMe, getSystemSettings, getSystemSettingsCatalog, selectSystemSetting, getSystemSettingsManage, createSystemSettingManage, updateSystemSettingManage, getEffectiveSettingSnapshot } from '../services/api';
import RechargeModal from '../components/RechargeModal'; // Import RechargeModal

const DEFAULT_CHARACTER_SUPPLEMENTS = [
    "Default Aesthetic Policy (when no explicit style is provided): prioritize premium cinematic beauty and modern elegance.",
    "Character portrayal should be attractive and charismatic, with tasteful sensual tension only (non-explicit, broadcast-safe).",
    "Keep identity anchors stable and explicit: preserve recognizable facial/hairstyle silhouette, signature accessory, and posture/mannerism cues for cross-shot consistency.",
].join('\n');

const DEFAULT_SCENE_SUPPLEMENTS = [
    "Default Aesthetic Policy (when no explicit style is provided): deliver modern, refined, high-pleasure visuals with clean composition and cinematic lighting hierarchy.",
    "Props should appear exquisite and well-crafted with clear material readability.",
    "Anchor Clarity Mandate: keep environment/character/prop anchors explicit and stable; never trade anchor consistency for style.",
    "If user style constraints are provided, obey them first.",
].join('\n');

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
    const [charSupplements, setCharSupplements] = useState(DEFAULT_CHARACTER_SUPPLEMENTS);
    const [sceneSupplements, setSceneSupplements] = useState(DEFAULT_SCENE_SUPPLEMENTS);

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
    const [systemSettings, setSystemSettings] = useState([]);
    const [systemCatalog, setSystemCatalog] = useState([]);
    const [isSystemSettingsLoading, setIsSystemSettingsLoading] = useState(false);
    const [selectingSystemId, setSelectingSystemId] = useState(null);
    const [selectedSystemCategory, setSelectedSystemCategory] = useState('All');
    const [currentUserMeta, setCurrentUserMeta] = useState(null);
    const [manageableSystemSettings, setManageableSystemSettings] = useState([]);
    const [manageSettingId, setManageSettingId] = useState('');
    const [manageApiKey, setManageApiKey] = useState('');
    const [manageBaseUrl, setManageBaseUrl] = useState('');
    const [manageModel, setManageModel] = useState('');
    const [manageWebHook, setManageWebHook] = useState('');
    const [isManageSaving, setIsManageSaving] = useState(false);
    const [isManageCreating, setIsManageCreating] = useState(false);
    const [createName, setCreateName] = useState('');
    const [createProvider, setCreateProvider] = useState('');
    const [createCategory, setCreateCategory] = useState('LLM');
    const [createApiKey, setCreateApiKey] = useState('');
    const [createBaseUrl, setCreateBaseUrl] = useState('');
    const [createModel, setCreateModel] = useState('');
    const [createWebHook, setCreateWebHook] = useState('');
    const [createIsActive, setCreateIsActive] = useState(false);
    const [errorLocatorInput, setErrorLocatorInput] = useState('');
    const [isRowEditOpen, setIsRowEditOpen] = useState(false);
    const [effectiveSnapshot, setEffectiveSnapshot] = useState(null);
    const [isSnapshotLoading, setIsSnapshotLoading] = useState(false);
    const [activeSettingSources, setActiveSettingSources] = useState({
        LLM: 'none',
        Image: 'none',
        Video: 'none',
        Vision: 'none',
    });

    // Unified Top Up entry: support /settings?tab=billing and cross-app 402 redirects.
    useEffect(() => {
        const params = new URLSearchParams(location.search || '');
        const tab = params.get('tab');
        if (tab === 'billing') {
            setActiveTab('billing');
        } else if (tab === 'system-api' || tab === 'system_api') {
            setActiveTab('system_api');
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

    const loadSystemSettingsCatalog = async () => {
        setIsSystemSettingsLoading(true);
        try {
            const [userRes, systemRes, catalogRes] = await Promise.all([fetchMe(), getSystemSettings(), getSystemSettingsCatalog()]);
            setCurrentUserMeta(userRes || null);
            if (userRes && userRes.credits !== undefined) {
                setUserCredits(userRes.credits);
            }
            setSystemSettings(Array.isArray(systemRes) ? systemRes : []);
            setSystemCatalog(Array.isArray(catalogRes) ? catalogRes : []);

            const canManage = !!(userRes?.is_superuser || userRes?.is_system);
            if (canManage) {
                const manageRows = await getSystemSettingsManage();
                const normalized = Array.isArray(manageRows) ? manageRows : [];
                setManageableSystemSettings(normalized);
                if (!manageSettingId && normalized.length > 0) {
                    const firstId = String(normalized[0].id);
                    setManageSettingId(firstId);
                }
            } else {
                setManageableSystemSettings([]);
                setManageSettingId('');
            }
        } catch (err) {
            console.error("Failed to load system API settings", err);
            setSystemSettings([]);
            setSystemCatalog([]);
            setManageableSystemSettings([]);
        } finally {
            setIsSystemSettingsLoading(false);
        }
    };

    useEffect(() => {
        if (!manageSettingId) {
            setManageApiKey('');
            setManageBaseUrl('');
            setManageModel('');
            setManageWebHook('');
            return;
        }
        const row = manageableSystemSettings.find((item) => String(item.id) === String(manageSettingId));
        if (!row) return;
        setManageApiKey('');
        setManageBaseUrl(row.base_url || '');
        setManageModel(row.model || '');
        setManageWebHook(row.config?.webHook || '');
    }, [manageSettingId, manageableSystemSettings]);

    const handleSaveManagedSystemSetting = async () => {
        if (!manageSettingId) {
            showNotification('Please select a system setting to edit', 'error');
            return;
        }
        setIsManageSaving(true);
        try {
            const selected = manageableSystemSettings.find((item) => String(item.id) === String(manageSettingId));
            const nextConfig = {
                ...(selected?.config || {}),
                webHook: manageWebHook || '',
            };

            await updateSystemSettingManage(Number(manageSettingId), {
                api_key: manageApiKey || undefined,
                base_url: manageBaseUrl,
                model: manageModel,
                config: nextConfig,
            });

            showNotification('System API setting updated', 'success');
            addLog('System API setting updated', 'success');
            await loadSystemSettingsCatalog();
        } catch (err) {
            console.error('Failed to update system setting', err);
            const msg = err?.response?.data?.detail || 'Failed to update system API setting';
            showNotification(msg, 'error');
        } finally {
            setIsManageSaving(false);
        }
    };

    const handleCreateManagedSystemSetting = async () => {
        const provider = String(createProvider || '').trim();
        if (!provider) {
            showNotification('Provider is required to create system setting', 'error');
            return;
        }

        setIsManageCreating(true);
        try {
            const payload = {
                name: String(createName || '').trim() || undefined,
                provider,
                category: createCategory || 'LLM',
                api_key: String(createApiKey || '').trim() || undefined,
                base_url: String(createBaseUrl || '').trim() || undefined,
                model: String(createModel || '').trim() || undefined,
                config: { webHook: String(createWebHook || '').trim() || '' },
                is_active: !!createIsActive,
            };

            const created = await createSystemSettingManage(payload);
            showNotification('System API setting created', 'success');
            addLog('System API setting created', 'success');

            setCreateName('');
            setCreateProvider('');
            setCreateCategory('LLM');
            setCreateApiKey('');
            setCreateBaseUrl('');
            setCreateModel('');
            setCreateWebHook('');
            setCreateIsActive(false);

            await loadSystemSettingsCatalog();
            if (created?.id) {
                setManageSettingId(String(created.id));
            }
        } catch (err) {
            console.error('Failed to create system setting', err);
            const msg = err?.response?.data?.detail || 'Failed to create system API setting';
            showNotification(msg, 'error');
        } finally {
            setIsManageCreating(false);
        }
    };

    const handleLoadEffectiveSnapshot = async () => {
        setIsSnapshotLoading(true);
        try {
            const data = await getEffectiveSettingSnapshot({ category: 'LLM' });
            setEffectiveSnapshot(data || null);
            if (!data?.found) {
                showNotification('No effective LLM setting found', 'error');
            }
        } catch (err) {
            console.error('Failed to fetch effective setting snapshot', err);
            const msg = err?.response?.data?.detail || 'Failed to fetch effective setting snapshot';
            showNotification(msg, 'error');
        } finally {
            setIsSnapshotLoading(false);
        }
    };

    const canManageSystemSettings = !!(currentUserMeta?.is_superuser);

    const openRowEditModal = (row) => {
        if (!canManageSystemSettings || !row?.id) return;
        setManageSettingId(String(row.id));
        setManageApiKey('');
        setManageBaseUrl(row.base_url || '');
        setManageModel(row.model || '');
        setManageWebHook(row.config?.webHook || '');
        setIsRowEditOpen(true);
    };

    const closeRowEditModal = () => {
        setIsRowEditOpen(false);
    };

    const handleSaveFromRowEdit = async () => {
        await handleSaveManagedSystemSetting();
        closeRowEditModal();
    };

    useEffect(() => {
        if (!isRowEditOpen) return;
        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                closeRowEditModal();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [isRowEditOpen]);

    const normalizeEndpoint = (url) => {
        const raw = String(url || '').trim().toLowerCase();
        if (!raw) return '';
        return raw
            .replace(/\/chat\/completions$/i, '')
            .replace(/\/responses$/i, '')
            .replace(/\/$/, '');
    };

    const handleLocateSettingFromError = () => {
        const raw = String(errorLocatorInput || '').trim();
        if (!raw) {
            showNotification('Paste error text first', 'error');
            return;
        }

        const provider = (raw.match(/provider=([^,\]]+)/i)?.[1] || '').trim().toLowerCase();
        const model = (raw.match(/model=([^,\]]+)/i)?.[1] || '').trim().toLowerCase();
        const endpoint = normalizeEndpoint(raw.match(/endpoint=([^\]]+)/i)?.[1] || '');

        if (!provider && !model && !endpoint) {
            showNotification('Cannot parse provider/model/endpoint from error', 'error');
            return;
        }

        let best = null;
        let bestScore = -1;

        for (const row of manageableSystemSettings) {
            const rowProvider = String(row.provider || '').trim().toLowerCase();
            const rowModel = String(row.model || '').trim().toLowerCase();
            const rowEndpoint = normalizeEndpoint(row.base_url || '');

            let score = 0;
            if (provider && provider === rowProvider) score += 3;
            if (model && model === rowModel) score += 3;
            if (endpoint && rowEndpoint && (endpoint === rowEndpoint || endpoint.includes(rowEndpoint) || rowEndpoint.includes(endpoint))) score += 2;

            if (score > bestScore) {
                best = row;
                bestScore = score;
            }
        }

        if (!best || bestScore <= 0) {
            showNotification('No matching system setting found from this error', 'error');
            return;
        }

        setManageSettingId(String(best.id));
        showNotification(`Matched: [${best.category}] ${best.provider} / ${best.model || '-'}`, 'success');
    };

    const refreshActiveSettingSources = async () => {
        try {
            const all = await getSettings();
            const next = {
                LLM: 'none',
                Image: 'none',
                Video: 'none',
                Vision: 'none',
            };
            (all || []).forEach((item) => {
                if (!item?.is_active || !item?.category) return;
                const source = item?.config?.selection_source === 'system' || item?.config?.use_system_setting_id ? 'system' : 'user';
                if (next[item.category] !== undefined) {
                    next[item.category] = source;
                }
            });
            setActiveSettingSources(next);
        } catch (err) {
            console.error('Failed to refresh active setting sources', err);
        }
    };

    const sourceBadgeClass = (source) => {
        if (source === 'system') return 'bg-green-500/20 text-green-300 border-green-500/30';
        if (source === 'user') return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
        return 'bg-white/10 text-muted-foreground border-white/20';
    };

    const sourceBadgeText = (source) => {
        if (source === 'system') return 'Source: System';
        if (source === 'user') return 'Source: User';
        return 'Source: Unset';
    };

    const categorizedSystemSettings = useMemo(() => {
        // Keep category taxonomy consistent with General page.
        const categoryLabelMap = {
            LLM: 'LLM',
            Image: 'Image',
            Video: 'Video',
            Vision: 'Vision',
            Tools: 'Tools',
        };
        const preferredOrder = ['LLM', 'Image', 'Video', 'Vision', 'Tools'];

        const grouped = (systemSettings || []).reduce((acc, item) => {
            const rawCategory = item?.category || 'Tools';
            const category = preferredOrder.includes(rawCategory) ? rawCategory : 'Tools';
            if (!acc[category]) acc[category] = [];
            acc[category].push({ ...item, category });
            return acc;
        }, {});

        const orderedKeys = [
            ...preferredOrder.filter((cat) => grouped[cat]),
            ...Object.keys(grouped)
                .filter((cat) => !preferredOrder.includes(cat))
                .sort((a, b) => a.localeCompare(b)),
        ];

        return orderedKeys.map((category) => ({
            category,
            label: categoryLabelMap[category] || category,
            groups: (grouped[category] || []).sort((a, b) => String(a.provider || '').localeCompare(String(b.provider || ''))),
        }));
    }, [systemSettings]);

    const selectedManageRow = useMemo(() => {
        if (!manageSettingId) return null;
        return manageableSystemSettings.find((item) => String(item.id) === String(manageSettingId)) || null;
    }, [manageableSystemSettings, manageSettingId]);

    const createProviderSuggestions = useMemo(() => {
        const cat = String(createCategory || 'LLM');
        const providers = (systemCatalog || [])
            .filter((item) => String(item?.category || '') === cat)
            .map((item) => String(item?.provider || '').trim())
            .filter(Boolean);
        return [...new Set(providers)].sort((a, b) => a.localeCompare(b));
    }, [systemCatalog, createCategory]);

    const createModelSuggestions = useMemo(() => {
        const cat = String(createCategory || 'LLM');
        const selectedProvider = String(createProvider || '').trim().toLowerCase();
        if (!selectedProvider) return [];

        const hit = (systemCatalog || []).find((item) => {
            const itemProvider = String(item?.provider || '').trim().toLowerCase();
            return String(item?.category || '') === cat && itemProvider === selectedProvider;
        });

        return [...new Set((hit?.models || []).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
    }, [systemCatalog, createCategory, createProvider]);

    const manageModelSuggestions = useMemo(() => {
        if (!selectedManageRow) return [];
        const cat = String(selectedManageRow.category || 'Tools');
        const selectedProvider = String(selectedManageRow.provider || '').trim().toLowerCase();
        if (!selectedProvider) return [];

        const hit = (systemCatalog || []).find((item) => {
            const itemProvider = String(item?.provider || '').trim().toLowerCase();
            return String(item?.category || '') === cat && itemProvider === selectedProvider;
        });

        return [...new Set((hit?.models || []).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
    }, [systemCatalog, selectedManageRow]);

    const visibleSystemSettings = useMemo(() => {
        if (selectedSystemCategory === 'All') return categorizedSystemSettings;
        return categorizedSystemSettings.filter((block) => block.category === selectedSystemCategory);
    }, [categorizedSystemSettings, selectedSystemCategory]);

    useEffect(() => {
        if (activeTab === 'billing') {
            refreshBilling();
        }
        if (activeTab === 'api') {
            refreshActiveSettingSources();
        }
        if (activeTab === 'system_api') {
            loadSystemSettingsCatalog();
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
                refreshActiveSettingSources();
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
        const withFallback = (value, fallbackValue) => {
            if (typeof value === 'string' && value.trim()) return value;
            return fallbackValue;
        };

        if (generationConfig) {
            setCharSupplements(withFallback(generationConfig.characterSupplements, DEFAULT_CHARACTER_SUPPLEMENTS));
            setSceneSupplements(withFallback(generationConfig.sceneSupplements, DEFAULT_SCENE_SUPPLEMENTS));
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
               setCharSupplements(DEFAULT_CHARACTER_SUPPLEMENTS);
               setSceneSupplements(DEFAULT_SCENE_SUPPLEMENTS);
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
                s.category === category &&
                (s.model || "") === (configData.model || "")
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

            const saved = await updateSetting(payload);
            console.log(`Synced ${category}/${backendProvider} to backend. Model: ${configData.model}`);
            return saved;
        } catch (e) {
            console.error(`Failed to sync ${category} setting to backend`, e);
            return null;
        }
    };

    const handleSave = async () => {
        // 1. Save specific provider config
        const configToSave = { apiKey, endpoint, model };
        saveProviderConfig(provider, configToSave);

        // 2. Set as active global LLM config
        setLLMConfig({
            provider,
            ...configToSave
        });

        // 3. Sync to Backend
        await syncToBackend("LLM", provider, configToSave);
        await refreshActiveSettingSources();
        showNotification(`Settings for ${provider} saved and activated`, "success");
        
        addLog(`Settings for ${provider} saved and activated`, "success");
    };

    const handleSaveGeneration = async () => {
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
        await syncToBackend("Image", imageModel, imgConfig);

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
        await syncToBackend("Video", videoModel, videoConfig);

        const visConfig = {
            apiKey: visToolKey,
            endpoint: visToolEndpoint,
            model: visToolModel
        };
        saveToolConfig(visionModel, visConfig);

        // Sync Vision to Backend
        await syncToBackend("Vision", visionModel, visConfig);

        await refreshActiveSettingSources();

        showNotification("Generation settings & credentials saved", "success");
        addLog("Generation settings & credentials saved", "success");
    };

    const handleSelectSystemSetting = async (setting) => {
        if (!setting?.id) return;
        setSelectingSystemId(setting.id);
        try {
            const selected = await selectSystemSetting(setting.id);
            if (selected?.category === 'LLM') {
                setProvider(selected.provider || 'openai');
                setEndpoint(selected.base_url || '');
                setModel(selected.model || '');
                setApiKey('');
                setLLMConfig({
                    provider: selected.provider || 'openai',
                    apiKey: '',
                    endpoint: selected.base_url || '',
                    model: selected.model || ''
                });
            }
            showNotification(`System setting activated: ${selected?.provider || setting.provider} / ${selected?.model || setting.model || ''}`, 'success');
            addLog(`Activated system API setting: ${selected?.provider || setting.provider} (${selected?.category || setting.category})`, 'success');
            await loadSystemSettingsCatalog();
            await refreshActiveSettingSources();
        } catch (err) {
            console.error('Failed to select system setting', err);
            const msg = err?.response?.data?.detail || 'Failed to activate system setting';
            showNotification(msg, 'error');
        } finally {
            setSelectingSystemId(null);
        }
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
                                onClick={() => setActiveTab('system_api')}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'system_api' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                               System API
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
                            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.LLM)}`}>
                                {sourceBadgeText(activeSettingSources.LLM)}
                            </span>
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
                                        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.Image)}`}>
                                            {sourceBadgeText(activeSettingSources.Image)}
                                        </span>
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
                                        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.Video)}`}>
                                            {sourceBadgeText(activeSettingSources.Video)}
                                        </span>
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
                                        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.Vision)}`}>
                                            {sourceBadgeText(activeSettingSources.Vision)}
                                        </span>
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
            ) : activeTab === 'system_api' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    {canManageSystemSettings && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-semibold">System API Config Editor</h2>
                            <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                                <p className="text-xs text-muted-foreground">
                                    Use this editor to fix provider authentication errors quickly (API Key / Model / Endpoint / WebHook).
                                </p>

                                <div className="space-y-3 border border-white/10 rounded-lg p-4 bg-white/5">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <h3 className="text-sm font-semibold">Effective LLM Setting Snapshot</h3>
                                        <button
                                            onClick={handleLoadEffectiveSnapshot}
                                            disabled={isSnapshotLoading}
                                            className="text-xs px-3 py-1.5 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {isSnapshotLoading ? 'Checking...' : 'Check Effective Setting'}
                                        </button>
                                    </div>

                                    {effectiveSnapshot && (
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                            <div className="space-y-1">
                                                <div className="text-muted-foreground">Source</div>
                                                <div className="font-mono">{effectiveSnapshot.source || '-'}</div>
                                            </div>
                                            <div className="space-y-1">
                                                <div className="text-muted-foreground">Setting ID</div>
                                                <div className="font-mono">{effectiveSnapshot.setting_id || '-'}</div>
                                            </div>
                                            <div className="space-y-1">
                                                <div className="text-muted-foreground">Provider / Model</div>
                                                <div className="font-mono break-all">{effectiveSnapshot.provider || '-'} / {effectiveSnapshot.model || '-'}</div>
                                            </div>
                                            <div className="space-y-1">
                                                <div className="text-muted-foreground">API Key</div>
                                                <div className="font-mono">{effectiveSnapshot.api_key_masked || '(empty)'}</div>
                                            </div>
                                            <div className="space-y-1 md:col-span-2">
                                                <div className="text-muted-foreground">Endpoint</div>
                                                <div className="font-mono break-all">{effectiveSnapshot.endpoint || '-'}</div>
                                            </div>
                                            <div className="space-y-1 md:col-span-2">
                                                <div className="text-muted-foreground">WebHook</div>
                                                <div className="font-mono break-all">{effectiveSnapshot.webhook || '-'}</div>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <div className="space-y-3 border border-white/10 rounded-lg p-4 bg-white/5">
                                    <h3 className="text-sm font-semibold">Create New System Setting</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">Name</label>
                                            <input
                                                type="text"
                                                value={createName}
                                                onChange={(e) => setCreateName(e.target.value)}
                                                placeholder="System Setting"
                                                className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">Provider *</label>
                                            <input
                                                list="system-provider-catalog"
                                                type="text"
                                                value={createProvider}
                                                onChange={(e) => setCreateProvider(e.target.value)}
                                                placeholder="openai / doubao / runway ..."
                                                className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">Category</label>
                                            <select
                                                value={createCategory}
                                                onChange={(e) => setCreateCategory(e.target.value)}
                                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                            >
                                                <option value="LLM">LLM</option>
                                                <option value="Image">Image</option>
                                                <option value="Video">Video</option>
                                                <option value="Vision">Vision</option>
                                                <option value="Tools">Tools</option>
                                            </select>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">API Key</label>
                                            <input
                                                type="password"
                                                value={createApiKey}
                                                onChange={(e) => setCreateApiKey(e.target.value)}
                                                placeholder="Optional; shared by provider"
                                                className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">Endpoint</label>
                                            <input
                                                type="text"
                                                value={createBaseUrl}
                                                onChange={(e) => setCreateBaseUrl(e.target.value)}
                                                placeholder="https://..."
                                                className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">Model</label>
                                            <input
                                                list="system-model-catalog-create"
                                                type="text"
                                                value={createModel}
                                                onChange={(e) => setCreateModel(e.target.value)}
                                                placeholder="model-id"
                                                className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                            />
                                        </div>
                                        <div className="space-y-2 md:col-span-2">
                                            <label className="text-xs font-medium uppercase text-muted-foreground">WebHook URL</label>
                                            <input
                                                type="text"
                                                value={createWebHook}
                                                onChange={(e) => setCreateWebHook(e.target.value)}
                                                placeholder="https://callback..."
                                                className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                            />
                                        </div>
                                    </div>

                                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <input
                                            type="checkbox"
                                            checked={createIsActive}
                                            onChange={(e) => setCreateIsActive(e.target.checked)}
                                            className="rounded border-white/20 bg-white/10"
                                        />
                                        Set as active for this category after create
                                    </label>

                                    <button
                                        onClick={handleCreateManagedSystemSetting}
                                        disabled={isManageCreating}
                                        className="w-full md:w-auto text-sm px-4 py-2 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {isManageCreating ? 'Creating...' : 'Create System Config'}
                                    </button>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-medium uppercase text-muted-foreground">Paste Error To Locate Setting</label>
                                    <textarea
                                        value={errorLocatorInput}
                                        onChange={(e) => setErrorLocatorInput(e.target.value)}
                                        placeholder="Error: API Error 401 [provider=doubao, model=..., endpoint=...]..."
                                        className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white min-h-[90px]"
                                    />
                                    <button
                                        onClick={handleLocateSettingFromError}
                                        className="w-full md:w-auto text-xs px-3 py-1.5 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20"
                                    >
                                        Locate From Error
                                    </button>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-medium uppercase text-muted-foreground">Target Setting</label>
                                    <select
                                        value={manageSettingId}
                                        onChange={(e) => setManageSettingId(e.target.value)}
                                        className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                    >
                                        <option value="">Select...</option>
                                        {manageableSystemSettings.map((row) => (
                                            <option key={row.id} value={row.id}>
                                                [{row.category}] {row.provider} / {row.model || '-'} (ID:{row.id})
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2 md:col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">API Key (Leave blank to keep current shared key)</label>
                                        <input
                                            type="password"
                                            value={manageApiKey}
                                            onChange={(e) => setManageApiKey(e.target.value)}
                                            placeholder="Paste new key to rotate shared provider key"
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Endpoint</label>
                                        <input
                                            type="text"
                                            value={manageBaseUrl}
                                            onChange={(e) => setManageBaseUrl(e.target.value)}
                                            placeholder="https://..."
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Model</label>
                                        <input
                                            list="system-model-catalog-manage"
                                            type="text"
                                            value={manageModel}
                                            onChange={(e) => setManageModel(e.target.value)}
                                            placeholder="doubao-seed-2-0-pro-260215"
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2 md:col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">WebHook URL</label>
                                        <input
                                            type="text"
                                            value={manageWebHook}
                                            onChange={(e) => setManageWebHook(e.target.value)}
                                            placeholder="https://your-callback..."
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                </div>

                                <button
                                    onClick={handleSaveManagedSystemSetting}
                                    disabled={!manageSettingId || isManageSaving}
                                    className="w-full md:w-auto text-sm px-4 py-2 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {isManageSaving ? 'Saving...' : 'Save System Config'}
                                </button>

                                <datalist id="system-provider-catalog">
                                    {createProviderSuggestions.map((providerItem) => (
                                        <option key={providerItem} value={providerItem} />
                                    ))}
                                </datalist>
                                <datalist id="system-model-catalog-create">
                                    {createModelSuggestions.map((modelItem) => (
                                        <option key={modelItem} value={modelItem} />
                                    ))}
                                </datalist>
                                <datalist id="system-model-catalog-manage">
                                    {manageModelSuggestions.map((modelItem) => (
                                        <option key={modelItem} value={modelItem} />
                                    ))}
                                </datalist>
                            </div>
                        </div>
                    )}

                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold">System API Settings</h2>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-medium">Select Shared Provider Configuration</h3>
                                <span className={`text-xs px-2 py-0.5 rounded border ${userCredits > 0 ? 'text-green-300 border-green-500/40 bg-green-500/10' : 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10'}`}>
                                    Credits: {userCredits}
                                </span>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                System keys are shared by provider. Choose one model config in each category as your active setting.
                            </p>

                            {!isSystemSettingsLoading && categorizedSystemSettings.length > 0 && (
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => setSelectedSystemCategory('All')}
                                        className={`text-xs px-2.5 py-1 rounded border transition-colors ${selectedSystemCategory === 'All' ? 'bg-primary/20 text-primary border-primary/40' : 'bg-white/5 text-muted-foreground border-white/10 hover:text-white hover:bg-white/10'}`}
                                    >
                                        All
                                    </button>
                                    {categorizedSystemSettings.map((block) => (
                                        <button
                                            key={block.category}
                                            onClick={() => setSelectedSystemCategory(block.category)}
                                            className={`text-xs px-2.5 py-1 rounded border transition-colors ${selectedSystemCategory === block.category ? 'bg-primary/20 text-primary border-primary/40' : 'bg-white/5 text-muted-foreground border-white/10 hover:text-white hover:bg-white/10'}`}
                                        >
                                            {block.label}
                                        </button>
                                    ))}
                                </div>
                            )}

                            {isSystemSettingsLoading ? (
                                <div className="text-sm text-muted-foreground">Loading system settings...</div>
                            ) : userCredits <= 0 ? (
                                <div className="text-sm text-yellow-300 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                                    Your credits are 0. Top up credits first to use system API settings.
                                </div>
                            ) : systemSettings.length === 0 ? (
                                <div className="text-sm text-muted-foreground">No system API settings available.</div>
                            ) : visibleSystemSettings.length === 0 ? (
                                <div className="text-sm text-muted-foreground">No settings in selected category.</div>
                            ) : (
                                <div className="space-y-4">
                                    {visibleSystemSettings.map((categoryBlock) => (
                                        <div key={categoryBlock.category} className="space-y-3">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-semibold">{categoryBlock.label}</span>
                                                <span className="text-[10px] px-2 py-0.5 rounded border border-white/20 text-muted-foreground">
                                                    {categoryBlock.groups.length} Provider{categoryBlock.groups.length > 1 ? 's' : ''}
                                                </span>
                                            </div>

                                            <div className="space-y-3">
                                                {categoryBlock.groups.map((group) => (
                                                    <div key={`${group.category}-${group.provider}`} className="border border-white/10 rounded-lg p-4 bg-white/5 space-y-3">
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <span className="text-sm font-semibold">{group.provider}</span>
                                                            {group.shared_key_configured ? (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-green-500/30 text-green-300 bg-green-500/10">Shared Key Ready</span>
                                                            ) : (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-yellow-500/30 text-yellow-300 bg-yellow-500/10">No Shared Key</span>
                                                            )}
                                                            {canManageSystemSettings && (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-white/20 text-muted-foreground">Click row to edit</span>
                                                            )}
                                                        </div>

                                                        <div className="space-y-2">
                                                            {(group.models || []).map((row) => (
                                                                <div
                                                                    key={row.id}
                                                                    onClick={() => openRowEditModal(row)}
                                                                    className={`grid grid-cols-1 md:grid-cols-12 gap-2 items-center p-2 rounded border border-white/10 bg-black/20 ${canManageSystemSettings ? 'cursor-pointer hover:bg-white/10 transition-colors' : ''}`}
                                                                >
                                                                    <div className="md:col-span-3 text-xs">
                                                                        <div className="text-muted-foreground">Model</div>
                                                                        <div className="font-mono break-all">{row.model || '-'}</div>
                                                                    </div>
                                                                    <div className="md:col-span-5 text-xs">
                                                                        <div className="text-muted-foreground">Endpoint</div>
                                                                        <div className="font-mono break-all">{row.base_url || '-'}</div>
                                                                    </div>
                                                                    <div className="md:col-span-2 text-xs">
                                                                        <div className="text-muted-foreground">WebHook</div>
                                                                        <div className="font-mono break-all">{row.webhook_url || '-'}</div>
                                                                    </div>
                                                                    <div className="md:col-span-2 flex md:justify-end">
                                                                        <button
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                handleSelectSystemSetting(row);
                                                                            }}
                                                                            disabled={!group.shared_key_configured || selectingSystemId === row.id}
                                                                            className="w-full md:w-auto text-xs px-3 py-1.5 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                                                        >
                                                                            {selectingSystemId === row.id ? 'Activating...' : (row.is_active ? 'Active' : 'Use This')}
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {canManageSystemSettings && isRowEditOpen && (
                        <div
                            onClick={closeRowEditModal}
                            className="fixed inset-0 z-[220] bg-black/70 flex items-center justify-center p-4"
                        >
                            <div
                                onClick={(e) => e.stopPropagation()}
                                className="w-full max-w-3xl bg-[#09090b] border border-white/10 rounded-xl p-5 space-y-4"
                            >
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold">Edit System API Setting</h3>
                                    <button
                                        onClick={closeRowEditModal}
                                        className="text-xs px-2 py-1 rounded border border-white/10 hover:bg-white/10"
                                    >
                                        Close
                                    </button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2 md:col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">API Key (Leave blank to keep current shared key)</label>
                                        <input
                                            type="password"
                                            value={manageApiKey}
                                            onChange={(e) => setManageApiKey(e.target.value)}
                                            placeholder="Paste new key to rotate shared provider key"
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Endpoint</label>
                                        <input
                                            type="text"
                                            value={manageBaseUrl}
                                            onChange={(e) => setManageBaseUrl(e.target.value)}
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">Model</label>
                                        <input
                                            list="system-model-catalog-manage"
                                            type="text"
                                            value={manageModel}
                                            onChange={(e) => setManageModel(e.target.value)}
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2 md:col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">WebHook URL</label>
                                        <input
                                            type="text"
                                            value={manageWebHook}
                                            onChange={(e) => setManageWebHook(e.target.value)}
                                            className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-white"
                                        />
                                    </div>
                                </div>

                                <div className="flex justify-end gap-2">
                                    <button
                                        onClick={closeRowEditModal}
                                        className="text-sm px-3 py-2 rounded border border-white/10 hover:bg-white/10"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        onClick={handleSaveFromRowEdit}
                                        disabled={!manageSettingId || isManageSaving}
                                        className="text-sm px-4 py-2 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {isManageSaving ? 'Saving...' : 'Save Changes'}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
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
