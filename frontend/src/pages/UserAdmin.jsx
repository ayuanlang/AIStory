import React, { useState, useEffect } from 'react';
import { api, getTransactions, updateUserCredits, getBillingOptions, getBillingFeaturePricing, updateBillingFeaturePricing, getBillingDefaultApiPricing, updateBillingDefaultApiPricing, getAgentToolPolicy, updateAgentToolPolicy, getSystemSettingsManage, createSystemSettingManage, updateSystemSettingManage, deleteSystemSettingManage, exportSystemSettingsManage, exportSystemSettingsToSeed, importSystemSettingsManage, exportSystemProviderBundleManage, importSystemProviderBundleManage, validateSystemProviderBundleManage, batchToggleSystemProviderDeprecatedManage, toggleSystemSettingDeprecatedManage, toggleSystemSettingDeprecatedByKeyManage, getSystemProviderKeysManage, setSystemProviderKeysManage, getAdminLlmLogFiles, getAdminLlmLogView, getAdminStorageUsage, getAdminMaintenanceConfig, updateAdminMaintenanceConfig, fetchPromptSkills, fetchPrompt } from '../services/api';
import Footer from '../components/Footer';
import { Shield, User, Key, Check, X, Crown, Settings, DollarSign, Activity, List, Plus, Trash2, Edit2, RefreshCw, CreditCard, Upload, Download, Mail, ArrowLeft, HardDrive } from 'lucide-react';
import { confirmUiMessage, promptUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI } from '../lib/uiLang';

