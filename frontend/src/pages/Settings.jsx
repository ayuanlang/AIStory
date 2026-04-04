import { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '@/lib/store';
import { Save, Info, Upload, Download, Coins, History, Palette, CheckCircle, ArrowLeft, User, KeyRound, Link as LinkIcon, Copy } from 'lucide-react';
import { API_URL } from '@/config';
import { getFunctionApiConfigs, updateSetting, getSettings, getTransactions, fetchMe, getSystemSettings, getUserPreferences, selectSystemSetting, updateMyProfile, updateMyPassword, uploadMyAvatar, recordSystemLogAction, getAutoDownloadLocalPreference, setAutoDownloadLocalPreference, getPromptSubmitLanguagePreference, setPromptSubmitLanguagePreference, normalizePromptSubmitLanguagePreference, updateUserPreferences, getHomepageShareLink } from '../services/api';
import RechargeModal from '../components/RechargeModal'; // Import RechargeModal
import { getUiLang, setUiLang as setGlobalUiLang, tUI, UI_LANG_EVENT } from '../lib/uiLang';
import { formatProviderLabel } from '../lib/providerLabel';

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
    },
    emerald: {
        name: { zh: '祖母绿幕', en: 'Emerald Noir' },
        description: { zh: '冷静青绿色，清晰层次。', en: 'Calm teal accents with clear layering.' },
        colors: {
            '--background': '168 44% 7%',
            '--card': '168 42% 9%',
            '--primary': '160 72% 78%',
            '--secondary': '167 30% 16%',
            '--muted': '167 26% 13%',
            '--border': '167 30% 18%'
        }
    },
    ember: {
        name: { zh: '余烬红', en: 'Ember Red' },
        description: { zh: '低饱和暖红，电影质感。', en: 'Muted warm reds with cinematic mood.' },
        colors: {
            '--background': '6 36% 8%',
            '--card': '6 34% 10%',
            '--primary': '12 84% 82%',
            '--secondary': '8 24% 17%',
            '--muted': '8 22% 14%',
            '--border': '8 24% 20%'
        }
    }
};

