
import FunctionApiSelector from '../components/FunctionApiSelector';
import { useFunctionApis } from '../components/useFunctionApis';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../lib/store';
import LogPanel from '../components/LogPanel';
import ProjectStatusBar from '../components/ProjectStatusBar';
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, RotateCcw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL, ASSET_BASE_URL } from '../config';
import { setUiLang as setGlobalUiLang } from '../lib/uiLang';
import {
    cleanMarkdownTableCells,
    reconcileSceneTableRowCells,
    buildSceneTableHeaderMap,
    getSceneTableFallbackIndices,
    normalizeSceneTableHeaderKey,
} from '../lib/sceneTableParser';

import {
    getFullUrl, createInitialFrameTrimState, clampFrameTrimPercent, normalizeFrameTrimMargins, brokenMediaUrls, brokenSceneImageUrls, warmMediaUrls, shouldBypassBrokenMediaCache, rememberBrokenMediaUrl, isBrokenMediaUrl, rememberWarmMediaUrl, isWarmMediaUrl, getSafeMediaUrl, extractImageJobResultUrl, rememberBrokenSceneImageUrl, isBrokenSceneImageUrl, normalizeBatchParallelLimit, normalizeAsciiSubjectSeparatorsForDeps, normalizeSubjectNameForDeps, normalizeSubjectKeyForDeps, normalizeAsciiSubjectSeparators, normalizeSubjectName, normalizeSubjectKey, normalizeImportSubjectKey, IMG_PLACEHOLDER_SRC, parseVisualDependencies, SafeImage, SafeAudio, normalizeMediaRefList, areMediaRefListsEqual, collectMatchedEntitiesFromPrompt, collectMatchedEntityImageUrlsFromPrompt, SCENE_SUBJECT_TYPE_LABELS, getSceneSubjectStatusKey, splitSceneSubjectNames, normalizeSceneSubjectDefaultType, parseTypedSceneSubjectToken, extractSceneSubjectRefsFromField, buildSceneSubjectNameCandidates, extractSceneSubjectRefs, findMatchingEntityByType, findMissingSceneSubjectRefs, findCrossTypeEntityMatches, buildSceneSubjectPlaceholderPayload, createMissingSceneSubjectPlaceholders, collectMatchedSubjectImageUrlsFromPrompt, resolveUnifiedVideoMode, buildAutoVideoRefList, resolveShotVideoPosterUrl, LazyHoverVideo, InViewVideo, ManagedVideoPlayer, parseEpisodeNumberFromText, normalizeEpisodeTitleForDisplay, buildEntityNegativePrompt, normalizeImageSizeOption, normalizeAspectRatioOption, parseAspectRatioParts, parseAspectRatioValue, reduceAspectRatioParts, buildAspectRatioString, inferImageSizeFromResolution, getEpisodePreferredImageSize, getEpisodePreferredAspectRatio, getProjectPreferredImageSize, getProjectPreferredAspectRatio, buildShotDiptychPlan, getShotDiptychLayoutLabel, buildShotDiptychLayoutInstruction, buildShotDiptychAspectContract, getShotDiptychSeamTrimPx, getShotDiptychSeamBiasPx, getShotDiptychFallbackCropPx, JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION, SHOT_FRAME_ASSET_UPLOAD_VERSION, hashStableText, buildJointShotDiptychUploadIdempotencyKey, buildShotFrameAssetUploadIdempotencyKey, collectSupportedAspectRatioOptions, collectSupportedImageSizeOptions, selectBestShotDiptychRequestAspectRatio, selectBestSupportedImageSize, resolveShotPanelExportResolution, resolveShotDiptychRequestResolution, getResolutionByAspectAndImageSize, SHOT_IMAGE_CFG_MIN, SHOT_IMAGE_CFG_MAX, SHOT_IMAGE_CFG_STEP, SHOT_IMAGE_CFG_FALLBACK, clampShotImageCfg, resolveShotImageCfgDefault, extractDialogueOnlyFromPrompt, inferLanguageCodeFromProjectLanguage, buildVoicePromptWithEntityContext, buildEpisodeDisplayLabel
} from './editor/editorHelpers';

import { 
    fetchProject, 
    updateProject,
    exportProjectBackup,
    importProjectBackup,
    generateProjectStoryGlobal,
    analyzeProjectNovel,
    generateProjectCharacterProfile,
    fetchEpisodes, 
    fetchEpisode,
    createEpisode, 
    updateEpisode,
    updateEpisodeSegments,
    deleteEpisode,
    fetchScenes, 
    createScene,
    batchUpsertScenes,
    purgeEpisodeScenes,
    updateScene, 
    deleteScene,
    regenerateScene,
    fetchShots,
    fetchEpisodeShots,
    createShot,
    batchCreateShots,
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
    fetchProjectBillingStats,
} from '../services/api';

import RefineControl from '../components/RefineControl.jsx';
import { DeletionTrashModal } from '../components/DeletionTrashModal';

import {
    PROVIDER_LABELS,
    MODEL_OPTIONS,
    getSettingSourceByCategory,
    formatProviderModelEndpointError,
} from './editor/editorConfig';
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
} from './editor/projectOptionConfig';

// RefineControl moved to components/RefineControl.jsx
import { processPrompt } from '../lib/promptUtils';
import { entityNameAppearsInText, entityTokenMatchesName, normalizeEntityToken } from '../lib/entityToken';
import SettingsPage from './Settings';
import { confirmUiMessage, promptUiMessage } from '../lib/uiMessage';
import ErrorBoundary from '../components/ErrorBoundary';

// Character Canon (Authoritative) generator (shared)

import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint } from './editor/editorConstants';


import { ImportModal } from './editor/components/ImportModal';
import { SceneManager } from './editor/components/SceneManager';

// Lazy loaded heavy components
const ProjectOverview = React.lazy(() => import('./editor/components/ProjectOverview').then(m => ({ default: m.ProjectOverview })));
const EpisodeInfo = React.lazy(() => import('./editor/components/EpisodeInfo').then(m => ({ default: m.EpisodeInfo })));
const ScriptEditor = React.lazy(() => import('./editor/components/ScriptEditor').then(m => ({ default: m.ScriptEditor })));
const SubjectLibrary = React.lazy(() => import('./editor/components/SubjectLibrary').then(m => ({ default: m.SubjectLibrary })));
const ShotsView = React.lazy(() => import('./editor/components/ShotsView').then(m => ({ default: m.ShotsView })));
const VideoStudio = React.lazy(() => import('../components/VideoStudio'));

const PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY = 'aistory.projects.return.snapshot';
const EPISODE_REQUIRED_TABS = new Set(['script', 'subjects', 'scenes', 'shots', 'montage']);

const buildProjectReturnSnapshot = ({
    projectId,
    activeTab,
    activeEpisodeId,
    editingShot,
}) => ({
    selectedProjectId: projectId,
    activeTab,
    activeEpisodeId,
    editingShotId: editingShot?.id ?? null,
    editingShotSceneId: editingShot?.scene_id ?? null,
    savedAt: Date.now(),
});

