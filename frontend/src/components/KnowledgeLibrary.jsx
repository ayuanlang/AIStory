import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    BookOpen,
    CheckCircle,
    Image as ImageIcon,
    Loader2,
    Plus,
    Search,
    Sparkles,
    Trash2,
    Upload,
    X,
    Ban,
} from 'lucide-react';
import {
    createKbEntry,
    createKbEvalCase,
    deleteKbEntry,
    deleteKbEntryMedia,
    downloadKbImportTemplateCsv,
    downloadKbImportTemplateJson,
    fetchKbEntries,
    fetchProjectKbCollection,
    importKbFile,
    ingestKbFromText,
    ingestKbFromWeb,
    captionKbEntryMedia,
    reindexKbEntry,
    reviewKbEntry,
    runKbEval,
    searchKbEntries,
    searchKbEntriesByImage,
    updateKbEntry,
    updateKbEntryQuality,
    updateProjectKbCollection,
    uploadKbEntryMedia,
} from '../services/api';
import { ASSET_BASE_URL, BASE_URL } from '../config';
import { confirmUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI, UI_LANG_EVENT } from '../lib/uiLang';

const CATEGORIES = [
    { id: 'portrait', zh: '肖像素材', en: 'Portraits' },
    { id: 'costume', zh: '服饰素材', en: 'Costumes' },
    { id: 'scenery', zh: '美景素材', en: 'Scenery' },
    { id: 'plot', zh: '剧情素材', en: 'Plot' },
];

const PLOT_SUBTYPES = [
    { id: '', zh: '全部子类', en: 'All subtypes' },
    { id: 'trope', zh: '经典桥段', en: 'Tropes' },
    { id: 'dialogue', zh: '对话', en: 'Dialogue' },
    { id: 'action', zh: '动作', en: 'Action' },
];

const REVIEW_FILTERS = [
    { id: '', zh: '全部状态', en: 'All status' },
    { id: 'pending', zh: '待审核', en: 'Pending' },
    { id: 'approved', zh: '已通过', en: 'Approved' },
    { id: 'rejected', zh: '已驳回', en: 'Rejected' },
];

const emptyForm = () => ({
    category: 'portrait',
    plot_subtype: 'trope',
    title: '',
    summary: '',
    body_text: '',
    tags: '',
    style_keywords: '',
    work_title: '',
    work_year: '',
    license_tier: 'reference_ok',
    copyright_note: '',
    source_type: 'manual',
    source_url: '',
});

const getFullUrl = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return '';
    if (raw.startsWith('http') || raw.startsWith('blob:') || raw.startsWith('data:')) return raw;
    let normalizedPath = raw;
    if (!normalizedPath.includes('/') && /^[A-Za-z0-9_.-]+$/.test(normalizedPath)) {
        normalizedPath = `/uploads/${normalizedPath}`;
    }
    const resolvedAssetBase = String(ASSET_BASE_URL || BASE_URL || '').trim();
    const base = resolvedAssetBase.endsWith('/') ? resolvedAssetBase.slice(0, -1) : resolvedAssetBase;
    if (normalizedPath.startsWith('/')) return `${base}${normalizedPath}`;
    if (normalizedPath.startsWith('uploads/')) return `${base}/${normalizedPath}`;
    return normalizedPath;
};

const splitCsv = (text) => String(text || '')
    .split(/[,，;；|/]/)
    .map((item) => item.trim())
    .filter(Boolean);

const statusBadgeClass = (status) => {
    if (status === 'approved') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    if (status === 'rejected') return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
    return 'bg-amber-500/15 text-amber-200 border-amber-500/30';
};

const LICENSE_OPTIONS = [
    { id: 'public_domain', zh: '公有领域', en: 'Public domain' },
    { id: 'reference_ok', zh: '可作参考', en: 'Reference OK' },
    { id: 'fair_use_ref', zh: '合理使用参考', en: 'Fair-use ref' },
    { id: 'restricted', zh: '受限', en: 'Restricted' },
    { id: 'blocked', zh: '禁止注入', en: 'Blocked' },
];

const INDEX_STATUS_OPTIONS = [
    { id: 'none', zh: '未建索引', en: 'Not indexed' },
    { id: 'pending', zh: '索引中', en: 'Indexing' },
    { id: 'ready', zh: '已就绪', en: 'Ready' },
    { id: 'failed', zh: '失败', en: 'Failed' },
];

const SOURCE_TYPE_OPTIONS = [
    { id: 'manual', zh: '人工录入', en: 'Manual' },
    { id: 'upload', zh: '上传', en: 'Upload' },
    { id: 'web', zh: '网络', en: 'Web' },
    { id: 'llm', zh: 'LLM 抽取', en: 'LLM extract' },
];

