import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    Image, Video, Upload, Link as LinkIcon, Plus, X, 
    MoreVertical, Trash2, Edit2, Info, Maximize2,
    Folder, User, Film, Globe, Layers, ArrowDown, ArrowUp,
    Sparkles, Copy, Loader2, CheckCircle, Settings, Calendar, AlertTriangle, FolderOpen, Download
} from 'lucide-react';
import { fetchAssets, createAsset, uploadAsset, deleteAsset, deleteAssetsBatch, updateAsset, analyzeAssetImage, fetchUnreferencedAssetIds } from '../services/api';
import { useLog } from '../context/LogContext';
import { API_URL, BASE_URL } from '../config';
import RefineControl from './RefineControl.jsx';
import { confirmUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI } from '../lib/uiLang';

// Helper to construct full URL if relative
const getFullUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('blob:') || url.startsWith('data:')) return url;
    if (url.startsWith('/')) {
        const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
        return `${base}${url}`;
    }
    return url; 
};

// Helper to normalize asset types
const getAssetCategory = (type) => {
    if (!type) return 'unknown';
    const t = String(type).toLowerCase();
    if (t.includes('video')) return 'video';
    if (t.includes('image') || t.includes('frame') || t.includes('photo')) return 'image';
    return t; // fallback
};

const inferDownloadName = (asset, index = 0) => {
    const existing = String(asset?.filename || '').trim();
    if (existing) return existing;
    const category = getAssetCategory(asset?.type);
    const fallbackExt = category === 'video' ? 'mp4' : 'png';
    return `asset_${String(index + 1).padStart(3, '0')}.${fallbackExt}`;
};


const LOCAL_DIR_RESTORE_HINT_KEY = 'assets_local_dir_restore_hint_v1';

const isKnownBrokenLegacyUrl = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return false;
    return /^https?:\/\/file\d+\.aitohumanize\.com\/file\//i.test(raw);
};

const parseMetaForGrouping = (rawMeta) => {
    let meta = rawMeta;
    for (let i = 0; i < 3; i++) {
        if (typeof meta !== 'string') break;
        try {
            meta = JSON.parse(meta);
        } catch {
            break;
        }
    }

    if (!meta || typeof meta !== 'object' || Array.isArray(meta)) return {};

    const merged = { ...meta };
    ['meta_info', 'metadata', 'extra', 'details'].forEach((k) => {
        const nested = meta?.[k];
        if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
            Object.assign(merged, nested);
        }
    });
    return merged;
};

const pickMetaValue = (meta, keys = []) => {
    for (const key of keys) {
        const value = meta?.[key];
        if (value === null || value === undefined) continue;
        const text = String(value).trim();
        if (!text || text.toLowerCase() === 'null' || text.toLowerCase() === 'undefined') continue;
        return text;
    }
    return '';
};


