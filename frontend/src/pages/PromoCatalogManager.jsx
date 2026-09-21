import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Home, Loader2, Pencil, Plus, Trash2 } from 'lucide-react';
import {
    createPromoBrand,
    createPromoEnterprise,
    createPromoProduct,
    deletePromoBrand,
    deletePromoEnterprise,
    deletePromoProduct,
    fetchPromoBrands,
    fetchPromoEnterprises,
    fetchPromoProducts,
    updatePromoBrand,
    updatePromoEnterprise,
    updatePromoProduct,
} from '../services/api';
import PromoCatalogAssets from './editor/components/PromoCatalogAssets';
import { SafeImage, getFullUrl } from './editor/editorHelpers';

export const PROMO_CATALOG_FOCUS_KEY = 'promo_catalog_focus';

export function writePromoCatalogFocus(focus) {
    try {
        sessionStorage.setItem(PROMO_CATALOG_FOCUS_KEY, JSON.stringify(focus || {}));
    } catch {
        // ignore
    }
}

export function readPromoCatalogFocus() {
    try {
        const raw = sessionStorage.getItem(PROMO_CATALOG_FOCUS_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
        return null;
    }
}

export function clearPromoCatalogFocus() {
    try {
        sessionStorage.removeItem(PROMO_CATALOG_FOCUS_KEY);
    } catch {
        // ignore
    }
}

const linesToList = (value) => String(value || '').split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
const listToLines = (value) => (Array.isArray(value) ? value : []).join('\n');

const ReadValue = ({ value, empty, minHeight = '2.4rem' }) => (
    <div className="px-3 py-2 bg-black/30 rounded-lg text-sm whitespace-pre-wrap" style={{ minHeight }}>
        {value || <span className="text-white/30">{empty}</span>}
    </div>
);

const emptyProductDraft = () => ({
    name: '',
    product_info: '',
    core_selling_points: '',
    differentiation: '',
    target_user: '',
    pain_points: '',
    competitor_problem: '',
});

function ImeField({ multiline = false, value, onChange, className, ...rest }) {
    const common = {
        ...rest,
        className,
        value: value || '',
        onChange: (event) => onChange(event.target.value),
    };
    return multiline ? <textarea {...common} /> : <input {...common} />;
}

function EntityColumn({
    t,
    title,
    items,
    selectedId,
    onSelect,
    onCreate,
    onEdit,
    onDelete,
    createKind,
    creating,
    draftName,
    draftIntro,
    onDraftName,
    onDraftIntro,
    onSubmitCreate,
    onCancelCreate,
    emptyHint,
    disabled,
    busy,
}) {
    return (
        <div className="bg-black/20 border border-white/10 rounded-2xl p-4 space-y-3 min-h-[22rem]">
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-white">{title}</h3>
                <button
                    type="button"
                    disabled={disabled || busy}
                    onClick={onCreate}
                    className="px-2.5 py-1 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                >
                    <Plus className="w-3 h-3" /> {t('新建', 'New')}
                </button>
            </div>
            {creating === createKind ? (
                <div className="space-y-2">
                    <ImeField
                        className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none"
                        value={draftName}
                        onChange={onDraftName}
                        placeholder={t('名称（仅新建时填写）', 'Name (create only)')}
                        autoFocus
                    />
                    {createKind !== 'offering' ? (
                        <ImeField
                            multiline
                            className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none min-h-[4.5rem]"
                            value={draftIntro}
                            onChange={onDraftIntro}
                            placeholder={t('简介（仅新建时填写）', 'Intro (create only)')}
                        />
                    ) : null}
                    <div className="flex gap-2">
                        <button type="button" disabled={busy || !String(draftName || '').trim()} onClick={onSubmitCreate} className="px-3 py-1.5 rounded-md text-xs font-bold bg-primary text-black disabled:opacity-40">
                            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : t('创建', 'Create')}
                        </button>
                        <button type="button" onClick={onCancelCreate} className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10">
                            {t('取消', 'Cancel')}
                        </button>
                    </div>
                </div>
            ) : null}
            <div className="space-y-1 max-h-[18rem] overflow-y-auto">
                {items.length === 0 ? (
                    <div className="text-xs text-white/40 py-6">{emptyHint}</div>
                ) : items.map((item) => (
                    <div
                        key={`${createKind}-${item.id}`}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer ${String(selectedId) === String(item.id) ? 'bg-primary/20 border border-primary/40' : 'bg-white/5 hover:bg-white/10 border border-transparent'}`}
                        onClick={() => onSelect(String(item.id))}
                    >
                        <div className="flex-1 min-w-0">
                            <div className="text-sm text-white truncate">{item.name}</div>
                            {item.intro ? <div className="text-[11px] text-white/50 truncate">{item.intro}</div> : null}
                            {Array.isArray(item.asset_previews) && item.asset_previews.length > 0 ? (
                                <div className="flex items-center gap-1 mt-1">
                                    {item.asset_previews.slice(0, 4).map((preview) => {
                                        const url = preview.img_url || preview.file_url;
                                        const isVideo = String(preview.media_kind || '') === 'video';
                                        return (
                                            <div key={preview.id || preview.img_url} className="w-12 h-12 rounded overflow-hidden bg-black/40 shrink-0">
                                                {url && !isVideo ? <SafeImage src={url} alt="" className="w-full h-full object-cover" /> : null}
                                                {url && isVideo ? <video src={getFullUrl(url)} className="w-full h-full object-cover" muted /> : null}
                                            </div>
                                        );
                                    })}
                                    <span className="text-[10px] text-white/50">{t(`${Number(item.asset_count || item.asset_previews.length)} 个素材`, `${Number(item.asset_count || item.asset_previews.length)} assets`)}</span>
                                </div>
                            ) : Number(item.asset_count || 0) > 0 ? (
                                <div className="text-[10px] text-white/50 mt-1">{t(`${Number(item.asset_count)} 个素材`, `${Number(item.asset_count)} assets`)}</div>
                            ) : null}
                        </div>
                        <button
                            type="button"
                            className="p-1 text-white/40 hover:text-primary"
                            title={t('编辑', 'Edit')}
                            onClick={(e) => {
                                e.stopPropagation();
                                onSelect(String(item.id));
                                onEdit(createKind, item);
                            }}
                        >
                            <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                            type="button"
                            className="p-1 text-white/40 hover:text-red-300"
                            title={t('删除', 'Delete')}
                            onClick={(e) => {
                                e.stopPropagation();
                                onDelete(createKind === 'offering' ? 'offering' : createKind, item.id);
                            }}
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function PromoCatalogManager({ t, focus = null, onFocusConsumed, returnTo = null, onReturn }) {
    const navigate = useNavigate();
    const [enterprises, setEnterprises] = useState([]);
    const [brands, setBrands] = useState([]);
    const [products, setProducts] = useState([]);
    const [enterpriseId, setEnterpriseId] = useState(() => String(focus?.enterpriseId || ''));
    const [brandId, setBrandId] = useState(() => String(focus?.brandId || ''));
    const [productId, setProductId] = useState(() => String(focus?.productId || ''));
    const [busy, setBusy] = useState(false);
    const [creating, setCreating] = useState('');
    const [editing, setEditing] = useState('');
    const [draftName, setDraftName] = useState('');
    const [draftIntro, setDraftIntro] = useState('');
    const [productDraft, setProductDraft] = useState(emptyProductDraft);
    const appliedActionKeyRef = useRef('');

    const selectedEnterprise = useMemo(
        () => enterprises.find((item) => String(item.id) === String(enterpriseId)) || null,
        [enterprises, enterpriseId]
    );
    const selectedBrand = useMemo(
        () => brands.find((item) => String(item.id) === String(brandId)) || null,
        [brands, brandId]
    );
    const selectedProduct = useMemo(
        () => products.find((item) => String(item.id) === String(productId)) || null,
        [products, productId]
    );

    const loadEnterprises = useCallback(async () => {
        const rows = await fetchPromoEnterprises().catch(() => []);
        const list = Array.isArray(rows) ? rows : [];
        setEnterprises(list);
        setEnterpriseId((current) => {
            if (current && list.some((item) => String(item.id) === String(current))) return current;
            const withAssets = list.find((item) => Number(item.asset_count || 0) > 0 || (item.asset_previews || []).length);
            const next = withAssets || list[0];
            return next ? String(next.id) : '';
        });
    }, []);

    const loadBrands = useCallback(async (nextEnterpriseId) => {
        if (!nextEnterpriseId) {
            setBrands([]);
            return;
        }
        const rows = await fetchPromoBrands({ enterprise_id: Number(nextEnterpriseId) }).catch(() => []);
        setBrands(Array.isArray(rows) ? rows : []);
    }, []);

    const loadProducts = useCallback(async (nextBrandId) => {
        if (!nextBrandId) {
            setProducts([]);
            return;
        }
        const rows = await fetchPromoProducts({ brand_id: Number(nextBrandId) }).catch(() => []);
        setProducts(Array.isArray(rows) ? rows : []);
    }, []);

    useEffect(() => {
        loadEnterprises();
    }, [loadEnterprises]);

    useEffect(() => {
        loadBrands(enterpriseId);
    }, [enterpriseId, loadBrands]);

    useEffect(() => {
        loadProducts(brandId);
    }, [brandId, loadProducts]);

    useEffect(() => {
        const nextEnterpriseId = String(focus?.enterpriseId || '');
        const nextBrandId = String(focus?.brandId || '');
        const nextProductId = String(focus?.productId || '');
        if (nextEnterpriseId) setEnterpriseId(nextEnterpriseId);
        if (nextBrandId) setBrandId(nextBrandId);
        if (nextProductId) setProductId(nextProductId);
    }, [focus?.enterpriseId, focus?.brandId, focus?.productId, focus?.key]);

    useEffect(() => {
        const action = String(focus?.action || '').trim();
        const kind = String(focus?.kind || '').trim();
        const key = String(focus?.key || `${action}:${kind}:${focus?.enterpriseId || ''}:${focus?.brandId || ''}:${focus?.productId || ''}`);
        if (!action || !kind || appliedActionKeyRef.current === key) return;
        if (action === 'create') {
            startCreate(kind);
            appliedActionKeyRef.current = key;
            onFocusConsumed?.();
            return;
        }
        if (action !== 'edit') return;
        const item = kind === 'enterprise' ? selectedEnterprise : kind === 'brand' ? selectedBrand : selectedProduct;
        if (!item) return;
        startEdit(kind, item);
        appliedActionKeyRef.current = key;
        onFocusConsumed?.();
    }, [focus, onFocusConsumed, selectedBrand, selectedEnterprise, selectedProduct]);

    useEffect(() => {
        if (editing === 'offering' && selectedProduct) return;
        if (!selectedProduct) {
            setProductDraft(emptyProductDraft());
            return;
        }
        setProductDraft({
            name: selectedProduct.name || '',
            product_info: selectedProduct.product_info || '',
            core_selling_points: listToLines(selectedProduct.core_selling_points),
            differentiation: selectedProduct.differentiation || '',
            target_user: selectedProduct.target_user || '',
            pain_points: listToLines(selectedProduct.pain_points),
            competitor_problem: selectedProduct.competitor_problem || '',
        });
    }, [editing, selectedProduct]);

    const startCreate = (kind) => {
        setEditing('');
        setCreating(kind);
        setDraftName('');
        setDraftIntro('');
    };

    const startEdit = (kind, item) => {
        setCreating('');
        setEditing(kind);
        setDraftName(item?.name || '');
        setDraftIntro(item?.intro || '');
        if (kind === 'offering' && item) {
            setProductDraft({
                name: item.name || '',
                product_info: item.product_info || '',
                core_selling_points: listToLines(item.core_selling_points),
                differentiation: item.differentiation || '',
                target_user: item.target_user || '',
                pain_points: listToLines(item.pain_points),
                competitor_problem: item.competitor_problem || '',
            });
        }
    };

    const handleCreate = async () => {
        const name = String(draftName || '').trim();
        const intro = String(draftIntro || '').trim();
        if (!name || busy) return;
        setBusy(true);
        try {
            if (creating === 'enterprise') {
                const created = await createPromoEnterprise({ name, intro: intro || undefined });
                setEnterprises((prev) => [created, ...prev.filter((item) => Number(item.id) !== Number(created.id))]);
                setEnterpriseId(String(created.id));
                setBrandId('');
                setProductId('');
                setBrands([]);
                setProducts([]);
            } else if (creating === 'brand') {
                if (!enterpriseId) return;
                const created = await createPromoBrand({ enterprise_id: Number(enterpriseId), name, intro: intro || undefined });
                setBrands((prev) => [created, ...prev.filter((item) => Number(item.id) !== Number(created.id))]);
                setBrandId(String(created.id));
                setProductId('');
                setProducts([]);
            } else if (creating === 'offering') {
                if (!brandId) return;
                const created = await createPromoProduct({
                    brand_id: Number(brandId),
                    enterprise_id: Number(enterpriseId) || undefined,
                    name,
                });
                setProducts((prev) => [created, ...prev.filter((item) => Number(item.id) !== Number(created.id))]);
                setProductId(String(created.id));
            }
            setCreating('');
            setDraftName('');
            setDraftIntro('');
        } catch (error) {
            alert(error?.response?.data?.detail || error?.message || t('创建失败', 'Create failed'));
        } finally {
            setBusy(false);
        }
    };

    const handleSaveEdit = async (kind) => {
        if (busy) return;
        setBusy(true);
        try {
            if (kind === 'enterprise' && selectedEnterprise) {
                const name = String(draftName || '').trim();
                if (!name) throw new Error(t('名称必填', 'Name is required'));
                const updated = await updatePromoEnterprise(selectedEnterprise.id, { name, intro: String(draftIntro || '').trim() });
                setEnterprises((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? { ...item, ...updated } : item)));
            } else if (kind === 'brand' && selectedBrand) {
                const name = String(draftName || '').trim();
                if (!name) throw new Error(t('名称必填', 'Name is required'));
                const updated = await updatePromoBrand(selectedBrand.id, { name, intro: String(draftIntro || '').trim() });
                setBrands((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? { ...item, ...updated } : item)));
            } else if (kind === 'offering' && selectedProduct) {
                const name = String(productDraft.name || '').trim();
                if (!name) throw new Error(t('名称必填', 'Name is required'));
                const updated = await updatePromoProduct(selectedProduct.id, {
                    name,
                    product_info: productDraft.product_info,
                    core_selling_points: linesToList(productDraft.core_selling_points),
                    differentiation: productDraft.differentiation,
                    target_user: productDraft.target_user,
                    pain_points: linesToList(productDraft.pain_points),
                    competitor_problem: productDraft.competitor_problem,
                });
                setProducts((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? { ...item, ...updated } : item)));
            }
            setEditing('');
        } catch (error) {
            alert(error?.response?.data?.detail || error?.message || t('保存失败', 'Save failed'));
        } finally {
            setBusy(false);
        }
    };

    const handleDelete = async (kind, id) => {
        if (!id || busy) return;
        const ok = window.confirm(t('确定删除？相关下级也会停用。', 'Delete this record? Child records will also be disabled.'));
        if (!ok) return;
        setBusy(true);
        try {
            if (kind === 'enterprise') {
                await deletePromoEnterprise(id);
                setEnterprises((prev) => prev.filter((item) => Number(item.id) !== Number(id)));
                if (String(enterpriseId) === String(id)) {
                    setEnterpriseId('');
                    setBrandId('');
                    setProductId('');
                    setBrands([]);
                    setProducts([]);
                }
            } else if (kind === 'brand') {
                await deletePromoBrand(id);
                setBrands((prev) => prev.filter((item) => Number(item.id) !== Number(id)));
                if (String(brandId) === String(id)) {
                    setBrandId('');
                    setProductId('');
                    setProducts([]);
                }
            } else {
                await deletePromoProduct(id);
                setProducts((prev) => prev.filter((item) => Number(item.id) !== Number(id)));
                if (String(productId) === String(id)) setProductId('');
            }
            if (editing === kind) setEditing('');
        } catch (error) {
            alert(error?.response?.data?.detail || error?.message || t('删除失败', 'Delete failed'));
        } finally {
            setBusy(false);
        }
    };

    const columnProps = {
        t,
        creating,
        draftName,
        draftIntro,
        onDraftName: setDraftName,
        onDraftIntro: setDraftIntro,
        onSubmitCreate: handleCreate,
        onCancelCreate: () => setCreating(''),
        onEdit: startEdit,
        onDelete: handleDelete,
        busy,
    };

    return (
        <div className="h-full overflow-y-auto p-4 sm:p-6 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-lg font-semibold text-white">{t('企业 / 品牌 / 产品与服务', 'Enterprise / Brand / Offering')}</h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        {t('这里是宣传主体素材库，保存企业/品牌/产品的全部素材。各宣传片项目再单独勾选要用的子集；项目内只用该项目选中的素材。', 'This is the subject library: all enterprise / brand / offering assets. Each promo project picks a subset; a project only uses what it selected.')}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <button
                        type="button"
                        onClick={() => navigate('/')}
                        className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 flex items-center gap-1"
                    >
                        <Home className="w-3.5 h-3.5" /> {t('网站首页', 'Website Home')}
                    </button>
                    {onReturn ? (
                        <button
                            type="button"
                            onClick={onReturn}
                            className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20"
                        >
                            {returnTo?.returnCreateForm
                                ? t('返回新建项目', 'Back to new project')
                                : t('返回项目', 'Back to project')}
                        </button>
                    ) : null}
                </div>
            </div>
            {enterpriseId ? (
                <div className="bg-black/20 border border-white/10 rounded-2xl p-4">
                    <PromoCatalogAssets
                        t={t}
                        ownerKind="enterprise"
                        ownerId={enterpriseId}
                        disabled={busy}
                        title={t('企业素材库（全部素材；各项目再勾选要用的）', 'Enterprise library (full set; projects pick a subset)')}
                    />
                </div>
            ) : (
                <div className="bg-black/20 border border-white/10 rounded-2xl px-4 py-3 text-xs text-white/50">
                    {t('先选择或新建企业，即可看到并管理企业素材。', 'Select or create an enterprise to see its asset library.')}
                </div>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <EntityColumn
                    {...columnProps}
                    title={t('企业', 'Enterprise')}
                    items={enterprises}
                    selectedId={enterpriseId}
                    onSelect={(id) => {
                        setEnterpriseId(id);
                        setBrandId('');
                        setProductId('');
                        setCreating((prev) => (prev === 'brand' || prev === 'offering' ? '' : prev));
                        setEditing((prev) => (prev === 'brand' || prev === 'offering' ? '' : prev));
                    }}
                    onCreate={() => startCreate('enterprise')}
                    createKind="enterprise"
                    emptyHint={t('还没有企业，先新建一个。', 'No enterprise yet. Create one first.')}
                />
                <EntityColumn
                    {...columnProps}
                    title={t('品牌', 'Brand')}
                    items={brands}
                    selectedId={brandId}
                    onSelect={(id) => {
                        setBrandId(id);
                        setProductId('');
                        setCreating((prev) => (prev === 'offering' ? '' : prev));
                        setEditing((prev) => (prev === 'offering' ? '' : prev));
                    }}
                    onCreate={() => startCreate('brand')}
                    createKind="brand"
                    emptyHint={t('先选择企业，再新建品牌。', 'Select an enterprise, then create a brand.')}
                    disabled={!enterpriseId}
                />
                <EntityColumn
                    {...columnProps}
                    title={t('产品与服务', 'Product / Service')}
                    items={products}
                    selectedId={productId}
                    onSelect={setProductId}
                    onCreate={() => startCreate('offering')}
                    createKind="offering"
                    emptyHint={t('先选择品牌，再新建产品或服务。', 'Select a brand, then create a product or service.')}
                    disabled={!brandId}
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="bg-black/20 border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-sm font-semibold text-white">{t('企业详情', 'Enterprise detail')}</h4>
                        <button
                            type="button"
                            disabled={!selectedEnterprise || busy}
                            onClick={() => startEdit('enterprise', selectedEnterprise)}
                            className="px-2.5 py-1 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                        >
                            <Pencil className="w-3 h-3" /> {t('编辑', 'Edit')}
                        </button>
                    </div>
                    {editing === 'enterprise' && selectedEnterprise ? (
                        <>
                            <ImeField className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none" value={draftName} onChange={setDraftName} placeholder={t('企业名称', 'Enterprise name')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none min-h-[4.5rem]" value={draftIntro} onChange={setDraftIntro} placeholder={t('企业简介', 'Enterprise intro')} />
                            <div className="flex gap-2">
                                <button type="button" disabled={busy || !String(draftName || '').trim()} onClick={() => handleSaveEdit('enterprise')} className="px-3 py-1.5 rounded-md text-xs font-bold bg-primary text-black disabled:opacity-40">{t('保存', 'Save')}</button>
                                <button type="button" onClick={() => setEditing('')} className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10">{t('取消', 'Cancel')}</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="px-3 py-2 bg-black/30 rounded-lg text-sm min-h-[2.4rem]">{selectedEnterprise?.name || <span className="text-white/30">{t('未选择', 'Not selected')}</span>}</div>
                            <div className="px-3 py-2 bg-black/30 rounded-lg text-sm whitespace-pre-wrap min-h-[4.5rem]">{selectedEnterprise?.intro || <span className="text-white/30">{t('无简介', 'No intro')}</span>}</div>
                        </>
                    )}
                </div>
                <div className="bg-black/20 border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-sm font-semibold text-white">{t('品牌详情', 'Brand detail')}</h4>
                        <button
                            type="button"
                            disabled={!selectedBrand || busy}
                            onClick={() => startEdit('brand', selectedBrand)}
                            className="px-2.5 py-1 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                        >
                            <Pencil className="w-3 h-3" /> {t('编辑', 'Edit')}
                        </button>
                    </div>
                    {editing === 'brand' && selectedBrand ? (
                        <>
                            <ImeField className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none" value={draftName} onChange={setDraftName} placeholder={t('品牌名称', 'Brand name')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none min-h-[4.5rem]" value={draftIntro} onChange={setDraftIntro} placeholder={t('品牌简介', 'Brand intro')} />
                            <div className="flex gap-2">
                                <button type="button" disabled={busy || !String(draftName || '').trim()} onClick={() => handleSaveEdit('brand')} className="px-3 py-1.5 rounded-md text-xs font-bold bg-primary text-black disabled:opacity-40">{t('保存', 'Save')}</button>
                                <button type="button" onClick={() => setEditing('')} className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10">{t('取消', 'Cancel')}</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="px-3 py-2 bg-black/30 rounded-lg text-sm min-h-[2.4rem]">{selectedBrand?.name || <span className="text-white/30">{t('未选择', 'Not selected')}</span>}</div>
                            <div className="px-3 py-2 bg-black/30 rounded-lg text-sm whitespace-pre-wrap min-h-[4.5rem]">{selectedBrand?.intro || <span className="text-white/30">{t('无简介', 'No intro')}</span>}</div>
                        </>
                    )}
                    <PromoCatalogAssets t={t} ownerKind="brand" ownerId={brandId} disabled={busy} title={t('品牌素材库（全部）', 'Brand library (full set)')} />
                </div>
                <div className="bg-black/20 border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-sm font-semibold text-white">{t('产品与服务详情', 'Offering detail')}</h4>
                        <button
                            type="button"
                            disabled={!selectedProduct || busy}
                            onClick={() => startEdit('offering', selectedProduct)}
                            className="px-2.5 py-1 rounded-md text-xs font-bold bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                        >
                            <Pencil className="w-3 h-3" /> {t('编辑', 'Edit')}
                        </button>
                    </div>
                    {editing === 'offering' && selectedProduct ? (
                        <>
                            <ImeField className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm outline-none" value={productDraft.name} onChange={(v) => setProductDraft((prev) => ({ ...prev, name: v }))} placeholder={t('名称', 'Name')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm min-h-[4rem]" value={productDraft.product_info} onChange={(v) => setProductDraft((prev) => ({ ...prev, product_info: v }))} placeholder={t('介绍', 'Intro')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm min-h-[3.5rem]" value={productDraft.core_selling_points} onChange={(v) => setProductDraft((prev) => ({ ...prev, core_selling_points: v }))} placeholder={t('核心卖点（每行一条）', 'Selling points (one per line)')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm min-h-[3rem]" value={productDraft.differentiation} onChange={(v) => setProductDraft((prev) => ({ ...prev, differentiation: v }))} placeholder={t('差异化', 'Differentiation')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm min-h-[3rem]" value={productDraft.target_user} onChange={(v) => setProductDraft((prev) => ({ ...prev, target_user: v }))} placeholder={t('目标人群', 'Target audience')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm min-h-[3rem]" value={productDraft.pain_points} onChange={(v) => setProductDraft((prev) => ({ ...prev, pain_points: v }))} placeholder={t('痛点（每行一条）', 'Pain points (one per line)')} />
                            <ImeField multiline className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm min-h-[3rem]" value={productDraft.competitor_problem} onChange={(v) => setProductDraft((prev) => ({ ...prev, competitor_problem: v }))} placeholder={t('竞品短板（可选）', 'Competitor gaps (optional)')} />
                            <div className="flex gap-2">
                                <button type="button" disabled={busy || !String(productDraft.name || '').trim()} onClick={() => handleSaveEdit('offering')} className="px-3 py-1.5 rounded-md text-xs font-bold bg-primary text-black disabled:opacity-40">{t('保存', 'Save')}</button>
                                <button type="button" onClick={() => setEditing('')} className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10">{t('取消', 'Cancel')}</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="text-[11px] text-white/45">{t('名称', 'Name')}</div>
                            <ReadValue value={selectedProduct?.name} empty={t('未选择', 'Not selected')} />
                            <div className="text-[11px] text-white/45">{t('介绍', 'Intro')}</div>
                            <ReadValue value={selectedProduct?.product_info} empty={t('无介绍', 'No intro')} minHeight="4rem" />
                            <div className="text-[11px] text-white/45">{t('核心卖点', 'Selling points')}</div>
                            <ReadValue value={listToLines(selectedProduct?.core_selling_points)} empty={t('无核心卖点', 'No selling points')} minHeight="3.5rem" />
                            <div className="text-[11px] text-white/45">{t('差异化', 'Differentiation')}</div>
                            <ReadValue value={selectedProduct?.differentiation} empty={t('无差异化说明', 'No differentiation')} minHeight="3rem" />
                            <div className="text-[11px] text-white/45">{t('目标人群', 'Target audience')}</div>
                            <ReadValue value={selectedProduct?.target_user} empty={t('无目标人群', 'No target audience')} minHeight="3rem" />
                            <div className="text-[11px] text-white/45">{t('痛点', 'Pain points')}</div>
                            <ReadValue value={listToLines(selectedProduct?.pain_points)} empty={t('无痛点', 'No pain points')} minHeight="3rem" />
                            <div className="text-[11px] text-white/45">{t('竞品短板', 'Competitor gaps')}</div>
                            <ReadValue value={selectedProduct?.competitor_problem} empty={t('无竞品短板', 'No competitor gaps')} minHeight="3rem" />
                        </>
                    )}
                    <PromoCatalogAssets t={t} ownerKind="offering" ownerId={productId} disabled={busy || !productId} title={t('产品与服务素材库（全部）', 'Offering library (full set)')} />
                </div>
            </div>
        </div>
    );
}
