import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Eye, Image as ImageIcon, Loader2, Plus, RefreshCw, Replace, Trash2, Upload, Video, X } from 'lucide-react';
import { SafeImage, getFullUrl } from '../editorHelpers';
import {
    analyzePromoCatalogAsset,
    createPromoCatalogAsset,
    deletePromoCatalogAsset,
    fetchPromoCatalogAssets,
    updatePromoCatalogAsset,
    uploadAsset,
} from '../../../services/api';

export const PROMO_ASSET_TYPES = [
    { value: 'product', zh: '产品', en: 'Product' },
    { value: 'character', zh: '角色', en: 'Character' },
    { value: 'scene', zh: '场景', en: 'Scene' },
    { value: 'prop', zh: '道具', en: 'Prop' },
];

const SCENE_VIEW_DIRECTIONS = [
    { value: '', zh: '未标方向（默认正面）', en: 'Unlabeled (front)' },
    { value: 'north', zh: '北壁', en: 'North wall' },
    { value: 'east', zh: '东壁', en: 'East wall' },
    { value: 'south', zh: '南壁', en: 'South wall' },
    { value: 'west', zh: '西壁', en: 'West wall' },
];
const SCENE_GROUP_DIRECTION_CYCLE = ['north', 'east', 'south', 'west'];

const sceneGroupIdOf = (asset) => String(asset?.scene_group_id || asset?.extra_info?.scene_group_id || '').trim();
const viewDirectionOf = (asset) => String(asset?.view_direction || asset?.extra_info?.view_direction || '').trim();
const isSceneAsset = (asset) => (asset?.asset_type || asset?.image_type) === 'scene';
const directionLabel = (value, t) => {
    const found = SCENE_VIEW_DIRECTIONS.find((item) => item.value === value);
    return found ? t(found.zh, found.en) : t('未标方向', 'Unlabeled');
};

export const PROMO_MEDIA_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov';
const WALL_IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp';
const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'webp'];
const VIDEO_EXTS = ['mp4', 'webm', 'mov'];
const MAX_MB = 40;

const ANALYSIS_STATUS_PENDING = 'pending';
const ANALYSIS_STATUS_SUCCESS = 'success';
const ANALYSIS_STATUS_FAILED = 'failed';
const ANALYSIS_STATUS_ANALYZING = 'analyzing';

const normalizeAnalysisStatus = (value, fallback = ANALYSIS_STATUS_PENDING) => {
    const raw = String(value || '').trim().toLowerCase();
    if (raw === ANALYSIS_STATUS_SUCCESS || raw === 'ok' || raw === 'done') return ANALYSIS_STATUS_SUCCESS;
    if (raw === ANALYSIS_STATUS_FAILED || raw === 'error' || raw === 'fail') return ANALYSIS_STATUS_FAILED;
    if (raw === ANALYSIS_STATUS_ANALYZING || raw === 'running') return ANALYSIS_STATUS_ANALYZING;
    if (raw === ANALYSIS_STATUS_PENDING || raw === 'unparsed' || raw === '未解析') return ANALYSIS_STATUS_PENDING;
    return fallback;
};

const analysisStatusLabel = (status, t) => {
    if (status === ANALYSIS_STATUS_SUCCESS) return t('成功', 'Success');
    if (status === ANALYSIS_STATUS_FAILED) return t('失败', 'Failed');
    if (status === ANALYSIS_STATUS_ANALYZING) return t('解析中', 'Analyzing');
    return t('未解析', 'Unparsed');
};

const analysisStatusClass = (status) => {
    if (status === ANALYSIS_STATUS_SUCCESS) return 'bg-emerald-500/20 text-emerald-200';
    if (status === ANALYSIS_STATUS_FAILED) return 'bg-red-500/20 text-red-200';
    if (status === ANALYSIS_STATUS_ANALYZING) return 'bg-sky-500/20 text-sky-100';
    return 'bg-white/10 text-white/70';
};

const isAcceptedMedia = (file) => {
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    const type = String(file?.type || '').toLowerCase();
    return IMAGE_EXTS.includes(ext) || VIDEO_EXTS.includes(ext) || type.startsWith('image/') || type.startsWith('video/');
};

const isWallImage = (file) => {
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    const type = String(file?.type || '').toLowerCase();
    return IMAGE_EXTS.includes(ext) || (type.startsWith('image/') && !type.startsWith('image/gif'));
};

const mediaKindOf = (file) => {
    const type = String(file?.type || '').toLowerCase();
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    if (type.startsWith('video/') || VIDEO_EXTS.includes(ext)) return 'video';
    return 'image';
};