const AssetItem = React.memo(({ asset, onClick, onDelete, isManageMode, isSelected, onToggleSelect, onReportError, t }) => {
    const videoRef = React.useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isError, setIsError] = useState(() => isKnownBrokenLegacyUrl(asset?.url));
    const category = getAssetCategory(asset.type);

    React.useEffect(() => {
        if (isError && onReportError) {
            onReportError(asset.id);
        }
    }, [isError, asset.id, onReportError]);

    const handleMouseEnter = async () => {
        if (!isManageMode && category === 'video' && videoRef.current && !isError) {
            try {
                videoRef.current.currentTime = 0;
                await videoRef.current.play();
                setIsPlaying(true);
            } catch (err) {
                // Auto-play might be prevented
            }
        }
    };

    const handleMouseLeave = () => {
        if (!isManageMode && category === 'video' && videoRef.current && !isError) {
            videoRef.current.pause();
            videoRef.current.currentTime = 0;
            setIsPlaying(false);
        }
    };
    
    // ... handleClick ...
    const handleClick = (e) => {
        if (isManageMode) {
            e.stopPropagation();
            onToggleSelect(asset.id);
        } else {
            onClick(asset);
        }
    };

    return (
        <div 
            onClick={handleClick}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
             className={`group relative aspect-square bg-card rounded-xl border overflow-hidden cursor-pointer transition-all hover:scale-[1.02] shadow-sm transform-gpu ${isSelected ? 'border-primary ring-2 ring-primary ring-offset-2 ring-offset-black' : 'border-white/5 hover:border-primary/50'}`}
        >
            {isError ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white/5 text-muted-foreground gap-2">
                    <AlertTriangle size={24} className="opacity-50" />
                    <span className="text-[10px] uppercase font-bold opacity-50">{t('资源不存在', 'Not Found')}</span>
                </div>
            ) : category === 'image' ? (
                <img 
                    src={getFullUrl(asset.url)} 
                    className="w-full h-full object-cover bg-black/20" 
                    alt="asset" 
                    onError={() => setIsError(true)}
                />
            ) : (
                <div className="relative w-full h-full bg-black">
                    <video 
                        ref={videoRef}
                        src={getFullUrl(asset.url)} 
                        className={`w-full h-full object-cover transition-opacity duration-300 ${isPlaying ? 'opacity-100' : 'opacity-70'}`}
                        preload="metadata"
                        muted
                        loop
                        playsInline
                        onError={() => setIsError(true)}
                    />
                    <div className={`absolute inset-0 flex items-center justify-center pointer-events-none transition-opacity duration-300 ${isPlaying ? 'opacity-0' : 'opacity-100'}`}>
                        <div className="bg-black/50 p-3 rounded-full backdrop-blur-sm">
                            <Video className="w-6 h-6 text-white" />
                        </div>
                    </div>
                </div>
            )}
            
            {/* Selection Overlay */}
            {isManageMode && (
                <div className={`absolute top-2 right-2 z-20 transition-transform ${isSelected ? 'scale-100' : 'scale-90 opacity-70 hover:opacity-100'}`}>
                    <div className={`p-1 rounded-full ${isSelected ? 'bg-primary text-black' : 'bg-black/50 text-white border border-white/20'}`}>
                        <CheckCircle size={18} className={isSelected ? 'fill-current' : ''} />
                    </div>
                </div>
            )}
            
            <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-4 pointer-events-none">
                <div className="flex justify-between items-end pointer-events-auto">
                    <div>
                        <div className="text-xs text-white/70 truncate w-24">{asset.filename || t('未命名', 'Untitled')}</div>
                        <div className="text-[10px] text-white/40 uppercase flex items-center gap-2">
                             {asset.type}
                             {asset.meta_info?.resolution && <span className="bg-white/10 px-1 rounded text-white/60">{asset.meta_info.resolution}</span>}
                        </div>
                    </div>
                    {!isManageMode && (
                        <button 
                            onClick={(e) => onDelete(asset.id, e)}
                            className="p-1.5 bg-red-500/20 text-red-400 rounded-md hover:bg-red-500 hover:text-white transition-colors"
                        >
                            <Trash2 size={14} />
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
});

const AssetsLibrary = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const { addLog } = useLog();
    const [assets, setAssets] = useState([]);
    const [filter, setFilter] = useState('all'); // all, image, video
    const [groupBy, setGroupBy] = useState('none'); // none, project, subject, shot
    const [sortOrder, setSortOrder] = useState('desc'); // desc (newest first), asc (oldest first)
    const [loading, setLoading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); 
    const [isUploadOpen, setIsUploadOpen] = useState(false);
    const [localAssets, setLocalAssets] = useState([]);
    const [showLocalRestoreHint, setShowLocalRestoreHint] = useState(false);
    const localObjectUrlsRef = React.useRef(new Set());
    const localDirInputRef = React.useRef(null);
    
    // Manage Mode State
    const [isManageMode, setIsManageMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [isDownloadingSelected, setIsDownloadingSelected] = useState(false);
    const brokenAssetsRef = React.useRef(new Set());

    const handleReportError = React.useCallback((id) => {
        brokenAssetsRef.current.add(id);
    }, []);

    const handleSelectBroken = () => {
        if (brokenAssetsRef.current.size === 0) {
            addLog("No broken assets detected yet (scroll to load them).");
            return;
        }
        const newSet = new Set(selectedIds);
        brokenAssetsRef.current.forEach(id => newSet.add(id));
        setSelectedIds(newSet);
        addLog(`Selected ${brokenAssetsRef.current.size} broken assets.`);
    };

    useEffect(() => {
        loadAssets();
        try {
            const remembered = localStorage.getItem(LOCAL_DIR_RESTORE_HINT_KEY);
            if (remembered === '1') {
                setShowLocalRestoreHint(true);
            }
        } catch {}
        return () => {
            localObjectUrlsRef.current.forEach((url) => {
                try { URL.revokeObjectURL(url); } catch {}
            });
            localObjectUrlsRef.current.clear();
        };
    }, []);

    const clearLocalAssets = React.useCallback(() => {
        localObjectUrlsRef.current.forEach((url) => {
            try { URL.revokeObjectURL(url); } catch {}
        });
        localObjectUrlsRef.current.clear();
        setLocalAssets([]);
    }, []);

    const buildLocalAsset = React.useCallback((file, relativePath = '') => {
        const category = file.type?.startsWith('video') ? 'video' : (file.type?.startsWith('image') ? 'image' : 'unknown');
        if (category === 'unknown') return null;

        const objectUrl = URL.createObjectURL(file);
        localObjectUrlsRef.current.add(objectUrl);
        const now = new Date().toISOString();
        const rel = String(relativePath || file.webkitRelativePath || file.name || '').trim();
        const idSeed = `${rel}|${file.size}|${file.lastModified}|${file.type}`;

        return {
            id: `local:${idSeed}`,
            url: objectUrl,
            type: category,
            filename: file.name,
            created_at: now,
            remark: rel || 'Local file',
            meta_info: {
                source: 'local-directory',
                local_path: rel,
                mime_type: file.type,
                size_bytes: file.size,
            },
            __is_local: true,
        };
    }, []);

    const loadLocalAssetsFromFiles = React.useCallback((fileList) => {
        const files = Array.from(fileList || []);
        if (!files.length) {
            addLog('No local files selected.');
            return;
        }

        clearLocalAssets();
        const parsed = files
            .map((file) => buildLocalAsset(file, file.webkitRelativePath || file.name))
            .filter(Boolean);
        setLocalAssets(parsed);
        try { localStorage.setItem(LOCAL_DIR_RESTORE_HINT_KEY, '1'); } catch {}
        setShowLocalRestoreHint(false);
        addLog(`Loaded ${parsed.length} local assets from selected directory.`);
    }, [addLog, buildLocalAsset, clearLocalAssets]);

    const pickLocalDirectory = async () => {
        try {
            if (window.showDirectoryPicker) {
                const dirHandle = await window.showDirectoryPicker();
                clearLocalAssets();
                const collected = [];

                const walk = async (handle, basePath = '') => {
                    for await (const [name, entry] of handle.entries()) {
                        const nextPath = basePath ? `${basePath}/${name}` : name;
                        if (entry.kind === 'directory') {
                            await walk(entry, nextPath);
                        } else if (entry.kind === 'file') {
                            const file = await entry.getFile();
                            const item = buildLocalAsset(file, nextPath);
                            if (item) collected.push(item);
                        }
                    }
                };

                await walk(dirHandle);
                setLocalAssets(collected);
                try { localStorage.setItem(LOCAL_DIR_RESTORE_HINT_KEY, '1'); } catch {}
                setShowLocalRestoreHint(false);
                addLog(`Loaded ${collected.length} local assets from selected directory.`);
                return;
            }

            if (localDirInputRef.current) {
                localDirInputRef.current.value = '';
                localDirInputRef.current.click();
                return;
            }

            addLog('Local directory picker is not supported by this browser.', 'error');
        } catch (e) {
            if (String(e?.name || '').toLowerCase() === 'aborterror') {
                return;
            }
            addLog(`Failed to read local directory: ${e.message}`, 'error');
        }
    };

    const loadAssets = async () => {
        setLoading(true);
        try {
            const data = await fetchAssets();
            // Ensure meta_info is always an object
            const cleanData = data.map(a => {
                let meta = a.meta_info;
                if (typeof meta === 'string') {
                    try { meta = JSON.parse(meta); } catch (e) { meta = {}; }
                }
                return { ...a, meta_info: meta || {} };
            });
            setAssets(cleanData);
            addLog(`Loaded ${cleanData.length} assets from library.`);
        } catch (e) {
            console.error("Failed to load assets", e);
            addLog(`Error loading assets: ${e.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();

        if (String(id).startsWith('local:')) {
            const target = localAssets.find((a) => a.id === id);
            if (target?.url && String(target.url).startsWith('blob:')) {
                try { URL.revokeObjectURL(target.url); } catch {}
                localObjectUrlsRef.current.delete(target.url);
            }
            setLocalAssets((prev) => prev.filter((a) => a.id !== id));
            if (selectedAsset?.id === id) setSelectedAsset(null);
            addLog(`Removed local asset ${id}.`);
            return;
        }

        if (!await confirmUiMessage("Are you sure you want to delete this asset?")) return;
        try {
            await deleteAsset(id);
            setAssets(prev => prev.filter(a => a.id !== id));
            if (selectedAsset?.id === id) setSelectedAsset(null);
            addLog(`Deleted asset ID ${id}.`);
        } catch (e) {
            console.error("Delete failed", e);
            addLog(`Failed to delete asset: ${e.message}`, 'error');
        }
    };

    const toggleSelect = (id) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) newSet.delete(id);
        else newSet.add(id);
        setSelectedIds(newSet);
    };

    const runBatchDelete = async (idsToDelete) => {
        try {
            const idsList = Array.isArray(idsToDelete) ? idsToDelete : Array.from(idsToDelete);
            const localIds = idsList.filter((id) => String(id).startsWith('local:'));
            const remoteIds = idsList.filter((id) => !String(id).startsWith('local:'));

            if (remoteIds.length > 0) {
                await deleteAssetsBatch(remoteIds);
                setAssets(prev => prev.filter(a => !remoteIds.includes(a.id)));
            }

            if (localIds.length > 0) {
                setLocalAssets((prev) => {
                    prev.forEach((item) => {
                        if (localIds.includes(item.id) && item.url && String(item.url).startsWith('blob:')) {
                            try { URL.revokeObjectURL(item.url); } catch {}
                            localObjectUrlsRef.current.delete(item.url);
                        }
                    });
                    return prev.filter((a) => !localIds.includes(a.id));
                });
            }

            setSelectedIds(prev => {
                const newSet = new Set(prev);
                idsList.forEach(id => newSet.delete(id));
                return newSet;
            });
            addLog(`Successfully deleted ${idsList.length} assets.`);
        } catch (e) {
            console.error("Batch delete failed", e);
            addLog(`Failed to delete assets: ${e.message}`, 'error');
        }
    };

    const handleDeleteSelected = async () => {
        if (selectedIds.size === 0) return;
        if (!await confirmUiMessage(`Delete ${selectedIds.size} selected assets? Files will be removed.`)) return;
        await runBatchDelete(selectedIds);
    };

    const handleDownloadSelected = async () => {
        const ids = Array.from(selectedIds || []);
        if (ids.length === 0) return;

        const allAssets = [...assets, ...localAssets];
        const selectedAssets = allAssets.filter((item) => ids.includes(item.id));
        if (selectedAssets.length === 0) return;

        setIsDownloadingSelected(true);
        let successCount = 0;
        let failCount = 0;

        for (let i = 0; i < selectedAssets.length; i++) {
            const asset = selectedAssets[i];
            const src = getFullUrl(asset.url);
            if (!src) {
                failCount += 1;
                continue;
            }

            const filename = inferDownloadName(asset, i);
            try {
                const response = await fetch(src, { credentials: 'include' });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const blob = await response.blob();
                const objectUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = objectUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(objectUrl);
                successCount += 1;
            } catch (e) {
                try {
                    const a = document.createElement('a');
                    a.href = src;
                    a.download = filename;
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    successCount += 1;
                } catch {
                    failCount += 1;
                }
            }
        }

        setIsDownloadingSelected(false);
        addLog(`Download selected complete. success=${successCount}, failed=${failCount}`);
    };

    const handleDeleteFiltered = async () => {
        const ids = filteredAssets.map(a => a.id);
        if (ids.length === 0) return;
        if (!await confirmUiMessage(`Delete ALL ${ids.length} currently filtered assets?`)) return;
        await runBatchDelete(ids);
    };

    const handleSelectOld = () => {
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        
        const oldAssets = filteredAssets.filter(a => {
            if (!a.created_at) return false;
            return new Date(a.created_at) < weekAgo;
        });
        
        if (oldAssets.length === 0) {
            addLog("No assets older than 1 week found in current view.");
            return;
        }
        
        const newSet = new Set(selectedIds);
        oldAssets.forEach(a => newSet.add(a.id));
        setSelectedIds(newSet);
        addLog(`Selected ${oldAssets.length} assets older than 7 days.`);
    };

    const handleSelectUnreferenced = async () => {
        try {
            const payload = await fetchUnreferencedAssetIds();
            const unreferencedIds = new Set((payload?.unreferenced_ids || []).map((id) => Number(id)));
            const targets = filteredAssets.filter((asset) => !String(asset.id).startsWith('local:') && unreferencedIds.has(Number(asset.id)));

            if (targets.length === 0) {
                addLog('No unreferenced assets found in current view.');
                return;
            }

            const newSet = new Set(selectedIds);
            targets.forEach((asset) => newSet.add(asset.id));
            setSelectedIds(newSet);
            addLog(`Selected ${targets.length} unreferenced assets (not used by current subject/shot image/video).`);
        } catch (e) {
            addLog(`Failed to select unreferenced assets: ${e.message}`, 'error');
        }
    };

    const filteredAssets = React.useMemo(() => {
        const mergedAssets = [...assets, ...localAssets];
        const list = mergedAssets.filter(a => {
            if (filter === 'all') return true;
            return getAssetCategory(a.type) === filter;
        });
        return list.sort((a, b) => {
             const tA = new Date(a.created_at || a.id).getTime ? new Date(a.created_at || 0).getTime() : 0; 
             // ID fallback is weak, assuming createdAt exists or backend provides it.
             // Usually created_at is ISO string. 
             const dateA = new Date(a.created_at || 0).getTime();
             const dateB = new Date(b.created_at || 0).getTime();
             return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
        });
    }, [assets, localAssets, filter, sortOrder]);


    const [isScanning, setIsScanning] = useState(false);
    const [scanProgress, setScanProgress] = useState(0);

    // Batch check valid URLs
    const handleScanBroken = async () => {
        if (isScanning) return;
        setIsScanning(true);
        setScanProgress(0);
        
        const assetsToCheck = filteredAssets;
        const total = assetsToCheck.length;
        const invalidIds = new Set();
        const batchSize = 10;
        
        for (let i = 0; i < total; i += batchSize) {
            const batch = assetsToCheck.slice(i, i + batchSize);
            await Promise.all(batch.map(async (asset) => {
                const url = getFullUrl(asset.url);
                try {
                    if (getAssetCategory(asset.type) === 'video') {
                         // Use fetch head for video if possible, else rely on error reporting later or just image check
                         // Simple fetch head might fail cors, so let's try fetch
                         const res = await fetch(url, { method: 'HEAD', mode: 'no-cors' }); 
                         // no-cors mode returns opaque response, so we can't check status.
                         // But if 404, it might still resolve.
                         // Better to just try standard fetch or skip video checking in this pass if problematic.
                         // Reverting to fetch head without no-cors, assuming user has access.
                         const check = await fetch(url, { method: 'HEAD' });
                         if (!check.ok) throw new Error(check.statusText);
                    } else {
                        await new Promise((resolve, reject) => {
                            const img = new window.Image();
                            img.onload = resolve;
                            img.onerror = reject;
                            img.src = url;
                        });
                    }
                } catch (e) {
                    invalidIds.add(asset.id);
                }
            }));
            setScanProgress(Math.round(((i + batchSize) / total) * 100));
            // Yield to main thread
            await new Promise(r => setTimeout(r, 10));
        }
        
        setIsScanning(false);
        setScanProgress(0);
        
        if (invalidIds.size > 0) {
            setSelectedIds(prev => new Set([...prev, ...invalidIds]));
            addLog(`Scan complete. Found ${invalidIds.size} broken assets.`);
        } else {
            addLog("Scan complete. No broken assets found.");
        }
    };

    const groupedSections = React.useMemo(() => {
        if (groupBy === 'none') return { 'All Assets': filteredAssets };
        
        const groups = {};
        const globalKey = 'Global / Unsorted';
        
        filteredAssets.forEach(asset => {
            const meta = parseMetaForGrouping(asset.meta_info);
            
            let key = globalKey;
            
            const pId = pickMetaValue(meta, ['project_id', 'Project_id', 'ProjectId', 'projectId']);
            const pTitle = pickMetaValue(meta, ['project_title', 'Project_title', 'projectTitle']);

            const eId = pickMetaValue(meta, ['entity_id', 'Entity_id', 'entityId', 'subject_id', 'subjectId']);
            const eName = pickMetaValue(meta, ['entity_name', 'Entity_name', 'entityName', 'subject_name', 'subjectName']);

            const sId = pickMetaValue(meta, ['shot_id', 'Shot_id', 'shotId']);
            const sNum = pickMetaValue(meta, ['shot_number', 'Shot_number', 'shotNumber']);

            if (groupBy === 'project') {
                if (pTitle) key = pTitle;
                else if (pId) key = `Project ${pId}`;
            } else if (groupBy === 'subject') {
                if (eName) key = eName;
                else if (eId) key = `Entity ${eId}`;
            } else if (groupBy === 'shot') {
                if (sNum) key = `Shot ${sNum}`;
                else if (sId) key = `Shot ${sId}`;
            }
            
            if (!groups[key]) groups[key] = [];
            groups[key].push(asset);
        });
        
        return groups;
    }, [filteredAssets, groupBy]);


    return (
        <div className="h-full flex flex-col p-6 animate-in fade-in">
            {/* Header Controls */}
            <div className="flex flex-col gap-4 mb-6">
                 {!isManageMode ? (
                 <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <div className="flex space-x-2 bg-card/50 p-1 rounded-lg border border-white/5">
                            <button onClick={() => setFilter('all')} className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${filter === 'all' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}>{t('全部', 'All')}</button>
                            <button onClick={() => setFilter('image')} className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${filter === 'image' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}><Image size={16} /> {t('图片', 'Images')}</button>
                            <button onClick={() => setFilter('video')} className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${filter === 'video' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}><Video size={16} /> {t('视频', 'Videos')}</button>
                        </div>
                        <button 
                            onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
                            className="p-2.5 rounded-lg bg-card/50 border border-white/5 text-muted-foreground hover:text-white hover:bg-white/10 transition-colors"
                            title={sortOrder === 'desc' ? t('排序：最新优先', 'Sort: Newest First') : t('排序：最旧优先', 'Sort: Oldest First')}
                        >
                            {sortOrder === 'desc' ? <ArrowDown size={18} /> : <ArrowUp size={18} />}
                        </button>
                    </div>
                    
                    <div className="flex items-center gap-3">
                        <input
                            ref={localDirInputRef}
                            type="file"
                            className="hidden"
                            multiple
                            webkitdirectory=""
                            directory=""
                            onChange={(e) => loadLocalAssetsFromFiles(e.target.files)}
                        />
                        <button onClick={pickLocalDirectory} className="flex items-center gap-2 px-4 py-2 bg-card border border-white/10 text-white rounded-lg hover:bg-white/5 transition-colors">
                            <FolderOpen size={18} /> {t('读取本地目录', 'Read Local Folder')}
                        </button>
                        {localAssets.length > 0 && (
                            <button onClick={clearLocalAssets} className="flex items-center gap-2 px-3 py-2 bg-card border border-white/10 text-muted-foreground rounded-lg hover:text-white hover:bg-white/5 transition-colors">
                                <X size={16} /> {t('清空本地', 'Clear Local')}
                            </button>
                        )}
                        <button onClick={() => setIsManageMode(true)} className="flex items-center gap-2 px-4 py-2 bg-card border border-white/10 text-white rounded-lg hover:bg-white/5 transition-colors"><Settings size={18} /> {t('管理', 'Manage')}</button>
                        <button onClick={() => setIsUploadOpen(true)} className="flex items-center gap-2 px-4 py-2 bg-primary text-black rounded-lg hover:bg-primary/90 transition-colors font-bold"><Plus size={18} /> {t('添加素材', 'Add Asset')}</button>
                    </div>
                </div>
                ) : (
                    <div className="flex justify-between items-center bg-red-500/10 p-2 rounded-lg border border-red-500/20 animate-in fade-in slide-in-from-top-2">
                         <div className="flex items-center gap-4">
                             <span className="font-bold text-red-200 ml-2">{t('管理', 'Manage')}</span>
                             <div className="h-6 w-px bg-white/10"></div>
                             <button onClick={() => {
                                 const allIds = filteredAssets.map(a => a.id);
                                 if (selectedIds.size === allIds.length) setSelectedIds(new Set());
                                 else setSelectedIds(new Set(allIds));
                             }} className="text-sm hover:text-white text-white/70">
                                 {selectedIds.size === filteredAssets.length && filteredAssets.length > 0 ? t('取消全选', 'Deselect All') : t('全选', 'Select All')}
                             </button>
                             <span className="text-white/50 text-sm">{selectedIds.size} {t('已选择', 'selected')}</span>
                         </div>
                         <div className="flex items-center gap-2">
                             {isScanning ? (
                                <div className="px-3 py-1.5 text-xs flex items-center gap-2 bg-card border border-white/10 rounded min-w-[120px]">
                                    <Loader2 size={12} className="animate-spin text-yellow-500" />
                                    <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                                        <div className="h-full bg-yellow-500 transition-all duration-300" style={{ width: `${scanProgress}%` }} />
                                    </div>
                                </div>
                             ) : (
                                 <button onClick={handleScanBroken} className="px-3 py-1.5 text-xs bg-card border border-white/10 hover:bg-white/5 rounded flex items-center gap-2 transition-colors text-yellow-500/80 hover:text-yellow-400" title={t('扫描并选中缺失文件', 'Scan & Select Missing Files')}>
                                     <AlertTriangle size={14} /> {t('扫描异常', 'Scan Broken')}
                                 </button>
                             )}
                             <button onClick={handleSelectOld} className="px-3 py-1.5 text-xs bg-card border border-white/10 hover:bg-white/5 rounded flex items-center gap-2 transition-colors" title={t('选择 7 天前的文件', 'Select files > 7 days old')}>
                                 <Calendar size={14} /> {t('选择旧文件', 'Select Old')}
                             </button>
                             <button onClick={handleSelectUnreferenced} className="px-3 py-1.5 text-xs bg-card border border-white/10 hover:bg-white/5 rounded flex items-center gap-2 transition-colors" title={t('选中未被 subject 当前图和 shot 当前图片/视频引用的素材', 'Select assets not referenced by subject current image or shot current image/video')}>
                                 <LinkIcon size={14} /> {t('选中未引用', 'Select Unreferenced')}
                             </button>
                             <button onClick={handleDeleteFiltered} className="px-3 py-1.5 text-xs bg-card border border-white/10 hover:bg-white/5 rounded flex items-center gap-2 transition-colors" title={t('删除当前可见项', 'Delete All Visible')}>
                                 <Layers size={14} /> {t('筛选结果', 'Filtered')}
                             </button>
                             <button 
                                 onClick={handleDeleteSelected} 
                                 disabled={selectedIds.size === 0}
                                 className={`px-3 py-1.5 text-xs bg-red-500 text-white rounded flex items-center gap-2 transition-colors ${selectedIds.size===0 ? 'opacity-50 cursor-not-allowed' : 'hover:bg-red-600'}`}
                             >
                                 <Trash2 size={14} /> {t('删除', 'Delete')} ({selectedIds.size})
                             </button>
                             <button
                                 onClick={handleDownloadSelected}
                                 disabled={selectedIds.size === 0 || isDownloadingSelected}
                                 className={`px-3 py-1.5 text-xs bg-primary text-black rounded flex items-center gap-2 transition-colors ${selectedIds.size===0 || isDownloadingSelected ? 'opacity-50 cursor-not-allowed' : 'hover:bg-primary/90'}`}
                             >
                                 {isDownloadingSelected ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} {t('下载所选', 'Download Selected')} ({selectedIds.size})
                             </button>
                             <div className="h-6 w-px bg-white/10 mx-2"></div>
                             <button onClick={() => { setIsManageMode(false); setSelectedIds(new Set()); }} className="p-1.5 hover:bg-white/10 rounded transition-colors"><X size={18}/></button>
                         </div>
                     </div>
                )}

                {/* Group By Controls */}
                <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
                    <span className="text-xs font-bold text-muted-foreground uppercase mr-2">{t('分组：', 'Group By:')}</span>
                    {[
                        { id: 'none', label: t('无', 'None'), icon: Layers },
                        { id: 'project', label: t('项目', 'Project'), icon: Folder },
                        { id: 'subject', label: t('主体', 'Subject'), icon: User },
                        { id: 'shot', label: t('镜头', 'Shot'), icon: Film },
                    ].map(g => (
                         <button 
                            key={g.id}
                            onClick={() => setGroupBy(g.id)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all whitespace-nowrap ${groupBy === g.id ? 'bg-white text-black border-white' : 'bg-transparent text-muted-foreground border-white/10 hover:border-white/30'}`}
                        >
                            <g.icon size={12} /> {g.label}
                        </button>
                    ))}
                </div>
            </div>

            {showLocalRestoreHint && localAssets.length === 0 && (
                <div className="mb-4 p-3 rounded-lg border border-white/10 bg-card/50 flex items-center justify-between gap-3">
                    <div className="text-xs text-muted-foreground">
                        {t('检测到你之前使用过本地目录。可一键重新读取本地素材。', 'Detected previous local folder usage. Re-mount local media with one click.')}
                    </div>
                    <div className="flex items-center gap-2">
                        <button onClick={pickLocalDirectory} className="px-3 py-1.5 text-xs bg-white text-black rounded hover:bg-white/90 transition-colors">
                            {t('重新读取', 'Re-mount')}
                        </button>
                        <button onClick={() => setShowLocalRestoreHint(false)} className="px-2 py-1.5 text-xs text-muted-foreground hover:text-white transition-colors">
                            {t('关闭', 'Dismiss')}
                        </button>
                    </div>
                </div>
            )}

            {/* Grid */}
            <div className="flex-1 overflow-y-auto min-h-0 pr-2">
                {Object.entries(groupedSections).map(([sectionTitle, sectionAssets]) => (
                    sectionAssets.length > 0 && (
                        <div key={sectionTitle} className="mb-8">
                            <h3 className="text-sm font-bold text-white/50 uppercase mb-4 sticky top-0 bg-black/95 backdrop-blur py-2 z-10 border-b border-white/5 flex items-center gap-2">
                                {groupBy === 'project' && <Folder size={14} />}
                                {groupBy === 'subject' && <User size={14} />}
                                {groupBy === 'shot' && <Film size={14} />}
                                {sectionTitle}
                                {isManageMode && (
                                    <button 
                                        onClick={() => {
                                            const groupIds = sectionAssets.map(a => a.id);
                                            const allSelected = groupIds.every(id => selectedIds.has(id));
                                            const newSet = new Set(selectedIds);
                                            if (allSelected) {
                                                groupIds.forEach(id => newSet.delete(id));
                                            } else {
                                                groupIds.forEach(id => newSet.add(id));
                                            }
                                            setSelectedIds(newSet);
                                        }} 
                                        className="ml-2 text-[10px] bg-white/5 hover:bg-white/10 px-2 py-0.5 rounded text-white/50 hover:text-white transition-colors uppercase tracking-wide"
                                    >
                                        {sectionAssets.every(a => selectedIds.has(a.id)) ? t('取消选择', 'Deselect') : t('全选', 'Select All')}
                                    </button>
                                )}
                                <span className="text-xs bg-white/10 text-white/50 px-2 py-0.5 rounded-full ml-auto">{sectionAssets.length}</span>
                            </h3>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                                {sectionAssets.map(asset => (
                                    <AssetItem 
                                        key={asset.id} 
                                        asset={asset} 
                                        onClick={setSelectedAsset} 
                                        onDelete={handleDelete}
                                        isManageMode={isManageMode}
                                        isSelected={selectedIds.has(asset.id)}
                                        onToggleSelect={toggleSelect}
                                        onReportError={handleReportError}
                                        t={t}
                                    />
                                ))}
                            </div>
                        </div>
                    )
                ))}
                
                {/* Empty State */}
                {filteredAssets.length === 0 && !loading && (
                    <div className="py-20 text-center text-muted-foreground border border-dashed border-white/10 rounded-xl">
                        <Image className="w-12 h-12 mx-auto mb-3 opacity-20" />
                        <p>{t('未找到素材，请先上传。', 'No assets found. Upload some!')}</p>
                    </div>
                )}
            </div>

            {/* Modals */}
            <AnimatePresence>
                {isUploadOpen && (
                    <UploadModal onClose={() => setIsUploadOpen(false)} onUploadSuccess={() => { loadAssets(); setIsUploadOpen(false); }} />
                )}
                {selectedAsset && (
                    <AssetDetailModal asset={selectedAsset} onClose={() => setSelectedAsset(null)} onUpdate={loadAssets} />
                )}
            </AnimatePresence>
        </div>
    );
};

