
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
    PROJECT_EP_CREATIVITY_OPTIONS,
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
    normalizeProjectSceneAnalysisEra,
    normalizeProjectSceneAnalysisSafety,
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
export const ProjectOverview = ({ id, project: initialProject = null, onProjectUpdate, onRefreshEpisodes, onJumpToEpisode, onTabChange, episodes = [], uiLang = 'en', mode = 'overview' }) => {
    const functionApiConfigs = useFunctionApis();
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const resolveVideoSoundFromInfo = (payload) => {
        const src = (payload && typeof payload === 'object') ? payload : {};
        const visual = (src.tech_params && src.tech_params.visual_standard && typeof src.tech_params.visual_standard === 'object')
            ? src.tech_params.visual_standard
            : {};
        const defaults = (src.project_generation_defaults && typeof src.project_generation_defaults === 'object')
            ? src.project_generation_defaults
            : {};
        const candidate = src.video_sound ?? src.sound ?? defaults.sound ?? visual.sound;
        return candidate === false ? false : true;
    };
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
        series_episode: "",
        base_positioning: "现代职场 / Modern Workplace",
        type: "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
        Global_Style: "",
        tech_params: {
            visual_standard: {
                horizontal_resolution: "720",
                vertical_resolution: "1280",
                frame_rate: "24",
                aspect_ratio: "9:16",
                quality: "超高 / Ultra High",
                image_size: "1K"
            }
        },
        tone: "",
        lighting: "",
        language: "英文 / English",
        video_sound: true,
        borrowed_films: [],
        generation_seed: "",
        project_share_users: [],
        project_reviewer_users: [],
        character_relationships: "",
        notes: "",
        story_dna_global_md: "",
        promo_dna_global_md: "",
        story_generator_global_input: {
            episodes_count: 12,
            background: "",
            setup: "",
            development: "",
            turning_points: "",
            climax: "",
            resolution: "",
            suspense: "",
            foreshadowing: "",
            extra_notes: "",
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
        episodes_count: 20,
        script_mode: "短剧快节奏 / Short Drama",
        target_audience: "男频路线 / Male-Oriented",
        background: "",
        setup: "",
        development: "",
        turning_points: "",
        climax: "",
        resolution: "",
        suspense: "",
        foreshadowing: "",
        extra_notes: "",
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
    const [targetEpisodeNumberForGen, setTargetEpisodeNumberForGen] = useState('');
    const [hasSetDefaultEp, setHasSetDefaultEp] = useState(false);
    
    useEffect(() => {
        if (episodes && episodes.length > 0) {
            let defaultEp = 1;
            const getEpNum = (e, i) => Number(e.episode_number) || parseEpisodeNumberFromText(e.title) || (i + 1);
            
            const ungeneratedEps = episodes.map((e, index) => ({ e, index }))
                .filter(({e}) => !e.script_content || String(e.script_content).trim() === '');
            
            if (ungeneratedEps.length > 0) {
                defaultEp = Math.min(...ungeneratedEps.map(({e, index}) => getEpNum(e, index)));
            } else {
                defaultEp = Math.max(...episodes.map((e, index) => getEpNum(e, index)));
            }
            
            if (!hasSetDefaultEp) {
                setTargetEpisodeNumberForGen(String(defaultEp));
                setHasSetDefaultEp(true);
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [episodes, hasSetDefaultEp]);

    const [isGeneratingGlobalStory, setIsGeneratingGlobalStory] = useState(false);
    const [isGeneratingEpisodeScripts, setIsGeneratingEpisodeScripts] = useState(false);
    const [isStoppingEpisodeScripts, setIsStoppingEpisodeScripts] = useState(false);
    const [episodeScriptsProgress, setEpisodeScriptsProgress] = useState(null);
    const [showEpisodeScriptsProgressModal, setShowEpisodeScriptsProgressModal] = useState(false);
    const [isAnalyzingNovel, setIsAnalyzingNovel] = useState(false);
    const [isImportingStoryPackage, setIsImportingStoryPackage] = useState(false);
    const [novelImportText, setNovelImportText] = useState('');
    const [showGlobalStoryGuide, setShowGlobalStoryGuide] = useState(false);
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

    useEffect(() => {
        if (mode !== 'generator') {
            setProjectTab('overview');
            return;
        }
        setProjectTab((prev) => (prev === 'promo_generator' ? 'promo_generator' : 'story_generator'));
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
                     merged.type = normalizeProjectEpisodeType(merged.type);
                     merged.language = normalizeProjectEpisodeLanguage(merged.language);
                     merged.base_positioning = normalizeProjectEpisodeBasePositioning(merged.base_positioning);
                     merged.era = normalizeProjectSceneAnalysisEra(merged.era);
                     merged.broadcast_safety_level = normalizeProjectSceneAnalysisSafety(merged.broadcast_safety_level);
                     merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
                     merged.tone = normalizeProjectEpisodeTone(merged.tone);
                     merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
                     merged.video_sound = resolveVideoSoundFromInfo(merged);
                     merged.generation_seed = resolveProjectSeedFromInfo(merged);
                     merged.project_share_users = normalizeUserListValues(merged.project_share_users);
                     merged.project_reviewer_users = normalizeUserListValues(merged.project_reviewer_users);
                     if (merged.tech_params?.visual_standard) {
                         merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
                     }
                     setInfo(merged);

                     // Restore Story Generator draft inputs (if previously saved)
                     if (merged.story_generator_global_input && typeof merged.story_generator_global_input === 'object') {
                         setGlobalStoryInput(prev => ({
                             ...prev,
                             ...merged.story_generator_global_input,
                         }));
                     }

                     if (merged.promo_generator_input && typeof merged.promo_generator_input === 'object') {
                        setPromoInput(prev => ({
                            ...prev,
                            ...merged.promo_generator_input,
                        }));
                     }

                     // Avoid immediately auto-saving right after hydration
                     skipNextGlobalStoryAutosaveRef.current = true;

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
            try {
                const payload = {
                    mode: 'global',
                    generator_kind: 'story',
                    episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
                    script_mode: globalStoryInput.script_mode,
                    target_audience: globalStoryInput.target_audience,
                    background: globalStoryInput.background,
                    setup: globalStoryInput.setup,
                    development: globalStoryInput.development,
                    turning_points: globalStoryInput.turning_points,
                    climax: globalStoryInput.climax,
                    resolution: globalStoryInput.resolution,
                    suspense: globalStoryInput.suspense,
                    foreshadowing: globalStoryInput.foreshadowing,
                    extra_notes: globalStoryInput.extra_notes,
                };
                await saveProjectStoryGeneratorGlobalInput(id, payload);
            } catch (e) {
                console.error('[Global Story Generator] Auto-save failed:', e);
            }
        }, 800);

        return () => {
            if (globalStoryAutosaveTimerRef.current) {
                clearTimeout(globalStoryAutosaveTimerRef.current);
            }
        };
    }, [id, globalStoryInput, isGeneratingGlobalStory]);

    const handleSave = async () => {
        try {
            const resolvedVideoSound = info.video_sound === false ? false : true;
            const seedParsed = Number(info.generation_seed);
            const resolvedSeed = Number.isFinite(seedParsed) && seedParsed > 0
                ? Math.trunc(seedParsed)
                : null;

            const global_info = {
                ...info,
                project_share_users: normalizeUserListValues(info.project_share_users),
                project_reviewer_users: normalizeUserListValues(info.project_reviewer_users),
                video_sound: resolvedVideoSound,
                project_generation_defaults: {
                    ...(info.project_generation_defaults || {}),
                    sound: resolvedVideoSound,
                },
                tech_params: {
                    ...(info.tech_params || {}),
                    visual_standard: {
                        ...(info.tech_params?.visual_standard || {}),
                        sound: resolvedVideoSound,
                    },
                },
                story_generator_global_input: {
                    ...globalStoryInput,
                    episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
                },
                promo_generator_input: {
                    ...promoInput,
                    episodes_count: Number(promoInput.episodes_count || 0) || 0,
                },
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

            const updated = await generateProjectStoryGlobal(id, payload);
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
                merged.base_positioning = normalizeProjectEpisodeBasePositioning(merged.base_positioning);
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

    const handleGenerateGlobalStory = async () => {
        if (globalStoryGenerationInFlightRef.current || isGeneratingGlobalStory) return;
        globalStoryGenerationInFlightRef.current = true;
        setIsGeneratingGlobalStory(true);
        try {
            const payload = {
                mode: 'global',
                generator_kind: 'story',
                episodes_count: Number(globalStoryInput.episodes_count || 0),
                script_mode: globalStoryInput.script_mode,
                target_audience: globalStoryInput.target_audience,
                // Project Overview / Basic Information (forward to LLM)
                script_title: info.script_title,
                expected_duration: info.expected_duration,
                type: info.type,
                language: info.language,
                base_positioning: info.base_positioning,
                Global_Style: info.Global_Style,
                background: globalStoryInput.background,
                setup: globalStoryInput.setup,
                development: globalStoryInput.development,
                turning_points: globalStoryInput.turning_points,
                climax: globalStoryInput.climax,
                resolution: globalStoryInput.resolution,
                suspense: globalStoryInput.suspense,
                foreshadowing: globalStoryInput.foreshadowing,
                extra_notes: globalStoryInput.extra_notes,
            };
            const updated = await generateProjectStoryGlobal(id, payload);
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
                merged.base_positioning = normalizeProjectEpisodeBasePositioning(merged.base_positioning);
                merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
                merged.tone = normalizeProjectEpisodeTone(merged.tone);
                merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
                if (merged.tech_params?.visual_standard) {
                    merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
                }
                setInfo(merged);
            }
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

                if (updated.global_info.story_generator_global_input && typeof updated.global_info.story_generator_global_input === 'object') {
                    skipNextGlobalStoryAutosaveRef.current = true;
                    setGlobalStoryInput(prev => ({
                        ...prev,
                        ...updated.global_info.story_generator_global_input,
                    }));
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

    const handleGenerateEpisodeScripts = async ({ retryFailedOnly = false, forceStart = false, specificEpisode = null } = {}) => {
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
        if (!specificEpisode && (!n || Number.isNaN(n) || n <= 0)) {
            alert('Please set a valid Episodes Count first.');
            episodeScriptsGenerationInFlightRef.current = false;
            return;
        }

        setIsGeneratingEpisodeScripts(true);
        setEpisodeScriptsProgress(null);
        setShowEpisodeScriptsProgressModal(true);

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
                : specificEpisode ? `generate-episode-${specificEpisode}`
                : 'overwrite-all-default';

            if (overwriteExisting && !specificEpisode) {
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
                `[DEBUG][Before API] Generate Episode Scripts payload: ${JSON.stringify({ generator_kind: generatorKind, episodes_count: n, script_mode: globalStoryInput.script_mode, overwrite_existing: overwriteExisting, retry_failed_only: retryFailedOnly, episode_number: specificEpisode })}`,
                'info'
            );
            const reqPayload = {
                generator_kind: generatorKind,
                episodes_count: n,
                script_mode: globalStoryInput.script_mode,
                overwrite_existing: overwriteExisting,
                retry_failed_only: retryFailedOnly,
            };
            if (specificEpisode) {
                reqPayload.episode_number = Number(specificEpisode);
            }
            const res = await generateProjectEpisodeScripts(id, reqPayload);

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
                await onRefreshEpisodes();
            }

            // In single-episode mode, jump directly to the resolved episode_id returned by backend.
            // This avoids staying on another duplicate-number episode and looking like overwrite failed.
            if (specificEpisode) {
                const generatedSingle = results.find((item) => {
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
                    onJumpToEpisode(resolvedEpisodeId);
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
            const updated = await generateProjectCharacterProfile(id, {
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
                function_name: 'generate_subjects',
            });
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
        setInfo(prev => ({
            ...prev,
            [key]: key === 'type'
                ? normalizeProjectEpisodeType(value)
                : key === 'language'
                    ? normalizeProjectEpisodeLanguage(value)
                    : key === 'base_positioning'
                        ? normalizeProjectEpisodeBasePositioning(value)
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
            const nextValue = key === 'quality' ? normalizeProjectEpisodeQuality(value) : value;
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
        const resolvedBasePositioning = String(info?.base_positioning || '').trim();
        const resolvedGlobalStyle = String(info?.Global_Style || '').trim();
        return [
            { label: t('剧本标题', 'Script Title'), value: resolvedScriptTitle },
            { label: t('类型', 'Type'), value: resolvedType },
            { label: t('语言', 'Language'), value: resolvedLanguage },
            { label: t('基础定位', 'Base Positioning'), value: resolvedBasePositioning },
            { label: t('全局风格', 'Global Style'), value: resolvedGlobalStyle },
        ];
    }, [info?.script_title, info?.type, info?.language, info?.base_positioning, info?.Global_Style, project?.title, t]);
    const storyGeneratorMissingInfo = useMemo(() => {
        const missing = [];
        if (!String(info?.script_title || project?.title || '').trim()) missing.push(t('剧本标题', 'Script Title'));
        if (!String(info?.type || '').trim()) missing.push(t('类型', 'Type'));
        if (!String(info?.language || '').trim()) missing.push(t('语言', 'Language'));
        if (!String(info?.base_positioning || '').trim()) missing.push(t('基础定位', 'Base Positioning'));
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

    if (!project) return <div className="p-8 text-muted-foreground">{t('加载中...', 'Loading...')}</div>;

    const prefix = "proj-";
    const generatorTabs = [
        { id: 'story_generator', label: t('故事生成器', 'Story Generator') },
        { id: 'promo_generator', label: t('宣传片生成器', 'Promo Generator') },
    ];

    return (
        <div className="p-4 sm:p-6 lg:p-8 w-full h-full overflow-y-auto">
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center mb-8">
                <div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold">{mode === 'generator' ? t('生成器', 'Generators') : t('项目总览', 'Project Overview')}</h2>
                    {mode === 'overview' && (
                        <div className="flex items-center px-3 py-1 rounded-full bg-primary/20 border border-primary/30 text-primary text-sm font-medium">
                            {t('阶段', 'Stage')}: {
                                (info?.workflow_stage === 'montage') ? t('剪辑', 'Montage') :
                                (info?.workflow_stage === 'shots') ? t('分镜', 'Shots') :
                                (info?.workflow_stage === 'subjects') ? t('资产', 'Assets') :
                                t('剧本', 'Script')
                            }
                        </div>
                    )}
                </div>
                <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center justify-center gap-2 w-full sm:w-auto">
                    <SettingsIcon className="w-4 h-4" /> {t('保存修改', 'Save Changes')}
                </button>
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
                            label={t('基础定位', 'Base Positioning')}
                            value={info.base_positioning}
                            onChange={v => updateField('base_positioning', v)}
                            list={PROJECT_EP_BASE_POSITIONING_OPTIONS}
                            placeholder={t('例如：都市爱情 / 科幻', 'e.g. Urban Romance / Sci-Fi')}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('年代', 'Era')}
                            value={info.era}
                            onChange={v => updateField('era', v)}
                            list={PROJECT_SCENE_ANALYSIS_ERA_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('镜头偏好', 'Lens Preference')}
                            value={info.lens_preference}
                            onChange={v => updateField('lens_preference', v)}
                            list={PROJECT_EP_LENS_PREFERENCE_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('画幅比例', 'Aspect Ratio')}
                            value={info.tech_params?.visual_standard?.aspect_ratio}
                            onChange={v => updateTech('aspect_ratio', v)}
                            list={["16:9", "2.35:1", "4:3", "9:16", "1:1"]}
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
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-muted-foreground uppercase font-bold">{t('视频声音', 'Video Sound')}</label>
                        <select
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
                            value={info.video_sound === false ? 'off' : 'on'}
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

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('借鉴影片（参考）', 'Borrowed Films (Ref)')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={info.borrowed_films.join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder={t('用逗号分隔，例如：银翼杀手, 黑客帝国', 'Use commas to separate, e.g. Blade Runner, Matrix')}
                        />
                    </div>

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

                {/* Story Generator (Global) */}
                {mode === 'generator' && projectTab === 'story_generator' && (
                <div className="bg-card border border-white/10 p-4 sm:p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('故事生成器（全局 / 项目）', 'Story Generator (Global / Project)')}</h3>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={handleGenerateGlobalStory}
                                disabled={isGeneratingGlobalStory}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingGlobalStory ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('生成国际化爆款故事框架并保存到项目总览', 'Generate an international-blockbuster story framework and store it in project Overview')}
                            >
                                {isGeneratingGlobalStory ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成全局框架', 'Generate Global Framework')}</>}
                            </button>

                            <button
                                onClick={handleGenerateEpisodeScripts}
                                disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('从全局框架 + 项目角色设定生成分集剧本，自动创建缺失分集并写入对应分集', 'Generate episode scripts from Global Framework + Project Character Canon, create missing episodes, and save each script into its episode')}
                            >
                                {episodeScriptsRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Wand2 className="w-4 h-4" /> {t('全量生成分集', 'Generate All')}</>}
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
                                    disabled={!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                    className={`px-3 py-2 text-sm font-bold flex items-center bg-white/10 hover:bg-white/20 transition-colors ${(!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts) ? 'opacity-50 cursor-not-allowed' : 'text-blue-300'}`}
                                    title={t('仅生成填写的单个集数', 'Generate only the specified episode number')}
                                >
                                    {t('单集生成', 'Gen Single')}
                                </button>
                            </div>
                            <button
                                onClick={() => handleGenerateEpisodeScripts({ forceStart: true })}
                                disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('强制启动所有目标分集并覆盖已有剧本', 'Force start generation for all target episodes and overwrite existing scripts')}
                            >
                                {episodeScriptsRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('执行中...', 'Running...')}</> : <><RefreshCw className="w-4 h-4" /> {t('强制启动剧本', 'Force Start Scripts')}</>}
                            </button>
                            <button
                                onClick={() => handleGenerateEpisodeScripts({ retryFailedOnly: true })}
                                disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('仅重试上次运行失败的分集', 'Retry only failed episodes from the last run')}
                            >
                                {episodeScriptsRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('执行中...', 'Running...')}</> : <><RefreshCw className="w-4 h-4" /> {t('重试失败分集', 'Retry Failed Episodes')}</>}
                            </button>
                            <button
                                onClick={handleStopEpisodeScripts}
                                disabled={isStoppingEpisodeScripts}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isStoppingEpisodeScripts ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                title={t('强制停止当前批量分集剧本任务', 'Force stop current batch episode scripts task')}
                            >
                                {isStoppingEpisodeScripts
                                    ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('停止中...', 'Stopping...')}</>
                                    : <><X className="w-4 h-4" /> {t('强制停止', 'Force Stop')}</>}
                            </button>
                        </div>
                    </div>

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
                                <button
                                    onClick={handleStopEpisodeScripts}
                                    disabled={isStoppingEpisodeScripts}
                                    className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1.5 ${isStoppingEpisodeScripts ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                >
                                    {isStoppingEpisodeScripts
                                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('停止中...', 'Stopping...')}</>
                                        : <><X className="w-3.5 h-3.5" /> {t('强制停止', 'Force Stop')}</>}
                                </button>
                            </div>
                        </div>
                    )}



                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                        <InputGroup
                            idPrefix={prefix}
                            label={t('产品规格与节奏', 'Product Format')}
                            value={globalStoryInput.script_mode}
                            onChange={v => setGlobalStoryInput(prev => ({ ...prev, script_mode: v }))}
                            list={[
                                '短剧快节奏 / Short Drama',
                                '电影 / Feature Film',
                                '通用连续剧 / General Series'
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
                            {t('大模型将根据【产品规格】严格套用不同的工业化叙事节奏与起承转合结构，并针对【受众定位】极化核心看点与张力。', 'The AI will apply distinct rhythmic and structural pacing based on the chosen Product Format and polarize constraints based on target audience.')}
                        </div>
                        <div className="sm:col-span-2">
                            <div className="flex justify-between items-end mb-1">
                                <label className="text-xs text-muted-foreground uppercase font-bold block">{t('天马行空的想法', 'Wild Ideas & Creative Prompt')}</label>
                                <span className="text-[11px] text-muted-foreground/70">
                                    {t('💡 引导：把脑海中的画面、台词或怪念头倒出来，AI会帮你结构化三幕剧与人物弧光！', '💡 Hint: Pour out the scenes, dialogues, or quirky ideas in your mind, and AI will structure the 3-act beats and arcs!')}
                                </span>
                            </div>
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-32 resize-none"
                                value={globalStoryInput.extra_notes}
                                onChange={(e) => setGlobalStoryInput(prev => ({ ...prev, extra_notes: e.target.value }))}
                                placeholder={t('尽情输入，例如：\n我想写一个绝症杀手替女儿复仇的故事；\n主角是个有双重人格的天才，杀人前必听贝多芬；\n开头是一场从直升机上的反杀；\n某处大结局必须有一场雨中废弃工厂的宿命对决，兄弟反目，说“我们都回不去了”...', 'E.g.:\nA dying assassin takes revenge for his daughter;\nThe protagonist is a dual-personality genius who listens to Beethoven before killing;\nThe climax must feature a fated battle in an abandoned factory with the line "We can never go back".')}
                            />
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('已生成全局框架（Markdown）', 'Generated Global Framework (Markdown)')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-48 resize-none"
                            value={info.story_dna_global_md || ''}
                            onChange={(e) => updateField('story_dna_global_md', e.target.value)}
                            placeholder={t('（生成后，全局框架会显示在这里。你可以编辑后保存修改。）', '(After generation, the global framework will appear here. You can edit it and Save Changes.)')}
                        />
                    </div>
                </div>
                )}

                {mode === 'generator' && projectTab === 'promo_generator' && (
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('宣传片生成器（企业 / 产品 / 文旅）', 'Promo Generator (Corporate / Product / Tourism)')}</h3>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={handleGeneratePromoFramework}
                                disabled={isGeneratingGlobalStory}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingGlobalStory ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                            >
                                {isGeneratingGlobalStory ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成宣传框架', 'Generate Promo Framework')}</>}
                            </button>
                            <button
                                onClick={handleGenerateEpisodeScripts}
                                disabled={episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${(episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                            >
                                {episodeScriptsRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Wand2 className="w-4 h-4" /> {t('全量生成分集', 'Generate All')}</>}
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
                                    disabled={!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts}
                                    className={`px-3 py-2 text-sm font-bold flex items-center bg-white/10 hover:bg-white/20 transition-colors ${(!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts) ? 'opacity-50 cursor-not-allowed' : 'text-blue-300'}`}
                                    title={t('仅生成填写的单个集数', 'Generate only the specified episode number')}
                                >
                                    {t('单集生成', 'Gen Single')}
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup
                            idPrefix={prefix}
                            label={t('宣传类型', 'Promo Type')}
                            value={promoInput.promo_type}
                            onChange={v => setPromoInput(prev => ({ ...prev, promo_type: v }))}
                            list={[
                                '企业宣传 / Corporate Promotion',
                                '商品宣传 / Product Promotion',
                                '文旅宣传 / Cultural Tourism Promotion',
                            ]}
                        />
                        <InputGroup
                            idPrefix={prefix}
                            label={t('集数', 'Episodes Count')}
                            value={String(promoInput.episodes_count || '')}
                            onChange={v => setPromoInput(prev => ({ ...prev, episodes_count: Number(v || 0) }))}
                            list={['1', '3', '5', '6', '8', '10', '12']}
                        />

                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('传播目标', 'Campaign Objective')}</label>
                            <textarea className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none" value={promoInput.campaign_objective} onChange={(e) => setPromoInput(prev => ({ ...prev, campaign_objective: e.target.value }))} />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('目标受众', 'Target Audience')}</label>
                            <textarea className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none" value={promoInput.target_audience} onChange={(e) => setPromoInput(prev => ({ ...prev, target_audience: e.target.value }))} />
                        </div>
                        <div className="sm:col-span-2">
                            <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('核心信息', 'Key Message')}</label>
                            <textarea className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none" value={promoInput.key_message} onChange={(e) => setPromoInput(prev => ({ ...prev, key_message: e.target.value }))} />
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between gap-3 mb-1">
                            <label className="text-xs text-muted-foreground uppercase font-bold block">{t('已生成宣传框架（Markdown）', 'Generated Promo Framework (Markdown)')}</label>
                            <div className="flex items-center gap-1 bg-black/20 border border-white/10 rounded-md p-1">
                                <button
                                    type="button"
                                    onClick={() => setPromoFrameworkViewMode('preview')}
                                    className={`px-2 py-1 rounded text-xs font-bold ${promoFrameworkViewMode === 'preview' ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'}`}
                                >
                                    {t('预览', 'Preview')}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setPromoFrameworkViewMode('edit')}
                                    className={`px-2 py-1 rounded text-xs font-bold ${promoFrameworkViewMode === 'edit' ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'}`}
                                >
                                    {t('编辑', 'Edit')}
                                </button>
                            </div>
                        </div>

                        {promoFrameworkViewMode === 'edit' ? (
                            <textarea
                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-56 resize-none"
                                value={info.promo_dna_global_md || ''}
                                onChange={(e) => updateField('promo_dna_global_md', e.target.value)}
                                placeholder={t('（生成后，宣传片全局框架会显示在这里。你可以编辑后保存修改。）', '(After generation, promo global framework will appear here. You can edit it and Save Changes.)')}
                            />
                        ) : (
                            <div className="bg-black/30 border border-white/10 rounded-md px-3 py-3 h-56 overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1">
                                {(info.promo_dna_global_md || '').trim()
                                    ? <ReactMarkdown>{info.promo_dna_global_md}</ReactMarkdown>
                                    : <div className="text-sm text-muted-foreground">{t('（生成后，宣传片全局框架会显示在这里。）', '(After generation, promo global framework will appear here.)')}</div>
                                }
                            </div>
                        )}
                    </div>
                </div>
                )}

                {/* Character Canon (Project) */}
                {mode === 'generator' && projectTab === 'story_generator' && (
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('角色设定集（项目）', 'Character Canon (Project)')}</h3>
                        <div className="flex items-center gap-2">
                            <FunctionApiSelector functionName="generate_subjects" configs={functionApiConfigs} />
                            <button
                                onClick={() => setShowCanonModal(true)}
                                disabled={isGeneratingCanon}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingCanon ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('生成权威角色档案并追加到项目级角色设定集', 'Generate an authoritative character profile and append it to the project-level canon')}
                            >
                                {isGeneratingCanon ? <><Loader2 className="w-4 h-4 animate-spin" /> {t('生成中...', 'Generating...')}</> : <><Sparkles className="w-4 h-4" /> {t('生成并追加', 'Generate & Append')}</>}
                            </button>
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('设定集输出（Markdown）', 'Canon Output (Markdown)')}</label>
                        <div className="space-y-3">
                            {Array.isArray(info.character_profiles) && info.character_profiles.length > 0 ? (
                                info.character_profiles.map((p, idx) => {
                                    const name = String(p?.name || '').trim() || `${t('角色', 'Character')} ${idx + 1}`;
                                    const md = String(p?.description_md || '').trim();
                                    const updatedAt = String(p?.updated_at || '').trim();
                                    return (
                                        <div key={`${name}-${idx}`} className="bg-black/20 border border-white/10 rounded-lg p-3 space-y-2">
                                            <div className="flex items-center justify-between gap-3">
                                                <div>
                                                    <div className="text-sm font-bold text-white">{name}</div>
                                                    {updatedAt ? (
                                                        <div className="text-xs text-muted-foreground">{t('更新时间', 'Updated')}: {updatedAt}</div>
                                                    ) : null}
                                                </div>
                                                {String(p?.name || '').trim() ? (
                                                    <button
                                                        onClick={() => handleDeleteCanonCharacter(String(p.name))}
                                                        className="px-2 py-1 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2"
                                                        title={t('从设定集中删除该角色', 'Delete this character from canon')}
                                                    >
                                                        <Trash2 size={14} /> {t('删除', 'Delete')}
                                                    </button>
                                                ) : null}
                                            </div>
                                            <textarea
                                                className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white w-full h-40 resize-none"
                                                value={md || ''}
                                                readOnly
                                                placeholder={t('（生成后，该角色的设定 Markdown 会显示在这里。）', "(This character's canonical markdown will appear here after generation.)")}
                                            />
                                        </div>
                                    );
                                })
                            ) : (
                                <textarea
                                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white w-full h-28 resize-none"
                                    value={''}
                                    readOnly
                                    placeholder={t('（暂无角色。点击“生成并追加”创建首个角色设定。）', '(No characters yet. Click Generate & Append to create the first canon profile.)')}
                                />
                            )}
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('角色关系（纯文本）', 'Character Relationships (Plain Text)')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-28 resize-none"
                            value={info.character_relationships || ''}
                            onChange={(e) => updateField('character_relationships', e.target.value)}
                            placeholder={t('示例：A 是 B 的上司；B 暗恋 C；C 是 A 的对手...', "Example: A is B's boss; B secretly loves C; C is A's rival...")}
                        />
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



