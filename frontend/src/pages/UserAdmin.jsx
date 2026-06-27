import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FunctionApiConfigTab from '../components/FunctionApiConfigTab';
import { api, getTransactions, updateUserCredits, getBillingOptions, getBillingFeaturePricing, updateBillingFeaturePricing, getBillingDefaultApiPricing, updateBillingDefaultApiPricing, getAgentToolPolicy, updateAgentToolPolicy, getBillingRuleResetConfigManage, updateBillingRuleResetConfigManage, getAssetImageRatioConfigManage, updateAssetImageRatioConfigManage, getSceneAnalysisConfigManage, updateSceneAnalysisConfigManage, getProjectCostEstimationConfigManage, updateProjectCostEstimationConfigManage, getSystemSettingsManage, getSystemApisMissingBillingRulesManage, createSystemSettingManage, updateSystemSettingManage, deleteSystemSettingManage, listTaskDefaultApisManage, createTaskDefaultApiManage, updateTaskDefaultApiManage, deleteTaskDefaultApiManage, listSystemApiBillingRulesManage, listSystemApiBillingRulesBatchManage, createSystemApiBillingRuleManage, updateSystemApiBillingRuleManage, deleteSystemApiBillingRuleManage, deleteSystemApiBillingRulesBatchManage, resetSystemApiBillingRuleChargeMultipliersManage, recomputeSystemApiPriceCacheManage, exportSystemSettingsManage, exportSystemSettingsToSeed, importSystemSettingsManage, exportSystemProviderBundleManage, importSystemProviderBundleManage, validateSystemProviderBundleManage, exportSystemConfigSyncBundleManage, importSystemConfigSyncBundleManage, batchToggleSystemProviderDeprecatedManage, toggleSystemSettingDeprecatedManage, toggleSystemSettingDeprecatedByKeyManage, getSystemProviderKeysManage, setSystemProviderKeysManage, listProviderKeyPools, createProviderKeyPool, updateProviderKeyPool, deleteProviderKeyPool, listOssProviderPools, createOssProviderPool, updateOssProviderPool, deleteOssProviderPool, listKieStandardValuesManage, listKieStandardMappingsManage, createKieStandardMappingManage, updateKieStandardMappingManage, deleteKieStandardMappingManage, inferKieStandardMappingBillingRelatedManage, exportKieDataDictionaryMappings, importKieDataDictionaryMappings, exportKieDataDictionaryValues, importKieDataDictionaryValues, exportKieDataDictionaryBundle, importKieDataDictionaryBundle, getAdminRuntimeLogFiles, getAdminRuntimeLogView, getLlmCallLogs, getAdminStorageUsage, getAdminExpiredFiles, remindAdminExpiredFiles, deleteAdminExpiredFiles, getAdminOrphanFiles, deleteAdminOrphanFiles, getAdminMaintenanceConfig, updateAdminMaintenanceConfig, fetchPromptSkills, fetchPrompt, savePrompt, getAdminUsersPage } from '../services/api';
import Footer from '../components/Footer';
import LlmLogViewer from '../components/LlmLogViewer';
import QueueAdmin from '../components/QueueAdmin';
import UserEditModal from '../components/UserEditModal';
import { Shield, User, Key, Check, X, Crown, Settings, DollarSign, Activity, List, Plus, Trash2, Edit2, RefreshCw, CreditCard, Upload, Download, Mail, ArrowLeft, HardDrive, Database } from 'lucide-react';
import { confirmUiMessage, promptUiMessage } from '../lib/uiMessage';

import { getUiLang, tUI } from '../lib/uiLang';

const Toggle = ({ active, onClick, color = "bg-green-500", label }) => (
    <button 
        onClick={onClick}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-primary ${active ? color : 'bg-gray-700'}`}
        title={label}
    >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${active ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
);

const RuleField = ({ label, children }) => (
    <label className="block space-y-1">
        <span className="text-[11px] uppercase tracking-wide text-gray-400">{label}</span>
        {children}
    </label>
);

const DEFAULT_PROJECT_COST_VISUAL_CONFIG = {
    version: 1,
    overview: {
        word_rate: 0.012,
    },
    suggested: {
        base_scene_point: 1.0,
        role_complexity: 1.0,
        env_complexity: 0.8,
        prop_complexity: 0.5,
        entity_tier_ratios: {
            tier1_max: 3,
            tier2_max: 6,
            tier3_max: 9,
            tier1_factor: 1.0,
            tier2_factor: 1.2,
            tier3_factor: 1.5,
            tier4_factor: 1.8,
        },
    },
    budget: {
        shot_unit_rate: 1.0,
        duration_weight: 1.0,
        asset_weight: 0.8,
    },
    project_multiplier: {
        default_factor: 1.0,
    },
};

const UserAdmin = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [billingOptions, setBillingOptions] = useState(null);
    const [featurePricingMap, setFeaturePricingMap] = useState({});
    const [featurePricingRows, setFeaturePricingRows] = useState([]);
    const [isFeaturePricingSaving, setIsFeaturePricingSaving] = useState(false);
    const [defaultApiPricingMap, setDefaultApiPricingMap] = useState({});
    const [recommendedDefaultApiPricingMap, setRecommendedDefaultApiPricingMap] = useState({});
    const [defaultApiPricingRows, setDefaultApiPricingRows] = useState([]);
    const [contentFallbackPricing, setContentFallbackPricing] = useState({
        enabled: false,
        strategy: 'manual',
        content_pricing: {
            text: { unit_type: 'per_call', cost: 0, cost_input: 0, cost_output: 0 },
            image: { unit_type: 'per_call', cost: 0, cost_input: 0, cost_output: 0 },
            video: { unit_type: 'per_second', cost: 0, cost_input: 0, cost_output: 0 },
        },
    });
    const [contentFallbackRows, setContentFallbackRows] = useState([]);
    const [isDefaultApiPricingSaving, setIsDefaultApiPricingSaving] = useState(false);
    const [agentToolPolicy, setAgentToolPolicy] = useState({ default_allow: true, roles: {} });
    const [agentToolPolicyDraft, setAgentToolPolicyDraft] = useState('{\n  "default_allow": true,\n  "roles": {}\n}');
    const [isAgentToolPolicySaving, setIsAgentToolPolicySaving] = useState(false);
    const [transactions, setTransactions] = useState([]);
    const [transactionFilterUser, setTransactionFilterUser] = useState(''); // User ID filter
    const [transactionFilterTaskType, setTransactionFilterTaskType] = useState('');
    const [transactionFilterProvider, setTransactionFilterProvider] = useState('');
    const [transactionFilterModel, setTransactionFilterModel] = useState('');
    const [transactionLimit, setTransactionLimit] = useState(100);
    const [isPricingBootstrapLoaded, setIsPricingBootstrapLoaded] = useState(false);
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
    const [isSystemApiEditing, setIsSystemApiEditing] = useState(false);
    const [systemApiEditToast, setSystemApiEditToast] = useState('');
    const [billingRuleRows, setBillingRuleRows] = useState([]);
    const [missingBillingRuleApiRows, setMissingBillingRuleApiRows] = useState([]);
    const [isMissingBillingRuleCheckLoading, setIsMissingBillingRuleCheckLoading] = useState(false);
    const [isBillingRuleLoading, setIsBillingRuleLoading] = useState(false);
    const [isBatchResetMultiplierLoading, setIsBatchResetMultiplierLoading] = useState(false);
    const [isPriceCacheRecomputeLoading, setIsPriceCacheRecomputeLoading] = useState(false);
    const [batchResetMinMultiplier, setBatchResetMinMultiplier] = useState('1.1');
    const [batchResetMaxMultiplier, setBatchResetMaxMultiplier] = useState('2.0');
    const [batchResetDefaultMultiplier, setBatchResetDefaultMultiplier] = useState('2.0');
    const [batchResetBinSizeCredits, setBatchResetBinSizeCredits] = useState('10');
    const [batchResetBinDropMultiplier, setBatchResetBinDropMultiplier] = useState('0.1');
    const [batchResetMaxIncreaseCredits, setBatchResetMaxIncreaseCredits] = useState('50');
    const [isBatchResetConfigSaving, setIsBatchResetConfigSaving] = useState(false);
    const [subjectAssetAspectRatio, setSubjectAssetAspectRatio] = useState('16:9');
    const [coverAssetAspectRatio, setCoverAssetAspectRatio] = useState('3:4');
    const [isAssetImageRatioConfigSaving, setIsAssetImageRatioConfigSaving] = useState(false);
    const [sceneAnalysisDefaultMode, setSceneAnalysisDefaultMode] = useState('classic');
    const [isSceneAnalysisConfigSaving, setIsSceneAnalysisConfigSaving] = useState(false);
    const [projectCostConfigData, setProjectCostConfigData] = useState(DEFAULT_PROJECT_COST_VISUAL_CONFIG);
    const [isProjectCostConfigSaving, setIsProjectCostConfigSaving] = useState(false);
    const [costFormKey, setCostFormKey] = useState(0);
    const [isBillingRuleEditing, setIsBillingRuleEditing] = useState(false);
    const [billingRuleEditToast, setBillingRuleEditToast] = useState('');
    const [selectedBillingRuleId, setSelectedBillingRuleId] = useState('');
    const [selectedBillingRuleIds, setSelectedBillingRuleIds] = useState([]);
    const [billingRuleFilterKeyword, setBillingRuleFilterKeyword] = useState('');
    const [billingRuleFilterStatus, setBillingRuleFilterStatus] = useState('all');
    const [billingRuleFilterTarget, setBillingRuleFilterTarget] = useState('all');
    const [billingRuleFilterUnitType, setBillingRuleFilterUnitType] = useState('all');
    const [billingRuleFilterApiCategory, setBillingRuleFilterApiCategory] = useState('all');
    const [billingRuleFilterApiProvider, setBillingRuleFilterApiProvider] = useState('all');
    const [billingRuleFilterApiBaseModel, setBillingRuleFilterApiBaseModel] = useState('all');
    const [billingRuleApiPickerCategory, setBillingRuleApiPickerCategory] = useState('all');
    const [billingRuleApiPickerProvider, setBillingRuleApiPickerProvider] = useState('all');
    const [billingRuleApiPickerBaseModel, setBillingRuleApiPickerBaseModel] = useState('all');
    const [kiePricingUrl, setKiePricingUrl] = useState('https://kie.ai/zh-CN/pricing');
    const [kiePricingProviderFilter, setKiePricingProviderFilter] = useState('kie');
    const [kiePricingManualText, setKiePricingManualText] = useState('');
    const [kiePricingManualTablesText, setKiePricingManualTablesText] = useState('[]');
    const [isKiePricingLoading, setIsKiePricingLoading] = useState(false);
    const [isKiePricingConfirmed, setIsKiePricingConfirmed] = useState(false);
    const [kiePricingResult, setKiePricingResult] = useState(null);

    const formatSyncProcessRecords = (records) => {
        if (!Array.isArray(records) || !records.length) return '';
        return records
            .map((record) => {
                const tableName = String(record?.table || '').trim() || 'unknown';
                const operation = String(record?.operation || '').trim() || 'unknown';
                const status = String(record?.status || '').trim() || 'info';
                const detail = String(record?.detail || '').trim();
                const extras = Object.entries(record || {})
                    .filter(([key, value]) => !['ts', 'direction', 'table', 'operation', 'status', 'detail'].includes(key) && value !== null && value !== undefined && value !== '')
                    .map(([key, value]) => `${key}=${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
                    .join(', ');
                return `- [${status}] ${tableName}.${operation}${detail ? `: ${detail}` : ''}${extras ? ` (${extras})` : ''}`;
            })
            .join('\n');
    };
    const [supplierFeatureProvider, setSupplierFeatureProvider] = useState('');
    const [supplierFeatureUrlsText, setSupplierFeatureUrlsText] = useState('');
    const [supplierFeatureKeywords, setSupplierFeatureKeywords] = useState('');
    const [supplierFeatureUserSupplement, setSupplierFeatureUserSupplement] = useState('');
    const [isSupplierFeatureAnalyzing, setIsSupplierFeatureAnalyzing] = useState(false);
    const [isSupplierFeatureApplying, setIsSupplierFeatureApplying] = useState(false);
    const [supplierFeatureResult, setSupplierFeatureResult] = useState(null);
    const [selectedSupplierFeatureModelKeys, setSelectedSupplierFeatureModelKeys] = useState([]);
    const [selectedSupplierTargetApiIds, setSelectedSupplierTargetApiIds] = useState([]);
    const [supplierFeatureFilterMode, setSupplierFeatureFilterMode] = useState('all');
    const [supplierOpsSubtab, setSupplierOpsSubtab] = useState('feature_analysis');
    const [selectedKieSuggestionIds, setSelectedKieSuggestionIds] = useState([]);
    const [isKieSuggestionEditOpen, setIsKieSuggestionEditOpen] = useState(false);
    const [editingKieSuggestionIndex, setEditingKieSuggestionIndex] = useState(-1);

    const [editingKieSuggestionMeta, setEditingKieSuggestionMeta] = useState({ system_api_id: '', model: '' });
    const [kieSuggestionEditForm, setKieSuggestionEditForm] = useState({
        target_system_api_id: '',
        billing_unit_type: 'per_call',
        billing_cost: '0',
        billing_cost_input: '0',
        billing_cost_output: '0',
        granular_rules: [],
    });
    const [billingRuleForm, setBillingRuleForm] = useState({
        name: 'Rule',
        description: '',
        is_active: true,
        priority: '0',
        applies_to_text: true,
        applies_to_image: false,
        applies_to_video: false,
        generation_mode: '',
        input_format: '',
        output_format: '',
        has_audio: 'any',
        input_tokens_min: '',
        input_tokens_max: '',
        output_tokens_min: '',
        output_tokens_max: '',
        total_tokens_min: '',
        total_tokens_max: '',
        image_count_min: '',
        image_count_max: '',
        width_min: '',
        width_max: '',
        height_min: '',
        height_max: '',
        pixels_min: '',
        pixels_max: '',
        duration_seconds_min: '',
        duration_seconds_max: '',
        fps_min: '',
        fps_max: '',
        billing_unit_type: 'per_call',
        billing_cost: '0',
        billing_cost_input: '0',
        billing_cost_output: '0',
        charge_multiplier: '2',
        extra_conditions_text: '{}',
    });
    const [isSystemApiImporting, setIsSystemApiImporting] = useState(false);
    const [isSystemApiExporting, setIsSystemApiExporting] = useState(false);
    const [isSystemProviderBundleImporting, setIsSystemProviderBundleImporting] = useState(false);
    const [isSystemProviderBundleExporting, setIsSystemProviderBundleExporting] = useState(false);
    const [isSystemConfigSyncExporting, setIsSystemConfigSyncExporting] = useState(false);
    const [isSystemConfigSyncImporting, setIsSystemConfigSyncImporting] = useState(false);
    const [selectedSystemApiId, setSelectedSystemApiId] = useState('');
    const [systemApiFilterCategory, setSystemApiFilterCategory] = useState('all');
    const [systemApiFilterProvider, setSystemApiFilterProvider] = useState('all');
    const [systemApiFilterRetryGroup, setSystemApiFilterRetryGroup] = useState('all');
    const [systemApiFilterRetryPriceGroup, setSystemApiFilterRetryPriceGroup] = useState('all');
    const [systemApiCapabilityFilter, setSystemApiCapabilityFilter] = useState('all');
    const [systemApiHideDeprecated, setSystemApiHideDeprecated] = useState(false);
    const [systemApiSortMode, setSystemApiSortMode] = useState('default');
    const [systemApiKeyProvider, setSystemApiKeyProvider] = useState('');
    const [providerKeysText, setProviderKeysText] = useState('');
    const [providerKeysMeta, setProviderKeysMeta] = useState({ key_count: 0, keys_masked: [] });
    const [providerKeyStrategy, setProviderKeyStrategy] = useState('random');
    const [providerKeyWeightsText, setProviderKeyWeightsText] = useState('');
    const [isProviderKeysSaving, setIsProviderKeysSaving] = useState(false);
    const [providerKeyPoolRows, setProviderKeyPoolRows] = useState([]);
    const [isProviderKeyPoolLoading, setIsProviderKeyPoolLoading] = useState(false);
    const [selectedKeyPoolId, setSelectedKeyPoolId] = useState('');
    const [keyPoolForm, setKeyPoolForm] = useState({ provider: '', provider_alias: '', api_keys: '', strategy: 'random', weights: '', intro_url: '' });        
    const [ossProviderPoolRows, setOssProviderPoolRows] = useState([]);        
    const [isOssProviderPoolLoading, setIsOssProviderPoolLoading] = useState(false);
    const [selectedOssProviderPoolId, setSelectedOssProviderPoolId] = useState('');
    const [ossProviderPoolForm, setOssProviderPoolForm] = useState({
        provider: 'qiniu',
        provider_alias: '',
        endpoint: '',
        region: '',
        bucket: '',
        public_base_url: '',
        root_prefix: 'aistory/upload',
        credentials_text: '[]',
        strategy: 'random',
        weights_text: '[]',
        default_storage_class: '',
        retention_days: '',
        force_path_style: false,
        is_active: true,
    });
    const [taskDefaultApiRows, setTaskDefaultApiRows] = useState([]);
    const [isTaskDefaultApiLoading, setIsTaskDefaultApiLoading] = useState(false);
    const [selectedTaskDefaultCategory, setSelectedTaskDefaultCategory] = useState('');

    const [taskDefaultForm, setTaskDefaultForm] = useState({ task_category: 'LLM', system_api_id: '' });
    const [kieStandardValueRows, setKieStandardValueRows] = useState([]);
    const [kieStandardMappingRows, setKieStandardMappingRows] = useState([]);
    const [isKieStandardLoading, setIsKieStandardLoading] = useState(false);
    const [isKieStandardSaving, setIsKieStandardSaving] = useState(false);
    const [isKieBillingInferLoading, setIsKieBillingInferLoading] = useState(false);
    const [isKieMappingExporting, setIsKieMappingExporting] = useState(false);
    const [isKieMappingImporting, setIsKieMappingImporting] = useState(false);
    const [isKieValueExporting, setIsKieValueExporting] = useState(false);
    const [isKieValueImporting, setIsKieValueImporting] = useState(false);
    const [isKieBundleExporting, setIsKieBundleExporting] = useState(false);
    const [isKieBundleImporting, setIsKieBundleImporting] = useState(false);
    const [selectedKieStandardMappingId, setSelectedKieStandardMappingId] = useState('');
    const [kieStandardSearchText, setKieStandardSearchText] = useState('');
    const [kieStandardDimensionFilter, setKieStandardDimensionFilter] = useState('all');
    const [kieStandardBillingOnly, setKieStandardBillingOnly] = useState(false);
    const [kieStandardMappingForm, setKieStandardMappingForm] = useState({
        provider: 'kie',
        model_key_inferred: '',
        model_title: '',
        model_url: '',
        source_field: '',
        source_enum_value: '',
        standard_dimension: '',
        standard_value: '',
        confidence: '',
        note: '',
        is_active: true,
        is_billing_related: false,
    });
    const [systemApiForm, setSystemApiForm] = useState({
        name: '',
        category: 'LLM',
        provider: '',
        api_key: '',
        base_url: '',
        model: '',
        base_model: '',
        retry_group: '',
        retry_price_group: '',
        explicit_selection: false,
        strict_provider: false,
        moderation_aes_key: '',
        config: '{}',
        is_active: false,
        deprecated: false,
        tags: '',
        generation_modes: '',
        input_formats: '',
        output_format: '',
        supported_resolutions: '',
        aspect_ratios: '',
        max_images_per_call: '',
        reference_image_limit: '',
        reference_video_limit: '',
        durations_seconds: '',
        max_duration: '',
        fps_options: '',
        has_audio: 'any',
        mode_values: '',
        capability_flags: '{}',
        text_capabilities: '{}',
        image_capabilities: '{}',
        video_capabilities: '{}',
        digital_human_capabilities: '{}',
        voice_capabilities: '{}',
        music_capabilities: '{}',
        pricing_unit: '',
        token_billing_supported: 'any',
        input_token_price: '',
        output_token_price: '',
        per_resolution_price_map: '{}',
        per_duration_price_map: '{}',
        has_tiered_pricing: 'any',
        free_quota: '',
        currency: '',
        billing_unit_type: 'per_call',
        billing_cost: '0',
        billing_cost_input: '0',
        billing_cost_output: '0',
    });
    const systemApiImportInputRef = React.useRef(null);
    const systemProviderBundleImportInputRef = React.useRef(null);
    const systemConfigSyncImportInputRef = React.useRef(null);
    const kieMappingImportInputRef = React.useRef(null);
    const kieValueImportInputRef = React.useRef(null);
    const kieBundleImportInputRef = React.useRef(null);
    const [runtimeLogFiles, setRuntimeLogFiles] = useState([]);
    const [selectedRuntimeLogFile, setSelectedRuntimeLogFile] = useState('app_info.log');
    const [runtimeLogTailLines, setRuntimeLogTailLines] = useState(300);
    const [runtimeLogFilters, setRuntimeLogFilters] = useState({
        user_name: '',
        action: '',
        start_time: '',
        end_time: ''
    });
    const [runtimeLogContent, setRuntimeLogContent] = useState('');
    const [llmLogs, setLlmLogs] = useState([]);
    const [isLlmLogsLoading, setIsLlmLogsLoading] = useState(false);
    const [llmLogsError, setLlmLogsError] = useState('');
    const [selectedLlmLog, setSelectedLlmLog] = useState(null);

    const fetchLlmLogs = async () => {
        setIsLlmLogsLoading(true);
        setLlmLogsError('');
        try {
            const logs = await getLlmCallLogs({ limit: 100 });
            setLlmLogs(logs || []);
        } catch (e) {
            setLlmLogsError(e.response?.data?.detail || e.message);
        } finally {
            setIsLlmLogsLoading(false);
        }
    };
    const [isRuntimeLogsLoading, setIsRuntimeLogsLoading] = useState(false);
    const [runtimeLogsError, setRuntimeLogsError] = useState('');
    const runtimeLogPreRef = React.useRef(null);
    const [storageUsage, setStorageUsage] = useState(null);
    const [isStorageUsageLoading, setIsStorageUsageLoading] = useState(false);
    const [storageUsageError, setStorageUsageError] = useState('');
    const [expiredFilesData, setExpiredFilesData] = useState(null);
    const [isExpiredFilesLoading, setIsExpiredFilesLoading] = useState(false);
    const [expiredFilesError, setExpiredFilesError] = useState('');
    const [orphanFilesData, setOrphanFilesData] = useState(null);
    const [isOrphanFilesLoading, setIsOrphanFilesLoading] = useState(false);
    const [orphanFilesError, setOrphanFilesError] = useState('');
    const [promptSkills, setPromptSkills] = useState([]);
    const [isPromptSkillsLoading, setIsPromptSkillsLoading] = useState(false);
    const [selectedPromptSkillId, setSelectedPromptSkillId] = useState('');
    const [selectedPromptSkillPromptRef, setSelectedPromptSkillPromptRef] = useState('');
    const [selectedPromptSkillText, setSelectedPromptSkillText] = useState('');
    const [isPromptSkillTextLoading, setIsPromptSkillTextLoading] = useState(false);
    const [isPromptSkillSaving, setIsPromptSkillSaving] = useState(false);
    const [promptSkillSaveMessage, setPromptSkillSaveMessage] = useState('');

    const SYSTEM_API_FILTER_HAS_VALUE = '__has_value__';
    const SYSTEM_API_FILTER_EMPTY_VALUE = '__empty__';

    const showSystemApiEditToast = (text) => {
        setSystemApiEditToast(String(text || '').trim());
        setTimeout(() => setSystemApiEditToast(''), 1800);
    };

    const showBillingRuleEditToast = (text) => {
        setBillingRuleEditToast(String(text || '').trim());
        setTimeout(() => setBillingRuleEditToast(''), 1800);
    };

    const supplierFeatureModelKey = (item = {}) => {
        const category = String(item?.category || '').trim().toLowerCase();
        const model = String(item?.model || '').trim().toLowerCase();
        return `${category}::${model}`;
    };

    const supplierTargetApiKey = (row = {}) => {
        const category = String(row?.category || '').trim().toLowerCase();
        const model = String(row?.model || '').trim().toLowerCase();
        return `${category}::${model}`;
    };

    const toggleSupplierTargetApiId = (id, checked) => {
        const normalized = Number(id || 0);
        if (!Number.isFinite(normalized) || normalized <= 0) return;
        setSelectedSupplierTargetApiIds((prev) => {
            const has = prev.includes(normalized);
            if (checked && !has) return [...prev, normalized];
            if (!checked && has) return prev.filter((item) => item !== normalized);
            return prev;
        });
    };

    const handleAnalyzeSupplierFeatures = async () => {
        const selectedTargetRows = systemApiRows.filter((row) => selectedSupplierTargetApiIds.includes(Number(row?.id || 0)));
        const inferredProvider = selectedTargetRows.length > 0 ? String(selectedTargetRows[0]?.provider || '').trim() : '';
        const provider = String(supplierFeatureProvider || inferredProvider || '').trim();
        const urls = String(supplierFeatureUrlsText || '')
            .split(/\r?\n/)
            .map((s) => String(s || '').trim())
            .filter(Boolean);
        const keywords = String(supplierFeatureKeywords || '')
            .split(/[\n,，]/)
            .map((s) => String(s || '').trim())
            .filter(Boolean);
        const userSupplement = String(supplierFeatureUserSupplement || '').trim();

        if (!provider) {
            alert(t('请填写供应商 provider 或先勾选系统 API', 'Please input provider or select system APIs first'));
            return;
        }
        // URL / selected APIs are optional now; backend supports auto-research fallback mode.

        try {
            setIsSupplierFeatureAnalyzing(true);
            const result = await ({
                provider,
                source_urls: urls,
                selected_system_api_ids: selectedSupplierTargetApiIds,
                include_provider_intro_url: true,
                search_keywords: keywords,
                user_supplement: userSupplement || null,
                save_to_db: false,
                create_missing_models: true,
                max_length: 40000,
                max_pages: 6,
            });
            const parsedResult = result || null;
            setSupplierFeatureResult(parsedResult);
            const modelKeys = Array.isArray(parsedResult?.models)
                ? parsedResult.models.map((item) => supplierFeatureModelKey(item)).filter(Boolean)
                : [];
            setSelectedSupplierFeatureModelKeys(modelKeys);
            alert(t('供应商特征分析完成，请勾选并保存到数据库', 'Supplier feature analysis completed. Select rows and save to DB.'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('供应商特征分析失败', 'Supplier feature analysis failed'));
        } finally {
            setIsSupplierFeatureAnalyzing(false);
        }
    };

    const handleToggleSupplierFeatureModelKey = (key) => {
        const normalized = String(key || '').trim();
        if (!normalized) return;
        setSelectedSupplierFeatureModelKeys((prev) => {
            if (prev.includes(normalized)) {
                return prev.filter((item) => item !== normalized);
            }
            return [...prev, normalized];
        });
    };

    const getSupplierCapabilitySections = (item = {}) => {
        const sections = [
            { key: 'text_capabilities', label: t('文本能力', 'Text') },
            { key: 'image_capabilities', label: t('图像能力', 'Image') },
            { key: 'video_capabilities', label: t('视频能力', 'Video') },
            { key: 'digital_human_capabilities', label: t('数字人能力', 'DigitalHuman') },
            { key: 'voice_capabilities', label: t('配音能力', 'Voice') },
            { key: 'music_capabilities', label: t('音乐能力', 'Music') },
        ];
        return sections.filter((section) => {
            const value = item?.[section.key];
            return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0;
        });
    };

    const toPrettyFeatureJson = (obj) => {
        try {
            return JSON.stringify(obj || {}, null, 2);
        } catch (_) {
            return String(obj || '');
        }
    };

    const hasFeatureObject = (item, key) => {
        const value = item?.[key];
        return !!(value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0);
    };

    const isMissingCoreSupplierFields = (item = {}) => {
        const hasMode = Array.isArray(item?.generation_modes) && item.generation_modes.length > 0;
        const hasAnyCoreCapability = [
            'text_capabilities',
            'image_capabilities',
            'video_capabilities',
            'digital_human_capabilities',
            'voice_capabilities',
            'music_capabilities',
        ].some((key) => hasFeatureObject(item, key));
        return !hasMode || !hasAnyCoreCapability;
    };

    const isMissingVoiceMusicFields = (item = {}) => {
        return !hasFeatureObject(item, 'voice_capabilities') || !hasFeatureObject(item, 'music_capabilities');
    };

    const isMissingBillingHints = (item = {}) => {
        const keys = [
            'text_capabilities',
            'image_capabilities',
            'video_capabilities',
            'digital_human_capabilities',
            'voice_capabilities',
            'music_capabilities',
        ];
        for (const key of keys) {
            const obj = item?.[key];
            if (!obj || typeof obj !== 'object' || Array.isArray(obj)) continue;
            if (
                obj.pricing_unit !== undefined
                || obj.token_billing_supported !== undefined
                || obj.input_token_price !== undefined
                || obj.output_token_price !== undefined
                || obj.per_resolution_price_map !== undefined
                || obj.per_duration_price_map !== undefined
                || obj.currency !== undefined
            ) {
                return false;
            }
        }
        return true;
    };

    const getFilteredSupplierModels = () => {
        const models = Array.isArray(supplierFeatureResult?.models) ? supplierFeatureResult.models : [];
        if (supplierFeatureFilterMode === 'all') return models;
        if (supplierFeatureFilterMode === 'missing_voice_music') {
            return models.filter((item) => isMissingVoiceMusicFields(item));
        }
        if (supplierFeatureFilterMode === 'missing_core') {
            return models.filter((item) => isMissingCoreSupplierFields(item));
        }
        if (supplierFeatureFilterMode === 'missing_billing') {
            return models.filter((item) => isMissingBillingHints(item));
        }
        return models;
    };

    const handleApplySupplierFeatures = async () => {
        const provider = String(supplierFeatureResult?.provider || supplierFeatureProvider || '').trim();
        const models = Array.isArray(supplierFeatureResult?.models) ? supplierFeatureResult.models : [];
        const selectedSet = new Set(selectedSupplierFeatureModelKeys || []);
        const selectedModels = models.filter((item) => selectedSet.has(supplierFeatureModelKey(item)));

        if (!provider) {
            alert(t('缺少 provider 信息，请先分析', 'Missing provider. Please run analysis first.'));
            return;
        }
        if (selectedModels.length === 0) {
            alert(t('请至少勾选一个模型后再保存', 'Please select at least one model before saving.'));
            return;
        }

        try {
            setIsSupplierFeatureApplying(true);
            const applyResult = await ({
                provider,
                models: selectedModels,
                create_missing_models: true,
            });
            setSupplierFeatureResult((prev) => {
                if (!prev) return prev;
                return {
                    ...prev,
                    saved_created: Number(applyResult?.saved_created || 0),
                    saved_updated: Number(applyResult?.saved_updated || 0),
                };
            });
            await fetchSystemApiManageRows();
            alert(t('已保存选中模型特征', 'Selected model features saved'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('保存选中模型失败', 'Failed to save selected models'));
        } finally {
            setIsSupplierFeatureApplying(false);
        }
    };

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
    const CONTENT_FALLBACK_TYPE_ORDER = ['text', 'image', 'video'];
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

    const normalizeContentFallbackPricing = (obj = {}) => {
        const src = (obj && typeof obj === 'object' && !Array.isArray(obj)) ? obj : {};
        const strategyRaw = String(src.strategy || 'manual').trim().toLowerCase();
        const strategy = ['manual', 'average', 'highest'].includes(strategyRaw) ? strategyRaw : 'manual';
        const contentSrc = (src.content_pricing && typeof src.content_pricing === 'object' && !Array.isArray(src.content_pricing)) ? src.content_pricing : {};

        const outMap = {};
        CONTENT_FALLBACK_TYPE_ORDER.forEach((contentType) => {
            const raw = (contentSrc[contentType] && typeof contentSrc[contentType] === 'object' && !Array.isArray(contentSrc[contentType])) ? contentSrc[contentType] : {};
            const defaultUnit = contentType === 'video' ? 'per_second' : 'per_call';
            outMap[contentType] = {
                unit_type: normalizeApiPricingUnitType(raw?.unit_type ?? defaultUnit),
                cost: toNonNegativeInt(raw?.cost ?? 0),
                cost_input: toNonNegativeInt(raw?.cost_input ?? 0),
                cost_output: toNonNegativeInt(raw?.cost_output ?? 0),
            };
        });

        return {
            enabled: !!src.enabled,
            strategy,
            content_pricing: outMap,
        };
    };

    const buildContentFallbackRows = (obj = {}) => {
        const normalized = normalizeContentFallbackPricing(obj);
        return CONTENT_FALLBACK_TYPE_ORDER.map((contentType) => ({
            id: `content-fallback-${contentType}`,
            content_type: contentType,
            unit_type: normalized.content_pricing[contentType].unit_type,
            cost: String(normalized.content_pricing[contentType].cost),
            cost_input: String(normalized.content_pricing[contentType].cost_input),
            cost_output: String(normalized.content_pricing[contentType].cost_output),
        }));
    };

    const buildContentFallbackMapFromRows = (rows = []) => {
        const outMap = {};
        (rows || []).forEach((row) => {
            const contentType = String(row?.content_type || '').trim().toLowerCase();
            if (!CONTENT_FALLBACK_TYPE_ORDER.includes(contentType)) return;
            outMap[contentType] = {
                unit_type: normalizeApiPricingUnitType(row?.unit_type),
                cost: toNonNegativeInt(row?.cost),
                cost_input: toNonNegativeInt(row?.cost_input),
                cost_output: toNonNegativeInt(row?.cost_output),
            };
        });
        return normalizeContentFallbackPricing({
            enabled: !!contentFallbackPricing?.enabled,
            strategy: contentFallbackPricing?.strategy || 'manual',
            content_pricing: outMap,
        });
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
        if (activeTab === 'runtime_logs') {
            fetchRuntimeLogs();
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'storage_usage') {
            fetchStorageUsage();
            fetchExpiredFiles();
            fetchOrphanFiles();
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
                await handleSelectPromptSkill(firstSkillId, items);
            } else {
                setSelectedPromptSkillId('');
                setSelectedPromptSkillPromptRef('');
                setSelectedPromptSkillText('');
            }
        } catch (err) {
            console.error('Failed to load prompt skills', err);
            setPromptSkills([]);
            setSelectedPromptSkillId('');
            setSelectedPromptSkillPromptRef('');
            setSelectedPromptSkillText('');
        } finally {
            setIsPromptSkillsLoading(false);
        }
    };

    const getPromptRefsForSkill = (skill) => {
        const refs = Array.isArray(skill?.prompts) ? skill.prompts : [];
        return refs.map((item) => String(item || '').trim()).filter(Boolean);
    };

    const resolveDefaultPromptRefForSkill = (skill) => {
        const refs = getPromptRefsForSkill(skill);
        const preferred = ['skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md', 'skills/shot_generation.md'];
        for (const candidate of preferred) {
            if (refs.includes(candidate)) return candidate;
        }
        if (refs.length > 0) return refs[0];
        const skillId = String(skill?.id || '').trim();
        return skillId ? `skill:${skillId}/system_prompt.txt` : '';
    };

    const loadPromptSkillPrompt = async (promptRef) => {
        const stableRef = String(promptRef || '').trim();
        setSelectedPromptSkillPromptRef(stableRef);
        setIsPromptSkillTextLoading(true);
        setPromptSkillSaveMessage('');
        try {
            const promptRes = await fetchPrompt(stableRef);
            setSelectedPromptSkillText(String(promptRes?.content || ''));
        } catch (err) {
            console.error('Failed to load skill prompt text', err);
            setSelectedPromptSkillText('');
        } finally {
            setIsPromptSkillTextLoading(false);
        }
    };

    const handleSelectPromptSkill = async (skillId, sourceItems = null) => {
        const id = String(skillId || '').trim();
        if (!id) return;
        setSelectedPromptSkillId(id);
        const items = Array.isArray(sourceItems) ? sourceItems : promptSkills;
        const skill = (Array.isArray(items) ? items : []).find((item) => String(item?.id || '').trim() === id);
        const defaultPromptRef = resolveDefaultPromptRefForSkill(skill || {});
        if (!defaultPromptRef) {
            setSelectedPromptSkillPromptRef('');
            setSelectedPromptSkillText('');
            return;
        }
        await loadPromptSkillPrompt(defaultPromptRef);
    };

    const handleSavePromptSkill = async () => {
        const promptRef = String(selectedPromptSkillPromptRef || '').trim();
        if (!promptRef) return;
        setIsPromptSkillSaving(true);
        setPromptSkillSaveMessage('');
        try {
            await savePrompt(promptRef, selectedPromptSkillText);
            setPromptSkillSaveMessage(t('已保存', 'Saved'));
            setTimeout(() => setPromptSkillSaveMessage(''), 2000);
        } catch (err) {
            console.error('Failed to save prompt skill text', err);
            alert(err?.response?.data?.detail || err?.message || 'Failed to save prompt');
        } finally {
            setIsPromptSkillSaving(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'prompt_skills') {
            loadPromptSkills();
        }
    }, [activeTab]);

    const resolveSystemApiSelection = (rows, preferredId, { allowEmpty = false } = {}) => {
        const normalizedRows = Array.isArray(rows) ? rows : [];
        if (normalizedRows.length === 0) return '';
        const matched = normalizedRows.find((row) => String(row.id) === String(preferredId));
        if (matched) return String(matched.id);
        return allowEmpty ? '' : String(normalizedRows[0].id);
    };

    const fetchSystemApiManageRows = async () => {
        setIsSystemApiLoading(true);
        try {
            const rows = await getSystemSettingsManage();
            const normalized = Array.isArray(rows) ? rows : [];
            setSystemApiRows(normalized);
            const nextSelectedId = resolveSystemApiSelection(normalized, selectedSystemApiId, {
                allowEmpty: activeTab === 'pricing_rules',
            });
            setSelectedSystemApiId(nextSelectedId);
            return {
                rows: normalized,
                selectedSystemApiId: nextSelectedId,
            };
        } catch (e) {
            console.error('Failed to load system API manage rows', e);
            setSystemApiRows([]);
            setSelectedSystemApiId('');
            return {
                rows: [],
                selectedSystemApiId: '',
            };
        } finally {
            setIsSystemApiLoading(false);
        }
    };

    const pauseAdminRefresh = (ms = 180) => new Promise((resolve) => setTimeout(resolve, ms));

    const refreshSystemApiAdminViews = async ({ includeSystemApi = true, includeProviderPools = false, includeOssPools = false, includeTaskDefaults = false, includeKie = false, includePayment = false, includeSmtp = false, includeBillingRules = false } = {}) => {
        let refreshedSelectedSystemApiId = selectedSystemApiId;
        if (includeSystemApi) {
            const result = await fetchSystemApiManageRows();

            refreshedSelectedSystemApiId = String(result?.selectedSystemApiId || '');
            await pauseAdminRefresh();
        }
        if (includeProviderPools) {
            await fetchProviderKeyPools();
            await pauseAdminRefresh();
        }
        if (includeOssPools) {
            await fetchOssProviderPools();
            await pauseAdminRefresh();
        }
        if (includeTaskDefaults) {
            await fetchTaskDefaultApis();
            await pauseAdminRefresh();

        }
        if (includeKie) {
            await fetchKieStandardMappingsAndValues();
            await pauseAdminRefresh();
        }
        if (includePayment) {
            await fetchPaymentConfig();
            await pauseAdminRefresh();
        }
        if (includeSmtp) {
            await fetchSmtpConfig();
            await pauseAdminRefresh();
        }
        if (includeBillingRules) {
            await fetchBillingRulesForSystemApi(refreshedSelectedSystemApiId);
        }
    };

    useEffect(() => {
        if (activeTab === 'system_api' || activeTab === 'pricing_rules' || activeTab === 'oss_pools') {
            if (activeTab === 'system_api') {
                refreshSystemApiAdminViews({
                    includeSystemApi: true,
                    includeProviderPools: true,
                    includeTaskDefaults: true,
                    includeKie: true,
                });
                return;
            }
            if (activeTab === 'oss_pools') {
                refreshSystemApiAdminViews({
                    includeSystemApi: true,
                    includeProviderPools: true,
                    includeOssPools: true,
                });
                return;
            }

            fetchSystemApiManageRows();
        }
    }, [activeTab]);

    const fetchBillingRuleResetConfig = async () => {
        try {
            const cfg = await getBillingRuleResetConfigManage();
            const minMul = Number(cfg?.min_multiplier);
            const maxMul = Number(cfg?.max_multiplier);
            const defaultMul = Number(cfg?.default_multiplier);
            const binSize = Number.parseInt(String(cfg?.bin_size_credits ?? 10), 10);
            const binDrop = Number(cfg?.bin_drop_multiplier);
            const cap = Number.parseInt(String(cfg?.max_total_increase_credits ?? 50), 10);
            setBatchResetMinMultiplier(String(Number.isFinite(minMul) ? minMul : 1.1));
            setBatchResetMaxMultiplier(String(Number.isFinite(maxMul) ? maxMul : 2.0));
            setBatchResetDefaultMultiplier(String(Number.isFinite(defaultMul) ? defaultMul : 2.0));
            setBatchResetBinSizeCredits(String(Number.isFinite(binSize) && binSize > 0 ? binSize : 10));
            setBatchResetBinDropMultiplier(String(Number.isFinite(binDrop) && binDrop > 0 ? binDrop : 0.1));
            setBatchResetMaxIncreaseCredits(String(Number.isFinite(cap) && cap >= 0 ? cap : 50));
        } catch (e) {
            console.error('Failed to load billing reset config', e);
        }
    };

    const saveBillingRuleResetConfig = async (nextValue) => {
        const parsedCap = Math.max(0, Number.parseInt(String(nextValue || batchResetMaxIncreaseCredits || '').trim(), 10) || 0);
        const parsedMin = Number.parseFloat(String(batchResetMinMultiplier || '').trim());
        const parsedMax = Number.parseFloat(String(batchResetMaxMultiplier || '').trim());
        const parsedDefault = Number.parseFloat(String(batchResetDefaultMultiplier || '').trim());
        const parsedBinSize = Math.max(1, Number.parseInt(String(batchResetBinSizeCredits || '').trim(), 10) || 10);
        const parsedBinDrop = Number.parseFloat(String(batchResetBinDropMultiplier || '').trim());

        const payload = {
            min_multiplier: Number.isFinite(parsedMin) ? parsedMin : 1.1,
            max_multiplier: Number.isFinite(parsedMax) ? parsedMax : 2.0,
            default_multiplier: Number.isFinite(parsedDefault) ? parsedDefault : 2.0,
            bin_size_credits: parsedBinSize,
            bin_drop_multiplier: Number.isFinite(parsedBinDrop) && parsedBinDrop > 0 ? parsedBinDrop : 0.1,
            max_total_increase_credits: parsedCap,
        };

        setIsBatchResetConfigSaving(true);
        try {
            const saved = await updateBillingRuleResetConfigManage(payload);
            const minMul = Number(saved?.min_multiplier);
            const maxMul = Number(saved?.max_multiplier);
            const defaultMul = Number(saved?.default_multiplier);
            const binSize = Number.parseInt(String(saved?.bin_size_credits ?? parsedBinSize), 10);
            const binDrop = Number(saved?.bin_drop_multiplier);
            const cap = Number.parseInt(String(saved?.max_total_increase_credits ?? parsedCap), 10);

            setBatchResetMinMultiplier(String(Number.isFinite(minMul) ? minMul : payload.min_multiplier));
            setBatchResetMaxMultiplier(String(Number.isFinite(maxMul) ? maxMul : payload.max_multiplier));
            setBatchResetDefaultMultiplier(String(Number.isFinite(defaultMul) ? defaultMul : payload.default_multiplier));
            setBatchResetBinSizeCredits(String(Number.isFinite(binSize) && binSize > 0 ? binSize : payload.bin_size_credits));
            setBatchResetBinDropMultiplier(String(Number.isFinite(binDrop) && binDrop > 0 ? binDrop : payload.bin_drop_multiplier));
            setBatchResetMaxIncreaseCredits(String(Number.isFinite(cap) && cap >= 0 ? cap : payload.max_total_increase_credits));
        } catch (e) {
            console.error('Failed to save billing reset config', e);
            alert(e?.response?.data?.detail || e?.message || t('保存增幅上限失败', 'Failed to save increase cap'));
        } finally {
            setIsBatchResetConfigSaving(false);
        }
    };

    const fetchAssetImageRatioConfig = async () => {
        try {
            const cfg = await getAssetImageRatioConfigManage();
            setSubjectAssetAspectRatio(String(cfg?.subject_aspect_ratio || '16:9').trim() || '16:9');
            setCoverAssetAspectRatio(String(cfg?.cover_aspect_ratio || '3:4').trim() || '3:4');
        } catch (e) {
            console.error('Failed to load asset image ratio config', e);
        }
    };

    const fetchSceneAnalysisConfig = async () => {
        try {
            const cfg = await getSceneAnalysisConfigManage();
            const nextMode = String(cfg?.default_mode || 'classic').trim() || 'classic';
            setSceneAnalysisDefaultMode(nextMode);
        } catch (e) {
            console.error('Failed to load scene analysis config', e);
        }
    };

    const normalizeProjectCostConfigForUi = (rawConfig) => {
        const src = rawConfig && typeof rawConfig === 'object' ? rawConfig : {};
        const srcSuggested = src?.suggested && typeof src.suggested === 'object' ? src.suggested : {};
        const srcTier = srcSuggested?.entity_tier_ratios && typeof srcSuggested.entity_tier_ratios === 'object'
            ? srcSuggested.entity_tier_ratios
            : {};

        return {
            ...src,
            overview: {
                ...DEFAULT_PROJECT_COST_VISUAL_CONFIG.overview,
                ...(src?.overview && typeof src.overview === 'object' ? src.overview : {}),
            },
            suggested: {
                ...DEFAULT_PROJECT_COST_VISUAL_CONFIG.suggested,
                ...srcSuggested,
                entity_tier_ratios: {
                    ...DEFAULT_PROJECT_COST_VISUAL_CONFIG.suggested.entity_tier_ratios,
                    ...srcTier,
                },
            },
            budget: {
                ...DEFAULT_PROJECT_COST_VISUAL_CONFIG.budget,
                ...(src?.budget && typeof src.budget === 'object' ? src.budget : {}),
            },
            project_multiplier: {
                ...DEFAULT_PROJECT_COST_VISUAL_CONFIG.project_multiplier,
                ...(src?.project_multiplier && typeof src.project_multiplier === 'object' ? src.project_multiplier : {}),
            },
        };
    };

    const getCostConfigNumber = (path, fallback = 0) => {
        let cursor = projectCostConfigData;
        for (const key of path) {
            if (!cursor || typeof cursor !== 'object') return fallback;
            cursor = cursor[key];
        }
        const parsed = Number(cursor);
        return Number.isFinite(parsed) ? parsed : fallback;
    };

    const setCostConfigNumber = (path, value, fallback = 0, asInt = false) => {
        const raw = String(value ?? '').trim();
        const parsed = asInt ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
        const nextValue = Number.isFinite(parsed) ? parsed : fallback;

        setProjectCostConfigData((prev) => {
            const next = { ...(prev || {}) };
            let cursor = next;
            for (let i = 0; i < path.length - 1; i += 1) {
                const key = path[i];
                const child = cursor?.[key];
                cursor[key] = child && typeof child === 'object' && !Array.isArray(child) ? { ...child } : {};
                cursor = cursor[key];
            }
            cursor[path[path.length - 1]] = nextValue;
            return next;
        });
    };

    const getCostFieldFactors = () => {
        const ff = projectCostConfigData?.project_multiplier?.field_factors;
        return ff && typeof ff === 'object' && !Array.isArray(ff) ? ff : {};
    };

    const setFieldFactors = (updater) => {
        setProjectCostConfigData((prev) => {
            const prevPm = prev?.project_multiplier && typeof prev.project_multiplier === 'object' ? prev.project_multiplier : {};
            const prevFf = prevPm?.field_factors && typeof prevPm.field_factors === 'object' ? prevPm.field_factors : {};
            const nextFf = typeof updater === 'function' ? updater(prevFf) : updater;
            return { ...prev, project_multiplier: { ...prevPm, field_factors: nextFf } };
        });
    };

    const addCostField = () => {
        setFieldFactors((ff) => {
            let name = 'new_field';
            let i = 1;
            while (Object.prototype.hasOwnProperty.call(ff, name)) { name = `new_field_${i}`; i += 1; }
            return { ...ff, [name]: { __default__: 1.0 } };
        });
    };

    const removeCostField = (fieldName) => {
        setFieldFactors((ff) => {
            const next = { ...ff };
            delete next[fieldName];
            return next;
        });
    };

    const renameCostField = (oldName, newName) => {
        const trimmed = String(newName || '').trim();
        if (!trimmed || trimmed === oldName) return;
        setFieldFactors((ff) => {
            if (Object.prototype.hasOwnProperty.call(ff, trimmed)) return ff;
            const next = {};
            for (const [k, v] of Object.entries(ff)) {
                next[k === oldName ? trimmed : k] = v;
            }
            return next;
        });
    };

    const addCostFieldMapping = (fieldName) => {
        setFieldFactors((ff) => {
            const existing = ff[fieldName] && typeof ff[fieldName] === 'object' ? ff[fieldName] : {};
            let val = 'value';
            let i = 1;
            while (Object.prototype.hasOwnProperty.call(existing, val)) { val = `value${i}`; i += 1; }
            return { ...ff, [fieldName]: { ...existing, [val]: 1.0 } };
        });
    };

    const removeCostFieldMapping = (fieldName, mappingKey) => {
        setFieldFactors((ff) => {
            const existing = { ...(ff[fieldName] || {}) };
            delete existing[mappingKey];
            return { ...ff, [fieldName]: existing };
        });
    };

    const updateCostFieldMappingKey = (fieldName, oldKey, newKey) => {
        const trimmed = String(newKey || '').trim();
        if (!trimmed || trimmed === oldKey) return;
        setFieldFactors((ff) => {
            const existing = ff[fieldName] && typeof ff[fieldName] === 'object' ? ff[fieldName] : {};
            if (Object.prototype.hasOwnProperty.call(existing, trimmed)) return ff;
            const next = {};
            for (const [k, v] of Object.entries(existing)) {
                next[k === oldKey ? trimmed : k] = v;
            }
            return { ...ff, [fieldName]: next };
        });
    };

    const updateCostFieldMappingFactor = (fieldName, mappingKey, value) => {
        const raw = String(value ?? '').trim();
        const parsed = Number.parseFloat(raw);
        const nextVal = Number.isFinite(parsed) ? parsed : 1.0;
        setFieldFactors((ff) => {
            const existing = { ...(ff[fieldName] || {}) };
            existing[mappingKey] = nextVal;
            return { ...ff, [fieldName]: existing };
        });
    };

    const fetchProjectCostEstimationConfig = async () => {
        try {
            const cfg = await getProjectCostEstimationConfigManage();
            const payload = cfg?.config && typeof cfg.config === 'object' ? cfg.config : {};
            setProjectCostConfigData(normalizeProjectCostConfigForUi(payload));
            setCostFormKey((k) => k + 1);
        } catch (e) {
            console.error('Failed to load project cost estimation config', e);
        }
    };

    const saveAssetImageRatioConfig = async (overrides = {}) => {
        const payload = {
            subject_aspect_ratio: String(overrides.subject_aspect_ratio ?? subjectAssetAspectRatio ?? '').trim() || '16:9',
            cover_aspect_ratio: String(overrides.cover_aspect_ratio ?? coverAssetAspectRatio ?? '').trim() || '3:4',
        };

        setIsAssetImageRatioConfigSaving(true);
        try {
            const saved = await updateAssetImageRatioConfigManage(payload);
            setSubjectAssetAspectRatio(String(saved?.subject_aspect_ratio || payload.subject_aspect_ratio).trim() || '16:9');
            setCoverAssetAspectRatio(String(saved?.cover_aspect_ratio || payload.cover_aspect_ratio).trim() || '3:4');
        } catch (e) {
            console.error('Failed to save asset image ratio config', e);
            alert(e?.response?.data?.detail || e?.message || t('保存资产画幅设置失败', 'Failed to save asset image ratio config'));
        } finally {
            setIsAssetImageRatioConfigSaving(false);
        }
    };

    const saveSceneAnalysisConfig = async (overrides = {}) => {
        const payload = {
            default_mode: String(overrides.default_mode ?? sceneAnalysisDefaultMode ?? 'classic').trim() || 'classic',
        };

        setIsSceneAnalysisConfigSaving(true);
        try {
            const saved = await updateSceneAnalysisConfigManage(payload);
            setSceneAnalysisDefaultMode(String(saved?.default_mode || payload.default_mode).trim() || 'classic');
        } catch (e) {
            console.error('Failed to save scene analysis config', e);
            alert(e?.response?.data?.detail || e?.message || t('保存场景分析总开关失败', 'Failed to save scene analysis config'));
        } finally {
            setIsSceneAnalysisConfigSaving(false);
        }
    };

    const saveProjectCostEstimationConfig = async () => {
        const payload = normalizeProjectCostConfigForUi(projectCostConfigData);
        setIsProjectCostConfigSaving(true);
        try {
            const saved = await updateProjectCostEstimationConfigManage({ config: payload });
            const normalized = saved?.config && typeof saved.config === 'object' ? saved.config : payload;
            setProjectCostConfigData(normalizeProjectCostConfigForUi(normalized));
            setCostFormKey((k) => k + 1);
        } catch (e) {
            console.error('Failed to save project cost estimation config', e);
            alert(e?.response?.data?.detail || e?.message || t('保存项目成本配置失败', 'Failed to save project cost estimation config'));
        } finally {
            setIsProjectCostConfigSaving(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'pricing_rules') {
            fetchBillingRuleResetConfig();
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'system_api') {
            fetchAssetImageRatioConfig();
            fetchSceneAnalysisConfig();
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'cost_estimation') {
            fetchProjectCostEstimationConfig();
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

    const getSystemApiRetryGroup = (row) => {
        const cfg = getSystemApiConfig(row);
        return String(cfg?.retry_group || '').trim();
    };

    const getSystemApiExplicitSelection = (row) => {
        const cfg = getSystemApiConfig(row);
        return !!cfg?.explicit_selection;
    };

    const getSystemApiStrictProvider = (row) => {
        const cfg = getSystemApiConfig(row);
        return !!cfg?.strict_provider;
    };

    const getSystemApiRetryPriceGroup = (row) => {
        const cfg = getSystemApiConfig(row);
        return String(cfg?.retry_price_group || '').trim();
    };

    const getSystemApiModerationAesKey = (row) => {
        const cfg = getSystemApiConfig(row);
        return String(
            cfg?.moderation_aes_key
            || cfg?.moderationAesKey
            || cfg?.moderation_key
            || cfg?.moderationKey
            || ''
        ).trim();
    };

    const getSystemApiModerationUserId = (row) => {
        const cfg = getSystemApiConfig(row);
        return String(
            cfg?.moderation_user_id
            || cfg?.moderationUserId
            || cfg?.user_id
            || cfg?.userId
            || ''
        ).trim();
    };

    const getSystemApiModerationEndpoint = (row) => {
        const cfg = getSystemApiConfig(row);
        return String(
            cfg?.moderation_endpoint
            || cfg?.moderationEndpoint
            || ''
        ).trim();
    };

    const buildSystemApiConfigPayload = () => {
        const parsed = parseJsonFieldSafe(systemApiForm.config);
        const baseConfig = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? { ...parsed } : {};
        const retryGroup = String(systemApiForm.retry_group || '').trim();
        const retryPriceGroup = String(systemApiForm.retry_price_group || '').trim();
        const moderationEndpoint = String(systemApiForm.moderation_endpoint || '').trim();
        const moderationUserId = String(systemApiForm.moderation_user_id || '').trim();
        const moderationAesKey = String(systemApiForm.moderation_aes_key || '').trim();
        
        if (systemApiForm.explicit_selection) {
            baseConfig.explicit_selection = true;
        } else {
            delete baseConfig.explicit_selection;
        }
        
        if (systemApiForm.strict_provider) {
            baseConfig.strict_provider = true;
        } else {
            delete baseConfig.strict_provider;
        }

        if (retryGroup) {
            baseConfig.retry_group = retryGroup;
        } else {
            delete baseConfig.retry_group;
        }
        if (retryPriceGroup) {
            baseConfig.retry_price_group = retryPriceGroup;
        } else {
            delete baseConfig.retry_price_group;
        }
        if (moderationEndpoint) {
            baseConfig.moderation_endpoint = moderationEndpoint;
        } else {
            delete baseConfig.moderation_endpoint;
        }
        if (moderationUserId) {
            baseConfig.moderation_user_id = moderationUserId;
        } else {
            delete baseConfig.moderation_user_id;
        }
        if (moderationAesKey) {
            baseConfig.moderation_aes_key = moderationAesKey;
        } else {
            delete baseConfig.moderation_aes_key;
        }
        delete baseConfig.moderationEndpoint;
        delete baseConfig.moderationUserId;
        delete baseConfig.user_id;
        delete baseConfig.userId;
        delete baseConfig.moderationAesKey;
        delete baseConfig.moderation_key;
        delete baseConfig.moderationKey;
        return baseConfig;
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

    const toRuleChargeMultiplier = (value, fallback = 2) => {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed < 0) return Number(fallback);
        return parsed;
    };

    const getApiPricing = (row) => {
        // 仅从宽表列读取计价信息
        return {
            unit_type: normalizeApiPricingUnitType(row?.billing_unit_type ?? 'per_call'),
            cost: toNonNegativeInt(row?.billing_cost ?? 0),
            cost_input: toNonNegativeInt(row?.billing_cost_input ?? 0),
            cost_output: toNonNegativeInt(row?.billing_cost_output ?? 0),
        };
    };

    const safeJsonStr = (val) => {
        if (val === null || val === undefined) return '';
        if (typeof val === 'string') return val;
        try { return JSON.stringify(val, null, 2); } catch { return ''; }
    };

    const createEmptyBillingRuleForm = () => ({
        name: 'Rule',
        description: '',
        is_active: true,
        priority: '0',
        applies_to_text: true,
        applies_to_image: false,
        applies_to_video: false,
        generation_mode: '',
        input_format: '',
        output_format: '',
        has_audio: 'any',
        input_tokens_min: '',
        input_tokens_max: '',
        output_tokens_min: '',
        output_tokens_max: '',
        total_tokens_min: '',
        total_tokens_max: '',
        image_count_min: '',
        image_count_max: '',
        width_min: '',
        width_max: '',
        height_min: '',
        height_max: '',
        pixels_min: '',
        pixels_max: '',
        duration_seconds_min: '',
        duration_seconds_max: '',
        fps_min: '',
        fps_max: '',
        billing_unit_type: 'per_call',
        billing_cost: '0',
        billing_cost_input: '0',
        billing_cost_output: '0',
        charge_multiplier: '2',
        extra_conditions_text: '{}',
    });

    const toNullableText = (value) => {
        const text = String(value || '').trim();
        return text || null;
    };

    const toNullableInt = (value) => {
        const text = String(value ?? '').trim();
        if (!text) return null;
        const parsed = Number(text);
        if (!Number.isFinite(parsed)) return null;
        return Math.floor(parsed);
    };

    const toNullableFloat = (value) => {
        const text = String(value ?? '').trim();
        if (!text) return null;
        const parsed = Number(text);
        if (!Number.isFinite(parsed)) return null;
        return parsed;
    };

    const toNullableBool = (value) => {
        if (value === true || value === false) return value;
        const text = String(value || '').trim().toLowerCase();
        if (text === 'true') return true;
        if (text === 'false') return false;
        return null;
    };

    const toRuleActiveBool = (value, fallback = true) => {
        if (value === true || value === false) return value;
        const text = String(value ?? '').trim().toLowerCase();
        if (!text) return Boolean(fallback);
        if (['active', 'true', '1', 'yes', 'on'].includes(text)) return true;
        if (['inactive', 'false', '0', 'no', 'off'].includes(text)) return false;
        return Boolean(fallback);
    };

    const parseRuleExtraConditions = (text) => {
        const trimmed = String(text || '').trim();
        if (!trimmed) return {};
        try {
            const parsed = JSON.parse(trimmed);
            if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                throw new Error('extra_conditions must be a JSON object');
            }
            return parsed;
        } catch {
            throw new Error('extra_conditions 必须是 JSON 对象');
        }
    };

    const ruleRowToForm = (row) => ({
        name: String(row?.name || 'Rule'),
        description: String(row?.description || ''),
        is_active: !!row?.is_active,
        priority: String(row?.priority ?? 0),
        applies_to_text: !!row?.applies_to_text,
        applies_to_image: !!row?.applies_to_image,
        applies_to_video: !!row?.applies_to_video,
        generation_mode: String(row?.generation_mode || ''),
        input_format: String(row?.input_format || ''),
        output_format: String(row?.output_format || ''),
        has_audio: row?.has_audio === true ? 'true' : (row?.has_audio === false ? 'false' : 'any'),
        input_tokens_min: row?.input_tokens_min === null || row?.input_tokens_min === undefined ? '' : String(row.input_tokens_min),
        input_tokens_max: row?.input_tokens_max === null || row?.input_tokens_max === undefined ? '' : String(row.input_tokens_max),
        output_tokens_min: row?.output_tokens_min === null || row?.output_tokens_min === undefined ? '' : String(row.output_tokens_min),
        output_tokens_max: row?.output_tokens_max === null || row?.output_tokens_max === undefined ? '' : String(row.output_tokens_max),
        total_tokens_min: row?.total_tokens_min === null || row?.total_tokens_min === undefined ? '' : String(row.total_tokens_min),
        total_tokens_max: row?.total_tokens_max === null || row?.total_tokens_max === undefined ? '' : String(row.total_tokens_max),
        image_count_min: row?.image_count_min === null || row?.image_count_min === undefined ? '' : String(row.image_count_min),
        image_count_max: row?.image_count_max === null || row?.image_count_max === undefined ? '' : String(row.image_count_max),
        width_min: row?.width_min === null || row?.width_min === undefined ? '' : String(row.width_min),
        width_max: row?.width_max === null || row?.width_max === undefined ? '' : String(row.width_max),
        height_min: row?.height_min === null || row?.height_min === undefined ? '' : String(row.height_min),
        height_max: row?.height_max === null || row?.height_max === undefined ? '' : String(row.height_max),
        pixels_min: row?.pixels_min === null || row?.pixels_min === undefined ? '' : String(row.pixels_min),
        pixels_max: row?.pixels_max === null || row?.pixels_max === undefined ? '' : String(row.pixels_max),
        duration_seconds_min: row?.duration_seconds_min === null || row?.duration_seconds_min === undefined ? '' : String(row.duration_seconds_min),
        duration_seconds_max: row?.duration_seconds_max === null || row?.duration_seconds_max === undefined ? '' : String(row.duration_seconds_max),
        fps_min: row?.fps_min === null || row?.fps_min === undefined ? '' : String(row.fps_min),
        fps_max: row?.fps_max === null || row?.fps_max === undefined ? '' : String(row.fps_max),
        billing_unit_type: normalizeApiPricingUnitType(row?.billing_unit_type || 'per_call'),
        billing_cost: String(toNonNegativeInt(row?.billing_cost ?? 0)),
        billing_cost_input: String(toNonNegativeInt(row?.billing_cost_input ?? 0)),
        billing_cost_output: String(toNonNegativeInt(row?.billing_cost_output ?? 0)),
        charge_multiplier: String(toRuleChargeMultiplier(row?.charge_multiplier, 2)),
        extra_conditions_text: safeJsonStr(row?.extra_conditions ?? {}) || '{}',
    });

    const buildBillingRulePayloadFromForm = (form) => ({
        name: String(form?.name || 'Rule').trim() || 'Rule',
        description: toNullableText(form?.description),
        is_active: toRuleActiveBool(form?.is_active, true),
        priority: toNullableInt(form?.priority) ?? 0,
        applies_to_text: !!form?.applies_to_text,
        applies_to_image: !!form?.applies_to_image,
        applies_to_video: !!form?.applies_to_video,
        generation_mode: toNullableText(form?.generation_mode),
        input_format: toNullableText(form?.input_format),
        output_format: toNullableText(form?.output_format),
        has_audio: toNullableBool(form?.has_audio),
        input_tokens_min: toNullableInt(form?.input_tokens_min),
        input_tokens_max: toNullableInt(form?.input_tokens_max),
        output_tokens_min: toNullableInt(form?.output_tokens_min),
        output_tokens_max: toNullableInt(form?.output_tokens_max),
        total_tokens_min: toNullableInt(form?.total_tokens_min),
        total_tokens_max: toNullableInt(form?.total_tokens_max),
        image_count_min: toNullableInt(form?.image_count_min),
        image_count_max: toNullableInt(form?.image_count_max),
        width_min: toNullableInt(form?.width_min),
        width_max: toNullableInt(form?.width_max),
        height_min: toNullableInt(form?.height_min),
        height_max: toNullableInt(form?.height_max),
        pixels_min: toNullableInt(form?.pixels_min),
        pixels_max: toNullableInt(form?.pixels_max),
        duration_seconds_min: toNullableFloat(form?.duration_seconds_min),
        duration_seconds_max: toNullableFloat(form?.duration_seconds_max),
        fps_min: toNullableFloat(form?.fps_min),
        fps_max: toNullableFloat(form?.fps_max),
        billing_unit_type: normalizeApiPricingUnitType(form?.billing_unit_type),
        billing_cost: toNonNegativeInt(form?.billing_cost),
        billing_cost_input: toNonNegativeInt(form?.billing_cost_input),
        billing_cost_output: toNonNegativeInt(form?.billing_cost_output),
        charge_multiplier: toRuleChargeMultiplier(form?.charge_multiplier, 2),
        extra_conditions: parseRuleExtraConditions(form?.extra_conditions_text),
    });

    const normalizeBillingRuleRows = (payload, fallbackSystemApiId = null) => {
        const list = Array.isArray(payload)
            ? payload
            : (Array.isArray(payload?.items)
                ? payload.items
                : (Array.isArray(payload?.rules)
                    ? payload.rules
                    : (Array.isArray(payload?.data) ? payload.data : [])));

        return list
            .filter((row) => row && typeof row === 'object')
            .map((row) => ({
                ...row,
                system_api_id: row?.system_api_id ?? fallbackSystemApiId ?? null,
            }));
    };

    const fetchBillingRulesForSystemApi = async (systemApiId) => {
        const requestedId = Number(systemApiId || 0);
        const hasRequestedId = requestedId > 0;
        const targetExists = !hasRequestedId || (systemApiRows || []).some((row) => Number(row?.id || 0) === requestedId);
        const targetId = targetExists ? requestedId : 0;

        if (hasRequestedId && !targetExists) {
            setSelectedSystemApiId('');
        }

        setIsBillingRuleLoading(true);
        try {
            let normalized = [];
            if (targetId) {
                const rows = await listSystemApiBillingRulesManage(targetId);
                normalized = normalizeBillingRuleRows(rows, targetId);
            } else {
                const ids = (systemApiRows || []).map((row) => Number(row?.id || 0)).filter((id) => id > 0);
                if (ids.length > 0) {
                    const grouped = await listSystemApiBillingRulesBatchManage(ids);
                    normalized = ids.flatMap((id) => normalizeBillingRuleRows(grouped?.[String(id)] || [], id));
                }
            }
            setBillingRuleRows(normalized);
            setSelectedBillingRuleId((prev) => {
                if (prev && normalized.some((row) => String(row.id) === String(prev))) return prev;
                return normalized.length > 0 ? String(normalized[0].id) : '';
            });
            setSelectedBillingRuleIds((prev) => (prev || []).filter((id) => normalized.some((row) => Number(row.id) === Number(id))));
            if (normalized.length === 0) {
                setBillingRuleForm(createEmptyBillingRuleForm());
            }
        } catch (e) {
            console.error('Failed to load billing rules', e);
            setBillingRuleRows([]);
            setSelectedBillingRuleId('');
            setSelectedBillingRuleIds([]);
            setBillingRuleForm(createEmptyBillingRuleForm());
        } finally {
            setIsBillingRuleLoading(false);
        }
    };

    const handleCheckMissingBillingRuleApis = async () => {
        setIsMissingBillingRuleCheckLoading(true);
        try {
            const rows = await getSystemApisMissingBillingRulesManage();
            const normalized = Array.isArray(rows) ? rows : [];
            setMissingBillingRuleApiRows(normalized);
            alert(
                normalized.length > 0
                    ? t(`检查完成：发现 ${normalized.length} 条 API 未关联计费规则。`, `Check completed: found ${normalized.length} APIs without billing rules.`)
                    : t('检查完成：所有启用且未弃用 API 均已关联计费规则。', 'Check completed: all active and non-deprecated APIs have billing rules.')
            );
        } catch (e) {
            console.error('Failed to check missing billing rules', e);
            alert(e?.response?.data?.detail || e.message || t('检查失败', 'Check failed'));
        } finally {
            setIsMissingBillingRuleCheckLoading(false);
        }
    };

    const systemApiIdDigest = React.useMemo(
        () => (systemApiRows || []).map((row) => Number(row?.id || 0)).filter((id) => id > 0).sort((a, b) => a - b).join(','),
        [systemApiRows]
    );

    useEffect(() => {
        if (activeTab !== 'system_api' && activeTab !== 'pricing_rules') return;
        fetchBillingRulesForSystemApi(selectedSystemApiId);
    }, [activeTab, selectedSystemApiId, systemApiIdDigest]);

    useEffect(() => {
        if (!selectedBillingRuleId) {
            setBillingRuleForm(createEmptyBillingRuleForm());
            return;
        }
        const row = billingRuleRows.find((item) => String(item.id) === String(selectedBillingRuleId));
        if (!row) return;
        setBillingRuleForm(ruleRowToForm(row));
    }, [selectedBillingRuleId, billingRuleRows]);

    const billingRuleSystemApiMetaMap = React.useMemo(() => {
        const map = new Map();
        (systemApiRows || []).forEach((row) => {
            const id = Number(row?.id || 0);
            if (id > 0) map.set(id, row);
        });
        return map;
    }, [systemApiRows]);

    const billingRuleApiCategoryOptions = React.useMemo(
        () => Array.from(new Set((systemApiRows || []).map((row) => String(row?.category || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
        [systemApiRows]
    );

    const billingRuleApiProviderOptions = React.useMemo(
        () => Array.from(new Set((systemApiRows || []).map((row) => String(row?.provider || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
        [systemApiRows]
    );

    const billingRuleApiBaseModelOptions = React.useMemo(
        () => Array.from(new Set((systemApiRows || []).map((row) => String(row?.base_model || row?.model || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
        [systemApiRows]
    );

    const billingRuleApiPickerCategoryOptions = React.useMemo(
        () => Array.from(new Set((systemApiRows || []).map((row) => String(row?.category || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
        [systemApiRows]
    );

    const billingRuleApiPickerProviderOptions = React.useMemo(() => {
        return Array.from(
            new Set(
                (systemApiRows || [])
                    .filter((row) => {
                        const category = String(row?.category || '').trim();
                        const baseModel = String(row?.base_model || row?.model || '').trim();
                        if (billingRuleApiPickerCategory !== 'all' && category !== billingRuleApiPickerCategory) return false;
                        if (billingRuleApiPickerBaseModel !== 'all' && baseModel !== billingRuleApiPickerBaseModel) return false;
                        return true;
                    })
                    .map((row) => String(row?.provider || '').trim())
                    .filter(Boolean)
            )
        ).sort((a, b) => a.localeCompare(b));
    }, [systemApiRows, billingRuleApiPickerCategory, billingRuleApiPickerBaseModel]);

    const billingRuleApiPickerBaseModelOptions = React.useMemo(() => {
        return Array.from(
            new Set(
                (systemApiRows || [])
                    .filter((row) => {
                        const category = String(row?.category || '').trim();
                        const provider = String(row?.provider || '').trim();
                        if (billingRuleApiPickerCategory !== 'all' && category !== billingRuleApiPickerCategory) return false;
                        if (billingRuleApiPickerProvider !== 'all' && provider !== billingRuleApiPickerProvider) return false;
                        return true;
                    })
                    .map((row) => String(row?.base_model || row?.model || '').trim())
                    .filter(Boolean)
            )
        ).sort((a, b) => a.localeCompare(b));
    }, [systemApiRows, billingRuleApiPickerCategory, billingRuleApiPickerProvider]);

    const filteredBillingRuleApiPickerRows = React.useMemo(() => {
        return (systemApiRows || []).filter((row) => {
            const category = String(row?.category || '').trim();
            const provider = String(row?.provider || '').trim();
            const baseModel = String(row?.base_model || row?.model || '').trim();
            if (billingRuleApiPickerCategory !== 'all' && category !== billingRuleApiPickerCategory) return false;
            if (billingRuleApiPickerProvider !== 'all' && provider !== billingRuleApiPickerProvider) return false;
            if (billingRuleApiPickerBaseModel !== 'all' && baseModel !== billingRuleApiPickerBaseModel) return false;
            return true;
        });
    }, [
        systemApiRows,
        billingRuleApiPickerCategory,
        billingRuleApiPickerProvider,
        billingRuleApiPickerBaseModel,
    ]);

    const filteredBillingRuleRows = React.useMemo(() => {
        const keyword = String(billingRuleFilterKeyword || '').trim().toLowerCase();
        return (billingRuleRows || []).filter((row) => {
            const apiRow = billingRuleSystemApiMetaMap.get(Number(row?.system_api_id || 0));
            const apiCategory = String(apiRow?.category || '').trim();
            const apiProvider = String(apiRow?.provider || '').trim();
            const apiBaseModel = String(apiRow?.base_model || apiRow?.model || '').trim();
            const ruleTarget = String(row?.content_type || '').trim().toLowerCase();
            const unitType = normalizeApiPricingUnitType(row?.billing_unit_type || 'per_call');

            if (billingRuleFilterStatus === 'active' && !row?.is_active) return false;
            if (billingRuleFilterStatus === 'inactive' && row?.is_active) return false;
            if (billingRuleFilterTarget !== 'all' && ruleTarget !== String(billingRuleFilterTarget || '').trim().toLowerCase()) return false;
            if (billingRuleFilterUnitType !== 'all' && unitType !== billingRuleFilterUnitType) return false;
            if (billingRuleFilterApiCategory !== 'all' && apiCategory !== billingRuleFilterApiCategory) return false;
            if (billingRuleFilterApiProvider !== 'all' && apiProvider !== billingRuleFilterApiProvider) return false;
            if (billingRuleFilterApiBaseModel !== 'all' && apiBaseModel !== billingRuleFilterApiBaseModel) return false;

            const haystack = [
                row?.provider,
                row?.rule_name,
                row?.description,
                row?.model,
                row?.mode,
                row?.content_type,
                row?.billing_unit_type,
                apiCategory,
                apiProvider,
                apiBaseModel,
            ].map((v) => String(v || '').toLowerCase()).join(' ');
            return haystack.includes(keyword);
        });
    }, [
        billingRuleRows,
        billingRuleFilterKeyword,
        billingRuleFilterStatus,
        billingRuleFilterTarget,
        billingRuleFilterUnitType,
        billingRuleFilterApiCategory,
        billingRuleFilterApiProvider,
        billingRuleFilterApiBaseModel,
        billingRuleSystemApiMetaMap,
    ]);

    useEffect(() => {
        if (!filteredBillingRuleRows.length) {
            setSelectedBillingRuleId('');
            return;
        }
        const exists = filteredBillingRuleRows.some((row) => String(row.id) === String(selectedBillingRuleId));
        if (!exists) {
            setSelectedBillingRuleId(String(filteredBillingRuleRows[0].id));
        }
    }, [filteredBillingRuleRows, selectedBillingRuleId]);

    const selectedBillingRuleRow = React.useMemo(
        () => billingRuleRows.find((item) => String(item?.id) === String(selectedBillingRuleId)) || null,
        [billingRuleRows, selectedBillingRuleId]
    );

    const selectedBillingRuleIdSet = React.useMemo(
        () => new Set((selectedBillingRuleIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)),
        [selectedBillingRuleIds]
    );

    const selectedFilteredBillingRuleCount = React.useMemo(
        () => filteredBillingRuleRows.filter((row) => selectedBillingRuleIdSet.has(Number(row?.id))).length,
        [filteredBillingRuleRows, selectedBillingRuleIdSet]
    );

    const allFilteredBillingRuleIds = React.useMemo(
        () => filteredBillingRuleRows.map((row) => Number(row?.id || 0)).filter((id) => id > 0),
        [filteredBillingRuleRows]
    );

    const toggleBillingRuleSelection = (ruleId, checked) => {
        const id = Number(ruleId || 0);
        if (!id) return;
        setSelectedBillingRuleIds((prev) => {
            const set = new Set((prev || []).map((v) => Number(v)).filter((v) => v > 0));
            if (checked) {
                set.add(id);
            } else {
                set.delete(id);
            }
            return Array.from(set);
        });
    };

    const toggleSelectAllFilteredBillingRules = (checked) => {
        if (!checked) {
            setSelectedBillingRuleIds((prev) => {
                const drop = new Set(allFilteredBillingRuleIds);
                return (prev || []).filter((id) => !drop.has(Number(id)));
            });
            return;
        }
        setSelectedBillingRuleIds((prev) => {
            const set = new Set((prev || []).map((v) => Number(v)).filter((v) => v > 0));
            allFilteredBillingRuleIds.forEach((id) => set.add(id));
            return Array.from(set);
        });
    };

    const selectedBillingRuleApiLabel = React.useMemo(() => {
        if (!selectedBillingRuleRow) return '-';
        const apiRow = systemApiRows.find((api) => Number(api?.id) === Number(selectedBillingRuleRow?.system_api_id));
        if (!apiRow) return `ID:${selectedBillingRuleRow?.system_api_id || '-'}`;
        return `[${apiRow.category}] ${apiRow.provider}/${apiRow.model || '-'} (ID:${apiRow.id})`;
    }, [selectedBillingRuleRow, systemApiRows]);

    const handleCreateBillingRule = async () => {
        const systemApiId = Number(selectedSystemApiId || 0);
        if (!systemApiId) {
            alert(t('请先选择一个系统 API 配置', 'Select a system API setting first'));
            return;
        }
        try {
            const payload = {
                system_api_id: systemApiId,
                ...buildBillingRulePayloadFromForm(billingRuleForm),
            };
            const created = await createSystemApiBillingRuleManage(systemApiId, payload);
            await fetchBillingRulesForSystemApi(systemApiId);
            if (created?.id) {
                setSelectedBillingRuleId(String(created.id));
            }
            alert(t('定价规则已创建', 'Pricing rule created'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('创建定价规则失败', 'Failed to create pricing rule'));
        }
    };

    const handleUpdateBillingRule = async () => {
        const ruleId = Number(selectedBillingRuleId || 0);
        if (!ruleId) {
            alert(t('请先选择一条定价规则', 'Select a pricing rule first'));
            return;
        }
        try {
            const payload = buildBillingRulePayloadFromForm(billingRuleForm);
            await updateSystemApiBillingRuleManage(ruleId, payload);
            await fetchBillingRulesForSystemApi(selectedSystemApiId);
            alert(t('定价规则已更新', 'Pricing rule updated'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('更新定价规则失败', 'Failed to update pricing rule'));
        }
    };

    const handleDeleteBillingRule = async () => {
        const selectedIds = (selectedBillingRuleIds || []).map((id) => Number(id || 0)).filter((id) => id > 0);
        const fallbackId = Number(selectedBillingRuleId || 0);
        const targetIds = selectedIds.length > 0 ? selectedIds : (fallbackId ? [fallbackId] : []);
        if (!targetIds.length) {
            alert(t('请先选择至少一条定价规则', 'Select at least one pricing rule first'));
            return;
        }
        const confirmText = targetIds.length > 1
            ? t(`确认删除选中的 ${targetIds.length} 条定价规则？`, `Delete ${targetIds.length} selected pricing rules?`)
            : t('确认删除该定价规则？', 'Delete this pricing rule?');
        if (!await confirmUiMessage(confirmText)) return;
        try {
            if (targetIds.length > 1) {
                await deleteSystemApiBillingRulesBatchManage(targetIds);
            } else {
                await deleteSystemApiBillingRuleManage(targetIds[0]);
            }
            setSelectedBillingRuleIds([]);
            setSelectedBillingRuleId('');
            await fetchBillingRulesForSystemApi(selectedSystemApiId);
            alert(targetIds.length > 1
                ? t(`已删除 ${targetIds.length} 条定价规则`, `Deleted ${targetIds.length} pricing rules`)
                : t('定价规则已删除', 'Pricing rule deleted'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('删除定价规则失败', 'Failed to delete pricing rule'));
        }
    };

    const handleBatchResetBillingRuleChargeMultiplier = async () => {
        const selectedApiId = Number(selectedSystemApiId || 0);
        const parsedMinMul = Number.parseFloat(String(batchResetMinMultiplier || '').trim());
        const parsedMaxMul = Number.parseFloat(String(batchResetMaxMultiplier || '').trim());
        const parsedDefaultMul = Number.parseFloat(String(batchResetDefaultMultiplier || '').trim());
        const parsedBinSize = Number.parseInt(String(batchResetBinSizeCredits || '').trim(), 10);
        const parsedBinDrop = Number.parseFloat(String(batchResetBinDropMultiplier || '').trim());
        const parsedMax = Number.parseInt(String(batchResetMaxIncreaseCredits || '').trim(), 10);

        const minMul = Number.isFinite(parsedMinMul) ? parsedMinMul : 1.1;
        const maxMul = Number.isFinite(parsedMaxMul) ? parsedMaxMul : 2.0;
        const defaultMul = Number.isFinite(parsedDefaultMul) ? parsedDefaultMul : 2.0;
        const binSize = Number.isFinite(parsedBinSize) && parsedBinSize > 0 ? parsedBinSize : 10;
        const binDrop = Number.isFinite(parsedBinDrop) && parsedBinDrop > 0 ? parsedBinDrop : 0.1;
        const maxIncreaseCredits = Number.isFinite(parsedMax) && parsedMax >= 0 ? parsedMax : 50;
        const scopeHint = selectedApiId > 0
            ? t('当前筛选 API 的规则', 'rules under current selected API')
            : t('全部规则', 'all rules');
        const ok = await confirmUiMessage(
            t(
                `确认重置${scopeHint}倍率？区间 ${minMul}-${maxMul}，每 ${binSize} 积分一箱，按每箱降幅 ${binDrop} 线性下降；单条规则相对原积分增幅上限 ${maxIncreaseCredits}。`,
                `Reset multipliers for ${scopeHint}? Range ${minMul}-${maxMul}, ${binSize} credits per bin with linear drop ${binDrop} per bin; per-rule increase cap is ${maxIncreaseCredits}.`
            )
        );
        if (!ok) return;

        setIsBatchResetMultiplierLoading(true);
        try {
            const result = await resetSystemApiBillingRuleChargeMultipliersManage({
                system_api_ids: selectedApiId > 0 ? [selectedApiId] : [],
                min_multiplier: minMul,
                max_multiplier: maxMul,
                default_multiplier: defaultMul,
                bin_size_credits: binSize,
                bin_drop_multiplier: binDrop,
                max_total_increase_credits: maxIncreaseCredits,
            });
            await fetchBillingRulesForSystemApi(selectedSystemApiId);
            alert(
                t(
                    `重置完成：共 ${Number(result?.total_rules || 0)} 条，更新 ${Number(result?.updated_rules || 0)} 条。成本范围 ${Number(result?.min_cost || 0)}-${Number(result?.max_cost || 0)}。分箱参数：每箱 ${Number(result?.bin_size_credits || binSize)} 积分，降幅 ${Number(result?.bin_drop_multiplier || binDrop)}。单条最大增幅 ${Number(result?.max_rule_increase_credits || 0).toFixed(2)} / ${Number(result?.max_total_increase_credits || maxIncreaseCredits)} 积分。`,
                    `Reset completed: total ${Number(result?.total_rules || 0)}, updated ${Number(result?.updated_rules || 0)}. Cost range ${Number(result?.min_cost || 0)}-${Number(result?.max_cost || 0)}. Binning params: ${Number(result?.bin_size_credits || binSize)} credits/bin, drop ${Number(result?.bin_drop_multiplier || binDrop)}. Max per-rule increase ${Number(result?.max_rule_increase_credits || 0).toFixed(2)} / ${Number(result?.max_total_increase_credits || maxIncreaseCredits)}.`
                )
            );
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('批量重置倍率失败', 'Failed to reset charge multipliers'));
        } finally {
            setIsBatchResetMultiplierLoading(false);
        }
    };

    const handleRecomputePriceCache = async () => {
        const selectedApiId = Number(selectedSystemApiId || 0);
        const scopeHint = selectedApiId > 0
            ? t('当前选中的 System API', 'current selected System API')
            : t('全部 System API', 'all System APIs');
        const ok = await confirmUiMessage(
            t(
                `确认对${scopeHint}执行“价格区间/样本均价”预计算吗？`,
                `Recompute precomputed price range/sample-average for ${scopeHint}?`
            )
        );
        if (!ok) return;

        setIsPriceCacheRecomputeLoading(true);
        try {
            const result = await recomputeSystemApiPriceCacheManage(selectedApiId > 0 ? [selectedApiId] : []);
            await fetchSystemApiManageRows();
            await fetchBillingRulesForSystemApi(selectedSystemApiId);
            alert(
                t(
                    `预计算完成：目标 ${Number(result?.target_count || 0)} 个 API，模型级更新 ${Number(result?.changed_model || 0)} 条，提供方级更新 ${Number(result?.changed_provider || 0)} 条。`,
                    `Precompute completed: target ${Number(result?.target_count || 0)} APIs, model-level updated ${Number(result?.changed_model || 0)}, provider-level updated ${Number(result?.changed_provider || 0)}.`
                )
            );
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('预计算失败', 'Precompute failed'));
        } finally {
            setIsPriceCacheRecomputeLoading(false);
        }
    };

    const handleConfirmManualKiePricing = () => {
        if (!String(kiePricingManualText || '').trim()) {
            alert(t('请先粘贴要分析的 KIE 定价内容', 'Please paste KIE pricing content to analyze first'));
            return;
        }
        setIsKiePricingConfirmed(true);
        alert(t('已确认手工输入内容，现在可以进行匹配与规则生成', 'Manual input confirmed. You can now run matching and rule generation.'));
    };

    const handleRunKiePricingAssistant = async (applyBaseRules = false) => {
        if (!isKiePricingConfirmed || !String(kiePricingManualText || '').trim()) {
            alert(t('请先粘贴并确认 KIE 定价内容', 'Please paste and confirm KIE pricing content first'));
            return;
        }
        try {
            const selectedIds = (selectedKieSuggestionIds || []).map((id) => Number(id || 0)).filter((id) => id > 0);

            // Step-3 optimization: if suggestions already exist, apply directly without regenerating.
            if (applyBaseRules && Array.isArray(kiePricingResult?.matches) && kiePricingResult.matches.length > 0) {
                setIsKiePricingLoading(true);
                const applyResult = await ({
                    provider_filter: kiePricingResult?.provider_filter || kiePricingProviderFilter,
                    include_deprecated: false,
                    selected_system_api_ids: selectedIds,
                    matches: kiePricingResult.matches,
                });
                setKiePricingResult((prev) => ({ ...(prev || {}), ...(applyResult || {}) }));
                await fetchBillingRulesForSystemApi(selectedSystemApiId);

                const appliedCount = Number(applyResult?.applied_count || 0);
                const applyStatus = String(applyResult?.apply_status || 'not_requested');
                if (appliedCount > 0 && applyStatus === 'applied') {
                    alert(t(`KIE 基础规则已写入 ${appliedCount} 个模型`, `KIE base rules were written to ${appliedCount} models`));
                } else {
                    alert(
                        (applyResult?.apply_message && String(applyResult.apply_message).trim())
                        || t('本次未写入任何基础规则，请检查匹配结果或勾选项', 'No base rules were written this time. Check matches or selected items.')
                    );
                }
                return;
            }

            const rawTablesText = String(kiePricingManualTablesText || '').trim();

            setIsKiePricingLoading(true);
            const result = await ({
                url: kiePricingUrl,
                provider_filter: kiePricingProviderFilter,
                include_deprecated: false,
                apply_base_rules: !!applyBaseRules,
                selected_system_api_ids: selectedIds,
                confirmed: true,
                confirmed_pricing_text: String(kiePricingManualText || ''),
                confirmed_pricing_tables_text: rawTablesText,
            });
            setKiePricingResult(result || null);
            setSelectedKieSuggestionIds((Array.isArray(result?.matches) ? result.matches : []).map((x) => Number(x?.system_api_id || 0)).filter((id) => id > 0));
            if (applyBaseRules) {
                await fetchBillingRulesForSystemApi(selectedSystemApiId);
            }
            if (applyBaseRules) {
                const appliedCount = Number(result?.applied_count || 0);
                const applyStatus = String(result?.apply_status || 'not_requested');
                if (appliedCount > 0 && applyStatus === 'applied') {
                    alert(t(`KIE 基础规则已写入 ${appliedCount} 个模型`, `KIE base rules were written to ${appliedCount} models`));
                } else {
                    alert(
                        (result?.apply_message && String(result.apply_message).trim())
                        || t('本次未写入任何基础规则，请检查匹配结果或勾选项', 'No base rules were written this time. Check matches or selected items.')
                    );
                }
            } else {
                alert(t('KIE 规则建议已生成', 'KIE pricing suggestions generated'));
            }
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('执行 KIE 定价助手失败', 'Failed to run KIE pricing assistant'));
        } finally {
            setIsKiePricingLoading(false);
        }
    };

    useEffect(() => {
        setIsKiePricingConfirmed(false);
        setKiePricingResult(null);
        setSelectedKieSuggestionIds([]);
        closeKieSuggestionEditor();
    }, [kiePricingUrl]);

    useEffect(() => {
        setIsKiePricingConfirmed(false);
        setKiePricingResult(null);
        setSelectedKieSuggestionIds([]);
        closeKieSuggestionEditor();
    }, [kiePricingManualText, kiePricingManualTablesText]);

    const toggleKieSuggestionSelection = (systemApiId, checked) => {
        const id = Number(systemApiId || 0);
        if (!id) return;
        setSelectedKieSuggestionIds((prev) => {
            const set = new Set((prev || []).map((v) => Number(v)).filter((v) => v > 0));
            if (checked) set.add(id);
            else set.delete(id);
            return Array.from(set);
        });
    };

    const toggleAllKieSuggestions = (checked) => {
        if (!Array.isArray(kiePricingResult?.matches)) {
            setSelectedKieSuggestionIds([]);
            return;
        }
        if (!checked) {
            setSelectedKieSuggestionIds([]);
            return;
        }
        setSelectedKieSuggestionIds(kiePricingResult.matches.map((x) => Number(x?.system_api_id || 0)).filter((id) => id > 0));
    };

    const closeKieSuggestionEditor = () => {
        setIsKieSuggestionEditOpen(false);
        setEditingKieSuggestionIndex(-1);
        setEditingKieSuggestionMeta({ system_api_id: '', model: '' });
        setKieSuggestionEditForm({
            target_system_api_id: '',
            billing_unit_type: 'per_call',
            billing_cost: '0',
            billing_cost_input: '0',
            billing_cost_output: '0',
            granular_rules: [],
        });
    };

    const createEmptyKieGranularRule = (fallbackUnitType = 'per_call') => ({
        name: '',
        billing_unit_type: normalizeApiPricingUnitType(fallbackUnitType),
        billing_cost: '0',
        billing_cost_input: '0',
        billing_cost_output: '0',
        width_min: '',
        width_max: '',
        height_min: '',
        height_max: '',
        pixels_min: '',
        pixels_max: '',
        generation_mode: '',
        input_format: '',
        output_format: '',
        priority: '1000',
        applies_to_text: false,
        applies_to_image: true,
        applies_to_video: false,
        extra_conditions: {},
    });

    const normalizeKieGranularRuleForEdit = (rule, fallbackUnitType = 'per_call') => {
        const source = (rule && typeof rule === 'object') ? rule : {};
        return {
            name: String(source?.name || ''),
            billing_unit_type: normalizeApiPricingUnitType(source?.billing_unit_type || fallbackUnitType),
            billing_cost: String(toNonNegativeInt(source?.billing_cost ?? source?.cost ?? 0)),
            billing_cost_input: String(toNonNegativeInt(source?.billing_cost_input ?? source?.cost_input ?? 0)),
            billing_cost_output: String(toNonNegativeInt(source?.billing_cost_output ?? source?.cost_output ?? 0)),
            width_min: source?.width_min === null || source?.width_min === undefined ? '' : String(toNonNegativeInt(source.width_min)),
            width_max: source?.width_max === null || source?.width_max === undefined ? '' : String(toNonNegativeInt(source.width_max)),
            height_min: source?.height_min === null || source?.height_min === undefined ? '' : String(toNonNegativeInt(source.height_min)),
            height_max: source?.height_max === null || source?.height_max === undefined ? '' : String(toNonNegativeInt(source.height_max)),
            pixels_min: source?.pixels_min === null || source?.pixels_min === undefined ? '' : String(toNonNegativeInt(source.pixels_min)),
            pixels_max: source?.pixels_max === null || source?.pixels_max === undefined ? '' : String(toNonNegativeInt(source.pixels_max)),
            generation_mode: String(source?.generation_mode || ''),
            input_format: String(source?.input_format || ''),
            output_format: String(source?.output_format || ''),
            priority: source?.priority === null || source?.priority === undefined ? '1000' : String(toNonNegativeInt(source.priority)),
            applies_to_text: !!source?.applies_to_text,
            applies_to_image: source?.applies_to_image === undefined ? true : !!source?.applies_to_image,
            applies_to_video: !!source?.applies_to_video,
            extra_conditions: (source?.extra_conditions && typeof source.extra_conditions === 'object') ? source.extra_conditions : {},
        };
    };

    const addKieGranularRuleForEdit = () => {
        setKieSuggestionEditForm((prev) => ({
            ...prev,
            granular_rules: [
                ...(Array.isArray(prev?.granular_rules) ? prev.granular_rules : []),
                createEmptyKieGranularRule(prev?.billing_unit_type || 'per_call'),
            ],
        }));
    };

    const removeKieGranularRuleForEdit = (ruleIndex) => {
        setKieSuggestionEditForm((prev) => ({
            ...prev,
            granular_rules: (Array.isArray(prev?.granular_rules) ? prev.granular_rules : []).filter((_, idx) => idx !== ruleIndex),
        }));
    };

    const updateKieGranularRuleForEdit = (ruleIndex, field, value) => {
        setKieSuggestionEditForm((prev) => ({
            ...prev,
            granular_rules: (Array.isArray(prev?.granular_rules) ? prev.granular_rules : []).map((item, idx) => {
                if (idx !== ruleIndex) return item;
                if (field === 'billing_unit_type') {
                    return { ...item, [field]: normalizeApiPricingUnitType(value) };
                }
                return { ...item, [field]: value };
            }),
        }));
    };

    const openKieSuggestionEditor = (rowIndex) => {
        const row = (Array.isArray(kiePricingResult?.matches) ? kiePricingResult.matches : [])[rowIndex];
        if (!row) return;
        setEditingKieSuggestionIndex(rowIndex);
        setEditingKieSuggestionMeta({
            system_api_id: String(row?.system_api_id || ''),
            model: String(row?.model || ''),
        });
        setKieSuggestionEditForm({
            target_system_api_id: String(row?.system_api_id || ''),
            billing_unit_type: normalizeApiPricingUnitType(row?.base_rule?.billing_unit_type),
            billing_cost: String(toNonNegativeInt(row?.base_rule?.billing_cost ?? 0)),
            billing_cost_input: String(toNonNegativeInt(row?.base_rule?.billing_cost_input ?? 0)),
            billing_cost_output: String(toNonNegativeInt(row?.base_rule?.billing_cost_output ?? 0)),
            granular_rules: (Array.isArray(row?.granular_rules) ? row.granular_rules : []).map((gr) =>
                normalizeKieGranularRuleForEdit(gr, row?.base_rule?.billing_unit_type || 'per_call')
            ),
        });
        setIsKieSuggestionEditOpen(true);
    };

    const saveKieSuggestionEditor = () => {
        const rowIndex = Number(editingKieSuggestionIndex);
        if (!Number.isInteger(rowIndex) || rowIndex < 0) {
            closeKieSuggestionEditor();
            return;
        }
        const targetSystemApiId = Number(kieSuggestionEditForm.target_system_api_id || 0);
        if (targetSystemApiId <= 0) {
            alert(t('请选择目标 System API', 'Please select a target System API'));
            return;
        }
        const sourceRow = (Array.isArray(kiePricingResult?.matches) ? kiePricingResult.matches : [])[rowIndex];
        const oldSystemApiId = Number(sourceRow?.system_api_id || 0);
        const selectedApiRow = (Array.isArray(systemApiRows) ? systemApiRows : []).find((x) => Number(x?.id || 0) === targetSystemApiId);
        const toOptionalNonNegativeInt = (value) => {
            const text = String(value ?? '').trim();
            if (!text) return null;
            return toNonNegativeInt(text);
        };
        const normalizedGranularRules = (Array.isArray(kieSuggestionEditForm?.granular_rules) ? kieSuggestionEditForm.granular_rules : [])
            .map((item, idx) => {
                const source = (item && typeof item === 'object') ? item : {};
                const nameText = String(source?.name || '').trim() || `Granular Rule ${idx + 1}`;
                return {
                    name: nameText,
                    billing_unit_type: normalizeApiPricingUnitType(source?.billing_unit_type || kieSuggestionEditForm.billing_unit_type || 'per_call'),
                    billing_cost: toNonNegativeInt(source?.billing_cost ?? 0),
                    billing_cost_input: toNonNegativeInt(source?.billing_cost_input ?? 0),
                    billing_cost_output: toNonNegativeInt(source?.billing_cost_output ?? 0),
                    width_min: toOptionalNonNegativeInt(source?.width_min),
                    width_max: toOptionalNonNegativeInt(source?.width_max),
                    height_min: toOptionalNonNegativeInt(source?.height_min),
                    height_max: toOptionalNonNegativeInt(source?.height_max),
                    pixels_min: toOptionalNonNegativeInt(source?.pixels_min),
                    pixels_max: toOptionalNonNegativeInt(source?.pixels_max),
                    generation_mode: String(source?.generation_mode || '').trim() || null,
                    input_format: String(source?.input_format || '').trim() || null,
                    output_format: String(source?.output_format || '').trim() || null,
                    priority: toNonNegativeInt(source?.priority ?? 1000),
                    applies_to_text: !!source?.applies_to_text,
                    applies_to_image: source?.applies_to_image === undefined ? true : !!source?.applies_to_image,
                    applies_to_video: !!source?.applies_to_video,
                    extra_conditions: (source?.extra_conditions && typeof source.extra_conditions === 'object') ? source.extra_conditions : {},
                };
            })
            .filter((item) => {
                const hasCost = toNonNegativeInt(item?.billing_cost ?? 0) > 0;
                const hasDimension = [item?.width_min, item?.width_max, item?.height_min, item?.height_max, item?.pixels_min, item?.pixels_max]
                    .some((v) => Number(v || 0) > 0);
                const hasMeta = String(item?.generation_mode || '').trim() || String(item?.input_format || '').trim() || String(item?.output_format || '').trim();
                return hasCost || hasDimension || !!hasMeta;
            });
        setKiePricingResult((prev) => {
            if (!prev || !Array.isArray(prev.matches)) return prev;
            const nextMatches = prev.matches.map((row, idx) => {
                if (idx !== rowIndex) return row;
                const currentBaseRule = (row?.base_rule && typeof row.base_rule === 'object') ? row.base_rule : {};
                return {
                    ...row,
                    system_api_id: targetSystemApiId,
                    provider: selectedApiRow?.provider || row?.provider,
                    category: selectedApiRow?.category || row?.category,
                    model: selectedApiRow?.model || row?.model,
                    base_rule: {
                        ...currentBaseRule,
                        billing_unit_type: normalizeApiPricingUnitType(kieSuggestionEditForm.billing_unit_type),
                        billing_cost: toNonNegativeInt(kieSuggestionEditForm.billing_cost),
                        billing_cost_input: toNonNegativeInt(kieSuggestionEditForm.billing_cost_input),
                        billing_cost_output: toNonNegativeInt(kieSuggestionEditForm.billing_cost_output),
                    },
                    granular_rules: normalizedGranularRules,
                };
            });
            return {
                ...prev,
                matches: nextMatches,
            };
        });
        if (oldSystemApiId > 0 && oldSystemApiId !== targetSystemApiId) {
            setSelectedKieSuggestionIds((prev) => {
                const set = new Set((prev || []).map((v) => Number(v)).filter((v) => v > 0));
                if (set.has(oldSystemApiId)) {
                    set.delete(oldSystemApiId);
                    set.add(targetSystemApiId);
                }
                return Array.from(set);
            });
        }
        closeKieSuggestionEditor();
    };

    const formatKieGranularRuleSummary = (rule) => {
        if (!rule || typeof rule !== 'object') return '-';
        const label = String(rule?.name || '').trim();
        const wMin = Number(rule?.width_min || 0);
        const wMax = Number(rule?.width_max || 0);
        const hMin = Number(rule?.height_min || 0);
        const hMax = Number(rule?.height_max || 0);
        const cost = toNonNegativeInt(rule?.billing_cost ?? 0);
        const unit = normalizeApiPricingUnitType(rule?.billing_unit_type);
        const sizeText = (wMin > 0 && hMin > 0)
            ? `${wMin}${wMax > 0 && wMax !== wMin ? `-${wMax}` : ''}x${hMin}${hMax > 0 && hMax !== hMin ? `-${hMax}` : ''}`
            : '';
        if (label && sizeText) return `${label}: ${sizeText} -> ${cost} ${unit}`;
        if (label) return `${label}: ${cost} ${unit}`;
        if (sizeText) return `${sizeText} -> ${cost} ${unit}`;
        return `${cost} ${unit}`;
    };

    useEffect(() => {
        if (!selectedSystemApiId) {
            setSystemApiForm({
                name: '',
                category: 'LLM',
                provider: '',
                api_key: '',
                base_url: '',
                model: '',
                base_model: '',
                retry_group: '',
                retry_price_group: '',
                explicit_selection: false,
                strict_provider: false,
                moderation_endpoint: '',
                moderation_user_id: '',
                moderation_aes_key: '',
                config: '{}',
                is_active: false,
                deprecated: false,
                tags: '',
                generation_modes: '',
                input_formats: '',
                output_format: '',
                supported_resolutions: '',
                aspect_ratios: '',
                max_images_per_call: '',
                reference_image_limit: '',
                reference_video_limit: '',
                durations_seconds: '',
                max_duration: '',
                fps_options: '',
                has_audio: 'any',
                has_google_search: 'any',
                has_thinking_mode: 'any',
                mode_values: '',
                capability_flags: '{}',
                text_capabilities: '{}',
                image_capabilities: '{}',
                video_capabilities: '{}',
                digital_human_capabilities: '{}',
                voice_capabilities: '{}',
                music_capabilities: '{}',
                pricing_unit: '',
                token_billing_supported: 'any',
                input_token_price: '',
                output_token_price: '',
                per_resolution_price_map: '{}',
                per_duration_price_map: '{}',
                has_tiered_pricing: 'any',
                free_quota: '',
                currency: '',
                billing_unit_type: 'per_call',
                billing_cost: '0',
                billing_cost_input: '0',
                billing_cost_output: '0',
            });
            return;
        }
        const row = systemApiRows.find((item) => String(item.id) === String(selectedSystemApiId));
        if (!row) return;
        const pricing = getApiPricing(row);
        setSystemApiForm({
            name: row.name || '',
            category: row.category || 'LLM',
            provider: row.provider || '',
            api_key: row.api_key || '',
            base_url: row.base_url || '',
            model: row.model || '',
            base_model: row.base_model || '',
            retry_group: getSystemApiRetryGroup(row),
            explicit_selection: getSystemApiExplicitSelection(row),
            strict_provider: getSystemApiStrictProvider(row),
            retry_price_group: getSystemApiRetryPriceGroup(row),
            moderation_endpoint: getSystemApiModerationEndpoint(row),
            moderation_user_id: getSystemApiModerationUserId(row),
            moderation_aes_key: getSystemApiModerationAesKey(row),
            config: safeJsonStr(row.config) || '{}',
            is_active: !!row.is_active,
            deprecated: !!row.deprecated,
            tags: Array.isArray(row.tags) ? row.tags.join(', ') : safeJsonStr(row.tags),
            generation_modes: Array.isArray(row.generation_modes) ? row.generation_modes.join(', ') : '',
            input_formats: Array.isArray(row.input_formats) ? row.input_formats.join(', ') : '',
            output_format: String(row.output_format || ''),
            supported_resolutions: Array.isArray(row.supported_resolutions) ? row.supported_resolutions.join(', ') : '',
            aspect_ratios: Array.isArray(row.aspect_ratios) ? row.aspect_ratios.join(', ') : '',
            max_images_per_call: row.max_images_per_call === null || row.max_images_per_call === undefined ? '' : String(row.max_images_per_call),
            reference_image_limit: String(row.reference_image_limit || ''),
            reference_video_limit: String(row.reference_video_limit || ''),
            durations_seconds: Array.isArray(row.durations_seconds) ? row.durations_seconds.join(', ') : '',
            max_duration: row.max_duration === null || row.max_duration === undefined ? '' : String(row.max_duration),
            fps_options: Array.isArray(row.fps_options) ? row.fps_options.join(', ') : '',
            has_audio: row.has_audio === true ? 'true' : (row.has_audio === false ? 'false' : 'any'),
            has_google_search: row.has_google_search === true ? 'true' : (row.has_google_search === false ? 'false' : 'any'),
            has_thinking_mode: row.has_thinking_mode === true ? 'true' : (row.has_thinking_mode === false ? 'false' : 'any'),
            mode_values: Array.isArray(row.mode_values) ? row.mode_values.join(', ') : '',
            capability_flags: safeJsonStr(row.capability_flags) || '{}',
            text_capabilities: safeJsonStr(row.text_capabilities) || '{}',
            image_capabilities: safeJsonStr(row.image_capabilities) || '{}',
            video_capabilities: safeJsonStr(row.video_capabilities) || '{}',
            digital_human_capabilities: safeJsonStr(row.digital_human_capabilities) || '{}',
            voice_capabilities: safeJsonStr(row.voice_capabilities) || '{}',
            music_capabilities: safeJsonStr(row.music_capabilities) || '{}',
            pricing_unit: String(row.pricing_unit || ''),
            token_billing_supported: row.token_billing_supported === true ? 'true' : (row.token_billing_supported === false ? 'false' : 'any'),
            input_token_price: row.input_token_price === null || row.input_token_price === undefined ? '' : String(row.input_token_price),
            output_token_price: row.output_token_price === null || row.output_token_price === undefined ? '' : String(row.output_token_price),
            per_resolution_price_map: safeJsonStr(row.per_resolution_price_map) || '{}',
            per_duration_price_map: safeJsonStr(row.per_duration_price_map) || '{}',
            has_tiered_pricing: row.has_tiered_pricing === true ? 'true' : (row.has_tiered_pricing === false ? 'false' : 'any'),
            free_quota: String(row.free_quota || ''),
            currency: String(row.currency || ''),
            billing_unit_type: pricing.unit_type,
            billing_cost: String(pricing.cost),
            billing_cost_input: String(pricing.cost_input),
            billing_cost_output: String(pricing.cost_output),
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

    const matchesSystemApiMetadataFilter = (value, filterValue) => {
        const normalizedValue = String(value || '').trim();
        if (filterValue === 'all') return true;
        if (filterValue === SYSTEM_API_FILTER_HAS_VALUE) return normalizedValue.length > 0;
        if (filterValue === SYSTEM_API_FILTER_EMPTY_VALUE) return normalizedValue.length === 0;
        return normalizedValue === String(filterValue || '').trim();
    };

    const systemApiRetryGroupOptions = React.useMemo(() => {
        const set = new Set();
        systemApiRows.forEach((row) => {
            if (systemApiFilterCategory !== 'all' && String(row?.category || '') !== systemApiFilterCategory) return;
            if (systemApiFilterProvider !== 'all' && String(row?.provider || '') !== systemApiFilterProvider) return;
            const retryGroup = getSystemApiRetryGroup(row);
            if (retryGroup) set.add(retryGroup);
        });
        return Array.from(set).sort((a, b) => a.localeCompare(b));
    }, [systemApiRows, systemApiFilterCategory, systemApiFilterProvider]);

    const systemApiRetryPriceGroupOptions = React.useMemo(() => {
        const set = new Set();
        systemApiRows.forEach((row) => {
            if (systemApiFilterCategory !== 'all' && String(row?.category || '') !== systemApiFilterCategory) return;
            if (systemApiFilterProvider !== 'all' && String(row?.provider || '') !== systemApiFilterProvider) return;
            if (!matchesSystemApiMetadataFilter(getSystemApiRetryGroup(row), systemApiFilterRetryGroup)) return;
            const retryPriceGroup = getSystemApiRetryPriceGroup(row);
            if (retryPriceGroup) set.add(retryPriceGroup);
        });
        return Array.from(set).sort((a, b) => a.localeCompare(b));
    }, [systemApiRows, systemApiFilterCategory, systemApiFilterProvider, systemApiFilterRetryGroup]);

    const getSystemApiCapabilityInfo = (row) => {
        const category = String(row?.category || '').trim();
        const provider = String(row?.provider || '').trim();
        if (!row || !provider || !category || category.startsWith('System_')) {
            return {
                callable: false,
                state: 'system',
                label: t('系统配置', 'System Config'),
                detail: t('非业务 API 调用入口', 'Not a business API runtime entry'),
            };
        }
        if (isSystemApiDeprecated(row)) {
            return {
                callable: false,
                state: 'deprecated',
                label: t('已弃用', 'Deprecated'),
                detail: t('该配置已被 system_api_settings.deprecated 标记为弃用', 'This configuration is disabled by system_api_settings.deprecated'),
            };
        }

        const cfg = getSystemApiConfig(row);
        const runtimeEndpoint = String(cfg?.endpoint || cfg?.endpoint_hint || '').trim();
        const runtimeActivation = String(cfg?.runtime_activation || '').trim();
        if (runtimeEndpoint || runtimeActivation) {
            return {
                callable: true,
                state: 'callable',
                label: t('已启用', 'Enabled'),
                detail: runtimeEndpoint
                    ? t('未弃用，且已声明运行时 endpoint', 'Not deprecated, with a declared runtime endpoint')
                    : t('未弃用，且已声明运行时激活方式', 'Not deprecated, with a declared runtime activation'),
            };
        }

        return {
            callable: true,
            state: 'staging_only',
            label: t('已启用', 'Enabled'),
            detail: t('未弃用，当前按 system_api_settings 记录参与前后端选择；建议继续补充 endpoint 与能力元数据', 'Not deprecated, so it participates in frontend/backend selection; add endpoint and capability metadata when available'),
        };
    };

    const systemApiProviderSummaryRows = React.useMemo(() => {
        const bucket = new Map();
        (systemApiRows || []).forEach((row) => {
            const category = String(row?.category || '').trim();
            if (!category || category.startsWith('System_')) return;
            if (systemApiFilterCategory !== 'all' && category !== systemApiFilterCategory) return;

            const provider = String(row?.provider || '').trim();
            if (!provider) return;

            if (!bucket.has(provider)) {
                bucket.set(provider, {
                    provider,
                    total_rows: 0,
                    callable_rows: 0,
                    deprecated_rows: 0,
                    default_rows: 0,
                    staging_only_rows: 0,
                    categories: new Set(),
                });
            }

            const summary = bucket.get(provider);
            const capability = getSystemApiCapabilityInfo(row);
            summary.total_rows += 1;
            summary.categories.add(category);
            if (capability.callable) summary.callable_rows += 1;
            if (capability.state === 'staging_only') summary.staging_only_rows += 1;
            if (isSystemApiDeprecated(row)) summary.deprecated_rows += 1;
            if (row?.is_active) summary.default_rows += 1;
        });

        return Array.from(bucket.values())
            .map((item) => ({
                ...item,
                categories: Array.from(item.categories).sort((a, b) => a.localeCompare(b)),
                has_callable_entry: item.callable_rows > 0,
            }))
            .sort((a, b) => String(a.provider || '').localeCompare(String(b.provider || '')));
    }, [systemApiRows, systemApiFilterCategory]);

    const filteredSystemApiRows = React.useMemo(() => {
        return systemApiRows.filter((row) => {
            if (systemApiFilterCategory !== 'all' && String(row?.category || '') !== systemApiFilterCategory) return false;
            if (systemApiFilterProvider !== 'all' && String(row?.provider || '') !== systemApiFilterProvider) return false;
            if (!matchesSystemApiMetadataFilter(getSystemApiRetryGroup(row), systemApiFilterRetryGroup)) return false;
            if (!matchesSystemApiMetadataFilter(getSystemApiRetryPriceGroup(row), systemApiFilterRetryPriceGroup)) return false;
            if (systemApiCapabilityFilter === 'callable' && !getSystemApiCapabilityInfo(row).callable) return false;
            if (systemApiCapabilityFilter === 'not_callable' && getSystemApiCapabilityInfo(row).callable) return false;
            if (systemApiCapabilityFilter === 'staging_only' && getSystemApiCapabilityInfo(row).state !== 'staging_only') return false;
            return true;
        });
    }, [systemApiRows, systemApiFilterCategory, systemApiFilterProvider, systemApiFilterRetryGroup, systemApiFilterRetryPriceGroup, systemApiCapabilityFilter]);

    function isSystemApiDeprecated(row) {
        if (typeof row?.deprecated === 'boolean') return row.deprecated;
        return false;
    }

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
        if (activeTab === 'pricing_rules') return;
        if (!visibleSystemApiRows.length) {
            setSelectedSystemApiId('');
            return;
        }
        const existsInFiltered = visibleSystemApiRows.some((row) => String(row.id) === String(selectedSystemApiId));
        if (!existsInFiltered) {
            setSelectedSystemApiId(String(visibleSystemApiRows[0].id));
        }
    }, [visibleSystemApiRows, selectedSystemApiId, activeTab]);

    const parseJsonFieldSafe = (text) => {
        const trimmed = String(text || '').trim();
        if (!trimmed) return undefined;
        try { return JSON.parse(trimmed); } catch { return undefined; }
    };

    const parseJsonObjectFieldSafe = (text) => {
        const parsed = parseJsonFieldSafe(text);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return undefined;
        return parsed;
    };

    const parseCsvArrayField = (text) => {
        const trimmed = String(text || '').trim();
        if (!trimmed) return undefined;
        return trimmed.split(',').map((s) => String(s || '').trim()).filter(Boolean);
    };

    const parseCsvNumberArrayField = (text) => {
        const arr = parseCsvArrayField(text);
        if (!arr || arr.length === 0) return undefined;
        const out = arr.map((x) => Number(x)).filter((n) => Number.isFinite(n));
        return out.length > 0 ? out : undefined;
    };

    const parseTagsField = (text) => {
        const trimmed = String(text || '').trim();
        if (!trimmed) return undefined;
        // try JSON array first
        try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) return parsed;
        } catch { /* ignore */ }
        // fallback: comma-separated
        return trimmed.split(',').map(s => s.trim()).filter(Boolean);
    };

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
                api_key: String(systemApiForm.api_key || '').trim() || undefined,
                base_url: String(systemApiForm.base_url || '').trim() || undefined,
                model: String(systemApiForm.model || '').trim() || undefined,
                base_model: String(systemApiForm.base_model || '').trim() || undefined,
                config: buildSystemApiConfigPayload(),
                is_active: !!systemApiForm.is_active,
                tags: parseTagsField(systemApiForm.tags),
                generation_modes: parseCsvArrayField(systemApiForm.generation_modes),
                input_formats: parseCsvArrayField(systemApiForm.input_formats),
                output_format: toNullableText(systemApiForm.output_format),
                supported_resolutions: parseCsvArrayField(systemApiForm.supported_resolutions),
                aspect_ratios: parseCsvArrayField(systemApiForm.aspect_ratios),
                max_images_per_call: toNullableInt(systemApiForm.max_images_per_call),
                reference_image_limit: toNullableText(systemApiForm.reference_image_limit),
                reference_video_limit: toNullableText(systemApiForm.reference_video_limit),
                durations_seconds: parseCsvNumberArrayField(systemApiForm.durations_seconds),
                max_duration: toNullableInt(systemApiForm.max_duration),
                fps_options: parseCsvNumberArrayField(systemApiForm.fps_options),
                has_audio: toNullableBool(systemApiForm.has_audio),
                has_google_search: toNullableBool(systemApiForm.has_google_search),
                has_thinking_mode: toNullableBool(systemApiForm.has_thinking_mode),
                mode_values: parseCsvArrayField(systemApiForm.mode_values),
                capability_flags: parseJsonObjectFieldSafe(systemApiForm.capability_flags),
                text_capabilities: parseJsonObjectFieldSafe(systemApiForm.text_capabilities),
                image_capabilities: parseJsonObjectFieldSafe(systemApiForm.image_capabilities),
                video_capabilities: parseJsonObjectFieldSafe(systemApiForm.video_capabilities),
                digital_human_capabilities: parseJsonObjectFieldSafe(systemApiForm.digital_human_capabilities),
                voice_capabilities: parseJsonObjectFieldSafe(systemApiForm.voice_capabilities),
                music_capabilities: parseJsonObjectFieldSafe(systemApiForm.music_capabilities),
                pricing_unit: toNullableText(systemApiForm.pricing_unit),
                token_billing_supported: toNullableBool(systemApiForm.token_billing_supported),
                input_token_price: toNullableFloat(systemApiForm.input_token_price),
                output_token_price: toNullableFloat(systemApiForm.output_token_price),
                per_resolution_price_map: parseJsonObjectFieldSafe(systemApiForm.per_resolution_price_map),
                per_duration_price_map: parseJsonObjectFieldSafe(systemApiForm.per_duration_price_map),
                has_tiered_pricing: toNullableBool(systemApiForm.has_tiered_pricing),
                free_quota: toNullableText(systemApiForm.free_quota),
                currency: toNullableText(systemApiForm.currency),
                billing_unit_type: normalizeApiPricingUnitType(systemApiForm.billing_unit_type),
                billing_cost: toNonNegativeInt(systemApiForm.billing_cost),
                billing_cost_input: toNonNegativeInt(systemApiForm.billing_cost_input),
                billing_cost_output: toNonNegativeInt(systemApiForm.billing_cost_output),
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
                api_key: String(systemApiForm.api_key || '').trim() || undefined,
                base_url: String(systemApiForm.base_url || '').trim() || undefined,
                model: String(systemApiForm.model || '').trim() || undefined,
                base_model: String(systemApiForm.base_model || '').trim() || undefined,
                config: buildSystemApiConfigPayload(),
                is_active: !!systemApiForm.is_active,
                tags: parseTagsField(systemApiForm.tags),
                generation_modes: parseCsvArrayField(systemApiForm.generation_modes),
                input_formats: parseCsvArrayField(systemApiForm.input_formats),
                output_format: toNullableText(systemApiForm.output_format),
                supported_resolutions: parseCsvArrayField(systemApiForm.supported_resolutions),
                aspect_ratios: parseCsvArrayField(systemApiForm.aspect_ratios),
                max_images_per_call: toNullableInt(systemApiForm.max_images_per_call),
                reference_image_limit: toNullableText(systemApiForm.reference_image_limit),
                reference_video_limit: toNullableText(systemApiForm.reference_video_limit),
                durations_seconds: parseCsvNumberArrayField(systemApiForm.durations_seconds),
                max_duration: toNullableInt(systemApiForm.max_duration),
                fps_options: parseCsvNumberArrayField(systemApiForm.fps_options),
                has_audio: toNullableBool(systemApiForm.has_audio),
                has_google_search: toNullableBool(systemApiForm.has_google_search),
                has_thinking_mode: toNullableBool(systemApiForm.has_thinking_mode),
                mode_values: parseCsvArrayField(systemApiForm.mode_values),
                capability_flags: parseJsonObjectFieldSafe(systemApiForm.capability_flags),
                text_capabilities: parseJsonObjectFieldSafe(systemApiForm.text_capabilities),
                image_capabilities: parseJsonObjectFieldSafe(systemApiForm.image_capabilities),
                video_capabilities: parseJsonObjectFieldSafe(systemApiForm.video_capabilities),
                digital_human_capabilities: parseJsonObjectFieldSafe(systemApiForm.digital_human_capabilities),
                voice_capabilities: parseJsonObjectFieldSafe(systemApiForm.voice_capabilities),
                music_capabilities: parseJsonObjectFieldSafe(systemApiForm.music_capabilities),
                pricing_unit: toNullableText(systemApiForm.pricing_unit),
                token_billing_supported: toNullableBool(systemApiForm.token_billing_supported),
                input_token_price: toNullableFloat(systemApiForm.input_token_price),
                output_token_price: toNullableFloat(systemApiForm.output_token_price),
                per_resolution_price_map: parseJsonObjectFieldSafe(systemApiForm.per_resolution_price_map),
                per_duration_price_map: parseJsonObjectFieldSafe(systemApiForm.per_duration_price_map),
                has_tiered_pricing: toNullableBool(systemApiForm.has_tiered_pricing),
                free_quota: toNullableText(systemApiForm.free_quota),
                currency: toNullableText(systemApiForm.currency),
                billing_unit_type: normalizeApiPricingUnitType(systemApiForm.billing_unit_type),
                billing_cost: toNonNegativeInt(systemApiForm.billing_cost),
                billing_cost_input: toNonNegativeInt(systemApiForm.billing_cost_input),
                billing_cost_output: toNonNegativeInt(systemApiForm.billing_cost_output),
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

    // ─── provider_key_pool CRUD ───
    const fetchProviderKeyPools = async () => {
        setIsProviderKeyPoolLoading(true);
        try {
            const rows = await listProviderKeyPools();
            setProviderKeyPoolRows(Array.isArray(rows) ? rows : []);
        } catch (e) {
            console.error('Failed to load provider key pools', e);
            setProviderKeyPoolRows([]);
        } finally {
            setIsProviderKeyPoolLoading(false);
        }
    };

    const fetchOssProviderPools = async () => {
        setIsOssProviderPoolLoading(true);
        try {
            const rows = await listOssProviderPools();
            setOssProviderPoolRows(Array.isArray(rows) ? rows : []);
        } catch (e) {
            console.error('Failed to load oss provider pools', e);
            setOssProviderPoolRows([]);
        } finally {
            setIsOssProviderPoolLoading(false);
        }
    };

    const fetchTaskDefaultApis = async () => {
        setIsTaskDefaultApiLoading(true);
        try {

            const rows = await listTaskDefaultApisManage();
            const normalized = Array.isArray(rows) ? rows : [];
            setTaskDefaultApiRows(normalized);
            if (!selectedTaskDefaultCategory && normalized.length > 0) {
                setSelectedTaskDefaultCategory(String(normalized[0].task_category || ''));
            }
        } catch (e) {
            console.error('Failed to load task default APIs', e);
            setTaskDefaultApiRows([]);
        } finally {
            setIsTaskDefaultApiLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'system_api' || activeTab === 'oss_pools') {
            // Loaded by refreshSystemApiAdminViews to avoid request bursts on admin page entry.
        }
    }, [activeTab]);

    function createEmptyKieStandardMappingForm() {
        return {
            provider: 'kie',
            model_key_inferred: '',
            model_title: '',
            model_url: '',
            source_field: '',
            source_enum_value: '',
            standard_dimension: '',
            standard_value: '',
            confidence: '',
            note: '',
            is_active: true,
            is_billing_related: false,
        };
    }

    async function fetchKieStandardMappingsAndValues() {
        setIsKieStandardLoading(true);
        try {
            const [values, mappings] = await Promise.all([
                listKieStandardValuesManage({ active_only: false, limit: 5000 }),
                listKieStandardMappingsManage({
                    provider: 'kie',
                    active_only: false,
                    billing_related_only: kieStandardBillingOnly,
                    ...(kieStandardDimensionFilter !== 'all' ? { standard_dimension: kieStandardDimensionFilter } : {}),
                    ...(String(kieStandardSearchText || '').trim() ? { q: String(kieStandardSearchText || '').trim() } : {}),
                    limit: 5000,
                }),
            ]);
            setKieStandardValueRows(Array.isArray(values) ? values : []);
            const normalizedMappings = Array.isArray(mappings) ? mappings : [];
            setKieStandardMappingRows(normalizedMappings);
            setSelectedKieStandardMappingId((prev) => {
                if (prev && normalizedMappings.some((row) => String(row?.id) === String(prev))) {
                    return prev;
                }
                return normalizedMappings.length ? String(normalizedMappings[0]?.id || '') : '';
            });
        } catch (e) {
            console.error('Failed to load KIE standard mappings', e);
            setKieStandardValueRows([]);
            setKieStandardMappingRows([]);
            setSelectedKieStandardMappingId('');
        } finally {
            setIsKieStandardLoading(false);
        }
    }

    useEffect(() => {
        if (activeTab !== 'system_api') return;
        const timer = setTimeout(() => {
            fetchKieStandardMappingsAndValues();
        }, 220);
        return () => clearTimeout(timer);
    }, [activeTab, kieStandardSearchText, kieStandardDimensionFilter, kieStandardBillingOnly]);

    useEffect(() => {
        if (!selectedKeyPoolId) {
            setKeyPoolForm({ provider: '', provider_alias: '', api_keys: '', strategy: 'random', weights: '', intro_url: '' });
            return;
        }
        const row = providerKeyPoolRows.find((r) => String(r.id) === String(selectedKeyPoolId));
        if (!row) return;
        setKeyPoolForm({
            provider: row.provider || '',
            provider_alias: row.provider_alias || '',
            api_keys: Array.isArray(row.api_keys) ? row.api_keys.join('\n') : '',
            strategy: row.strategy || 'random',
            weights: Array.isArray(row.weights) && row.weights.length ? row.weights.join('\n') : '',
            intro_url: row.intro_url || '',
        });
    }, [selectedKeyPoolId, providerKeyPoolRows]);

    useEffect(() => {
        if (!selectedOssProviderPoolId) {
            setOssProviderPoolForm({
                provider: 'qiniu',
                provider_alias: '',
                endpoint: '',
                region: '',
                bucket: '',
                public_base_url: '',
                root_prefix: 'aistory/upload',
                credentials_text: '[]',
                strategy: 'random',
                weights_text: '[]',
                default_storage_class: '',
                retention_days: '',
                force_path_style: false,
                is_active: true,
            });
            return;
        }
        const row = ossProviderPoolRows.find((item) => String(item.id) === String(selectedOssProviderPoolId));
        if (!row) return;
        setOssProviderPoolForm({
            provider: row.provider || 'qiniu',
            provider_alias: row.provider_alias || '',
            endpoint: row.endpoint || '',
            region: row.region || '',
            bucket: row.bucket || '',
            public_base_url: row.public_base_url || '',
            root_prefix: row.root_prefix || '',
            credentials_text: JSON.stringify(Array.isArray(row.credentials) ? row.credentials : [], null, 2),
            strategy: row.strategy || 'random',
            weights_text: JSON.stringify(Array.isArray(row.weights) ? row.weights : [], null, 2),
            default_storage_class: row.default_storage_class || '',
            retention_days: row.retention_days === null || row.retention_days === undefined ? '' : String(row.retention_days),
            force_path_style: !!row.force_path_style,
            is_active: row.is_active !== false,
        });
    }, [selectedOssProviderPoolId, ossProviderPoolRows]);

    useEffect(() => {
        if (!selectedTaskDefaultCategory) {
            return;

        }
        const row = taskDefaultApiRows.find((item) => String(item?.task_category || '') === String(selectedTaskDefaultCategory));
        if (!row) {
            return;
        }
        setTaskDefaultForm({
            task_category: String(row.task_category || '').trim() || 'LLM',
            system_api_id: String(row.system_api_id || ''),
        });
    }, [selectedTaskDefaultCategory, taskDefaultApiRows]);

    useEffect(() => {
        if (!selectedKieStandardMappingId) {
            setKieStandardMappingForm(createEmptyKieStandardMappingForm());
            return;
        }
        const row = (kieStandardMappingRows || []).find((item) => String(item?.id || '') === String(selectedKieStandardMappingId));
        if (!row) return;
        setKieStandardMappingForm({
            provider: String(row?.provider || 'kie'),
            model_key_inferred: String(row?.model_key_inferred || ''),
            model_title: String(row?.model_title || ''),
            model_url: String(row?.model_url || ''),
            source_field: String(row?.source_field || ''),
            source_enum_value: String(row?.source_enum_value || ''),
            standard_dimension: String(row?.standard_dimension || ''),
            standard_value: String(row?.standard_value || ''),
            confidence: String(row?.confidence || ''),
            note: String(row?.note || ''),
            is_active: !!row?.is_active,
            is_billing_related: !!row?.is_billing_related,
        });
    }, [selectedKieStandardMappingId, kieStandardMappingRows]);

    useEffect(() => {
        const normalizedProvider = String(supplierFeatureProvider || '').trim().toLowerCase();
        const allowedIdSet = new Set(
            systemApiRows
                .filter((row) => {
                    if (String(row?.category || '').startsWith('System_')) return false;
                    if (!normalizedProvider) return true;
                    return String(row?.provider || '').trim().toLowerCase() === normalizedProvider;
                })
                .map((row) => Number(row?.id || 0))
                .filter((id) => Number.isFinite(id) && id > 0)
        );
        setSelectedSupplierTargetApiIds((prev) => prev.filter((id) => allowedIdSet.has(id)));
    }, [supplierFeatureProvider, systemApiRows]);

    const handleCreateKeyPool = async () => {
        const provider = String(keyPoolForm.provider || '').trim();
        if (!provider) { alert(t('Provider 不能为空', 'Provider is required')); return; }
        const keys = String(keyPoolForm.api_keys || '').split(/\r?\n|,/).map(s => s.trim()).filter(Boolean);
        const weights = String(keyPoolForm.weights || '').split(/\r?\n|,/).map(s => Number(s.trim())).filter(n => Number.isFinite(n) && n > 0);
        try {
            await createProviderKeyPool({
                provider,
                provider_alias: String(keyPoolForm.provider_alias || '').trim() || undefined,
                api_keys: keys,
                strategy: keyPoolForm.strategy || 'random',
                weights: keyPoolForm.strategy === 'weighted' ? weights : undefined,
                intro_url: String(keyPoolForm.intro_url || '').trim() || undefined,
            });
            await fetchProviderKeyPools();
            setSelectedKeyPoolId('');
            alert(t('已创建', 'Created'));
        } catch (e) { alert(e?.response?.data?.detail || e.message || 'Failed'); }
    };

    const handleUpdateKeyPool = async () => {
        if (!selectedKeyPoolId) { alert(t('请先选择一条记录', 'Select a record first')); return; }
        const keys = String(keyPoolForm.api_keys || '').split(/\r?\n|,/).map(s => s.trim()).filter(Boolean);
        const weights = String(keyPoolForm.weights || '').split(/\r?\n|,/).map(s => Number(s.trim())).filter(n => Number.isFinite(n) && n > 0);
        try {
            await updateProviderKeyPool(Number(selectedKeyPoolId), {
                provider: String(keyPoolForm.provider || '').trim() || undefined,
                provider_alias: String(keyPoolForm.provider_alias || '').trim() || undefined,
                api_keys: keys,
                strategy: keyPoolForm.strategy || 'random',
                weights: keyPoolForm.strategy === 'weighted' ? weights : undefined,
                intro_url: String(keyPoolForm.intro_url || '').trim() || undefined,
            });
            await fetchProviderKeyPools();
            alert(t('已更新', 'Updated'));
        } catch (e) { alert(e?.response?.data?.detail || e.message || 'Failed'); }
    };

    const handleDeleteKeyPool = async () => {
        if (!selectedKeyPoolId) { alert(t('请先选择一条记录', 'Select a record first')); return; }
        if (!await confirmUiMessage(t('确认删除该供应商密钥池？', 'Delete this provider key pool entry?'))) return;
        try {
            await deleteProviderKeyPool(Number(selectedKeyPoolId));
            setSelectedKeyPoolId('');
            await fetchProviderKeyPools();
            alert(t('已删除', 'Deleted'));
        } catch (e) { alert(e?.response?.data?.detail || e.message || 'Failed'); }
    };

    const parseOssProviderPoolPayloadFromForm = () => {
        let credentials = [];
        let weights = [];
        try {
            credentials = JSON.parse(String(ossProviderPoolForm.credentials_text || '[]').trim() || '[]');
            if (!Array.isArray(credentials)) throw new Error('credentials must be an array');
        } catch (e) {
            throw new Error(t('凭证 JSON 格式不正确', 'Credentials JSON is invalid'));
        }
        try {
            weights = JSON.parse(String(ossProviderPoolForm.weights_text || '[]').trim() || '[]');
            if (!Array.isArray(weights)) throw new Error('weights must be an array');
        } catch (e) {
            throw new Error(t('权重 JSON 格式不正确', 'Weights JSON is invalid'));
        }
        return {
            provider: String(ossProviderPoolForm.provider || '').trim(),       
            provider_alias: String(ossProviderPoolForm.provider_alias || '').trim() || undefined,
            endpoint: String(ossProviderPoolForm.endpoint || '').trim(),       
            region: String(ossProviderPoolForm.region || '').trim() || undefined,
            bucket: String(ossProviderPoolForm.bucket || '').trim(),
            public_base_url: String(ossProviderPoolForm.public_base_url || '').trim() || undefined,
            root_prefix: String(ossProviderPoolForm.root_prefix || '').trim() || undefined,
            credentials,
            strategy: String(ossProviderPoolForm.strategy || 'random').trim() || 'random',
            weights,
            default_storage_class: String(ossProviderPoolForm.default_storage_class || '').trim() || undefined,
            retention_days: String(ossProviderPoolForm.retention_days || '').trim() ? Number(ossProviderPoolForm.retention_days) : undefined,
            force_path_style: !!ossProviderPoolForm.force_path_style,
            is_active: !!ossProviderPoolForm.is_active,
        };
    };

    const handleCreateOssProviderPool = async () => {
        try {
            const payload = parseOssProviderPoolPayloadFromForm();
            await createOssProviderPool(payload);
            await fetchOssProviderPools();
            setSelectedOssProviderPoolId('');
            alert(t('OSS 供应商配置已创建', 'OSS provider pool created'));     
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('创建 OSS 供应商 配置失败', 'Failed to create OSS provider pool'));
        }
    };

    const handleUpdateOssProviderPool = async () => {
        if (!selectedOssProviderPoolId) {
            alert(t('请先选择一条 OSS 配置记录', 'Select an OSS provider pool record first'));
            return;
        }
        try {
            const payload = parseOssProviderPoolPayloadFromForm();
            await updateOssProviderPool(Number(selectedOssProviderPoolId), payload);
            await fetchOssProviderPools();
            alert(t('OSS 供应商配置已更新', 'OSS provider pool updated'));     
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('更新 OSS 供应商 配置失败', 'Failed to update OSS provider pool'));
        }
    };

    const handleDeleteOssProviderPool = async () => {
        if (!selectedOssProviderPoolId) {
            alert(t('请先选择一条 OSS 配置记录', 'Select an OSS provider pool record first'));
            return;
        }
        if (!await confirmUiMessage(t('确认删除该 OSS 供应商配置？', 'Delete this OSS provider pool entry?'))) return;
        try {
            await deleteOssProviderPool(Number(selectedOssProviderPoolId));    
            setSelectedOssProviderPoolId('');
            await fetchOssProviderPools();
            alert(t('OSS 供应商配置已删除', 'OSS provider pool deleted'));     
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('删除 OSS 供应商 配置失败', 'Failed to delete OSS provider pool'));
        }
    };

    const handleCreateTaskDefaultApi = async () => {
        const taskCategory = String(taskDefaultForm.task_category || '').trim();
        const systemApiId = Number(taskDefaultForm.system_api_id || 0);        

        if (!taskCategory) {
            alert(t('task_category 不能为空', 'task_category is required'));
            return;
        }
        if (!Number.isFinite(systemApiId) || systemApiId <= 0) {
            alert(t('请先选择有效的 system_api_id', 'Please select a valid system_api_id'));
            return;
        }
        try {
            await createTaskDefaultApiManage({ task_category: taskCategory, system_api_id: systemApiId });
            await refreshSystemApiAdminViews({ includeSystemApi: true, includeTaskDefaults: true });
            setSelectedTaskDefaultCategory(taskCategory.toUpperCase());
            alert(t('默认 API 映射已创建', 'Default API mapping created'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('创建默认 API 映射失败', 'Failed to create default API mapping'));
        }
    };

    const handleUpdateTaskDefaultApi = async () => {
        const taskCategory = String(taskDefaultForm.task_category || '').trim();
        const systemApiId = Number(taskDefaultForm.system_api_id || 0);
        if (!taskCategory) {
            alert(t('task_category 不能为空', 'task_category is required'));
            return;
        }
        if (!Number.isFinite(systemApiId) || systemApiId <= 0) {
            alert(t('请先选择有效的 system_api_id', 'Please select a valid system_api_id'));
            return;
        }
        try {
            await updateTaskDefaultApiManage(taskCategory, { system_api_id: systemApiId });
            await refreshSystemApiAdminViews({ includeSystemApi: true, includeTaskDefaults: true });
            setSelectedTaskDefaultCategory(taskCategory.toUpperCase());
            alert(t('默认 API 映射已更新', 'Default API mapping updated'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('更新默认 API 映射失败', 'Failed to update default API mapping'));
        }
    };

    const handleDeleteTaskDefaultApi = async () => {
        const taskCategory = String(taskDefaultForm.task_category || '').trim();
        if (!taskCategory) {
            alert(t('task_category 不能为空', 'task_category is required'));
            return;
        }
        if (!await confirmUiMessage(t('确认删除该类别默认 API 映射？', 'Delete this category default API mapping?'))) {
            return;
        }
        try {
            await deleteTaskDefaultApiManage(taskCategory);
            await refreshSystemApiAdminViews({ includeSystemApi: true, includeTaskDefaults: true });
            setSelectedTaskDefaultCategory('');
            alert(t('默认 API 映射已删除', 'Default API mapping deleted'));
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('删除默认 API 映射失败', 'Failed to delete default API mapping'));
        }
    };

    const handleCreateKieStandardMapping = async () => {
        const sourceField = String(kieStandardMappingForm.source_field || '').trim();
        const sourceEnumValue = String(kieStandardMappingForm.source_enum_value || '').trim();
        const standardDimension = String(kieStandardMappingForm.standard_dimension || '').trim().toUpperCase();
        const standardValue = String(kieStandardMappingForm.standard_value || '').trim();
        if (!sourceField || !sourceEnumValue || !standardDimension || !standardValue) {
            alert(t('请至少填写 source_field/source_enum_value/standard_dimension/standard_value', 'Please fill source_field/source_enum_value/standard_dimension/standard_value'));
            return;
        }
        setIsKieStandardSaving(true);
        try {
            const created = await createKieStandardMappingManage({
                provider: String(kieStandardMappingForm.provider || 'kie').trim() || 'kie',
                model_key_inferred: String(kieStandardMappingForm.model_key_inferred || '').trim() || null,
                model_title: String(kieStandardMappingForm.model_title || '').trim() || null,
                model_url: String(kieStandardMappingForm.model_url || '').trim() || null,
                source_field: sourceField,
                source_enum_value: sourceEnumValue,
                standard_dimension: standardDimension,
                standard_value: standardValue,
                confidence: String(kieStandardMappingForm.confidence || '').trim() || null,
                note: String(kieStandardMappingForm.note || '').trim() || null,
                is_active: !!kieStandardMappingForm.is_active,
                is_billing_related: !!kieStandardMappingForm.is_billing_related,
            });
            await fetchKieStandardMappingsAndValues();
            setSelectedKieStandardMappingId(String(created?.id || ''));
            alert(t('映射已创建', 'Mapping created'));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('创建映射失败', 'Failed to create mapping'));
        } finally {
            setIsKieStandardSaving(false);
        }
    };

    const handleUpdateKieStandardMapping = async () => {
        const mappingId = Number(selectedKieStandardMappingId || 0);
        if (!mappingId) {
            alert(t('请先选择要更新的映射', 'Please select a mapping to update'));
            return;
        }
        setIsKieStandardSaving(true);
        try {
            await updateKieStandardMappingManage(mappingId, {
                provider: String(kieStandardMappingForm.provider || 'kie').trim() || 'kie',
                model_key_inferred: String(kieStandardMappingForm.model_key_inferred || '').trim() || null,
                model_title: String(kieStandardMappingForm.model_title || '').trim() || null,
                model_url: String(kieStandardMappingForm.model_url || '').trim() || null,
                source_field: String(kieStandardMappingForm.source_field || '').trim(),
                source_enum_value: String(kieStandardMappingForm.source_enum_value || '').trim(),
                standard_dimension: String(kieStandardMappingForm.standard_dimension || '').trim().toUpperCase(),
                standard_value: String(kieStandardMappingForm.standard_value || '').trim(),
                confidence: String(kieStandardMappingForm.confidence || '').trim() || null,
                note: String(kieStandardMappingForm.note || '').trim() || null,
                is_active: !!kieStandardMappingForm.is_active,
                is_billing_related: !!kieStandardMappingForm.is_billing_related,
            });
            await fetchKieStandardMappingsAndValues();
            alert(t('映射已更新', 'Mapping updated'));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('更新映射失败', 'Failed to update mapping'));
        } finally {
            setIsKieStandardSaving(false);
        }
    };

    const handleDeleteKieStandardMapping = async () => {
        const mappingId = Number(selectedKieStandardMappingId || 0);
        if (!mappingId) {
            alert(t('请先选择要删除的映射', 'Please select a mapping to delete'));
            return;
        }
        if (!await confirmUiMessage(t('确认删除该字典映射？', 'Delete this dictionary mapping?'))) {
            return;
        }
        setIsKieStandardSaving(true);
        try {
            await deleteKieStandardMappingManage(mappingId);
            setSelectedKieStandardMappingId('');
            await fetchKieStandardMappingsAndValues();
            alert(t('映射已删除', 'Mapping deleted'));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('删除映射失败', 'Failed to delete mapping'));
        } finally {
            setIsKieStandardSaving(false);
        }
    };

    const handleInferKieBillingRelated = async () => {
        setIsKieBillingInferLoading(true);
        try {
            const result = await inferKieStandardMappingBillingRelatedManage('kie');
            await fetchKieStandardMappingsAndValues();
            alert(t(
                `反推完成，更新 ${Number(result?.updated_count || 0)} 条映射，识别 ${Number(result?.matched_dimension_count || 0)} 个计费维度。`,
                `Inference completed. Updated ${Number(result?.updated_count || 0)} mappings and matched ${Number(result?.matched_dimension_count || 0)} billing dimensions.`
            ));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('反推计费关联失败', 'Failed to infer billing-related mappings'));
        } finally {
            setIsKieBillingInferLoading(false);
        }
    };

    const downloadTextFile = (content, fileName, mimeType = 'text/plain;charset=utf-8') => {
        const blob = new Blob([String(content || '')], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const parseBooleanLike = (value, defaultValue = false) => {
        if (value === undefined || value === null || value === '') return !!defaultValue;
        const norm = String(value).trim().toLowerCase();
        if (['1', 'true', 'yes', 'y'].includes(norm)) return true;
        if (['0', 'false', 'no', 'n'].includes(norm)) return false;
        return !!defaultValue;
    };

    const parseCsvText = (text) => {
        const rows = [];
        let row = [];
        let field = '';
        let inQuotes = false;

        for (let i = 0; i < text.length; i += 1) {
            const ch = text[i];
            const next = text[i + 1];

            if (ch === '"') {
                if (inQuotes && next === '"') {
                    field += '"';
                    i += 1;
                } else {
                    inQuotes = !inQuotes;
                }
                continue;
            }

            if (!inQuotes && ch === ',') {
                row.push(field);
                field = '';
                continue;
            }

            if (!inQuotes && (ch === '\n' || ch === '\r')) {
                if (ch === '\r' && next === '\n') {
                    i += 1;
                }
                row.push(field);
                const hasAnyValue = row.some((cell) => String(cell || '').trim() !== '');
                if (hasAnyValue) {
                    rows.push(row);
                }
                row = [];
                field = '';
                continue;
            }

            field += ch;
        }

        if (field !== '' || row.length > 0) {
            row.push(field);
            const hasAnyValue = row.some((cell) => String(cell || '').trim() !== '');
            if (hasAnyValue) {
                rows.push(row);
            }
        }

        if (!rows.length) return [];
        const headers = rows[0].map((h) => String(h || '').trim());
        return rows.slice(1).map((cells) => {
            const out = {};
            headers.forEach((header, idx) => {
                out[header] = cells[idx] !== undefined ? String(cells[idx]) : '';
            });
            return out;
        });
    };

    const normalizeKieImportItem = (raw) => {
        const provider = String(raw?.provider || 'kie').trim() || 'kie';
        const modelKey = String(raw?.model_key_inferred || raw?.model_key || raw?.model || '').trim();
        const sourceField = String(raw?.source_field || '').trim();
        const sourceEnum = String(raw?.source_enum_value || raw?.mapped_api_enum_value || raw?.source_enum || '').trim();
        const standardDimension = String(raw?.standard_dimension || raw?.dimension || '').trim().toUpperCase();
        const standardValue = String(raw?.standard_value || '').trim();

        if (!sourceField || !sourceEnum || !standardDimension || !standardValue) {
            return null;
        }

        if (Object.prototype.hasOwnProperty.call(raw || {}, 'is_mapped') && !parseBooleanLike(raw?.is_mapped, false)) {
            return null;
        }

        const mappingRule = String(raw?.mapping_rule || '').trim();
        const confidence = String(raw?.confidence || '').trim() || null;
        const note = String(raw?.note || '').trim() || (mappingRule ? `std_to_api:${mappingRule}` : null);

        return {
            provider,
            model_key_inferred: modelKey || null,
            model_title: String(raw?.model_title || '').trim() || null,
            model_url: String(raw?.model_url || '').trim() || null,
            source_field: sourceField,
            source_enum_value: sourceEnum,
            standard_dimension: standardDimension,
            standard_value: standardValue,
            confidence,
            note,
            is_active: parseBooleanLike(raw?.is_active, true),
            is_billing_related: parseBooleanLike(raw?.is_billing_related, false),
        };
    };

    const normalizeKieValueItem = (raw) => {
        const standardDimension = String(raw?.standard_dimension || raw?.dimension || '').trim().toUpperCase();
        const standardValue = String(raw?.standard_value || raw?.value || '').trim();
        if (!standardDimension || !standardValue) {
            return null;
        }

        return {
            standard_dimension: standardDimension,
            standard_value: standardValue,
            value_type: String(raw?.value_type || 'enum').trim() || 'enum',
            definition: String(raw?.definition || '').trim() || null,
            alias_values: String(raw?.alias_values || '').trim() || null,
            is_active: parseBooleanLike(raw?.is_active, true),
        };
    };

    const handleExportKieDictionaryValues = async () => {
        setIsKieValueExporting(true);
        try {
            const payload = await exportKieDataDictionaryValues({
                active_only: false,
                include_csv: true,
                limit: 50000,
            });
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            const csvText = String(payload?.csv || '').trim();
            if (csvText) {
                downloadTextFile(csvText, `kie_data_dictionary_values_${ts}.csv`, 'text/csv;charset=utf-8');
            } else {
                downloadTextFile(JSON.stringify(payload || {}, null, 2), `kie_data_dictionary_values_${ts}.json`, 'application/json;charset=utf-8');
            }
            alert(t('KIE 数据字典导出完成', 'KIE dictionary values exported'));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('导出 KIE 数据字典失败', 'Failed to export KIE dictionary values'));
        } finally {
            setIsKieValueExporting(false);
        }
    };

    const handleOpenImportKieDictionaryValues = () => {
        if (!kieValueImportInputRef.current) return;
        kieValueImportInputRef.current.value = '';
        kieValueImportInputRef.current.click();
    };

    const handleImportKieDictionaryValuesFile = async (event) => {
        const file = event?.target?.files?.[0];
        if (!file) return;

        try {
            const rawText = await file.text();
            const lowerName = String(file?.name || '').toLowerCase();
            let rows = [];

            if (lowerName.endsWith('.json')) {
                const parsed = JSON.parse(rawText);
                if (Array.isArray(parsed)) {
                    rows = parsed;
                } else if (Array.isArray(parsed?.items)) {
                    rows = parsed.items;
                }
            } else {
                rows = parseCsvText(rawText);
            }

            const items = (Array.isArray(rows) ? rows : [])
                .map((row) => normalizeKieValueItem(row))
                .filter(Boolean);

            if (!items.length) {
                alert(t('导入文件中没有可用数据字典行', 'No valid dictionary rows found in import file'));
                return;
            }

            const confirmReplace = await confirmUiMessage(
                t('将使用清空式导入覆盖 KIE 数据字典，是否继续？', 'This will run clear-import and replace KIE dictionary values. Continue?'),
                {
                    title: t('确认字典导入', 'Confirm Dictionary Import'),
                    confirmText: t('确认导入', 'Import'),
                    cancelText: t('取消', 'Cancel'),
                }
            );
            if (!confirmReplace) return;

            setIsKieValueImporting(true);
            const result = await importKieDataDictionaryValues({
                items,
                replace_all: true,
                upsert_by_natural_key: false,
            });
            await fetchKieStandardMappingsAndValues();
            alert(t(
                `KIE 字典导入完成：接收 ${Number(result?.received || 0)}，新建 ${Number(result?.created || 0)}，更新 ${Number(result?.updated || 0)}，跳过 ${Number(result?.skipped || 0)}`,
                `KIE dictionary import finished: received ${Number(result?.received || 0)}, created ${Number(result?.created || 0)}, updated ${Number(result?.updated || 0)}, skipped ${Number(result?.skipped || 0)}`
            ));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('导入 KIE 数据字典失败', 'Failed to import KIE dictionary values'));
        } finally {
            setIsKieValueImporting(false);
        }
    };

    const handleExportKieDictionaryMappings = async () => {
        setIsKieMappingExporting(true);
        try {
            const payload = await exportKieDataDictionaryMappings({
                provider: 'kie',
                active_only: false,
                include_csv: true,
                limit: 50000,
            });
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            const csvText = String(payload?.csv || '').trim();
            if (csvText) {
                downloadTextFile(csvText, `kie_data_dictionary_mappings_${ts}.csv`, 'text/csv;charset=utf-8');
            } else {
                downloadTextFile(JSON.stringify(payload || {}, null, 2), `kie_data_dictionary_mappings_${ts}.json`, 'application/json;charset=utf-8');
            }
            alert(t('KIE 数据字典映射导出完成', 'KIE dictionary mappings exported'));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('导出 KIE 数据字典映射失败', 'Failed to export KIE dictionary mappings'));
        } finally {
            setIsKieMappingExporting(false);
        }
    };

    const handleOpenImportKieDictionaryMappings = () => {
        if (!kieMappingImportInputRef.current) return;
        kieMappingImportInputRef.current.value = '';
        kieMappingImportInputRef.current.click();
    };

    const handleImportKieDictionaryMappingsFile = async (event) => {
        const file = event?.target?.files?.[0];
        if (!file) return;

        try {
            const rawText = await file.text();
            const lowerName = String(file?.name || '').toLowerCase();
            let rows = [];

            if (lowerName.endsWith('.json')) {
                const parsed = JSON.parse(rawText);
                if (Array.isArray(parsed)) {
                    rows = parsed;
                } else if (Array.isArray(parsed?.items)) {
                    rows = parsed.items;
                }
            } else {
                rows = parseCsvText(rawText);
            }

            const items = (Array.isArray(rows) ? rows : [])
                .map((row) => normalizeKieImportItem(row))
                .filter(Boolean);

            if (!items.length) {
                alert(t('导入文件中没有可用映射数据', 'No valid mapping rows found in import file'));
                return;
            }

            const confirmReplace = await confirmUiMessage(
                t('将使用清空式导入覆盖 KIE 映射数据，是否继续？', 'This will run clear-import and replace KIE mapping data. Continue?'),
                {
                    title: t('确认 KIE 导入', 'Confirm KIE Import'),
                    confirmText: t('确认导入', 'Import'),
                    cancelText: t('取消', 'Cancel'),
                }
            );
            if (!confirmReplace) return;

            setIsKieMappingImporting(true);
            const result = await importKieDataDictionaryMappings({
                items,
                replace_all: true,
                upsert_by_natural_key: false,
            });
            await fetchKieStandardMappingsAndValues();
            alert(t(
                `KIE 映射导入完成：接收 ${Number(result?.received || 0)}，新建 ${Number(result?.created || 0)}，更新 ${Number(result?.updated || 0)}，跳过 ${Number(result?.skipped || 0)}`,
                `KIE mapping import finished: received ${Number(result?.received || 0)}, created ${Number(result?.created || 0)}, updated ${Number(result?.updated || 0)}, skipped ${Number(result?.skipped || 0)}`
            ));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('导入 KIE 数据字典映射失败', 'Failed to import KIE dictionary mappings'));
        } finally {
            setIsKieMappingImporting(false);
        }
    };

    const handleExportKieDictionaryBundle = async () => {
        setIsKieBundleExporting(true);
        try {
            const payload = await exportKieDataDictionaryBundle({
                include_csv: true,
                values_limit: 50000,
                mappings_limit: 50000,
            });
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            downloadTextFile(
                JSON.stringify(payload || {}, null, 2),
                `kie_data_dictionary_bundle_${ts}.json`,
                'application/json;charset=utf-8'
            );
            alert(t('KIE 数据字典包导出完成', 'KIE dictionary bundle exported'));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('导出 KIE 数据字典包失败', 'Failed to export KIE dictionary bundle'));
        } finally {
            setIsKieBundleExporting(false);
        }
    };

    const handleOpenImportKieDictionaryBundle = () => {
        if (!kieBundleImportInputRef.current) return;
        kieBundleImportInputRef.current.value = '';
        kieBundleImportInputRef.current.click();
    };

    const handleImportKieDictionaryBundleFile = async (event) => {
        const file = event?.target?.files?.[0];
        if (!file) return;

        try {
            const rawText = await file.text();
            const parsed = JSON.parse(rawText || '{}');

            const valuesRaw = Array.isArray(parsed?.values)
                ? parsed.values
                : Array.isArray(parsed?.items)
                    ? parsed.items
                    : [];
            const mappingsRaw = Array.isArray(parsed?.mappings)
                ? parsed.mappings
                : [];

            const values = valuesRaw.map((row) => normalizeKieValueItem(row)).filter(Boolean);
            const mappings = mappingsRaw.map((row) => normalizeKieImportItem(row)).filter(Boolean);

            if (!values.length && !mappings.length) {
                alert(t('字典包中没有可导入数据（values/mappings）', 'No importable values/mappings found in bundle'));
                return;
            }

            const confirmReplace = await confirmUiMessage(
                t('将清空并重建 KIE 数据字典值与映射，是否继续？', 'This will clear and rebuild KIE dictionary values and mappings. Continue?'),
                {
                    title: t('确认导入字典包', 'Confirm Dictionary Bundle Import'),
                    confirmText: t('确认导入', 'Import'),
                    cancelText: t('取消', 'Cancel'),
                }
            );
            if (!confirmReplace) return;

            setIsKieBundleImporting(true);
            const result = await importKieDataDictionaryBundle({
                values,
                mappings,
                replace_all: true,
                strict_mapping_validation: false,
            });
            await fetchKieStandardMappingsAndValues();
            alert(t(
                `字典包导入完成：值 ${Number(result?.created_values || 0)}/${Number(result?.received_values || 0)}，映射 ${Number(result?.created_mappings || 0)}/${Number(result?.received_mappings || 0)}。`,
                `Bundle import done: values ${Number(result?.created_values || 0)}/${Number(result?.received_values || 0)}, mappings ${Number(result?.created_mappings || 0)}/${Number(result?.received_mappings || 0)}.`
            ));
        } catch (e) {
            alert(e?.response?.data?.detail || e?.message || t('导入 KIE 数据字典包失败', 'Failed to import KIE dictionary bundle'));
        } finally {
            setIsKieBundleImporting(false);
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

    const handleExportSystemConfigSyncBundle = async () => {
        setIsSystemConfigSyncExporting(true);
        try {
            const payload = await exportSystemConfigSyncBundleManage();
            const dataStr = JSON.stringify(payload, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            a.href = url;
            a.download = `system_config_sync_bundle_${ts}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            const exportedRowCounts = payload?.summary?.exported_row_counts && typeof payload.summary.exported_row_counts === 'object'
                ? payload.summary.exported_row_counts
                : {};
            const exportedCountsSummary = Object.entries(exportedRowCounts)
                .map(([tableName, count]) => `${tableName}: ${Number(count || 0)}`)
                .join(', ');
            const taskDefaultExportSource = String(payload?.summary?.task_default_export_source || '').trim();
            const processText = formatSyncProcessRecords(payload?.process_records);
            alert(`System config sync bundle exported.${exportedCountsSummary ? ` Exported Rows: ${exportedCountsSummary}` : ''}${taskDefaultExportSource ? `, task_default_apis source: ${taskDefaultExportSource}` : ''}${processText ? `\n\nProcess Records:\n${processText}` : ''}`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to export system config sync bundle');
        } finally {
            setIsSystemConfigSyncExporting(false);
        }
    };

    const handleOpenImportSystemConfigSyncBundle = () => {
        if (systemConfigSyncImportInputRef.current) {
            systemConfigSyncImportInputRef.current.value = '';
            systemConfigSyncImportInputRef.current.click();
        }
    };

    const handleImportSystemConfigSyncBundleFile = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const text = await file.text();
            const parsed = JSON.parse(text);
            const data = parsed?.data;
            if (!data || typeof data !== 'object') {
                alert('Invalid sync bundle file. Expected { data: {...} }.');
                return;
            }

            const confirmReplace = await confirmUiMessage(
                'This will replace current deployment config with the bundle data and keep tables in full sync. Continue?',
                {
                    title: 'Full Sync Import',
                    confirmText: 'Import & Replace',
                    cancelText: 'Cancel',
                }
            );
            if (!confirmReplace) {
                return;
            }

            const confirmClearTables = await confirmUiMessage(
                '将先删除并重建以下表数据后再导入：system_api_settings、system_api_billing_rules、provider_key_pool、smtp_system_configs、wechat_pay_configs、function_api_configs、system_task_default_apis。是否继续？',
                {
                    title: '确认清空原表数据',
                    confirmText: '确认清空并导入',
                    cancelText: '取消',
                }
            );
            if (!confirmClearTables) {
                return;
            }

            setIsSystemConfigSyncImporting(true);
            const result = await importSystemConfigSyncBundleManage({
                data,
                replace_all: true,
                confirm_clear_existing: true,
            });
            await refreshSystemApiAdminViews({
                includeSystemApi: true,
                includeProviderPools: true,
                includeTaskDefaults: true,
                includeKie: true,
                includePayment: true,
                includeSmtp: true,
                includeBillingRules: true,
            });
            const clearedRows = result?.cleared_rows && typeof result.cleared_rows === 'object' ? result.cleared_rows : {};
            const clearedSummary = Object.entries(clearedRows)
                .map(([tableName, count]) => `${tableName}: ${Number(count || 0)}`)
                .join(', ');
            const processText = formatSyncProcessRecords(result?.process_records);
            alert(`Full sync import finished. Providers: ${result?.provider_result?.providers || 0}, Billing Rules: ${result?.billing_rules?.created || 0}${clearedSummary ? `, Cleared Rows: ${clearedSummary}` : ''}${processText ? `\n\nProcess Records:\n${processText}` : ''}`);
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to import system config sync bundle');
        } finally {
            setIsSystemConfigSyncImporting(false);
        }
    };

    const formatBytes = (value) => {
        const n = Number(value || 0);
        if (!Number.isFinite(n) || n <= 0) return '0 B';
        if (n < 1024) return `${n} B`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
        return `${(n / (1024 * 1024)).toFixed(1)} MB`;
    };

    const fetchRuntimeLogs = async (preferredFile = null) => {
        setIsRuntimeLogsLoading(true);
        setRuntimeLogsError('');
        try {
            const files = await getAdminRuntimeLogFiles();
            const normalizedFiles = Array.isArray(files) ? files : [];
            setRuntimeLogFiles(normalizedFiles);

            if (!normalizedFiles.length) {
                setRuntimeLogContent('No runtime log files found.');
                return;
            }

            let targetFile = preferredFile || selectedRuntimeLogFile || normalizedFiles[0].name;
            if (!normalizedFiles.some((f) => f.name === targetFile)) {
                targetFile = normalizedFiles[0].name;
            }
            setSelectedRuntimeLogFile(targetFile);

            const view = await getAdminRuntimeLogView({
                filename: targetFile,
                tail_lines: Math.max(1, Number(runtimeLogTailLines) || 300),
                user_name: runtimeLogFilters.user_name,
                action: runtimeLogFilters.action,
                start_time: runtimeLogFilters.start_time,
                end_time: runtimeLogFilters.end_time
            });
            setRuntimeLogContent(view?.content || '');
        } catch (e) {
            const detail = e?.response?.data?.detail || e.message || 'Failed to load runtime logs';
            setRuntimeLogsError(detail);
            setRuntimeLogContent('');
        } finally {
            setIsRuntimeLogsLoading(false);
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

    const fetchExpiredFiles = async () => {
        setIsExpiredFilesLoading(true);
        setExpiredFilesError('');
        try {
            const payload = await getAdminExpiredFiles();
            setExpiredFilesData(payload || null);
        } catch (e) {
            const detail = e?.response?.data?.detail || e.message || 'Failed to load expired files';
            setExpiredFilesError(detail);
            setExpiredFilesData(null);
        } finally {
            setIsExpiredFilesLoading(false);
        }
    };

    const fetchOrphanFiles = async () => {
        setIsOrphanFilesLoading(true);
        setOrphanFilesError('');
        try {
            const payload = await getAdminOrphanFiles();
            setOrphanFilesData(payload || null);
        } catch (e) {
            const detail = e?.response?.data?.detail || e.message || 'Failed to load orphan files';
            setOrphanFilesError(detail);
            setOrphanFilesData(null);
        } finally {
            setIsOrphanFilesLoading(false);
        }
    };

    const handleRemindExpiredFiles = async (userIds = null) => {
        try {
            const res = await remindAdminExpiredFiles(userIds);
            alert(res.message || 'Reminders sent');
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to send reminders');
        }
    };

    const handleDeleteExpiredFiles = async (userIds = null) => {
        if (!window.confirm('Delete these expired files permanently?')) return;
        try {
            const res = await deleteAdminExpiredFiles(userIds);
            alert(res.message || 'Files deleted');
            await fetchExpiredFiles();
            await fetchStorageUsage();
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || 'Failed to delete files');
        }
    };

    const handleDeleteOrphanFiles = async (userIds = null) => {
        if (!window.confirm(t('确定永久删除这些未被资产/分镜引用的孤立文件？', 'Delete these unreferenced orphan files permanently?'))) return;
        try {
            const res = await deleteAdminOrphanFiles(userIds);
            alert(res.message || t('文件已删除', 'Files deleted'));
            await fetchOrphanFiles();
            await fetchStorageUsage();
        } catch (e) {
            alert(e?.response?.data?.detail || e.message || t('删除失败', 'Failed to delete files'));
        }
    };

    useEffect(() => {
        if (activeTab !== 'runtime_logs' || isRuntimeLogsLoading) return;
        requestAnimationFrame(() => {
            const node = runtimeLogPreRef.current;
            if (!node) return;
            node.scrollTop = node.scrollHeight;
        });
    }, [activeTab, isRuntimeLogsLoading, runtimeLogContent]);

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

    const formatAdminDateTime = (value) => {
        const raw = String(value || '').trim();
        if (!raw) return '-';

        // Normalize backend timestamps for browser Date parsing:
        // - keep explicit timezone (Z or +08:00)
        // - append Z only when timezone is missing
        // - trim microseconds to milliseconds for better cross-browser compatibility
        let normalized = raw;
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
            <details className="rounded-lg border border-cyan-400/20 bg-cyan-500/5 p-2">
                <summary className="cursor-pointer list-none text-xs font-medium text-cyan-200">
                    {t('供应商用量审计', 'Provider Usage Audit')}
                    {summaryText ? <span className="ml-2 text-[11px] text-cyan-100/70">{summaryText}</span> : null}
                </summary>
                <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {usageInfo.items.map((item) => (
                        <div key={item.key} className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5">
                            <div className="text-[10px] uppercase tracking-wide text-cyan-100/60">{item.label}</div>
                            <div className="mt-1 break-all font-mono text-[11px] text-cyan-50">{String(txn.details.provider_usage?.[item.key] ?? txn.details.usage?.[item.key] ?? '')}</div>
                        </div>
                    ))}
                    {usageInfo.source ? (
                        <div className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5">
                            <div className="text-[10px] uppercase tracking-wide text-cyan-100/60">{t('来源', 'Source')}</div>
                            <div className="mt-1 break-all font-mono text-[11px] text-cyan-50">{usageInfo.source}</div>
                        </div>
                    ) : null}
                </div>
            </details>
        );
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
    const [usersPage, setUsersPage] = useState(1);
    const [usersPageSize, setUsersPageSize] = useState(20);
    const [usersTotal, setUsersTotal] = useState(0);
    const [userEditModal, setUserEditModal] = useState(null);
    const [isSavingUserEditModal, setIsSavingUserEditModal] = useState(false);

    const totalPages = Math.max(1, Math.ceil((Number(usersTotal) || 0) / Math.max(1, Number(usersPageSize) || 1)));

    const normalizeUserActiveLevel = (value, fallback = 1) => {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return Math.max(0, Number(fallback) || 0);
        return Math.max(0, Math.trunc(parsed));
    };

    const isUserEnabled = (value) => normalizeUserActiveLevel(value, 1) > 0;

    const toUserEditDraft = (user) => ({
        id: user?.id,
        username: String(user?.username || ''),
        email: String(user?.email || ''),
        full_name: String(user?.full_name || ''),
        is_active: normalizeUserActiveLevel(user?.is_active, 1),
        account_status: Number(user?.account_status ?? 1),
        email_verified: !!user?.email_verified,
        is_authorized: !!user?.is_authorized,
        is_system: !!user?.is_system,
        is_superuser: !!user?.is_superuser,
    });

    const fetchAllData = async (nextPage = usersPage, nextPageSize = usersPageSize) => {
        setLoading(true);
        try {
            const [usersRes] = await Promise.allSettled([
                getAdminUsersPage(nextPage, nextPageSize),
            ]);

            if (usersRes.status === 'fulfilled') {
                const fetchedUsers = Array.isArray(usersRes.value?.items) ? usersRes.value.items : [];
                setUsers(fetchedUsers);
                setUsersTotal(Number(usersRes.value?.total || 0));
                setUsersPage(Number(usersRes.value?.page || nextPage));
                setUsersPageSize(Number(usersRes.value?.page_size || nextPageSize));
                
                // Extract System User Settings to populate Model Options
                const systemUsers = fetchedUsers.filter(u => u.is_system);
                if (systemUsers.length > 0) {
                     // Keep room for future dynamic provider/model extraction from system settings.
                }
            } 
            
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchPricingBootstrapData = async () => {
        try {
            const [optionsRes, featurePricingRes, defaultApiPricingRes, agentToolPolicyRes] = await Promise.allSettled([
                getBillingOptions(),
                getBillingFeaturePricing(),
                getBillingDefaultApiPricing(),
                getAgentToolPolicy(),
            ]);

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
                const normalizedContentFallback = normalizeContentFallbackPricing(defaultApiPricingRes.value?.content_fallback_pricing || {});
                setDefaultApiPricingMap(normalizedDefault);
                setRecommendedDefaultApiPricingMap(normalizedRecommended);
                setDefaultApiPricingRows(buildDefaultApiPricingRows(normalizedDefault));
                setContentFallbackPricing(normalizedContentFallback);
                setContentFallbackRows(buildContentFallbackRows(normalizedContentFallback));
            } else {
                const fallbackDefault = normalizeDefaultApiPricingMap({});
                const fallbackContent = normalizeContentFallbackPricing({});
                setDefaultApiPricingMap(fallbackDefault);
                setRecommendedDefaultApiPricingMap(fallbackDefault);
                setDefaultApiPricingRows(buildDefaultApiPricingRows(fallbackDefault));
                setContentFallbackPricing(fallbackContent);
                setContentFallbackRows(buildContentFallbackRows(fallbackContent));
            }

            if (agentToolPolicyRes.status === 'fulfilled') {
                const normalizedPolicy = normalizeAgentToolPolicy(agentToolPolicyRes.value || {});
                setAgentToolPolicy(normalizedPolicy);
                setAgentToolPolicyDraft(JSON.stringify(normalizedPolicy, null, 2));
            }

            setIsPricingBootstrapLoaded(true);
        } catch (e) {
            console.error('Failed to load pricing bootstrap data', e);
        }
    };

    const fetchTransactionsOnly = async () => {
        try {
            const data = await getTransactions(
                transactionLimit,
                transactionFilterUser || null,
                transactionFilterTaskType || null,
                transactionFilterProvider || null,
                transactionFilterModel || null
            );
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
    }, [transactionFilterUser, transactionFilterTaskType, transactionFilterProvider, transactionFilterModel, transactionLimit, activeTab]);

    useEffect(() => {
        if (activeTab === 'pricing' && !isPricingBootstrapLoaded) {
            fetchPricingBootstrapData();
        }
    }, [activeTab, isPricingBootstrapLoaded]);

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
            const normalizedContentFallback = buildContentFallbackMapFromRows(contentFallbackRows);
            const res = await updateBillingDefaultApiPricing(normalized, normalizedContentFallback);
            const saved = normalizeDefaultApiPricingMap(res?.default_api_pricing || {});
            const savedContentFallback = normalizeContentFallbackPricing(res?.content_fallback_pricing || {});
            setDefaultApiPricingMap(saved);
            setDefaultApiPricingRows(buildDefaultApiPricingRows(saved));
            setContentFallbackPricing(savedContentFallback);
            setContentFallbackRows(buildContentFallbackRows(savedContentFallback));
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

    const handleContentFallbackRowChange = (rowId, field, value) => {
        setContentFallbackRows((prev) => prev.map((row) => {
            if (row.id !== rowId) return row;
            if (field === 'unit_type') {
                return { ...row, unit_type: normalizeApiPricingUnitType(value) };
            }
            return { ...row, [field]: String(value).replace(/[^0-9]/g, '') };
        }));
    };

    const handleResetContentFallbackRows = () => {
        setContentFallbackRows(buildContentFallbackRows(contentFallbackPricing || {}));
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
            fetchAllData(usersPage, usersPageSize);
        } catch (e) { alert(e.message); }
    };

    const handleSaveUserModal = async () => {
        if (!userEditModal?.id) return;
        try {
            setIsSavingUserEditModal(true);
            const payload = {
                username: String(userEditModal.username || '').trim(),
                email: String(userEditModal.email || '').trim(),
                full_name: String(userEditModal.full_name || '').trim(),
                is_active: normalizeUserActiveLevel(userEditModal.is_active, 1),
                account_status: Number(userEditModal.account_status ?? 1),
                email_verified: !!userEditModal.email_verified,
                is_authorized: !!userEditModal.is_authorized,
                is_system: !!userEditModal.is_system,
                is_superuser: !!userEditModal.is_superuser,
            };
            await updateUser(userEditModal.id, payload);
            setUserEditModal(null);
        } finally {
            setIsSavingUserEditModal(false);
        }
    };

    // Initial Fetch
    useEffect(() => {
        fetchAllData(usersPage, usersPageSize);
    }, []);

    useEffect(() => {
        if (activeTab !== 'users') return;
        fetchAllData(usersPage, usersPageSize);
    }, [activeTab, usersPage, usersPageSize]);

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

    const adminTabs = [
        { id: 'users', label: t('用户', 'Users'), icon: User },
        { id: 'function_api_config', label: t('功能API配置', 'Function APIs'), icon: Settings },
        { id: 'pricing', label: t('定价', 'Pricing'), icon: DollarSign },
        { id: 'transactions', label: t('记录', 'History'), icon: Activity },
        { id: 'cost_estimation', label: t('成本估算', 'Cost Estimation'), icon: DollarSign },
        { id: 'system_api', label: t('系统 API', 'System API'), icon: Key },
        { id: 'queue', label: t('队列', 'Queue'), icon: Activity },
        { id: 'config_sync', label: t('配置同步', 'Config Sync'), icon: Database },
        { id: 'pricing_rules', label: t('计费规则', 'Pricing Rules'), icon: DollarSign },
        { id: 'oss_pools', label: t('OSS 存储配置', 'OSS Storage'), icon: Database },
        { id: 'prompt_skills', label: t('Prompt Skills', 'Prompt Skills'), icon: List },
        { id: 'storage_usage', label: t('磁盘统计', 'Storage Usage'), icon: HardDrive },
        { id: 'runtime_logs', label: t('运行日志', 'Runtime Logs'), icon: List },
        { id: 'llm_logs', label: t('LLM 调用日志', 'LLM Call Logs'), icon: List },
        { id: 'payment', label: t('支付', 'Payment'), icon: CreditCard },
        
        { id: 'smtp', label: t('邮件 SMTP', 'Email SMTP'), icon: Mail },
    ];

    const updateUser = async (userId, data) => {
        try {
            const response = await api.put(`/users/${userId}`, data);
            setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, ...response.data, is_active: normalizeUserActiveLevel(response.data?.is_active, u?.is_active ?? 1) } : u)));
            if (data.is_system !== undefined) fetchAllData(usersPage, usersPageSize);
        } catch (e) {
            alert(e.message || t('更新失败', 'Update failed'));
        }
    };

    if (error) {
         return (
             <div className="min-h-screen bg-[#09090b] text-white flex flex-col">
                <div className="container mx-auto px-4 pt-8">
                    <button
                        onClick={() => navigate('/projects')}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 text-sm"
                    >
                        <ArrowLeft size={16} />
                        {t('返回项目主页', 'Back to Projects')}
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
                        onClick={() => navigate('/projects')}
                        className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 shrink-0"
                        title={t('返回项目主页', 'Back to Projects')}
                        aria-label={t('返回项目主页', 'Back to Projects')}
                    >
                        <ArrowLeft size={16} />
                    </button>

                </div>

                <div className="mb-4 space-y-3 md:hidden">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-gray-400">
                            {t('当前模块', 'Current Section')}
                        </label>
                        <select
                            value={activeTab}
                            onChange={(e) => setActiveTab(e.target.value)}
                            className="w-full rounded-xl border border-white/10 bg-[#111114] px-4 py-3 text-sm text-white outline-none transition-colors focus:border-primary/40"
                        >
                            {adminTabs.map((tab) => (
                                <option key={`admin-tab-select-${tab.id}`} value={tab.id}>{tab.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/10 bg-white/[0.03] p-1.5">
                        <div className="flex min-w-max items-center gap-1">
                            {adminTabs.map((tab) => (
                                <TabButton key={`admin-tab-mobile-${tab.id}`} id={tab.id} label={tab.label} icon={tab.icon} />
                            ))}
                        </div>
                    </div>
                </div>

                <div className="hidden md:block mb-6 rounded-xl border border-white/10 bg-white/5 p-1.5 overflow-x-auto no-scrollbar">
                    <div className="flex items-center gap-1 min-w-max">
                        {adminTabs.map((tab) => (
                            <TabButton key={`admin-tab-${tab.id}`} id={tab.id} label={tab.label} icon={tab.icon} />
                        ))}
                    </div>
                </div>

                {/* Content Area */}
                <div className="bg-[#18181b] rounded-xl border border-gray-800 p-6 min-h-[500px]">

                    {/* CONFIG SYNC TAB */}
                    {activeTab === 'config_sync' && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-6 max-w-4xl space-y-5">
                            <div>
                                <h2 className="text-xl font-bold mb-2 flex items-center gap-2 text-white">
                                    <Database className="text-primary" /> {t('研发/部署配置同步', 'Dev/Deploy Config Sync')}
                                </h2>
                                <p className="text-sm text-gray-300">
                                    {t('导出将打包 system api、功能 API 映射、供应商密钥池、计费规则、SMTP、微信支付配置；导入会全量覆盖，保证与研发环境一致。', 'Export packages system API, function API mappings, provider key pools, billing rules, SMTP, and WeChat Pay configs. Import performs full replace to keep deployment identical to dev.')}
                                </p>
                            </div>

                            <input
                                ref={systemConfigSyncImportInputRef}
                                type="file"
                                accept="application/json,.json"
                                className="hidden"
                                onChange={handleImportSystemConfigSyncBundleFile}
                            />

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <button
                                    onClick={handleExportSystemConfigSyncBundle}
                                    disabled={isSystemConfigSyncExporting || isSystemConfigSyncImporting}
                                    className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-3 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                    <Download size={16} />
                                    {isSystemConfigSyncExporting ? t('导出中...', 'Exporting...') : t('导出统一同步包', 'Export Sync Bundle')}
                                </button>

                                <button
                                    onClick={handleOpenImportSystemConfigSyncBundle}
                                    disabled={isSystemConfigSyncImporting || isSystemConfigSyncExporting}
                                    className="bg-primary hover:opacity-90 text-black px-4 py-3 rounded-lg font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                    <Upload size={16} />
                                    {isSystemConfigSyncImporting ? t('导入中...', 'Importing...') : t('导入并全量同步', 'Import & Full Sync')}
                                </button>
                            </div>

                            <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                                {t('注意：导入会覆盖部署环境的目标配置表，建议先在部署环境导出备份。', 'Note: import overwrites target config tables in deployment. Export a backup from deployment first.')}
                            </div>
                        </div>
                    )}
                    
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
                                                autoComplete="off"
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

                    {/* Function API Configs TAB */}
                    {activeTab === 'function_api_config' && (
                        <FunctionApiConfigTab />
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
                                                autoComplete="off"
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

                    {/* QUEUE TAB */}
                    {activeTab === 'queue' && <QueueAdmin />}

                    {/* USERS TAB */}
                    {activeTab === 'users' && (
                        <div>
                            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm text-gray-300">
                                <div>
                                    {t('用户总量', 'Total Users')}: <span className="font-semibold text-white">{usersTotal}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span>{t('每页', 'Per Page')}</span>
                                    <select
                                        className="bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs"
                                        value={usersPageSize}
                                        onChange={(e) => {
                                            const nextSize = Number(e.target.value || 20);
                                            setUsersPage(1);
                                            setUsersPageSize(nextSize);
                                        }}
                                    >
                                        {[10, 20, 50, 100].map((size) => (
                                            <option key={size} value={size}>{size}</option>
                                        ))}
                                    </select>
                                    <button
                                        className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                                        disabled={usersPage <= 1}
                                        onClick={() => setUsersPage((prev) => Math.max(1, prev - 1))}
                                    >
                                        {t('上一页', 'Prev')}
                                    </button>
                                    <span>{usersPage} / {totalPages}</span>
                                    <button
                                        className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                                        disabled={usersPage >= totalPages}
                                        onClick={() => setUsersPage((prev) => Math.min(totalPages, prev + 1))}
                                    >
                                        {t('下一页', 'Next')}
                                    </button>
                                </div>
                            </div>
                            <div className="md:hidden space-y-3">
                                {users.map((user) => (
                                    <div key={`user-card-${user.id}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="min-w-0">
                                                <div className="text-sm font-semibold text-white">#{user.id} {user.username || t('未命名用户', 'Unnamed User')}</div>
                                                <div className="text-xs text-gray-400 truncate mt-1">{user.email || '-'}</div>
                                            </div>
                                            <button
                                                className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 shrink-0"
                                                onClick={async () => {
                                                    const pwd = window.prompt(t('请输入新密码（至少 6 位）', 'Enter new password (min 6 chars)'));
                                                    if (!pwd) return;
                                                    await updateUser(user.id, { password: pwd });
                                                }}
                                            >
                                                {t('重置密码', 'Reset Password')}
                                            </button>
                                        </div>

                                        <div className="grid grid-cols-1 gap-3 text-sm">
                                            <div>
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('用户', 'User')}</div>
                                                <input
                                                    className="w-full bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm"
                                                    value={user.username || ''}
                                                    onChange={(e) => setUsers(users.map(u => u.id === user.id ? { ...u, username: e.target.value } : u))}
                                                    onBlur={() => updateUser(user.id, { username: user.username })}
                                                />
                                            </div>
                                            <div>
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('邮箱', 'Email')}</div>
                                                <input
                                                    className="w-full bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300"
                                                    value={user.email || ''}
                                                    onChange={(e) => setUsers(users.map(u => u.id === user.id ? { ...u, email: e.target.value } : u))}
                                                    onBlur={() => updateUser(user.id, { email: user.email })}
                                                />
                                            </div>
                                            <div>
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('姓名', 'Full Name')}</div>
                                                <input
                                                    className="w-full bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm"
                                                    value={user.full_name || ''}
                                                    onChange={(e) => setUsers(users.map(u => u.id === user.id ? { ...u, full_name: e.target.value } : u))}
                                                    onBlur={() => updateUser(user.id, { full_name: user.full_name })}
                                                />
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-3 text-sm">
                                            <div className="rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('积分', 'Credits')}</div>
                                                <button
                                                    onClick={() => { setCreditEditUser(user); setCreditAmount(user.credits); }}
                                                    className="inline-flex items-center gap-2 text-green-400 font-mono"
                                                >
                                                    {user.credits}
                                                    <Edit2 size={12} />
                                                </button>
                                            </div>
                                            <div className="rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('状态', 'Status')}</div>
                                                <select
                                                    className="w-full bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs"
                                                    value={user.account_status ?? 1}
                                                    onChange={(e) => updateUser(user.id, { account_status: Number(e.target.value) })}
                                                >
                                                    <option value={1}>{t('正常', 'Active')}</option>
                                                    <option value={0}>{t('禁用', 'Disabled')}</option>
                                                    <option value={-1}>{t('待邮箱校验', 'Pending Verify')}</option>
                                                </select>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 gap-3 text-sm">
                                            <div className="flex items-center justify-between rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <span>{t('启用级别', 'Active Level')}</span>
                                                <div className="flex items-center gap-2">
                                                    <input
                                                        className="w-20 bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs text-right"
                                                        inputMode="numeric"
                                                        value={normalizeUserActiveLevel(user.is_active, 1)}
                                                        onChange={(e) => setUsers(users.map((u) => (u.id === user.id ? { ...u, is_active: normalizeUserActiveLevel(e.target.value, u.is_active) } : u)))}
                                                        onBlur={() => updateUser(user.id, { is_active: normalizeUserActiveLevel(user.is_active, 1) })}
                                                    />
                                                    <Toggle active={isUserEnabled(user.is_active)} onClick={() => updateUser(user.id, { is_active: isUserEnabled(user.is_active) ? 0 : 1 })} />
                                                </div>
                                            </div>
                                            <div className="flex items-center justify-between rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <span>{t('邮箱已验证', 'Email Verified')}</span>
                                                <Toggle active={!!user.email_verified} color="bg-amber-500" onClick={() => updateUser(user.id, { email_verified: !user.email_verified })} />
                                            </div>
                                            <div className="flex items-center justify-between rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <span>{t('超级管理员', 'Superuser')}</span>
                                                <Toggle active={user.is_superuser} color="bg-red-500" onClick={() => updateUser(user.id, { is_superuser: !user.is_superuser })} />
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <div className="hidden md:block overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-gray-800 text-gray-400 text-sm">
                                        <th className="p-3">{t('用户ID', 'User ID')}</th>
                                        <th className="p-3">{t('用户', 'User')}</th>
                                        <th className="p-3">{t('姓名', 'Full Name')}</th>
                                        <th className="p-3">{t('积分', 'Credits')}</th>
                                        <th className="p-3 text-center">{t('启用级别', 'Active Level')}</th>
                                        <th className="p-3 text-center">{t('状态', 'Status')}</th>
                                        <th className="p-3 text-center">{t('邮箱已验证', 'Email Verified')}</th>
                                        <th className="p-3 text-center">{t('超级管理员', 'Superuser')}</th>
                                        <th className="p-3">{t('操作', 'Actions')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr
                                            key={user.id}
                                            className="border-b border-gray-800/50 hover:bg-gray-800/50"
                                            onDoubleClick={() => setUserEditModal(toUserEditDraft(user))}
                                            title={t('双击可快速编辑该用户', 'Double-click to edit this user quickly')}
                                        >
                                            <td className="p-3 font-mono text-xs text-gray-300">{user.id}</td>
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
                                                <div className="flex items-center justify-center gap-2">
                                                    <input
                                                        className="w-20 bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs text-right"
                                                        inputMode="numeric"
                                                        value={normalizeUserActiveLevel(user.is_active, 1)}
                                                        onChange={(e) => setUsers(users.map((u) => (u.id === user.id ? { ...u, is_active: normalizeUserActiveLevel(e.target.value, u.is_active) } : u)))}
                                                        onBlur={() => updateUser(user.id, { is_active: normalizeUserActiveLevel(user.is_active, 1) })}
                                                    />
                                                    <Toggle 
                                                        active={isUserEnabled(user.is_active)} 
                                                        onClick={() => updateUser(user.id, { is_active: isUserEnabled(user.is_active) ? 0 : 1 })}
                                                    />
                                                </div>
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
                        </div>
                    )}

                    {/* PRICING TAB */}
                    {activeTab === 'pricing' && (
                        <div>
                            <div className="space-y-4">
                                <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4">
                                    <h3 className="text-xl font-extrabold tracking-wide text-red-200">{t('超级用户计费控制台', 'Superuser Billing Console')}</h3>
                                    <p className="text-xs text-red-100/80 mt-1">
                                        {t('此模块仅用于平台级计费策略配置，不面向普通用户。', 'This module is for platform-level billing policy only and is not exposed to regular users.')}
                                    </p>
                                </div>

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
                                        <table className="w-full text-xs min-w-[760px]">
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
                                    <h3 className="text-lg font-bold mb-2">{t('按内容类型兜底定价', 'Content-Type Fallback Pricing')}</h3>
                                    <p className="text-xs text-gray-400 mb-3">
                                        {t('当未命中细粒度规则时，可按文本/图片/视频内容类型兜底。策略支持手动配置、按平均价、按最高价。', 'When no granular rule matches, fallback can be applied by content type (text/image/video). Strategy supports manual values, average price, or highest price.')}
                                    </p>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                                        <label className="flex items-center gap-2 text-xs text-gray-300">
                                            <input
                                                type="checkbox"
                                                checked={!!contentFallbackPricing?.enabled}
                                                onChange={(e) => setContentFallbackPricing((prev) => ({
                                                    ...(prev || {}),
                                                    enabled: e.target.checked,
                                                }))}
                                            />
                                            {t('启用内容兜底', 'Enable content fallback')}
                                        </label>

                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-gray-400">{t('策略', 'Strategy')}</span>
                                            <select
                                                value={contentFallbackPricing?.strategy || 'manual'}
                                                onChange={(e) => setContentFallbackPricing((prev) => ({
                                                    ...(prev || {}),
                                                    strategy: e.target.value,
                                                }))}
                                                className="bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                            >
                                                <option value="manual">{t('手动', 'Manual')}</option>
                                                <option value="average">{t('平均价', 'Average')}</option>
                                                <option value="highest">{t('最高价', 'Highest')}</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div className="overflow-x-auto">
                                        <table className="w-full text-xs border-collapse">
                                            <thead>
                                                <tr className="border-b border-white/10 text-gray-400">
                                                    <th className="text-left p-2">{t('内容类型', 'Content Type')}</th>
                                                    <th className="text-left p-2">unit_type</th>
                                                    <th className="text-left p-2">cost</th>
                                                    <th className="text-left p-2">cost_input</th>
                                                    <th className="text-left p-2">cost_output</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {contentFallbackRows.map((row) => (
                                                    <tr key={row.id} className="border-b border-white/5">
                                                        <td className="p-2 text-gray-200 font-medium uppercase">{row.content_type}</td>
                                                        <td className="p-2">
                                                            <select
                                                                value={row.unit_type}
                                                                onChange={(e) => handleContentFallbackRowChange(row.id, 'unit_type', e.target.value)}
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
                                                                onChange={(e) => handleContentFallbackRowChange(row.id, 'cost', e.target.value)}
                                                                inputMode="numeric"
                                                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                value={row.cost_input}
                                                                onChange={(e) => handleContentFallbackRowChange(row.id, 'cost_input', e.target.value)}
                                                                inputMode="numeric"
                                                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                value={row.cost_output}
                                                                onChange={(e) => handleContentFallbackRowChange(row.id, 'cost_output', e.target.value)}
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
                                            {isDefaultApiPricingSaving ? t('保存中...', 'Saving...') : t('保存内容兜底策略', 'Save Content Fallback')}
                                        </button>
                                        <button
                                            onClick={handleResetContentFallbackRows}
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
                             <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4 mb-6">
                                <h3 className="text-lg font-bold">{t('交易记录', 'Transaction History')} ({transactions.length} record(s))</h3>
                                <div className="flex flex-col sm:flex-row sm:items-center flex-wrap gap-2">
                                    <select
                                        className="bg-gray-800 border border-gray-700 text-sm rounded p-2 text-gray-300 focus:outline-none focus:border-primary min-w-[150px]"
                                        value={transactionFilterUser}
                                        onChange={(e) => setTransactionFilterUser(e.target.value)}
                                    >
                                        <option value="">{t('全部用户', 'All Users')}</option>
                                        {users.map(u => (
                                            <option key={u.id} value={u.id}>
                                                {u.username} (ID: {u.id})
                                            </option>
                                        ))}
                                    </select>
                                    <input
                                        type="text"
                                        placeholder={t('按类型 (task_type) 筛选', 'Filter by Type')}
                                        className="bg-gray-800 border border-gray-700 text-sm rounded p-2 text-gray-300 focus:outline-none focus:border-primary w-[140px]"
                                        value={transactionFilterTaskType}
                                        onChange={(e) => setTransactionFilterTaskType(e.target.value)}
                                    />
                                    <input
                                        type="text"
                                        placeholder={t('按渠道 (provider) 筛选', 'Filter by Provider')}
                                        className="bg-gray-800 border border-gray-700 text-sm rounded p-2 text-gray-300 focus:outline-none focus:border-primary w-[160px]"
                                        value={transactionFilterProvider}
                                        onChange={(e) => setTransactionFilterProvider(e.target.value)}
                                    />
                                    <input
                                        type="text"
                                        placeholder={t('按模型 (model) 筛选', 'Filter by Model')}
                                        className="bg-gray-800 border border-gray-700 text-sm rounded p-2 text-gray-300 focus:outline-none focus:border-primary w-[140px]"
                                        value={transactionFilterModel}
                                        onChange={(e) => setTransactionFilterModel(e.target.value)}
                                    />
                                    <div className="flex items-center gap-1 bg-gray-800 border border-gray-700 rounded px-2">
                                        <span className="text-xs text-gray-400">{t('Limit:', 'Limit:')}</span>
                                        <input 
                                            type="number"
                                            className="bg-transparent text-sm p-1.5 focus:outline-none w-16 text-gray-200"
                                            value={transactionLimit}
                                            onChange={(e) => setTransactionLimit(Number(e.target.value))}
                                            min="10"
                                            max="1000"
                                        />
                                    </div>
                                    <button
                                        onClick={fetchTransactionsOnly}
                                        className="p-2 ml-1 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 transition-colors"
                                        title={t('刷新', 'Refresh')}
                                    >
                                        <RefreshCw size={16} />
                                    </button>
                                </div>
                             </div>
                             <div className="md:hidden space-y-3">
                                    {transactions.map(txn => (
                                      <div key={`txn-card-${txn.id}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
                                          <div className="flex items-start justify-between gap-3">
                                              <div className="min-w-0">
                                                  <div className="text-sm font-semibold text-white">{formatAdminDateTime(txn.created_at)}</div>
                                                  <div className="text-xs text-gray-400 mt-1">User #{txn.user_id}</div>
                                              </div>
                                              <div className="flex flex-col items-end gap-1">
                                                  <span className="bg-gray-800 px-2 py-0.5 rounded text-[10px] uppercase text-gray-300 shrink-0">{txn.provider_alias || txn.provider || '-'}</span>
                                                  <span className="bg-gray-800 px-2 py-0.5 rounded text-xs uppercase text-gray-300 shrink-0">{txn.task_type || '-'}</span>
                                              </div>
                                          </div>
                                          <div className="grid grid-cols-2 gap-3 text-sm">
                                            <div className="rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('金额', 'Amount')}</div>
                                                    <div className={`font-mono ${txn.amount < 0 ? 'text-red-400' : 'text-green-400'}`}>{txn.amount > 0 ? '+' : ''}{txn.amount}</div>
                                            </div>
                                            <div className="rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('余额', 'Balance')}</div>
                                                    <div className="font-mono text-gray-300">{txn.balance_after}</div>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('详情', 'Details')}</div>
                                            <div className="mb-2">
                                                {renderTransactionProviderUsage(txn)}
                                            </div>
                                            <div className="max-h-[180px] overflow-y-auto whitespace-pre-wrap break-all rounded-lg bg-gray-900/50 p-2 border border-gray-800 font-mono text-[11px] text-gray-400">
                                                    {JSON.stringify(txn.details, null, 2)}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                             <div className="hidden md:block overflow-x-auto">
                                <table className="w-full text-left border-collapse text-sm">
                                      <thead>
                                          <tr className="border-b border-gray-800 text-gray-400">
                                              <th className="p-3">{t('时间', 'Time')}</th>
                                              <th className="p-3">{t('用户 ID', 'User ID')}</th>
                                              <th className="p-3">{t('类型', 'Type')}</th>
                                              <th className="p-3">{t('渠道', 'Provider')}</th>
                                              <th className="p-3">{t('模型', 'Model')}</th>
                                              <th className="p-3 max-w-[300px]">{t('详情', 'Details')}</th>
                                              <th className="p-3 text-right">{t('金额', 'Amount')}</th>
                                              <th className="p-3 text-right">{t('余额', 'Balance')}</th>
                                          </tr>
                                      </thead>
                                      <tbody>
                                          {transactions.map(txn => (
                                              <tr key={txn.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                                  <td className="p-3 text-gray-400 whitespace-nowrap">
                                                      {formatAdminDateTime(txn.created_at)}
                                                  </td>
                                                  <td className="p-3">{txn.user_id}</td>
                                                  <td className="p-3"><span className="bg-gray-800 px-2 py-0.5 rounded text-xs uppercase text-gray-300">{txn.task_type || '-'}</span></td>
                                                  <td className="p-3 text-xs text-gray-400 text-center whitespace-nowrap">{txn.provider_alias || txn.provider || '-'}</td>
                                                  <td className="p-3 text-xs text-gray-400 text-center whitespace-nowrap">{txn.model || '-'}</td>
                                                  <td className="p-3 text-xs text-gray-500 w-[300px] min-w-[200px]">
                                                      {txn.description && (
                                                        <div className="mb-2 text-[11px] text-gray-300 font-medium">{txn.description} {txn.project_id ? `[Proj: ${txn.project_id}]` : ''} {txn.episode_id ? `[Ep: ${txn.episode_id}]` : ''}</div>
                                                      )}
                                                      <div className="mb-2 w-full">
                                                          {renderTransactionProviderUsage(txn)}
                                                      </div>
                                                      <div className="max-h-[150px] overflow-y-auto whitespace-pre-wrap break-all bg-gray-900/50 p-1 w-full rounded border border-gray-800 font-mono">
                                                          {JSON.stringify(txn.details, null, 2)}
                                                      </div>
                                                  </td>
                                                  <td className={`p-3 text-right font-mono whitespace-nowrap ${txn.amount < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                                      {txn.amount > 0 ? '+' : ''}{txn.amount}
                                                  </td>
                                                  <td className="p-3 text-right font-mono text-gray-400 whitespace-nowrap">{txn.balance_after}</td>
                                              </tr>
                                          ))}
                                      </tbody>
                                  </table>
                            </div>
                        </div>
                    )}

                    {/* COST ESTIMATION TAB */}
                    {activeTab === 'cost_estimation' && (
                        <div className="space-y-5">
                            <div className="border border-cyan-500/30 rounded-xl p-4 bg-cyan-500/5 space-y-3">
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <h4 className="text-sm font-semibold text-white">{t('项目成本评估模型配置', 'Project Cost Estimation Model Config')}</h4>
                                        <p className="text-xs text-gray-400 mt-1">{t('核心参数可视化编辑（不再只靠 JSON）：概要成本 / 建议成本 / 预算成本、实体分档与项目基础倍率。', 'Edit core parameters visually (no longer JSON-only): Overview/Suggested/Budget, entity tiers, and base project multiplier.')}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={fetchProjectCostEstimationConfig}
                                            disabled={isProjectCostConfigSaving}
                                            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded text-xs disabled:opacity-50 flex items-center gap-2"
                                        >
                                            <RefreshCw size={14} /> {t('刷新配置', 'Refresh Config')}
                                        </button>
                                        <button
                                            onClick={saveProjectCostEstimationConfig}
                                            disabled={isProjectCostConfigSaving}
                                            className="bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-1 rounded text-xs disabled:opacity-50"
                                        >
                                            {isProjectCostConfigSaving ? t('保存中...', 'Saving...') : t('保存配置', 'Save Config')}
                                        </button>
                                    </div>
                                </div>
                                <div key={costFormKey} className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                                    <div className="rounded-lg border border-white/10 bg-black/20 p-3 space-y-3">
                                        <h5 className="text-xs font-semibold text-white">{t('概要成本（Overview）', 'Overview')}</h5>
                                        <label className="block text-xs text-gray-300">
                                            {t('word_rate（每词基价）', 'word_rate (unit price per word)')}
                                            <input
                                                type="number"
                                                step="0.0001"
                                                min="0"
                                                defaultValue={String(getCostConfigNumber(['overview', 'word_rate'], 0.012))}
                                                onBlur={(e) => setCostConfigNumber(['overview', 'word_rate'], e.target.value, 0.012)}
                                                onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                            />
                                        </label>
                                    </div>

                                    <div className="rounded-lg border border-white/10 bg-black/20 p-3 space-y-3">
                                        <h5 className="text-xs font-semibold text-white">{t('预算成本（Budget）', 'Budget')}</h5>
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                            <label className="block text-xs text-gray-300">
                                                {t('shot_unit_rate（镜头单位成本）', 'shot_unit_rate (shot unit rate)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['budget', 'shot_unit_rate'], 1.0))}
                                                    onBlur={(e) => setCostConfigNumber(['budget', 'shot_unit_rate'], e.target.value, 1.0)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                            <label className="block text-xs text-gray-300">
                                                {t('duration_weight（时长权重）', 'duration_weight (duration weight)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['budget', 'duration_weight'], 1.0))}
                                                    onBlur={(e) => setCostConfigNumber(['budget', 'duration_weight'], e.target.value, 1.0)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                            <label className="block text-xs text-gray-300">
                                                {t('asset_weight（资产权重）', 'asset_weight (asset weight)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['budget', 'asset_weight'], 0.8))}
                                                    onBlur={(e) => setCostConfigNumber(['budget', 'asset_weight'], e.target.value, 0.8)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                        </div>
                                    </div>

                                    <div className="xl:col-span-2 rounded-lg border border-cyan-400/20 bg-cyan-500/5 p-3 space-y-3">
                                        <h5 className="text-xs font-semibold text-cyan-100">{t('建议成本（Suggested，按 Scene）', 'Suggested (per Scene)')}</h5>
                                        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                                            <label className="block text-xs text-gray-200">
                                                {t('base_scene_point（场景基点）', 'base_scene_point (base scene point)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['suggested', 'base_scene_point'], 1.0))}
                                                    onBlur={(e) => setCostConfigNumber(['suggested', 'base_scene_point'], e.target.value, 1.0)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                            <label className="block text-xs text-gray-200">
                                                {t('role_complexity（角色复杂度）', 'role_complexity (role complexity)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['suggested', 'role_complexity'], 1.0))}
                                                    onBlur={(e) => setCostConfigNumber(['suggested', 'role_complexity'], e.target.value, 1.0)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                            <label className="block text-xs text-gray-200">
                                                {t('env_complexity（环境复杂度）', 'env_complexity (environment complexity)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['suggested', 'env_complexity'], 0.8))}
                                                    onBlur={(e) => setCostConfigNumber(['suggested', 'env_complexity'], e.target.value, 0.8)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                            <label className="block text-xs text-gray-200">
                                                {t('prop_complexity（道具复杂度）', 'prop_complexity (prop complexity)')}
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    min="0"
                                                    defaultValue={String(getCostConfigNumber(['suggested', 'prop_complexity'], 0.5))}
                                                    onBlur={(e) => setCostConfigNumber(['suggested', 'prop_complexity'], e.target.value, 0.5)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                    className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </label>
                                        </div>

                                        <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                                            <div className="text-xs font-semibold text-gray-200 mb-2">{t('实体总数分档系数（entity_tier_ratios）', 'Entity Tier Ratios')}</div>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                                <label className="block text-xs text-gray-300">{t('tier1_max（第一档上限）', 'tier1_max (tier-1 upper bound)')}
                                                    <input type="number" step="1" min="1" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier1_max'], 3))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier1_max'], e.target.value, 3, true)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                                <label className="block text-xs text-gray-300">{t('tier2_max（第二档上限）', 'tier2_max (tier-2 upper bound)')}
                                                    <input type="number" step="1" min="1" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier2_max'], 6))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier2_max'], e.target.value, 6, true)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                                <label className="block text-xs text-gray-300">{t('tier3_max（第三档上限）', 'tier3_max (tier-3 upper bound)')}
                                                    <input type="number" step="1" min="1" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier3_max'], 9))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier3_max'], e.target.value, 9, true)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                                <label className="block text-xs text-gray-300">{t('tier4_factor（第四档系数）', 'tier4_factor (tier-4 factor)')}
                                                    <input type="number" step="0.0001" min="0" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier4_factor'], 1.8))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier4_factor'], e.target.value, 1.8)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                                <label className="block text-xs text-gray-300">{t('tier1_factor（第一档系数）', 'tier1_factor (tier-1 factor)')}
                                                    <input type="number" step="0.0001" min="0" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier1_factor'], 1.0))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier1_factor'], e.target.value, 1.0)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                                <label className="block text-xs text-gray-300">{t('tier2_factor（第二档系数）', 'tier2_factor (tier-2 factor)')}
                                                    <input type="number" step="0.0001" min="0" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier2_factor'], 1.2))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier2_factor'], e.target.value, 1.2)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                                <label className="block text-xs text-gray-300">{t('tier3_factor（第三档系数）', 'tier3_factor (tier-3 factor)')}
                                                    <input type="number" step="0.0001" min="0" defaultValue={String(getCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier3_factor'], 1.5))} onBlur={(e) => setCostConfigNumber(['suggested', 'entity_tier_ratios', 'tier3_factor'], e.target.value, 1.5)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} className="mt-1 w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" />
                                                </label>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="xl:col-span-2 rounded-lg border border-amber-400/20 bg-amber-500/5 p-3 space-y-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <div>
                                                <h5 className="text-xs font-semibold text-amber-100">{t('项目信息字段倍率规则（project_multiplier）', 'Project Field Multiplier Rules (project_multiplier)')}</h5>
                                                <p className="text-[11px] text-gray-400 mt-0.5">{t('default_factor 为基础倍率；field_factors 根据项目字段值精确匹配后连乘，匹配不到则走 __default__。最终 project_info_multiplier = default_factor × ∏ 字段系数', 'default_factor is base; field_factors are multiplied by matched project field values; fallback to __default__. Final: project_info_multiplier = default_factor × ∏ field_factor')}</p>
                                            </div>
                                        </div>

                                        <label className="block text-xs text-gray-300">
                                            {t('default_factor（基础倍率，未命中任何字段规则时的起点）', 'default_factor (base multiplier when no field rules match)')}
                                            <input
                                                type="number"
                                                step="0.0001"
                                                min="0"
                                                defaultValue={String(getCostConfigNumber(['project_multiplier', 'default_factor'], 1.0))}
                                                onBlur={(e) => setCostConfigNumber(['project_multiplier', 'default_factor'], e.target.value, 1.0)}
                                                onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                className="mt-1 w-48 bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                            />
                                        </label>

                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <span className="text-xs font-semibold text-gray-200">{t('字段倍率规则（field_factors）', 'Field Factor Rules (field_factors)')}</span>
                                                <button
                                                    type="button"
                                                    onClick={addCostField}
                                                    className="text-[11px] bg-amber-600/30 hover:bg-amber-600/50 border border-amber-500/30 text-amber-100 px-2 py-1 rounded flex items-center gap-1"
                                                >
                                                    <Plus size={11} /> {t('添加字段', 'Add Field')}
                                                </button>
                                            </div>

                                            {Object.keys(getCostFieldFactors()).length === 0 && (
                                                <div className="text-[11px] text-gray-500 italic">{t('暂无字段规则，点击「添加字段」创建。', 'No field rules yet. Click "Add Field" to create one.')}</div>
                                            )}

                                            {Object.entries(getCostFieldFactors()).map(([fieldName, mapping]) => (
                                                <div key={fieldName} className="rounded-lg border border-white/10 bg-black/30 p-3 space-y-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-[11px] text-gray-400 shrink-0">{t('字段名', 'Field')}</span>
                                                        <input
                                                            type="text"
                                                            defaultValue={fieldName}
                                                            onBlur={(e) => renameCostField(fieldName, e.target.value)}
                                                            onKeyDown={(e) => { if (e.key === 'Enter') { e.currentTarget.blur(); } }}
                                                            className="flex-1 bg-black/40 border border-gray-600 rounded px-2 py-1 text-xs font-mono text-amber-200"
                                                        />
                                                        <button
                                                            type="button"
                                                            onClick={() => removeCostField(fieldName)}
                                                            className="text-[11px] text-red-400 hover:text-red-300 px-1.5 py-0.5 rounded border border-red-500/20 hover:bg-red-500/10 shrink-0"
                                                        >
                                                            <Trash2 size={11} />
                                                        </button>
                                                    </div>

                                                    <div className="space-y-1">
                                                        {Object.entries(mapping && typeof mapping === 'object' ? mapping : {}).map(([mappingKey, factor]) => (
                                                            <div key={mappingKey} className="flex items-center gap-2">
                                                                <input
                                                                    type="text"
                                                                    defaultValue={mappingKey}
                                                                    onBlur={(e) => updateCostFieldMappingKey(fieldName, mappingKey, e.target.value)}
                                                                    onKeyDown={(e) => { if (e.key === 'Enter') { e.currentTarget.blur(); } }}
                                                                    className="flex-1 bg-black/40 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-gray-200"
                                                                    placeholder={t('字段值（或 __default__）', 'field value or __default__')}
                                                                />
                                                                <input
                                                                    type="number"
                                                                    step="0.01"
                                                                    min="0"
                                                                    defaultValue={String(Number.isFinite(Number(factor)) ? Number(factor) : 1.0)}
                                                                    onBlur={(e) => updateCostFieldMappingFactor(fieldName, mappingKey, e.target.value)}
                                                                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
                                                                    className="w-24 bg-black/40 border border-gray-700 rounded px-2 py-1 text-xs text-right"
                                                                />
                                                                <button
                                                                    type="button"
                                                                    onClick={() => removeCostFieldMapping(fieldName, mappingKey)}
                                                                    className="text-red-400/60 hover:text-red-300 shrink-0"
                                                                >
                                                                    <X size={11} />
                                                                </button>
                                                            </div>
                                                        ))}
                                                    </div>

                                                    <button
                                                        type="button"
                                                        onClick={() => addCostFieldMapping(fieldName)}
                                                        className="text-[11px] text-gray-400 hover:text-gray-200 flex items-center gap-1"
                                                    >
                                                        <Plus size={10} /> {t('添加值映射', 'Add mapping')}
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-gray-400 leading-6">
                                        <div>{t('说明：dimension_rules 等高级影响因子规则暂未在界面展示，会在保存时原样保留，如需调整请联系开发者。', 'Note: advanced dimension_rules are not shown here and will be preserved as-is on save.')}</div>
                                    </div>
                                </div>
                            </div>

                            <div className="border border-white/10 rounded-xl p-4 bg-white/5 space-y-3">
                                <h4 className="text-sm font-semibold text-white">{t('估算算法梳理', 'Estimation Algorithm Summary')}</h4>
                                <div className="text-xs text-gray-300 leading-6 space-y-2">
                                    <div>{t('核心规则：三阶段是逐步精细化估算，不相加；当前结果只取最精细可用阶段。', 'Core rule: stages are progressive refinements, not additive; current result uses only the finest available stage.')}</div>
                                </div>

                                <details className="rounded-lg border border-white/10 bg-black/20 p-3">
                                    <summary className="cursor-pointer text-xs font-semibold text-white">{t('展开：公式视图', 'Expand: Formula View')}</summary>
                                    <div className="mt-3 space-y-2 text-xs text-gray-300">
                                        <div>{t('阶段选择：若 shot_count > 0 => 当前阶段=budget；否则若 scene_count > 0 => 当前阶段=suggested；否则=overview。', 'Stage selection: if shot_count > 0 => stage=budget; else if scene_count > 0 => stage=suggested; else overview.')}</div>
                                        <div>{t('概要成本 raw_overview = word_count * overview.word_rate', 'Overview raw_overview = word_count * overview.word_rate')}</div>
                                        <div>{t('建议成本（逐 Scene）：scene_cost = duration * base_scene_point * (1.0 + (role_count - 1) * role_complexity + (env_count - 1) * env_complexity + prop_count * prop_complexity) * entity_tier_ratio * project_info_multiplier', 'Suggested (per scene): scene_cost = duration * base_scene_point * (1.0 + (role_count - 1) * role_complexity + (env_count - 1) * env_complexity + prop_count * prop_complexity) * entity_tier_ratio * project_info_multiplier')}</div>
                                        <div>{t('汇总：raw_suggested = sum(scene_cost) * dimension_multiplier_only（因逐景计算已含项目系数）', 'Aggregation: raw_suggested = sum(scene_cost) * dimension_multiplier_only (scene cost already includes project mult)')}</div>
                                        <div>{t('预算成本 raw_budget = sum(shot_complexity) * budget.shot_unit_rate', 'Budget raw_budget = sum(shot_complexity) * budget.shot_unit_rate')}</div>
                                        <div>{t('shot_complexity = duration_weight * duration + asset_weight * shot_asset_count', 'shot_complexity = duration_weight * duration + asset_weight * shot_asset_count')}</div>
                                        <div>{t('总倍率 total_multiplier = project_info_multiplier * dimension_multiplier', 'total_multiplier = project_info_multiplier * dimension_multiplier')}</div>
                                        <div>{t('最终估算：概览/预算阶段 = raw * total_multiplier，建议阶段已在汇总时自动乘齐。', 'Final: overview/budget = raw * total_multiplier, suggested is already scaled.')}</div>
                                    </div>
                                </details>

                                <details className="rounded-lg border border-white/10 bg-black/20 p-3">
                                    <summary className="cursor-pointer text-xs font-semibold text-white">{t('展开：字段对照', 'Expand: Field Mapping')}</summary>
                                    <div className="mt-3 overflow-x-auto">
                                        <table className="w-full text-xs min-w-[680px]">
                                            <thead className="text-gray-400">
                                                <tr className="border-b border-white/10">
                                                    <th className="text-left py-2 pr-3">{t('业务名', 'Business Name')}</th>
                                                    <th className="text-left py-2 pr-3">{t('配置键', 'Config Key')}</th>
                                                    <th className="text-left py-2 pr-3">{t('主要参数', 'Main Params')}</th>
                                                    <th className="text-left py-2">{t('输出字段', 'Output Fields')}</th>
                                                </tr>
                                            </thead>
                                            <tbody className="text-gray-200">
                                                <tr className="border-b border-white/5">
                                                    <td className="py-2 pr-3">{t('概要成本', 'Overview Cost')}</td>
                                                    <td className="py-2 pr-3">overview</td>
                                                    <td className="py-2 pr-3">word_rate</td>
                                                    <td className="py-2">stages.overview, episode_costs[].overview_cost</td>
                                                </tr>
                                                <tr className="border-b border-white/5">
                                                    <td className="py-2 pr-3">{t('建议成本', 'Suggested Cost')}</td>
                                                    <td className="py-2 pr-3">suggested</td>
                                                    <td className="py-2 pr-3">base_scene_point, role/env/prop_complexity, entity_tier_ratios</td>
                                                    <td className="py-2">stages.suggested, episode_costs[].suggested_cost</td>
                                                </tr>
                                                <tr className="border-b border-white/5">
                                                    <td className="py-2 pr-3">{t('预算成本', 'Budget Cost')}</td>
                                                    <td className="py-2 pr-3">budget</td>
                                                    <td className="py-2 pr-3">shot_unit_rate, duration_weight, asset_weight</td>
                                                    <td className="py-2">stages.budget, episode_costs[].budget_cost</td>
                                                </tr>
                                                <tr>
                                                    <td className="py-2 pr-3">{t('当前阶段估算', 'Current Stage Estimate')}</td>
                                                    <td className="py-2 pr-3">summary.current_stage</td>
                                                    <td className="py-2 pr-3">按 scene/shot 可用性自动选择</td>
                                                    <td className="py-2">summary.current_estimate, episode_costs[].current_estimated_cost</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </details>
                            </div>
                        </div>
                    )}

                    {/* SYSTEM API TAB */}
                    {activeTab === 'system_api' && (
                        <div className="space-y-4">
                            <div className="border border-emerald-500/30 rounded-xl p-4 bg-emerald-500/5 space-y-3">
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <h4 className="text-sm font-semibold text-white">{t('场景分析总开关', 'Scene Analysis Master Switch')}</h4>
                                        <p className="text-xs text-gray-400 mt-1">{t('超级管理员在这里设定默认走原始提示词还是 Skill 决策引擎。所有路径输出协议保持一致，只改变提示词组装策略。', 'Superusers set the default path here: original prompt or skill decision engine. All paths keep the same output contract; only prompt assembly strategy changes.')}</p>
                                    </div>
                                    {isSceneAnalysisConfigSaving && <span className="text-[11px] text-gray-400">{t('保存中', 'Saving')}</span>}
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
                                    <div>
                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('默认分析路径', 'Default Analysis Path')}</label>
                                        <select
                                            value={sceneAnalysisDefaultMode}
                                            onChange={(e) => {
                                                const value = e.target.value;
                                                setSceneAnalysisDefaultMode(value);
                                                saveSceneAnalysisConfig({ default_mode: value });
                                            }}
                                            disabled={isSceneAnalysisConfigSaving}
                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                        >
                                            <option value="classic">{t('原始提示词', 'Original Prompt')}</option>
                                            <option value="decision_engine">{t('Skill 决策引擎', 'Skill Decision Engine')}</option>
                                            <option value="feature_stack">{t('Feature Stack（调试/过渡）', 'Feature Stack (Debug/Transition)')}</option>
                                        </select>
                                    </div>
                                    <div className="text-xs text-gray-400 leading-5">
                                        {sceneAnalysisDefaultMode === 'classic'
                                            ? t('当前默认：完全走 scene_analysis.txt 原始路径。', 'Current default: use the original scene_analysis.txt path only.')
                                            : sceneAnalysisDefaultMode === 'decision_engine'
                                                ? t('当前默认：走 Skill 决策引擎，结合项目维度组合 skills。', 'Current default: use the skill decision engine and compose skills from project dimensions.')
                                                : t('当前默认：走 Feature Stack 叠加模式，适合调试和过渡。', 'Current default: use feature-stack additive mode for debugging or transition.')}
                                    </div>
                                </div>
                            </div>
                            <div className="border border-white/10 rounded-xl p-4 bg-white/5 space-y-3">
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <h4 className="text-sm font-semibold text-white">{t('系统通用资产画幅', 'System Asset Aspect Ratios')}</h4>
                                        <p className="text-xs text-gray-400 mt-1">{t('主体资产图与封面图提交到上游图片 API 时，会优先读取这里的默认画幅。', 'Subject asset image and cover image submissions to upstream image APIs will prefer these default aspect ratios.')}</p>
                                    </div>
                                    {isAssetImageRatioConfigSaving && <span className="text-[11px] text-gray-400">{t('保存中', 'Saving')}</span>}
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('Subjects 资产比例', 'Subjects Asset Ratio')}</label>
                                        <input
                                            value={subjectAssetAspectRatio}
                                            onChange={(e) => setSubjectAssetAspectRatio(e.target.value)}
                                            onBlur={() => saveAssetImageRatioConfig()}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault();
                                                    saveAssetImageRatioConfig();
                                                }
                                            }}
                                            disabled={isAssetImageRatioConfigSaving}
                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                            placeholder="16:9"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('封面图比例', 'Cover Image Ratio')}</label>
                                        <input
                                            value={coverAssetAspectRatio}
                                            onChange={(e) => setCoverAssetAspectRatio(e.target.value)}
                                            onBlur={() => saveAssetImageRatioConfig()}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault();
                                                    saveAssetImageRatioConfig();
                                                }
                                            }}
                                            disabled={isAssetImageRatioConfigSaving}
                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                            placeholder="3:4"
                                        />
                                    </div>
                                </div>
                            </div>
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
                                        onClick={() => {
                                            const section = document.getElementById('task-default-api-mapping-crud');
                                            if (section) {
                                                section.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                            }
                                        }}
                                        className="bg-cyan-700 hover:bg-cyan-600 text-white px-3 py-1 rounded flex items-center gap-2"
                                        title={t('快速跳转到类别默认 API 映射 CRUD 区块', 'Jump to category default API mapping CRUD section')}
                                    >
                                        <List size={16} /> {t('默认 API 映射', 'Default API Mapping')}
                                    </button>
                                    <button
                                        onClick={fetchSystemApiManageRows}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2"
                                    >
                                        <RefreshCw size={16} /> {t('刷新', 'Refresh')}
                                    </button>
                                    <button
                                        onClick={handleCheckMissingBillingRuleApis}
                                        disabled={isMissingBillingRuleCheckLoading}
                                        className="bg-indigo-700 hover:bg-indigo-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                        title={t('检查哪些 System API 没有对应计费规则', 'Check which System APIs are missing billing rules')}
                                    >
                                        <List size={16} /> {isMissingBillingRuleCheckLoading ? t('检查中...', 'Checking...') : t('检查缺失规则 API', 'Check Missing-Rule APIs')}
                                    </button>
                                </div>
                            </div>

                            {systemApiEditToast && (
                                <div className="rounded border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
                                    {systemApiEditToast}
                                </div>
                            )}

                            <div className="border border-indigo-500/30 rounded-lg p-4 bg-indigo-500/5 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <div className="text-sm font-semibold text-indigo-200">
                                        {t('未关联计费规则的 System API（已排除弃用和停用）', 'System APIs Missing Billing Rules (Deprecated and Inactive Excluded)')}
                                    </div>
                                    <div className="text-xs text-indigo-100/80">
                                        {t('共', 'Total')} {missingBillingRuleApiRows.length} {t('条', 'items')}
                                    </div>
                                </div>
                                {isMissingBillingRuleCheckLoading ? (
                                    <div className="text-xs text-gray-300">{t('检查中...', 'Checking...')}</div>
                                ) : (
                                    <>
                                    <div className="md:hidden space-y-2">
                                        {missingBillingRuleApiRows.map((row) => (
                                            <div key={`missing-billing-card-${row.id}`} className="rounded-lg border border-indigo-400/20 bg-indigo-500/10 p-3 text-xs space-y-2">
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="min-w-0">
                                                        <div className="font-semibold text-indigo-100 break-all">#{row.id} {row.name || '-'}</div>
                                                        <div className="text-indigo-100/70 mt-1">[{row.category || '-'}] {row.provider || '-'} / {row.model || '-'}</div>
                                                    </div>
                                                    <span className="shrink-0 rounded bg-indigo-950/60 px-2 py-1 text-[11px] text-indigo-100">{row.base_model || '-'}</span>
                                                </div>
                                                <div className="grid grid-cols-2 gap-2 text-[11px] text-indigo-100/80">
                                                    <div className="rounded bg-black/20 px-2 py-1.5">
                                                        <div className="text-indigo-100/50 mb-1">{t('类别', 'Category')}</div>
                                                        <div>{row.category || '-'}</div>
                                                    </div>
                                                    <div className="rounded bg-black/20 px-2 py-1.5">
                                                        <div className="text-indigo-100/50 mb-1">{t('类别默认', 'Category Default')}</div>
                                                        <div>{row.is_active ? t('是', 'Yes') : t('否', 'No')}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                        {missingBillingRuleApiRows.length === 0 && (
                                            <div className="rounded border border-indigo-400/20 px-3 py-4 text-indigo-100/80 text-xs">
                                                {t('暂无缺失项，请点击“检查缺失规则 API”执行检测。', 'No missing items yet. Click "Check Missing-Rule APIs" to run detection.')}
                                            </div>
                                        )}
                                    </div>
                                    <div className="hidden md:block overflow-x-auto max-h-[220px] border border-indigo-400/20 rounded">
                                        <table className="w-full text-xs min-w-[680px]">
                                            <thead className="bg-indigo-500/10 text-indigo-100 sticky top-0">
                                                <tr>
                                                    <th className="text-left p-2">ID</th>
                                                    <th className="text-left p-2">{t('类别', 'Category')}</th>
                                                    <th className="text-left p-2">{t('提供方', 'Provider')}</th>
                                                    <th className="text-left p-2">{t('模型', 'Model')}</th>
                                                    <th className="text-left p-2">{t('基础模型', 'Base Model')}</th>
                                                    <th className="text-left p-2">{t('名称', 'Name')}</th>
                                                    <th className="text-left p-2">{t('类别默认', 'Category Default')}</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {missingBillingRuleApiRows.map((row) => (
                                                    <tr key={`missing-billing-${row.id}`} className="border-t border-indigo-400/20">
                                                        <td className="p-2">{row.id}</td>
                                                        <td className="p-2">{row.category || '-'}</td>
                                                        <td className="p-2">{row.provider || '-'}</td>
                                                        <td className="p-2">{row.model || '-'}</td>
                                                        <td className="p-2">{row.base_model || '-'}</td>
                                                        <td className="p-2">{row.name || '-'}</td>
                                                        <td className="p-2">{row.is_active ? t('是', 'Yes') : t('否', 'No')}</td>
                                                    </tr>
                                                ))}
                                                {missingBillingRuleApiRows.length === 0 && (
                                                    <tr className="border-t border-indigo-400/20">
                                                        <td className="p-3 text-indigo-100/80" colSpan={7}>{t('暂无缺失项，请点击“检查缺失规则 API”执行检测。', 'No missing items yet. Click "Check Missing-Rule APIs" to run detection.')}</td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                    </>
                                )}
                            </div>

                            {isSystemApiLoading ? (
                                <div className="text-sm text-gray-400">{t('加载中...', 'Loading...')}</div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="border border-emerald-500/30 rounded-lg p-4 bg-emerald-500/5 space-y-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <h4 className="text-sm font-bold text-emerald-200">{t('供应商密钥池 CRUD（provider_key_pool）', 'Provider Key Pool CRUD (provider_key_pool)')}</h4>
                                            <button onClick={fetchProviderKeyPools} className="text-xs text-emerald-300 hover:text-emerald-100 flex items-center gap-1"><RefreshCw size={12} /> {t('刷新', 'Refresh')}</button>
                                        </div>

                                        {isProviderKeyPoolLoading ? (
                                            <div className="text-xs text-gray-400">{t('加载中...', 'Loading...')}</div>
                                        ) : (
                                            <>
                                                <div className="md:hidden space-y-2">
                                                    {providerKeyPoolRows.map((row) => (
                                                        <button
                                                            key={`key-pool-card-${row.id}`}
                                                            type="button"
                                                            onClick={() => setSelectedKeyPoolId(String(row.id))}
                                                            className={`w-full rounded-lg border p-3 text-left space-y-2 transition-colors ${String(row.id) === String(selectedKeyPoolId) ? 'border-emerald-400/40 bg-emerald-500/10' : 'border-white/10 bg-black/20 hover:bg-white/5'}`}
                                                        >
                                                            <div className="flex items-start justify-between gap-3">
                                                                <div className="min-w-0">
                                                                    <div className="font-semibold text-sm text-white">#{row.id} {row.provider || '-'}</div>
                                                                    <div className="text-xs text-gray-400 mt-1 break-all">{row.provider_alias || '-'}</div>
                                                                </div>
                                                                <span className="shrink-0 rounded bg-emerald-950/60 px-2 py-1 text-[11px] text-emerald-100">{row.strategy || 'random'}</span>
                                                            </div>
                                                            <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-300">
                                                                <div className="rounded bg-black/20 px-2 py-1.5">
                                                                    <div className="text-gray-500 mb-1">{t('密钥数', 'Keys')}</div>
                                                                    <div>{Array.isArray(row.api_keys) ? row.api_keys.length : 0}</div>
                                                                </div>
                                                                <div className="rounded bg-black/20 px-2 py-1.5">
                                                                    <div className="text-gray-500 mb-1">{t('更新时间', 'Updated')}</div>
                                                                    <div>{row.updated_at || '-'}</div>
                                                                </div>
                                                            </div>
                                                            <div className="text-[11px] text-gray-400 break-all">
                                                                <span className="text-gray-500">{t('介绍 URL', 'Intro URL')}:</span> {row.intro_url || '-'}
                                                            </div>
                                                        </button>
                                                    ))}
                                                    {providerKeyPoolRows.length === 0 && (
                                                        <div className="rounded border border-white/10 px-3 py-4 text-center text-xs text-gray-500">{t('暂无数据', 'No data')}</div>
                                                    )}
                                                </div>
                                                <div className="hidden md:block overflow-x-auto">
                                                    <table className="w-full text-xs">
                                                        <thead>
                                                            <tr className="text-gray-400 border-b border-white/10">
                                                                <th className="text-left py-1.5 px-2">ID</th>
                                                                <th className="text-left py-1.5 px-2">Provider</th>
                                                                <th className="text-left py-1.5 px-2">{t('供应商别名', 'Provider Alias')}</th>
                                                                <th className="text-left py-1.5 px-2">{t('密钥数', 'Keys')}</th>
                                                                <th className="text-left py-1.5 px-2">{t('策略', 'Strategy')}</th>
                                                                <th className="text-left py-1.5 px-2">{t('介绍 URL', 'Intro URL')}</th>
                                                                <th className="text-left py-1.5 px-2">{t('更新时间', 'Updated')}</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {providerKeyPoolRows.map((row) => (
                                                                <tr key={row.id}
                                                                    className={`border-b border-white/5 cursor-pointer hover:bg-white/5 ${String(row.id) === String(selectedKeyPoolId) ? 'bg-emerald-500/10' : ''}`}
                                                                    onClick={() => setSelectedKeyPoolId(String(row.id))}
                                                                >
                                                                    <td className="py-1.5 px-2">{row.id}</td>
                                                                    <td className="py-1.5 px-2 font-mono">{row.provider}</td>
                                                                    <td className="py-1.5 px-2">{row.provider_alias || '-'}</td>
                                                                    <td className="py-1.5 px-2">{Array.isArray(row.api_keys) ? row.api_keys.length : 0}</td>
                                                                    <td className="py-1.5 px-2">{row.strategy || 'random'}</td>
                                                                    <td className="py-1.5 px-2 max-w-[220px] truncate" title={row.intro_url || '-'}>{row.intro_url || '-'}</td>
                                                                    <td className="py-1.5 px-2 text-gray-500">{row.updated_at || '-'}</td>
                                                                </tr>
                                                            ))}
                                                            {providerKeyPoolRows.length === 0 && (
                                                                <tr><td colSpan={7} className="py-3 px-2 text-center text-gray-500">{t('暂无数据', 'No data')}</td></tr>
                                                            )}
                                                        </tbody>
                                                    </table>
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">Provider</label>
                                                        <input
                                                            value={keyPoolForm.provider}
                                                            onChange={(e) => setKeyPoolForm(f => ({ ...f, provider: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                            placeholder="e.g. openai"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('供应商别名', 'Provider Alias')}</label>
                                                        <input
                                                            value={keyPoolForm.provider_alias}
                                                            onChange={(e) => setKeyPoolForm(f => ({ ...f, provider_alias: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                            placeholder={t('例如 OpenAI 官方', 'e.g. OpenAI Official')}
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('策略', 'Strategy')}</label>
                                                        <select
                                                            value={keyPoolForm.strategy}
                                                            onChange={(e) => setKeyPoolForm(f => ({ ...f, strategy: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        >
                                                            <option value="random">{t('随机', 'Random')}</option>
                                                            <option value="round_robin">{t('轮询', 'Round Robin')}</option>
                                                            <option value="weighted">{t('权重随机', 'Weighted Random')}</option>
                                                        </select>
                                                    </div>
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">{t('供应商介绍 URL', 'Provider Intro URL')}</label>
                                                    <input
                                                        value={keyPoolForm.intro_url}
                                                        onChange={(e) => setKeyPoolForm(f => ({ ...f, intro_url: e.target.value }))}
                                                        className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        placeholder="https://example.com/provider-docs"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">{t('密钥池（按行或逗号分隔）', 'API Keys (newline/comma separated)')}</label>
                                                    <textarea
                                                        value={keyPoolForm.api_keys}
                                                        onChange={(e) => setKeyPoolForm(f => ({ ...f, api_keys: e.target.value }))}
                                                        rows={4}
                                                        className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                        placeholder={"sk-key-1\nsk-key-2"}
                                                    />
                                                </div>
                                                {keyPoolForm.strategy === 'weighted' && (
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('权重（与 key 顺序对应）', 'Weights (same order as keys)')}</label>
                                                        <textarea
                                                            value={keyPoolForm.weights}
                                                            onChange={(e) => setKeyPoolForm(f => ({ ...f, weights: e.target.value }))}
                                                            rows={3}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                            placeholder={"1\n3\n1"}
                                                        />
                                                    </div>
                                                )}
                                                <div className="flex items-center gap-2">
                                                    <button onClick={handleCreateKeyPool} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-xs flex items-center gap-1"><Plus size={12} /> {t('新建', 'Create')}</button>
                                                    <button onClick={handleUpdateKeyPool} disabled={!selectedKeyPoolId} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-bold rounded text-xs flex items-center gap-1"><Edit2 size={12} /> {t('更新', 'Update')}</button>
                                                    <button onClick={handleDeleteKeyPool} disabled={!selectedKeyPoolId} className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-bold rounded text-xs flex items-center gap-1"><Trash2 size={12} /> {t('删除', 'Delete')}</button>
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    <div id="task-default-api-mapping-crud" className="border border-cyan-500/30 rounded-lg p-4 bg-cyan-500/5 space-y-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <h4 className="text-sm font-bold text-cyan-200">{t('类别默认 API 映射 CRUD', 'Category Default API Mapping CRUD')}</h4>
                                            <button
                                                onClick={fetchTaskDefaultApis}
                                                disabled={isTaskDefaultApiLoading}
                                                className="text-xs text-cyan-300 hover:text-cyan-100 flex items-center gap-1 disabled:opacity-50"
                                            >
                                                <RefreshCw size={12} /> {t('刷新', 'Refresh')}
                                            </button>
                                        </div>

                                        {isTaskDefaultApiLoading ? (
                                            <div className="text-xs text-gray-400">{t('加载中...', 'Loading...')}</div>
                                        ) : (
                                            <>
                                                <div className="overflow-x-auto border border-cyan-500/20 rounded max-h-44">
                                                    <table className="w-full text-xs">
                                                        <thead className="bg-cyan-500/10 text-cyan-100 sticky top-0">
                                                            <tr>
                                                                <th className="text-left py-1.5 px-2">task_category</th>
                                                                <th className="text-left py-1.5 px-2">system_api_id</th>
                                                                <th className="text-left py-1.5 px-2">{t('目标 API', 'Target API')}</th>
                                                                <th className="text-left py-1.5 px-2">{t('更新时间', 'Updated')}</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {taskDefaultApiRows.map((row) => (
                                                                <tr
                                                                    key={`task-default-${row.task_category}`}
                                                                    className={`border-t border-cyan-500/20 cursor-pointer hover:bg-white/5 ${String(selectedTaskDefaultCategory) === String(row.task_category) ? 'bg-cyan-500/10' : ''}`}
                                                                    onClick={() => setSelectedTaskDefaultCategory(String(row.task_category || ''))}
                                                                >
                                                                    <td className="py-1.5 px-2 font-mono">{row.task_category}</td>
                                                                    <td className="py-1.5 px-2">{row.system_api_id}</td>
                                                                    <td className="py-1.5 px-2">{`[${row.system_api_category || '-'}] ${row.system_api_provider || '-'} / ${row.system_api_model || '-'}`}</td>
                                                                    <td className="py-1.5 px-2 text-gray-500">{row.updated_at || '-'}</td>
                                                                </tr>
                                                            ))}
                                                            {taskDefaultApiRows.length === 0 && (
                                                                <tr>
                                                                    <td colSpan={4} className="py-3 px-2 text-center text-gray-500">{t('暂无映射记录', 'No mapping records')}</td>
                                                                </tr>
                                                            )}
                                                        </tbody>
                                                    </table>
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">task_category</label>
                                                        <input
                                                            value={taskDefaultForm.task_category}
                                                            onChange={(e) => setTaskDefaultForm((prev) => ({ ...prev, task_category: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                            placeholder="LLM / IMAGE / VIDEO / DIGITAL_HUMAN / VOICE / MUSIC"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">system_api_id</label>
                                                        <select
                                                            value={taskDefaultForm.system_api_id}
                                                            onChange={(e) => setTaskDefaultForm((prev) => ({ ...prev, system_api_id: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        >
                                                            <option value="">{t('请选择目标 System API', 'Select target System API')}</option>
                                                            {systemApiRows
                                                                .filter((row) => !String(row?.category || '').startsWith('System_'))
                                                                .map((row) => (
                                                                    <option key={`task-default-target-${row.id}`} value={row.id}>
                                                                        {`#${row.id} [${row.category || '-'}] ${row.provider || '-'} / ${row.model || '-'}`}
                                                                    </option>
                                                                ))}
                                                        </select>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    <button onClick={handleCreateTaskDefaultApi} className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded text-xs flex items-center gap-1"><Plus size={12} /> {t('新建', 'Create')}</button>
                                                    <button onClick={handleUpdateTaskDefaultApi} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded text-xs flex items-center gap-1"><Edit2 size={12} /> {t('更新', 'Update')}</button>
                                                    <button onClick={handleDeleteTaskDefaultApi} className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white font-bold rounded text-xs flex items-center gap-1"><Trash2 size={12} /> {t('删除', 'Delete')}</button>
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    <div className="border border-fuchsia-500/30 rounded-lg p-4 bg-fuchsia-500/5 space-y-3">
                                        <input
                                            ref={kieBundleImportInputRef}
                                            type="file"
                                            accept="application/json,.json"
                                            className="hidden"
                                            onChange={handleImportKieDictionaryBundleFile}
                                        />
                                        <div className="flex items-center justify-between gap-2">
                                            <h4 className="text-sm font-bold text-fuchsia-200">{t('KIE 数据字典（值+映射）CRUD', 'KIE Dictionary (Values + Mappings) CRUD')}</h4>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={handleOpenImportKieDictionaryBundle}
                                                    disabled={isKieBundleImporting || isKieStandardLoading}
                                                    className="text-xs bg-fuchsia-700 hover:bg-fuchsia-600 text-white px-2 py-1 rounded disabled:opacity-50 flex items-center gap-1"
                                                    title={t('导入 KIE 数据字典包（包含标准值与映射）', 'Import KIE dictionary bundle (values + mappings)')}
                                                >
                                                    <Upload size={12} /> {isKieBundleImporting ? t('导入中...', 'Importing...') : t('导入字典包', 'Import Dictionary Bundle')}
                                                </button>
                                                <button
                                                    onClick={handleExportKieDictionaryBundle}
                                                    disabled={isKieBundleExporting || isKieStandardLoading}
                                                    className="text-xs bg-purple-700 hover:bg-purple-600 text-white px-2 py-1 rounded disabled:opacity-50 flex items-center gap-1"
                                                    title={t('导出 KIE 数据字典包（包含标准值与映射）', 'Export KIE dictionary bundle (values + mappings)')}
                                                >
                                                    <Download size={12} /> {isKieBundleExporting ? t('导出中...', 'Exporting...') : t('导出字典包', 'Export Dictionary Bundle')}
                                                </button>
                                                <button
                                                    onClick={handleInferKieBillingRelated}
                                                    disabled={isKieBillingInferLoading || isKieStandardLoading}
                                                    className="text-xs bg-indigo-700 hover:bg-indigo-600 text-white px-2 py-1 rounded disabled:opacity-50"
                                                    title={t('从计费规则反推并更新 is_billing_related 字段', 'Infer billing-related flags from billing rules and update is_billing_related')}
                                                >
                                                    {isKieBillingInferLoading ? t('反推中...', 'Inferring...') : t('反推计费关联', 'Infer Billing Related')}
                                                </button>
                                                <button
                                                    onClick={fetchKieStandardMappingsAndValues}
                                                    disabled={isKieStandardLoading}
                                                    className="text-xs text-fuchsia-300 hover:text-fuchsia-100 flex items-center gap-1 disabled:opacity-50"
                                                >
                                                    <RefreshCw size={12} /> {t('刷新', 'Refresh')}
                                                </button>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                                            <input
                                                value={kieStandardSearchText}
                                                onChange={(e) => setKieStandardSearchText(e.target.value)}
                                                className="bg-black/40 border border-gray-700 rounded p-2 text-xs md:col-span-2"
                                                placeholder={t('关键词：模型/字段/枚举/标准值', 'Keyword: model/field/enum/standard value')}
                                            />
                                            <select
                                                value={kieStandardDimensionFilter}
                                                onChange={(e) => setKieStandardDimensionFilter(e.target.value)}
                                                className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                            >
                                                <option value="all">{t('全部维度', 'All Dimensions')}</option>
                                                {Array.from(new Set((kieStandardValueRows || []).map((row) => String(row?.standard_dimension || '').trim()).filter(Boolean))).sort().map((dim) => (
                                                    <option key={`kie-dim-${dim}`} value={dim}>{dim}</option>
                                                ))}
                                            </select>
                                            <label className="flex items-center gap-2 text-xs text-gray-300 px-2">
                                                <input
                                                    type="checkbox"
                                                    checked={kieStandardBillingOnly}
                                                    onChange={(e) => setKieStandardBillingOnly(e.target.checked)}
                                                />
                                                {t('仅计费相关', 'Billing Related Only')}
                                            </label>
                                        </div>

                                        {isKieStandardLoading ? (
                                            <div className="text-xs text-gray-400">{t('加载中...', 'Loading...')}</div>
                                        ) : (
                                            <>
                                                <div className="overflow-x-auto border border-fuchsia-500/20 rounded max-h-56">
                                                    <table className="w-full text-xs min-w-[980px]">
                                                        <thead className="bg-fuchsia-500/10 text-fuchsia-100 sticky top-0">
                                                            <tr>
                                                                <th className="text-left py-1.5 px-2">ID</th>
                                                                <th className="text-left py-1.5 px-2">model_key</th>
                                                                <th className="text-left py-1.5 px-2">source_field</th>
                                                                <th className="text-left py-1.5 px-2">source_enum</th>
                                                                <th className="text-left py-1.5 px-2">dimension</th>
                                                                <th className="text-left py-1.5 px-2">standard_value</th>
                                                                <th className="text-left py-1.5 px-2">{t('计费相关', 'Billing Related')}</th>
                                                                <th className="text-left py-1.5 px-2">{t('启用', 'Active')}</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {(kieStandardMappingRows || []).map((row) => (
                                                                <tr
                                                                    key={`kie-mapping-${row.id}`}
                                                                    className={`border-t border-fuchsia-500/20 cursor-pointer hover:bg-white/5 ${String(selectedKieStandardMappingId) === String(row.id) ? 'bg-fuchsia-500/10' : ''}`}
                                                                    onClick={() => setSelectedKieStandardMappingId(String(row.id))}
                                                                >
                                                                    <td className="py-1.5 px-2">{row.id}</td>
                                                                    <td className="py-1.5 px-2 font-mono">{row.model_key_inferred || '-'}</td>
                                                                    <td className="py-1.5 px-2 font-mono">{row.source_field || '-'}</td>
                                                                    <td className="py-1.5 px-2">{row.source_enum_value || '-'}</td>
                                                                    <td className="py-1.5 px-2">{row.standard_dimension || '-'}</td>
                                                                    <td className="py-1.5 px-2">{row.standard_value || '-'}</td>
                                                                    <td className="py-1.5 px-2">{row.is_billing_related ? t('是', 'Yes') : t('否', 'No')}</td>
                                                                    <td className="py-1.5 px-2">{row.is_active ? t('是', 'Yes') : t('否', 'No')}</td>
                                                                </tr>
                                                            ))}
                                                            {(kieStandardMappingRows || []).length === 0 && (
                                                                <tr>
                                                                    <td colSpan={8} className="py-3 px-2 text-center text-gray-500">{t('暂无映射记录', 'No mapping records')}</td>
                                                                </tr>
                                                            )}
                                                        </tbody>
                                                    </table>
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">provider</label>
                                                        <input
                                                            value={kieStandardMappingForm.provider}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, provider: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">model_key_inferred</label>
                                                        <input
                                                            value={kieStandardMappingForm.model_key_inferred}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, model_key_inferred: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">source_field</label>
                                                        <input
                                                            value={kieStandardMappingForm.source_field}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, source_field: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">source_enum_value</label>
                                                        <input
                                                            value={kieStandardMappingForm.source_enum_value}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, source_enum_value: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">standard_dimension</label>
                                                        <input
                                                            value={kieStandardMappingForm.standard_dimension}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, standard_dimension: e.target.value.toUpperCase() }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                            list="kie-standard-dimension-list"
                                                        />
                                                        <datalist id="kie-standard-dimension-list">
                                                            {Array.from(new Set((kieStandardValueRows || []).map((row) => String(row?.standard_dimension || '').trim()).filter(Boolean))).sort().map((dim) => (
                                                                <option key={`kie-dim-option-${dim}`} value={dim} />
                                                            ))}
                                                        </datalist>
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">standard_value</label>
                                                        <input
                                                            value={kieStandardMappingForm.standard_value}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, standard_value: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">confidence</label>
                                                        <input
                                                            value={kieStandardMappingForm.confidence}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, confidence: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                            placeholder="HIGH / MEDIUM / LOW"
                                                        />
                                                    </div>
                                                    <div className="md:col-span-2">
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">note</label>
                                                        <input
                                                            value={kieStandardMappingForm.note}
                                                            onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, note: e.target.value }))}
                                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                        />
                                                    </div>
                                                    <div className="md:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                                                        <label className="flex items-center gap-2 text-xs text-gray-300 px-2 py-1">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!kieStandardMappingForm.is_active}
                                                                onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                                                            />
                                                            {t('启用', 'Active')}
                                                        </label>
                                                        <label className="flex items-center gap-2 text-xs text-gray-300 px-2 py-1">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!kieStandardMappingForm.is_billing_related}
                                                                onChange={(e) => setKieStandardMappingForm((prev) => ({ ...prev, is_billing_related: e.target.checked }))}
                                                            />
                                                            {t('计费相关', 'Billing Related')}
                                                        </label>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    <button
                                                        onClick={handleCreateKieStandardMapping}
                                                        disabled={isKieStandardSaving}
                                                        className="px-3 py-1.5 bg-fuchsia-600 hover:bg-fuchsia-500 text-white font-bold rounded text-xs flex items-center gap-1 disabled:opacity-50"
                                                    >
                                                        <Plus size={12} /> {t('新建', 'Create')}
                                                    </button>
                                                    <button
                                                        onClick={handleUpdateKieStandardMapping}
                                                        disabled={isKieStandardSaving || !selectedKieStandardMappingId}
                                                        className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded text-xs flex items-center gap-1 disabled:opacity-50"
                                                    >
                                                        <Edit2 size={12} /> {t('更新', 'Update')}
                                                    </button>
                                                    <button
                                                        onClick={handleDeleteKieStandardMapping}
                                                        disabled={isKieStandardSaving || !selectedKieStandardMappingId}
                                                        className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white font-bold rounded text-xs flex items-center gap-1 disabled:opacity-50"
                                                    >
                                                        <Trash2 size={12} /> {t('删除', 'Delete')}
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            setSelectedKieStandardMappingId('');
                                                            setKieStandardMappingForm(createEmptyKieStandardMappingForm());
                                                        }}
                                                        className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded text-xs"
                                                    >
                                                        {t('清空表单', 'Clear Form')}
                                                    </button>
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    <div className="flex flex-col gap-4">
                                    <div className="border border-white/10 rounded-lg p-4 bg-black/20 space-y-3">
                                        <div className="text-[11px] text-gray-300 bg-white/5 border border-white/10 rounded p-2 leading-relaxed">
                                            {t('智能路由规则：多参考图（>4）会优先尝试“多图默认 API”；主通道达到重试上限后，按同类别优先级（数字越小越优先）依次回退。', 'Smart routing rule: multi-reference image jobs (>4) first try the “multi-ref default API”; after retry limit on the main path, fallback follows same-category priority (lower number first).')}
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                                            <div>
                                                <label className="text-xs uppercase text-gray-400">{t('模型类型筛选', 'Model Type Filter')}</label>
                                                <select
                                                    value={systemApiFilterCategory}
                                                    onChange={(e) => {
                                                        setSystemApiFilterCategory(e.target.value);
                                                        setSystemApiFilterProvider('all');
                                                        setSystemApiFilterRetryGroup('all');
                                                        setSystemApiFilterRetryPriceGroup('all');
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
                                                    onChange={(e) => {
                                                        setSystemApiFilterProvider(e.target.value);
                                                        setSystemApiFilterRetryGroup('all');
                                                        setSystemApiFilterRetryPriceGroup('all');
                                                    }}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="all">{t('全部供应商', 'All Providers')}</option>
                                                    {systemApiProviderOptions.map((provider) => (
                                                        <option key={provider} value={provider}>{provider}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="text-xs uppercase text-gray-400">{t('回退分组筛选', 'Retry Group Filter')}</label>
                                                <select
                                                    value={systemApiFilterRetryGroup}
                                                    onChange={(e) => {
                                                        setSystemApiFilterRetryGroup(e.target.value);
                                                        setSystemApiFilterRetryPriceGroup('all');
                                                    }}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="all">{t('全部分组', 'All Retry Groups')}</option>
                                                    <option value={SYSTEM_API_FILTER_HAS_VALUE}>{t('仅有值', 'Has Value Only')}</option>
                                                    <option value={SYSTEM_API_FILTER_EMPTY_VALUE}>{t('仅空值', 'Empty Only')}</option>
                                                    {systemApiRetryGroupOptions.map((retryGroup) => (
                                                        <option key={retryGroup} value={retryGroup}>{retryGroup}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="text-xs uppercase text-gray-400">{t('价格档位筛选', 'Price Tier Filter')}</label>
                                                <select
                                                    value={systemApiFilterRetryPriceGroup}
                                                    onChange={(e) => setSystemApiFilterRetryPriceGroup(e.target.value)}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="all">{t('全部档位', 'All Price Tiers')}</option>
                                                    <option value={SYSTEM_API_FILTER_HAS_VALUE}>{t('仅有值', 'Has Value Only')}</option>
                                                    <option value={SYSTEM_API_FILTER_EMPTY_VALUE}>{t('仅空值', 'Empty Only')}</option>
                                                    {systemApiRetryPriceGroupOptions.map((retryPriceGroup) => (
                                                        <option key={retryPriceGroup} value={retryPriceGroup}>{retryPriceGroup}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="text-xs uppercase text-gray-400">{t('调用能力筛选', 'Capability Filter')}</label>
                                                <select
                                                    value={systemApiCapabilityFilter}
                                                    onChange={(e) => setSystemApiCapabilityFilter(e.target.value)}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="all">{t('全部能力', 'All Capability States')}</option>
                                                    <option value="callable">{t('仅启用', 'Enabled Only')}</option>
                                                    <option value="not_callable">{t('仅禁用', 'Disabled Only')}</option>
                                                    <option value="staging_only">{t('缺少运行时元数据', 'Missing Runtime Metadata')}</option>
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
                                                        setSystemApiFilterRetryGroup('all');
                                                        setSystemApiFilterRetryPriceGroup('all');
                                                        setSystemApiCapabilityFilter('all');
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
                                                    onClick={() => {
                                                        setIsSystemApiEditing(true);
                                                        setSelectedSystemApiId('');
                                                        showSystemApiEditToast(t('已进入新建 API 编辑', 'Entered new API editor'));
                                                    }}
                                                    className="px-2.5 py-1 rounded border border-emerald-500/40 text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20"
                                                    title={t('新建 System API 配置', 'Create a new System API setting')}
                                                >
                                                    {t('新建 API', 'New API')}
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        if (!selectedSystemApiId) {
                                                            alert(t('请先选择一条 API 配置', 'Select a System API setting first'));
                                                            return;
                                                        }
                                                        setIsSystemApiEditing(true);
                                                        showSystemApiEditToast(t('已进入 API 编辑模式', 'Entered API edit mode'));
                                                    }}
                                                    className="px-2.5 py-1 rounded border border-sky-500/40 text-sky-300 bg-sky-500/10 hover:bg-sky-500/20"
                                                    title={t('编辑当前选中项', 'Edit selected item')}
                                                >
                                                    {t('编辑选中', 'Edit Selected')}
                                                </button>
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

                                        <div className="border border-cyan-500/20 rounded-lg p-3 bg-cyan-500/5 space-y-2">
                                            <div className="flex items-center justify-between gap-2">
                                                <div className="text-xs font-semibold text-cyan-200">{t('供应商功能入口（按数据去重）', 'Provider Capability Entry (Deduped by Data)')}</div>
                                                <div className="text-[11px] text-cyan-100/70">{t('点击下方 provider 快速筛选；“已启用”表示当前未被 system_api_settings.deprecated 禁用。', 'Click a provider below to filter quickly; “Enabled” means the row is not disabled by system_api_settings.deprecated.')}</div>
                                            </div>
                                            <div className="flex flex-wrap gap-2">
                                                {systemApiProviderSummaryRows.map((item) => {
                                                    const isSelected = String(systemApiFilterProvider || 'all') === String(item.provider || '');
                                                    return (
                                                        <button
                                                            key={`system-api-provider-summary-${item.provider}`}
                                                            type="button"
                                                            onClick={() => {
                                                                setSystemApiFilterProvider(String(item.provider || 'all'));
                                                                setSystemApiFilterRetryGroup('all');
                                                                setSystemApiFilterRetryPriceGroup('all');
                                                            }}
                                                            className={`rounded-lg border px-3 py-2 text-left min-w-[180px] ${isSelected ? 'border-cyan-300 bg-cyan-700/20 text-cyan-50' : 'border-cyan-500/20 bg-black/20 text-cyan-100/90 hover:bg-cyan-500/10'}`}
                                                            title={item.categories.join(', ') || '-'}
                                                        >
                                                            <div className="flex items-center justify-between gap-2">
                                                                <span className="font-mono text-xs font-semibold">{item.provider}</span>
                                                                <span className={`rounded px-1.5 py-0.5 text-[10px] ${item.has_callable_entry ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-200 border border-amber-500/30'}`}>
                                                                    {item.has_callable_entry ? t('已启用', 'Enabled') : t('已禁用', 'Disabled')}
                                                                </span>
                                                            </div>
                                                            <div className="mt-1 text-[11px] text-cyan-100/70">
                                                                {t('行数', 'Rows')}: {item.total_rows} | {t('已启用', 'Enabled')}: {item.callable_rows}
                                                            </div>
                                                            <div className="text-[11px] text-cyan-100/60">
                                                                {t('缺少运行时元数据', 'Missing Runtime Metadata')}: {item.staging_only_rows} | {t('默认', 'Default')}: {item.default_rows}
                                                            </div>
                                                        </button>
                                                    );
                                                })}
                                                {systemApiProviderSummaryRows.length === 0 && (
                                                    <div className="text-[11px] text-gray-400">{t('暂无 provider 数据', 'No provider summary data')}</div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="text-xs text-gray-400">
                                            {t('共', 'Total')} {systemApiRows.length} {t('条，当前显示', ', showing')} {visibleSystemApiRows.length} {t('条', 'items')}
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
                                                        <th className="text-left p-2 whitespace-nowrap">{t('基础模型', 'Base Model')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('名称', 'Name')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('分组', 'Group')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('价格档', 'Price Tier')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('Base URL', 'Base URL')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('模态', 'Modality')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('标签', 'Tags')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('弃用', 'Deprecated')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('API 调用能力', 'API Capability')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('智能策略', 'Smart Strategy')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('类别默认', 'Category Default')}</th>
                                                        <th className="text-left p-2 whitespace-nowrap">{t('操作', 'Actions')}</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {visibleSystemApiRows.map((row) => {
                                                        const capability = getSystemApiCapabilityInfo(row);
                                                        return (
                                                        <tr
                                                            key={row.id}
                                                            onClick={() => setSelectedSystemApiId(String(row.id))}
                                                            onDoubleClick={() => {
                                                                setSelectedSystemApiId(String(row.id));
                                                                setIsSystemApiEditing(true);
                                                                showSystemApiEditToast(t('已进入 API 编辑模式', 'Entered API edit mode'));
                                                            }}
                                                            className={`border-t border-white/10 cursor-pointer ${String(selectedSystemApiId) === String(row.id) ? 'bg-primary/10' : 'hover:bg-white/5'}`}
                                                        >
                                                            <td className="p-2">{row.id}</td>
                                                            <td className="p-2">{row.category}</td>
                                                            <td className="p-2">{row.provider}</td>
                                                            <td className="p-2 max-w-[220px] truncate" title={row.model || '-'}>{row.model || '-'}</td>
                                                            <td className="p-2 max-w-[220px] truncate" title={row.base_model || '-'}>{row.base_model || '-'}</td>
                                                            <td className="p-2 max-w-[160px] truncate" title={row.name || '-'}>{row.name || '-'}</td>
                                                            <td className="p-2 max-w-[140px] truncate" title={getSystemApiRetryGroup(row) || '-'}>{getSystemApiRetryGroup(row) || '-'}</td>
                                                            <td className="p-2 max-w-[120px] truncate" title={getSystemApiRetryPriceGroup(row) || '-'}>{getSystemApiRetryPriceGroup(row) || '-'}</td>
                                                            <td className="p-2 max-w-[200px] truncate" title={row.base_url || '-'}>{row.base_url || '-'}</td>
                                                            <td className="p-2 max-w-[160px] truncate" title={Array.isArray(row.generation_modes) ? row.generation_modes.join(', ') : '-'}>{Array.isArray(row.generation_modes) ? row.generation_modes.join(', ') : '-'}</td>
                                                            <td className="p-2 max-w-[120px] truncate" title={Array.isArray(row.tags) ? row.tags.join(', ') : '-'}>{Array.isArray(row.tags) && row.tags.length > 0 ? row.tags.join(', ') : '-'}</td>
                                                            <td className="p-2">
                                                                {isSystemApiDeprecated(row) ? (
                                                                    <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30">{t('已弃用', 'Deprecated')}</span>
                                                                ) : (
                                                                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">{t('正常', 'Active')}</span>
                                                                )}
                                                            </td>
                                                            <td className="p-2">
                                                                <div className="flex flex-col gap-1">
                                                                    <span className={`inline-flex w-fit px-1.5 py-0.5 rounded border text-[11px] ${capability.callable ? 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30' : 'bg-amber-500/20 text-amber-200 border-amber-500/30'}`}>
                                                                        {capability.label}
                                                                    </span>
                                                                    <span className="text-[10px] text-gray-500 max-w-[180px] truncate" title={capability.detail}>{capability.detail}</span>
                                                                </div>
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
                                                            <td className="p-2">{row.is_active ? t('默认', 'Default') : t('否', 'No')}</td>
                                                            <td className="p-2">
                                                                <button
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        handleToggleSingleSystemApiDeprecated(row);
                                                                    }}
                                                                    className={`px-2 py-0.5 rounded border text-[11px] ${isSystemApiDeprecated(row) ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20' : 'border-red-500/40 text-red-300 bg-red-500/10 hover:bg-red-500/20'}`}
                                                                >
                                                                    {isSystemApiDeprecated(row) ? t('取消弃用', 'Undeprecate') : t('弃用', 'Deprecate')}
                                                                </button>
                                                            </td>
                                                        </tr>
                                                    )})}
                                                    {visibleSystemApiRows.length === 0 && (
                                                        <tr className="border-t border-white/10">
                                                            <td className="p-3 text-gray-400" colSpan={16}>
                                                                {t('无匹配结果，请调整筛选条件。', 'No matching settings. Adjust your filters.')}
                                                            </td>
                                                        </tr>
                                                    )}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>

                                    {false && (
                                    <div className="border border-sky-500/30 rounded-lg p-4 bg-sky-500/5 space-y-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <h4 className="text-sm font-bold text-sky-200">{t('定价规则 CRUD（按模型）', 'Pricing Rule CRUD (per model)')}</h4>
                                            <button
                                                onClick={() => fetchBillingRulesForSystemApi(selectedSystemApiId)}
                                                disabled={isBillingRuleLoading || !selectedSystemApiId}
                                                className="text-xs text-sky-300 hover:text-sky-100 flex items-center gap-1 disabled:opacity-50"
                                            >
                                                <RefreshCw size={12} /> {t('刷新', 'Refresh')}
                                            </button>
                                        </div>

                                        {!selectedSystemApiId ? (
                                            <div className="text-xs text-gray-400">{t('请先在上方选择一个 System API 配置。', 'Select a System API setting above first.')}</div>
                                        ) : (
                                            <>
                                                <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                                                    <input
                                                        value={billingRuleFilterKeyword}
                                                        onChange={(e) => setBillingRuleFilterKeyword(e.target.value)}
                                                        placeholder={t('关键词（名称/描述/模式）', 'Keyword (name/description/mode)')}
                                                        className="md:col-span-2 bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                                    />
                                                    <select
                                                        value={billingRuleFilterStatus}
                                                        onChange={(e) => setBillingRuleFilterStatus(e.target.value)}
                                                        className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                                    >
                                                        <option value="all">{t('全部状态', 'All Status')}</option>
                                                        <option value="active">{t('启用', 'Active')}</option>
                                                        <option value="inactive">{t('停用', 'Inactive')}</option>
                                                    </select>
                                                    <select
                                                        value={billingRuleFilterTarget}
                                                        onChange={(e) => setBillingRuleFilterTarget(e.target.value)}
                                                        className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                                    >
                                                        <option value="all">{t('全部目标', 'All Targets')}</option>
                                                        <option value="text">Text</option>
                                                        <option value="image">Image</option>
                                                        <option value="video">Video</option>
                                                    </select>
                                                    <select
                                                        value={billingRuleFilterUnitType}
                                                        onChange={(e) => setBillingRuleFilterUnitType(e.target.value)}
                                                        className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                                    >
                                                        <option value="all">{t('全部计费单位', 'All Units')}</option>
                                                        <option value="per_call">per_call</option>
                                                        <option value="per_second">per_second</option>
                                                        <option value="per_minute">per_minute</option>
                                                        <option value="per_token">per_token</option>
                                                        <option value="per_1k_tokens">per_1k_tokens</option>
                                                        <option value="per_million_tokens">per_million_tokens</option>
                                                    </select>
                                                </div>

                                                {isBillingRuleLoading ? (
                                                    <div className="text-xs text-gray-400">{t('定价规则加载中...', 'Loading pricing rules...')}</div>
                                                ) : (
                                                    <div className="space-y-2">
                                                        <div className="flex items-center justify-between gap-2 text-xs text-gray-400">
                                                            <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                                                                <input
                                                                    type="checkbox"
                                                                    checked={allFilteredBillingRuleIds.length > 0 && selectedFilteredBillingRuleCount === allFilteredBillingRuleIds.length}
                                                                    onChange={(e) => toggleSelectAllFilteredBillingRules(e.target.checked)}
                                                                />
                                                                <span>{t('全选当前筛选结果', 'Select all filtered')}</span>
                                                            </label>
                                                            <span>{t(`已选 ${selectedBillingRuleIds.length} 条`, `${selectedBillingRuleIds.length} selected`)}</span>
                                                        </div>
                                                    <div className="overflow-x-auto max-h-[260px] border border-white/10 rounded">
                                                        <table className="w-full text-xs min-w-[1700px]">
                                                            <thead className="bg-white/5 text-gray-400 sticky top-0">
                                                                <tr>
                                                                    <th className="text-left p-2 w-8">
                                                                        <input
                                                                            type="checkbox"
                                                                            checked={allFilteredBillingRuleIds.length > 0 && selectedFilteredBillingRuleCount === allFilteredBillingRuleIds.length}
                                                                            onChange={(e) => toggleSelectAllFilteredBillingRules(e.target.checked)}
                                                                        />
                                                                    </th>
                                                                    <th className="text-left p-2">ID</th>
                                                                    <th className="text-left p-2">{t('名称', 'Name')}</th>
                                                                    <th className="text-left p-2">{t('状态', 'Status')}</th>
                                                                    <th className="text-left p-2">{t('优先级', 'Priority')}</th>
                                                                    <th className="text-left p-2">T</th>
                                                                    <th className="text-left p-2">I</th>
                                                                    <th className="text-left p-2">V</th>
                                                                    <th className="text-left p-2">generation_mode</th>
                                                                    <th className="text-left p-2">input_format</th>
                                                                    <th className="text-left p-2">output_format</th>
                                                                    <th className="text-left p-2">has_audio</th>
                                                                    <th className="text-left p-2">billing_unit_type</th>
                                                                    <th className="text-left p-2">billing_cost</th>
                                                                    <th className="text-left p-2">billing_cost_input</th>
                                                                    <th className="text-left p-2">billing_cost_output</th>
                                                                    <th className="text-left p-2">charge_multiplier</th>
                                                                    <th className="text-left p-2">{t('更新时间', 'Updated')}</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {filteredBillingRuleRows.map((row) => {
                                                                    return (
                                                                        <tr
                                                                            key={row.id}
                                                                            onClick={() => setSelectedBillingRuleId(String(row.id))}
                                                                            className={`border-t border-white/10 cursor-pointer ${String(selectedBillingRuleId) === String(row.id) ? 'bg-sky-500/10' : 'hover:bg-white/5'}`}
                                                                        >
                                                                            <td className="p-2" onClick={(e) => e.stopPropagation()}>
                                                                                <input
                                                                                    type="checkbox"
                                                                                    checked={selectedBillingRuleIdSet.has(Number(row.id))}
                                                                                    onChange={(e) => toggleBillingRuleSelection(row.id, e.target.checked)}
                                                                                />
                                                                            </td>
                                                                            <td className="p-2">{row.id}</td>
                                                                            <td className="p-2 max-w-[200px] truncate" title={row.name || '-'}>{row.name || '-'}</td>
                                                                            <td className="p-2">{row.is_active ? t('启用', 'Active') : t('停用', 'Inactive')}</td>
                                                                            <td className="p-2">{row.priority ?? 0}</td>
                                                                            <td className="p-2">{row?.applies_to_text ? t('是', 'Yes') : t('否', 'No')}</td>
                                                                            <td className="p-2">{row?.applies_to_image ? t('是', 'Yes') : t('否', 'No')}</td>
                                                                            <td className="p-2">{row?.applies_to_video ? t('是', 'Yes') : t('否', 'No')}</td>
                                                                            <td className="p-2">{row?.generation_mode || '-'}</td>
                                                                            <td className="p-2">{row?.input_format || '-'}</td>
                                                                            <td className="p-2">{row?.output_format || '-'}</td>
                                                                            <td className="p-2">{row?.has_audio === null || row?.has_audio === undefined ? '-' : (row?.has_audio ? t('是', 'Yes') : t('否', 'No'))}</td>
                                                                            <td className="p-2">{row?.billing_unit_type || 'per_call'}</td>
                                                                            <td className="p-2">{toNonNegativeInt(row?.billing_cost ?? 0)}</td>
                                                                            <td className="p-2">{toNonNegativeInt(row?.billing_cost_input ?? 0)}</td>
                                                                            <td className="p-2">{toNonNegativeInt(row?.billing_cost_output ?? 0)}</td>
                                                                            <td className="p-2">{toRuleChargeMultiplier(row?.charge_multiplier, 2).toFixed(2)}</td>
                                                                            <td className="p-2 text-gray-500">{row.updated_at || '-'}</td>
                                                                        </tr>
                                                                    );
                                                                })}
                                                                {filteredBillingRuleRows.length === 0 && (
                                                                    <tr className="border-t border-white/10">
                                                                        <td className="p-3 text-gray-400" colSpan={17}>{t('无匹配规则', 'No matching rules')}</td>
                                                                    </tr>
                                                                )}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                    </div>
                                                )}

                                                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('名称', 'Name')}</label>
                                                        <input value={billingRuleForm.name} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, name: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('优先级', 'Priority')}</label>
                                                        <input type="number" value={billingRuleForm.priority} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, priority: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('计费单位', 'Unit')}</label>
                                                        <select value={billingRuleForm.billing_unit_type} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_unit_type: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                                            <option value="per_call">per_call</option>
                                                            <option value="per_second">per_second</option>
                                                            <option value="per_minute">per_minute</option>
                                                            <option value="per_token">per_token</option>
                                                            <option value="per_1k_tokens">per_1k_tokens</option>
                                                            <option value="per_million_tokens">per_million_tokens</option>
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('状态', 'Status')}</label>
                                                        <select value={billingRuleForm.is_active ? 'active' : 'inactive'} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, is_active: e.target.value === 'active' }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                                            <option value="active">{t('启用', 'Active')}</option>
                                                            <option value="inactive">{t('停用', 'Inactive')}</option>
                                                        </select>
                                                    </div>
                                                    <div className="md:col-span-2">
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('描述', 'Description')}</label>
                                                        <input value={billingRuleForm.description} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, description: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('匹配模式', 'Mode')}</label>
                                                        <input value={billingRuleForm.generation_mode} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, generation_mode: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" placeholder="t2i / i2i / ..." />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">{t('音频要求', 'Has Audio')}</label>
                                                        <select value={billingRuleForm.has_audio} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, has_audio: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                                            <option value="any">Any</option>
                                                            <option value="true">true</option>
                                                            <option value="false">false</option>
                                                        </select>
                                                    </div>
                                                </div>

                                                <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                                                    <input type="number" placeholder="cost" value={billingRuleForm.billing_cost} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_cost: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    <input type="number" placeholder="cost_input" value={billingRuleForm.billing_cost_input} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_cost_input: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    <input type="number" placeholder="cost_output" value={billingRuleForm.billing_cost_output} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_cost_output: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    <input type="number" placeholder="total_tokens_min" value={billingRuleForm.total_tokens_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, total_tokens_min: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    <input type="number" placeholder="total_tokens_max" value={billingRuleForm.total_tokens_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, total_tokens_max: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                    <input type="number" placeholder="image_count_min" value={billingRuleForm.image_count_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, image_count_min: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                    <label className="flex items-center gap-2 text-xs text-gray-300">
                                                        <input type="checkbox" checked={!!billingRuleForm.applies_to_text} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, applies_to_text: e.target.checked }))} /> Text
                                                    </label>
                                                    <label className="flex items-center gap-2 text-xs text-gray-300">
                                                        <input type="checkbox" checked={!!billingRuleForm.applies_to_image} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, applies_to_image: e.target.checked }))} /> Image
                                                    </label>
                                                    <label className="flex items-center gap-2 text-xs text-gray-300">
                                                        <input type="checkbox" checked={!!billingRuleForm.applies_to_video} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, applies_to_video: e.target.checked }))} /> Video
                                                    </label>
                                                </div>

                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">extra_conditions (JSON object)</label>
                                                    <textarea
                                                        rows={3}
                                                        value={billingRuleForm.extra_conditions_text}
                                                        onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, extra_conditions_text: e.target.value }))}
                                                        className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono"
                                                    />
                                                </div>

                                                <div className="flex flex-wrap gap-2 pt-2 border-t border-white/10">
                                                    <button onClick={handleCreateBillingRule} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-xs flex items-center gap-1"><Plus size={12} /> {t('新建规则', 'Create Rule')}</button>
                                                    <button onClick={handleUpdateBillingRule} disabled={!selectedBillingRuleId} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-bold rounded text-xs flex items-center gap-1"><Edit2 size={12} /> {t('更新规则', 'Update Rule')}</button>
                                                    <button onClick={handleDeleteBillingRule} disabled={!selectedBillingRuleId && selectedBillingRuleIds.length === 0} className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-bold rounded text-xs flex items-center gap-1"><Trash2 size={12} /> {selectedBillingRuleIds.length > 1 ? t('批量删除规则', 'Delete Selected') : t('删除规则', 'Delete Rule')}</button>
                                                    <button onClick={() => { setSelectedBillingRuleId(''); setBillingRuleForm(createEmptyBillingRuleForm()); }} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs">{t('清空表单', 'Clear Form')}</button>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                    )}

                                    {!isSystemApiEditing && (
                                        <div className="border border-white/10 rounded-lg p-4 bg-black/20 text-sm text-gray-300">
                                            {t('先在上方列表中双击一条记录进行编辑，或点击“新建 API”。', 'Double-click an item in the list above to edit, or click "New API".')}
                                        </div>
                                    )}

                                    {isSystemApiEditing && (
                                    <div
                                        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[1px] flex items-center justify-center p-4"
                                        onClick={() => setIsSystemApiEditing(false)}
                                    >
                                    <div
                                        className="w-full max-w-5xl max-h-[88vh] overflow-y-auto border border-white/15 rounded-xl p-4 bg-[#0d0f14] space-y-3 shadow-2xl"
                                        onClick={(e) => e.stopPropagation()}
                                    >
                                        <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                                            <h4 className="text-sm font-bold text-sky-200">
                                                {selectedSystemApiId ? t('编辑 System API', 'Edit System API') : t('新建 System API', 'Create System API')}
                                            </h4>
                                            <button
                                                onClick={() => setIsSystemApiEditing(false)}
                                                className="px-2.5 py-1 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs"
                                            >
                                                {t('关闭', 'Close')}
                                            </button>
                                        </div>

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
                                                    <option value="DigitalHuman">{t('数字人', 'DigitalHuman')}</option>
                                                    <option value="Voice">{t('语音', 'Voice')}</option>
                                                    <option value="Music">{t('音乐', 'Music')}</option>
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
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('基础模型', 'Base Model')}</label>
                                                <input
                                                    value={systemApiForm.base_model}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, base_model: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                    placeholder={t('用于归类同一基础模型', 'Used to group same base model')}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('重试分组', 'Retry Group')}</label>
                                                <input
                                                    value={systemApiForm.retry_group}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, retry_group: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                    placeholder={t('同类回退分组键', 'Fallback group key for same category')}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('价格档位', 'Price Tier')}</label>
                                                <select
                                                    value={systemApiForm.retry_price_group}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, retry_price_group: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                >
                                                    <option value="">{t('未设置', 'Unset')}</option>
                                                    <option value="low">low</option>
                                                    <option value="mid">mid</option>
                                                    <option value="high">high</option>
                                                </select>
                                            </div>
                                            
                                            <div className="flex items-end pb-2">
                                                <label className="flex items-center space-x-2 text-sm cursor-pointer">
                                                    <input
                                                        type="checkbox"
                                                        checked={!!systemApiForm.explicit_selection}
                                                        onChange={(e) => setSystemApiForm((prev) => ({ ...prev, explicit_selection: e.target.checked }))}
                                                        className="h-4 w-4 text-cyan-500 rounded bg-black/20 border-gray-600 focus:ring-cyan-500 focus:ring-1"
                                                    />
                                                    <span className="text-gray-300">{t('显式选择', 'Explicit Selection')}</span>
                                                </label>
                                            </div>
                                            
                                            <div className="flex items-end pb-2">
                                                <label className="flex items-center space-x-2 text-sm cursor-pointer" title={t('严格执行此提供商，若无法连通则直接失败而不使用功能绑定', 'Strict mode avoids falling back to function-binding provider')}>
                                                    <input
                                                        type="checkbox"
                                                        checked={!!systemApiForm.strict_provider}
                                                        onChange={(e) => setSystemApiForm((prev) => ({ ...prev, strict_provider: e.target.checked }))}
                                                        className="h-4 w-4 text-cyan-500 rounded bg-black/20 border-gray-600 focus:ring-cyan-500 focus:ring-1"
                                                    />
                                                    <span className="text-gray-300">{t('严格供应商', 'Strict Provider')}</span>
                                                </label>
                                            </div>

                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">Moderation Endpoint</label>
                                                <input
                                                    value={systemApiForm.moderation_endpoint}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, moderation_endpoint: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                    placeholder={t('保存到 config.moderation_endpoint', 'Saved to config.moderation_endpoint')}
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">Moderation User ID</label>
                                                <input
                                                    value={systemApiForm.moderation_user_id}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, moderation_user_id: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                    placeholder={t('保存到 config.moderation_user_id', 'Saved to config.moderation_user_id')}
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">API Key</label>
                                                <input
                                                    value={systemApiForm.api_key}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, api_key: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                    placeholder={t('可选', 'Optional')}
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('素材审核密钥', 'Asset Moderation Key')}</label>
                                                <input
                                                    type="password"
                                                    value={systemApiForm.moderation_aes_key}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, moderation_aes_key: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                    placeholder={t('保存到 config.moderation_aes_key', 'Saved to config.moderation_aes_key')}
                                                    autoComplete="new-password"
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('端点', 'Base URL')}</label>
                                                <input
                                                    value={systemApiForm.base_url}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, base_url: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('配置 (JSON)', 'Config (JSON)')}</label>
                                                <textarea
                                                    value={systemApiForm.config}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, config: e.target.value }))}
                                                    rows={3}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono"
                                                    placeholder='{"webHook":"", "smart_priority": 100}'
                                                />
                                            </div>
                                            <div className="md:col-span-2 border border-white/10 rounded p-3 space-y-2 bg-white/5">
                                                <div className="text-xs font-semibold text-cyan-200">{t('通用模态字段', 'Generic Modality Fields')}</div>
                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">generation_modes</label><input value={systemApiForm.generation_modes} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, generation_modes: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="t2i,i2i,t2v" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">input_formats</label><input value={systemApiForm.input_formats} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, input_formats: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="text,image,audio" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">output_format</label><input value={systemApiForm.output_format} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, output_format: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="image/video/audio/text" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">supported_resolutions</label><input value={systemApiForm.supported_resolutions} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, supported_resolutions: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="1280x720,4k" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">aspect_ratios</label><input value={systemApiForm.aspect_ratios} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, aspect_ratios: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="16:9,9:16,1:1" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">mode_values</label><input value={systemApiForm.mode_values} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, mode_values: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="std,pro,fast" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">max_images_per_call</label><input type="number" min="0" value={systemApiForm.max_images_per_call} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, max_images_per_call: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="1" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">reference_image_limit</label><input value={systemApiForm.reference_image_limit} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, reference_image_limit: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="1-2 images" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">reference_video_limit</label><input value={systemApiForm.reference_video_limit} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, reference_video_limit: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="1 video" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">durations_seconds</label><input value={systemApiForm.durations_seconds} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, durations_seconds: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="3,5,10" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">max_duration</label><input type="number" min="0" value={systemApiForm.max_duration} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, max_duration: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="10" /></div>
                                                    <div><label className="block text-xs uppercase text-gray-400 mb-1">fps_options</label><input value={systemApiForm.fps_options} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, fps_options: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="24,30,60" /></div>
                                                </div>
                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">has_audio</label>
                                                        <select value={systemApiForm.has_audio} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, has_audio: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm">
                                                            <option value="any">any</option>
                                                            <option value="true">true</option>
                                                            <option value="false">false</option>
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">has_google_search</label>
                                                        <select value={systemApiForm.has_google_search} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, has_google_search: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm">
                                                            <option value="any">any</option>
                                                            <option value="true">true</option>
                                                            <option value="false">false</option>
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs uppercase text-gray-400 mb-1">has_thinking_mode</label>
                                                        <select value={systemApiForm.has_thinking_mode} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, has_thinking_mode: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm">
                                                            <option value="any">any</option>
                                                            <option value="true">true</option>
                                                            <option value="false">false</option>
                                                        </select>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="md:col-span-2 border border-white/10 rounded p-3 space-y-2 bg-white/5">
                                                <div className="text-xs font-semibold text-emerald-200">{t('类别能力字段（JSON对象）', 'Category Capability Fields (JSON object)')}</div>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                    <textarea rows={3} value={systemApiForm.capability_flags} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, capability_flags: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='capability_flags: {"supports_first_frame":true,"supports_last_frame":true}' />
                                                    <textarea rows={3} value={systemApiForm.text_capabilities} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, text_capabilities: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='text_capabilities: {"supports_chat":true}' />
                                                    <textarea rows={3} value={systemApiForm.image_capabilities} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, image_capabilities: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='image_capabilities: {}' />
                                                    <textarea rows={3} value={systemApiForm.video_capabilities} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, video_capabilities: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='video_capabilities: {}' />
                                                    <textarea rows={3} value={systemApiForm.digital_human_capabilities} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, digital_human_capabilities: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='digital_human_capabilities: {}' />
                                                    <textarea rows={3} value={systemApiForm.voice_capabilities} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, voice_capabilities: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='voice_capabilities: {}' />
                                                    <textarea rows={3} value={systemApiForm.music_capabilities} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, music_capabilities: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='music_capabilities: {}' />
                                                </div>
                                            </div>
                                            <div className="md:col-span-2 border border-white/10 rounded p-3 space-y-2 bg-white/5">
                                                <div className="text-xs font-semibold text-amber-200">{t('供应商计费线索（宽表字段）', 'Supplier Billing Hints (Wide Columns)')}</div>
                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                    <input value={systemApiForm.pricing_unit} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, pricing_unit: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="pricing_unit" />
                                                    <input type="number" value={systemApiForm.input_token_price} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, input_token_price: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="input_token_price" />
                                                    <input type="number" value={systemApiForm.output_token_price} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, output_token_price: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="output_token_price" />
                                                    <input value={systemApiForm.free_quota} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, free_quota: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="free_quota" />
                                                    <input value={systemApiForm.currency} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, currency: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="currency" />
                                                    <div className="grid grid-cols-2 gap-2">
                                                        <select value={systemApiForm.token_billing_supported} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, token_billing_supported: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm">
                                                            <option value="any">token billing:any</option>
                                                            <option value="true">token billing:true</option>
                                                            <option value="false">token billing:false</option>
                                                        </select>
                                                        <select value={systemApiForm.has_tiered_pricing} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, has_tiered_pricing: e.target.value }))} className="bg-black/40 border border-gray-700 rounded p-2 text-sm">
                                                            <option value="any">tiered:any</option>
                                                            <option value="true">tiered:true</option>
                                                            <option value="false">tiered:false</option>
                                                        </select>
                                                    </div>
                                                </div>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                    <textarea rows={3} value={systemApiForm.per_resolution_price_map} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, per_resolution_price_map: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='per_resolution_price_map: {"1920x1080":100}' />
                                                    <textarea rows={3} value={systemApiForm.per_duration_price_map} onChange={(e) => setSystemApiForm((prev) => ({ ...prev, per_duration_price_map: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder='per_duration_price_map: {"5":100}' />
                                                </div>
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('标签', 'Tags')}</label>
                                                <input
                                                    value={systemApiForm.tags}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, tags: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                    placeholder={t('逗号分隔 或 JSON 数组', 'Comma-separated or JSON array')}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('计费单位', 'Billing Unit')}</label>
                                                <select
                                                    value={systemApiForm.billing_unit_type}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, billing_unit_type: e.target.value }))}
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
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('计费成本（基础）', 'Billing Cost')}</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={systemApiForm.billing_cost}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, billing_cost: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('计费成本（输入）', 'Billing Cost Input')}</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={systemApiForm.billing_cost_input}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, billing_cost_input: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('计费成本（输出）', 'Billing Cost Output')}</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={systemApiForm.billing_cost_output}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, billing_cost_output: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-4">
                                            <label className="flex items-center gap-2 text-xs text-gray-400">
                                                <input
                                                    type="checkbox"
                                                    checked={!!systemApiForm.is_active}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                                                />
                                                {t('类别默认', 'Category Default')}
                                            </label>
                                            <label className="flex items-center gap-2 text-xs text-gray-400">
                                                <input
                                                    type="checkbox"
                                                    checked={!!systemApiForm.deprecated}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, deprecated: e.target.checked }))}
                                                />
                                                {t('已弃用', 'Deprecated')}
                                            </label>
                                        </div>
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
                                            <button
                                                onClick={() => setIsSystemApiEditing(false)}
                                                className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded"
                                            >
                                                {t('完成编辑', 'Done Editing')}
                                            </button>
                                        </div>
                                    </div>
                                    </div>
                                    )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* PRICING RULES TAB */}
                    {activeTab === 'pricing_rules' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between gap-2">
                                <h3 className="text-lg font-bold">{t('计费规则 CRUD（独立页）', 'Pricing Rule CRUD (Dedicated Tab)')}</h3>
                                <div className="flex items-center gap-2">
                                    <div className="flex items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-1">
                                        <span className="text-[11px] text-gray-300 whitespace-nowrap">{t('最小倍率', 'Min Mul')}</span>
                                        <input
                                            type="number"
                                            min="1.1"
                                            max="2"
                                            step="0.01"
                                            value={batchResetMinMultiplier}
                                            onChange={(e) => setBatchResetMinMultiplier(e.target.value)}
                                            onBlur={() => saveBillingRuleResetConfig(batchResetMaxIncreaseCredits)}
                                            disabled={isBatchResetConfigSaving}
                                            className="w-14 bg-black/50 border border-gray-700 rounded px-1 py-0.5 text-xs text-white"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-1">
                                        <span className="text-[11px] text-gray-300 whitespace-nowrap">{t('最大倍率', 'Max Mul')}</span>
                                        <input
                                            type="number"
                                            min="1.1"
                                            max="2"
                                            step="0.01"
                                            value={batchResetMaxMultiplier}
                                            onChange={(e) => setBatchResetMaxMultiplier(e.target.value)}
                                            onBlur={() => saveBillingRuleResetConfig(batchResetMaxIncreaseCredits)}
                                            disabled={isBatchResetConfigSaving}
                                            className="w-14 bg-black/50 border border-gray-700 rounded px-1 py-0.5 text-xs text-white"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-1">
                                        <span className="text-[11px] text-gray-300 whitespace-nowrap">{t('默认倍率', 'Default')}</span>
                                        <input
                                            type="number"
                                            min="0"
                                            step="0.01"
                                            value={batchResetDefaultMultiplier}
                                            onChange={(e) => setBatchResetDefaultMultiplier(e.target.value)}
                                            onBlur={() => saveBillingRuleResetConfig(batchResetMaxIncreaseCredits)}
                                            disabled={isBatchResetConfigSaving}
                                            className="w-14 bg-black/50 border border-gray-700 rounded px-1 py-0.5 text-xs text-white"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-1">
                                        <span className="text-[11px] text-gray-300 whitespace-nowrap">{t('分箱(积分)', 'Bin Size')}</span>
                                        <input
                                            type="number"
                                            min="1"
                                            step="1"
                                            value={batchResetBinSizeCredits}
                                            onChange={(e) => setBatchResetBinSizeCredits(e.target.value)}
                                            onBlur={() => saveBillingRuleResetConfig(batchResetMaxIncreaseCredits)}
                                            disabled={isBatchResetConfigSaving}
                                            className="w-14 bg-black/50 border border-gray-700 rounded px-1 py-0.5 text-xs text-white"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-1">
                                        <span className="text-[11px] text-gray-300 whitespace-nowrap">{t('每箱降幅', 'Drop/Bin')}</span>
                                        <input
                                            type="number"
                                            min="0.0001"
                                            step="0.01"
                                            value={batchResetBinDropMultiplier}
                                            onChange={(e) => setBatchResetBinDropMultiplier(e.target.value)}
                                            onBlur={() => saveBillingRuleResetConfig(batchResetMaxIncreaseCredits)}
                                            disabled={isBatchResetConfigSaving}
                                            className="w-14 bg-black/50 border border-gray-700 rounded px-1 py-0.5 text-xs text-white"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-1">
                                        <span className="text-[11px] text-gray-300 whitespace-nowrap">{t('单条增幅上限', 'Per-Rule Cap')}</span>
                                        <input
                                            type="number"
                                            min="0"
                                            step="1"
                                            value={batchResetMaxIncreaseCredits}
                                            onChange={(e) => setBatchResetMaxIncreaseCredits(e.target.value)}
                                            onBlur={(e) => saveBillingRuleResetConfig(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault();
                                                    saveBillingRuleResetConfig(batchResetMaxIncreaseCredits);
                                                }
                                            }}
                                            disabled={isBatchResetConfigSaving}
                                            className="w-16 bg-black/50 border border-gray-700 rounded px-1 py-0.5 text-xs text-white"
                                            title={t('批量重置后，单条规则相对原积分的增幅不得超过该值', 'Per-rule increase over original credits cannot exceed this value')}
                                        />
                                        {isBatchResetConfigSaving && <span className="text-[10px] text-gray-400">{t('保存中', 'Saving')}</span>}
                                    </div>
                                    <button
                                        onClick={fetchSystemApiManageRows}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2"
                                    >
                                        <RefreshCw size={16} /> {t('刷新 API 列表', 'Refresh API List')}
                                    </button>
                                    <button
                                        onClick={() => fetchBillingRulesForSystemApi(selectedSystemApiId)}
                                        disabled={isBillingRuleLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <RefreshCw size={16} /> {t('刷新规则', 'Refresh Rules')}
                                    </button>
                                    <button
                                        onClick={handleRecomputePriceCache}
                                        disabled={isPriceCacheRecomputeLoading}
                                        className="bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                        title={t('重算并持久化价格区间与样本均价（写入 system_api_settings）', 'Recompute and persist price range/sample-average into system_api_settings')}
                                    >
                                        <Database size={16} /> {isPriceCacheRecomputeLoading ? t('预计算中...', 'Precomputing...') : t('预计算价格缓存', 'Precompute Price Cache')}
                                    </button>
                                    <button
                                        onClick={handleBatchResetBillingRuleChargeMultiplier}
                                        disabled={isBatchResetMultiplierLoading}
                                        className="bg-amber-700 hover:bg-amber-600 text-white px-3 py-1 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <RefreshCw size={16} /> {isBatchResetMultiplierLoading ? t('重置中...', 'Resetting...') : t('批量重置倍率', 'Batch Reset Multiplier')}
                                    </button>
                                </div>
                            </div>

                            <div className="text-xs text-gray-400">
                                {t('共', 'Total')} {billingRuleRows.length} {t('条，当前显示', ', showing')} {filteredBillingRuleRows.length} {t('条', 'items')}
                            </div>

                            {billingRuleEditToast && (
                                <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                                    {billingRuleEditToast}
                                </div>
                            )}

                            <div className="border border-white/10 rounded-lg p-4 bg-black/20 space-y-3">
                                <label className="text-xs uppercase text-gray-400">{t('筛选 System API 模型', 'Filter by System API Model')}</label>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                    <select
                                        value={billingRuleApiPickerProvider}
                                        onChange={(e) => setBillingRuleApiPickerProvider(e.target.value)}
                                        className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                    >
                                        <option value="all">{t('全部服务商', 'All Providers')}</option>
                                        {billingRuleApiPickerProviderOptions.map((value) => (
                                            <option key={`billing-rule-api-picker-provider-${value}`} value={value}>{value}</option>
                                        ))}
                                    </select>
                                    <select
                                        value={billingRuleApiPickerCategory}
                                        onChange={(e) => setBillingRuleApiPickerCategory(e.target.value)}
                                        className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                    >
                                        <option value="all">{t('全部类型', 'All Categories')}</option>
                                        {billingRuleApiPickerCategoryOptions.map((value) => (
                                            <option key={`billing-rule-api-picker-category-${value}`} value={value}>{value}</option>
                                        ))}
                                    </select>
                                    <select
                                        value={billingRuleApiPickerBaseModel}
                                        onChange={(e) => setBillingRuleApiPickerBaseModel(e.target.value)}
                                        className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                    >
                                        <option value="all">{t('全部基础模型', 'All Base Models')}</option>
                                        {billingRuleApiPickerBaseModelOptions.map((value) => (
                                            <option key={`billing-rule-api-picker-base-model-${value}`} value={value}>{value}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="text-[11px] text-gray-400">
                                    {t('API 候选：', 'API candidates:')} {filteredBillingRuleApiPickerRows.length}
                                </div>
                                <select
                                    value={selectedSystemApiId}
                                    onChange={(e) => {
                                        setSelectedSystemApiId(e.target.value);
                                        setIsBillingRuleEditing(false);
                                    }}
                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                >
                                    <option value="">{t('全部 API（默认）', 'All APIs (Default)')}</option>
                                    {filteredBillingRuleApiPickerRows.map((row) => (
                                        <option key={row.id} value={row.id}>
                                            [{row.category}] {row.provider} / {row.model || '-'} (ID:{row.id})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="border border-sky-500/30 rounded-lg p-4 bg-sky-500/5 space-y-3">
                                <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                                    <input
                                        value={billingRuleFilterKeyword}
                                        onChange={(e) => setBillingRuleFilterKeyword(e.target.value)}
                                        placeholder={t('关键词（名称/描述/模式）', 'Keyword (name/description/mode)')}
                                        className="md:col-span-2 bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                    />
                                    <select value={billingRuleFilterStatus} onChange={(e) => setBillingRuleFilterStatus(e.target.value)} className="bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                        <option value="all">{t('全部状态', 'All Status')}</option>
                                        <option value="active">{t('启用', 'Active')}</option>
                                        <option value="inactive">{t('停用', 'Inactive')}</option>
                                    </select>
                                    <select value={billingRuleFilterTarget} onChange={(e) => setBillingRuleFilterTarget(e.target.value)} className="bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                        <option value="all">{t('全部目标', 'All Targets')}</option>
                                        <option value="text">Text</option>
                                        <option value="image">Image</option>
                                        <option value="video">Video</option>
                                    </select>
                                    <select value={billingRuleFilterUnitType} onChange={(e) => setBillingRuleFilterUnitType(e.target.value)} className="bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                        <option value="all">{t('全部计费单位', 'All Units')}</option>
                                        <option value="per_call">per_call</option>
                                        <option value="per_second">per_second</option>
                                        <option value="per_minute">per_minute</option>
                                        <option value="per_token">per_token</option>
                                        <option value="per_1k_tokens">per_1k_tokens</option>
                                        <option value="per_million_tokens">per_million_tokens</option>
                                    </select>
                                </div>

                                {isBillingRuleLoading ? (
                                    <div className="text-xs text-gray-400">{t('定价规则加载中...', 'Loading pricing rules...')}</div>
                                ) : (
                                    <>
                                    <div className="md:hidden space-y-2">
                                        {filteredBillingRuleRows.map((row) => {
                                            const apiRow = systemApiRows.find((api) => Number(api?.id) === Number(row?.system_api_id));
                                            const apiLabel = apiRow ? `[${apiRow.category}] ${apiRow.provider}/${apiRow.model || '-'}` : `ID:${row?.system_api_id || '-'}`;
                                            const isSelected = String(selectedBillingRuleId) === String(row.id);
                                            return (
                                                <button
                                                    key={`billing-rule-card-${row.id}`}
                                                    type="button"
                                                    onClick={() => setSelectedBillingRuleId(String(row.id))}
                                                    onDoubleClick={() => {
                                                        setSelectedBillingRuleId(String(row.id));
                                                        setIsBillingRuleEditing(true);
                                                        showBillingRuleEditToast(t('已进入规则编辑模式', 'Entered rule edit mode'));
                                                    }}
                                                    className={`w-full rounded-lg border p-3 text-left space-y-2 transition-colors ${isSelected ? 'border-sky-400/40 bg-sky-500/10' : 'border-white/10 bg-black/20 hover:bg-white/5'}`}
                                                >
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div className="min-w-0">
                                                            <div className="font-semibold text-sm text-white">#{row.id} {row.name || '-'}</div>
                                                            <div className="text-[11px] text-gray-400 mt-1 break-words">{apiLabel}</div>
                                                        </div>
                                                        <span className={`shrink-0 rounded px-2 py-1 text-[11px] ${row.is_active ? 'bg-emerald-500/20 text-emerald-300' : 'bg-gray-700 text-gray-300'}`}>
                                                            {row.is_active ? t('启用', 'Active') : t('停用', 'Inactive')}
                                                        </span>
                                                    </div>
                                                    <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-300">
                                                        <div className="rounded bg-black/20 px-2 py-1.5">
                                                            <div className="text-gray-500 mb-1">{t('优先级', 'Priority')}</div>
                                                            <div>{row.priority ?? 0}</div>
                                                        </div>
                                                        <div className="rounded bg-black/20 px-2 py-1.5">
                                                            <div className="text-gray-500 mb-1">{t('计费单位', 'Billing Unit')}</div>
                                                            <div>{row?.billing_unit_type || 'per_call'}</div>
                                                        </div>
                                                        <div className="rounded bg-black/20 px-2 py-1.5">
                                                            <div className="text-gray-500 mb-1">billing_cost</div>
                                                            <div>{toNonNegativeInt(row?.billing_cost ?? 0)}</div>
                                                        </div>
                                                        <div className="rounded bg-black/20 px-2 py-1.5">
                                                            <div className="text-gray-500 mb-1">charge_multiplier</div>
                                                            <div>{toRuleChargeMultiplier(row?.charge_multiplier, 2).toFixed(2)}</div>
                                                        </div>
                                                    </div>
                                                    <div className="flex flex-wrap gap-2 text-[11px] text-gray-400">
                                                        <span className="rounded bg-white/5 px-2 py-1">T: {row?.applies_to_text ? t('是', 'Yes') : t('否', 'No')}</span>
                                                        <span className="rounded bg-white/5 px-2 py-1">I: {row?.applies_to_image ? t('是', 'Yes') : t('否', 'No')}</span>
                                                        <span className="rounded bg-white/5 px-2 py-1">V: {row?.applies_to_video ? t('是', 'Yes') : t('否', 'No')}</span>
                                                        <span className="rounded bg-white/5 px-2 py-1">mode: {row?.generation_mode || '-'}</span>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                        {filteredBillingRuleRows.length === 0 && (
                                            <div className="rounded border border-white/10 px-3 py-4 text-gray-400 text-xs">{t('无匹配规则', 'No matching rules')}</div>
                                        )}
                                    </div>
                                    <div className="hidden md:block overflow-x-auto max-h-[320px] border border-white/10 rounded">
                                        <table className="w-full text-xs min-w-[1480px]">
                                            <thead className="bg-white/5 text-gray-400 sticky top-0">
                                                <tr>
                                                    <th className="text-left p-2">ID</th>
                                                    <th className="text-left p-2">API</th>
                                                    <th className="text-left p-2">{t('名称', 'Name')}</th>
                                                    <th className="text-left p-2">{t('状态', 'Status')}</th>
                                                    <th className="text-left p-2">{t('优先级', 'Priority')}</th>
                                                    <th className="text-left p-2">T</th>
                                                    <th className="text-left p-2">I</th>
                                                    <th className="text-left p-2">V</th>
                                                    <th className="text-left p-2">generation_mode</th>
                                                    <th className="text-left p-2">input_format</th>
                                                    <th className="text-left p-2">output_format</th>
                                                    <th className="text-left p-2">has_audio</th>
                                                    <th className="text-left p-2">billing_unit_type</th>
                                                    <th className="text-left p-2">billing_cost</th>
                                                    <th className="text-left p-2">billing_cost_input</th>
                                                    <th className="text-left p-2">billing_cost_output</th>
                                                    <th className="text-left p-2">charge_multiplier</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {filteredBillingRuleRows.map((row) => {
                                                    const apiRow = systemApiRows.find((api) => Number(api?.id) === Number(row?.system_api_id));
                                                    const apiLabel = apiRow ? `[${apiRow.category}] ${apiRow.provider}/${apiRow.model || '-'}` : `ID:${row?.system_api_id || '-'}`;
                                                    return (
                                                        <tr
                                                            key={row.id}
                                                            onClick={() => setSelectedBillingRuleId(String(row.id))}
                                                            onDoubleClick={() => {
                                                                setSelectedBillingRuleId(String(row.id));
                                                                setIsBillingRuleEditing(true);
                                                                showBillingRuleEditToast(t('已进入规则编辑模式', 'Entered rule edit mode'));
                                                            }}
                                                            className={`border-t border-white/10 cursor-pointer ${String(selectedBillingRuleId) === String(row.id) ? 'bg-sky-500/10' : 'hover:bg-white/5'}`}
                                                        >
                                                            <td className="p-2">{row.id}</td>
                                                            <td className="p-2 max-w-[260px] truncate" title={apiLabel}>{apiLabel}</td>
                                                            <td className="p-2">{row.name || '-'}</td>
                                                            <td className="p-2">{row.is_active ? t('启用', 'Active') : t('停用', 'Inactive')}</td>
                                                            <td className="p-2">{row.priority ?? 0}</td>
                                                            <td className="p-2">{row?.applies_to_text ? t('是', 'Yes') : t('否', 'No')}</td>
                                                            <td className="p-2">{row?.applies_to_image ? t('是', 'Yes') : t('否', 'No')}</td>
                                                            <td className="p-2">{row?.applies_to_video ? t('是', 'Yes') : t('否', 'No')}</td>
                                                            <td className="p-2">{row?.generation_mode || '-'}</td>
                                                            <td className="p-2">{row?.input_format || '-'}</td>
                                                            <td className="p-2">{row?.output_format || '-'}</td>
                                                            <td className="p-2">{row?.has_audio === null || row?.has_audio === undefined ? '-' : (row?.has_audio ? t('是', 'Yes') : t('否', 'No'))}</td>
                                                            <td className="p-2">{row?.billing_unit_type || 'per_call'}</td>
                                                            <td className="p-2">{toNonNegativeInt(row?.billing_cost ?? 0)}</td>
                                                            <td className="p-2">{toNonNegativeInt(row?.billing_cost_input ?? 0)}</td>
                                                            <td className="p-2">{toNonNegativeInt(row?.billing_cost_output ?? 0)}</td>
                                                            <td className="p-2">{toRuleChargeMultiplier(row?.charge_multiplier, 2).toFixed(2)}</td>
                                                        </tr>
                                                    );
                                                })}
                                                {filteredBillingRuleRows.length === 0 && (
                                                    <tr className="border-t border-white/10">
                                                        <td className="p-3 text-gray-400" colSpan={17}>{t('无匹配规则', 'No matching rules')}</td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                    </>
                                )}

                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => {
                                            if (!selectedSystemApiId) {
                                                alert(t('请先选择一个 System API', 'Select a System API first'));
                                                return;
                                            }
                                            setSelectedBillingRuleId('');
                                            setBillingRuleForm(createEmptyBillingRuleForm());
                                            setIsBillingRuleEditing(true);
                                            showBillingRuleEditToast(t('已进入新建规则编辑', 'Entered new rule editor'));
                                        }}
                                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-xs"
                                    >
                                        {t('新建规则', 'New Rule')}
                                    </button>
                                    <button
                                        onClick={() => {
                                            if (!selectedBillingRuleId) {
                                                alert(t('请先双击一条规则', 'Double-click a rule first'));
                                                return;
                                            }
                                            setIsBillingRuleEditing(true);
                                            showBillingRuleEditToast(t('已进入规则编辑模式', 'Entered rule edit mode'));
                                        }}
                                        className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded text-xs"
                                    >
                                        {t('编辑选中', 'Edit Selected')}
                                    </button>
                                </div>
                            </div>

                            {!isBillingRuleEditing && (
                                <div className="border border-white/10 rounded-lg p-4 bg-black/20 text-sm text-gray-300">
                                    {t('先在列表中双击一条规则进行编辑，或点击“新建规则”。', 'Double-click a rule in the list to edit, or click "New Rule".')}
                                </div>
                            )}

                            {isBillingRuleEditing && (
                            <div
                                className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[1px] flex items-center justify-center p-4"
                                onClick={() => setIsBillingRuleEditing(false)}
                            >
                            <div
                                className="w-full max-w-4xl max-h-[88vh] overflow-y-auto border border-white/15 rounded-xl p-4 bg-[#0d0f14] space-y-3 shadow-2xl"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                                    <h4 className="text-sm font-bold text-sky-200">
                                        {selectedBillingRuleId ? t('编辑计费规则', 'Edit Pricing Rule') : t('新建计费规则', 'Create Pricing Rule')}
                                    </h4>
                                    <button
                                        onClick={() => setIsBillingRuleEditing(false)}
                                        className="px-2.5 py-1 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs"
                                    >
                                        {t('关闭', 'Close')}
                                    </button>
                                </div>

                                <div className="text-xs text-gray-400">
                                    {t('绑定 API', 'Bound API')}: {selectedBillingRuleApiLabel}
                                </div>

                                {selectedBillingRuleRow && (
                                    <div className="border border-white/10 rounded-lg p-3 bg-black/20 space-y-2">
                                        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
                                            <div><span className="text-gray-400">Rule ID:</span> <span className="text-white">{selectedBillingRuleRow.id}</span></div>
                                            <div><span className="text-gray-400">System API ID:</span> <span className="text-white">{selectedBillingRuleRow.system_api_id || '-'}</span></div>
                                            <div><span className="text-gray-400">Created:</span> <span className="text-white">{selectedBillingRuleRow.created_at || '-'}</span></div>
                                            <div><span className="text-gray-400">Updated:</span> <span className="text-white">{selectedBillingRuleRow.updated_at || '-'}</span></div>
                                        </div>
                                        <div>
                                            <div className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">{t('当前规则完整信息', 'Current Rule Full Payload')}</div>
                                            <pre className="max-h-44 overflow-auto bg-black/40 border border-gray-700 rounded p-2 text-[11px] text-gray-200 whitespace-pre-wrap break-all font-mono">
{JSON.stringify(selectedBillingRuleRow, null, 2)}
                                            </pre>
                                        </div>
                                    </div>
                                )}

                                <details open className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('基础信息', 'Basic')}</summary>
                                    <div className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-2">
                                        <RuleField label="name">
                                            <input value={billingRuleForm.name} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, name: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </RuleField>
                                        <RuleField label="description">
                                            <input value={billingRuleForm.description} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, description: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </RuleField>
                                        <RuleField label="priority">
                                            <input type="number" value={billingRuleForm.priority} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, priority: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </RuleField>
                                        <RuleField label="is_active">
                                            <select value={billingRuleForm.is_active ? 'active' : 'inactive'} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, is_active: e.target.value === 'active' }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                                <option value="active">{t('启用', 'Active')}</option>
                                                <option value="inactive">{t('停用', 'Inactive')}</option>
                                            </select>
                                        </RuleField>
                                    </div>
                                </details>

                                <details open className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('匹配条件', 'Matching')}</summary>
                                    <div className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-2">
                                        <RuleField label="generation_mode">
                                            <input value={billingRuleForm.generation_mode} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, generation_mode: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </RuleField>
                                        <RuleField label="input_format">
                                            <input value={billingRuleForm.input_format} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, input_format: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </RuleField>
                                        <RuleField label="output_format">
                                            <input value={billingRuleForm.output_format} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, output_format: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </RuleField>
                                        <RuleField label="has_audio">
                                            <select value={billingRuleForm.has_audio} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, has_audio: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                                <option value="any">any</option>
                                                <option value="true">true</option>
                                                <option value="false">false</option>
                                            </select>
                                        </RuleField>
                                    </div>
                                    <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                                        <label className="flex items-center gap-2 text-xs text-gray-300"><input type="checkbox" checked={!!billingRuleForm.applies_to_text} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, applies_to_text: e.target.checked }))} /> Text</label>
                                        <label className="flex items-center gap-2 text-xs text-gray-300"><input type="checkbox" checked={!!billingRuleForm.applies_to_image} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, applies_to_image: e.target.checked }))} /> Image</label>
                                        <label className="flex items-center gap-2 text-xs text-gray-300"><input type="checkbox" checked={!!billingRuleForm.applies_to_video} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, applies_to_video: e.target.checked }))} /> Video</label>
                                    </div>
                                </details>

                                <details open className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('计费参数', 'Pricing')}</summary>
                                    <div className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-2">
                                        <RuleField label="billing_unit_type">
                                            <select value={billingRuleForm.billing_unit_type} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_unit_type: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs">
                                                <option value="per_call">per_call</option>
                                                <option value="per_second">per_second</option>
                                                <option value="per_minute">per_minute</option>
                                                <option value="per_token">per_token</option>
                                                <option value="per_1k_tokens">per_1k_tokens</option>
                                                <option value="per_million_tokens">per_million_tokens</option>
                                            </select>
                                        </RuleField>
                                        <RuleField label="billing_cost"><input type="number" value={billingRuleForm.billing_cost} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_cost: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="billing_cost_input"><input type="number" value={billingRuleForm.billing_cost_input} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_cost_input: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="billing_cost_output"><input type="number" value={billingRuleForm.billing_cost_output} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, billing_cost_output: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="charge_multiplier"><input type="number" step="0.01" value={billingRuleForm.charge_multiplier} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, charge_multiplier: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                    </div>
                                </details>

                                <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('文本维度', 'Text Dimensions')}</summary>
                                    <div className="mt-3 grid grid-cols-2 md:grid-cols-6 gap-2">
                                        <RuleField label="input_tokens_min"><input type="number" value={billingRuleForm.input_tokens_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, input_tokens_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="input_tokens_max"><input type="number" value={billingRuleForm.input_tokens_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, input_tokens_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="output_tokens_min"><input type="number" value={billingRuleForm.output_tokens_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, output_tokens_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="output_tokens_max"><input type="number" value={billingRuleForm.output_tokens_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, output_tokens_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="total_tokens_min"><input type="number" value={billingRuleForm.total_tokens_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, total_tokens_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="total_tokens_max"><input type="number" value={billingRuleForm.total_tokens_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, total_tokens_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                    </div>
                                </details>

                                <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('图像维度', 'Image Dimensions')}</summary>
                                    <div className="mt-3 grid grid-cols-2 md:grid-cols-6 gap-2">
                                        <RuleField label="image_count_min"><input type="number" value={billingRuleForm.image_count_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, image_count_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="image_count_max"><input type="number" value={billingRuleForm.image_count_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, image_count_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="width_min"><input type="number" value={billingRuleForm.width_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, width_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="width_max"><input type="number" value={billingRuleForm.width_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, width_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="height_min"><input type="number" value={billingRuleForm.height_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, height_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="height_max"><input type="number" value={billingRuleForm.height_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, height_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="pixels_min"><input type="number" value={billingRuleForm.pixels_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, pixels_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="pixels_max"><input type="number" value={billingRuleForm.pixels_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, pixels_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                    </div>
                                </details>

                                <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('视频维度', 'Video Dimensions')}</summary>
                                    <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
                                        <RuleField label="duration_seconds_min"><input type="number" step="0.1" value={billingRuleForm.duration_seconds_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, duration_seconds_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="duration_seconds_max"><input type="number" step="0.1" value={billingRuleForm.duration_seconds_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, duration_seconds_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="fps_min"><input type="number" step="0.1" value={billingRuleForm.fps_min} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, fps_min: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                        <RuleField label="fps_max"><input type="number" step="0.1" value={billingRuleForm.fps_max} onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, fps_max: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" /></RuleField>
                                    </div>
                                </details>

                                <details className="border border-white/10 rounded-lg p-3 bg-black/20">
                                    <summary className="cursor-pointer text-xs text-sky-200 font-semibold">{t('扩展条件', 'Extra Conditions')}</summary>
                                    <div className="mt-3">
                                        <label className="block text-xs text-gray-400 mb-1">extra_conditions (JSON)</label>
                                        <textarea
                                            rows={3}
                                            value={billingRuleForm.extra_conditions_text}
                                            onChange={(e) => setBillingRuleForm((prev) => ({ ...prev, extra_conditions_text: e.target.value }))}
                                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono"
                                        />
                                    </div>
                                </details>

                                <div className="flex flex-wrap gap-2 pt-2 border-t border-white/10">
                                    <button onClick={handleCreateBillingRule} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-xs">{t('创建', 'Create')}</button>
                                    <button onClick={handleUpdateBillingRule} disabled={!selectedBillingRuleId} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-bold rounded text-xs">{t('更新', 'Update')}</button>
                                    <button onClick={handleDeleteBillingRule} disabled={!selectedBillingRuleId && selectedBillingRuleIds.length === 0} className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-bold rounded text-xs">{selectedBillingRuleIds.length > 1 ? t('批量删除', 'Delete Selected') : t('删除', 'Delete')}</button>
                                    <button onClick={() => setBillingRuleForm(createEmptyBillingRuleForm())} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded text-xs">{t('清空表单', 'Clear Form')}</button>
                                    <button onClick={() => setIsBillingRuleEditing(false)} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded text-xs">{t('完成编辑', 'Done Editing')}</button>
                                </div>
                            </div>
                            </div>
                            )}
                        </div>
                    )}

                    {activeTab === 'oss_pools' && (
                                <div className="border border-sky-500/20 rounded p-4 bg-sky-500/5 space-y-4">
                                    <div className="flex items-center justify-between gap-2">
                                        <div>
                                            <div className="text-sm font-bold text-sky-200">{t('OSS 供应商配置', 'OSS Provider Pool Configuration')}</div>     
                                            <div className="text-xs text-sky-100/80 mt-1">{t('管理 oss_provider_pools 表，支持多供应商、多个凭证和启用状态。credentials 与 weights 使用 JSON 数组编辑。', 'Manage the oss_provider_pools table, including multi-provider pools, multiple credentials, and activation state. Edit credentials and weights as JSON arrays.')}</div>
                                        </div>
                                        <div className="flex items-center gap-4">
                                            <button onClick={handleExportSystemConfigSyncBundle} disabled={isSystemConfigSyncExporting} className="text-xs bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 rounded px-2 py-1 flex items-center gap-1 transition-colors">
                                                {isSystemConfigSyncExporting ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />} {t('导出', 'Export')}
                                            </button>
                                            <label className="text-xs bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 rounded px-2 py-1 flex items-center gap-1 transition-colors cursor-pointer">
                                                {isSystemConfigSyncImporting ? <RefreshCw size={12} className="animate-spin" /> : <Upload size={12} />} {t('导入', 'Import')}
                                                <input type="file" accept=".json" className="hidden" onChange={handleImportSystemConfigSyncBundleFile} />
                                            </label>
                                            <button onClick={fetchOssProviderPools} className="text-xs text-sky-300 hover:text-sky-100 flex items-center gap-1"><RefreshCw size={12} /> {t('刷新', 'Refresh')}</button>
                                        </div>
                                    </div>

                                    {isOssProviderPoolLoading ? (
                                        <div className="text-sm text-gray-400">{t('加载中...', 'Loading...')}</div>
                                    ) : (
                                        <>
                                            <div className="hidden md:block overflow-x-auto">
                                                <table className="w-full text-xs">
                                                    <thead>
                                                        <tr className="text-gray-400 border-b border-white/10">
                                                            <th className="text-left py-1.5 px-2">ID</th>
                                                            <th className="text-left py-1.5 px-2">Provider</th>
                                                            <th className="text-left py-1.5 px-2">Alias</th>
                                                            <th className="text-left py-1.5 px-2">Endpoint</th>
                                                            <th className="text-left py-1.5 px-2">Bucket</th>
                                                            <th className="text-left py-1.5 px-2">{t('凭证数', 'Credentials')}</th>
                                                            <th className="text-left py-1.5 px-2">{t('启用', 'Active')}</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {ossProviderPoolRows.map((row) => (
                                                            <tr
                                                                key={row.id}   
                                                                className={`border-b border-white/5 cursor-pointer hover:bg-white/5 ${String(row.id) === String(selectedOssProviderPoolId) ? 'bg-sky-500/10' : ''}`}
                                                                onClick={() => setSelectedOssProviderPoolId(String(row.id))}
                                                            >
                                                                <td className="py-1.5 px-2">{row.id}</td>
                                                                <td className="py-1.5 px-2 font-mono">{row.provider}</td>
                                                                <td className="py-1.5 px-2">{row.provider_alias || '-'}</td>
                                                                <td className="py-1.5 px-2 max-w-[260px] truncate" title={row.endpoint || '-'}>{row.endpoint || '-'}</td>
                                                                <td className="py-1.5 px-2">{row.bucket || '-'}</td>
                                                                <td className="py-1.5 px-2">{Array.isArray(row.credentials) ? row.credentials.length : 0}</td> 
                                                                <td className="py-1.5 px-2">{row.is_active ? t('是', 'Yes') : t('否', 'No')}</td>
                                                            </tr>
                                                        ))}
                                                        {ossProviderPoolRows.length === 0 && (
                                                            <tr><td colSpan={7} className="py-3 px-2 text-center text-gray-500">{t('暂无 OSS 配置', 'No OSS provider pools')}</td></tr>
                                                        )}
                                                    </tbody>
                                                </table>
                                            </div>

                                            <div className="md:hidden space-y-2">
                                                {ossProviderPoolRows.map((row) => (
                                                    <button
                                                        key={`oss-pool-card-${row.id}`}
                                                        type="button"
                                                        onClick={() => setSelectedOssProviderPoolId(String(row.id))}
                                                        className={`w-full rounded-lg border p-3 text-left space-y-2 transition-colors ${String(row.id) === String(selectedOssProviderPoolId) ? 'border-sky-400/40 bg-sky-500/10' : 'border-white/10 bg-black/20 hover:bg-white/5'}`}
                                                    >
                                                        <div className="flex items-start justify-between gap-3">
                                                            <div className="min-w-0">
                                                                <div className="font-semibold text-sm text-white">#{row.id} {row.provider || '-'}</div>        
                                                                <div className="text-xs text-gray-400 mt-1 break-all">{row.endpoint || '-'}</div>
                                                            </div>
                                                            <span className={`shrink-0 rounded px-2 py-1 text-[11px] ${row.is_active ? 'bg-emerald-950/60 text-emerald-100' : 'bg-gray-800 text-gray-300'}`}>{row.is_active ? t('启用', 'Active') : t('停用', 'Inactive')}</span>
                                                        </div>
                                                        <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-300">
                                                            <div className="rounded bg-black/20 px-2 py-1.5"><div className="text-gray-500 mb-1">Bucket</div><div>{row.bucket || '-'}</div></div>
                                                            <div className="rounded bg-black/20 px-2 py-1.5"><div className="text-gray-500 mb-1">{t('凭证数', 'Credentials')}</div><div>{Array.isArray(row.credentials) ? row.credentials.length : 0}</div></div>
                                                        </div>
                                                    </button>
                                                ))}
                                            </div>

                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Provider</label>
                                                    <input value={ossProviderPoolForm.provider} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, provider: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono" placeholder="qiniu / s3 / minio" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Alias</label>
                                                    <input value={ossProviderPoolForm.provider_alias} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, provider_alias: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="Qiniu CN South" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Endpoint</label>
                                                    <input value={ossProviderPoolForm.endpoint} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, endpoint: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="https://s3.cn-south-1.qiniucs.com" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Region</label>
                                                    <input value={ossProviderPoolForm.region} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, region: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="cn-south-1" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Bucket</label>
                                                    <input value={ossProviderPoolForm.bucket} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, bucket: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="aistoryboard" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Public Base URL</label>
                                                    <input value={ossProviderPoolForm.public_base_url} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, public_base_url: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="https://cdn.example.com" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Root Prefix</label>
                                                    <input value={ossProviderPoolForm.root_prefix} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, root_prefix: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm font-mono" placeholder="aistory/upload" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Strategy</label>
                                                    <select value={ossProviderPoolForm.strategy} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, strategy: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm">
                                                        <option value="random">{t('随机', 'Random')}</option>
                                                        <option value="round_robin">{t('轮询', 'Round Robin')}</option>
                                                        <option value="weighted">{t('权重随机', 'Weighted Random')}</option>
                                                    </select>
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Default Storage Class</label>
                                                    <input value={ossProviderPoolForm.default_storage_class} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, default_storage_class: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="STANDARD" />
                                                </div>
                                                <div>
                                                    <label className="block text-xs uppercase text-gray-400 mb-1">Retention Days</label>
                                                    <input value={ossProviderPoolForm.retention_days} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, retention_days: e.target.value }))} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm" placeholder="30" />
                                                </div>
                                                <label className="flex items-center gap-2 text-sm text-gray-300"><input type="checkbox" checked={!!ossProviderPoolForm.force_path_style} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, force_path_style: e.target.checked }))} /> force_path_style</label>
                                                <label className="flex items-center gap-2 text-sm text-gray-300"><input type="checkbox" checked={!!ossProviderPoolForm.is_active} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, is_active: e.target.checked }))} /> {t('启用该池', 'Pool Active')}</label>
                                            </div>

                                            <div className="space-y-2">
                                                <div className="flex items-center justify-between">
                                                    <label className="block text-xs uppercase text-gray-400">Credentials ({t('多个密钥池', 'Multiple Keys')})</label>
                                                    <button 
                                                        onClick={() => {
                                                            let creds = [];
                                                            try { creds = JSON.parse(ossProviderPoolForm.credentials_text || '[]'); } catch(e){}
                                                            if (!Array.isArray(creds)) creds = [];
                                                            creds.push({ access_key: '', secret_key: '', label: '', is_active: true });
                                                            setOssProviderPoolForm(f => ({ ...f, credentials_text: JSON.stringify(creds, null, 2) }));
                                                        }}
                                                        className="text-xs px-2 py-1 bg-sky-600/20 hover:bg-sky-600/40 text-sky-400 rounded flex items-center gap-1 transition-colors"
                                                    ><Plus size={12}/> {t('添加密钥', 'Add Credential')}</button>
                                                </div>
                                                {(() => {
                                                    let creds = [];
                                                    try { creds = JSON.parse(ossProviderPoolForm.credentials_text || '[]'); } catch(e){ return <div className="text-red-400 text-xs text-center py-2">JSON Parse Error in Credentials</div>; }
                                                    if (!Array.isArray(creds)) creds = [];
                                                    const updateCred = (index, field, value) => {
                                                        const newCreds = [...creds];
                                                        newCreds[index] = { ...newCreds[index], [field]: value };
                                                        setOssProviderPoolForm(f => ({ ...f, credentials_text: JSON.stringify(newCreds, null, 2) }));
                                                    };
                                                    const removeCred = (index) => {
                                                        const newCreds = creds.filter((_, i) => i !== index);
                                                        setOssProviderPoolForm(f => ({ ...f, credentials_text: JSON.stringify(newCreds, null, 2) }));
                                                    };

                                                    return creds.length === 0 ? (
                                                        <div className="text-center text-gray-500 text-xs py-4 bg-black/20 border border-white/5 rounded italic">{t('暂无配置凭证', 'No credentials configured')}</div>
                                                    ) : creds.map((cred, idx) => (
                                                        <div key={idx} className="border border-white/10 rounded p-3 bg-black/20 gap-2 flex flex-col relative group">
                                                            <button onClick={() => removeCred(idx)} className="absolute right-2 top-2 text-red-400/50 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity" title={t('删除', 'Delete')}><Trash2 size={14}/></button>
                                                            <div className="grid grid-cols-2 gap-2">
                                                                <div>
                                                                    <div className="text-[10px] text-gray-500 mb-0.5">Access Key</div>
                                                                    <input className="w-full bg-black/40 border border-gray-700/50 rounded px-2 py-1 text-xs" value={cred.access_key || ''} onChange={e => updateCred(idx, 'access_key', e.target.value)} placeholder="Access Key" />
                                                                </div>
                                                                <div>
                                                                    <div className="text-[10px] text-gray-500 mb-0.5">Secret Key</div>
                                                                    <input className="w-full bg-black/40 border border-gray-700/50 rounded px-2 py-1 text-xs" value={cred.secret_key || ''} onChange={e => updateCred(idx, 'secret_key', e.target.value)} placeholder="Secret Key" />
                                                                </div>
                                                                <div>
                                                                    <div className="text-[10px] text-gray-500 mb-0.5">Label (可选)</div>
                                                                    <input className="w-full bg-black/40 border border-gray-700/50 rounded px-2 py-1 text-xs" value={cred.label || ''} onChange={e => updateCred(idx, 'label', e.target.value)} placeholder="e.g. primary" />
                                                                </div>
                                                                <div className="flex items-center pt-2 pb-0.5 px-1">
                                                                    <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
                                                                        <input type="checkbox" checked={cred.is_active !== false} onChange={e => updateCred(idx, 'is_active', e.target.checked)} className="rounded border-gray-700/50 bg-black/40" />
                                                                        {t('启用此密钥', 'Active')}
                                                                    </label>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ));
                                                })()}
                                            </div>
                                            <div>
                                                <label className="block text-xs uppercase text-gray-400 mb-1">Weights JSON</label>
                                                <textarea value={ossProviderPoolForm.weights_text} onChange={(e) => setOssProviderPoolForm((f) => ({ ...f, weights_text: e.target.value }))} rows={3} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs font-mono" placeholder="[1, 3, 1]" />
                                            </div>

                                            <div className="flex flex-wrap gap-2">
                                                <button onClick={handleCreateOssProviderPool} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-xs flex items-center gap-1"><Plus size={12} /> {t(' 新建', 'Create')}</button>
                                                <button onClick={handleUpdateOssProviderPool} disabled={!selectedOssProviderPoolId} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-bold rounded text-xs flex items-center gap-1"><Edit2 size={12} /> {t('更新', 'Update')}</button>    
                                                <button onClick={handleDeleteOssProviderPool} disabled={!selectedOssProviderPoolId} className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-bold rounded text-xs flex items-center gap-1"><Trash2 size={12} /> {t('删除', 'Delete')}</button>   
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}

                      {/* LLM CALL LOGS */}
                      {activeTab === 'llm_logs' && (
                          <div className="space-y-4">
                              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                  <h3 className="text-lg font-bold">{t('LLM 调用日志', 'LLM Call Logs')}</h3>
                                  <div className="flex gap-2">
                                      <button className="px-3 py-1 flex items-center gap-1 bg-primary text-white rounded hover:bg-primary/90" onClick={() => fetchLlmLogs()}>
                                          <RefreshCw className="w-4 h-4" /> {t('刷新', 'Refresh')}
                                      </button>
                                  </div>
                              </div>
                              {isLlmLogsLoading ? (
                                  <div className="flex justify-center p-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>
                              ) : llmLogsError ? (
                                  <div className="p-4 text-red-400 bg-red-400/10 rounded-xl">{llmLogsError}</div>
                              ) : (
                                  <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden overflow-x-auto">
                                      <table className="w-full text-sm text-left">
                                          <thead className="text-xs uppercase bg-black/40 text-gray-400">
                                              <tr>
                                                  <th className="px-4 py-3">ID</th>
                                                  <th className="px-4 py-3">Time</th>
                                                  <th className="px-4 py-3">Provider</th>
                                                  <th className="px-4 py-3">Model</th>
                                                  <th className="px-4 py-3">{t('状态', 'Status')}</th>
                                                  <th className="px-4 py-3">Latency</th>
                                                  <th className="px-4 py-3">API URL</th>
                                                  <th className="px-4 py-3">Details</th>
                                              </tr>
                                          </thead>
                                          <tbody className="divide-y divide-white/5">
                                              {llmLogs.map(log => (
                                                  <tr key={log.id} className="hover:bg-white/5">
                                                      <td className="px-4 py-3 opacity-60">#{log.id}</td>
                                                      <td className="px-4 py-3 whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
                                                      <td className="px-4 py-3 whitespace-nowrap">{log.provider}</td>
                                                      <td className="px-4 py-3 whitespace-nowrap">{log.model}</td>
                                                      <td className="px-4 py-3 whitespace-nowrap">
                                                          {log.tag === 'LLM_REQUEST' ? <span className="text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded text-xs">{t('请求中', 'Pending')}</span> :
                                                           log.tag === 'LLM_RESPONSE' ? <span className="text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded text-xs">{t('成功', 'Success')}</span> :
                                                           log.tag === 'LLM_RESPONSE_ERROR' ? <span className="text-red-400 bg-red-400/10 px-2 py-1 rounded text-xs">{t('失败', 'Failed')}</span> :
                                                           <span className="text-gray-400 bg-gray-400/10 px-2 py-1 rounded text-xs">{log.tag}</span>}
                                                      </td>
                                                      <td className="px-4 py-3 whitespace-nowrap">{log.latency_ms ? `${log.latency_ms}ms` : '-'}</td>
                                                      <td className="px-4 py-3 whitespace-nowrap">{log.api_url ? log.api_url : '-'}</td>
                                                      <td className="px-4 py-3">
                                                          <button className="text-primary hover:underline text-xs" onClick={() => setSelectedLlmLog(log)}>{t('查看', 'View')}</button>
                                                      </td>
                                                  </tr>
                                              ))}
                                              {llmLogs.length === 0 && (
                                                  <tr><td colSpan="8" className="px-4 py-8 text-center text-gray-500">{t('暂无日志', 'No logs found')}</td></tr>
                                              )}
                                          </tbody>
                                      </table>
                                  </div>
                              )}
                          </div>
                      )}

                      {/* RUNTIME LOGS TAB */}
                      {activeTab === 'runtime_logs' && (
                        <div className="space-y-4">
                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                <h3 className="text-lg font-bold">{t('系统运行日志（含 logger.info）', 'Runtime Logs (including logger.info)')}</h3>
                                <div className="flex flex-wrap items-center gap-2">
                                    <select
                                        value={selectedRuntimeLogFile}
                                        onChange={(e) => {
                                            const fileName = e.target.value;
                                            setSelectedRuntimeLogFile(fileName);
                                            fetchRuntimeLogs(fileName);
                                        }}
                                        className="bg-black/40 border border-gray-700 rounded p-2 text-sm min-w-[220px]"
                                    >
                                        {runtimeLogFiles.map((f) => (
                                            <option key={f.name} value={f.name}>
                                                {f.name} ({formatBytes(f.size_bytes)})
                                            </option>
                                        ))}
                                    </select>
                                    <input
                                        type="number"
                                        min={1}
                                        max={5000}
                                        value={runtimeLogTailLines}
                                        onChange={(e) => setRuntimeLogTailLines(e.target.value)}
                                        className="w-24 bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                        title={t('尾部行数', 'Tail lines')}
                                    />
                                    <button
                                        onClick={() => fetchRuntimeLogs(selectedRuntimeLogFile)}
                                        disabled={isRuntimeLogsLoading}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <RefreshCw size={16} className={isRuntimeLogsLoading ? 'animate-spin' : ''} /> Refresh
                                    </button>
                                </div>
                            </div>
                            
                            {/* Runtime Log Filters */}
                            <div className="flex flex-wrap gap-3 bg-black/20 p-3 rounded border border-gray-800 text-sm mt-2">
                                <div className="text-xs text-gray-500 w-full mb-1">
                                    {t('使用子串过滤文件里的记录', 'Filter by substrings in log lines')}
                                </div>
                                <input 
                                    type="text" 
                                    placeholder={t('过滤用户名', 'Filter by User')} 
                                    value={runtimeLogFilters.user_name}
                                    onChange={(e) => setRuntimeLogFilters({...runtimeLogFilters, user_name: e.target.value})}
                                    className="flex-1 min-w-[120px] bg-black/40 border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-primary"
                                />
                                <input 
                                    type="text" 
                                    placeholder={t('过滤操作内容', 'Filter by Action/Content')} 
                                    value={runtimeLogFilters.action}
                                    onChange={(e) => setRuntimeLogFilters({...runtimeLogFilters, action: e.target.value})}
                                    className="flex-1 min-w-[120px] bg-black/40 border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-primary"
                                />
                                <input 
                                    type="datetime-local" 
                                    title={t('起始时间', 'Start time')}
                                    value={runtimeLogFilters.start_time}
                                    onChange={(e) => setRuntimeLogFilters({...runtimeLogFilters, start_time: e.target.value})}
                                    className="bg-black/40 border border-gray-700 rounded px-2 py-1.5 outline-none hidden-calendar-icon focus:border-primary"
                                    style={{ colorScheme: 'dark' }}
                                />
                                <input 
                                    type="datetime-local"
                                    title={t('结束时间', 'End time')}
                                    value={runtimeLogFilters.end_time}
                                    onChange={(e) => setRuntimeLogFilters({...runtimeLogFilters, end_time: e.target.value})}
                                    className="bg-black/40 border border-gray-700 rounded px-2 py-1.5 outline-none hidden-calendar-icon focus:border-primary"
                                    style={{ colorScheme: 'dark' }}
                                />
                                <button
                                      onClick={() => {
                                          setRuntimeLogFilters({user_name:'', action:'', start_time:'', end_time:''});
                                          fetchRuntimeLogs(selectedRuntimeLogFile);
                                      }}
                                      className="bg-gray-800 hover:bg-gray-700 text-xs px-3 py-1.5 rounded transition-colors whitespace-nowrap"
                                >{t('重置', 'Reset')}</button>
                            </div>

                            {runtimeLogsError ? (
                                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">
                                    {runtimeLogsError}
                                </div>
                            ) : null}

                            <div className="text-xs text-gray-500">
                                Showing last {Math.max(1, Number(runtimeLogTailLines) || 300)} lines from {selectedRuntimeLogFile}
                            </div>

                            <pre ref={runtimeLogPreRef} className="w-full min-h-[420px] max-h-[620px] overflow-auto bg-black/40 border border-gray-700 rounded p-3 text-xs text-gray-100 whitespace-pre-wrap break-all font-mono">
                                {isRuntimeLogsLoading ? 'Loading runtime logs...' : (runtimeLogContent || 'No content')}
                            </pre>
                        </div>
                    )}

                    {activeTab === 'storage_usage' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-lg font-bold">{t('用户磁盘使用统计', 'Per-User Storage Usage')}</h3>
                                <button
                                    onClick={() => { fetchStorageUsage(); fetchExpiredFiles(); fetchOrphanFiles(); }}
                                    disabled={isStorageUsageLoading || isExpiredFilesLoading || isOrphanFilesLoading}
                                    className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                >
                                    <RefreshCw size={16} className={(isStorageUsageLoading || isExpiredFilesLoading || isOrphanFilesLoading) ? 'animate-spin' : ''} /> {t('刷新', 'Refresh')}
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

                            <hr className="border-white/20 my-6" />

                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-bold text-orange-400">{t('超期文件清理 (超过60天)', 'Expired Files Cleanup (>60 days)')}</h3>
                                    <p className="text-xs text-gray-400 mt-1">
                                        {t(`总计: ${expiredFilesData?.total_count || 0} 个文件, 占用空间: ${formatBytes(expiredFilesData?.total_size || 0)}`, `Total: ${expiredFilesData?.total_count || 0} files, Size: ${formatBytes(expiredFilesData?.total_size || 0)}`)}
                                    </p>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => handleRemindExpiredFiles()}
                                        disabled={isExpiredFilesLoading || !expiredFilesData?.files?.length}
                                        className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <Mail size={16} /> {t('群发提醒邮件', 'Send Reminder Emails')}
                                    </button>
                                    <button
                                        onClick={() => handleDeleteExpiredFiles()}
                                        disabled={isExpiredFilesLoading || !expiredFilesData?.files?.length}
                                        className="bg-red-600 hover:bg-red-500 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <Trash2 size={16} /> {t('清除超期文件', 'Clear Expired Files')}
                                    </button>
                                </div>
                            </div>
                            
                            {expiredFilesError ? (
                                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">{expiredFilesError}</div>
                            ) : null}

                            <div className="overflow-x-auto border border-white/10 rounded-lg max-h-96 overflow-y-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-black/40 sticky top-0">
                                        <tr className="text-left text-gray-300">
                                            <th className="px-3 py-2">{t('用户名', 'User')}</th>
                                            <th className="px-3 py-2">{t('文件路径', 'File Path')}</th>
                                            <th className="px-3 py-2 text-right">{t('修改时间', 'Modified At')}</th>
                                            <th className="px-3 py-2 text-right">{t('大小', 'Size')}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(expiredFilesData?.files || []).map((row, idx) => (
                                            <tr key={idx} className="border-t border-white/5">
                                                <td className="px-3 py-2">{row.username} <span className="text-xs text-gray-500">({row.user_id})</span></td>
                                                <td className="px-3 py-2 text-gray-300 break-all">{row.filepath}</td>
                                                <td className="px-3 py-2 text-right whitespace-nowrap">{new Date(row.modified_at).toLocaleString()}</td>
                                                <td className="px-3 py-2 text-right font-mono">{formatBytes(row.size || 0)}</td>
                                            </tr>
                                        ))}
                                        {!isExpiredFilesLoading && (!expiredFilesData?.files || expiredFilesData.files.length === 0) && (
                                            <tr>
                                                <td colSpan={4} className="px-3 py-6 text-center text-gray-400">{t('暂无超期文件', 'No expired files')}</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>

                            <hr className="border-white/20 my-6" />

                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-bold text-yellow-400">{t('孤立文件检测', 'Orphan File Detection')}</h3>
                                    <p className="text-xs text-gray-400 mt-1">
                                        {t(
                                            '检测素材库中未被活跃资产或分镜引用的图片/视频（含已删除资产/分镜遗留文件）。',
                                            'Detect image/video files on disk not referenced by active assets or shots (including leftovers from deleted assets/shots).'
                                        )}
                                    </p>
                                    <p className="text-xs text-gray-400 mt-1">
                                        {t(`总计: ${orphanFilesData?.total_count || 0} 个文件, 占用空间: ${formatBytes(orphanFilesData?.total_size || 0)}`, `Total: ${orphanFilesData?.total_count || 0} files, Size: ${formatBytes(orphanFilesData?.total_size || 0)}`)}
                                    </p>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => handleDeleteOrphanFiles()}
                                        disabled={isOrphanFilesLoading || !orphanFilesData?.files?.length}
                                        className="bg-red-600 hover:bg-red-500 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <Trash2 size={16} /> {t('清除孤立文件', 'Clear Orphan Files')}
                                    </button>
                                </div>
                            </div>

                            {orphanFilesError ? (
                                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">{orphanFilesError}</div>
                            ) : null}

                            <div className="overflow-x-auto border border-white/10 rounded-lg max-h-96 overflow-y-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-black/40 sticky top-0">
                                        <tr className="text-left text-gray-300">
                                            <th className="px-3 py-2">{t('用户名', 'User')}</th>
                                            <th className="px-3 py-2">{t('文件路径', 'File Path')}</th>
                                            <th className="px-3 py-2 text-right">{t('修改时间', 'Modified At')}</th>
                                            <th className="px-3 py-2 text-right">{t('大小', 'Size')}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(orphanFilesData?.files || []).map((row, idx) => (
                                            <tr key={idx} className="border-t border-white/5">
                                                <td className="px-3 py-2">{row.username} <span className="text-xs text-gray-500">({row.user_id})</span></td>
                                                <td className="px-3 py-2 text-gray-300 break-all">{row.filepath}</td>
                                                <td className="px-3 py-2 text-right whitespace-nowrap">{new Date(row.modified_at).toLocaleString()}</td>
                                                <td className="px-3 py-2 text-right font-mono">{formatBytes(row.size || 0)}</td>
                                            </tr>
                                        ))}
                                        {!isOrphanFilesLoading && (!orphanFilesData?.files || orphanFilesData.files.length === 0) && (
                                            <tr>
                                                <td colSpan={4} className="px-3 py-6 text-center text-gray-400">{t('暂无孤立文件', 'No orphan files')}</td>
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
                                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
                                            <div className="flex-1">
                                                <div className="text-xs text-muted-foreground mb-1">
                                                    {t('Prompt 文件', 'Prompt File')}
                                                </div>
                                                <select
                                                    value={selectedPromptSkillPromptRef}
                                                    onChange={(e) => loadPromptSkillPrompt(e.target.value)}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs text-gray-200"
                                                >
                                                    {getPromptRefsForSkill(promptSkills.find((item) => String(item?.id || '').trim() === selectedPromptSkillId) || {}).map((promptRef) => (
                                                        <option key={promptRef} value={promptRef}>{promptRef}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {promptSkillSaveMessage && <span className="text-xs text-emerald-300">{promptSkillSaveMessage}</span>}
                                                <button
                                                    onClick={() => loadPromptSkillPrompt(selectedPromptSkillPromptRef)}
                                                    disabled={isPromptSkillTextLoading || !selectedPromptSkillPromptRef}
                                                    className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded text-xs disabled:opacity-50"
                                                >
                                                    {t('重载', 'Reload')}
                                                </button>
                                                <button
                                                    onClick={handleSavePromptSkill}
                                                    disabled={isPromptSkillSaving || isPromptSkillTextLoading || !selectedPromptSkillPromptRef}
                                                    className="bg-primary hover:bg-primary/90 text-white px-3 py-2 rounded text-xs disabled:opacity-50"
                                                >
                                                    {isPromptSkillSaving ? t('保存中...', 'Saving...') : t('保存 Prompt', 'Save Prompt')}
                                                </button>
                                            </div>
                                        </div>
                                        {isPromptSkillTextLoading ? (
                                            <div className="text-sm text-muted-foreground">{t('加载提示词中...', 'Loading prompt...')}</div>
                                        ) : selectedPromptSkillText ? (
                                            <textarea
                                                value={selectedPromptSkillText}
                                                onChange={(e) => setSelectedPromptSkillText(e.target.value)}
                                                className="w-full min-h-[420px] bg-gray-900 border border-gray-700 rounded p-3 font-mono text-xs text-gray-200"
                                                spellCheck={false}
                                            />
                                        ) : (
                                            <div className="text-sm text-muted-foreground">{t('该 skill 暂无可编辑 Prompt。', 'No editable prompt for this skill.')}</div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                </div>
            </main>

            {isKieSuggestionEditOpen && (
                <div
                    className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[1px] flex items-center justify-center p-4"
                    onClick={closeKieSuggestionEditor}
                >
                    <div
                        className="w-full max-w-5xl max-h-[86vh] overflow-y-auto border border-white/15 rounded-xl p-4 bg-[#0d0f14] space-y-3 shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                            <h4 className="text-sm font-bold text-sky-200">{t('编辑 KIE 建议规则', 'Edit KIE Suggested Rule')}</h4>
                            <button
                                onClick={closeKieSuggestionEditor}
                                className="px-2.5 py-1 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs"
                            >
                                {t('关闭', 'Close')}
                            </button>
                        </div>

                        <div className="text-xs text-gray-300 space-y-1">
                            <div>system_api_id: <span className="text-white">{editingKieSuggestionMeta.system_api_id || '-'}</span></div>
                            <div className="truncate" title={editingKieSuggestionMeta.model || '-'}>model: <span className="text-white">{editingKieSuggestionMeta.model || '-'}</span></div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <div className="md:col-span-2">
                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('目标 System API', 'Target System API')}</label>
                                <select
                                    value={kieSuggestionEditForm.target_system_api_id}
                                    onChange={(e) => setKieSuggestionEditForm((prev) => ({ ...prev, target_system_api_id: e.target.value }))}
                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                >
                                    <option value="">{t('请选择', 'Please select')}</option>
                                    {(Array.isArray(systemApiRows) ? systemApiRows : []).map((apiRow) => {
                                        const apiId = Number(apiRow?.id || 0);
                                        if (apiId <= 0) return null;
                                        const label = `${apiId} | ${String(apiRow?.provider || '-')} | ${String(apiRow?.category || '-')} | ${String(apiRow?.model || '-')}`;
                                        return (
                                            <option key={`kie-target-api-${apiId}`} value={String(apiId)}>{label}</option>
                                        );
                                    })}
                                </select>
                            </div>
                            <div className="md:col-span-2">
                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('单位', 'Unit')}</label>
                                <select
                                    value={kieSuggestionEditForm.billing_unit_type}
                                    onChange={(e) => setKieSuggestionEditForm((prev) => ({ ...prev, billing_unit_type: e.target.value }))}
                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
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
                                <label className="block text-xs uppercase text-gray-400 mb-1">cost</label>
                                <input
                                    type="number"
                                    min={0}
                                    step={1}
                                    value={kieSuggestionEditForm.billing_cost}
                                    onChange={(e) => setKieSuggestionEditForm((prev) => ({ ...prev, billing_cost: e.target.value }))}
                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                />
                            </div>
                            <div>
                                <label className="block text-xs uppercase text-gray-400 mb-1">cost_input</label>
                                <input
                                    type="number"
                                    min={0}
                                    step={1}
                                    value={kieSuggestionEditForm.billing_cost_input}
                                    onChange={(e) => setKieSuggestionEditForm((prev) => ({ ...prev, billing_cost_input: e.target.value }))}
                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                />
                            </div>
                            <div>
                                <label className="block text-xs uppercase text-gray-400 mb-1">cost_output</label>
                                <input
                                    type="number"
                                    min={0}
                                    step={1}
                                    value={kieSuggestionEditForm.billing_cost_output}
                                    onChange={(e) => setKieSuggestionEditForm((prev) => ({ ...prev, billing_cost_output: e.target.value }))}
                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                />
                            </div>
                        </div>

                        <div className="border border-white/10 rounded-lg p-3 bg-black/20 space-y-2">
                            <div className="flex items-center justify-between gap-2">
                                <div className="text-xs uppercase text-gray-400">{t('细分规则 (Granular Rules)', 'Granular Rules')}</div>
                                <button
                                    type="button"
                                    onClick={addKieGranularRuleForEdit}
                                    className="px-2 py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded text-[11px]"
                                >
                                    {t('新增分档', 'Add Tier')}
                                </button>
                            </div>

                            {(Array.isArray(kieSuggestionEditForm?.granular_rules) ? kieSuggestionEditForm.granular_rules : []).length === 0 && (
                                <div className="text-xs text-gray-500">{t('当前没有 granular 规则，可点击“新增分档”。', 'No granular rules yet. Click Add Tier.')}</div>
                            )}

                            {(Array.isArray(kieSuggestionEditForm?.granular_rules) ? kieSuggestionEditForm.granular_rules : []).map((gr, grIdx) => (
                                <div key={`kie-gr-edit-${grIdx}`} className="border border-white/10 rounded p-2 bg-black/30 space-y-2">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="text-xs text-sky-300">{`#${grIdx + 1}`}</div>
                                        <button
                                            type="button"
                                            onClick={() => removeKieGranularRuleForEdit(grIdx)}
                                            className="px-2 py-1 bg-rose-700 hover:bg-rose-600 text-white rounded text-[11px]"
                                        >
                                            {t('删除', 'Delete')}
                                        </button>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                                        <div className="md:col-span-2">
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">name</label>
                                            <input
                                                value={gr?.name || ''}
                                                onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'name', e.target.value)}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">unit</label>
                                            <select
                                                value={normalizeApiPricingUnitType(gr?.billing_unit_type)}
                                                onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'billing_unit_type', e.target.value)}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
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
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">priority</label>
                                            <input
                                                type="number"
                                                min={0}
                                                step={1}
                                                value={gr?.priority ?? ''}
                                                onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'priority', e.target.value)}
                                                className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">cost</label>
                                            <input type="number" min={0} step={1} value={gr?.billing_cost ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'billing_cost', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">cost_input</label>
                                            <input type="number" min={0} step={1} value={gr?.billing_cost_input ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'billing_cost_input', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">cost_output</label>
                                            <input type="number" min={0} step={1} value={gr?.billing_cost_output ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'billing_cost_output', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>

                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">generation_mode</label>
                                            <input value={gr?.generation_mode || ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'generation_mode', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">input_format</label>
                                            <input value={gr?.input_format || ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'input_format', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">output_format</label>
                                            <input value={gr?.output_format || ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'output_format', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>

                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">width_min</label>
                                            <input type="number" min={0} step={1} value={gr?.width_min ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'width_min', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">width_max</label>
                                            <input type="number" min={0} step={1} value={gr?.width_max ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'width_max', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">height_min</label>
                                            <input type="number" min={0} step={1} value={gr?.height_min ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'height_min', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">height_max</label>
                                            <input type="number" min={0} step={1} value={gr?.height_max ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'height_max', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">pixels_min</label>
                                            <input type="number" min={0} step={1} value={gr?.pixels_min ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'pixels_min', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                        <div>
                                            <label className="block text-[11px] uppercase text-gray-400 mb-1">pixels_max</label>
                                            <input type="number" min={0} step={1} value={gr?.pixels_max ?? ''} onChange={(e) => updateKieGranularRuleForEdit(grIdx, 'pixels_max', e.target.value)} className="w-full bg-black/40 border border-gray-700 rounded p-2 text-xs" />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                            <button
                                onClick={closeKieSuggestionEditor}
                                className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                onClick={saveKieSuggestionEditor}
                                className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
                            >
                                {t('保存修改', 'Save Changes')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

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

            <UserEditModal
                draft={userEditModal}
                setDraft={setUserEditModal}
                onClose={() => setUserEditModal(null)}
                onSave={handleSaveUserModal}
                isSaving={isSavingUserEditModal}
                normalizeUserActiveLevel={normalizeUserActiveLevel}
                isUserEnabled={isUserEnabled}
            />
            
            <LlmLogViewer log={selectedLlmLog} onClose={() => setSelectedLlmLog(null)} />
            
        </div>
    );
};

export default UserAdmin;