const newImageId = () => `promo-cat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const analysisForAsset = (asset) => {
    const data = asset?.image_asset_analysis && typeof asset.image_asset_analysis === 'object'
        ? asset.image_asset_analysis
        : (asset?.extra_info?.image_asset_analysis || {});
    return data && typeof data === 'object' ? data : {};
};

const analysisRowForAsset = (asset) => {
    const analysis = analysisForAsset(asset);
    const imageId = String(asset?.image_id || '').trim();
    const list = Array.isArray(analysis.image_list) ? analysis.image_list : [];
    return list.find((row) => String(row?.image_id || '').trim() === imageId) || list[0] || {};
};

const hasAnalysisText = (asset) => {
    const analysis = analysisForAsset(asset);
    const row = analysisRowForAsset(asset);
    const subjects = Array.isArray(analysis.rebuild_subjects) ? analysis.rebuild_subjects : [];
    return Boolean(
        String(analysis.global_visual_summary || '').trim()
        || String(row.content_desc || '').trim()
        || String(row.rebuild_brief || '').trim()
        || subjects.length
    );
};

const DetailLine = ({ label, value }) => {
    const text = String(value || '').trim();
    if (!text || text === '无' || text === '未见') return null;
    return (
        <div className="space-y-0.5">
            <div className="text-[11px] text-white/45">{label}</div>
            <div className="text-xs text-white/85 whitespace-pre-wrap">{text}</div>
        </div>
    );
};

export default function PromoCatalogAssets({
    t,
    ownerKind,
    ownerId,
    disabled = false,
    title,
}) {
    const [assets, setAssets] = useState([]);
    const [busy, setBusy] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [previewAsset, setPreviewAsset] = useState(null);
    const [groupDrafts, setGroupDrafts] = useState({});
    const fileInputRef = useRef(null);
    const sceneGroupInputRef = useRef(null);
    const replaceInputRef = useRef(null);
    const replaceTargetRef = useRef(null);
    const wallFileInputRef = useRef(null);
    const wallPickRef = useRef(null);
    const assetsRef = useRef([]);
    const analyzeFlightRef = useRef(0);
    const queuedAnalyzeRef = useRef(null);
    const analyzeDebounceRef = useRef(null);

    useEffect(() => {
        assetsRef.current = assets;
    }, [assets]);

    useEffect(() => () => {
        if (analyzeDebounceRef.current) clearTimeout(analyzeDebounceRef.current);
    }, []);

    const load = useCallback(async () => {
        if (!ownerId) {
            setAssets([]);
            return;
        }
        try {
            const rows = await fetchPromoCatalogAssets({ owner_kind: ownerKind, owner_entity_id: Number(ownerId) });
            const incoming = Array.isArray(rows) ? rows : [];
            setAssets((prev) => {
                const analyzing = new Set(
                    prev
                        .filter((item) => normalizeAnalysisStatus(item.analysis_status) === ANALYSIS_STATUS_ANALYZING)
                        .map((item) => Number(item.id))
                );
                return incoming.map((row) => (
                    analyzing.has(Number(row.id))
                        ? { ...row, analysis_status: ANALYSIS_STATUS_ANALYZING, analysis_error: '' }
                        : row
                ));
            });
        } catch (err) {
            console.error('[PromoCatalogAssets] load failed', err);
        }
    }, [ownerId, ownerKind]);

    useEffect(() => {
        load();
    }, [load]);

    useEffect(() => {
        const onFocus = () => load();
        const onVisible = () => {
            if (document.visibilityState === 'visible') load();
        };
        window.addEventListener('focus', onFocus);
        document.addEventListener('visibilitychange', onVisible);
        return () => {
            window.removeEventListener('focus', onFocus);
            document.removeEventListener('visibilitychange', onVisible);
        };
    }, [load]);

    const sceneGroupMates = (asset, list = assetsRef.current || []) => {
        const gid = sceneGroupIdOf(asset);
        if (!gid || !isSceneAsset(asset)) return [asset];
        const mates = list.filter((item) => isSceneAsset(item) && sceneGroupIdOf(item) === gid);
        return mates.length ? mates : [asset];
    };

    const latestAsset = (asset) => (
        (assetsRef.current || []).find((item) => Number(item.id) === Number(asset?.id)) || asset
    );

    const publishAssets = (next, preview) => {
        assetsRef.current = next;
        setAssets(next);
        if (preview !== undefined) setPreviewAsset(preview);
    };

    const analyzeOne = async (asset, options = {}) => {
        if (!asset?.id || disabled) return;
        const current = latestAsset(asset);
        if (!(current.img_url || current.file_url)) return;
        if (analyzeFlightRef.current > 0) {
            if (options.queue) queuedAnalyzeRef.current = current;
            return;
        }
        analyzeFlightRef.current += 1;
        const mates = sceneGroupMates(current);
        const mateIds = new Set(mates.map((item) => Number(item.id)));
        const marked = (assetsRef.current || []).map((item) => (
            mateIds.has(Number(item.id))
                ? { ...item, analysis_status: ANALYSIS_STATUS_ANALYZING, analysis_error: '' }
                : item
        ));
        publishAssets(
            marked,
            undefined,
        );
        setPreviewAsset((prev) => (
            prev && mateIds.has(Number(prev.id))
                ? { ...prev, analysis_status: ANALYSIS_STATUS_ANALYZING, analysis_error: '' }
                : prev
        ));
        try {
            const data = await analyzePromoCatalogAsset(current.id, {});
            const returned = Array.isArray(data?.group_assets) ? data.group_assets : [];
            const byId = new Map(returned.map((item) => [Number(item.id), item]));
            const applyRow = (item) => {
                const nextRow = byId.get(Number(item.id));
                if (!nextRow && Number(item.id) !== Number(current.id)) return item;
                const source = nextRow || { ...item, ...data };
                return {
                    ...item,
                    ...source,
                    analysis_status: normalizeAnalysisStatus(source.analysis_status, ANALYSIS_STATUS_FAILED),
                    analysis_error: String(source.analysis_error || '').trim(),
                    image_asset_analysis: source.image_asset_analysis || item.image_asset_analysis || {},
                };
            };
            const completed = (assetsRef.current || []).map(applyRow);
            assetsRef.current = completed;
            setAssets((prev) => {
                const next = prev.map(applyRow);
                assetsRef.current = next;
                return next;
            });
            setPreviewAsset((prev) => (prev ? applyRow(prev) : prev));
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || t('解析失败', 'Analysis failed');
            const failed = (assetsRef.current || []).map((item) => (
                mateIds.has(Number(item.id))
                    ? { ...item, analysis_status: ANALYSIS_STATUS_FAILED, analysis_error: String(message) }
                    : item
            ));
            assetsRef.current = failed;
            setAssets((prev) => {
                const next = prev.map((item) => (
                    mateIds.has(Number(item.id))
                        ? { ...item, analysis_status: ANALYSIS_STATUS_FAILED, analysis_error: String(message) }
                        : item
                ));
                assetsRef.current = next;
                return next;
            });
            setPreviewAsset((prev) => (
                prev && mateIds.has(Number(prev.id))
                    ? { ...prev, analysis_status: ANALYSIS_STATUS_FAILED, analysis_error: String(message) }
                    : prev
            ));
        } finally {
            analyzeFlightRef.current = Math.max(0, analyzeFlightRef.current - 1);
            const pending = queuedAnalyzeRef.current;
            if (pending && !analyzeDebounceRef.current && analyzeFlightRef.current === 0) {
                queuedAnalyzeRef.current = null;
                await analyzeOne(latestAsset(pending), { queue: true });
            }
        }
    };

    const scheduleGroupAnalyze = (asset) => {
        queuedAnalyzeRef.current = latestAsset(asset);
        if (analyzeDebounceRef.current) clearTimeout(analyzeDebounceRef.current);
        analyzeDebounceRef.current = setTimeout(() => {
            analyzeDebounceRef.current = null;
            const target = queuedAnalyzeRef.current;
            queuedAnalyzeRef.current = null;
            if (target) analyzeOne(latestAsset(target), { queue: true });
        }, 500);
    };

    const analyzePending = async () => {
        const targets = (assetsRef.current || []).filter((item) => {
            const status = normalizeAnalysisStatus(item.analysis_status);
            return (item.img_url || item.file_url) && status !== ANALYSIS_STATUS_SUCCESS && status !== ANALYSIS_STATUS_ANALYZING;
        });
        const seenGroups = new Set();
        for (const item of targets) {
            const gid = sceneGroupIdOf(item);
            if (isSceneAsset(item) && gid) {
                if (seenGroups.has(gid)) continue;
                seenGroups.add(gid);
            }
            await analyzeOne(item);
        }
    };

    const uploadOne = async (file, options = {}) => {
        if (!ownerId || disabled) return null;
        if (!isAcceptedMedia(file)) {
            alert(t('仅支持 jpg / png / webp / mp4 / webm / mov', 'Only jpg / png / webp / mp4 / webm / mov'));
            return null;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
            alert(t(`单文件不超过 ${MAX_MB}MB`, `Max ${MAX_MB}MB per file`));
            return null;
        }
        const imageId = newImageId();
        const mediaKind = mediaKindOf(file);
        const manageBusy = options.manageBusy !== false;
        if (manageBusy) setBusy(true);
        try {
            const uploaded = await uploadAsset(file, {
                type: mediaKind,
                asset_type: 'promo_catalog_asset',
                remark: `promo_catalog:${ownerKind}:${ownerId}:${imageId}`,
            });
            const url = String(uploaded?.url || '').trim();
            if (!url) throw new Error(t('上传成功但未返回地址', 'Upload succeeded but no URL returned'));
            const created = await createPromoCatalogAsset({
                owner_kind: ownerKind,
                owner_entity_id: Number(ownerId),
                media_kind: mediaKind,
                asset_type: options.assetType || 'product',
                image_id: imageId,
                file_url: url,
                img_url: url,
                object_name: options.objectName || file.name.replace(/\.[^.]+$/, ''),
                extra_info: options.extraInfo || undefined,
            });
            setAssets((prev) => [created, ...prev.filter((item) => Number(item.id) !== Number(created.id))]);
            assetsRef.current = [created, ...(assetsRef.current || []).filter((item) => Number(item.id) !== Number(created.id))];
            if (options.autoAnalyze !== false) analyzeOne(created);
            return created;
        } catch (err) {
            alert(err?.response?.data?.detail || err?.message || t('上传失败', 'Upload failed'));
            return null;
        } finally {
            if (manageBusy) setBusy(false);
        }
    };

    const replacePhoto = async (file) => {
        const asset = replaceTargetRef.current;
        replaceTargetRef.current = null;
        if (!asset?.id || !file || disabled) return;
        if (!isAcceptedMedia(file)) {
            alert(t('仅支持 jpg / png / webp / mp4 / webm / mov', 'Only jpg / png / webp / mp4 / webm / mov'));
            return;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
            alert(t(`单文件不超过 ${MAX_MB}MB`, `Max ${MAX_MB}MB per file`));
            return;
        }
        const mediaKind = mediaKindOf(file);
        setBusy(true);
        try {
            const uploaded = await uploadAsset(file, {
                type: mediaKind,
                asset_type: 'promo_catalog_asset',
                remark: `promo_catalog_replace:${ownerKind}:${ownerId}:${asset.image_id || asset.id}`,
            });
            const url = String(uploaded?.url || '').trim();
            if (!url) throw new Error(t('上传成功但未返回地址', 'Upload succeeded but no URL returned'));
            const updated = await updatePromoCatalogAsset(asset.id, {
                file_url: url,
                img_url: url,
                media_kind: mediaKind,
            });
            const next = {
                ...asset,
                ...updated,
                file_url: url,
                img_url: url,
                media_kind: mediaKind,
                analysis_status: ANALYSIS_STATUS_PENDING,
                analysis_error: '',
                image_asset_analysis: {},
            };
            const list = (assetsRef.current || []).map((item) => (
                Number(item.id) === Number(asset.id) ? next : item
            ));
            assetsRef.current = list;
            setAssets(list);
            setPreviewAsset((prev) => (prev && Number(prev.id) === Number(asset.id) ? next : prev));
            setBusy(false);
            await analyzeOne(next);
        } catch (err) {
            alert(err?.response?.data?.detail || err?.message || t('更换失败', 'Replace failed'));
        } finally {
            setBusy(false);
        }
    };

    const handleFiles = async (fileList) => {
        const files = Array.from(fileList || []);
        for (const file of files) {
            await uploadOne(file);
        }
    };

    const handleSceneGroupFiles = async (fileList) => {
        const files = Array.from(fileList || []);
        if (!files.length || !ownerId || disabled) return;
        const groupId = `scene-${Date.now()}`;
        const baseName = String(files[0]?.name || '场景').replace(/\.[^.]+$/, '');
        setBusy(true);
        const created = [];
        try {
            for (let index = 0; index < files.length; index += 1) {
                const row = await uploadOne(files[index], {
                    manageBusy: false,
                    autoAnalyze: false,
                    assetType: 'scene',
                    objectName: baseName,
                    extraInfo: {
                        scene_group_id: groupId,
                        view_direction: SCENE_GROUP_DIRECTION_CYCLE[index] || '',
                    },
                });
                if (row) created.push(row);
            }
        } finally {
            setBusy(false);
        }
        if (created[0]) await analyzeOne(created[0]);
    };

    const commitSceneMeta = async (asset, next) => {
        const current = latestAsset(asset);
        const extra = { ...(current.extra_info || {}) };
        if (Object.prototype.hasOwnProperty.call(next, 'view_direction')) extra.view_direction = next.view_direction;
        if (Object.prototype.hasOwnProperty.call(next, 'scene_group_id')) extra.scene_group_id = next.scene_group_id;
        const patch = {
            extra_info: extra,
            view_direction: extra.view_direction || '',
            scene_group_id: extra.scene_group_id || '',
        };
        const apply = (list, row) => list.map((item) => (
            Number(item.id) === Number(current.id) ? { ...item, ...row } : item
        ));
        assetsRef.current = apply(assetsRef.current || [], patch);
        setAssets(assetsRef.current);
        setPreviewAsset((prev) => (prev && Number(prev.id) === Number(current.id) ? { ...prev, ...patch } : prev));
        const updated = await updatePromoCatalogAsset(current.id, patch);
        const merged = apply(assetsRef.current || [], updated);
        assetsRef.current = merged;
        setAssets(merged);
        const saved = merged.find((item) => Number(item.id) === Number(current.id)) || { ...current, ...updated };
        setPreviewAsset((prev) => (prev && Number(prev.id) === Number(current.id) ? { ...prev, ...saved } : prev));
        return saved;
    };

    const addWallPhoto = async (anchor, direction, file) => {
        if (!isWallImage(file)) {
            alert(t('壁面只补图片：jpg / png / webp', 'Walls take jpg / png / webp only'));
            return;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
            alert(t(`单文件不超过 ${MAX_MB}MB`, `Max ${MAX_MB}MB per file`));
            return;
        }
        let current = latestAsset(anchor);
        if (!isSceneAsset(current) || !direction) return;
        if (!viewDirectionOf(current)) {
            alert(t('先选定当前这张正对的壁，再补其他壁。', 'Label this photo’s wall before adding another.'));
            return;
        }
        const taken = new Set(sceneGroupMates(current).map((item) => viewDirectionOf(item)).filter(Boolean));
        if (taken.has(direction)) {
            alert(t('这面墙已经有照片。', 'This wall already has a photo.'));
            return;
        }
        let gid = sceneGroupIdOf(current);
        if (!gid) {
            gid = `scene-${Date.now()}`;
            current = await commitSceneMeta(current, {
                scene_group_id: gid,
                view_direction: viewDirectionOf(current),
            });
            gid = sceneGroupIdOf(current) || gid;
        }
        const created = await uploadOne(file, {
            manageBusy: false,
            autoAnalyze: false,
            assetType: 'scene',
            objectName: current.object_name || String(file.name || '场景').replace(/\.[^.]+$/, ''),
            extraInfo: {
                scene_group_id: gid,
                view_direction: direction,
            },
        });
        if (created) scheduleGroupAnalyze(created);
    };

    const openWallUpload = (asset, direction) => {
        if (disabled || busy || !asset?.id || !direction) return;
        wallPickRef.current = { assetId: asset.id, direction };
        wallFileInputRef.current?.click();
    };

    const handleWallFile = async (file) => {
        const pick = wallPickRef.current;
        wallPickRef.current = null;
        if (!pick || !file) return;
        const asset = latestAsset({ id: pick.assetId });
        if (!asset?.id) return;
        setBusy(true);
        try {
            await addWallPhoto(asset, pick.direction, file);
        } catch (err) {
            alert(err?.response?.data?.detail || err?.message || t('补壁失败', 'Could not add this wall'));
        } finally {
            setBusy(false);
        }
    };

    const patchSceneMeta = (asset, next) => {
        const extra = { ...(asset.extra_info || {}) };
        if (Object.prototype.hasOwnProperty.call(next, 'view_direction')) extra.view_direction = next.view_direction;
        if (Object.prototype.hasOwnProperty.call(next, 'scene_group_id')) extra.scene_group_id = next.scene_group_id;
        patchAsset(asset, {
            extra_info: extra,
            view_direction: extra.view_direction || '',
            scene_group_id: extra.scene_group_id || '',
            analysis_status: ANALYSIS_STATUS_PENDING,
            analysis_error: '',
            image_asset_analysis: {},
        });
    };

    const patchAsset = async (asset, patch) => {
        if (!asset?.id || disabled) return;
        const apply = (list, row) => list.map((item) => (
            Number(item.id) === Number(asset.id) ? { ...item, ...row } : item
        ));
        assetsRef.current = apply(assetsRef.current || [], patch);
        setAssets((prev) => {
            const next = apply(prev, patch);
            assetsRef.current = next;
            return next;
        });
        setPreviewAsset((prev) => (prev && Number(prev.id) === Number(asset.id) ? { ...prev, ...patch } : prev));
        try {
            const updated = await updatePromoCatalogAsset(asset.id, patch);
            assetsRef.current = apply(assetsRef.current || [], updated);
            setAssets((prev) => {
                const next = apply(prev, updated);
                assetsRef.current = next;
                return next;
            });
            setPreviewAsset((prev) => (prev && Number(prev.id) === Number(asset.id) ? { ...prev, ...updated } : prev));
        } catch (err) {
            console.error('[PromoCatalogAssets] update failed', err);
        }
    };

    const removeAsset = async (asset) => {
        if (!asset?.id || disabled) return;
        try {
            await deletePromoCatalogAsset(asset.id);
            setAssets((prev) => prev.filter((item) => Number(item.id) !== Number(asset.id)));
            setPreviewAsset((prev) => (prev && Number(prev.id) === Number(asset.id) ? null : prev));
        } catch (err) {
            alert(err?.response?.data?.detail || err?.message || t('删除失败', 'Delete failed'));
        }
    };

    const renderWallExtras = (asset) => {
        if (!isSceneAsset(asset)) return null;
        if (!viewDirectionOf(asset)) {
            return (
                <div className="text-[11px] text-white/45">
                    {t('先选定这张正对的壁，再补其他壁。补上后会重新解析。', 'Label this photo’s wall, then add the others. Adding a wall re-analyzes the room.')}
                </div>
            );
        }
        const mates = sceneGroupMates(asset, assets);
        const missing = SCENE_GROUP_DIRECTION_CYCLE.filter((dir) => !mates.some((item) => viewDirectionOf(item) === dir));
        if (!missing.length) return null;
        return (
            <div className="space-y-1">
                <div className="text-[11px] text-white/45">{t('补充其他壁，补完会重新解析同一场景。', 'Add the other walls. The room is analyzed again.')}</div>
                <div className="flex flex-wrap gap-1">
                    {missing.map((dir) => (
                        <button
                            key={dir}
                            type="button"
                            disabled={disabled || busy}
                            onClick={() => openWallUpload(asset, dir)}
                            className="text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 inline-flex items-center gap-1"
                        >
                            <Plus className="w-3 h-3" /> {directionLabel(dir, t)}
                        </button>
                    ))}
                </div>
            </div>
        );
    };

    if (!ownerId) {
        return (
            <div className="text-xs text-white/40">
                {t('选择后可管理该主体的全部素材。宣传片项目只勾选要用的子集，不会自动用完全库。', 'Manage this subject’s full library here. Promo projects pick a subset and do not auto-use the whole set.')}
            </div>
        );
    }

    const pendingCount = assets.filter((item) => {
        const status = normalizeAnalysisStatus(item.analysis_status);
        return (item.img_url || item.file_url) && status !== ANALYSIS_STATUS_SUCCESS && status !== ANALYSIS_STATUS_ANALYZING;
    }).length;

    return (
        <div className="space-y-2 pt-2 border-t border-white/5">
            <div className="flex items-center justify-between gap-2">
                <h5 className="text-sm font-semibold text-white">{title || t('关联素材', 'Linked assets')}{assets.length ? t(`（${assets.length}）`, ` (${assets.length})`) : ''}</h5>
                {pendingCount > 0 ? (
                    <button
                        type="button"
                        disabled={disabled || busy}
                        onClick={analyzePending}
                        className="text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                    >
                        <RefreshCw className="w-3 h-3" /> {t('解析未解析/失败', 'Retry unparsed / failed')}
                    </button>
                ) : null}
            </div>
            <div
                className={`border border-dashed rounded-lg px-3 py-4 text-center cursor-pointer transition-colors ${dragOver ? 'border-primary bg-primary/10' : 'border-white/15 hover:border-white/30'} ${disabled || busy ? 'opacity-50 pointer-events-none' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    handleFiles(e.dataTransfer.files);
                }}
            >
                <Upload className="w-4 h-4 mx-auto mb-1 text-white/70" />
                <div className="text-xs text-white/80">{t('拖拽或点击上传图片 / 视频', 'Drop or click to upload images / videos')}</div>
                <div className="text-[11px] text-muted-foreground mt-1">{t(`jpg / png / webp / mp4 / webm / mov，单文件不超过 ${MAX_MB}MB`, `jpg / png / webp / mp4 / webm / mov, max ${MAX_MB}MB`)}</div>
            </div>
            <button
                type="button"
                disabled={disabled || busy}
                onClick={() => sceneGroupInputRef.current?.click()}
                className="w-full text-xs px-3 py-2 rounded-lg border border-white/15 hover:border-white/30 disabled:opacity-40"
            >
                {t('上传场景组（多张，按北、东、南、西标注）', 'Upload a scene group (north, east, south, west)')}
                <div className="text-[11px] text-muted-foreground mt-1">{t('第1张北壁，第2张东壁，第3张南壁，第4张西壁。已有场景可再补缺的壁，补完会重新解析。', '1st north, 2nd east, 3rd south, 4th west. An existing scene can gain the missing walls, then the room is analyzed again.')}</div>
            </button>
            <input ref={fileInputRef} type="file" accept={PROMO_MEDIA_ACCEPT} multiple className="hidden" onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }} />
            <input ref={sceneGroupInputRef} type="file" accept={PROMO_MEDIA_ACCEPT} multiple className="hidden" onChange={(e) => { handleSceneGroupFiles(e.target.files); e.target.value = ''; }} />
            <input
                ref={wallFileInputRef}
                type="file"
                accept={WALL_IMAGE_ACCEPT}
                className="hidden"
                onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleWallFile(file);
                    e.target.value = '';
                }}
            />
            <input
                ref={replaceInputRef}
                type="file"
                accept={PROMO_MEDIA_ACCEPT}
                className="hidden"
                onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) replacePhoto(file);
                    e.target.value = '';
                }}
            />
            {assets.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {assets.map((asset) => {
                        const rawUrl = asset.img_url || asset.file_url;
                        const url = getFullUrl(rawUrl);
                        const isVideo = String(asset.media_kind || '') === 'video';
                        const status = normalizeAnalysisStatus(asset.analysis_status);
                        return (
                            <div key={asset.id || asset.image_id} className="bg-black/30 border border-white/10 rounded-lg overflow-hidden">
                                <div
                                    className="relative h-28 bg-black/40 cursor-zoom-in"
                                    onClick={() => setPreviewAsset(asset)}
                                >
                                    {rawUrl && !isVideo ? (
                                        <SafeImage src={rawUrl} alt={asset.object_name || 'asset'} className="w-full h-full object-cover" />
                                    ) : url && isVideo ? (
                                        <video src={url} className="w-full h-full object-cover" muted />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-white/30">
                                            {isVideo ? <Video className="w-7 h-7" /> : <ImageIcon className="w-7 h-7" />}
                                        </div>
                                    )}
                                    {isSceneAsset(asset) && viewDirectionOf(asset) ? (
                                        <div className="absolute top-2 left-2 text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white">
                                            {directionLabel(viewDirectionOf(asset), t)}
                                        </div>
                                    ) : null}
                                    {isSceneAsset(asset) && sceneGroupIdOf(asset) ? (
                                        <div className="absolute bottom-2 left-2 max-w-[70%] truncate text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white/80">
                                            {sceneGroupIdOf(asset)}
                                        </div>
                                    ) : null}
                                    <div className={`absolute top-2 right-2 text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1 ${analysisStatusClass(status)}`}>
                                        {status === ANALYSIS_STATUS_ANALYZING ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                        {analysisStatusLabel(status, t)}
                                    </div>
                                </div>
                                <div className="p-2 space-y-1.5">
                                    <select
                                        className="w-full bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs"
                                        value={asset.asset_type || asset.image_type || 'product'}
                                        disabled={disabled}
                                        onChange={(e) => patchAsset(asset, { asset_type: e.target.value })}
                                    >
                                        {PROMO_ASSET_TYPES.map((opt) => (
                                            <option key={opt.value} value={opt.value}>{t(opt.zh, opt.en)}</option>
                                        ))}
                                    </select>
                                    <input
                                        className="w-full bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs"
                                        value={asset.object_name || ''}
                                        disabled={disabled}
                                        onChange={(e) => patchAsset(asset, { object_name: e.target.value })}
                                        placeholder={t('命名，如主视觉 / 厨师', 'Name, e.g. hero / chef')}
                                    />
                                    {isSceneAsset(asset) ? (
                                        <>
                                            <select
                                                className="w-full bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs"
                                                value={viewDirectionOf(asset)}
                                                disabled={disabled || status === ANALYSIS_STATUS_ANALYZING}
                                                onChange={(e) => patchSceneMeta(asset, { view_direction: e.target.value })}
                                            >
                                                {SCENE_VIEW_DIRECTIONS.map((opt) => (
                                                    <option key={opt.value || 'unset'} value={opt.value}>{t(opt.zh, opt.en)}</option>
                                                ))}
                                            </select>
                                            <input
                                                className="w-full bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs"
                                                value={groupDrafts[asset.id] ?? sceneGroupIdOf(asset)}
                                                disabled={disabled || status === ANALYSIS_STATUS_ANALYZING}
                                                onChange={(e) => setGroupDrafts((prev) => ({ ...prev, [asset.id]: e.target.value }))}
                                                onBlur={(e) => {
                                                    const value = e.target.value.trim();
                                                    setGroupDrafts((prev) => {
                                                        const next = { ...prev };
                                                        delete next[asset.id];
                                                        return next;
                                                    });
                                                    if (value === sceneGroupIdOf(asset)) return;
                                                    patchSceneMeta(asset, { scene_group_id: value });
                                                }}
                                                placeholder={t('场景组名，同组填同一个', 'Scene group, same name joins photos')}
                                            />
                                            {renderWallExtras(asset)}
                                        </>
                                    ) : null}
                                    {status === ANALYSIS_STATUS_FAILED && asset.analysis_error ? (
                                        <div className="text-[11px] text-red-300 break-words">{asset.analysis_error}</div>
                                    ) : null}
                                    <div className="flex flex-wrap gap-1.5">
                                        <button
                                            type="button"
                                            className="flex-1 text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 flex items-center justify-center gap-1"
                                            onClick={() => setPreviewAsset(asset)}
                                        >
                                            <Eye className="w-3 h-3" /> {t('查看', 'View')}
                                        </button>
                                        <button
                                            type="button"
                                            className="flex-1 text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center justify-center gap-1"
                                            disabled={disabled || busy || status === ANALYSIS_STATUS_ANALYZING}
                                            title={t('更换后会自动重新解析', 'Re-analyzes automatically after replace')}
                                            onClick={() => {
                                                replaceTargetRef.current = asset;
                                                replaceInputRef.current?.click();
                                            }}
                                        >
                                            <Replace className="w-3 h-3" /> {t('更换照片', 'Replace photo')}
                                        </button>
                                        <button
                                            type="button"
                                            className="flex-1 text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center justify-center gap-1"
                                            disabled={disabled || !rawUrl || status === ANALYSIS_STATUS_ANALYZING}
                                            onClick={() => analyzeOne(asset)}
                                        >
                                            {status === ANALYSIS_STATUS_ANALYZING ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                            {t('重新解析', 'Re-analyze')}
                                        </button>
                                        <button type="button" className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-200 hover:bg-red-500/30 flex items-center justify-center gap-1" onClick={() => removeAsset(asset)} disabled={disabled}>
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="text-xs text-muted-foreground">{t('可先不上传。宣传片项目内上传的素材也会出现在这里，供之后的项目勾选。', 'Assets are optional. Uploads from promo projects also land here for later films to pick.')}</div>
            )}
            {previewAsset ? (
                <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 sm:p-6" onClick={() => setPreviewAsset(null)}>
                    <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-[#111827] border border-white/10 rounded-2xl p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
                        <button type="button" className="absolute top-3 right-3 text-white/70 hover:text-white" onClick={() => setPreviewAsset(null)}>
                            <X className="w-5 h-5" />
                        </button>
                        <div className="pr-8">
                            <div className="text-sm font-semibold text-white">{previewAsset.object_name || t('未命名素材', 'Untitled asset')}</div>
                            <div className="text-[11px] text-white/50 mt-0.5">
                                {previewAsset.media_kind || 'image'} · {previewAsset.asset_type || previewAsset.image_type || 'product'}
                                {isSceneAsset(previewAsset) ? ` · ${directionLabel(viewDirectionOf(previewAsset), t)}` : ''}
                                {isSceneAsset(previewAsset) && sceneGroupIdOf(previewAsset) ? ` · ${sceneGroupIdOf(previewAsset)}` : ''}
                            </div>
                        </div>
                        <div className="bg-black/40 rounded-xl overflow-hidden max-h-[46vh] flex items-center justify-center">
                            {String(previewAsset.media_kind || '') === 'video' ? (
                                <video src={getFullUrl(previewAsset.img_url || previewAsset.file_url)} className="w-full max-h-[46vh] object-contain" controls />
                            ) : (
                                <SafeImage src={previewAsset.img_url || previewAsset.file_url} alt={previewAsset.object_name || 'asset'} className="w-full max-h-[46vh] object-contain" />
                            )}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                            <span className={`text-[11px] px-1.5 py-0.5 rounded flex items-center gap-1 ${analysisStatusClass(normalizeAnalysisStatus(previewAsset.analysis_status))}`}>
                                {normalizeAnalysisStatus(previewAsset.analysis_status) === ANALYSIS_STATUS_ANALYZING ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                {t('解析', 'Analysis')}：{analysisStatusLabel(normalizeAnalysisStatus(previewAsset.analysis_status), t)}
                            </span>
                            <button
                                type="button"
                                className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                                disabled={disabled || busy || normalizeAnalysisStatus(previewAsset.analysis_status) === ANALYSIS_STATUS_ANALYZING}
                                title={t('更换后会自动重新解析', 'Re-analyzes automatically after replace')}
                                onClick={() => {
                                    replaceTargetRef.current = previewAsset;
                                    replaceInputRef.current?.click();
                                }}
                            >
                                <Replace className="w-3 h-3" /> {t('更换照片', 'Replace photo')}
                            </button>
                            <button
                                type="button"
                                className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-40 flex items-center gap-1"
                                disabled={disabled || normalizeAnalysisStatus(previewAsset.analysis_status) === ANALYSIS_STATUS_ANALYZING}
                                onClick={() => analyzeOne(previewAsset)}
                            >
                                {normalizeAnalysisStatus(previewAsset.analysis_status) === ANALYSIS_STATUS_ANALYZING ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                {t('重新解析', 'Re-analyze')}
                            </button>
                        </div>
                        {isSceneAsset(previewAsset) ? (
                            <select
                                className="w-full bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs"
                                value={viewDirectionOf(previewAsset)}
                                disabled={disabled || busy || normalizeAnalysisStatus(previewAsset.analysis_status) === ANALYSIS_STATUS_ANALYZING}
                                onChange={(e) => patchSceneMeta(previewAsset, { view_direction: e.target.value })}
                            >
                                {SCENE_VIEW_DIRECTIONS.map((opt) => (
                                    <option key={opt.value || 'unset'} value={opt.value}>{t(opt.zh, opt.en)}</option>
                                ))}
                            </select>
                        ) : null}
                        {renderWallExtras(previewAsset)}
                        {previewAsset.analysis_error ? (
                            <div className="text-xs text-red-300 break-words">{previewAsset.analysis_error}</div>
                        ) : null}
                        {hasAnalysisText(previewAsset) ? (
                            <div className="space-y-3 bg-black/25 rounded-xl p-3">
                                <div className="text-xs font-semibold text-white/80">{t('解析结果', 'Analysis result')}</div>
                                <DetailLine label={t('全局视觉', 'Global visual')} value={analysisForAsset(previewAsset).global_visual_summary} />
                                <DetailLine label={t('内容描述', 'Content')} value={analysisRowForAsset(previewAsset).content_desc} />
                                <DetailLine label={t('重生全文', 'Rebuild brief')} value={analysisRowForAsset(previewAsset).rebuild_brief} />
                                <DetailLine label={t('场景细节', 'Scene detail')} value={analysisRowForAsset(previewAsset).environment_detail} />
                                <DetailLine label={t('道具细节', 'Prop detail')} value={analysisRowForAsset(previewAsset).prop_detail} />
                                <DetailLine label={t('人物细节', 'Character detail')} value={analysisRowForAsset(previewAsset).character_detail} />
                                <DetailLine label={t('光色', 'Lighting')} value={analysisRowForAsset(previewAsset).light_info} />
                                <DetailLine label={t('视频动作', 'Video motion')} value={analysisRowForAsset(previewAsset).video_motion} />
                                {(Array.isArray(analysisForAsset(previewAsset).rebuild_subjects) ? analysisForAsset(previewAsset).rebuild_subjects : []).map((subject, idx) => (
                                    <div key={`${subject.name_for_script || subject.object_name || idx}`} className="space-y-1 pt-1 border-t border-white/5">
                                        <div className="text-[11px] text-white/50">{t('可重生主体', 'Rebuild subject')} · {subject.kind || ''} · {subject.name_for_script || subject.object_name || ''}</div>
                                        <DetailLine label={t('外形', 'Appearance')} value={subject.appearance || subject.rebuild_brief} />
                                        <DetailLine label={t('衣着/材质', 'Clothing / material')} value={subject.clothing_or_material} />
                                        <DetailLine label={t('空间', 'Space')} value={subject.space_layout} />
                                        <DetailLine label={t('光色', 'Lighting')} value={subject.lighting} />
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-xs text-white/45">
                                {normalizeAnalysisStatus(previewAsset.analysis_status) === ANALYSIS_STATUS_ANALYZING
                                    ? t('正在解析，完成后会显示结果。', 'Analysis is running. Results will appear here.')
                                    : t('还没有解析结果。点「重新解析」生成外形与场景细节。', 'No analysis yet. Click Re-analyze to generate visual details.')}
                            </div>
                        )}
                    </div>
                </div>
            ) : null}
        </div>
    );
}