const Editor = ({
    projectId,
    initialProject,
    onClose,
    initialActiveTab,
    initialEpisodeId = null,
    initialEditingShotId = null,
    initialEditingShotSceneId = null,
}) => {
    const functionApiConfigs = useFunctionApis();
    const params = useParams();
    const id = projectId || params.id;
    const navigate = useNavigate();
    const cachedInitialProject = initialProject && String(initialProject.id) === String(id) ? initialProject : null;

    const [isInitializing, setIsInitializing] = useState(!cachedInitialProject);
    const [project, setProject] = useState(cachedInitialProject || null);
    const [episodes, setEpisodes] = useState([]);
    const [isEpisodesLoading, setIsEpisodesLoading] = useState(false);
    const [activeEpisodeId, setActiveEpisodeId] = useState(initialEpisodeId);
    const pendingInitialEpisodeIdRef = useRef(initialEpisodeId);
    const [isEpisodeMenuOpen, setIsEpisodeMenuOpen] = useState(false);
    const [activeTab, setActiveTab] = useState(
        (initialActiveTab === 'ep_info' ? 'overview' : initialActiveTab) 
          || initialProject?.global_info?.workflow_stage 
          || 'overview'
    );
    const [isImportOpen, setIsImportOpen] = useState(false);
    const [isJobPoolOpen, setIsJobPoolOpen] = useState(false);
    const [trashModalOpen, setTrashModalOpen] = useState(false);
    const [isProjectBackupExporting, setIsProjectBackupExporting] = useState(false);
    const [isProjectBackupImporting, setIsProjectBackupImporting] = useState(false);
    const [jobPoolLoading, setJobPoolLoading] = useState(false);
    const [jobPoolStoppingId, setJobPoolStoppingId] = useState('');
    const [jobPoolDeletingId, setJobPoolDeletingId] = useState('');
    const [jobPoolStoppingAll, setJobPoolStoppingAll] = useState(false);
    const [jobPoolStoppingAllApi, setJobPoolStoppingAllApi] = useState(false);
    const projectBackupFileInputRef = useRef(null);
    const [jobPoolStopLimit, setJobPoolStopLimit] = useState('20');
    const [jobPoolFilterKind, setJobPoolFilterKind] = useState('all');
    const [jobPoolRunningOnly, setJobPoolRunningOnly] = useState(true);
    const [jobPoolData, setJobPoolData] = useState({ total: 0, status_counts: {}, items: [] });
    const [isSuperuser, setIsSuperuser] = useState(false);
    const [currentUserId, setCurrentUserId] = useState(null);
    const [currentUserCredits, setCurrentUserCredits] = useState(0);
    const [userBatchParallelLimit, setUserBatchParallelLimit] = useState(3);
    const [projectBillingStats, setProjectBillingStats] = useState({ user_cost: 0, total_cost: 0 });
    const [refreshKey, setRefreshKey] = useState(0);
    const [entitiesRefreshKey, setEntitiesRefreshKey] = useState(0);
    const [editingShot, setEditingShot] = useState(null);
    const [shotsFocusRequest, setShotsFocusRequest] = useState(null);
    const [assetRerunRequest, setAssetRerunRequest] = useState(null);
    const hasAppliedInitialShotFocusRef = useRef(false);
    const [uiLang, setUiLang] = useState(() => {
        try {
            const saved = localStorage.getItem('aistory.ui.lang');
            if (saved === 'zh' || saved === 'en') return saved;
        } catch (e) {}
        const navLang = (typeof navigator !== 'undefined' && navigator.language) ? navigator.language : 'en';
        return navLang.toLowerCase().startsWith('zh') ? 'zh' : 'en';
    });
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);

    // Global Logging Context
    const { addLog } = useLog();
    const episodesLoadPromiseRef = useRef(null);
    const episodesRef = useRef([]);
    const activeEpisodeIdRef = useRef(initialEpisodeId);
    const previousProjectIdRef = useRef(null);

    const persistProjectReturnSnapshot = useCallback(() => {
        try {
            const snapshot = buildProjectReturnSnapshot({
                projectId: id,
                activeTab,
                activeEpisodeId,
                editingShot,
            });
            sessionStorage.setItem(PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY, JSON.stringify(snapshot));
            return snapshot;
        } catch (e) {
            return null;
        }
    }, [activeEpisodeId, activeTab, editingShot, id]);

    const loadProjectData = async () => {
        if (!id) return;
        try {
            const [p, user] = await Promise.all([
                fetchProject(id),
                fetchMe().catch(() => null)
            ]);
            if (p) setProject(p);
            if (user && typeof user.credits === 'number') {
                setCurrentUserCredits(user.credits);
            }
            void loadEpisodesForEditor(p);
        } catch (e) {
            console.error("Failed to load project data", e);
        }
        fetchProjectBillingStats(id).then(stats => {
            if (stats) setProjectBillingStats({ user_cost: stats.user_cost || 0, total_cost: stats.total_cost || 0 });
        }).catch(() => {});
    };

    const evalWorkflowStageTimerRef = useRef(null);

    const refreshProjectBillingStats = useCallback(() => {
        if (!id) return;
        fetchProjectBillingStats(id).then(stats => {
            if (stats) setProjectBillingStats({ user_cost: stats.user_cost || 0, total_cost: stats.total_cost || 0 });
        }).catch(() => {});
    }, [id]);

    const resolveEpisodeOrderNumber = useCallback((episode) => {
        const info = episode?.episode_info && typeof episode.episode_info === 'object' ? episode.episode_info : {};
        const nestedGlobalInfo = info?.e_global_info && typeof info.e_global_info === 'object' ? info.e_global_info : {};
        const candidates = [
            episode?.episode_number,
            info?.episode_number,
            info?.episode_script_episode_number,
            info?.story_dna_episode_number,
            info?.index,
            nestedGlobalInfo?.episode_script_episode_number,
            nestedGlobalInfo?.story_dna_episode_number,
            parseEpisodeNumberFromText(episode?.title),
            episode?.id,
        ];

        for (const candidate of candidates) {
            const parsed = Number(candidate);
            if (Number.isFinite(parsed) && parsed > 0) return parsed;
        }
        return 0;
    }, []);

    const pickMaxEpisodeId = useCallback((eps) => {
        const list = Array.isArray(eps) ? eps : [];
        if (!list.length) return null;

        let best = list[0];
        let bestOrder = resolveEpisodeOrderNumber(best);
        for (let i = 1; i < list.length; i += 1) {
            const candidate = list[i];
            const candidateOrder = resolveEpisodeOrderNumber(candidate);
            if (candidateOrder > bestOrder) {
                best = candidate;
                bestOrder = candidateOrder;
                continue;
            }
            if (candidateOrder === bestOrder) {
                const bestId = Number(best?.id || 0);
                const candidateId = Number(candidate?.id || 0);
                if (candidateId > bestId) best = candidate;
            }
        }
        return best?.id ?? null;
    }, [resolveEpisodeOrderNumber]);

    const sortEpisodesForEditor = useCallback((eps) => {
        return (Array.isArray(eps) ? [...eps] : []).sort((a, b) => {
            const numberDiff = resolveEpisodeOrderNumber(b) - resolveEpisodeOrderNumber(a);
            if (numberDiff !== 0) return numberDiff;
            return String(b?.id || '').localeCompare(String(a?.id || ''), undefined, { numeric: true });
        });
    }, [resolveEpisodeOrderNumber]);

    const DEFERRED_EPISODE_FIELDS = useMemo(() => ([
        'script_content',
        'ai_scene_analysis_result',
        'ai_scene_analysis_scene_markdown',
        'ai_scene_analysis_subject_index',
        'ai_scene_analysis_adaptation',
        'ai_entity_design_result',
        'ai_stage_outputs',
        'character_profiles',
    ]), []);

    const mergeEpisodeListWithCachedFields = useCallback((incomingEps, previousEps, options = {}) => {
        const invalidateSet = new Set(
            (Array.isArray(options.invalidateEpisodeIds) ? options.invalidateEpisodeIds : [])
                .map((episodeId) => String(episodeId))
        );
        const prevById = new Map(
            (Array.isArray(previousEps) ? previousEps : []).map((ep) => [String(ep.id), ep])
        );
        return sortEpisodesForEditor(incomingEps).map((ep) => {
            const previous = prevById.get(String(ep.id));
            if (!previous) return ep;

            const merged = { ...previous, ...ep };
            if (invalidateSet.has(String(ep.id))) {
                delete merged._fullLoaded;
                return merged;
            }
            for (const field of DEFERRED_EPISODE_FIELDS) {
                const incomingValue = ep[field];
                const cachedValue = previous[field];
                if ((incomingValue === undefined || incomingValue === null) && cachedValue != null) {
                    merged[field] = cachedValue;
                }
            }
            if (ep.script_content === undefined && previous._fullLoaded) {
                merged._fullLoaded = previous._fullLoaded;
            }
            return merged;
        });
    }, [DEFERRED_EPISODE_FIELDS, sortEpisodesForEditor]);

    const resolveEpisodeDisplayNumber = useCallback((episode) => {
        const directNumber = Number(episode?.episode_number);
        if (Number.isFinite(directNumber) && directNumber > 0) return directNumber;
        return parseEpisodeNumberFromText(episode?.title);
    }, []);

    const hydrateEpisodesState = useCallback((eps, options = {}) => {
        const normalized = mergeEpisodeListWithCachedFields(eps, episodesRef.current, options);
        episodesRef.current = normalized;
        setEpisodes(normalized);

        if (normalized.length > 0) {
            const pendingRestoreId = pendingInitialEpisodeIdRef.current;
            const currentActiveId = activeEpisodeIdRef.current;
            let nextActiveId = null;
            if (pendingRestoreId != null && normalized.some((ep) => String(ep.id) === String(pendingRestoreId))) {
                nextActiveId = pendingRestoreId;
            } else if (currentActiveId != null && normalized.some((ep) => String(ep.id) === String(currentActiveId))) {
                nextActiveId = currentActiveId;
            } else {
                nextActiveId = pickMaxEpisodeId(normalized);
            }
            pendingInitialEpisodeIdRef.current = null;
            setActiveEpisodeId(nextActiveId);
        } else {
            pendingInitialEpisodeIdRef.current = null;
            setActiveEpisodeId(null);
        }
        return normalized;
    }, [mergeEpisodeListWithCachedFields, pickMaxEpisodeId]);

    const refreshEpisodesForEditor = useCallback(async (options = {}) => {
        if (!id) return [];
        const fresh = await fetchEpisodes(id).catch(() => []);
        return hydrateEpisodesState(fresh, options);
    }, [id, hydrateEpisodesState]);

    const reloadEpisodeIntoState = useCallback(async (episodeId) => {
        const fullEp = await fetchEpisode(episodeId);
        setEpisodes((prev) => sortEpisodesForEditor(
            prev.map((episode) => (
                String(episode.id) === String(episodeId)
                    ? { ...fullEp, _fullLoaded: true }
                    : episode
            ))
        ));
        return fullEp;
    }, [sortEpisodesForEditor]);

    const loadEpisodesForEditor = useCallback(async (projectSnapshot = null) => {
        if (!id) return [];
        if (episodesLoadPromiseRef.current) {
            return episodesLoadPromiseRef.current;
        }

        setIsEpisodesLoading(true);
        const loadPromise = (async () => {
            let eps = await fetchEpisodes(id).catch(() => []);
            if (eps.length === 0 && projectSnapshot) {
                const newEp = await createEpisode(id, { title: "Episode 1" });
                eps = [newEp];
            }
            return hydrateEpisodesState(eps);
        })();

        episodesLoadPromiseRef.current = loadPromise;

        try {
            return await loadPromise;
        } finally {
            episodesLoadPromiseRef.current = null;
            setIsEpisodesLoading(false);
        }
    }, [hydrateEpisodesState, id]);

    useEffect(() => {
        episodesRef.current = episodes;
    }, [episodes]);

    useEffect(() => {
        activeEpisodeIdRef.current = activeEpisodeId;
    }, [activeEpisodeId]);

    useEffect(() => {
        pendingInitialEpisodeIdRef.current = initialEpisodeId;

        const previousProjectId = previousProjectIdRef.current;
        const hasProjectChanged = previousProjectId != null && String(previousProjectId) !== String(id);
        previousProjectIdRef.current = id;

        if (!hasProjectChanged) return;

        episodesRef.current = [];
        setEpisodes([]);
        setActiveEpisodeId(initialEpisodeId ?? null);
    }, [id, initialEpisodeId]);

    useEffect(() => {
        const handler = () => refreshProjectBillingStats();
        window.addEventListener('aistory:generation-complete', handler);
        return () => window.removeEventListener('aistory:generation-complete', handler);
    }, [refreshProjectBillingStats]);

    const checkWorkflowStageDebounced = useCallback((force = false) => {
        if (evalWorkflowStageTimerRef.current) {
            clearTimeout(evalWorkflowStageTimerRef.current);
        }
        if (force) {
            evalProjectWorkflowStage();
        } else {
            evalWorkflowStageTimerRef.current = setTimeout(() => {
                evalProjectWorkflowStage();
            }, 2000); // Debounce API events by 2 seconds
        }
    }, [id]);

    const evalProjectWorkflowStage = async () => {
        if (!id) return;
        try {
            const currentProj = await fetchProject(id);
            const currentStage = currentProj?.global_info?.workflow_stage || 'script';
            let nextStage = 'script';

            const [entities, eps] = await Promise.all([
                fetchEntities(id).catch(() => []),
                fetchEpisodes(id).catch(() => [])
            ]);

            const hasAssets = entities && entities.length > 0;
            let hasScenes = false;
            
            if (eps && eps.length > 0) {
                const ep1Scenes = await fetchScenes(eps[0].id).catch(() => []);
                hasScenes = ep1Scenes && ep1Scenes.length > 0;
            }

            let allAssetsReady = false;
            if (hasAssets) {
                // 如果所有的资产都有对应图片了，就应该进入分镜阶段
                allAssetsReady = entities.every(e => !!e.image_url);
            }

            let allVideosReady = false;
            let hasShots = false;
            if (allAssetsReady && eps && eps.length > 0) {
                let anyActive = false;
                let allVids = true;
                for (const ep of eps) {
                    const epShots = await fetchEpisodeShots(ep.id, { compact: true }).catch(() => []);
                    if (epShots && epShots.length > 0) {
                        hasShots = true;
                        anyActive = true;
                        if (!epShots.every(s => !!s.video_url)) {
                            allVids = false;
                            break;
                        }
                    }
                }
                allVideosReady = anyActive && allVids;
            }

            if (allVideosReady) {
                nextStage = 'montage';
            } else if (hasAssets && allAssetsReady) {
                nextStage = 'shots';
            } else if (hasAssets || hasScenes) {
                nextStage = 'subjects';
            } else {
                nextStage = 'script';
            }

            if (nextStage !== currentStage) {
                console.log(`Advancing project stage in background: ${currentStage} => ${nextStage}`);
                await updateProject(id, {
                    global_info: {
                        ...(currentProj?.global_info || {}),
                        workflow_stage: nextStage
                    }
                });
                setProject(prev => ({
                    ...prev,
                    global_info: {
                        ...(prev?.global_info || {}),
                        workflow_stage: nextStage
                    }
                }));
                // We do not forcefully change activeTab in the background to avoid UI jumps
            }
        } catch (e) {
            console.error("Failed to eval project stage", e);
        }
    };

    useEffect(() => {
        let isStale = false;
        const initEditor = async () => {
            if (!id) return;
            if (!cachedInitialProject) {
                setIsInitializing(true);
            }
            try {
                const [p, user] = await Promise.all([
                    cachedInitialProject
                        ? Promise.resolve(cachedInitialProject)
                        : fetchProject(id).catch(e => { console.error(e); return null; }),
                    fetchMe().catch(() => null)
                ]);
                
                if (isStale) return;
                if (p) setProject(p);
                
                if (user) {
                    setIsSuperuser(!!user?.is_superuser);
                    setCurrentUserId(Number(user?.id || 0) || null);
                    setCurrentUserCredits(typeof user?.credits === 'number' ? user.credits : 0);
                    setUserBatchParallelLimit(normalizeBatchParallelLimit(user?.is_active));
                } else {
                    setIsSuperuser(false);
                    setCurrentUserId(null);
                    setCurrentUserCredits(0);
                    setUserBatchParallelLimit(3);
                }

                // Fire-and-forget billing stats load
                fetchProjectBillingStats(id).then(stats => {
                    if (stats) setProjectBillingStats({ user_cost: stats.user_cost || 0, total_cost: stats.total_cost || 0 });
                }).catch(() => {});

                const currentStage = p?.global_info?.workflow_stage || 'script';
                let startTab = initialActiveTab || 'overview';
                
                if (!initialActiveTab || initialActiveTab === 'overview' || initialActiveTab === 'ep_info') {
                    // Start tab defaults to the currently saved stage without heavy recalculation
                    startTab = currentStage;
                }
                
                if (isStale) return;
                setActiveTab(startTab);

                const loadedEpisodes = await loadEpisodesForEditor(p);
                if (isStale) return;
                if (loadedEpisodes.length > 0) {
                    setActiveEpisodeId((prev) => {
                        if (prev != null && loadedEpisodes.some((ep) => String(ep.id) === String(prev))) {
                            return prev;
                        }
                        return pickMaxEpisodeId(loadedEpisodes);
                    });
                }

            } catch (err) {
                console.error("Initialization error:", err);
            } finally {
                if (!isStale) setIsInitializing(false);
            }
        };

        initEditor();

        const handleStageRefresh = () => checkWorkflowStageDebounced(false);
        window.addEventListener('aistory:workflow_stage_check', handleStageRefresh);
        return () => {
            isStale = true;
            window.removeEventListener('aistory:workflow_stage_check', handleStageRefresh);
        };
    }, [cachedInitialProject, id, initialActiveTab, loadEpisodesForEditor, pickMaxEpisodeId]);

    useEffect(() => {
        if (!EPISODE_REQUIRED_TABS.has(activeTab)) return;
        if (episodes.length > 0 || isEpisodesLoading) return;
        void loadEpisodesForEditor(project);
    }, [activeTab, episodes.length, isEpisodesLoading, loadEpisodesForEditor, project]);

    useEffect(() => {
        try {
            setGlobalUiLang(uiLang);
        } catch (e) {}
    }, [uiLang]);

    useEffect(() => {
        if (hasAppliedInitialShotFocusRef.current) return;
        if (String(initialActiveTab || '') !== 'shots') return;
        if (!initialEditingShotSceneId) return;
        hasAppliedInitialShotFocusRef.current = true;
        setShotsFocusRequest({ sceneId: String(initialEditingShotSceneId), nonce: Date.now() });
    }, [initialActiveTab, initialEditingShotSceneId]);

    const handleUpdateScript = async (epId, content) => {
        try {
            const updatedEp = await updateEpisode(epId, { script_content: content });
            // Verify content length
            if (updatedEp.script_content && updatedEp.script_content.length !== content.length) {
                console.warn("Warning: Saved content length differs from local content.");
            }
            // Update local state to reflect content change
            setEpisodes(prev => prev.map(e => e.id === epId ? { ...e, script_content: content } : e));
            return updatedEp;
        } catch (e) {
            console.error("Update Script Failed in Parent:", e);
            throw e;
        }
    };

    const handleUpdateEpisodeInfo = async (epId, data) => {
        try {
            const updatedEp = await updateEpisode(epId, data);
            setEpisodes(prev => sortEpisodesForEditor(prev.map(e => e.id === epId ? updatedEp : e)));
            return updatedEp;
        } catch (e) {
            console.error("Episode Info Update Failed:", e);
            throw e;
        }
    };

    const handleCreateEpisode = async () => {
        const title = await promptUiMessage("Enter Episode Title (e.g., Episode 2):", {
            title: 'Create Episode',
            confirmText: 'Create',
            cancelText: 'Cancel',
            placeholder: 'Episode 2',
        });
        if (!title) return;
        try {
            const newEp = await createEpisode(id, { title });
            await refreshEpisodesForEditor();
            setActiveEpisodeId(newEp.id);
            setIsEpisodeMenuOpen(false);
        } catch (e) {
            console.error(e);
        }
    };

    const handleDeleteEpisode = async (e, epId) => {
        e.stopPropagation();
        if (!await confirmUiMessage("Delete this episode? It will be marked as deleted and hidden from the list; data will remain in the database.")) return;
         try {
            await deleteEpisode(epId);
            const remaining = sortEpisodesForEditor(episodes.filter(ep => ep.id !== epId));
            episodesRef.current = remaining;
            setEpisodes(remaining);
            if (activeEpisodeId === epId) {
                setActiveEpisodeId(remaining.length > 0 ? pickMaxEpisodeId(remaining) : null);
            }
        } catch (err) {
            console.error(err);
        }
    };

    // Helper to repair common JSON syntax errors like unquoted strings
    function repairJSON(jsonStr) {
        try {
            return JSON.parse(jsonStr);
        } catch (e) {
            // Regex to match "key": value where value is unquoted
            // 1. "([^"]+)" matches key
            // 2. \s*:\s* matches colon
            // 3. ([^\s"{\[][\s\S]*?) matches value starting with non-quote/brace/bracket
            // 4. (?=\s*[,}\]]) lookahead for end of value (comma or brace/bracket)
            let repaired = jsonStr.replace(
                /"([^"]+)"\s*:\s*([^\s"{\[][\s\S]*?)(?=\s*[,}\]])/g, 
                (match, key, value) => {
                    const trimmedValue = value.trim();
                    if (!trimmedValue) return match;
                    
                    // Allow valid JSON primitives (numbers, bools, null)
                    if (/^(true|false|null)$/.test(trimmedValue)) return match;
                    if (!isNaN(parseFloat(trimmedValue)) && isFinite(trimmedValue)) return match;
                    
                    // Quote the string, escaping quotes and newlines
                    const safeValue = trimmedValue
                        .replace(/\\/g, '\\\\') // Escape backslashes first
                        .replace(/"/g, '\\"')
                        .replace(/\n/g, '\\n')
                        .replace(/\r/g, '');
                    return `"${key}": "${safeValue}"`;
                }
            );
            
            // Fix trailing commas
            repaired = repaired.replace(/,\s*([}\]])/g, '$1');

            try {
                return JSON.parse(repaired);
            } catch {
                return null;
            }
        }
    }

    // Helper to extract multiple JSON blocks from mixed text
    const extractJSONBlocks = (text) => {
        const results = [];
        let braceCount = 0;
        let startIndex = -1;
        
        let i = 0;
        while (i < text.length) {
            const char = text[i];
            
            // Skip strings to avoid counting braces inside them
            if (char === '"') {
                i++;
                while (i < text.length) {
                    if (text[i] === '"' && text[i-1] !== '\\') break;
                    // Remove the break on newline so that JSON with physical newlines can be extracted
                    i++;
                }
            } else if (char === '{') {
                if (braceCount === 0) startIndex = i;
                braceCount++;
            } else if (char === '}') {
                braceCount--;
                if (braceCount === 0 && startIndex !== -1) {
                    const jsonStr = text.substring(startIndex, i + 1);
                    try {
                        const obj = repairJSON(jsonStr);
                        if (obj && typeof obj === 'object') {
                            results.push(obj);
                        }
                    } catch (e) {
                        // keep import flow resilient: skip invalid blocks silently
                        // Optional: Could try to fuzzy find the end if brace counting was off
                    }
                    startIndex = -1;
                }
            }
            i++;
        }
        return results;
    }

    const collectImportJsonCandidates = (inputText) => {
        const raw = String(inputText || '');
        const candidates = [];

        const pushCandidate = (value) => {
            if (value == null) return;
            if (typeof value === 'object') {
                candidates.push(value);
                return;
            }
            const text = String(value || '').trim();
            if (!text) return;
            try {
                const parsed = JSON.parse(text);
                if (parsed && typeof parsed === 'object') candidates.push(parsed);
                return;
            } catch (_) {}
            const repaired = repairJSON(text);
            if (repaired && typeof repaired === 'object') {
                candidates.push(repaired);
            }
        };

        const fenceJsonRe = /```json\s*([\s\S]*?)```/gi;
        let match;
        while ((match = fenceJsonRe.exec(raw)) !== null) {
            pushCandidate(match[1]);
        }

        const fenceRe = /```\s*([\s\S]*?)```/gi;
        while ((match = fenceRe.exec(raw)) !== null) {
            const block = String(match[1] || '').trim();
            if (block.startsWith('{') || block.startsWith('[')) {
                pushCandidate(block);
            }
        }

        const trimmed = raw.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            pushCandidate(trimmed);
        }

        for (const obj of extractJSONBlocks(raw)) {
            pushCandidate(obj);
        }

        const deduped = [];
        const seen = new Set();
        for (const item of candidates) {
            try {
                const key = JSON.stringify(item);
                if (seen.has(key)) continue;
                seen.add(key);
                deduped.push(item);
            } catch (_) {
                deduped.push(item);
            }
        }
        return deduped;
    };

    // Project-level import helpers (local to Editor scope)
    const getEntitiesPayloadFromJsonText = (jsonText) => {
        const blocks = collectImportJsonCandidates(jsonText);

        const normalizeKey = (key) => String(key || '').toLowerCase().replace(/[\s_\-]/g, '');
        const keyHasKeyword = (key, keywords) => {
            const nk = normalizeKey(key);
            return (keywords || []).some((kw) => nk.includes(normalizeKey(kw)));
        };

        const deepFindArrayByKeywords = (root, keywords) => {
            const queue = [root];
            const seen = new WeakSet();

            while (queue.length > 0) {
                const cur = queue.shift();
                if (!cur || typeof cur !== 'object') continue;
                if (seen.has(cur)) continue;
                seen.add(cur);

                if (Array.isArray(cur)) {
                    for (const item of cur) {
                        if (item && typeof item === 'object') queue.push(item);
                    }
                    continue;
                }

                for (const [k, v] of Object.entries(cur)) {
                    if (Array.isArray(v) && keyHasKeyword(k, keywords)) return v;
                    if (v && typeof v === 'object') queue.push(v);
                }
            }
            return [];
        };
        const splitByTypeFromArray = (arr) => {
            const payload = { characters: [], props: [], environments: [], posters: [] };
            const toType = (value) => normalizeKey(value);
            for (const item of (arr || [])) {
                if (!item || typeof item !== 'object') continue;
                const type = toType(item.type || item.subject_type || item.entity_type || '');
                if (['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(type)) {
                    payload.characters.push(item);
                } else if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(type)) {
                    payload.props.push(item);
                } else if (['environment', 'environments', 'env', 'scene', '场景', '环境'].includes(type)) {
                    payload.environments.push(item);
                } else if (['poster', 'posters', 'cover', 'covers', '海报', '封面'].includes(type)) {
                    payload.posters.push(item);
                }
            }
            return payload;
        };

        const mergePayload = (base, patch) => {
            const out = base || { characters: [], props: [], environments: [], posters: [] };
            const appendUnique = (target, incoming) => {
                const seen = new Set(target.map((x) => JSON.stringify(x || {})));
                for (const item of (incoming || [])) {
                    const key = JSON.stringify(item || {});
                    if (seen.has(key)) continue;
                    seen.add(key);
                    target.push(item);
                }
            };
            appendUnique(out.characters, Array.isArray(patch?.characters) ? patch.characters : []);
            appendUnique(out.props, Array.isArray(patch?.props) ? patch.props : []);
            appendUnique(out.environments, Array.isArray(patch?.environments) ? patch.environments : []);
            appendUnique(out.posters, Array.isArray(patch?.posters) ? patch.posters : []);
            return out;
        };

        const pick = (obj, aliases) => {
            const aliasSet = new Set((aliases || []).map(normalizeKey));
            for (const [k, v] of Object.entries(obj || {})) {
                if (Array.isArray(v) && aliasSet.has(normalizeKey(k))) return v;
            }
            return [];
        };

        const normalizePayloadFromObject = (obj) => {
            if (!obj || typeof obj !== 'object') return null;

            const characters = pick(obj, ['characters', 'character', 'chars', 'roles', 'people', '人物', '角色']);
            const props = pick(obj, ['props', 'prop', 'items', '道具', '物件']);
            const environments = pick(obj, ['environments', 'environment', 'env', 'scenes', '场景', '环境']);
            const posters = pick(obj, ['poster', 'posters', 'cover', 'covers', '海报', '封面']);
            if (characters.length || props.length || environments.length || posters.length) {
                return { characters, props, environments, posters };
            }

            const byKeywordCharacters = deepFindArrayByKeywords(obj, ['character', 'role', 'cast', '角色', '人物']);
            const byKeywordProps = deepFindArrayByKeywords(obj, ['prop', 'item', 'object', '道具', '物件']);
            const byKeywordEnvironments = deepFindArrayByKeywords(obj, ['environment', 'scene', 'location', '场景', '环境']);
            const byKeywordPosters = deepFindArrayByKeywords(obj, ['poster', 'cover', '海报', '封面']);
            if (byKeywordCharacters.length || byKeywordProps.length || byKeywordEnvironments.length || byKeywordPosters.length) {
                return {
                    characters: byKeywordCharacters,
                    props: byKeywordProps,
                    environments: byKeywordEnvironments,
                    posters: byKeywordPosters,
                };
            }

            // Wrappers using one mixed entities array (e.g. subjects/entities with subject_type).
            const entityArray = pick(obj, ['entities', 'entity', 'subjectlist']);
            if (entityArray.length) {
                const split = splitByTypeFromArray(entityArray);
                if (split.characters.length || split.props.length || split.environments.length || split.posters.length) {
                    return split;
                }
            }

            // Part-labeled keys often produced by markdown sections (Part2A/B/C).
            const partA = pick(obj, ['part2a', 'part2acharacters', 'charactersjson', 'characterjson']);
            const partB = pick(obj, ['part2b', 'part2bprops', 'propsjson', 'propjson']);
            const partC = pick(obj, ['part2c', 'part2cenvironments', 'environmentsjson', 'environmentjson']);
            const partD = pick(obj, ['part2d', 'part2dposters', 'postersjson', 'posterjson']);
            if (partA.length || partB.length || partC.length || partD.length) {
                return { characters: partA, props: partB, environments: partC, posters: partD };
            }

            const nested = obj.entities || obj.entity || obj.subjects || obj.subject || obj.data || obj.payload || obj.result;
            if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
                return normalizePayloadFromObject(nested);
            }
            return null;
        };

        let mergedPayload = { characters: [], props: [], environments: [], posters: [] };
        for (const obj of blocks) {
            if (Array.isArray(obj)) {
                mergedPayload = mergePayload(mergedPayload, splitByTypeFromArray(obj));
                continue;
            }
            const payload = normalizePayloadFromObject(obj);
            if (payload) {
                mergedPayload = mergePayload(mergedPayload, payload);
            }
        }
        if (mergedPayload.characters.length || mergedPayload.props.length || mergedPayload.environments.length || mergedPayload.posters.length) {
            return mergedPayload;
        }
        return null;
    };

    const getGlobalInfoPayloadFromJsonText = (jsonText) => {
        const blocks = collectImportJsonCandidates(jsonText);
        const normalizeKey = (key) => String(key || '').toLowerCase().replace(/[\s_\-]/g, '');
        const keyHasKeyword = (key, keywords) => {
            const nk = normalizeKey(key);
            return (keywords || []).some((kw) => nk.includes(normalizeKey(kw)));
        };

        const findNestedObjectByKeywords = (root, keywords) => {
            const queue = [root];
            const seen = new WeakSet();

            while (queue.length > 0) {
                const cur = queue.shift();
                if (!cur || typeof cur !== 'object' || Array.isArray(cur)) continue;
                if (seen.has(cur)) continue;
                seen.add(cur);

                for (const [k, v] of Object.entries(cur)) {
                    if (v && typeof v === 'object' && !Array.isArray(v) && keyHasKeyword(k, keywords)) {
                        return v;
                    }
                    if (v && typeof v === 'object') queue.push(v);
                }
            }
            return null;
        };

        const pickValue = (obj, aliases) => {
            if (!obj || typeof obj !== 'object') return undefined;
            const aliasSet = new Set((aliases || []).map(normalizeKey));
            for (const [k, v] of Object.entries(obj)) {
                if (aliasSet.has(normalizeKey(k))) return v;
            }
            return undefined;
        };

        const toText = (value) => String(value == null ? '' : value).trim();
        const toStringArray = (value) => {
            if (Array.isArray(value)) {
                return Array.from(new Set(value.map(v => String(v || '').trim()).filter(Boolean)));
            }
            const text = String(value || '').trim();
            if (!text) return [];
            return Array.from(new Set(text.split(/[\n,，;；]/).map(v => v.trim()).filter(Boolean)));
        };

        for (const obj of blocks) {
            if (!obj || typeof obj !== 'object' || Array.isArray(obj)) continue;

            const candidate =
                (obj.global_info && typeof obj.global_info === 'object' && obj.global_info)
                || (obj.project_global_info && typeof obj.project_global_info === 'object' && obj.project_global_info)
                || findNestedObjectByKeywords(obj, ['globalinfo', 'projectinfo', '项目信息']);

            const base = candidate || obj;

            const toneRaw = pickValue(base, ['tone', '色调', 'mood']);
            const lightingRaw = pickValue(base, ['lighting', '灯光', 'light']);
            const payloadRaw = {
                script_title: toText(pickValue(base, ['script_title', 'title', '项目标题'])),
                expected_duration: toText(pickValue(base, ['expected_duration', '预期时长(秒)', '预期时长'])) || "",
                type: toText(pickValue(base, ['type', 'project_type', '类型'])),
                language: toText(pickValue(base, ['language', 'lang', '语言'])),
                base_positioning: toText(pickValue(base, ['base_positioning', 'positioning', '定位'])),
                notes: toText(pickValue(base, ['notes', 'note', '备注'])),      
                Global_Style: toText(pickValue(base, ['global_style', 'Global_Style', 'style', '风格'])),
                borrowed_films: toStringArray(pickValue(base, ['borrowed_films', 'reference_films', '参考影片'])),
                borrowed_films_note: toText(pickValue(base, ['borrowed_films_note', 'reference_films_note', '参考影片备注'])),
                tone: toneRaw ? toText(toneRaw) : '',
                lighting: lightingRaw ? toText(lightingRaw) : '',
                plot_summary: toText(pickValue(base, ['plot_summary', 'story_summary', '剧情总结'])),
                music_recommendation: toText(pickValue(base, ['music_recommendation', 'score_recommendation', '配乐推荐'])),
            };

            const payload = {};
            let hasData = false;
            for (const [k, v] of Object.entries(payloadRaw)) {
                if (k === 'borrowed_films') {
                    if (Array.isArray(v) && v.length > 0) {
                        payload[k] = v;
                        hasData = true;
                    }
                } else if (String(v || '').trim().length > 0) {
                    payload[k] = v;
                    hasData = true;
                }
            }

            if (hasData) return { global_info: payload };
        }

        return null;
    };

    const getProjectVisualBackfillFromJsonText = (jsonText) => {
        const blocks = collectImportJsonCandidates(jsonText);

        const normalizeKey = (key) => String(key || '').toLowerCase().replace(/[\s_\-]/g, '');
        const toNonEmptyString = (value) => {
            const text = String(value == null ? '' : value).trim();
            return text.length > 0 ? text : '';
        };
        const toStringArray = (value) => {
            if (Array.isArray(value)) {
                return Array.from(new Set(value.map(v => String(v || '').trim()).filter(Boolean)));
            }
            const text = String(value || '').trim();
            if (!text) return [];
            return Array.from(new Set(text.split(/[\n,，;；]/).map(v => v.trim()).filter(Boolean)));
        };

        const findValueByAliases = (obj, aliases) => {
            if (!obj || typeof obj !== 'object') return undefined;
            const aliasSet = new Set((aliases || []).map(normalizeKey));
            for (const [k, v] of Object.entries(obj)) {
                if (aliasSet.has(normalizeKey(k))) return v;
            }
            return undefined;
        };

        const candidateObjects = [];
        for (const obj of blocks) {
            if (!obj || typeof obj !== 'object' || Array.isArray(obj)) continue;
            candidateObjects.push(obj);
            if (obj.global_info && typeof obj.global_info === 'object') candidateObjects.push(obj.global_info);
            if (obj.project_global_info && typeof obj.project_global_info === 'object') candidateObjects.push(obj.project_global_info);
            if (obj.project_style_backfill && typeof obj.project_style_backfill === 'object') candidateObjects.push(obj.project_style_backfill);
            if (obj.project_visual_backfill && typeof obj.project_visual_backfill === 'object') candidateObjects.push(obj.project_visual_backfill);
        }

        for (const obj of candidateObjects) {
            const globalStyleRaw = findValueByAliases(obj, ['Global_Style', 'global_style', 'style', 'project_style']);
            const borrowedFilmsRaw = findValueByAliases(obj, ['borrowed_films', 'borrowedFilms', 'reference_films', 'referenceFilms']);
            const borrowedFilmsNoteRaw = findValueByAliases(obj, ['borrowed_films_note', 'borrowedFilmsNote', 'reference_films_note', 'referenceFilmsNote']);
            const toneRaw = findValueByAliases(obj, ['tone', 'mood']);
            const lightingRaw = findValueByAliases(obj, ['lighting', 'light']);
            const plotSummaryRaw = findValueByAliases(obj, ['plot_summary', 'plotSummary', 'story_summary', 'storySummary', '剧情总结']);
            const musicRecommendationRaw = findValueByAliases(obj, ['music_recommendation', 'musicRecommendation', 'score_recommendation', 'scoreRecommendation', '配乐推荐']);

            const payload = {
                Global_Style: toNonEmptyString(globalStyleRaw),
                borrowed_films: toStringArray(borrowedFilmsRaw),
                borrowed_films_note: toNonEmptyString(borrowedFilmsNoteRaw),
                tone: toNonEmptyString(toneRaw),
                lighting: toNonEmptyString(lightingRaw),
                plot_summary: toNonEmptyString(plotSummaryRaw),
                music_recommendation: toNonEmptyString(musicRecommendationRaw),
            };

            if (payload.Global_Style || payload.borrowed_films.length > 0 || payload.borrowed_films_note || payload.tone || payload.lighting || payload.plot_summary || payload.music_recommendation) {
                return payload;
            }
        }

        return null;
    };

    const extractFinalConsistencyReport = (text) => {
        const raw = String(text || '');
        if (!raw.trim()) return null;

        const lines = raw.split('\n').map(line => String(line || '').trim());
        const report = {};
        let inReportTable = false;

        const normalizeType = (value) => {
            const key = String(value || '').trim().toLowerCase();
            if (!key) return '';
            if (key.includes('character')) return 'character';
            if (key.includes('prop')) return 'prop';
            if (key.includes('environment')) return 'environment';
            return '';
        };

        const toInt = (value) => {
            const n = Number(String(value || '').trim());
            return Number.isFinite(n) ? n : null;
        };

        for (const line of lines) {
            if (!inReportTable && /final\s+consistency\s+report/i.test(line)) {
                inReportTable = true;
                continue;
            }

            if (!inReportTable) continue;
            if (!line.startsWith('|') || !line.includes('|')) continue;

            let cols = line.split('|').map(v => String(v || '').trim());
            if (cols.length > 0 && cols[0] === '') cols.shift();
            if (cols.length > 0 && cols[cols.length - 1] === '') cols.pop();
            if (cols.length < 5) continue;

            const firstCol = String(cols[0] || '').toLowerCase();
            if (firstCol.includes('subject_type') || /^:?-{3,}:?$/.test(firstCol) || firstCol.includes('---')) continue;

            const type = normalizeType(cols[0]);
            if (!type) continue;

            report[type] = {
                subject_index_count: toInt(cols[1]),
                json_count: toInt(cols[2]),
                is_consistent: /true|yes|是/i.test(String(cols[3] || '').trim()),
                difference_note: String(cols[4] || '').trim(),
            };
        }

        return Object.keys(report).length > 0 ? report : null;
    };

        const getEntitiesPayloadFromSubjectIndexTable = (text) => {
        const raw = String(text || '');
        if (!raw.trim()) return null;

        const sectionMatch = raw.match(/###\s*Subject\s*Index[\s\S]*?(?=\n###\s+|$)/i);
        const section = sectionMatch ? sectionMatch[0] : raw;
        const lines = section
            .split('\n')
            .map(line => String(line || '').trim())
            .filter(line => line.startsWith('|') && line.includes('|'));

        if (lines.length >= 3) {
            const cleanCells = (line) => {
                const cols = line.split('|').map(c => c.trim());
                if (cols.length > 0 && cols[0] === '') cols.shift();
                if (cols.length > 0 && cols[cols.length - 1] === '') cols.pop();
                return cols;
            };
            const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_\-()（）]/g, '');
            const isSeparator = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);

            const headers = cleanCells(lines[0]);
            if (headers.length > 0 && isSeparator(lines[1])) {
                const headerMap = {};
                headers.forEach((h, idx) => { headerMap[normalizeHeader(h)] = idx; });

                const findHeaderIdx = (aliases) => {
                    for (const alias of aliases) {
                        if (headerMap[alias] !== undefined) return headerMap[alias];
                    }
                    return -1;
                };

                const typeIdx = findHeaderIdx(['subjecttype', 'type', '实体类型']);
                const nameIdx = findHeaderIdx(['subjectnameexact', 'subjectname', 'name', '名称']);
                if (typeIdx >= 0 && nameIdx >= 0) {
                    const payload = { characters: [], props: [], environments: [] };
                    const seen = new Set();
                    const toType = (value) => {
                        const token = String(value || '').trim().toLowerCase();
                        if (!token) return '';
                        if (token.includes('character') || token.includes('角色') || token.includes('人物') || token.includes('char')) return 'character';
                        if (token.includes('prop') || token.includes('道具') || token.includes('item')) return 'prop';
                        if (token.includes('environment') || token.includes('场景') || token.includes('环境') || token.includes('env')) return 'environment';
                        return '';
                    };

                    for (let i = 2; i < lines.length; i++) {
                        const line = lines[i];
                        if (isSeparator(line)) continue;
                        const cells = cleanCells(line);
                        if (cells.length <= Math.max(typeIdx, nameIdx)) continue;

                        const type = toType(cells[typeIdx]);
                        const subjectName = String(cells[nameIdx] || '').trim();
                        if (!type || !subjectName) continue;

                        const dedupKey = `${type}:${normalizeEntityToken(subjectName)}`;
                        if (seen.has(dedupKey)) continue;
                        seen.add(dedupKey);

                        const item = {
                            name: subjectName,
                            name_en: '',
                            subject_name_exact: subjectName,
                            anchor_description: '',
                        };
                        if (type === 'character') payload.characters.push(item);
                        else if (type === 'prop') payload.props.push(item);
                        else if (type === 'environment') payload.environments.push(item);
                    }

                    if (payload.characters.length || payload.props.length || payload.environments.length) {
                        return payload;
                    }
                }
            }
        }