const KnowledgeLibrary = ({ currentUser = null, projectOptions = [] }) => {
    const [uiLang, setUiLangState] = useState(() => getUiLang());
    const t = (zh, en) => tUI(uiLang, zh, en);
    const fileInputRef = useRef(null);
    const imageSearchInputRef = useRef(null);

    useEffect(() => {
        const onLang = (event) => {
            const next = event?.detail === 'en' ? 'en' : getUiLang();
            setUiLangState(next);
        };
        window.addEventListener(UI_LANG_EVENT, onLang);
        return () => window.removeEventListener(UI_LANG_EVENT, onLang);
    }, []);

    const [category, setCategory] = useState('portrait');
    const [plotSubtype, setPlotSubtype] = useState('');
    const [reviewStatus, setReviewStatus] = useState('');
    const [query, setQuery] = useState('');
    const [semanticEnabled, setSemanticEnabled] = useState(true);
    const [searchMeta, setSearchMeta] = useState(null);
    const [imageSearching, setImageSearching] = useState(false);
    const [captioningMediaId, setCaptioningMediaId] = useState(null);
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [isSuperuser, setIsSuperuser] = useState(!!currentUser?.is_superuser);
    const [reindexing, setReindexing] = useState(false);
    const [qualitySaving, setQualitySaving] = useState(false);
    const [evalRunning, setEvalRunning] = useState(false);
    const [evalSummary, setEvalSummary] = useState(null);
    const [collectionProjectId, setCollectionProjectId] = useState('');
    const [collectionBusy, setCollectionBusy] = useState(false);
    const importInputRef = useRef(null);
    const [importing, setImporting] = useState(false);
    const [importAutoApprove, setImportAutoApprove] = useState(false);

    const [selectedId, setSelectedId] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [form, setForm] = useState(emptyForm());
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [reviewing, setReviewing] = useState(false);

    const [showIngest, setShowIngest] = useState(false);
    const [ingesting, setIngesting] = useState(false);
    const [reloadToken, setReloadToken] = useState(0);
    const [ingestForm, setIngestForm] = useState({
        mode: 'web',
        category: 'portrait',
        topic: '',
        work_title: '',
        work_year: '',
        source_text: '',
        max_entries: 6,
        language: 'zh',
    });

    const selected = useMemo(
        () => items.find((item) => Number(item.id) === Number(selectedId)) || null,
        [items, selectedId],
    );

    const loadEntries = async () => {
        setLoading(true);
        setError('');
        try {
            const q = query.trim();
            let data;
            if (q && semanticEnabled) {
                data = await searchKbEntries({
                    query: q,
                    category,
                    plot_subtype: category === 'plot' && plotSubtype ? plotSubtype : null,
                    top_k: 40,
                    mode: 'hybrid',
                });
                setSearchMeta({
                    mode: data?.mode || 'hybrid',
                    embedding_model: data?.embedding_model || null,
                });
            } else {
                const params = {
                    category,
                    limit: 80,
                    offset: 0,
                };
                if (category === 'plot' && plotSubtype) params.plot_subtype = plotSubtype;
                if (reviewStatus) params.review_status = reviewStatus;
                if (q) params.q = q;
                data = await fetchKbEntries(params);
                setSearchMeta(null);
            }
            let nextItems = Array.isArray(data?.items) ? data.items : [];
            if (q && semanticEnabled && reviewStatus) {
                nextItems = nextItems.filter((item) => String(item.review_status || '') === reviewStatus);
            }
            setItems(nextItems);
            setTotal(Number(data?.total || nextItems.length) || 0);
            if (typeof data?.is_superuser === 'boolean') {
                setIsSuperuser(data.is_superuser);
            }
            if (selectedId && !nextItems.some((item) => Number(item.id) === Number(selectedId))) {
                setSelectedId(nextItems[0]?.id ?? null);
            } else if (!selectedId && nextItems.length) {
                setSelectedId(nextItems[0].id);
            }
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('加载失败', 'Failed to load'));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadEntries();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [category, plotSubtype, reviewStatus, reloadToken]);

    const openCreate = () => {
        setEditingId(null);
        setForm({ ...emptyForm(), category });
        setShowForm(true);
    };

    const openIngest = () => {
        setIngestForm((prev) => ({
            ...prev,
            category,
            topic: '',
            source_text: '',
            language: uiLang === 'en' ? 'en' : 'zh',
        }));
        setShowIngest(true);
    };

    const handleIngest = async () => {
        const payload = {
            category: ingestForm.category,
            work_title: ingestForm.work_title.trim() || null,
            work_year: ingestForm.work_year.trim() || null,
            max_entries: Math.max(1, Math.min(Number(ingestForm.max_entries) || 6, 12)),
            language: ingestForm.language || 'zh',
        };
        if (ingestForm.mode === 'web') {
            if (!ingestForm.topic.trim()) {
                setError(t('请填写采集主题', 'Topic is required'));
                return;
            }
        } else if (ingestForm.source_text.trim().length < 20) {
            setError(t('粘贴文本过短', 'Source text is too short'));
            return;
        }

        setIngesting(true);
        setError('');
        try {
            const result = ingestForm.mode === 'web'
                ? await ingestKbFromWeb({ ...payload, topic: ingestForm.topic.trim() })
                : await ingestKbFromText({ ...payload, source_text: ingestForm.source_text.trim() });
            setShowIngest(false);
            const created = Array.isArray(result?.entries) ? result.entries : [];
            if (created[0]?.id) setSelectedId(created[0].id);
            setCategory(ingestForm.category);
            setReviewStatus('pending');
            setQuery('');
            setSemanticEnabled(false);
            setReloadToken((n) => n + 1);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('采集失败', 'Ingest failed'));
        } finally {
            setIngesting(false);
        }
    };

    const openEdit = (entry) => {
        if (!entry) return;
        setEditingId(entry.id);
        setForm({
            category: entry.category || 'portrait',
            plot_subtype: entry.plot_subtype || 'trope',
            title: entry.title || '',
            summary: entry.summary || '',
            body_text: entry.body_text || '',
            tags: (entry.tags || []).join(', '),
            style_keywords: (entry.style_keywords || []).join(', '),
            work_title: entry.work?.title || '',
            work_year: entry.work?.year || '',
            license_tier: entry.license_tier || 'reference_ok',
            copyright_note: entry.copyright_note || '',
            source_type: entry.source_type || 'manual',
            source_url: entry.source_url || '',
        });
        setShowForm(true);
    };

    const handleSave = async () => {
        const title = String(form.title || '').trim();
        if (!title) {
            setError(t('请填写标题', 'Title is required'));
            return;
        }
        setSaving(true);
        setError('');
        try {
            const payload = {
                category: form.category,
                title,
                summary: form.summary.trim() || null,
                body_text: form.body_text.trim() || null,
                tags: splitCsv(form.tags),
                style_keywords: splitCsv(form.style_keywords),
                license_tier: form.license_tier,
                copyright_note: form.copyright_note.trim() || null,
                source_type: form.source_type,
                source_url: form.source_url.trim() || null,
                plot_subtype: form.category === 'plot' ? (form.plot_subtype || 'trope') : null,
            };
            if (!editingId && form.work_title.trim()) {
                payload.work_title = form.work_title.trim();
                payload.work_year = form.work_year.trim() || null;
            }
            let saved;
            if (editingId) {
                saved = await updateKbEntry(editingId, payload);
            } else {
                saved = await createKbEntry(payload);
            }
            setShowForm(false);
            setEditingId(null);
            await loadEntries();
            if (saved?.id) setSelectedId(saved.id);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('保存失败', 'Save failed'));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (entry) => {
        if (!entry) return;
        const ok = await confirmUiMessage(t(`确认删除「${entry.title}」？`, `Delete "${entry.title}"?`));
        if (!ok) return;
        try {
            await deleteKbEntry(entry.id);
            if (Number(selectedId) === Number(entry.id)) setSelectedId(null);
            await loadEntries();
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('删除失败', 'Delete failed'));
        }
    };

    const handleReview = async (action) => {
        if (!selected) return;
        setReviewing(true);
        setError('');
        try {
            const updated = await reviewKbEntry(selected.id, { action });
            setItems((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? updated : item)));
            if (action === 'approve') {
                // indexing runs in background; refresh shortly
                setTimeout(() => { loadEntries(); }, 1200);
            }
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('审核失败', 'Review failed'));
        } finally {
            setReviewing(false);
        }
    };

    const handleReindex = async () => {
        if (!selected) return;
        setReindexing(true);
        setError('');
        try {
            const result = await reindexKbEntry(selected.id, { sync: true });
            const updated = result?.entry;
            if (updated) {
                setItems((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? updated : item)));
            } else {
                await loadEntries();
            }
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('重建索引失败', 'Reindex failed'));
        } finally {
            setReindexing(false);
        }
    };

    const patchSelected = (updated) => {
        if (!updated?.id) return;
        setItems((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? { ...item, ...updated } : item)));
    };

    const handleQualitySave = async () => {
        if (!selected) return;
        setQualitySaving(true);
        setError('');
        try {
            const updated = await updateKbEntryQuality(selected.id, {
                quality_score: Number(selected.quality_score ?? 3),
                quality_notes: selected.quality_notes || null,
                is_eval_gold: !!selected.is_eval_gold,
            });
            patchSelected(updated);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('评分保存失败', 'Failed to save quality'));
        } finally {
            setQualitySaving(false);
        }
    };

    const handleCreateEvalCase = async () => {
        if (!selected || !isSuperuser) return;
        try {
            await createKbEvalCase({
                name: selected.title,
                query: selected.title,
                category: selected.category,
                expected_entry_ids: [selected.id],
                expected_tags: selected.tags || [],
                notes: t('由条目一键创建', 'Created from entry'),
            });
            setEvalSummary({ message: t('已创建评测用例', 'Eval case created') });
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('创建评测用例失败', 'Failed to create eval case'));
        }
    };

    const handleRunEval = async () => {
        if (!isSuperuser) return;
        setEvalRunning(true);
        setError('');
        try {
            const result = await runKbEval({ top_k: 8, mode: 'hybrid', category: category || null });
            setEvalSummary(result);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('评测失败', 'Eval failed'));
        } finally {
            setEvalRunning(false);
        }
    };

    const handleAddToProjectCollection = async () => {
        if (!selected || !collectionProjectId) return;
        setCollectionBusy(true);
        setError('');
        try {
            const current = await fetchProjectKbCollection(collectionProjectId);
            const ids = Array.isArray(current?.entry_ids) ? current.entry_ids.map(Number) : [];
            if (!ids.includes(Number(selected.id))) ids.push(Number(selected.id));
            await updateProjectKbCollection(collectionProjectId, {
                entry_ids: ids,
                collection_only: !!current?.collection_only,
            });
            setEvalSummary({ message: t('已加入项目收藏集', 'Added to project collection') });
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('加入收藏失败', 'Failed to update collection'));
        } finally {
            setCollectionBusy(false);
        }
    };

    const triggerDownloadBlob = (blob, filename) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleDownloadCsvTemplate = async () => {
        try {
            const blob = await downloadKbImportTemplateCsv();
            triggerDownloadBlob(blob, 'kb_import_template.csv');
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('模板下载失败', 'Template download failed'));
        }
    };

    const handleDownloadJsonTemplate = async () => {
        try {
            const data = await downloadKbImportTemplateJson();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
            triggerDownloadBlob(blob, 'kb_import_template.json');
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('模板下载失败', 'Template download failed'));
        }
    };

    const handleImageSearch = async (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file) return;
        setImageSearching(true);
        setLoading(true);
        setError('');
        try {
            const data = await searchKbEntriesByImage(file, {
                query: query.trim(),
                category,
                plotSubtype: category === 'plot' && plotSubtype ? plotSubtype : null,
                topK: 40,
                mode: 'hybrid',
            });
            let nextItems = Array.isArray(data?.items) ? data.items : [];
            if (reviewStatus) {
                nextItems = nextItems.filter((item) => String(item.review_status || '') === reviewStatus);
            }
            setItems(nextItems);
            setTotal(Number(data?.total || nextItems.length) || 0);
            setSearchMeta({
                mode: data?.mode || 'hybrid',
                embedding_model: data?.embedding_model || null,
                search_type: 'image',
                vision_model: data?.vision_model || null,
                query_text: data?.query_text || data?.vision_query || '',
            });
            if (nextItems[0]?.id) setSelectedId(nextItems[0].id);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('以图检索失败', 'Image search failed'));
        } finally {
            setImageSearching(false);
            setLoading(false);
        }
    };

    const handleCaptionMedia = async (media) => {
        if (!selected || !media) return;
        setCaptioningMediaId(media.id);
        setError('');
        try {
            const result = await captionKbEntryMedia(selected.id, media.id, { force: true });
            const updated = result?.entry;
            if (updated) {
                setItems((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? updated : item)));
            } else {
                await loadEntries();
            }
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('图像描述失败', 'Caption failed'));
        } finally {
            setCaptioningMediaId(null);
        }
    };

    const handleImportFile = async (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file) return;
        setImporting(true);
        setError('');
        try {
            // dry-run first
            const preview = await importKbFile(file, {
                dryRun: true,
                autoApprove: false,
                reindexApproved: false,
            });
            const willImport = Number(preview?.will_import || 0);
            const importStatusLabel = importAutoApprove && isSuperuser
                ? t('直接通过并建索引', 'approve and index')
                : t('待审核', 'pending review');
            const ok = await confirmUiMessage(
                t(
                    `预检通过，将导入 ${willImport} 条（状态：${importStatusLabel}）。确认继续？`,
                    `Validation OK. Import ${willImport} rows as ${importStatusLabel}. Continue?`,
                ),
            );
            if (!ok) return;
            const result = await importKbFile(file, {
                dryRun: false,
                autoApprove: !!(importAutoApprove && isSuperuser),
                reindexApproved: true,
            });
            setReviewStatus(importAutoApprove && isSuperuser ? 'approved' : 'pending');
            setReloadToken((n) => n + 1);
            setEvalSummary({
                message: t(
                    `已导入 ${result?.created_count || 0} 条`,
                    `Imported ${result?.created_count || 0} entries`,
                ),
            });
            if (Array.isArray(result?.entries) && result.entries[0]?.id) {
                setSelectedId(result.entries[0].id);
            }
        } catch (err) {
            const detail = err?.response?.data?.detail;
            const msg = typeof detail === 'object'
                ? (detail.message || JSON.stringify(detail.errors || detail))
                : (detail || err?.message);
            setError(msg || t('批量导入失败', 'Batch import failed'));
        } finally {
            setImporting(false);
        }
    };

    const handleUploadClick = () => {
        if (!selected) return;
        fileInputRef.current?.click();
    };

    const handleFileChange = async (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file || !selected) return;
        setUploading(true);
        setError('');
        try {
            const result = await uploadKbEntryMedia(selected.id, file);
            const updated = result?.entry;
            if (updated) {
                setItems((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? updated : item)));
            } else {
                await loadEntries();
            }
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('上传失败', 'Upload failed'));
        } finally {
            setUploading(false);
        }
    };

    const handleDeleteMedia = async (media) => {
        if (!selected || !media) return;
        const ok = await confirmUiMessage(t('确认删除该附件？', 'Delete this attachment?'));
        if (!ok) return;
        try {
            const result = await deleteKbEntryMedia(selected.id, media.id);
            const updated = result?.entry;
            if (updated) {
                setItems((prev) => prev.map((item) => (Number(item.id) === Number(updated.id) ? updated : item)));
            } else {
                await loadEntries();
            }
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || t('删除附件失败', 'Failed to delete media'));
        }
    };

    const labelFromOptions = (options, id, fallback = '') => {
        const found = options.find((item) => item.id === id);
        if (found) return t(found.zh, found.en);
        return fallback || id || '';
    };

    const statusLabel = (status) => labelFromOptions(REVIEW_FILTERS.filter((item) => item.id), status, t('待审核', 'Pending'));

    const categoryLabel = (id) => labelFromOptions(CATEGORIES, id, id);

    const plotSubtypeLabel = (id) => {
        if (!id) return '';
        return labelFromOptions(PLOT_SUBTYPES.filter((item) => item.id), id, id);
    };

    const licenseLabel = (id) => labelFromOptions(LICENSE_OPTIONS, id, id);

    const indexStatusLabel = (id) => labelFromOptions(INDEX_STATUS_OPTIONS, id || 'none', id || t('未建索引', 'Not indexed'));

    const sourceTypeLabel = (id) => labelFromOptions(SOURCE_TYPE_OPTIONS, id, id);

    const chunkKindLabel = (kind) => {
        if (kind === 'image') return t('图像', 'Image');
        return t('文本', 'Text');
    };

    return (
        <div className="h-full flex flex-col">
            <div className="px-4 sm:px-6 lg:px-8 py-4 border-b border-white/5 flex flex-col gap-4">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <BookOpen className="w-4 h-4" />
                        <span>{t('平台知识库 · 经典流行作品参考', 'Platform knowledge base · classic & popular references')}</span>
                        <span className="text-white/40">·</span>
                        <span>{total}</span>
                    </div>
                    <div className="flex flex-wrap gap-2 items-center">
                        {isSuperuser && (
                            <button
                                type="button"
                                disabled={evalRunning}
                                onClick={handleRunEval}
                                className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-secondary/40 disabled:opacity-50"
                            >
                                {evalRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                                {t('跑评测', 'Run eval')}
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={handleDownloadCsvTemplate}
                            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-secondary/40"
                        >
                            {t('CSV模板', 'CSV template')}
                        </button>
                        <button
                            type="button"
                            onClick={handleDownloadJsonTemplate}
                            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-secondary/40"
                        >
                            {t('JSON模板', 'JSON template')}
                        </button>
                        <button
                            type="button"
                            disabled={importing}
                            onClick={() => importInputRef.current?.click()}
                            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-secondary/40 disabled:opacity-50"
                        >
                            {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                            {t('批量导入', 'Batch import')}
                        </button>
                        <input
                            ref={importInputRef}
                            type="file"
                            accept=".csv,.json,text/csv,application/json"
                            className="hidden"
                            onChange={handleImportFile}
                        />
                        {isSuperuser && (
                            <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                                <input
                                    type="checkbox"
                                    checked={importAutoApprove}
                                    onChange={(e) => setImportAutoApprove(e.target.checked)}
                                />
                                {t('导入即通过', 'Auto-approve')}
                            </label>
                        )}
                        <button
                            type="button"
                            onClick={openIngest}
                            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-secondary/40"
                        >
                            <Sparkles className="w-4 h-4" />
                            {t('采集入库', 'Ingest')}
                        </button>
                        <button
                            type="button"
                            onClick={openCreate}
                            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
                        >
                            <Plus className="w-4 h-4" />
                            {t('新建条目', 'New entry')}
                        </button>
                    </div>
                </div>
                {evalSummary && (
                    <div className="text-xs text-muted-foreground">
                        {evalSummary.message
                            || t(
                                `评测 Hit@K=${evalSummary.hit_at_k ?? '-'} · MRR=${evalSummary.avg_reciprocal_rank ?? '-'} · 用例=${evalSummary.case_count ?? 0}`,
                                `Eval Hit@K=${evalSummary.hit_at_k ?? '-'} · MRR=${evalSummary.avg_reciprocal_rank ?? '-'} · cases=${evalSummary.case_count ?? 0}`,
                            )}
                    </div>
                )}

                <div className="flex flex-wrap gap-2">
                    {CATEGORIES.map((item) => (
                        <button
                            key={item.id}
                            type="button"
                            onClick={() => {
                                setCategory(item.id);
                                setSelectedId(null);
                            }}
                            className={`rounded-lg px-3 py-1.5 text-sm border transition-colors ${
                                category === item.id
                                    ? 'bg-primary text-primary-foreground border-primary'
                                    : 'border-white/10 text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                            }`}
                        >
                            {t(item.zh, item.en)}
                        </button>
                    ))}
                </div>

                <div className="flex flex-col sm:flex-row gap-2">
                    <div className="relative flex-1">
                        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') loadEntries();
                            }}
                            placeholder={t('搜索标题、摘要、正文…', 'Search title, summary, body…')}
                            className="w-full rounded-lg border border-white/10 bg-black/20 pl-9 pr-3 py-2 text-sm outline-none focus:border-primary/40"
                        />
                    </div>
                    {category === 'plot' && (
                        <select
                            value={plotSubtype}
                            onChange={(e) => setPlotSubtype(e.target.value)}
                            className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm outline-none focus:border-primary/40"
                        >
                            {PLOT_SUBTYPES.map((item) => (
                                <option key={item.id || 'all'} value={item.id}>{t(item.zh, item.en)}</option>
                            ))}
                        </select>
                    )}
                    <select
                        value={reviewStatus}
                        onChange={(e) => setReviewStatus(e.target.value)}
                        className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm outline-none focus:border-primary/40"
                    >
                        {REVIEW_FILTERS.map((item) => (
                            <option key={item.id || 'all-status'} value={item.id}>{t(item.zh, item.en)}</option>
                        ))}
                    </select>
                    <label className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-muted-foreground">
                        <input
                            type="checkbox"
                            checked={semanticEnabled}
                            onChange={(e) => setSemanticEnabled(e.target.checked)}
                        />
                        {t('语义检索', 'Semantic')}
                    </label>
                    <button
                        type="button"
                        onClick={loadEntries}
                        className="rounded-lg border border-white/10 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-secondary/40"
                    >
                        {t('搜索', 'Search')}
                    </button>
                    <button
                        type="button"
                        onClick={() => imageSearchInputRef.current?.click()}
                        disabled={imageSearching}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-secondary/40 disabled:opacity-50"
                        title={t('上传参考图，视觉描述后混合检索', 'Upload a reference image for vision→hybrid search')}
                    >
                        {imageSearching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5" />}
                        {t('以图搜', 'Image search')}
                    </button>
                    <input
                        ref={imageSearchInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={handleImageSearch}
                    />
                </div>
                {searchMeta && (
                    <div className="text-xs text-muted-foreground space-y-1">
                        <div>
                            {searchMeta.search_type === 'image'
                                ? t('以图检索', 'Image search')
                                : t('混合检索', 'Hybrid search')}
                            {searchMeta.embedding_model ? ` · ${searchMeta.embedding_model}` : ''}
                            {searchMeta.vision_model ? ` · vision:${searchMeta.vision_model}` : ''}
                        </div>
                        {searchMeta.query_text ? (
                            <div className="line-clamp-2 text-foreground/70">
                                {t('查询改写：', 'Query rewrite: ')}{searchMeta.query_text}
                            </div>
                        ) : null}
                    </div>
                )}
            </div>

            {error && (
                <div className="mx-4 sm:mx-6 lg:mx-8 mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                    {String(error)}
                </div>
            )}

            <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
                <div className="min-h-0 overflow-y-auto border-r border-white/5 p-4 sm:p-6">
                    {loading ? (
                        <div className="h-40 flex items-center justify-center text-muted-foreground gap-2">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            {t('加载中…', 'Loading…')}
                        </div>
                    ) : items.length === 0 ? (
                        <div className="h-40 flex flex-col items-center justify-center text-muted-foreground gap-2">
                            <ImageIcon className="w-8 h-8 opacity-40" />
                            <div>{t('暂无条目，点击「新建条目」开始。', 'No entries yet. Click “New entry” to start.')}</div>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                            {items.map((entry) => {
                                const cover = getFullUrl(entry.cover_url || entry.media?.[0]?.url);
                                const active = Number(selectedId) === Number(entry.id);
                                return (
                                    <button
                                        key={entry.id}
                                        type="button"
                                        onClick={() => setSelectedId(entry.id)}
                                        className={`text-left rounded-xl border overflow-hidden transition-colors ${
                                            active
                                                ? 'border-primary/60 bg-primary/10'
                                                : 'border-white/10 bg-black/20 hover:border-white/20'
                                        }`}
                                    >
                                        <div className="aspect-[16/10] bg-black/40 relative overflow-hidden">
                                            {cover ? (
                                                <img src={cover} alt="" className="w-full h-full object-cover" />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-white/20">
                                                    <BookOpen className="w-8 h-8" />
                                                </div>
                                            )}
                                            <span className={`absolute top-2 right-2 rounded-full border px-2 py-0.5 text-[10px] ${statusBadgeClass(entry.review_status)}`}>
                                                {statusLabel(entry.review_status)}
                                            </span>
                                        </div>
                                        <div className="p-3 space-y-1">
                                            <div className="font-medium text-sm line-clamp-1">{entry.title}</div>
                                            <div className="text-xs text-muted-foreground line-clamp-1">
                                                {entry.work?.title || categoryLabel(entry.category)}
                                                {entry.plot_subtype ? ` · ${plotSubtypeLabel(entry.plot_subtype)}` : ''}
                                                {typeof entry.score === 'number' ? ` · ${entry.score.toFixed(2)}` : ''}
                                                {entry.matched_chunk_kind === 'image' ? ` · ${chunkKindLabel('image')}` : ''}
                                            </div>
                                            {entry.snippet && (
                                                <div className="text-[11px] text-white/45 line-clamp-2">{entry.snippet}</div>
                                            )}
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>

                <div className="min-h-0 overflow-y-auto p-4 sm:p-6">
                    {!selected ? (
                        <div className="h-full min-h-[16rem] flex items-center justify-center text-muted-foreground text-sm">
                            {t('选择左侧条目查看详情', 'Select an entry to view details')}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <div className="text-lg font-semibold truncate">{selected.title}</div>
                                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                        <span className={`rounded-full border px-2 py-0.5 ${statusBadgeClass(selected.review_status)}`}>
                                            {statusLabel(selected.review_status)}
                                        </span>
                                        <span>{categoryLabel(selected.category)}</span>
                                        {selected.plot_subtype && <span>{plotSubtypeLabel(selected.plot_subtype)}</span>}
                                        {selected.work?.title && <span>{selected.work.title}{selected.work.year ? ` (${selected.work.year})` : ''}</span>}
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-2 shrink-0">
                                    <button
                                        type="button"
                                        onClick={() => openEdit(selected)}
                                        className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-secondary/40"
                                    >
                                        {t('编辑', 'Edit')}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => handleDelete(selected)}
                                        className="rounded-lg border border-rose-500/30 text-rose-300 px-3 py-1.5 text-xs hover:bg-rose-500/10"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>

                            {selected.summary && (
                                <p className="text-sm text-muted-foreground whitespace-pre-wrap">{selected.summary}</p>
                            )}
                            {selected.body_text && (
                                <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm whitespace-pre-wrap">
                                    {selected.body_text}
                                </div>
                            )}

                            {(selected.tags?.length > 0 || selected.style_keywords?.length > 0) && (
                                <div className="flex flex-wrap gap-1.5">
                                    {(selected.tags || []).map((tag) => (
                                        <span key={`tag-${tag}`} className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-muted-foreground">{tag}</span>
                                    ))}
                                    {(selected.style_keywords || []).map((tag) => (
                                        <span key={`style-${tag}`} className="rounded-full border border-primary/30 px-2 py-0.5 text-[11px] text-primary/90">{tag}</span>
                                    ))}
                                </div>
                            )}

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <div className="text-sm font-medium">{t('参考图像', 'Reference images')}</div>
                                    <button
                                        type="button"
                                        onClick={handleUploadClick}
                                        disabled={uploading}
                                        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-secondary/40 disabled:opacity-50"
                                    >
                                        {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                                        {t('上传', 'Upload')}
                                    </button>
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept="image/*,video/mp4,video/webm,video/quicktime"
                                        className="hidden"
                                        onChange={handleFileChange}
                                    />
                                </div>
                                {(selected.media || []).length === 0 ? (
                                    <div className="rounded-xl border border-dashed border-white/10 px-3 py-8 text-center text-xs text-muted-foreground">
                                        {t('尚无附件', 'No attachments yet')}
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                        {selected.media.map((media) => (
                                            <div key={media.id} className="relative group rounded-lg overflow-hidden border border-white/10 bg-black/30">
                                                {media.media_type === 'video' ? (
                                                    <video src={getFullUrl(media.url)} className="w-full aspect-square object-cover" controls />
                                                ) : (
                                                    <img src={getFullUrl(media.url)} alt="" className="w-full aspect-square object-cover" />
                                                )}
                                                <div className="absolute top-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    {media.media_type === 'image' && (
                                                        <button
                                                            type="button"
                                                            onClick={() => handleCaptionMedia(media)}
                                                            disabled={captioningMediaId === media.id}
                                                            className="rounded-md bg-black/70 p-1 disabled:opacity-50"
                                                            title={t('生成检索描述', 'Generate search caption')}
                                                        >
                                                            {captioningMediaId === media.id
                                                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                                : <Sparkles className="w-3.5 h-3.5" />}
                                                        </button>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={() => handleDeleteMedia(media)}
                                                        className="rounded-md bg-black/70 p-1"
                                                        title={t('删除', 'Delete')}
                                                    >
                                                        <X className="w-3.5 h-3.5" />
                                                    </button>
                                                </div>
                                                {media.caption ? (
                                                    <div className="absolute inset-x-0 bottom-0 bg-black/75 px-1.5 py-1 text-[10px] text-white/85 line-clamp-2">
                                                        {media.caption}
                                                    </div>
                                                ) : null}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="text-xs text-muted-foreground space-y-1">
                                <div>{t('版权层级', 'License')}: {licenseLabel(selected.license_tier)}</div>
                                <div>{t('来源类型', 'Source type')}: {sourceTypeLabel(selected.source_type)}</div>
                                <div>{t('质量分', 'Quality')}: {Number(selected.quality_score ?? 3).toFixed(1)} / 5 · {t('注入次数', 'Injects')}: {selected.inject_count || 0}</div>
                                {selected.is_eval_gold && <div className="text-amber-300">{t('评测金标', 'Eval gold')}</div>}
                                {selected.copyright_note && <div>{selected.copyright_note}</div>}
                                {selected.source_url && (
                                    <div>
                                        {t('来源', 'Source')}:{' '}
                                        <a href={selected.source_url} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">
                                            {selected.source_url}
                                        </a>
                                    </div>
                                )}
                                {selected.review_note && <div>{t('审核备注', 'Review note')}: {selected.review_note}</div>}
                            </div>

                            <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                                <div className="text-sm font-medium">{t('治理', 'Governance')}</div>
                                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                    <span className="w-16 shrink-0">{t('质量分', 'Quality')}</span>
                                    <input
                                        type="range"
                                        min="0"
                                        max="5"
                                        step="0.5"
                                        value={Number(selected.quality_score ?? 3)}
                                        onChange={(e) => patchSelected({ ...selected, quality_score: Number(e.target.value) })}
                                        className="flex-1"
                                    />
                                    <span className="w-8 text-right">{Number(selected.quality_score ?? 3).toFixed(1)}</span>
                                </label>
                                {isSuperuser && (
                                    <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                                        <input
                                            type="checkbox"
                                            checked={!!selected.is_eval_gold}
                                            onChange={(e) => patchSelected({ ...selected, is_eval_gold: e.target.checked })}
                                        />
                                        {t('评测金标', 'Eval gold')}
                                    </label>
                                )}
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        type="button"
                                        disabled={qualitySaving}
                                        onClick={handleQualitySave}
                                        className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-secondary/40 disabled:opacity-50"
                                    >
                                        {qualitySaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : t('保存评分', 'Save score')}
                                    </button>
                                    {isSuperuser && (
                                        <button
                                            type="button"
                                            onClick={handleCreateEvalCase}
                                            className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-secondary/40"
                                        >
                                            {t('创建评测用例', 'Create eval case')}
                                        </button>
                                    )}
                                </div>
                                {Array.isArray(projectOptions) && projectOptions.length > 0 && (
                                    <div className="flex flex-wrap items-center gap-2 pt-1">
                                        <select
                                            value={collectionProjectId}
                                            onChange={(e) => setCollectionProjectId(e.target.value)}
                                            className="rounded-lg border border-white/10 bg-black/30 px-2 py-1.5 text-xs outline-none"
                                        >
                                            <option value="">{t('选择项目加入收藏', 'Choose project for collection')}</option>
                                            {projectOptions.map((p) => (
                                                <option key={p.id} value={String(p.id)}>{p.title || `#${p.id}`}</option>
                                            ))}
                                        </select>
                                        <button
                                            type="button"
                                            disabled={!collectionProjectId || collectionBusy}
                                            onClick={handleAddToProjectCollection}
                                            className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-secondary/40 disabled:opacity-50"
                                        >
                                            {collectionBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : t('加入收藏集', 'Add to collection')}
                                        </button>
                                    </div>
                                )}
                            </div>

                            <div className="text-xs text-muted-foreground">
                                {t('索引状态', 'Index')}: {indexStatusLabel(selected.index_status)}
                                {selected.indexed_at ? ` · ${selected.indexed_at}` : ''}
                                {selected.index_error ? ` · ${selected.index_error}` : ''}
                            </div>

                            {isSuperuser && (
                                <div className="flex flex-wrap gap-2 pt-2 border-t border-white/5">
                                    <button
                                        type="button"
                                        disabled={reviewing || selected.review_status === 'approved'}
                                        onClick={() => handleReview('approve')}
                                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600/90 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                                    >
                                        {reviewing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                                        {t('通过审核', 'Approve')}
                                    </button>
                                    <button
                                        type="button"
                                        disabled={reviewing || selected.review_status === 'rejected'}
                                        onClick={() => handleReview('reject')}
                                        className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600/90 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                                    >
                                        {reviewing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Ban className="w-3.5 h-3.5" />}
                                        {t('驳回', 'Reject')}
                                    </button>
                                    {selected.review_status === 'approved' && (
                                        <button
                                            type="button"
                                            disabled={reindexing}
                                            onClick={handleReindex}
                                            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs hover:bg-secondary/40 disabled:opacity-50"
                                        >
                                            {reindexing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                                            {t('重建索引', 'Reindex')}
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {showForm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
                    <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-white/10 bg-card p-5 space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="text-lg font-semibold">
                                {editingId ? t('编辑条目', 'Edit entry') : t('新建条目', 'New entry')}
                            </div>
                            <button type="button" onClick={() => setShowForm(false)} className="p-1.5 rounded-lg hover:bg-secondary/50">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('栏目', 'Category')}</span>
                                <select
                                    value={form.category}
                                    onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                >
                                    {CATEGORIES.map((item) => (
                                        <option key={item.id} value={item.id}>{t(item.zh, item.en)}</option>
                                    ))}
                                </select>
                            </label>
                            {form.category === 'plot' && (
                                <label className="space-y-1 text-sm">
                                    <span className="text-muted-foreground">{t('剧情子类', 'Plot subtype')}</span>
                                    <select
                                        value={form.plot_subtype}
                                        onChange={(e) => setForm((prev) => ({ ...prev, plot_subtype: e.target.value }))}
                                        className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                    >
                                        {PLOT_SUBTYPES.filter((item) => item.id).map((item) => (
                                            <option key={item.id} value={item.id}>{t(item.zh, item.en)}</option>
                                        ))}
                                    </select>
                                </label>
                            )}
                            <label className="space-y-1 text-sm sm:col-span-2">
                                <span className="text-muted-foreground">{t('标题', 'Title')}</span>
                                <input
                                    value={form.title}
                                    onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            {!editingId && (
                                <>
                                    <label className="space-y-1 text-sm">
                                        <span className="text-muted-foreground">{t('作品名（可选）', 'Work title (optional)')}</span>
                                        <input
                                            value={form.work_title}
                                            onChange={(e) => setForm((prev) => ({ ...prev, work_title: e.target.value }))}
                                            className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                        />
                                    </label>
                                    <label className="space-y-1 text-sm">
                                        <span className="text-muted-foreground">{t('年份', 'Year')}</span>
                                        <input
                                            value={form.work_year}
                                            onChange={(e) => setForm((prev) => ({ ...prev, work_year: e.target.value }))}
                                            className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                        />
                                    </label>
                                </>
                            )}
                            <label className="space-y-1 text-sm sm:col-span-2">
                                <span className="text-muted-foreground">{t('摘要', 'Summary')}</span>
                                <textarea
                                    value={form.summary}
                                    onChange={(e) => setForm((prev) => ({ ...prev, summary: e.target.value }))}
                                    rows={2}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm sm:col-span-2">
                                <span className="text-muted-foreground">{t('正文 / 可检索描述', 'Body / searchable text')}</span>
                                <textarea
                                    value={form.body_text}
                                    onChange={(e) => setForm((prev) => ({ ...prev, body_text: e.target.value }))}
                                    rows={5}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('标签（逗号分隔）', 'Tags (comma-separated)')}</span>
                                <input
                                    value={form.tags}
                                    onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('风格词', 'Style keywords')}</span>
                                <input
                                    value={form.style_keywords}
                                    onChange={(e) => setForm((prev) => ({ ...prev, style_keywords: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('版权层级', 'License tier')}</span>
                                <select
                                    value={form.license_tier}
                                    onChange={(e) => setForm((prev) => ({ ...prev, license_tier: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                >
                                    {LICENSE_OPTIONS.map((item) => (
                                        <option key={item.id} value={item.id}>{t(item.zh, item.en)}</option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('来源类型', 'Source type')}</span>
                                <select
                                    value={form.source_type}
                                    onChange={(e) => setForm((prev) => ({ ...prev, source_type: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                >
                                    {SOURCE_TYPE_OPTIONS.map((item) => (
                                        <option key={item.id} value={item.id}>{t(item.zh, item.en)}</option>
                                    ))}
                                    <option value="llm">LLM</option>
                                </select>
                            </label>
                            <label className="space-y-1 text-sm sm:col-span-2">
                                <span className="text-muted-foreground">{t('来源 URL', 'Source URL')}</span>
                                <input
                                    value={form.source_url}
                                    onChange={(e) => setForm((prev) => ({ ...prev, source_url: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm sm:col-span-2">
                                <span className="text-muted-foreground">{t('版权备注', 'Copyright note')}</span>
                                <input
                                    value={form.copyright_note}
                                    onChange={(e) => setForm((prev) => ({ ...prev, copyright_note: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                            <button
                                type="button"
                                onClick={() => setShowForm(false)}
                                className="rounded-lg border border-white/10 px-4 py-2 text-sm hover:bg-secondary/40"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                type="button"
                                disabled={saving}
                                onClick={handleSave}
                                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                            >
                                {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                                {t('保存', 'Save')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {showIngest && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
                    <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl border border-white/10 bg-card p-5 space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="text-lg font-semibold">{t('采集入库', 'Ingest to knowledge base')}</div>
                            <button type="button" onClick={() => setShowIngest(false)} className="p-1.5 rounded-lg hover:bg-secondary/50">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="text-xs text-muted-foreground">
                            {t('网络检索或粘贴文本，经 LLM 结构化后生成待审核条目。', 'Web search or paste text; LLM structures pending entries for review.')}
                        </div>

                        <div className="flex gap-2">
                            <button
                                type="button"
                                onClick={() => setIngestForm((prev) => ({ ...prev, mode: 'web' }))}
                                className={`rounded-lg px-3 py-1.5 text-sm border ${ingestForm.mode === 'web' ? 'bg-primary text-primary-foreground border-primary' : 'border-white/10 text-muted-foreground'}`}
                            >
                                {t('网络检索', 'Web search')}
                            </button>
                            <button
                                type="button"
                                onClick={() => setIngestForm((prev) => ({ ...prev, mode: 'llm' }))}
                                className={`rounded-lg px-3 py-1.5 text-sm border ${ingestForm.mode === 'llm' ? 'bg-primary text-primary-foreground border-primary' : 'border-white/10 text-muted-foreground'}`}
                            >
                                {t('粘贴文本', 'Paste text')}
                            </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('栏目', 'Category')}</span>
                                <select
                                    value={ingestForm.category}
                                    onChange={(e) => setIngestForm((prev) => ({ ...prev, category: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                >
                                    {CATEGORIES.map((item) => (
                                        <option key={item.id} value={item.id}>{t(item.zh, item.en)}</option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('最多条目', 'Max entries')}</span>
                                <input
                                    type="number"
                                    min={1}
                                    max={12}
                                    value={ingestForm.max_entries}
                                    onChange={(e) => setIngestForm((prev) => ({ ...prev, max_entries: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            {ingestForm.mode === 'web' ? (
                                <label className="space-y-1 text-sm sm:col-span-2">
                                    <span className="text-muted-foreground">{t('采集主题', 'Topic')}</span>
                                    <input
                                        value={ingestForm.topic}
                                        onChange={(e) => setIngestForm((prev) => ({ ...prev, topic: e.target.value }))}
                                        placeholder={t('如：古装权谋 女主定妆 / 雨夜对峙桥段', 'e.g. palace intrigue heroine look / rainy confrontation trope')}
                                        className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                    />
                                </label>
                            ) : (
                                <label className="space-y-1 text-sm sm:col-span-2">
                                    <span className="text-muted-foreground">{t('源文本', 'Source text')}</span>
                                    <textarea
                                        value={ingestForm.source_text}
                                        onChange={(e) => setIngestForm((prev) => ({ ...prev, source_text: e.target.value }))}
                                        rows={8}
                                        placeholder={t('粘贴剧情介绍、造型描述、桥段笔记等…', 'Paste synopsis, costume notes, trope notes…')}
                                        className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                    />
                                </label>
                            )}
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('作品名（可选）', 'Work title (optional)')}</span>
                                <input
                                    value={ingestForm.work_title}
                                    onChange={(e) => setIngestForm((prev) => ({ ...prev, work_title: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm">
                                <span className="text-muted-foreground">{t('年份', 'Year')}</span>
                                <input
                                    value={ingestForm.work_year}
                                    onChange={(e) => setIngestForm((prev) => ({ ...prev, work_year: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                />
                            </label>
                            <label className="space-y-1 text-sm sm:col-span-2">
                                <span className="text-muted-foreground">{t('输出语言', 'Output language')}</span>
                                <select
                                    value={ingestForm.language || 'zh'}
                                    onChange={(e) => setIngestForm((prev) => ({ ...prev, language: e.target.value }))}
                                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 outline-none focus:border-primary/40"
                                >
                                    <option value="zh">{t('中文', 'Chinese')}</option>
                                    <option value="en">{t('英文', 'English')}</option>
                                </select>
                            </label>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                            <button
                                type="button"
                                onClick={() => setShowIngest(false)}
                                className="rounded-lg border border-white/10 px-4 py-2 text-sm hover:bg-secondary/40"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                type="button"
                                disabled={ingesting}
                                onClick={handleIngest}
                                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                            >
                                {ingesting && <Loader2 className="w-4 h-4 animate-spin" />}
                                {ingesting ? t('采集中…', 'Ingesting…') : t('开始采集', 'Start ingest')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default KnowledgeLibrary;
