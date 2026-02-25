import { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '@/lib/store';
import { Save, Info, Upload, Download, Coins, History, Palette, CheckCircle, ArrowLeft, User, KeyRound } from 'lucide-react';
import { API_URL } from '@/config';
import { updateSetting, getSettings, getTransactions, fetchMe, getSystemSettings, selectSystemSetting, updateMyProfile, updateMyPassword, uploadMyAvatar, recordSystemLogAction } from '../services/api';
import RechargeModal from '../components/RechargeModal'; // Import RechargeModal
import { getUiLang, setUiLang as setGlobalUiLang, tUI, UI_LANG_EVENT } from '../lib/uiLang';

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

const USER_PROFILE_UPDATED_EVENT = 'aistory.user.profile.updated';

const THEMES = {
    default: {
        name: { zh: '电影暗夜', en: 'Cinematic Dark' },
        description: { zh: '深色高对比，聚焦创作内容。', en: 'Deep blacks and high contrast for focus.' },
        colors: {
            '--background': '224 71% 4%',
            '--card': '224 71% 4%',
            '--primary': '210 40% 98%',
            '--secondary': '222.2 47.4% 11.2%',
            '--muted': '223 47% 11%',
            '--border': '216 34% 17%'
        }
    },
    midnight: {
        name: { zh: '午夜蓝', en: 'Midnight Blue' },
        description: { zh: '专业感深蓝色调。', en: 'Professional deep blue tones.' },
        colors: {
            '--background': '222 47% 11%',
            '--card': '223 47% 13%',
            '--primary': '210 40% 98%',
            '--secondary': '217 33% 17%',
            '--muted': '217 33% 15%',
            '--border': '217 33% 20%'
        }
    },
    slate: {
        name: { zh: '钛灰', en: 'Titanium Slate' },
        description: { zh: '中性工业灰风格。', en: 'Neutral, industrial grey tones.' },
        colors: {
            '--background': '210 14% 12%',
            '--card': '210 14% 14%',
            '--primary': '210 40% 98%',
            '--secondary': '210 10% 20%',
            '--muted': '210 10% 18%',
            '--border': '210 10% 22%'
        }
    },
    nebula: {
        name: { zh: '星云紫', en: 'Cosmic Nebula' },
        description: { zh: '紫色深空氛围感。', en: 'Atmospheric purple and deep space vibes.' },
        colors: {
            '--background': '260 40% 8%',
            '--card': '260 40% 10%',
            '--primary': '280 70% 85%',
            '--secondary': '260 30% 18%',
            '--muted': '260 30% 14%',
            '--border': '260 30% 18%'
        }
    }
};

const Settings = () => {
    const [uiLang, setUiLang] = useState(getUiLang());
    const t = (zh, en) => tUI(uiLang, zh, en);
    const location = useLocation();
    const navigate = useNavigate();
    const { llmConfig, setLLMConfig, savedConfigs, saveProviderConfig, addLog, generationConfig, setGenerationConfig, savedToolConfigs, saveToolConfig } = useStore();
    
    // Internal state for form
    const [provider, setProvider] = useState("openai");
    const [apiKey, setApiKey] = useState("");
    const [endpoint, setEndpoint] = useState("");
    const [model, setModel] = useState("");
    
    // Hidden file input ref
    const fileInputRef = useRef(null);

    // Theme / Appearance
    const [currentTheme, setCurrentTheme] = useState('default');

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
    const [activeTab, setActiveTab] = useState('general');

    // Account Management
    const [profileName, setProfileName] = useState('');
    const [profileEmail, setProfileEmail] = useState('');
    const [profileAvatarUrl, setProfileAvatarUrl] = useState('');
    const [isSavingProfile, setIsSavingProfile] = useState(false);
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);
    const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
    
    // Billing State
    const [userCredits, setUserCredits] = useState(0);
    const [transactions, setTransactions] = useState([]);
    const [isBillingLoading, setIsBillingLoading] = useState(false);
    const [showRecharge, setShowRecharge] = useState(false); // Recharge Modal State
    const [systemSettings, setSystemSettings] = useState([]);
    const [isSystemSettingsLoading, setIsSystemSettingsLoading] = useState(false);
    const [selectingSystemId, setSelectingSystemId] = useState(null);
    const [selectedSystemCategory, setSelectedSystemCategory] = useState('All');
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
        if (tab === 'billing' || tab === 'usage') {
            setActiveTab('usage');
        } else if (tab === 'system-api' || tab === 'system_api' || tab === 'api' || tab === 'api-settings') {
            setActiveTab('api_settings');
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
            setActiveTab('usage');
            setShowRecharge(true);
        }
    }, [location.search]);

    useEffect(() => {
        const fn = () => {
            setActiveTab('usage');
            setShowRecharge(true);
        };
        window.addEventListener('SHOW_RECHARGE_MODAL', fn);
        return () => window.removeEventListener('SHOW_RECHARGE_MODAL', fn);
    }, []);

    useEffect(() => {
        if (activeTab === 'api' || activeTab === 'prompts') {
            setActiveTab('api_settings');
        }
    }, [activeTab]);

    useEffect(() => {
        const onUiLangChanged = (e) => {
            const detailLang = e?.detail;
            if (detailLang === 'zh' || detailLang === 'en') {
                setUiLang(detailLang);
            } else {
                setUiLang(getUiLang());
            }
        };

        const onStorage = (e) => {
            if (e.key === 'aistory.ui.lang') {
                setUiLang(e.newValue === 'en' ? 'en' : 'zh');
            }
        };
        window.addEventListener('storage', onStorage);
        window.addEventListener(UI_LANG_EVENT, onUiLangChanged);
        return () => {
            window.removeEventListener('storage', onStorage);
            window.removeEventListener(UI_LANG_EVENT, onUiLangChanged);
        };
    }, []);

    const handleUiLangChange = (lang) => {
        const next = lang === 'en' ? 'en' : 'zh';
        setUiLang(next);
        setGlobalUiLang(next);
    };

    const notifyUserProfileUpdated = (userData) => {
        try {
            window.dispatchEvent(new CustomEvent(USER_PROFILE_UPDATED_EVENT, { detail: userData || null }));
        } catch {
            // ignore event dispatch failures
        }
    };

    const handleExitSettings = () => {
        const params = new URLSearchParams(location.search || '');
        const returnToRaw = params.get('return_to') || '';
        const returnTo = decodeURIComponent(returnToRaw || '').trim();
        if (returnTo && returnTo.startsWith('/') && !returnTo.startsWith('//')) {
            navigate(returnTo);
            return;
        }
        if (window.history.length > 1) {
            navigate(-1);
            return;
        }
        navigate('/projects');
    };

    const handleThemeChange = (themeKey) => {
        if (!THEMES[themeKey]) return;
        setCurrentTheme(themeKey);
        const root = document.documentElement;
        Object.entries(THEMES[themeKey].colors).forEach(([property, value]) => {
            root.style.setProperty(property, value);
        });
        localStorage.setItem('theme', themeKey);
        showNotification(t('页面风格已切换', 'Theme updated'), 'success');
    };

    const trackMenuAction = (menuKey, menuLabel, actionFn) => {
        const page = `${location.pathname}${location.search}${location.hash}`;
        void recordSystemLogAction({
            action: 'MENU_CLICK',
            menu_key: menuKey,
            menu_label: menuLabel,
            page,
        });

        try {
            const actionResult = actionFn?.();
            if (actionResult && typeof actionResult.then === 'function') {
                actionResult
                    .then(() => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'success',
                        });
                    })
                    .catch((error) => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'failed',
                            details: error?.message || 'unknown error',
                        });
                    });
                return;
            }

            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'success',
            });
        } catch (error) {
            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'failed',
                details: error?.message || 'unknown error',
            });
            throw error;
        }
    };

    const loadMyProfile = async () => {
        try {
            const me = await fetchMe();
            setProfileName(me?.full_name || '');
            setProfileEmail(me?.email || '');
            setProfileAvatarUrl(me?.avatar_url || '');
        } catch (e) {
            console.error('Failed to load profile', e);
        }
    };

    const handleSaveProfile = async () => {
        setIsSavingProfile(true);
        try {
            const updated = await updateMyProfile({ full_name: profileName });
            setProfileName(updated?.full_name || '');
            setProfileEmail(updated?.email || '');
            setProfileAvatarUrl(updated?.avatar_url || '');
            notifyUserProfileUpdated(updated);
            showNotification(t('用户资料已更新', 'Profile updated'), 'success');
        } catch (e) {
            showNotification(t(`资料更新失败：${e.message}`, `Failed to update profile: ${e.message}`), 'error');
        } finally {
            setIsSavingProfile(false);
        }
    };

    const handleChangePassword = async () => {
        if (!currentPassword || !newPassword) {
            showNotification(t('请填写当前密码和新密码', 'Please enter current and new password'), 'error');
            return;
        }
        if (newPassword !== confirmPassword) {
            showNotification(t('两次输入的新密码不一致', 'New passwords do not match'), 'error');
            return;
        }

        setIsUpdatingPassword(true);
        try {
            await updateMyPassword({ current_password: currentPassword, new_password: newPassword });
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
            showNotification(t('密码修改成功', 'Password updated successfully'), 'success');
        } catch (e) {
            showNotification(t(`密码修改失败：${e.message}`, `Failed to update password: ${e.message}`), 'error');
        } finally {
            setIsUpdatingPassword(false);
        }
    };

    const handleAvatarFileChange = async (event) => {
        const file = event?.target?.files?.[0];
        if (!file) return;

        setIsUploadingAvatar(true);
        try {
            const updated = await uploadMyAvatar(file);
            setProfileAvatarUrl(updated?.avatar_url || '');
            notifyUserProfileUpdated(updated);
            showNotification(t('头像已更新', 'Avatar updated'), 'success');
        } catch (e) {
            showNotification(t(`头像上传失败：${e.message}`, `Failed to upload avatar: ${e.message}`), 'error');
        } finally {
            setIsUploadingAvatar(false);
            if (event?.target) event.target.value = '';
        }
    };

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
            const [userRes, systemRes] = await Promise.all([fetchMe(), getSystemSettings()]);
            if (userRes && userRes.credits !== undefined) {
                setUserCredits(userRes.credits);
            }
            setSystemSettings(Array.isArray(systemRes) ? systemRes : []);
        } catch (err) {
            console.error("Failed to load system API settings", err);
            setSystemSettings([]);
        } finally {
            setIsSystemSettingsLoading(false);
        }
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


    const visibleSystemSettings = useMemo(() => {
        if (selectedSystemCategory === 'All') return categorizedSystemSettings;
        return categorizedSystemSettings.filter((block) => block.category === selectedSystemCategory);
    }, [categorizedSystemSettings, selectedSystemCategory]);

    useEffect(() => {
        if (activeTab === 'usage') {
            refreshBilling();
        }
        if (activeTab === 'api_settings') {
            loadSystemSettingsCatalog();
        }
    }, [activeTab]);

    useEffect(() => {
        const savedTheme = localStorage.getItem('theme');
        const key = savedTheme && THEMES[savedTheme] ? savedTheme : 'default';
        setCurrentTheme(key);
        const root = document.documentElement;
        Object.entries(THEMES[key].colors).forEach(([property, value]) => {
            root.style.setProperty(property, value);
        });
    }, []);

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
            showNotification(`Failed to export settings: ${e?.message || 'Unknown error'}`, "error");
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
        loadMyProfile();
    }, []);

    useEffect(() => {
        if (activeTab === 'account') {
            loadMyProfile();
        }
    }, [activeTab]);

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
            const msg = err?.message || 'Failed to activate system setting';
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
                                <label className="text-sm font-medium">{t('基础 URL', 'Base URL')}</label>
                                <span className="text-xs text-muted-foreground">{t('默认值：http://localhost:11434', 'Default: http://localhost:11434')}</span>
                            </div>
                            <input 
                                type="text" 
                                value={endpoint}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder={t('http://localhost:11434', 'http://localhost:11434')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">{t('模型名称', 'Model Name')}</label>
                            <input 
                                type="text" 
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                placeholder={t('例如：llama3、mistral...', 'e.g. llama3, mistral...')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                    </>
                );
            case 'doubao':
                return (
                    <>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">{t('API 密钥', 'API Key')}</label>
                            <input 
                                type="password" 
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder={t('sk-...', 'sk-...')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">{t('模型 / 端点 ID（必填）', 'Model / Endpoint ID (Required)')}</label>
                            <input 
                                type="text" 
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                placeholder={t('ep-2024...（部署端点 ID）', 'ep-2024... (The deployment endpoint ID)')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">{t('基础 URL（可选）', 'Base URL (Optional)')}</label>
                            <input 
                                type="text" 
                                value={endpoint}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder={t('https://ark.cn-beijing.volces.com/api/v3', 'https://ark.cn-beijing.volces.com/api/v3')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                    </>
                );
            case 'grsai':
                return (
                    <>
                         <div className="space-y-2">
                                    <label className="text-sm font-medium">{t('API 密钥', 'API Key')}</label>
                            <input 
                                type="password" 
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder={t('sk-...', 'sk-...')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                         <div className="space-y-2">
                                     <label className="text-sm font-medium">{t('模型名称', 'Model Name')}</label>
                            <select 
                                value={model} 
                                onChange={(e) => setModel(e.target.value)}
                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                            >
                                <option className="bg-zinc-900" value="gemini-3-pro">{t('Gemini 3 Pro（推荐）', 'Gemini 3 Pro (Recommended)')}</option>
                                <option className="bg-zinc-900" value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                                <option className="bg-zinc-900" value="gemini-3-flash">Gemini 3 Flash</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</option>
                                <option className="bg-zinc-900" value="gemini-2.5-flash-think">Gemini 2.5 Flash Think</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">{t('基础 URL', 'Base URL')}</label>
                            <input 
                                type="text" 
                                value={endpoint || "https://grsai.dakka.com.cn"}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder={t('https://grsai.dakka.com.cn', 'https://grsai.dakka.com.cn')}
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
                                    <label className="text-sm font-medium">{t('API 密钥', 'API Key')}</label>
                            <input 
                                type="password" 
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder={t('sk-...', 'sk-...')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                         <div className="space-y-2">
                                     <label className="text-sm font-medium">{t('模型名称（可选）', 'Model Name (Optional)')}</label>
                            <input 
                                type="text" 
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                placeholder={t('例如：gpt-4o、gpt-4-turbo...', 'e.g. gpt-4o, gpt-4-turbo...')}
                                className="w-full p-2 rounded-md bg-white/10 border border-white/10" 
                            />
                        </div>
                        <div className="space-y-2">
                            <div className="flex gap-2 items-center">
                                <label className="text-sm font-medium">{t('端点 URL（可选）', 'Endpoint URL (Optional)')}</label>
                                <div className="group relative">
                                    <Info size={12} className="text-muted-foreground cursor-help" />
                                    <div className="absolute left-0 bottom-full mb-2 w-48 p-2 bg-black text-white text-xs rounded border border-white/10 hidden group-hover:block z-50">
                                        {t('可用于 OneAPI 等兼容代理。', 'Use this for compatible proxies like OneAPI')}
                                    </div>
                                </div>
                            </div>
                            <input 
                                type="text" 
                                value={endpoint}
                                onChange={(e) => setEndpoint(e.target.value)}
                                placeholder={t('https://api.openai.com/v1', 'https://api.openai.com/v1')}
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
                                onClick={() => trackMenuAction('settings.tab.general', t('常规', 'General'), () => setActiveTab('general'))}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'general' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                                         {t('常规', 'General')}
                            </button>
                            <button 
                                onClick={() => trackMenuAction('settings.tab.api_settings', t('API 设置', 'API Settings'), () => setActiveTab('api_settings'))}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'api_settings' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                                         {t('API 设置', 'API Settings')}
                            </button>
                            <button
                                onClick={() => trackMenuAction('settings.tab.account', t('用户管理', 'Account'), () => setActiveTab('account'))}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'account' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                                {t('用户管理', 'Account')}
                            </button>
                        <button 
                             onClick={() => trackMenuAction('settings.tab.usage', t('用量', 'Usage'), () => setActiveTab('usage'))}
                             className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'usage' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                        >
                            <span className="flex items-center gap-2"><Coins size={14}/> {t('用量', 'Usage')}</span>
                        </button>
                    </div>
                </div>

                <div className="flex gap-2 shrink-0 items-center">
                    <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-2 py-1.5 rounded-lg">
                        <span className="text-[11px] text-muted-foreground">{t('界面语言', 'UI Language')}</span>
                        <div className="flex bg-black/20 rounded-md p-0.5 border border-white/10">
                            <button
                                onClick={() => trackMenuAction('settings.ui_lang.zh', '中文', () => handleUiLangChange('zh'))}
                                className={`px-2 py-1 rounded text-[11px] transition-colors ${uiLang === 'zh' ? 'bg-primary text-black font-medium' : 'text-muted-foreground hover:text-white'}`}
                            >
                                中文
                            </button>
                            <button
                                onClick={() => trackMenuAction('settings.ui_lang.en', 'EN', () => handleUiLangChange('en'))}
                                className={`px-2 py-1 rounded text-[11px] transition-colors ${uiLang === 'en' ? 'bg-primary text-black font-medium' : 'text-muted-foreground hover:text-white'}`}
                            >
                                EN
                            </button>
                        </div>
                    </div>
                    <button 
                        onClick={() => trackMenuAction('settings.action.import', t('导入', 'Import'), handleImportClick)}
                        className="flex items-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors"
                        title={t('导入设置 JSON', 'Import Settings JSON')}
                    >
                        <Upload size={14} />
                        <span>{t('导入', 'Import')}</span>
                    </button>
                    <button 
                        onClick={() => trackMenuAction('settings.action.export', t('导出', 'Export'), handleExportSettings)}
                        className="flex items-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors"
                        title={t('导出设置 JSON', 'Export Settings JSON')}
                    >
                        <Download size={14} />
                        <span>{t('导出', 'Export')}</span>
                    </button>
                    <button
                        onClick={() => trackMenuAction('settings.action.exit', t('退出', 'Exit'), handleExitSettings)}
                        className="flex items-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors"
                        title={t('退出设置并返回来源页面', 'Exit settings and return to caller page')}
                    >
                        <ArrowLeft size={14} />
                        <span>{t('退出', 'Exit')}</span>
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

            {activeTab === 'general' && (
            <section className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                    <Palette className="w-5 h-5 text-primary" />
                    {t('页面风格', 'Page Appearance')}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Object.entries(THEMES).map(([themeKey, theme]) => (
                        <button
                            key={themeKey}
                            onClick={() => handleThemeChange(themeKey)}
                            className={`text-left rounded-xl border p-4 transition-all ${currentTheme === themeKey ? 'border-primary ring-2 ring-primary/20 bg-white/10' : 'border-white/10 bg-white/5 hover:bg-white/10'}`}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <div className="text-sm font-bold">{t(theme.name.zh, theme.name.en)}</div>
                                {currentTheme === themeKey && <CheckCircle className="w-4 h-4 text-green-400" />}
                            </div>
                            <div className="text-xs text-muted-foreground">{t(theme.description.zh, theme.description.en)}</div>
                        </button>
                    ))}
                </div>
            </section>
            )}

            {activeTab === 'account' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <section className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <User className="w-5 h-5 text-primary" />
                            {t('用户资料', 'Profile')}
                        </h2>

                        <div className="flex flex-col sm:flex-row gap-4 sm:items-center">
                            <div className="w-20 h-20 rounded-full overflow-hidden border border-white/20 bg-white/5 flex items-center justify-center shrink-0">
                                {profileAvatarUrl ? (
                                    <img src={profileAvatarUrl} alt="avatar" className="w-full h-full object-cover" />
                                ) : (
                                    <User className="w-8 h-8 text-muted-foreground" />
                                )}
                            </div>
                            <div className="space-y-2">
                                <label className="text-xs text-muted-foreground uppercase font-bold">{t('头像', 'Avatar')}</label>
                                <input
                                    type="file"
                                    accept="image/png,image/jpeg,image/webp"
                                    onChange={handleAvatarFileChange}
                                    disabled={isUploadingAvatar}
                                    className="block text-sm text-muted-foreground file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:bg-white/10 file:text-white hover:file:bg-white/20"
                                />
                                <div className="text-xs text-muted-foreground">{isUploadingAvatar ? t('上传中...', 'Uploading...') : t('支持 PNG/JPG/WEBP', 'PNG/JPG/WEBP supported')}</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">{t('名称', 'Name')}</label>
                                <input
                                    type="text"
                                    value={profileName}
                                    onChange={(e) => setProfileName(e.target.value)}
                                    placeholder={t('输入你的显示名称', 'Enter your display name')}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">{t('邮箱', 'Email')}</label>
                                <input
                                    type="text"
                                    value={profileEmail}
                                    readOnly
                                    className="w-full p-2 rounded-md bg-white/5 border border-white/10 text-muted-foreground"
                                />
                            </div>
                        </div>

                        <button
                            onClick={handleSaveProfile}
                            disabled={isSavingProfile}
                            className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:opacity-90 disabled:opacity-50"
                        >
                            {isSavingProfile ? t('保存中...', 'Saving...') : t('保存资料', 'Save Profile')}
                        </button>
                    </section>

                    <section className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <KeyRound className="w-5 h-5 text-primary" />
                            {t('修改密码', 'Change Password')}
                        </h2>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">{t('当前密码', 'Current Password')}</label>
                                <input
                                    type="password"
                                    value={currentPassword}
                                    onChange={(e) => setCurrentPassword(e.target.value)}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">{t('新密码', 'New Password')}</label>
                                <input
                                    type="password"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">{t('确认新密码', 'Confirm New Password')}</label>
                                <input
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                />
                            </div>
                        </div>

                        <button
                            onClick={handleChangePassword}
                            disabled={isUpdatingPassword}
                            className="px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-sm font-bold hover:bg-white/20 disabled:opacity-50"
                        >
                            {isUpdatingPassword ? t('更新中...', 'Updating...') : t('更新密码', 'Update Password')}
                        </button>
                    </section>
                </div>
            )}
            
            {activeTab === 'usage' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="grid grid-cols-1 gap-6">
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 shadow-sm flex flex-col items-center justify-center text-center relative">
                             <div className="absolute top-4 right-4">
                                <button
                                    onClick={() => setShowRecharge(true)}
                                    className="bg-green-500 hover:bg-green-600 text-white font-medium py-1.5 px-3 rounded-lg transition-colors flex items-center justify-center gap-1 text-xs shadow-lg shadow-green-500/20"
                                >
                                    <Coins size={14} />
                                    {t('充值', 'Top Up')}
                                </button>
                             </div>
                             <Coins className="w-12 h-12 text-yellow-400 mb-4 mt-2" />
                             <h3 className="text-muted-foreground font-medium">{t('可用积分', 'Available Credits')}</h3>
                             <p className="text-4xl font-bold text-white mt-2">{userCredits}</p>
                             <p className="text-xs text-muted-foreground mt-2 mb-4">{t('生成任务会消耗积分。', 'Credits are deducted for generation tasks.')}</p>
                             <button
                                onClick={() => setShowRecharge(true)}
                                className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm"
                             >
                                <Coins size={14} />
                                {t('充值套餐', 'Recharge Bundle')}
                             </button>
                        </div>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 shadow-sm">
                             <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                <History className="w-5 h-5" /> {t('最近交易', 'Recent Transactions')}
                             </h3>
                             {isBillingLoading ? (
                                <div className="text-center py-10 text-muted-foreground">{t('加载记录中...', 'Loading history...')}</div>
                             ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse text-sm">
                                        <thead>
                                            <tr className="border-b border-white/10 text-muted-foreground">
                                                <th className="p-3">{t('时间', 'Time')}</th>
                                                <th className="p-3">{t('类型', 'Type')}</th>
                                                <th className="p-3">{t('详情', 'Details')}</th>
                                                <th className="p-3 text-right">{t('金额', 'Amount')}</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {transactions.length === 0 ? (
                                                <tr><td colSpan="4" className="text-center p-8 text-muted-foreground">{t('暂无交易记录', 'No transactions found')}</td></tr>
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
                                showNotification(t('充值成功！', 'Recharge successful!'), "success");
                            }}
                        />                                
                    )}
                </div>
            ) : activeTab === 'api' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">
                            {t('核心 LLM 配置', 'Core LLM Configuration')}
                            <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full border border-primary/30 font-mono">{t('任务：llm_chat', 'Task: llm_chat')}</span>
                            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.LLM)}`}>
                                {sourceBadgeText(activeSettingSources.LLM)}
                            </span>
                        </h2>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">{t('文本模型提供方', 'Text Model Provider')}</label>
                                <select 
                                    value={provider} 
                                    onChange={(e) => handleProviderChange(e.target.value)}
                                    className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                >
                                        <option className="bg-zinc-900" value="openai">{t('OpenAI / 兼容接口', 'OpenAI / Compatible')}</option>
                                    <option className="bg-zinc-900" value="doubao">{t('豆包（火山引擎）', 'Doubao (Volcengine)')}</option>
                                    <option className="bg-zinc-900" value="ollama">{t('Ollama（本地）', 'Ollama (Local)')}</option>
                                        <option className="bg-zinc-900" value="deepseek">{t('DeepSeek（深度求索）', 'DeepSeek')}</option>
                                    <option className="bg-zinc-900" value="grsai">{t('Grsai（聚合）', 'Grsai (Aggregation)')}</option>
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
                                <span>{t('保存并激活配置', 'Save & Activate Configuration')}</span>
                            </button>
                            
                            <p className="text-xs text-center text-muted-foreground mt-2">
                                {t('每个提供方的参数都会自动保存。', 'Parameters are saved automatically for each provider.')}
                            </p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold">{t('图片与视频工具 API', 'Image & Video Tools API')}</h2>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-6 shadow-sm">
                            {/* Translation Tool Section */}
                            <div className="space-y-4 border-b border-white/10 pb-6">
                                <h3 className="text-base font-medium flex items-center gap-2">
                                    {t('翻译服务（百度）', 'Translation Service (Baidu)')}
                                </h3>
                                <p className="text-xs text-muted-foreground">{t('配置百度翻译 API 以启用提示词翻译能力。', 'Configure Baidu Translate API to enable prompt translation features.')}</p>

                                <form 
                                    onSubmit={(e) => { e.preventDefault(); handleSaveTranslation(); }}
                                    className="grid grid-cols-1 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in"
                                >
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground flex items-center justify-between">
                                            <span>{t('访问令牌', 'Access Token')}</span>
                                            <a href="https://console.bce.baidu.com/ai/#/ai/machine_learning/overview/index" target="_blank" rel="noreferrer" className="text-[10px] text-blue-400 hover:underline">{t('获取 Token', 'Get Token')}</a>
                                        </label>
                                        <input 
                                            type="password" 
                                            value={baiduToken}
                                            onChange={(e) => setBaiduToken(e.target.value)}
                                            placeholder={t('粘贴百度 AI Access Token...', 'Paste Baidu AI Access Token...')}
                                            autoComplete="new-password"
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                        <p className="text-[10px] text-muted-foreground">
                                            {t("需要在百度云启用 'machine_translation' 或同等能力。输入 Access Token（以 '24.' 开头）。", "Requires 'machine_translation' or equivalent capability enabled on Baidu Cloud. Enter the Access Token (starts with '24.').")}
                                        </p>
                                    </div>
                                    <div>
                                        <button 
                                            type="submit"
                                            className="text-xs bg-primary/10 text-primary hover:bg-primary/20 px-3 py-2 rounded transition-colors w-full"
                                        >
                                            {t('保存翻译 Token', 'Save Translation Token')}
                                        </button>
                                    </div>
                                </form>
                            </div>
                            
                            {/* Image Tool Section */}
                            <div className="space-y-4 border-b border-white/10 pb-6">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-blue-400 flex items-center gap-2">
                                        {t('图片生成工具', 'Image Generation Tool')}
                                        <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded border border-blue-500/30 font-mono">{t('任务：image_gen', 'Task: image_gen')}</span>
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
                                        <option className="bg-zinc-900" value="Doubao">{t('Doubao（豆包 - 火山引擎）', 'Doubao (豆包 - Volcengine)')}</option>
                                        <option className="bg-zinc-900" value="Grsai-Image">{t('Grsai（聚合）', 'Grsai (Aggregation)')}</option>
                                        <option className="bg-zinc-900" value="DALL-E 3">DALL-E 3</option>
                                        <option className="bg-zinc-900" value="Stable Diffusion">{t('Stable Diffusion（SDXL/Pony）', 'Stable Diffusion (SDXL/Pony)')}</option>
                                        <option className="bg-zinc-900" value="Flux">Flux.1</option>
                                        <option className="bg-zinc-900" value="Tencent Hunyuan">{t('腾讯混元（Tencent Hunyuan）', 'Tencent Hunyuan (腾讯混元)')}</option>
                                    </select>
                                    <p className="text-xs text-muted-foreground">{t('选择工具以配置凭据和提示词优化参数。', 'Select tool to configure credentials and prompt optimization.')}</p>
                                </div>
                                
                                {/* Dynamic fields for Image Tool */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in">
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('API 密钥', 'API Key')}</label>
                                        <input 
                                            type="password" 
                                            value={imgToolKey}
                                            onChange={(e) => setImgToolKey(e.target.value)}
                                            placeholder={
                                                imageModel === "Midjourney" ? t('网页版无需填写', 'Not required for web use') : 
                                                imageModel === "Tencent Hunyuan" ? t('SecretId:SecretKey', 'SecretId:SecretKey') :
                                                "sk-..."
                                            }
                                            disabled={imageModel === "Midjourney"}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('端点 URL', 'Endpoint URL')}</label>
                                        <input 
                                            type="text" 
                                            value={imgToolEndpoint}
                                            onChange={(e) => setImgToolEndpoint(e.target.value)}
                                            placeholder={t('https://api...', 'https://api...')}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('模型 ID', 'Model ID')}</label>
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
                                                placeholder={t('例如：doubao-seedream-4-5-251128', 'e.g. doubao-seedream-4-5-251128')}
                                                className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                            />
                                        )}
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('宽度（px）', 'Width (px)')}</label>
                                        <input 
                                            type="number" 
                                            value={imgToolWidth}
                                            onChange={(e) => setImgToolWidth(e.target.value)}
                                            placeholder={t('1024', '1024')}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('高度（px）', 'Height (px)')}</label>
                                        <input 
                                            type="number" 
                                            value={imgToolHeight}
                                            onChange={(e) => setImgToolHeight(e.target.value)}
                                            placeholder={t('1024', '1024')}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('回调 URL（Webhook）', 'WebHook URL')}</label>
                                        <input 
                                            type="text" 
                                            value={imgToolWebHook}
                                            onChange={(e) => setImgToolWebHook(e.target.value)}
                                            placeholder={t('例如：https://your-callback.com/...', 'e.g. https://your-callback.com/...')}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Video Tool Section */}
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-orange-400 flex items-center gap-2">
                                        {t('视频生成工具', 'Video Generation Tool')}
                                        <span className="text-[10px] bg-orange-500/20 text-orange-300 px-1.5 py-0.5 rounded border border-orange-500/30 font-mono">{t('任务：video_gen', 'Task: video_gen')}</span>
                                        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.Video)}`}>
                                            {sourceBadgeText(activeSettingSources.Video)}
                                        </span>
                                    </label>
                                    <select 
                                        value={videoModel}
                                        onChange={(e) => handleVideoToolChange(e.target.value)}
                                        className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                    >
                                        <option className="bg-zinc-900" value="Runway">{t('Runway Gen-2/Gen-3（跑道）', 'Runway Gen-2/Gen-3')}</option>
                                        <option className="bg-zinc-900" value="Luma">{t('Luma 梦境引擎', 'Luma Dream Machine')}</option>
                                        <option className="bg-zinc-900" value="Kling">{t('Kling AI（可灵）', 'Kling AI (可灵)')}</option>
                                        <option className="bg-zinc-900" value="Sora">Sora (OpenAI)</option>
                                        <option className="bg-zinc-900" value="Grsai-Video">{t('Grsai（标准）', 'Grsai (Standard)')}</option>
                                        <option className="bg-zinc-900" value="Grsai-Video (Upload)">{t('Grsai（文件上传）', 'Grsai (File Upload)')}</option>
                                        <option className="bg-zinc-900" value="Stable Video">{t('Stable Video 组件', 'Stable Video Component')}</option>
                                        <option className="bg-zinc-900" value="Doubao Video">{t('Doubao（豆包 - 火山引擎）', 'Doubao (豆包 - Volcengine)')}</option>
                                        <option className="bg-zinc-900" value="Wanxiang">{t('Wanxiang（通义万相 - 阿里云）', 'Wanxiang (通义万相 - Aliyun)')}</option>
                                        <option className="bg-zinc-900" value="Vidu (Video)">{t('Vidu（生数）', 'Vidu (Shengshu)')}</option>
                                    </select>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white/5 p-4 rounded-lg animate-in fade-in">
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('API 密钥', 'API Key')}</label>
                                        <input 
                                            type="password" 
                                            value={vidToolKey}
                                            onChange={(e) => setVidToolKey(e.target.value)}
                                            placeholder={t('密钥...', 'Key...')}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2 md:col-span-1">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('端点', 'Endpoint')}</label>
                                        <input 
                                            type="text" 
                                            value={vidToolEndpoint}
                                            onChange={(e) => handleVidEndpointChange(e.target.value)}
                                            placeholder={t('可选', 'Optional')}
                                            className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                        />
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('模型 ID', 'Model ID')}</label>
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
                                                    placeholder={t('例如：vidu2.0，或从列表选择', 'e.g. vidu2.0 or select from list')}
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
                                                <p className="text-[10px] text-muted-foreground mt-1">{t('可从列表选择或手动输入模型 ID', 'Select or type custom model ID')}</p>
                                            </>
                                        ) : (
                                            <input 
                                                type="text" 
                                                value={vidToolModel}
                                                onChange={(e) => handleVidSubModelChange(e.target.value)}
                                                placeholder={t('例如：doubao-seedance-1-5-pro-251215', 'e.g. doubao-seedance-1-5-pro-251215')}
                                                className="w-full p-2 text-sm rounded-md bg-white/10 border border-white/10 text-white" 
                                            />
                                        )}
                                    </div>
                                    <div className="space-y-2 col-span-2">
                                        <label className="text-xs font-medium uppercase text-muted-foreground">{t('回调 URL（Webhook）', 'WebHook URL')}</label>
                                        <input 
                                            type="text" 
                                            value={vidToolWebHook}
                                            onChange={(e) => setVidToolWebHook(e.target.value)}
                                            placeholder={t('例如：https://your-callback.com/...', 'e.g. https://your-callback.com/...')}
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
                                                    {t('草稿模式（样片模式）', 'Draft Mode (Sample Mode)')}
                                                </label>
                                                <span className="text-[10px] text-muted-foreground leading-tight">
                                                    {t('仅 Seedance 1.5 pro 支持控制是否开启样片模式。', 'Only Seedance 1.5 pro supports controlling whether to enable sample mode.')}<br/>
                                                    {t('True：开启样片模式，可生成高度一致的 5 秒视频。', 'True: Indicates that the sample mode is turned on, allowing for the generation of a highly consistent 5s video.')}<br/>
                                                    {t('False：普通生成模式。', 'False: Normal generation mode.')}
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
                                        {t('视觉 / 图像识别工具', 'Vision / Image Recognition Tool')}
                                        <span className="text-[10px] bg-pink-500/20 text-pink-300 px-1.5 py-0.5 rounded border border-pink-500/30 font-mono">{t('任务：analysis', 'Task: analysis')}</span>
                                        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${sourceBadgeClass(activeSettingSources.Vision)}`}>
                                            {sourceBadgeText(activeSettingSources.Vision)}
                                        </span>
                                    </label>
                                    <select 
                                        value={visionModel}
                                        onChange={(e) => setVisionModel(e.target.value)}
                                        className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white"
                                    >
                                        <option className="bg-zinc-900" value="Grsai-Vision">{t('Grsai（视觉能力）', 'Grsai (Vision Capability)')}</option>
                                    </select>
                                    <p className="text-xs text-muted-foreground">
                                        {t('用于图像场景分析、图像转文本等，兼容 OpenAI Vision API 格式。', 'Used for Scene Analysis from Image, Image to Text, etc. Compatible with OpenAI Vision API format.')}
                                    </p>
                                </div>
                                
                                {visionModel === "Grsai-Vision" && (
                                    <div className="space-y-2 pl-4 border-l-2 border-pink-400/30">
                                         <div className="space-y-1">
                                            <label className="text-xs font-medium text-muted-foreground">{t('API 密钥', 'API Key')}</label>
                                            <input 
                                                type="password" 
                                                value={visToolKey}
                                                onChange={(e) => setVisToolKey(e.target.value)}
                                                placeholder={t('sk-...', 'sk-...')}
                                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white text-sm"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium text-muted-foreground">{t('端点 URL', 'Endpoint URL')}</label>
                                            <input 
                                                type="text" 
                                                value={visToolEndpoint}
                                                onChange={(e) => setVisToolEndpoint(e.target.value)}
                                                placeholder={t('https://grsaiapi.com/v1/chat/completions', 'https://grsaiapi.com/v1/chat/completions')}
                                                className="w-full p-2 rounded-md bg-zinc-900 border border-white/10 text-white text-sm"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium text-muted-foreground">{t('模型名称（ID）', 'Model Name (ID)')}</label>
                                            <input 
                                                type="text" 
                                                value={visToolModel}
                                                onChange={(e) => setVisToolModel(e.target.value)}
                                                placeholder={t('例如：gemini-3-pro、gemini-2.5-pro 等', 'e.g. gemini-3-pro, gemini-2.5-pro, etc.')}
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
                                <span>{t('保存工具凭据', 'Save Tool Credentials')}</span>

                            </button>
                        </div>
                    </div>
                </div>
            ) : activeTab === 'api_settings' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold">{t('系统 API 设置', 'System API Settings')}</h2>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-medium">{t('选择共享提供方配置', 'Select Shared Provider Configuration')}</h3>
                                <span className={`text-xs px-2 py-0.5 rounded border ${userCredits > 0 ? 'text-green-300 border-green-500/40 bg-green-500/10' : 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10'}`}>
                                    {t('积分', 'Credits')}: {userCredits}
                                </span>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {t('系统密钥按提供方共享。你可以在每个类别中选择一个模型配置作为当前激活项；可计费动作会在调用时校验积分。', 'System keys are shared by provider. Choose one model config in each category as your active setting. Credits are checked at call time for billable actions.')}
                            </p>

                            {!isSystemSettingsLoading && categorizedSystemSettings.length > 0 && (
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => setSelectedSystemCategory('All')}
                                        className={`text-xs px-2.5 py-1 rounded border transition-colors ${selectedSystemCategory === 'All' ? 'bg-primary/20 text-primary border-primary/40' : 'bg-white/5 text-muted-foreground border-white/10 hover:text-white hover:bg-white/10'}`}
                                    >
                                        {t('全部', 'All')}
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
                                <div className="text-sm text-muted-foreground">{t('加载系统设置中...', 'Loading system settings...')}</div>
                            ) : systemSettings.length === 0 ? (
                                <div className="text-sm text-muted-foreground">{t('暂无系统 API 设置。', 'No system API settings available.')}</div>
                            ) : visibleSystemSettings.length === 0 ? (
                                <div className="text-sm text-muted-foreground">{t('所选类别下暂无设置。', 'No settings in selected category.')}</div>
                            ) : (
                                <div className="space-y-4">
                                    {visibleSystemSettings.map((categoryBlock) => (
                                        <div key={categoryBlock.category} className="space-y-3">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-semibold">{categoryBlock.label}</span>
                                                <span className="text-[10px] px-2 py-0.5 rounded border border-white/20 text-muted-foreground">
                                                    {categoryBlock.groups.length} {t(categoryBlock.groups.length > 1 ? '个提供方' : '个提供方', categoryBlock.groups.length > 1 ? 'Providers' : 'Provider')}
                                                </span>
                                            </div>

                                            <div className="space-y-3">
                                                {categoryBlock.groups.map((group) => (
                                                    <div key={`${group.category}-${group.provider}`} className="border border-white/10 rounded-lg p-4 bg-white/5 space-y-3">
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <span className="text-sm font-semibold">{group.provider}</span>
                                                            {group.shared_key_configured ? (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-green-500/30 text-green-300 bg-green-500/10">{t('共享密钥已就绪', 'Shared Key Ready')}</span>
                                                            ) : (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-yellow-500/30 text-yellow-300 bg-yellow-500/10">{t('无共享密钥', 'No Shared Key')}</span>
                                                            )}
                                                        </div>

                                                        <div className="space-y-2">
                                                            {(group.models || []).map((row) => (
                                                                <div
                                                                    key={row.id}
                                                                    className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center p-2 rounded border border-white/10 bg-black/20"
                                                                >
                                                                    <div className="md:col-span-9 text-xs">
                                                                        <div className="text-muted-foreground">{t('模型', 'Model')}</div>
                                                                        <div className="font-mono break-all">{row.model || '-'}</div>
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
                                                                            {selectingSystemId === row.id ? t('激活中...', 'Activating...') : (row.is_active ? t('已激活', 'Active') : t('使用此配置', 'Use This'))}
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
                </div>
            ) : null}
        </div>
    )
}

export default Settings;
