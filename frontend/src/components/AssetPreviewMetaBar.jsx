import React from 'react';
import { Loader2 } from 'lucide-react';

const normalizeMetaKey = (key) => String(key || '').toLowerCase().replace(/[^a-z0-9]/g, '');

const parseMetaObject = (raw) => {
    if (!raw) return {};
    if (typeof raw === 'object' && !Array.isArray(raw)) return raw;
    if (typeof raw === 'string') {
        const text = raw.trim();
        if (!text) return {};
        try {
            const parsed = JSON.parse(text);
            return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
        } catch {
            return {};
        }
    }
    return {};
};

const buildMetaLookupFromAsset = (asset) => {
    const meta = parseMetaObject(asset?.meta_info);
    const merged = {
        ...(asset && typeof asset === 'object' ? asset : {}),
        ...meta,
    };
    const lookup = {};
    Object.entries(merged).forEach(([key, value]) => {
        if (value === null || value === undefined || typeof value === 'object') return;
        const text = String(value).trim();
        if (!text) return;
        lookup[normalizeMetaKey(key)] = text;
    });
    return lookup;
};

const pickMetaValue = (lookup, keys = []) => {
    for (const key of keys) {
        const value = lookup?.[normalizeMetaKey(key)];
        if (value === null || value === undefined) continue;
        const text = String(value).trim();
        if (!text || text.toLowerCase() === 'null' || text.toLowerCase() === 'undefined') continue;
        return text;
    }
    return '';
};

const gcdInt = (a, b) => (b ? gcdInt(b, a % b) : Math.abs(a));

const deriveAspectRatioFromSize = (width, height) => {
    const w = Number(width);
    const h = Number(height);
    if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return '';
    const g = gcdInt(w, h);
    return `${Math.round(w / g)}:${Math.round(h / g)}`;
};

const formatAssetFileSize = (meta = {}) => {
    const display = String(meta.file_size_display || meta.size_display || '').trim();
    if (display) return display;
    const rawBytes = meta.file_size_bytes ?? (typeof meta.size === 'number' ? meta.size : null);
    const bytes = Number(rawBytes);
    if (Number.isFinite(bytes) && bytes > 0) {
        if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
        return `${(bytes / 1024).toFixed(2)} KB`;
    }
    return String(meta.size || meta.file_size || '').trim();
};

const getAssetCategory = (type) => {
    const value = String(type || '').toLowerCase();
    if (value.includes('video')) return 'video';
    if (value.includes('image') || value.includes('frame') || value.includes('photo')) return 'image';
    return value || 'unknown';
};

export const buildAssetMetaSummary = (asset) => {
    const meta = parseMetaObject(asset?.meta_info);
    const lookup = buildMetaLookupFromAsset(asset);
    const width = pickMetaValue(lookup, ['width']);
    const height = pickMetaValue(lookup, ['height']);
    const resolution = pickMetaValue(lookup, ['resolution', 'dimensions'])
        || (width && height ? `${width}x${height}` : '');
    const aspectRatio = pickMetaValue(lookup, ['aspect_ratio', 'aspectratio', 'submit_aspect_ratio'])
        || deriveAspectRatioFromSize(width, height);
    const fileSize = formatAssetFileSize(meta);
    const model = pickMetaValue(lookup, ['model']);
    const providerAlias = pickMetaValue(lookup, ['provider_alias']);
    const provider = pickMetaValue(lookup, ['provider']);
    const providerLabel = providerAlias || provider;
    const durationRaw = pickMetaValue(lookup, ['duration']);
    let duration = '';
    if (durationRaw) {
        const durationNum = Number(durationRaw);
        duration = Number.isFinite(durationNum) && durationNum > 0
            ? `${Number(durationNum.toFixed(2))}s`
            : String(durationRaw).trim();
    }
    const format = pickMetaValue(lookup, ['format']);
    return {
        resolution,
        aspectRatio,
        fileSize,
        model,
        provider: providerLabel,
        providerCode: provider,
        duration,
        format,
    };
};

export default function AssetPreviewMetaBar({
    asset,
    t,
    loading = false,
    className = '',
    emptyHint,
}) {
    const category = getAssetCategory(asset?.type);
    const summary = buildAssetMetaSummary(asset);
    const items = [
        { label: t('分辨率', 'Resolution'), value: summary.resolution },
        { label: t('画幅比', 'Aspect Ratio'), value: summary.aspectRatio },
        { label: t('文件大小', 'File Size'), value: summary.fileSize },
        { label: t('生成模型', 'Model'), value: summary.model },
        { label: t('提供商', 'Provider'), value: summary.provider },
        ...(category === 'video' ? [{ label: t('时长', 'Duration'), value: summary.duration }] : []),
        ...(summary.format ? [{ label: t('格式', 'Format'), value: summary.format }] : []),
    ].filter((item) => String(item.value || '').trim());

    const fallbackHint = emptyHint || t('暂无分辨率/模型等元数据', 'No resolution/model metadata yet');

    return (
        <div className={`border-t border-white/10 bg-black/75 backdrop-blur-md px-4 py-3 shrink-0 ${className}`.trim()}>
            {loading ? (
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {t('读取元数据中...', 'Reading metadata...')}
                </div>
            ) : items.length > 0 ? (
                <div className="flex flex-wrap gap-x-5 gap-y-2">
                    {items.map(({ label, value }) => (
                        <div key={label} className="flex items-baseline gap-1.5 text-[11px] min-w-0 max-w-full">
                            <span className="text-white/45 shrink-0">{label}</span>
                            <span
                                className="text-white/90 font-mono truncate max-w-[240px]"
                                title={String(value)}
                            >
                                {value}
                                {label === t('提供商', 'Provider') && summary.providerCode && summary.provider !== summary.providerCode ? (
                                    <span className="ml-1 text-white/40">({summary.providerCode})</span>
                                ) : null}
                            </span>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="text-[11px] text-white/40">{fallbackHint}</div>
            )}
        </div>
    );
}
