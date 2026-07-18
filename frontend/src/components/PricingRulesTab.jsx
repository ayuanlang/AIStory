import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Save } from 'lucide-react';
import { getFunctionApiConfigs, getSystemSettingsManage, updateSystemSettingManage } from '../services/api';
import { getUiLang, tUI } from '../lib/uiLang';

const FUNCTION_LABELS = {
    generate_subjects: '文生文 (角色/道具/环境文本)',
    generate_subjects_t2i: '文生图 (角色/道具/环境)',
    generate_subjects_i2i: '图生图 (角色/道具/环境)',
    generate_cover: '生成封面',
    generate_shot_images: '生成分镜图片',
    generate_videos: '生成视频',
    script_analysis: '剧本分析',
    ai_assistant: 'AI Assistant',
    ai_shot: 'AI生成分镜(脚本)',
};

const CATEGORY_ORDER = ['LLM', 'Vision', 'Tools', 'Image', 'Video', 'Voice', 'Music'];

const BILLING_UNIT_OPTIONS = [
    'per_call',
    'per_second',
    'per_minute',
    'per_token',
    'per_1k_tokens',
    'per_million_tokens',
];

const TOKEN_UNIT_TYPES = new Set(['per_token', 'per_1k_tokens', 'per_million_tokens']);

const UNIT_TYPE_LABELS = {
    per_call: '按次',
    per_second: '按秒',
    per_minute: '按分钟',
    per_token: '按 Token',
    per_1k_tokens: '按千 Token',
    per_million_tokens: '按百万 Token',
};

const DEFAULT_CHARGE_MULTIPLIER = 2;

const normalizeUnitType = (value) => {
    const unit = String(value || 'per_call').trim() || 'per_call';
    return BILLING_UNIT_OPTIONS.includes(unit) ? unit : 'per_call';
};

const isTokenUnitType = (unitType) => TOKEN_UNIT_TYPES.has(normalizeUnitType(unitType));

const toNonNegativeFloatString = (value, fallback = '0') => {
    if (value === null || value === undefined || value === '') return fallback;
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) return fallback;
    return String(parsed);
};

const toChargeMultiplier = (value, fallback = DEFAULT_CHARGE_MULTIPLIER) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) return fallback;
    return parsed;
};

const toNullableSupplierPrice = (value) => {
    const text = String(value ?? '').trim();
    if (!text) return null;
    const parsed = Number(text);
    if (!Number.isFinite(parsed) || parsed < 0) return null;
    return parsed;
};

const supplierCnyToBaseCredits = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return Math.ceil(parsed * 100);
};

const applyOddsToBaseCredits = (baseCredits, odds) => {
    const base = Number(baseCredits);
    const multiplier = toChargeMultiplier(odds, DEFAULT_CHARGE_MULTIPLIER);
    if (!Number.isFinite(base) || base < 0) return 0;
    if (multiplier <= 0) return base;
    return Math.ceil(base * multiplier);
};

const deriveSupplierPriceFromCredits = (credits) => {
    const parsed = Number(credits);
    if (!Number.isFinite(parsed) || parsed <= 0) return '0';
    return String(parsed / 100);
};

const buildDraftFromApi = (api) => ({
    billing_unit_type: normalizeUnitType(api?.billing_unit_type),
    supplier_price: toNonNegativeFloatString(
        api?.supplier_price ?? deriveSupplierPriceFromCredits(api?.billing_cost),
        '0',
    ),
    supplier_price_input: toNonNegativeFloatString(
        api?.supplier_price_input ?? deriveSupplierPriceFromCredits(api?.billing_cost_input),
        '0',
    ),
    supplier_price_output: toNonNegativeFloatString(
        api?.supplier_price_output ?? deriveSupplierPriceFromCredits(api?.billing_cost_output),
        '0',
    ),
    charge_multiplier: String(toChargeMultiplier(api?.charge_multiplier, DEFAULT_CHARGE_MULTIPLIER)),
});

