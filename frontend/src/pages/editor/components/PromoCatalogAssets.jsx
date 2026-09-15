import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Image as ImageIcon, Trash2, Upload, Video } from 'lucide-react';
import { getFullUrl } from '../editorHelpers';
import {
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

export const PROMO_MEDIA_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov';
const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'webp'];
const VIDEO_EXTS = ['mp4', 'webm', 'mov'];
const MAX_MB = 40;

const isAcceptedMedia = (file) => {
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    const type = String(file?.type || '').toLowerCase();
    return IMAGE_EXTS.includes(ext) || VIDEO_EXTS.includes(ext) || type.startsWith('image/') || type.startsWith('video/');
};

const mediaKindOf = (file) => {
    const type = String(file?.type || '').toLowerCase();
    const name = String(file?.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';
    if (type.startsWith('video/') || VIDEO_EXTS.includes(ext)) return 'video';
    return 'image';
};

const newImageId = () => `promo-cat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

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
    const fileInputRef = useRef(null);

    const load = useCallback(async () => {
        if (!ownerId) {
            setAssets([]);
            return;
        }
        try {
            const rows = await fetchPromoCatalogAssets({ owner_kind: ownerKind, owner_entity_id: Number(ownerId) });
            setAssets(Array.isArray(rows) ? rows : []);
        } catch (err) {
            console.error('[PromoCatalogAssets] load failed', err);
            setAssets([]);
        }
    }, [ownerId, ownerKind]);

    useEffect(() => {
        load();
    }, [load]);

    const uploadOne = async (file) => {
        if (!ownerId || disabled) return;
        if (!isAcceptedMedia(file)) {
            alert(t('仅支持 jpg / png / webp / mp4 / webm / mov', 'Only jpg / png / webp / mp4 / webm / mov'));
            return;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
            alert(t(`单文件不超过 ${MAX_MB}MB`, `Max ${MAX_MB}MB per file`));
            return;
        }
        const imageId = newImageId();
        const mediaKind = mediaKindOf(file);
        setBusy(true);
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
                asset_type: 'product',
                image_id: imageId,
                file_url: url,
                img_url: url,
                object_name: file.name.replace(/\.[^.]+$/, ''),
            });
            setAssets((prev) => [created, ...prev.filter((item) => Number(item.id) !== Number(created.id))]);
        } catch (err) {
            alert(err?.response?.data?.detail || err?.message || t('上传失败', 'Upload failed'));
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

    const patchAsset = async (asset, patch) => {
        if (!asset?.id || disabled) return;
        setAssets((prev) => prev.map((item) => (Number(item.id) === Number(asset.id) ? { ...item, ...patch } : item)));
        try {
            const updated = await updatePromoCatalogAsset(asset.id, patch);
            setAssets((prev) => prev.map((item) => (Number(item.id) === Number(asset.id) ? { ...item, ...updated } : item)));
        } catch (err) {
            console.error('[PromoCatalogAssets] update failed', err);
        }
    };

    const removeAsset = async (asset) => {
        if (!asset?.id || disabled) return;
        try {
            await deletePromoCatalogAsset(asset.id);
            setAssets((prev) => prev.filter((item) => Number(item.id) !== Number(asset.id)));
        } catch (err) {
            alert(err?.response?.data?.detail || err?.message || t('删除失败', 'Delete failed'));
        }
    };

    if (!ownerId) {
        return (
            <div className="text-xs text-white/40">
                {t('选择后可上传图片或视频素材（产品 / 角色 / 场景 / 道具）', 'Select first to attach image or video assets (product / character / scene / prop)')}
            </div>
        );
    }

    return (
        <div className="space-y-2 pt-2 border-t border-white/5">
            <div className="flex items-center justify-between gap-2">
                <h5 className="text-sm font-semibold text-white">{title || t('关联素材', 'Linked assets')}</h5>
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
            <input ref={fileInputRef} type="file" accept={PROMO_MEDIA_ACCEPT} multiple className="hidden" onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }} />
            {assets.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {assets.map((asset) => {
                        const url = getFullUrl(asset.img_url || asset.file_url);
                        const isVideo = String(asset.media_kind || '') === 'video';
                        return (
                            <div key={asset.id || asset.image_id} className="bg-black/30 border border-white/10 rounded-lg overflow-hidden">
                                <div className="relative h-28 bg-black/40">
                                    {url && !isVideo ? (
                                        <img src={url} alt={asset.object_name || 'asset'} className="w-full h-full object-cover" />
                                    ) : url && isVideo ? (
                                        <video src={url} className="w-full h-full object-cover" muted />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-white/30">
                                            {isVideo ? <Video className="w-7 h-7" /> : <ImageIcon className="w-7 h-7" />}
                                        </div>
                                    )}
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
                                    <button type="button" className="w-full text-xs px-2 py-1 rounded bg-red-500/20 text-red-200 hover:bg-red-500/30 flex items-center justify-center gap-1" onClick={() => removeAsset(asset)} disabled={disabled}>
                                        <Trash2 className="w-3 h-3" /> {t('删除', 'Delete')}
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="text-xs text-muted-foreground">{t('可先不上传，策划仍可生成。', 'Assets are optional. The plan still generates without them.')}</div>
            )}
        </div>
    );
}
