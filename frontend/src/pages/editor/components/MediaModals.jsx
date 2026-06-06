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
                            className="w-full h-full object-contain shadow-lg rounded"
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
        // 调试日志：弹窗打开时的 context
        useEffect(() => {
            if (isOpen && typeof window !== 'undefined') {
                console.log('[素材选择][弹窗context]', context);
            }
        }, [isOpen, context]);
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [tab, setTab] = useState('assets');
    const [allCleanData, setAllCleanData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); // Detail/Preview Mode
    const [showHistoricalProjectAssets, setShowHistoricalProjectAssets] = useState(true);

    const [episodeFilter, setEpisodeFilter] = useState('all');
    const [assetTypeFilter, setAssetTypeFilter] = useState('all');
    const [secondaryFilterKind, setSecondaryFilterKind] = useState('all'); // all | entity | shot
    const [secondaryFilterValue, setSecondaryFilterValue] = useState('');
    const [subCategoryFilter, setSubCategoryFilter] = useState('all'); // all | character | prop | environment | shot_start | shot_video
    const [secondaryAutoFollow, setSecondaryAutoFollow] = useState(false);
    const [nameFilter, setNameFilter] = useState('');
    const [selectedAssetId, setSelectedAssetId] = useState('');
    const [selectedMulti, setSelectedMulti] = useState(new Set());
    const [availableShots, setAvailableShots] = useState([]);
    const loadAssetsRequestSeqRef = useRef(0);

    const assetPickerDebugEnabled = useMemo(() => {
        if (!isOpen || typeof window === 'undefined') return false;
        const ctxFlag = context?.debugAssetPicker;
        if (typeof ctxFlag === 'boolean') return ctxFlag;
        if (typeof ctxFlag === 'string') {
            const normalized = ctxFlag.trim().toLowerCase();
            if (normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on') return true;
            if (normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off') return false;
        }
        try {
            const persisted = String(window.localStorage.getItem('AISTORY_ASSET_PICKER_DEBUG') || '').trim().toLowerCase();
            return persisted === '1' || persisted === 'true' || persisted === 'yes' || persisted === 'on';
        } catch (error) {
            return false;
        }
    }, [context?.debugAssetPicker, isOpen]);

    const isAssetVideoLike = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        const stableType = String(asset?.type || meta?.type || '').trim().toLowerCase();
        const frameType = String(meta?.frame_type || meta?.asset_type || '').trim().toLowerCase();
        const mimeType = String(meta?.mime_type || meta?.content_type || '').trim().toLowerCase();
        const url = String(asset?.url || '').trim().toLowerCase();
        if (stableType === 'video') return true;
        if (frameType.includes('video')) return true;
        if (mimeType.startsWith('video/')) return true;
        return /\.(mp4|mov|mkv|webm|avi|m4v)(\?.*)?$/i.test(url);
    }, []);

    const summarizeAssetsForDebug = useCallback((rows) => {
        const items = Array.isArray(rows) ? rows : [];
        const summary = {
            total: items.length,
            videoLike: 0,
            typeVideo: 0,
            frameVideo: 0,
            shotBound: 0,
            missingType: 0,
            sampleVideo: [],
        };
        items.forEach((asset) => {
            const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
            const stableType = String(asset?.type || '').trim().toLowerCase();
            const frameType = String(meta?.frame_type || meta?.asset_type || '').trim().toLowerCase();
            const shotId = String(meta?.shot_id ?? asset?.shot_id ?? '').trim();
            if (!stableType) summary.missingType += 1;
            if (stableType === 'video') summary.typeVideo += 1;
            if (frameType.includes('video')) summary.frameVideo += 1;
            if (shotId || frameType.includes('start') || frameType.includes('end') || frameType.includes('keyframe') || frameType.includes('video') || frameType.includes('shot')) {
                summary.shotBound += 1;
            }
            if (isAssetVideoLike(asset)) {
                summary.videoLike += 1;
                if (summary.sampleVideo.length < 6) {
                    summary.sampleVideo.push({
                        id: asset?.id,
                        type: stableType || '(empty)',
                        frameType: frameType || '(empty)',
                        shotId: shotId || '(empty)',
                        name: String(asset?.name || meta?.asset_name || meta?.filename || '').trim(),
                    });
                }
            }
        });
        return summary;
    }, [isAssetVideoLike]);

    const logAssetPickerDebug = useCallback((stage, payload) => {
        if (!assetPickerDebugEnabled || typeof window === 'undefined') return;
        const safeStage = String(stage || '').trim() || 'unknown';
        console.log(`[素材选择][debug][${safeStage}]`, payload || {});
    }, [assetPickerDebugEnabled]);

    const contextAllowMultiSelect = useMemo(() => {
        const raw = context?.allowMultiSelect;
        if (typeof raw === 'string') {
            return raw === '1' || raw.toLowerCase() === 'true';
        }
        return Boolean(raw);
    }, [context?.allowMultiSelect]);

    const contextDisableShotFilter = useMemo(() => {
        const raw = context?.disableShotFilter;
        if (typeof raw === 'string') {
            const normalized = raw.trim().toLowerCase();
            if (normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off') {
                return false;
            }
            if (normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on') {
                return true;
            }
        }
        if (typeof raw === 'boolean') return raw;

        // Fallback: entity-only entry (has entityId but no shotId) should not expose shot filter.
        const stableEntityId = String(context?.entityId ?? context?.entity_id ?? '').trim();
        const stableShotId = String(context?.shotId ?? context?.shot_id ?? '').trim();
        return Boolean(stableEntityId) && !stableShotId;
    }, [context?.disableShotFilter, context?.entityId, context?.entity_id, context?.shotId, context?.shot_id]);

    const contextDesiredAssetType = useMemo(() => {
        const raw = String(context?.desiredAssetType || context?.assetType || context?.type || '').trim().toLowerCase();
        if (raw.includes('video')) return 'video';
        if (raw.includes('image')) return 'image';
        return 'all';
    }, [context?.assetType, context?.desiredAssetType, context?.type]);

    const contextLockAssetType = useMemo(() => {
        const raw = context?.lockAssetType;
        if (typeof raw === 'string') {
            return raw === '1' || raw.toLowerCase() === 'true';
        }
        return Boolean(raw);
    }, [context?.lockAssetType]);

    const contextShotId = useMemo(() => String(context?.shotId ?? context?.shot_id ?? '').trim(), [context?.shotId, context?.shot_id]);
    const contextEntityId = useMemo(() => String(context?.entityId ?? context?.entity_id ?? '').trim(), [context?.entityId, context?.entity_id]);
    const contextFrameType = useMemo(() => String(context?.shotFrameType ?? context?.shot_frame_type ?? context?.frame_type ?? context?.type ?? '').trim().toLowerCase(), [context?.frame_type, context?.shotFrameType, context?.shot_frame_type, context?.type]);
    const secondaryKindChoices = useMemo(() => {
        if (contextDisableShotFilter) return ['all', 'entity'];
        return ['all', 'entity', 'shot'];
    }, [contextDisableShotFilter]);

    const inferPreferredAssetType = useCallback(() => {
        if (contextDesiredAssetType !== 'all') return contextDesiredAssetType;
        const stableType = String(context?.type || '').trim().toLowerCase();
        const stableFrameType = contextFrameType;
        if (stableFrameType.includes('video')) return 'video';
        if (stableType.includes('video')) return 'video';
        if (stableType.includes('image')) return 'image';
        if (stableFrameType) return 'image';
        return 'all';
    }, [context?.type, contextDesiredAssetType, contextFrameType]);

    const preferredAssetType = useMemo(() => inferPreferredAssetType(), [inferPreferredAssetType]);

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

    const resolveAssetDisplayName = useCallback((asset) => {
        const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
        const fallbackName = String(asset?.url || '').split('/').pop();
        return String(
            asset?.name
            || asset?.asset_name
            || meta?.asset_name
            || meta?.display_name
            || meta?.name
            || meta?.title
            || asset?.filename
            || meta?.original_filename
            || meta?.filename
            || fallbackName
            || `${t('素材', 'Asset')} #${asset?.id ?? '-'}`
        ).trim();
    }, [t]);

    const collectUrlTokens = useCallback((value) => {
        const raw = String(value || '').trim();
        if (!raw) return [];
        const tokens = new Set();
        const push = (part) => {
            const text = String(part || '').trim().toLowerCase();
            if (text) tokens.add(text);
        };
        push(raw);
        const normalizedRaw = raw.split('#')[0].split('?')[0].trim();
        push(normalizedRaw);
        try {
            const parsed = new URL(raw, 'https://dummy.local');
            const path = decodeURIComponent(String(parsed.pathname || '').trim());
            const normalizedPath = path.replace(/\\/g, '/').trim();
            const trimmedPath = normalizedPath.replace(/^\/+/, '');
            push(normalizedPath);
            push(trimmedPath);
            const parts = trimmedPath.split('/').filter(Boolean);
            const fileName = parts.length ? parts[parts.length - 1] : '';
            push(fileName);
            if (parts.length >= 2) push(parts.slice(-2).join('/'));
            if (parts.length >= 3) push(parts.slice(-3).join('/'));
        } catch (error) {
            // Best-effort tokenization for non-standard urls/paths.
            const fallbackPath = normalizedRaw.replace(/\\/g, '/').replace(/^\/+/, '');
            push(fallbackPath);
            const parts = fallbackPath.split('/').filter(Boolean);
            const fileName = parts.length ? parts[parts.length - 1] : '';
            push(fileName);
            if (parts.length >= 2) push(parts.slice(-2).join('/'));
            if (parts.length >= 3) push(parts.slice(-3).join('/'));
        }
        return Array.from(tokens);
    }, []);

    const entityIdByImageToken = useMemo(() => {
        const tokenMap = new Map();
        (Array.isArray(entities) ? entities : []).forEach((entity) => {
            const entityId = String(entity?.id || '').trim();
            if (!entityId) return;

            const customAttrs = (() => {
                try {
                    if (!entity?.custom_attributes) return {};
                    if (typeof entity.custom_attributes === 'string') return JSON.parse(entity.custom_attributes || '{}') || {};
                    if (typeof entity.custom_attributes === 'object') return entity.custom_attributes;
                } catch (error) {
                    return {};
                }
                return {};
            })();

            const imageCandidates = [
                entity?.image_url,
                entity?.imageUrl,
                customAttrs?.image_url,
                customAttrs?.imageUrl,
                customAttrs?.origin_image_url,
                customAttrs?.reused_image_url,
            ].map((value) => String(value || '').trim()).filter(Boolean);

            imageCandidates.forEach((urlText) => {
                collectUrlTokens(urlText).forEach((token) => {
                    if (!tokenMap.has(token)) tokenMap.set(token, entityId);
                });
            });
        });
        return tokenMap;
    }, [collectUrlTokens, entities]);

    const resolveAssetEntityId = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        const directId = String(
            meta?.entity_id
            ?? asset?.entity_id
            ?? meta?.subject_id
            ?? asset?.subject_id
            ?? meta?.character_id
            ?? asset?.character_id
            ?? meta?.owner_entity_id
            ?? asset?.owner_entity_id
            ?? ''
        ).trim();
        if (directId) return directId;

        const entityNameCandidates = [
            meta?.entity_name,
            meta?.subject_name,
            meta?.character_name,
            meta?.owner_entity_name,
            asset?.entity_name,
            asset?.subject_name,
            asset?.character_name,
        ]
            .map((value) => String(value || '').trim())
            .filter(Boolean);

        if (!entityNameCandidates.length || !Array.isArray(entities) || entities.length === 0) return '';

        const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, '');
        const candidateSet = new Set(entityNameCandidates.map(normalize).filter(Boolean));
        if (candidateSet.size === 0) return '';

        const matched = entities.find((item) => {
            const name = normalize(item?.name || '');
            const nameEn = normalize(item?.name_en || '');
            return candidateSet.has(name) || candidateSet.has(nameEn);
        });

        if (matched?.id) return String(matched.id || '').trim();

        const urlCandidates = [
            asset?.url,
            asset?.source_asset_url,
            meta?.url,
            meta?.image_url,
            meta?.source_asset_url,
        ].map((value) => String(value || '').trim()).filter(Boolean);

        for (const candidateUrl of urlCandidates) {
            const matchedByUrl = collectUrlTokens(candidateUrl)
                .map((token) => entityIdByImageToken.get(token))
                .find(Boolean);
            if (matchedByUrl) return String(matchedByUrl || '').trim();
        }

        return '';
    }, [collectUrlTokens, entities, entityIdByImageToken]);

    const resolveAssetShotId = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        return String(meta?.shot_id ?? asset?.shot_id ?? '').trim();
    }, []);

    const resolveAssetFrameType = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        return String(meta?.frame_type || meta?.asset_type || '').trim().toLowerCase();
    }, []);

    const resolveAssetEntityType = useCallback((asset) => {
        const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
        const entityId = String(
            meta?.entity_id
            ?? asset?.entity_id
            ?? meta?.subject_id
            ?? asset?.subject_id
            ?? meta?.character_id
            ?? asset?.character_id
            ?? meta?.owner_entity_id
            ?? asset?.owner_entity_id
            ?? ''
        ).trim();
        const entityRecord = entityId && Array.isArray(entities)
            ? entities.find((item) => String(item?.id || '') === entityId)
            : null;
        if (entityRecord?.type) return String(entityRecord.type).trim().toLowerCase();

        const entityName = String(
            meta?.entity_name
            || meta?.subject_name
            || meta?.character_name
            || meta?.owner_entity_name
            || asset?.entity_name
            || asset?.subject_name
            || asset?.character_name
            || ''
        ).trim();
        if (entityName && Array.isArray(entities)) {
            const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, '');
            const normalizedName = normalize(entityName);
            const matched = entities.find((item) => normalize(item?.name || '') === normalizedName || normalize(item?.name_en || '') === normalizedName);
            if (matched?.type) return String(matched.type).trim().toLowerCase();
        }

        const subjectType = String(meta?.subject_type ?? asset?.subject_type ?? meta?.character_type ?? asset?.character_type ?? '').trim().toLowerCase();
        if (subjectType) return subjectType;

        return String(meta?.entity_type || asset?.entity_type || meta?.type || asset?.type || '').trim().toLowerCase();
    }, [entities]);

    const resolveContextualAssetDisplayName = useCallback((asset) => {
        const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
        const baseName = resolveAssetDisplayName(asset);
        const frameType = resolveAssetFrameType(asset);
        const shotNumber = String(meta?.shot_number || '').trim();
        const shotName = String(meta?.shot_name || '').trim();
        const entityId = resolveAssetEntityId(asset);
        const entityName = String(meta?.entity_name || '').trim();
        const frameLabel = frameType.includes('start')
            ? t('起始帧', 'Start Frame')
            : frameType.includes('end')
                ? t('结束帧', 'End Frame')
                : (frameType.includes('video') || String(asset?.type || '').toLowerCase() === 'video')
                    ? t('视频', 'Video')
                    : frameType.includes('subject')
                        ? t('实体素材', 'Entity Asset')
                        : '';

        const stableContextShotId = contextShotId;
        const stableContextEntityId = contextEntityId;
        const useShotPrefix = stableContextShotId || resolveAssetShotId(asset);
        const useEntityPrefix = !useShotPrefix && (stableContextEntityId || entityId);

        if (useShotPrefix) {
            const shotLabel = shotNumber
                ? `${t('分镜', 'Shot')} ${shotNumber}`
                : (shotName ? `${t('分镜', 'Shot')} ${shotName}` : t('分镜素材', 'Shot Asset'));
            const prefix = frameLabel ? `${shotLabel} ${frameLabel}` : shotLabel;
            return `${prefix} · ${baseName}`;
        }

        if (useEntityPrefix) {
            const entityRecord = entityId
                ? (Array.isArray(entities) ? entities.find((item) => String(item?.id || '') === entityId) : null)
                : null;
            const entityType = String(entityRecord?.type || '').trim().toLowerCase();
            const entityTypeLabel = entityType === 'character'
                ? t('角色', 'Character')
                : entityType === 'prop'
                    ? t('道具', 'Prop')
                    : entityType === 'environment'
                        ? t('环境', 'Environment')
                        : t('实体', 'Entity');
            const labelName = entityName || String(entityRecord?.name || '').trim() || t('未命名实体', 'Unnamed Entity');
            return `${entityTypeLabel} ${labelName} · ${baseName}`;
        }

        if (frameLabel) {
            return `${frameLabel} · ${baseName}`;
        }

        return baseName;
    }, [contextEntityId, contextShotId, entities, resolveAssetDisplayName, resolveAssetEntityId, resolveAssetFrameType, resolveAssetShotId, t]);

    const resolveAssetContextLabel = useCallback((asset) => {
        const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
        const shotNumber = String(meta?.shot_number || '').trim();
        const shotName = String(meta?.shot_name || '').trim();
        const shotId = String(resolveAssetShotId(asset) || '').trim();
        if (shotNumber) return `${t('分镜', 'Shot')} ${shotNumber}`;
        if (shotName) return `${t('分镜', 'Shot')} ${shotName}`;
        if (shotId) return `${t('分镜', 'Shot')} #${shotId}`;

        const entityId = String(resolveAssetEntityId(asset) || '').trim();
        const entityNameFromMeta = String(meta?.entity_name || '').trim();
        const entityRecord = entityId && Array.isArray(entities)
            ? entities.find((item) => String(item?.id || '') === entityId)
            : null;
        const entityName = entityNameFromMeta || String(entityRecord?.name || '').trim();
        if (entityName) return entityName;
        if (entityId) return `${t('实体', 'Entity')} #${entityId}`;

        return t('未绑定分镜/实体', 'Unbound Shot/Entity');
    }, [entities, resolveAssetEntityId, resolveAssetShotId, t]);

    useEffect(() => {
        if (isOpen) {
             setSelectedAsset(null); // Reset detail view on open
             setShowHistoricalProjectAssets(true);
             setEpisodeFilter('all');
             setAssetTypeFilter(preferredAssetType);
             let nextSecondaryKind = 'all';
             const preferredKind = String(context?.defaultSecondaryKind || '').trim().toLowerCase();
             if (contextDisableShotFilter && preferredKind !== 'all') {
                 nextSecondaryKind = 'entity';
             } else if (secondaryKindChoices.includes(preferredKind)) {
                 nextSecondaryKind = preferredKind;
             }
             setSecondaryFilterKind(nextSecondaryKind);
             const defaultSecondaryValue = nextSecondaryKind === 'entity'
                 ? contextEntityId
                 : nextSecondaryKind === 'shot'
                     ? contextShotId
                     : '';
             setSecondaryFilterValue(String(defaultSecondaryValue || '').trim());
             const preferredSubCategory = String(context?.defaultSubCategory || '').trim().toLowerCase();
             if (preferredSubCategory === 'character' || preferredSubCategory === 'prop' || preferredSubCategory === 'environment') {
                 setSubCategoryFilter(preferredSubCategory);
             } else {
                 setSubCategoryFilter('all');
             }
             setSecondaryAutoFollow(false);
             setNameFilter('');
             setSelectedAssetId('');
             setSelectedMulti(new Set());
        }
    }, [context?.defaultSecondaryKind, context?.defaultSubCategory, contextDisableShotFilter, contextEntityId, contextShotId, episodeId, isOpen, preferredAssetType, secondaryKindChoices]);

    useEffect(() => {
        if (!contextDisableShotFilter) return;
        if (secondaryFilterKind === 'shot') {
            setSecondaryFilterKind('entity');
            setSecondaryFilterValue('');
        }
    }, [contextDisableShotFilter, secondaryFilterKind]);

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
            loadAssetsRequestSeqRef.current += 1;
            setAllCleanData(null);
            setLoading(false);
            setSelectedAsset(null);
            setNameFilter('');
            setSelectedAssetId('');
            setSelectedMulti(new Set());
        }
    }, [episodeFilter, episodeId, isOpen, projectId, showHistoricalProjectAssets, tab]);

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

    const levelOneAssets = useMemo(() => {
        const rows = Array.isArray(allCleanData) ? [...allCleanData] : [];
        let filtered = rows;

        logAssetPickerDebug('level1:before', {
            filters: {
                episodeFilter,
                assetTypeFilter,
                episodeId: String(episodeId || '').trim(),
            },
            summary: summarizeAssetsForDebug(rows),
        });

        const currentEpisodeStable = String(episodeId || '').trim();
        if (episodeFilter === 'current' && currentEpisodeStable) {
            filtered = filtered.filter((asset) => resolveAssetEpisodeId(asset) === currentEpisodeStable);
        } else if (episodeFilter !== 'all') {
            filtered = filtered.filter((asset) => resolveAssetEpisodeId(asset) === episodeFilter);
        }

        logAssetPickerDebug('level1:after-episode', {
            summary: summarizeAssetsForDebug(filtered),
        });

        if (assetTypeFilter !== 'all') {
            filtered = filtered.filter((asset) => {
                const videoLike = isAssetVideoLike(asset);
                if (assetTypeFilter === 'video') return videoLike;
                if (assetTypeFilter === 'image') return !videoLike;
                return true;
            });
        }

        logAssetPickerDebug('level1:after-type', {
            summary: summarizeAssetsForDebug(filtered),
        });

        if (typeof window !== 'undefined') {
            console.log('[素材选择][levelOneAssets]', filtered);
        }
        return filtered;
    }, [allCleanData, assetTypeFilter, episodeFilter, episodeId, isAssetVideoLike, logAssetPickerDebug, resolveAssetEpisodeId, summarizeAssetsForDebug]);

    const secondaryEntityOptions = useMemo(() => {
        const grouped = new Map();
        const groupedByAliasKey = new Map();
        const groupedBuckets = new Map();
        const allowedTypes = new Set(['character', 'prop', 'environment']);
        const normalizeAlias = (value) => String(value || '').trim().toLowerCase().replace(/[\s/\\|,，、·._-]+/g, '');
        const collectAliasKeys = (...values) => {
            const keys = new Set();
            values.flat().forEach((value) => {
                const stableValue = String(value || '').trim();
                if (!stableValue) return;
                stableValue
                    .split(/[/\\|,，、]+/)
                    .map((part) => normalizeAlias(part))
                    .filter(Boolean)
                    .forEach((part) => keys.add(part));
                const wholeKey = normalizeAlias(stableValue);
                if (wholeKey) keys.add(wholeKey);
            });
            return Array.from(keys);
        };
        const activeEntityIds = new Set(
            (Array.isArray(levelOneAssets) ? levelOneAssets : [])
                .map((asset) => String(resolveAssetEntityId(asset) || '').trim())
                .filter(Boolean)
        );
        const canonicalEntities = Array.isArray(entities) ? entities : [];
        canonicalEntities.forEach((entity) => {
            const type = String(entity?.type || '').trim().toLowerCase();
            if (!allowedTypes.has(type)) return;
            const eid = String(entity?.id || '').trim();
            if (!eid || grouped.has(eid)) return;
            const nameZh = String(entity?.name || '').trim();
            const nameEn = String(entity?.name_en || '').trim();
            const isSubset = nameZh && nameEn && (nameZh.toLowerCase().includes(nameEn.toLowerCase()) || nameEn.toLowerCase().includes(nameZh.toLowerCase()));
            const label = nameZh && nameEn && !isSubset
                ? `${nameZh} / ${nameEn}`
                : (nameZh || nameEn || `${t('实体', 'Entity')} #${eid}`);
            grouped.set(eid, {
                label,
                type,
                aliases: [nameZh, nameEn, label],
            });
        });

        // Always enrich with asset-derived ids so historical/multi-episode alias ids
        // still appear and can later merge back into the canonical label bucket.
        levelOneAssets.forEach((asset) => {
            const eid = String(resolveAssetEntityId(asset) || '').trim();
            if (!eid) return;
            const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
            const entityRecord = (Array.isArray(entities) ? entities.find((item) => String(item?.id || '') === eid) : null);
            const entityName = String(meta?.entity_name || meta?.subject_name || meta?.character_name || meta?.owner_entity_name || entityRecord?.name || '').trim() || `${t('实体', 'Entity')} #${eid}`;
            const inferredType = String(entityRecord?.type || resolveAssetEntityType(asset) || '').trim().toLowerCase();
            const normalizedType = allowedTypes.has(inferredType) ? inferredType : '';
            const assetAliases = [
                meta?.entity_name,
                meta?.subject_name,
                meta?.character_name,
                meta?.owner_entity_name,
                entityRecord?.name,
                entityRecord?.name_en,
                entityName,
            ];
            const existing = grouped.get(eid);
            if (!existing) {
                grouped.set(eid, {
                    label: entityName,
                    type: normalizedType,
                    aliases: assetAliases,
                });
                return;
            }
            if (!existing.label && entityName) {
                existing.label = entityName;
            }
            if (!existing.type && normalizedType) {
                existing.type = normalizedType;
            }
            existing.aliases = Array.from(new Set([...(existing.aliases || []), ...assetAliases].filter(Boolean)));
        });

        Array.from(grouped.entries()).forEach(([id, entry]) => {
            const label = String(entry?.label || '').trim();
            const type = String(entry?.type || '').trim().toLowerCase();
            const aliasKeys = collectAliasKeys(label, entry?.aliases || []);
            const bucketId = aliasKeys.find((key) => groupedByAliasKey.has(key)) ? groupedByAliasKey.get(aliasKeys.find((key) => groupedByAliasKey.has(key))) : null;
            const existing = bucketId ? groupedBuckets.get(bucketId) : null;
            if (!existing) {
                const nextBucket = {
                    id,
                    label,
                    aliasIds: [id],
                    types: type ? [type] : [],
                    aliasKeys,
                };
                groupedBuckets.set(id, nextBucket);
                aliasKeys.forEach((key) => groupedByAliasKey.set(key, id));
                return;
            }
            existing.aliasIds.push(id);
            if (type) existing.types.push(type);
            existing.aliasKeys = Array.from(new Set([...(existing.aliasKeys || []), ...aliasKeys]));
            existing.aliasKeys.forEach((key) => groupedByAliasKey.set(key, existing.id));
            // Keep the earliest stable id and the longer, more descriptive label.
            if (String(label || '').length > String(existing.label || '').length) {
                existing.label = label;
            }
        });

        const pickPrimaryType = (types) => {
            const candidates = Array.from(new Set((Array.isArray(types) ? types : []).map((value) => String(value || '').trim().toLowerCase()).filter(Boolean)));
            if (candidates.includes('character')) return 'character';
            if (candidates.includes('prop')) return 'prop';
            if (candidates.includes('environment')) return 'environment';
            return '';
        };

        const options = Array.from(groupedBuckets.values())
            .map((item) => ({
                id: item.id,
                label: item.label,
                aliasIds: Array.from(new Set(item.aliasIds.map((v) => String(v).trim()).filter(Boolean))),
                type: pickPrimaryType(item.types),
            }))
            .sort((a, b) => String(a.label).localeCompare(String(b.label), undefined, { numeric: true }));
        if (typeof window !== 'undefined') {
            console.log('[素材选择][secondaryEntityOptions]', options);
        }
        return options;
    }, [entities, levelOneAssets, resolveAssetEntityId, resolveAssetEntityType, t]);

    const secondaryShotOptions = useMemo(() => {
        if (contextDisableShotFilter || secondaryFilterKind !== 'shot') {
            if (typeof window !== 'undefined') {
                console.log('[素材选择][secondaryShotOptions]', []);
            }
            return [];
        }

        const grouped = new Map();

        // Prefer canonical episode shots first so shot choices remain available even
        // when assets do not carry a shot_id in their metadata.
        if (Array.isArray(availableShots)) {
            availableShots.forEach((shot) => {
                const sid = String(shot?.id || '').trim();
                if (!sid || grouped.has(sid)) return;
                const shotIdText = String(shot?.shot_id || '').trim();
                const shotName = String(shot?.shot_name || '').trim();
                const labelParts = [];
                if (shotIdText) labelParts.push(shotIdText);
                if (shotName) labelParts.push(shotName);
                const label = labelParts.length > 0
                    ? `${t('分镜', 'Shot')} ${labelParts.join(' · ')}`
                    : `${t('分镜', 'Shot')} #${sid}`;
                grouped.set(sid, label);
            });
        }

        levelOneAssets.forEach((asset) => {
            const sid = String(resolveAssetShotId(asset) || '').trim();
            if (!sid) return;
            if (grouped.has(sid)) return;
            const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
            const shotNumber = String(meta?.shot_number || '').trim();
            const shotName = String(meta?.shot_name || '').trim();
            let label = shotNumber ? `${t('分镜', 'Shot')} ${shotNumber}` : (shotName ? `${t('分镜', 'Shot')} ${shotName}` : `${t('分镜', 'Shot')} #${sid}`);
            const shotRecord = Array.isArray(availableShots) ? availableShots.find((row) => String(row?.id || '') === sid) : null;
            if (shotRecord?.shot_id) {
                label = `${label} (${shotRecord.shot_id})`;
            }
            grouped.set(sid, label);
        });
        const options = Array.from(grouped.entries())
            .map(([id, label]) => ({ id, label }))
            .sort((a, b) => String(a.label).localeCompare(String(b.label), undefined, { numeric: true }));
        if (typeof window !== 'undefined') {
            console.log('[素材选择][secondaryShotOptions]', options);
        }
        return options;
    }, [availableShots, contextDisableShotFilter, levelOneAssets, resolveAssetShotId, secondaryFilterKind, t]);

    const visibleSecondaryEntityOptions = useMemo(() => {
        if (secondaryFilterKind !== 'entity' || subCategoryFilter === 'all') {
            return secondaryEntityOptions;
        }
        return secondaryEntityOptions.filter((option) => String(option?.type || '').trim().toLowerCase() === subCategoryFilter);
    }, [secondaryEntityOptions, secondaryFilterKind, subCategoryFilter]);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const typeCounts = secondaryEntityOptions.reduce((acc, option) => {
            const key = String(option?.type || '').trim().toLowerCase() || '(empty)';
            acc[key] = (acc[key] || 0) + 1;
            return acc;
        }, {});
        console.log('[素材选择][entity-visibility]', {
            secondaryFilterKind,
            subCategoryFilter,
            totalSecondaryEntityOptions: secondaryEntityOptions.length,
            visibleSecondaryEntityOptions: visibleSecondaryEntityOptions.length,
            typeCounts,
            visiblePreview: visibleSecondaryEntityOptions.slice(0, 12).map((option) => ({
                id: option?.id,
                label: option?.label,
                type: option?.type,
                aliasIds: option?.aliasIds,
            })),
        });
    }, [secondaryFilterKind, subCategoryFilter, secondaryEntityOptions, visibleSecondaryEntityOptions]);

    const filteredAssets = useMemo(() => {
        let filtered = [...levelOneAssets];

        const hasShotLink = (asset) => {
            const shotId = String(resolveAssetShotId(asset) || '').trim();
            return Boolean(shotId);
        };

        const isExplicitShotFrameAsset = (asset) => {
            const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
            const shotNo = String(meta?.shot_number || '').trim();
            const shotName = String(meta?.shot_name || '').trim();
            if (shotNo || shotName) return true;
            const frameType = String(resolveAssetFrameType(asset) || '').trim().toLowerCase();
            if (frameType.includes('start')
                || frameType.includes('end')
                || frameType.includes('keyframe')
                || frameType.includes('video')
                || frameType.includes('shot')) {
                return true;
            }
            const assetName = String(asset?.name || meta?.asset_name || meta?.display_name || '').trim().toLowerCase();
            return assetName.includes('分镜') || assetName.includes('shot_') || assetName.includes('storyboard');
        };

        const isShotBoundAsset = (asset) => hasShotLink(asset) || isExplicitShotFrameAsset(asset);

        logAssetPickerDebug('level2:before-secondary', {
            filters: {
                secondaryFilterKind,
                secondaryFilterValue,
                subCategoryFilter,
                contextShotId,
                contextEntityId,
                contextFrameType,
                nameFilter,
            },
            summary: summarizeAssetsForDebug(filtered),
        });

        const entityOptionIdsByType = new Map();
        secondaryEntityOptions.forEach((option) => {
            const normalizedType = String(option?.type || '').trim().toLowerCase();
            if (!normalizedType) return;
            const bucket = entityOptionIdsByType.get(normalizedType) || new Set();
            [String(option?.id || ''), ...((option?.aliasIds || []).map((value) => String(value || '')))]
                .map((value) => String(value || '').trim())
                .filter(Boolean)
                .forEach((id) => bucket.add(id));
            entityOptionIdsByType.set(normalizedType, bucket);
        });

        if (secondaryFilterKind === 'entity') {
            filtered = filtered.filter((asset) => {
                const entityId = String(resolveAssetEntityId(asset) || '').trim();
                if (!entityId) return false;
                if (isExplicitShotFrameAsset(asset)) return false;
                return true;
            });
            logAssetPickerDebug('level2:entity-scope-non-shot', {
                summary: summarizeAssetsForDebug(filtered),
            });

            if (subCategoryFilter !== 'all') {
                const allowedEntityIds = entityOptionIdsByType.get(subCategoryFilter) || new Set();
                filtered = filtered.filter((asset) => allowedEntityIds.has(String(resolveAssetEntityId(asset) || '').trim()));
                logAssetPickerDebug('level2:entity-subtype-options', {
                    subCategoryFilter,
                    allowedEntityIds: Array.from(allowedEntityIds),
                    summary: summarizeAssetsForDebug(filtered),
                });
            }

            if (secondaryFilterValue) {
                const selectedOption = secondaryEntityOptions.find((item) => String(item.id) === String(secondaryFilterValue) || (item.aliasIds && item.aliasIds.some((v) => String(v) === String(secondaryFilterValue))));
                const acceptedEntityIds = new Set([
                    String(secondaryFilterValue),
                    ...((selectedOption?.aliasIds || []).map((value) => String(value))),
                ]);
                filtered = filtered.filter((asset) => acceptedEntityIds.has(String(resolveAssetEntityId(asset) || '')));
                logAssetPickerDebug('level2:entity-value', {
                    selectedEntityIds: Array.from(acceptedEntityIds),
                    summary: summarizeAssetsForDebug(filtered),
                });
            }
        } else if (secondaryFilterKind === 'shot') {
            // Shot scope should not mix in entity assets.
            filtered = filtered.filter((asset) => isShotBoundAsset(asset));
            logAssetPickerDebug('level2:shot-scope', {
                summary: summarizeAssetsForDebug(filtered),
            });
            // Only narrow by exact shot when user explicitly chooses a shot value.
            if (secondaryFilterValue) {
                const exactShotOnly = filtered.filter((asset) => String(resolveAssetShotId(asset)) === String(secondaryFilterValue));
                logAssetPickerDebug('level2:shot-exact-candidates', {
                    value: secondaryFilterValue,
                    exactShotOnly: summarizeAssetsForDebug(exactShotOnly),
                });
                if (exactShotOnly.length > 0) {
                    filtered = exactShotOnly;
                    logAssetPickerDebug('level2:shot-exact-applied', {
                        summary: summarizeAssetsForDebug(filtered),
                    });
                }
            }
        }

        if (secondaryFilterKind === 'shot') {
            if (subCategoryFilter === 'shot_start') {
                filtered = filtered.filter((asset) => {
                    const frameType = resolveAssetFrameType(asset);
                    return frameType.includes('start') || frameType.includes('keyframe');
                });
                logAssetPickerDebug('level2:subcategory-shot_start', {
                    summary: summarizeAssetsForDebug(filtered),
                });
            } else if (subCategoryFilter === 'shot_video') {
                filtered = filtered.filter((asset) => {
                    return isAssetVideoLike(asset);
                });
                logAssetPickerDebug('level2:subcategory-shot_video', {
                    summary: summarizeAssetsForDebug(filtered),
                });
            }
        }

        const stableNameFilter = String(nameFilter || '').trim().toLowerCase();
        if (stableNameFilter) {
            filtered = filtered.filter((asset) => String(resolveContextualAssetDisplayName(asset) || '').toLowerCase().includes(stableNameFilter));
            logAssetPickerDebug('level2:name-filter', {
                value: stableNameFilter,
                summary: summarizeAssetsForDebug(filtered),
            });
        }

        const dedupMap = new Map();
        filtered.forEach((asset) => {
            const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
            const idKey = String(asset?.id || '').trim();
            const urlKey = String(asset?.url || '').trim();
            const normalizedUrlKey = urlKey ? urlKey.replace(/[?#].*$/, '').trim().toLowerCase() : '';
            const nameKey = String(asset?.name || meta?.asset_name || meta?.display_name || '').trim();
            // Keep distinct persisted rows first; only fall back to URL-based dedup when id is missing.
            const compositeKey = idKey || normalizedUrlKey || `${urlKey}::${nameKey}`;
            if (!compositeKey) return;
            if (!dedupMap.has(compositeKey)) {
                dedupMap.set(compositeKey, asset);
            }
        });
        filtered = Array.from(dedupMap.values());

        filtered.sort((left, right) => {
            const l = new Date(left?.created_at || 0).getTime();
            const r = new Date(right?.created_at || 0).getTime();
            return r - l;
        });
        logAssetPickerDebug('level2:final', {
            summary: summarizeAssetsForDebug(filtered),
        });
        return filtered;
    }, [assetTypeFilter, contextDisableShotFilter, contextEntityId, contextFrameType, contextShotId, episodeFilter, levelOneAssets, logAssetPickerDebug, nameFilter, resolveAssetEntityId, resolveAssetFrameType, resolveAssetShotId, resolveContextualAssetDisplayName, secondaryEntityOptions, secondaryFilterKind, secondaryFilterValue, subCategoryFilter, summarizeAssetsForDebug]);

    useEffect(() => {
        if (secondaryFilterKind !== 'entity' && secondaryFilterKind !== 'shot') {
            if (subCategoryFilter !== 'all') setSubCategoryFilter('all');
            return;
        }

        if (secondaryFilterKind === 'entity') {
            const allowed = new Set(['all', 'character', 'prop', 'environment']);
            if (!allowed.has(subCategoryFilter)) setSubCategoryFilter('all');
            return;
        }

        const allowed = new Set(['all', 'shot_start', 'shot_video']);
        if (!allowed.has(subCategoryFilter)) setSubCategoryFilter('all');
    }, [secondaryFilterKind, subCategoryFilter]);

    useEffect(() => {
        if (secondaryAutoFollow) return;
        if (secondaryFilterKind === 'entity') {
            const match = visibleSecondaryEntityOptions.find((item) => String(item.id) === String(secondaryFilterValue) || (item.aliasIds && item.aliasIds.some((v) => String(v) === String(secondaryFilterValue))));
            if (!match && secondaryFilterValue) {
                setSecondaryFilterValue('');
            } else if (match && String(match.id) !== String(secondaryFilterValue)) {
                setSecondaryFilterValue(String(match.id));
            }
            return;
        }
        if (secondaryFilterKind === 'shot') {
            const exists = secondaryShotOptions.some((item) => String(item.id) === String(secondaryFilterValue));
            if (!exists && secondaryFilterValue) setSecondaryFilterValue('');
            return;
        }
        if (secondaryFilterValue) setSecondaryFilterValue('');
    }, [secondaryAutoFollow, secondaryFilterKind, secondaryFilterValue, secondaryShotOptions, visibleSecondaryEntityOptions]);

    useEffect(() => {
        if (!isOpen || tab !== 'assets') return;
        if (!filteredAssets.length) {
            setSelectedAsset(null);
            if (selectedAssetId) setSelectedAssetId('');
            return;
        }
        // 如果当前选中的资产不在新筛选结果里，或切换了二级筛选，则自动选中第一个
        const matched = filteredAssets.find((item) => String(item.id) === String(selectedAssetId));
        if (matched) {
            if (String(selectedAsset?.id || '') !== String(matched.id)) setSelectedAsset(matched);
            return;
        }
        // 只要 filteredAssets 变化或二级筛选变化就自动选第一个
        const first = filteredAssets[0];
        setSelectedAssetId(String(first.id));
        setSelectedAsset(first);
    }, [filteredAssets, isOpen, selectedAsset?.id, selectedAssetId, tab, secondaryFilterKind, secondaryFilterValue]);

    useEffect(() => {
        if (!isOpen || tab !== 'assets') return;
        if (!contextAllowMultiSelect) {
            setSelectedMulti((prev) => (prev.size > 0 ? new Set() : prev));
            return;
        }
        const visibleIds = new Set(filteredAssets.map((item) => String(item.id)));
        setSelectedMulti((prev) => {
            if (!prev || prev.size === 0) return prev;
            const next = new Set();
            prev.forEach((id) => {
                if (visibleIds.has(String(id))) next.add(id);
            });
            if (next.size === prev.size) {
                let unchanged = true;
                prev.forEach((id) => {
                    if (!next.has(String(id))) unchanged = false;
                });
                if (unchanged) return prev;
            }
            return next;
        });
    }, [contextAllowMultiSelect, filteredAssets, isOpen, tab]);

    const loadAssets = useCallback(async () => {
        const requestSeq = ++loadAssetsRequestSeqRef.current;
                if (typeof window !== 'undefined') {
                    console.log('[素材选择][loadAssets] params', {
                        requestSeq,
                        projectId,
                        episodeId,
                        entityId: contextEntityId,
                        shotId: contextShotId,
                    });
                }
        setLoading(true);
        try {
            const fetchAssetsPaged = async (params = {}) => {
                const pageSize = 200;
                const maxPages = 30;
                const merged = [];

                for (let page = 0; page < maxPages; page += 1) {
                    const pageRows = await fetchAssets({
                        ...params,
                        skip: page * pageSize,
                        limit: pageSize,
                    });
                    const rows = Array.isArray(pageRows) ? pageRows : [];
                    if (!rows.length) break;
                    merged.push(...rows);
                    if (rows.length < pageSize) break;
                }

                return merged;
            };

            const baseParams = {};
            if (projectId) {
                baseParams.project_id = projectId;
                baseParams.current_project_asset = showHistoricalProjectAssets ? 'all' : '1';
            }

            const currentEpisodeStable = String(episodeId || '').trim();
            const selectedEpisodeStable = String(episodeFilter || '').trim();
            if (selectedEpisodeStable === 'current' && currentEpisodeStable) {
                baseParams.episode_id = currentEpisodeStable;
                baseParams.include_project_null_episode = 'true';
            } else if (selectedEpisodeStable && selectedEpisodeStable !== 'all') {
                baseParams.episode_id = selectedEpisodeStable;
            }
            const scopedParams = { ...baseParams };

            const shouldFilterReferencedOnly = Boolean(projectId) && !showHistoricalProjectAssets;
            const [scopedData, refsPayload] = await Promise.all([
                fetchAssetsPaged(scopedParams),
                shouldFilterReferencedOnly ? fetchUnreferencedAssetIds({ project_id: projectId, episode_id: episodeId || undefined }) : Promise.resolve(null)
            ]);

            logAssetPickerDebug('load:scoped-response', {
                scopedParams,
                shouldFilterReferencedOnly,
                summary: summarizeAssetsForDebug(scopedData),
            });

            const data = scopedData;

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

            logAssetPickerDebug('load:clean-data', {
                requestSeq,
                shouldFilterReferencedOnly,
                hasReferencedHints,
                referencedCount: referencedSet.size,
                before: summarizeAssetsForDebug(data),
                after: summarizeAssetsForDebug(cleanData),
            });

            if (typeof window !== 'undefined') {
                console.log('[素材选择][cleanData]', cleanData);
            }
            if (requestSeq !== loadAssetsRequestSeqRef.current) {
                logAssetPickerDebug('load:stale-response-ignored', {
                    requestSeq,
                    latestRequestSeq: loadAssetsRequestSeqRef.current,
                    summary: summarizeAssetsForDebug(cleanData),
                });
                return;
            }
            setAllCleanData(cleanData); // Save clean version to memory
        } catch (error) {
            console.error(error);
        } finally {
            if (requestSeq === loadAssetsRequestSeqRef.current) {
                setLoading(false);
            }
        }
    }, [episodeFilter, episodeId, logAssetPickerDebug, projectId, showHistoricalProjectAssets, summarizeAssetsForDebug]);

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
             <div className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-4xl h-[82vh] max-h-[760px] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
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
                                setSelectedAssetId('');
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
                                setSelectedAssetId('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                            disabled={contextLockAssetType && preferredAssetType !== 'all'}
                        >
                            <option value="all">{t('全部类型', 'All Types')}</option>
                            <option value="image">{t('图片', 'Image')}</option>
                            <option value="video">{t('视频', 'Video')}</option>
                        </select>

                        <select
                            value={secondaryFilterKind}
                            onChange={(e) => {
                                setSecondaryAutoFollow(false);
                                setSecondaryFilterKind(e.target.value);
                                setSecondaryFilterValue('');
                                setSelectedAssetId('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="all">{t('全部', 'All')}</option>
                            <option value="entity">{t('实体', 'Entity')}</option>
                            {!contextDisableShotFilter && <option value="shot">{t('分镜', 'Shot')}</option>}
                        </select>

                        <select
                            value={secondaryFilterValue}
                            onChange={(e) => {
                                setSecondaryAutoFollow(false);
                                setSecondaryFilterValue(e.target.value);
                                setSelectedAssetId('');
                            }}
                            className="min-w-[180px] bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                            disabled={secondaryFilterKind === 'all'}
                        >
                            <option value="">{secondaryFilterKind === 'shot' ? t('全部分镜', 'All Shots') : t('全部实体', 'All Entities')}</option>
                            {(secondaryFilterKind === 'shot' ? secondaryShotOptions : visibleSecondaryEntityOptions).map((option) => (
                                <option key={option.id} value={option.id}>{option.label}</option>
                            ))}
                        </select>

                        <select
                            value={subCategoryFilter}
                            onChange={(e) => {
                                setSubCategoryFilter(e.target.value);
                                setSelectedAssetId('');
                            }}
                            className="min-w-[140px] bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                            disabled={secondaryFilterKind === 'all'}
                        >
                            {secondaryFilterKind === 'entity' ? (
                                <>
                                    <option value="all">{t('全部细类', 'All Subtypes')}</option>
                                    <option value="character">{t('角色', 'Character')}</option>
                                    <option value="prop">{t('道具', 'Prop')}</option>
                                    <option value="environment">{t('环境', 'Environment')}</option>
                                </>
                            ) : secondaryFilterKind === 'shot' ? (
                                <>
                                    <option value="all">{t('全部细类', 'All Subtypes')}</option>
                                    <option value="shot_start">{t('起始帧', 'Start Frame')}</option>
                                    <option value="shot_video">{t('视频', 'Video')}</option>
                                </>
                            ) : (
                                <option value="all">{t('全部细类', 'All Subtypes')}</option>
                            )}
                        </select>

                        <input
                            value={nameFilter}
                            onChange={(e) => {
                                setNameFilter(e.target.value);
                                setSelectedAssetId('');
                            }}
                            className="min-w-[180px] flex-1 bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                            placeholder={t('按名称搜索', 'Search by name')}
                        />

                        <div className="ml-auto text-[10px] text-muted-foreground">
                            {filteredAssets.length} {t('条结果', 'results')} · {selectedMulti.size} {t('已选', 'selected')}
                        </div>
                    </div>
                )}

                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#151515]">
                    {tab === 'assets' && (
                        loading ? <div className="flex items-center justify-center h-full"><RefreshCw className="animate-spin text-muted-foreground"/></div> :
                        <div className="h-full min-h-0">
                            {filteredAssets.length === 0 ? (
                                <div className="h-full flex items-center justify-center text-center text-muted-foreground">
                                    <div>
                                        <p>{t('未找到素材', 'No assets found')}</p>
                                        <p className="text-xs mt-2 text-white/40">{t('请调整分集/类型筛选后再试。', 'Please adjust episode/type filters and try again.')}</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="h-full min-h-0 rounded-lg border border-white/10 bg-black/20 p-2 overflow-y-auto custom-scrollbar">
                                        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2">
                                            {filteredAssets.map((asset) => {
                                                const checked = selectedMulti.has(String(asset.id));
                                                const isSelected = String(selectedAssetId) === String(asset.id);
                                                const isVideo = isAssetVideoLike(asset);
                                                return (
                                                    <button
                                                        key={asset.id}
                                                        type="button"
                                                        onClick={() => {
                                                            const stableId = String(asset.id);
                                                            setSelectedAsset(asset);
                                                            setSelectedAssetId(stableId);
                                                            if (contextAllowMultiSelect) {
                                                                setSelectedMulti((prev) => {
                                                                    const next = new Set(prev);
                                                                    if (next.has(stableId)) next.delete(stableId);
                                                                    else next.add(stableId);
                                                                    return next;
                                                                });
                                                                return;
                                                            }
                                                            setSelectedMulti(new Set());
                                                        }}
                                                        className={`relative rounded overflow-hidden border text-left transition-all ${checked || isSelected ? 'border-primary/60 ring-1 ring-primary/30' : 'border-white/10 hover:border-white/30'}`}
                                                        title={resolveAssetContextLabel(asset)}
                                                    >
                                                        <div className="aspect-square bg-black/40 flex items-center justify-center">
                                                            {isVideo ? (
                                                                <div className="w-full h-full flex items-center justify-center bg-black/50">
                                                                    <Video className="w-7 h-7 text-white/65" />
                                                                </div>
                                                            ) : (
                                                                <SafeImage src={asset.url} className="w-full h-full object-cover" alt={resolveAssetContextLabel(asset)} />
                                                            )}
                                                        </div>
                                                        <div className="px-1.5 py-1 bg-black/55 flex flex-col justify-center">
                                                            <div className="text-[10px] text-white/85 truncate" title={resolveAssetContextLabel(asset)}>
                                                                {resolveAssetContextLabel(asset)}
                                                            </div>
                                                            <div className="text-[9px] text-white/50 truncate" title={resolveAssetDisplayName(asset)}>
                                                                {resolveAssetDisplayName(asset)}
                                                            </div>
                                                        </div>
                                                        {(checked || isSelected) && (
                                                            <div className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-primary" />
                                                        )}
                                                    </button>
                                                );
                                            })}
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
                            {contextAllowMultiSelect && selectedMulti.size > 0
                                ? `${selectedMulti.size} ${t('个资产已选中', 'assets selected')}`
                                : (selectedAsset ? (resolveContextualAssetDisplayName(selectedAsset) || t('已选中目标资产', 'Selected Target Asset')) : t('未选择资产', 'No asset selected'))}
                        </div>
                        <button
                            disabled={!selectedAsset && (!contextAllowMultiSelect || selectedMulti.size === 0)}
                            onClick={async () => {
                                const selectedItems = contextAllowMultiSelect
                                    ? filteredAssets.filter((asset) => selectedMulti.has(String(asset.id)))
                                    : [];
                                const orderedSelectedItems = (() => {
                                    if (!contextAllowMultiSelect || selectedItems.length <= 1) return selectedItems;
                                    const allVideo = selectedItems.every((asset) => isAssetVideoLike(asset));
                                    if (!allVideo) return selectedItems;
                                    return [...selectedItems].sort((left, right) => {
                                        const leftName = String(resolveAssetDisplayName(left) || '').trim();
                                        const rightName = String(resolveAssetDisplayName(right) || '').trim();
                                        return leftName.localeCompare(rightName, undefined, { numeric: true, sensitivity: 'base' });
                                    });
                                })();
                                if (contextAllowMultiSelect && orderedSelectedItems.length > 0) {
                                    if (projectId) {
                                        await Promise.all(orderedSelectedItems.map((asset) => handleMarkAssetCurrent(asset).catch(() => null)));
                                    }
                                    const first = orderedSelectedItems[0];
                                    onSelect(first?.url, first?.type, orderedSelectedItems);
                                    return;
                                }
                                if (!selectedAsset) return;
                                await handleSelectAsset(selectedAsset);
                            }}
                            className="bg-primary text-black text-sm font-bold px-6 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {contextAllowMultiSelect && selectedMulti.size > 0 ? t('选择已勾选资产', 'Select Checked Assets') : t('选择目标资产', 'Select Target Asset')}
                        </button>
                    </div>
                )}
             </div>
        </div>
    );
};