const UserAdmin = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [billingOptions, setBillingOptions] = useState(null);
    const [featurePricingMap, setFeaturePricingMap] = useState({});
    const [featurePricingRows, setFeaturePricingRows] = useState([]);
    const [isFeaturePricingSaving, setIsFeaturePricingSaving] = useState(false);
    const [defaultApiPricingMap, setDefaultApiPricingMap] = useState({});
    const [recommendedDefaultApiPricingMap, setRecommendedDefaultApiPricingMap] = useState({});
    const [defaultApiPricingRows, setDefaultApiPricingRows] = useState([]);
    const [isDefaultApiPricingSaving, setIsDefaultApiPricingSaving] = useState(false);
    const [agentToolPolicy, setAgentToolPolicy] = useState({ default_allow: true, roles: {} });
    const [agentToolPolicyDraft, setAgentToolPolicyDraft] = useState('{\n  "default_allow": true,\n  "roles": {}\n}');
    const [isAgentToolPolicySaving, setIsAgentToolPolicySaving] = useState(false);
    const [transactions, setTransactions] = useState([]);
    const [transactionFilterUser, setTransactionFilterUser] = useState(''); // User ID filter
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Payment Config State
    const [paymentConfig, setPaymentConfig] = useState({
        mchid: '',
        appid: '',
        api_v3_key: '',
        cert_serial_no: '',
        private_key: '',
        notify_url: '',
        use_mock: true
    });
    const [isPaymentConfigLoading, setIsPaymentConfigLoading] = useState(false);
    const [smtpConfig, setSmtpConfig] = useState({
        host: '',
        port: 587,
        username: '',
        password: '',
        use_ssl: false,
        use_tls: true,
        from_email: '',
        frontend_base_url: '',
    });
    const [isSmtpConfigLoading, setIsSmtpConfigLoading] = useState(false);
    const [maintenanceConfig, setMaintenanceConfig] = useState({
        enabled: false,
        ends_at: '',
        message: '系统正在维护',
    });
    const [isMaintenanceLoading, setIsMaintenanceLoading] = useState(false);
    const [smtpTestEmail, setSmtpTestEmail] = useState('');
    const [isSmtpTestLoading, setIsSmtpTestLoading] = useState(false);
    const [smtpBroadcast, setSmtpBroadcast] = useState({
        subject: '',
        content_html: '',
        content_text: '',
    });
    const [isSmtpBroadcastLoading, setIsSmtpBroadcastLoading] = useState(false);
    const [isGrsaiDiagLoading, setIsGrsaiDiagLoading] = useState(false);
    const [grsaiDiagResult, setGrsaiDiagResult] = useState(null);
    const [isRuntimeStatsLoading, setIsRuntimeStatsLoading] = useState(false);
    const [runtimeStats, setRuntimeStats] = useState(null);
    const [systemApiRows, setSystemApiRows] = useState([]);
    const [isSystemApiLoading, setIsSystemApiLoading] = useState(false);
    const [isSystemApiImporting, setIsSystemApiImporting] = useState(false);
    const [isSystemApiExporting, setIsSystemApiExporting] = useState(false);
    const [isSystemProviderBundleImporting, setIsSystemProviderBundleImporting] = useState(false);
    const [isSystemProviderBundleExporting, setIsSystemProviderBundleExporting] = useState(false);
    const [selectedSystemApiId, setSelectedSystemApiId] = useState('');
    const [systemApiFilterCategory, setSystemApiFilterCategory] = useState('all');
    const [systemApiFilterProvider, setSystemApiFilterProvider] = useState('all');
    const [systemApiHideDeprecated, setSystemApiHideDeprecated] = useState(false);
    const [systemApiSortMode, setSystemApiSortMode] = useState('default');
    const [systemApiKeyProvider, setSystemApiKeyProvider] = useState('');
    const [providerKeysText, setProviderKeysText] = useState('');
    const [providerKeysMeta, setProviderKeysMeta] = useState({ key_count: 0, keys_masked: [] });
    const [providerKeyStrategy, setProviderKeyStrategy] = useState('random');
    const [providerKeyWeightsText, setProviderKeyWeightsText] = useState('');
    const [isProviderKeysSaving, setIsProviderKeysSaving] = useState(false);
    const [systemApiForm, setSystemApiForm] = useState({
        name: '',
        category: 'LLM',
        provider: '',
        base_url: '',
        model: '',
        webHook: '',
        api_unit_type: 'per_call',
        api_cost: '0',
        api_cost_input: '0',
        api_cost_output: '0',
        smart_priority: '100',
        smart_retry_limit: '1',
        smart_multi_ref_default: false,
        is_active: false,
    });
    const systemApiImportInputRef = React.useRef(null);
    const systemProviderBundleImportInputRef = React.useRef(null);
    const [llmLogFiles, setLlmLogFiles] = useState([]);
    const [selectedLlmLogFile, setSelectedLlmLogFile] = useState('llm_calls.log');
    const [llmLogTailLines, setLlmLogTailLines] = useState(300);
    const [llmLogContent, setLlmLogContent] = useState('');
    const [isLlmLogsLoading, setIsLlmLogsLoading] = useState(false);
    const [llmLogsError, setLlmLogsError] = useState('');
    const [storageUsage, setStorageUsage] = useState(null);
    const [isStorageUsageLoading, setIsStorageUsageLoading] = useState(false);
    const [storageUsageError, setStorageUsageError] = useState('');
    const [promptSkills, setPromptSkills] = useState([]);
    const [isPromptSkillsLoading, setIsPromptSkillsLoading] = useState(false);
    const [selectedPromptSkillId, setSelectedPromptSkillId] = useState('');
    const [selectedPromptSkillText, setSelectedPromptSkillText] = useState('');
    const [isPromptSkillTextLoading, setIsPromptSkillTextLoading] = useState(false);

    // ... existing code ...

    const normalizeFeaturePricing = (obj = {}) => {
        const normalized = {};
        Object.entries(obj || {}).forEach(([key, value]) => {
            const name = String(key || '').trim();
            if (!name) return;
            const parsed = Number(value);
            normalized[name] = Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0;
        });
        return normalized;
    };

    const buildFeaturePricingRows = (obj = {}) => {
        const normalized = normalizeFeaturePricing(obj);
        return Object.entries(normalized)
            .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
            .map(([feature, credits], idx) => ({
                id: `feature-pricing-${idx}-${feature}`,
                feature,
                credits: String(credits),
            }));
    };

    const buildFeaturePricingMapFromRows = (rows = []) => {
        const next = {};
        (rows || []).forEach((row) => {
            const name = String(row?.feature || '').trim();
            if (!name) return;
            const parsed = Number(row?.credits);
            next[name] = Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0;
        });
        return next;
    };

    const DEFAULT_API_PRICING_CATEGORY_ORDER = ['LLM', 'Vision', 'Image', 'Video', 'Tools'];
    const DEFAULT_API_PRICING_FALLBACK = {
        LLM: { unit_type: 'per_million_tokens', cost: 90, cost_input: 90, cost_output: 700 },
        Vision: { unit_type: 'per_million_tokens', cost: 120, cost_input: 120, cost_output: 800 },
        Image: { unit_type: 'per_call', cost: 10, cost_input: 0, cost_output: 0 },
        Video: { unit_type: 'per_second', cost: 30, cost_input: 0, cost_output: 0 },
        Tools: { unit_type: 'per_call', cost: 5, cost_input: 0, cost_output: 0 },
    };

    const normalizeDefaultApiPricingMap = (obj = {}) => {
        const source = (obj && typeof obj === 'object' && !Array.isArray(obj)) ? obj : {};
        const out = {};
        DEFAULT_API_PRICING_CATEGORY_ORDER.forEach((category) => {
            const raw = (source[category] && typeof source[category] === 'object' && !Array.isArray(source[category]))
                ? source[category]
                : {};
            out[category] = {
                unit_type: normalizeApiPricingUnitType(raw?.unit_type ?? DEFAULT_API_PRICING_FALLBACK[category].unit_type),
                cost: toNonNegativeInt(raw?.cost ?? DEFAULT_API_PRICING_FALLBACK[category].cost),
                cost_input: toNonNegativeInt(raw?.cost_input ?? DEFAULT_API_PRICING_FALLBACK[category].cost_input),
                cost_output: toNonNegativeInt(raw?.cost_output ?? DEFAULT_API_PRICING_FALLBACK[category].cost_output),
            };
        });
        return out;
    };

    const buildDefaultApiPricingRows = (obj = {}) => {
        const normalized = normalizeDefaultApiPricingMap(obj);
        return DEFAULT_API_PRICING_CATEGORY_ORDER.map((category) => ({
            id: `default-api-pricing-${category}`,
            category,
            unit_type: normalized[category].unit_type,
            cost: String(normalized[category].cost),
            cost_input: String(normalized[category].cost_input),
            cost_output: String(normalized[category].cost_output),
        }));
    };

    const buildDefaultApiPricingMapFromRows = (rows = []) => {
        const next = {};
        (rows || []).forEach((row) => {
            const category = String(row?.category || '').trim();
            if (!category || !DEFAULT_API_PRICING_CATEGORY_ORDER.includes(category)) return;
            next[category] = {
                unit_type: normalizeApiPricingUnitType(row?.unit_type),
                cost: toNonNegativeInt(row?.cost),
                cost_input: toNonNegativeInt(row?.cost_input),
                cost_output: toNonNegativeInt(row?.cost_output),
            };
        });
        return normalizeDefaultApiPricingMap(next);
    };

    const createEmptyFeaturePricingRow = () => ({
        id: `feature-pricing-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        feature: '',
        credits: '0',
    });

    const normalizeAgentToolPolicy = (obj = {}) => {
        const fallback = {
            default_allow: true,
            roles: {
                user: { allow: [], deny: ['internet_search'] },
                authorized: { allow: ['internet_search'], deny: [] },
                superuser: { allow: ['*'], deny: [] },
            },
        };

        const src = (obj && typeof obj === 'object' && !Array.isArray(obj)) ? obj : {};
        const roles = (src.roles && typeof src.roles === 'object' && !Array.isArray(src.roles)) ? src.roles : {};

        const normalizeRole = (roleName) => {
            const raw = (roles[roleName] && typeof roles[roleName] === 'object' && !Array.isArray(roles[roleName])) ? roles[roleName] : {};
            const allow = Array.isArray(raw.allow) ? raw.allow.map((x) => String(x || '').trim()).filter(Boolean) : [];
            const deny = Array.isArray(raw.deny) ? raw.deny.map((x) => String(x || '').trim()).filter(Boolean) : [];
            return {
                allow: Array.from(new Set(allow)),
                deny: Array.from(new Set(deny)),
            };
        };

        return {
            default_allow: typeof src.default_allow === 'boolean' ? src.default_allow : fallback.default_allow,
            roles: {
                user: normalizeRole('user') || fallback.roles.user,
                authorized: normalizeRole('authorized') || fallback.roles.authorized,
                superuser: normalizeRole('superuser') || fallback.roles.superuser,
            },
        };
    };

    const buildRecommendedAgentToolPolicy = () => normalizeAgentToolPolicy({
        default_allow: true,
        roles: {
            user: { allow: [], deny: ['internet_search'] },
            authorized: { allow: ['internet_search'], deny: [] },
            superuser: { allow: ['*'], deny: [] },
        },
    });

    const AGENT_POLICY_ROLE_ORDER = ['user', 'authorized', 'superuser'];
    const AGENT_POLICY_TOOL_OPTIONS = [
        'search_project_data',
        'internet_search',
        'visualize_user_requirement',
        'update_project_metadata',
        'analyze_script',
        'generate_project_asset',
        'generate_image_text_to_image',
        'generate_image_image_to_image',
        'generate_video_text_to_video',
        'generate_video_image_to_video',
    ];

    const parsePolicyFromDraftOrState = () => {
        try {
            const parsed = JSON.parse(agentToolPolicyDraft || '{}');
            return normalizeAgentToolPolicy(parsed);
        } catch {
            return normalizeAgentToolPolicy(agentToolPolicy || {});
        }
    };

    const applyAgentPolicyToState = (nextPolicy) => {
        const normalized = normalizeAgentToolPolicy(nextPolicy || {});
        setAgentToolPolicy(normalized);
        setAgentToolPolicyDraft(JSON.stringify(normalized, null, 2));
    };

    const isAgentToolAllowedForRole = (policy, role, tool) => {
        const normalized = normalizeAgentToolPolicy(policy || {});
        const roleCfg = normalized.roles?.[role] || { allow: [], deny: [] };
        const allowSet = new Set(Array.isArray(roleCfg.allow) ? roleCfg.allow : []);
        const denySet = new Set(Array.isArray(roleCfg.deny) ? roleCfg.deny : []);

        if (denySet.has(tool)) return false;
        if (allowSet.has('*')) return true;
        if (allowSet.has(tool)) return true;
        return !!normalized.default_allow;
    };

    const handleToggleAgentPolicyTool = (role, tool, checked) => {
        const base = parsePolicyFromDraftOrState();
        const roleCfg = base.roles?.[role] || { allow: [], deny: [] };
        const allowSet = new Set(Array.isArray(roleCfg.allow) ? roleCfg.allow : []);
        const denySet = new Set(Array.isArray(roleCfg.deny) ? roleCfg.deny : []);

        if (checked) {
            denySet.delete(tool);
            allowSet.add(tool);
        } else {
            allowSet.delete(tool);
            denySet.add(tool);
        }

        base.roles[role] = {
            allow: Array.from(allowSet),
            deny: Array.from(denySet),
        };
        applyAgentPolicyToState(base);
    };

    const handleToggleAgentPolicyDefaultAllow = (checked) => {
        const base = parsePolicyFromDraftOrState();
        base.default_allow = !!checked;
        applyAgentPolicyToState(base);
    };

    const handleRestoreRecommendedAgentPolicy = () => {
        const recommended = buildRecommendedAgentToolPolicy();
        applyAgentPolicyToState(recommended);
    };

    const fetchPaymentConfig = async () => {
        setIsPaymentConfigLoading(true);
        try {
            const res = await api.get('/admin/payment-config');
            if (res.data) {
                setPaymentConfig(res.data);
            }
        } catch (e) {
            console.error("Failed to load payment config", e);
            // If 404 or empty, we use defaults
        } finally {
            setIsPaymentConfigLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'payment') {
            fetchPaymentConfig();
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'smtp') {
            fetchSmtpConfig();
            fetchMaintenanceConfig();
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'llm_logs') {
            fetchLlmLogs();
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'storage_usage') {
            fetchStorageUsage();
        }
    }, [activeTab]);

    const loadPromptSkills = async () => {
        setIsPromptSkillsLoading(true);
        try {
            const res = await fetchPromptSkills();
            const items = Array.isArray(res?.skills) ? res.skills : [];
            setPromptSkills(items);

            if (items.length > 0) {
                const firstSkillId = String(items[0]?.id || '').trim();
                setSelectedPromptSkillId(firstSkillId);
                if (firstSkillId) {
                    setIsPromptSkillTextLoading(true);
                    try {
                        const promptRes = await fetchPrompt(`skill:${firstSkillId}/system_prompt.txt`);
                        setSelectedPromptSkillText(String(promptRes?.content || ''));
                    } catch {
                        setSelectedPromptSkillText('');
                    } finally {
                        setIsPromptSkillTextLoading(false);
                    }
                } else {
                    setSelectedPromptSkillText('');
                }
            } else {
                setSelectedPromptSkillId('');
                setSelectedPromptSkillText('');
            }
        } catch (err) {
            console.error('Failed to load prompt skills', err);
            setPromptSkills([]);
            setSelectedPromptSkillId('');
            setSelectedPromptSkillText('');
        } finally {
            setIsPromptSkillsLoading(false);
        }
    };

    const handleSelectPromptSkill = async (skillId) => {
        const id = String(skillId || '').trim();
        if (!id) return;
        setSelectedPromptSkillId(id);
        setIsPromptSkillTextLoading(true);
        try {
            const promptRes = await fetchPrompt(`skill:${id}/system_prompt.txt`);
            setSelectedPromptSkillText(String(promptRes?.content || ''));
        } catch (err) {
            console.error('Failed to load skill prompt text', err);
            setSelectedPromptSkillText('');
        } finally {
            setIsPromptSkillTextLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'prompt_skills') {
            loadPromptSkills();
        }
    }, [activeTab]);

    const fetchSystemApiManageRows = async () => {
        setIsSystemApiLoading(true);
        try {
            const rows = await getSystemSettingsManage();
            const normalized = Array.isArray(rows) ? rows : [];
            setSystemApiRows(normalized);
            if (normalized.length > 0) {
                const current = normalized.find((row) => String(row.id) === String(selectedSystemApiId)) || normalized[0];
                setSelectedSystemApiId(String(current.id));
            } else {
                setSelectedSystemApiId('');
            }
        } catch (e) {
            console.error('Failed to load system API manage rows', e);
            setSystemApiRows([]);
            setSelectedSystemApiId('');
        } finally {
            setIsSystemApiLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'system_api') {
            fetchSystemApiManageRows();
        }
    }, [activeTab]);

    const getSystemApiConfig = (row) => {
        const raw = row?.config;
        if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw;
        if (typeof raw === 'string') {
            try {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
            } catch {
                return {};
            }
        }
        return {};
    };

    const normalizeApiPricingUnitType = (value) => {
        const unit = String(value || 'per_call').trim() || 'per_call';
        const allowed = new Set(['per_call', 'per_second', 'per_minute', 'per_token', 'per_1k_tokens', 'per_million_tokens']);
        return allowed.has(unit) ? unit : 'per_call';
    };

    const toNonNegativeInt = (value) => {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed < 0) return 0;
        return Math.floor(parsed);
    };

    const getApiPricing = (row) => {
        const cfg = getSystemApiConfig(row);
        const pricing = (cfg?.api_pricing && typeof cfg.api_pricing === 'object') ? cfg.api_pricing : {};
        return {
            unit_type: normalizeApiPricingUnitType(pricing?.unit_type ?? cfg?.billing_unit_type ?? 'per_call'),
            cost: toNonNegativeInt(pricing?.cost ?? cfg?.billing_cost ?? 0),
            cost_input: toNonNegativeInt(pricing?.cost_input ?? cfg?.billing_cost_input ?? 0),
            cost_output: toNonNegativeInt(pricing?.cost_output ?? cfg?.billing_cost_output ?? 0),
        };
    };

    useEffect(() => {
        if (!selectedSystemApiId) {
            setSystemApiForm({
                name: '',
                category: 'LLM',
                provider: '',
                base_url: '',
                model: '',
                webHook: '',
                api_unit_type: 'per_call',
                api_cost: '0',
                api_cost_input: '0',
                api_cost_output: '0',
                smart_priority: '100',
                smart_retry_limit: '1',
                smart_multi_ref_default: false,
                is_active: false,
            });
            return;
        }
        const row = systemApiRows.find((item) => String(item.id) === String(selectedSystemApiId));
        if (!row) return;
        const cfg = getSystemApiConfig(row);
        const pricing = getApiPricing(row);
        setSystemApiForm({
            name: row.name || '',
            category: row.category || 'LLM',
            provider: row.provider || '',
            base_url: row.base_url || '',
            model: row.model || '',
            webHook: cfg?.webHook || '',
            api_unit_type: pricing.unit_type,
            api_cost: String(pricing.cost),
            api_cost_input: String(pricing.cost_input),
            api_cost_output: String(pricing.cost_output),
            smart_priority: String(cfg?.smart_priority ?? cfg?.priority ?? '100'),
            smart_retry_limit: String(cfg?.smart_retry_limit ?? cfg?.retry_limit ?? '1'),
            smart_multi_ref_default: !!cfg?.smart_multi_ref_default,
            is_active: !!row.is_active,
        });
    }, [selectedSystemApiId, systemApiRows]);

    const allSystemApiProviders = React.useMemo(() => {
        const set = new Set();
        systemApiRows.forEach((row) => {
            const provider = String(row?.provider || '').trim();
            if (provider) set.add(provider);
        });
        return Array.from(set);
    }, [systemApiRows]);

    useEffect(() => {
        if (systemApiFilterProvider && systemApiFilterProvider !== 'all') {
            setSystemApiKeyProvider(systemApiFilterProvider);
            return;
        }
        if (!systemApiKeyProvider && allSystemApiProviders.length > 0) {
            setSystemApiKeyProvider(allSystemApiProviders[0]);
        }
    }, [systemApiFilterProvider, allSystemApiProviders, systemApiKeyProvider]);

    useEffect(() => {
        const provider = String(systemApiKeyProvider || '').trim();
        if (!provider) {
            setProviderKeysText('');
            setProviderKeysMeta({ key_count: 0, keys_masked: [] });
            setProviderKeyStrategy('random');
            setProviderKeyWeightsText('');
            return;
        }

        let cancelled = false;
        (async () => {
            try {
                const res = await getSystemProviderKeysManage(provider);
                if (cancelled) return;
                const keys = Array.isArray(res?.keys) ? res.keys : [];
                setProviderKeysText(keys.join('\n'));
                setProviderKeysMeta({
                    key_count: Number(res?.key_count || keys.length || 0),
                    keys_masked: Array.isArray(res?.keys_masked) ? res.keys_masked : [],
                });
                setProviderKeyStrategy(String(res?.strategy || 'random'));
                const weights = Array.isArray(res?.weights) ? res.weights : [];
                setProviderKeyWeightsText(weights.length ? weights.join('\n') : '');
            } catch (e) {
                if (cancelled) return;
                setProviderKeysText('');
                setProviderKeysMeta({ key_count: 0, keys_masked: [] });
                setProviderKeyStrategy('random');
                setProviderKeyWeightsText('');
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [systemApiKeyProvider]);

    const systemApiCategoryOptions = React.useMemo(() => {
        const set = new Set();
        systemApiRows.forEach((row) => {
            const category = String(row?.category || '').trim();
            if (category) set.add(category);
        });
        return Array.from(set);
    }, [systemApiRows]);

    const systemApiProviderOptions = React.useMemo(() => {
        const set = new Set();
        systemApiRows.forEach((row) => {
            const provider = String(row?.provider || '').trim();
            if (!provider) return;
            if (systemApiFilterCategory !== 'all' && String(row?.category || '') !== systemApiFilterCategory) return;
            set.add(provider);
        });
        return Array.from(set);
    }, [systemApiRows, systemApiFilterCategory]);

    const filteredSystemApiRows = React.useMemo(() => {
        return systemApiRows.filter((row) => {
            if (systemApiFilterCategory !== 'all' && String(row?.category || '') !== systemApiFilterCategory) return false;
            if (systemApiFilterProvider !== 'all' && String(row?.provider || '') !== systemApiFilterProvider) return false;
            return true;
        });
    }, [systemApiRows, systemApiFilterCategory, systemApiFilterProvider]);

    const isSystemApiDeprecated = (row) => {
        if (typeof row?.deprecated === 'boolean') return row.deprecated;
        const cfg = getSystemApiConfig(row);
        return !!(cfg?.deprecated || cfg?.is_deprecated || cfg?.disable_api);
    };

    const getSmartPriority = (row) => {
        const cfg = getSystemApiConfig(row);
        const raw = cfg?.smart_priority ?? cfg?.priority ?? 100;
        const parsed = Number(raw);
        return Number.isFinite(parsed) ? parsed : 100;
    };

    const visibleSystemApiRows = React.useMemo(() => {
        let rows = [...filteredSystemApiRows];
        if (systemApiHideDeprecated) {
            rows = rows.filter((row) => !isSystemApiDeprecated(row));
        }
        if (systemApiSortMode === 'priority') {
            rows.sort((a, b) => {
                const pa = getSmartPriority(a);
                const pb = getSmartPriority(b);
                if (pa !== pb) return pa - pb;
                return Number(a?.id || 0) - Number(b?.id || 0);
            });
        }
        return rows;
    }, [filteredSystemApiRows, systemApiSortMode, systemApiHideDeprecated]);

    const getSmartRetryLimit = (row) => {
        const cfg = getSystemApiConfig(row);
        const raw = cfg?.smart_retry_limit ?? cfg?.retry_limit ?? 1;
        const parsed = Number(raw);
        return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
    };

    const isSmartMultiRefDefault = (row) => {
        const cfg = getSystemApiConfig(row);
        return !!cfg?.smart_multi_ref_default;
    };

    const formatApiPricingSummary = (row) => {
        const pricing = getApiPricing(row);
        if (pricing.unit_type === 'per_token' || pricing.unit_type === 'per_1k_tokens' || pricing.unit_type === 'per_million_tokens') {
            return `${pricing.unit_type} | in:${pricing.cost_input} out:${pricing.cost_output}`;
        }
        return `${pricing.unit_type} | ${pricing.cost}`;
    };

    useEffect(() => {
        if (!visibleSystemApiRows.length) {
            setSelectedSystemApiId('');
            return;
        }
        const existsInFiltered = visibleSystemApiRows.some((row) => String(row.id) === String(selectedSystemApiId));
        if (!existsInFiltered) {
            setSelectedSystemApiId(String(visibleSystemApiRows[0].id));
        }
    }, [visibleSystemApiRows, selectedSystemApiId]);

    const handleCreateSystemApiSetting = async () => {
        const provider = String(systemApiForm.provider || '').trim();
        if (!provider) {
            alert('Provider is required.');
            return;
        }
        try {
            await createSystemSettingManage({
                name: String(systemApiForm.name || '').trim() || undefined,
                category: systemApiForm.category || 'LLM',
                provider,
                base_url: String(systemApiForm.base_url || '').trim() || undefined,
                model: String(systemApiForm.model || '').trim() || undefined,
                config: {
                    webHook: String(systemApiForm.webHook || '').trim() || '',
                    api_pricing: {
                        unit_type: normalizeApiPricingUnitType(systemApiForm.api_unit_type),
                        cost: toNonNegativeInt(systemApiForm.api_cost),
                        cost_input: toNonNegativeInt(systemApiForm.api_cost_input),
                        cost_output: toNonNegativeInt(systemApiForm.api_cost_output),
                    },
                    smart_priority: Number(systemApiForm.smart_priority || 100),
                    smart_retry_limit: Number(systemApiForm.smart_retry_limit || 1),
                    smart_multi_ref_default: !!systemApiForm.smart_multi_ref_default,
                },
                is_active: !!systemApiForm.is_active,
            });
            await fetchSystemApiManageRows();
            alert('System API setting created.');
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to create system API setting');
        }
    };

    const handleUpdateSystemApiSetting = async () => {
        if (!selectedSystemApiId) {
            alert('Select a setting first.');
            return;
        }
        try {
            await updateSystemSettingManage(Number(selectedSystemApiId), {
                name: String(systemApiForm.name || '').trim() || undefined,
                category: systemApiForm.category || 'LLM',
                provider: String(systemApiForm.provider || '').trim() || undefined,
                base_url: String(systemApiForm.base_url || '').trim() || undefined,
                model: String(systemApiForm.model || '').trim() || undefined,
                config: {
                    webHook: String(systemApiForm.webHook || '').trim() || '',
                    api_pricing: {
                        unit_type: normalizeApiPricingUnitType(systemApiForm.api_unit_type),
                        cost: toNonNegativeInt(systemApiForm.api_cost),
                        cost_input: toNonNegativeInt(systemApiForm.api_cost_input),
                        cost_output: toNonNegativeInt(systemApiForm.api_cost_output),
                    },
                    smart_priority: Number(systemApiForm.smart_priority || 100),
                    smart_retry_limit: Number(systemApiForm.smart_retry_limit || 1),
                    smart_multi_ref_default: !!systemApiForm.smart_multi_ref_default,
                },
                is_active: !!systemApiForm.is_active,
            });
            await fetchSystemApiManageRows();
            alert('System API setting updated.');
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to update system API setting');
        }
    };

    const handleDeleteSystemApiSetting = async () => {
        if (!selectedSystemApiId) {
            alert('Select a setting first.');
            return;
        }
        if (!await confirmUiMessage('Delete this system API setting?')) return;
        try {
            await deleteSystemSettingManage(Number(selectedSystemApiId));
            await fetchSystemApiManageRows();
            alert('System API setting deleted.');
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to delete system API setting');
        }
    };

    const handleBatchToggleProviderDeprecated = async (deprecated) => {
        const provider = String(systemApiFilterProvider || '').trim();
        if (!provider || provider === 'all') {
            alert('请先在“供应商筛选”中选择具体供应商。');
            return;
        }

        const category = systemApiFilterCategory !== 'all' ? String(systemApiFilterCategory || '').trim() : null;
        const actionLabel = deprecated ? '弃用' : '启用';
        const scopeLabel = category ? `${provider} / ${category}` : provider;
        if (!await confirmUiMessage(`确认批量${actionLabel}供应商 ${scopeLabel} 的 System API 配置？`)) return;

        try {
            const res = await batchToggleSystemProviderDeprecatedManage(provider, !!deprecated, category);
            setSystemApiRows((prev) => prev.map((item) => {
                const sameProvider = String(item?.provider || '').trim() === provider;
                const sameCategory = !category || String(item?.category || '').trim() === category;
                if (!sameProvider || !sameCategory) return item;
                const cfg = getSystemApiConfig(item);
                return {
                    ...item,
                    deprecated: !!deprecated,
                    config: {
                        ...cfg,
                        deprecated: !!deprecated,
                        is_deprecated: !!deprecated,
                        disable_api: !!deprecated,
                    },
                };
            }));
            alert(`批量${actionLabel}完成。匹配 ${res?.matched || 0} 条，变更 ${res?.changed || 0} 条。`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || `批量${actionLabel}失败`);
        }
    };

    const handleToggleSingleSystemApiDeprecated = async (row) => {
        if (!row?.id) return;
        const current = isSystemApiDeprecated(row);
        const next = !current;
        const actionLabel = next ? '弃用' : '启用';
        if (!await confirmUiMessage(`确认${actionLabel}该模型配置？`)) return;

        try {
            const updated = await toggleSystemSettingDeprecatedByKeyManage({
                provider: row.provider,
                category: row.category,
                model: row.model || '',
                setting_id: Number(row.id),
                deprecated: next,
            });
            const effectiveDeprecated = typeof updated?.deprecated === 'boolean' ? !!updated.deprecated : !!next;
            setSystemApiRows((prev) => prev.map((item) => {
                if (Number(item?.id) !== Number(row.id)) return item;
                const cfg = getSystemApiConfig(item);
                return {
                    ...item,
                    ...((updated && typeof updated === 'object') ? updated : {}),
                    deprecated: effectiveDeprecated,
                    config: {
                        ...cfg,
                        deprecated: effectiveDeprecated,
                        is_deprecated: effectiveDeprecated,
                        disable_api: effectiveDeprecated,
                    },
                };
            }));
            alert(`已${actionLabel}：${row.provider} / ${row.model || '-'}`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || `${actionLabel}失败`);
        }
    };

    const handleSaveProviderKeys = async () => {
        const provider = String(systemApiKeyProvider || '').trim();
        if (!provider) {
            alert('请先选择供应商。');
            return;
        }

        const pool = String(providerKeysText || '').split(/\r?\n|,/).map((s) => s.trim()).filter(Boolean);
        const weights = String(providerKeyWeightsText || '').split(/\r?\n|,/).map((s) => Number(s.trim())).filter((n) => Number.isFinite(n) && n > 0);
        setIsProviderKeysSaving(true);
        try {
            const res = await setSystemProviderKeysManage(provider, pool, providerKeyStrategy, (providerKeyStrategy === 'weighted' ? weights : null));
            setProviderKeysMeta({
                key_count: Number(res?.key_count || pool.length || 0),
                keys_masked: Array.isArray(res?.keys_masked) ? res.keys_masked : [],
            });
            setProviderKeyStrategy(String(res?.strategy || providerKeyStrategy || 'random'));
            setProviderKeyWeightsText(Array.isArray(res?.weights) && res.weights.length ? res.weights.join('\n') : '');
            await fetchSystemApiManageRows();
            alert(`供应商密钥池已保存（${res?.key_count || 0} 个）。`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || '保存供应商密钥池失败');
        } finally {
            setIsProviderKeysSaving(false);
        }
    };

    const handleExportSystemApiSettings = async () => {
        setIsSystemApiExporting(true);
        try {
            const payload = await exportSystemSettingsManage();
            const dataStr = JSON.stringify(payload, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            a.href = url;
            a.download = `system_api_settings_${ts}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            alert('System API settings exported.');
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to export system API settings');
        } finally {
            setIsSystemApiExporting(false);
        }
    };

    const handleOpenImportSystemApiSettings = () => {
        if (systemApiImportInputRef.current) {
            systemApiImportInputRef.current.value = '';
            systemApiImportInputRef.current.click();
        }
    };

    const handleImportSystemApiSettingsFile = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const text = await file.text();
            const parsed = JSON.parse(text);
            const items = Array.isArray(parsed?.items) ? parsed.items : [];
            if (!items.length) {
                alert('No items found in import file. Expected { items: [...] }.');
                return;
            }

            const replaceAll = await confirmUiMessage('Replace all existing system API settings before import? Click Cancel for merge/update mode.', {
                title: 'Import Mode',
                confirmText: 'Replace All',
                cancelText: 'Merge/Update',
            });
            setIsSystemApiImporting(true);
            const result = await importSystemSettingsManage({ items, replace_all: replaceAll });
            await fetchSystemApiManageRows();
            alert(`Import finished. Created: ${result?.created || 0}, Updated: ${result?.updated || 0}`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to import system API settings');
        } finally {
            setIsSystemApiImporting(false);
        }
    };

    const handleExportSystemProviderBundle = async () => {
        setIsSystemProviderBundleExporting(true);
        try {
            const payload = await exportSystemProviderBundleManage();
            const dataStr = JSON.stringify(payload, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            a.href = url;
            a.download = `system_api_provider_bundle_${ts}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            alert('System API provider bundle exported.');
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to export system API provider bundle');
        } finally {
            setIsSystemProviderBundleExporting(false);
        }
    };

    const handleOpenImportSystemProviderBundle = () => {
        if (systemProviderBundleImportInputRef.current) {
            systemProviderBundleImportInputRef.current.value = '';
            systemProviderBundleImportInputRef.current.click();
        }
    };

    const handleImportSystemProviderBundleFile = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const text = await file.text();
            const parsed = JSON.parse(text);
            const providers = Array.isArray(parsed?.providers) ? parsed.providers : [];
            if (!providers.length) {
                alert('No providers found in import file. Expected { providers: [...] }.');
                return;
            }

            const validation = await validateSystemProviderBundleManage({ providers, replace_all: false });
            const errorCount = Number(validation?.error_count || 0);
            const warningCount = Number(validation?.warning_count || 0);

            if (errorCount > 0) {
                const firstError = Array.isArray(validation?.errors) && validation.errors.length
                    ? String(validation.errors[0]?.message || '')
                    : '';
                alert(`导入预检失败：发现 ${errorCount} 个错误。${firstError ? `\n首个错误：${firstError}` : ''}`);
                return;
            }

            if (warningCount > 0) {
                const proceed = await confirmUiMessage(`导入预检发现 ${warningCount} 个警告，是否继续导入？`, {
                    title: 'Import Validation Warning',
                    confirmText: 'Continue Import',
                    cancelText: 'Cancel',
                });
                if (!proceed) {
                    return;
                }
            }

            const replaceAll = await confirmUiMessage('Replace all existing system API settings before provider import? Click Cancel for merge/update mode.', {
                title: 'Import Mode',
                confirmText: 'Replace All',
                cancelText: 'Merge/Update',
            });
            setIsSystemProviderBundleImporting(true);
            const result = await importSystemProviderBundleManage({ providers, replace_all: replaceAll });
            await fetchSystemApiManageRows();
            alert(`Provider import finished. Providers: ${result?.providers || 0}, Created: ${result?.created || 0}, Updated: ${result?.updated || 0}`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to import system API provider bundle');
        } finally {
            setIsSystemProviderBundleImporting(false);
        }
    };

    const formatBytes = (value) => {
        const n = Number(value || 0);
        if (!Number.isFinite(n) || n <= 0) return '0 B';
        if (n < 1024) return `${n} B`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
        return `${(n / (1024 * 1024)).toFixed(1)} MB`;
    };

    const fetchLlmLogs = async (preferredFile = null) => {
        setIsLlmLogsLoading(true);
        setLlmLogsError('');
        try {
            const files = await getAdminLlmLogFiles();
            const normalizedFiles = Array.isArray(files) ? files : [];
            setLlmLogFiles(normalizedFiles);

            if (!normalizedFiles.length) {
                setLlmLogContent('No llm log files found.');
                return;
            }

            let targetFile = preferredFile || selectedLlmLogFile || normalizedFiles[0].name;
            if (!normalizedFiles.some((f) => f.name === targetFile)) {
                targetFile = normalizedFiles[0].name;
            }
            setSelectedLlmLogFile(targetFile);

            const view = await getAdminLlmLogView({
                filename: targetFile,
                tail_lines: Math.max(1, Number(llmLogTailLines) || 300),
            });
            setLlmLogContent(view?.content || '');
        } catch (e) {
            const detail = e?.response?.data?.detail || e.message || 'Failed to load LLM logs';
            setLlmLogsError(detail);
            setLlmLogContent('');
        } finally {
            setIsLlmLogsLoading(false);
        }
    };

    const fetchStorageUsage = async () => {
        setIsStorageUsageLoading(true);
        setStorageUsageError('');
        try {
            const payload = await getAdminStorageUsage();
            setStorageUsage(payload || null);
        } catch (e) {
            const detail = e?.response?.data?.detail || e.message || 'Failed to load storage usage';
            setStorageUsageError(detail);
            setStorageUsage(null);
        } finally {
            setIsStorageUsageLoading(false);
        }
    };

    const fetchSmtpConfig = async () => {
        setIsSmtpConfigLoading(true);
        try {
            const res = await api.get('/admin/smtp-config');
            if (res.data) {
                setSmtpConfig({
                    host: res.data.host || '',
                    port: Number(res.data.port || 587),
                    username: res.data.username || '',
                    password: res.data.password || '',
                    use_ssl: !!res.data.use_ssl,
                    use_tls: !!res.data.use_tls,
                    from_email: res.data.from_email || '',
                    frontend_base_url: res.data.frontend_base_url || '',
                });
            }
        } catch (e) {
            console.error('Failed to load SMTP config', e);
        } finally {
            setIsSmtpConfigLoading(false);
        }
    };

    const toDatetimeLocalValue = (isoValue) => {
        const raw = String(isoValue || '').trim();
        if (!raw) return '';
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) return '';
        const pad = (n) => String(n).padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    };

    const toIsoFromDatetimeLocal = (localValue) => {
        const raw = String(localValue || '').trim();
        if (!raw) return '';
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) return '';
        return date.toISOString();
    };

    const fetchMaintenanceConfig = async () => {
        setIsMaintenanceLoading(true);
        try {
            const data = await getAdminMaintenanceConfig();
            setMaintenanceConfig({
                enabled: !!data?.enabled,
                ends_at: toDatetimeLocalValue(data?.ends_at),
                message: String(data?.message || '系统正在维护'),
            });
        } catch (e) {
            console.error('Failed to load maintenance config', e);
        } finally {
            setIsMaintenanceLoading(false);
        }
    };

    const handleSavePaymentConfig = async () => {
        try {
            await api.post('/admin/payment-config', paymentConfig);
            alert("Payment configuration saved successfully!");
        } catch (e) {
            console.error("Failed to save payment config", e);
            alert(`Failed to save payment configuration: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleSaveSmtpConfig = async () => {
        setIsSmtpConfigLoading(true);
        try {
            await api.post('/admin/smtp-config', {
                ...smtpConfig,
                port: Number(smtpConfig.port || 587),
            });
            alert('SMTP configuration saved successfully!');
        } catch (e) {
            console.error('Failed to save SMTP config', e);
            alert(`Failed to save SMTP configuration: ${e?.message || 'Unknown error'}`);
        } finally {
            setIsSmtpConfigLoading(false);
        }
    };

    const handleSendSmtpTestEmail = async () => {
        const toEmail = String(smtpTestEmail || '').trim();
        if (!toEmail) {
            alert('Please input a test recipient email.');
            return;
        }
        setIsSmtpTestLoading(true);
        try {
            await api.post('/admin/smtp-config/test', { to_email: toEmail });
            alert(`Test email sent to ${toEmail}`);
        } catch (e) {
            console.error('Failed to send SMTP test email', e);
            alert(e?.response?.data?.detail || e?.message || 'Failed to send test email');
        } finally {
            setIsSmtpTestLoading(false);
        }
    };

    const handleSendSmtpBroadcast = async () => {
        const subject = String(smtpBroadcast.subject || '').trim();
        const html = String(smtpBroadcast.content_html || '');
        const text = String(smtpBroadcast.content_text || '').trim();

        if (!subject) {
            alert(t('请先填写邮件主题。', 'Please fill in the email subject.'));
            return;
        }
        if (!html.trim() && !text) {
            alert(t('请填写 HTML 或纯文本内容。', 'Please fill HTML or plain text content.'));
            return;
        }

        const ok = await confirmUiMessage(
            t('将向所有用户发送邮件，是否继续？', 'This will send email to ALL users. Continue?'),
            {
                title: t('群发确认', 'Broadcast Confirmation'),
                confirmText: t('继续', 'Continue'),
                cancelText: t('取消', 'Cancel'),
            }
        );
        if (!ok) return;

        const phrase = await promptUiMessage(
            t('为避免误发，请输入确认口令：SEND_TO_ALL_USERS', 'To prevent mistakes, type confirmation phrase: SEND_TO_ALL_USERS'),
            {
                title: t('二次确认', 'Second Confirmation'),
                defaultValue: '',
            }
        );
        if (String(phrase || '').trim() !== 'SEND_TO_ALL_USERS') {
            alert(t('确认口令不正确，已取消发送。', 'Confirmation phrase is incorrect. Sending canceled.'));
            return;
        }

        setIsSmtpBroadcastLoading(true);
        try {
            const res = await api.post('/admin/smtp-config/broadcast', {
                subject,
                content_html: html,
                content_text: text,
                confirm_phrase: 'SEND_TO_ALL_USERS',
            });
            const info = res?.data || {};
            alert(
                t(
                    `群发完成：总计 ${info.total || 0}，成功 ${info.sent || 0}，失败 ${info.failed || 0}，无效邮箱 ${info.invalid || 0}`,
                    `Broadcast finished: total ${info.total || 0}, sent ${info.sent || 0}, failed ${info.failed || 0}, invalid ${info.invalid || 0}`
                )
            );
        } catch (e) {
            console.error('Failed to send SMTP broadcast', e);
            alert(e?.response?.data?.detail || e?.message || 'Failed to send broadcast email');
        } finally {
            setIsSmtpBroadcastLoading(false);
        }
    };

    const handleRunGrsaiDiagnostics = async () => {
        setIsGrsaiDiagLoading(true);
        try {
            const res = await api.get('/admin/upstream-diagnostics/grsai', {
                params: { timeout_seconds: 5 },
            });
            setGrsaiDiagResult(res?.data || null);
        } catch (e) {
            console.error('Failed to run Grsai diagnostics', e);
            setGrsaiDiagResult({
                ok: false,
                error: e?.response?.data?.detail || e?.message || 'Failed to run diagnostics',
            });
        } finally {
            setIsGrsaiDiagLoading(false);
        }
    };

    const handleLoadRuntimeStats = async () => {
        setIsRuntimeStatsLoading(true);
        try {
            const res = await api.get('/admin/runtime-stats');
            setRuntimeStats(res?.data || null);
        } catch (e) {
            console.error('Failed to load runtime stats', e);
            setRuntimeStats({
                error: e?.response?.data?.detail || e?.message || 'Failed to load runtime stats',
            });
        } finally {
            setIsRuntimeStatsLoading(false);
        }
    };

    const handleToggleMaintenance = async () => {
        const nextEnabled = !maintenanceConfig.enabled;
        const endsAtIso = toIsoFromDatetimeLocal(maintenanceConfig.ends_at);

        if (nextEnabled && !endsAtIso) {
            alert(t('请先输入维护结束时间。', 'Please input maintenance end time first.'));
            return;
        }

        setIsMaintenanceLoading(true);
        try {
            const saved = await updateAdminMaintenanceConfig({
                enabled: nextEnabled,
                ends_at: nextEnabled ? endsAtIso : null,
                message: String(maintenanceConfig.message || '系统正在维护').trim() || '系统正在维护',
            });

            setMaintenanceConfig({
                enabled: !!saved?.enabled,
                ends_at: toDatetimeLocalValue(saved?.ends_at),
                message: String(saved?.message || '系统正在维护'),
            });

            alert(nextEnabled ? t('系统维护已开启。', 'Maintenance mode enabled.') : t('系统维护已关闭。', 'Maintenance mode disabled.'));
        } catch (e) {
            console.error('Failed to update maintenance config', e);
            alert(e?.response?.data?.detail || e?.message || t('维护配置更新失败', 'Failed to update maintenance config'));
        } finally {
            setIsMaintenanceLoading(false);
        }
    };

    // Credit Edit State
    const [creditEditUser, setCreditEditUser] = useState(null);
    const [creditAmount, setCreditAmount] = useState(0);

    const fetchAllData = async () => {
        setLoading(true);
        try {
            const [usersRes, transRes, optionsRes, featurePricingRes, defaultApiPricingRes, agentToolPolicyRes] = await Promise.allSettled([
                api.get('/users'),
                getTransactions(50, transactionFilterUser || null),
                getBillingOptions(),
                getBillingFeaturePricing(),
                getBillingDefaultApiPricing(),
                getAgentToolPolicy(),
            ]);

            if (usersRes.status === 'fulfilled') {
                const fetchedUsers = usersRes.value.data;
                setUsers(fetchedUsers);
                
                // Extract System User Settings to populate Model Options
                const systemUsers = fetchedUsers.filter(u => u.is_system);
                if (systemUsers.length > 0) {
                     // Keep room for future dynamic provider/model extraction from system settings.
                }
            } 
            
            if (optionsRes.status === 'fulfilled') {
                setBillingOptions(optionsRes.value);
                if (!featurePricingRes || featurePricingRes.status !== 'fulfilled') {
                    const fromOptions = normalizeFeaturePricing(optionsRes.value?.featurePricing || {});
                    setFeaturePricingMap(fromOptions);
                    setFeaturePricingRows(buildFeaturePricingRows(fromOptions));
                }
            }

            if (featurePricingRes.status === 'fulfilled') {
                const normalized = normalizeFeaturePricing(featurePricingRes.value?.feature_pricing || {});
                setFeaturePricingMap(normalized);
                setFeaturePricingRows(buildFeaturePricingRows(normalized));
            }

            if (defaultApiPricingRes.status === 'fulfilled') {
                const normalizedDefault = normalizeDefaultApiPricingMap(defaultApiPricingRes.value?.default_api_pricing || {});
                const normalizedRecommended = normalizeDefaultApiPricingMap(defaultApiPricingRes.value?.recommended_default_api_pricing || {});
                setDefaultApiPricingMap(normalizedDefault);
                setRecommendedDefaultApiPricingMap(normalizedRecommended);
                setDefaultApiPricingRows(buildDefaultApiPricingRows(normalizedDefault));
            } else {
                const fallbackDefault = normalizeDefaultApiPricingMap({});
                setDefaultApiPricingMap(fallbackDefault);
                setRecommendedDefaultApiPricingMap(fallbackDefault);
                setDefaultApiPricingRows(buildDefaultApiPricingRows(fallbackDefault));
            }

            if (agentToolPolicyRes.status === 'fulfilled') {
                const normalizedPolicy = normalizeAgentToolPolicy(agentToolPolicyRes.value || {});
                setAgentToolPolicy(normalizedPolicy);
                setAgentToolPolicyDraft(JSON.stringify(normalizedPolicy, null, 2));
            }

            if (transRes.status === 'fulfilled') setTransactions(transRes.value.sort((a,b)=>b.id-a.id));
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchTransactionsOnly = async () => {
        try {
            const data = await getTransactions(50, transactionFilterUser || null);
            setTransactions(data.sort((a,b)=>b.id-a.id));
        } catch (e) {
            console.error("Failed to load transactions", e);
        }
    };

    // Reload transactions when filter changes
    useEffect(() => {
        if (activeTab === 'transactions') {
            fetchTransactionsOnly();
        }
    }, [transactionFilterUser, activeTab]);

    const handleSaveFeaturePricing = async () => {
        try {
            setIsFeaturePricingSaving(true);
            const normalized = normalizeFeaturePricing(buildFeaturePricingMapFromRows(featurePricingRows));
            const res = await updateBillingFeaturePricing(normalized);
            const saved = normalizeFeaturePricing(res?.feature_pricing || {});
            setFeaturePricingMap(saved);
            setFeaturePricingRows(buildFeaturePricingRows(saved));
            alert(t('功能定价已保存', 'Feature pricing saved'));
        } catch (e) {
            alert(t('保存功能定价失败：', 'Failed to save feature pricing: ') + (e?.message || 'unknown error'));
        } finally {
            setIsFeaturePricingSaving(false);
        }
    };

    const handleFeaturePricingRowChange = (rowId, field, value) => {
        setFeaturePricingRows((prev) => prev.map((row) => {
            if (row.id !== rowId) return row;
            if (field === 'credits') {
                return { ...row, credits: String(value).replace(/[^0-9]/g, '') };
            }
            return { ...row, [field]: value };
        }));
    };

    const handleAddFeaturePricingRow = () => {
        setFeaturePricingRows((prev) => [...prev, createEmptyFeaturePricingRow()]);
    };

    const handleRemoveFeaturePricingRow = (rowId) => {
        setFeaturePricingRows((prev) => prev.filter((row) => row.id !== rowId));
    };

    const handleResetFeaturePricingRows = () => {
        setFeaturePricingRows(buildFeaturePricingRows(featurePricingMap || {}));
    };

    const handleDefaultApiPricingRowChange = (rowId, field, value) => {
        setDefaultApiPricingRows((prev) => prev.map((row) => {
            if (row.id !== rowId) return row;
            if (field === 'unit_type') {
                return { ...row, unit_type: normalizeApiPricingUnitType(value) };
            }
            return { ...row, [field]: String(value).replace(/[^0-9]/g, '') };
        }));
    };

    const handleSaveDefaultApiPricing = async () => {
        try {
            setIsDefaultApiPricingSaving(true);
            const normalized = buildDefaultApiPricingMapFromRows(defaultApiPricingRows);
            const res = await updateBillingDefaultApiPricing(normalized);
            const saved = normalizeDefaultApiPricingMap(res?.default_api_pricing || {});
            setDefaultApiPricingMap(saved);
            setDefaultApiPricingRows(buildDefaultApiPricingRows(saved));
            alert(t('默认 API 定价映射已保存', 'Default API pricing map saved'));
        } catch (e) {
            alert(t('保存默认 API 定价映射失败：', 'Failed to save default API pricing map: ') + (e?.message || 'unknown error'));
        } finally {
            setIsDefaultApiPricingSaving(false);
        }
    };

    const handleResetDefaultApiPricingRows = () => {
        setDefaultApiPricingRows(buildDefaultApiPricingRows(defaultApiPricingMap || {}));
    };

    const handleRestoreRecommendedDefaultApiPricingRows = () => {
        setDefaultApiPricingRows(buildDefaultApiPricingRows(recommendedDefaultApiPricingMap || {}));
    };

    const handleSaveAgentToolPolicy = async () => {
        try {
            const parsed = JSON.parse(agentToolPolicyDraft || '{}');
            if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                alert(t('Agent 工具策略必须是 JSON 对象', 'Agent tool policy must be a JSON object'));
                return;
            }

            setIsAgentToolPolicySaving(true);
            const normalized = normalizeAgentToolPolicy(parsed);
            const saved = await updateAgentToolPolicy(normalized);
            const normalizedSaved = normalizeAgentToolPolicy(saved || {});
            setAgentToolPolicy(normalizedSaved);
            setAgentToolPolicyDraft(JSON.stringify(normalizedSaved, null, 2));
            alert(t('Agent 工具策略已保存', 'Agent tool policy saved'));
        } catch (e) {
            alert(t('保存 Agent 工具策略失败：', 'Failed to save agent tool policy: ') + (e?.message || 'unknown error'));
        } finally {
            setIsAgentToolPolicySaving(false);
        }
    };

    const handleUpdateCredits = async () => {
        if (!creditEditUser) return;
        try {
            await updateUserCredits(creditEditUser.id, parseInt(creditAmount), 'set'); // or 'add' logic if UI supports it
            setCreditEditUser(null);
            fetchAllData();
        } catch (e) { alert(e.message); }
    };

    // Initial Fetch
    useEffect(() => {
        fetchAllData();
    }, []);

    // Helper Components
    const TabButton = ({ id, label, icon: Icon }) => (
        <button
            onClick={() => setActiveTab(id)}
            className={`relative flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all whitespace-nowrap ${
                activeTab === id
                    ? 'bg-primary/10 border-primary/30 text-white'
                    : 'bg-transparent border-transparent text-gray-300 hover:bg-white/5 hover:text-white'
            }`}
        >
            <Icon size={16} />
            {label}
            <span
                className={`absolute left-3 right-3 -bottom-1 h-0.5 rounded-full transition-all ${
                    activeTab === id ? 'bg-primary opacity-100' : 'bg-transparent opacity-0'
                }`}
            />
        </button>
    );

    const Toggle = ({ active, onClick, color = "bg-green-500", label }) => (
        <button 
            onClick={onClick}
            className={`
                relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-primary
                ${active ? color : 'bg-gray-700'}
            `}
            title={label}
        >
            <span
                className={`${
                    active ? 'translate-x-6' : 'translate-x-1'
                } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
            />
        </button>
    );



    const updateUser = async (userId, data) => {
        try {
            const response = await api.put(`/users/${userId}`, data);
            setUsers(users.map(u => u.id === userId ? { ...u, ...response.data } : u));
            if (data.is_system) fetchAllData();
        } catch (e) {
            alert(e.message || t('更新失败', 'Update failed'));
        }
    };

    if (error) {
         return (
             <div className="min-h-screen bg-[#09090b] text-white flex flex-col">
                <div className="container mx-auto px-4 pt-8">
                    <button
                        onClick={() => window.history.back()}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 text-sm"
                    >
                        <ArrowLeft size={16} />
                        {t('返回', 'Back')}
                    </button>
                </div>
                <div className="flex-1 flex items-center justify-center">
                    <div className="bg-red-500/10 border border-red-500/50 p-8 rounded-xl text-center">
                        <Shield className="w-12 h-12 text-red-500 mx-auto mb-4" />
                        <h2 className="text-xl font-bold mb-2">{t('访问受限', 'Access Restricted')}</h2>
                        <p className="text-red-200">{error}</p>
                    </div>
                </div>
                <Footer />
             </div>
         )
    }

    return (
        <div className="min-h-screen bg-[#09090b] text-white flex flex-col font-sans">
            <main className="flex-1 w-full max-w-[1920px] mx-auto px-4 pt-8 pb-8">
                <div className="mb-4 flex items-start justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Shield className="w-8 h-8 text-primary" />
                            {t('管理控制台', 'Admin Console')}
                        </h1>
                        <p className="text-gray-400 mt-1">{t('管理用户、权限与计费。', 'Manage users, permissions, and billing.')}</p>
                    </div>
                    <button
                        onClick={() => window.history.back()}
                        className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 shrink-0"
                        title={t('返回', 'Back')}
                        aria-label={t('返回', 'Back')}
                    >
                        <ArrowLeft size={16} />
                    </button>

                </div>

                <div className="mb-6 rounded-xl border border-white/10 bg-white/5 p-1.5 overflow-x-auto">
                    <div className="flex items-center gap-1 min-w-max">
                        <TabButton id="users" label={t('用户', 'Users')} icon={User} />
                        <TabButton id="pricing" label={t('定价', 'Pricing')} icon={DollarSign} />
                        <TabButton id="transactions" label={t('记录', 'History')} icon={Activity} />
                        <TabButton id="system_api" label={t('系统 API', 'System API')} icon={Key} />
                        <TabButton id="prompt_skills" label={t('Prompt Skills', 'Prompt Skills')} icon={List} />
                        <TabButton id="storage_usage" label={t('磁盘统计', 'Storage Usage')} icon={HardDrive} />
                        <TabButton id="llm_logs" label={t('LLM 日志', 'LLM Logs')} icon={List} />
                        <TabButton id="payment" label={t('支付', 'Payment')} icon={CreditCard} />
                        <TabButton id="smtp" label={t('邮件 SMTP', 'Email SMTP')} icon={Mail} />
                    </div>
                </div>

                {/* Content Area */}
                <div className="bg-[#18181b] rounded-xl border border-gray-800 p-6 min-h-[500px]">
                    
                    {/* PAYMENT TAB */}
                    {activeTab === 'payment' && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                            <h2 className="text-xl font-bold mb-6 flex items-center gap-2 text-white">
                                <CreditCard className="text-primary"/> {t('微信支付配置', 'WeChat Pay Configuration')}
                            </h2>

                            <div className="space-y-6 max-w-4xl">
                                {/* Mode Selection */}
                                <div className="bg-black/20 p-4 rounded-lg border border-white/10">
                                    <label className="block text-sm font-medium mb-3 text-primary">{t('支付环境', 'Payment Environment')}</label>
                                    <div className="flex items-center gap-6">
                                        <label className={`flex items-center gap-2 cursor-pointer p-3 rounded-lg border transition-all ${paymentConfig.use_mock ? 'bg-primary/20 border-primary' : 'border-gray-700 hover:bg-white/5'}`}>
                                            <input 
                                                type="radio" 
                                                checked={paymentConfig.use_mock} 
                                                onChange={() => setPaymentConfig({...paymentConfig, use_mock: true})}
                                                className="hidden"
                                            />
                                            <div className="w-4 h-4 rounded-full border border-gray-400 flex items-center justify-center">
                                                {paymentConfig.use_mock && <div className="w-2 h-2 rounded-full bg-primary" />}
                                            </div>
                                            <span className="font-bold text-yellow-400">{t('模拟 / 沙箱', 'Mock / Sandbox')}</span>
                                        </label>
                                        <label className={`flex items-center gap-2 cursor-pointer p-3 rounded-lg border transition-all ${!paymentConfig.use_mock ? 'bg-primary/20 border-primary' : 'border-gray-700 hover:bg-white/5'}`}>
                                            <input 
                                                type="radio" 
                                                checked={!paymentConfig.use_mock} 
                                                onChange={() => setPaymentConfig({...paymentConfig, use_mock: false})}
                                                className="hidden"
                                            />
                                            <div className="w-4 h-4 rounded-full border border-gray-400 flex items-center justify-center">
                                                {!paymentConfig.use_mock && <div className="w-2 h-2 rounded-full bg-primary" />}
                                            </div>
                                            <span className="font-bold text-green-400">{t('正式环境', 'Live Production')}</span>
                                        </label>
                                    </div>
                                    <p className="text-xs text-gray-500 mt-2">
                                        {t('模拟模式会立即返回支付成功；正式模式会连接微信支付 API。', 'Mock mode simulates payment success immediately. Live mode connects to WeChat Pay API.')}
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">{t('App ID（微信 AppID）', 'App ID (WeChat AppID)')}</label>
                                            <input 
                                                type="text" 
                                                value={paymentConfig.appid}
                                                onChange={(e) => setPaymentConfig({...paymentConfig, appid: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('例如：wx8888888888888888', 'e.g. wx8888888888888888')}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">{t('商户号（MchID）', 'Merchant ID (MchID)')}</label>
                                            <input 
                                                type="text" 
                                                value={paymentConfig.mchid}
                                                onChange={(e) => setPaymentConfig({...paymentConfig, mchid: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('例如：1600000000', 'e.g. 1600000000')}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">{t('API V3 密钥', 'API V3 Key')}</label>
                                            <input 
                                                type="password" 
                                                value={paymentConfig.api_v3_key}
                                                onChange={(e) => setPaymentConfig({...paymentConfig, api_v3_key: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('32 位 API Key', '32 characters API Key')}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">{t('回调通知 URL', 'Notify URL')}</label>
                                            <input 
                                                type="text" 
                                                value={paymentConfig.notify_url}
                                                onChange={(e) => setPaymentConfig({...paymentConfig, notify_url: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('例如：https://api.yourdomain.com/billing/recharge/notify', 'e.g. https://api.yourdomain.com/billing/recharge/notify')}
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">{t('证书序列号', 'Certificate Serial No.')}</label>
                                            <input 
                                                type="text" 
                                                value={paymentConfig.cert_serial_no}
                                                onChange={(e) => setPaymentConfig({...paymentConfig, cert_serial_no: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('证书序列号', 'Certificate serial number')}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">{t('私钥（PEM 内容）', 'Private Key (PEM Content)')}</label>
                                            <textarea 
                                                value={paymentConfig.private_key}
                                                onChange={(e) => setPaymentConfig({...paymentConfig, private_key: e.target.value})}
                                                className="w-full h-48 bg-black/40 border border-gray-700 rounded p-2.5 text-xs font-mono focus:border-primary outline-none resize-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----')}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="pt-6 flex justify-end border-t border-white/10">
                                    <button 
                                        onClick={handleSavePaymentConfig}
                                        disabled={isPaymentConfigLoading}
                                        className="bg-primary text-black px-6 py-2.5 rounded-lg font-bold hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transform active:scale-95 transition-all"
                                    >
                                        {isPaymentConfigLoading ? <RefreshCw className="animate-spin" size={18}/> : <Check size={18}/>}
                                        {t('保存配置', 'Save Configuration')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* SMTP TAB */}
                    {activeTab === 'smtp' && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                            <h2 className="text-xl font-bold mb-6 flex items-center gap-2 text-white">
                                <Mail className="text-primary"/> {t('邮件 SMTP 配置', 'Email SMTP Configuration')}
                            </h2>

                            <div className="space-y-6 max-w-4xl">
                                <div className="border border-yellow-400/30 bg-yellow-500/10 rounded-lg p-4 space-y-3">
                                    <h3 className="text-sm font-bold text-yellow-200">{t('系统维护模式', 'System Maintenance Mode')}</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3">
                                        <input
                                            type="datetime-local"
                                            value={maintenanceConfig.ends_at}
                                            onChange={(e) => setMaintenanceConfig((prev) => ({ ...prev, ends_at: e.target.value }))}
                                            className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                        />
                                        <button
                                            onClick={handleToggleMaintenance}
                                            disabled={isMaintenanceLoading}
                                            className={`px-4 py-2.5 rounded-lg font-bold disabled:opacity-50 flex items-center justify-center gap-2 ${maintenanceConfig.enabled ? 'bg-green-600 text-white hover:bg-green-500' : 'bg-yellow-500 text-black hover:opacity-90'}`}
                                        >
                                            {isMaintenanceLoading ? <RefreshCw className="animate-spin" size={16}/> : <Settings size={16}/>}
                                            {maintenanceConfig.enabled ? t('恢复正常', 'Restore Normal') : t('启动维护', 'Start Maintenance')}
                                        </button>
                                    </div>
                                    <p className="text-xs text-yellow-100">
                                        {maintenanceConfig.enabled
                                            ? t(`系统正在维护，预计 ${maintenanceConfig.ends_at || '-'} 结束。`, `System is under maintenance, estimated end at ${maintenanceConfig.ends_at || '-'}.`)
                                            : t('维护模式关闭，用户可正常访问。', 'Maintenance mode is off; users can access normally.')}
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">SMTP Host</label>
                                            <input
                                                type="text"
                                                value={smtpConfig.host}
                                                onChange={(e) => setSmtpConfig({...smtpConfig, host: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder="smtp.qq.com"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">SMTP Port</label>
                                            <input
                                                type="number"
                                                value={smtpConfig.port}
                                                onChange={(e) => setSmtpConfig({...smtpConfig, port: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder="587"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">SMTP Username</label>
                                            <input
                                                type="text"
                                                value={smtpConfig.username}
                                                onChange={(e) => setSmtpConfig({...smtpConfig, username: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('发信邮箱账号', 'Sender email account')}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">SMTP Password / App Password</label>
                                            <input
                                                type="password"
                                                value={smtpConfig.password}
                                                onChange={(e) => setSmtpConfig({...smtpConfig, password: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('邮箱授权码', 'Email app password')}
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">From Email</label>
                                            <input
                                                type="text"
                                                value={smtpConfig.from_email}
                                                onChange={(e) => setSmtpConfig({...smtpConfig, from_email: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('例如：noreply@yourdomain.com', 'e.g. noreply@yourdomain.com')}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs uppercase font-bold text-gray-500 mb-1">Frontend Base URL</label>
                                            <input
                                                type="text"
                                                value={smtpConfig.frontend_base_url}
                                                onChange={(e) => setSmtpConfig({...smtpConfig, frontend_base_url: e.target.value})}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                                placeholder={t('例如：https://your-frontend-domain.com', 'e.g. https://your-frontend-domain.com')}
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                {t('用于密码重置邮件中的跳转链接。', 'Used for password reset links in email.')}
                                            </p>
                                        </div>
                                        <div className="bg-black/20 p-4 rounded-lg border border-white/10">
                                            <label className="flex items-center gap-3 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={!!smtpConfig.use_ssl}
                                                    onChange={(e) => setSmtpConfig({...smtpConfig, use_ssl: e.target.checked, use_tls: e.target.checked ? false : smtpConfig.use_tls})}
                                                />
                                                <span className="font-medium text-white">{t('启用 SSL（常用于 465 端口）', 'Enable SSL (usually for port 465)')}</span>
                                            </label>
                                        </div>
                                        <div className="bg-black/20 p-4 rounded-lg border border-white/10">
                                            <label className="flex items-center gap-3 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={!!smtpConfig.use_tls}
                                                    onChange={(e) => setSmtpConfig({...smtpConfig, use_tls: e.target.checked, use_ssl: e.target.checked ? false : smtpConfig.use_ssl})}
                                                />
                                                <span className="font-medium text-white">{t('启用 STARTTLS（推荐）', 'Enable STARTTLS (recommended)')}</span>
                                            </label>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 border-t border-white/10 pt-5">
                                    <input
                                        type="email"
                                        value={smtpTestEmail}
                                        onChange={(e) => setSmtpTestEmail(e.target.value)}
                                        className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                        placeholder={t('输入测试收件邮箱', 'Input test recipient email')}
                                    />
                                    <button
                                        onClick={handleSendSmtpTestEmail}
                                        disabled={isSmtpTestLoading || isSmtpConfigLoading}
                                        className="bg-white/10 text-white px-4 py-2.5 rounded-lg font-medium hover:bg-white/20 disabled:opacity-50 flex items-center justify-center gap-2"
                                    >
                                        {isSmtpTestLoading ? <RefreshCw className="animate-spin" size={16}/> : <Mail size={16}/>}
                                        {t('发送测试邮件', 'Send Test Email')}
                                    </button>
                                </div>

                                <div className="border-t border-white/10 pt-5 space-y-3">
                                    <div className="flex items-center justify-between gap-3 flex-wrap">
                                        <h3 className="text-sm font-bold text-white">{t('Grsai 连通性诊断（Render 环境）', 'Grsai Connectivity Diagnostics (Render Environment)')}</h3>
                                        <button
                                            onClick={handleRunGrsaiDiagnostics}
                                            disabled={isGrsaiDiagLoading}
                                            className="bg-white/10 text-white px-4 py-2 rounded-lg font-medium hover:bg-white/20 disabled:opacity-50 flex items-center gap-2"
                                        >
                                            {isGrsaiDiagLoading ? <RefreshCw className="animate-spin" size={16}/> : <Activity size={16}/>}
                                            {t('运行诊断', 'Run Diagnostics')}
                                        </button>
                                    </div>

                                    {!grsaiDiagResult && (
                                        <p className="text-xs text-gray-400">
                                            {t('点击“运行诊断”后将返回主备域名的 DNS / TCP / HTTP 可达性与代理环境变量。', 'Click "Run Diagnostics" to check DNS / TCP / HTTP reachability and proxy env vars for primary/fallback domains.')}
                                        </p>
                                    )}

                                    {!!grsaiDiagResult && (
                                        <div className="bg-black/20 border border-white/10 rounded-lg p-3 space-y-3 text-sm">
                                            <div className="flex items-center gap-2">
                                                <span className={`inline-block w-2 h-2 rounded-full ${grsaiDiagResult.ok ? 'bg-green-400' : 'bg-red-400'}`}></span>
                                                <span className="text-white font-semibold">
                                                    {grsaiDiagResult.ok ? t('至少一个上游可达', 'At least one upstream is reachable') : t('上游不可达或异常', 'Upstream unreachable or abnormal')}
                                                </span>
                                            </div>

                                            {grsaiDiagResult.error && (
                                                <div className="text-red-300 text-xs">{String(grsaiDiagResult.error)}</div>
                                            )}

                                            {Array.isArray(grsaiDiagResult.checks) && grsaiDiagResult.checks.map((item) => (
                                                <div key={item?.name || Math.random()} className="border border-white/10 rounded p-2">
                                                    <div className="text-white font-medium mb-1">{item?.name || 'upstream'} · {item?.host || '-'}</div>
                                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-gray-300">
                                                        <div>DNS: {item?.dns?.ok ? 'OK' : 'FAIL'} ({item?.dns?.ms ?? '-'}ms)</div>
                                                        <div>TCP: {item?.tcp?.ok ? 'OK' : 'FAIL'} ({item?.tcp?.ms ?? '-'}ms)</div>
                                                        <div>HTTP: {item?.http?.ok ? 'OK' : 'FAIL'} ({item?.http?.status ?? '-'}, {item?.http?.ms ?? '-'}ms)</div>
                                                    </div>
                                                    {item?.dns?.error && <div className="text-red-300 text-xs mt-1">DNS Error: {String(item.dns.error)}</div>}
                                                    {item?.tcp?.error && <div className="text-red-300 text-xs mt-1">TCP Error: {String(item.tcp.error)}</div>}
                                                    {item?.http?.error && <div className="text-red-300 text-xs mt-1">HTTP Error: {String(item.http.error)}</div>}
                                                </div>
                                            ))}

                                            {!!grsaiDiagResult.proxy_env && (
                                                <div className="text-xs text-gray-400">
                                                    HTTP_PROXY: {grsaiDiagResult.proxy_env.HTTP_PROXY || '(empty)'}<br />
                                                    HTTPS_PROXY: {grsaiDiagResult.proxy_env.HTTPS_PROXY || '(empty)'}<br />
                                                    NO_PROXY: {grsaiDiagResult.proxy_env.NO_PROXY || '(empty)'}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                <div className="border-t border-white/10 pt-5 space-y-3">
                                    <div className="flex items-center justify-between gap-3 flex-wrap">
                                        <h3 className="text-sm font-bold text-white">{t('运行时内存监控（Render）', 'Runtime Memory Monitor (Render)')}</h3>
                                        <button
                                            onClick={handleLoadRuntimeStats}
                                            disabled={isRuntimeStatsLoading}
                                            className="bg-white/10 text-white px-4 py-2 rounded-lg font-medium hover:bg-white/20 disabled:opacity-50 flex items-center gap-2"
                                        >
                                            {isRuntimeStatsLoading ? <RefreshCw className="animate-spin" size={16}/> : <Activity size={16}/>}
                                            {t('刷新监控', 'Refresh Stats')}
                                        </button>
                                    </div>

                                    {!runtimeStats && (
                                        <p className="text-xs text-gray-400">
                                            {t('显示服务实例、图片任务缓存条目数、状态分布与估算内存占用。', 'Shows service instance info, image job cache size, status distribution, and estimated memory usage.')}
                                        </p>
                                    )}

                                    {!!runtimeStats && (
                                        <div className="bg-black/20 border border-white/10 rounded-lg p-3 space-y-3 text-sm">
                                            {runtimeStats.error ? (
                                                <div className="text-red-300 text-xs">{String(runtimeStats.error)}</div>
                                            ) : (
                                                <>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-300">
                                                        <div>PID: {runtimeStats?.pid ?? '-'}</div>
                                                        <div>Commit: {runtimeStats?.render?.git_commit || '-'}</div>
                                                        <div>Instance: {runtimeStats?.render?.instance_id || '-'}</div>
                                                        <div>Service: {runtimeStats?.render?.service_id || '-'}</div>
                                                    </div>
                                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-gray-200">
                                                        <div>
                                                            {t('缓存条目', 'Cache Items')}: <span className="font-semibold">{runtimeStats?.image_jobs?.store_items ?? 0}</span>
                                                        </div>
                                                        <div>
                                                            {t('估算内存(MB)', 'Estimated MB')}: <span className="font-semibold">{runtimeStats?.image_jobs?.approx_store_mb ?? 0}</span>
                                                        </div>
                                                        <div>
                                                            TTL(s): <span className="font-semibold">{runtimeStats?.image_jobs?.ttl_seconds ?? '-'}</span>
                                                        </div>
                                                    </div>
                                                    <div className="text-xs text-gray-400">
                                                        max_items: {runtimeStats?.image_jobs?.max_items ?? '-'}
                                                        {' | '}
                                                        oldest: {runtimeStats?.image_jobs?.oldest_created_at || '-'}
                                                        {' | '}
                                                        newest: {runtimeStats?.image_jobs?.newest_created_at || '-'}
                                                    </div>
                                                    <div className="text-xs text-gray-300">
                                                        {t('状态分布', 'Status Counts')}:
                                                        {' '}
                                                        {runtimeStats?.image_jobs?.status_counts
                                                            ? Object.entries(runtimeStats.image_jobs.status_counts)
                                                                .map(([k, v]) => `${k}:${v}`)
                                                                .join(' | ')
                                                            : '-'}
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    )}
                                </div>

                                <div className="border-t border-white/10 pt-5 space-y-3">
                                    <h3 className="text-sm font-bold text-white">{t('群发邮件给所有用户', 'Broadcast Email to All Users')}</h3>
                                    <p className="text-xs text-gray-400">
                                        {t('支持 HTML 内容（可包含符号、链接、图片标签如 <img src="..." />）。发送前需二次确认口令，避免误发。', 'Supports HTML content (symbols, links, image tags like <img src="..." />). Requires double confirmation phrase before sending.')}
                                    </p>

                                    <input
                                        type="text"
                                        value={smtpBroadcast.subject}
                                        onChange={(e) => setSmtpBroadcast((prev) => ({ ...prev, subject: e.target.value }))}
                                        className="w-full bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none focus:ring-1 focus:ring-primary"
                                        placeholder={t('邮件主题', 'Email subject')}
                                    />

                                    <textarea
                                        value={smtpBroadcast.content_html}
                                        onChange={(e) => setSmtpBroadcast((prev) => ({ ...prev, content_html: e.target.value }))}
                                        className="w-full h-40 bg-black/40 border border-gray-700 rounded p-2.5 text-sm font-mono focus:border-primary outline-none resize-y focus:ring-1 focus:ring-primary"
                                        placeholder={t('HTML 内容（可选，推荐）', 'HTML content (optional, recommended)')}
                                    />

                                    <textarea
                                        value={smtpBroadcast.content_text}
                                        onChange={(e) => setSmtpBroadcast((prev) => ({ ...prev, content_text: e.target.value }))}
                                        className="w-full h-24 bg-black/40 border border-gray-700 rounded p-2.5 text-sm focus:border-primary outline-none resize-y focus:ring-1 focus:ring-primary"
                                        placeholder={t('纯文本内容（可选，作为兜底）', 'Plain text content (optional, fallback)')}
                                    />

                                    <div className="flex justify-end">
                                        <button
                                            onClick={handleSendSmtpBroadcast}
                                            disabled={isSmtpBroadcastLoading || isSmtpConfigLoading}
                                            className="bg-red-500/80 text-white px-5 py-2.5 rounded-lg font-bold hover:bg-red-500 disabled:opacity-50 flex items-center gap-2"
                                        >
                                            {isSmtpBroadcastLoading ? <RefreshCw className="animate-spin" size={16}/> : <Mail size={16}/>}
                                            {t('确认并群发', 'Confirm & Broadcast')}
                                        </button>
                                    </div>
                                </div>

                                <div className="pt-6 flex justify-end border-t border-white/10">
                                    <button
                                        onClick={handleSaveSmtpConfig}
                                        disabled={isSmtpConfigLoading}
                                        className="bg-primary text-black px-6 py-2.5 rounded-lg font-bold hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transform active:scale-95 transition-all"
                                    >
                                        {isSmtpConfigLoading ? <RefreshCw className="animate-spin" size={18}/> : <Check size={18}/>}
                                        {t('保存 SMTP 配置', 'Save SMTP Configuration')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* USERS TAB */}
                    {activeTab === 'users' && (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-gray-800 text-gray-400 text-sm">
                                        <th className="p-3">{t('用户', 'User')}</th>
                                        <th className="p-3">{t('姓名', 'Full Name')}</th>
                                        <th className="p-3">{t('积分', 'Credits')}</th>
                                        <th className="p-3 text-center">{t('启用', 'Active')}</th>
                                        <th className="p-3 text-center">{t('状态', 'Status')}</th>
                                        <th className="p-3 text-center">{t('邮箱已验证', 'Email Verified')}</th>
                                        <th className="p-3 text-center">{t('授权', 'Authorized')}</th>
                                        <th className="p-3 text-center">{t('系统密钥提供方', 'System Key Provider')}</th>
                                        <th className="p-3 text-center">{t('超级管理员', 'Superuser')}</th>
                                        <th className="p-3">{t('操作', 'Actions')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr key={user.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                            <td className="p-3">
                                                <input
                                                    className="w-full bg-black/30 border border-gray-700 rounded px-2 py-1 text-sm"
                                                    value={user.username || ''}
                                                    onChange={(e) => setUsers(users.map(u => u.id === user.id ? { ...u, username: e.target.value } : u))}
                                                    onBlur={() => updateUser(user.id, { username: user.username })}
                                                />
                                                <input
                                                    className="w-full mt-1 bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
                                                    value={user.email || ''}
                                                    onChange={(e) => setUsers(users.map(u => u.id === user.id ? { ...u, email: e.target.value } : u))}
                                                    onBlur={() => updateUser(user.id, { email: user.email })}
                                                />
                                            </td>
                                            <td className="p-3">
                                                <input
                                                    className="w-full bg-black/30 border border-gray-700 rounded px-2 py-1 text-sm"
                                                    value={user.full_name || ''}
                                                    onChange={(e) => setUsers(users.map(u => u.id === user.id ? { ...u, full_name: e.target.value } : u))}
                                                    onBlur={() => updateUser(user.id, { full_name: user.full_name })}
                                                />
                                            </td>
                                            <td className="p-3 font-mono text-green-400">
                                                {user.credits}
                                                <button 
                                                    onClick={() => { setCreditEditUser(user); setCreditAmount(user.credits); }}
                                                    className="ml-2 text-gray-500 hover:text-white"
                                                >
                                                    <Edit2 size={12} />
                                                </button>
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle 
                                                    active={user.is_active} 
                                                    onClick={() => updateUser(user.id, { is_active: !user.is_active })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                <select
                                                    className="bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs"
                                                    value={user.account_status ?? 1}
                                                    onChange={(e) => updateUser(user.id, { account_status: Number(e.target.value) })}
                                                >
                                                    <option value={1}>{t('正常', 'Active')}</option>
                                                    <option value={0}>{t('禁用', 'Disabled')}</option>
                                                    <option value={-1}>{t('待邮箱校验', 'Pending Verify')}</option>
                                                </select>
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle
                                                    active={!!user.email_verified}
                                                    color="bg-amber-500"
                                                    onClick={() => updateUser(user.id, { email_verified: !user.email_verified })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle 
                                                    active={user.is_authorized} 
                                                    color="bg-blue-500"
                                                    onClick={() => updateUser(user.id, { is_authorized: !user.is_authorized })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle 
                                                    active={user.is_system} 
                                                    color="bg-purple-500"
                                                    onClick={() => updateUser(user.id, { is_system: !user.is_system })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                 <Toggle 
                                                    active={user.is_superuser} 
                                                    color="bg-red-500"
                                                    onClick={() => updateUser(user.id, { is_superuser: !user.is_superuser })}
                                                />
                                            </td>
                                            <td className="p-3">
                                                <button
                                                    className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20"
                                                    onClick={async () => {
                                                        const pwd = window.prompt(t('请输入新密码（至少 6 位）', 'Enter new password (min 6 chars)'));
                                                        if (!pwd) return;
                                                        await updateUser(user.id, { password: pwd });
                                                    }}
                                                >
                                                    {t('重置密码', 'Reset Password')}
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {/* PRICING TAB */}
                    {activeTab === 'pricing' && (
                        <div>
                            <div className="space-y-4">
                                <div className="bg-black/30 border border-white/10 rounded-lg p-4">
                                    <h3 className="text-lg font-bold mb-2">{t('功能定价（积分）', 'Feature Pricing (Credits)')}</h3>
                                    <p className="text-xs text-gray-400 mb-3">
                                        {t('按功能维度设置固定积分消耗，未配置功能默认 0。每行填写一个功能键与积分。', 'Set fixed credit cost by feature. Unconfigured features default to 0. Fill one feature key and credits per row.')}
                                    </p>

                                    <div className="space-y-2">
                                        {featurePricingRows.length === 0 && (
                                            <div className="text-xs text-gray-400 border border-dashed border-white/20 rounded p-3">
                                                {t('暂无功能定价项，请点击“新增条目”。', 'No feature pricing entries yet. Click "Add Entry".')}
                                            </div>
                                        )}

                                        {featurePricingRows.map((row) => (
                                            <div key={row.id} className="grid grid-cols-12 gap-2 items-center">
                                                <input
                                                    value={row.feature}
                                                    onChange={(e) => handleFeaturePricingRowChange(row.id, 'feature', e.target.value)}
                                                    placeholder={t('功能键，例如 llm_chat', 'Feature key, e.g. llm_chat')}
                                                    className="col-span-8 bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                />
                                                <input
                                                    value={row.credits}
                                                    onChange={(e) => handleFeaturePricingRowChange(row.id, 'credits', e.target.value)}
                                                    placeholder="0"
                                                    inputMode="numeric"
                                                    className="col-span-3 bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                />
                                                <button
                                                    onClick={() => handleRemoveFeaturePricingRow(row.id)}
                                                    className="col-span-1 inline-flex items-center justify-center h-8 rounded bg-gray-700 hover:bg-gray-600 text-white"
                                                    title={t('删除条目', 'Delete Entry')}
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="mt-3 flex items-center gap-2">
                                        <button
                                            onClick={handleAddFeaturePricingRow}
                                            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded inline-flex items-center gap-1"
                                        >
                                            <Plus className="w-3.5 h-3.5" />
                                            {t('新增条目', 'Add Entry')}
                                        </button>
                                        <button
                                            onClick={handleSaveFeaturePricing}
                                            disabled={isFeaturePricingSaving}
                                            className="bg-primary hover:bg-primary/90 text-white px-3 py-1 rounded disabled:opacity-50"
                                        >
                                            {isFeaturePricingSaving ? t('保存中...', 'Saving...') : t('保存功能定价', 'Save Feature Pricing')}
                                        </button>
                                        <button
                                            onClick={handleResetFeaturePricingRows}
                                            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded"
                                        >
                                            {t('重置草稿', 'Reset Draft')}
                                        </button>
                                    </div>
                                </div>

                                <div className="bg-black/30 border border-white/10 rounded-lg p-4">
                                    <h3 className="text-lg font-bold mb-2">{t('API 调用定价', 'API Call Pricing')}</h3>
                                    <p className="text-xs text-gray-400 mb-3">
                                        {t('API 调用定价已迁移到「系统 API」配置中（config.api_pricing）。请前往“系统 API”标签，为每个 provider/model 设置 unit_type、cost、cost_input、cost_output。', 'API call pricing is now configured in System API settings (config.api_pricing). Go to the System API tab and set unit_type, cost, cost_input, cost_output per provider/model.')}
                                    </p>
                                    <button
                                        onClick={() => setActiveTab('system_api')}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded"
                                    >
                                        {t('前往系统 API 配置', 'Go to System API Settings')}
                                    </button>
                                </div>

                                <div className="bg-black/30 border border-white/10 rounded-lg p-4">
                                    <h3 className="text-lg font-bold mb-2">{t('默认 API 定价映射（兜底）', 'Default API Pricing Map (Fallback)')}</h3>
                                    <p className="text-xs text-gray-400 mb-3">
                                        {t('当 System API 定价为空或 <= 0 时，将按 API 类型使用这里的默认价。', 'When System API pricing is empty or <= 0, billing falls back to this map by API category.')}
                                    </p>

                                    <div className="overflow-x-auto">
                                        <table className="w-full text-xs border-collapse">
                                            <thead>
                                                <tr className="border-b border-white/10 text-gray-400">
                                                    <th className="text-left p-2">{t('API 类型', 'API Category')}</th>
                                                    <th className="text-left p-2">unit_type</th>
                                                    <th className="text-left p-2">cost</th>
                                                    <th className="text-left p-2">cost_input</th>
                                                    <th className="text-left p-2">cost_output</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {defaultApiPricingRows.map((row) => (
                                                    <tr key={row.id} className="border-b border-white/5">
                                                        <td className="p-2 text-gray-200 font-medium">{row.category}</td>
                                                        <td className="p-2">
                                                            <select
                                                                value={row.unit_type}
                                                                onChange={(e) => handleDefaultApiPricingRowChange(row.id, 'unit_type', e.target.value)}
                                                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                            >
                                                                <option value="per_call">per_call</option>
                                                                <option value="per_second">per_second</option>
                                                                <option value="per_minute">per_minute</option>
                                                                <option value="per_token">per_token</option>
                                                                <option value="per_1k_tokens">per_1k_tokens</option>
                                                                <option value="per_million_tokens">per_million_tokens</option>
                                                            </select>
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                value={row.cost}
                                                                onChange={(e) => handleDefaultApiPricingRowChange(row.id, 'cost', e.target.value)}
                                                                inputMode="numeric"
                                                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                value={row.cost_input}
                                                                onChange={(e) => handleDefaultApiPricingRowChange(row.id, 'cost_input', e.target.value)}
                                                                inputMode="numeric"
                                                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                value={row.cost_output}
                                                                onChange={(e) => handleDefaultApiPricingRowChange(row.id, 'cost_output', e.target.value)}
                                                                inputMode="numeric"
                                                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                            />
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>

                                    <div className="mt-3 flex items-center gap-2">
                                        <button
                                            onClick={handleSaveDefaultApiPricing}
                                            disabled={isDefaultApiPricingSaving}
                                            className="bg-primary hover:bg-primary/90 text-white px-3 py-1 rounded disabled:opacity-50"
                                        >
                                            {isDefaultApiPricingSaving ? t('保存中...', 'Saving...') : t('保存默认映射', 'Save Default Map')}
                                        </button>
                                        <button
                                            onClick={handleRestoreRecommendedDefaultApiPricingRows}
                                            className="bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded"
                                        >
                                            {t('恢复推荐默认方案', 'Restore Recommended Defaults')}
                                        </button>
                                        <button
                                            onClick={handleResetDefaultApiPricingRows}
                                            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded"
                                        >
                                            {t('重置草稿', 'Reset Draft')}
                                        </button>
                                    </div>
                                </div>

                                <div className="bg-black/30 border border-white/10 rounded-lg p-4">
                                    <h3 className="text-lg font-bold mb-2">{t('Agent 工具权限策略（按角色）', 'Agent Tool Permission Policy (By Role)')}</h3>
                                    <p className="text-xs text-gray-400 mb-3">
                                        {t('控制 user / authorized / superuser 可调用的 Agent 工具。格式：{ default_allow, roles.{role}.{allow|deny} }。支持 * 通配。', 'Control which Agent tools user / authorized / superuser can call. Format: { default_allow, roles.{role}.{allow|deny} }. Supports * wildcard.')}
                                    </p>

                                    <div className="mb-3 border border-white/10 rounded p-3 bg-black/20">
                                        <label className="flex items-center gap-2 text-xs text-gray-300 mb-3">
                                            <input
                                                type="checkbox"
                                                checked={!!normalizeAgentToolPolicy(agentToolPolicy).default_allow}
                                                onChange={(e) => handleToggleAgentPolicyDefaultAllow(e.target.checked)}
                                            />
                                            {t('default_allow（未显式 allow/deny 的工具默认允许）', 'default_allow (tools without explicit allow/deny are allowed by default)')}
                                        </label>

                                        <div className="overflow-x-auto">
                                            <table className="w-full text-xs border-collapse">
                                                <thead>
                                                    <tr className="border-b border-white/10 text-gray-400">
                                                        <th className="text-left p-2">{t('工具', 'Tool')}</th>
                                                        {AGENT_POLICY_ROLE_ORDER.map((role) => (
                                                            <th key={role} className="text-center p-2 uppercase">{role}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {AGENT_POLICY_TOOL_OPTIONS.map((tool) => (
                                                        <tr key={tool} className="border-b border-white/5">
                                                            <td className="p-2 font-mono text-gray-200">{tool}</td>
                                                            {AGENT_POLICY_ROLE_ORDER.map((role) => {
                                                                const checked = isAgentToolAllowedForRole(agentToolPolicy, role, tool);
                                                                return (
                                                                    <td key={`${role}-${tool}`} className="p-2 text-center">
                                                                        <input
                                                                            type="checkbox"
                                                                            checked={checked}
                                                                            onChange={(e) => handleToggleAgentPolicyTool(role, tool, e.target.checked)}
                                                                        />
                                                                    </td>
                                                                );
                                                            })}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>

                                    <textarea
                                        value={agentToolPolicyDraft}
                                        onChange={(e) => setAgentToolPolicyDraft(e.target.value)}
                                        className="w-full min-h-[240px] bg-gray-900 border border-gray-700 rounded p-3 font-mono text-xs text-gray-200"
                                        spellCheck={false}
                                    />
                                    <div className="mt-3 flex items-center gap-2">
                                        <button
                                            onClick={handleSaveAgentToolPolicy}
                                            disabled={isAgentToolPolicySaving}
                                            className="bg-primary hover:bg-primary/90 text-white px-3 py-1 rounded disabled:opacity-50"
                                        >
                                            {isAgentToolPolicySaving ? t('保存中...', 'Saving...') : t('保存 Agent 策略', 'Save Agent Policy')}
                                        </button>
                                        <button
                                            onClick={handleRestoreRecommendedAgentPolicy}
                                            className="bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded"
                                        >
                                            {t('恢复推荐策略', 'Restore Recommended Policy')}
                                        </button>
                                        <button
                                            onClick={() => setAgentToolPolicyDraft(JSON.stringify(agentToolPolicy || {}, null, 2))}
                                            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded"
                                        >
                                            {t('重置草稿', 'Reset Draft')}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TRANSACTIONS TAB */}
                    {activeTab === 'transactions' && (
                        <div>
                             <div className="flex justify-between items-center mb-4">
                                <h3 className="text-lg font-bold">{t('最近交易（最近 50 条）', 'Recent Transactions (Last 50)')}</h3>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-gray-400">{t('按用户筛选：', 'Filter by User:')}</span>
                                    <select 
                                        className="bg-gray-800 border border-gray-700 text-sm rounded p-2 text-gray-300 focus:outline-none focus:border-primary min-w-[200px]"
                                        value={transactionFilterUser}
                                        onChange={(e) => setTransactionFilterUser(e.target.value)}
                                    >
                                        <option value="">{t('全部用户', 'All Users')}</option>
                                        {users.map(u => (
                                            <option key={u.id} value={u.id}>
                                                {u.username} (ID: {u.id}) - {u.credits} {t('积分', 'credits')}
                                            </option>
                                        ))}
                                    </select>
                                    <button 
                                        onClick={fetchTransactionsOnly}
                                        className="p-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300"
                                        title={t('刷新', 'Refresh')}
                                    >
                                        <RefreshCw size={16} />
                                    </button>
                                </div>
                             </div>
                             <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse text-sm">
                                    <thead>
                                        <tr className="border-b border-gray-800 text-gray-400">
                                            <th className="p-3">{t('时间', 'Time')}</th>
                                            <th className="p-3">{t('用户 ID', 'User ID')}</th>
                                            <th className="p-3">{t('类型', 'Type')}</th>
                                            <th className="p-3">{t('详情', 'Details')}</th>
                                            <th className="p-3 text-right">{t('金额', 'Amount')}</th>
                                            <th className="p-3 text-right">{t('余额', 'Balance')}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {transactions.map(t => (
                                            <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                                <td className="p-3 text-gray-400">
                                                    {new Date(t.created_at.endsWith('Z') ? t.created_at : t.created_at + 'Z').toLocaleString()}
                                                </td>
                                                <td className="p-3">{t.user_id}</td>
                                                <td className="p-3"><span className="bg-gray-800 px-2 py-0.5 rounded text-xs uppercase text-gray-300">{t.task_type}</span></td>
                                                <td className="p-3 text-xs text-gray-500">
                                                    <div className="max-h-[150px] overflow-y-auto whitespace-pre-wrap break-all w-[350px] bg-gray-900/50 p-1 rounded border border-gray-800 font-mono">
                                                        {JSON.stringify(t.details, null, 2)}
                                                    </div>
                                                </td>
                                                <td className={`p-3 text-right font-mono ${t.amount < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                                    {t.amount > 0 ? '+' : ''}{t.amount}
                                                </td>
                                                <td className="p-3 text-right font-mono text-gray-400">{t.balance_after}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* SYSTEM API TAB */}
                    {activeTab === 'system_api' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between gap-2">
                                <h3 className="text-lg font-bold">{t('系统 API 设置（超级管理员 CRUD）', 'System API Settings (Superuser CRUD)')}</h3>
                                <div className="flex items-center gap-2">
                                    <input
                                        ref={systemApiImportInputRef}
                                        type="file"
                                        accept="application/json,.json"
                                        className="hidden"
                                        onChange={handleImportSystemApiSettingsFile}
                                    />
                                    <input
                                        ref={systemProviderBundleImportInputRef}
                                        type="file"
                                        accept="application/json,.json"
                                        className="hidden"
                                        onChange={handleImportSystemProviderBundleFile}
                                    />
                                    <button
                                        onClick={handleOpenImportSystemApiSettings}
                                        disabled={isSystemApiImporting || isSystemApiLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <Upload size={16} /> {isSystemApiImporting ? t('导入中...', 'Importing...') : t('导入', 'Import')}
                                    </button>
                                    <button
                                        onClick={handleExportSystemApiSettings}
                                        disabled={isSystemApiExporting || isSystemApiLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <Download size={16} /> {isSystemApiExporting ? t('导出中...', 'Exporting...') : t('导出', 'Export')}
                                    </button>
                                    <button
                                        onClick={async () => {
                                            if (!await confirmUiMessage(t('将当前 System API 配置导出到服务器种子文件\uff08下次部署时自动同步\uff09\uff0c确认\uff1f', 'Export current System API config to server seed file (auto-sync on next deploy). Confirm?'))) return;
                                            try {
                                                const res = await exportSystemSettingsToSeed();
                                                alert(t(`已导出 ${res.count} 条配置到种子文件`, `Exported ${res.count} settings to seed file`));
                                            } catch (e) {
                                                alert(e?.response?.data?.detail || e.message || 'Failed to export seed');
                                            }
                                        }}
                                        disabled={isSystemApiLoading}
                                        className="bg-sky-700 hover:bg-sky-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                        title={t('导出到服务器种子文件\uff0c部署时自动同步', 'Export to server seed file for auto-sync on deploy')}
                                    >
                                        <Download size={16} /> {t('导出 Seed', 'Export Seed')}
                                    </button>
                                    <button
                                        onClick={handleOpenImportSystemProviderBundle}
                                        disabled={isSystemProviderBundleImporting || isSystemApiLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                        title={t('按供应商+密钥池+模型导入', 'Import by provider + key pool + models')}
                                    >
                                        <Upload size={16} /> {isSystemProviderBundleImporting ? t('供应商导入中...', 'Provider Importing...') : t('导入供应商', 'Import Providers')}
                                    </button>
                                    <button
                                        onClick={handleExportSystemProviderBundle}
                                        disabled={isSystemProviderBundleExporting || isSystemApiLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                        title={t('按供应商+密钥池+模型导出', 'Export by provider + key pool + models')}
                                    >
                                        <Download size={16} /> {isSystemProviderBundleExporting ? t('供应商导出中...', 'Provider Exporting...') : t('导出供应商', 'Export Providers')}
                                    </button>
                                    <button
                                        onClick={fetchSystemApiManageRows}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2"
                                    >
                                        <RefreshCw size={16} /> {t('刷新', 'Refresh')}
                                    </button>
                                </div>
                            </div>

                            {isSystemApiLoading ? (
                                <div className="text-sm text-gray-400">{t('加载中...', 'Loading...')}</div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="border border-emerald-500/30 rounded-lg p-4 bg-emerald-500/5 space-y-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <h4 className="text-sm font-bold text-emerald-200">{t('供应商统一密钥池（独立配置区）', 'Provider Unified Key Pool (Standalone)')}</h4>
                                            <span className="text-[11px] text-emerald-300">{t('模型配置不再编辑密钥', 'Model editor no longer edits keys')}</span>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('供应商', 'Provider')}</label>
                                                <select
                                                    value={systemApiKeyProvider}
                                                    onChange={(e) => setSystemApiKeyProvider(e.target.value)}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="">{t('请选择供应商', 'Select Provider')}</option>
                                                    {allSystemApiProviders.map((provider) => (
                                                        <option key={provider} value={provider}>{provider}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('密钥调度策略', 'Key Dispatch Strategy')}</label>
                                                <select
                                                    value={providerKeyStrategy}
                                                    onChange={(e) => setProviderKeyStrategy(e.target.value)}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="random">{t('随机', 'Random')}</option>
                                                    <option value="round_robin">{t('轮询', 'Round Robin')}</option>
                                                    <option value="weighted">{t('权重随机', 'Weighted Random')}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-xs uppercase text-gray-400 mb-1">{t('密钥池（多 key，按行或逗号分隔）', 'Key Pool (multi-key, newline/comma separated)')}</label>
                                            <textarea
                                                value={providerKeysText}
                                                onChange={(e) => setProviderKeysText(e.target.value)}
                                                rows={4}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                placeholder="sk-key-1\nsk-key-2\nsk-key-3"
                                            />
                                        </div>

                                        {providerKeyStrategy === 'weighted' && (
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('权重（与 key 顺序对应）', 'Weights (same order as keys)')}</label>
                                                <textarea
                                                    value={providerKeyWeightsText}
                                                    onChange={(e) => setProviderKeyWeightsText(e.target.value)}
                                                    rows={3}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                    placeholder="1\n3\n1"
                                                />
                                            </div>
                                        )}

                                        <div className="text-[11px] text-gray-400">
                                            {t('对同一 provider 的所有模型统一生效；模型配置仅引用所属供应商密钥。', 'Applies to all models under the same provider; model settings only read provider keys.')}
                                        </div>
                                        <div className="text-[11px] text-gray-500">
                                            {t('当前服务端记录', 'Server snapshot')}: {providerKeysMeta.key_count || 0} {t('个密钥', 'keys')} {providerKeysMeta.keys_masked?.length ? `(${providerKeysMeta.keys_masked.slice(0, 3).join(', ')}${providerKeysMeta.keys_masked.length > 3 ? ', ...' : ''})` : ''}
                                        </div>
                                        <div>
                                            <button
                                                onClick={handleSaveProviderKeys}
                                                disabled={isProviderKeysSaving || !systemApiKeyProvider}
                                                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold rounded text-xs"
                                            >
                                                {isProviderKeysSaving ? t('保存中...', 'Saving...') : t('保存供应商密钥池', 'Save Provider Key Pool')}
                                            </button>
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-4">
                                    <div className="border border-white/10 rounded-lg p-4 bg-black/20 space-y-3">
                                        <div className="text-[11px] text-gray-300 bg-white/5 border border-white/10 rounded p-2 leading-relaxed">
                                            {t('智能路由规则：多参考图（>4）会优先尝试“多图默认 API”；主通道达到重试上限后，按同类别优先级（数字越小越优先）依次回退。', 'Smart routing rule: multi-reference image jobs (>4) first try the “multi-ref default API”; after retry limit on the main path, fallback follows same-category priority (lower number first).')}
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                            <div>
                                                <label className="text-xs uppercase text-gray-400">{t('模型类型筛选', 'Model Type Filter')}</label>
                                                <select
                                                    value={systemApiFilterCategory}
                                                    onChange={(e) => {
                                                        setSystemApiFilterCategory(e.target.value);
                                                        setSystemApiFilterProvider('all');
                                                    }}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="all">{t('全部类型', 'All Types')}</option>
                                                    {systemApiCategoryOptions.map((category) => (
                                                        <option key={category} value={category}>{category}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="text-xs uppercase text-gray-400">{t('供应商筛选', 'Provider Filter')}</label>
                                                <select
                                                    value={systemApiFilterProvider}
                                                    onChange={(e) => setSystemApiFilterProvider(e.target.value)}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="all">{t('全部供应商', 'All Providers')}</option>
                                                    {systemApiProviderOptions.map((provider) => (
                                                        <option key={provider} value={provider}>{provider}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="flex items-end gap-2">
                                                <button
                                                    onClick={() => setSystemApiHideDeprecated(h => !h)}
                                                    className={`px-3 py-2 rounded text-sm border whitespace-nowrap ${systemApiHideDeprecated ? 'bg-amber-500/20 text-amber-200 border-amber-500/40 hover:bg-amber-500/30' : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10'}`}
                                                >
                                                    {systemApiHideDeprecated ? t('已隐藏弃用', 'Deprecated Hidden') : t('显示弃用', 'Show Deprecated')}
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setSystemApiFilterCategory('all');
                                                        setSystemApiFilterProvider('all');
                                                        setSystemApiHideDeprecated(false);
                                                        setSystemApiSortMode('default');
                                                    }}
                                                    className="px-3 py-2 rounded text-sm bg-gray-700 hover:bg-gray-600 text-white whitespace-nowrap"
                                                >
                                                    {t('重置筛选', 'Reset Filters')}
                                                </button>
                                            </div>
                                        </div>

                                        <div className="flex items-center justify-between gap-2 text-xs">
                                            <span className="text-gray-400">{t('列表排序', 'List Order')}</span>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => handleBatchToggleProviderDeprecated(true)}
                                                    className="px-2.5 py-1 rounded border border-red-500/40 text-red-300 bg-red-500/10 hover:bg-red-500/20"
                                                    title={t('按当前供应商筛选批量弃用（可叠加类别筛选）', 'Batch deprecate current provider filter (category filter optional)')}
                                                >
                                                    {t('批量弃用', 'Batch Deprecate')}
                                                </button>
                                                <button
                                                    onClick={() => handleBatchToggleProviderDeprecated(false)}
                                                    className="px-2.5 py-1 rounded border border-emerald-500/40 text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20"
                                                    title={t('按当前供应商筛选批量启用（可叠加类别筛选）', 'Batch enable current provider filter (category filter optional)')}
                                                >
                                                    {t('批量启用', 'Batch Enable')}
                                                </button>
                                                <button
                                                    onClick={() => setSystemApiSortMode((prev) => (prev === 'priority' ? 'default' : 'priority'))}
                                                    className={`px-2.5 py-1 rounded border transition-colors ${systemApiSortMode === 'priority' ? 'bg-primary/20 text-primary border-primary/40' : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10'}`}
                                                    title={t('仅改变当前列表展示顺序，不修改数据库数据。', 'Only changes current list view order, does not modify database data.')}
                                                >
                                                    {systemApiSortMode === 'priority' ? t('当前：按优先级', 'Current: By Priority') : t('当前：默认顺序', 'Current: Default Order')}
                                                </button>
                                            </div>
                                        </div>

                                        <label className="text-xs uppercase text-gray-400">{t('选择已有设置', 'Select Existing Setting')}</label>
                                        <select
                                            value={selectedSystemApiId}
                                            onChange={(e) => setSelectedSystemApiId(e.target.value)}
                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                        >
                                            <option value="">{t('请选择...', 'Select...')}</option>
                                            {visibleSystemApiRows.map((row) => (
                                                <option key={row.id} value={row.id}>
                                                    [{row.category}] {row.provider} / {row.model || '-'} (ID:{row.id})
                                                </option>
                                            ))}
                                        </select>

                                        <div className="overflow-auto max-h-[520px] border border-white/10 rounded">
                                            <table className="w-full text-xs min-w-[1000px]">
                                                <thead className="bg-white/5 text-gray-400 sticky top-0">
                                                    <tr>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('编号', 'ID')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('类别', 'Category')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('提供方', 'Provider')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('模型', 'Model')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('名称', 'Name')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('Base URL', 'Base URL')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('模态', 'Modality')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('弃用', 'Deprecated')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('智能策略', 'Smart Strategy')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('启用', 'Active')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('操作', 'Actions')}</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {visibleSystemApiRows.map((row) => (
                                                        <tr
                                                            key={row.id}
                                                            onClick={() => setSelectedSystemApiId(String(row.id))}
                                                            className={`border-t border-white/10 cursor-pointer ${String(selectedSystemApiId) === String(row.id) ? 'bg-primary/10' : 'hover:bg-white/5'}`}
                                                        >
                                                            <td className="p-2">{row.id}</td>
                                                            <td className="p-2">{row.category}</td>
                                                            <td className="p-2">{row.provider}</td>
                                                            <td className="p-2 max-w-[220px] truncate" title={row.model || '-'}>{row.model || '-'}</td>
                                                            <td className="p-2 max-w-[160px] truncate" title={row.name || '-'}>{row.name || '-'}</td>
                                                            <td className="p-2 max-w-[200px] truncate" title={row.base_url || '-'}>{row.base_url || '-'}</td>
                                                            <td className="p-2 max-w-[160px] truncate" title={row.modality || '-'}>{row.modality || '-'}</td>
                                                            <td className="p-2">
                                                                {isSystemApiDeprecated(row) ? (
                                                                    <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30">{t('已弃用', 'Deprecated')}</span>
                                                                ) : (
                                                                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">{t('正常', 'Active')}</span>
                                                                )}
                                                            </td>
                                                            <td className="p-2">
                                                                <div className="flex flex-wrap gap-1">
                                                                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-200 border border-blue-500/30">
                                                                        {t('优先级', 'Priority')}: {getSmartPriority(row)}
                                                                    </span>
                                                                    <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-200 border border-purple-500/30">
                                                                        {t('重试', 'Retry')}: {getSmartRetryLimit(row)}
                                                                    </span>
                                                                    <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200 border border-amber-500/30">
                                                                        {t('API 定价', 'API Pricing')}: {formatApiPricingSummary(row)}
                                                                    </span>
                                                                    {isSmartMultiRefDefault(row) && (
                                                                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-500/30">
                                                                            {t('多图默认', 'Multi-ref Default')}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </td>
                                                            <td className="p-2">{row.is_active ? t('是', 'Yes') : t('否', 'No')}</td>
                                                            <td className="p-2">
                                                                <button
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        handleToggleSingleSystemApiDeprecated(row);
                                                                    }}
                                                                    className={`px-2 py-0.5 rounded border text-[11px] ${isSystemApiDeprecated(row) ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20' : 'border-red-500/40 text-red-300 bg-red-500/10 hover:bg-red-500/20'}`}
                                                                >
                                                                    {isSystemApiDeprecated(row) ? t('启用', 'Enable') : t('弃用', 'Deprecate')}
                                                                </button>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                    {visibleSystemApiRows.length === 0 && (
                                                        <tr className="border-t border-white/10">
                                                            <td className="p-3 text-gray-400" colSpan={11}>
                                                                {t('无匹配结果，请调整筛选条件。', 'No matching settings. Adjust your filters.')}
                                                            </td>
                                                        </tr>
                                                    )}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>

                                    <div className="border border-white/10 rounded-lg p-4 bg-black/20 space-y-3">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('名称', 'Name')}</label>
                                                <input
                                                    value={systemApiForm.name}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, name: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('类别', 'Category')}</label>
                                                <select
                                                    value={systemApiForm.category}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, category: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="LLM">{t('大语言模型', 'LLM')}</option>
                                                    <option value="Image">{t('图片', 'Image')}</option>
                                                    <option value="Video">{t('视频', 'Video')}</option>
                                                    <option value="Vision">{t('视觉', 'Vision')}</option>
                                                    <option value="Tools">{t('工具', 'Tools')}</option>
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('提供方 *', 'Provider *')}</label>
                                                <input
                                                    value={systemApiForm.provider}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, provider: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('模型', 'Model')}</label>
                                                <input
                                                    value={systemApiForm.model}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, model: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('端点', 'Endpoint')}</label>
                                                <input
                                                    value={systemApiForm.base_url}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, base_url: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('回调 WebHook', 'WebHook')}</label>
                                                <input
                                                    value={systemApiForm.webHook}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, webHook: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('API 计费单位', 'API Billing Unit')}</label>
                                                <select
                                                    value={systemApiForm.api_unit_type}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, api_unit_type: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="per_call">per_call</option>
                                                    <option value="per_second">per_second</option>
                                                    <option value="per_minute">per_minute</option>
                                                    <option value="per_token">per_token</option>
                                                    <option value="per_1k_tokens">per_1k_tokens</option>
                                                    <option value="per_million_tokens">per_million_tokens</option>
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('API 成本（基础）', 'API Cost (Base)')}</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={systemApiForm.api_cost}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, api_cost: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('API 成本（输入）', 'API Cost (Input)')}</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={systemApiForm.api_cost_input}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, api_cost_input: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('API 成本（输出）', 'API Cost (Output)')}</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={systemApiForm.api_cost_output}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, api_cost_output: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('智能路由优先级（越小越优先）', 'Smart Priority (lower first)')}</label>
                                                <input
                                                    type="number"
                                                    value={systemApiForm.smart_priority}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, smart_priority: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('重试上限（触发回退前）', 'Retry Limit (before fallback)')}</label>
                                                <input
                                                    type="number"
                                                    min="1"
                                                    value={systemApiForm.smart_retry_limit}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, smart_retry_limit: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <label className="md:col-span-2 flex items-center gap-2 text-xs text-gray-300 bg-white/5 border border-white/10 rounded p-2">
                                                <input
                                                    type="checkbox"
                                                    checked={!!systemApiForm.smart_multi_ref_default}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, smart_multi_ref_default: e.target.checked }))}
                                                />
                                                {t('设为“多参考图（>4）”临时默认 API', 'Use as temporary default API for multi-ref image (>4)')}
                                            </label>
                                        </div>

                                        <label className="flex items-center gap-2 text-xs text-gray-400">
                                            <input
                                                type="checkbox"
                                                checked={!!systemApiForm.is_active}
                                                onChange={(e) => setSystemApiForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                                            />
                                            {t('将该项设为此类别的激活配置', 'Set active for this category')}
                                        </label>

                                        <div className="flex flex-wrap gap-2 pt-2 border-t border-white/10">
                                            <button
                                                onClick={handleCreateSystemApiSetting}
                                                className="px-3 py-2 bg-primary hover:bg-primary/90 text-black font-bold rounded"
                                            >
                                                {t('创建', 'Create')}
                                            </button>
                                            <button
                                                onClick={handleUpdateSystemApiSetting}
                                                disabled={!selectedSystemApiId}
                                                className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold rounded"
                                            >
                                                {t('更新', 'Update')}
                                            </button>
                                            <button
                                                onClick={handleDeleteSystemApiSetting}
                                                disabled={!selectedSystemApiId}
                                                className="px-3 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-bold rounded"
                                            >
                                                {t('删除', 'Delete')}
                                            </button>
                                        </div>
                                    </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* LLM LOGS TAB */}
                    {activeTab === 'llm_logs' && (
                        <div className="space-y-4">
                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                <h3 className="text-lg font-bold">{t('LLM 调用日志', 'LLM Call Logs')}</h3>
                                <div className="flex flex-wrap items-center gap-2">
                                    <select
                                        value={selectedLlmLogFile}
                                        onChange={(e) => {
                                            const fileName = e.target.value;
                                            setSelectedLlmLogFile(fileName);
                                            fetchLlmLogs(fileName);
                                        }}
                                        className="bg-black/40 border border-gray-700 rounded p-2 text-sm min-w-[220px]"
                                    >
                                        {llmLogFiles.map((f) => (
                                            <option key={f.name} value={f.name}>
                                                {f.name} ({formatBytes(f.size_bytes)})
                                            </option>
                                        ))}
                                    </select>
                                    <input
                                        type="number"
                                        min={1}
                                        max={5000}
                                        value={llmLogTailLines}
                                        onChange={(e) => setLlmLogTailLines(e.target.value)}
                                        className="w-24 bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                        title={t('尾部行数', 'Tail lines')}
                                    />
                                    <button
                                        onClick={() => fetchLlmLogs(selectedLlmLogFile)}
                                        disabled={isLlmLogsLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <RefreshCw size={16} className={isLlmLogsLoading ? 'animate-spin' : ''} /> Refresh
                                    </button>
                                </div>
                            </div>

                            {llmLogsError ? (
                                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">
                                    {llmLogsError}
                                </div>
                            ) : null}

                            <div className="text-xs text-gray-500">
                                Showing last {Math.max(1, Number(llmLogTailLines) || 300)} lines from {selectedLlmLogFile}
                            </div>

                            <pre className="w-full min-h-[420px] max-h-[620px] overflow-auto bg-black/40 border border-gray-700 rounded p-3 text-xs text-gray-100 whitespace-pre-wrap break-all font-mono">
                                {isLlmLogsLoading ? 'Loading LLM logs...' : (llmLogContent || 'No content')}
                            </pre>
                        </div>
                    )}

                    {activeTab === 'storage_usage' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-lg font-bold">{t('用户磁盘使用统计', 'Per-User Storage Usage')}</h3>
                                <button
                                    onClick={fetchStorageUsage}
                                    disabled={isStorageUsageLoading}
                                    className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                >
                                    <RefreshCw size={16} className={isStorageUsageLoading ? 'animate-spin' : ''} /> {t('刷新', 'Refresh')}
                                </button>
                            </div>

                            {storageUsageError ? (
                                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">{storageUsageError}</div>
                            ) : null}

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                                    <div className="text-xs text-gray-400">{t('总占用', 'Total Size')}</div>
                                    <div className="text-lg font-bold">{formatBytes(storageUsage?.total_bytes || 0)}</div>
                                </div>
                                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                                    <div className="text-xs text-gray-400">{t('总文件数', 'Total Files')}</div>
                                    <div className="text-lg font-bold">{Number(storageUsage?.total_files || 0)}</div>
                                </div>
                                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                                    <div className="text-xs text-gray-400">{t('上传根目录', 'Upload Root')}</div>
                                    <div className="text-xs break-all text-gray-200">{storageUsage?.upload_root || '-'}</div>
                                </div>
                            </div>

                            <div className="overflow-x-auto border border-white/10 rounded-lg">
                                <table className="w-full text-sm">
                                    <thead className="bg-black/40">
                                        <tr className="text-left text-gray-300">
                                            <th className="px-3 py-2">{t('用户ID', 'User ID')}</th>
                                            <th className="px-3 py-2">{t('用户名', 'Username')}</th>
                                            <th className="px-3 py-2">Email</th>
                                            <th className="px-3 py-2 text-right">{t('文件数', 'Files')}</th>
                                            <th className="px-3 py-2 text-right">{t('占用', 'Size')}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(storageUsage?.users || []).map((row) => (
                                            <tr key={row.user_id} className="border-t border-white/5">
                                                <td className="px-3 py-2">{row.user_id}</td>
                                                <td className="px-3 py-2">{row.username}</td>
                                                <td className="px-3 py-2 text-gray-300">{row.email || '-'}</td>
                                                <td className="px-3 py-2 text-right">{Number(row.file_count || 0)}</td>
                                                <td className="px-3 py-2 text-right font-mono">{formatBytes(row.bytes || 0)}</td>
                                            </tr>
                                        ))}
                                        {!isStorageUsageLoading && (!storageUsage?.users || storageUsage.users.length === 0) && (
                                            <tr>
                                                <td colSpan={5} className="px-3 py-6 text-center text-gray-400">{t('暂无数据', 'No data')}</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {activeTab === 'prompt_skills' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-lg font-bold">{t('Prompt Skills 浏览器', 'Prompt Skills Browser')}</h3>
                                <button
                                    onClick={loadPromptSkills}
                                    disabled={isPromptSkillsLoading}
                                    className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                >
                                    <RefreshCw size={16} className={isPromptSkillsLoading ? 'animate-spin' : ''} /> {t('刷新', 'Refresh')}
                                </button>
                            </div>

                            <p className="text-xs text-muted-foreground">
                                {t('用于查看按 skills 组织的提示词（Claude skills 风格），方便排查与运营配置。', 'Browse skills-organized prompts (Claude skills style) for operations and debugging.')}
                            </p>

                            {isPromptSkillsLoading ? (
                                <div className="text-sm text-muted-foreground">{t('加载 Prompt Skills 中...', 'Loading prompt skills...')}</div>
                            ) : promptSkills.length === 0 ? (
                                <div className="text-sm text-muted-foreground">{t('暂无 Prompt Skills。', 'No prompt skills found.')}</div>
                            ) : (
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                                    <div className="lg:col-span-1 space-y-2">
                                        {promptSkills.map((item) => {
                                            const id = String(item?.id || '').trim();
                                            if (!id) return null;
                                            return (
                                                <button
                                                    key={id}
                                                    onClick={() => handleSelectPromptSkill(id)}
                                                    className={`w-full text-left px-3 py-2 rounded border transition-colors ${selectedPromptSkillId === id ? 'bg-primary/20 text-primary border-primary/40' : 'bg-white/5 text-muted-foreground border-white/10 hover:bg-white/10 hover:text-white'}`}
                                                >
                                                    <div className="text-sm font-medium">{item?.title || id}</div>
                                                    <div className="text-[11px] opacity-75 font-mono">{id}</div>
                                                </button>
                                            );
                                        })}
                                    </div>

                                    <div className="lg:col-span-2 border border-white/10 rounded-lg bg-black/20 p-3">
                                        <div className="text-xs text-muted-foreground mb-2">
                                            {t('system_prompt.txt 预览', 'system_prompt.txt preview')}
                                        </div>
                                        {isPromptSkillTextLoading ? (
                                            <div className="text-sm text-muted-foreground">{t('加载提示词中...', 'Loading prompt...')}</div>
                                        ) : selectedPromptSkillText ? (
                                            <pre className="whitespace-pre-wrap break-words text-xs text-gray-200 max-h-[420px] overflow-auto">{selectedPromptSkillText}</pre>
                                        ) : (
                                            <div className="text-sm text-muted-foreground">{t('该 skill 暂无 system_prompt.txt。', 'No system_prompt.txt for this skill.')}</div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                </div>
            </main>

            {/* Credit Modal */}
            {creditEditUser && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
                    <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-sm">
                        <h3 className="text-xl font-bold mb-4">{t('编辑用户积分', 'Edit Credits for')} {creditEditUser.username}</h3>
                        <p className="text-gray-400 text-sm mb-4">{t('设置该用户的绝对积分余额。', 'Set the absolute credit balance for this user.')}</p>
                        <input 
                            type="number" 
                            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-2xl font-mono text-center text-green-400 mb-6"
                            value={creditAmount}
                            onChange={e => setCreditAmount(e.target.value)}
                        />
                        <div className="flex justify-end gap-2">
                                <button onClick={() => setCreditEditUser(null)} className="px-4 py-2 hover:bg-gray-800 rounded">{t('取消', 'Cancel')}</button>
                                <button onClick={handleUpdateCredits} className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white font-bold rounded">{t('更新余额', 'Update Balance')}</button>
                        </div>
                    </div>
                </div>
            )}
            
        </div>
    );
};

export default UserAdmin;

