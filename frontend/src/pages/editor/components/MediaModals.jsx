
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

import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint } from '../editorConstants';
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

export const AssetHoverMetaOverlay = ({ asset, t }) => {
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

    const rows = [
        { label: t('文件', 'File'), value: fileName },
        { label: t('类型', 'Type'), value: typeLabel },
        ...(resolution ? [{ label: t('分辨率', 'Resolution'), value: resolution }] : []),
        ...(size ? [{ label: t('大小', 'Size'), value: size }] : []),
        ...(assetType === 'video' && duration ? [{ label: t('时长', 'Duration'), value: String(duration).endsWith('.0') ? `${parseInt(duration, 10)}s` : `${duration}s` }] : []),
        ...(createdLabel ? [{ label: t('创建时间', 'Created'), value: createdLabel }] : []),
    ].slice(0, 5);

    return (
        <div className="pointer-events-none absolute left-2 right-2 top-2 opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-150 z-10">
            <div className="rounded-lg border border-white/10 bg-black/88 backdrop-blur-sm shadow-2xl p-2.5">
                <div className="text-[10px] font-bold uppercase tracking-wide text-primary/80 mb-2">
                    {t('核心信息', 'Quick Info')}
                </div>
                <div className="space-y-1.5">
                    {rows.map((row) => (
                        <div key={`${row.label}:${row.value}`} className="grid grid-cols-[52px_1fr] gap-2 text-[10px] leading-4">
                            <div className="text-white/45 uppercase truncate">{row.label}</div>
                            <div className="text-white/90 break-all line-clamp-2">{row.value}</div>
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
    const [assets, setAssets] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); // Detail/Preview Mode
    
    // Filters
    const [filterScope, setFilterScope] = useState('project'); // 'project', 'subject', 'shot', 'type'
    const [filterType, setFilterType] = useState('all'); // 'all', 'image', 'video'
    const [filterValue, setFilterValue] = useState(''); // entity_id or shot_id or entity_type
    
    const [availableShots, setAvailableShots] = useState([]);
    const assetsViewportRef = useRef(null);
    const [assetsViewportHeight, setAssetsViewportHeight] = useState(0);
    const [assetsViewportWidth, setAssetsViewportWidth] = useState(0);
    const [assetsScrollTop, setAssetsScrollTop] = useState(0);

    const ASSET_GRID_COLUMNS = 4;
    const ASSET_GRID_GAP = 12;
    const assetCardWidth = useMemo(() => {
        if (!assetsViewportWidth) return 160;
        const usableWidth = Math.max(0, assetsViewportWidth - ASSET_GRID_GAP * (ASSET_GRID_COLUMNS - 1));
        return Math.max(96, Math.floor(usableWidth / ASSET_GRID_COLUMNS));
    }, [assetsViewportWidth]);
    const assetRowHeight = useMemo(() => Math.max(108, assetCardWidth + ASSET_GRID_GAP), [assetCardWidth]);
    const assetTotalRows = useMemo(() => Math.ceil((assets?.length || 0) / ASSET_GRID_COLUMNS), [assets?.length]);
    const assetVisibleRows = useMemo(() => {
        if (!assetsViewportHeight) return 8;
        return Math.max(1, Math.ceil(assetsViewportHeight / assetRowHeight));
    }, [assetsViewportHeight, assetRowHeight]);
    const assetOverscanRows = 3;
    const assetStartRow = useMemo(() => {
        if (!assets?.length) return 0;
        return Math.max(0, Math.floor(assetsScrollTop / assetRowHeight) - assetOverscanRows);
    }, [assets?.length, assetsScrollTop, assetRowHeight]);
    const assetEndRow = useMemo(() => {
        if (!assetTotalRows) return 0;
        return Math.min(assetTotalRows, assetStartRow + assetVisibleRows + assetOverscanRows * 2);
    }, [assetTotalRows, assetStartRow, assetVisibleRows]);
    const assetStartIndex = useMemo(() => assetStartRow * ASSET_GRID_COLUMNS, [assetStartRow]);
    const assetEndIndex = useMemo(() => {
        if (!assets?.length) return 0;
        return Math.min(assets.length, assetEndRow * ASSET_GRID_COLUMNS);
    }, [assets?.length, assetEndRow]);
    const visibleAssets = useMemo(() => {
        if (!assets?.length) return [];
        return assets.slice(assetStartIndex, assetEndIndex);
    }, [assets, assetStartIndex, assetEndIndex]);
    const assetTopSpacerHeight = useMemo(() => assetStartRow * assetRowHeight, [assetStartRow, assetRowHeight]);
    const assetBottomSpacerHeight = useMemo(() => {
        const remainingRows = Math.max(0, assetTotalRows - assetEndRow);
        return remainingRows * assetRowHeight;
    }, [assetTotalRows, assetEndRow, assetRowHeight]);

    useEffect(() => {
        if (isOpen) {
             setSelectedAsset(null); // Reset detail view on open
        }
        if (isOpen && tab === 'assets') {
             // Reset filters if context is provided?
             // If context has entityId, maybe default to subject?
             if (context.entityId && filterScope === 'project') {
                 setFilterScope('subject');
                 setFilterValue(context.entityId);
             } else if (context.shotId && filterScope === 'project') {
                 // setFilterScope('shot'); // Optional: heuristic
                 // setFilterValue(context.shotId);
             }
        }
    }, [isOpen]);

    useEffect(() => {
         // Load shots if needed
         if (filterScope === 'shot' && episodeId && availableShots.length === 0) {
               fetchEpisodeShots(episodeId, { compact: true }).then(data => {
                 setAvailableShots(data.sort((a,b) => {
                      // simple sort by shot_id alphanumeric
                      return a.shot_id.localeCompare(b.shot_id, undefined, { numeric: true });
                 }));
             }).catch(console.error);
         }
    }, [filterScope, episodeId]);

    useEffect(() => {
        if (isOpen && tab === 'assets') {
            loadAssets();
        }
    }, [isOpen, tab, filterScope, filterType, filterValue]);

    useEffect(() => {
        if (!isOpen || tab !== 'assets') return;
        const viewport = assetsViewportRef.current;
        if (!viewport) return;

        const updateSize = () => {
            setAssetsViewportHeight(viewport.clientHeight || 0);
            setAssetsViewportWidth(viewport.clientWidth || 0);
        };

        updateSize();
        let observer;
        if (typeof ResizeObserver !== 'undefined') {
            observer = new ResizeObserver(updateSize);
            observer.observe(viewport);
        } else {
            window.addEventListener('resize', updateSize);
        }

        return () => {
            if (observer) observer.disconnect();
            else window.removeEventListener('resize', updateSize);
        };
    }, [isOpen, tab]);

    useEffect(() => {
        setAssetsScrollTop(0);
        const viewport = assetsViewportRef.current;
        if (viewport) viewport.scrollTop = 0;
    }, [filterScope, filterType, filterValue, tab, isOpen]);

    const loadAssets = () => {
        setLoading(true);
        const params = {};
        if (filterType !== 'all') params.type = filterType;
        
        // Base scope is Project
        if (projectId) params.project_id = projectId;
        
        // Refine scope
        let clientSideFilterIds = null; // If set, filter by these entity IDs locally

        if (filterScope === 'subject' && filterValue) {
            params.entity_id = filterValue;
        } else if (filterScope === 'shot' && filterValue) {
            params.shot_id = filterValue;
        } else if (filterScope === 'type' && filterValue) {
            // "By Type" strategy: Fetch project assets, then filter by entity_id belonging to that type
            // Find all entities of this type
            const targetEntities = entities.filter(e => (e.type || 'prop').toLowerCase() === filterValue.toLowerCase());
            clientSideFilterIds = new Set(targetEntities.map(e => e.id));
        }
        
        fetchAssets(params).then(data => {
            let res = data || [];
            
            // Client-side filtering for Entity Type logic (if backend doesn't support recursive type filtering)
            if (clientSideFilterIds) {
                res = res.filter(a => {
                    const eid = a.meta_info?.entity_id;
                    return eid && clientSideFilterIds.has(Number(eid));
                });
            }

            setAssets(res);
        }).catch(console.error).finally(() => setLoading(false));
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true);
        try {
            // Attach context to upload
            const meta = {};
            if (projectId) meta.project_id = projectId;
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
                            value={filterScope}
                            onChange={(e) => {
                                setFilterScope(e.target.value);
                                setFilterValue('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="project">{t('项目全部素材', 'All Project Assets')}</option>
                            <option value="type">{t('按主体类型', 'By Subject Type')}</option>
                            <option value="subject">{t('按指定主体', 'By Exact Subject')}</option>
                            <option value="shot">{t('按分镜（Shot）', 'By Storyboard (Shot)')}</option>
                        </select>

                        {/* Refinement Selector */}
                        {filterScope === 'type' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">{t('选择类型...', 'Select Type...')}</option>
                                <option value="character">{t('角色', 'Characters')}</option>
                                <option value="prop">{t('道具', 'Props')}</option>
                                <option value="environment">{t('环境', 'Environments')}</option>
                                <option value="poster">{t('海报', 'Poster')}</option>
                                <option value="poster">{t('海报', 'Poster')}</option>
                            </select>
                        )}

                        {filterScope === 'subject' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">{t('选择主体...', 'Select Subject...')}</option>
                                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                            </select>
                        )}

                        {filterScope === 'shot' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">{t('选择镜头...', 'Select Shot...')}</option>
                                {availableShots.map(s => <option key={s.id} value={s.id}>{s.shot_id} - {s.shot_name || t('未命名', 'Untitled')}</option>)}
                            </select>
                        )}

                        <select 
                            value={filterType}
                            onChange={(e) => setFilterType(e.target.value)}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="all">{t('全部类型', 'All Types')}</option>
                            <option value="image">{t('仅图片', 'Images Only')}</option>
                            <option value="video">{t('仅视频', 'Videos Only')}</option>
                        </select>
                        
                        <div className="ml-auto text-[10px] text-muted-foreground">
                            {assets.length} {t('条结果', 'results')}
                        </div>
                    </div>
                )}

                <div
                    ref={assetsViewportRef}
                    onScroll={(e) => setAssetsScrollTop(e.currentTarget.scrollTop || 0)}
                    className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#151515]"
                >
                    {tab === 'assets' && (
                        loading ? <div className="flex items-center justify-center h-full"><RefreshCw className="animate-spin text-muted-foreground"/></div> :
                        <>
                            {assetTopSpacerHeight > 0 && <div style={{ height: `${assetTopSpacerHeight}px` }} />}
                            <div className="grid grid-cols-4 gap-3">
                            {visibleAssets.map(asset => (
                                <div 
                                    key={asset.id} 
                                    onClick={() => setSelectedAsset(asset)}
                                    className="aspect-square bg-black/40 rounded overflow-hidden border border-white/5 hover:border-primary/50 cursor-pointer group relative"
                                >
                                    <AssetHoverMetaOverlay asset={asset} t={t} />
                                    {asset.type === 'video' ? (
                                        <div className="w-full h-full flex items-center justify-center bg-black">
                                            <Video className="text-white/50 group-hover:text-primary transition-colors"/>
                                        </div>
                                    ) : (
                                        <SafeImage src={asset.url} alt="asset" className="w-full h-full object-cover" />
                                    )}
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                    <div className="absolute bottom-0 inset-x-0 p-1 bg-black/60 text-[9px] truncate text-white/70">
                                        {asset.name}
                                    </div>
                                    {/* Quick Select Button on Hover */}
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); onSelect(asset.url, asset.type); }}
                                        className="absolute top-1 right-1 bg-primary text-black p-1 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:scale-110 shadow-lg"
                                        title={t('快速选择', 'Quick Select')}
                                    >
                                        <Check size={12} strokeWidth={3} />
                                    </button>
                                </div>
                            ))}
                            </div>
                            {assetBottomSpacerHeight > 0 && <div style={{ height: `${assetBottomSpacerHeight}px` }} />}
                            {assets.length === 0 && <div className="text-center text-muted-foreground py-8">{t('未找到素材', 'No assets found')}</div>}
                        </>
                    )}
                    
                    {/* Asset Detail Overlay */}
                    {selectedAsset && (
                        <div className="absolute inset-0 bg-[#1e1e1e] z-20 flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-200">
                             <div className="flex justify-between items-center p-3 border-b border-white/10 bg-black/20">
                                <h4 className="font-bold text-sm flex items-center gap-2">
                                    <button onClick={() => setSelectedAsset(null)} className="hover:bg-white/10 p-1 rounded"><ArrowLeft size={16}/></button>
                                    {t('素材详情', 'Asset Details')}
                                </h4>
                                <div className="flex gap-2">
                                     <button 
                                        onClick={() => { onSelect(selectedAsset.url, selectedAsset.type); }}
                                        className="bg-primary text-black text-xs font-bold px-3 py-1.5 rounded hover:opacity-90 flex items-center gap-1"
                                     >
                                        <Check size={14}/> {t('选择该素材', 'Select This Asset')}
                                     </button>
                                </div>
                            </div>
                            <div className="flex-1 overflow-hidden flex">
                                <div className="flex-1 bg-black/40 flex items-center justify-center p-4">
                                     {selectedAsset.type === 'video' ? (
                                                     <InViewVideo
                                                          src={selectedAsset.url}
                                                          controls
                                                          className="max-w-full max-h-full rounded shadow-lg"
                                                           visibleDelayMs={420}
                                                          fallback={<Video className="w-8 h-8 opacity-30" />}
                                                     />
                                     ) : (
                                                     <SafeImage src={selectedAsset.url} className="max-w-full max-h-full object-contain rounded shadow-lg" alt="asset-detail" />
                                     )}
                                </div>
                                <div className="w-80 bg-[#151515] border-l border-white/10 p-4 overflow-y-auto space-y-4">
                                    <div>
                                        <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('名称', 'Name')}</label>
                                        <div className="text-sm font-medium">{selectedAsset.name || t('未命名', 'Untitled')}</div>
                                    </div>
                                    
                                    {selectedAsset.meta_info?.entity_id && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('关联主体', 'Linked Entity')}</label>
                                            <div className="text-xs bg-white/5 p-2 rounded border border-white/5 mt-1">
                                                {entities.find(e => e.id === Number(selectedAsset.meta_info.entity_id))?.name || `Entity #${selectedAsset.meta_info.entity_id}`}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {selectedAsset.meta_info?.shot_id && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('来源镜头', 'Source Shot')}</label>
                                            <div className="text-xs bg-white/5 p-2 rounded border border-white/5 mt-1">
                                                {availableShots.find(s => s.id === Number(selectedAsset.meta_info.shot_id))?.shot_id || `Shot #${selectedAsset.meta_info.shot_id}`}
                                            </div>
                                        </div>
                                    )}

                                    {selectedAsset.meta_info?.prompt && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('提示词', 'Prompt')}</label>
                                            <div className="text-xs text-gray-400 bg-white/5 p-2 rounded border border-white/5 mt-1 max-h-[150px] overflow-y-auto custom-scrollbar">
                                                {selectedAsset.meta_info.prompt}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {/* Detailed Technical Metadata */}
                                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/5">
                                         {selectedAsset.meta_info?.resolution && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('分辨率', 'Resolution')}</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.resolution}</div>
                                            </div>
                                         )}
                                         {selectedAsset.meta_info?.size && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('大小', 'Size')}</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.size}</div>
                                            </div>
                                         )}
                                          {selectedAsset.meta_info?.format && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('格式', 'Format')}</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.format}</div>
                                            </div>
                                         )}
                                          {selectedAsset.meta_info?.duration && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">{t('时长', 'Duration')}</label>
                                                <div className="text-xs text-gray-300">{/* Normalize 5.0 to 5s */}
                                                {String(selectedAsset.meta_info.duration).endsWith('.0') ? parseInt(selectedAsset.meta_info.duration) : selectedAsset.meta_info.duration}s
                                                </div>
                                            </div>
                                         )}
                                    </div>

                                    <div className="text-[10px] text-muted-foreground pt-4 border-t border-white/5">
                                        {t('文件', 'File')}: {selectedAsset.url.split('/').pop()} <br/>
                                        {t('创建时间', 'Created')}: {new Date(selectedAsset.created_at).toLocaleString()}
                                    </div>
                                </div>
                            </div>
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
             </div>
        </div>
    );
};

