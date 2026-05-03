
import FunctionApiSelector, { useFunctionApis } from '../../../components/FunctionApiSelector';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../../../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../../../lib/store';
import LogPanel from '../../../components/LogPanel';
import ProjectStatusBar from '../../../components/ProjectStatusBar';
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL, ASSET_BASE_URL } from '../../../config';
import { setUiLang as setGlobalUiLang } from '../../../lib/uiLang';

import {
    getFullUrl, createInitialFrameTrimState, clampFrameTrimPercent, normalizeFrameTrimMargins, brokenMediaUrls, brokenSceneImageUrls, warmMediaUrls, shouldBypassBrokenMediaCache, rememberBrokenMediaUrl, isBrokenMediaUrl, rememberWarmMediaUrl, isWarmMediaUrl, getSafeMediaUrl, extractImageJobResultUrl, rememberBrokenSceneImageUrl, isBrokenSceneImageUrl, normalizeBatchParallelLimit, normalizeAsciiSubjectSeparatorsForDeps, normalizeSubjectNameForDeps, normalizeSubjectKeyForDeps, normalizeAsciiSubjectSeparators, normalizeSubjectName, normalizeSubjectKey, normalizeImportSubjectKey, IMG_PLACEHOLDER_SRC, parseVisualDependencies, SafeImage, SafeAudio, normalizeMediaRefList, areMediaRefListsEqual, collectMatchedEntitiesFromPrompt, collectMatchedEntityImageUrlsFromPrompt, SCENE_SUBJECT_TYPE_LABELS, getSceneSubjectStatusKey, splitSceneSubjectNames, normalizeSceneSubjectDefaultType, parseTypedSceneSubjectToken, extractSceneSubjectRefsFromField, buildSceneSubjectNameCandidates, extractSceneSubjectRefs, findMatchingEntityByType, findMissingSceneSubjectRefs, findCrossTypeEntityMatches, buildSceneSubjectPlaceholderPayload, createMissingSceneSubjectPlaceholders, collectMatchedSubjectImageUrlsFromPrompt, resolveUnifiedVideoMode, buildAutoVideoRefList, resolveShotVideoPosterUrl, LazyHoverVideo, InViewVideo, ManagedVideoPlayer, parseEpisodeNumberFromText, normalizeEpisodeTitleForDisplay, buildEntityNegativePrompt, normalizeImageSizeOption, normalizeAspectRatioOption, parseAspectRatioParts, parseAspectRatioValue, reduceAspectRatioParts, buildAspectRatioString, inferImageSizeFromResolution, getEpisodePreferredImageSize, getEpisodePreferredAspectRatio, getProjectPreferredImageSize, getProjectPreferredAspectRatio, buildShotDiptychPlan, getShotDiptychLayoutLabel, buildShotDiptychLayoutInstruction, buildShotDiptychAspectContract, getShotDiptychSeamTrimPx, getShotDiptychSeamBiasPx, getShotDiptychFallbackCropPx, JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION, SHOT_FRAME_ASSET_UPLOAD_VERSION, hashStableText, buildJointShotDiptychUploadIdempotencyKey, buildShotFrameAssetUploadIdempotencyKey, collectSupportedAspectRatioOptions, collectSupportedImageSizeOptions, selectBestShotDiptychRequestAspectRatio, selectBestSupportedImageSize, resolveShotPanelExportResolution, resolveShotDiptychRequestResolution, getResolutionByAspectAndImageSize, SHOT_IMAGE_CFG_MIN, SHOT_IMAGE_CFG_MAX, SHOT_IMAGE_CFG_STEP, SHOT_IMAGE_CFG_FALLBACK, clampShotImageCfg, resolveShotImageCfgDefault, extractDialogueOnlyFromPrompt, inferLanguageCodeFromProjectLanguage, buildVoicePromptWithEntityContext, buildEpisodeDisplayLabel
} from '../editorHelpers';

