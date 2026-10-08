
import FunctionApiSelector from '../../../components/FunctionApiSelector';
import { useFunctionApis } from '../../../components/useFunctionApis';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../../../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../../../lib/store';
import LogPanel from '../../../components/LogPanel';
import ProjectStatusBar from '../../../components/ProjectStatusBar';
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, TrendingUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL, ASSET_BASE_URL } from '../../../config';
import { setUiLang as setGlobalUiLang } from '../../../lib/uiLang';

import {
    getFullUrl, createInitialFrameTrimState, clampFrameTrimPercent, normalizeFrameTrimMargins, brokenMediaUrls, brokenSceneImageUrls, warmMediaUrls, shouldBypassBrokenMediaCache, rememberBrokenMediaUrl, isBrokenMediaUrl, rememberWarmMediaUrl, isWarmMediaUrl, getSafeMediaUrl, extractImageJobResultUrl, rememberBrokenSceneImageUrl, isBrokenSceneImageUrl, normalizeBatchParallelLimit, normalizeAsciiSubjectSeparatorsForDeps, normalizeSubjectNameForDeps, normalizeSubjectKeyForDeps, normalizeAsciiSubjectSeparators, normalizeSubjectName, normalizeSubjectKey, normalizeImportSubjectKey, IMG_PLACEHOLDER_SRC, parseVisualDependencies, SafeImage, SafeAudio, normalizeMediaRefList, areMediaRefListsEqual, collectMatchedEntitiesFromPrompt, collectMatchedEntityImageUrlsFromPrompt, SCENE_SUBJECT_TYPE_LABELS, getSceneSubjectStatusKey, splitSceneSubjectNames, normalizeSceneSubjectDefaultType, parseTypedSceneSubjectToken, extractSceneSubjectRefsFromField, buildSceneSubjectNameCandidates, extractSceneSubjectRefs, findMatchingEntityByType, findMissingSceneSubjectRefs, findCrossTypeEntityMatches, buildSceneSubjectPlaceholderPayload, createMissingSceneSubjectPlaceholders, collectMatchedSubjectImageUrlsFromPrompt, resolveUnifiedVideoMode, buildAutoVideoRefList, resolveShotVideoPosterUrl, LazyHoverVideo, InViewVideo, ManagedVideoPlayer, parseEpisodeNumberFromText, normalizeEpisodeTitleForDisplay, buildEntityNegativePrompt, normalizeImageSizeOption, normalizeAspectRatioOption, parseAspectRatioParts, parseAspectRatioValue, reduceAspectRatioParts, buildAspectRatioString, inferImageSizeFromResolution, getEpisodePreferredImageSize, getEpisodePreferredAspectRatio, getProjectPreferredImageSize, getProjectPreferredAspectRatio, buildShotDiptychPlan, getShotDiptychLayoutLabel, buildShotDiptychLayoutInstruction, buildShotDiptychAspectContract, getShotDiptychSeamTrimPx, getShotDiptychSeamBiasPx, getShotDiptychFallbackCropPx, JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION, SHOT_FRAME_ASSET_UPLOAD_VERSION, hashStableText, buildJointShotDiptychUploadIdempotencyKey, buildShotFrameAssetUploadIdempotencyKey, collectSupportedAspectRatioOptions, collectSupportedImageSizeOptions, selectBestShotDiptychRequestAspectRatio, selectBestSupportedImageSize, resolveShotPanelExportResolution, resolveShotDiptychRequestResolution, getResolutionByAspectAndImageSize, SHOT_IMAGE_CFG_MIN, SHOT_IMAGE_CFG_MAX, SHOT_IMAGE_CFG_STEP, SHOT_IMAGE_CFG_FALLBACK, clampShotImageCfg, resolveShotImageCfgDefault, extractDialogueOnlyFromPrompt, inferLanguageCodeFromProjectLanguage, buildVoicePromptWithEntityContext, buildEpisodeDisplayLabel, useTabMediaRefreshEffect, TabMediaRefreshButton
} from '../editorHelpers';
import { PROJECT_ASPECT_RATIO_OPTIONS } from '../projectOptionConfig';
import {
    SAVE_THE_CAT_ACTS,
    STORY_PREFILL_KEYS,
    emptyStoryPrefillFields,
    migrateLegacyPlotToBeats,
    rollupSaveTheCat,
    storyPrefillPayloadFields,
    SERIES_IP_SCRIPT_MODE,
    isSeriesIpScriptMode,
    composeSeriesIpEpisodeGuidance,
} from '../storyPrefill';

import { 
    fetchProject, 
    updateProject,
    generateProjectStoryGlobal,
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
    stopGenerationJob,
    deleteGenerationJob,
    stopAllGenerationJobs,
    stopShotMediaBatch,
    saveProjectStoryGeneratorGlobalInput,
    structureProjectCreativeInput,
    fetchTrendingAiShortDramas,
    fetchIndustryAnalysisAiShortDramas,
    listMarketIntelReports,
    getMarketIntelReport,
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
    getProjectCostEstimation,
    recomputeProjectCostEstimation,
} from '../../../services/api';

import RefineControl from '../../../components/RefineControl.jsx';
import VideoStudio from '../../../components/VideoStudio';
import InputGroup from './InputGroup';
import MarkdownCell from './MarkdownCell';
import MarkdownHelpModal from './MarkdownHelpModal';
import {
    PROVIDER_LABELS,
    MODEL_OPTIONS,
    getSettingSourceByCategory,
    formatProviderModelEndpointError,
} from '../editorConfig';
import {
    PROJECT_EP_TYPE_OPTIONS,
    PROJECT_EP_COUNTRY_REGION_OPTIONS,
    PROJECT_EP_LANGUAGE_OPTIONS,
    PROJECT_EP_BASE_POSITIONING_OPTIONS,
    PROJECT_STORY_SCRIPT_MODE_OPTIONS,
    PROJECT_EP_GLOBAL_STYLE_OPTIONS,
    PROJECT_EP_TONE_OPTIONS,
    PROJECT_EP_LIGHTING_OPTIONS,
    PROJECT_EP_QUALITY_OPTIONS,
    PROJECT_EP_LENS_PREFERENCE_OPTIONS,
    PROJECT_EP_VIDEO_GEN_PREFERENCE_OPTIONS,
    PROJECT_VIDEO_RESOLUTION_OPTIONS,
    normalizeProjectVideoResolution,
    PROJECT_EP_CREATIVITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_ERA_OPTIONS,
    PROJECT_EP_SEASON_OCCURRENCE_OPTIONS,
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
    normalizeProjectSceneAnalysisEra,
    normalizeProjectSceneAnalysisSafety,
    normalizeProjectEpisodeGlobalStyle,
    normalizeProjectEpisodeTone,
    normalizeProjectEpisodeLighting,
    normalizeProjectEpisodeQuality,
    applyStyleModeDefaults,
    syncProjectStyleFromPositioning,
} from '../projectOptionConfig';

// RefineControl moved to components/RefineControl.jsx
import { processPrompt } from '../../../lib/promptUtils';
import { entityNameAppearsInText, entityTokenMatchesName, normalizeEntityToken } from '../../../lib/entityToken';
import SettingsPage from '../../Settings';
import { confirmUiMessage, promptUiMessage } from '../../../lib/uiMessage';

// Character Canon (Authoritative) generator (shared)

import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, DEFAULT_CANON_IDENTITY_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint, resolveProjectVideoSoundEnabled, DEFAULT_MAX_SHOT_SECONDS, resolveMaxShotSeconds } from '../editorConstants';

/** Collapse buggy stacked production motifs: 天逆·实拍（真人剧·实拍（真人剧… → 天逆 */
const stripStackedProductionScriptTitleSuffixes = (title) => {
    const raw = String(title || '').trim();
    if (!raw) return '';
    const cleaned = raw.replace(/(?:·\s*实拍\s*（\s*真人剧[^·]*)+$/g, '').trim();
    return cleaned || raw;
};