const computePreview = (draft) => {
    const odds = toChargeMultiplier(draft?.charge_multiplier, DEFAULT_CHARGE_MULTIPLIER);
    const tokenUnit = isTokenUnitType(draft?.billing_unit_type);

    if (tokenUnit) {
        const baseInput = supplierCnyToBaseCredits(draft?.supplier_price_input);
        const baseOutput = supplierCnyToBaseCredits(draft?.supplier_price_output);
        return {
            tokenUnit: true,
            odds,
            baseInput,
            baseOutput,
            userInput: applyOddsToBaseCredits(baseInput, odds),
            userOutput: applyOddsToBaseCredits(baseOutput, odds),
        };
    }

    const base = supplierCnyToBaseCredits(draft?.supplier_price);
    return {
        tokenUnit: false,
        odds,
        base,
        user: applyOddsToBaseCredits(base, odds),
    };
};

const isDraftDirty = (draft, api) => {
    if (!draft || !api) return false;
    const baseline = buildDraftFromApi(api);
    return (
        draft.billing_unit_type !== baseline.billing_unit_type
        || String(toNullableSupplierPrice(draft.supplier_price) ?? '') !== String(toNullableSupplierPrice(baseline.supplier_price) ?? '')
        || String(toNullableSupplierPrice(draft.supplier_price_input) ?? '') !== String(toNullableSupplierPrice(baseline.supplier_price_input) ?? '')
        || String(toNullableSupplierPrice(draft.supplier_price_output) ?? '') !== String(toNullableSupplierPrice(baseline.supplier_price_output) ?? '')
        || String(toChargeMultiplier(draft.charge_multiplier)) !== String(toChargeMultiplier(baseline.charge_multiplier))
    );
};

