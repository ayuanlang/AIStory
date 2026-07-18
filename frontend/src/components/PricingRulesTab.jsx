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

const VIDEO_RESOLUTION_TIERS = ['480p', '720p', '1080p', '4k'];

const DEFAULT_SEEDANCE_RESOLUTION_RATES = {
    '480p': { with_video_input: '28', without_video_input: '46' },
    '720p': { with_video_input: '28', without_video_input: '46' },
    '1080p': { with_video_input: '31', without_video_input: '51' },
    '4k': { with_video_input: '16', without_video_input: '26' },
};

// KIE Seedance 2: CNY / second
// FX: ~200 KIE credits / 1 USD, USD:CNY = 1:7 => 1 KIE = 0.035 CNY
const KIE_CREDIT_TO_CNY = 7 / 200;
const DEFAULT_KIE_SEEDANCE_SECOND_RATES_KIE = {
    '480p': { with_video_input: 11.5, without_video_input: 19 },
    '720p': { with_video_input: 25, without_video_input: 41 },
    '1080p': { with_video_input: 62, without_video_input: 102 },
    '4k': { with_video_input: 128, without_video_input: 208 },
};
const DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES = Object.fromEntries(
    Object.entries(DEFAULT_KIE_SEEDANCE_SECOND_RATES_KIE).map(([tier, row]) => ([
        tier,
        {
            with_video_input: String(Number((row.with_video_input * KIE_CREDIT_TO_CNY).toFixed(6))),
            without_video_input: String(Number((row.without_video_input * KIE_CREDIT_TO_CNY).toFixed(6))),
        },
    ])),
);
// alias used by fill button / legacy references
const DEFAULT_KIE_SEEDANCE_SECOND_RATES = DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES;


const kieCreditRatesToCnyRates = (raw) => {
    const src = (raw && typeof raw === 'object') ? raw : {};
    const out = {};
    VIDEO_RESOLUTION_TIERS.forEach((tier) => {
        const row = (src[tier] && typeof src[tier] === 'object') ? src[tier] : {};
        const withVal = row.with_video_input ?? row.with;
        const withoutVal = row.without_video_input ?? row.without;
        const withN = withVal === '' || withVal == null ? null : Number(withVal);
        const withoutN = withoutVal === '' || withoutVal == null ? null : Number(withoutVal);
        out[tier] = {
            with_video_input: Number.isFinite(withN) ? String(Number((withN * KIE_CREDIT_TO_CNY).toFixed(6))) : '',
            without_video_input: Number.isFinite(withoutN) ? String(Number((withoutN * KIE_CREDIT_TO_CNY).toFixed(6))) : '',
        };
    });
    return out;
};

const hasAnyRateValue = (rates) => {
    if (!rates || typeof rates !== 'object') return false;
    return Object.values(rates).some((row) => {
        if (!row || typeof row !== 'object') return false;
        return Object.values(row).some((v) => v != null && String(v).trim() !== '');
    });
};


const SPARKVIDEO_RESOLUTION_TIERS = ['480p', '720p', '1080p_native', '4k_native', '1080p', '2k', '4k'];

// RunningHub SparkVideo 2.0: CNY / second
const DEFAULT_SPARKVIDEO_SECOND_CNY_RATES = {
    '480p': { without_video_input: '0.6', with_video_input: '0.4' },
    '720p': { without_video_input: '1.2', with_video_input: '0.8' },
    '1080p_native': { without_video_input: '3', with_video_input: '2' },
    '4k_native': { without_video_input: '6', with_video_input: '4' },
    '1080p': { without_video_input: '1.48', with_video_base: '0.8', with_video_addon: '0.28', pricing_kind: 'upscale' },
    '2k': { without_video_input: '1.62', with_video_base: '0.8', with_video_addon: '0.42', pricing_kind: 'upscale' },
    '4k': { without_video_input: '1.83', with_video_base: '0.8', with_video_addon: '0.63', pricing_kind: 'upscale' },
};

const DEFAULT_SPARKVIDEO_MIN_BILLABLE_BY_OUTPUT = {
    4: 7, 5: 9, 6: 10, 7: 12, 8: 14, 9: 15, 10: 17, 11: 19, 12: 20, 13: 22, 14: 24, 15: 25,
};