const UploadModal = ({ onClose, onUploadSuccess }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const { addLog } = useLog();
    const [mode, setMode] = useState('file'); // file, url
    const [url, setUrl] = useState('');
    const [file, setFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [meta, setMeta] = useState(null);
    const [type, setType] = useState('image');
    const [remark, setRemark] = useState('');
    const [uploading, setUploading] = useState(false);

    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        }
    }, [previewUrl]);

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (!selectedFile) return;

        setFile(selectedFile);
        const objectUrl = URL.createObjectURL(selectedFile);
        setPreviewUrl(objectUrl);

        // Basic Meta
        const newMeta = {
            size: (selectedFile.size / 1024).toFixed(2) + ' KB',
            type: selectedFile.type,
            name: selectedFile.name
        };

        if (selectedFile.type.startsWith('image')) {
            setType('image');
            const img = new window.Image();
            img.onload = () => {
                setMeta({
                    ...newMeta,
                    resolution: `${img.width}x${img.height}`,
                    width: img.width,
                    height: img.height
                });
            };
            img.src = objectUrl;
        } else if (selectedFile.type.startsWith('video')) {
            setType('video');
            const video = document.createElement('video');
            video.preload = 'metadata';
            video.onloadedmetadata = () => {
                setMeta({
                    ...newMeta,
                    resolution: `${video.videoWidth}x${video.videoHeight}`,
                    duration: video.duration.toFixed(2) + 's'
                });
            };
            video.src = objectUrl;
        } else {
            setMeta(newMeta);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setUploading(true);
        addLog(`Starting upload (${mode})...`);
        try {
            if (mode === 'url') {
                await createAsset({ url, type, remark });
                addLog(`Asset created from URL: ${url}`);
            } else {
                if (!file) return;
                const formData = new FormData();
                formData.append('file', file);
                formData.append('type', type);
                formData.append('remark', remark);
                await uploadAsset(formData);
                addLog(`File uploaded successfully: ${file.name}`);
            }
            onUploadSuccess();
        } catch (e) {
            console.error(e);
            alert("Upload failed");
            addLog(`Upload failed: ${e.message}`, 'error');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <motion.div 
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-md p-6 shadow-2xl"
            >
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-bold">{t('添加新素材', 'Add New Asset')}</h3>
                    <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full"><X size={20} /></button>
                </div>

                <div className="flex gap-2 mb-6 p-1 bg-white/5 rounded-lg">
                    <button 
                        onClick={() => setMode('file')}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all flex justify-center items-center gap-2 ${mode === 'file' ? 'bg-secondary text-white' : 'text-muted-foreground'}`}
                    >
                        <Upload size={16} /> {t('文件上传', 'File Upload')}
                    </button>
                    <button 
                        onClick={() => setMode('url')}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all flex justify-center items-center gap-2 ${mode === 'url' ? 'bg-secondary text-white' : 'text-muted-foreground'}`}
                    >
                        <LinkIcon size={16} /> {t('外部链接', 'External URL')}
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-2 text-muted-foreground">{t('素材类型', 'Asset Type')}</label>
                        <div className="flex gap-4">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input type="radio" checked={type === 'image'} onChange={() => setType('image')} className="accent-primary" />
                                <span>{t('图片', 'Image')}</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input type="radio" checked={type === 'video'} onChange={() => setType('video')} className="accent-primary" />
                                <span>{t('视频', 'Video')}</span>
                            </label>
                        </div>
                    </div>

                    {mode === 'url' ? (
                        <div>
                            <label className="block text-sm font-medium mb-2 text-muted-foreground">URL</label>
                            <input 
                                value={url} onChange={e => setUrl(e.target.value)}
                                className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-sm focus:border-primary outline-none"
                                placeholder="https://..."
                                required
                            />
                        </div>
                    ) : (
                        <div>
                             <label className="block text-sm font-medium mb-2 text-muted-foreground">{t('文件', 'File')}</label>
                             <div className="border-2 border-dashed border-white/10 rounded-xl p-4 text-center hover:border-white/30 transition-colors relative min-h-[160px] flex flex-col items-center justify-center bg-black/20 overflow-hidden group">
                                <input 
                                    type="file" 
                                    accept={type === 'image' ? "image/*" : "video/*"}
                                    onChange={handleFileChange}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                                />
                                
                                {file ? (
                                    <div className="w-full flex flex-col items-center gap-2">
                                        {previewUrl && type === 'image' && (
                                            <img src={previewUrl} className="h-32 object-contain rounded-md shadow-lg border border-white/10" alt="Preview" />
                                        )}
                                        {previewUrl && type === 'video' && (
                                            <video src={previewUrl} className="h-32 object-contain rounded-md shadow-lg border border-white/10" controls />
                                        )}
                                        
                                        <div className="text-primary font-medium text-sm truncate max-w-full px-4">{file.name}</div>
                                        
                                        {/* Metadata Badge */}
                                        {meta && (
                                            <div className="flex gap-2 text-[10px] text-muted-foreground bg-black/40 px-2 py-1 rounded-full border border-white/5">
                                                <span>{meta.size}</span>
                                                {meta.resolution && <span className="border-l border-white/10 pl-2">{meta.resolution}</span>}
                                                {meta.duration && <span className="border-l border-white/10 pl-2">{meta.duration}</span>}
                                            </div>
                                        )}
                                        
                                        <div className="text-[10px] text-muted-foreground mt-1 group-hover:text-white transition-colors">{t('点击替换', 'Click to replace')}</div>
                                    </div>
                                ) : (
                                    <>
                                        <Upload className="w-8 h-8 text-muted-foreground mb-2 opacity-50" />
                                        <div className="text-muted-foreground text-sm">
                                            {t('点击或拖拽选择', 'Click or drop to select')} {type === 'image' ? t('图片', 'image') : t('视频', 'video')}
                                        </div>
                                    </>
                                )}
                             </div>
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium mb-2 text-muted-foreground">{t('备注（可选）', 'Remark (Optional)')}</label>
                        <textarea 
                            value={remark} onChange={e => setRemark(e.target.value)}
                            className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-sm focus:border-primary outline-none resize-none h-20"
                            placeholder={t('添加备注...', 'Add notes...')}
                        />
                    </div>

                    <button 
                        type="submit" 
                        disabled={uploading}
                        className="w-full py-3 bg-primary text-black font-bold rounded-lg hover:bg-primary/90 transition-all disabled:opacity-50 mt-4"
                    >
                        {uploading ? t('处理中...', 'Processing...') : t('添加到素材库', 'Add to Library')}
                    </button>
                </form>
            </motion.div>
        </div>
    );
};

const AssetDetailModal = ({ asset, onClose, onUpdate }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [remark, setRemark] = useState(asset.remark || '');
    const [isEditing, setIsEditing] = useState(false);

    const handleSave = async () => {
        try {
            await updateAsset(asset.id, { remark });
            setIsEditing(false);
            onUpdate();
        } catch (e) {
            console.error(e);
        }
    };

    return (
         <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md p-4" onClick={onClose}>
             <motion.div 
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="w-full max-w-5xl h-[80vh] flex bg-[#121212] border border-white/10 rounded-2xl overflow-hidden shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                {/* Preview Area */}
                <div className="flex-1 bg-black/50 flex items-center justify-center p-8 relative">
                    {asset.type === 'image' ? (
                        <img src={getFullUrl(asset.url)} alt="preview" className="max-w-full max-h-full object-contain rounded-lg shadow-2xl" />
                    ) : (
                        <video src={getFullUrl(asset.url)} controls className="max-w-full max-h-full rounded-lg shadow-2xl" />
                    )}
                    <div className="absolute top-4 left-4 p-2 bg-black/60 backdrop-blur rounded-lg text-xs text-white/50 font-mono">
                        {asset.type.toUpperCase()}
                    </div>
                </div>

                {/* Sidebar Info */}
                <div className="w-80 bg-card border-l border-white/10 p-6 flex flex-col">
                    <div className="flex justify-between items-start mb-6">
                        <h3 className="font-bold text-lg leading-tight break-all">{asset.filename || t('未命名素材', 'Untitled Asset')}</h3>
                        <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full ml-2"><X size={20} /></button>
                    </div>

                    <div className="space-y-6 flex-1 overflow-y-auto">
                        <div>
                            <label className="text-xs font-bold text-muted-foreground uppercase mb-2 block">{t('创建时间', 'Create Date')}</label>
                            <p className="text-sm font-mono text-white/80">{new Date(asset.created_at).toLocaleString()}</p>
                        </div>
                        
                        {asset.meta_info && Object.keys(asset.meta_info).length > 0 && (
                             <div>
                                <label className="text-xs font-bold text-muted-foreground uppercase mb-2 block">{t('元数据', 'Metadata')}</label>
                                <div className="bg-black/30 rounded-lg p-3 space-y-1">
                                    {Object.entries(asset.meta_info).map(([k, v]) => (
                                        <div key={k} className="flex justify-between text-xs">
                                            <span className="text-white/40">{k}:</span>
                                            <span className="font-mono text-white/80">{v}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div>
                            <div className="flex justify-between items-center mb-2">
                                <label className="text-xs font-bold text-muted-foreground uppercase block">{t('用途备注', 'Usage Remark')}</label>
                                {!isEditing && (
                                    <button onClick={() => setIsEditing(true)} className="text-primary hover:text-primary/80"><Edit2 size={12} /></button>
                                )}
                            </div>
                            {isEditing ? (
                                <div className="space-y-2">
                                    <textarea 
                                        value={remark} 
                                        onChange={e => setRemark(e.target.value)}
                                        className="w-full bg-black/20 border border-white/10 rounded p-2 text-sm"
                                        rows={4}
                                    />
                                    <div className="flex gap-2 justify-end">
                                        <button onClick={() => setIsEditing(false)} className="text-xs px-2 py-1 bg-secondary rounded">{t('取消', 'Cancel')}</button>
                                        <button onClick={handleSave} className="text-xs px-2 py-1 bg-primary text-black rounded font-bold">{t('保存', 'Save')}</button>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-sm text-white/70 italic bg-white/5 p-3 rounded-lg min-h-[4rem]">
                                    {asset.remark || t('暂无备注。', 'No remarks added.')}
                                </p>
                            )}
                        </div>

                        {asset.type === 'image' && (
                            <div className="pt-6 border-t border-white/10">
                                <label className="text-xs font-bold text-muted-foreground uppercase mb-2 block">{t('AI 修改', 'AI Modify')}</label>
                                <div className="text-[10px] text-white/40 mb-2">{t('将使用原图作为参考，结果会保存为新素材。', 'Original image will be used as reference. Result will be saved as new asset.')}</div>
                                <RefineControl 
                                    originalText="" 
                                    onUpdate={() => {}} 
                                    currentImage={asset.url}
                                    onImageUpdate={async (url) => {
                                        try {
                                             const res = await fetch(url);
                                             const blob = await res.blob();
                                             const fname = (asset.filename || 'asset').replace(/\.[^/.]+$/, "");
                                             const file = new File([blob], `${fname}_refined.png`, { type: 'image/png' });
                                             await uploadAsset(file);
                                             onUpdate();
                                             alert("Refined version saved as new asset!");
                                        } catch(e) { console.error(e); alert(`Failed to save result: ${e?.message || 'Unknown error'}`); }
                                    }}
                                    type="image"
                                />
                            </div>
                        )}
                        
                        {asset.type === 'image' && (
                             <AnalyzeSection asset={asset} />
                        )}
                    </div>
                </div>
            </motion.div>
         </div>
    );
};

const AnalyzeSection = ({ asset }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [analyzing, setAnalyzing] = useState(false);
    const [result, setResult] = useState('');

    const handleAnalyze = async () => {
        setAnalyzing(true);
        try {
            const data = await analyzeAssetImage(asset.id);
            setResult(data.result);
        } catch (e) {
            console.error(e);
            setResult(t(`分析失败：${e.message}`, `Analysis Failed: ${e.message}`));
        } finally {
            setAnalyzing(false);
        }
    };

    const copyToClipboard = () => {
        if (!result) return;
        navigator.clipboard.writeText(result);
        alert(t('提示词已复制到剪贴板！', 'Prompt copied to clipboard!')); 
    };

    return (
        <div className="pt-6 border-t border-white/10 mt-6">
            <div className="flex justify-between items-center mb-3">
                <label className="text-xs font-bold text-muted-foreground uppercase block flex items-center gap-2">
                    <Sparkles size={12} className="text-primary" />
                    {t('风格分析', 'Style Analysis')}
                </label>
                {result && (
                    <button onClick={copyToClipboard} className="text-white/60 hover:text-white" title={t('复制', 'Copy')}>
                        <Copy size={12} />
                    </button>
                )}
            </div>
            
            {!result && !analyzing && (
                <button 
                    onClick={handleAnalyze}
                    className="w-full py-2 bg-secondary/50 border border-white/10 rounded-lg text-xs font-medium hover:bg-secondary hover:text-white transition-colors flex items-center justify-center gap-2"
                >
                    <Sparkles size={14} />
                    {t('提取风格与提示词', 'Extract Style & Prompt')}
                </button>
            )}

            {analyzing && (
                <div className="flex items-center justify-center py-4 text-xs text-muted-foreground gap-2">
                    <Loader2 size={14} className="animate-spin text-primary" />
                    {t('正在分析图片...', 'Analyzing image...')}
                </div>
            )}

            {result && (
                <div className="relative group">
                    <p className="text-xs leading-relaxed text-white/80 p-3 bg-black/30 border border-white/5 rounded-lg max-h-40 overflow-y-auto font-mono">
                        {result}
                    </p>
                    <button 
                        onClick={() => setResult('')}
                        className="absolute right-2 top-2 p-1 text-white/20 hover:text-red-400 hidden group-hover:block"
                    >
                        <X size={10} />
                    </button>
                </div>
            )}
        </div>
    );
};

export default AssetsLibrary;
