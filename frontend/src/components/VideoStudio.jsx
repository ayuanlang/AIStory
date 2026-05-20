import React, { useState, useEffect } from 'react';
import { fetchScenes, fetchShots, api, waitForAsyncTask, stopAsyncTask, deleteMontageResult, downloadEpisodeShotVideosZip } from '../services/api';
import { Loader2, Play, Plus, Trash2, Film, Save, Clock, Scissors, ChevronRight, GripVertical, Download, Check } from 'lucide-react';
import { getUiLang, tUI } from '../lib/uiLang';

const buildMontageHistoryStorageKey = (projectId) => {
    const stableProjectId = String(projectId || '').trim();
    return stableProjectId ? `aistory.montageHistory.${stableProjectId}` : '';
};

const readMontageHistory = (projectId) => {
    const storageKey = buildMontageHistoryStorageKey(projectId);
    if (!storageKey) return [];
    try {
        const raw = localStorage.getItem(storageKey);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
};

const writeMontageHistory = (projectId, items) => {
    const storageKey = buildMontageHistoryStorageKey(projectId);
    if (!storageKey) return;
    const stableItems = Array.isArray(items) ? items.slice(0, 12) : [];
    if (stableItems.length === 0) {
        localStorage.removeItem(storageKey);
        return;
    }
    localStorage.setItem(storageKey, JSON.stringify(stableItems));
};

const formatMontageTime = (value) => {
    const ts = Number(value || 0);
    if (!Number.isFinite(ts) || ts <= 0) return '';
    try {
        return new Date(ts).toLocaleString();
    } catch {
        return '';
    }
};

const getMontageProgressMeta = (status, startedAt) => {
    const stableStatus = String(status || '').trim().toLowerCase();
    const elapsedMs = Math.max(0, Date.now() - Number(startedAt || Date.now()));
    const runningPercent = Math.min(88, 24 + Math.floor(elapsedMs / 4000) * 6);

    if (stableStatus === 'queued' || stableStatus === 'pending') {
        return { labelZh: '排队中', labelEn: 'Queued', percent: 16 };
    }
    if (stableStatus === 'completed') {
        return { labelZh: '已完成', labelEn: 'Completed', percent: 100 };
    }
    if (stableStatus === 'failed') {
        return { labelZh: '失败', labelEn: 'Failed', percent: 100 };
    }
    if (stableStatus === 'canceled' || stableStatus === 'cancelled') {
        return { labelZh: '已取消', labelEn: 'Canceled', percent: 100 };
    }
    return { labelZh: '渲染中', labelEn: 'Rendering', percent: runningPercent };
};

const VideoStudio = ({ activeEpisode, projectId, onLog }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [scenes, setScenes] = useState([]);
    const [shots, setShots] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedSceneId, setSelectedSceneId] = useState('all');
    
    // Playlist State
    const [playlist, setPlaylist] = useState([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isDownloadingAllShots, setIsDownloadingAllShots] = useState(false);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [isCleaningMontage, setIsCleaningMontage] = useState(false);
    const [activeMontageTaskId, setActiveMontageTaskId] = useState(null);
    const [activeMontageTaskStatus, setActiveMontageTaskStatus] = useState('idle');
    const [activeMontageStartedAt, setActiveMontageStartedAt] = useState(0);
    const [montageHistory, setMontageHistory] = useState([]);

    useEffect(() => {
        loadData();
    }, [activeEpisode]);

    useEffect(() => {
        setMontageHistory(readMontageHistory(projectId));
    }, [projectId]);

    useEffect(() => {
        writeMontageHistory(projectId, montageHistory);
    }, [montageHistory, projectId]);

    useEffect(() => {
        if (!activeMontageTaskId) {
            setActiveMontageTaskStatus('idle');
        }
    }, [activeMontageTaskId]);

    const pushMontageHistoryItem = (url, options = {}) => {
        const stableUrl = String(url || '').trim();
        if (!stableUrl) return;
        setMontageHistory((prev) => {
            const withoutDup = (Array.isArray(prev) ? prev : []).filter((item) => String(item?.url || '').trim() !== stableUrl);
            return [
                {
                    id: String(options.id || `${Date.now()}-${Math.random()}`),
                    url: stableUrl,
                    createdAt: Number(options.createdAt || Date.now()),
                    clipCount: Number(options.clipCount || playlist.length || 0),
                    label: String(options.label || '').trim(),
                },
                ...withoutDup,
            ].slice(0, 12);
        });
    };

    const removeMontageHistoryItem = (url) => {
        const stableUrl = String(url || '').trim();
        if (!stableUrl) return;
        setMontageHistory((prev) => (Array.isArray(prev) ? prev : []).filter((item) => String(item?.url || '').trim() !== stableUrl));
    };

    const loadData = async () => {
        if (!activeEpisode) return;
        setLoading(true);
        try {
            const scenesData = await fetchScenes(activeEpisode.id);
            setScenes(scenesData);

            // Fetch shots for all scenes in parallel
            const shotsPromises = scenesData.map(scene => fetchShots(scene.id));
            const shotsArrays = await Promise.all(shotsPromises);
            
            // Flatten and filter for videos
            const allShots = shotsArrays.flat().filter(s => s.video_url);
            setShots(allShots);
        } catch (error) {
            console.error(error);
            onLog("Failed to load video assets", "error");
        } finally {
            setLoading(false);
        }
    };

    const addToPlaylist = (shot) => {
        const newItem = {
            id: Date.now() + Math.random().toString(), // Helper ID for list mapping
            shotId: shot.id,
            url: shot.video_url,
            thumbnail: shot.image_url, // Assuming shot has image_url as thumbnail
            shotNumber: shot.shot_number,
            shotName: String(shot.shot_name || shot.title || shot.description || '').trim(),
            shotDisplayName: String(shot.shot_name || '').trim() || t(`镜头 ${shot.shot_number}`, `Shot ${shot.shot_number}`),
            description: shot.description,
            speed: 1.0,
            trimStart: 0,
            trimEnd: 0, // 0 means no trim from end
            originalDuration: shot.duration || 4.0 // Default 4s if unknown
        };
        setPlaylist([...playlist, newItem]);
    };

    const updatePlaylistItem = (id, changes) => {
        setPlaylist(prev => prev.map(item => item.id === id ? { ...item, ...changes } : item));
    };

    const removeFromPlaylist = (id) => {
        setPlaylist(prev => prev.filter(item => item.id !== id));
    };

    const moveItem = (index, direction) => {
        const newPlaylist = [...playlist];
        if (direction === 'up' && index > 0) {
            [newPlaylist[index], newPlaylist[index - 1]] = [newPlaylist[index - 1], newPlaylist[index]];
        }
        if (direction === 'down' && index < newPlaylist.length - 1) {
            [newPlaylist[index], newPlaylist[index + 1]] = [newPlaylist[index + 1], newPlaylist[index]];
        }
        setPlaylist(newPlaylist);
    };

    const handleGenerateMontage = async () => {
        if (playlist.length === 0 || isGenerating) return;
        
        setIsGenerating(true);
        setPreviewUrl(null);
        setActiveMontageStartedAt(Date.now());
        setActiveMontageTaskStatus('queued');
        
        try {
            const response = await api.post(`/projects/${projectId}/montage?async_mode=1`, {
                items: playlist.map(item => ({
                    url: item.url,
                    speed: parseFloat(item.speed),
                    trim_start: parseFloat(item.trimStart),
                    trim_end: parseFloat(item.trimEnd)
                }))
            });

            if (response.data?.task_id && response.data?.async) {
                setActiveMontageTaskId(response.data.task_id);
                setActiveMontageTaskStatus('running');
                onLog?.(t('蒙太奇渲染任务已提交，后台处理中。', 'Montage render task submitted and running in background.'), 'info');
                const result = await waitForAsyncTask(response.data.task_id, { timeout: 30 * 60 * 1000, interval: 3000 });
                if (result?.url) {
                    setActiveMontageTaskStatus('completed');
                    setPreviewUrl(result.url);
                    pushMontageHistoryItem(result.url, {
                        id: response.data.task_id,
                        createdAt: Date.now(),
                        clipCount: playlist.length,
                        label: playlist[0]?.shotDisplayName || '',
                    });
                    onLog("Montage generated successfully!", "success");
                }
            } else if (response.data.url) {
                setActiveMontageTaskStatus('completed');
                setPreviewUrl(response.data.url);
                pushMontageHistoryItem(response.data.url, {
                    createdAt: Date.now(),
                    clipCount: playlist.length,
                    label: playlist[0]?.shotDisplayName || '',
                });
                onLog("Montage generated successfully!", "success");
            }
        } catch (error) {
            console.error(error);
            setActiveMontageTaskStatus('failed');
            onLog("Failed to generate montage: " + (error.response?.data?.detail || error.message), "error");
        } finally {
            setActiveMontageTaskId(null);
            setIsGenerating(false);
        }
    };

    const handleClearMontage = async () => {
        const activeTaskId = activeMontageTaskId;
        const stablePreviewUrl = String(previewUrl || '').trim();
        if (!activeTaskId && !stablePreviewUrl) return;

        setIsCleaningMontage(true);
        try {
            if (activeTaskId) {
                await stopAsyncTask(activeTaskId);
                setActiveMontageTaskId(null);
                onLog?.(t('已取消蒙太奇渲染任务。', 'Montage render task canceled.'), 'warning');
            }
            if (stablePreviewUrl) {
                await deleteMontageResult(projectId, stablePreviewUrl);
                removeMontageHistoryItem(stablePreviewUrl);
                onLog?.(t('已清理蒙太奇结果文件。', 'Montage result file cleared.'), 'warning');
            }
            setPreviewUrl(null);
        } catch (error) {
            console.error(error);
            onLog?.(
                t('清理蒙太奇失败：', 'Failed to clear montage: ') + (error.response?.data?.detail || error.message),
                'error'
            );
        } finally {
            setIsCleaningMontage(false);
            setIsGenerating(false);
        }
    };

    const handleSelectMontageHistoryItem = (item) => {
        const stableUrl = String(item?.url || '').trim();
        if (!stableUrl) return;
        setPreviewUrl(stableUrl);
    };

    const handleDeleteMontageHistoryItem = async (item) => {
        const stableUrl = String(item?.url || '').trim();
        if (!stableUrl) return;
        setIsCleaningMontage(true);
        try {
            await deleteMontageResult(projectId, stableUrl);
            removeMontageHistoryItem(stableUrl);
            if (String(previewUrl || '').trim() === stableUrl) {
                setPreviewUrl(null);
            }
            onLog?.(t('已删除历史蒙太奇结果。', 'Historical montage result deleted.'), 'warning');
        } catch (error) {
            console.error(error);
            onLog?.(t('删除历史蒙太奇失败：', 'Failed to delete montage history item: ') + (error.response?.data?.detail || error.message), 'error');
        } finally {
            setIsCleaningMontage(false);
        }
    };

    const handleDownloadAllShots = async () => {
        if (isDownloadingAllShots) return;
        if (!activeEpisode?.id) {
            onLog?.(t('当前剧集无效，无法下载分镜视频。', 'Active episode is invalid, unable to download shot videos.'), 'warning');
            return;
        }

        const uniqueUrls = Array.from(
            new Set(
                (Array.isArray(shots) ? shots : [])
                    .map((shot) => String(shot?.video_url || '').trim())
                    .filter(Boolean)
            )
        );

        if (uniqueUrls.length === 0) {
            onLog?.(t('当前剧集没有可下载的分镜视频。', 'No shot videos available for download in this episode.'), 'warning');
            return;
        }

        setIsDownloadingAllShots(true);
        try {
            const result = await downloadEpisodeShotVideosZip(
                activeEpisode.id,
                `episode_${activeEpisode.id}_shot_videos.zip`
            );
            const completedCount = Number(result?.count || uniqueUrls.length || 0);
            const failureCount = Number(result?.failures || 0);

            onLog?.(
                t(
                    `已开始下载分镜视频压缩包，包含 ${completedCount} 个视频。`,
                    `Started downloading the shot video archive with ${completedCount} videos.`
                ),
                failureCount > 0 ? 'warning' : 'success'
            );

            if (failureCount > 0) {
                onLog?.(
                    t(
                        `${failureCount} 个分镜视频未能打包进压缩包。`,
                        `${failureCount} shot videos could not be added to the archive.`
                    ),
                    'warning'
                );
            }
        } catch (error) {
            console.error(error);
            onLog?.(
                t('下载分镜视频压缩包失败：', 'Failed to download shot video archive: ') + (error.response?.data?.detail || error.message),
                'error'
            );
        } finally {
            setIsDownloadingAllShots(false);
        }
    };

    const filteredShots = selectedSceneId === 'all' 
        ? shots 
        : shots.filter(s => s.scene_id === selectedSceneId);

    // Calculate total estimated duration
    const totalDuration = playlist.reduce((acc, item) => {
        const effectiveDuration = (item.originalDuration - item.trimStart - item.trimEnd) / item.speed;
        return acc + (effectiveDuration > 0 ? effectiveDuration : 0);
    }, 0);

    const montageProgressMeta = getMontageProgressMeta(activeMontageTaskStatus, activeMontageStartedAt);

    return (
        <div className="h-full flex flex-col md:flex-row gap-4 p-4 text-gray-100 overflow-hidden">
            {/* Left Panel: Library */}
            <div className="w-full md:w-1/3 flex flex-col bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800">
                    <h2 className="font-semibold flex items-center gap-2">
                        <Film size={18} /> {t('素材库', 'Library')}
                    </h2>
                    <select 
                        className="bg-gray-700 border-none rounded px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-blue-500"
                        value={selectedSceneId}
                        onChange={(e) => setSelectedSceneId(e.target.value)}
                    >
                        <option value="all">{t('全部场景', 'All Scenes')}</option>
                        {scenes.map(s => (
                            <option key={s.id} value={s.id}>{t(`场景 ${s.scene_number}`, `Scene ${s.scene_number}`)}</option>
                        ))}
                    </select>
                </div>
                
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {loading ? (
                        <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>
                    ) : filteredShots.length === 0 ? (
                        <div className="text-gray-500 text-center p-4">{t('未找到视频素材，请先生成分镜视频。', 'No videos found. Generate some shots first!')}</div>
                    ) : (
                        filteredShots.map(shot => (
                            <div key={shot.id} className="group relative bg-gray-800 rounded border border-gray-700 hover:border-blue-500 transition-colors cursor-pointer overflow-hidden p-2 flex gap-3 items-center" onClick={() => addToPlaylist(shot)}>
                                <div className="w-20 h-12 bg-black rounded overflow-hidden flex-shrink-0 relative">
                                    {shot.image_url ? (
                                        <img src={shot.image_url} alt="" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center bg-gray-700"><Film size={12}/></div>
                                    )}
                                    <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Plus className="text-white" size={20} />
                                    </div>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium truncate">{String(shot.shot_name || '').trim() || t(`镜头 ${shot.shot_number}`, `Shot ${shot.shot_number}`)}</div>
                                    <div className="text-xs text-gray-400 truncate">{String(shot.shot_id || shot.shot_number || '').trim() || shot.description}</div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Right Panel: Timeline / Editor */}
            <div className="flex-1 flex flex-col bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800">
                    <h2 className="font-semibold flex items-center gap-2">
                        <Scissors size={18} /> {t(`蒙太奇（${playlist.length} 段）`, `Montage (${playlist.length} clips)`)}
                    </h2>
                    <div className="text-sm text-gray-400 flex items-center gap-2">
                        <Clock size={14} /> {t('预计时长：', 'Estimated: ')}{totalDuration.toFixed(1)}s
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-950/50">
                    <div className="bg-gray-900/70 border border-gray-800 rounded-lg overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900">
                            <div className="flex items-center gap-2 text-sm font-medium text-gray-200">
                                <Play size={16} /> {t('结果预览', 'Result Preview')}
                            </div>
                            {(previewUrl || activeMontageTaskId) && (
                                <button
                                    onClick={handleClearMontage}
                                    disabled={isCleaningMontage}
                                    className="flex items-center gap-2 px-3 py-1.5 text-xs rounded bg-red-600/15 text-red-300 hover:bg-red-600/25 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    {isCleaningMontage ? <Loader2 className="animate-spin" size={14} /> : <Trash2 size={14} />}
                                    {activeMontageTaskId ? t('取消并清理', 'Cancel & Clear') : t('清理结果', 'Clear Result')}
                                </button>
                            )}
                        </div>
                        <div className="aspect-video bg-black flex items-center justify-center">
                            {previewUrl ? (
                                <video
                                    key={previewUrl}
                                    src={previewUrl}
                                    controls
                                    preload="metadata"
                                    className="w-full h-full"
                                />
                            ) : isGenerating ? (
                                <div className="flex flex-col items-center gap-3 text-gray-400">
                                    <Loader2 className="animate-spin" size={28} />
                                    <div className="w-64 max-w-[80%] space-y-2">
                                        <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-gray-500">
                                            <span>{t(montageProgressMeta.labelZh, montageProgressMeta.labelEn)}</span>
                                            <span>{montageProgressMeta.percent}%</span>
                                        </div>
                                        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                                            <div className="h-full bg-blue-500 transition-all duration-500" style={{ width: `${montageProgressMeta.percent}%` }} />
                                        </div>
                                    </div>
                                    <span className="text-sm">{t('蒙太奇渲染中，完成后会显示在这里。', 'Montage is rendering and will appear here when finished.')}</span>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center gap-3 text-gray-500">
                                    <Film size={28} />
                                    <span className="text-sm">{t('渲染完成后的蒙太奇会显示在这里。', 'Rendered montage will appear here.')}</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {montageHistory.length > 0 && (
                        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4 space-y-3">
                            <div className="flex items-center justify-between">
                                <div className="text-sm font-medium text-gray-200">{t('最近结果', 'Recent Results')}</div>
                                <div className="text-[11px] uppercase tracking-[0.14em] text-gray-500">{montageHistory.length}</div>
                            </div>
                            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                                {montageHistory.map((item) => (
                                    <div key={item.id} className="border border-gray-800 rounded-lg bg-black/20 overflow-hidden">
                                        <button
                                            onClick={() => handleSelectMontageHistoryItem(item)}
                                            className="w-full text-left p-3 hover:bg-white/5 transition-colors"
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="text-sm font-medium text-gray-100 truncate">{item.label || t('蒙太奇结果', 'Montage Result')}</div>
                                                    <div className="text-xs text-gray-400 truncate">{t('片段数：', 'Clips: ')}{Number(item.clipCount || 0)}</div>
                                                    <div className="text-[11px] text-gray-500 truncate">{formatMontageTime(item.createdAt)}</div>
                                                </div>
                                                <Play size={14} className="text-gray-500 shrink-0 mt-1" />
                                            </div>
                                        </button>
                                        <div className="px-3 pb-3 flex items-center justify-between gap-3">
                                            <a href={item.url} target="_blank" download className="text-xs text-blue-400 hover:text-blue-300">
                                                {t('下载', 'Download')}
                                            </a>
                                            <button
                                                onClick={() => handleDeleteMontageHistoryItem(item)}
                                                disabled={isCleaningMontage}
                                                className="text-xs text-red-300 hover:text-red-200 disabled:opacity-50"
                                            >
                                                {t('删除', 'Delete')}
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {playlist.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-gray-500 border-2 border-dashed border-gray-800 rounded-lg">
                            <Film size={48} className="mb-4 opacity-20" />
                            <p>{t('将片段拖拽到这里，或在素材库点击 + 添加', 'Drag clips here or click + from Library')}</p>
                        </div>
                    ) : (
                        playlist.map((item, index) => (
                            <div key={item.id} className="bg-gray-800 p-3 rounded border border-gray-700 flex flex-col gap-3 group">
                                <div className="flex items-start gap-4">
                                    <div className="flex flex-col gap-1 items-center justify-center pt-2">
                                        <button onClick={() => moveItem(index, 'up')} disabled={index === 0} className="p-1 hover:bg-gray-700 rounded disabled:opacity-20"><ChevronRight className="-rotate-90" size={14} /></button>
                                        <span className="text-xs text-gray-500 font-mono">{index + 1}</span>
                                        <button onClick={() => moveItem(index, 'down')} disabled={index === playlist.length - 1} className="p-1 hover:bg-gray-700 rounded disabled:opacity-20"><ChevronRight className="rotate-90" size={14} /></button>
                                    </div>

                                    {/* Thumbnail Preview */}
                                    <div className="w-32 h-20 bg-black rounded overflow-hidden flex-shrink-0 relative">
                                        {item.thumbnail && <img src={item.thumbnail} className="w-full h-full object-cover opacity-50" />}
                                        <div className="absolute inset-0 flex items-center justify-center">
                                            <span className="text-xs font-mono bg-black/50 px-1 rounded text-white">{item.shotDisplayName}</span>
                                        </div>
                                    </div>

                                    {/* Controls */}
                                    <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-4">
                                        <div className="flex flex-col gap-1">
                                            <label className="text-xs text-gray-400">{t('速度', 'Speed')}</label>
                                            <select 
                                                className="bg-gray-700 border-none rounded px-2 py-1 text-xs"
                                                value={item.speed}
                                                onChange={(e) => updatePlaylistItem(item.id, { speed: e.target.value })}
                                            >
                                                <option value="0.5">{t('0.5x（慢）', '0.5x (Slow)')}</option>
                                                <option value="1.0">{t('1.0x（正常）', '1.0x (Normal)')}</option>
                                                <option value="1.5">{t('1.5x（快）', '1.5x (Fast)')}</option>
                                                <option value="2.0">{t('2.0x（两倍速）', '2.0x (2x Fast)')}</option>
                                            </select>
                                        </div>

                                        <div className="flex flex-col gap-1">
                                            <label className="text-xs text-gray-400">{t('起始裁剪（秒）', 'Trim Start (s)')}</label>
                                            <input 
                                                type="number" step="0.1" min="0"
                                                className="bg-gray-700 border-none rounded px-2 py-1 text-xs w-full"
                                                value={item.trimStart}
                                                onChange={(e) => updatePlaylistItem(item.id, { trimStart: parseFloat(e.target.value) || 0 })}
                                            />
                                        </div>

                                        <div className="flex flex-col gap-1">
                                            <label className="text-xs text-gray-400">{t('结束裁剪（秒）', 'Trim End (s)')}</label>
                                            <input 
                                                type="number" step="0.1" min="0"
                                                className="bg-gray-700 border-none rounded px-2 py-1 text-xs w-full"
                                                value={item.trimEnd}
                                                onChange={(e) => updatePlaylistItem(item.id, { trimEnd: parseFloat(e.target.value) || 0 })}
                                            />
                                        </div>
                                        
                                        <div className="flex items-center justify-end">
                                            <button 
                                                onClick={() => removeFromPlaylist(item.id)}
                                                className="p-2 hover:bg-red-900/50 text-red-400 rounded transition-colors"
                                                title={t('从蒙太奇中移除', 'Remove from montage')}
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>

                <div className="p-4 bg-gray-800 border-t border-gray-700 flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={handleDownloadAllShots}
                            disabled={loading || isDownloadingAllShots || shots.length === 0}
                            className="flex items-center gap-2 text-sm px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {isDownloadingAllShots ? <Loader2 className="animate-spin" size={16} /> : <Download size={16} />}
                            {isDownloadingAllShots ? t('下载中...', 'Downloading...') : t('下载全部分镜', 'Download All Shots')}
                        </button>
                        {previewUrl && (
                             <a href={previewUrl} target="_blank" download className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm">
                                          <Download size={16} /> {t('下载蒙太奇', 'Download Montage')}
                             </a>
                        )}
                    </div>
                    
                    <button 
                        onClick={handleGenerateMontage}
                        disabled={playlist.length === 0 || isGenerating || isCleaningMontage}
                        className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {isGenerating ? <Loader2 className="animate-spin" size={18} /> : <Film size={18} />}
                        {isGenerating ? t('渲染中...', 'Rendering...') : t('渲染蒙太奇', 'Render Montage')}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default VideoStudio;