const Settings = () => {
    const [uiLang, setUiLang] = useState(getUiLang());
    const t = (zh, en) => tUI(uiLang, zh, en);
    const formatSamplePrices = (samplePrices) => {
        const safe = (Array.isArray(samplePrices) ? samplePrices : [])
            .map((v) => Number(v || 0))
            .filter((v) => Number.isFinite(v) && v > 0);
        if (safe.length === 0) {
            return '-';
        }
        return safe.join(' / ');
    };
    const normalizePositiveNumber = (value) => {
        const num = Number(value || 0);
        return Number.isFinite(num) && num > 0 ? num : 0;
    };
    const pickFirst = (obj, keys = []) => {
        for (const key of keys) {
            if (obj && Object.prototype.hasOwnProperty.call(obj, key) && obj[key] !== undefined && obj[key] !== null) {
                return obj[key];
            }
        }
        return undefined;
    };
    const buildPriceDisplay = (row) => {
        const source = String(
            pickFirst(row, ['avg_price_source', 'avgPriceSource', 'provider_price_source', 'providerPriceSource']) || ''
        ).trim().toLowerCase();
        const isMultiplierScore = source.includes('charge_multiplier_x100');
        const avg = normalizePositiveNumber(
            pickFirst(row, ['avg_price_estimate', 'avgPriceEstimate', 'provider_avg_price_estimate', 'providerAvgPriceEstimate'])
        );
        const rawSamples = pickFirst(row, ['sample_prices', 'samplePrices', 'provider_sample_prices', 'providerSamplePrices']);
        const samples = (Array.isArray(rawSamples) ? rawSamples : [])
            .map((v) => normalizePositiveNumber(v))
            .filter((v) => v > 0);
        const rangeMin = normalizePositiveNumber(
            pickFirst(row, ['price_range_min', 'priceRangeMin', 'provider_price_range_min', 'providerPriceRangeMin'])
        );
        const rangeMax = normalizePositiveNumber(
            pickFirst(row, ['price_range_max', 'priceRangeMax', 'provider_price_range_max', 'providerPriceRangeMax'])
        );
        const hasRange = rangeMin > 0 || rangeMax > 0;
        const rangeLabelMin = rangeMin > 0 ? rangeMin : '-';
        const rangeLabelMax = rangeMax > 0 ? rangeMax : '-';
        const avgLabel = avg > 0 ? avg : '-';
        const pretty = (value) => {
            const num = Number(value || 0);
            if (!Number.isFinite(num) || num <= 0) return '-';
            if (!isMultiplierScore) return num;
            const scaled = num / 100;
            return Number.isInteger(scaled) ? String(scaled) : scaled.toFixed(2).replace(/\.00$/, '');
        };

        return {
            avg,
            avgLabel: pretty(avgLabel),
            rangeMin,
            rangeMax,
            hasRange,
            rangeLabelMin: pretty(rangeLabelMin),
            rangeLabelMax: pretty(rangeLabelMax),
            samples,
            hasAny: avg > 0 || hasRange || samples.length > 0,
            isMultiplierScore,
        };
    };
    const formatBillingUnitType = (value) => {
        const unit = String(value || '').trim().toLowerCase();
        if (!unit) return '-';
        const unitLabelMap = {
            per_call: t('按次', 'Per Call'),
            per_second: t('按秒', 'Per Second'),
            per_minute: t('按分钟', 'Per Minute'),
            per_token: t('按 Token', 'Per Token'),
            per_1k_tokens: t('每 1K Token', 'Per 1K Tokens'),
            per_million_tokens: t('每百万 Token', 'Per Million Tokens'),
        };
        return unitLabelMap[unit] || unit;
    };
    const formatTransactionDateTime = (value) => {
        const raw = String(value || '').trim();
        if (!raw) return '-';

        let normalized = raw.replace(' ', 'T');
        const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
        if (!hasTimezone) {
            normalized = `${normalized}Z`;
        }
        normalized = normalized.replace(/\.(\d{3})\d+(?=(?:Z|[+-]\d{2}:?\d{2})$)/i, '.$1');

        const parsed = new Date(normalized);
        if (Number.isNaN(parsed.getTime())) {
            return raw;
        }
        return parsed.toLocaleString();
    };
    const getTransactionProviderUsage = (txn) => {
        const details = txn?.details && typeof txn.details === 'object' ? txn.details : {};
        const usage = details?.provider_usage && typeof details.provider_usage === 'object'
            ? details.provider_usage
            : details?.usage && typeof details.usage === 'object'
                ? details.usage
                : null;
        if (!usage) return null;

        const items = [
            { key: 'thirdPartyConsumeMoney', label: t('第三方消耗金额', 'Third-Party Cost') },
            { key: 'consumeMoney', label: t('供应商消耗金额', 'Provider Cost') },
            { key: 'consumeCoins', label: t('消耗点数', 'Consumed Coins') },
            { key: 'taskCostTime', label: t('任务耗时', 'Task Cost Time') },
        ].filter((item) => usage[item.key] !== undefined && usage[item.key] !== null && String(usage[item.key]).trim() !== '');

        if (items.length === 0) return null;

        return {
            items,
            source: String(details?.usage_source || '').trim(),
        };
    };
    const renderTransactionProviderUsage = (txn) => {
        const usageInfo = getTransactionProviderUsage(txn);
        if (!usageInfo) return null;

        const summaryText = usageInfo.items
            .slice(0, 2)
            .map((item) => `${item.label}: ${txn.details.provider_usage?.[item.key] ?? txn.details.usage?.[item.key]}`)
            .join(' · ');

        return (
            <details className="mt-2 rounded-lg border border-cyan-400/20 bg-cyan-500/5 p-2">
                <summary className="cursor-pointer list-none text-xs font-medium text-cyan-200">
                    {t('供应商用量审计', 'Provider Usage Audit')}
                    {summaryText ? <span className="ml-2 text-[11px] text-cyan-100/70">{summaryText}</span> : null}
                </summary>
                <div className="mt-2 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                    {usageInfo.items.map((item) => (
                        <div key={item.key} className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5">
                            <div className="text-[10px] uppercase tracking-wide text-cyan-100/60">{item.label}</div>
                            <div className="mt-1 font-mono text-cyan-50 break-all">{String(txn.details.provider_usage?.[item.key] ?? txn.details.usage?.[item.key] ?? '')}</div>
                        </div>
                    ))}
                    {usageInfo.source ? (
                        <div className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5">
                            <div className="text-[10px] uppercase tracking-wide text-cyan-100/60">{t('来源', 'Source')}</div>
                            <div className="mt-1 font-mono text-cyan-50 break-all">{usageInfo.source}</div>
                        </div>
                    ) : null}
                </div>
            </details>
        );
    };
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
    const [autoDownloadLocal, setAutoDownloadLocal] = useState(false);
    const [promptSubmitLanguage, setPromptSubmitLanguage] = useState(() => getPromptSubmitLanguagePreference());
    const [advancedTemperature, setAdvancedTemperature] = useState('0.7');
    const [advancedSeed, setAdvancedSeed] = useState('');
    const [advancedCfg, setAdvancedCfg] = useState('');
    const [advancedReasoningEffort, setAdvancedReasoningEffort] = useState('high');

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
    const [autoIntelligentApiCalling, setAutoIntelligentApiCalling] = useState(true);

    // State for tabs
    const [activeTab, setActiveTab] = useState('general');

    // Account Management
    const [profileName, setProfileName] = useState('');
    const [profileEmail, setProfileEmail] = useState('');
    const [profileAvatarUrl, setProfileAvatarUrl] = useState('');
    const [homepageShareLink, setHomepageShareLink] = useState('');
    const [isSavingProfile, setIsSavingProfile] = useState(false);
    const [isLoadingHomepageShareLink, setIsLoadingHomepageShareLink] = useState(false);
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
    const [functionApiConfigs, setFunctionApiConfigs] = useState([]);
    const [isSystemSettingsLoading, setIsSystemSettingsLoading] = useState(false);
    const [selectingSystemId, setSelectingSystemId] = useState(null);
    const [selectedSystemCategory, setSelectedSystemCategory] = useState('All');
    const [activeSettingSources, setActiveSettingSources] = useState({
        LLM: 'none',
        Image: 'none',
        Video: 'none',
        Vision: 'none',
    });
    const [apiStrategyByCategory, setApiStrategyByCategory] = useState({});
    const [activeModeByCategory, setActiveModeByCategory] = useState({});
    const [systemModeSelectionById, setSystemModeSelectionById] = useState({});

    // Unified Top Up entry: support /settings?tab=billing and cross-app 402 redirects.
    useEffect(() => {
        const params = new URLSearchParams(location.search || '');
        const tab = params.get('tab');
        if (tab === 'billing' || tab === 'usage') {
            setActiveTab('usage');
        } else if (tab === 'system-api' || tab === 'system_api' || tab === 'api' || tab === 'api-settings' || tab === 'default-api-activation') {
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

    const handleAutoDownloadLocalChange = (checked) => {
        const next = !!checked;
        setAutoDownloadLocal(next);
        setAutoDownloadLocalPreference(next);
        setGenerationConfig({
            ...(generationConfig || {}),
            autoDownloadLocal: next,
        });
        void updateUserPreferences({ auto_download_local: next });
    };

    const handlePromptSubmitLanguageChange = (value) => {
        const next = normalizePromptSubmitLanguagePreference(value);
        setPromptSubmitLanguage(next);
        setPromptSubmitLanguagePreference(next);
        void updateUserPreferences({ prompt_submit_language: next });
    };

    const buildAdvancedModelPayload = () => {
        const tempNum = Number(advancedTemperature);
        const seedNum = Number(advancedSeed);
        const cfgNum = Number(advancedCfg);
        const effort = ['low', 'medium', 'high'].includes(String(advancedReasoningEffort || '').toLowerCase())
            ? String(advancedReasoningEffort).toLowerCase()
            : 'high';

        return {
            temperature: Number.isFinite(tempNum) ? Math.max(0, Math.min(2, tempNum)) : 0.7,
            seed: Number.isFinite(seedNum) && seedNum > 0 ? Math.trunc(seedNum) : null,
            cfg: Number.isFinite(cfgNum) && cfgNum > 0 ? cfgNum : null,
            reasoning_effort: effort,
        };
    };

    const handleSaveAdvancedModelPreferences = async () => {
        const advancedModelPayload = buildAdvancedModelPayload();
        setGenerationConfig({
            ...(generationConfig || {}),
            advanced_model: advancedModelPayload,
        });

        try {
            await updateUserPreferences({
                advanced_model: advancedModelPayload,
            });
            showNotification(t('高级模型参数已保存', 'Advanced model preferences saved'), 'success');
        } catch (e) {
            console.warn('Failed to persist advanced model preferences', e);
            showNotification(t('高级模型参数保存失败', 'Failed to save advanced model preferences'), 'error');
        }
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
            const [me, shareLinkRes] = await Promise.all([
                fetchMe(),
                getHomepageShareLink().catch(() => null),
            ]);
            setProfileName(me?.full_name || '');
            setProfileEmail(me?.email || '');
            setProfileAvatarUrl(me?.avatar_url || '');
            if (shareLinkRes?.homepage_path) {
                setHomepageShareLink(`${window.location.origin}${shareLinkRes.homepage_path}`);
            }
        } catch (e) {
            console.error('Failed to load profile', e);
        }
    };

    const handleCopyHomepageShareLink = async () => {
        setIsLoadingHomepageShareLink(true);
        try {
            let nextLink = homepageShareLink;
            if (!nextLink) {
                const shareLinkRes = await getHomepageShareLink();
                nextLink = shareLinkRes?.homepage_path ? `${window.location.origin}${shareLinkRes.homepage_path}` : '';
                setHomepageShareLink(nextLink);
            }
            if (!nextLink) {
                throw new Error(t('未能生成主页链接', 'Failed to generate homepage link'));
            }

            if (navigator?.clipboard?.writeText) {
                await navigator.clipboard.writeText(nextLink);
            } else {
                const input = document.createElement('textarea');
                input.value = nextLink;
                input.setAttribute('readonly', 'readonly');
                input.style.position = 'absolute';
                input.style.left = '-9999px';
                document.body.appendChild(input);
                input.select();
                document.execCommand('copy');
                document.body.removeChild(input);
            }
            showNotification(t('主页链接已复制', 'Homepage link copied'), 'success');
        } catch (e) {
            showNotification(t(`复制主页链接失败：${e.message}`, `Failed to copy homepage link: ${e.message}`), 'error');
        } finally {
            setIsLoadingHomepageShareLink(false);
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
            const [userRes, systemRes, funcConfigs] = await Promise.all([fetchMe(), getSystemSettings(), getFunctionApiConfigs().catch(()=>[])]);
            setFunctionApiConfigs(Array.isArray(funcConfigs) ? funcConfigs : []);
            if (import.meta.env.DEV) {
                const firstGroup = Array.isArray(systemRes) && systemRes.length > 0 ? systemRes[0] : null;
                const firstModel = firstGroup && Array.isArray(firstGroup.models) && firstGroup.models.length > 0 ? firstGroup.models[0] : null;
                // Dev-only visibility: confirm which backend is used and what pricing fields arrive.
                console.debug('[Settings][SystemPricing] API_URL=', API_URL, 'group=', firstGroup, 'firstModelPricing=', firstModel ? {
                    id: firstModel.id,
                    provider: firstModel.provider,
                    model: firstModel.model,
                    avg_price_estimate: firstModel.avg_price_estimate,
                    price_range_min: firstModel.price_range_min,
                    price_range_max: firstModel.price_range_max,
                    sample_prices: firstModel.sample_prices,
                    avg_price_source: firstModel.avg_price_source,
                } : null);
            }
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

    const normalizeApiStrategy = (value) => {
        const raw = String(value || '').trim().toLowerCase();
        if (raw === 'low_price_replace') return 'low_price_replace';
        if (raw === 'fixed') return 'fixed';
        return 'smart_default';
    };

    const normalizeModeValue = (value) => {
        const text = String(value == null ? '' : value).trim();
        return text;
    };

    const collectModeOptionsFromRow = (row) => {
        const merged = Array.isArray(row?.mode_values) ? row.mode_values : [];
        const out = [];
        const seen = new Set();
        for (const item of merged) {
            const text = normalizeModeValue(item);
            if (!text) continue;
            const key = text.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);
            out.push(text);
        }
        return out;
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
            const strategyMap = {};
            const modeMap = {};
            (all || []).forEach((item) => {
                if (!item?.is_active || !item?.category) return;
                const source = item?.config?.selection_source === 'system' || item?.config?.use_system_setting_id ? 'system' : 'user';
                if (next[item.category] !== undefined) {
                    next[item.category] = source;
                }
                strategyMap[item.category] = normalizeApiStrategy(item?.config?.api_strategy);
                const activeMode = normalizeModeValue(item?.mode);
                if (activeMode) {
                    modeMap[item.category] = activeMode;
                }
            });
            setActiveSettingSources(next);
            setApiStrategyByCategory(strategyMap);
            setActiveModeByCategory(modeMap);
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
        // User default activation page only exposes runtime generation categories.
        const categoryLabelMap = {
            LLM: 'LLM',
            Image: 'Image',
            Video: 'Video',
            Vision: 'Vision',
        };
        const preferredOrder = ['LLM', 'Image', 'Video', 'Vision'];
        const visibleCategorySet = new Set(preferredOrder);

        const grouped = (systemSettings || []).reduce((acc, item) => {
            const rawCategory = String(item?.category || '').trim();
            if (!visibleCategorySet.has(rawCategory)) {
                return acc;
            }
            if (!acc[rawCategory]) acc[rawCategory] = [];
            acc[rawCategory].push({ ...item, category: rawCategory });
            return acc;
        }, {});

        const orderedKeys = [
            ...preferredOrder.filter((cat) => grouped[cat]),
            ...Object.keys(grouped)
                .filter((cat) => !preferredOrder.includes(cat))
                .sort((a, b) => a.localeCompare(b)),
        ];

        return orderedKeys.map((category) => {
            const sourceGroups = grouped[category] || [];
            const mergedByProvider = sourceGroups.reduce((bucket, item) => {
                const providerKey = `${String(item?.provider || '').trim().toLowerCase()}::${String(item?.provider_alias || '').trim().toLowerCase()}`;
                const currentModels = Array.isArray(item?.models) ? item.models : [];

                if (!bucket[providerKey]) {
                    bucket[providerKey] = {
                        ...item,
                        category,
                        models: [...currentModels],
                        shared_key_configured: !!item?.shared_key_configured,
                    };
                    return bucket;
                }

                const existing = bucket[providerKey];
                existing.shared_key_configured = !!existing.shared_key_configured || !!item?.shared_key_configured;
                if (!existing.provider_alias && item?.provider_alias) {
                    existing.provider_alias = item.provider_alias;
                }

                const mergedModels = [...(Array.isArray(existing.models) ? existing.models : []), ...currentModels];
                const dedupedModels = [];
                const seenModelKeys = new Set();
                for (const row of mergedModels) {
                    const modelKey = `${String(row?.id ?? '')}::${String(row?.model ?? '').trim().toLowerCase()}`;
                    if (seenModelKeys.has(modelKey)) continue;
                    seenModelKeys.add(modelKey);
                    dedupedModels.push(row);
                }
                existing.models = dedupedModels;
                return bucket;
            }, {});

            const mergedGroups = Object.values(mergedByProvider)
                .sort((a, b) => String(a.provider || '').localeCompare(String(b.provider || '')));

            return {
                category,
                label: categoryLabelMap[category] || category,
                groups: mergedGroups,
            };
        }).filter((block) => (block.groups || []).length > 0);
    }, [systemSettings]);


    const visibleSystemSettings = useMemo(() => {
        if (selectedSystemCategory === 'All') return categorizedSystemSettings;
        return categorizedSystemSettings.filter((block) => block.category === selectedSystemCategory);
    }, [categorizedSystemSettings, selectedSystemCategory]);

    useEffect(() => {
        setSystemModeSelectionById((prev) => {
            const next = { ...(prev || {}) };
            const validIds = new Set();

            for (const categoryBlock of categorizedSystemSettings || []) {
                const category = String(categoryBlock?.category || '').trim();
                const activeMode = normalizeModeValue(activeModeByCategory?.[category]);

                for (const group of categoryBlock?.groups || []) {
                    for (const row of group?.models || []) {
                        const rowId = Number(row?.id || 0);
                        if (!rowId) continue;
                        validIds.add(rowId);

                        const modeOptions = collectModeOptionsFromRow(row);
                        if (modeOptions.length === 0) {
                            delete next[rowId];
                            continue;
                        }

                        const current = normalizeModeValue(next[rowId]);
                        const hasCurrent = current && modeOptions.some((opt) => opt.toLowerCase() === current.toLowerCase());
                        if (hasCurrent) continue;

                        const preferredActive =
                            row?.is_active && activeMode
                                ? modeOptions.find((opt) => opt.toLowerCase() === activeMode.toLowerCase())
                                : '';

                        next[rowId] = preferredActive || modeOptions[0];
                    }
                }
            }

            Object.keys(next).forEach((key) => {
                if (!validIds.has(Number(key))) {
                    delete next[key];
                }
            });

            return next;
        });
    }, [categorizedSystemSettings, activeModeByCategory]);

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
                const [data, userPreferences] = await Promise.all([
                    getSettings(),
                    getUserPreferences().catch(() => null),
                ]);
                if (data) {
                    // Find existing Baidu Translation setting
                    const baiduSetting = data.find(s => s.provider === 'baidu_translate' || s.provider === 'baidu');
                    if (baiduSetting) {
                        setBaiduToken(baiduSetting.api_key || "");
                    }

                    const smartRouterSetting = data.find((s) => String(s.provider || '').toLowerCase() === 'smart_router' && s.category === 'Tools');
                    if (smartRouterSetting?.config && Object.prototype.hasOwnProperty.call(smartRouterSetting.config, 'auto_intelligent_api_calling')) {
                        setAutoIntelligentApiCalling(!!smartRouterSetting.config.auto_intelligent_api_calling);
                    } else {
                        setAutoIntelligentApiCalling(true);
                    }
                }

                if (userPreferences && typeof userPreferences === 'object') {
                    const generation = userPreferences.generation && typeof userPreferences.generation === 'object'
                        ? userPreferences.generation
                        : {};
                    const advanced = userPreferences.advanced_model && typeof userPreferences.advanced_model === 'object'
                        ? userPreferences.advanced_model
                        : {};
                    const withFallback = (value, fallbackValue) => {
                        if (typeof value === 'string' && value.trim()) return value;
                        return fallbackValue;
                    };
                    const tempNum = Number(advanced.temperature);
                    const seedNum = Number(advanced.seed);
                    const cfgNum = Number(advanced.cfg);

                    setPromptSubmitLanguage(normalizePromptSubmitLanguagePreference(userPreferences.prompt_submit_language));
                    setAutoDownloadLocal(!!userPreferences.auto_download_local);
                    setCharSupplements(withFallback(generation.characterSupplements, DEFAULT_CHARACTER_SUPPLEMENTS));
                    setSceneSupplements(withFallback(generation.sceneSupplements, DEFAULT_SCENE_SUPPLEMENTS));
                    setPromptLanguage(generation.prompt_language || 'mixed');
                    setAdvancedTemperature(
                        Number.isFinite(tempNum) ? String(Math.max(0, Math.min(2, tempNum))) : '0.7'
                    );
                    setAdvancedSeed(Number.isFinite(seedNum) && seedNum > 0 ? String(Math.trunc(seedNum)) : '');
                    setAdvancedCfg(Number.isFinite(cfgNum) && cfgNum > 0 ? String(cfgNum) : '');
                    setAdvancedReasoningEffort(
                        ['low', 'medium', 'high'].includes(String(advanced.reasoning_effort || '').toLowerCase())
                            ? String(advanced.reasoning_effort).toLowerCase()
                            : 'high'
                    );
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
            const advanced = (generationConfig.advanced_model && typeof generationConfig.advanced_model === 'object')
                ? generationConfig.advanced_model
                : {};
            const tempNum = Number(advanced.temperature);
            const seedNum = Number(advanced.seed);
            const cfgNum = Number(advanced.cfg);
            setAdvancedTemperature(
                Number.isFinite(tempNum) ? String(Math.max(0, Math.min(2, tempNum))) : '0.7'
            );
            setAdvancedSeed(Number.isFinite(seedNum) && seedNum > 0 ? String(Math.trunc(seedNum)) : '');
            setAdvancedCfg(Number.isFinite(cfgNum) && cfgNum > 0 ? String(cfgNum) : '');
            setAdvancedReasoningEffort(
                ['low', 'medium', 'high'].includes(String(advanced.reasoning_effort || '').toLowerCase())
                    ? String(advanced.reasoning_effort).toLowerCase()
                    : 'high'
            );
            const userPref = getAutoDownloadLocalPreference();
            setAutoDownloadLocal(
                userPref !== null
                    ? userPref
                    : (
                        Object.prototype.hasOwnProperty.call(generationConfig, 'autoDownloadLocal')
                            ? !!generationConfig.autoDownloadLocal
                            : false
                    )
            );
            
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
                         setAdvancedTemperature('0.7');
                         setAdvancedSeed('');
                         setAdvancedCfg('');
                         setAdvancedReasoningEffort('high');
             setAutoDownloadLocal(getAutoDownloadLocalPreference() ?? false);
             // Even if no generationConfig, we might have defaults set in state (e.g. Midjourney/Runway)
             // and we should load their configs if savedToolConfigs updates
             loadToolConfig(imageModel, 'image');
             loadToolConfig(videoModel, 'video');
             loadToolConfig(visionModel || "Grsai-Vision", 'vision');
        }
    }, [generationConfig, savedToolConfigs]);

    const loadToolConfig = (toolName, type) => {
        const legacyToolName = toolName === "Zlhub Video" ? "Lzhbu Video" : toolName;
        const saved = savedToolConfigs[toolName] || savedToolConfigs[legacyToolName];
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
                setImgToolWebHook((toolName === "Grsai-Image" || toolName === "Kie-Image") && saved.webHook === "-1" ? "" : (saved.webHook || ""));
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
                     setImgToolWebHook("");
                 } else if (toolName === "Kie-Image") {
                     setImgToolKey("");
                     setImgToolEndpoint("https://api.kie.ai/api/v1/jobs/createTask");
                     setImgToolModel("flux-kontext-pro");
                     setImgToolWidth("1024");
                     setImgToolHeight("1024");
                     setImgToolWebHook("");
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
                setVidToolWebHook((toolName === "Grsai-Video" || toolName === "Kie-Video") && saved.webHook === "-1" ? "" : (saved.webHook || ""));
                setVidToolDraft(saved.draft || false);
             } else {
                 setVidEndpointMap({});
                 if (toolName === "Doubao Video") {
                    setVidToolKey("");
                    setVidToolEndpoint("https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks");
                    setVidToolModel("doubao-seedance-1-5-pro-251215");
                    setVidToolWebHook("");
                    setVidToolDraft(false);
                                            } else if (toolName === "Zlhub Video" || toolName === "Lzhbu Video") {
                          setVidToolKey("");
                          setVidToolEndpoint("https://zlhub.xiaowaiyou.cn/zhonglian/api/v1/proxy/chat/completions");
                          setVidToolModel("doubao-seedance-2-0");
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
                          setVidToolWebHook("");
                      } else if (toolName === "Kie-Video") {
                          setVidToolKey("");
                                  setVidToolEndpoint("https://api.kie.ai/api/v1/jobs/createTask");
                              setVidToolModel("veo3_fast");
                          setVidToolWebHook("");
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
            else if (frontendProviderName === "Zlhub Video" || frontendProviderName === "Lzhbu Video") backendProvider = "zlhub";
            else if (frontendProviderName === "Wanxiang") backendProvider = "wanxiang";
            else if (frontendProviderName === "Vidu (Video)") backendProvider = "vidu";
            else if (frontendProviderName === "Tencent Hunyuan") backendProvider = "tencent";
            else if (frontendProviderName === "Kie-Image" || frontendProviderName === "Kie-Video") backendProvider = "kie";
            else if (frontendProviderName === "Midjourney") backendProvider = "midjourney";
            else if (frontendProviderName === "DALL-E 3") backendProvider = "openai";

            // Get existing to find ID
            const allSettings = await getSettings();
            const existing = allSettings.find(s => 
                ((backendProvider === "zlhub" && ["zlhub", "lzhbu"].includes((s.provider || "").toLowerCase())) ||
                 (backendProvider !== "zlhub" && (s.provider || "").toLowerCase() === backendProvider)) && 
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

        let providerAlias = '';
        try {
            const latestSettings = await getSettings();
            const targetProvider = String(provider || '').trim().toLowerCase();
            const targetModel = String(configToSave.model || '').trim();
            const exact = (latestSettings || []).find((row) => (
                String(row?.provider || '').trim().toLowerCase() === targetProvider
                && String(row?.category || '').trim() === 'LLM'
                && String(row?.model || '').trim() === targetModel
            ));
            const fallback = exact || (latestSettings || []).find((row) => (
                String(row?.provider || '').trim().toLowerCase() === targetProvider
                && String(row?.category || '').trim() === 'LLM'
            ));
            providerAlias = String(fallback?.provider_alias || '').trim();
        } catch {
            providerAlias = '';
        }

        const providerLabel = formatProviderLabel(provider, providerAlias);
        showNotification(`Settings for ${providerLabel} saved and activated`, "success");
        addLog(`Settings for ${providerLabel} saved and activated`, "success");
    };

    const handleSaveGeneration = async () => {
        const advancedModelPayload = buildAdvancedModelPayload();
        const generationPayload = {
            characterSupplements: charSupplements,
            sceneSupplements: sceneSupplements,
            prompt_language: promptLanguage,
            imageModel,
            videoModel,
            visionModel,
            autoDownloadLocal,
        };
        setGenerationConfig({
            ...generationPayload,
            advanced_model: advancedModelPayload,
        });

        try {
            await updateUserPreferences({
                prompt_submit_language: promptSubmitLanguage,
                auto_download_local: !!autoDownloadLocal,
                generation: generationPayload,
                advanced_model: advancedModelPayload,
            });
        } catch (e) {
            console.warn('Failed to persist user preferences to backend', e);
        }

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

        try {
            const allSettings = await getSettings();
            const existingSmartRouter = allSettings.find((s) => String(s.provider || '').toLowerCase() === 'smart_router' && s.category === 'Tools');
            await updateSetting({
                id: existingSmartRouter?.id,
                name: existingSmartRouter?.name || 'Smart API Router',
                provider: 'smart_router',
                category: 'Tools',
                is_active: false,
                config: {
                    auto_intelligent_api_calling: !!autoIntelligentApiCalling,
                },
            });
        } catch (e) {
            console.error('Failed to save smart router setting', e);
            showNotification(t('智能 API 调用开关保存失败', 'Failed to save intelligent API toggle'), 'error');
        }

        await refreshActiveSettingSources();

        showNotification("Generation settings & credentials saved", "success");
        addLog("Generation settings & credentials saved", "success");
    };

    const handleSelectSystemSetting = async (setting, category, providerAlias = '', selectedMode = '') => {
        if (!setting?.id) return;
        setSelectingSystemId(setting.id);
        try {
            const chosenStrategy = normalizeApiStrategy(apiStrategyByCategory?.[category]);
            const normalizedSelectedMode = normalizeModeValue(selectedMode);
            const selected = await selectSystemSetting(
                setting.id,
                chosenStrategy,
                normalizedSelectedMode || null,
            );
            if (selected?.category === 'LLM') {
                const resolvedEndpoint = selected.base_url || setting.base_url || '';
                setProvider(selected.provider || 'openai');
                setEndpoint(resolvedEndpoint);
                setModel(selected.model || '');
                setApiKey('');
                setLLMConfig({
                    provider: selected.provider || 'openai',
                    apiKey: '',
                    endpoint: resolvedEndpoint,
                    model: selected.model || ''
                });
            }
            const providerLabel = formatProviderLabel(
                selected?.provider || setting.provider,
                providerAlias || selected?.provider_alias || setting.provider_alias,
            );
            const activeModeText = normalizeModeValue(selected?.mode) || normalizedSelectedMode;
            const modeSuffix = activeModeText ? ` / mode=${activeModeText}` : '';
            showNotification(`System setting activated: ${providerLabel} / ${selected?.model || setting.model || ''}${modeSuffix}`, 'success');
            addLog(`Activated system API setting: ${providerLabel} (${selected?.category || setting.category}), strategy=${chosenStrategy}`, 'success');
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
                                autoComplete="off"
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
                                autoComplete="off"
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
                                autoComplete="off"
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
        <div className="w-full max-w-7xl mx-auto space-y-6 h-full overflow-y-auto p-3 sm:p-4 flex flex-col text-white relative">
            {/* Notification Toast */}
            {notification && (
                <div className={`fixed top-10 left-1/2 transform -translate-x-1/2 z-[200] px-6 py-3 rounded-lg shadow-2xl border font-bold flex items-center gap-2 animate-in slide-in-from-top-4 fade-in duration-300 ${
                    notification.type === 'success' ? 'bg-green-500/90 text-white border-green-400' : 'bg-red-500/90 text-white border-red-400'
                }`}>
                    {notification.type === 'success' ? <Save size={18} /> : <Info size={18} />}
                    {notification.message}
                </div>
            )}
            <header className="flex flex-col md:flex-row justify-between items-stretch md:items-center gap-3 sm:gap-4 bg-card p-3 sm:p-4 rounded-xl border border-white/10 shadow-sm bg-black/20">
                <div className="flex items-center gap-6 overflow-x-auto w-full md:w-auto no-scrollbar">
                    <div className="flex bg-white/5 p-1 rounded-lg shrink-0">
                            <button 
                                onClick={() => trackMenuAction('settings.tab.general', t('常规', 'General'), () => setActiveTab('general'))}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'general' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                                         {t('常规', 'General')}
                            </button>
                            <button 
                                onClick={() => trackMenuAction('settings.tab.api_settings', t('默认 API 激活', 'Default API Activation'), () => setActiveTab('api_settings'))}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'api_settings' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                                         {t('默认 API 激活', 'Default API Activation')}
                            </button>
                            <button
                                onClick={() => trackMenuAction('settings.tab.account', t('用户管理', 'Account'), () => setActiveTab('account'))}
                                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'account' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                            >
                                {t('用户管理', 'Account')}
                            </button>
                        <button 
                             onClick={() => trackMenuAction('settings.tab.usage', t('用量', 'Usage'), () => setActiveTab('usage'))}
                             className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'usage' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}
                        >
                            <span className="flex items-center gap-2"><Coins size={14}/> {t('用量', 'Usage')}</span>
                        </button>
                    </div>
                </div>

                <div className="flex flex-wrap gap-2 w-full md:w-auto shrink-0 items-center justify-start md:justify-end">
                    <div className="w-full sm:w-auto flex items-center gap-2 bg-white/5 border border-white/10 px-2 py-1.5 rounded-lg">
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
                        className="flex-1 sm:flex-none flex items-center justify-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors whitespace-nowrap"
                        title={t('导入设置 JSON', 'Import Settings JSON')}
                    >
                        <Upload size={14} />
                        <span>{t('导入', 'Import')}</span>
                    </button>
                    <button 
                        onClick={() => trackMenuAction('settings.action.export', t('导出', 'Export'), handleExportSettings)}
                        className="flex-1 sm:flex-none flex items-center justify-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors whitespace-nowrap"
                        title={t('导出设置 JSON', 'Export Settings JSON')}
                    >
                        <Download size={14} />
                        <span>{t('导出', 'Export')}</span>
                    </button>
                    <button
                        onClick={() => trackMenuAction('settings.action.exit', t('退出', 'Exit'), handleExitSettings)}
                        className="flex-1 sm:flex-none flex items-center justify-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/10 text-xs transition-colors whitespace-nowrap"
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
            <section className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
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

                <div className="pt-4 border-t border-white/10 space-y-2">
                    <h3 className="text-sm font-semibold text-white/90">{t('生成偏好', 'Generation Preference')}</h3>
                    <label className="flex items-center gap-3 text-sm text-white bg-white/5 p-3 rounded-lg border border-white/10">
                        <input
                            type="checkbox"
                            checked={!!autoDownloadLocal}
                            onChange={(e) => handleAutoDownloadLocalChange(e.target.checked)}
                        />
                        <span>
                            {t('生成成功后自动下载到本地（按当前用户设置）', 'Auto-download generated media to local device (per-user setting)')}
                        </span>
                    </label>
                    <p className="text-[11px] text-muted-foreground">
                        {t('该开关会立即保存到当前用户本地设置。', 'This toggle is saved immediately to current user local settings.')}
                    </p>
                    <div className="space-y-2 bg-white/5 p-3 rounded-lg border border-white/10">
                        <div className="flex flex-wrap items-center gap-2 md:gap-3">
                            <label className="text-sm leading-6 text-white/90">{t('提示词提交语种', 'Prompt Submit Language')}</label>
                            <select
                                value={promptSubmitLanguage}
                                onChange={(e) => handlePromptSubmitLanguageChange(e.target.value)}
                                className="w-full sm:w-56 p-2 rounded-md bg-white/10 border border-white/10 text-sm"
                            >
                                <option value="en">{t('英文', 'English')}</option>
                                <option value="cn">{t('中文', 'Chinese')}</option>
                                <option value="auto">{t('按界面语言', 'Follow UI Language')}</option>
                            </select>
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                            {t('该选项会立即保存到当前用户本地设置，并用于 Subject 与 Shot 的生成提交。', 'This option is saved immediately to current user local settings and applies to Subject and Shot generation submissions.')}
                        </p>
                    </div>
                    <div className="space-y-3 bg-white/5 p-3 rounded-lg border border-white/10">
                        <div className="flex items-center justify-between gap-3">
                            <label className="text-sm leading-6 text-white/90">{t('高级模型参数', 'Advanced Model Parameters')}</label>
                            <button
                                type="button"
                                onClick={handleSaveAdvancedModelPreferences}
                                className="px-3 py-1.5 rounded-md text-xs bg-primary text-black hover:opacity-90"
                            >
                                {t('保存参数', 'Save Parameters')}
                            </button>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <label className="text-xs text-muted-foreground space-y-1">
                                <span>{t('Temperature (0-2)', 'Temperature (0-2)')}</span>
                                <input
                                    type="number"
                                    min="0"
                                    max="2"
                                    step="0.1"
                                    value={advancedTemperature}
                                    onChange={(e) => setAdvancedTemperature(e.target.value)}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-sm text-white"
                                />
                            </label>
                            <label className="text-xs text-muted-foreground space-y-1">
                                <span>{t('Seed (可选)', 'Seed (Optional)')}</span>
                                <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={advancedSeed}
                                    onChange={(e) => setAdvancedSeed(e.target.value)}
                                    placeholder={t('留空则随机', 'Leave blank for random')}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-sm text-white"
                                />
                            </label>
                            <label className="text-xs text-muted-foreground space-y-1">
                                <span>{t('CFG (可选)', 'CFG (Optional)')}</span>
                                <input
                                    type="number"
                                    min="0.1"
                                    step="0.1"
                                    value={advancedCfg}
                                    onChange={(e) => setAdvancedCfg(e.target.value)}
                                    placeholder={t('留空则使用模型默认', 'Leave blank for provider default')}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-sm text-white"
                                />
                            </label>
                            <label className="text-xs text-muted-foreground space-y-1">
                                <span>{t('Reasoning Effort', 'Reasoning Effort')}</span>
                                <select
                                    value={advancedReasoningEffort}
                                    onChange={(e) => setAdvancedReasoningEffort(e.target.value)}
                                    className="w-full p-2 rounded-md bg-white/10 border border-white/10 text-sm text-white"
                                >
                                    <option value="low">low</option>
                                    <option value="medium">medium</option>
                                    <option value="high">high</option>
                                </select>
                            </label>
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                            {t('用于 LLM 分析与生图默认参数。若请求中显式传参，将优先使用请求参数。', 'Used as defaults for LLM analysis and image generation. Explicit request parameters take priority.')}
                        </p>
                    </div>
                </div>
            </section>
            )}

            {activeTab === 'account' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <section className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
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

                    <section className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <LinkIcon className="w-5 h-5 text-primary" />
                            {t('主页分享链接', 'Homepage Share Link')}
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            {t('复制一个带来源标记的主页地址。链接本身不包含明文用户信息，后续通过该链接注册的用户会把解析结果写入 preferences。', 'Copy a homepage URL with an encoded referral marker. The link does not expose plain user information, and registrations through it will store the parsed result in preferences.')}
                        </p>
                        <div className="flex flex-col gap-3 md:flex-row">
                            <input
                                type="text"
                                readOnly
                                value={homepageShareLink}
                                placeholder={t('点击右侧按钮生成主页链接', 'Generate a homepage link with the button on the right')}
                                className="w-full rounded-md border border-white/10 bg-white/5 p-2 text-sm text-muted-foreground"
                            />
                            <button
                                onClick={handleCopyHomepageShareLink}
                                disabled={isLoadingHomepageShareLink}
                                className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/10 px-4 py-2 text-sm font-bold hover:bg-white/20 disabled:opacity-50"
                            >
                                <Copy className="h-4 w-4" />
                                {isLoadingHomepageShareLink ? t('生成中...', 'Generating...') : t('复制链接', 'Copy Link')}
                            </button>
                        </div>
                    </section>

                    <section className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <KeyRound className="w-5 h-5 text-primary" />
                            {t('修改密码', 'Change Password')}
                        </h2>
                        <form
                            onSubmit={(e) => {
                                e.preventDefault();
                                handleChangePassword();
                            }}
                            className="space-y-4"
                        >
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">{t('当前密码', 'Current Password')}</label>
                                    <input
                                        type="password"
                                        autoComplete="current-password"
                                        value={currentPassword}
                                        onChange={(e) => setCurrentPassword(e.target.value)}
                                        className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">{t('新密码', 'New Password')}</label>
                                    <input
                                        type="password"
                                        autoComplete="new-password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">{t('确认新密码', 'Confirm New Password')}</label>
                                    <input
                                        type="password"
                                        autoComplete="new-password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className="w-full p-2 rounded-md bg-white/10 border border-white/10"
                                    />
                                </div>
                            </div>

                            <button
                                type="submit"
                                disabled={isUpdatingPassword}
                                className="px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-sm font-bold hover:bg-white/20 disabled:opacity-50"
                            >
                                {isUpdatingPassword ? t('更新中...', 'Updating...') : t('更新密码', 'Update Password')}
                            </button>
                        </form>
                    </section>
                </div>
            )}
            
            {activeTab === 'usage' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="grid grid-cols-1 gap-6">
                            <div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 shadow-sm flex flex-col items-center justify-center text-center relative">
                                <div className="mb-3 self-end sm:mb-0 sm:absolute sm:top-4 sm:right-4">
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
                        <div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 shadow-sm">
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
                                                <th className="p-3 text-right">{t('金额', 'Amount')}</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {transactions.length === 0 ? (
                                                <tr><td colSpan="3" className="text-center p-8 text-muted-foreground">{t('暂无交易记录', 'No transactions found')}</td></tr>
                                            ) : transactions.map(t => (
                                                <tr key={t.id} className="hover:bg-white/[0.02]">
                                                    <td className="p-3 text-muted-foreground">
                                                        {formatTransactionDateTime(t.created_at)}
                                                    </td>
                                                    <td className="p-3">
                                                        <span className="bg-white/5 px-2 py-0.5 rounded text-xs uppercase border border-white/10">{t.task_type}</span>
                                                        {renderTransactionProviderUsage(t)}
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
            ) : activeTab === 'api_settings' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="space-y-4">
                        <div className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-4">
                            <h2 className="text-2xl font-extrabold tracking-wide text-cyan-200">{t('默认 API 激活', 'Default API Activation')}</h2>
                            <p className="text-xs text-cyan-100/80 mt-1">{t('仅用于当前用户选择每个类别的默认激活 API 配置。', 'Only used for current user default active API selection by category.')}</p>
                        </div>
                        <div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-cyan-400/20 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-medium">{t('选择默认激活的 API 配置', 'Select Default Activated API Config')}</h3>
                                <span className={`text-xs px-2 py-0.5 rounded border ${userCredits > 0 ? 'text-green-300 border-green-500/40 bg-green-500/10' : 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10'}`}>
                                    {t('积分', 'Credits')}: {userCredits}
                                </span>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {t('在每个类别中选择一个默认激活配置。调用时将按你当前激活项生效。', 'Pick one default active config per category. Calls will use your currently active selection.')}
                            </p>
                            {!isSystemSettingsLoading && systemSettings.length > 0 && categorizedSystemSettings.length === 0 ? (
                                <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-xs text-yellow-200">
                                    {t('已读取到系统 API 数据，但当前提供方尚未配置可用共享密钥，所以默认激活列表为空。请到管理面板检查 provider key pool 或 system_api_settings.api_key。', 'System API data was loaded, but no provider currently has a usable shared key configured, so the activation list is empty. Check provider key pools or system_api_settings.api_key in the admin panel.')}
                                </div>
                            ) : null}

                            <div className="grid grid-cols-1 gap-3 rounded-lg border border-white/10 bg-white/5 p-3">
                                <div className="text-xs text-muted-foreground">
                                    {t('用户 API 激活策略：智能选择（默认）先对默认激活 API 重试 3 次，再按同类候选依次尝试 3 个；固定 API 在失败重试 3 次后结束；低价替换在失败重试 3 次后按同类同 mode 的平均价格从低到高尝试前 3 个。', 'User API activation policy: Smart default (default) retries the selected API 3 times, then tries 3 same-category fallback APIs in order; Fixed retries selected API 3 times then exits; Low-price replace retries selected API 3 times then tries top 3 lowest average-price APIs in same category and mode.')}
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                    {['Image', 'Video'].map((policyCategory) => (
                                        <div key={`policy-${policyCategory}`} className="flex items-center gap-2">
                                            <span className="text-xs min-w-[64px] text-muted-foreground">{policyCategory}</span>
                                            <select
                                                value={apiStrategyByCategory?.[policyCategory] || 'smart_default'}
                                                onChange={(e) => setApiStrategyByCategory((prev) => ({ ...prev, [policyCategory]: normalizeApiStrategy(e.target.value) }))}
                                                className="w-full px-2 py-1.5 rounded border border-white/15 bg-black/30 text-xs"
                                            >
                                                <option value="smart_default">{t('智能选择', 'Smart default')}</option>
                                                <option value="fixed">{t('固定 API', 'Fixed API')}</option>
                                                <option value="low_price_replace">{t('低价替换', 'Low-price replace')}</option>
                                            </select>
                                        </div>
                                    ))}
                                </div>
                            </div>

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
                                                {categoryBlock.groups.map((group, groupIndex) => {
                                                    const providerPricing = buildPriceDisplay(group);
                                                    return (
                                                    <div key={`${group.category}-${group.provider}-${group.provider_alias || ''}-${groupIndex}`} className="border border-white/10 rounded-lg p-4 bg-white/5 space-y-3">
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <span className="text-sm font-semibold">{group.provider_alias || group.provider}</span>
                                                            {group.provider_alias && (
                                                                <span className="text-[10px] px-1.5 py-0.5 rounded border border-white/20 text-muted-foreground font-mono">
                                                                    {group.provider}
                                                                </span>
                                                            )}
                                                            {group.shared_key_configured ? (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-green-500/30 text-green-300 bg-green-500/10">{t('共享密钥已就绪', 'Shared Key Ready')}</span>
                                                            ) : (
                                                                <span className="text-[10px] px-2 py-0.5 rounded border border-yellow-500/30 text-yellow-300 bg-yellow-500/10">{t('无共享密钥', 'No Shared Key')}</span>
                                                            )}
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded border border-emerald-400/30 bg-emerald-500/10 text-emerald-200">
                                                                {t('提供方均价', 'Provider Avg')}: {providerPricing.avgLabel}
                                                            </span>
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded border border-sky-400/30 bg-sky-500/10 text-sky-200">
                                                                {t('提供方区间', 'Provider Range')}: {providerPricing.rangeLabelMin} ~ {providerPricing.rangeLabelMax}
                                                            </span>
                                                        </div>

                                                        <div className="space-y-2">
                                                            {(group.models || []).map((row, rowIndex) => (
                                                                (() => {
                                                                    const pricing = buildPriceDisplay(row);
                                                                    const modeOptions = collectModeOptionsFromRow(row);
                                                                    const selectedMode = normalizeModeValue(systemModeSelectionById?.[row?.id]);
                                                                    const activeMode = normalizeModeValue(activeModeByCategory?.[categoryBlock.category]);
                                                                    return (
                                                                <div
                                                                    key={`system-row-${group.category}-${group.provider}-${String(row?.id ?? '')}-${String(row?.model || '')}-${rowIndex}`}
                                                                    className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center p-2 rounded border border-white/10 bg-black/20"
                                                                >
                                                                    <div className="md:col-span-8 text-xs">
                                                                        <div className="text-muted-foreground">{t('名称', 'Name')}</div>
                                                                        <div className="font-mono break-all flex flex-wrap items-center gap-2">
                                                                            <span>{row.name || '-'}</span>
                                                                            {row.is_active && activeMode && (
                                                                                <span className="text-[10px] px-1.5 py-0.5 rounded border border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-200">
                                                                                    {t('当前 mode', 'Current mode')}: {activeMode}
                                                                                </span>
                                                                            )}
                                                                            <span className="text-[10px] px-1.5 py-0.5 rounded border border-emerald-400/30 bg-emerald-500/10 text-emerald-200">
                                                                                {t('平均价格', 'Avg Price')}: {pricing.avgLabel}
                                                                            </span>
                                                                            <span className="text-[10px] px-1.5 py-0.5 rounded border border-amber-400/30 bg-amber-500/10 text-amber-200">
                                                                                {t('计费类型', 'Billing Type')}: {formatBillingUnitType(row.billing_unit_type)}
                                                                            </span>
                                                                            <span className="text-[10px] px-1.5 py-0.5 rounded border border-sky-400/30 bg-sky-500/10 text-sky-200">
                                                                                {t('价格区间', 'Price Range')}: {pricing.rangeLabelMin} ~ {pricing.rangeLabelMax}
                                                                            </span>
                                                                        </div>
                                                                    </div>
                                                                    <div className="md:col-span-2 text-xs">
                                                                        <div className="text-muted-foreground mb-1">{t('Mode', 'Mode')}</div>
                                                                        {modeOptions.length > 0 ? (
                                                                            <select
                                                                                value={selectedMode || modeOptions[0]}
                                                                                onChange={(e) => {
                                                                                    const nextMode = normalizeModeValue(e.target.value);
                                                                                    setSystemModeSelectionById((prev) => ({
                                                                                        ...(prev || {}),
                                                                                        [row.id]: nextMode,
                                                                                    }));
                                                                                }}
                                                                                className="w-full px-2 py-1.5 rounded border border-white/15 bg-black/30 text-xs"
                                                                            >
                                                                                {modeOptions.map((opt) => (
                                                                                    <option key={`${row.id}-mode-${opt}`} value={opt}>{opt}</option>
                                                                                ))}
                                                                            </select>
                                                                        ) : (
                                                                            <div className="text-muted-foreground">-</div>
                                                                        )}
                                                                    </div>
                                                                    <div className="md:col-span-2 flex md:justify-end">
                                                                        <div className="w-full md:w-auto flex gap-2 justify-end">
                                                                            <button
                                                                                onClick={(e) => {
                                                                                    e.stopPropagation();
                                                                                    handleSelectSystemSetting(
                                                                                        row,
                                                                                        categoryBlock.category,
                                                                                        group.provider_alias || '',
                                                                                        modeOptions.length > 0 ? (selectedMode || modeOptions[0]) : '',
                                                                                    );
                                                                                }}
                                                                                disabled={!group.shared_key_configured || selectingSystemId === row.id || !!row.deprecated}
                                                                                className="text-xs px-3 py-1.5 rounded border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                                                            >
                                                                                {selectingSystemId === row.id ? t('激活中...', 'Activating...') : (row.is_active ? t('已激活', 'Active') : t('使用此配置', 'Use This'))}
                                                                            </button>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                                    );
                                                                })()
                                                            ))}
                                                        </div>
                                                    </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="mt-8 rounded-xl border border-blue-400/30 bg-blue-500/10 p-4">
                            <h2 className="text-2xl font-extrabold tracking-wide text-blue-200">{t('功能专属 API 默认激活', 'Function-specific API Default Activation')}</h2>
                            <p className="text-xs text-blue-100/80 mt-1">{t('选择各功能的默认 API，将保存到你的本地用户设置中。', 'Select default API for each function to save to your local preferences.')}</p>
                        </div>
                        <div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-blue-400/20 space-y-4 shadow-sm">
                            {functionApiConfigs.map(funcConfig => {
                                const funcName = funcConfig.function_name;
                                const apiList = funcConfig.api_settings || [];
                                const storageKey = 'func_api_' + funcName;
                                const currentVal = Number(localStorage.getItem(storageKey)) || '';
                                
                                return (
                                    <div key={funcName} className="flex flex-col md:flex-row md:items-center justify-between p-3 bg-white/5 border border-white/10 rounded-lg gap-2">
                                        <div className="text-sm font-medium text-white/90">{funcName}</div>
                                        <select
                                            value={currentVal || ''}
                                            onChange={(e) => {
                                                const val = e.target.value;
                                                localStorage.setItem(storageKey, val);
                                                setFunctionApiConfigs([...functionApiConfigs]); // trigger re-render
                                            }}
                                            className="bg-[#111114] border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50 min-w-[200px]"
                                        >
                                            <option value="">-- {t('系统默认', 'System Default')} --</option>
                                            {apiList.map((api, idx) => {
                                                let label = api.alias || (api.system_api_model || api.system_api_name || ('API ID: ' + api.system_api_id));
                                                if (api.provider_alias) {
                                                    label = `[${api.provider_alias}] ` + label;
                                                }
                                                if (api.applicable_languages && api.applicable_languages.length > 0) {
                                                    label += ' (' + api.applicable_languages.join(', ') + ')';
                                                }
                                                if (api.is_fallback) {
                                                    label += ' (备用)';
                                                }
                                                return (
                                                    <option key={idx} value={api.system_api_id}>
                                                        {label}
                                                    </option>
                                                );
                                            })}
                                        </select>
                                    </div>
                                );
                            })}
                            {functionApiConfigs.length === 0 && <div className="text-sm text-gray-500">{t('暂无功能 API 配置', 'No function API configs available')}</div>}
                        </div>
                    </div>
            ) : null}
        </div>
    )
}

export default Settings;