// Fallback: generic key-value rows (with or without backticks, with or without numbered list)
        const payload = { characters: [], props: [], environments: [] };        
        const seen = new Set();
        
        const fallbackLines = section.split('\n')
            .map(line => String(line || '').trim().replace(/`/g, ''))
            .filter(line => /subject_type\s*=/i.test(line) && /subject_name_(exact|zh|en)\s*=/i.test(line));

        for (const line of fallbackLines) {
            const typeMatch = line.match(/subject_type\s*=\s*([^|\n]+)/i);     
            const nameMatch = line.match(/subject_name_(?:exact|zh|en)\s*=\s*([^|\n]+)/i);
            const anchorMatch = line.match(/entity_attributes\s*=\s*([^|\n]+)/i) || line.match(/attributes\s*=\s*([^|\n]+)/i) || line.match(/entity_traits\s*=\s*([^|\n]+)/i);
            
            const typeToken = String(typeMatch?.[1] || '').trim().toLowerCase();
            let subjectName = String(nameMatch?.[1] || '').trim();
            // remove CHAR: / PROP: prefixes
            subjectName = subjectName.replace(/^(CHAR|PROP|ENV|VEFX|SFX)\s*:\s*/i, '').trim();
            
            if (!typeToken || !subjectName) continue;

            let type = '';
            if (typeToken.includes('character') || typeToken.includes('角色') || typeToken.includes('人物') || typeToken.includes('char')) type = 'character';  
            else if (typeToken.includes('prop') || typeToken.includes('道具') || typeToken.includes('item') || typeToken.includes('vefx') || typeToken.includes('sfx') || typeToken.includes('特效')) type = 'prop';
            else if (typeToken.includes('environment') || typeToken.includes('场景') || typeToken.includes('环境') || typeToken.includes('env')) type = 'environment';
            if (!type) continue;

            const dedupKey = `${type}:${normalizeEntityToken(subjectName)}`;
            if (seen.has(dedupKey)) continue;
            seen.add(dedupKey);

            const item = {
                name: subjectName,
                name_en: '',
                subject_name_exact: subjectName,
                anchor_description: String(anchorMatch?.[1] || '').trim(),
            };
            if (type === 'character') payload.characters.push(item);
            else if (type === 'prop') payload.props.push(item);
            else if (type === 'environment') payload.environments.push(item);
        }

        if (payload.characters.length || payload.props.length || payload.environments.length) return payload;
        return null;
    };

    const getSubjectIndexTableRowCount = (text) => {
        const raw = String(text || '');
        if (!raw.trim()) return 0;

        const sectionMatch = raw.match(/###\s*Subject\s*Index[\s\S]*?(?=\n###\s+|$)/i);
        const section = sectionMatch ? sectionMatch[0] : raw;
        const lines = section
            .split('\n')
            .map(line => String(line || '').trim())
            .filter(line => line.startsWith('|') && line.includes('|'));

        if (lines.length >= 3) {
            const isSeparator = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);
            let count = 0;
            for (let i = 2; i < lines.length; i++) {
                if (!isSeparator(lines[i])) count += 1;
            }
            if (count > 0) return count;
        }

        // Fallback count for generic key-value line style.
        const fallbackLines = section.split('\n')
            .map(line => String(line || '').trim().replace(/`/g, ''))
            .filter(line => /subject_type\s*=/i.test(line) && /subject_name_(exact|zh|en)\s*=/i.test(line));
        return fallbackLines.length;
    };

    const shouldForceAutoImportForAnalysisBundle = (text) => {
        const raw = String(text || '');
        if (!raw.trim()) return false;

        // Typical full scene-analysis bundle includes scene table + entities section markers.
        const hasPart1 = /###\s*Part\s*1\s*:\s*Scenes\s*Table/i.test(raw);
        const hasPart2 = /###\s*Part\s*2\s*:\s*Entities\s*JSON/i.test(raw);
        const hasSubjectIndex = /###\s*Subject\s*Index/i.test(raw);
        const hasSceneHeader = raw.includes('Scene No') || raw.includes('场次序号') || raw.includes('Scene ID');
        return (hasPart1 && hasPart2) || (hasPart1 && hasSubjectIndex) || (hasSceneHeader && (hasPart2 || hasSubjectIndex));
    };

    // Extract a named JSON array fragment from mixed text, e.g. "characters": [ ... ]
    const extractNamedJsonArrayFromRawText = (inputText, keyName) => {
        const raw = String(inputText || '');
        const key = String(keyName || '').trim();
        if (!raw || !key) return [];

        const keyRe = new RegExp(`"${key}"\\s*:\\s*\\[`, 'i');
        const keyMatch = keyRe.exec(raw);
        if (!keyMatch) return [];

        const startBracketIdx = raw.indexOf('[', keyMatch.index);
        if (startBracketIdx < 0) return [];

        let depth = 0;
        let inString = false;
        let escape = false;
        let endBracketIdx = -1;
        for (let i = startBracketIdx; i < raw.length; i++) {
            const ch = raw[i];
            if (inString) {
                if (escape) {
                    escape = false;
                    continue;
                }
                if (ch === '\\') {
                    escape = true;
                    continue;
                }
                if (ch === '"') {
                    inString = false;
                }
                continue;
            }

            if (ch === '"') {
                inString = true;
                continue;
            }
            if (ch === '[') depth += 1;
            if (ch === ']') {
                depth -= 1;
                if (depth === 0) {
                    endBracketIdx = i;
                    break;
                }
            }
        }

        if (endBracketIdx < 0) return [];
        const arrText = raw.slice(startBracketIdx, endBracketIdx + 1);
        try {
            const parsed = JSON.parse(arrText);
            return Array.isArray(parsed) ? parsed : [];
        } catch (_) {
            const repaired = repairJSON(arrText);
            return Array.isArray(repaired) ? repaired : [];
        }
    };

    const getMergedEntitiesPayloadFromText = (inputText) => {
        const text = String(inputText || '');
        const emptyPayload = { characters: [], props: [], environments: [], posters: [] };

        const normalizeName = (item) => {
            const rawName = String(
                item?.name || item?.subject_name_exact || item?.subject_name || item?.name_en || item?.name_zh || ''
            ).trim();
            if (!rawName) return '';

            const normalized = normalizeEntityToken(
                rawName
                    .replace(/^CHAR\s*:\s*/i, '')
                    .replace(/^PROP\s*:\s*/i, '')
                    .replace(/^ENV\s*:\s*/i, '')
            );
            return String(normalized || '').replace(/[^\p{L}\p{N}\u4e00-\u9fff]/gu, '');
        };

        const hasAny = (payload) =>
            (Array.isArray(payload?.characters) && payload.characters.length > 0)
            || (Array.isArray(payload?.props) && payload.props.length > 0)
            || (Array.isArray(payload?.environments) && payload.environments.length > 0)
            || (Array.isArray(payload?.posters) && payload.posters.length > 0);

        const mergePayload = (base, patch, onlyMissingTypes = false) => {
            const out = {
                characters: Array.isArray(base?.characters) ? [...base.characters] : [],
                props: Array.isArray(base?.props) ? [...base.props] : [],
                environments: Array.isArray(base?.environments) ? [...base.environments] : [],
                posters: Array.isArray(base?.posters) ? [...base.posters] : [],
            };

            const mergeList = (target, incoming) => {
                const seen = new Set(target.map((x) => normalizeName(x) || JSON.stringify(x || {})));
                for (const item of (incoming || [])) {
                    const key = normalizeName(item) || JSON.stringify(item || {});
                    if (seen.has(key)) continue;
                    seen.add(key);
                    target.push(item);
                }
            };

            if (!onlyMissingTypes || out.characters.length === 0) {
                mergeList(out.characters, Array.isArray(patch?.characters) ? patch.characters : []);
            }
            if (!onlyMissingTypes || out.props.length === 0) {
                mergeList(out.props, Array.isArray(patch?.props) ? patch.props : []);
            }
            if (!onlyMissingTypes || out.environments.length === 0) {
                mergeList(out.environments, Array.isArray(patch?.environments) ? patch.environments : []);
            }
            if (!onlyMissingTypes || out.posters.length === 0) {
                mergeList(out.posters, Array.isArray(patch?.posters) ? patch.posters : []);
            }
            return out;
        };

        let merged = { ...emptyPayload };
        const sources = [];

        const parsedPayload = getEntitiesPayloadFromJsonText(text);
        if (hasAny(parsedPayload)) {
            merged = mergePayload(merged, parsedPayload);
            sources.push('entities_json');
        }

        const fragmentPayload = {
            characters: extractNamedJsonArrayFromRawText(text, 'characters'),
            props: extractNamedJsonArrayFromRawText(text, 'props'),
            environments: extractNamedJsonArrayFromRawText(text, 'environments'),
            posters: extractNamedJsonArrayFromRawText(text, 'posters'),
        };
        if (hasAny(fragmentPayload)) {
            merged = mergePayload(merged, fragmentPayload);
            sources.push('json_key_fragments');
        }

        // Feature change: By removing the `getEntitiesPayloadFromSubjectIndexTable` fallback, 
        // we explicitly block Phase 1 Markdown Subject Index tables from being imported 
        // as empty assets (e.g. without proper descriptions or JSON structures).
        // This ensures asset generation ONLY happens from valid JSON produced in Phase 2.

        if (!hasAny(merged)) return null;
        return {
            payload: merged,
            source: sources.join('+') || 'unknown',
        };
    };

    const handleImport = async (text, importType = 'auto', importOptions = {}) => {
        text = (typeof text === 'string') ? text : String(text || '');
        const requestedImportType = String(importType || 'auto');
        const effectiveImportType = shouldForceAutoImportForAnalysisBundle(text) ? 'auto' : requestedImportType;
        const autoSupplementSceneSubjects = Boolean(importOptions?.autoSupplementSceneSubjects);
        const suppressAlerts = Boolean(importOptions?.suppressAlerts);
        const skipDbVerify = Boolean(importOptions?.skipDbVerify) || suppressAlerts;
        const replaceExistingScenes = Boolean(importOptions?.replaceExistingScenes);
        // Allow modal loading state to paint before heavy parsing/import logic starts.
        await new Promise(resolve => setTimeout(resolve, 0));
        addLog(`Starting Import Analysis (${effectiveImportType})...`, "process");
        if (requestedImportType !== effectiveImportType) {
            addLog(
                `Detected full analysis bundle; normalized import type from '${requestedImportType}' to '${effectiveImportType}' to match auto-import pipeline.`,
                'info'
            );
        }

        const importedSubjectCounts = { character: 0, prop: 0, environment: 0, poster: 0 };
        const createdSubjectItems = [];
        const skippedSubjectItems = [];
        const normalizeImportTargetType = (value) => {
            const key = String(value || '').trim().toLowerCase();
            if (!key) return '';
            if (['character', 'characters', 'role', 'roles', '人物', '角色'].includes(key)) return 'characters';
            if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(key)) return 'props';
            if (['environment', 'environments', 'env', 'scene', 'scenes', '场景', '环境'].includes(key)) return 'environments';
            if (['poster', 'posters', 'cover', 'covers', 'cover_poster', '海报', '封面'].includes(key)) return key === 'covers' ? 'covers' : 'posters';
            return key;
        };
        const targetTypeFilters = Array.isArray(importOptions?.targetEntityTypes)
            ? Array.from(new Set(importOptions.targetEntityTypes.map(normalizeImportTargetType).filter(Boolean)))
            : null;
        const shouldOverwriteExistingSubjects = Boolean(importOptions?.overwriteExistingSubjects);
        const isPosterOnlyImport = Boolean(
            targetTypeFilters
            && targetTypeFilters.length > 0
            && targetTypeFilters.every((item) => item === 'posters' || item === 'covers')
        );
        const shouldOverwritePoster = shouldOverwriteExistingSubjects || isPosterOnlyImport;
        const importStats = {
            scriptLines: 0,
            scenesCreated: 0,
            scenesUpdated: 0,
            shotsCreated: 0,
            jsonBlocks: 0,
            genericJsonBlocks: 0,
        };
        const importDiagnostics = {
            entitiesPayloadSource: 'none',
            subjectIndexTableRows: 0,
            subjectIndexExtracted: 0,
            markers: { script: false, scene: false, shot: false },
            importMode: { requested: requestedImportType, effective: effectiveImportType },
        };
        let sceneSubjectAutoSupplementReport = {
            createdItems: [],
            skippedItems: [],
            failedItems: [],
            sceneReports: [],
            countsByType: { character: 0, prop: 0, environment: 0 },
            entities: [],
        };
        const importedSceneRows = [];
        const createdSceneIds = [];
        let dbPersistedCounts = null;
        let dbRunInsertedCounts = null;
        let postImportStatusNote = '';
        const llmFinalReport = extractFinalConsistencyReport(text);
        const projectVisualBackfill = getProjectVisualBackfillFromJsonText(text);
        
        // --- 1. JSON Processing (Only if 'auto' or 'json') ---
        // For project-level import, prefer targeted extraction to avoid UI stalls on huge mixed text.
        const jsonBlocks = [];
        if (effectiveImportType === 'auto' || effectiveImportType === 'json') {
            importDiagnostics.subjectIndexTableRows = getSubjectIndexTableRowCount(text);

            const filterSubjectsByTargetTypes = (payload) => {
                if (!payload || typeof payload !== 'object' || !targetTypeFilters || targetTypeFilters.length === 0) {
                    return payload;
                }
                const filtered = { characters: [], props: [], environments: [], posters: [], covers: [] };
                if (targetTypeFilters.includes('characters')) filtered.characters = Array.isArray(payload.characters) ? payload.characters : [];
                if (targetTypeFilters.includes('props')) filtered.props = Array.isArray(payload.props) ? payload.props : [];
                if (targetTypeFilters.includes('environments')) filtered.environments = Array.isArray(payload.environments) ? payload.environments : [];
                if (targetTypeFilters.includes('posters') || targetTypeFilters.includes('covers')) {
                    filtered.posters = Array.isArray(payload.posters) ? payload.posters : [];
                    filtered.covers = Array.isArray(payload.covers) ? payload.covers : [];
                }
                return filtered;
            };

            const globalInfoPayload = getGlobalInfoPayloadFromJsonText(text);
            if (globalInfoPayload?.global_info) {
                jsonBlocks.push(globalInfoPayload);
            }

            // Prefer backend-provided subjects_json (clean, pre-parsed) over
            // re-parsing raw LLM markdown with heuristic regex extractors.
            const backendSubjectsJson = filterSubjectsByTargetTypes(importOptions?.subjectsJson || null);
            const hasBackendSubjects = backendSubjectsJson
                && typeof backendSubjectsJson === 'object'
                && (
                    (Array.isArray(backendSubjectsJson.characters) && backendSubjectsJson.characters.length > 0)
                    || (Array.isArray(backendSubjectsJson.props) && backendSubjectsJson.props.length > 0)
                    || (Array.isArray(backendSubjectsJson.environments) && backendSubjectsJson.environments.length > 0)
                    || (Array.isArray(backendSubjectsJson.covers) && backendSubjectsJson.covers.length > 0)
                    || (Array.isArray(backendSubjectsJson.posters) && backendSubjectsJson.posters.length > 0)
                );

            if (hasBackendSubjects) {
                jsonBlocks.push(backendSubjectsJson);
                importDiagnostics.entitiesPayloadSource = 'backend_subjects_json';
                addLog('Using backend-extracted subjects_json for entity import.', 'info');
            } else {
                const mergedEntities = getMergedEntitiesPayloadFromText(text);
                if (mergedEntities?.payload) {
                    const filteredMergedPayload = filterSubjectsByTargetTypes(mergedEntities.payload);
                    jsonBlocks.push(filteredMergedPayload);
                    importDiagnostics.entitiesPayloadSource = mergedEntities.source || 'merged';
                    if (String(importDiagnostics.entitiesPayloadSource).includes('subject_index_fallback')) {
                        importDiagnostics.subjectIndexExtracted =
                            (Array.isArray(filteredMergedPayload.characters) ? filteredMergedPayload.characters.length : 0)
                            + (Array.isArray(filteredMergedPayload.props) ? filteredMergedPayload.props.length : 0)
                            + (Array.isArray(filteredMergedPayload.environments) ? filteredMergedPayload.environments.length : 0);
                        addLog('Entities payload merged with Subject Index fallback for missing types.', 'warning');
                    }
                }
            }

            // Fallback: explicit JSON mode can still parse generic object blocks.
            if (effectiveImportType === 'json' && jsonBlocks.length === 0) {
                const genericBlocks = extractJSONBlocks(text);
                importStats.genericJsonBlocks = genericBlocks.length;
                for (const block of genericBlocks) {
                    if (block && typeof block === 'object') jsonBlocks.push(block);
                }
                if (jsonBlocks.length > 0 && importDiagnostics.entitiesPayloadSource === 'none') {
                    importDiagnostics.entitiesPayloadSource = 'generic_json_blocks';
                }
            }
        }
        if (jsonBlocks.length > 0) {
               importStats.jsonBlocks = jsonBlocks.length;
             addLog(`Found ${jsonBlocks.length} JSON blocks to process.`, "info");
             // Process JSON Loop (same as before)
             // ... existing JSON processing code will run below ...
        }

        // Feature Flags based on Type
        // If specific type selected, FORCE recognition of that type and IGNORE others logic
        const canScript = effectiveImportType === 'auto' || effectiveImportType === 'script';
        const canScene = effectiveImportType === 'auto' || effectiveImportType === 'scene';
        const canShot = effectiveImportType === 'auto' || effectiveImportType === 'shot';

        // Strict: If explicit type, don't require specific headers if possible, OR just bypass strict header check?
        // Actually, existing logic relies on headers to parse columns. We still need headers.
        // But we won't misidentify Scene table as Shot table if we force one.
        
        const hasScriptTable = canScript && text.includes('|') && (text.includes('Paragraph ID') || text.includes('Paragraph Title'));
        
        // Scene header detection (Relaxed if forced scene type?)
        const sceneHeaderMarkers = ['Scene No', '场次序号', 'Scene ID', '场次'];
        let hasSceneTable = canScene && text.includes('|') && sceneHeaderMarkers.some(m => text.includes(m));
        
        // Shot header detection
        const shotHeaderMarkers = ['Shot ID', '镜头ID', 'Shot No'];
        let hasShotTable = canShot && text.includes('|') && shotHeaderMarkers.some(m => text.includes(m));
        importDiagnostics.markers = {
            script: hasScriptTable,
            scene: hasSceneTable,
            shot: hasShotTable,
        };

        // If explicit type is set but markers are missing, try to help user?
        if (effectiveImportType === 'scene' && !hasSceneTable && text.includes('|')) {
            // Fallback: If strict mode, maybe assume the first row with | is header? 
            // Warning user is safer.
            addLog("Warning: 'Scenes' type selected, but specific Scene headers not found. Attempting to parse anyway if table exists.", "warning");
            hasSceneTable = true;
        }
        if (effectiveImportType === 'shot' && !hasShotTable && text.includes('|')) {
             addLog("Warning: 'Shots' type selected, but specific Shot headers not found. Attempting to parse anyway if table exists.", "warning");
             hasShotTable = true;
        }

        addLog(`Import Flags: Script=${hasScriptTable}, Scene=${hasSceneTable}, Shot=${hasShotTable}`, "info");

        if (jsonBlocks.length === 0 && !hasScriptTable && !hasSceneTable && !hasShotTable && !projectVisualBackfill) {

            addLog("No recognizable markers found.", "error");
            alert("No supported format detected. Please check your markers.");
            return {
                ok: false,
                changed: false,
                reason: 'No supported format detected.',
                importedSubjectCounts,
                importStats,
                importDiagnostics,
                postImportStatusNote,
            };
        }

        let changesMade = false;
        let reloadRequired = false;
        const canonicalSubjectType = (value) => {
            const lc = String(value || '').trim().toLowerCase();
            if (!lc) return '';
            if (['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(lc)) return 'character';
            if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(lc)) return 'prop';
            if (['environment', 'environments', 'env', 'scene', 'scenes', '场景', '环境'].includes(lc)) return 'environment';
            if (['poster', 'posters', 'cover', 'covers', 'cover_poster', '海报', '封面'].includes(lc)) return 'poster';
            return lc;
        };
        const existingEntities = (id
            ? await fetchEntities(id).catch(() => [])
            : []);
        let knownEntities = Array.isArray(existingEntities) ? [...existingEntities] : [];
        const normalizeEntityKey = (type, name) => `${canonicalSubjectType(type) || 'unknown'}:${normalizeEntityToken(name)}`;
        const existingEntityMap = new Map();
        for (const e of (existingEntities || [])) {
            const t = canonicalSubjectType(e?.type);
            if (!t) continue;
            const name = String(e?.name || '').trim();
            const nameEn = String(e?.name_en || '').trim();
            if (name) existingEntityMap.set(normalizeEntityKey(t, name), e);
            if (nameEn) existingEntityMap.set(normalizeEntityKey(t, nameEn), e);
        }

        if (projectVisualBackfill && id) {
            const originalGlobalInfo = (project?.global_info && typeof project.global_info === 'object') ? project.global_info : {};
            const currentBorrowedFilms = Array.isArray(originalGlobalInfo.borrowed_films)
                ? originalGlobalInfo.borrowed_films.map(v => String(v || '').trim()).filter(Boolean)
                : [];

            const isBlank = (value) => String(value || '').trim().length === 0;
            const backfillPatch = {};

            if (isBlank(originalGlobalInfo.Global_Style) && projectVisualBackfill.Global_Style) {
                backfillPatch.Global_Style = projectVisualBackfill.Global_Style;
            }
            if (currentBorrowedFilms.length === 0 && Array.isArray(projectVisualBackfill.borrowed_films) && projectVisualBackfill.borrowed_films.length > 0) {
                backfillPatch.borrowed_films = projectVisualBackfill.borrowed_films;
            }
            if (isBlank(originalGlobalInfo.tone) && projectVisualBackfill.tone) {
                backfillPatch.tone = projectVisualBackfill.tone;
            }
            if (isBlank(originalGlobalInfo.lighting) && projectVisualBackfill.lighting) {
                backfillPatch.lighting = projectVisualBackfill.lighting;
            }
            if (isBlank(originalGlobalInfo.borrowed_films_note) && projectVisualBackfill.borrowed_films_note) {
                backfillPatch.borrowed_films_note = projectVisualBackfill.borrowed_films_note;
            }
            if (isBlank(originalGlobalInfo.plot_summary) && projectVisualBackfill.plot_summary) {
                backfillPatch.plot_summary = projectVisualBackfill.plot_summary;
            }
            if (isBlank(originalGlobalInfo.music_recommendation) && projectVisualBackfill.music_recommendation) {
                backfillPatch.music_recommendation = projectVisualBackfill.music_recommendation;
            }

            if (Object.keys(backfillPatch).length > 0) {
                try {
                    await updateProject(id, { global_info: { ...originalGlobalInfo, ...backfillPatch } });
                    addLog(
                        `Project visual fields backfilled from analysis: ${Object.keys(backfillPatch).join(', ')}`,
                        'success'
                    );
                    changesMade = true;
                    reloadRequired = true;
                } catch (e) {
                    addLog(`Project visual field backfill failed: ${e.message}`, 'warning');
                }
            }
        }

        // Process all found JSON blocks
        for (const data of jsonBlocks) {
            // 2. Process Global Info (JSON)
            if (data.global_info) {
                try {
                    const latestProj = await fetchProject(id);
                    const currentGInfo = (latestProj?.global_info && typeof latestProj.global_info === 'object') ? latestProj.global_info : {};
                    const mergedGI = { ...currentGInfo, ...data.global_info };
                    await updateProject(id, { global_info: mergedGI });
                    addLog("Project Global Info updated.", "success");
                    changesMade = true;
                    reloadRequired = true;
                } catch (e) {
                    addLog(`Global Info Update Failed: ${e.message}`, "error"); 
                }
            }

            // 2c. Process Entities (JSON)
            // Can be { characters: [] } or { props: [] } etc
            if (data.characters || data.props || data.environments || data.covers || data.posters) {
                try {
                    addLog("Processing Entities block...", "process");
                    let count = 0;
                    const skippedExistingSubjectCounts = { character: 0, prop: 0, environment: 0, poster: 0 };
                    const logSkippedExistingSubject = (type, entityName, entityNameEn = '') => {
                        const normalizedType = String(type || '').trim().toLowerCase();
                        if (Object.prototype.hasOwnProperty.call(skippedExistingSubjectCounts, normalizedType)) {
                            skippedExistingSubjectCounts[normalizedType] += 1;
                        }
                        skippedSubjectItems.push({
                            type: normalizedType,
                            name: entityName,
                            name_en: entityNameEn || '',
                            reason: 'existing_subject_reused',
                        });
                        const aliasSuffix = entityNameEn ? ` / ${entityNameEn}` : '';
                        addLog(
                            `Skipped existing ${normalizedType} subject during import: ${entityName}${aliasSuffix}`,
                            'info'
                        );
                    };
                    const plannedCharacterCount = Array.isArray(data.characters) ? data.characters.length : 0;
                    const plannedPropCount = Array.isArray(data.props) ? data.props.length : 0;
                    const plannedEnvironmentCount = Array.isArray(data.environments) ? data.environments.length : 0;
                    const plannedPosterCount = (Array.isArray(data.posters) ? data.posters.length : 0) + (Array.isArray(data.covers) ? data.covers.length : 0);
                    addLog(
                        `Entities block detected: character=${plannedCharacterCount}, prop=${plannedPropCount}, environment=${plannedEnvironmentCount}, poster=${plannedPosterCount}`,
                        'info'
                    );

                    const _isFallbackIndex = (n) => {
                        const lc = String(n || '').toLowerCase().replace(/[\s_\-]/g, '');
                        return ['subjectindex', 'subjectsindex', 'sceneanalysis', 'entities', 'character', 'characters', 'prop', 'props', 'environment', 'environments', 'role', 'roles', 'item', 'items', 'scene', 'scenes', '角色', '道具', '场景', '人物', '环境', '物件'].includes(lc);
                    };
                    const skipSubjectIndex = (n, en) => _isFallbackIndex(n) || _isFallbackIndex(en);

                    // Characters
                    if (data.characters && Array.isArray(data.characters)) {
                        for (const char of data.characters) {
                            const entityName = String(
                                char?.subject_name_exact ||
                                    char?.name ||
                                char?.subject_name ||
                                char?.name_zh ||
                                char?.name_en ||
                                ''
                            ).trim();
                            const entityNameEn = String(char?.name_en || char?.english_name || char?.en_name || '').trim();
                            if (skipSubjectIndex(entityName, entityNameEn)) {
                                addLog(`Skipped entity payload named '${entityName}' (it matched subject index fallback rules).`, 'warning');
                                continue;
                            }
                            if (!entityName) {
                                addLog('Skipped character entity without name aliases (name/subject_name_exact/name_en).', 'warning');
                                continue;
                            }
                            const existingForName = existingEntityMap.get(normalizeEntityKey('character', entityName)) || (entityNameEn ? existingEntityMap.get(normalizeEntityKey('character', entityNameEn)) : null);
                            if (existingForName) {
                                if (String(existingForName.episode_id) === String(activeEpisode?.id)) {
                                    logSkippedExistingSubject('character', entityName, entityNameEn);
                                    continue;
                                } else {
                                    char.visual_dependencies = Array.isArray(char.visual_dependencies) ? char.visual_dependencies : (typeof char.visual_dependencies === 'string' ? [char.visual_dependencies] : []);
                                    // Use format expected by the backend/prompts
                                    char.visual_dependencies.push(`existing_id:${existingForName.id}`);
                                }
                            }
                            const desc = [
                                `Name (EN): ${entityNameEn || char.name_en || ''}`,
                                `Description: ${char.description_cn || char.description || char.narrative_description || ''}`,
                                `Role: ${char.role}`,
                                `Archetype: ${char.archetype}`,
                                `Appearance: ${char.appearance_cn}`,
                                `Clothing: ${char.clothing}`,
                                `Action: ${char.action_characteristics}`,
                                char.generation_prompt_cn ? `Prompt (CN): ${char.generation_prompt_cn}` : '',
                                `Prompt: ${char.generation_prompt_en}`,
                                char.negative_prompt_en ? `Negative Prompt: ${char.negative_prompt_en}` : ''
                            ].filter(Boolean).join('\n\n');

                            try {
                                const payload = {
                                    name: entityName,
                                    type: 'character',
                                    episode_id: activeEpisode?.id || undefined,
                                    description: desc,
                                    generation_prompt_cn: char.generation_prompt_cn || '',
                                    generation_prompt_en: char.generation_prompt_en || '',
                                    anchor_description: char.anchor_description || '',

                                    name_en: entityNameEn,
                                    base_name_en: char.base_name_en || '',
                                    gender: char.gender,
                                    role: char.role,
                                    archetype: char.archetype,
                                    appearance_cn: char.appearance_cn,
                                    clothing: char.clothing,
                                    action_characteristics: char.action_characteristics,
                                    visual_dependencies: parseVisualDependencies(char.visual_dependencies),
                                    dependency_strategy: char.dependency_strategy || {},
                                    custom_attributes: {
                                        ...(char.custom_attributes || {}),
                                        ...(char.negative_prompt_en ? { negative_prompt_en: char.negative_prompt_en } : {}),
                                    },
                                };
                                const created = await createEntity(id, payload);
                                if (created?.id) {
                                    knownEntities.push(created);
                                    existingEntityMap.set(normalizeEntityKey('character', entityName), created);
                                    if (entityNameEn) existingEntityMap.set(normalizeEntityKey('character', entityNameEn), created);
                                    count++;
                                    importedSubjectCounts.character += 1;
                                    createdSubjectItems.push({
                                        type: 'character',
                                        name: entityName,
                                        name_en: entityNameEn || '',
                                        id: created.id,
                                    });
                                }
                            } catch (err) {
                                addLog(`Character import failed (${entityName}): ${err?.message || err}`, 'warning');
                            }
                        }
                    }

                    // Props
                    if (data.props && Array.isArray(data.props)) {
                        for (const prop of data.props) {
                                      const entityName = String(
                                          prop?.subject_name_exact ||
                                            prop?.name ||
                                          prop?.subject_name ||
                                          prop?.name_zh ||
                                          prop?.name_en ||
                                          ''
                                      ).trim();
                                      const entityNameEn = String(prop?.name_en || prop?.english_name || prop?.en_name || '').trim();
                             if (skipSubjectIndex(entityName, entityNameEn)) continue;
                             if (!entityName) {
                                          addLog('Skipped prop entity without name aliases (name/subject_name_exact/name_en).', 'warning');
                                continue;
                             }
                             if (existingEntityMap.has(normalizeEntityKey('prop', entityName)) || (entityNameEn && existingEntityMap.has(normalizeEntityKey('prop', entityNameEn)))) {
                                logSkippedExistingSubject('prop', entityName, entityNameEn);
                                continue;
                             }
                             const desc = [
                                          `Name (EN): ${entityNameEn || prop.name_en || ''}`,
                                `Type: ${prop.type}`, // inner type from JSON
                                          `Description: ${prop.description_cn || prop.description || ''}`,
                                prop.generation_prompt_cn ? `Prompt (CN): ${prop.generation_prompt_cn}` : '',
                                `Prompt: ${prop.generation_prompt_en}`,
                                prop.negative_prompt_en ? `Negative Prompt: ${prop.negative_prompt_en}` : '',
                                prop.dependency_strategy?.logic ? `Dependency: ${prop.dependency_strategy.logic}` : ''
                            ].filter(Boolean).join('\n\n');

                            try {
                                const payload = {
                                    name: entityName,
                                    type: 'prop',
                                    episode_id: activeEpisode?.id || undefined,
                                    description: desc,
                                    generation_prompt_cn: prop.generation_prompt_cn || '',
                                    generation_prompt_en: prop.generation_prompt_en || '',
                                    anchor_description: prop.anchor_description || '',

                                    name_en: entityNameEn,
                                    base_name_en: prop.base_name_en || '',
                                    visual_dependencies: parseVisualDependencies(prop.visual_dependencies),
                                    dependency_strategy: prop.dependency_strategy || {},
                                    custom_attributes: {
                                        ...(prop.custom_attributes || {}),
                                        ...(prop.negative_prompt_en ? { negative_prompt_en: prop.negative_prompt_en } : {}),
                                    },
                                };
                                const created = await createEntity(id, payload);
                                if (created?.id) {
                                    knownEntities.push(created);
                                    existingEntityMap.set(normalizeEntityKey('prop', entityName), created);
                                    if (entityNameEn) existingEntityMap.set(normalizeEntityKey('prop', entityNameEn), created);
                                    count++;
                                    importedSubjectCounts.prop += 1;
                                    createdSubjectItems.push({
                                        type: 'prop',
                                        name: entityName,
                                        name_en: entityNameEn || '',
                                        id: created.id,
                                    });
                                }
                            } catch (err) {
                                addLog(`Prop import failed (${entityName}): ${err?.message || err}`, 'warning');
                            }
                        }
                    }

                    // Environments
                    if (data.environments && Array.isArray(data.environments)) {
                        for (const env of data.environments) {
                                      const entityName = String(
                                          env?.subject_name_exact ||
                                            env?.name ||
                                          env?.subject_name ||
                                          env?.name_zh ||
                                          env?.name_en ||
                                          ''
                                      ).trim();
                                      const entityNameEn = String(env?.name_en || env?.english_name || env?.en_name || '').trim();
                             if (skipSubjectIndex(entityName, entityNameEn)) continue;
                             if (!entityName) {
                                          addLog('Skipped environment entity without name aliases (name/subject_name_exact/name_en).', 'warning');
                                continue;
                             }
                             if (existingEntityMap.has(normalizeEntityKey('environment', entityName)) || (entityNameEn && existingEntityMap.has(normalizeEntityKey('environment', entityNameEn)))) {
                                logSkippedExistingSubject('environment', entityName, entityNameEn);
                                continue;
                             }
                             const desc = [
                                          `Name (EN): ${entityNameEn || env.name_en || ''}`,
                                `Atmosphere: ${env.atmosphere}`,
                                `Visual Params: ${env.visual_params}`,
                                          `Description: ${env.description_cn || env.description || env.narrative_description || ''}`,
                                env.generation_prompt_cn ? `Prompt (CN): ${env.generation_prompt_cn}` : '',
                                `Prompt: ${env.generation_prompt_en}`,
                                env.negative_prompt_en ? `Negative Prompt: ${env.negative_prompt_en}` : ''
                            ].filter(Boolean).join('\n\n');

                            try {
                                const payload = {
                                    name: entityName,
                                    type: 'environment',
                                    episode_id: activeEpisode?.id || undefined,
                                    description: desc,
                                    generation_prompt_cn: env.generation_prompt_cn || '',
                                    generation_prompt_en: env.generation_prompt_en || '',
                                    anchor_description: env.anchor_description || '',

                                    name_en: entityNameEn,
                                    base_name_en: env.base_name_en || '',
                                    atmosphere: env.atmosphere,
                                    visual_params: env.visual_params,
                                    narrative_description: env.description_cn,

                                    visual_dependencies: parseVisualDependencies(env.visual_dependencies),
                                    dependency_strategy: env.dependency_strategy || {},
                                    custom_attributes: {
                                        ...(env.custom_attributes || {}),
                                        ...(env.negative_prompt_en ? { negative_prompt_en: env.negative_prompt_en } : {}),
                                    },
                                };
                                const created = await createEntity(id, payload);
                                if (created?.id) {
                                    knownEntities.push(created);
                                    existingEntityMap.set(normalizeEntityKey('environment', entityName), created);
                                    if (entityNameEn) existingEntityMap.set(normalizeEntityKey('environment', entityNameEn), created);
                                    count++;
                                    importedSubjectCounts.environment += 1;
                                    createdSubjectItems.push({
                                        type: 'environment',
                                        name: entityName,
                                        name_en: entityNameEn || '',
                                        id: created.id,
                                    });
                                }
                            } catch (err) {
                                addLog(`Environment import failed (${entityName}): ${err?.message || err}`, 'warning');
                            }
                        }
                    }

                    // Posters
                    const resolvedPosters = (data.posters && Array.isArray(data.posters) && data.posters.length > 0) ? data.posters : ((data.covers && Array.isArray(data.covers) && data.covers.length > 0) ? data.covers : null);
                    if (resolvedPosters) {
                        for (const poster of resolvedPosters) {
                                      const entityName = String(
                                          poster?.subject_name_exact ||
                                            poster?.name ||
                                          poster?.subject_name ||
                                          poster?.name_zh ||
                                          poster?.name_en ||
                                          ''
                                      ).trim();
                                      const entityNameEn = String(poster?.name_en || poster?.english_name || poster?.en_name || '').trim();
                             if (skipSubjectIndex(entityName, entityNameEn)) continue;
                             if (!entityName) {
                                          addLog('Skipped poster entity without name aliases (name/subject_name_exact/name_en).', 'warning');
                                continue;
                             }
                             const existingPoster = existingEntityMap.get(normalizeEntityKey('poster', entityName))
                                || (entityNameEn ? existingEntityMap.get(normalizeEntityKey('poster', entityNameEn)) : null)
                                || (shouldOverwritePoster
                                    ? (knownEntities.find((item) => {
                                        if (canonicalSubjectType(item?.type) !== 'poster') return false;
                                        if (activeEpisode?.id && String(item?.episode_id || '') !== String(activeEpisode.id)) return false;
                                        return true;
                                    }) || null)
                                    : null);
                             if (existingPoster && shouldOverwritePoster) {
                                const desc = [
                                          `Name (EN): ${entityNameEn || poster.name_en || ''}`,
                                `Atmosphere: ${poster.atmosphere}`,
                                `Visual Params: ${poster.visual_params}`,
                                          `Description: ${poster.description_cn || poster.description || poster.narrative_description || ''}`,
                                poster.generation_prompt_cn ? `Prompt (CN): ${poster.generation_prompt_cn}` : '',
                                `Prompt: ${poster.generation_prompt_en}`,
                                poster.negative_prompt_en ? `Negative Prompt: ${poster.negative_prompt_en}` : ''
                            ].filter(Boolean).join('\n\n');
                                try {
                                    const payload = {
                                        name: entityName,
                                        type: 'poster',
                                        episode_id: activeEpisode?.id || existingPoster.episode_id || undefined,
                                        description: desc,
                                        generation_prompt_cn: poster.generation_prompt_cn || '',
                                        generation_prompt_en: poster.generation_prompt_en || '',
                                        anchor_description: poster.anchor_description || '',
                                        name_en: entityNameEn,
                                        base_name_en: poster.base_name_en || '',
                                        atmosphere: poster.atmosphere,
                                        visual_params: poster.visual_params,
                                        narrative_description: poster.description_cn,
                                        visual_dependencies: parseVisualDependencies(poster.visual_dependencies),
                                        dependency_strategy: poster.dependency_strategy || {},
                                        custom_attributes: {
                                            ...(existingPoster.custom_attributes || {}),
                                            ...(poster.custom_attributes || {}),
                                            ...(poster.subject_no ? { subject_no: poster.subject_no } : {}),
                                            ...(poster.negative_prompt_en ? { negative_prompt_en: poster.negative_prompt_en } : {}),
                                        },
                                    };
                                    const updated = await updateEntity(existingPoster.id, payload);
                                    if (updated?.id) {
                                        knownEntities = knownEntities.map((item) => (item.id === updated.id ? updated : item));
                                        existingEntityMap.set(normalizeEntityKey('poster', entityName), updated);
                                        if (entityNameEn) existingEntityMap.set(normalizeEntityKey('poster', entityNameEn), updated);
                                        count++;
                                        importedSubjectCounts.poster += 1;
                                        createdSubjectItems.push({
                                            type: 'poster',
                                            name: entityName,
                                            name_en: entityNameEn || '',
                                            id: updated.id,
                                            updated: true,
                                        });
                                        addLog(`Updated existing poster subject during import: ${entityName}${entityNameEn ? ` / ${entityNameEn}` : ''}`, 'success');
                                    }
                                } catch (err) {
                                    addLog(`Poster update failed (${entityName}): ${err?.message || err}`, 'warning');
                                }
                                continue;
                             }
                             if (existingPoster) {
                                logSkippedExistingSubject('poster', entityName, entityNameEn);
                                continue;
                             }
                             const desc = [
                                          `Name (EN): ${entityNameEn || poster.name_en || ''}`,
                                `Atmosphere: ${poster.atmosphere}`,
                                `Visual Params: ${poster.visual_params}`,
                                          `Description: ${poster.description_cn || poster.description || poster.narrative_description || ''}`,
                                poster.generation_prompt_cn ? `Prompt (CN): ${poster.generation_prompt_cn}` : '',
                                `Prompt: ${poster.generation_prompt_en}`,
                                poster.negative_prompt_en ? `Negative Prompt: ${poster.negative_prompt_en}` : ''
                            ].filter(Boolean).join('\n\n');

                            try {
                                const payload = {
                                    name: entityName,
                                    type: 'poster',
                                    episode_id: activeEpisode?.id || undefined,
                                    description: desc,
                                    generation_prompt_cn: poster.generation_prompt_cn || '',
                                    generation_prompt_en: poster.generation_prompt_en || '',
                                    anchor_description: poster.anchor_description || '',

                                    name_en: entityNameEn,
                                    base_name_en: poster.base_name_en || '',
                                    atmosphere: poster.atmosphere,
                                    visual_params: poster.visual_params,
                                    narrative_description: poster.description_cn,

                                    visual_dependencies: parseVisualDependencies(poster.visual_dependencies),
                                    dependency_strategy: poster.dependency_strategy || {},
                                    custom_attributes: {
                                        ...(poster.custom_attributes || {}),
                                        ...(poster.negative_prompt_en ? { negative_prompt_en: poster.negative_prompt_en } : {}),
                                    },
                                };
                                const created = await createEntity(id, payload);
                                if (created?.id) {
                                    knownEntities.push(created);
                                    existingEntityMap.set(normalizeEntityKey('poster', entityName), created);
                                    if (entityNameEn) existingEntityMap.set(normalizeEntityKey('poster', entityNameEn), created);
                                    count++;
                                    importedSubjectCounts.poster += 1;
                                    createdSubjectItems.push({
                                        type: 'poster',
                                        name: entityName,
                                        name_en: entityNameEn || '',
                                        id: created.id,
                                    });
                                }
                            } catch (err) {
                                addLog(`Poster import failed (${entityName}): ${err?.message || err}`, 'warning');
                            }
                        }
                    }
                    
                    if (count > 0) {
                        addLog(`Imported ${count} entities from block.`, "success");
                        const skippedExistingTotal = skippedExistingSubjectCounts.character + skippedExistingSubjectCounts.prop + skippedExistingSubjectCounts.environment + skippedExistingSubjectCounts.poster;
                        if (skippedExistingTotal > 0) {
                            addLog(
                                `Reused existing subjects without overwrite: character=${skippedExistingSubjectCounts.character}, prop=${skippedExistingSubjectCounts.prop}, environment=${skippedExistingSubjectCounts.environment}, poster=${skippedExistingSubjectCounts.poster}.`,
                                'info'
                            );
                        }
                        changesMade = true;
                    } else {
                        const skippedExistingTotal = skippedExistingSubjectCounts.character + skippedExistingSubjectCounts.prop + skippedExistingSubjectCounts.environment + skippedExistingSubjectCounts.poster;
                        if (skippedExistingTotal > 0) {
                            addLog(
                                `Entities block matched existing subjects only; no overwrite performed. Reused existing subjects: character=${skippedExistingSubjectCounts.character}, prop=${skippedExistingSubjectCounts.prop}, environment=${skippedExistingSubjectCounts.environment}, poster=${skippedExistingSubjectCounts.poster}.`,
                                'info'
                            );
                        } else {
                            addLog('Entities block found but no importable subjects were created.', 'warning');
                        }
                    }
                } catch (e) {
                    addLog(`Entity Import Failed: ${e.message}`, "error");
                    console.error(e);
                }
            }
        }

        // Check episode selection for Script/Scene import
        if ((hasScriptTable || hasSceneTable) && !activeEpisodeId) {
             addLog("Detection: Script/Scene content found but NO Active Episode selected.", "error");
             alert("Please create or select an episode before importing Script or Scene content.");
             return; 
        }

        // 3. Process Script Content
        if (hasScriptTable && activeEpisodeId) {
            try {
                addLog(`Processing Script Table for Episode ${activeEpisodeId}...`, "process");
                const lines = text.split('\n');
                let scriptLines = [];
                let capturing = false;

                for (let line of lines) {
                    // Start marker
                    if (line.includes('|') && (line.includes('Paragraph ID') || line.includes('Paragraph Title'))) {
                        capturing = true;
                        addLog("Found Script Header.", "info");
                    }
                    
                    if (capturing) {
                        if (line.trim().startsWith('|')) {
                            // Validate column count roughly to avoid bad lines? optional.
                            scriptLines.push(line);
                        } else if (scriptLines.length > 2 && !line.trim().startsWith('|')) {
                            capturing = false;
                            addLog("End of Script Table.", "info");
                        }
                    }
                }

                if (scriptLines.length > 0) {
                    const content = scriptLines.join('\n');
                    // await updateEpisode(activeEpisodeId, { script_content: content });
                    addLog(`Parsed ${scriptLines.length} lines of Script content from LLM result. Skipped auto-backfilling to script_content to preserve original text.`, "success");
                    importStats.scriptLines = scriptLines.length;
                    changesMade = true;
                } else {
                    addLog("Script markers found but no lines extracted.", "error");
                }
            } catch (e) {
                addLog(`Script Import Failed: ${e.message}`, "error");
            }
        }

        // 4. Process Scene Content (and interleaved Shots)
        if ((hasSceneTable || hasShotTable) && activeEpisodeId) {
             try {
                addLog(`Processing Scene/Shot Tables for Episode ${activeEpisodeId}...`, "process");
                const lines = text.split('\n');
                let sceneLines = [];
                let shotLines = [];
                
                // DB Sync State
                let existingScenes = [];
                if (replaceExistingScenes) {
                    try {
                        const purgeResult = await purgeEpisodeScenes(activeEpisodeId, { clearProgress: false });
                        addLog(
                            `Replaced episode scenes before import: deleted=${Number(purgeResult?.deleted_scenes || 0)}.`,
                            'info'
                        );
                    } catch (clearErr) {
                        addLog(`Pre-import scene replace warning: ${clearErr?.message || clearErr}`, 'warning');
                    }
                }
                try { existingScenes = await fetchScenes(activeEpisodeId); } catch(e) {}
                let currentSceneDbId = null;
                const deferredShots = [];
                const pendingShotItems = [];
                const pendingSceneRows = [];
                const queueShotItem = (sceneId, shotData) => {
                    const sid = Number(sceneId || 0);
                    if (!Number.isFinite(sid) || sid <= 0 || !shotData?.shot_id) return;
                    pendingShotItems.push({ scene_id: sid, shot: shotData });
                };
                const normalizeSceneNoToken = (value) => {
                    const text = String(value || '')
                        .replace(/<br\s*\/?>/gi, ' ')
                        .trim()
                        .toLowerCase();
                    // Keep only alphanumerics so EP01_SC01 / EP01-SC01 / EP01 SC01 can match.
                    return text.replace(/[^a-z0-9]/g, '');
                };
                const toSceneNumber = (value) => {
                    const text = String(value || '').trim();
                    if (!text) return null;
                    const scMatches = Array.from(text.matchAll(/sc(?:ene)?\s*0*([0-9]{1,4})/ig));
                    if (scMatches.length > 0) {
                        const n = Number.parseInt(scMatches[scMatches.length - 1][1], 10);
                        return Number.isFinite(n) && n > 0 ? n : null;
                    }

                    const allNum = Array.from(text.matchAll(/0*([0-9]{1,4})/g));
                    if (allNum.length > 0) {
                        // Prefer the last numeric token so EP01_SC16 resolves to 16.
                        const n = Number.parseInt(allNum[allNum.length - 1][1], 10);
                        return Number.isFinite(n) && n > 0 ? n : null;
                    }

                    const m = text.match(/\b0*([0-9]{1,4})\b/);
                    if (m && m[1]) {
                        const n = Number.parseInt(m[1], 10);
                        return Number.isFinite(n) && n > 0 ? n : null;
                    }
                    return null;
                };
                const extractSceneNoCandidates = (rawValue) => {
                    const out = [];
                    const text = String(rawValue || '').trim();
                    if (!text) return out;

                    out.push(text);

                    // Match patterns like EP01_SC01, SC01, scene01 and map to 1.
                    const scMatch = text.match(/(?:^|[_\-])sc(?:ene)?\s*0*([0-9]{1,4})(?:$|[_\-])/i) || text.match(/^sc(?:ene)?\s*0*([0-9]{1,4})$/i);
                    if (scMatch && scMatch[1]) {
                        out.push(String(parseInt(scMatch[1], 10)));
                    }

                    const sceneNum = toSceneNumber(text);
                    if (Number.isFinite(sceneNum) && sceneNum > 0) {
                        out.push(String(sceneNum));
                    }

                    // Include all numeric tokens (EP01_SC01 => 1, 1).
                    const allNum = text.match(/\b0*([0-9]{1,4})\b/g) || [];
                    for (const token of allNum) {
                        const n = Number.parseInt(String(token).replace(/^0+/, '') || '0', 10);
                        if (Number.isFinite(n) && n > 0) out.push(String(n));
                    }

                    return Array.from(new Set(out.map(v => String(v || '').trim()).filter(Boolean)));
                };

                const resolveSceneByCode = (sceneCodeRaw) => {
                    const rawCandidates = extractSceneNoCandidates(sceneCodeRaw);
                    const candidates = rawCandidates.map(v => normalizeSceneNoToken(v)).filter(Boolean);
                    const candidateNums = rawCandidates
                        .map((v) => toSceneNumber(v))
                        .filter((v) => Number.isFinite(v));
                    if (candidates.length === 0 && candidateNums.length === 0) return null;

                    const directMatch = existingScenes.find((s) => {
                        const dbTokens = [s?.scene_no, s?.scene_id, s?.scene_code]
                            .map((v) => normalizeSceneNoToken(v))
                            .filter(Boolean);
                        if (dbTokens.some((token) => candidates.includes(token))) return true;

                        const dbSceneNums = [toSceneNumber(s?.scene_no), toSceneNumber(s?.scene_id), toSceneNumber(s?.scene_code)]
                            .filter((v) => Number.isFinite(v));
                        if (dbSceneNums.some((n) => candidateNums.includes(n))) return true;

                        return false;
                    }) || null;

                    if (directMatch) return directMatch;

                    // Fallback: if we can parse scene index N but DB scene_no values are irregular,
                    // map to the Nth scene in current episode order.
                    const fallbackNum = candidateNums.length > 0
                        ? candidateNums[candidateNums.length - 1]
                        : null;
                    if (Number.isFinite(fallbackNum) && fallbackNum > 0) {
                        const orderedScenes = [...existingScenes].sort((a, b) => {
                            const aNum = toSceneNumber(a?.scene_no);
                            const bNum = toSceneNumber(b?.scene_no);
                            if (Number.isFinite(aNum) && Number.isFinite(bNum) && aNum !== bNum) return aNum - bNum;
                            return Number(a?.id || 0) - Number(b?.id || 0);
                        });
                        if (orderedScenes.length >= fallbackNum) {
                            return orderedScenes[fallbackNum - 1] || null;
                        }
                    }

                    return null;
                };
                
                // State flags
                let inShotTable = false;
                let inSceneTable = false;
                let shotHeaderMap = {};
                let sceneHeaderMap = {};
                let sceneTableHeaders = [];
                let sceneTableHeaderMap = {};

                for (let line of lines) {
                    const trimmed = line.trim();
                    let isTableRow = trimmed.startsWith('|');
                    
                    // Robustness: Allow internal rows without leading pipe
                    if (!isTableRow && (inSceneTable || inShotTable) && trimmed.includes('|')) isTableRow = true;
                    
                    let cols = [];
                    if (isTableRow || trimmed.includes('|')) { 
                        cols = line.split('|').map(c => c.trim());
                        if (trimmed.startsWith('|') && cols.length > 0 && cols[0] === "") cols.shift();
                        if (trimmed.endsWith('|') && cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                    }

                    // 1. Header Detection (Relaxed)
                    const isShotKey = (isTableRow || line.includes('|')) && (line.includes("Shot ID") || line.includes("镜头ID") || line.includes("Shot Name") || line.includes("Shot No"));
                    const isSceneKey = (isTableRow || line.includes('|')) && (line.includes('Scene No') || line.includes('场次序号') || (line.includes('Scene ID') && !line.includes('Shot ID')));

                    // Enter Shot Table Mode
                    if (canShot && (isShotKey || (effectiveImportType === 'shot' && !inShotTable && isTableRow && cols.length > 2))) {
                        inShotTable = true;
                        inSceneTable = false;
                        addLog("Found Shot Header (or Forced Type).", "info");
                        shotLines.push(line); 
                        
                        // Parse Header Map
                        const curCols = line.split('|').map(c => c.trim());
                        // ... (same as original code)
                        if (curCols.length > 0 && curCols[0] === "") curCols.shift();
                        if (curCols.length > 0 && curCols[curCols.length-1] === "") curCols.pop();
                        
                        shotHeaderMap = {};
                        curCols.forEach((col, idx) => {
                             const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                             shotHeaderMap[key] = idx;
                        });
                        continue;
                    }
                    else if (canScene && (isSceneKey || (effectiveImportType === 'scene' && !inSceneTable && line.includes('|') && cols.length > 2))) {
                        inSceneTable = true;
                        inShotTable = false;
                        addLog("Found Scene Header (or Forced Type).", "info");
                        sceneLines.push(line);

                        const curCols = line.split('|').map(c => c.trim());
                        if (curCols.length > 0 && curCols[0] === "") curCols.shift();
                        if (curCols.length > 0 && curCols[curCols.length-1] === "") curCols.pop();

                        sceneTableHeaders = cleanMarkdownTableCells(line);
                        sceneTableHeaderMap = buildSceneTableHeaderMap(sceneTableHeaders);
                        sceneHeaderMap = {};
                        sceneTableHeaders.forEach((col, idx) => {
                            const key = normalizeSceneTableHeaderKey(col);
                            sceneHeaderMap[key] = idx;
                        });
                        continue;
                    }

                    // 2. Data Line Processing
                    if (isTableRow) {
                         // cols already parsed and cleaned at top of loop
                         // Only skip if strict separator line. 
                         // Check only for regex match of '---|---' style or '---' in cells (handling :--- for alignment)
                         const isSeparator = /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);
                         const isEmptyRow = cols.every(c => c === "");

                         if (cols.length < 2 || isSeparator || isEmptyRow) {
                             if (inSceneTable) sceneLines.push(line);
                             if (inShotTable) shotLines.push(line);
                             continue; 
                         }
                         
                         const clean = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';

                         // A. Handle Scene Row
                         if (inSceneTable) {
                             if (sceneTableHeaders.length > 0) {
                                 cols = reconcileSceneTableRowCells(cleanMarkdownTableCells(line), sceneTableHeaders);
                             }
                             sceneLines.push(line);
                             
                             try {
                                const fallback = getSceneTableFallbackIndices(cols.length, sceneTableHeaderMap);
                                const getSceneVal = (headerKey, legacyKeys, fallbackIdx) => {
                                    if (sceneTableHeaderMap[headerKey] !== undefined && sceneTableHeaderMap[headerKey] < cols.length) {
                                        return clean(cols[sceneTableHeaderMap[headerKey]]);
                                    }
                                    for (const k of legacyKeys) {
                                        if (sceneHeaderMap[k] !== undefined && sceneHeaderMap[k] < cols.length) {
                                            return clean(cols[sceneHeaderMap[k]]);
                                        }
                                    }
                                    const resolvedFallback = fallbackIdx !== undefined ? fallbackIdx : fallback[headerKey];
                                    return resolvedFallback !== undefined && resolvedFallback < cols.length
                                        ? clean(cols[resolvedFallback])
                                        : '';
                                };

                                const scData = {
                                    scene_no: getSceneVal('scene_no', ['sceneno', 'scene_no', '场次序号', '场次']),
                                    scene_name: getSceneVal('scene_name', ['scenename', 'title', 'scene_name', '场景名称']),
                                    equivalent_duration: getSceneVal('equivalent_duration', ['equivalentduration', 'duration', 'equivalent_duration']),
                                    core_scene_info: getSceneVal('core_scene_info', ['coresceneinfo', 'coregoal', 'core_scene_info']),
                                    original_script_text: getSceneVal('original_script_text', ['originalscripttext', 'description', 'original_script_text', 'adaptedscripttext', '改编剧本', '改编剧本文本']),
                                    environment_name: getSceneVal('environment_name', ['environmentname', 'environment_name', '环境名称', '环境', '环境锚点']),
                                    linked_characters: getSceneVal('linked_characters', ['linkedcharacters', 'linked_characters', '关联角色', '角色', 'characters']),
                                    key_props: getSceneVal('key_props', ['keyprops', 'key_props', '关键道具', '道具', 'props']),
                                };

                                const linkedByHeader = sceneTableHeaderMap.linked_characters !== undefined;
                                const propsByHeader = sceneTableHeaderMap.key_props !== undefined;
                                if (!linkedByHeader || !propsByHeader) {
                                    addLog(
                                        `Scene row import used fallback columns for subject fields (linked_by_header=${linkedByHeader}, props_by_header=${propsByHeader}) scene_no=${scData.scene_no || '(empty)'}.`,
                                        'warning'
                                    );
                                }
                                
                                if (!scData.scene_no || String(scData.scene_no).trim().length === 0) {
                                    // addLog("Skipping empty Scene row", "info"); // Optional log
                                    continue;
                                }

                                addLog(`Processing Scene Row: No=${scData.scene_no} Name=${(scData.scene_name || '').substring(0, 20)}...`, "info");
                                importedSceneRows.push({
                                    ...scData,
                                    id: null,
                                });
                                pendingSceneRows.push(scData);
                             } catch (rowErr) {
                                 console.error("Row Error", rowErr);
                                 addLog(`Row Processing Failed: ${rowErr.message}`, "error");
                             }
                         }
                         
                         // B. Handle Shot Row
                         else if (inShotTable) {
                             shotLines.push(line);
                             
                             const useMap = Object.keys(shotHeaderMap).length > 0;
                             
                             const getVal = (keys, defaultIdx) => {
                                 for (const k of keys) {
                                     if (shotHeaderMap[k] !== undefined && shotHeaderMap[k] < cols.length) return clean(cols[shotHeaderMap[k]]);
                                 }
                                 if (!useMap && defaultIdx < cols.length) return clean(cols[defaultIdx]);
                                 return '';
                             };
                             
                             // Legacy offset logic
                             let colStart = 2; 
                             let legacySceneCode = '';
                             if (!useMap) {
                                if (cols.length >= 8) {
                                    legacySceneCode = clean(cols[2]);
                                    colStart = 3;
                                }
                             }

                             const rawShotId = useMap ? getVal(['shotid', 'shotno', '镜头id', 'id'], 0) : clean(cols[0]);
                             
                             if (!rawShotId || String(rawShotId).trim().length === 0) {
                                 continue; 
                             }

                             // Resolve scene per-row to avoid stale scene mapping in mixed tables.
                             let sceneCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                             let resolvedSceneDbId = currentSceneDbId;
                             if (!sceneCode) {
                                 // Check shot id pattern like EP01_SC01_SH16 or 1-1A
                                 const scFromShotId = String(rawShotId || '').match(/(?:^|[_\-])sc(?:ene)?\s*0*[0-9]{1,4}(?:$|[_\-])/i);
                                 if (scFromShotId && scFromShotId[0]) {
                                     sceneCode = scFromShotId[0];
                                 } else {
                                     const parts = rawShotId.split(/[-_]/);
                                     if (parts.length > 1) sceneCode = parts[0];
                                 }
                             }

                             if (sceneCode) {
                                 const sceneMatch = resolveSceneByCode(sceneCode);
                                 if (sceneMatch?.id) {
                                     resolvedSceneDbId = sceneMatch.id;
                                     currentSceneDbId = sceneMatch.id;
                                 }
                             }

                             // Retry path: if unresolved, derive scene token from shot id and refetch scenes once.
                             if (!resolvedSceneDbId) {
                                 const shotSceneToken = String(rawShotId || '').match(/ep\s*\d+[_\- ]sc\s*\d+/i)
                                     || String(rawShotId || '').match(/sc(?:ene)?\s*0*\d+/i);
                                 const retrySceneCode = shotSceneToken && shotSceneToken[0]
                                     ? String(shotSceneToken[0]).replace(/\s+/g, '_')
                                     : '';

                                 if (retrySceneCode) {
                                     const retryMatch = resolveSceneByCode(retrySceneCode);
                                     if (retryMatch?.id) {
                                         resolvedSceneDbId = retryMatch.id;
                                         currentSceneDbId = retryMatch.id;
                                         if (!sceneCode) sceneCode = retrySceneCode;
                                     }
                                 }

                                 if (!resolvedSceneDbId) {
                                     try {
                                         existingScenes = await fetchScenes(activeEpisodeId);
                                     } catch (e) {}

                                     const retryCode = sceneCode || retrySceneCode;
                                     if (retryCode) {
                                         const refreshedMatch = resolveSceneByCode(retryCode);
                                         if (refreshedMatch?.id) {
                                             resolvedSceneDbId = refreshedMatch.id;
                                             currentSceneDbId = refreshedMatch.id;
                                         }
                                     }
                                 }
                             }

                             // Keep scene_code text from table/shot id for traceability.
                             if (!sceneCode && resolvedSceneDbId) {
                                 const sObj = existingScenes.find(s => s.id === resolvedSceneDbId);
                                 if (sObj) sceneCode = sObj.scene_no;
                             }

                            if (resolvedSceneDbId) {
                                 const shotData = {
                                     shot_id: rawShotId,
                                     shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                                     scene_code: sceneCode, 
                                     start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                                     end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                                     video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                                     duration: useMap ? getVal(['duration', 'durations', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                                     associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                                     shot_logic_cn: useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)', 'shot logic (cn)', 'logic(cn)'], 7) : ''
                                 };
                                 
                                 addLog(`Creating Shot ${shotData.shot_id} for Scene ID ${resolvedSceneDbId}...`, "info");
                                queueShotItem(resolvedSceneDbId, shotData);
                             } else {
                                 const shotData = {
                                     shot_id: rawShotId,
                                     shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                                     scene_code: sceneCode,
                                     start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                                     end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                                     video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                                     duration: useMap ? getVal(['duration', 'durations', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                                     associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                                     shot_logic_cn: useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)', 'shot logic (cn)', 'logic(cn)'], 7) : ''
                                 };
                                 deferredShots.push({ rawShotId, sceneCode, shotData });
                                 addLog(
                                     `Deferred Shot ${rawShotId}: unresolved Scene code '${sceneCode || ''}'. Will retry after scene refresh.`,
                                     "warning"
                                 );
                             }
                         }

                    } else if (sceneLines.length > 2 && inSceneTable && !isTableRow && trimmed !== '') {
                         inSceneTable = false;
                    } else if (shotLines.length > 2 && inShotTable && !isTableRow && trimmed !== '') {
                         inShotTable = false;
                    }
                }

                if (pendingSceneRows.length > 0) {
                    try {
                        const batchResp = await batchUpsertScenes(activeEpisodeId, pendingSceneRows, { recomputeCost: false });
                        const batchScenes = Array.isArray(batchResp?.scenes) ? batchResp.scenes : [];
                        const sceneIdByNo = new Map(
                            batchScenes
                                .map((item) => [String(item?.scene_no || '').replace(/\s+/g, ''), item])
                                .filter(([k]) => Boolean(k))
                        );
                        const existingIdSet = new Set(
                            (existingScenes || []).map((s) => Number(s?.id)).filter((idVal) => Number.isFinite(idVal))
                        );

                        importedSceneRows.forEach((row) => {
                            const noKey = String(row?.scene_no || '').replace(/\s+/g, '');
                            const mapped = sceneIdByNo.get(noKey);
                            if (mapped?.id) {
                                row.id = mapped.id;
                                currentSceneDbId = mapped.id;
                                if (!existingIdSet.has(Number(mapped.id))) {
                                    createdSceneIds.push(mapped.id);
                                    existingIdSet.add(Number(mapped.id));
                                }
                            }
                        });
                        importStats.scenesCreated += Number(batchResp?.created || 0);
                        importStats.scenesUpdated += Number(batchResp?.updated || 0);
                        addLog(
                            `Batch scene import done: processed=${Number(batchResp?.processed || pendingSceneRows.length)}, created=${Number(batchResp?.created || 0)}, updated=${Number(batchResp?.updated || 0)}, elapsed=${Number(batchResp?.elapsed_ms || 0)}ms`,
                            "success"
                        );
                        if (batchScenes.length > 0) {
                            const mergedMap = new Map(
                                (existingScenes || []).map((s) => [String(s?.id || ''), s]).filter(([k]) => Boolean(k))
                            );
                            batchScenes.forEach((item) => {
                                const stableId = String(item?.id || '').trim();
                                if (!stableId) return;
                                const prev = mergedMap.get(stableId) || {};
                                mergedMap.set(stableId, {
                                    ...prev,
                                    id: Number(item.id),
                                    scene_no: item.scene_no,
                                    scene_name: item.scene_name,
                                });
                            });
                            existingScenes = Array.from(mergedMap.values());
                        }
                    } catch (batchErr) {
                        addLog(`Batch scene import failed, fallback to row-by-row import: ${batchErr.message || batchErr}`, "warning");
                        for (const scData of pendingSceneRows) {
                            const currentSceneNo = String(scData.scene_no || '').replace(/\s+/g, '');
                            const match = existingScenes.find(s =>
                                String(s.scene_no || '').replace(/\s+/g, '') === currentSceneNo
                            );
                            if (match) {
                                currentSceneDbId = match.id;
                                const rowRef = importedSceneRows.find((x) => String(x?.scene_no || '').replace(/\s+/g, '') === currentSceneNo);
                                if (rowRef) rowRef.id = match.id;
                                try {
                                    await updateScene(match.id, scData);
                                    importStats.scenesUpdated += 1;
                                    addLog(`Updated existing Scene ${scData.scene_no}`, 'success');
                                } catch (updateErr) {
                                    addLog(`Failed to update existing Scene ${scData.scene_no}: ${updateErr?.message || updateErr}`, 'error');
                                }
                            } else {
                                const newScene = await createScene(activeEpisodeId, scData);
                                currentSceneDbId = newScene.id;
                                const rowRef = importedSceneRows.find((x) => String(x?.scene_no || '').replace(/\s+/g, '') === currentSceneNo);
                                if (rowRef) rowRef.id = newScene.id;
                                createdSceneIds.push(newScene.id);
                                existingScenes.push(newScene);
                                importStats.scenesCreated += 1;
                                addLog(`Created Scene ${scData.scene_no}`, "success");
                            }
                        }
                    }
                }

                // Retry unresolved shots after entire document pass. This covers cases where shot rows
                // appear before scene rows or scene list was stale during first pass.
                if (deferredShots.length > 0) {
                    addLog(`Retrying ${deferredShots.length} deferred shots after scene refresh...`, 'process');
                    const unresolvedAfterLocalPass = [];
                    for (const deferred of deferredShots) {
                        const retryCode = deferred.sceneCode || deferred.shotData?.scene_code || deferred.rawShotId;
                        const sceneMatch = resolveSceneByCode(retryCode);
                        if (sceneMatch?.id) {
                            queueShotItem(sceneMatch.id, deferred.shotData);
                            currentSceneDbId = sceneMatch.id;
                        } else {
                            unresolvedAfterLocalPass.push(deferred);
                        }
                    }

                    if (unresolvedAfterLocalPass.length > 0) {
                        try { existingScenes = await fetchScenes(activeEpisodeId); } catch (e) {}
                        for (const deferred of unresolvedAfterLocalPass) {
                            const retryCode = deferred.sceneCode || deferred.shotData?.scene_code || deferred.rawShotId;
                            const sceneMatch = resolveSceneByCode(retryCode);
                            if (sceneMatch?.id) {
                                queueShotItem(sceneMatch.id, deferred.shotData);
                                currentSceneDbId = sceneMatch.id;
                            } else {
                                const debugCandidates = extractSceneNoCandidates(retryCode).join(', ');
                                const availableSceneNos = existingScenes
                                    .map((s) => String(s?.scene_no || s?.scene_id || s?.id || '').trim())
                                    .filter(Boolean)
                                    .slice(0, 12)
                                    .join(', ');
                                addLog(
                                    `Skipped Shot ${deferred.rawShotId}: No matching Scene found for code '${deferred.sceneCode}' (candidates: ${debugCandidates || 'none'}, available: ${availableSceneNos || 'none'})`,
                                    'warning'
                                );
                            }
                        }
                    }
                }

                if (pendingShotItems.length > 0) {
                    try {
                        const shotBatchResp = await batchCreateShots(activeEpisodeId, pendingShotItems, { recomputeCost: false });
                        importStats.shotsCreated += Number(shotBatchResp?.created || 0);
                        addLog(
                            `Batch shot import done: processed=${Number(shotBatchResp?.processed || pendingShotItems.length)}, created=${Number(shotBatchResp?.created || 0)}, skipped=${Number(shotBatchResp?.skipped || 0)}, elapsed=${Number(shotBatchResp?.elapsed_ms || 0)}ms`,
                            'success'
                        );
                    } catch (shotBatchErr) {
                        addLog(`Batch shot import failed, fallback to row-by-row create: ${shotBatchErr.message || shotBatchErr}`, 'warning');
                        for (const item of pendingShotItems) {
                            try {
                                await createShot(item.scene_id, item.shot);
                                importStats.shotsCreated += 1;
                            } catch (shotErr) {
                                console.error('Shot DB Sync Error', shotErr);
                                addLog(`Failed to create shot ${item?.shot?.shot_id || '(unknown)'}: ${shotErr.message}`, 'error');
                            }
                        }
                    }
                }

                // Update contents separately
                // Removed legacy scene_content/shot_content updates as they are deprecated in backend
                /* 
                const updatePayload = {};
                if (sceneLines.length > 0) { ... }
                */
                
                // Just force refresh
                if (sceneLines.length > 0 || shotLines.length > 0) {
                    changesMade = true;
                    reloadRequired = true;
                }

                if (autoSupplementSceneSubjects && id && importedSceneRows.length > 0) {
                    sceneSubjectAutoSupplementReport = await createMissingSceneSubjectPlaceholders({
                        projectId: id,
                        sceneRows: importedSceneRows,
                        existingEntities: knownEntities,
                        onLog: addLog,
                    });
                    knownEntities = Array.isArray(sceneSubjectAutoSupplementReport?.entities)
                        ? sceneSubjectAutoSupplementReport.entities
                        : knownEntities;

                    const autoCreatedCount = Array.isArray(sceneSubjectAutoSupplementReport?.createdItems)
                        ? sceneSubjectAutoSupplementReport.createdItems.length
                        : 0;
                    const autoFailedCount = Array.isArray(sceneSubjectAutoSupplementReport?.failedItems)
                        ? sceneSubjectAutoSupplementReport.failedItems.length
                        : 0;
                    if (autoCreatedCount > 0) {
                        changesMade = true;
                        addLog(
                            `Auto-supplemented missing scene subjects after import: character=${Number(sceneSubjectAutoSupplementReport?.countsByType?.character || 0)}, prop=${Number(sceneSubjectAutoSupplementReport?.countsByType?.prop || 0)}, environment=${Number(sceneSubjectAutoSupplementReport?.countsByType?.environment || 0)}.`,
                            'success'
                        );
                    }
                    if (autoFailedCount > 0) {
                        addLog(`Scene subject auto-supplement failed for ${autoFailedCount} item(s).`, 'warning');
                    }
                }
             } catch (e) {
                 addLog(`Scene Import Failed: ${e.message}`, "error");
             }
        }

        if (changesMade) {
            setIsImportOpen(false);

            const importedTotal = importedSubjectCounts.character + importedSubjectCounts.prop + importedSubjectCounts.environment + importedSubjectCounts.poster;
            if (importedTotal > 0) {
                setEntitiesRefreshKey((prev) => prev + 1);
                addLog(
                    `Imported subjects summary: character=${importedSubjectCounts.character}, prop=${importedSubjectCounts.prop}, environment=${importedSubjectCounts.environment}, poster=${importedSubjectCounts.poster}.`,
                    'info'
                );
            }

            if (llmFinalReport && importedTotal > 0) {
                const types = ['character', 'prop', 'environment'];
                const mismatches = [];

                for (const type of types) {
                    const expected = llmFinalReport?.[type]?.json_count;
                    if (expected === null || expected === undefined || Number.isNaN(expected)) continue;
                    const actual = importedSubjectCounts[type] || 0;
                    if (actual !== expected) {
                        mismatches.push(`${type}: imported=${actual}, llm_json_count=${expected}`);
                    }
                }

                if (mismatches.length === 0) {
                    addLog('Final Consistency Report check passed: imported subject counts match LLM json_count.', 'success');
                    postImportStatusNote = 'Subject count check passed (matches Final Consistency Report).';
                } else {
                    addLog(`Final Consistency Report check mismatch: ${mismatches.join(' | ')}`, 'warning');
                    postImportStatusNote = `Subject count mismatch: ${mismatches.join(' | ')}`;
                }
            }
            
            // Always refresh episodes to show new scripts/scenes
            const fresh = await fetchEpisodes(id);
            setEpisodes((prev) => mergeEpisodeListWithCachedFields(fresh, prev));

            if (reloadRequired) {
                // Force Overview refresh if needed
                setRefreshKey(prev => prev + 1);
                addLog("Project Settings updated. Refreshing views...", "info");
            }

            try {
                if (id && !skipDbVerify) {
                    const [dbEntitiesRaw, dbScenesRaw] = await Promise.all([
                        fetchEntities(id).catch(() => []),
                        activeEpisodeId ? fetchScenes(activeEpisodeId).catch(() => []) : Promise.resolve([]),
                    ]);
                    const dbEntities = Array.isArray(dbEntitiesRaw) ? dbEntitiesRaw : [];
                    const dbCharacterCount = dbEntities.filter((item) => canonicalSubjectType(item?.type) === 'character').length;
                    const dbPropCount = dbEntities.filter((item) => canonicalSubjectType(item?.type) === 'prop').length;
                    const dbEnvironmentCount = dbEntities.filter((item) => canonicalSubjectType(item?.type) === 'environment').length;
                    dbPersistedCounts = {
                        scenes: {
                            currentEpisode: Array.isArray(dbScenesRaw) ? dbScenesRaw.length : 0,
                        },
                        entities: {
                            total: dbEntities.length,
                            character: dbCharacterCount,
                            prop: dbPropCount,
                            environment: dbEnvironmentCount,
                        },
                    };

                    const createdEntityIdSet = new Set(
                        (Array.isArray(createdSubjectItems) ? createdSubjectItems : [])
                            .map((item) => item?.id)
                            .filter((idValue) => idValue !== null && idValue !== undefined)
                            .map((idValue) => String(idValue))
                    );
                    const createdSceneIdSet = new Set(
                        (Array.isArray(createdSceneIds) ? createdSceneIds : [])
                            .filter((idValue) => idValue !== null && idValue !== undefined)
                            .map((idValue) => String(idValue))
                    );
                    const dbInsertedEntities = dbEntities.filter((item) => createdEntityIdSet.has(String(item?.id)));
                    const dbInsertedScenes = (Array.isArray(dbScenesRaw) ? dbScenesRaw : []).filter((item) => createdSceneIdSet.has(String(item?.id)));

                    const dbInsertedCharacterCount = dbInsertedEntities.filter((item) => canonicalSubjectType(item?.type) === 'character').length;
                    const dbInsertedPropCount = dbInsertedEntities.filter((item) => canonicalSubjectType(item?.type) === 'prop').length;
                    const dbInsertedEnvironmentCount = dbInsertedEntities.filter((item) => canonicalSubjectType(item?.type) === 'environment').length;
                    const dbInsertedPosterCount = dbInsertedEntities.filter((item) => canonicalSubjectType(item?.type) === 'poster').length;

                    dbRunInsertedCounts = {
                        scenes: {
                            created: dbInsertedScenes.length,
                        },
                        entities: {
                            total: dbInsertedEntities.length,
                            character: dbInsertedCharacterCount,
                            prop: dbInsertedPropCount,
                            environment: dbInsertedEnvironmentCount,
                            poster: dbInsertedPosterCount,
                        },
                    };
                    addLog(
                        `[DB Verify] episode_scenes=${dbPersistedCounts.scenes.currentEpisode}, entities_total=${dbPersistedCounts.entities.total} (character=${dbPersistedCounts.entities.character}, prop=${dbPersistedCounts.entities.prop}, environment=${dbPersistedCounts.entities.environment})`,
                        'info'
                    );
                    addLog(
                        `[DB Verify This Run] created_scenes=${dbRunInsertedCounts.scenes.created}, created_entities(new_only)=${dbRunInsertedCounts.entities.total} (character=${dbRunInsertedCounts.entities.character}, prop=${dbRunInsertedCounts.entities.prop}, environment=${dbRunInsertedCounts.entities.environment}, poster=${dbRunInsertedCounts.entities.poster})`,
                        'info'
                    );
                    addLog(
                        `[DB Verify This Run] reused_entities(skipped_existing)=${Array.isArray(skippedSubjectItems) ? skippedSubjectItems.length : 0}`,
                        'info'
                    );
                } else if (skipDbVerify) {
                    addLog('[DB Verify] skipped for fast import path.', 'info');
                }
            } catch (dbCountErr) {
                addLog(`DB verification count query failed: ${dbCountErr?.message || dbCountErr}`, 'warning');
            }

            const importedSubjectsTotal = importedSubjectCounts.character + importedSubjectCounts.prop + importedSubjectCounts.environment;
            const skippedSubjectsTotal = skippedSubjectItems.length;
            const autoSupplementCreatedTotal = Array.isArray(sceneSubjectAutoSupplementReport?.createdItems)
                ? sceneSubjectAutoSupplementReport.createdItems.length
                : 0;
            const autoSupplementFailedTotal = Array.isArray(sceneSubjectAutoSupplementReport?.failedItems)
                ? sceneSubjectAutoSupplementReport.failedItems.length
                : 0;
            const importedScenesTotal = importStats.scenesCreated + importStats.scenesUpdated;
            const summaryLines = [
                'Import Successful!',
                `Subjects: total=${importedSubjectsTotal} (character=${importedSubjectCounts.character}, prop=${importedSubjectCounts.prop}, environment=${importedSubjectCounts.environment}, poster=${importedSubjectCounts.poster})`,
                `Subjects skipped as existing=${skippedSubjectsTotal}`,
                `Scene subject auto-supplement: created=${autoSupplementCreatedTotal}, failed=${autoSupplementFailedTotal}`,
                `Scenes: created=${importStats.scenesCreated}, updated=${importStats.scenesUpdated}, total=${importedScenesTotal}`,
                `Shots: created=${importStats.shotsCreated}`,
                `Script lines: ${importStats.scriptLines}`,
                `JSON blocks detected: ${importStats.jsonBlocks}`,
                `Import mode: requested=${requestedImportType}, effective=${effectiveImportType}`,
                `Parse diagnostics: source=${importDiagnostics.entitiesPayloadSource}, subject_index_rows=${importDiagnostics.subjectIndexTableRows}, subject_index_extracted=${importDiagnostics.subjectIndexExtracted}, generic_json_blocks=${importStats.genericJsonBlocks}`,
                `Markers: script=${importDiagnostics.markers.script}, scene=${importDiagnostics.markers.scene}, shot=${importDiagnostics.markers.shot}`,
            ];
            if (dbPersistedCounts) {
                summaryLines.push(
                    `DB persisted: scenes(current_episode)=${dbPersistedCounts.scenes.currentEpisode}, entities(total=${dbPersistedCounts.entities.total}, character=${dbPersistedCounts.entities.character}, prop=${dbPersistedCounts.entities.prop}, environment=${dbPersistedCounts.entities.environment})`
                );
            }
            if (dbRunInsertedCounts) {
                summaryLines.push(
                    `DB this run inserted: scenes(created=${dbRunInsertedCounts.scenes.created}), entities(created_total=${dbRunInsertedCounts.entities.total}, character=${dbRunInsertedCounts.entities.character}, prop=${dbRunInsertedCounts.entities.prop}, environment=${dbRunInsertedCounts.entities.environment}, poster=${dbRunInsertedCounts.entities.poster})`
                );
            }
            if (postImportStatusNote) summaryLines.push(postImportStatusNote);
            if (!suppressAlerts) {
                alert(summaryLines.join('\n'));
            }
            return {
                ok: true,
                changed: true,
                importedSubjectCounts,
                createdSubjectItems,
                skippedSubjectItems,
                importedSceneRows,
                sceneSubjectAutoSupplementReport,
                dbPersistedCounts,
                dbRunInsertedCounts,
                importStats,
                importDiagnostics,
                postImportStatusNote,
                summaryLines,
            };
        } else {
            const noChangeLines = [
                'Import finished, but no new data was applied.',
                'Please verify table headers and entities JSON keys.',
                `Import mode: requested=${requestedImportType}, effective=${effectiveImportType}`,
                `Parse diagnostics: source=${importDiagnostics.entitiesPayloadSource}, subject_index_rows=${importDiagnostics.subjectIndexTableRows}, subject_index_extracted=${importDiagnostics.subjectIndexExtracted}, generic_json_blocks=${importStats.genericJsonBlocks}`,
                `Markers: script=${importDiagnostics.markers.script}, scene=${importDiagnostics.markers.scene}, shot=${importDiagnostics.markers.shot}`,
            ];
            if (!suppressAlerts) {
                alert(noChangeLines.join('\n'));
            }
            return {
                ok: true,
                changed: false,
                importedSubjectCounts,
                createdSubjectItems,
                skippedSubjectItems,
                importedSceneRows,
                sceneSubjectAutoSupplementReport,
                dbPersistedCounts,
                dbRunInsertedCounts,
                importStats,
                importDiagnostics,
                postImportStatusNote,
            };
        }
    };

    const handleExport = async () => {
        if (isProjectBackupExporting) return;
        addLog("Preparing project export...", "process");
        setIsProjectBackupExporting(true);
        try {
            const exportData = await exportProjectBackup(id);
            const backupTitle = String(exportData?.project?.title || project?.title || id || 'project').trim();
            const jsonString = JSON.stringify(exportData, null, 2);
            const blob = new Blob([jsonString], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `Project_${backupTitle.replace(/[^a-z0-9]/gi, '_')}_Backup.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            addLog("Project backup exported to local disk.", "success");
        } catch (e) {
            console.error(e);
            addLog(`Export failed: ${e.message}`, "error");
            alert(`Failed to export project: ${e?.message || 'Unknown error'}`);
        } finally {
            setIsProjectBackupExporting(false);
        }
    };

    const handleImportBackupClick = () => {
        if (isProjectBackupImporting) return;
        projectBackupFileInputRef.current?.click();
    };

    const handleImportBackupFileChange = async (event) => {
        const file = event?.target?.files?.[0] || null;
        event.target.value = '';
        if (!file) return;
        if (isProjectBackupImporting) return;

        let parsed = null;
        try {
            const rawText = await file.text();
            parsed = JSON.parse(rawText);
        } catch (e) {
            alert(t('备份文件不是有效的 JSON。', 'Backup file is not valid JSON.'));
            return;
        }

        const sourceTitle = String(parsed?.project?.title || '').trim() || file.name.replace(/\.json$/i, '');
        const ok = await confirmUiMessage(t(
            `确认导入项目备份？\n将基于备份新建一个项目：${sourceTitle}`,
            `Import this project backup?\nA new project will be created from: ${sourceTitle}`
        ));
        if (!ok) return;

        setIsProjectBackupImporting(true);
        addLog(`Importing project backup: ${file.name}`, 'process');
        try {
            const res = await importProjectBackup({ backup: parsed });
            const importedProject = res?.project;
            const imported = res?.imported || {};
            addLog(
                `Project backup imported: episodes=${Number(imported?.episodes || 0)}, scenes=${Number(imported?.scenes || 0)}, shots=${Number(imported?.shots || 0)}, entities=${Number(imported?.entities || 0)}, assets=${Number(imported?.assets || 0)}`,
                'success'
            );
            if (importedProject?.id) {
                navigate(`/projects/${importedProject.id}`);
            }
        } catch (e) {
            console.error(e);
            addLog(`Project backup import failed: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
            alert(e?.response?.data?.detail || e?.message || t('项目备份导入失败', 'Failed to import project backup'));
        } finally {
            setIsProjectBackupImporting(false);
        }
    };

    const refreshGenerationJobPool = useCallback(async (override = {}) => {
        const kind = String(override.kind || jobPoolFilterKind || 'all');
        const runningOnly = typeof override.runningOnly === 'boolean' ? override.runningOnly : jobPoolRunningOnly;
        setJobPoolLoading(true);
        try {
            const data = await getGenerationJobPool({
                kind,
                running_only: runningOnly,
                limit: 300,
            });
            setJobPoolData({
                total: Number(data?.total || 0),
                status_counts: data?.status_counts || {},
                items: Array.isArray(data?.items) ? data.items : [],
            });
        } catch (e) {
            addLog(`Failed to load job pool: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setJobPoolLoading(false);
        }
    }, [addLog, jobPoolFilterKind, jobPoolRunningOnly]);

    useEffect(() => {
        if (!isJobPoolOpen) return;
        refreshGenerationJobPool();
    }, [isJobPoolOpen, refreshGenerationJobPool]);

    const handleStopJobFromPool = async (item) => {
        const kind = String(item?.kind || '').trim();
        const jobId = String(item?.job_id || '').trim();
        if (!kind || !jobId) return;
        const ok = await confirmUiMessage(t(
            `确认强制停止任务？\n${kind} / ${jobId}`,
            `Force stop this task?\n${kind} / ${jobId}`
        ));
        if (!ok) return;

        setJobPoolStoppingId(`${kind}:${jobId}`);
        try {
            const res = await stopGenerationJob(kind, jobId, { force: true });
            if (kind === 'video') {
                releaseShotVideoUiByJobId(jobId);
            } else if (kind === 'image') {
                releaseShotImageUiByJobId(jobId);
            }
            addLog(`Job force stopped: ${kind}/${jobId} - ${res?.message || 'ok'}`, 'warning');
            await refreshShots();
            await refreshGenerationJobPool();
        } catch (e) {
            addLog(`Failed to stop job ${kind}/${jobId}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setJobPoolStoppingId('');
        }
    };

    const handleDeleteJobFromPool = async (item) => {
        const kind = String(item?.kind || '').trim();
        const jobId = String(item?.job_id || '').trim();
        if (!kind || !jobId) return;
        const ownerId = Number(item?.user_id || 0) || null;
        const canDelete = isSuperuser || (ownerId !== null && currentUserId !== null && ownerId === currentUserId);
        if (!canDelete) {
            addLog(t('仅可删除自己的任务（超级用户可删除全部）。', 'You can only delete your own jobs (superuser can delete all).'), 'warning');
            return;
        }

        const ok = await confirmUiMessage(t(
            `确认删除任务记录？\n${kind} / ${jobId}\n若任务仍在运行，将一并终止并清除当前页面的挂起状态。`,
            `Delete this job record?\n${kind} / ${jobId}\nIf the job is still running, this will also terminate it and clear the pending UI state.`
        ));
        if (!ok) return;

        const rowKey = `${kind}:${jobId}`;
        setJobPoolDeletingId(rowKey);
        try {
            const res = await deleteGenerationJob(kind, jobId);
            if (kind === 'video') {
                releaseShotVideoUiByJobId(jobId);
            } else if (kind === 'image') {
                releaseShotImageUiByJobId(jobId);
            }
            addLog(`Job deleted: ${kind}/${jobId} - ${res?.message || 'ok'}`, 'warning');
            await refreshShots();
            await refreshGenerationJobPool();
        } catch (e) {
            addLog(`Failed to delete job ${kind}/${jobId}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setJobPoolDeletingId('');
        }
    };

    const isJobPoolItemStoppable = () => {
        return true;
    };

    const runningJobPoolItems = (jobPoolData?.items || []).filter(isJobPoolItemStoppable);
    const parsedStopLimit = Number.parseInt(String(jobPoolStopLimit || '0'), 10);
    const stopAllUsesUnlimited = String(jobPoolStopLimit || '').toLowerCase() === 'all' || !Number.isFinite(parsedStopLimit) || parsedStopLimit <= 0;
    const stopAllTargetItems = stopAllUsesUnlimited ? runningJobPoolItems : runningJobPoolItems.slice(0, parsedStopLimit);

    const handleStopAllJobsFromPool = async () => {
        if (jobPoolStoppingAll) return;
        const candidates = stopAllTargetItems;
        if (!candidates.length) {
            addLog(t('当前没有可停止的运行中任务。', 'No running tasks can be stopped right now.'), 'warning');
            return;
        }

        const limitLabel = stopAllUsesUnlimited ? t('全部', 'all') : String(parsedStopLimit);
        const ok = await confirmUiMessage(t(
            `确认批量强制停止任务？\n将停止前 ${limitLabel} 个（本次 ${candidates.length} / 可停止 ${runningJobPoolItems.length}）。`,
            `Force stop tasks in batch?\nWill stop first ${limitLabel} (this run ${candidates.length} / stoppable ${runningJobPoolItems.length}).`
        ));
        if (!ok) return;

        setJobPoolStoppingAll(true);
        setJobPoolStoppingId('');
        let successCount = 0;
        let failedCount = 0;

        try {
            for (const item of candidates) {
                const kind = String(item?.kind || '').trim();
                const jobId = String(item?.job_id || '').trim();
                if (!kind || !jobId) {
                    failedCount += 1;
                    continue;
                }
                try {
                    await stopGenerationJob(kind, jobId, { force: true });
                    successCount += 1;
                } catch (e) {
                    failedCount += 1;
                    addLog(`Failed to stop job ${kind}/${jobId}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
                }
            }

            if (failedCount > 0) {
                addLog(t(
                    `批量停止完成：成功 ${successCount}，失败 ${failedCount}（目标 ${candidates.length}）。`,
                    `Batch stop completed: ${successCount} succeeded, ${failedCount} failed (target ${candidates.length}).`
                ), 'warning');
            } else {
                addLog(t(
                    `批量停止完成：共停止 ${successCount} 个任务（目标 ${candidates.length}）。`,
                    `Batch stop completed: ${successCount} tasks stopped (target ${candidates.length}).`
                ), 'warning');
            }
        } finally {
            setJobPoolStoppingAll(false);
            await refreshGenerationJobPool();
        }
    };

    const handleStopAllJobsFromApi = async () => {
        if (jobPoolStoppingAllApi) return;
        const targetKind = String(jobPoolFilterKind || 'all').trim().toLowerCase() || 'all';
        const ok = await confirmUiMessage(t(
            `确认调用“停止全部任务”接口？\n范围：${targetKind}`,
            `Call stop-all endpoint now?\nScope: ${targetKind}`
        ));
        if (!ok) return;

        setJobPoolStoppingAllApi(true);
        try {
            const res = await stopAllGenerationJobs(targetKind, { force: true });
            const stopped = Number(res?.stopped || 0);
            addLog(t(
                `已请求停止全部任务：kind=${targetKind}，停止 ${stopped} 个。`,
                `Stop-all requested: kind=${targetKind}, stopped ${stopped}.`
            ), 'warning');
        } catch (e) {
            addLog(`Failed to stop-all (${targetKind}): ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setJobPoolStoppingAllApi(false);
            await refreshGenerationJobPool();
        }
    };

    const getJobPoolScopeText = useCallback((item) => {
        if (!item || typeof item !== 'object') return '-';
        const metadata = (item?.metadata && typeof item.metadata === 'object') ? item.metadata : {};
        const payload = (item?.payload && typeof item.payload === 'object') ? item.payload : {};
        const context = (item?.context && typeof item.context === 'object') ? item.context : {};
        const ownerPage = String(
            item?.ownerPage
            || metadata?.ownerPage
            || payload?.ownerPage
            || context?.ownerPage
            || ''
        ).trim();
        const ownerScopeType = String(
            item?.ownerScopeType
            || metadata?.ownerScopeType
            || payload?.ownerScopeType
            || context?.ownerScopeType
            || ''
        ).trim();
        const ownerScopeId = String(
            item?.ownerScopeId
            || metadata?.ownerScopeId
            || payload?.ownerScopeId
            || context?.ownerScopeId
            || ''
        ).trim();
        const ownerSceneId = String(
            item?.ownerSceneId
            || metadata?.ownerSceneId
            || payload?.ownerSceneId
            || context?.ownerSceneId
            || ''
        ).trim();
        const ownerShotId = String(
            item?.ownerShotId
            || metadata?.ownerShotId
            || payload?.ownerShotId
            || context?.ownerShotId
            || ''
        ).trim();
        const ownerEntityId = String(
            item?.ownerEntityId
            || metadata?.ownerEntityId
            || payload?.ownerEntityId
            || context?.ownerEntityId
            || ''
        ).trim();
        const ownerMediaKind = String(
            item?.ownerMediaKind
            || metadata?.ownerMediaKind
            || payload?.ownerMediaKind
            || context?.ownerMediaKind
            || ''
        ).trim();
        const jobKind = String(
            item?.jobKind
            || metadata?.jobKind
            || payload?.jobKind
            || context?.jobKind
            || ''
        ).trim();

        const episodeId = Number(
            item?.episode_id
            || metadata?.episode_id
            || payload?.episode_id
            || context?.episode_id
            || 0
        );
        const currentSceneLabel = String(
            item?.current_scene_label
            || metadata?.current_scene_label
            || payload?.current_scene_label
            || context?.current_scene_label
            || ''
        ).trim();
        const sceneId = Number(
            item?.scene_id
            || metadata?.scene_id
            || payload?.scene_id
            || context?.scene_id
            || 0
        );
        const shotId = Number(
            item?.shot_id
            || metadata?.shot_id
            || payload?.shot_id
            || context?.shot_id
            || 0
        );
        const sceneIds =
            (Array.isArray(payload?.scene_ids) && payload.scene_ids.length > 0 ? payload.scene_ids : null)
            || (Array.isArray(metadata?.scene_ids) && metadata.scene_ids.length > 0 ? metadata.scene_ids : null)
            || (Array.isArray(context?.scene_ids) && context.scene_ids.length > 0 ? context.scene_ids : null)
            || [];
        const shotIds =
            (Array.isArray(payload?.shot_ids) && payload.shot_ids.length > 0 ? payload.shot_ids : null)
            || (Array.isArray(metadata?.shot_ids) && metadata.shot_ids.length > 0 ? metadata.shot_ids : null)
            || (Array.isArray(context?.shot_ids) && context.shot_ids.length > 0 ? context.shot_ids : null)
            || [];

        const chunks = [];
        if (ownerPage) chunks.push(`page:${ownerPage}`);
        if (ownerScopeType && ownerScopeId) chunks.push(`${ownerScopeType}:${ownerScopeId}`);
        if (ownerSceneId) chunks.push(`scene:${ownerSceneId}`);
        if (ownerShotId) chunks.push(`shot:${ownerShotId}`);
        if (ownerEntityId) chunks.push(`entity:${ownerEntityId}`);
        if (ownerMediaKind) chunks.push(`media:${ownerMediaKind}`);
        if (jobKind) chunks.push(`job:${jobKind}`);
        if (Number.isFinite(episodeId) && episodeId > 0) chunks.push(`EP:${episodeId}`);
        if (currentSceneLabel) chunks.push(`${t('当前场景', 'Current Scene')}:${currentSceneLabel}`);
        if (Number.isFinite(sceneId) && sceneId > 0) chunks.push(`SC:${sceneId}`);
        if (sceneIds.length > 0) chunks.push(`SCx${sceneIds.length}`);
        if (Number.isFinite(shotId) && shotId > 0) chunks.push(`SH:${shotId}`);
        if (shotIds.length > 0) chunks.push(`SHx${shotIds.length}`);
        return chunks.length > 0 ? chunks.join(' · ') : '-';
    }, [t]);

    const getJobPoolOwnerPageText = useCallback((item) => {
        if (!item || typeof item !== 'object') return '-';
        const metadata = (item?.metadata && typeof item.metadata === 'object') ? item.metadata : {};
        const payload = (item?.payload && typeof item.payload === 'object') ? item.payload : {};
        const context = (item?.context && typeof item.context === 'object') ? item.context : {};
        const ownerPage = String(
            item?.ownerPage
            || metadata?.ownerPage
            || payload?.ownerPage
            || context?.ownerPage
            || ''
        ).trim();
        if (ownerPage === 'subject-library') return t('主体页', 'Subject Library');
        if (ownerPage === 'shot-editor') return t('镜头页', 'Shot Editor');
        if (ownerPage) return ownerPage;
        return t('未标记', 'Unscoped');
    }, [t]);

    // Lazy load full episode data if missing
    useEffect(() => {
        if (!activeEpisodeId) return;
        const ep = episodes.find(e => String(e.id) === String(activeEpisodeId));
        if (!ep) return;
        if (!ep._fullLoaded) {
            fetchEpisode(activeEpisodeId).then(fullEp => {
                setEpisodes(prev => sortEpisodesForEditor(prev.map(e => String(e.id) === String(activeEpisodeId) ? { ...fullEp, _fullLoaded: true } : e)));
            }).catch(err => {
                console.error("Failed to fetch full episode", err);
            });
        }
    }, [activeEpisodeId, episodes, sortEpisodesForEditor]);

    const activeEpisode = episodes.find(e => String(e.id) === String(activeEpisodeId)) || null;
    const activeEpisodeIndex = activeEpisode ? episodes.findIndex((episode) => String(episode.id) === String(activeEpisode.id)) : -1;
    const getEpisodeDisplayFallbackNumber = useCallback((index) => {
        return index >= 0 ? episodes.length - index : null;
    }, [episodes.length]);
    const getEpisodeDropdownLabel = useCallback((episode, index) => buildEpisodeDisplayLabel({
        episodeNumber: resolveEpisodeDisplayNumber(episode),
        title: episode?.title,
        fallbackNumber: getEpisodeDisplayFallbackNumber(index),
    }), [getEpisodeDisplayFallbackNumber, resolveEpisodeDisplayNumber]);
    const activeEpisodeLabel = activeEpisode
        ? getEpisodeDropdownLabel(activeEpisode, activeEpisodeIndex)
        : t('选择剧集', 'Select Episode');

    const MENU_ITEMS = [
    { id: 'overview', label: '项目信息', icon: Briefcase },
    { id: 'script', label: '剧本', icon: FileText },
    { id: 'scenes', label: '场景', icon: ImageIcon },
    { id: 'subjects', label: '资产', icon: Users },
    { id: 'shots', label: '分镜', icon: Film },
    { id: 'montage', label: '剪辑', icon: Video }
];
    const activeMenuItem = MENU_ITEMS.find((item) => item.id === activeTab) || MENU_ITEMS[0];

    const trackMenuAction = (menuKey, menuLabel, actionFn) => {
        const page = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        void recordSystemLogAction({
            action: 'MENU_CLICK',
            menu_key: menuKey,
            menu_label: menuLabel,
            page,
        });

        try {
            const actionResult = actionFn?.();
            if (actionResult && typeof actionResult.then === 'function') {
                actionResult
                    .then(() => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'success',
                        });
                    })
                    .catch((error) => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'failed',
                            details: error?.message || 'unknown error',
                        });
                    });
                return;
            }

            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'success',
            });
        } catch (error) {
            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'failed',
                details: error?.message || 'unknown error',
            });
            throw error;
        }
    };

    const [tabResetKey, setTabResetKey] = useState(0);

    const navigateTopMenu = (item) => {
        if (item.id === activeTab) {
            setTabResetKey(prev => prev + 1);
        }
        if (item.id === 'shots') {
            setEditingShot(null);
        }
        setActiveTab(item.id);
    };



    return (
        <div className="flex flex-col h-screen w-full bg-background overflow-hidden relative text-foreground">
            {/* Top Navigation Bar - Compact */}
            <div className="px-3 py-3 md:h-12 md:px-4 md:py-0 border-b border-white/10 bg-[#09090b] flex flex-col md:flex-row md:items-center md:justify-between gap-3 shrink-0 z-40 relative">
                {/* Left: Project Info & Episode Selector */}
                <div className="flex items-center gap-3 md:gap-4 min-w-0 w-full md:w-auto">
                     {/* Back Button if in embedded mode */}
                     {onClose && (
                                <button onClick={() => trackMenuAction('editor.back.embedded', t('返回项目', 'Back to Projects'), onClose)} className="p-1.5 hover:bg-white/10 rounded-md text-muted-foreground hover:text-white transition-colors mr-2">
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                     )}
                     <div className="flex items-center gap-3 md:gap-4 min-w-0 w-full md:w-auto">
                        <h1 className="font-bold text-sm tracking-wide text-white flex items-center gap-2 min-w-0">
                            <span className="text-primary hover:underline cursor-pointer truncate">{project ? project.title : `Project #${id}`}</span>
                        </h1>
                        
                        {/* Episode Dropdown */}
                        <div className="relative flex-1 md:flex-none min-w-0">
                            <button 
                                onClick={() => trackMenuAction('editor.episode.dropdown_toggle', t('剧集菜单', 'Episode Menu'), () => setIsEpisodeMenuOpen(!isEpisodeMenuOpen))}
                                className="w-full md:w-[260px] flex items-center justify-between gap-2 px-3 py-2 md:py-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-md text-xs font-medium text-white transition-colors"
                            >
                                <span className="truncate text-left">{activeEpisodeLabel}</span>
                                <ChevronDown className="w-3 h-3 text-muted-foreground" />
                            </button>

                            {/* Dropdown Menu */}
                            {isEpisodeMenuOpen && (
                                <div className="absolute top-full left-0 mt-2 w-full md:w-[320px] bg-[#09090b] border border-white/10 rounded-lg shadow-xl py-1 z-50 max-h-[60vh] overflow-y-auto">
                                    {episodes.map((ep, index) => (
                                        <div 
                                            key={ep.id}
                                            className={`px-3 py-2 text-xs flex justify-between items-center group cursor-pointer ${String(activeEpisodeId) === String(ep.id) ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:bg-white/5 hover:text-white'}`}
                                            onClick={() => {
                                                trackMenuAction('editor.episode.select', getEpisodeDropdownLabel(ep, index), () => {
                                                    setActiveEpisodeId(ep.id);
                                                    setIsEpisodeMenuOpen(false);
                                                });
                                            }}
                                        >
                                            <span className="truncate flex-1 pr-2" title={getEpisodeDropdownLabel(ep, index)}>
                                                {getEpisodeDropdownLabel(ep, index)}
                                            </span>
                                            <button 
                                                onClick={(e) => handleDeleteEpisode(e, ep.id)}
                                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 hover:text-red-500 rounded"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    ))}
                                    <div className="border-t border-white/10 mt-1 pt-1 px-1">
                                         <button 
                                            onClick={() => trackMenuAction('editor.episode.create', t('新建分集', 'New Episode'), handleCreateEpisode)}
                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground hover:text-white hover:bg-white/5 rounded transition-colors"
                                        >
                                            <Plus className="w-3 h-3" /> {t('新建分集', 'New Episode')}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                     </div>
                </div>

                {/* Center: Navigation Menu */}
                <div className="w-full md:flex-1 md:min-w-0">
                    <div className="md:hidden mb-2">
                        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/80">
                            {t('当前模块', 'Current Section')}
                        </label>
                        <select
                            value={activeMenuItem?.id || activeTab}
                            onChange={(e) => navigateTopMenu(MENU_ITEMS.find((item) => item.id === e.target.value))}
                            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none transition-colors focus:border-primary/40"
                        >
                            {MENU_ITEMS.map((item) => (
                                <option key={`editor-top-menu-${item.id}`} value={item.id}>{item.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="hidden md:block overflow-x-auto no-scrollbar">
                        <div className="flex justify-center items-center bg-transparent min-w-max w-full">
                            {MENU_ITEMS.map(item => {
                                const Icon = item.icon;
                                const isActive = activeTab === item.id;
                                return (
                                    <button
                                        key={item.id}
                                        onClick={() => navigateTopMenu(item)}
                                        className={`shrink-0 flex items-center gap-2 px-4 py-1.5 text-xs font-bold transition-all relative ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-white'}`}
                                    >
                                        
                                        <Icon className="w-3.5 h-3.5" />
                                        {item.label}
                                        {isActive && <div className="absolute bottom-[-13px] left-0 right-0 h-[2px] bg-primary shadow-[0_0_10px_rgba(255,255,255,0.5)]"></div>}
                                    </button>
                                )
                            })}
                        </div>
                    </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 md:gap-3 flex-wrap md:flex-nowrap justify-end w-full md:w-auto">
                    <button
                        onClick={() => {
                            trackMenuAction('editor.action.generator', t('生成器', 'Generator'), () => setActiveTab('generator'));
                        }}
                        className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${activeTab === 'generator' ? 'text-primary bg-white/10' : 'text-muted-foreground hover:text-white hover:bg-white/10'}`}
                        title={t('生成器', 'Generator')}
                    >
                        <Wand2 className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('剧本生成', 'Scripts Gen')}</span>
                        
                    </button>
                    <button
                        onClick={() => trackMenuAction('editor.ui_language.toggle', t('切换界面语言', 'Toggle UI Language'), () => setUiLang(prev => prev === 'zh' ? 'en' : 'zh'))}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5"
                        title={t('切换到英文界面', 'Switch to Chinese UI')}
                    >
                        <Languages className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{uiLang === 'zh' ? '中文' : 'EN'}</span>
                    </button>
                    <button
                        onClick={() => {
                            trackMenuAction('editor.back.projects', t('返回项目', 'Back to Projects'), () => {
                                const snapshot = persistProjectReturnSnapshot();
                                if (onClose) {
                                    onClose(snapshot);
                                    return;
                                }
                                navigate('/projects');
                            });
                        }}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5"
                        title={t('返回项目列表', 'Back to Projects')}
                    >
                        <ArrowLeft className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('返回项目', 'Back to Projects')}</span>
                    </button>
                    
                    <button
                        onClick={() => {
                            trackMenuAction('editor.action.project_backup_export', t('导出备份', 'Export Backup'), handleExport);
                        }}
                        disabled={isProjectBackupExporting}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t('导出当前项目完整备份', 'Export full backup for current project')}
                    >
                        {isProjectBackupExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        <span className="text-xs font-medium hidden sm:block">{t('导出备份', 'Export Backup')}</span>
                    </button>

                    <button
                        onClick={() => {
                            trackMenuAction('editor.action.project_backup_import', t('导入备份', 'Import Backup'), handleImportBackupClick);
                        }}
                        disabled={isProjectBackupImporting}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t('从备份文件新建项目', 'Create a new project from backup file')}
                    >
                        {isProjectBackupImporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        <span className="text-xs font-medium hidden sm:block">{t('导入备份', 'Import Backup')}</span>
                    </button>

                    <button
                        onClick={() => {
                            trackMenuAction('editor.action.job_pool', t('任务池', 'Job Pool'), () => setIsJobPoolOpen(true));
                        }}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5"
                        title={t('全局任务池', 'Global Job Pool')}
                    >
                        <Layers className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('任务池', 'Job Pool')}</span>
                    </button>

                    <button
                        onClick={() => setTrashModalOpen(true)}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center justify-center"
                        title={t('回收站', 'Recycle Bin')}
                        aria-label={t('回收站', 'Recycle Bin')}
                    >
                        <RotateCcw className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => {
                            trackMenuAction('editor.action.settings', t('设置', 'Settings'), () => {
                                persistProjectReturnSnapshot();
                                const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
                                window.location.assign(`/settings?tab=default-api-activation&return_to=${returnTo}`);
                            });
                        }}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors"
                        title={t('设置', 'Settings')}
                    >
                        <SettingsIcon className="w-4 h-4" />
                    </button>
                </div>
            </div>

            <input
                ref={projectBackupFileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={handleImportBackupFileChange}
            />

            {/* Compact Project Status and Cost Bar */}
            <ProjectStatusBar 
                activeTab={activeTab} 
                workflowStage={project?.global_info?.workflow_stage}
                totalProjectCost={projectBillingStats.total_cost}
                userCost={projectBillingStats.user_cost}
                userBalance={currentUserCredits}
                t={t}
                hasAssets={project?.global_info?.has_existing_assets === true}
                lensPreference={project?.global_info?.lens_preference}
                videoGenPreference={project?.global_info?.video_generation_preference}
            />

            {/* Main Content Area */}
            <div className="flex-1 overflow-hidden relative bg-background">
                <div className="h-full overflow-y-auto custom-scrollbar p-0">
                    <div className="animate-in fade-in duration-300 min-h-full">
                        {isInitializing ? (
                            <div className="flex-1 flex flex-col items-center justify-center h-[50vh]">
                                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }} className="mb-4">
                                    <Loader2 className="h-8 w-8 text-primary opacity-80" />
                                </motion.div>
                                <div className="text-white/60 text-sm font-medium tracking-wide uppercase animate-pulse">
                                    {t('正在加载', 'Loading')}...
                                </div>
                            </div>
                        ) : (
                        <React.Suspense fallback={<div className="flex-1 flex items-center justify-center h-[50vh]"><Loader2 className="h-8 w-8 text-primary animate-spin" /></div>}>
                            {EPISODE_REQUIRED_TABS.has(activeTab) && !activeEpisode && isEpisodesLoading ? (
                                <div className="flex-1 flex flex-col items-center justify-center h-[50vh]">
                                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }} className="mb-4">
                                        <Loader2 className="h-8 w-8 text-primary opacity-80" />
                                    </motion.div>
                                    <div className="text-white/60 text-sm font-medium tracking-wide uppercase animate-pulse">
                                        {t('正在加载分集', 'Loading episodes')}...
                                    </div>
                                </div>
                            ) : (
                                <>
                            {activeTab === 'overview' && (
                                <>
                                    <ProjectOverview
                                        id={id}
                                        project={project}
                                        key={refreshKey}
                                        episodes={episodes}
                                        uiLang={uiLang}
                                        mode="overview"
                                        onProjectUpdate={loadProjectData}
                                        onRefreshEpisodes={refreshEpisodesForEditor}
                                        onTabChange={setActiveTab}
                                        onJumpToEpisode={(episodeId, options = {}) => {
                                            const jump = () => {
                                                setActiveEpisodeId(episodeId);
                                                setActiveTab('script');
                                            };
                                            if (options?.forceReload) {
                                                void reloadEpisodeIntoState(episodeId)
                                                    .then(jump)
                                                    .catch((err) => {
                                                        console.error('Failed to reload episode after jump', err);
                                                        jump();
                                                    });
                                                return;
                                            }
                                            jump();
                                        }}
                                    />
                                    <EpisodeInfo
                                        episode={activeEpisode}
                                        onUpdate={handleUpdateEpisodeInfo}
                                        project={project}
                                        projectId={id}
                                        uiLang={uiLang}
                                        mergedSimplified={true}
                                    />
                                </>
                            )}
                            {activeTab === 'generator' && (
                                <ProjectOverview
                                    id={id}
                                    project={project}
                                    key={`generator-${refreshKey}`}
                                    episodes={episodes}
                                    uiLang={uiLang}
                                    mode="generator"
                                    onProjectUpdate={loadProjectData}
                                    onRefreshEpisodes={refreshEpisodesForEditor}
                                    onTabChange={setActiveTab}
                                    onJumpToEpisode={(episodeId, options = {}) => {
                                        const jump = () => {
                                            setActiveEpisodeId(episodeId);
                                            setActiveTab('script');
                                        };
                                        if (options?.forceReload) {
                                            void reloadEpisodeIntoState(episodeId)
                                                .then(jump)
                                                .catch((err) => {
                                                    console.error('Failed to reload episode after jump', err);
                                                    jump();
                                                });
                                            return;
                                        }
                                        jump();
                                    }}
                                />
                            )}
                            {activeTab === 'script' && <ScriptEditor key={`script-${activeEpisode?.id || 'none'}-${tabResetKey}`} activeEpisode={activeEpisode} projectId={id} project={project} onUpdateScript={handleUpdateScript} onUpdateEpisodeInfo={handleUpdateEpisodeInfo} onRefreshEpisodes={refreshEpisodesForEditor} onLog={addLog} onImportText={handleImport} onSwitchToScenes={() => setActiveTab('scenes')} assetRerunRequest={assetRerunRequest} onAssetRerunRequestConsumed={() => setAssetRerunRequest(null)} uiLang={uiLang} />}
                            {activeTab === 'subjects' && <SubjectLibrary key={`subjects-${activeEpisode?.id || 'none'}-${tabResetKey}-${entitiesRefreshKey}`} projectId={id} project={project} currentEpisode={activeEpisode} uiLang={uiLang} userBatchParallelLimit={userBatchParallelLimit} onImportText={handleImport} />}
                            {activeTab === 'scenes' && (
                                <ErrorBoundary
                                    fallbackRender={({ resetErrorBoundary }) => (
                                        <div className="flex flex-col items-center justify-center h-[50vh] gap-3 p-6 text-center">
                                            <AlertTriangle className="h-8 w-8 text-yellow-400" />
                                            <div className="text-sm text-white/80">{t('场景页加载失败', 'Failed to load Scenes tab')}</div>
                                            <button
                                                type="button"
                                                className="px-3 py-1.5 rounded-lg bg-white/10 text-sm hover:bg-white/20"
                                                onClick={resetErrorBoundary}
                                            >
                                                {t('重试', 'Retry')}
                                            </button>
                                        </div>
                                    )}
                                >
                                    <SceneManager key={`scenes-${activeEpisode?.id || 'none'}-${tabResetKey}`} activeEpisode={activeEpisode} projectId={id} project={project} onLog={addLog} onImportText={handleImport} onSwitchToShots={(sceneId) => {
                                        if (sceneId) {
                                            setShotsFocusRequest({ sceneId: String(sceneId), nonce: Date.now() });
                                        }
                                        setActiveTab('shots');
                                    }} onSwitchToScriptAssetRerun={(patch) => {
                                        setAssetRerunRequest({ ...(patch && typeof patch === 'object' ? patch : {}), nonce: Date.now() });
                                        setActiveTab('script');
                                    }} uiLang={uiLang} />
                                </ErrorBoundary>
                            )}
                            {activeTab === 'shots' && <ShotsView key={`shots-${activeEpisode?.id || 'none'}-${tabResetKey}`} activeEpisode={activeEpisode} projectId={id} project={project} onLog={addLog} editingShot={editingShot} setEditingShot={setEditingShot} isSuperuser={isSuperuser} uiLang={uiLang} focusRequest={shotsFocusRequest} restoreEditingShotId={initialEditingShotId} userBatchParallelLimit={userBatchParallelLimit} />}
                            {activeTab === 'montage' && <VideoStudio key={`montage-${activeEpisode?.id || 'none'}-${tabResetKey}`} activeEpisode={activeEpisode} projectId={id} onLog={addLog} />}
                                </>
                            )}
                        </React.Suspense>
                        )}
                    </div>
                </div>
            </div>

            <ImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} onImport={handleImport} project={project} activeEpisodeId={activeEpisode?.id || null} uiLang={uiLang} />

            {isJobPoolOpen && (
                <div className="fixed inset-0 z-[110] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setIsJobPoolOpen(false)}>
                    <div className="bg-[#09090b] border border-white/10 rounded-xl w-full max-w-5xl max-h-[88vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
                        <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between gap-3">
                            <div>
                                <div className="text-sm font-bold text-white">{t('全局任务池', 'Global Job Pool')}</div>
                                <div className="text-[11px] text-muted-foreground">{t('可查询并强制停止 image/video 及批处理任务。', 'Query and force-stop async image/video and batch tasks.')}</div>
                            </div>
                            <button className="p-2 rounded hover:bg-white/10" onClick={() => setIsJobPoolOpen(false)}><X size={16} /></button>
                        </div>

                        <div className="px-4 py-3 border-b border-white/10 flex flex-wrap items-center gap-2 text-xs">
                            <select
                                value={jobPoolFilterKind}
                                onChange={(e) => setJobPoolFilterKind(e.target.value)}
                                className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white"
                            >
                                <option value="all">all</option>
                                <option value="image">image</option>
                                <option value="video">video</option>
                                <option value="episode-scenes">episode-scenes</option>
                                <option value="episode-scripts">episode-scripts</option>
                                <option value="scene-ai-shots-batch">scene-ai-shots-batch</option>
                                <option value="shot-media-batch">shot-media-batch</option>
                            </select>
                            <label className="flex items-center gap-1 text-muted-foreground">
                                <input
                                    type="checkbox"
                                    checked={jobPoolRunningOnly}
                                    onChange={(e) => setJobPoolRunningOnly(e.target.checked)}
                                />
                                {t('仅运行中', 'Running only')}
                            </label>
                            <button
                                onClick={() => refreshGenerationJobPool()}
                                disabled={jobPoolLoading}
                                className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-white flex items-center gap-1 disabled:opacity-50"
                            >
                                {jobPoolLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />} {t('刷新', 'Refresh')}
                            </button>
                            <button
                                onClick={handleStopAllJobsFromPool}
                                disabled={jobPoolStoppingAll || stopAllTargetItems.length === 0}
                                className={`px-3 py-1.5 rounded text-white flex items-center gap-1 disabled:opacity-50 ${jobPoolStoppingAll ? 'bg-red-500/30' : 'bg-red-500/20 hover:bg-red-500/30'}`}
                                title={t('按列表批量强制停止任务', 'Force stop tasks in current list')}
                            >
                                {jobPoolStoppingAll ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                                {jobPoolStoppingAll ? t('批量强停中...', 'Force stopping...') : t('批量强制停止', 'Batch Force Stop')}
                            </button>
                            <button
                                onClick={handleStopAllJobsFromApi}
                                disabled={jobPoolStoppingAllApi}
                                className={`px-3 py-1.5 rounded text-white flex items-center gap-1 disabled:opacity-50 ${jobPoolStoppingAllApi ? 'bg-red-600/40' : 'bg-red-600/25 hover:bg-red-600/35'}`}
                                title={t('直接调用后端强制 stop-all 接口', 'Directly call backend force stop-all endpoint')}
                            >
                                {jobPoolStoppingAllApi ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                                {jobPoolStoppingAllApi ? t('接口强停中...', 'Force stopping via API...') : t('强制停止全部（接口）', 'Force Stop All (API)')}
                            </button>
                            <label className="flex items-center gap-1 text-muted-foreground">
                                {t('阈值', 'Limit')}
                                <select
                                    value={jobPoolStopLimit}
                                    onChange={(e) => setJobPoolStopLimit(e.target.value)}
                                    className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white"
                                    disabled={jobPoolStoppingAll || jobPoolStoppingAllApi}
                                >
                                    <option value="10">10</option>
                                    <option value="20">20</option>
                                    <option value="50">50</option>
                                    <option value="100">100</option>
                                    <option value="all">{t('全部', 'All')}</option>
                                </select>
                            </label>
                            <div className="w-full md:w-auto md:ml-auto text-muted-foreground">
                                {t('任务数', 'Tasks')}: <b className="text-white">{Number(jobPoolData?.total || 0)}</b>
                                <span className="ml-3">{t('可停止', 'Stoppable')}: <b className="text-white">{runningJobPoolItems.length}</b></span>
                                <span className="ml-3">{t('本次目标', 'Target now')}: <b className="text-white">{stopAllTargetItems.length}</b></span>
                            </div>
                        </div>

                        <div className="px-4 py-2 text-[11px] text-muted-foreground border-b border-white/10">
                            {Object.entries(jobPoolData?.status_counts || {}).map(([key, value]) => `${key}:${value}`).join(' · ') || '-'}
                        </div>

                        <div className="flex-1 overflow-auto custom-scrollbar">
                            <div className="md:hidden p-3 space-y-3">
                                {(jobPoolData?.items || []).map((item) => {
                                    const rowKey = `${item.kind}:${item.job_id}`;
                                    const stopping = jobPoolStoppingId === rowKey;
                                    const canStop = isJobPoolItemStoppable(item);
                                    const deleting = jobPoolDeletingId === rowKey;
                                    const ownerId = Number(item?.user_id || 0) || null;
                                    const canDelete = isSuperuser || (ownerId !== null && currentUserId !== null && ownerId === currentUserId);
                                    return (
                                        <div key={`mobile-${rowKey}`} className="bg-white/5 border border-white/10 rounded-lg p-3 space-y-2.5">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="text-[12px] font-semibold text-white/90 break-all">{item.kind}</div>
                                                <span className="text-[11px] px-2.5 py-1 rounded bg-white/10 border border-white/10 text-white/80">{item.status || '-'}</span>
                                            </div>
                                            <div className="text-[12px] font-mono text-white/80 break-all">{item.job_id || '-'}</div>
                                            <div className="text-[11px] text-cyan-200/80">{getJobPoolOwnerPageText(item)}</div>
                                            <div className="text-[11px] text-white/70 break-all">{getJobPoolScopeText(item)}</div>
                                            <div className="text-[11px] text-muted-foreground">{item.created_at || '-'}</div>
                                            {item.error ? (
                                                <div className="text-[11px] text-amber-300/80 bg-black/30 border border-white/10 rounded px-2.5 py-1.5 break-all">{item.error}</div>
                                            ) : null}
                                            <div className="flex justify-end">
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        onClick={() => handleStopJobFromPool(item)}
                                                        disabled={stopping || deleting || jobPoolStoppingAll || !canStop}
                                                        className={`px-3 py-2 rounded-md text-[12px] font-semibold ${(stopping || deleting || jobPoolStoppingAll || !canStop) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                                    >
                                                        {stopping ? t('停止中...', 'Stopping...') : t('强制停止', 'Force Stop')}
                                                    </button>
                                                    {canDelete && (
                                                        <button
                                                            onClick={() => handleDeleteJobFromPool(item)}
                                                            disabled={stopping || deleting || jobPoolStoppingAll}
                                                            className={`px-3 py-2 rounded-md text-[12px] font-semibold ${(stopping || deleting || jobPoolStoppingAll) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-orange-500/20 text-orange-200 hover:bg-orange-500/30'}`}
                                                        >
                                                            {deleting ? t('删除中...', 'Deleting...') : t('删除', 'Delete')}
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {(!jobPoolData?.items || jobPoolData.items.length === 0) && (
                                    <div className="px-3 py-8 text-center text-muted-foreground text-xs">{t('暂无任务', 'No tasks')}</div>
                                )}
                            </div>
                            <table className="hidden md:table w-full min-w-[760px] text-xs">
                                <thead className="sticky top-0 bg-[#111] border-b border-white/10">
                                    <tr className="text-muted-foreground">
                                        <th className="px-3 py-2 text-left">kind</th>
                                        <th className="px-3 py-2 text-left">job_id</th>
                                        <th className="px-3 py-2 text-left">status</th>
                                        <th className="hidden lg:table-cell px-3 py-2 text-left">page</th>
                                        <th className="hidden md:table-cell px-3 py-2 text-left">user</th>
                                        <th className="hidden lg:table-cell px-3 py-2 text-left">scope</th>
                                        <th className="px-3 py-2 text-left">created_at</th>
                                        <th className="hidden lg:table-cell px-3 py-2 text-left">error</th>
                                        <th className="px-3 py-2 text-right">action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(jobPoolData?.items || []).map((item) => {
                                        const rowKey = `${item.kind}:${item.job_id}`;
                                        const stopping = jobPoolStoppingId === rowKey;
                                        const canStop = isJobPoolItemStoppable(item);
                                        const deleting = jobPoolDeletingId === rowKey;
                                        const ownerId = Number(item?.user_id || 0) || null;
                                        const canDelete = isSuperuser || (ownerId !== null && currentUserId !== null && ownerId === currentUserId);
                                        return (
                                            <tr key={rowKey} className="border-b border-white/5 hover:bg-white/5">
                                                <td className="px-3 py-2 text-white/80">{item.kind}</td>
                                                <td className="px-3 py-2 font-mono text-[11px] text-white/80">{item.job_id}</td>
                                                <td className="px-3 py-2 text-white">{item.status}</td>
                                                <td className="hidden lg:table-cell px-3 py-2 text-cyan-200/80">{getJobPoolOwnerPageText(item)}</td>
                                                <td className="hidden md:table-cell px-3 py-2 text-white/70">{item.username || item.user_id || '-'}</td>
                                                <td className="hidden lg:table-cell px-3 py-2 text-white/70 max-w-[280px] truncate" title={getJobPoolScopeText(item)}>{getJobPoolScopeText(item)}</td>
                                                <td className="px-3 py-2 text-white/60">{item.created_at || '-'}</td>
                                                <td className="hidden lg:table-cell px-3 py-2 text-amber-300/80 max-w-[220px] truncate" title={item.error || ''}>{item.error || '-'}</td>
                                                <td className="px-3 py-2 text-right">
                                                    <div className="flex justify-end items-center gap-1.5">
                                                        <button
                                                            onClick={() => handleStopJobFromPool(item)}
                                                            disabled={stopping || deleting || jobPoolStoppingAll || !canStop}
                                                            className={`px-2.5 py-1 rounded text-[11px] font-semibold ${(stopping || deleting || jobPoolStoppingAll || !canStop) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                                        >
                                                            {stopping ? t('停止中...', 'Stopping...') : t('强制停止', 'Force Stop')}
                                                        </button>
                                                        {canDelete && (
                                                            <button
                                                                onClick={() => handleDeleteJobFromPool(item)}
                                                                disabled={stopping || deleting || jobPoolStoppingAll}
                                                                className={`px-2.5 py-1 rounded text-[11px] font-semibold ${(stopping || deleting || jobPoolStoppingAll) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-orange-500/20 text-orange-200 hover:bg-orange-500/30'}`}
                                                            >
                                                                {deleting ? t('删除中...', 'Deleting...') : t('删除', 'Delete')}
                                                            </button>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {(!jobPoolData?.items || jobPoolData.items.length === 0) && (
                                        <tr>
                                            <td colSpan={9} className="px-3 py-8 text-center text-muted-foreground">{t('暂无任务', 'No tasks')}</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* Log Panel */}
            <LogPanel />

            <DeletionTrashModal
                open={trashModalOpen}
                onClose={() => setTrashModalOpen(false)}
                projectId={id}
                uiLang={uiLang}
                onRestored={() => setRefreshKey((k) => k + 1)}
            />

        </div>
    );
};

export default Editor;