export default function PricingRulesTab() {
    const lang = getUiLang();
    const t = (zh, en) => tUI(lang, zh, en);

    const [loading, setLoading] = useState(true);
    const [systemApis, setSystemApis] = useState([]);
    const [functionUsages, setFunctionUsages] = useState({});
    const [drafts, setDrafts] = useState({});
    const [savingIds, setSavingIds] = useState({});
    const [categoryFilter, setCategoryFilter] = useState('all');
    const [keyword, setKeyword] = useState('');
    const [toast, setToast] = useState('');

    const showToast = (text) => {
        setToast(String(text || '').trim());
        setTimeout(() => setToast(''), 2000);
    };

    const fetchData = async () => {
        setLoading(true);
        try {
            const [configsData, sysApis] = await Promise.all([
                getFunctionApiConfigs(),
                getSystemSettingsManage(),
            ]);

            const apiMap = new Map();
            (Array.isArray(sysApis) ? sysApis : []).forEach((api) => {
                const id = Number(api?.id || 0);
                if (id > 0) apiMap.set(id, api);
            });

            const usageMap = {};
            const usedIds = new Set();
            (Array.isArray(configsData) ? configsData : []).forEach((cfg) => {
                const funcName = String(cfg?.function_name || '').trim();
                const items = Array.isArray(cfg?.api_settings) ? cfg.api_settings : [];
                items.forEach((item) => {
                    const id = Number(item?.system_api_id || 0);
                    if (id <= 0 || !apiMap.has(id)) return;
                    usedIds.add(id);
                    if (!usageMap[id]) usageMap[id] = [];
                    if (funcName && !usageMap[id].includes(funcName)) {
                        usageMap[id].push(funcName);
                    }
                });
            });

            const rows = Array.from(usedIds)
                .map((id) => apiMap.get(id))
                .filter(Boolean)
                .sort((a, b) => {
                    const ca = String(a?.category || '');
                    const cb = String(b?.category || '');
                    if (ca !== cb) return ca.localeCompare(cb);
                    const pa = String(a?.provider || '');
                    const pb = String(b?.provider || '');
                    if (pa !== pb) return pa.localeCompare(pb);
                    return String(a?.model || '').localeCompare(String(b?.model || ''));
                });

            const nextDrafts = {};
            rows.forEach((api) => {
                nextDrafts[String(api.id)] = buildDraftFromApi(api);
            });

            setSystemApis(rows);
            setFunctionUsages(usageMap);
            setDrafts(nextDrafts);
        } catch (error) {
            console.error('Failed to load pricing rules from function API configs', error);
            alert(t('加载失败', 'Failed to load'));
            setSystemApis([]);
            setFunctionUsages({});
            setDrafts({});
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const categoryOptions = useMemo(() => {
        const set = new Set(systemApis.map((row) => String(row?.category || '').trim()).filter(Boolean));
        return Array.from(set).sort((a, b) => {
            const ia = CATEGORY_ORDER.indexOf(a);
            const ib = CATEGORY_ORDER.indexOf(b);
            if (ia === -1 && ib === -1) return a.localeCompare(b);
            if (ia === -1) return 1;
            if (ib === -1) return -1;
            return ia - ib;
        });
    }, [systemApis]);

    const filteredApis = useMemo(() => {
        const kw = String(keyword || '').trim().toLowerCase();
        return systemApis.filter((api) => {
            const category = String(api?.category || '').trim();
            if (categoryFilter !== 'all' && category !== categoryFilter) return false;
            if (!kw) return true;
            const usage = (functionUsages[Number(api.id)] || [])
                .map((name) => FUNCTION_LABELS[name] || name)
                .join(' ');
            const haystack = [
                api?.id,
                api?.provider,
                api?.model,
                api?.base_model,
                api?.name,
                category,
                usage,
            ].join(' ').toLowerCase();
            return haystack.includes(kw);
        });
    }, [systemApis, categoryFilter, keyword, functionUsages]);

    const groupedApis = useMemo(() => {
        const groups = new Map();
        filteredApis.forEach((api) => {
            const category = String(api?.category || '').trim() || 'Other';
            if (!groups.has(category)) groups.set(category, []);
            groups.get(category).push(api);
        });

        return Array.from(groups.entries()).sort(([a], [b]) => {
            const ia = CATEGORY_ORDER.indexOf(a);
            const ib = CATEGORY_ORDER.indexOf(b);
            if (ia === -1 && ib === -1) return a.localeCompare(b);
            if (ia === -1) return 1;
            if (ib === -1) return -1;
            return ia - ib;
        });
    }, [filteredApis]);

    const updateDraft = (apiId, field, value) => {
        const key = String(apiId);
        setDrafts((prev) => ({
            ...prev,
            [key]: {
                ...(prev[key] || buildDraftFromApi({})),
                [field]: value,
            },
        }));
    };

    const handleSave = async (api) => {
        const id = Number(api?.id || 0);
        if (id <= 0) return;
        const draft = drafts[String(id)] || buildDraftFromApi(api);
        if (!isDraftDirty(draft, api)) {
            showToast(t('无变更', 'No changes'));
            return;
        }

        const tokenUnit = isTokenUnitType(draft.billing_unit_type);
        const payload = {
            billing_unit_type: normalizeUnitType(draft.billing_unit_type),
            supplier_currency: 'CNY',
            supplier_price_basis: 'money',
            charge_multiplier: toChargeMultiplier(draft.charge_multiplier),
        };

        if (tokenUnit) {
            payload.supplier_price_input = toNullableSupplierPrice(draft.supplier_price_input);
            payload.supplier_price_output = toNullableSupplierPrice(draft.supplier_price_output);
            payload.supplier_price = null;
        } else {
            payload.supplier_price = toNullableSupplierPrice(draft.supplier_price);
            payload.supplier_price_input = null;
            payload.supplier_price_output = null;
        }

        setSavingIds((prev) => ({ ...prev, [id]: true }));
        try {
            const updated = await updateSystemSettingManage(id, payload);

            setSystemApis((prev) => prev.map((row) => (
                Number(row.id) === id
                    ? {
                        ...row,
                        ...updated,
                        billing_unit_type: updated?.billing_unit_type ?? normalizeUnitType(draft.billing_unit_type),
                        supplier_price: updated?.supplier_price ?? payload.supplier_price,
                        supplier_price_input: updated?.supplier_price_input ?? payload.supplier_price_input,
                        supplier_price_output: updated?.supplier_price_output ?? payload.supplier_price_output,
                        charge_multiplier: updated?.charge_multiplier ?? payload.charge_multiplier,
                        billing_cost: updated?.billing_cost ?? row.billing_cost,
                        billing_cost_input: updated?.billing_cost_input ?? row.billing_cost_input,
                        billing_cost_output: updated?.billing_cost_output ?? row.billing_cost_output,
                    }
                    : row
            )));
            setDrafts((prev) => ({
                ...prev,
                [String(id)]: buildDraftFromApi({
                    billing_unit_type: updated?.billing_unit_type ?? draft.billing_unit_type,
                    supplier_price: updated?.supplier_price ?? payload.supplier_price,
                    supplier_price_input: updated?.supplier_price_input ?? payload.supplier_price_input,
                    supplier_price_output: updated?.supplier_price_output ?? payload.supplier_price_output,
                    charge_multiplier: updated?.charge_multiplier ?? payload.charge_multiplier,
                    billing_cost: updated?.billing_cost,
                    billing_cost_input: updated?.billing_cost_input,
                    billing_cost_output: updated?.billing_cost_output,
                }),
            }));
            showToast(t('已保存计费规则', 'Pricing rules saved'));
        } catch (error) {
            console.error('Failed to save pricing rules', error);
            alert(error?.response?.data?.detail || error?.message || t('保存失败', 'Save failed'));
        } finally {
            setSavingIds((prev) => ({ ...prev, [id]: false }));
        }
    };

    const renderPreview = (draft, { videoTokenTier = false } = {}) => {
        const preview = computePreview(draft);
        if (preview.tokenUnit) {
            const inputLabel = videoTokenTier
                ? t('含视频输入', 'With video input')
                : t('输入', 'Input');
            const outputLabel = videoTokenTier
                ? t('不含视频输入', 'Without video input')
                : t('输出', 'Output');
            return (
                <div className="space-y-1 text-[11px] leading-relaxed">
                    <div className="text-gray-400">
                        {inputLabel}: {t('基础', 'Base')} {preview.baseInput} → {t('用户', 'User')} {preview.userInput}
                        {videoTokenTier ? <span className="text-gray-500"> /MTok</span> : null}
                    </div>
                    <div className="text-gray-400">
                        {outputLabel}: {t('基础', 'Base')} {preview.baseOutput} → {t('用户', 'User')} {preview.userOutput}
                        {videoTokenTier ? <span className="text-gray-500"> /MTok</span> : null}
                    </div>
                    <div className="text-sky-300/90">
                        {t('赔率', 'Odds')} ×{preview.odds.toFixed(2)}
                    </div>
                </div>
            );
        }

        return (
            <div className="space-y-1 text-[11px] leading-relaxed">
                <div className="text-gray-300">
                    {t('基础积分', 'Base credits')}: <span className="text-white font-medium">{preview.base}</span>
                </div>
                <div className="text-sky-200">
                    {t('用户积分', 'User credits')}: <span className="font-medium">{preview.user}</span>
                </div>
                <div className="text-sky-300/90">
                    {t('赔率', 'Odds')} ×{preview.odds.toFixed(2)}
                </div>
            </div>
        );
    };

    if (loading) {
        return <div className="text-gray-400 p-4">{t('加载中...', 'Loading...')}</div>;
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-bold">{t('计费规则（供应商价 + 赔率）', 'Pricing Rules (Supplier + Odds)')}</h3>
                    <p className="text-xs text-gray-400 mt-1">
                        {t(
                            '根据「功能 API 配置」中已绑定的 API 去重列出，按类型分组。录入供应商 CNY 单价与赔率，实时预览基础/用户积分。',
                            'Deduplicated APIs from Function API configs, grouped by category. Enter supplier CNY prices and charge multiplier with live credit preview.',
                        )}
                    </p>
                    <p className="text-[11px] text-gray-500 mt-1">
                        {t(
                            '基础积分 = ceil(供应商价 × 100)；用户积分 = ceil(基础 × 赔率)',
                            'Base credits = ceil(supplier CNY × 100); user credits = ceil(base × odds)',
                        )}
                    </p>
                </div>
                <button
                    type="button"
                    onClick={fetchData}
                    className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded flex items-center gap-2 text-sm"
                >
                    <RefreshCw size={16} /> {t('刷新', 'Refresh')}
                </button>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
                <span>{t('共', 'Total')} {systemApis.length} {t('个 API', 'APIs')}</span>
                <span>·</span>
                <span>{t('当前显示', 'Showing')} {filteredApis.length}</span>
            </div>

            {toast && (
                <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                    {toast}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="bg-black/40 border border-gray-700 rounded p-2 text-xs"
                >
                    <option value="all">{t('全部类型', 'All Categories')}</option>
                    {categoryOptions.map((value) => (
                        <option key={`pricing-category-${value}`} value={value}>{value}</option>
                    ))}
                </select>
                <input
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder={t('搜索 provider / model / 功能', 'Search provider / model / function')}
                    className="md:col-span-2 bg-black/40 border border-gray-700 rounded p-2 text-xs"
                />
            </div>

            {groupedApis.length === 0 ? (
                <div className="rounded border border-white/10 bg-black/20 px-4 py-6 text-sm text-gray-400">
                    {t('功能 API 配置中暂无可用的 System API。', 'No System APIs found in Function API configs.')}
                </div>
            ) : (
                groupedApis.map(([category, rows]) => {
                    const isVideoCategory = String(category || '').trim() === 'Video';
                    return (
                    <div key={`pricing-group-${category}`} className="border border-white/10 rounded-lg bg-black/20 overflow-hidden">
                        <div className="flex items-center justify-between gap-2 px-4 py-2.5 bg-white/5 border-b border-white/10">
                            <div>
                                <div className="font-semibold text-sky-200 text-sm">{category}</div>
                                {isVideoCategory ? (
                                    <div className="text-[11px] text-gray-500 mt-0.5">
                                        {t(
                                            '按百万 Token：含视频输入价 / 不含视频输入价（元/百万 tokens）',
                                            'Per million tokens: with-video / without-video rates (CNY per MTok)',
                                        )}
                                    </div>
                                ) : null}
                            </div>
                            <div className="text-xs text-gray-400">{rows.length} {t('个', 'items')}</div>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full text-xs min-w-[1180px]">
                                <thead className="text-gray-400">
                                    <tr>
                                        <th className="text-left p-2.5">ID</th>
                                        <th className="text-left p-2.5">Provider</th>
                                        <th className="text-left p-2.5">Model</th>
                                        <th className="text-left p-2.5">{t('关联功能', 'Functions')}</th>
                                        <th className="text-left p-2.5">{t('计费方式', 'Billing Unit')}</th>
                                        <th className="text-left p-2.5">{t('供应商价 (CNY)', 'Supplier (CNY)')}</th>
                                        <th className="text-left p-2.5">
                                            {isVideoCategory
                                                ? t('含视频输入 (元/百万Token)', 'With video input (CNY/MTok)')
                                                : t('输入价 (CNY)', 'Input (CNY)')}
                                        </th>
                                        <th className="text-left p-2.5">
                                            {isVideoCategory
                                                ? t('不含视频输入 (元/百万Token)', 'Without video input (CNY/MTok)')
                                                : t('输出价 (CNY)', 'Output (CNY)')}
                                        </th>
                                        <th className="text-left p-2.5">{t('赔率', 'Odds')}</th>
                                        <th className="text-left p-2.5">{t('积分预览', 'Credit Preview')}</th>
                                        <th className="text-left p-2.5">{t('操作', 'Actions')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((api) => {
                                        const id = Number(api.id);
                                        const draft = drafts[String(id)] || buildDraftFromApi(api);
                                        const tokenUnit = isTokenUnitType(draft.billing_unit_type);
                                        const dirty = isDraftDirty(draft, api);
                                        const saving = !!savingIds[id];
                                        const usages = (functionUsages[id] || []).map((name) => FUNCTION_LABELS[name] || name);
                                        return (
                                            <tr key={`pricing-api-${id}`} className="border-t border-white/10 align-top">
                                                <td className="p-2.5 text-gray-300">{id}</td>
                                                <td className="p-2.5">{api.provider || '-'}</td>
                                                <td className="p-2.5">
                                                    <div className="text-white">{api.model || '-'}</div>
                                                    {api.base_model ? (
                                                        <div className="text-[11px] text-gray-500 mt-0.5">{api.base_model}</div>
                                                    ) : null}
                                                </td>
                                                <td className="p-2.5 max-w-[240px]">
                                                    <div className="flex flex-wrap gap-1">
                                                        {usages.length > 0 ? usages.map((label) => (
                                                            <span key={`${id}-${label}`} className="rounded bg-white/5 px-1.5 py-0.5 text-[11px] text-gray-300">
                                                                {label}
                                                            </span>
                                                        )) : (
                                                            <span className="text-gray-500">-</span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="p-2.5">
                                                    <select
                                                        value={draft.billing_unit_type}
                                                        onChange={(e) => updateDraft(id, 'billing_unit_type', e.target.value)}
                                                        className="w-full min-w-[140px] bg-black/40 border border-gray-700 rounded p-1.5 text-xs"
                                                    >
                                                        {BILLING_UNIT_OPTIONS.map((unit) => (
                                                            <option key={unit} value={unit}>
                                                                {UNIT_TYPE_LABELS[unit] || unit} ({unit})
                                                            </option>
                                                        ))}
                                                    </select>
                                                </td>
                                                <td className="p-2.5">
                                                    {tokenUnit ? (
                                                        <span className="text-gray-500">—</span>
                                                    ) : (
                                                        <input
                                                            type="number"
                                                            min="0"
                                                            step="0.000001"
                                                            value={draft.supplier_price}
                                                            onChange={(e) => updateDraft(id, 'supplier_price', e.target.value)}
                                                            className="w-28 bg-black/40 border border-gray-700 rounded p-1.5 text-xs"
                                                        />
                                                    )}
                                                </td>
                                                <td className="p-2.5">
                                                    {tokenUnit ? (
                                                        <input
                                                            type="number"
                                                            min="0"
                                                            step="0.000001"
                                                            value={draft.supplier_price_input}
                                                            onChange={(e) => updateDraft(id, 'supplier_price_input', e.target.value)}
                                                            className="w-28 bg-black/40 border border-gray-700 rounded p-1.5 text-xs"
                                                        />
                                                    ) : (
                                                        <span className="text-gray-500">—</span>
                                                    )}
                                                </td>
                                                <td className="p-2.5">
                                                    {tokenUnit ? (
                                                        <input
                                                            type="number"
                                                            min="0"
                                                            step="0.000001"
                                                            value={draft.supplier_price_output}
                                                            onChange={(e) => updateDraft(id, 'supplier_price_output', e.target.value)}
                                                            className="w-28 bg-black/40 border border-gray-700 rounded p-1.5 text-xs"
                                                        />
                                                    ) : (
                                                        <span className="text-gray-500">—</span>
                                                    )}
                                                </td>
                                                <td className="p-2.5">
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        step="0.01"
                                                        value={draft.charge_multiplier}
                                                        onChange={(e) => updateDraft(id, 'charge_multiplier', e.target.value)}
                                                        className="w-20 bg-black/40 border border-gray-700 rounded p-1.5 text-xs"
                                                        title={t('赔率 (charge_multiplier)', 'Odds (charge_multiplier)')}
                                                    />
                                                </td>
                                                <td className="p-2.5 min-w-[160px]">
                                                    {renderPreview(draft, { videoTokenTier: isVideoCategory && tokenUnit })}
                                                </td>
                                                <td className="p-2.5">
                                                    <button
                                                        type="button"
                                                        onClick={() => handleSave(api)}
                                                        disabled={!dirty || saving}
                                                        className="px-2.5 py-1.5 rounded text-xs font-semibold flex items-center gap-1 disabled:opacity-40 bg-sky-600 hover:bg-sky-500 text-white"
                                                    >
                                                        {saving ? <RefreshCw size={12} className="animate-spin" /> : <Save size={12} />}
                                                        {saving ? t('保存中', 'Saving') : t('保存', 'Save')}
                                                    </button>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    );
                })
            )}
        </div>
    );
}