const normalizeSparkvideoCnyRates = (raw) => {
    const src = (raw && typeof raw === 'object') ? raw : {};
    const out = {};
    SPARKVIDEO_RESOLUTION_TIERS.forEach((tier) => {
        const row = (src[tier] && typeof src[tier] === 'object') ? src[tier] : {};
        const next = {
            without_video_input: row.without_video_input != null && row.without_video_input !== '' ? String(row.without_video_input) : '',
            with_video_input: row.with_video_input != null && row.with_video_input !== '' ? String(row.with_video_input) : '',
            with_video_base: row.with_video_base != null && row.with_video_base !== '' ? String(row.with_video_base) : '',
            with_video_addon: row.with_video_addon != null && row.with_video_addon !== '' ? String(row.with_video_addon) : '',
            pricing_kind: row.pricing_kind ? String(row.pricing_kind) : '',
        };
        if (!next.without_video_input && !next.with_video_input && !next.with_video_base && !next.with_video_addon) {
            out[tier] = { without_video_input: '', with_video_input: '', with_video_base: '', with_video_addon: '', pricing_kind: '' };
        } else {
            out[tier] = next;
        }
    });
    return out;
};

const sparkvideoCnyRatesToPayload = (rates) => {
    const out = {};
    SPARKVIDEO_RESOLUTION_TIERS.forEach((tier) => {
        const row = rates?.[tier] || {};
        const item = {};
        const withoutN = toNullableSupplierPrice(row.without_video_input);
        const withN = toNullableSupplierPrice(row.with_video_input);
        const baseN = toNullableSupplierPrice(row.with_video_base);
        const addonN = toNullableSupplierPrice(row.with_video_addon);
        if (withoutN != null) item.without_video_input = withoutN;
        if (withN != null) item.with_video_input = withN;
        if (baseN != null) item.with_video_base = baseN;
        if (addonN != null) item.with_video_addon = addonN;
        if (row.pricing_kind) item.pricing_kind = row.pricing_kind;
        else if (baseN != null || addonN != null) item.pricing_kind = 'upscale';
        if (Object.keys(item).length) out[tier] = item;
    });
    return out;
};

const normalizeResolutionRates = (raw) => {
    const src = (raw && typeof raw === 'object') ? raw : {};
    const out = {};
    VIDEO_RESOLUTION_TIERS.forEach((tier) => {
        const row = (src[tier] && typeof src[tier] === 'object') ? src[tier] : {};
        const fallback = DEFAULT_SEEDANCE_RESOLUTION_RATES[tier] || {};
        const withVal = row.with_video_input ?? row.with ?? '';
        const withoutVal = row.without_video_input ?? row.without ?? '';
        out[tier] = {
            with_video_input: withVal === null || withVal === undefined || withVal === ''
                ? ''
                : String(withVal),
            without_video_input: withoutVal === null || withoutVal === undefined || withoutVal === ''
                ? ''
                : String(withoutVal),
        };
        // Keep empty by default; UI can "fill defaults" separately if needed.
        if (!out[tier].with_video_input && !out[tier].without_video_input) {
            out[tier] = { with_video_input: '', without_video_input: '' };
        }
        void fallback;
    });
    return out;
};