import { 
    fetchProject, 
    updateProject,
    generateProjectStoryGlobal,
    analyzeProjectNovel,
    generateProjectCharacterProfile,
    fetchEpisodes, 
    createEpisode, 
    updateEpisode,
    updateEpisodeSegments,
    deleteEpisode,
    fetchScenes, 
    createScene,
    updateScene, 
    deleteScene,
    regenerateScene,
    fetchShots,
    fetchEpisodeShots,
    createShot,
    updateShot,
    deleteShot,
    fetchEntities, 
    createEntity,
    cloneEntityWithLLM,
    updateEntity,
    deleteEntity,
    deleteAllEntities,
    generateImage,
    submitImageGenerationJob,
    getImageGenerationJobStatus,
    generateVideo,
    generateVoice,
    fetchAssets, 
    generateSceneShots,
    regenerateSceneShots,
    fetchSceneShotsPrompt,
    createAsset,
    uploadAsset,
    getSettings,
    getSystemSettings,
    getPromptSubmitLanguagePreference,
    resolvePromptSubmitLanguage,
    translateText,
    refinePrompt,
    analyzeScene,
    waitForAsyncTask,
    stopAsyncTask,
    fetchPrompt,
    fetchMe,
    fetchShot,
    analyzeEntityImage,
    applySceneAIResult,
    updateSceneLatestAIResult,
    getSceneLatestAIResult,
    generateEpisodeCharacterProfile,
    generateEpisodeScenes,
    generateProjectEpisodeScripts,
    getProjectEpisodeScriptsStatus,
    stopProjectEpisodeScripts,
    startSceneAiShotsBatch,
    getSceneAiShotsBatchStatus,
    stopSceneAiShotsBatch,
    startEpisodeScenesGeneration,
    getEpisodeScenesGenerationStatus,
    stopEpisodeScenesGeneration,
    startShotMediaBatch,
    getShotMediaBatchStatus,
    getVideoGenerationJobStatus,
    getGenerationJobPool,
    stopGenerationJob,
    deleteGenerationJob,
    stopAllGenerationJobs,
    stopShotMediaBatch,
    saveProjectStoryGeneratorGlobalInput,
    exportProjectStoryGlobalPackage,
    importProjectStoryGlobalPackage,
    saveProjectCharacterCanonInput,
    saveProjectCharacterCanonCategories,
    updateProjectCharacterProfiles,
    fetchProjectReviewThreads,
    createProjectReviewThread,
    fetchReviewThreadRounds,
    fetchReviewRoundMessages,
    createReviewRoundMessage,
    markReviewThreadRead,
    recordSystemLogAction,
    rebindShotMediaAssets,
    getCachedUserPreferences,
    fetchUnreferencedAssetIds,
    markAssetAsCurrentProjectAsset
} from '../../../services/api';

import RefineControl from '../../../components/RefineControl.jsx';
import VideoStudio from '../../../components/VideoStudio';
import InputGroup from './InputGroup';
import MarkdownCell from './MarkdownCell';
import {
    PROVIDER_LABELS,
    MODEL_OPTIONS,
    getSettingSourceByCategory,
    formatProviderModelEndpointError,
} from '../editorConfig';
import {
    PROJECT_EP_TYPE_OPTIONS,
    PROJECT_EP_LANGUAGE_OPTIONS,
    PROJECT_EP_BASE_POSITIONING_OPTIONS,
    PROJECT_EP_GLOBAL_STYLE_OPTIONS,
    PROJECT_EP_TONE_OPTIONS,
    PROJECT_EP_LIGHTING_OPTIONS,
    PROJECT_EP_QUALITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_ERA_OPTIONS,
    PROJECT_SCENE_ANALYSIS_REGION_OPTIONS,
    PROJECT_SCENE_ANALYSIS_MODEL_FAMILY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_WORKFLOW_OPTIONS,
    PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS,
    PROJECT_SCENE_ANALYSIS_CHARACTER_EMPHASIS_OPTIONS,
    PROJECT_SCENE_ANALYSIS_NARRATIVE_DENSITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_COMMERCIAL_CONSTRAINT_OPTIONS,
    PROJECT_SCENE_ANALYSIS_MODALITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_CONTINUITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_DEFAULTS,
    normalizeProjectEpisodeType,
    normalizeProjectEpisodeLanguage,
    normalizeProjectEpisodeBasePositioning,
    normalizeProjectEpisodeGlobalStyle,
    normalizeProjectEpisodeTone,
    normalizeProjectEpisodeLighting,
    normalizeProjectEpisodeQuality,
} from '../projectOptionConfig';

