
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
    fetchUnreferencedAssetIds
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
    const [assets, setAssets] = useState([]);
    const [allCleanData, setAllCleanData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); // Detail/Preview Mode
    const [selectedMulti, setSelectedMulti] = useState(new Set()); // Multi-selection state
    
    // Filters
    const [filterScope, setFilterScope] = useState('characters'); // 'characters', 'props', 'environments', 'shots', 'all'
    const [filterType, setFilterType] = useState('all');
    const [filterValue, setFilterValue] = useState('');
    const [filterFrameType, setFilterFrameType] = useState('all');
    const [availableShots, setAvailableShots] = useState([]);
    const [assetsViewportHeight, setAssetsViewportHeight] = useState(0);
    const [assetsViewportWidth, setAssetsViewportWidth] = useState(0);
    const [assetsScrollTop, setAssetsScrollTop] = useState(0);
    const assetsViewportRef = useRef(null);

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
             
             // Setup initial filters based on context
             if (context && context.entityId) {
                 const t = entities.find(e => String(e.id) === String(context.entityId))?.type || 'character';
                 setFilterScope(t === 'character' ? 'characters' : t === 'prop' ? 'props' : t === 'environment' ? 'environments' : 'characters');
             } else {
                 setFilterScope('characters');
             }
        }
    }, [isOpen]);

    useEffect(() => {
         // Load shots if needed
         if (filterScope === 'shots' && episodeId && availableShots.length === 0) {
               fetchEpisodeShots(episodeId, { compact: true }).then(data => {
                 setAvailableShots(data.sort((a,b) => {
                      // simple sort by shot_id alphanumeric
                        return String(a.shot_id || '').localeCompare(String(b.shot_id || ''), undefined, { numeric: true });
                 }));
             }).catch(console.error);
         }
    }, [filterScope, episodeId]);

    useEffect(() => {
        if (isOpen && tab === 'assets') {
            if (!allCleanData) loadAssets();
        } else if (!isOpen) {
            setAllCleanData(null);
            setAssets([]);
        }
    }, [isOpen, tab]); // Removed filter scopes from here so it only fetches broadly

    useEffect(() => {
        if (!allCleanData) return;
        
        // Step 2: Apply Scope Filtering locally fast
        let res = allCleanData;

        const buildEntityAssets = (typeMatch) => {
            return entities
                .filter(e => e.type === typeMatch && e.image_url)
                .map(e => ({
                    id: 'entity_' + e.id,
                    url: e.image_url,
                    type: 'image',
                    meta_info: { entity_id: e.id, source: 'entity' }
                }));
        };

        const mergeAssets = (baseAssets, entityAssets) => {
            const urlSet = new Set(baseAssets.map(a => String(a.url).trim()));
            const uniqueEntities = entityAssets.filter(ea => !urlSet.has(String(ea.url).trim()));
            return [...uniqueEntities, ...baseAssets];
        };

        if (filterScope === 'characters') {
              res = buildEntityAssets('character');
          } else if (filterScope === 'props') {
              res = buildEntityAssets('prop');
          } else if (filterScope === 'environments') {
              res = buildEntityAssets('environment');
          } else if (filterScope === 'shots') {
                res = availableShots.flatMap(s => {
                    let startUrl = s.image_url ? String(s.image_url).trim() : '';
                    let endUrl = s.end_frame_url;
                    if (!endUrl && s.technical_notes) {
                        try {
                            const tech = typeof s.technical_notes === 'string' ? JSON.parse(s.technical_notes) : s.technical_notes;
                            endUrl = tech?.end_frame_url;
                        } catch (e) {}
                    }
                    endUrl = endUrl ? String(endUrl).trim() : '';
                    
                    return [
                        startUrl && { id: 'shot_start_' + s.id, url: startUrl, type: 'image', meta_info: { source: 'shot', shot_id: s.id } },
                        endUrl && { id: 'shot_end_' + s.id, url: endUrl, type: 'image', meta_info: { source: 'shot', shot_id: s.id } },
                        s.video_url && { id: 'shot_video_' + s.id, url: String(s.video_url).trim(), type: 'video', meta_info: { source: 'shot', shot_id: s.id } }
                    ];
                }).filter(Boolean);            }
        // Step 3: Global Media Type Filter
        if (filterType !== 'all') {
            res = res.filter(a => a.type === filterType);
        }

        console.log("[MediaModal Debug] filterScope:", filterScope, "availableShots:", availableShots.length, "res:", res.length);
        setAssets(res);
    }, [allCleanData, filterScope, filterType, filterValue, filterFrameType, entities, availableShots]);

    useEffect(() => {
        if (isOpen) {
            setSelectedMulti(new Set());
        }
    }, [isOpen]);

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
    }, [filterScope, filterType, filterValue, filterFrameType, tab, isOpen]);

    const loadAssets = async () => {
        setLoading(true);
        try {
            const params = {};
            if (projectId) params.project_id = projectId;
            
            const [data, refsPayload] = await Promise.all([
                fetchAssets(params),
                fetchUnreferencedAssetIds({ project_id: projectId }) // scope optimization
            ]);

            const referencedSet = new Set((refsPayload?.referenced_ids || []).map(id => String(id)));
            
            // Step 1: Clean list to EXCLUDE historical/unreferenced generated assets
            const cleanData = ((data || []) ).filter(a => {
                const meta = a.meta_info || {};
                const isGenerated = meta.provider || meta.prompt || meta.source === 'ai_generation';
                if (isGenerated) {
                    return referencedSet.has(String(a.id)); // Must be active
                }
                return true; // Keep manual standalone uploads 
            });

            setAllCleanData(cleanData); // Save clean version to memory
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
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
                            <option value="characters">{t('项目角色', 'Project Characters')}</option>
                            <option value="props">{t('项目道具', 'Project Props')}</option>
                            <option value="environments">{t('项目环境', 'Project Environments')}</option>
                            <option value="shots">{t('项目分镜', 'Project Shots')}</option>
                            <option value="all">{t('所有素材', 'All Assets')}</option>
                        </select>



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
                            {visibleAssets.map((asset, index) => {
                                const globalIndex = assetStartIndex + index;
                                const isFirstRow = globalIndex < 4;
                                return (
                                <div
                                    key={asset.id}
                                    className="relative group"
                                >
                                    <div
                                        onClick={() => {
                                            const nextSet = new Set(selectedMulti);
                                            if (nextSet.has(asset.id)) nextSet.delete(asset.id);
                                            else nextSet.add(asset.id);
                                            setSelectedMulti(nextSet);
                                        }}
                                        className={`aspect-square bg-black/40 rounded overflow-hidden border cursor-pointer relative transition-all ${selectedMulti.has(asset.id) ? 'border-primary shadow-[0_0_0_2px_rgba(var(--color-primary),0.5)]' : 'border-white/5 hover:border-primary/50'}`}
                                    >
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
                                        {/* Floating Button for Detail/Preview */}
                                        <button
                                            onClick={(e) => { e.stopPropagation(); setSelectedAsset(asset); }}
                                            className="absolute top-1 right-1 bg-black/60 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:scale-110 shadow-lg z-10"
                                            title={t('预览详情', 'Preview Details')}
                                        >
                                            <Maximize2 size={12} strokeWidth={2} />
                                        </button>
                                        {/* Selected Indicator */}
                                        {selectedMulti.has(asset.id) && (
                                            <div className="absolute top-1 left-1 bg-primary text-black p-0.5 rounded-full shadow-lg z-10">
                                                <Check size={14} strokeWidth={3} />
                                            </div>
                                        )}
                                    </div>
                                    <AssetHoverMetaOverlay asset={asset} t={t} entities={entities} position={isFirstRow ? 'bottom' : 'top'} />
                                </div>
                                );
                            })}
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
                                                {selectedAsset.meta_info.frame_type || selectedAsset.meta_info.asset_type ? ` - ${selectedAsset.meta_info.frame_type || selectedAsset.meta_info.asset_type}` : ''}
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

                {tab === 'assets' && (
                    <div className="flex border-t border-white/10 p-3 bg-black/40 justify-between items-center shrink-0">
                        <div className="text-sm font-medium text-white/80">
                            {selectedMulti.size} {t('已选中', 'selected')}
                        </div>
                        <button
                            disabled={selectedMulti.size === 0}
                            onClick={() => {
                                const selectedItems = Array.from(selectedMulti).map(id => assets.find(a => a.id === id)).filter(Boolean);
                                if (selectedItems.length > 0) {
                                    onSelect(selectedItems[0].url, selectedItems[0].type, selectedItems);
                                }
                            }}
                            className="bg-primary text-black text-sm font-bold px-6 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {t('确认', 'Confirm')}
                        </button>
                    </div>
                )}
             </div>
        </div>
    );
};