const resolutionRatesToPayload = (rates) => {
    const out = {};
    VIDEO_RESOLUTION_TIERS.forEach((tier) => {
        const row = rates?.[tier] || {};
        const withN = toNullableSupplierPrice(row.with_video_input);
        const withoutN = toNullableSupplierPrice(row.without_video_input);
        if (withN === null && withoutN === null) return;
        out[tier] = {};
        if (withN !== null) out[tier].with_video_input = withN;
        if (withoutN !== null) out[tier].without_video_input = withoutN;
    });
    return out;
};


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
    video_token_resolution_rates: normalizeResolutionRates(api?.video_token_resolution_rates),
    video_second_resolution_rates: normalizeResolutionRates({}),
    video_second_cny_resolution_rates: (() => {
        const provider = String(api?.provider || '').trim().toLowerCase();
        const model = String(api?.model || '').trim().toLowerCase();
        const isSpark = provider.includes('runninghub') || model.includes('sparkvideo');
        const existingCny = normalizeSparkvideoCnyRates(api?.video_second_cny_resolution_rates);
        if (hasAnyRateValue(existingCny)) return existingCny;
        // Legacy KIE credit/s matrix -> CNY/s for editing
        if (!isSpark && hasAnyRateValue(api?.video_second_resolution_rates)) {
            return normalizeSparkvideoCnyRates(kieCreditRatesToCnyRates(api.video_second_resolution_rates));
        }
        return existingCny;
    })(),
    video_second_min_billable_by_output: api?.video_second_min_billable_by_output || { ...DEFAULT_SPARKVIDEO_MIN_BILLABLE_BY_OUTPUT },
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
        || JSON.stringify(resolutionRatesToPayload(draft.video_token_resolution_rates))
            !== JSON.stringify(resolutionRatesToPayload(baseline.video_token_resolution_rates))
        || JSON.stringify(resolutionRatesToPayload(draft.video_second_resolution_rates))
            !== JSON.stringify(resolutionRatesToPayload(baseline.video_second_resolution_rates))
        || JSON.stringify(sparkvideoCnyRatesToPayload(draft.video_second_cny_resolution_rates))
            !== JSON.stringify(sparkvideoCnyRatesToPayload(baseline.video_second_cny_resolution_rates))
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
        if (String(api?.category || '').trim() === 'Video' && tokenUnit) {
            payload.video_token_resolution_rates = resolutionRatesToPayload(draft.video_token_resolution_rates);
        }
        if (String(api?.category || '').trim() === 'Video' && draft.billing_unit_type === 'per_second') {
            const provider = String(api?.provider || '').trim().toLowerCase();
            const model = String(api?.model || '').toLowerCase();
            const isSpark = provider.includes('runninghub') || model.includes('sparkvideo');
            // KIE / others: store CNY/s in video_second_cny_resolution_rates (money basis).
            // SparkVideo: same field + min-billable table.
            if (isSpark) {
                payload.video_second_cny_resolution_rates = sparkvideoCnyRatesToPayload(draft.video_second_cny_resolution_rates);
                payload.video_second_min_billable_by_output = draft.video_second_min_billable_by_output || DEFAULT_SPARKVIDEO_MIN_BILLABLE_BY_OUTPUT;
            } else {
                // Persist only the common 480p/720p/1080p/4k CNY tiers for KIE Seedance.
                const cnyPayload = {};
                VIDEO_RESOLUTION_TIERS.forEach((tier) => {
                    const row = (draft.video_second_cny_resolution_rates || {})[tier] || {};
                    const withN = toNullableSupplierPrice(row.with_video_input);
                    const withoutN = toNullableSupplierPrice(row.without_video_input);
                    if (withN == null && withoutN == null) return;
                    cnyPayload[tier] = {};
                    if (withN != null) cnyPayload[tier].with_video_input = withN;
                    if (withoutN != null) cnyPayload[tier].without_video_input = withoutN;
                });
                payload.video_second_cny_resolution_rates = cnyPayload;
                // Clear legacy KIE-credit matrix so billing uses CNY path.
                payload.video_second_resolution_rates = {};
            }
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
                        video_token_resolution_rates: updated?.video_token_resolution_rates ?? payload.video_token_resolution_rates,
                        video_second_resolution_rates: updated?.video_second_resolution_rates ?? payload.video_second_resolution_rates,
                        video_second_cny_resolution_rates: updated?.video_second_cny_resolution_rates ?? payload.video_second_cny_resolution_rates,
                        video_second_min_billable_by_output: updated?.video_second_min_billable_by_output ?? payload.video_second_min_billable_by_output,
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
                        video_token_resolution_rates: updated?.video_token_resolution_rates ?? payload.video_token_resolution_rates,
                        video_second_resolution_rates: updated?.video_second_resolution_rates ?? payload.video_second_resolution_rates,
                        video_second_cny_resolution_rates: updated?.video_second_cny_resolution_rates ?? payload.video_second_cny_resolution_rates,
                        video_second_min_billable_by_output: updated?.video_second_min_billable_by_output ?? payload.video_second_min_billable_by_output,
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
                        {t('倍率', 'Multiplier')} ×{preview.odds.toFixed(2)}
                    </div>
                </div>
            );
        }

        if (preview.perSecondDual) {
            return (
                <div className="space-y-1 text-[11px] leading-relaxed">
                    <div className="text-gray-500">{t('预览档', 'Preview tier')} {preview.previewTier}/s</div>
                    <div className="text-gray-400">
                        {t('有视频', 'With video')}: {t('基础', 'Base')} {preview.baseWith} → {t('用户', 'User')} {preview.userWith}
                        <span className="text-gray-500"> {t('×(入+出)', '×(in+out)')}</span>
                    </div>
                    <div className="text-gray-400">
                        {t('无视频', 'No video')}: {t('基础', 'Base')} {preview.baseWithout} → {t('用户', 'User')} {preview.userWithout}
                        <span className="text-gray-500"> {t('×输出', '×output')}</span>
                    </div>
                    <div className="text-sky-300/90">
                        {t('倍率', 'Multiplier')} ×{preview.odds.toFixed(2)}
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
                    {t('倍率', 'Multiplier')} ×{preview.odds.toFixed(2)}
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
                    <h3 className="text-lg font-bold">{t('计费规则（供应商价 + 倍率）', 'Pricing Rules (Supplier + Multiplier)')}</h3>
                    <p className="text-xs text-gray-400 mt-1">
                        {t(
                            '根据「功能 API 配置」中已绑定的 API 去重列出，按类型分组。录入供应商 CNY 单价与倍率，实时预览基础/用户积分。',
                            'Deduplicated APIs from Function API configs, grouped by category. Enter supplier CNY prices and charge multiplier with live credit preview.',
                        )}
                    </p>
                    <p className="text-[11px] text-gray-500 mt-1">
                        {t(
                            '基础积分 = ceil(供应商价 × 100)；用户积分 = ceil(基础 × 倍率)',
                            'Base credits = ceil(supplier CNY × 100); user credits = ceil(base × multiplier)',
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
                                                'Token 计费：Seedance 分档（CNY/MTok）；按秒：KIE=CNY/秒（无视频×输出 / 有视频×输入+输出）；SparkVideo=CNY/秒+最低时长',
                                                'Token: Seedance (CNY/MTok); Per-second: KIE CNY/s (no-video×output / with-video×input+output); SparkVideo CNY/s + min duration',
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
                                        <th className="text-left p-2.5">{t('倍率', 'Multiplier')}</th>
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
                                                        title={t('倍率 (charge_multiplier)', 'Multiplier (charge_multiplier)')}
                                                    />
                                                </td>
                                                <td className="p-2.5 min-w-[160px]">
                                                    {renderPreview(draft, { videoTokenTier: isVideoCategory && tokenUnit })}
                                                    {isVideoCategory && tokenUnit ? (
                                                        <div className="mt-2 space-y-1">
                                                            <div className="text-[10px] text-gray-500">{t('分辨率单价 (元/百万Token)', 'Resolution rates (CNY/MTok)')}</div>
                                                            <div className="grid grid-cols-1 gap-1">
                                                                {VIDEO_RESOLUTION_TIERS.map((tier) => {
                                                                    const row = (draft.video_token_resolution_rates || {})[tier] || {};
                                                                    return (
                                                                        <div key={`${id}-${tier}`} className="flex items-center gap-1">
                                                                            <span className="w-12 text-[10px] text-sky-200">{tier}</span>
                                                                            <input
                                                                                type="number"
                                                                                min="0"
                                                                                step="0.000001"
                                                                                placeholder={t('含输入', 'With')}
                                                                                value={row.with_video_input ?? ''}
                                                                                onChange={(e) => {
                                                                                    const value = e.target.value;
                                                                                    setDrafts((prev) => {
                                                                                        const key = String(id);
                                                                                        const cur = prev[key] || buildDraftFromApi(api);
                                                                                        const rates = { ...(cur.video_token_resolution_rates || normalizeResolutionRates({})) };
                                                                                        rates[tier] = { ...(rates[tier] || {}), with_video_input: value };
                                                                                        return { ...prev, [key]: { ...cur, video_token_resolution_rates: rates } };
                                                                                    });
                                                                                }}
                                                                                className="w-16 bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                title={t('含视频输入', 'With video input')}
                                                                            />
                                                                            <input
                                                                                type="number"
                                                                                min="0"
                                                                                step="0.000001"
                                                                                placeholder={t('不含', 'W/O')}
                                                                                value={row.without_video_input ?? ''}
                                                                                onChange={(e) => {
                                                                                    const value = e.target.value;
                                                                                    setDrafts((prev) => {
                                                                                        const key = String(id);
                                                                                        const cur = prev[key] || buildDraftFromApi(api);
                                                                                        const rates = { ...(cur.video_token_resolution_rates || normalizeResolutionRates({})) };
                                                                                        rates[tier] = { ...(rates[tier] || {}), without_video_input: value };
                                                                                        return { ...prev, [key]: { ...cur, video_token_resolution_rates: rates } };
                                                                                    });
                                                                                }}
                                                                                className="w-16 bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                title={t('不含视频输入', 'Without video input')}
                                                                            />
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                            <button
                                                                type="button"
                                                                className="text-[10px] text-sky-300 hover:text-sky-200"
                                                                onClick={() => {
                                                                    setDrafts((prev) => {
                                                                        const key = String(id);
                                                                        const cur = prev[key] || buildDraftFromApi(api);
                                                                        const filled = {};
                                                                        VIDEO_RESOLUTION_TIERS.forEach((tier) => {
                                                                            filled[tier] = { ...DEFAULT_SEEDANCE_RESOLUTION_RATES[tier] };
                                                                        });
                                                                        return { ...prev, [key]: { ...cur, video_token_resolution_rates: filled } };
                                                                    });
                                                                }}
                                                            >
                                                                {t('填入 Seedance 参考价', 'Fill Seedance reference rates')}
                                                            </button>
                                                        </div>
                                                    ) : null}
                                                                
                                                                {isVideoCategory && draft.billing_unit_type === 'per_second' ? (
                                                                    (() => {
                                                                        const provider = String(api?.provider || '').trim().toLowerCase();
                                                                        const model = String(api?.model || '').trim().toLowerCase();
                                                                        const isSpark = provider.includes('runninghub') || model.includes('sparkvideo');
                                                                        if (isSpark) {
                                                                            return (
                                                                    <div className="mt-2 space-y-1">
                                                                        <div className="text-[10px] text-gray-500">
                                                                            {t('SparkVideo 单价（CNY/秒；放大档有参考=基础+附加）', 'SparkVideo rates (CNY/s; upscale+ref = base+addon)')}
                                                                        </div>
                                                                        <div className="grid grid-cols-1 gap-1">
                                                                            {SPARKVIDEO_RESOLUTION_TIERS.map((tier) => {
                                                                                const row = (draft.video_second_cny_resolution_rates || {})[tier] || {};
                                                                                const isUpscale = Boolean(row.with_video_base || row.with_video_addon || row.pricing_kind === 'upscale' || ['1080p', '2k', '4k'].includes(tier));
                                                                                return (
                                                                                    <div key={`${id}-${tier}-sv`} className="flex flex-wrap items-center gap-1">
                                                                                        <span className="w-20 text-[10px] text-amber-200">{tier}</span>
                                                                                        <input
                                                                                            type="number"
                                                                                            min="0"
                                                                                            step="0.01"
                                                                                            placeholder={t('无参考', 'No ref')}
                                                                                            value={row.without_video_input ?? ''}
                                                                                            onChange={(e) => {
                                                                                                const value = e.target.value;
                                                                                                setDrafts((prev) => {
                                                                                                    const key = String(id);
                                                                                                    const cur = prev[key] || buildDraftFromApi(api);
                                                                                                    const rates = { ...(cur.video_second_cny_resolution_rates || normalizeSparkvideoCnyRates({})) };
                                                                                                    rates[tier] = { ...(rates[tier] || {}), without_video_input: value };
                                                                                                    return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: rates } };
                                                                                                });
                                                                                            }}
                                                                                            className="w-14 bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                            title={t('无参考视频 CNY/秒', 'No reference video CNY/s')}
                                                                                        />
                                                                                        {isUpscale ? (
                                                                                            <>
                                                                                                <input
                                                                                                    type="number"
                                                                                                    min="0"
                                                                                                    step="0.01"
                                                                                                    placeholder={t('基础', 'Base')}
                                                                                                    value={row.with_video_base ?? ''}
                                                                                                    onChange={(e) => {
                                                                                                        const value = e.target.value;
                                                                                                        setDrafts((prev) => {
                                                                                                            const key = String(id);
                                                                                                            const cur = prev[key] || buildDraftFromApi(api);
                                                                                                            const rates = { ...(cur.video_second_cny_resolution_rates || normalizeSparkvideoCnyRates({})) };
                                                                                                            rates[tier] = { ...(rates[tier] || {}), with_video_base: value, pricing_kind: 'upscale' };
                                                                                                            return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: rates } };
                                                                                                        });
                                                                                                    }}
                                                                                                    className="w-14 bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                                    title={t('有参考基础 CNY/秒', 'With-ref base CNY/s')}
                                                                                                />
                                                                                                <input
                                                                                                    type="number"
                                                                                                    min="0"
                                                                                                    step="0.01"
                                                                                                    placeholder={t('附加', 'Addon')}
                                                                                                    value={row.with_video_addon ?? ''}
                                                                                                    onChange={(e) => {
                                                                                                        const value = e.target.value;
                                                                                                        setDrafts((prev) => {
                                                                                                            const key = String(id);
                                                                                                            const cur = prev[key] || buildDraftFromApi(api);
                                                                                                            const rates = { ...(cur.video_second_cny_resolution_rates || normalizeSparkvideoCnyRates({})) };
                                                                                                            rates[tier] = { ...(rates[tier] || {}), with_video_addon: value, pricing_kind: 'upscale' };
                                                                                                            return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: rates } };
                                                                                                        });
                                                                                                    }}
                                                                                                    className="w-14 bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                                    title={t('有参考附加 CNY/秒（×生成时长）', 'With-ref addon CNY/s (x output)')}
                                                                                                />
                                                                                            </>
                                                                                        ) : (
                                                                                            <input
                                                                                                type="number"
                                                                                                min="0"
                                                                                                step="0.01"
                                                                                                placeholder={t('有参考', 'With ref')}
                                                                                                value={row.with_video_input ?? ''}
                                                                                                onChange={(e) => {
                                                                                                    const value = e.target.value;
                                                                                                    setDrafts((prev) => {
                                                                                                        const key = String(id);
                                                                                                        const cur = prev[key] || buildDraftFromApi(api);
                                                                                                        const rates = { ...(cur.video_second_cny_resolution_rates || normalizeSparkvideoCnyRates({})) };
                                                                                                        rates[tier] = { ...(rates[tier] || {}), with_video_input: value };
                                                                                                        return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: rates } };
                                                                                                    });
                                                                                                }}
                                                                                                className="w-14 bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                                title={t('有参考视频 CNY/秒', 'With reference video CNY/s')}
                                                                                            />
                                                                                        )}
                                                                                    </div>
                                                                                );
                                                                            })}
                                                                        </div>
                                                                        <button
                                                                            type="button"
                                                                            className="text-[10px] text-amber-300 hover:text-amber-200"
                                                                            onClick={() => {
                                                                                setDrafts((prev) => {
                                                                                    const key = String(id);
                                                                                    const cur = prev[key] || buildDraftFromApi(api);
                                                                                    const filled = {};
                                                                                    SPARKVIDEO_RESOLUTION_TIERS.forEach((tier) => {
                                                                                        filled[tier] = { ...DEFAULT_SPARKVIDEO_SECOND_CNY_RATES[tier] };
                                                                                    });
                                                                                    return {
                                                                                        ...prev,
                                                                                        [key]: {
                                                                                            ...cur,
                                                                                            video_second_cny_resolution_rates: filled,
                                                                                            video_second_min_billable_by_output: { ...DEFAULT_SPARKVIDEO_MIN_BILLABLE_BY_OUTPUT },
                                                                                        },
                                                                                    };
                                                                                });
                                                                            }}
                                                                        >
                                                                            {t('填入 SparkVideo 参考价', 'Fill SparkVideo reference rates')}
                                                                        </button>
                                                                    </div>
                                                                            );
                                                                        }
                                                                        return (
                                                                    <div className="mt-2 space-y-1.5 min-w-[280px]">
                                                                        <div className="text-[10px] text-sky-200/90 leading-snug">
                                                                            {t(
                                                                                'KIE Seedance：CNY/秒（已按 200积分/$ · 汇率7 折算）',
                                                                                'KIE Seedance: CNY/s (200 credits/USD · FX 7)',
                                                                            )}
                                                                        </div>
                                                                        <div className="text-[10px] text-amber-200/80 leading-snug bg-amber-500/10 border border-amber-500/20 rounded px-1.5 py-1">
                                                                            {t(
                                                                                '计费：无视频 = 单价 × 输出时长；有视频 = 单价 × (输入时长 + 输出时长)',
                                                                                'Billing: no video = rate × output; with video = rate × (input + output)',
                                                                            )}
                                                                        </div>
                                                                        <div className="grid grid-cols-[48px_1fr_1fr] gap-1 items-center text-[10px] text-gray-500 px-0.5">
                                                                            <span>{t('档位', 'Tier')}</span>
                                                                            <span title={t('有视频输入：单价 × (输入+输出)', 'With video: rate × (input+output)')}>
                                                                                {t('有视频 ×(入+出)', 'With ×(in+out)')}
                                                                            </span>
                                                                            <span title={t('无视频输入：单价 × 输出', 'No video: rate × output')}>
                                                                                {t('无视频 ×输出', 'No-video ×out')}
                                                                            </span>
                                                                        </div>
                                                                        <div className="grid grid-cols-1 gap-1">
                                                                            {VIDEO_RESOLUTION_TIERS.map((tier) => {
                                                                                const row = (draft.video_second_cny_resolution_rates || {})[tier] || {};
                                                                                return (
                                                                                    <div key={`${id}-${tier}-s`} className="grid grid-cols-[48px_1fr_1fr] gap-1 items-center">
                                                                                        <span className="text-[10px] text-sky-200">{tier}</span>
                                                                                        <input
                                                                                            type="number"
                                                                                            min="0"
                                                                                            step="0.000001"
                                                                                            placeholder={t('有视频', 'With')}
                                                                                            value={row.with_video_input ?? ''}
                                                                                            onChange={(e) => {
                                                                                                const value = e.target.value;
                                                                                                setDrafts((prev) => {
                                                                                                    const key = String(id);
                                                                                                    const cur = prev[key] || buildDraftFromApi(api);
                                                                                                    const rates = { ...(cur.video_second_cny_resolution_rates || normalizeSparkvideoCnyRates({})) };
                                                                                                    rates[tier] = { ...(rates[tier] || {}), with_video_input: value };
                                                                                                    return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: rates } };
                                                                                                });
                                                                                            }}
                                                                                            className="w-full bg-black/40 border border-sky-800/60 rounded px-1 py-0.5 text-[10px]"
                                                                                            title={t('有视频输入单价 CNY/秒；总价=单价×(输入+输出)', 'With-video CNY/s; total=rate×(input+output)')}
                                                                                        />
                                                                                        <input
                                                                                            type="number"
                                                                                            min="0"
                                                                                            step="0.000001"
                                                                                            placeholder={t('无视频', 'No video')}
                                                                                            value={row.without_video_input ?? ''}
                                                                                            onChange={(e) => {
                                                                                                const value = e.target.value;
                                                                                                setDrafts((prev) => {
                                                                                                    const key = String(id);
                                                                                                    const cur = prev[key] || buildDraftFromApi(api);
                                                                                                    const rates = { ...(cur.video_second_cny_resolution_rates || normalizeSparkvideoCnyRates({})) };
                                                                                                    rates[tier] = { ...(rates[tier] || {}), without_video_input: value };
                                                                                                    return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: rates } };
                                                                                                });
                                                                                            }}
                                                                                            className="w-full bg-black/40 border border-gray-700 rounded px-1 py-0.5 text-[10px]"
                                                                                            title={t('无视频输入单价 CNY/秒；总价=单价×输出', 'No-video CNY/s; total=rate×output')}
                                                                                        />
                                                                                    </div>
                                                                                );
                                                                            })}
                                                                        </div>
                                                                        <button
                                                                            type="button"
                                                                            className="text-[10px] text-sky-300 hover:text-sky-200"
                                                                            onClick={() => {
                                                                                setDrafts((prev) => {
                                                                                    const key = String(id);
                                                                                    const cur = prev[key] || buildDraftFromApi(api);
                                                                                    const filled = {};
                                                                                    VIDEO_RESOLUTION_TIERS.forEach((tier) => {
                                                                                        filled[tier] = { ...DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES[tier] };
                                                                                    });
                                                                                    return { ...prev, [key]: { ...cur, video_second_cny_resolution_rates: filled } };
                                                                                });
                                                                            }}
                                                                        >
                                                                            {t('填入 KIE Seedance 参考价（CNY）', 'Fill KIE Seedance reference rates (CNY)')}
                                                                        </button>
                                                                    </div>
                                                                        )
                                                                    })()
                                                                ) : null}


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