export const ProjectOverview = ({ id, project: initialProject = null, onProjectUpdate, onRefreshEpisodes, onJumpToEpisode, onTabChange, episodes = [], uiLang = 'en', mode = 'overview', tabMediaRefreshSignal = 0, isTabActive = true, onMediaRefreshRequest = null }) => {
    const functionApiConfigs = useFunctionApis();
    const [selectedScriptAnalysisApiId, setSelectedScriptAnalysisApiId] = useState(() => {
        return Number(localStorage.getItem('func_api_script_analysis') || 0) || null;
    });
    useEffect(() => {
        const apiList = Array.isArray(functionApiConfigs?.script_analysis) ? functionApiConfigs.script_analysis : [];
        if (apiList.length <= 0) return;

        const currentId = Number(selectedScriptAnalysisApiId || 0);
        const hasCurrent = currentId > 0 && apiList.some((item) => Number(item?.system_api_id || 0) === currentId);
        if (hasCurrent) return;

        const storageId = Number(localStorage.getItem('func_api_script_analysis') || 0);
        const hasStorage = storageId > 0 && apiList.some((item) => Number(item?.system_api_id || 0) === storageId);
        const fallbackId = hasStorage
            ? storageId
            : Number((apiList.find((item) => !item?.is_fallback) || apiList[0])?.system_api_id || 0);

        if (fallbackId > 0) {
            setSelectedScriptAnalysisApiId(fallbackId);
            localStorage.setItem('func_api_script_analysis', String(fallbackId));
        }
    }, [functionApiConfigs?.script_analysis, selectedScriptAnalysisApiId]);

    useEffect(() => {
        const handleFunctionApiChanged = (event) => {
            if (String(event?.detail?.storageKey || '') !== 'func_api_script_analysis') return;
            const nextId = Number(event?.detail?.value || 0) || null;
            setSelectedScriptAnalysisApiId(nextId);
        };
        window.addEventListener('aistory:function-api-changed', handleFunctionApiChanged);
        return () => window.removeEventListener('aistory:function-api-changed', handleFunctionApiChanged);
    }, []);

    const buildScriptAnalysisApiPayload = useCallback((payload = {}) => ({
        ...payload,
        function_name: 'script_analysis',
        system_api_id: Number(selectedScriptAnalysisApiId || 0) || null,
    }), [selectedScriptAnalysisApiId]);

    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const resolveProjectSeedFromInfo = (payload) => {
        const src = (payload && typeof payload === 'object') ? payload : {};
        const generation = (src.generation && typeof src.generation === 'object') ? src.generation : {};
        const candidate = src.generation_seed ?? src.seed ?? generation.seed ?? null;
        const parsed = Number(candidate);
        if (!Number.isFinite(parsed) || parsed <= 0) return "";
        return String(Math.trunc(parsed));
    };
    const [project, setProject] = useState(() => (
        initialProject && String(initialProject.id) === String(id) ? initialProject : null
    ));
    const { addLog } = useLog();
    const [info, setInfo] = useState({
        script_title: "",
        expected_duration: "",
        max_shot_seconds: String(DEFAULT_MAX_SHOT_SECONDS),
        series_episode: "",
        base_positioning: "当代都市 / Contemporary Urban",
        type: "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
        style_mode: "当代都市 / Contemporary Urban",
        Global_Style: "",
        tech_params: {
            visual_standard: {
                horizontal_resolution: "720",
                vertical_resolution: "1280",
                frame_rate: "24",
                aspect_ratio: "9:16",
                quality: "超高 / Ultra High",
                image_size: "2K",
                video_resolution: "720",
            }
        },
        tone: "",
        lighting: "",
        language: "英文 / English",
        season_occurrence: "",
        video_sound: true,
        kb_enabled: false,
        kb_collection_only: false,
        kb_collection_ids: [],
        borrowed_films: [],
        color_palette: "",
        plot_summary: "",
        music_recommendation: "",
        generation_seed: "",
        project_share_users: [],
        project_reviewer_users: [],
        character_relationships: "",
        notes: "",
        story_dna_global_md: "",
        promo_dna_global_md: "",
        story_generator_global_input: {
            episodes_count: 30,
            episode_duration_minutes: 1,
            ...emptyStoryPrefillFields(),
            wild_creative_notes: "",
            extra_notes: "",
            episode_generation_guidance: "",
            ip_episode_plot: "",
            ip_episode_conflict: "",
            ip_episode_highlights: "",
            ip_episode_reference: "",
        },
        character_profiles: [],
        character_canon_md: "",
        character_canon_input: {
            name: "",
            selected_tag_ids: [],
            selected_identity_ids: [],
            custom_identity: "",
            body_features: "",
            custom_style_tags: "",
            extra_notes: "",
        },
        ...PROJECT_SCENE_ANALYSIS_DEFAULTS,
    });
    const [isSceneAnalysisDimensionsCollapsed, setIsSceneAnalysisDimensionsCollapsed] = useState(true);

    const [globalStoryInput, setGlobalStoryInput] = useState({
        episodes_count: 30,
        episode_duration_minutes: 1,
        script_mode: "短剧快节奏 / Short Drama",
        target_audience: "男频路线 / Male-Oriented",
        ...emptyStoryPrefillFields(),
        wild_creative_notes: "",
        extra_notes: "",
        episode_generation_guidance: "",
        ip_episode_plot: "",
        ip_episode_conflict: "",
        ip_episode_highlights: "",
        ip_episode_reference: "",
    });
    const [promoInput, setPromoInput] = useState({
        promo_type: "企业宣传 / Corporate Promotion",
        episodes_count: 1,
        campaign_objective: "",
        target_audience: "",
        key_message: "",
        core_highlights: "",
        credibility_proof: "",
        hook_opening: "",
        conversion_cta: "",
        channel_context: "",
        constraints: "",
    });
    const [promoFrameworkViewMode, setPromoFrameworkViewMode] = useState('preview');
    const [storyFrameworkViewMode, setStoryFrameworkViewMode] = useState('preview');
    const [storyGenFocusStep, setStoryGenFocusStep] = useState('wild_ideas');
    const storyGenStepRefs = useRef({});
    const [targetEpisodeNumberForGen, setTargetEpisodeNumberForGen] = useState('');
    const [trailerFocus, setTrailerFocus] = useState('');
    const [trailerEpisodeFrom, setTrailerEpisodeFrom] = useState('');
    const [trailerEpisodeTo, setTrailerEpisodeTo] = useState('');
    const [hasSetDefaultEp, setHasSetDefaultEp] = useState(false);
    
    useEffect(() => {
        if (episodes) {
            let defaultEp = 1;
            if (episodes.length > 0) {
                const getEpNum = (e, i) => Number(e.episode_number) || parseEpisodeNumberFromText(e.title) || (i + 1);
                defaultEp = Math.max(...episodes.map((e, index) => getEpNum(e, index))) + 1;
                if (episodes.length === 1 && (!episodes[0].script_content || !episodes[0].script_content.trim())) {
                    defaultEp = 1;
                }
            }
            if (!hasSetDefaultEp) {
                setTargetEpisodeNumberForGen(String(defaultEp));
                setHasSetDefaultEp(true);
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [episodes, hasSetDefaultEp]);

    const [isGeneratingGlobalStory, setIsGeneratingGlobalStory] = useState(false);
    const [isStructuringCreativeInput, setIsStructuringCreativeInput] = useState(false);
    const [isFetchingMarketResearch, setIsFetchingMarketResearch] = useState(false);
    const [trendingDramasReport, setTrendingDramasReport] = useState(null);
    const [industryAnalysisReport, setIndustryAnalysisReport] = useState(null);
    const [marketIntelHistory, setMarketIntelHistory] = useState([]);
    const [selectedIndustryReportId, setSelectedIndustryReportId] = useState('');
    const [selectedTrendingReportId, setSelectedTrendingReportId] = useState('');
    const [isLoadingMarketIntelHistory, setIsLoadingMarketIntelHistory] = useState(false);
    const [isGeneratingEpisodeScripts, setIsGeneratingEpisodeScripts] = useState(false);
    const [isStoppingEpisodeScripts, setIsStoppingEpisodeScripts] = useState(false);
    const [episodeScriptsProgress, setEpisodeScriptsProgress] = useState(null);
    const [showEpisodeScriptsProgressModal, setShowEpisodeScriptsProgressModal] = useState(false);
    const [isAnalyzingNovel, setIsAnalyzingNovel] = useState(false);
    const [isImportingStoryPackage, setIsImportingStoryPackage] = useState(false);
    const [novelImportText, setNovelImportText] = useState('');
    const [showGlobalStoryGuide, setShowGlobalStoryGuide] = useState(false);
    const [manualModalOpen, setManualModalOpen] = useState(false);
    const [projectTab, setProjectTab] = useState(mode === 'generator' ? 'story_generator' : 'overview');

    const [expandedSections, setExpandedSections] = useState({
        basic: true,
        cost: true,
        management: false,
        tech: false,
        review: false,
    });
    const toggleSection = (section) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

    const storyPackageFileInputRef = useRef(null);
    const globalStoryGenerationInFlightRef = useRef(false);
    const episodeScriptsGenerationInFlightRef = useRef(false);
    const projectCanonGenerationInFlightRef = useRef(false);
    const episodeScriptsStatusTimerRef = useRef(null);
    const globalStoryAutosaveTimerRef = useRef(null);
    const skipNextGlobalStoryAutosaveRef = useRef(true);
    const promoAutosaveTimerRef = useRef(null);
    const skipNextPromoAutosaveRef = useRef(true);
    const generatorResultAutosaveTimerRef = useRef(null);
    const skipNextGeneratorResultAutosaveRef = useRef(true);
    const autosaveFeedbackTimerRef = useRef(null);
    const [generatorAutosaveFeedback, setGeneratorAutosaveFeedback] = useState({
        phase: 'idle',
        message: '',
    });
    const [projectReviewThreads, setProjectReviewThreads] = useState([]);
    const [isReviewPanelLoading, setIsReviewPanelLoading] = useState(false);
    const [isReviewPanelSubmitting, setIsReviewPanelSubmitting] = useState(false);
    const [currentUserId, setCurrentUserId] = useState(null);
    const [selectedQuickReviewThreadId, setSelectedQuickReviewThreadId] = useState(null);
    const [selectedQuickReviewRounds, setSelectedQuickReviewRounds] = useState([]);
    const [selectedQuickReviewRoundId, setSelectedQuickReviewRoundId] = useState(null);
    const [selectedQuickReviewMessages, setSelectedQuickReviewMessages] = useState([]);
    const [isQuickReviewDetailLoading, setIsQuickReviewDetailLoading] = useState(false);
    const [quickReviewReplyDraft, setQuickReviewReplyDraft] = useState({
        message_text: '',
        entity_decision: 'pending',
        shot_decision: 'pending',
        entity_feedback: '',
        shot_feedback: '',
    });
    const [quickReviewDraft, setQuickReviewDraft] = useState({
        reviewer_user: '',
        title: '',
        request_message: '',
        entity_required: true,
        shot_required: true,
    });
    const [costEstimation, setCostEstimation] = useState(() => {
        const cached = initialProject?.global_info?.cost_estimation;
        return cached && typeof cached === 'object' ? cached : null;
    });
    const [isCostLoading, setIsCostLoading] = useState(false);
    const [isCostRefreshing, setIsCostRefreshing] = useState(false);
    const [costError, setCostError] = useState('');

    const setGeneratorAutosaveState = useCallback((phase, message = '') => {
        if (autosaveFeedbackTimerRef.current) {
            clearTimeout(autosaveFeedbackTimerRef.current);
            autosaveFeedbackTimerRef.current = null;
        }
        setGeneratorAutosaveFeedback({ phase, message });
        if (phase === 'saved') {
            autosaveFeedbackTimerRef.current = setTimeout(() => {
                setGeneratorAutosaveFeedback({ phase: 'idle', message: '' });
                autosaveFeedbackTimerRef.current = null;
            }, 2500);
        }
    }, []);

    useEffect(() => {
        return () => {
            if (autosaveFeedbackTimerRef.current) {
                clearTimeout(autosaveFeedbackTimerRef.current);
                autosaveFeedbackTimerRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        if (mode !== 'generator') {
            setProjectTab('overview');
            return;
        }
        setProjectTab((prev) => {
            if (prev === 'promo_generator' || prev === 'trending_dramas' || prev === 'industry_analysis' || prev === 'market_research') {
                return 'story_generator';
            }
            return prev;
        });
    }, [mode]);

    const loadProjectReviewPanel = useCallback(async () => {
        if (!id) return;
        setIsReviewPanelLoading(true);
        try {
            const threads = await fetchProjectReviewThreads(id);
            const normalizedThreads = Array.isArray(threads) ? threads : [];
            setProjectReviewThreads(normalizedThreads);
        } catch (reviewErr) {
            console.warn('Failed to load project review panel', reviewErr);
            setProjectReviewThreads([]);
        } finally {
            setIsReviewPanelLoading(false);
        }
    }, [id]);

    const loadProjectCost = useCallback(async ({ forceRecompute = false } = {}) => {
        if (!id || mode !== 'overview') return null;
        if (forceRecompute) {
            setIsCostRefreshing(true);
        } else {
            setIsCostLoading(true);
        }
        setCostError('');
        try {
            const payload = forceRecompute
                ? await recomputeProjectCostEstimation(id)
                : await getProjectCostEstimation(id);
            const normalized = payload && typeof payload === 'object' ? payload : null;
            setCostEstimation(normalized);
            return normalized;
        } catch (error) {
            console.warn('Failed to load project cost estimation', error);
            setCostError(error?.response?.data?.detail || error?.message || 'Failed to load project cost estimation');
            return null;
        } finally {
            if (forceRecompute) {
                setIsCostRefreshing(false);
            } else {
                setIsCostLoading(false);
            }
        }
    }, [id, mode]);

    const pollEpisodeScriptsStatus = useCallback(async () => {
        if (!id) return null;
        try {
            const status = await getProjectEpisodeScriptsStatus(id);
            setEpisodeScriptsProgress(status || null);
            return status || null;
        } catch (error) {
            console.warn('Failed to poll episode scripts status', error);
            return null;
        }
    }, [id]);

    useEffect(() => {
        return () => {
            if (episodeScriptsStatusTimerRef.current) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        if (!id || mode !== 'generator') {
            if (episodeScriptsStatusTimerRef.current && !isGeneratingEpisodeScripts) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
            return;
        }
        let cancelled = false;

        const hydrateEpisodeScriptsStatus = async () => {
            const status = await pollEpisodeScriptsStatus();
            if (cancelled || !status || typeof status !== 'object') return;
            if (status.running) {
                setShowEpisodeScriptsProgressModal(true);
                if (!episodeScriptsStatusTimerRef.current) {
                    episodeScriptsStatusTimerRef.current = setInterval(pollEpisodeScriptsStatus, 3000);
                }
            } else if (episodeScriptsStatusTimerRef.current && !isGeneratingEpisodeScripts) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
        };

        hydrateEpisodeScriptsStatus();

        return () => {
            cancelled = true;
        };
    }, [id, mode, pollEpisodeScriptsStatus, isGeneratingEpisodeScripts]);

    useEffect(() => {
        if (!id || mode !== 'overview' || !expandedSections.review) return;
        loadProjectReviewPanel();
    }, [expandedSections.review, id, mode, loadProjectReviewPanel]);

    useEffect(() => {
        if (!id || mode !== 'overview' || !expandedSections.review) return undefined;

        const refreshIfVisible = () => {
            if (document.visibilityState !== 'visible') return;
            loadProjectReviewPanel();
        };

        const intervalId = window.setInterval(refreshIfVisible, 30000);
        document.addEventListener('visibilitychange', refreshIfVisible);
        window.addEventListener('focus', refreshIfVisible);

        return () => {
            window.clearInterval(intervalId);
            document.removeEventListener('visibilitychange', refreshIfVisible);
            window.removeEventListener('focus', refreshIfVisible);
        };
    }, [expandedSections.review, id, mode, loadProjectReviewPanel]);

    useEffect(() => {
        if (!expandedSections.review) return;
        fetchMe()
            .then((user) => {
                setCurrentUserId(Number(user?.id || 0) || null);
            })
            .catch(() => {
                setCurrentUserId(null);
            });
    }, [expandedSections.review]);

    const quickReviewUnreadCount = useMemo(
        () => projectReviewThreads.filter((thread) => !!thread?.has_unread).length,
        [projectReviewThreads]
    );

    const handleCreateQuickProjectReview = async () => {
        if (!id) return;
        const reviewerUser = String(quickReviewDraft.reviewer_user || '').trim();
        if (!reviewerUser) {
            alert(t('请先输入审核人用户名或邮箱。', 'Please enter reviewer username or email first.'));
            return;
        }
        if (!quickReviewDraft.entity_required && !quickReviewDraft.shot_required) {
            alert(t('至少需要选择资产审核或镜头审核。', 'Please enable asset review or shot review.'));
            return;
        }
        setIsReviewPanelSubmitting(true);
        try {
            await createProjectReviewThread(id, {
                reviewer_user: reviewerUser,
                title: quickReviewDraft.title,
                request_message: quickReviewDraft.request_message,
                scope_type: 'all_current',
                entity_required: !!quickReviewDraft.entity_required,
                shot_required: !!quickReviewDraft.shot_required,
            });
            setQuickReviewDraft({
                reviewer_user: '',
                title: '',
                request_message: '',
                entity_required: true,
                shot_required: true,
            });
            await loadProjectReviewPanel();
            alert(t('审核请求已发起。', 'Review request created.'));
        } catch (err) {
            console.error('Failed to create quick project review', err);
            alert(err?.response?.data?.detail || t('发起审核失败。', 'Failed to create review request.'));
        } finally {
            setIsReviewPanelSubmitting(false);
        }
    };

    const loadQuickReviewThreadDetail = useCallback(async (threadId, preferredRoundId = null) => {
        if (!threadId) {
            setSelectedQuickReviewThreadId(null);
            setSelectedQuickReviewRounds([]);
            setSelectedQuickReviewRoundId(null);
            setSelectedQuickReviewMessages([]);
            return;
        }
        setIsQuickReviewDetailLoading(true);
        try {
            await markReviewThreadRead(threadId);
            const rounds = await fetchReviewThreadRounds(threadId);
            const normalizedRounds = Array.isArray(rounds) ? rounds : [];
            const activeRoundId = preferredRoundId || normalizedRounds[normalizedRounds.length - 1]?.id || null;
            setSelectedQuickReviewThreadId(threadId);
            setSelectedQuickReviewRounds(normalizedRounds);
            setSelectedQuickReviewRoundId(activeRoundId);
            if (activeRoundId) {
                const messages = await fetchReviewRoundMessages(activeRoundId);
                setSelectedQuickReviewMessages(Array.isArray(messages) ? messages : []);
            } else {
                setSelectedQuickReviewMessages([]);
            }
            setQuickReviewReplyDraft({
                message_text: '',
                entity_decision: 'pending',
                shot_decision: 'pending',
                entity_feedback: '',
                shot_feedback: '',
            });
            await loadProjectReviewPanel();
        } catch (err) {
            console.error('Failed to load quick review thread detail', err);
            alert(err?.response?.data?.detail || t('加载审核详情失败。', 'Failed to load review details.'));
        } finally {
            setIsQuickReviewDetailLoading(false);
        }
    }, [loadProjectReviewPanel, t]);

    const handleSelectQuickReviewRound = async (roundId) => {
        if (!roundId) return;
        setIsQuickReviewDetailLoading(true);
        try {
            const messages = await fetchReviewRoundMessages(roundId);
            setSelectedQuickReviewRoundId(roundId);
            setSelectedQuickReviewMessages(Array.isArray(messages) ? messages : []);
        } catch (err) {
            console.error('Failed to load quick review round messages', err);
            alert(err?.response?.data?.detail || t('加载轮次消息失败。', 'Failed to load round messages.'));
        } finally {
            setIsQuickReviewDetailLoading(false);
        }
    };

    const handleCreateQuickReviewReply = async () => {
        if (!selectedQuickReviewRoundId || !selectedQuickReviewThreadId) return;
        const selectedThread = projectReviewThreads.find((item) => Number(item.id) === Number(selectedQuickReviewThreadId));
        const selectedRound = selectedQuickReviewRounds.find((item) => Number(item.id) === Number(selectedQuickReviewRoundId));
        if (!selectedThread || !selectedRound) return;
        const amReviewer = Number(currentUserId || 0) === Number(selectedThread.reviewer_user_id || 0);
        const payload = {
            message_text: quickReviewReplyDraft.message_text,
            message_type: 'message',
        };
        if (amReviewer) {
            payload.entity_decision = quickReviewReplyDraft.entity_decision;
            payload.shot_decision = quickReviewReplyDraft.shot_decision;
            payload.entity_feedback = quickReviewReplyDraft.entity_feedback;
            payload.shot_feedback = quickReviewReplyDraft.shot_feedback;
        }
        setIsReviewPanelSubmitting(true);
        try {
            await createReviewRoundMessage(selectedQuickReviewRoundId, payload);
            await loadQuickReviewThreadDetail(selectedQuickReviewThreadId, selectedQuickReviewRoundId);
            alert(t('审核回复已发送。', 'Review reply sent.'));
        } catch (err) {
            console.error('Failed to create quick review reply', err);
            alert(err?.response?.data?.detail || t('发送审核回复失败。', 'Failed to send review reply.'));
        } finally {
            setIsReviewPanelSubmitting(false);
        }
    };

    // Project-level Character Canon (keep original tag-selection UX)
    const [canonName, setCanonName] = useState('');
    const [canonIdentityCategories, setCanonIdentityCategories] = useState(DEFAULT_CANON_IDENTITY_CATEGORIES);
    const [canonSelectedIdentityIds, setCanonSelectedIdentityIds] = useState([]);
    const [canonCustomIdentity, setCanonCustomIdentity] = useState('');
    const [canonBody, setCanonBody] = useState('');
    const [canonExtra, setCanonExtra] = useState('');
    const [canonCustomTags, setCanonCustomTags] = useState('');
    const [canonTagCategories, setCanonTagCategories] = useState(DEFAULT_CANON_TAG_CATEGORIES);
    const [canonTagEditMode, setCanonTagEditMode] = useState(false);
    const [canonSelectedTagIds, setCanonSelectedTagIds] = useState([]);
    const [isGeneratingCanon, setIsGeneratingCanon] = useState(false);
    const [showCanonModal, setShowCanonModal] = useState(false);

    const renderCanonMarkdownFromProfiles = (profiles) => {
        const items = Array.isArray(profiles) ? profiles : [];
        const blocks = [];
        for (const it of items) {
            if (!it || typeof it !== 'object') continue;
            const nm = String(it.name || '').trim();
            if (!nm) continue;
            const md = String(it.description_md || '').trim();
            if (md) {
                blocks.push(md);
            } else {
                blocks.push(`### ${nm} (Canonical)\n- Identity: ${it.identity || ''}\n`);
            }
        }
        return blocks.join('\n\n').trim();
    };

    const handleDeleteCanonCharacter = async (characterName) => {
        const name = String(characterName || '').trim();
        if (!id || !name) return;
        const ok = await confirmUiMessage(`Delete "${name}" from Character Canon? You can re-generate it later.`);
        if (!ok) return;

        try {
            const current = Array.isArray(info.character_profiles) ? info.character_profiles : [];
            const nextProfiles = current.filter(p => (p && typeof p === 'object' ? String(p.name || '').trim() !== name : true));
            await updateProjectCharacterProfiles(id, nextProfiles);
            setInfo(prev => {
                const merged = { ...prev };
                merged.character_profiles = nextProfiles;
                merged.character_canon_md = renderCanonMarkdownFromProfiles(nextProfiles);
                return merged;
            });
        } catch (e) {
            console.error('[Character Canon] Delete failed:', e);
            alert(`Delete failed: ${e?.message || 'Unknown error'}`);
        }
    };

    const canonAutosaveTimerRef = useRef(null);
    const skipNextCanonAutosaveRef = useRef(true);
    const canonCategoriesAutosaveTimerRef = useRef(null);
    const skipNextCanonCategoriesAutosaveRef = useRef(true);

    const persistCanonTagCategories = (categories) => {
        try {
            const normalized = normalizeCanonTagCategories(categories);
            if (!normalized) return false;
            localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(normalized));
            return true;
        } catch (e) {
            return false;
        }
    };

    const persistCanonIdentityCategories = (categories) => {
        try {
            const normalized = normalizeCanonTagCategories(categories);
            if (!normalized) return false;
            localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(normalized));
            return true;
        } catch (e) {
            return false;
        }
    };

    useEffect(() => {
        try {
            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);
            const LEGACY_SEXY_OPTION_IDS = new Set([
                'sexy_1',
                'sexy_2',
                'sexy_3',
                'sexy_4',
                'sexy_m1',
                'sexy_m2',
            ]);

            const mergeCategoriesByKey = (savedCats, defaultCats) => {
                const byKey = new Map();
                for (const c of (savedCats || [])) {
                    if (!c?.key) continue;
                    if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                    byKey.set(c.key, c);
                }

                const mergeOne = (savedCat, defCat) => {
                    if (!savedCat) return defCat;
                    const categoryKey = savedCat.key || defCat?.key;
                    let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                    if (categoryKey === 'sexy') {
                        savedOptions = savedOptions.filter(o => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
                    }
                    const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                    const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                    const mergedOptions = [...savedOptions];
                    for (const opt of defOptions) {
                        if (!opt?.id) continue;
                        if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                    }
                    return {
                        ...savedCat,
                        key: savedCat.key || defCat?.key,
                        title: savedCat.title || defCat?.title,
                        options: mergedOptions,
                    };
                };

                const merged = [];
                for (const def of (defaultCats || [])) {
                    const saved = byKey.get(def.key);
                    merged.push(mergeOne(saved, def));
                    byKey.delete(def.key);
                }
                for (const rest of byKey.values()) {
                    if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                    merged.push(rest);
                }
                return merged;
            };

            const savedTags = localStorage.getItem(CANON_TAG_STORAGE_KEY);
            if (savedTags) {
                const parsed = JSON.parse(savedTags);
                const normalized = normalizeCanonTagCategories(parsed);
                if (normalized) {
                    setCanonTagCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES));
                } else {
                    setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
                }
            } else {
                setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
            }

            const savedIdentity = localStorage.getItem(CANON_IDENTITY_STORAGE_KEY);
            if (savedIdentity) {
                const parsed = JSON.parse(savedIdentity);
                const normalized = normalizeCanonTagCategories(parsed);
                if (normalized) {
                    setCanonIdentityCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES));
                }
            }
        } catch (e) {
            setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
            setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const toggleCanonTagId = (tagId) => {
        setCanonSelectedTagIds(prev => (
            prev.includes(tagId) ? prev.filter(t => t !== tagId) : [...prev, tagId]
        ));
    };

    const toggleCanonIdentityId = (identityId) => {
        setCanonSelectedIdentityIds(prev => (
            prev.includes(identityId) ? prev.filter(t => t !== identityId) : [...prev, identityId]
        ));
    };

    const canonSelectedTagStrings = () => {
        const selected = [];
        for (const cat of (canonTagCategories || [])) {
            for (const opt of (cat.options || [])) {
                if (canonSelectedTagIds.includes(opt.id)) {
                    selected.push(canonOptionValue(opt));
                }
            }
        }
        return selected;
    };

    const canonSelectedIdentityStrings = () => {
        const selected = [];
        for (const cat of (canonIdentityCategories || [])) {
            for (const opt of (cat.options || [])) {
                if (canonSelectedIdentityIds.includes(opt.id)) {
                    selected.push(canonOptionValue(opt));
                }
            }
        }
        return selected;
    };

    const newCanonOptionId = (prefix = 'opt') => `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;

    const updateCanonCategoryTitle = (catKey, title) => {
        setCanonTagCategories(prev => (prev || []).map(c => (c.key === catKey ? { ...c, title } : c)));
    };
    const updateCanonOption = (catKey, optId, patch) => {
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return {
                ...c,
                options: (c.options || []).map(o => (o.id === optId ? { ...o, ...patch } : o)),
            };
        }));
    };
    const addCanonOption = (catKey) => {
        const newId = newCanonOptionId(catKey);
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id: newId, label: '新标签', detail: '细节描述' }] };
        }));
    };
    const removeCanonOption = (catKey, optId) => {
        setCanonSelectedTagIds(prev => prev.filter(id2 => id2 !== optId));
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
    };

    const updateIdentityCategoryTitle = (catKey, title) => {
        setCanonIdentityCategories(prev => (prev || []).map(c => (c.key === catKey ? { ...c, title } : c)));
    };
    const updateIdentityOption = (catKey, optId, patch) => {
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return {
                ...c,
                options: (c.options || []).map(o => (o.id === optId ? { ...o, ...patch } : o)),
            };
        }));
    };
    const addIdentityOption = (catKey) => {
        const newId = newCanonOptionId(catKey);
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id: newId, label: '新身份', detail: '细节描述' }] };
        }));
    };
    const removeIdentityOption = (catKey, optId) => {
        setCanonSelectedIdentityIds(prev => prev.filter(id2 => id2 !== optId));
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
    };

    const closeCanonModal = () => {
        if (canonTagEditMode) {
            persistCanonTagCategories(canonTagCategories);
            persistCanonIdentityCategories(canonIdentityCategories);
        }
        setCanonTagEditMode(false);
        setShowCanonModal(false);
    };

    useEffect(() => {
        const cachedInitialProject = initialProject && String(initialProject.id) === String(id) ? initialProject : null;

        const load = async () => {
            try {
                const data = cachedInitialProject || await fetchProject(id);
                setProject(data);

                try {
                    const missing = Array.isArray(data?.missing_basic_fields) ? data.missing_basic_fields : [];
                    if (!cachedInitialProject && missing.length > 0) {
                        const labels = missing.map((field) => {
                            if (field === 'type') return t('类型', 'Type');
                            if (field === 'country_region') return t('国家地域', 'Country/Region');
                            if (field === 'language') return t('语言', 'Language');
                            return String(field || '');
                        }).filter(Boolean).join(' / ');

                        await confirmUiMessage(
                            `${t('项目基本信息缺失，请先设置：', 'Project basic info is missing, please set: ')}${labels}\n${t('将为你自动跳转到项目概览页。', 'You will be redirected to Project Overview.')}`
                        );
                        setProjectTab('overview');
                        if (onTabChange) onTabChange('overview');
                        try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch {}
                    }
                } catch (healthErr) {
                    console.warn('Project health reminder failed:', healthErr);
                }

                if (data.global_info) {
                     // Merger with defaults to ensure structure
                     const merged = {
                         ...info,
                         ...data.global_info,
                         tech_params: {
                             visual_standard: {
                                 ...info.tech_params.visual_standard,
                                 ...(data.global_info.tech_params?.visual_standard || {})
                             }
                         }
                     };

                     // Default Script Title to project.title when empty
                     if (!merged.script_title || String(merged.script_title).trim().length === 0) {
                         if (data?.title && String(data.title).trim().length > 0) {
                             merged.script_title = String(data.title).trim();
                         }
                     }
                     merged.script_title = stripStackedProductionScriptTitleSuffixes(merged.script_title);
                     merged.type = normalizeProjectEpisodeType(merged.type);
                     merged.language = normalizeProjectEpisodeLanguage(merged.language);
                     Object.assign(merged, syncProjectStyleFromPositioning(merged));
                     merged.era = normalizeProjectSceneAnalysisEra(merged.era);
                     merged.broadcast_safety_level = normalizeProjectSceneAnalysisSafety(merged.broadcast_safety_level);
                     merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
                     merged.tone = normalizeProjectEpisodeTone(merged.tone);
                     merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
                     merged.video_sound = resolveProjectVideoSoundEnabled(merged);
                     merged.max_shot_seconds = String(resolveMaxShotSeconds(merged.max_shot_seconds));
                     merged.generation_seed = resolveProjectSeedFromInfo(merged);
                     merged.project_share_users = normalizeUserListValues(merged.project_share_users);
                     merged.project_reviewer_users = normalizeUserListValues(merged.project_reviewer_users);
                     if (merged.tech_params?.visual_standard) {
                         merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
                     }
                     setInfo(merged);

                     // Restore Story Generator draft inputs (if previously saved)
                     if (merged.story_generator_global_input && typeof merged.story_generator_global_input === 'object') {
                         setGlobalStoryInput(prev => migrateLegacyPlotToBeats({
                             ...prev,
                             ...merged.story_generator_global_input,
                             episode_duration_minutes: Number(merged.story_generator_global_input.episode_duration_minutes) > 0
                                 ? Number(merged.story_generator_global_input.episode_duration_minutes)
                                 : 1,
                         }));
                         if (merged.story_generator_global_input.trending_ai_short_dramas_report) {
                             setTrendingDramasReport(merged.story_generator_global_input.trending_ai_short_dramas_report);
                         }
                         if (merged.story_generator_global_input.ai_short_drama_industry_report) {
                             setIndustryAnalysisReport(merged.story_generator_global_input.ai_short_drama_industry_report);
                         } else if (merged.story_generator_global_input.trending_ai_short_dramas_report?.industry_analysis) {
                             const legacy = merged.story_generator_global_input.trending_ai_short_dramas_report;
                             setIndustryAnalysisReport({
                                 report_month: legacy.report_month,
                                 report_period: legacy.report_period,
                                 summary: legacy.summary,
                                 industry_analysis: legacy.industry_analysis,
                                 markdown: legacy.markdown,
                                 disclaimer: legacy.disclaimer,
                                 search_meta: legacy.search_meta,
                             });
                         }
                     }

                     if (merged.promo_planner_input && typeof merged.promo_planner_input === 'object') {
                        const demand = merged.promo_planner_input.campaign_demand || {};
                        setPromoInput(prev => ({
                            ...prev,
                            episodes_count: Number(demand.episodes_count || prev.episodes_count || 1) || 1,
                            campaign_objective: demand.user_raw_text || prev.campaign_objective,
                            conversion_cta: demand.cta || prev.conversion_cta,
                            constraints: demand.constraint || prev.constraints,
                        }));
                     } else if (merged.promo_generator_input && typeof merged.promo_generator_input === 'object') {
                        setPromoInput(prev => ({
                            ...prev,
                            ...merged.promo_generator_input,
                        }));
                     }

                     // Avoid immediately auto-saving right after hydration
                     skipNextGlobalStoryAutosaveRef.current = true;
                     skipNextPromoAutosaveRef.current = true;
                     skipNextGeneratorResultAutosaveRef.current = true;

                     // Restore Character Canon draft inputs (if previously saved)
                     const canonDraft = merged.character_canon_input;
                     if (canonDraft && typeof canonDraft === 'object') {
                         if (typeof canonDraft.name === 'string') setCanonName(canonDraft.name);
                         if (Array.isArray(canonDraft.selected_identity_ids)) setCanonSelectedIdentityIds(canonDraft.selected_identity_ids);
                         if (Array.isArray(canonDraft.selected_tag_ids)) setCanonSelectedTagIds(canonDraft.selected_tag_ids);
                         if (typeof canonDraft.custom_identity === 'string') setCanonCustomIdentity(canonDraft.custom_identity);
                         if (typeof canonDraft.body_features === 'string') setCanonBody(canonDraft.body_features);
                         if (typeof canonDraft.custom_style_tags === 'string') setCanonCustomTags(canonDraft.custom_style_tags);
                         if (typeof canonDraft.extra_notes === 'string') setCanonExtra(canonDraft.extra_notes);
                     }

                     // Restore Character Canon tag/identity categories from DB (cross-device)
                     if (merged.character_canon_tag_categories) {
                         const normalized = normalizeCanonTagCategories(merged.character_canon_tag_categories);
                         if (normalized) {
                            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);
                            const LEGACY_SEXY_OPTION_IDS = new Set([
                                'sexy_1',
                                'sexy_2',
                                'sexy_3',
                                'sexy_4',
                                'sexy_m1',
                                'sexy_m2',
                            ]);

                             const mergeCategoriesByKey = (savedCats, defaultCats) => {
                                 const byKey = new Map();
                                 for (const c of (savedCats || [])) {
                                     if (!c?.key) continue;
                                     if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                                     byKey.set(c.key, c);
                                 }

                                 const mergeOne = (savedCat, defCat) => {
                                     if (!savedCat) return defCat;
                                     const categoryKey = savedCat.key || defCat?.key;
                                     let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                                     if (categoryKey === 'sexy') {
                                         savedOptions = savedOptions.filter(o => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
                                     }
                                     const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                                     const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                                     const mergedOptions = [...savedOptions];
                                     for (const opt of defOptions) {
                                         if (!opt?.id) continue;
                                         if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                                     }
                                     return {
                                         ...savedCat,
                                         key: savedCat.key || defCat?.key,
                                         title: savedCat.title || defCat?.title,
                                         options: mergedOptions,
                                     };
                                 };

                                 const mergedCats = [];
                                 for (const def of (defaultCats || [])) {
                                     const saved = byKey.get(def.key);
                                     mergedCats.push(mergeOne(saved, def));
                                     byKey.delete(def.key);
                                 }
                                 for (const rest of byKey.values()) {
                                     if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                                     mergedCats.push(rest);
                                 }
                                 return mergedCats;
                             };

                             const mergedCats = mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES);
                             setCanonTagCategories(mergedCats);
                             try { localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(mergedCats)); } catch {}
                         }
                     }
                     if (merged.character_canon_identity_categories) {
                         const normalized = normalizeCanonTagCategories(merged.character_canon_identity_categories);
                         if (normalized) {
                            const DEPRECATED_CANON_CATEGORY_KEYS = new Set(['combat']);

                             const mergeCategoriesByKey = (savedCats, defaultCats) => {
                                 const byKey = new Map();
                                 for (const c of (savedCats || [])) {
                                     if (!c?.key) continue;
                                     if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                                     byKey.set(c.key, c);
                                 }

                                 const mergeOne = (savedCat, defCat) => {
                                     if (!savedCat) return defCat;
                                     const savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                                     const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                                     const seenIds = new Set(savedOptions.map(o => o?.id).filter(Boolean));
                                     const mergedOptions = [...savedOptions];
                                     for (const opt of defOptions) {
                                         if (!opt?.id) continue;
                                         if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                                     }
                                     return {
                                         ...savedCat,
                                         key: savedCat.key || defCat?.key,
                                         title: savedCat.title || defCat?.title,
                                         options: mergedOptions,
                                     };
                                 };

                                 const mergedCats = [];
                                 for (const def of (defaultCats || [])) {
                                     const saved = byKey.get(def.key);
                                     mergedCats.push(mergeOne(saved, def));
                                     byKey.delete(def.key);
                                 }
                                 for (const rest of byKey.values()) {
                                     if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                                     mergedCats.push(rest);
                                 }
                                 return mergedCats;
                             };

                             const mergedCats = mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES);
                             setCanonIdentityCategories(mergedCats);
                             try { localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(mergedCats)); } catch {}
                         }
                     }

                     // Avoid immediately auto-saving right after hydration
                     skipNextCanonAutosaveRef.current = true;
                     skipNextCanonCategoriesAutosaveRef.current = true;
                }
                if (data?.global_info?.cost_estimation && typeof data.global_info.cost_estimation === 'object') {
                    setCostEstimation(data.global_info.cost_estimation);
                }
            } catch (e) {
                console.error("Failed to load project", e);
            }
        };
        load();
    }, [id, t]);

    // Auto-save Character Canon tag/identity categories (debounced) when in edit mode
    useEffect(() => {
        if (!id) return;
        if (!canonTagEditMode) return;

        if (skipNextCanonCategoriesAutosaveRef.current) {
            skipNextCanonCategoriesAutosaveRef.current = false;
            return;
        }

        if (canonCategoriesAutosaveTimerRef.current) {
            clearTimeout(canonCategoriesAutosaveTimerRef.current);
        }

        canonCategoriesAutosaveTimerRef.current = setTimeout(async () => {
            try {
                const normalizedTags = normalizeCanonTagCategories(canonTagCategories);
                const normalizedIdentity = normalizeCanonTagCategories(canonIdentityCategories);
                if (!normalizedTags || !normalizedIdentity) return;
                await saveProjectCharacterCanonCategories(id, {
                    tag_categories: normalizedTags,
                    identity_categories: normalizedIdentity,
                });
                try { localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(normalizedTags)); } catch {}
                try { localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(normalizedIdentity)); } catch {}
            } catch (e) {
                console.error('[Character Canon Categories] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (canonCategoriesAutosaveTimerRef.current) {
                clearTimeout(canonCategoriesAutosaveTimerRef.current);
            }
        };
    }, [id, canonTagEditMode, canonTagCategories, canonIdentityCategories]);

    // Auto-save Project Character Canon draft inputs (debounced)
    useEffect(() => {
        if (!id) return;
        if (isGeneratingCanon) return;

        if (skipNextCanonAutosaveRef.current) {
            skipNextCanonAutosaveRef.current = false;
            return;
        }

        if (canonAutosaveTimerRef.current) {
            clearTimeout(canonAutosaveTimerRef.current);
        }

        canonAutosaveTimerRef.current = setTimeout(async () => {
            try {
                const payload = {
                    name: canonName || '',
                    selected_tag_ids: Array.isArray(canonSelectedTagIds) ? canonSelectedTagIds : [],
                    selected_identity_ids: Array.isArray(canonSelectedIdentityIds) ? canonSelectedIdentityIds : [],
                    custom_identity: canonCustomIdentity || '',
                    body_features: canonBody || '',
                    custom_style_tags: canonCustomTags || '',
                    extra_notes: canonExtra || '',
                };
                await saveProjectCharacterCanonInput(id, payload);
            } catch (e) {
                console.error('[Character Canon] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (canonAutosaveTimerRef.current) {
                clearTimeout(canonAutosaveTimerRef.current);
            }
        };
    }, [
        id,
        isGeneratingCanon,
        canonName,
        canonSelectedTagIds,
        canonSelectedIdentityIds,
        canonCustomIdentity,
        canonBody,
        canonCustomTags,
        canonExtra,
    ]);

    // Auto-save Story Generator (Global/Project) draft inputs (debounced)
    useEffect(() => {
        if (!id) return;
        if (isGeneratingGlobalStory) return;

        if (skipNextGlobalStoryAutosaveRef.current) {
            skipNextGlobalStoryAutosaveRef.current = false;
            return;
        }

        if (globalStoryAutosaveTimerRef.current) {
            clearTimeout(globalStoryAutosaveTimerRef.current);
        }

        globalStoryAutosaveTimerRef.current = setTimeout(async () => {
            setGeneratorAutosaveState('saving', t('自动保存中...', 'Auto-saving...'));
            try {
                const payload = {
                    mode: 'global',
                    generator_kind: 'story',
                    episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
                    episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0
                        ? Number(globalStoryInput.episode_duration_minutes)
                        : 1,
                    script_mode: globalStoryInput.script_mode,
                    target_audience: globalStoryInput.target_audience,
                    ...storyPrefillPayloadFields(globalStoryInput),
                };
                await saveProjectStoryGeneratorGlobalInput(id, payload);
                setGeneratorAutosaveState('saved', t('故事输入已自动保存', 'Story input auto-saved'));
            } catch (e) {
                console.error('[Global Story Generator] Auto-save failed:', e);
                setGeneratorAutosaveState('error', t('自动保存失败', 'Auto-save failed'));
            }
        }, 800);

        return () => {
            if (globalStoryAutosaveTimerRef.current) {
                clearTimeout(globalStoryAutosaveTimerRef.current);
            }
        };
    }, [id, globalStoryInput, isGeneratingGlobalStory, setGeneratorAutosaveState, t]);

    // Promo planner draft autosave lives in PromoPlanner (structured enterprise + assets + demand).

    // Auto-save editable generator results (framework markdown + relationships) (debounced)
    useEffect(() => {
        if (!id) return;
        if (mode !== 'generator') return;
        if (isGeneratingGlobalStory) return;

        if (skipNextGeneratorResultAutosaveRef.current) {
            skipNextGeneratorResultAutosaveRef.current = false;
            return;
        }

        if (generatorResultAutosaveTimerRef.current) {
            clearTimeout(generatorResultAutosaveTimerRef.current);
        }

        generatorResultAutosaveTimerRef.current = setTimeout(async () => {
            setGeneratorAutosaveState('saving', t('自动保存中...', 'Auto-saving...'));
            try {
                const baseGlobalInfo = (project?.global_info && typeof project.global_info === 'object')
                    ? project.global_info
                    : {};
                const global_info = {
                    ...baseGlobalInfo,
                    story_dna_global_md: info.story_dna_global_md || '',
                    promo_dna_global_md: info.promo_dna_global_md || '',
                    character_relationships: info.character_relationships || '',
                };
                await updateProject(id, { global_info });
                setGeneratorAutosaveState('saved', t('生成结果已自动保存', 'Generated content auto-saved'));
            } catch (e) {
                console.error('[Generator Result] Auto-save failed:', e);
                setGeneratorAutosaveState('error', t('自动保存失败', 'Auto-save failed'));
            }
        }, 1200);

        return () => {
            if (generatorResultAutosaveTimerRef.current) {
                clearTimeout(generatorResultAutosaveTimerRef.current);
            }
        };
    }, [
        id,
        mode,
        isGeneratingGlobalStory,
        info.story_dna_global_md,
        info.promo_dna_global_md,
        info.character_relationships,
        project,
        setGeneratorAutosaveState,
        t,
    ]);

    const handleSave = async () => {
        try {
            const resolvedVideoSound = resolveProjectVideoSoundEnabled(info);
            const seedParsed = Number(info.generation_seed);
            const resolvedSeed = Number.isFinite(seedParsed) && seedParsed > 0
                ? Math.trunc(seedParsed)
                : null;

            const global_info = {
                ...info,
                script_title: stripStackedProductionScriptTitleSuffixes(info.script_title),
                max_shot_seconds: String(resolveMaxShotSeconds(info.max_shot_seconds)),
                project_share_users: normalizeUserListValues(info.project_share_users),
                project_reviewer_users: normalizeUserListValues(info.project_reviewer_users),
                video_sound: resolvedVideoSound,
                project_generation_defaults: {
                    ...(info.project_generation_defaults || {}),
                    sound: resolvedVideoSound,
                    video_resolution: normalizeProjectVideoResolution(
                        info.tech_params?.visual_standard?.video_resolution
                        || info.project_generation_defaults?.video_resolution
                    ) || '720',
                },
                tech_params: {
                    ...(info.tech_params || {}),
                    visual_standard: {
                        ...(info.tech_params?.visual_standard || {}),
                        sound: resolvedVideoSound,
                        video_resolution: normalizeProjectVideoResolution(
                            info.tech_params?.visual_standard?.video_resolution
                            || info.project_generation_defaults?.video_resolution
                        ) || '720',
                    },
                },
                story_generator_global_input: {
                    ...globalStoryInput,
                    episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
                    episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0
                        ? Number(globalStoryInput.episode_duration_minutes)
                        : 1,
                },
                promo_generator_input: {
                    ...promoInput,
                    episodes_count: Number(promoInput.episodes_count || 0) || 0,
                },
                promo_planner_input: info.promo_planner_input || undefined,
                promo_planner_result: info.promo_planner_result || undefined,
                character_canon_input: {
                    name: canonName || '',
                    selected_tag_ids: Array.isArray(canonSelectedTagIds) ? canonSelectedTagIds : [],
                    selected_identity_ids: Array.isArray(canonSelectedIdentityIds) ? canonSelectedIdentityIds : [],
                    custom_identity: canonCustomIdentity || '',
                    body_features: canonBody || '',
                    custom_style_tags: canonCustomTags || '',
                    extra_notes: canonExtra || '',
                },
            };
            if (resolvedSeed !== null) {
                global_info.generation_seed = resolvedSeed;
            }
            await updateProject(id, {
                global_info,
                share_users: global_info.project_share_users,
                reviewer_users: global_info.project_reviewer_users,
            });
            await loadProjectCost({ forceRecompute: true });
            alert("Project info saved!");
            if (onProjectUpdate) onProjectUpdate();
        } catch (e) {
            console.error("Failed to save", e);
            alert(`Failed to save: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleGeneratePromoFramework = async () => {
        if (globalStoryGenerationInFlightRef.current || isGeneratingGlobalStory) return;
        globalStoryGenerationInFlightRef.current = true;
        setIsGeneratingGlobalStory(true);
        try {
            const episodesCount = Number(promoInput.episodes_count || 0) || 0;
            if (episodesCount <= 0) {
                alert('Please set a valid Episodes Count for Promo Generator.');
                return;
            }

            const payload = {
                mode: 'global',
                generator_kind: 'promo',
                episodes_count: episodesCount,
                script_title: info.script_title,
                expected_duration: info.expected_duration,
                type: promoInput.promo_type || info.type,
                language: info.language,
                base_positioning: info.base_positioning,
                Global_Style: info.Global_Style,
                background: [
                    `Campaign Objective: ${promoInput.campaign_objective || ''}`,
                    `Target Audience: ${promoInput.target_audience || ''}`,
                    `Channel Context: ${promoInput.channel_context || ''}`,
                ].join('\n'),
                setup: [
                    `Hook Opening: ${promoInput.hook_opening || ''}`,
                    `Core Message: ${promoInput.key_message || ''}`,
                ].join('\n'),
                development: [
                    `Core Highlights: ${promoInput.core_highlights || ''}`,
                    `Credibility Proof: ${promoInput.credibility_proof || ''}`,
                ].join('\n'),
                turning_points: `Differentiation & Persuasion Pivot: ${promoInput.key_message || ''}`,
                climax: `Flagship Demonstration / Emotional Peak: ${promoInput.core_highlights || ''}`,
                resolution: `Conversion CTA: ${promoInput.conversion_cta || ''}`,
                suspense: `Retention Hook for Next Episode / Segment: ${promoInput.conversion_cta || ''}`,
                foreshadowing: `Brand/Message anchors to repeat: ${promoInput.key_message || ''}`,
                extra_notes: [
                    `Promo Type: ${promoInput.promo_type || ''}`,
                    `Constraints: ${promoInput.constraints || ''}`,
                ].join('\n'),
            };

            const updated = await generateProjectStoryGlobal(id, buildScriptAnalysisApiPayload(payload));
            setProject(updated);
            const responseGlobalInfo = (updated?.global_info && typeof updated.global_info === 'object')
                ? updated.global_info
                : {};
            const returnedMarkdown = String(
                responseGlobalInfo.promo_dna_global_md
                || responseGlobalInfo.story_dna_global_md
                || updated?.promo_dna_global_md
                || updated?.story_dna_global_md
                || ''
            );

            setInfo(prev => {
                const merged = {
                    ...prev,
                    ...responseGlobalInfo,
                    promo_dna_global_md: returnedMarkdown || prev.promo_dna_global_md || '',
                    promo_generator_input: {
                        ...promoInput,
                        episodes_count: episodesCount,
                    },
                    tech_params: {
                        visual_standard: {
                            ...(prev?.tech_params?.visual_standard || {}),
                            ...(responseGlobalInfo.tech_params?.visual_standard || {})
                        }
                    }
                };
                merged.type = normalizeProjectEpisodeType(merged.type);
                merged.language = normalizeProjectEpisodeLanguage(merged.language);
                Object.assign(merged, syncProjectStyleFromPositioning(merged));
                merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
                merged.tone = normalizeProjectEpisodeTone(merged.tone);
                merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
                if (merged.tech_params?.visual_standard) {
                    merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
                }
                return merged;
            });

            setGlobalStoryInput(prev => ({
                ...prev,
                episodes_count: episodesCount,
            }));

            setPromoFrameworkViewMode('preview');

            await updateProject(id, {
                global_info: {
                    ...(updated?.global_info || info || {}),
                    promo_generator_input: {
                        ...promoInput,
                        episodes_count: episodesCount,
                    },
                }
            });

            alert('Promo framework generated and saved. You can now generate episode scripts.');
        } catch (e) {
            console.error(e);
            const readable = formatProviderModelEndpointError(e);
            alert(`Failed to generate promo framework:\n${readable}`);
        } finally {
            setIsGeneratingGlobalStory(false);
            globalStoryGenerationInFlightRef.current = false;
        }
    };

    const persistStoryGeneratorInputPatch = async (patch = {}) => {
        await saveProjectStoryGeneratorGlobalInput(id, {
            mode: 'global',
            generator_kind: 'story',
            episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
            episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0
                ? Number(globalStoryInput.episode_duration_minutes)
                : 1,
            script_mode: globalStoryInput.script_mode,
            target_audience: globalStoryInput.target_audience,
            ...storyPrefillPayloadFields(globalStoryInput),
            trending_ai_short_dramas_report: trendingDramasReport,
            ai_short_drama_industry_report: industryAnalysisReport,
            ...patch,
        });
    };

    const loadMarketIntelHistory = useCallback(async () => {
        if (!id) return [];
        setIsLoadingMarketIntelHistory(true);
        try {
            const data = await listMarketIntelReports(id, { limit: 100 });
            const items = Array.isArray(data?.items) ? data.items : [];
            setMarketIntelHistory(items);

            const industryItems = items.filter((item) => item.report_kind === 'industry_analysis');
            const trendingItems = items.filter((item) => item.report_kind === 'trending_dramas');

            const pickLatestId = (list, currentId) => {
                if (currentId && list.some((item) => String(item.id) === String(currentId))) {
                    return String(currentId);
                }
                return list[0]?.id ? String(list[0].id) : '';
            };

            setSelectedIndustryReportId((prev) => pickLatestId(industryItems, prev));
            setSelectedTrendingReportId((prev) => pickLatestId(trendingItems, prev));
            return items;
        } catch (err) {
            console.warn('[Market Research] load history failed:', err);
            setMarketIntelHistory([]);
            return [];
        } finally {
            setIsLoadingMarketIntelHistory(false);
        }
    }, [id]);

    const handleSelectMarketIntelReport = useCallback(async (reportId, kind) => {
        const nextId = String(reportId || '').trim();
        if (!id || !nextId) return;
        if (kind === 'industry_analysis') setSelectedIndustryReportId(nextId);
        if (kind === 'trending_dramas') setSelectedTrendingReportId(nextId);
        try {
            const report = await getMarketIntelReport(id, nextId);
            if (kind === 'industry_analysis') {
                setIndustryAnalysisReport(report);
            } else if (kind === 'trending_dramas') {
                setTrendingDramasReport(report);
            }
        } catch (err) {
            console.warn('[Market Research] load report failed:', err);
            alert(`${t('加载历史报告失败', 'Failed to load historical report')}: ${formatProviderModelEndpointError(err)}`);
        }
    }, [id, t]);

    useEffect(() => {
        if (mode !== 'market_research' || !id) return;
        let cancelled = false;
        (async () => {
            const items = await loadMarketIntelHistory();
            if (cancelled) return;
            const industryLatest = items.find((item) => item.report_kind === 'industry_analysis');
            const trendingLatest = items.find((item) => item.report_kind === 'trending_dramas');
            if (industryLatest?.id && !industryAnalysisReport?.markdown) {
                try {
                    const report = await getMarketIntelReport(id, industryLatest.id);
                    if (!cancelled) {
                        setIndustryAnalysisReport(report);
                        setSelectedIndustryReportId(String(industryLatest.id));
                    }
                } catch (e) { /* ignore */ }
            }
            if (trendingLatest?.id && !trendingDramasReport?.markdown) {
                try {
                    const report = await getMarketIntelReport(id, trendingLatest.id);
                    if (!cancelled) {
                        setTrendingDramasReport(report);
                        setSelectedTrendingReportId(String(trendingLatest.id));
                    }
                } catch (e) { /* ignore */ }
            }
        })();
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [mode, id, loadMarketIntelHistory]);

    const handleFetchMarketResearch = async () => {
        if (isFetchingMarketResearch || isGeneratingGlobalStory) return;
        setIsFetchingMarketResearch(true);
        const payload = buildScriptAnalysisApiPayload({ language: info.language });
        const errors = [];
        let industryReport = null;
        let trendingReport = null;

        try {
            const [industryResult, trendingResult] = await Promise.allSettled([
                fetchIndustryAnalysisAiShortDramas(id, payload),
                fetchTrendingAiShortDramas(id, { ...payload, limit: 12 }),
            ]);

            if (industryResult.status === 'fulfilled') {
                industryReport = industryResult.value;
                setIndustryAnalysisReport(industryReport);
                if (industryReport?.id) setSelectedIndustryReportId(String(industryReport.id));
                setGlobalStoryInput(prev => ({
                    ...prev,
                    ai_short_drama_industry_report: industryReport,
                }));
            } else {
                console.error(industryResult.reason);
                errors.push(`${t('行业分析', 'Industry analysis')}: ${formatProviderModelEndpointError(industryResult.reason)}`);
            }

            if (trendingResult.status === 'fulfilled') {
                trendingReport = trendingResult.value;
                setTrendingDramasReport(trendingReport);
                if (trendingReport?.id) setSelectedTrendingReportId(String(trendingReport.id));
                setGlobalStoryInput(prev => ({
                    ...prev,
                    trending_ai_short_dramas_report: trendingReport,
                }));
            } else {
                console.error(trendingResult.reason);
                errors.push(`${t('热门榜单', 'Trending list')}: ${formatProviderModelEndpointError(trendingResult.reason)}`);
            }

            // Backend already persists to market_intel_reports; keep latest pointer in story generator draft.
            if (industryReport || trendingReport) {
                try {
                    await persistStoryGeneratorInputPatch({
                        ...(industryReport ? { ai_short_drama_industry_report: industryReport } : {}),
                        ...(trendingReport ? { trending_ai_short_dramas_report: trendingReport } : {}),
                    });
                } catch (saveErr) {
                    console.warn('[Market Research] save report failed:', saveErr);
                }
                try {
                    await loadMarketIntelHistory();
                } catch (histErr) {
                    console.warn('[Market Research] refresh history failed:', histErr);
                }
            }

            if (errors.length > 0) {
                alert(`${t('部分市场情报获取失败', 'Some market research requests failed')}:\n${errors.join('\n')}`);
            }
        } finally {
            setIsFetchingMarketResearch(false);
        }
    };

    const handleAppendMarketResearchToWildIdeas = () => {
        const blocks = [];

        if (industryAnalysisReport?.markdown) {
            const period = industryAnalysisReport.report_period || industryAnalysisReport.report_month || '';
            const header = t(
                `【${period} AI短剧热榜题材变化参考】\n${industryAnalysisReport.summary || ''}\n`,
                `[${period} AI Short Drama Hot-List Genre Shift Reference]\n${industryAnalysisReport.summary || ''}\n`
            );
            blocks.push(`${header}\n${String(industryAnalysisReport.markdown || '').trim()}`.trim());
        }

        if (trendingDramasReport?.markdown) {
            const period = trendingDramasReport.report_period || trendingDramasReport.report_month || '';
            const header = t(
                `【${period} AI短剧热榜参考】\n${trendingDramasReport.summary || ''}\n`,
                `[${period} AI Short Drama Trending Reference]\n${trendingDramasReport.summary || ''}\n`
            );
            blocks.push(`${header}\n${String(trendingDramasReport.markdown || '').trim()}`.trim());
        }

        if (blocks.length === 0) return;
        const block = blocks.join('\n\n');
        const nextNotes = globalStoryInput.wild_creative_notes
            ? `${String(globalStoryInput.wild_creative_notes).trim()}\n\n${block}`
            : block;
        setGlobalStoryInput(prev => ({
            ...prev,
            wild_creative_notes: nextNotes,
        }));
        setStoryGenFocusStep('wild_ideas');
        void persistStoryGeneratorInputPatch({ wild_creative_notes: nextNotes }).catch((err) => {
            console.warn('[Market Research] append to wild ideas save failed:', err);
        });
        if (mode === 'market_research' && typeof onTabChange === 'function') {
            onTabChange('generator');
        }
    };

    const handleStructureCreativeInput = async () => {
        const creativeText = String(globalStoryInput.wild_creative_notes || '').trim();
        if (!creativeText) {
            alert(t('请先在「天马行空」输入框中写下创意脑洞。', 'Please write your wild ideas in the brainstorm box first.'));
            return;
        }
        if (isStructuringCreativeInput || isGeneratingGlobalStory) return;

        setIsStructuringCreativeInput(true);
        try {
            const structured = await structureProjectCreativeInput(id, buildScriptAnalysisApiPayload({
                creative_text: creativeText,
                script_mode: globalStoryInput.script_mode,
                target_audience: globalStoryInput.target_audience,
                type: info.type,
                language: info.language,
            }));
            setGlobalStoryInput(prev => {
                const next = { ...prev, wild_creative_notes: prev.wild_creative_notes };
                STORY_PREFILL_KEYS.forEach((key) => {
                    next[key] = String(structured?.[key] ?? '').trim();
                });
                return { ...next, ...rollupSaveTheCat(next) };
            });
            setStoryGenFocusStep('structure_prefill');
            alert(t('已按救猫咪 15 节拍预填。请核对：主控思想是否是「价值+因为」，人物是否有前提、三维和弧光，15 拍是否一拍压一拍，主框架是否现代/当代且辅助至少 5 部。', 'Prefilled on the Save the Cat 15 beats. Check: controlling idea is value-plus-because, characters have premise, dimensions, and an arc, the 15 beats chain, and the primary is modern/contemporary with at least 5 auxiliaries.'));
        } catch (e) {
            console.error(e);
            const readable = formatProviderModelEndpointError(e);
            alert(`${t('结构化失败', 'Structuring failed')}:\n${readable}`);
        } finally {
            setIsStructuringCreativeInput(false);
        }
    };

    const handleGenerateGlobalStory = async () => {
        if (globalStoryGenerationInFlightRef.current || isGeneratingGlobalStory) return;
        globalStoryGenerationInFlightRef.current = true;
        setIsGeneratingGlobalStory(true);
        try {
            const payload = {
                mode: 'global',
                generator_kind: 'story',
                episodes_count: Number(globalStoryInput.episodes_count || 0),
                episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0
                    ? Number(globalStoryInput.episode_duration_minutes)
                    : 1,
                script_mode: globalStoryInput.script_mode,
                target_audience: globalStoryInput.target_audience,
                // Project Overview / Basic Information (forward to LLM)
                script_title: info.script_title,
                expected_duration: info.expected_duration,
                type: info.type,
                language: info.language,
                base_positioning: info.base_positioning,
                Global_Style: info.Global_Style,
                ...storyPrefillPayloadFields(globalStoryInput),
            };
            const updated = await generateProjectStoryGlobal(id, buildScriptAnalysisApiPayload(payload));
            setProject(updated);
            if (updated?.global_info) {
                const merged = {
                    ...info,
                    ...updated.global_info,
                    tech_params: {
                        visual_standard: {
                            ...info.tech_params.visual_standard,
                            ...(updated.global_info.tech_params?.visual_standard || {})
                        }
                    }
                };
                merged.type = normalizeProjectEpisodeType(merged.type);
                merged.language = normalizeProjectEpisodeLanguage(merged.language);
                Object.assign(merged, syncProjectStyleFromPositioning(merged));
                merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
                merged.tone = normalizeProjectEpisodeTone(merged.tone);
                merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
                merged.script_title = stripStackedProductionScriptTitleSuffixes(merged.script_title);
                if (merged.tech_params?.visual_standard) {
                    merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
                }
                setInfo(merged);
            }
            setStoryGenFocusStep('global_framework');
            alert('Global story framework generated and saved to Overview.');
        } catch (e) {
            console.error(e);
            const readable = formatProviderModelEndpointError(e);
            alert(`Failed to generate global story:\n${readable}`);
        } finally {
            setIsGeneratingGlobalStory(false);
            globalStoryGenerationInFlightRef.current = false;
        }
    };

    const handleExportStoryGeneratorPackage = async () => {
        try {
            const pkg = await exportProjectStoryGlobalPackage(id);
            const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const safeName = String(project?.title || `project_${id}`)
                .replace(/[\\/:*?"<>|]+/g, '_')
                .replace(/\s+/g, '_')
                .slice(0, 60);
            a.href = url;
            a.download = `${safeName}_story_generator_global_export.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || String(e);
            alert(`Failed to export Story Generator package: ${detail}`);
        }
    };

    const handleOpenImportStoryGeneratorPackage = () => {
        if (!storyPackageFileInputRef.current) return;
        storyPackageFileInputRef.current.value = '';
        storyPackageFileInputRef.current.click();
    };

    const handleImportStoryGeneratorPackageFile = async (event) => {
        const file = event?.target?.files?.[0];
        if (!file) return;

        setIsImportingStoryPackage(true);
        try {
            const raw = await file.text();
            let parsed;
            try {
                parsed = JSON.parse(raw);
            } catch {
                throw new Error('Invalid JSON file.');
            }

            const payload = {
                project_overview: parsed?.project_overview || {},
                basic_information: parsed?.basic_information || {},
                character_canon_project: parsed?.character_canon_project || {},
                story_generator_global_project: parsed?.story_generator_global_project || {},
                story_generator_global_structured: parsed?.story_generator_global_structured || {},
                story_generator_global_input: parsed?.story_generator_global_input || {},
                story_dna_global_md: parsed?.story_dna_global_md || '',
            };

            const updated = await importProjectStoryGlobalPackage(id, payload);
            setProject(updated);
            if (updated?.global_info) {
                const merged = {
                    ...info,
                    ...updated.global_info,
                    tech_params: {
                        visual_standard: {
                            ...info.tech_params.visual_standard,
                            ...(updated.global_info.tech_params?.visual_standard || {})
                        }
                    }
                };
                setInfo(merged);
                setStoryFrameworkViewMode('preview');

                if (updated.global_info.story_generator_global_input && typeof updated.global_info.story_generator_global_input === 'object') {
                    skipNextGlobalStoryAutosaveRef.current = true;
                    setGlobalStoryInput(prev => ({
                        ...prev,
                        ...updated.global_info.story_generator_global_input,
                        episode_duration_minutes: Number(updated.global_info.story_generator_global_input.episode_duration_minutes) > 0
                            ? Number(updated.global_info.story_generator_global_input.episode_duration_minutes)
                            : 1,
                    }));
                    if (updated.global_info.story_generator_global_input.trending_ai_short_dramas_report) {
                        setTrendingDramasReport(updated.global_info.story_generator_global_input.trending_ai_short_dramas_report);
                    }
                    if (updated.global_info.story_generator_global_input.ai_short_drama_industry_report) {
                        setIndustryAnalysisReport(updated.global_info.story_generator_global_input.ai_short_drama_industry_report);
                    }
                }

                // Restore Character Canon draft inputs/categories immediately after package import
                const importedCanonDraft = updated.global_info.character_canon_input;
                if (importedCanonDraft && typeof importedCanonDraft === 'object') {
                    if (typeof importedCanonDraft.name === 'string') setCanonName(importedCanonDraft.name);
                    if (Array.isArray(importedCanonDraft.selected_identity_ids)) setCanonSelectedIdentityIds(importedCanonDraft.selected_identity_ids);
                    if (Array.isArray(importedCanonDraft.selected_tag_ids)) setCanonSelectedTagIds(importedCanonDraft.selected_tag_ids);
                    if (typeof importedCanonDraft.custom_identity === 'string') setCanonCustomIdentity(importedCanonDraft.custom_identity);
                    if (typeof importedCanonDraft.body_features === 'string') setCanonBody(importedCanonDraft.body_features);
                    if (typeof importedCanonDraft.custom_style_tags === 'string') setCanonCustomTags(importedCanonDraft.custom_style_tags);
                    if (typeof importedCanonDraft.extra_notes === 'string') setCanonExtra(importedCanonDraft.extra_notes);
                }

                if (Array.isArray(updated.global_info.character_canon_tag_categories)) {
                    const normalizedTags = normalizeCanonTagCategories(updated.global_info.character_canon_tag_categories);
                    if (normalizedTags) setCanonTagCategories(normalizedTags);
                }

                if (Array.isArray(updated.global_info.character_canon_identity_categories)) {
                    const normalizedIdentities = normalizeCanonTagCategories(updated.global_info.character_canon_identity_categories);
                    if (normalizedIdentities) setCanonIdentityCategories(normalizedIdentities);
                }
            }

            alert('Story Generator package imported and saved to this project.');
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || String(e);
            alert(`Failed to import Story Generator package: ${detail}`);
        } finally {
            setIsImportingStoryPackage(false);
        }
    };

    const handleGenerateEpisodeScripts = async ({ retryFailedOnly = false, forceStart = false, specificEpisode = null, outputKind = null } = {}) => {
        if (episodeScriptsGenerationInFlightRef.current || isGeneratingEpisodeScripts || isStoppingEpisodeScripts) return;
        episodeScriptsGenerationInFlightRef.current = true;
        if (!id) {
            addLog?.('Cannot generate episode scripts: missing project id.', 'error');
            alert('Cannot generate episode scripts: missing project id.');
            episodeScriptsGenerationInFlightRef.current = false;
            return;
        }
        const generatorKind = projectTab === 'promo_generator' ? 'promo' : 'story';
        const n = Number(
            projectTab === 'promo_generator'
                ? (promoInput.episodes_count || 0)
                : (globalStoryInput.episodes_count || 0)
        );
        const trailerMode = outputKind === 'trailer';
        const seriesIpMode = isSeriesIpScriptMode(globalStoryInput.script_mode);
        if (seriesIpMode && !trailerMode && !specificEpisode) {
            alert('系列剧（IP模式）不预生成全部分集。请填写这一集的基本剧情和冲突，再用单集生成。');
            episodeScriptsGenerationInFlightRef.current = false;
            return;
        }
        if (seriesIpMode && !trailerMode && specificEpisode) {
            const plot = String(globalStoryInput.ip_episode_plot || '').trim();
            const conflict = String(globalStoryInput.ip_episode_conflict || '').trim();
            if (!plot || !conflict) {
                alert('系列剧（IP模式）需要填写本集基本剧情，以及要体现的冲突。');
                episodeScriptsGenerationInFlightRef.current = false;
                return;
            }
        }
        if (!specificEpisode && (!n || Number.isNaN(n) || n <= 0)) {
            alert(trailerMode
                ? '请先填写集数。预告片默认从第 1 集取到最后一集。'
                : 'Please set a valid Episodes Count first.');
            episodeScriptsGenerationInFlightRef.current = false;
            return;
        }
        let trailerFromNum = null;
        let trailerToNum = null;
        let trailerFocusText = '';
        if (trailerMode) {
            const readBound = (raw) => {
                const text = String(raw || '').trim();
                if (!text) return null;
                const num = Number(text);
                if (!Number.isInteger(num) || num <= 0) return NaN;
                return num;
            };
            const fromBound = readBound(trailerEpisodeFrom);
            const toBound = readBound(trailerEpisodeTo);
            if (Number.isNaN(fromBound) || Number.isNaN(toBound)) {
                alert('起始集和结束集必须是正整数。留空表示从头到尾。');
                episodeScriptsGenerationInFlightRef.current = false;
                return;
            }
            trailerFromNum = fromBound || 1;
            trailerToNum = toBound || n;
            trailerFocusText = String(trailerFocus || '').trim();
            if (trailerFocusText.length > 800) {
                alert('侧重点请控制在 800 字以内。');
                episodeScriptsGenerationInFlightRef.current = false;
                return;
            }
            if (trailerFromNum > trailerToNum || trailerFromNum > n || trailerToNum > n) {
                alert(`取材范围须落在第 1 集到第 ${n} 集之间，且起始集不能大于结束集。`);
                episodeScriptsGenerationInFlightRef.current = false;
                return;
            }
        }

        setIsGeneratingEpisodeScripts(true);
        setEpisodeScriptsProgress(null);
        setShowEpisodeScriptsProgressModal(true);
        if (generatorKind === 'story') setStoryGenFocusStep('episode_scripts');

        if (episodeScriptsStatusTimerRef.current) {
            clearInterval(episodeScriptsStatusTimerRef.current);
            episodeScriptsStatusTimerRef.current = null;
        }

        episodeScriptsStatusTimerRef.current = setInterval(pollEpisodeScriptsStatus, 3000);
        pollEpisodeScriptsStatus();

        try {
            const overwriteExisting = true;
            const modeLabel = retryFailedOnly
                ? 'retry-failed-only'
                : trailerMode ? 'generate-trailer'
                : specificEpisode ? `generate-episode-${specificEpisode}`
                : 'overwrite-all-default';

            if (trailerMode) {
                const focusLine = trailerFocusText
                    ? `侧重点：${trailerFocusText}。`
                    : '未指定侧重点，按这一段的来龙去脉取样。';
                const ok = await confirmUiMessage(
                    `将新写一条预告片，不覆盖已有预告片和正片。取材第 ${trailerFromNum} 集到第 ${trailerToNum} 集。${focusLine}是否继续？`,
                    `This adds a new trailer and does not overwrite existing trailers or episodes. It samples episodes ${trailerFromNum}–${trailerToNum}. ${trailerFocusText ? `Focus: ${trailerFocusText}. ` : 'No focus set. '}Continue?`
                );
                if (!ok) {
                    addLog?.('Trailer generation canceled.', 'warning');
                    return;
                }
            } else if (overwriteExisting && !specificEpisode) {
                const ok = await confirmUiMessage('默认会覆盖目标范围内已有分集剧本，是否继续？', 'This will overwrite existing episode scripts in the target range by default. Continue?');
                if (!ok) {
                    addLog?.('Force Start canceled.', 'warning');
                    return;
                }
            } else if (specificEpisode) {
                const ok = await confirmUiMessage(`确定要单独生成第 ${specificEpisode} 集的剧本吗？这会覆盖已有内容。`, `Are you sure you want to regenerate episode ${specificEpisode}? This will overwrite existing script.`);
                if (!ok) {
                    addLog?.('Single Episode Generation canceled.', 'warning');
                    return;
                }
            }

            addLog?.(`Generating episode scripts (${modeLabel}, target 1..${n})... (This may take several minutes)`, 'process');
            addLog?.(
                `[DEBUG][Before API] Generate Episode Scripts payload: ${JSON.stringify({ generator_kind: generatorKind, episodes_count: n, episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1, script_mode: globalStoryInput.script_mode, script_title: info?.script_title || project?.title || '', overwrite_existing: overwriteExisting, retry_failed_only: retryFailedOnly, episode_number: specificEpisode, episode_generation_guidance_len: String(globalStoryInput.episode_generation_guidance || '').trim().length })}`,
                'info'
            );
            const reqPayload = {
                generator_kind: generatorKind,
                episodes_count: n,
                episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0
                    ? Number(globalStoryInput.episode_duration_minutes)
                    : 1,
                script_mode: globalStoryInput.script_mode,
                target_audience: globalStoryInput.target_audience,
                script_title: String(info?.script_title || project?.title || '').trim(),
                overwrite_existing: overwriteExisting,
                retry_failed_only: retryFailedOnly,
                ...(trailerMode ? {
                    output_kind: 'trailer',
                    trailer_episode_from: trailerFromNum,
                    trailer_episode_to: trailerToNum,
                    ...(trailerFocusText ? { trailer_focus: trailerFocusText } : {}),
                } : {}),
            };
            if (specificEpisode) {
                reqPayload.episode_number = Number(specificEpisode);
                const seriesIpGuidance = seriesIpMode ? composeSeriesIpEpisodeGuidance(globalStoryInput) : '';
                const guidance = seriesIpGuidance || String(globalStoryInput.episode_generation_guidance || '').trim();
                if (guidance) {
                    reqPayload.episode_generation_guidance = guidance;
                    reqPayload.ip_episode_plot = String(globalStoryInput.ip_episode_plot || '').trim();
                    reqPayload.ip_episode_conflict = String(globalStoryInput.ip_episode_conflict || '').trim();
                    reqPayload.ip_episode_highlights = String(globalStoryInput.ip_episode_highlights || '').trim();
                    reqPayload.ip_episode_reference = String(globalStoryInput.ip_episode_reference || '').trim();
                    void persistStoryGeneratorInputPatch({
                        episode_generation_guidance: guidance,
                        ip_episode_plot: reqPayload.ip_episode_plot,
                        ip_episode_conflict: reqPayload.ip_episode_conflict,
                        ip_episode_highlights: reqPayload.ip_episode_highlights,
                        ip_episode_reference: reqPayload.ip_episode_reference,
                    }).catch(() => {});
                }
            }
            const res = await generateProjectEpisodeScripts(id, buildScriptAnalysisApiPayload(reqPayload));

            await pollEpisodeScriptsStatus();
            addLog?.(
                `[DEBUG][After API] response summary: ${JSON.stringify({
                    project_id: res?.project_id,
                    episodes_target: res?.episodes_target,
                    episodes_generated: res?.episodes_generated,
                    episodes_created: res?.episodes_created,
                    results_count: Array.isArray(res?.results) ? res.results.length : 0,
                    errors_count: Array.isArray(res?.errors) ? res.errors.length : 0,
                })}`,
                'info'
            );

            const dbg = res?.debug_context || {};
            addLog?.(
                `[DEBUG][Input Confirm] Character relationships imported: ${dbg.has_character_relationships ? 'YES' : 'NO'}; ` +
                `Character source: ${dbg.character_canon_source || 'unknown'}; ` +
                `Global DNA len: ${dbg.global_story_dna_length ?? 0}; Character canon len: ${dbg.character_canon_length ?? 0}`,
                'info'
            );
            const created = Number(res?.episodes_created ?? 0);
            const errors = Array.isArray(res?.errors) ? res.errors : [];
            const results = Array.isArray(res?.results) ? res.results : [];
            const generatedCount = Number(res?.episodes_generated ?? results.filter(r => r?.generated === true).length);
            const generated = Number.isFinite(generatedCount) ? generatedCount : results.filter(r => r?.generated === true).length;
            const skipped = results.filter(r => r?.skipped === true).length;
            const generatedEpisodeIds = results
                .filter((item) => item?.generated && Number(item?.episode_id || 0) > 0)
                .map((item) => Number(item.episode_id));
            const summary = `Generated: ${generated}, Skipped: ${skipped}, Created Episodes: ${created}, Errors: ${errors.length}`;
            if (errors.length > 0) {
                addLog?.(`Episode script generation finished. ${summary}`, 'warning');
                alert(`Episode script generation finished. ${summary}`);
            } else {
                addLog?.(`Episode script generation finished. ${summary}`, 'success');
                alert(`Episode script generation finished. ${summary}`);
            }
            if (onProjectUpdate) {
                await onProjectUpdate();
            }
            if (onRefreshEpisodes) {
                await onRefreshEpisodes({ invalidateEpisodeIds: generatedEpisodeIds });
            }

            // In single-episode or trailer mode, jump directly to the resolved episode_id returned by backend.
            if (trailerMode || specificEpisode) {
                const generatedSingle = trailerMode
                    ? (results.find((item) => item && Number(item.episode_id || 0) > 0 && Boolean(item.generated)) || null)
                    : results.find((item) => {
                    if (!item || typeof item !== 'object') return false;
                    const num = Number(item.episode_number || 0);
                    const eid = Number(item.episode_id || 0);
                    return num === Number(specificEpisode) && eid > 0 && Boolean(item.generated);
                }) || results.find((item) => {
                    if (!item || typeof item !== 'object') return false;
                    const eid = Number(item.episode_id || 0);
                    return eid > 0 && Boolean(item.generated);
                });

                const resolvedEpisodeId = Number(generatedSingle?.episode_id || 0);
                const resolvedTitle = String(generatedSingle?.episode_title || '').trim();
                if (resolvedEpisodeId > 0 && onJumpToEpisode) {
                    addLog?.(
                        `[Single Episode] Jumping to generated episode_id=${resolvedEpisodeId}${resolvedTitle ? ` title=${resolvedTitle}` : ''}`,
                        'info'
                    );
                    onJumpToEpisode(resolvedEpisodeId, { forceReload: true });
                }
            }
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.response?.data?.message || e?.message || String(e);
            addLog?.(`Episode script generation failed: ${detail}`, 'error');
            alert(`Failed to generate episode scripts: ${detail}`);
        } finally {
            if (episodeScriptsStatusTimerRef.current) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
            setIsGeneratingEpisodeScripts(false);
            setShowEpisodeScriptsProgressModal(false);
            setEpisodeScriptsProgress(prev => {
                if (prev) {
                    return { ...prev, running: false };
                }
                return null;
            });
            episodeScriptsGenerationInFlightRef.current = false;
        }
    };

    const handleStopEpisodeScripts = async () => {
        if (!id) return;
        setIsStoppingEpisodeScripts(true);
        try {
            const res = await stopProjectEpisodeScripts(id);
            // Force-reset local state to stopped
            setEpisodeScriptsProgress((prev) => {
                if (!prev || typeof prev !== 'object') return prev;
                return {
                    ...prev,
                    running: false,
                    stop_requested: true,
                    force_stopped: true,
                    status: 'canceled',
                    message: res?.message || 'Force stopped',
                };
            });
            // Also release the frontend generating lock so UI unblocks
            setIsGeneratingEpisodeScripts(false);
            // Clear polling timer
            if (episodeScriptsStatusTimerRef.current) {
                clearInterval(episodeScriptsStatusTimerRef.current);
                episodeScriptsStatusTimerRef.current = null;
            }
            addLog?.(res?.message || 'Force stopped episode scripts task.', 'warning');
            await pollEpisodeScriptsStatus();
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || String(e);
            addLog?.(`Stop episode scripts failed: ${detail}`, 'error');
            alert(`Failed to stop episode scripts: ${detail}`);
        } finally {
            setIsStoppingEpisodeScripts(false);
        }
    };

    const handleGenerateProjectCanon = async () => {
        if (projectCanonGenerationInFlightRef.current || isGeneratingCanon) return;
        projectCanonGenerationInFlightRef.current = true;
        const name = (canonName || '').trim();
        if (!name) {
            alert('请输入角色名称');
            projectCanonGenerationInFlightRef.current = false;
            return;
        }

        const custom = (canonCustomTags || '')
            .split(/[,，\n]/)
            .map(t => t.trim())
            .filter(Boolean);
        const selectedStrings = canonSelectedTagStrings();
        const style_tags = Array.from(new Set([...(selectedStrings || []), ...custom]));

        const identityCustom = (canonCustomIdentity || '')
            .split(/[,，\n]/)
            .map(t => t.trim())
            .filter(Boolean);
        const identityStrings = canonSelectedIdentityStrings();
        const identityMerged = Array.from(new Set([...(identityStrings || []), ...identityCustom]));
        const identity = identityMerged.join(' / ');

        setIsGeneratingCanon(true);
        try {
            const updated = await generateProjectCharacterProfile(id, buildScriptAnalysisApiPayload({
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
            }));
            setProject(updated);
            if (updated?.global_info) {
                const merged = {
                    ...info,
                    ...updated.global_info,
                    tech_params: {
                        visual_standard: {
                            ...info.tech_params.visual_standard,
                            ...(updated.global_info.tech_params?.visual_standard || {})
                        }
                    }
                };
                setInfo(merged);
            }
            setShowCanonModal(false);
            alert('Character Canon generated and appended in Overview.');
        } catch (e) {
            console.error(e);
            alert(`Failed to generate Character Canon: ${e.message}`);
        } finally {
            setIsGeneratingCanon(false);
            projectCanonGenerationInFlightRef.current = false;
        }
    };

    const updateField = (key, value) => {
        if (key === 'base_positioning') {
            setInfo(prev => applyStyleModeDefaults(prev, value));
            return;
        }
        setInfo(prev => ({
            ...prev,
            [key]: key === 'type'
                ? normalizeProjectEpisodeType(value)
                : key === 'language'
                    ? normalizeProjectEpisodeLanguage(value)
                        : key === 'Global_Style'
                            ? normalizeProjectEpisodeGlobalStyle(value)
                            : key === 'tone'
                                ? normalizeProjectEpisodeTone(value)
                                : key === 'lighting'
                                    ? normalizeProjectEpisodeLighting(value)
                        : key === 'project_share_users' || key === 'project_reviewer_users'
                            ? normalizeUserListValues(value)
                        : value,
        }));
    };

    const updateTech = (key, value) => {
        setInfo(prev => {
            const prevVisual = prev?.tech_params?.visual_standard || {};
            const nextValue = key === 'quality'
                ? normalizeProjectEpisodeQuality(value)
                : (key === 'video_resolution' ? (normalizeProjectVideoResolution(value) || '720') : value);
            const nextVisual = {
                ...prevVisual,
                [key]: nextValue,
            };

            // Keep resolution aligned with aspect ratio + image size selection.
            if (key === 'aspect_ratio' || key === 'image_size') {
                const preset = getResolutionByAspectAndImageSize(
                    key === 'aspect_ratio' ? nextValue : nextVisual.aspect_ratio,
                    key === 'image_size' ? nextValue : nextVisual.image_size,
                );
                if (preset) {
                    nextVisual.horizontal_resolution = preset.width;
                    nextVisual.vertical_resolution = preset.height;
                }
            }

            return {
                ...prev,
                tech_params: {
                    ...prev.tech_params,
                    visual_standard: nextVisual,
                },
            };
        });
    };

    const handleBorrowedFilmsChange = (str) => {
        const arr = str.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        setInfo(prev => ({ ...prev, borrowed_films: arr }));
    };

    const isGeneratorMode = mode === 'generator';
    const episodeScriptResults = isGeneratorMode && Array.isArray(episodeScriptsProgress?.results) ? episodeScriptsProgress.results : [];
    const episodesInRun = isGeneratorMode ? Number(episodeScriptsProgress?.episodes_in_run || 0) : 0;
    const processedCount = isGeneratorMode ? Number(episodeScriptsProgress?.processed || 0) : 0;
    const progressPercent = episodesInRun > 0 ? Math.min(100, Math.round((processedCount / episodesInRun) * 100)) : 0;
    const episodeScriptsRunning = Boolean(episodeScriptsProgress?.running) || isGeneratingEpisodeScripts;
    const episodeScriptsStopRequested = Boolean(episodeScriptsProgress?.stop_requested);
    const storyGeneratorInheritedInfo = useMemo(() => {
        const resolvedScriptTitle = String(info?.script_title || project?.title || '').trim();
        const resolvedType = String(info?.type || '').trim();
        const resolvedLanguage = String(info?.language || '').trim();
        const resolvedBasePositioning = String(info?.base_positioning || info?.style_mode || '').trim();
        const resolvedGlobalStyle = String(info?.Global_Style || '').trim();
        return [
            { label: t('剧本标题', 'Script Title'), value: resolvedScriptTitle },
            { label: t('类型', 'Type'), value: resolvedType },
            { label: t('语言', 'Language'), value: resolvedLanguage },
            { label: t('剧本模式 (基础定位)', 'Script Mode (Base Positioning)'), value: resolvedBasePositioning },
            { label: t('全局风格', 'Global Style'), value: resolvedGlobalStyle },
        ];
    }, [info?.script_title, info?.type, info?.language, info?.base_positioning, info?.style_mode, info?.Global_Style, project?.title, t]);
    const storyGeneratorMissingInfo = useMemo(() => {
        const missing = [];
        if (!String(info?.script_title || project?.title || '').trim()) missing.push(t('剧本标题', 'Script Title'));
        if (!String(info?.type || '').trim()) missing.push(t('类型', 'Type'));
        if (!String(info?.language || '').trim()) missing.push(t('语言', 'Language'));
        if (!String(info?.base_positioning || '').trim()) missing.push(t('剧本模式 (基础定位)', 'Script Mode (Base Positioning)'));
        if (!String(info?.Global_Style || '').trim()) missing.push(t('全局风格', 'Global Style'));
        return missing;
    }, [info?.script_title, info?.type, info?.language, info?.base_positioning, info?.Global_Style, project?.title, t]);

    const episodeTitleByNumber = useMemo(() => {
        if (!isGeneratorMode) return new Map();
        const titleMap = new Map();
        (Array.isArray(episodes) ? episodes : []).forEach((ep, index) => {
            const parsedNumber = Number(ep?.episode_number) > 0
                ? Number(ep?.episode_number)
                : (parseEpisodeNumberFromText(ep?.title) || (index + 1));
            if (!parsedNumber || titleMap.has(parsedNumber)) return;
            titleMap.set(parsedNumber, String(ep?.title || '').trim());
        });
        return titleMap;
    }, [episodes, isGeneratorMode]);

    const episodeResultRows = useMemo(() => {
        if (!isGeneratorMode || !episodeScriptsProgress || episodesInRun <= 0) return [];
        const byEpisodeNumber = new Map();
        for (const item of episodeScriptResults) {
            const num = Number(item?.episode_number || 0);
            if (!num) continue;
            byEpisodeNumber.set(num, item);
        }

        // Prefer concrete episode numbers returned by backend (especially in single-episode mode)
        // so the progress table does not incorrectly remap episode 2 as row 1.
        const resultEpisodeNumbers = Array.from(byEpisodeNumber.keys())
            .filter((n) => Number.isFinite(n) && n > 0)
            .sort((a, b) => a - b);
        const plannedEpisodeNumbers = resultEpisodeNumbers.length > 0
            ? resultEpisodeNumbers
            : Array.from({ length: episodesInRun }, (_, idx) => idx + 1);

        const rows = [];
        for (const i of plannedEpisodeNumbers) {
            const row = byEpisodeNumber.get(i);
            const knownTitle = episodeTitleByNumber.get(i);
            if (row) {
                rows.push({
                    episode_number: i,
                    episode_id: row?.episode_id,
                    project_episode_title: row?.project_episode_title || knownTitle || t(`第 ${i} 集`, `Episode ${i}`),
                    episode_title: row?.episode_title || knownTitle || t(`第 ${i} 集`, `Episode ${i}`),
                    llm_episode_number: row?.llm_episode_number,
                    title_mismatch: Boolean(row?.title_mismatch),
                    status: row?.status || (row?.generated ? 'generated' : row?.skipped ? 'skipped' : row?.error ? 'failed' : 'unknown'),
                    output_chars: row?.output_chars,
                    error: row?.error,
                    reason: row?.reason,
                });
            } else {
                rows.push({
                    episode_number: i,
                    episode_title: knownTitle || t(`第 ${i} 集`, `Episode ${i}`),
                    status: 'pending',
                });
            }
        }
        return rows;
    }, [episodeScriptsProgress, episodeScriptResults, episodesInRun, episodeTitleByNumber, isGeneratorMode, t]);

    const failedEpisodeRows = useMemo(() => {
        if (!isGeneratorMode || episodeResultRows.length === 0) return [];
        return episodeResultRows.filter(item => item?.status === 'failed' && item?.episode_id);
    }, [episodeResultRows, isGeneratorMode]);

    const seriesIpMode = isSeriesIpScriptMode(globalStoryInput.script_mode);
    const priorEpisodeSummaries = useMemo(() => {
        if (!seriesIpMode) return [];
        const rows = [];
        const seen = new Set();
        (Array.isArray(episodes) ? episodes : []).forEach((ep, index) => {
            if (String(ep?.episode_info?.script_output_kind || '') === 'trailer') return;
            const parsedNumber = Number(ep?.episode_info?.episode_script_episode_number) > 0
                ? Number(ep.episode_info.episode_script_episode_number)
                : (Number(ep?.episode_number) > 0
                    ? Number(ep.episode_number)
                    : (parseEpisodeNumberFromText(ep?.title) || (index + 1)));
            if (!parsedNumber || seen.has(parsedNumber)) return;
            const summary = String(ep?.episode_info?.series_episode_summary || '').trim();
            const hasScript = Boolean(String(ep?.script_content || '').trim());
            if (!summary && !hasScript) return;
            seen.add(parsedNumber);
            rows.push({
                number: parsedNumber,
                title: String(ep?.title || '').trim(),
                summary,
            });
        });
        rows.sort((a, b) => a.number - b.number);
        return rows;
    }, [seriesIpMode, episodes]);

    const STORY_GEN_STEP_LABELS = {
        wild_ideas: { zh: '输入天马行空想法', en: 'Wild Ideas' },
        structure_prefill: { zh: '结构化预填', en: 'Structure & Prefill' },
        global_framework: { zh: '全局框架生成', en: 'Global Framework' },
        episode_scripts: { zh: '分集生成', en: 'Episode Generation' },
    };
    const getStoryGenStepLabel = (key) => {
        const row = STORY_GEN_STEP_LABELS[key];
        return row ? t(row.zh, row.en) : key;
    };
    const wildIdeasReady = Boolean(String(globalStoryInput?.wild_creative_notes || '').trim());
    const structurePrefillReady = Boolean(String(globalStoryInput?.logline || '').trim());
    const globalFrameworkReady = Boolean(String(info?.story_dna_global_md || '').trim());
    const episodeScriptsGeneratedCount = Number(episodeScriptsProgress?.generated || 0);
    const episodeScriptsReady = !episodeScriptsRunning
        && (episodeScriptsGeneratedCount > 0
            || failedEpisodeRows.length > 0
            || Number(episodeScriptsProgress?.processed || 0) > 0);
    const structurePrefillActive = isStructuringCreativeInput;
    const globalFrameworkActive = isGeneratingGlobalStory;
    const episodeScriptsActive = episodeScriptsRunning;
    const scrollToStoryGenStep = (stepKey) => {
        setStoryGenFocusStep(stepKey);
        const el = storyGenStepRefs.current?.[stepKey];
        if (el && typeof el.scrollIntoView === 'function') {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    const shouldComputeCostPanel = mode === 'overview' && expandedSections.cost;

    const episodeCostChart = useMemo(() => {
        if (!shouldComputeCostPanel) return { rows: [], maxStage: 0 };
        const rows = (costEstimation && typeof costEstimation === 'object' && Array.isArray(costEstimation.episode_costs))
            ? costEstimation.episode_costs
            : [];
        const normalized = rows.map((item, idx) => {
            const overviewCost = Number(item?.overview_cost || 0);
            const hasSuggestedField = Object.prototype.hasOwnProperty.call((item || {}), 'suggested_cost');
            const suggestedCost = Number(hasSuggestedField ? (item?.suggested_cost || 0) : (item?.budget_cost || 0));
            const budgetCost = Number(hasSuggestedField ? (item?.budget_cost || 0) : (item?.execution_cost || 0));
            const currentEstimatedCost = Number(item?.current_estimated_cost || item?.total_cost || 0);
            const episodeNo = Number(item?.episode_number || (idx + 1));
            return {
                episode_number: Number.isFinite(episodeNo) ? episodeNo : (idx + 1),
                episode_title: String(item?.episode_title || ''),
                overview_cost: Number.isFinite(overviewCost) ? overviewCost : 0,
                suggested_cost: Number.isFinite(suggestedCost) ? suggestedCost : 0,
                budget_cost: Number.isFinite(budgetCost) ? budgetCost : 0,
                current_stage: String(item?.current_stage || ''),
                current_estimated_cost: Number.isFinite(currentEstimatedCost) ? currentEstimatedCost : 0,
            };
        });
        const maxStage = normalized.reduce((acc, row) => Math.max(acc, row.overview_cost, row.suggested_cost, row.budget_cost), 0);
        return { rows: normalized, maxStage };
    }, [costEstimation, shouldComputeCostPanel]);

    const costExecutionSuggestions = useMemo(() => {
        if (!shouldComputeCostPanel) return [];
        const suggestions = (costEstimation && typeof costEstimation === 'object' && Array.isArray(costEstimation.execution_suggestions))
            ? costEstimation.execution_suggestions
            : [];
        return suggestions.filter((item) => typeof item === 'string' && item.trim().length > 0);
    }, [costEstimation, shouldComputeCostPanel]);

    const hasNewCostSchema = useMemo(() => {
        if (!shouldComputeCostPanel) return false;
        if (!costEstimation || typeof costEstimation !== 'object') return false;
        if (Object.prototype.hasOwnProperty.call((costEstimation?.summary || {}), 'suggested_estimate')) return true;
        const firstRow = Array.isArray(costEstimation?.episode_costs) ? costEstimation.episode_costs[0] : null;
        return !!(firstRow && Object.prototype.hasOwnProperty.call(firstRow, 'suggested_cost'));
    }, [costEstimation, shouldComputeCostPanel]);

    const costStageLabel = useCallback((stageKey) => {
        const key = String(stageKey || '').trim();
        if (key === 'overview') return t('概要成本', 'Overview Cost');
        if (key === 'suggested') return t('建议成本', 'Suggested Cost');
        if (key === 'budget') return hasNewCostSchema ? t('预算成本', 'Budget Cost') : t('建议成本', 'Suggested Cost');
        if (key === 'execution') return t('预算成本', 'Budget Cost');
        return key || t('概要成本', 'Overview Cost');
    }, [hasNewCostSchema, t]);

    useTabMediaRefreshEffect({
        tabMediaRefreshSignal,
        isTabActive,
        onRefresh: () => {
            if (typeof onProjectUpdate === 'function') {
                void onProjectUpdate();
            }
            if (typeof onRefreshEpisodes === 'function') {
                void onRefreshEpisodes();
            }
        },
    });

    if (!project) return <div className="p-8 text-muted-foreground">{t('加载中...', 'Loading...')}</div>;

    const prefix = "proj-";
    const generatorTabs = [
        { id: 'story_generator', label: t('故事生成器', 'Story Generator') },
    ];

    const industryHistoryOptions = marketIntelHistory.filter((item) => item.report_kind === 'industry_analysis');
    const trendingHistoryOptions = marketIntelHistory.filter((item) => item.report_kind === 'trending_dramas');
    const formatMarketIntelOptionLabel = (item) => {
        const month = item.report_month || item.report_period || '';
        const when = item.fetched_at || item.created_at || '';
        return [month, when].filter(Boolean).join(' · ') || `#${item.id}`;
    };

    return (
        <div className="p-4 sm:p-6 lg:p-8 w-full h-full overflow-y-auto">
            <MarkdownHelpModal
                open={manualModalOpen}
                initialDocKey="generation"
                onClose={() => setManualModalOpen(false)}
                uiLang={uiLang}
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center mb-8">
                <div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold">
                        {mode === 'generator'
                            ? t('生成器', 'Generators')
                            : mode === 'market_research'
                                ? t('行业分析 & 热榜', 'Industry & Trending')
                                : t('项目总览', 'Project Overview')}
                    </h2>
                    {mode === 'overview' && (
                        <div className="flex items-center px-3 py-1 rounded-full bg-primary/20 border border-primary/30 text-primary text-sm font-medium">
                            {t('阶段', 'Stage')}: {
                                (info?.workflow_stage === 'montage' || info?.workflow_stage === 'shots') ? t('分镜', 'Shots') :
                                (info?.workflow_stage === 'subjects') ? t('资产', 'Assets') :
                                t('剧本', 'Script')
                            }
                        </div>
                    )}
                </div>
                <div className="flex flex-col items-stretch sm:items-end gap-2 w-full sm:w-auto">
                    {mode !== 'market_research' && (
                        <TabMediaRefreshButton
                            onClick={() => onMediaRefreshRequest?.()}
                            uiLang={uiLang}
                            className="w-full sm:w-auto"
                        />
                    )}
                    {mode === 'market_research' && (
                        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
                            <FunctionApiSelector
                                functionName="script_analysis"
                                configs={functionApiConfigs}
                                label={t('剧本分析 API', 'Script Analysis API')}
                                value={selectedScriptAnalysisApiId}
                                onChange={setSelectedScriptAnalysisApiId}
                                className="sm:justify-end"
                            />
                        </div>
                    )}
                    {mode === 'generator' && (
                        <button
                            type="button"
                            onClick={() => setManualModalOpen(true)}
                            className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20 border border-white/10 flex items-center justify-center gap-2 w-full sm:w-auto"
                            title={t('查看生成剧本操作手册', 'View script generation manual')}
                        >
                            <Info className="w-4 h-4" /> {t('生成剧本操作手册', 'Script Generation Manual')}
                        </button>
                    )}
                    {mode !== 'market_research' && (
                        <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center justify-center gap-2 w-full sm:w-auto">
                            <SettingsIcon className="w-4 h-4" /> {t('保存修改', 'Save Changes')}
                        </button>
                    )}
                    {mode === 'generator' && generatorAutosaveFeedback.phase !== 'idle' && (
                        <div
                            className={`text-xs px-3 py-1 rounded-full border ${generatorAutosaveFeedback.phase === 'error' ? 'border-red-400/40 text-red-200 bg-red-500/10' : generatorAutosaveFeedback.phase === 'saved' ? 'border-emerald-400/40 text-emerald-200 bg-emerald-500/10' : 'border-white/20 text-white/80 bg-white/5'}`}
                        >
                            {generatorAutosaveFeedback.phase === 'saving' && <Loader2 className="w-3 h-3 inline-block mr-1 animate-spin" />}
                            {generatorAutosaveFeedback.message}
                        </div>
                    )}
                </div>
            </div>

            {mode === 'generator' && (
                <div className="mb-6 space-y-3">
                    <div className="sm:hidden">
                        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/80">
                            {t('生成器模块', 'Generator Mode')}
                        </label>
                        <select
                            value={projectTab}
                            onChange={(e) => setProjectTab(e.target.value)}
                            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none transition-colors focus:border-primary/40"
                        >
                            {generatorTabs.map((tab) => (
                                <option key={`generator-tab-select-${tab.id}`} value={tab.id}>{tab.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="overflow-x-auto no-scrollbar">
                            <div className="flex items-center gap-2 min-w-max">
                                {generatorTabs.map((tab) => (
                                    <button
                                        key={`generator-tab-${tab.id}`}
                                        onClick={() => setProjectTab(tab.id)}
                                        className={`shrink-0 px-4 py-2 rounded-lg text-sm font-bold ${projectTab === tab.id ? 'bg-white text-black' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                    >
                                        {tab.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <FunctionApiSelector
                            functionName="script_analysis"
                            configs={functionApiConfigs}
                            label={t('剧本分析 API', 'Script Analysis API')}
                            value={selectedScriptAnalysisApiId}
                            onChange={setSelectedScriptAnalysisApiId}
                            className="sm:justify-end"
                        />
                    </div>
                </div>
            )}

            {mode === 'generator' && (
                // Keeping generator container if it has its own needs
                <div className="grid grid-cols-1 gap-6 sm:gap-8 w-full">
                </div>
            )}
            
            <div className="flex flex-col gap-6 sm:gap-8 w-full">
                {mode === 'overview' && (
                <div className="bg-card border border-white/10 rounded-xl overflow-hidden">
                    <button 
                        onClick={() => toggleSection('basic')}
                        className="w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        <h3 className="text-lg font-semibold text-primary">{t('基本信息', 'Basic Information')}</h3>
                        <ChevronDown className={`w-5 h-5 transition-transform ${expandedSections.basic ? 'rotate-180' : ''}`} />
                    </button>
                    <AnimatePresence initial={false}>
                        {expandedSections.basic && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: 'easeInOut' }}
                                className="border-t border-white/10"
                            >
                                <div className="p-4 sm:p-6 space-y-6">
                                    <div className="grid grid-cols-1 gap-4">
                                        <InputGroup idPrefix={prefix} label={t('剧本标题', 'Script Title')} value={info.script_title} onChange={v => updateField('script_title', v)} placeholder={t('例如：我的科幻史诗', 'e.g. My Sci-Fi Epic')} />
                                        <InputGroup idPrefix={prefix} label={t('预期时长(秒)', 'Expected Duration (s)')} type="number" min="1" value={info.expected_duration || ''} onChange={v => updateField('expected_duration', v)} placeholder="60" />
                                        <InputGroup idPrefix={prefix} label={t('分镜最长秒数', 'Max Shot Seconds')} type="number" min="4" value={info.max_shot_seconds || String(DEFAULT_MAX_SHOT_SECONDS)} onChange={v => updateField('max_shot_seconds', v)} placeholder={String(DEFAULT_MAX_SHOT_SECONDS)} />
                                    </div>

<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('类型', 'Type')}
                            value={info.type}
                            onChange={v => updateField('type', v)}
                            list={PROJECT_EP_TYPE_OPTIONS}
                        />
                         <InputGroup idPrefix={prefix}
                            label={t('国家地域', 'Country/Region')}
                            value={info.country_region}
                            onChange={v => updateField('country_region', v)}
                            list={PROJECT_EP_COUNTRY_REGION_OPTIONS}
                        />
                         <InputGroup idPrefix={prefix}
                            label={t('语言', 'Language')}
                            value={info.language}
                            onChange={v => updateField('language', v)}
                                     list={PROJECT_EP_LANGUAGE_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('剧本模式 (基础定位)', 'Script Mode (Base Positioning)')}
                            value={info.base_positioning}
                            onChange={v => updateField('base_positioning', v)}
                            list={PROJECT_EP_BASE_POSITIONING_OPTIONS}
                            placeholder={t('例如：武侠江湖 / 赛博朋克 / 古装战争', 'e.g. Wuxia Jianghu / Cyberpunk / Ancient War')}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('年代', 'Era')}
                            value={info.era}
                            onChange={v => updateField('era', v)}
                            list={PROJECT_SCENE_ANALYSIS_ERA_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('发生季节', 'Season Occurrence')}
                            value={info.season_occurrence}
                            onChange={v => updateField('season_occurrence', v)}
                            list={PROJECT_EP_SEASON_OCCURRENCE_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('镜头偏好', 'Lens Preference')}
                            value={PROJECT_EP_LENS_PREFERENCE_OPTIONS.includes(info.lens_preference) ? info.lens_preference : PROJECT_EP_LENS_PREFERENCE_OPTIONS[0]}
                            onChange={v => updateField('lens_preference', v)}
                            list={PROJECT_EP_LENS_PREFERENCE_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('画幅比例', 'Aspect Ratio')}
                            value={info.tech_params?.visual_standard?.aspect_ratio}
                            onChange={v => updateTech('aspect_ratio', v)}
                            list={PROJECT_ASPECT_RATIO_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('播出安全等级', 'Broadcast Safety Level')}
                            value={info.broadcast_safety_level}
                            onChange={v => updateField('broadcast_safety_level', v)}
                            list={PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS}
                        />

                        
                        <InputGroup idPrefix={prefix}
                            label={t('创作力', 'Creativity')}
                            value={info.creativity}
                            onChange={v => updateField('creativity', v)}
                            list={PROJECT_EP_CREATIVITY_OPTIONS}
                        />
                        <div className="flex items-center gap-2 mt-[28px] pl-1">
                            <input 
                                type="checkbox" 
                                id="hasExistingAssetsOverview" 
                                checked={info.has_existing_assets !== false} 
                                onChange={(e) => updateField('has_existing_assets', e.target.checked)} 
                                className="w-4 h-4 text-primary focus:ring-primary/30 rounded border-white/20 bg-background"
                            />
                            <label htmlFor="hasExistingAssetsOverview" className="text-sm font-semibold text-primary/95 cursor-pointer">
                                {t('有现有资产', 'Has Existing Assets')}
                            </label>
                        </div>
                        <div className="flex items-center gap-2 mt-[28px] pl-1 md:col-span-2">
                            <input
                                type="checkbox"
                                id="kbEnabledOverview"
                                checked={!!info.kb_enabled}
                                onChange={(e) => updateField('kb_enabled', e.target.checked)}
                                className="w-4 h-4 text-primary focus:ring-primary/30 rounded border-white/20 bg-background"
                            />
                            <label htmlFor="kbEnabledOverview" className="text-sm font-semibold text-primary/95 cursor-pointer">
                                {t('启用知识库参考（Stage1/资产设计 RAG）', 'Enable Knowledge Base refs (Stage1 / asset design RAG)')}
                            </label>
                        </div>
                        <div className="flex items-center gap-2 mt-[28px] pl-1 md:col-span-2">
                            <input
                                type="checkbox"
                                id="kbCollectionOnlyOverview"
                                checked={!!info.kb_collection_only}
                                onChange={(e) => updateField('kb_collection_only', e.target.checked)}
                                className="w-4 h-4 text-primary focus:ring-primary/30 rounded border-white/20 bg-background"
                                disabled={!info.kb_enabled}
                            />
                            <label htmlFor="kbCollectionOnlyOverview" className="text-sm font-semibold text-primary/95 cursor-pointer">
                                {t('仅使用项目收藏集（知识库）', 'KB collection-only mode')}
                                {Array.isArray(info.kb_collection_ids) && info.kb_collection_ids.length > 0
                                    ? ` · ${info.kb_collection_ids.length}`
                                    : ''}
                            </label>
                        </div>
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-muted-foreground uppercase font-bold">{t('视频声音', 'Video Sound')}</label>
                        <select
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                            value={resolveProjectVideoSoundEnabled(info) ? 'on' : 'off'}
                            onChange={(e) => updateField('video_sound', e.target.value !== 'off')}
                        >
                            <option value="on">{t('有', 'Enabled')}</option>
                            <option value="off">{t('无', 'Disabled')}</option>
                        </select>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('补充说明', 'Additional Notes')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={info.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder={t('其他需要补充的重要信息...', 'Any other important information...')}
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('分享人（可选，可多个）', 'Share Users (Optional, Multiple)')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                                value={formatUserListForTextarea(info.project_share_users)}
                                onChange={(e) => updateField('project_share_users', e.target.value)}
                                placeholder={t('输入用户名或邮箱，支持逗号、分号或换行分隔', 'Enter usernames or emails, separated by commas, semicolons, or new lines')}
                            />
                            <div className="mt-2 text-xs text-muted-foreground">
                                {formatManagedUserHint(info.project_share_users, t)}
                            </div>
                        </div>
                        <div>
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('审核人（可选，可多个）', 'Reviewer Users (Optional, Multiple)')}</label>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                                value={formatUserListForTextarea(info.project_reviewer_users)}
                                onChange={(e) => updateField('project_reviewer_users', e.target.value)}
                                placeholder={t('输入用户名或邮箱，保存时校验是否存在', 'Enter usernames or emails. Existence will be validated on save')}
                            />
                            <div className="mt-2 text-xs text-muted-foreground">
                                {formatManagedUserHint(info.project_reviewer_users, t)}
                            </div>
                        </div>
                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                )}

                {mode === 'overview' && (
                <div className="bg-card border border-white/10 rounded-xl overflow-hidden">
                    <button
                        onClick={() => toggleSection('cost')}
                        className="w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        <div className="flex items-center gap-3">
                            <h3 className="text-lg font-semibold text-primary">{t('成本评估与执行建议', 'Cost Estimation & Execution Advice')}</h3>
                            <span className="text-xs text-muted-foreground hidden sm:inline">{t('基于项目属性自动计算', 'Auto-calculated from project attributes')}</span>
                        </div>
                        <ChevronDown className={`w-5 h-5 transition-transform ${expandedSections.cost ? 'rotate-180' : ''}`} />
                    </button>
                    <AnimatePresence initial={false}>
                        {expandedSections.cost && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: 'easeInOut' }}
                                className="border-t border-white/10"
                            >
                                <div className="p-4 sm:p-6 space-y-6">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div className="text-sm text-muted-foreground">
                                            {costEstimation ? (
                                                <>
                                                    {t('当前阶段估算', 'Current Stage Estimate')}: <span className="text-white font-semibold">{Number(costEstimation?.summary?.current_estimate || 0).toLocaleString()}</span>
                                                    <span className="ml-3">{t('当前阶段', 'Current Stage')}: <span className="text-white font-semibold">{costStageLabel(costEstimation?.summary?.current_stage || 'overview')}</span></span>
                                                    <span className="ml-3">{t('总倍率', 'Total Multiplier')}: <span className="text-white font-semibold">{Number(costEstimation?.project_multiplier || 1).toFixed(3)}x</span></span>
                                                </>
                                            ) : (
                                                t('当前未缓存成本快照，可按需加载或重算。', 'No cached cost snapshot yet. Load or recompute on demand.')
                                            )}
                                        </div>
                                        <button
                                            onClick={() => loadProjectCost({ forceRecompute: !!costEstimation })}
                                            disabled={isCostRefreshing || isCostLoading}
                                            className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 ${(isCostRefreshing || isCostLoading) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                        >
                                            {(isCostRefreshing || isCostLoading) ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                                            {isCostRefreshing
                                                ? t('重算中...', 'Recomputing...')
                                                : isCostLoading
                                                    ? t('加载中...', 'Loading...')
                                                    : costEstimation
                                                        ? t('重算成本', 'Recompute Cost')
                                                        : t('加载成本', 'Load Cost')}
                                        </button>
                                    </div>

                                    {costError && (
                                        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                                            {costError}
                                        </div>
                                    )}

                                    {isCostLoading && !costEstimation && (
                                        <div className="text-sm text-muted-foreground flex items-center gap-2">
                                            <Loader2 className="w-4 h-4 animate-spin" /> {t('加载成本评估中...', 'Loading cost estimation...')}
                                        </div>
                                    )}

                                    {!isCostLoading && !costEstimation && !costError && (
                                        <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-3 text-sm text-muted-foreground">
                                            {t('当前展示优先使用项目已保存的成本快照；如需最新值，请点击“加载成本”或直接“重算成本”。', 'The panel prefers a saved project cost snapshot. Click "Load Cost" for the cached snapshot or recompute for the latest values.')}
                                        </div>
                                    )}

                                    {costEstimation && (
                                        <>
                                            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                                                <div className="flex items-center justify-between gap-3 mb-3">
                                                    <div className="text-sm font-semibold">{t('分集成本图', 'Per-Episode Cost Chart')}</div>
                                                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                                                        <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-sky-400" />{t('概要成本', 'Overview Cost')}</span>
                                                        <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-400" />{t('建议成本', 'Suggested Cost')}</span>
                                                        <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-400" />{t('预算成本', 'Budget Cost')}</span>
                                                    </div>
                                                </div>
                                                <div className="space-y-3">
                                                    {episodeCostChart.rows.length > 0 ? (
                                                        episodeCostChart.rows.map((row) => {
                                                            const ovPct = episodeCostChart.maxStage > 0 ? Math.max(4, (row.overview_cost / episodeCostChart.maxStage) * 100) : 4;
                                                            const sgPct = episodeCostChart.maxStage > 0 ? Math.max(4, (row.suggested_cost / episodeCostChart.maxStage) * 100) : 4;
                                                            const bgPct = episodeCostChart.maxStage > 0 ? Math.max(4, (row.budget_cost / episodeCostChart.maxStage) * 100) : 4;
                                                            return (
                                                                <div key={`episode-cost-${row.episode_number}`} className="space-y-1">
                                                                    <div className="flex items-center justify-between text-xs">
                                                                        <span className="text-muted-foreground">
                                                                            {t('第', 'Ep. ')}{row.episode_number}
                                                                            {row.episode_title ? ` · ${row.episode_title}` : ''}
                                                                        </span>
                                                                        <span className="text-white font-semibold">{row.current_estimated_cost.toLocaleString()} ({costStageLabel(row.current_stage || 'overview')})</span>
                                                                    </div>
                                                                    <div className="space-y-1">
                                                                        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                                                                            <div className="h-full rounded-full" style={{ width: `${ovPct}%`, backgroundColor: '#38bdf8' }} />
                                                                        </div>
                                                                        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                                                                            <div className="h-full rounded-full" style={{ width: `${sgPct}%`, backgroundColor: '#34d399' }} />
                                                                        </div>
                                                                        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                                                                            <div className="h-full rounded-full" style={{ width: `${bgPct}%`, backgroundColor: '#f59e0b' }} />
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })
                                                    ) : (
                                                        <div className="text-sm text-muted-foreground">{t('暂无分集成本数据，请先生成分集并重算成本。', 'No per-episode cost data yet. Generate episodes and recompute cost.')}</div>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                                                <div className="text-sm font-semibold mb-3">{t('执行建议', 'Execution Suggestions')}</div>
                                                <div className="space-y-2 text-sm text-primary/95">
                                                    {costExecutionSuggestions.length > 0 ? (
                                                        costExecutionSuggestions.map((item, idx) => (
                                                            <div key={`cost-suggestion-${idx}`} className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                                                                {idx + 1}. {item}
                                                            </div>
                                                        ))
                                                    ) : (
                                                        <div className="text-muted-foreground">{t('暂无建议。', 'No suggestions yet.')}</div>
                                                    )}
                                                </div>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                )}

                {/* Project Management */}
                {mode === 'overview' && (
                <div className="bg-card border border-white/10 rounded-xl overflow-hidden">
                    <button 
                        onClick={() => toggleSection('management')}
                        className="w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        <h3 className="text-lg font-semibold text-primary">{t('项目管理', 'Project Management')}</h3>
                        <ChevronDown className={`w-5 h-5 transition-transform ${expandedSections.management ? 'rotate-180' : ''}`} />
                    </button>
                    <AnimatePresence initial={false}>
                        {expandedSections.management && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: 'easeInOut' }}
                                className="border-t border-white/10"
                            >
                                <div className="p-4 sm:p-6 space-y-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix} 
                            label={t('计划完成时间', 'Planned Completion Time')} 
                            value={info.planned_completion_time} 
                            onChange={v => updateField('planned_completion_time', v)} 
                            placeholder={t('例如：2026-12-31', 'e.g., 2026-12-31')} 
                        />
                        <InputGroup idPrefix={prefix} 
                            label={t('项目预算', 'Budget')} 
                            value={info.budget} 
                            onChange={v => updateField('budget', v)} 
                            placeholder={t('例如：100万', 'e.g., 1M')} 
                        />
                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                )}

                {/* Technical & Visual Params */}
                {mode === 'overview' && (
                <div className="bg-card border border-white/10 rounded-xl overflow-hidden">
                    <button 
                        onClick={() => toggleSection('tech')}
                        className="w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        <div className="flex items-center justify-between gap-3 text-left">
                            <h3 className="text-lg font-semibold text-primary m-0">{t('技术与视觉参数', 'Technical & Visual Parameters')}</h3>
                            <span className="text-xs font-medium text-muted-foreground normal-case whitespace-nowrap hidden sm:block">{t('建议不改动，待大模型回填。', 'Recommended to keep unchanged, waiting for LLM backfill.')}</span>
                        </div>
                        <ChevronDown className={`w-5 h-5 shrink-0 transition-transform ${expandedSections.tech ? 'rotate-180' : ''}`} />
                    </button>
                    <AnimatePresence initial={false}>
                        {expandedSections.tech && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: 'easeInOut' }}
                                className="border-t border-white/10"
                            >
                                <div className="p-4 sm:p-6 space-y-6">
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('横向分辨率', 'H. Resolution')} 
                            value={info.tech_params?.visual_standard?.horizontal_resolution} 
                            onChange={v => updateTech('horizontal_resolution', v)} 
                            placeholder="1080"
                            list={["720", "1080", "1920", "3840"]}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('纵向分辨率', 'V. Resolution')} 
                            value={info.tech_params?.visual_standard?.vertical_resolution} 
                            onChange={v => updateTech('vertical_resolution', v)} 
                            placeholder="2160"
                            list={["2160", "1920", "1080", "720"]}
                        />
                    </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                        <InputGroup idPrefix={prefix}
                            label={t('图像尺寸', 'Image Size')}
                            value={info.tech_params?.visual_standard?.image_size}
                            onChange={v => updateTech('image_size', v)}
                            list={["0.5K", "1K", "2K", "4K"]}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('视频分辨率', 'Video Resolution')}
                            value={normalizeProjectVideoResolution(info.tech_params?.visual_standard?.video_resolution) || '720'}
                            onChange={v => updateTech('video_resolution', v)}
                            list={PROJECT_VIDEO_RESOLUTION_OPTIONS}
                        />
<InputGroup idPrefix={prefix}
                            label={t('视频生成偏好', 'Video Gen Preference')}
                            value={info.video_generation_preference}
                            onChange={v => updateField('video_generation_preference', v)}
                            list={PROJECT_EP_VIDEO_GEN_PREFERENCE_OPTIONS,
    PROJECT_EP_CREATIVITY_OPTIONS}
                        />
                    </div>
<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('帧率', 'Frame Rate')} 
                            value={info.tech_params?.visual_standard?.frame_rate} 
                            onChange={v => updateTech('frame_rate', v)} 
                            list={["24", "30", "60"]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label={t('质量等级', 'Quality')} 
                            value={info.tech_params?.visual_standard?.quality} 
                            onChange={v => updateTech('quality', v)} 
                                     list={PROJECT_EP_QUALITY_OPTIONS} 
                        />
                    </div>

                    <InputGroup idPrefix={prefix}
                        label={t('项目 Seed', 'Project Seed')}
                        value={info.generation_seed}
                        onChange={v => updateField('generation_seed', String(v || '').replace(/[^0-9]/g, ''))}
                        placeholder={t('例如：12345678', 'e.g. 12345678')}
                    />

                    <InputGroup idPrefix={prefix}
                        label={t('全局风格', 'Global Style')}
                        value={info.Global_Style}
                        onChange={v => updateField('Global_Style', v)}
                        multi={true}
                        list={PROJECT_EP_GLOBAL_STYLE_OPTIONS}
                    />
                    <p className="text-[11px] text-muted-foreground -mt-2">
                        {t('剧本模式即基础风格模式。全局统筹默认继承；单场可按场景改选并传下游。空的全局风格/光线/色调会按该模式补入。', 'Script mode is the base visual style. Global orchestration inherits it; each scene may pick a different mode and pass it downstream. Empty global style / lighting / tone are filled from the mode.')}
                    </p>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('借鉴影片（参考）', 'Borrowed Films (Ref)')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={info.borrowed_films.join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder={t('用逗号分隔，例如：银翼杀手, 黑客帝国', 'Use commas to separate, e.g. Blade Runner, Matrix')}
                        />
                    </div>

                    <InputGroup idPrefix={prefix}
                        label={t('色卡', 'Color Palette')}
                        value={info.color_palette || ''}
                        onChange={v => updateField('color_palette', v)}
                        multi={true}
                        placeholder={t('据借鉴影片选定：对标片=…｜主色=…｜辅色=…｜点缀=…｜过渡=…', 'From borrowed films: film=… | primary=… | secondary=… | accent=… | bridge=…')}
                    />

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('色调', 'Tone')} 
                            value={info.tone} 
                            onChange={v => updateField('tone', v)} 
                            multi={true}
                            list={PROJECT_EP_TONE_OPTIONS} 
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('光照', 'Lighting')} 
                            value={info.lighting} 
                            onChange={v => updateField('lighting', v)} 
                            multi={true}
                            list={PROJECT_EP_LIGHTING_OPTIONS} 
                        />
                    </div>

                    <InputGroup idPrefix={prefix}
                        label={t('百字剧情总结', 'Plot Summary (100 chars)')}
                        value={info.plot_summary}
                        onChange={v => updateField('plot_summary', v)}
                        multi={true}
                        placeholder={t('80-120字概括核心剧情、人物关系与情感走向', '80-120 chars summarizing plot, relationships, and emotional arc')}
                    />

                    <InputGroup idPrefix={prefix}
                        label={t('配乐推荐', 'Music Recommendation')}
                        value={info.music_recommendation}
                        onChange={v => updateField('music_recommendation', v)}
                        multi={true}
                        placeholder={t('最多5件乐器协作、风格、情绪、节奏、音量、质量、混响空间、参考及适用场景', 'Up to 5 cooperating instruments, style, mood, rhythm, volume, timbre, reverb space, references, and usage scenes')}
                    />
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                )}



                {mode === 'overview' && (
                <div className="bg-card border border-white/10 rounded-xl overflow-hidden xl:col-span-2">
                    <button 
                        onClick={() => toggleSection('review')}
                        className="w-full flex items-start sm:items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        <div className="flex flex-col sm:flex-row sm:items-center gap-3 text-left">
                            <h3 className="text-lg font-semibold text-primary m-0">{t('项目审核协作', 'Project Review Collaboration')}</h3>
                            <p className="m-0 text-sm text-muted-foreground hidden sm:block">
                                {t('可直接从项目总览发起资产/镜头审核，不必回到项目列表。', 'Create asset and shot review requests directly from project overview without returning to the project list.')}
                            </p>
                        </div>
                        <ChevronDown className={`w-5 h-5 shrink-0 mt-1 sm:mt-0 transition-transform ${expandedSections.review ? 'rotate-180' : ''}`} />
                    </button>
                    <AnimatePresence initial={false}>
                        {expandedSections.review && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: 'easeInOut' }}
                                className="border-t border-white/10"
                            >
                                <div className="p-4 sm:p-6 space-y-6">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between pb-3">
                        <div className="flex flex-wrap gap-2">
                            <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-muted-foreground">
                                {t(`线程 ${projectReviewThreads.length}`, `Threads ${projectReviewThreads.length}`)}
                            </span>
                            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${quickReviewUnreadCount > 0 ? 'bg-amber-500 text-black' : 'border border-white/10 text-muted-foreground'}`}>
                                {t(`未读 ${quickReviewUnreadCount}`, `Unread ${quickReviewUnreadCount}`)}
                            </span>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                        <div className="rounded-xl border border-white/10 bg-black/20 p-4 space-y-4">
                            <div className="text-sm font-semibold">{t('快速发起审核', 'Quick Review Request')}</div>
                            <>
                                <input
                                    value={quickReviewDraft.reviewer_user}
                                    onChange={(e) => setQuickReviewDraft((prev) => ({ ...prev, reviewer_user: e.target.value }))}
                                    placeholder={t('输入审核人用户名或邮箱', 'Enter reviewer username or email')}
                                    className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                                />
                            </>
                            <input
                                value={quickReviewDraft.title}
                                onChange={(e) => setQuickReviewDraft((prev) => ({ ...prev, title: e.target.value }))}
                                placeholder={t('审核标题，可选', 'Review title, optional')}
                                className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                            />
                            <textarea
                                value={quickReviewDraft.request_message}
                                onChange={(e) => setQuickReviewDraft((prev) => ({ ...prev, request_message: e.target.value }))}
                                placeholder={t('写明本次审核目标、注意点与截止要求', 'Describe goals, focus points, and deadline expectations for this review')}
                                className="w-full h-28 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                            />
                            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                                <label className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        checked={!!quickReviewDraft.entity_required}
                                        onChange={(e) => setQuickReviewDraft((prev) => ({ ...prev, entity_required: e.target.checked }))}
                                    />
                                    {t('资产审核', 'Asset Review')}
                                </label>
                                <label className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        checked={!!quickReviewDraft.shot_required}
                                        onChange={(e) => setQuickReviewDraft((prev) => ({ ...prev, shot_required: e.target.checked }))}
                                    />
                                    {t('镜头审核', 'Shot Review')}
                                </label>
                            </div>
                            <button
                                onClick={handleCreateQuickProjectReview}
                                disabled={isReviewPanelSubmitting || isReviewPanelLoading}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-2 ${(isReviewPanelSubmitting || isReviewPanelLoading) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                            >
                                {isReviewPanelSubmitting ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('发起中...', 'Creating...')}</> : <><Users className="w-4 h-4" /> {t('发起审核', 'Create Review')}</>}
                            </button>
                            <div className="text-xs text-muted-foreground">
                                {t('可直接输入任意已存在用户的用户名或邮箱；若项目作者指定了新审核人，系统会自动授予 reviewer 访问。', 'You can directly enter any existing username or email; when the project owner assigns a new reviewer, reviewer access will be granted automatically.')}
                            </div>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-black/20 p-4 space-y-4">
                            <div className="flex items-center justify-between gap-3">
                                <div className="text-sm font-semibold">{t('最近审核线程', 'Recent Review Threads')}</div>
                                <button
                                    onClick={loadProjectReviewPanel}
                                    disabled={isReviewPanelLoading}
                                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/10 text-white hover:bg-white/20 disabled:opacity-50"
                                >
                                    {isReviewPanelLoading ? t('刷新中...', 'Refreshing...') : t('刷新', 'Refresh')}
                                </button>
                            </div>
                            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[0.85fr_1.15fr]">
                                <div className="space-y-2 max-h-96 overflow-auto pr-1">
                                    {isReviewPanelLoading && projectReviewThreads.length === 0 ? (
                                        <div className="text-sm text-muted-foreground">{t('加载中...', 'Loading...')}</div>
                                    ) : projectReviewThreads.length === 0 ? (
                                        <div className="text-sm text-muted-foreground">{t('暂无审核线程', 'No review threads yet')}</div>
                                    ) : projectReviewThreads.slice(0, 8).map((thread) => (
                                        <button
                                            key={`editor-review-thread-${thread.id}`}
                                            onClick={() => loadQuickReviewThreadDetail(thread.id)}
                                            className={`w-full rounded-lg border p-3 text-left transition ${Number(selectedQuickReviewThreadId) === Number(thread.id) ? 'border-primary/40 bg-primary/10' : 'border-white/10 bg-black/30 hover:bg-white/5'}`}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="truncate text-sm font-medium text-white">{thread.title || `${t('审核线程', 'Review Thread')} #${thread.id}`}</div>
                                                    <div className="mt-1 text-xs text-muted-foreground">{thread.requester_username || '-'} → {thread.reviewer_username || '-'}</div>
                                                </div>
                                                <div className="flex flex-col items-end gap-1">
                                                    {thread.has_unread && <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-semibold text-black">{t('未读', 'Unread')}</span>}
                                                    <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-muted-foreground">{thread.status || 'open'}</span>
                                                </div>
                                            </div>
                                        </button>
                                    ))}
                                </div>

                                <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                                    {!selectedQuickReviewThreadId ? (
                                        <div className="flex min-h-56 items-center justify-center text-sm text-muted-foreground">
                                            {t('选择一个审核线程查看详情并直接回复。', 'Select a review thread to inspect details and reply directly.')}
                                        </div>
                                    ) : (
                                        (() => {
                                            const selectedThread = projectReviewThreads.find((item) => Number(item.id) === Number(selectedQuickReviewThreadId));
                                            const selectedRound = selectedQuickReviewRounds.find((item) => Number(item.id) === Number(selectedQuickReviewRoundId)) || selectedQuickReviewRounds[selectedQuickReviewRounds.length - 1] || null;
                                            const amReviewer = Number(currentUserId || 0) === Number(selectedThread?.reviewer_user_id || 0);
                                            return (
                                                <div className="space-y-4">
                                                    <div className="border-b border-white/10 pb-3">
                                                        <div className="flex items-center justify-between gap-3">
                                                            <div className="text-sm font-semibold text-white">{selectedThread?.title || `${t('审核线程', 'Review Thread')} #${selectedThread?.id || ''}`}</div>
                                                            {isQuickReviewDetailLoading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
                                                        </div>
                                                        <div className="mt-1 text-xs text-muted-foreground">{selectedThread?.requester_username || '-'} → {selectedThread?.reviewer_username || '-'}</div>
                                                    </div>

                                                    <div className="flex flex-wrap gap-2">
                                                        {selectedQuickReviewRounds.map((round) => (
                                                            <button
                                                                key={`editor-round-${round.id}`}
                                                                onClick={() => handleSelectQuickReviewRound(round.id)}
                                                                className={`rounded-full px-3 py-1 text-xs transition ${Number(selectedQuickReviewRoundId) === Number(round.id) ? 'bg-primary text-primary-foreground' : 'bg-white/10 text-muted-foreground hover:text-white'}`}
                                                            >
                                                                #{round.round_no}
                                                            </button>
                                                        ))}
                                                    </div>

                                                    {selectedRound && (
                                                        <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-muted-foreground space-y-2">
                                                            {selectedRound.request_message && <div>{selectedRound.request_message}</div>}
                                                            <div className="flex flex-wrap gap-4">
                                                                {selectedRound.entity_required && <span>{t('资产', 'Asset')}: {selectedRound.entity_decision || 'pending'}</span>}
                                                                {selectedRound.shot_required && <span>{t('镜头', 'Shot')}: {selectedRound.shot_decision || 'pending'}</span>}
                                                            </div>
                                                            {selectedRound.entity_feedback && <div>{t('资产意见', 'Asset feedback')}: {selectedRound.entity_feedback}</div>}
                                                            {selectedRound.shot_feedback && <div>{t('镜头意见', 'Shot feedback')}: {selectedRound.shot_feedback}</div>}
                                                        </div>
                                                    )}

                                                    <div className="max-h-48 space-y-2 overflow-auto pr-1">
                                                        {selectedQuickReviewMessages.length === 0 ? (
                                                            <div className="text-sm text-muted-foreground">{t('暂无消息', 'No messages')}</div>
                                                        ) : selectedQuickReviewMessages.map((message) => (
                                                            <div key={`editor-review-msg-${message.id}`} className="rounded-lg border border-white/10 bg-black/20 p-3">
                                                                <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                                                                    <span>{message.sender_username || '-'}</span>
                                                                    <span>{message.sender_role === 'reviewer' ? t('审核方', 'Reviewer') : t('发起方', 'Requester')}</span>
                                                                </div>
                                                                {message.message_text && <div className="mt-1 text-sm text-white">{message.message_text}</div>}
                                                                <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                                                                    {message.entity_decision && message.entity_decision !== 'pending' && <div>{t('资产结论', 'Asset decision')}: {message.entity_decision}</div>}
                                                                    {message.shot_decision && message.shot_decision !== 'pending' && <div>{t('镜头结论', 'Shot decision')}: {message.shot_decision}</div>}
                                                                    {message.entity_feedback && <div>{t('资产意见', 'Asset feedback')}: {message.entity_feedback}</div>}
                                                                    {message.shot_feedback && <div>{t('镜头意见', 'Shot feedback')}: {message.shot_feedback}</div>}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>

                                                    {selectedRound && (
                                                        <div className="space-y-3 border-t border-white/10 pt-3">
                                                            <textarea
                                                                value={quickReviewReplyDraft.message_text}
                                                                onChange={(e) => setQuickReviewReplyDraft((prev) => ({ ...prev, message_text: e.target.value }))}
                                                                placeholder={amReviewer ? t('填写审核回复与结论', 'Add review reply and decisions') : t('填写补充说明或回应', 'Add follow-up notes or response')}
                                                                className="w-full h-24 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                                                            />
                                                            {amReviewer && (
                                                                <>
                                                                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                                                        {selectedRound.entity_required && (
                                                                            <select
                                                                                value={quickReviewReplyDraft.entity_decision}
                                                                                onChange={(e) => setQuickReviewReplyDraft((prev) => ({ ...prev, entity_decision: e.target.value }))}
                                                                                className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                                                                            >
                                                                                <option value="pending">{t('资产待定', 'Asset pending')}</option>
                                                                                <option value="approved">{t('资产通过', 'Asset approved')}</option>
                                                                                <option value="conditional">{t('资产有条件通过', 'Asset conditional')}</option>
                                                                                <option value="rejected">{t('资产不通过', 'Asset rejected')}</option>
                                                                            </select>
                                                                        )}
                                                                        {selectedRound.shot_required && (
                                                                            <select
                                                                                value={quickReviewReplyDraft.shot_decision}
                                                                                onChange={(e) => setQuickReviewReplyDraft((prev) => ({ ...prev, shot_decision: e.target.value }))}
                                                                                className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                                                                            >
                                                                                <option value="pending">{t('镜头待定', 'Shot pending')}</option>
                                                                                <option value="approved">{t('镜头通过', 'Shot approved')}</option>
                                                                                <option value="conditional">{t('镜头有条件通过', 'Shot conditional')}</option>
                                                                                <option value="rejected">{t('镜头不通过', 'Shot rejected')}</option>
                                                                            </select>
                                                                        )}
                                                                    </div>
                                                                    {selectedRound.entity_required && (
                                                                        <textarea
                                                                            value={quickReviewReplyDraft.entity_feedback}
                                                                            onChange={(e) => setQuickReviewReplyDraft((prev) => ({ ...prev, entity_feedback: e.target.value }))}
                                                                            placeholder={t('资产审核意见', 'Asset review feedback')}
                                                                            className="w-full h-20 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                                                                        />
                                                                    )}
                                                                    {selectedRound.shot_required && (
                                                                        <textarea
                                                                            value={quickReviewReplyDraft.shot_feedback}
                                                                            onChange={(e) => setQuickReviewReplyDraft((prev) => ({ ...prev, shot_feedback: e.target.value }))}
                                                                            placeholder={t('镜头审核意见', 'Shot review feedback')}
                                                                            className="w-full h-20 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                                                                        />
                                                                    )}
                                                                </>
                                                            )}
                                                            <button
                                                                onClick={handleCreateQuickReviewReply}
                                                                disabled={isReviewPanelSubmitting}
                                                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-2 ${isReviewPanelSubmitting ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                                            >
                                                                {isReviewPanelSubmitting ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('发送中...', 'Sending...')}</> : <>{t('发送回复', 'Send Reply')}</>}
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })()
                                    )}
                                </div>
                            </div>
                            <div className="text-xs text-muted-foreground">
                                {t('更完整的轮次管理、状态变更和归档仍在项目列表的“项目协作”工作台中。', 'Full round management, status changes, and archiving remain in the project collaboration workspace on the project list page.')}
                            </div>
                        </div>
                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                )}

                {/* Story Generator (Global) — 4-step flow */}
                {mode === 'generator' && projectTab === 'story_generator' && (
                <div className="bg-card border border-white/10 p-4 sm:p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('故事生成器（全局 / 项目）', 'Story Generator (Global / Project)')}</h3>
                    </div>

                    {/* Workflow Diagnostics stepper (mirrors ScriptEditor progress panel) */}
                    <div className="rounded-2xl border border-white/10 bg-black/25 p-4 backdrop-blur-sm">
                        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                            <div className="flex items-center gap-2 font-bold text-sm shrink-0">
                                <div className="w-1 h-5 bg-purple-500 rounded-full"></div>
                                {t('剧本生成流程', 'Story Generation Flow')}
                            </div>
                            {(() => {
                                const stepBtnClass = 'text-[10px] px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 disabled:opacity-40 disabled:cursor-not-allowed hover:text-white transition-colors';
                                const primaryChipClass = 'text-[10px] px-2 py-0.5 rounded border border-purple-500/50 text-purple-200 bg-purple-500/20 hover:bg-purple-500/30 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1';
                                const renderProcessingLabel = () => (
                                    <span className="text-[10px] text-purple-300 flex items-center gap-1">
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                        {t('处理中', 'Processing')}
                                    </span>
                                );
                                const circleClass = (ready, active) => (
                                    ready
                                        ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]'
                                        : (active
                                            ? 'bg-purple-500/50 border-purple-400 text-white backdrop-blur-sm shadow-[0_0_10px_rgba(168,85,247,0.3)]'
                                            : 'bg-white/5 border-white/20 text-white/50 backdrop-blur-sm')
                                );
                                const steps = [
                                    {
                                        key: 'wild_ideas',
                                        n: 1,
                                        ready: wildIdeasReady,
                                        active: storyGenFocusStep === 'wild_ideas' && !wildIdeasReady,
                                    },
                                    {
                                        key: 'structure_prefill',
                                        n: 2,
                                        ready: structurePrefillReady,
                                        active: structurePrefillActive,
                                    },
                                    {
                                        key: 'global_framework',
                                        n: 3,
                                        ready: globalFrameworkReady,
                                        active: globalFrameworkActive,
                                    },
                                    {
                                        key: 'episode_scripts',
                                        n: 4,
                                        ready: episodeScriptsReady && episodeScriptsGeneratedCount > 0 && !episodeScriptsActive,
                                        active: episodeScriptsActive,
                                    },
                                ];
                                return (
                                    <div className="flex-1 w-full flex items-start justify-between relative max-w-4xl px-2 mt-2 md:mt-0 gap-1">
                                        <div className="absolute top-4 left-8 right-8 h-0.5 bg-white/10 -z-10"></div>
                                        {steps.map((step) => (
                                            <div key={step.key} className="flex flex-col items-center gap-2 relative flex-1 min-w-0">
                                                <button
                                                    type="button"
                                                    onClick={() => scrollToStoryGenStep(step.key)}
                                                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold z-10 border ${circleClass(step.ready, step.active || (storyGenFocusStep === step.key && !step.ready))}`}
                                                    title={getStoryGenStepLabel(step.key)}
                                                >
                                                    {step.ready
                                                        ? <Check className="w-4 h-4" />
                                                        : (step.active ? <Loader2 className="w-4 h-4 animate-spin" /> : step.n)}
                                                </button>
                                                <div className="flex flex-col items-center gap-1 text-center px-0.5">
                                                    <button
                                                        type="button"
                                                        onClick={() => scrollToStoryGenStep(step.key)}
                                                        className={`text-xs font-semibold leading-tight ${storyGenFocusStep === step.key ? 'text-white' : 'text-white/80 hover:text-white'}`}
                                                    >
                                                        {getStoryGenStepLabel(step.key)}
                                                    </button>
                                                    {step.key === 'wild_ideas' && (
                                                        wildIdeasReady ? (
                                                            <div className="flex items-center gap-1 flex-wrap justify-center">
                                                                <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                                                <button type="button" onClick={() => scrollToStoryGenStep('wild_ideas')} className={stepBtnClass}>
                                                                    {t('编辑', 'Edit')}
                                                                </button>
                                                            </div>
                                                        ) : (
                                                            <button type="button" onClick={() => scrollToStoryGenStep('wild_ideas')} className={primaryChipClass}>
                                                                {t('去输入', 'Go Input')}
                                                            </button>
                                                        )
                                                    )}
                                                    {step.key === 'structure_prefill' && (
                                                        structurePrefillActive ? renderProcessingLabel() : (
                                                            structurePrefillReady ? (
                                                                <div className="flex items-center gap-1 flex-wrap justify-center">
                                                                    <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                                                    <button type="button" onClick={() => scrollToStoryGenStep('structure_prefill')} className={stepBtnClass}>
                                                                        {t('编辑', 'Edit')}
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        onClick={handleStructureCreativeInput}
                                                                        disabled={isStructuringCreativeInput || isGeneratingGlobalStory || !wildIdeasReady}
                                                                        className={stepBtnClass}
                                                                    >
                                                                        {t('重跑', 'Rerun')}
                                                                    </button>
                                                                </div>
                                                            ) : wildIdeasReady ? (
                                                                <button
                                                                    type="button"
                                                                    onClick={handleStructureCreativeInput}
                                                                    disabled={isStructuringCreativeInput || isGeneratingGlobalStory}
                                                                    className={primaryChipClass}
                                                                >
                                                                    <Wand2 className="w-3 h-3" />
                                                                    {t('结构化预填', 'Structure')}
                                                                </button>
                                                            ) : (
                                                                <span className="text-[10px] text-white/30">{t('待上一步完成', 'Wait previous step')}</span>
                                                            )
                                                        )
                                                    )}
                                                    {step.key === 'global_framework' && (
                                                        globalFrameworkActive ? renderProcessingLabel() : (
                                                            globalFrameworkReady ? (
                                                                <div className="flex items-center gap-1 flex-wrap justify-center">
                                                                    <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                                                    <button type="button" onClick={() => scrollToStoryGenStep('global_framework')} className={stepBtnClass}>
                                                                        {t('编辑', 'Edit')}
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        onClick={handleGenerateGlobalStory}
                                                                        disabled={isGeneratingGlobalStory}
                                                                        className={stepBtnClass}
                                                                    >
                                                                        {t('重跑', 'Rerun')}
                                                                    </button>
                                                                </div>
                                                            ) : structurePrefillReady ? (
                                                                <button
                                                                    type="button"
                                                                    onClick={handleGenerateGlobalStory}
                                                                    disabled={isGeneratingGlobalStory}
                                                                    className={primaryChipClass}
                                                                >
                                                                    <Sparkles className="w-3 h-3" />
                                                                    {t('生成框架', 'Generate')}
                                                                </button>
                                                            ) : (
                                                                <span className="text-[10px] text-white/30">{t('待上一步完成', 'Wait previous step')}</span>
                                                            )
                                                        )
                                                    )}
                                                    {step.key === 'episode_scripts' && (
                                                        episodeScriptsActive ? (
                                                            <div className="flex flex-col items-center gap-1">
                                                                {renderProcessingLabel()}
                                                                <button
                                                                    type="button"
                                                                    onClick={handleStopEpisodeScripts}
                                                                    disabled={isStoppingEpisodeScripts}
                                                                    className="text-[10px] px-2 py-0.5 rounded border border-red-400/50 text-red-100 bg-red-500/20 hover:bg-red-500/30 disabled:opacity-50"
                                                                >
                                                                    {isStoppingEpisodeScripts ? t('停止中...', 'Stopping...') : t('强制停止', 'Force Stop')}
                                                                </button>
                                                            </div>
                                                        ) : (
                                                            globalFrameworkReady ? (
                                                                <div className="flex flex-col items-center gap-1">
                                                                    {episodeScriptsGeneratedCount > 0 ? (
                                                                        <span className="text-[10px] text-emerald-400/80">
                                                                            {t(`已生成 ${episodeScriptsGeneratedCount}`, `Generated ${episodeScriptsGeneratedCount}`)}
                                                                        </span>
                                                                    ) : null}
                                                                    <div className="flex items-center gap-1 flex-wrap justify-center">
                                                                        <button
                                                                            type="button"
                                                                            onClick={handleGenerateEpisodeScripts}
                                                                            disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                                                            className={primaryChipClass}
                                                                            title={t('从全局框架 + 项目角色设定生成分集剧本', 'Generate episode scripts from Global Framework + Character Canon')}
                                                                        >
                                                                            <Wand2 className="w-3 h-3" />
                                                                            {t('全量生成', 'Gen All')}
                                                                        </button>
                                                                        <button type="button" onClick={() => scrollToStoryGenStep('episode_scripts')} className={stepBtnClass}>
                                                                            {t('单集/详情', 'Single / Details')}
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            ) : (
                                                                <span className="text-[10px] text-white/30">{t('待上一步完成', 'Wait previous step')}</span>
                                                            )
                                                        )
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                );
                            })()}
                        </div>
                    </div>

                        <div className="sm:col-span-2 rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <div className="text-sm font-semibold text-white">{t('自动继承的项目信息', 'Inherited Project Info')}</div>
                                    <div className="text-xs text-muted-foreground mt-1">
                                        {t('故事生成器会自动读取项目概览里的基础信息，这里只需要补故事骨架，不需要重复输入已有项目字段。', 'The Story Generator automatically reuses Project Overview info. Only fill the story skeleton here; no need to repeat existing project fields.')}
                                    </div>
                                </div>
                                {storyGeneratorMissingInfo.length > 0 ? (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setProjectTab('overview');
                                            if (onTabChange) onTabChange('overview');
                                        }}
                                        className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20"
                                    >
                                        {t('去项目概览补齐', 'Complete in Overview')}
                                    </button>
                                ) : null}
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                                {storyGeneratorInheritedInfo.map(item => (
                                    <div key={item.label} className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                                        <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{item.label}</div>
                                        <div className={item.value ? 'text-white mt-1' : 'text-muted-foreground mt-1'}>
                                            {item.value || t('未设置，将只在缺失时自动推断', 'Not set. It will only be inferred when still missing.')}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('载体规格 / 集数', 'Format / Episodes')}</label>
                                <input
                                    type="number"
                                    min="1"
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                    value={globalStoryInput.episodes_count}
                                    onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, episodes_count: e.target.value }))}
                                    placeholder={t('例如：20', 'e.g. 20')}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('每集时长（分钟）', 'Episode Duration (min)')}</label>
                                <input
                                    type="number"
                                    min="1"
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                    value={globalStoryInput.episode_duration_minutes}
                                    onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, episode_duration_minutes: e.target.value }))}
                                    placeholder={t('例如：1', 'e.g. 1')}
                                />
                            </div>
                            <InputGroup
                                idPrefix={prefix}
                                label={t('产品规格与节奏', 'Product Format')}
                                value={globalStoryInput.script_mode}
                                onChange={v => setGlobalStoryInput(prev => ({ ...prev, script_mode: v }))}
                                list={[
                                    '短剧快节奏 / Short Drama',
                                    '电影 / Feature Film',
                                    '通用连续剧 / General Series',
                                    SERIES_IP_SCRIPT_MODE,
                                ]}
                            />
                            <InputGroup
                                idPrefix={prefix}
                                label={t('受众定位', 'Target Audience')}
                                value={globalStoryInput.target_audience}
                                onChange={v => setGlobalStoryInput(prev => ({ ...prev, target_audience: v }))}
                                list={[
                                    '男频路线 / Male-Oriented',
                                    '女频路线 / Female-Oriented',
                                    '全受众 / General Audience'
                                ]}
                            />
                            <div className="sm:col-span-2 text-xs text-muted-foreground mb-1">
                                {seriesIpMode
                                    ? t('系列剧（IP模式）只生成全剧信息：世界观、主要角色 IP、基本故事线索。不预写各集剧情。每一集另填基本剧情、冲突和亮点，并自动带上此前各集摘要。', 'Series IP keeps a series bible only: world, lead character IP, and story threads. Episode plots are not prewritten. Each episode adds its plot, conflict, and highlights, plus summaries of earlier episodes.')
                                    : t('大模型将根据【产品规格】严格套用不同的工业化叙事节奏与起承转合结构，并针对【受众定位】极化核心看点与张力。', 'The AI will apply distinct rhythmic and structural pacing based on the chosen Product Format and polarize constraints based on target audience.')}
                            </div>
                        </div>

                        {/* Step 1: Wild Ideas */}
                        <div
                            ref={(el) => { storyGenStepRefs.current.wild_ideas = el; }}
                            className={`sm:col-span-2 rounded-xl border p-4 space-y-3 transition-colors ${storyGenFocusStep === 'wild_ideas' ? 'border-purple-500/40 bg-purple-500/5' : 'border-white/10 bg-white/[0.02]'}`}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center border ${wildIdeasReady ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-white/5 border-white/20 text-white/60'}`}>1</span>
                                        <label className="text-xs text-muted-foreground uppercase font-bold block">
                                            {t('天马行空的想法', 'Wild Ideas & Creative Prompt')}
                                        </label>
                                    </div>
                                    <div className="text-[11px] text-muted-foreground/80 mt-1">
                                        {t('先把脑海中的画面、台词、怪念头倒在这里；完成后进入步骤 2 结构化预填。', 'Pour raw scenes, lines, and quirky ideas here; then go to Step 2 Structure & Prefill.')}
                                    </div>
                                </div>
                            </div>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-32 resize-none placeholder:text-white/25"
                                value={globalStoryInput.wild_creative_notes}
                                onChange={(e) => {
                                    setStoryGenFocusStep('wild_ideas');
                                    setGlobalStoryInput(prev => ({ ...prev, wild_creative_notes: e.target.value }));
                                }}
                                onFocus={() => setStoryGenFocusStep('wild_ideas')}
                                placeholder={t(
                                    '尽情输入脑洞与名场面设想，例如：绝症杀手替女儿复仇；双重人格杀人前必听贝多芬；开头直升机反杀；高潮雨中工厂兄弟反目、经典台词「我们都回不去了」…',
                                    'Wild ideas + iconic scenes: dying assassin avenges daughter; dual-personality killer listens to Beethoven; helicopter opening; rainy factory climax with line "We can never go back"…'
                                )}
                            />
                        </div>

                        {/* Step 2: Structure & Prefill (McKee + Egri + Save the Cat) */}
                        <div
                            ref={(el) => { storyGenStepRefs.current.structure_prefill = el; }}
                            className={`sm:col-span-2 rounded-xl border p-4 space-y-4 transition-colors ${storyGenFocusStep === 'structure_prefill' ? 'border-purple-500/40 bg-purple-500/5' : 'border-white/10 bg-white/[0.02]'}`}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center border ${structurePrefillReady ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-white/5 border-white/20 text-white/60'}`}>2</span>
                                        <div className="text-sm font-semibold text-white">{t('结构化预填（核心建置 · 人物弧光 · 救猫咪15拍）', 'Structure & Prefill (Concept · Character · 15 Beats)')}</div>
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-1">
                                        {seriesIpMode
                                            ? t('IP 模式的预填只锁全剧：世界观、角色 IP、故事线索，以及经典作品对整体剧本的机制参考。15 拍可以只写全剧走向，不要写成各集场表。', 'IP prefill locks the series only: world, character IP, story threads, and classic works as a mechanism reference for the whole script. The 15 beats, if used, stay series direction and are not episode scenes.')
                                            : t('点「结构化预填」生成三层：三幕与麦基做核心建置，编剧的艺术做人设和弧光，情节按救猫咪 15 节拍往下接。主骨架仍优先现代/当代，并至少配 5 部辅助。地点拿不准可以不写。', 'Structure & Prefill builds three layers: three-act and McKee for the concept, Egri for character and arc, and the Save the Cat 15 beats for the plot. The primary spine stays modern/contemporary, with at least 5 auxiliaries. Omit a location if you are unsure.')}
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={handleStructureCreativeInput}
                                    disabled={isStructuringCreativeInput || isGeneratingGlobalStory || !wildIdeasReady}
                                    className={`shrink-0 px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 ${(isStructuringCreativeInput || isGeneratingGlobalStory || !wildIdeasReady) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary/20 text-primary hover:bg-primary/30'}`}
                                    title={t('按三幕与麦基、编剧的艺术、救猫咪 15 拍，从天马行空直接预填', 'Prefill from wild ideas using three-act and McKee, Egri, and the Save the Cat 15 beats')}
                                >
                                    {isStructuringCreativeInput
                                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('结构化中...', 'Structuring...')}</>
                                        : <><Wand2 className="w-3.5 h-3.5" /> {t('结构化预填', 'Structure & Prefill')}</>}
                                </button>
                            </div>
                            {[
                                {
                                    id: 'logline',
                                    label: t('高概念 · 欲望脊柱', 'High Concept · Desire Spine'),
                                    hint: t(
                                        '麦基的脊柱：谁想要什么、谁在挡、失败会失去什么。三秒能懂。不写主题，不写十五拍。',
                                        'McKee\'s spine: who wants what, who blocks them, what is lost on failure. Understandable in three seconds. Not the theme, and not the 15 beats.'
                                    ),
                                    example: t(
                                        '例：能看见死亡倒计时的实习律师，要在被当成疯子之前救下将被谋杀的上司；挡住她的是封口体系。',
                                        'e.g. An intern who sees death countdowns must save her boss before she is called insane; a cover-up system stands in the way.'
                                    ),
                                    rows: 2,
                                },
                                {
                                    id: 'theme',
                                    label: t('主控思想', 'Controlling Idea'),
                                    hint: t('麦基：价值电荷 + 原因。写成「……战胜/输掉……，因为……」。三幕结局要能证明这句。', 'McKee: value charge plus cause. Write "X beats/loses to Y, because …". The ending must be able to prove it.'),
                                    example: t(
                                        '例：真相战胜封口，因为有人愿意用职业生涯把证据公开。',
                                        'e.g. Truth beats the cover-up, because someone will spend their career to make the evidence public.'
                                    ),
                                    rows: 2,
                                },
                                {
                                    id: 'core_conflict',
                                    label: t('对抗 · 鸿沟 · 危机', 'Antagonism · Gap · Crisis'),
                                    hint: t('对抗原则（对手更强）、否定之否定、期望和实际结果的鸿沟、赌注，以及危机时必须做的两难。', 'Principle of antagonism, negation of the negation, the gap between expected and actual results, the stakes, and the crisis dilemma.'),
                                    example: t(
                                        '例：封口体系比林一更有权；最坏不是查无结果，而是真相被当成诬告。两难：交牌自保，或留证担责。',
                                        'e.g. The cover-up outranks Lin. The worst charge is not "no proof" but truth branded as slander. Dilemma: hand over the badge, or keep the evidence and take the blame.'
                                    ),
                                    rows: 3,
                                },
                                {
                                    id: 'three_act',
                                    label: t('三幕价值弧', 'Three-Act Value Arc'),
                                    hint: t('只写三幕各自往哪边翻价值，不写十五拍的场面。建置如何被打破，对抗如何逐级翻转，结局用哪一次危机选择证明主控思想。', 'The value turn of each act, not the 15 scenes. How the balance breaks, how confrontation turns the value, and which crisis choice proves the controlling idea.'),
                                    example: t(
                                        '例：第一幕，审计日常被一封无署名解雇信打破。第二幕，每查一步权限就收紧，中点是假胜利。第三幕，交牌或留证；公开证据证明真相能救人，人也被行业放下。',
                                        'e.g. Act I: an unsigned termination letter breaks the audit routine. Act II: each probe tightens access; the midpoint is a false win. Act III: surrender the badge or keep the proof; going public proves truth can save a life, at the cost of the career.'
                                    ),
                                    rows: 3,
                                },
                                {
                                    id: 'background',
                                    label: t('故事世界 · 压力场', 'Story World · Pressure'),
                                    hint: t('迫使人物做选择的时代、制度、礼法和能力边界。不是地点清单。', 'The era, institution, custom, and limits of ability that force the choice. Not a list of locations.'),
                                    example: t(
                                        '例：2026 跨国律所。职级决定能进哪扇门。审计 24 小时留痕。越权本身就会触发约谈。',
                                        'e.g. A 2026 megafirm. Rank decides which door opens. Audit logs last 24 hours. Overreach itself triggers a hearing.'
                                    ),
                                    rows: 3,
                                },
                                {
                                    id: 'characters',
                                    label: t('人物 · 前提与弧光', 'Characters · Premise & Arc'),
                                    hint: t('编剧的艺术：前提、生理/社会/心理、谁逼谁变、统一的对立面、编排对照、弧光从哪一极走到哪一极。姓名用日常人名。', 'Egri: premise, physiology/sociology/psychology, who forces the change, unity of opposites, orchestration, and the arc from one pole to the other. Ordinary names.'),
                                    example: t(
                                        '例：前提：怕失去位置的人，经过封口冲突，会学会用位置去公开真相。林一：社会=实习法务｜心理=先自保｜弧光：交牌→留证。周薇：信念相反，两人互相锁死。',
                                        'e.g. Premise: fear of losing one\'s place, through a cover-up, learns to spend that place on the truth. Lin: sociology=intern, psychology=self-protection, arc=hand over the badge → keep the proof. Zhou holds the opposite belief; the two lock each other.'
                                    ),
                                    rows: 5,
                                },
                            ].map((field) => (
                                <div key={field.id}>
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{field.label}</label>
                                    <div className="text-[11px] text-muted-foreground/80 mb-0.5">{field.hint}</div>
                                    <div className="text-[11px] text-primary/70 mb-1.5 italic">{field.example}</div>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25"
                                        rows={field.rows}
                                        placeholder={field.example}
                                        value={globalStoryInput[field.id] || ''}
                                        onFocus={() => setStoryGenFocusStep('structure_prefill')}
                                        onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, [field.id]: e.target.value }))}
                                    />
                                </div>
                            ))}
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('I10 经典作品框架', 'I10 Classic Works Framework')}</label>
                                <div className="text-[11px] text-muted-foreground/80 mb-0.5">
                                    {t('主框架优先选现代、当代作品的剧情逻辑，并写明落在哪几拍。除主框架外至少再列 5 部辅助，各贡献不同维度，用来拆开主框架。古典原典只可作辅助。写作品名、机制与转译。', 'Primary spine: prefer modern/contemporary plot logic, and name which beats it lands on. Besides the primary, list at least 5 auxiliaries, each a different dimension, so the 15 beats are not a remake. Pre-modern classics are auxiliaries only. Name works, mechanisms, and the transfer.')}
                                </div>
                                <div className="text-[11px] text-primary/70 mb-1.5 italic">
                                    {t('例：主框架：《消失的爱人》— 证据战与身份反转；转译→宫斗密折/朝堂对质。辅助≥5：《肖申克的救赎》取证；《喜剧之王》身份反差；《无间道》双面身份；《寄生虫》阶层空间；《致命ID》封闭空间置换。各写机制+转译，禁五部复述主框架。', 'e.g. Spine: Gone Girl — evidence war + identity reversal; transfer → palace memorial / court confrontation. Aux≥5: Shawshank (covert proof); King of Comedy (status reversal); Infernal Affairs (double identity); Parasite (class space); Identity (closed-room swap). Each a different mechanism + transfer; do not retell the primary five times.')}
                                </div>
                                <textarea
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25"
                                    rows={5}
                                    value={globalStoryInput.classic_framework || ''}
                                    onFocus={() => setStoryGenFocusStep('structure_prefill')}
                                    onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, classic_framework: e.target.value }))}
                                    placeholder={t('例：主框架：《消失的爱人》— 剧情逻辑：…；转译→…。辅助≥5：《肖申克的救赎》…；《无间道》…；《寄生虫》…；…', 'e.g. Spine: Gone Girl — plot logic: …; transfer → …. Aux≥5: Shawshank …; Infernal Affairs …; Parasite …; …')}
                                />
                            </div>
                            <div className="space-y-3">
                                <div>
                                    <div className="text-xs font-bold text-white">{t('救猫咪 15 节拍', 'Save the Cat · 15 Beats')}</div>
                                    <div className="text-[11px] text-muted-foreground/80 mt-0.5">
                                        {seriesIpMode
                                            ? t('可留空。若填写，只作为全剧走向，不会被拆成各集剧情框架。', 'Optional. If filled, this is series direction only and will not be split into episode frameworks.')
                                            : t('情节按这 15 拍往下接。每一拍写谁对谁做了什么、期望和实际差在哪、价值往哪边翻。上一拍的结果是下一拍的压力。地点拿不准就不写。', 'The plot runs down these 15 beats. Each beat: who does what to whom, the gap between expected and actual, and which way the value turns. One beat\'s result is the next beat\'s pressure. Omit a location if you are unsure.')}
                                    </div>
                                </div>
                                {SAVE_THE_CAT_ACTS.map((act) => (
                                    <div key={act.id} className="space-y-2">
                                        <div className="text-[11px] font-bold uppercase tracking-wide text-primary/80">{t(act.zh, act.en)}</div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            {act.beats.map((beat) => (
                                                <div key={beat.id}>
                                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">
                                                        {beat.no} {t(beat.zh, beat.en)}
                                                    </label>
                                                    <div className="text-[11px] text-muted-foreground/80 mb-1">{t(beat.hintZh, beat.hintEn)}</div>
                                                    <textarea
                                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25"
                                                        rows={3}
                                                        placeholder={t(beat.hintZh, beat.hintEn)}
                                                        value={globalStoryInput[beat.id] || ''}
                                                        onFocus={() => setStoryGenFocusStep('structure_prefill')}
                                                        onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, [beat.id]: e.target.value }))}
                                                    />
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {[
                                    {
                                        id: 'suspense',
                                        label: t('I8a 核心悬念', 'I8a Core Suspense'),
                                        hint: t('观众贯穿全剧想追问的问题。和危机两难互补，不代替它。', 'Questions the audience keeps asking. They complement the crisis dilemma; they do not replace it.'),
                                        example: t(
                                            '例：谁写了解雇信？谁给了林一总裁权限？',
                                            'e.g. Who wrote the letter? Who gave Lin CEO-level access?'
                                        ),
                                        rows: 2,
                                    },
                                    {
                                        id: 'foreshadowing',
                                        label: t('I8b 伏笔与必留元素', 'I8b Foreshadowing & Must-Keep'),
                                        hint: t('必保留台词/道具/反转/回收约束', 'Must-keep lines, props, payoffs'),
                                        example: t(
                                            '例：镜前工牌特写；台词「这扇门认的不是我」；工牌终集再触发门禁。',
                                            'e.g. Mirror badge shot; line "This door knows a name I haven\'t met"; badge triggers access in finale.'
                                        ),
                                        rows: 2,
                                    },
                                ].map((field) => (
                                    <div key={field.id}>
                                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{field.label}</label>
                                        <div className="text-[11px] text-muted-foreground/80 mb-0.5">{field.hint}</div>
                                        <div className="text-[11px] text-primary/70 mb-1.5 italic">{field.example}</div>
                                        <textarea
                                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25"
                                            rows={field.rows}
                                            placeholder={field.example}
                                            value={globalStoryInput[field.id] || ''}
                                            onFocus={() => setStoryGenFocusStep('structure_prefill')}
                                            onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, [field.id]: e.target.value }))}
                                        />
                                    </div>
                                ))}
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('I9 自由脑洞补充', 'I9 Raw Creative Fragments')}</label>
                                <div className="text-[11px] text-muted-foreground/80 mb-0.5">
                                    {t('画面/台词/怪念头等未归类碎片；可留空', 'Unsorted scenes, lines, ideas; optional')}
                                </div>
                                <div className="text-[11px] text-primary/70 mb-1.5 italic">
                                    {t('例：开头倒叙工牌特写；集末保安上门断点；兄弟反目台词「我们都回不去了」。', 'e.g. Cold-open badge close-up; cliffhanger security at door; line "We can never go back".')}
                                </div>
                                <textarea
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none placeholder:text-white/25"
                                    value={globalStoryInput.extra_notes}
                                    onFocus={() => setStoryGenFocusStep('structure_prefill')}
                                    onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, extra_notes: e.target.value }))}
                                    placeholder={t('例：开头倒叙工牌特写；集末保安上门断点…', 'e.g. Cold-open badge close-up; cliffhanger security at door…')}
                                />
                            </div>
                        </div>

                        {/* Step 3: Global Framework */}
                        <div
                            ref={(el) => { storyGenStepRefs.current.global_framework = el; }}
                            className={`rounded-xl border p-4 space-y-3 transition-colors ${storyGenFocusStep === 'global_framework' ? 'border-purple-500/40 bg-purple-500/5' : 'border-white/10 bg-white/[0.02]'}`}
                        >
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2">
                                    <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center border ${globalFrameworkReady ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-white/5 border-white/20 text-white/60'}`}>3</span>
                                    <label className="text-xs text-muted-foreground uppercase font-bold block">{seriesIpMode ? t('已生成全剧信息（Markdown）', 'Generated Series Bible (Markdown)') : t('已生成全局框架（Markdown）', 'Generated Global Framework (Markdown)')}</label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        type="button"
                                        onClick={handleGenerateGlobalStory}
                                        disabled={isGeneratingGlobalStory || !structurePrefillReady}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 ${(isGeneratingGlobalStory || !structurePrefillReady) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary/20 text-primary hover:bg-primary/30'}`}
                                        title={t('生成国际化爆款故事框架并保存到项目总览', 'Generate an international-blockbuster story framework and store it in project Overview')}
                                    >
                                        {isGeneratingGlobalStory
                                            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('生成中...', 'Generating...')}</>
                                            : <><Sparkles className="w-3.5 h-3.5" /> {globalFrameworkReady ? t('重新生成', 'Regenerate') : (seriesIpMode ? t('生成全剧信息', 'Generate Series Bible') : t('生成全局框架', 'Generate Framework'))}</>}
                                    </button>
                                    <div className="flex items-center gap-1 bg-black/20 border border-white/10 rounded-md p-1">
                                        <button
                                            type="button"
                                            onClick={() => setStoryFrameworkViewMode('preview')}
                                            className={`px-2 py-1 rounded text-xs font-bold ${storyFrameworkViewMode === 'preview' ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'}`}
                                        >
                                            {t('预览', 'Preview')}
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setStoryFrameworkViewMode('edit')}
                                            className={`px-2 py-1 rounded text-xs font-bold ${storyFrameworkViewMode === 'edit' ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'}`}
                                        >
                                            {t('编辑', 'Edit')}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {storyFrameworkViewMode === 'edit' ? (
                                <textarea
                                    ref={(el) => {
                                        if (el) {
                                            if (el.dataset.content === el.value) return;
                                            const scrollParent = el.closest('.overflow-y-auto');
                                            const scrollTopContainer = scrollParent ? scrollParent.scrollTop : 0;
                                            const scrollTopWindow = window.scrollY;
                                            el.style.height = 'auto';
                                            el.style.height = el.scrollHeight + 'px';
                                            el.dataset.content = el.value;
                                            if (scrollParent) scrollParent.scrollTop = scrollTopContainer;
                                            window.scrollTo(0, scrollTopWindow);
                                        }
                                    }}
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full min-h-[12rem] resize-none overflow-hidden"
                                    value={info.story_dna_global_md || ''}
                                    onFocus={() => setStoryGenFocusStep('global_framework')}
                                    onChange={(e) => updateField('story_dna_global_md', e.target.value)}
                                    placeholder={t('（生成后，全局框架会显示在这里。你可以编辑后保存修改。）', '(After generation, the global framework will appear here. You can edit it and Save Changes.)')}
                                />
                            ) : (
                                <div className="bg-black/30 border border-white/10 rounded-md px-3 py-3 min-h-[12rem] overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1">
                                    {(info.story_dna_global_md || '').trim()
                                        ? <ReactMarkdown>{info.story_dna_global_md}</ReactMarkdown>
                                        : <div className="text-sm text-muted-foreground">{t('（生成后，全局框架会显示在这里。）', '(After generation, the global framework will appear here.)')}</div>
                                    }
                                </div>
                            )}
                        </div>

                        {/* Step 4: Episode Generation */}
                        <div
                            ref={(el) => { storyGenStepRefs.current.episode_scripts = el; }}
                            className={`rounded-xl border p-4 space-y-3 transition-colors ${storyGenFocusStep === 'episode_scripts' ? 'border-purple-500/40 bg-purple-500/5' : 'border-white/10 bg-white/[0.02]'}`}
                        >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                <div className="flex items-center gap-2">
                                    <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center border ${(episodeScriptsReady && episodeScriptsGeneratedCount > 0) ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-white/5 border-white/20 text-white/60'}`}>4</span>
                                    <div>
                                        <div className="text-sm font-semibold text-white">{t('分集剧本生成', 'Episode Script Generation')}</div>
                                        <div className="text-[11px] text-muted-foreground mt-0.5">
                                            {seriesIpMode
                                                ? t('按集写。填写这一集的基本剧情、冲突和亮点；此前各集摘要会自动作为下一集的输入。不预写全部分集。', 'Write one episode at a time. Give this episode’s plot, conflict, and highlights. Summaries of earlier episodes are fed into the next one. Episode frameworks are not prewritten.')
                                                : t('基于全局框架与角色设定批量/单集生成正片。预告片每次新写一条，不覆盖已有预告；可指定侧重点，以及从哪一集到哪一集，留空则从头到尾。', 'Batch or single-episode scripts from the global framework. Each trailer is a new piece. Set a focus and an episode range, or leave the range blank to cover the whole series.')}
                                        </div>
                                    </div>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <button
                                        onClick={handleGenerateEpisodeScripts}
                                        disabled={seriesIpMode || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts || !globalFrameworkReady}
                                        className={`px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 ${(seriesIpMode || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts || !globalFrameworkReady) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary/20 text-primary hover:bg-primary/30'}`}
                                        title={seriesIpMode
                                            ? t('系列剧（IP模式）不预生成全部分集，请使用单集生成。', 'Series IP does not prewrite every episode. Use single-episode generation.')
                                            : t('从全局框架 + 项目角色设定生成分集剧本，自动创建缺失分集并写入对应分集', 'Generate episode scripts from Global Framework + Project Character Canon, create missing episodes, and save each script into its episode')}
                                    >
                                        {episodeScriptsRunning ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Wand2 className="w-3.5 h-3.5" /> {t('全量生成分集', 'Generate All')}</>}
                                    </button>
                                    <div className="flex items-center bg-white/5 rounded-lg overflow-hidden border border-white/10">
                                        <input
                                            type="number"
                                            min="1"
                                            placeholder={t('单集', 'Ep#')}
                                            className="w-16 px-2 py-2 bg-transparent text-sm text-center outline-none text-white placeholder-white/30"
                                            value={targetEpisodeNumberForGen}
                                            onChange={e => setTargetEpisodeNumberForGen(e.target.value)}
                                            disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                        />
                                        <button
                                            onClick={() => handleGenerateEpisodeScripts({ specificEpisode: targetEpisodeNumberForGen })}
                                            disabled={!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts || !globalFrameworkReady}
                                            className={`px-3 py-2 text-xs font-bold flex items-center bg-white/10 hover:bg-white/20 transition-colors ${(!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts || !globalFrameworkReady) ? 'opacity-50 cursor-not-allowed' : 'text-blue-300'}`}
                                            title={t('仅生成填写的单个集数', 'Generate only the specified episode number')}
                                        >
                                            {t('单集生成', 'Gen Single')}
                                        </button>
                                    </div>
                                    <button
                                        onClick={handleStopEpisodeScripts}
                                        disabled={isStoppingEpisodeScripts}
                                        className={`px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 ${isStoppingEpisodeScripts ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                        title={t('强制停止当前批量分集剧本任务', 'Force stop current batch episode scripts task')}
                                    >
                                        {isStoppingEpisodeScripts
                                            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('停止中...', 'Stopping...')}</>
                                            : <><X className="w-3.5 h-3.5" /> {t('强制停止', 'Force Stop')}</>}
                                    </button>
                                </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-2 py-2">
                                <span className="text-[11px] text-amber-100/80 whitespace-nowrap">{t('预告片', 'Trailer')}</span>
                                <input
                                    type="text"
                                    value={trailerFocus}
                                    onChange={(e) => setTrailerFocus(e.target.value)}
                                    placeholder={t('侧重点（可选，如感情线、动作高光）', 'Focus (optional)')}
                                    disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                    className="min-w-[12rem] flex-1 px-2 py-1.5 rounded bg-black/30 border border-white/10 text-xs text-white placeholder-white/30 outline-none"
                                />
                                <span className="text-[11px] text-white/70 whitespace-nowrap">{t('从第', 'From ep')}</span>
                                <input
                                    type="number"
                                    min="1"
                                    value={trailerEpisodeFrom}
                                    onChange={(e) => setTrailerEpisodeFrom(e.target.value)}
                                    placeholder={t('首', 'Start')}
                                    disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                    className="w-16 px-2 py-1.5 rounded bg-black/30 border border-white/10 text-xs text-center text-white placeholder-white/30 outline-none"
                                />
                                <span className="text-[11px] text-white/70 whitespace-nowrap">{t('集到第', 'to ep')}</span>
                                <input
                                    type="number"
                                    min="1"
                                    value={trailerEpisodeTo}
                                    onChange={(e) => setTrailerEpisodeTo(e.target.value)}
                                    placeholder={t('末', 'End')}
                                    disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                    className="w-16 px-2 py-1.5 rounded bg-black/30 border border-white/10 text-xs text-center text-white placeholder-white/30 outline-none"
                                />
                                <span className="text-[11px] text-white/45 whitespace-nowrap">{t('集，留空则从头到尾', 'Blank = whole series')}</span>
                                <button
                                    type="button"
                                    onClick={() => handleGenerateEpisodeScripts({ outputKind: 'trailer' })}
                                    disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts || !globalFrameworkReady}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 ${(episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts || !globalFrameworkReady) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-amber-500/20 text-amber-200 hover:bg-amber-500/30'}`}
                                    title={t('新写一条预告片，不覆盖已有预告和正片。可指定侧重点和集数范围。', 'Add a new trailer without overwriting existing trailers or episodes. Optional focus and episode range.')}
                                >
                                    {t('生成预告片', 'Generate Trailer')}
                                </button>
                            </div>

                            {seriesIpMode ? (
                                <div className="space-y-3">
                                    <div className="text-[11px] text-muted-foreground/80">
                                        {t('单集生成时，下面四项是这一集的唯一剧情指定。全剧信息里的经典对标仍作整体剧本参考。此前各集摘要会自动写入提示词。', 'On single-episode generation, these four fields are the only plot brief for this episode. Classic references in the series bible still guide the whole script. Summaries of earlier episodes are added automatically.')}
                                    </div>
                                    {[
                                        {
                                            id: 'ip_episode_plot',
                                            label: t('本集基本剧情', 'This Episode Plot'),
                                            placeholder: t('这一集发生什么：谁、在什么压力下、做成哪一步。', 'What happens: who, under what pressure, and which step they complete.'),
                                            rows: 3,
                                        },
                                        {
                                            id: 'ip_episode_conflict',
                                            label: t('要体现的冲突', 'Conflict To Play'),
                                            placeholder: t('这一集要撞上的相反欲望，以及人物被迫做的选择。', 'The opposing wants that collide, and the choice the character is forced to make.'),
                                            rows: 2,
                                        },
                                        {
                                            id: 'ip_episode_highlights',
                                            label: t('重要亮点', 'Highlights'),
                                            placeholder: t('必须被看见的场面、金句或关系变化。可留空。', 'Scenes, lines, or relationship turns that must be seen. Optional.'),
                                            rows: 2,
                                        },
                                        {
                                            id: 'ip_episode_reference',
                                            label: t('本集对标（可选）', 'This Episode Reference (optional)'),
                                            placeholder: t('可点名一部经典的机制，用来演这一集。不填则沿用全剧对标。不要要求照搬剧情。', 'Name one classic mechanism for this episode. If empty, the series reference is used. Do not ask to copy the plot.'),
                                            rows: 2,
                                        },
                                    ].map((field) => (
                                        <div key={field.id}>
                                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{field.label}</label>
                                            <textarea
                                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25"
                                                rows={field.rows}
                                                value={globalStoryInput[field.id] || ''}
                                                onFocus={() => setStoryGenFocusStep('episode_scripts')}
                                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, [field.id]: e.target.value }))}
                                                disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                                placeholder={field.placeholder}
                                            />
                                        </div>
                                    ))}
                                    <div>
                                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('此前各集摘要', 'Earlier Episode Summaries')}</label>
                                        <div className="text-[11px] text-muted-foreground/80 mb-1.5">
                                            {t('生成后面的集时，这些摘要会作为已发生事实输入。改过前面的集之后，请重生成后面的集。', 'These summaries are fed in as facts when a later episode is generated. After changing an earlier episode, regenerate the later ones.')}
                                        </div>
                                        {priorEpisodeSummaries.length === 0 ? (
                                            <div className="text-sm text-muted-foreground rounded-md border border-white/10 bg-black/20 px-3 py-2">
                                                {t('还没有已生成的分集。第 1 集只根据全剧信息和本集指定来写。', 'No episodes yet. Episode 1 uses the series bible and this episode brief only.')}
                                            </div>
                                        ) : (
                                            <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
                                                {priorEpisodeSummaries.map((row) => (
                                                    <div key={row.number} className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
                                                        <div className="text-xs font-bold text-white">{t(`第${row.number}集`, `Episode ${row.number}`)}{row.title ? ` · ${row.title}` : ''}</div>
                                                        <div className="text-sm text-white/80 mt-1 whitespace-pre-wrap">
                                                            {row.summary || t('已有剧本，重新生成该集后会写入摘要。', 'Script exists. Regenerate this episode to store its summary.')}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ) : (
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('本集生成指导', 'This Episode Generation Guidance')}</label>
                                <div className="text-[11px] text-muted-foreground/80 mb-1.5">
                                    {t('仅「单集生成」时作为最高优先写入用户提示词；全量生成不会注入。', 'Injected as highest-priority user brief only for single-episode generation; not used by Generate All.')}
                                </div>
                                <textarea
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none placeholder:text-white/25"
                                    value={globalStoryInput.episode_generation_guidance || ''}
                                    onFocus={() => setStoryGenFocusStep('episode_scripts')}
                                    onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, episode_generation_guidance: e.target.value }))}
                                    disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                    placeholder={t('例如：本集强化反派压迫感；开场必须回收上集门铃声；高潮改在雨中对峙。', 'e.g. Heighten antagonist pressure; open by paying off last episode’s doorbell; move the climax to a rain confrontation.')}
                                />
                            </div>
                            )}

                            {episodeScriptsProgress && (
                                <div className="border border-white/10 rounded-lg p-3 bg-black/20 space-y-2">
                                    <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('分集剧本进度快照', 'Episode Scripts Progress Snapshot')}</div>
                                    <div className="h-2 rounded bg-white/10 overflow-hidden">
                                        <div
                                            className="h-2 bg-primary"
                                            style={{ width: `${progressPercent}%` }}
                                        />
                                    </div>
                                    <div className="text-sm text-white flex flex-wrap gap-x-4 gap-y-1">
                                        <span>{t('状态', 'Status')}: <b>{episodeScriptsProgress.running ? t('运行中', 'Running') : t('空闲', 'Idle')}</b></span>
                                        {episodeScriptsProgress.stop_requested ? <span>{t('停止请求', 'Stop Requested')}: <b>{t('是', 'Yes')}</b></span> : null}
                                        <span>{t('已处理', 'Processed')}: <b>{processedCount}</b> / <b>{episodesInRun}</b></span>
                                        <span>{t('已生成', 'Generated')}: <b>{episodeScriptsProgress.generated || 0}</b></span>
                                        <span>{t('失败', 'Failed')}: <b>{episodeScriptsProgress.failed || 0}</b></span>
                                        <span>{t('跳过', 'Skipped')}: <b>{episodeScriptsProgress.skipped || 0}</b></span>
                                    </div>
                                    <div className="flex items-center gap-2 pt-1">
                                        <button
                                            onClick={() => setShowEpisodeScriptsProgressModal(true)}
                                            className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20"
                                        >
                                            {t('查看详情', 'View Details')}
                                        </button>
                                        <button
                                            onClick={pollEpisodeScriptsStatus}
                                            className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-1.5"
                                        >
                                            <RefreshCw className="w-3.5 h-3.5" /> {t('刷新', 'Refresh')}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                </div>
                )}

                {(mode === 'market_research' || (mode === 'generator' && projectTab === 'market_research')) && (
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 space-y-4">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <div className="text-sm font-semibold text-white flex items-center gap-2">
                                    <Layers className="w-4 h-4 text-violet-300" />
                                    {t('近两月 AI 短剧市场情报', 'AI Short Drama Market Intelligence (Last 2 Months)')}
                                </div>
                                <div className="text-xs text-muted-foreground mt-1">
                                    {t('一键并行拉取：热榜题材变化分析 + 热门作品榜单（含高潮/名场面·画面·对白·动作）。联网检索后由剧本分析 LLM 分别汇总，并按时间写入数据库（搜索结果快照，需人工核对）。', 'One-click parallel fetch: genre-shift analysis + trending list with climax/iconic scenes. Web search + LLM synthesis; results are time-indexed and persisted (snapshot; verify before use).')}
                                </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                                {(industryAnalysisReport?.markdown || trendingDramasReport?.markdown) ? (
                                    <button
                                        type="button"
                                        onClick={handleAppendMarketResearchToWildIdeas}
                                        className="px-3 py-2 rounded-lg text-xs font-bold bg-white/10 text-white hover:bg-white/20"
                                    >
                                        {t('引用到天马行空', 'Append to Wild Ideas')}
                                    </button>
                                ) : null}
                                <button
                                    type="button"
                                    onClick={handleFetchMarketResearch}
                                    disabled={isFetchingMarketResearch || isGeneratingGlobalStory}
                                    className={`px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 ${(isFetchingMarketResearch || isGeneratingGlobalStory) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-violet-500/20 text-violet-100 hover:bg-violet-500/30'}`}
                                >
                                    {isFetchingMarketResearch
                                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('获取中...', 'Fetching...')}</>
                                        : <><RefreshCw className="w-3.5 h-3.5" /> {t('获取行业分析与热榜', 'Fetch Industry & Trending')}</>}
                                </button>
                            </div>
                        </div>

                        <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4 space-y-3">
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                                <div className="text-sm font-semibold text-white flex items-center gap-2">
                                    <Layers className="w-4 h-4 text-sky-300" />
                                    {t('热榜题材变化分析', 'Hot-List Genre Shift Analysis')}
                                </div>
                                <select
                                    value={selectedIndustryReportId}
                                    onChange={(e) => handleSelectMarketIntelReport(e.target.value, 'industry_analysis')}
                                    disabled={isLoadingMarketIntelHistory || industryHistoryOptions.length === 0}
                                    className="rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none disabled:opacity-50"
                                >
                                    {industryHistoryOptions.length === 0 ? (
                                        <option value="">{t('暂无历史', 'No history')}</option>
                                    ) : (
                                        industryHistoryOptions.map((item) => (
                                            <option key={`industry-hist-${item.id}`} value={String(item.id)}>
                                                {formatMarketIntelOptionLabel(item)}
                                            </option>
                                        ))
                                    )}
                                </select>
                            </div>
                            {industryAnalysisReport?.markdown ? (
                                <div className="bg-black/30 border border-white/10 rounded-md px-3 py-3 max-h-[28rem] overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 text-sm">
                                    <ReactMarkdown>{industryAnalysisReport.markdown}</ReactMarkdown>
                                    {industryAnalysisReport.disclaimer ? (
                                        <div className="text-[11px] text-muted-foreground mt-3 not-prose">{industryAnalysisReport.disclaimer}</div>
                                    ) : null}
                                </div>
                            ) : (
                                <div className="text-sm text-muted-foreground">
                                    {isFetchingMarketResearch
                                        ? t('正在生成题材变化分析...', 'Generating genre-shift analysis...')
                                        : t('点击上方按钮后，将在此显示热榜变化与题材趋势。', 'Genre-shift analysis will appear here after fetch.')}
                                </div>
                            )}
                        </div>

                        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                                <div className="text-sm font-semibold text-white flex items-center gap-2">
                                    <TrendingUp className="w-4 h-4 text-amber-300" />
                                    {t('热门作品榜单（高潮/名场面）', 'Trending List (Climax & Iconic Scenes)')}
                                </div>
                                <select
                                    value={selectedTrendingReportId}
                                    onChange={(e) => handleSelectMarketIntelReport(e.target.value, 'trending_dramas')}
                                    disabled={isLoadingMarketIntelHistory || trendingHistoryOptions.length === 0}
                                    className="rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none disabled:opacity-50"
                                >
                                    {trendingHistoryOptions.length === 0 ? (
                                        <option value="">{t('暂无历史', 'No history')}</option>
                                    ) : (
                                        trendingHistoryOptions.map((item) => (
                                            <option key={`trending-hist-${item.id}`} value={String(item.id)}>
                                                {formatMarketIntelOptionLabel(item)}
                                            </option>
                                        ))
                                    )}
                                </select>
                            </div>
                            {trendingDramasReport?.markdown ? (
                                <div className="bg-black/30 border border-white/10 rounded-md px-3 py-3 max-h-[28rem] overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 text-sm">
                                    <ReactMarkdown>{trendingDramasReport.markdown}</ReactMarkdown>
                                    {trendingDramasReport.disclaimer ? (
                                        <div className="text-[11px] text-muted-foreground mt-3 not-prose">{trendingDramasReport.disclaimer}</div>
                                    ) : null}
                                </div>
                            ) : (
                                <div className="text-sm text-muted-foreground">
                                    {isFetchingMarketResearch
                                        ? t('正在生成热门榜单...', 'Generating trending list...')
                                        : t('点击上方按钮后，将在此显示最热/新上榜作品及其高潮名场面、经典对白与画面动作看点。', 'Trending dramas with climax/iconic scenes, dialogue, and visual-action highlights will appear here after fetch.')}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
                )}

      </div>

            {showEpisodeScriptsProgressModal && (
                <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setShowEpisodeScriptsProgressModal(false)}>
                    <div className="bg-[#0f0f10] border border-white/10 rounded-xl w-full max-w-6xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
                        <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between gap-3">
                            <div>
                                <h3 className="text-lg font-semibold text-primary">{t('分集剧本进度中心', 'Episode Scripts Progress Center')}</h3>
                                <div className="text-xs text-muted-foreground">
                                    {t('实时跟踪每个分集并查看生成结果。', 'Track each episode in real time and review generation results.')}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleStopEpisodeScripts}
                                    disabled={isStoppingEpisodeScripts}
                                    className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1.5 ${isStoppingEpisodeScripts ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                >
                                    {isStoppingEpisodeScripts
                                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('停止中...', 'Stopping...')}</>
                                        : <><X className="w-3.5 h-3.5" /> {t('强制停止', 'Force Stop')}</>}
                                </button>
                                <button
                                    onClick={pollEpisodeScriptsStatus}
                                    className="px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-1.5"
                                >
                                    <RefreshCw className="w-3.5 h-3.5" /> {t('刷新', 'Refresh')}
                                </button>
                                <button
                                    className="p-2 rounded-md hover:bg-white/10 text-white/80"
                                    onClick={() => setShowEpisodeScriptsProgressModal(false)}
                                    title={t('关闭', 'Close')}
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        <div className="p-5 space-y-4 overflow-y-auto max-h-[calc(90vh-80px)]">
                            {episodeScriptsProgress ? (
                                <>
                                    <div className="grid grid-cols-2 md:grid-cols-7 gap-3 text-sm">
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('模式', 'Mode')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.mode || 'full'}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('状态', 'Status')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.running ? t('运行中', 'Running') : t('空闲', 'Idle')}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('停止请求', 'Stop Requested')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.stop_requested ? t('是', 'Yes') : t('否', 'No')}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('已处理', 'Processed')}</div>
                                            <div className="font-bold text-white">{processedCount} / {episodesInRun}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('已生成', 'Generated')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.generated || 0}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('失败', 'Failed')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.failed || 0}</div>
                                        </div>
                                        <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                                            <div className="text-xs text-muted-foreground">{t('跳过', 'Skipped')}</div>
                                            <div className="font-bold text-white">{episodeScriptsProgress.skipped || 0}</div>
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                                            <span>{t('总体进度', 'Overall Progress')}</span>
                                            <span>{progressPercent}%</span>
                                        </div>
                                        <div className="h-2 rounded bg-white/10 overflow-hidden">
                                            <div className="h-2 bg-primary" style={{ width: `${progressPercent}%` }} />
                                        </div>
                                    </div>

                                    {failedEpisodeRows.length > 0 && (
                                        <div className="border border-red-500/30 rounded-lg p-3 bg-red-500/10">
                                            <div className="text-xs text-red-200 mb-2">{t('失败分集（点击跳转）', 'Failed Episodes (click to jump)')}</div>
                                            <div className="flex flex-wrap gap-2">
                                                {failedEpisodeRows.map((item, idx) => (
                                                    <button
                                                        key={`${item.episode_id}_${idx}`}
                                                        onClick={() => {
                                                            if (onJumpToEpisode && item.episode_id) onJumpToEpisode(item.episode_id);
                                                        }}
                                                        className="px-2 py-1 rounded text-xs bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-100"
                                                        title={item.error || t('跳转到分集', 'Jump to episode')}
                                                    >
                                                        {buildEpisodeDisplayLabel({
                                                            episodeNumber: item?.episode_number,
                                                            title: item?.episode_title,
                                                            fallbackNumber: Number(item?.episode_number || 0) || null,
                                                        })}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <div className="border border-white/10 rounded-lg overflow-hidden">
                                        <div className="grid grid-cols-12 bg-white/5 text-xs text-muted-foreground px-3 py-2">
                                            <div className="col-span-1">#</div>
                                            <div className="col-span-4">{t('分集', 'Episode')}</div>
                                            <div className="col-span-2">{t('状态', 'Status')}</div>
                                            <div className="col-span-3">{t('结果', 'Result')}</div>
                                            <div className="col-span-2 text-right">{t('操作', 'Action')}</div>
                                        </div>
                                        <div className="max-h-[38vh] overflow-y-auto">
                                            {episodeResultRows.length > 0 ? episodeResultRows.map((row, idx) => {
                                                const status = String(row?.status || 'pending');
                                                const statusClass =
                                                    status === 'generated'
                                                        ? 'bg-green-500/20 text-green-200 border-green-500/30'
                                                        : status === 'failed'
                                                            ? 'bg-red-500/20 text-red-200 border-red-500/30'
                                                            : status === 'skipped'
                                                                ? 'bg-yellow-500/20 text-yellow-200 border-yellow-500/30'
                                                                : 'bg-white/10 text-white/80 border-white/20';
                                                const resultText = row?.error || row?.reason || (row?.output_chars ? `${row.output_chars} ${t('字符', 'chars')}` : (status === 'pending' ? t('等待中', 'Waiting') : '-'));
                                                const titleMismatchSuffix = row?.title_mismatch ? ` · ${t('标题/编号不一致', 'Title/number mismatch')}` : '';
                                                const statusLabel =
                                                    status === 'generated'
                                                        ? t('已生成', 'Generated')
                                                        : status === 'failed'
                                                            ? t('失败', 'Failed')
                                                            : status === 'skipped'
                                                                ? t('跳过', 'Skipped')
                                                                : status === 'pending'
                                                                    ? t('待处理', 'Pending')
                                                                    : status;
                                                return (
                                                    <div key={`${row?.episode_number || idx}_${idx}`} className="grid grid-cols-12 px-3 py-2 text-sm border-t border-white/5 items-center">
                                                        <div className="col-span-1 text-white/90">{row?.episode_number || '-'}</div>
                                                        <div
                                                            className="col-span-4 text-white/90 truncate"
                                                            title={`${buildEpisodeDisplayLabel({
                                                                episodeNumber: row?.episode_number,
                                                                title: row?.episode_title,
                                                                fallbackNumber: Number(row?.episode_number || 0) || null,
                                                            })}${titleMismatchSuffix}`}
                                                        >
                                                            {buildEpisodeDisplayLabel({
                                                                episodeNumber: row?.episode_number,
                                                                title: row?.episode_title,
                                                                fallbackNumber: Number(row?.episode_number || 0) || null,
                                                            })}{titleMismatchSuffix}
                                                        </div>
                                                        <div className="col-span-2">
                                                            <span className={`px-2 py-0.5 rounded text-xs border ${statusClass}`}>{statusLabel}</span>
                                                        </div>
                                                        <div className="col-span-3 text-xs text-white/70 truncate" title={resultText}>{resultText}</div>
                                                        <div className="col-span-2 text-right">
                                                            {row?.episode_id ? (
                                                                <button
                                                                    onClick={() => onJumpToEpisode && onJumpToEpisode(row.episode_id)}
                                                                    className="px-2 py-1 rounded text-xs bg-white/10 text-white hover:bg-white/20"
                                                                >
                                                                    {t('打开', 'Open')}
                                                                </button>
                                                            ) : (
                                                                <span className="text-xs text-white/40">-</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            }) : (
                                                <div className="px-3 py-6 text-center text-sm text-muted-foreground">{t('暂无分集运行记录。', 'No episode run records yet.')}</div>
                                            )}
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="text-sm text-muted-foreground py-10 text-center">
                                    {t('暂无生成状态。点击“生成分集剧本”开始跟踪。', 'No generation status yet. Start “Generate Episode Scripts” to begin tracking.')}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {showCanonModal && (
                <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
                    <div className="bg-[#0f0f10] border border-white/10 rounded-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto custom-scrollbar">
                        <div className="p-6 space-y-5">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-semibold text-primary">{t('角色设定集（项目）', 'Character Canon (Project)')}</h3>
                                    <div className="text-xs text-muted-foreground">选择身份标签 + 外观/风格标签，生成后会追加到项目 Canon。</div>
                                </div>
                                <button
                                    className="p-2 rounded-md hover:bg-white/10 text-white/80"
                                    onClick={closeCanonModal}
                                    title={t('关闭', 'Close')}
                                >
                                    <X size={18} />
                                </button>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">角色名称</label>
                                    <input
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                        value={canonName}
                                        onChange={(e) => setCanonName(e.target.value)}
                                        placeholder="例如：林娜 / Lina"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">自定义身份（可选，逗号/换行分隔）</label>
                                    <input
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                        value={canonCustomIdentity}
                                        onChange={(e) => setCanonCustomIdentity(e.target.value)}
                                        placeholder="例如：失忆 / 黑客 / 继承人"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">身材/体态/身体特征（可选）</label>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-16 resize-none"
                                        value={canonBody}
                                        onChange={(e) => setCanonBody(e.target.value)}
                                        placeholder="例如：高挑、肩颈线清晰、走路很稳、短发…"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">自定义风格标签（可选，逗号/换行分隔）</label>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-16 resize-none"
                                        value={canonCustomTags}
                                        onChange={(e) => setCanonCustomTags(e.target.value)}
                                        placeholder="例如：冷艳、黑西装、琥珀眼、雨夜霓虹…"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">额外备注（可选）</label>
                                    <textarea
                                        className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                                        value={canonExtra}
                                        onChange={(e) => setCanonExtra(e.target.value)}
                                        placeholder="例如：镜头表现、禁忌、语气/动作习惯…"
                                    />
                                </div>
                            </div>

                            <div className="flex items-center justify-between gap-3">
                                <div className="text-sm text-white/80">身份标签</div>
                                <button
                                    className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-2 ${canonTagEditMode ? 'bg-primary text-black' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                    onClick={() => setCanonTagEditMode(v => !v)}
                                    title={t('切换分类编辑模式', 'Toggle edit mode for categories')}
                                >
                                    <Edit3 className="w-3.5 h-3.5" /> {canonTagEditMode ? '编辑中' : '编辑标签'}
                                </button>
                            </div>

                            <div className="space-y-4">
                                {(canonIdentityCategories || []).map(cat => (
                                    <div key={cat.key} className="border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        <div className="flex items-center justify-between gap-3 mb-3">
                                            {canonTagEditMode ? (
                                                <input
                                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                    value={cat.title}
                                                    onChange={(e) => updateIdentityCategoryTitle(cat.key, e.target.value)}
                                                />
                                            ) : (
                                                <div className="text-sm font-semibold text-white">{cat.title}</div>
                                            )}
                                            {canonTagEditMode && (
                                                <button
                                                    className="px-3 py-2 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                                    onClick={() => addIdentityOption(cat.key)}
                                                >
                                                    <Plus size={14} /> 新增
                                                </button>
                                            )}
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {(cat.options || []).map(opt => {
                                                const selected = canonSelectedIdentityIds.includes(opt.id);
                                                return (
                                                    <div key={opt.id} className={`border rounded-lg p-3 flex gap-3 ${selected ? 'border-primary/60 bg-primary/10' : 'border-white/10 bg-black/20'}`}>
                                                        <button
                                                            className="flex-1 text-left"
                                                            onClick={() => !canonTagEditMode && toggleCanonIdentityId(opt.id)}
                                                            title={canonTagEditMode ? '编辑模式下不可选择' : '点击选择'}
                                                        >
                                                            {canonTagEditMode ? (
                                                                <div className="space-y-2">
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.label}
                                                                        onChange={(e) => updateIdentityOption(cat.key, opt.id, { label: e.target.value })}
                                                                    />
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs text-white/90 focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.detail}
                                                                        onChange={(e) => updateIdentityOption(cat.key, opt.id, { detail: e.target.value })}
                                                                    />
                                                                </div>
                                                            ) : (
                                                                <>
                                                                    <div className="text-sm font-semibold text-white flex items-center gap-2">
                                                                        {selected ? <Check size={16} className="text-primary" /> : <span className="w-4" />}
                                                                        {opt.label}
                                                                    </div>
                                                                    <div className="text-xs text-white/60 mt-1">{opt.detail}</div>
                                                                </>
                                                            )}
                                                        </button>

                                                        {canonTagEditMode && (
                                                            <button
                                                                className="p-2 rounded-md hover:bg-white/10 text-white/70"
                                                                onClick={() => removeIdentityOption(cat.key, opt.id)}
                                                                title={t('删除', 'Delete')}
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="text-sm text-white/80">外观/风格标签</div>

                            <div className="space-y-4">
                                {(canonTagCategories || []).map(cat => (
                                    <div key={cat.key} className="border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        <div className="flex items-center justify-between gap-3 mb-3">
                                            {canonTagEditMode ? (
                                                <input
                                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                    value={cat.title}
                                                    onChange={(e) => updateCanonCategoryTitle(cat.key, e.target.value)}
                                                />
                                            ) : (
                                                <div className="text-sm font-semibold text-white">{cat.title}</div>
                                            )}
                                            {canonTagEditMode && (
                                                <button
                                                    className="px-3 py-2 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                                    onClick={() => addCanonOption(cat.key)}
                                                >
                                                    <Plus size={14} /> 新增
                                                </button>
                                            )}
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {(cat.options || []).map(opt => {
                                                const selected = canonSelectedTagIds.includes(opt.id);
                                                return (
                                                    <div key={opt.id} className={`border rounded-lg p-3 flex gap-3 ${selected ? 'border-primary/60 bg-primary/10' : 'border-white/10 bg-black/20'}`}>
                                                        <button
                                                            className="flex-1 text-left"
                                                            onClick={() => !canonTagEditMode && toggleCanonTagId(opt.id)}
                                                            title={canonTagEditMode ? '编辑模式下不可选择' : '点击选择'}
                                                        >
                                                            {canonTagEditMode ? (
                                                                <div className="space-y-2">
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.label}
                                                                        onChange={(e) => updateCanonOption(cat.key, opt.id, { label: e.target.value })}
                                                                    />
                                                                    <input
                                                                        className="bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs text-white/90 focus:border-primary/50 focus:outline-none w-full"
                                                                        value={opt.detail}
                                                                        onChange={(e) => updateCanonOption(cat.key, opt.id, { detail: e.target.value })}
                                                                    />
                                                                </div>
                                                            ) : (
                                                                <>
                                                                    <div className="text-sm font-semibold text-white flex items-center gap-2">
                                                                        {selected ? <Check size={16} className="text-primary" /> : <span className="w-4" />}
                                                                        {opt.label}
                                                                    </div>
                                                                    <div className="text-xs text-white/60 mt-1">{opt.detail}</div>
                                                                </>
                                                            )}
                                                        </button>
                                                        {canonTagEditMode && (
                                                            <button
                                                                className="p-2 rounded-md hover:bg-white/10 text-white/70"
                                                                onClick={() => removeCanonOption(cat.key, opt.id)}
                                                                title={t('删除', 'Delete')}
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="flex items-center justify-end gap-2 pt-2">
                                {canonTagEditMode && (
                                    <button
                                        className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20"
                                        onClick={async () => {
                                            const normalizedTags = normalizeCanonTagCategories(canonTagCategories);
                                            const normalizedIdentity = normalizeCanonTagCategories(canonIdentityCategories);
                                            const ok1 = normalizedTags ? persistCanonTagCategories(normalizedTags) : false;
                                            const ok2 = normalizedIdentity ? persistCanonIdentityCategories(normalizedIdentity) : false;
                                            let okDb = true;
                                            try {
                                                if (!id) throw new Error('Missing project id');
                                                if (!normalizedTags || !normalizedIdentity) throw new Error('Invalid categories');
                                                await saveProjectCharacterCanonCategories(id, {
                                                    tag_categories: normalizedTags,
                                                    identity_categories: normalizedIdentity,
                                                });
                                            } catch (e) {
                                                okDb = false;
                                                console.error('[Character Canon Categories] Save failed:', e);
                                            }
                                            alert(ok1 && ok2 && okDb ? t('已保存标签配置（数据库+localStorage）', 'Tag configuration saved (database + localStorage)') : t('保存失败', 'Save failed'));
                                        }}
                                    >
                                        <Save className="w-4 h-4 inline-block mr-2" /> {t('保存标签配置', 'Save Tag Configuration')}
                                    </button>
                                )}
                                <button
                                    className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20"
                                    onClick={closeCanonModal}
                                    disabled={isGeneratingCanon}
                                >
                                    {t('关闭', 'Close')}
                                </button>
                                <button
                                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingCanon ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-primary text-black hover:bg-primary/90'}`}
                                    onClick={handleGenerateProjectCanon}
                                    disabled={isGeneratingCanon}
                                >
                                    {isGeneratingCanon ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成并追加', 'Generate & Append')}</>}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};