// RefineControl moved to components/RefineControl.jsx
import { processPrompt } from '../../../lib/promptUtils';
import { entityNameAppearsInText, entityTokenMatchesName, normalizeEntityToken } from '../../../lib/entityToken';
import SettingsPage from '../../Settings';
import { confirmUiMessage, promptUiMessage } from '../../../lib/uiMessage';

// Character Canon (Authoritative) generator (shared)

import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, DEFAULT_CANON_IDENTITY_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint } from '../editorConstants';
export const MediaDetailModal = ({ media, onClose }) => {
    if (!media) return null;

    return (
           <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-8" onClick={onClose}>
               <div className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden max-w-6xl w-full max-h-[90vh] flex flex-col lg:flex-row shadow-2xl" onClick={e => e.stopPropagation()}>
                {/* Media Area */}
                <div className="flex-1 bg-black/50 flex items-center justify-center p-3 sm:p-4 relative group/modal min-h-[260px] sm:min-h-[400px]">
                    {media.type === 'video' ? (
                        <InViewVideo
                            src={media.url}
                            controls
                            autoPlay
                            className="max-w-full max-h-full shadow-lg rounded"
                            visibleDelayMs={160}
                            fallback={<Video className="w-8 h-8 opacity-30" />}
                        />
                    ) : (
                        <SafeImage src={media.url} className="max-w-full max-h-full object-contain shadow-lg rounded" alt="Detail" />
                    )}
                    
                    <button 
                        className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full hover:bg-white/20 transition-colors"
                        onClick={onClose}
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Metadata Sidebar */}
                <div className="w-full lg:w-80 bg-[#151515] border-t lg:border-t-0 lg:border-l border-white/10 p-4 sm:p-6 flex flex-col gap-4 overflow-y-auto shrink-0 max-h-[40vh] lg:max-h-none">
                    <div>
                        <h3 className="text-xl font-bold text-white mb-1 truncate" title={media.title || 'Media Details'}>{media.title || 'Media Details'}</h3>
                        <div className="text-xs text-muted-foreground uppercase font-bold">{media.type || 'Image'} Asset</div>
                    </div>

                    <div className="space-y-4">
                        {media.prompt && (
                             <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                <span className="text-[10px] uppercase font-bold text-primary/70 block mb-1">{t('提示词 / 描述', 'Prompt / Description')}</span>
                                <p className="text-xs text-gray-300 leading-relaxed font-mono">
                                    {media.prompt}
                                </p>
                            </div>
                        )}
                        
                        <div className="grid grid-cols-2 gap-2">
                             <div className="bg-white/5 p-2 rounded border border-white/5">
                                <span className="text-[10px] uppercase text-gray-500 block">{t('分辨率', 'Resolution')}</span>
                                <span className="text-xs text-gray-300">{media.resolution || 'Unknown'}</span>
                            </div>
                             <div className="bg-white/5 p-2 rounded border border-white/5">
                                <span className="text-[10px] uppercase text-gray-500 block">{t('来源', 'Source')}</span>
                                <span className="text-xs text-gray-300">{media.source || 'Generated'}</span>
                            </div>
                        </div>

                         {/* JSON Metadata */}
                         {media.metadata && (
                            <div className="space-y-1">
                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('技术元数据', 'Technical Metadata')}</h4>
                                <div className="p-2 bg-black/40 rounded border border-white/5 text-[10px] font-mono text-gray-400 overflow-x-auto whitespace-pre-wrap">
                                    {typeof media.metadata === 'string' ? media.metadata : JSON.stringify(media.metadata, null, 2)}
                                </div>
                            </div>
                         )}

                         <div className="mt-auto pt-4 border-t border-white/10">
                            <a href={media.url} download target="_blank" rel="noopener noreferrer" className="w-full py-2 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded flex items-center justify-center gap-2 text-sm font-medium transition-colors">
                                <Download size={16}/> Download Original
                            </a>
                         </div>
                    </div>
                </div>
             </div>
        </div>
    );
};

