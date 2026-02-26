import React, { useState, useEffect } from 'react';
import { api, getPricingRules, createPricingRule, updatePricingRule, deletePricingRule, getTransactions, updateUserCredits, syncPricingRules, getBillingOptions, getSystemSettingsManage, createSystemSettingManage, updateSystemSettingManage, deleteSystemSettingManage, exportSystemSettingsManage, importSystemSettingsManage, getAdminLlmLogFiles, getAdminLlmLogView } from '../services/api';
import Footer from '../components/Footer';
import { Shield, User, Key, Check, X, Crown, Settings, DollarSign, Activity, List, Plus, Trash2, Edit2, RefreshCw, CreditCard, Upload, Download, Mail, ArrowLeft } from 'lucide-react';
import { confirmUiMessage, promptUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI } from '../lib/uiLang';

const UserAdmin = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [pricingRules, setPricingRules] = useState([]);
    const [billingOptions, setBillingOptions] = useState(null);
    const [transactions, setTransactions] = useState([]);
    const [transactionFilterUser, setTransactionFilterUser] = useState(''); // User ID filter
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // New/Edit Rule State
    const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
    const [editingRule, setEditingRule] = useState(null);
    const [ruleForm, setRuleForm] = useState({ task_type: 'llm_chat', provider: '', model: '', cost: 1, cost_input: 0, cost_output: 0, unit_type: 'per_call' });
    
    // Calculator State
    const [calcPriceUSD, setCalcPriceUSD] = useState('');
    const [calcPriceInput, setCalcPriceInput] = useState('');
    const [calcPriceOutput, setCalcPriceOutput] = useState('');
    const [exchangeRate, setExchangeRate] = useState(10); // Default: ￥1 = 10 Credits
    const [markup, setMarkup] = useState('1.0'); // Default: 1.0x (No markup) - String for better input handling

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
    const [smtpTestEmail, setSmtpTestEmail] = useState('');
    const [isSmtpTestLoading, setIsSmtpTestLoading] = useState(false);
    const [smtpBroadcast, setSmtpBroadcast] = useState({
        subject: '',
        content_html: '',
        content_text: '',
    });
    const [isSmtpBroadcastLoading, setIsSmtpBroadcastLoading] = useState(false);
    const [systemApiRows, setSystemApiRows] = useState([]);
    const [isSystemApiLoading, setIsSystemApiLoading] = useState(false);
    const [isSystemApiImporting, setIsSystemApiImporting] = useState(false);
    const [isSystemApiExporting, setIsSystemApiExporting] = useState(false);
    const [selectedSystemApiId, setSelectedSystemApiId] = useState('');
    const [systemApiFilterCategory, setSystemApiFilterCategory] = useState('all');
    const [systemApiFilterProvider, setSystemApiFilterProvider] = useState('all');
    const [systemApiSortMode, setSystemApiSortMode] = useState('default');
    const [systemApiForm, setSystemApiForm] = useState({
        name: '',
        category: 'LLM',
        provider: '',
        api_key: '',
        base_url: '',
        model: '',
        webHook: '',
        smart_priority: '100',
        smart_retry_limit: '1',
        smart_multi_ref_default: false,
        is_active: false,
    });
    const systemApiImportInputRef = React.useRef(null);
    const [llmLogFiles, setLlmLogFiles] = useState([]);
    const [selectedLlmLogFile, setSelectedLlmLogFile] = useState('llm_calls.log');
    const [llmLogTailLines, setLlmLogTailLines] = useState(300);
    const [llmLogContent, setLlmLogContent] = useState('');
    const [isLlmLogsLoading, setIsLlmLogsLoading] = useState(false);
    const [llmLogsError, setLlmLogsError] = useState('');

    // ... existing code ...

    const isTokenUnitType = (unitType) => ['per_token', 'per_1k_tokens', 'per_million_tokens'].includes(unitType);
    const tokenUnitLabel = (unitType) => {
        if (unitType === 'per_1k_tokens') return '1K';
        if (unitType === 'per_token') return 'token';
        return '1M';
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
        }
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'llm_logs') {
            fetchLlmLogs();
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

    useEffect(() => {
        if (!selectedSystemApiId) {
            setSystemApiForm({
                name: '',
                category: 'LLM',
                provider: '',
                api_key: '',
                base_url: '',
                model: '',
                webHook: '',
                smart_priority: '100',
                smart_retry_limit: '1',
                smart_multi_ref_default: false,
                is_active: false,
            });
            return;
        }
        const row = systemApiRows.find((item) => String(item.id) === String(selectedSystemApiId));
        if (!row) return;
        setSystemApiForm({
            name: row.name || '',
            category: row.category || 'LLM',
            provider: row.provider || '',
            api_key: '',
            base_url: row.base_url || '',
            model: row.model || '',
            webHook: row?.config?.webHook || '',
            smart_priority: String(row?.config?.smart_priority ?? row?.config?.priority ?? '100'),
            smart_retry_limit: String(row?.config?.smart_retry_limit ?? row?.config?.retry_limit ?? '1'),
            smart_multi_ref_default: !!row?.config?.smart_multi_ref_default,
            is_active: !!row.is_active,
        });
    }, [selectedSystemApiId, systemApiRows]);

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

    const visibleSystemApiRows = React.useMemo(() => {
        const rows = [...filteredSystemApiRows];
        if (systemApiSortMode === 'priority') {
            rows.sort((a, b) => {
                const pa = getSmartPriority(a);
                const pb = getSmartPriority(b);
                if (pa !== pb) return pa - pb;
                return Number(a?.id || 0) - Number(b?.id || 0);
            });
        }
        return rows;
    }, [filteredSystemApiRows, systemApiSortMode]);

    const getSmartPriority = (row) => {
        const raw = row?.config?.smart_priority ?? row?.config?.priority ?? 100;
        const parsed = Number(raw);
        return Number.isFinite(parsed) ? parsed : 100;
    };

    const getSmartRetryLimit = (row) => {
        const raw = row?.config?.smart_retry_limit ?? row?.config?.retry_limit ?? 1;
        const parsed = Number(raw);
        return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
    };

    const isSmartMultiRefDefault = (row) => !!row?.config?.smart_multi_ref_default;

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
                api_key: String(systemApiForm.api_key || '').trim() || undefined,
                base_url: String(systemApiForm.base_url || '').trim() || undefined,
                model: String(systemApiForm.model || '').trim() || undefined,
                config: {
                    webHook: String(systemApiForm.webHook || '').trim() || '',
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
                api_key: String(systemApiForm.api_key || '').trim() || undefined,
                base_url: String(systemApiForm.base_url || '').trim() || undefined,
                model: String(systemApiForm.model || '').trim() || undefined,
                config: {
                    webHook: String(systemApiForm.webHook || '').trim() || '',
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

    const apply126Template = () => {
        setSmtpConfig((prev) => ({
            ...prev,
            host: 'smtp.126.com',
            port: 465,
            use_ssl: true,
            use_tls: false,
        }));
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

    // ... existing fetchAllData ...

    // Effect to auto-calculate
    useEffect(() => {
        const rate = parseFloat(exchangeRate) || 10;
        const mark = parseFloat(markup) || 1.0;
        
        // Single Cost Calculation (Generic)
        const price = parseFloat(calcPriceUSD);
        let validUpdate = false;
        let updates = {};

        // Always save reference values
        updates.ref_markup = mark;
        updates.ref_exchange_rate = rate;
        
        if (!isNaN(price)) {
            updates.cost = Math.ceil(price * rate * mark);
            updates.ref_cost_cny = price;
            validUpdate = true;
        }

        // Dual Cost Calculation (Token-based)
        if (isTokenUnitType(ruleForm.unit_type)) {
            const pInput = parseFloat(calcPriceInput);
            const pOutput = parseFloat(calcPriceOutput);
            
            if (!isNaN(pInput) || !isNaN(pOutput)) {
                 const costIn = !isNaN(pInput) ? pInput * rate * mark : 0;
                 const costOut = !isNaN(pOutput) ? pOutput * rate * mark : 0;

                 updates.cost_input = Math.ceil(costIn);
                 updates.cost_output = Math.ceil(costOut);
                 updates.ref_cost_input_cny = !isNaN(pInput) ? pInput : 0;
                 updates.ref_cost_output_cny = !isNaN(pOutput) ? pOutput : 0;
                 validUpdate = true;
            }
        }
        
        if (validUpdate) {
            setRuleForm(prev => ({ ...prev, ...updates }));
        }
    }, [calcPriceUSD, calcPriceInput, calcPriceOutput, exchangeRate, markup, ruleForm.unit_type]);

    // Credit Edit State
    const [creditEditUser, setCreditEditUser] = useState(null);
    const [creditAmount, setCreditAmount] = useState(0);

    const providerOptionsForTask = (taskType) => {
        const providers = billingOptions?.providersByTaskType?.[taskType] || [];
        return providers.map(p => ({ value: p, label: p }));
    };

    const modelOptionsForProvider = (provider) => {
        if (!provider) return [];
        return billingOptions?.modelsByProvider?.[provider] || [];
    };

    const fetchAllData = async () => {
        setLoading(true);
        try {
            const [usersRes, rulesRes, transRes, optionsRes] = await Promise.allSettled([
                api.get('/users'),
                getPricingRules(),
                getTransactions(50, transactionFilterUser || null),
                getBillingOptions()
            ]);

            if (usersRes.status === 'fulfilled') {
                const fetchedUsers = usersRes.value.data;
                setUsers(fetchedUsers);
                
                // Extract System User Settings to populate Model Options
                const systemUsers = fetchedUsers.filter(u => u.is_system);
                if (systemUsers.length > 0) {
                     // We actually need to fetch api_settings from somewhere for these users, 
                     // OR rely on the sync endpoint logic.
                     // But the UI hardcoded MODEL_OPTIONS.
                     // Let's TRY to fetch system settings if an endpoint exists, or infer.
                     // The endpoint `GET /billing/rules/sync` does sync, maybe we call it or rely on existing rules?
                     // Better: Extract unique provider/models from existing Pricing Rules to seed the dropdowns + defaults
                }
            } 
            
            if (rulesRes.status === 'fulfilled') {
                const rules = rulesRes.value;
                setPricingRules(rules);
            }

            if (optionsRes.status === 'fulfilled') {
                setBillingOptions(optionsRes.value);
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

    const handleSaveRule = async () => {
        try {
            if (isTokenUnitType(ruleForm.unit_type)) {
                const ci = parseInt(ruleForm.cost_input || 0);
                const co = parseInt(ruleForm.cost_output || 0);
                if (ci <= 0 || co <= 0) {
                    alert('Token unit types require both Input and Output token costs (> 0).');
                    return;
                }
            }

            if (editingRule) {
                await updatePricingRule(editingRule.id, ruleForm);
            } else {
                await createPricingRule(ruleForm);
            }
            setIsRuleModalOpen(false);
            setEditingRule(null);
            fetchAllData(); // Refresh
        } catch (e) {
            alert("Failed to save rule: " + e.message);
        }
    };

    const handleSyncRules = async () => {
        setLoading(true);
        try {
            const added = await syncPricingRules();
            alert(`Sync complete. Added ${added.length} new rules.`);
            fetchAllData();
        } catch(e) {
            alert("Sync failed: " + e.message);
            setLoading(false);
        }
    };

    const handleDeleteRule = async (id) => {
        if (!await confirmUiMessage("Delete this pricing rule?")) return;
        try {
            await deletePricingRule(id);
            fetchAllData();
        } catch (e) { alert(e.message); }
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
            <main className="flex-1 container mx-auto px-4 pt-8 pb-8">
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

                            <div className="mb-4 p-4 rounded-lg border border-white/10 bg-black/20">
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <p className="text-sm text-gray-300">
                                        {t('网易 126 推荐模板：smtp.126.com，端口 465，SSL 开启，STARTTLS 关闭。', 'NetEase 126 template: smtp.126.com, port 465, SSL on, STARTTLS off.')}
                                    </p>
                                    <button
                                        onClick={apply126Template}
                                        className="px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 text-white"
                                    >
                                        {t('一键填充 126 模板', 'Apply 126 Template')}
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-6 max-w-4xl">
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
                            <div className="flex justify-between mb-4">
                                <h3 className="text-lg font-bold">{t('定价规则', 'Pricing Rules')}</h3>
                                <div className="flex gap-2">
                                    <button
                                        onClick={handleSyncRules}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2"
                                        title={t('导入系统 API 设置', 'Import system API settings')}
                                    >
                                        <RefreshCw size={16} /> {t('同步设置', 'Sync Settings')}
                                    </button>
                                    <button 
                                        onClick={() => { 
                                            setEditingRule(null); 
                                            setRuleForm({ task_type: 'llm_chat', provider: '', model: '', cost: 1, cost_input: 0, cost_output: 0, unit_type: 'per_call' }); 
                                            setCalcPriceUSD('');
                                            setCalcPriceInput('');
                                            setCalcPriceOutput('');
                                            setExchangeRate(10);
                                            setMarkup('1.0');
                                            setIsRuleModalOpen(true); 
                                        }}
                                        className="bg-primary hover:bg-primary/90 text-white px-3 py-1 rounded flex items-center gap-2"
                                    >
                                    <Plus size={16} /> {t('新增规则', 'Add Rule')}
                                </button>
                                </div>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-gray-800 text-gray-400 text-sm">
                                            <th className="p-3">{t('提供方', 'Provider')}</th>
                                            <th className="p-3">{t('模型', 'Model')}</th>
                                            <th className="p-3">{t('任务', 'Task')}</th>
                                            <th className="p-3">{t('成本（积分）', 'Cost (Credits)')}</th>
                                            <th className="p-3">{t('状态', 'Status')}</th>
                                            <th className="p-3 text-right">{t('操作', 'Actions')}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {pricingRules.map(rule => (
                                            <tr key={rule.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                                <td className="p-3">{rule.provider || t('*（全部）', '* (All)')}</td>
                                                <td className="p-3">{rule.model || t('*（全部）', '* (All)')}</td>
                                                <td className="p-3"><span className="bg-gray-700 px-2 py-0.5 rounded text-xs">{rule.task_type}</span></td>
                                                <td className="p-3">
                                                    {isTokenUnitType(rule.unit_type) ? (
                                                        <div className="flex flex-col text-xs font-mono">
                                                            <span className="text-blue-300" title={t('输入 Tokens', 'Input Tokens')}>In: {rule.cost_input} <span className="text-gray-600">/ {tokenUnitLabel(rule.unit_type)}</span></span>
                                                            <span className="text-green-300" title={t('输出 Tokens', 'Output Tokens')}>Out: {rule.cost_output} <span className="text-gray-600">/ {tokenUnitLabel(rule.unit_type)}</span></span>
                                                        </div>
                                                    ) : (
                                                        <span className="font-bold text-yellow-400">
                                                            {rule.cost} <span className="text-[10px] text-gray-500 font-normal">/ {rule.unit_type.replace('per_', '').replace('_', ' ')}</span>
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="p-3">
                                                    <span className={`w-2 h-2 rounded-full inline-block mr-2 ${rule.is_active ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                                    {rule.is_active ? t('启用', 'Active') : t('停用', 'Inactive')}
                                                </td>
                                                <td className="p-3 text-right flex justify-end gap-2">
                                                    <button onClick={() => { 
                                                        setEditingRule(rule); 
                                                        setRuleForm(rule); 
                                                        
                                                        const m = rule.ref_markup || 1.0;
                                                        const r = rule.ref_exchange_rate || 10;
                                                        setMarkup(m.toString());
                                                        setExchangeRate(r);

                                                        setCalcPriceUSD(rule.ref_cost_cny !== undefined && rule.ref_cost_cny !== null ? rule.ref_cost_cny : ((rule.cost || 0)/(r*m)));
                                                        
                                                        // For dual pricing, recreate approximates if ref missing
                                                        const inputApprox = (rule.cost_input || 0) / (r * m);
                                                        const outputApprox = (rule.cost_output || 0) / (r * m);

                                                        setCalcPriceInput(rule.ref_cost_input_cny !== undefined && rule.ref_cost_input_cny !== null ? rule.ref_cost_input_cny : inputApprox);
                                                        setCalcPriceOutput(rule.ref_cost_output_cny !== undefined && rule.ref_cost_output_cny !== null ? rule.ref_cost_output_cny : outputApprox);
                                                        
                                                        setIsRuleModalOpen(true); 
                                                    }} className="text-blue-400 hover:text-blue-300"><Edit2 size={16} /></button>
                                                    <button onClick={() => handleDeleteRule(rule.id)} className="text-red-400 hover:text-red-300"><Trash2 size={16} /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
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
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
                                            <div className="flex items-end">
                                                <button
                                                    onClick={() => {
                                                        setSystemApiFilterCategory('all');
                                                        setSystemApiFilterProvider('all');
                                                        setSystemApiSortMode('default');
                                                    }}
                                                    className="w-full bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded text-sm"
                                                >
                                                    {t('重置筛选', 'Reset Filters')}
                                                </button>
                                            </div>
                                        </div>

                                        <div className="flex items-center justify-between gap-2 text-xs">
                                            <span className="text-gray-400">{t('列表排序', 'List Order')}</span>
                                            <button
                                                onClick={() => setSystemApiSortMode((prev) => (prev === 'priority' ? 'default' : 'priority'))}
                                                className={`px-2.5 py-1 rounded border transition-colors ${systemApiSortMode === 'priority' ? 'bg-primary/20 text-primary border-primary/40' : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10'}`}
                                                title={t('仅改变当前列表展示顺序，不修改数据库数据。', 'Only changes current list view order, does not modify database data.')}
                                            >
                                                {systemApiSortMode === 'priority' ? t('当前：按优先级', 'Current: By Priority') : t('当前：默认顺序', 'Current: Default Order')}
                                            </button>
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

                                        <div className="overflow-y-auto max-h-[420px] border border-white/10 rounded">
                                            <table className="w-full text-xs">
                                                <thead className="bg-white/5 text-gray-400 sticky top-0">
                                                    <tr>
                                                        <th className="text-left p-2">{t('编号', 'ID')}</th>
                                                        <th className="text-left p-2">{t('类别', 'Category')}</th>
                                                        <th className="text-left p-2">{t('提供方', 'Provider')}</th>
                                                        <th className="text-left p-2">{t('模型', 'Model')}</th>
                                                        <th className="text-left p-2">{t('智能策略', 'Smart Strategy')}</th>
                                                        <th className="text-left p-2">{t('启用', 'Active')}</th>
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
                                                            <td className="p-2">{row.model || '-'}</td>
                                                            <td className="p-2">
                                                                <div className="flex flex-wrap gap-1">
                                                                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-200 border border-blue-500/30">
                                                                        {t('优先级', 'Priority')}: {getSmartPriority(row)}
                                                                    </span>
                                                                    <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-200 border border-purple-500/30">
                                                                        {t('重试', 'Retry')}: {getSmartRetryLimit(row)}
                                                                    </span>
                                                                    {isSmartMultiRefDefault(row) && (
                                                                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-500/30">
                                                                            {t('多图默认', 'Multi-ref Default')}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </td>
                                                            <td className="p-2">{row.is_active ? t('是', 'Yes') : t('否', 'No')}</td>
                                                        </tr>
                                                    ))}
                                                    {visibleSystemApiRows.length === 0 && (
                                                        <tr className="border-t border-white/10">
                                                            <td className="p-3 text-gray-400" colSpan={6}>
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
                                            <div className="md:col-span-2">
                                                <label className="block text-xs uppercase text-gray-400 mb-1">{t('API Key（留空则保留当前共享密钥）', 'API Key (leave blank to keep current shared key)')}</label>
                                                <input
                                                    type="password"
                                                    value={systemApiForm.api_key}
                                                    onChange={(e) => setSystemApiForm((prev) => ({ ...prev, api_key: e.target.value }))}
                                                    className="w-full bg-black/40 border border-gray-700 rounded p-2 text-sm"
                                                />
                                            </div>
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

                </div>
            </main>

            {/* Config Modal */}
            {isRuleModalOpen && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
                    <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-md">
                        <h3 className="text-xl font-bold mb-4">{editingRule ? t('编辑规则', 'Edit Rule') : t('新建定价规则', 'New Pricing Rule')}</h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">{t('任务类型', 'Task Type')}</label>
                                <select 
                                    className="w-full bg-gray-800 border border-gray-700 rounded p-2"
                                    value={ruleForm.task_type}
                                    onChange={e => setRuleForm({
                                        ...ruleForm, 
                                        task_type: e.target.value,
                                        provider: '',  // Reset dependent fields
                                        model: ''
                                    })}
                                >
                                    <option value="llm_chat">{t('聊天（LLM）', 'Chat (LLM)')}</option>
                                    <option value="image_gen">{t('图片生成', 'Image Generation')}</option>
                                    <option value="video_gen">{t('视频生成', 'Video Generation')}</option>
                                    <option value="analysis">{t('文本分析', 'Analysis (Text)')}</option>
                                    <option value="analysis_character">{t('角色分析', 'Character Analysis')}</option>
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">{t('提供方（可选）', 'Provider (Optional)')}</label>
                                    <select 
                                        className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm"
                                        value={ruleForm.provider || ''}
                                        onChange={e => setRuleForm({...ruleForm, provider: e.target.value || null, model: ''})}
                                    >
                                        <option value="">{t('任意（*）', 'Any (*)')}</option>
                                        {providerOptionsForTask(ruleForm.task_type).map(opt => (
                                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">{t('模型（可选）', 'Model (Optional)')}</label>
                                    <select 
                                        className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm"
                                        value={ruleForm.model || ''}
                                        onChange={e => setRuleForm({...ruleForm, model: e.target.value || null})}
                                    >
                                       <option value="">{t('任意（*）', 'Any (*)')}</option>
                                       {modelOptionsForProvider(ruleForm.provider).map(m => (
                                           <option key={m} value={m}>{m}</option>
                                       ))}
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">{t('计费单位', 'Unit Type')}</label>
                                <select 
                                    className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm"
                                    value={ruleForm.unit_type || 'per_call'}
                                    onChange={e => setRuleForm({...ruleForm, unit_type: e.target.value})}
                                >
                                    <option value="per_call">{t('按 API 调用（请求）', 'Per API Call (Request)')}</option>
                                    <option value="per_1k_tokens">{t('每 1k Tokens', 'Per 1k Tokens')}</option>
                                    <option value="per_million_tokens">{t('每 1M Tokens', 'Per 1M Tokens')}</option>
                                    <option value="per_image">{t('每张图片', 'Per Image')}</option>
                                    <option value="per_second">{t('每秒（视频）', 'Per Second (Video)')}</option>
                                    <option value="per_minute">{t('每分钟', 'Per Minute')}</option>
                                </select>
                            </div>

                            <div className="bg-black/40 p-3 rounded border border-white/5 space-y-3">
                                <label className="block text-xs font-medium text-blue-400 uppercase">{t('自动计算成本（人民币）', 'Auto-Calculate Cost (CNY)')}</label>
                                
                                {isTokenUnitType(ruleForm.unit_type) ? (
                                    /* LLM Dual Pricing Calculator */
                                    <div className="grid grid-cols-2 gap-3 mb-2">
                                        <div>
                                            <label className="block text-[10px] text-gray-400 mb-1">{t(`输入价格（每 ${tokenUnitLabel(ruleForm.unit_type)} Tokens）`, `Input Price (Per ${tokenUnitLabel(ruleForm.unit_type)} Tokens)`)}</label>
                                            <input 
                                                type="number" 
                                                step="0.0001"
                                                placeholder={ruleForm.unit_type === 'per_1k_tokens' ? t('例如：0.002', 'e.g. 0.002') : t('例如：1.00', 'e.g. 1.00')}
                                                className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                                value={calcPriceInput}
                                                onChange={(e) => setCalcPriceInput(e.target.value)}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] text-gray-400 mb-1">{t(`输出价格（每 ${tokenUnitLabel(ruleForm.unit_type)} Tokens）`, `Output Price (Per ${tokenUnitLabel(ruleForm.unit_type)} Tokens)`)}</label>
                                            <input 
                                                type="number" 
                                                step="0.0001"
                                                placeholder={ruleForm.unit_type === 'per_1k_tokens' ? t('例如：0.006', 'e.g. 0.006') : t('例如：6.00', 'e.g. 6.00')}
                                                className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                                value={calcPriceOutput}
                                                onChange={(e) => setCalcPriceOutput(e.target.value)}
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    /* Standard Single Pricing Calculator */
                                    <div className="mb-2">
                                        <label className="block text-[10px] text-gray-400 mb-1">
                                            {ruleForm.unit_type === 'per_million_tokens' ? t('每 1M Tokens 价格（元）', 'Price per 1M Tokens (Yuan)') :
                                            ruleForm.unit_type === 'per_1k_tokens' ? t('每 1K Tokens 价格（元）', 'Price per 1K Tokens (Yuan)') :
                                            ruleForm.unit_type === 'per_image' ? t('每张图片价格（元）', 'Price per Image (Yuan)') :
                                            ruleForm.unit_type === 'per_second' ? t('每秒价格（元）', 'Price per Second (Yuan)') :
                                            ruleForm.unit_type === 'per_minute' ? t('每分钟价格（元）', 'Price per Minute (Yuan)') :
                                            t('每次请求价格（元）', 'Price per Request (Yuan)')}
                                        </label>
                                        <input 
                                            type="number" 
                                            step="0.0001"
                                            placeholder={
                                                ruleForm.unit_type === 'per_million_tokens' ? '36.00' :
                                                ruleForm.unit_type === 'per_image' ? '0.30' :
                                                '0.015'
                                            }
                                            className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                            value={calcPriceUSD}
                                            onChange={(e) => setCalcPriceUSD(e.target.value)}
                                        />
                                        <p className="text-[9px] text-gray-600 mt-1">
                                            {ruleForm.unit_type === 'per_million_tokens' ? t('例如：GPT-4o 输入：约￥36.00', 'e.g. GPT-4o Input: ~￥36.00') :
                                            ruleForm.unit_type === 'per_image' ? t('例如：DALL-E 3：约￥0.30', 'e.g. DALL-E 3: ~￥0.30') :
                                            ruleForm.unit_type === 'per_second' ? t('例如：Runway：约￥0.35/秒', 'e.g. Runway: ~￥0.35/sec') :
                                            t('供应商基础成本（元）', 'Base provider cost in Yuan')}
                                        </p>
                                    </div>
                                )}

                                <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-2">
                                    <div>
                                        <label className="block text-[10px] text-gray-400 mb-1">{t('倍率（加价）', 'Multiplier (Markup)')}</label>
                                        <input 
                                            type="number"
                                            step="0.1" 
                                            value={markup}
                                            className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                            onChange={(e) => setMarkup(e.target.value)}
                                        />
                                        <p className="text-[9px] text-gray-600 mt-1">{t('例如：2.0 = 2倍成本', 'e.g. 2.0 = 2x Cost')}</p>
                                    </div>
                                    <div>
                                        <label className="block text-[10px] text-gray-400 mb-1">{t('汇率（￥1=积分）', 'Exchange (￥1=Credits)')}</label>
                                        <input 
                                            type="number" 
                                            value={exchangeRate}
                                            className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                            onChange={(e) => setExchangeRate(parseFloat(e.target.value) || 10)}
                                        />
                                    </div>
                                </div>
                                <div className="text-[10px] text-gray-500 bg-white/5 p-2 rounded">
                                    <div className="flex justify-between items-center mb-1">
                                        <span>{t('计算公式：', 'Calculation:')}</span>
                                        <span className="font-mono text-xs text-white">
                                           Price × {exchangeRate} × {markup}x
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center border-t border-white/10 pt-1">
                                        <span className="text-yellow-500 font-bold">{t('最终成本：', 'Final Cost:')}</span>
                                        <span className="font-mono text-yellow-400 font-bold text-sm">
                                            {isTokenUnitType(ruleForm.unit_type) ? (
                                                <span>
                                                    In: {Math.ceil((parseFloat(calcPriceInput)||0) * exchangeRate * markup)} / 
                                                    Out: {Math.ceil((parseFloat(calcPriceOutput)||0) * exchangeRate * markup)}
                                                </span>
                                            ) : (
                                                <span>{Math.ceil((parseFloat(calcPriceUSD) || 0) * exchangeRate * markup)} {t('积分', 'Credits')}</span>
                                            )}
                                        </span>
                                    </div>
                                    <div className="text-[9px] text-gray-600 mt-1 text-right">
                                        Per {ruleForm.unit_type.replace('per_', '').replace('_', ' ')}
                                    </div>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm text-gray-400 mb-1">
                                    {isTokenUnitType(ruleForm.unit_type) ? t('成本（积分：输入 / 输出）', 'Cost (Credits: Input / Output)') : t('成本（积分）', 'Cost (Credits)')}
                                </label>
                                {isTokenUnitType(ruleForm.unit_type) ? (
                                     <div className="grid grid-cols-2 gap-2">
                                        <div>
                                            <span className="text-[10px] text-gray-500">{t(`输入（每 ${tokenUnitLabel(ruleForm.unit_type)}）`, `Input (per ${tokenUnitLabel(ruleForm.unit_type)})`)}</span>
                                            <input 
                                                type="number" 
                                                className="w-full bg-gray-800 border border-gray-700 rounded p-2 font-mono text-yellow-400 font-bold"
                                                value={ruleForm.cost_input || 0}
                                                onChange={e => setRuleForm({...ruleForm, cost_input: parseInt(e.target.value) || 0})}
                                            />
                                        </div>
                                        <div>
                                            <span className="text-[10px] text-gray-500">{t(`输出（每 ${tokenUnitLabel(ruleForm.unit_type)}）`, `Output (per ${tokenUnitLabel(ruleForm.unit_type)})`)}</span>
                                            <input 
                                                type="number" 
                                                className="w-full bg-gray-800 border border-gray-700 rounded p-2 font-mono text-yellow-400 font-bold"
                                                value={ruleForm.cost_output || 0}
                                                onChange={e => setRuleForm({...ruleForm, cost_output: parseInt(e.target.value) || 0})}
                                            />
                                        </div>
                                     </div>
                                ) : (
                                    <input 
                                        type="number" 
                                        className="w-full bg-gray-800 border border-gray-700 rounded p-2 font-mono text-yellow-400 font-bold"
                                        value={ruleForm.cost}
                                        onChange={e => setRuleForm({...ruleForm, cost: parseInt(e.target.value)})}
                                    />
                                )}
                            </div>
                            <div className="flex justify-end gap-2 mt-6">
                                <button onClick={() => setIsRuleModalOpen(false)} className="px-4 py-2 hover:bg-gray-800 rounded">{t('取消', 'Cancel')}</button>
                                <button onClick={handleSaveRule} className="px-4 py-2 bg-primary hover:bg-primary/90 text-black font-bold rounded">{t('保存', 'Save')}</button>
                            </div>
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
            
        </div>
    );
};

export default UserAdmin;