export const AssetHoverMetaOverlay = ({ asset, t, entities = [], position = 'top' }) => {
    if (!asset) return null;

    const meta = (asset.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
    const fileName = String(
        asset.name
        || meta.original_filename
        || meta.filename
        || String(asset.url || '').split('/').pop()
        || ''
    ).trim() || t('未命名文件', 'Untitled File');
    const assetType = String(asset.type || meta.type || '').trim().toLowerCase();
    const resolution = String(meta.resolution || meta.dimensions || '').trim();
    const size = String(meta.size || meta.file_size || '').trim();
    const duration = String(meta.duration || '').trim();
    const createdAt = String(asset.created_at || meta.created_at || '').trim();
    const createdLabel = createdAt ? new Date(createdAt).toLocaleString() : '';
    const typeLabel = assetType === 'video'
        ? t('视频', 'Video')
        : assetType === 'audio'
            ? t('音频', 'Audio')
            : t('图片', 'Image');

    // Find Entity Info
    let entityInfo = null;
    if (meta.entity_id) {
        const matchingEntity = entities.find(e => String(e.id) === String(meta.entity_id));
        if (matchingEntity) {
            entityInfo = `${matchingEntity.name} (${t(matchingEntity.type === 'character' ? '角色' : matchingEntity.type === 'prop' ? '道具' : '环境', matchingEntity.type)})`;
        } else {
            entityInfo = `ID: ${meta.entity_id}`;
        }
    }

    const rows = [
        ...(entityInfo ? [{ label: t('实体', 'Entity'), value: entityInfo }] : []),
        { label: t('文件', 'File'), value: fileName },
        { label: t('类型', 'Type'), value: typeLabel },
        ...(resolution ? [{ label: t('分辨率', 'Resolution'), value: resolution }] : []),
        ...(size ? [{ label: t('大小', 'Size'), value: size }] : []),
        ...(assetType === 'video' && duration ? [{ label: t('时长', 'Duration'), value: String(duration).endsWith('.0') ? `${parseInt(duration, 10)}s` : `${duration}s` }] : []),
        ...(createdLabel ? [{ label: t('创建时间', 'Created'), value: createdLabel }] : []),
    ];

    const popoverPositionClass = position === 'bottom' 
        ? "top-full mt-2 origin-top -translate-y-2 group-hover:translate-y-0" 
        : "bottom-full mb-2 origin-bottom translate-y-2 group-hover:translate-y-0";

    return (
        <div className={`pointer-events-none absolute left-0 opacity-0 group-hover:opacity-100 transition-all duration-150 z-[60] ${popoverPositionClass}`}>
            <div className="rounded-lg border border-white/10 bg-black/95 backdrop-blur-md shadow-2xl p-3 w-56 max-w-[280px]">
                <div className="text-[11px] font-bold uppercase tracking-wide text-primary/90 mb-2.5">
                    {t('资产信息', 'Asset Info')}
                </div>
                <div className="space-y-2">
                    {rows.map((row) => (
                        <div key={`${row.label}:${row.value}`} className="grid grid-cols-[56px_1fr] gap-2 text-[11px] leading-snug">
                            <div className="text-white/50 uppercase truncate">{row.label}</div>
                            <div className="text-white/95 break-words line-clamp-3">{row.value}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export const MediaPickerModal = ({ isOpen, onClose, onSelect, projectId, context = {}, entities = [], episodeId = null, uiLang = 'zh' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [tab, setTab] = useState('assets');
    const [allCleanData, setAllCleanData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); // Detail/Preview Mode
    const [showHistoricalProjectAssets, setShowHistoricalProjectAssets] = useState(false);

    const [episodeFilter, setEpisodeFilter] = useState(episodeId ? 'current' : 'all');
    const [assetTypeFilter, setAssetTypeFilter] = useState('image');
    const [assetNameFilter, setAssetNameFilter] = useState('');
    const [availableShots, setAvailableShots] = useState([]);

    const inferPreferredAssetType = useCallback(() => {
        const stableType = String(context?.type || '').trim().toLowerCase();
        if (stableType.includes('video')) return 'video';
        if (stableType.includes('image')) return 'image';
        if (context?.shotFrameType) return 'image';
        return 'image';
    }, [context]);

    const resolveAssetEpisodeId = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        const raw = meta?.episode_id ?? asset?.episode_id;
        const stable = String(raw ?? '').trim();
        return stable || '';
    }, []);

    const resolveAssetEpisodeLabel = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        const title = String(meta?.episode_title || '').trim();
        if (title) return title;
        const id = resolveAssetEpisodeId(asset);
        if (!id) return t('未标记分集', 'Unassigned Episode');
        return `${t('分集', 'Episode')} ${id}`;
    }, [resolveAssetEpisodeId, t]);

    useEffect(() => {
        if (isOpen) {
             setSelectedAsset(null); // Reset detail view on open
             setShowHistoricalProjectAssets(false);
             setEpisodeFilter(episodeId ? 'current' : 'all');
             setAssetTypeFilter(inferPreferredAssetType());
             setAssetNameFilter('');
        }
    }, [episodeId, inferPreferredAssetType, isOpen]);

        useEffect(() => {
                 if (episodeId && availableShots.length === 0) {
                             fetchEpisodeShots(episodeId, { compact: true }).then(data => {
                                 setAvailableShots(data.sort((a,b) => {
                                                return String(a.shot_id || '').localeCompare(String(b.shot_id || ''), undefined, { numeric: true });
                                 }));
                         }).catch(console.error);
                 }
        }, [episodeId, availableShots.length]);

    useEffect(() => {
        if (isOpen && tab === 'assets') {
            loadAssets();
        } else if (!isOpen) {
            setAllCleanData(null);
            setSelectedAsset(null);
            setAssetNameFilter('');
        }
    }, [isOpen, tab, showHistoricalProjectAssets, projectId, episodeId]);

    const episodeOptions = useMemo(() => {
        const grouped = new Map();
        (Array.isArray(allCleanData) ? allCleanData : []).forEach((asset) => {
            const epId = resolveAssetEpisodeId(asset);
            if (!epId) return;
            if (!grouped.has(epId)) {
                grouped.set(epId, resolveAssetEpisodeLabel(asset));
            }
        });
        return Array.from(grouped.entries())
            .map(([id, label]) => ({ id, label }))
            .sort((a, b) => String(a.id).localeCompare(String(b.id), undefined, { numeric: true }));
    }, [allCleanData, resolveAssetEpisodeId, resolveAssetEpisodeLabel]);

    const filteredAssets = useMemo(() => {
        const rows = Array.isArray(allCleanData) ? [...allCleanData] : [];
        let filtered = rows;

        const currentEpisodeStable = String(episodeId || '').trim();
        if (episodeFilter === 'current' && currentEpisodeStable) {
            filtered = filtered.filter((asset) => resolveAssetEpisodeId(asset) === currentEpisodeStable);
        } else if (episodeFilter !== 'all') {
            filtered = filtered.filter((asset) => resolveAssetEpisodeId(asset) === episodeFilter);
        }

        if (assetTypeFilter !== 'all') {
            filtered = filtered.filter((asset) => String(asset?.type || '').trim().toLowerCase() === assetTypeFilter);
        }

        filtered.sort((left, right) => {
            const l = new Date(left?.created_at || 0).getTime();
            const r = new Date(right?.created_at || 0).getTime();
            return r - l;
        });
        return filtered;
    }, [allCleanData, assetTypeFilter, episodeFilter, episodeId, resolveAssetEpisodeId]);

    useEffect(() => {
        if (!isOpen || tab !== 'assets') return;
        if (!filteredAssets.length) {
            setSelectedAsset(null);
            if (assetNameFilter) setAssetNameFilter('');
            return;
        }
        const matched = filteredAssets.find((item) => String(item.id) === String(assetNameFilter));
        if (matched) {
            if (String(selectedAsset?.id || '') !== String(matched.id)) setSelectedAsset(matched);
            return;
        }
        const first = filteredAssets[0];
        setAssetNameFilter(String(first.id));
        setSelectedAsset(first);
    }, [assetNameFilter, filteredAssets, isOpen, selectedAsset?.id, tab]);

    const loadAssets = async () => {
        setLoading(true);
        try {
            const params = {};
            if (projectId) {
                params.project_id = projectId;
                params.current_project_asset = showHistoricalProjectAssets ? 'all' : '1';
            }
            if (episodeId) {
                params.episode_id = episodeId;
            }

            const shouldFilterReferencedOnly = Boolean(projectId) && !showHistoricalProjectAssets;
            const [data, refsPayload] = await Promise.all([
                fetchAssets(params),
                shouldFilterReferencedOnly ? fetchUnreferencedAssetIds({ project_id: projectId, episode_id: episodeId || undefined }) : Promise.resolve(null)
            ]);

            const referencedSet = new Set((refsPayload?.referenced_ids || []).map(id => String(id)));
            const hasReferencedHints = referencedSet.size > 0;

            // Step 1: By default only keep active/current generated assets. History mode keeps all rows.
            const cleanData = ((data || [])).filter(a => {
                if (!shouldFilterReferencedOnly) return true;
                const meta = a.meta_info || {};
                const isGenerated = meta.provider || meta.prompt || meta.source === 'ai_generation';
                // If backend has no referenced hints yet, keep generated rows to avoid empty picker.
                if (isGenerated && hasReferencedHints) {
                    return referencedSet.has(String(a.id));
                }
                return true;
            });

            setAllCleanData(cleanData); // Save clean version to memory
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleMarkAssetCurrent = useCallback(async (asset) => {
        const assetId = Number(asset?.id || 0);
        if (!projectId || assetId <= 0) return null;
        const updated = await markAssetAsCurrentProjectAsset(assetId);
        await loadAssets();
        setSelectedAsset((prev) => (Number(prev?.id || 0) === assetId ? { ...(prev || {}), ...(updated || {}) } : prev));
        return updated;
    }, [loadAssets, projectId]);

    const handleSelectAsset = useCallback(async (asset, selectedItems = null) => {
        const assetId = Number(asset?.id || 0);
        if (projectId && assetId > 0) {
            try {
                await handleMarkAssetCurrent(asset);
            } catch (e) {
                console.error('Failed to mark current project asset', e);
            }
        }
        onSelect(asset?.url, asset?.type, selectedItems || undefined);
    }, [handleMarkAssetCurrent, onSelect, projectId]);

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true);
        try {
            // Attach context to upload
            const meta = {};
            if (projectId) meta.project_id = projectId;
            if (episodeId) meta.episode_id = episodeId;
            if (context.entityId) meta.entity_id = context.entityId;
            if (context.shotId) meta.shot_id = context.shotId;

            const asset = await uploadAsset(file, meta); 
            if (asset && asset.url) {
                onSelect(asset.url, asset.type || (file.type.startsWith('video') ? 'video' : 'image'));
            }
            if (tab === 'assets') loadAssets();
        } catch (e) {
            console.error("Upload failed", e);
            alert("Upload failed: " + e.message);
        } finally {
            setUploading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[110] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
             <div className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-2xl h-[600px] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/20">
                    <h3 className="font-bold text-md">{t('选择媒体', 'Select Media')}</h3>
                    <button onClick={onClose} className="text-white/50 hover:text-white"><X size={20} /></button>
                </div>

                <div className="flex border-b border-white/10">
                    {['assets', 'upload', 'url'].map(tabKey => (
                        <button
                            key={tabKey}
                            onClick={() => setTab(tabKey)}
                            className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${tab === tabKey ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'}`}
                        >
                            {tabKey === 'assets' ? t('素材', 'Assets') : tabKey === 'upload' ? t('上传', 'Upload') : 'URL'}
                        </button>
                    ))}
                </div>

                {/* Filters Bar */}
                {tab === 'assets' && (
                    <div className="flex items-center gap-2 p-3 bg-black/10 border-b border-white/5 flex-wrap">
                        <select 
                            value={episodeFilter}
                            onChange={(e) => {
                                setEpisodeFilter(e.target.value);
                                setAssetNameFilter('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            {episodeId && <option value="current">{t('本分集', 'Current Episode')}</option>}
                            <option value="all">{t('全部分集', 'All Episodes')}</option>
                            {episodeOptions.map((option) => (
                                <option key={option.id} value={option.id}>{option.label}</option>
                            ))}
                        </select>

                        <select 
                            value={assetTypeFilter}
                            onChange={(e) => {
                                setAssetTypeFilter(e.target.value);
                                setAssetNameFilter('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="all">{t('全部类型', 'All Types')}</option>
                            <option value="image">{t('仅图片', 'Images Only')}</option>
                            <option value="video">{t('仅视频', 'Videos Only')}</option>
                        </select>

                        <select
                            value={assetNameFilter}
                            onChange={(e) => {
                                const nextId = e.target.value;
                                setAssetNameFilter(nextId);
                                const picked = filteredAssets.find((item) => String(item.id) === String(nextId));
                                if (picked) setSelectedAsset(picked);
                            }}
                            className="min-w-[260px] flex-1 bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                            disabled={filteredAssets.length === 0}
                        >
                            {filteredAssets.length === 0 ? (
                                <option value="">{t('无可选资产', 'No assets available')}</option>
                            ) : (
                                filteredAssets.map((asset) => {
                                    const stableName = String(asset?.name || '').trim() || String(asset?.url || '').split('/').pop() || `${t('素材', 'Asset')} #${asset.id}`;
                                    return (
                                        <option key={asset.id} value={String(asset.id)}>
                                            {stableName}
                                        </option>
                                    );
                                })
                            )}
                        </select>

                        {projectId && (
                            <button
                                type="button"
                                onClick={() => setShowHistoricalProjectAssets((prev) => !prev)}
                                className={`text-xs px-2.5 py-1 rounded border transition-colors ${showHistoricalProjectAssets ? 'border-amber-400/40 bg-amber-500/10 text-amber-100' : 'border-white/10 bg-[#151515] text-white/75 hover:bg-white/5'}`}
                            >
                                {showHistoricalProjectAssets ? t('显示历史分集', 'Showing History Episodes') : t('仅当前项目资产', 'Current Project Assets Only')}
                            </button>
                        )}
                        
                        <div className="ml-auto text-[10px] text-muted-foreground">
                            {filteredAssets.length} {t('条结果', 'results')}
                        </div>
                    </div>
                )}

                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#151515]">
                    {tab === 'assets' && (
                        loading ? <div className="flex items-center justify-center h-full"><RefreshCw className="animate-spin text-muted-foreground"/></div> :
                        <div className="h-full">
                            {filteredAssets.length === 0 || !selectedAsset ? (
                                <div className="h-full flex items-center justify-center text-center text-muted-foreground">
                                    <div>
                                        <p>{t('未找到素材', 'No assets found')}</p>
                                        <p className="text-xs mt-2 text-white/40">{t('请调整分集/类型筛选后再试。', 'Please adjust episode/type filters and try again.')}</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="h-full flex flex-col gap-4">
                                    <div className="rounded-lg border border-white/10 bg-black/30 p-3 min-h-[260px] flex items-center justify-center">
                                        {selectedAsset.type === 'video' ? (
                                            <InViewVideo
                                                src={selectedAsset.url}
                                                controls
                                                className="max-h-[320px] max-w-full rounded"
                                                visibleDelayMs={280}
                                                fallback={<Video className="w-8 h-8 opacity-30" />}
                                            />
                                        ) : (
                                            <SafeImage src={selectedAsset.url} className="max-h-[320px] max-w-full object-contain rounded" alt="asset-preview" />
                                        )}
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-white/80">
                                        <div className="rounded border border-white/10 bg-black/20 p-3">
                                            <div className="text-[10px] uppercase text-white/50 mb-1">{t('名称', 'Name')}</div>
                                            <div>{selectedAsset.name || t('未命名', 'Untitled')}</div>
                                        </div>
                                        <div className="rounded border border-white/10 bg-black/20 p-3">
                                            <div className="text-[10px] uppercase text-white/50 mb-1">{t('分集', 'Episode')}</div>
                                            <div>{resolveAssetEpisodeLabel(selectedAsset)}</div>
                                        </div>
                                        <div className="rounded border border-white/10 bg-black/20 p-3">
                                            <div className="text-[10px] uppercase text-white/50 mb-1">{t('类型', 'Type')}</div>
                                            <div>{selectedAsset.type === 'video' ? t('视频', 'Video') : t('图片', 'Image')}</div>
                                        </div>
                                        <div className="rounded border border-white/10 bg-black/20 p-3">
                                            <div className="text-[10px] uppercase text-white/50 mb-1">{t('创建时间', 'Created')}</div>
                                            <div>{selectedAsset?.created_at ? new Date(selectedAsset.created_at).toLocaleString() : '-'}</div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {tab === 'upload' && (
                        <div className="flex flex-col items-center justify-center h-full space-y-4">
                            <div className="p-8 border-2 border-dashed border-white/10 rounded-xl bg-black/20 hover:border-primary/50 hover:bg-primary/5 transition-all w-full max-w-sm flex flex-col items-center justify-center cursor-pointer relative">
                                <input 
                                    type="file" 
                                    accept="image/*,video/*" 
                                    onChange={handleUpload}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                    disabled={uploading} 
                                />
                                {uploading ? <RefreshCw className="animate-spin text-primary mb-2" size={32} /> : <Upload className="text-muted-foreground mb-2" size={32} />}
                                <span className="text-sm font-medium text-muted-foreground">
                                    {uploading ? t('上传中...', 'Uploading...') : t('点击或拖拽文件到此处', 'Click or drop file here')}
                                </span>
                            </div>
                        </div>
                    )}

                    {tab === 'url' && (
                         <div className="flex flex-col items-center justify-center h-full">
                            <div className="w-full max-w-sm space-y-4">
                                <div>
                                    <label className="text-xs font-bold uppercase text-muted-foreground mb-1 block">{t('图片 / 视频 URL', 'Image / Video URL')}</label>
                                    <input 
                                        type="text" 
                                        id="media-url-input"
                                        placeholder="https://..." 
                                        className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:border-primary/50 outline-none"
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') onSelect(e.target.value, 'image'); // Default to image on enter, user can correct contexts usually know
                                        }}
                                    />
                                </div>
                                <button 
                                    onClick={() => {
                                        const val = document.getElementById('media-url-input').value;
                                        if (val) onSelect(val, 'image');
                                    }}
                                    className="w-full py-2 bg-primary text-black font-bold rounded hover:opacity-90"
                                >
                                    Confirm
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {tab === 'assets' && (
                    <div className="flex border-t border-white/10 p-3 bg-black/40 justify-between items-center shrink-0">
                        <div className="text-sm font-medium text-white/80">
                            {selectedAsset ? (selectedAsset.name || t('已选中目标资产', 'Selected Target Asset')) : t('未选择资产', 'No asset selected')}
                        </div>
                        <button
                            disabled={!selectedAsset}
                            onClick={async () => {
                                if (!selectedAsset) return;
                                await handleSelectAsset(selectedAsset);
                            }}
                            className="bg-primary text-black text-sm font-bold px-6 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {t('选择目标资产', 'Select Target Asset')}
                        </button>
                    </div>
                )}
             </div>
        </div>
    );
};

