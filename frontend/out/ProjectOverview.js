import FunctionApiSelector from "../../../components/FunctionApiSelector";
import { useFunctionApis } from "../../../components/useFunctionApis";
import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useLog } from "../../../context/LogContext";
import ReactMarkdown from "react-markdown";
import { useStore } from "../../../lib/store";
import LogPanel from "../../../components/LogPanel";
import ProjectStatusBar from "../../../components/ProjectStatusBar";
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, TrendingUp, Activity } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { API_URL, BASE_URL, ASSET_BASE_URL } from "../../../config";
import { setUiLang as setGlobalUiLang } from "../../../lib/uiLang";
import {
  getFullUrl,
  createInitialFrameTrimState,
  clampFrameTrimPercent,
  normalizeFrameTrimMargins,
  brokenMediaUrls,
  brokenSceneImageUrls,
  warmMediaUrls,
  shouldBypassBrokenMediaCache,
  rememberBrokenMediaUrl,
  isBrokenMediaUrl,
  rememberWarmMediaUrl,
  isWarmMediaUrl,
  getSafeMediaUrl,
  extractImageJobResultUrl,
  rememberBrokenSceneImageUrl,
  isBrokenSceneImageUrl,
  normalizeBatchParallelLimit,
  normalizeAsciiSubjectSeparatorsForDeps,
  normalizeSubjectNameForDeps,
  normalizeSubjectKeyForDeps,
  normalizeAsciiSubjectSeparators,
  normalizeSubjectName,
  normalizeSubjectKey,
  normalizeImportSubjectKey,
  IMG_PLACEHOLDER_SRC,
  parseVisualDependencies,
  SafeImage,
  SafeAudio,
  normalizeMediaRefList,
  areMediaRefListsEqual,
  collectMatchedEntitiesFromPrompt,
  collectMatchedEntityImageUrlsFromPrompt,
  SCENE_SUBJECT_TYPE_LABELS,
  getSceneSubjectStatusKey,
  splitSceneSubjectNames,
  normalizeSceneSubjectDefaultType,
  parseTypedSceneSubjectToken,
  extractSceneSubjectRefsFromField,
  buildSceneSubjectNameCandidates,
  extractSceneSubjectRefs,
  findMatchingEntityByType,
  findMissingSceneSubjectRefs,
  findCrossTypeEntityMatches,
  buildSceneSubjectPlaceholderPayload,
  createMissingSceneSubjectPlaceholders,
  collectMatchedSubjectImageUrlsFromPrompt,
  resolveUnifiedVideoMode,
  buildAutoVideoRefList,
  resolveShotVideoPosterUrl,
  LazyHoverVideo,
  InViewVideo,
  ManagedVideoPlayer,
  parseEpisodeNumberFromText,
  normalizeEpisodeTitleForDisplay,
  buildEntityNegativePrompt,
  normalizeImageSizeOption,
  normalizeAspectRatioOption,
  parseAspectRatioParts,
  parseAspectRatioValue,
  reduceAspectRatioParts,
  buildAspectRatioString,
  inferImageSizeFromResolution,
  getEpisodePreferredImageSize,
  getEpisodePreferredAspectRatio,
  getProjectPreferredImageSize,
  getProjectPreferredAspectRatio,
  buildShotDiptychPlan,
  getShotDiptychLayoutLabel,
  buildShotDiptychLayoutInstruction,
  buildShotDiptychAspectContract,
  getShotDiptychSeamTrimPx,
  getShotDiptychSeamBiasPx,
  getShotDiptychFallbackCropPx,
  JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION,
  SHOT_FRAME_ASSET_UPLOAD_VERSION,
  hashStableText,
  buildJointShotDiptychUploadIdempotencyKey,
  buildShotFrameAssetUploadIdempotencyKey,
  collectSupportedAspectRatioOptions,
  collectSupportedImageSizeOptions,
  selectBestShotDiptychRequestAspectRatio,
  selectBestSupportedImageSize,
  resolveShotPanelExportResolution,
  resolveShotDiptychRequestResolution,
  getResolutionByAspectAndImageSize,
  SHOT_IMAGE_CFG_MIN,
  SHOT_IMAGE_CFG_MAX,
  SHOT_IMAGE_CFG_STEP,
  SHOT_IMAGE_CFG_FALLBACK,
  clampShotImageCfg,
  resolveShotImageCfgDefault,
  extractDialogueOnlyFromPrompt,
  inferLanguageCodeFromProjectLanguage,
  buildVoicePromptWithEntityContext,
  buildEpisodeDisplayLabel,
  useTabMediaRefreshEffect,
  TabMediaRefreshButton
} from "../editorHelpers";
import { PROJECT_ASPECT_RATIO_OPTIONS } from "../projectOptionConfig";
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
  recomputeProjectCostEstimation
} from "../../../services/api";
import RefineControl from "../../../components/RefineControl.jsx";
import VideoStudio from "../../../components/VideoStudio";
import InputGroup from "./InputGroup";
import MarkdownCell from "./MarkdownCell";
import MarkdownHelpModal from "./MarkdownHelpModal";
import {
  PROVIDER_LABELS,
  MODEL_OPTIONS,
  getSettingSourceByCategory,
  formatProviderModelEndpointError
} from "../editorConfig";
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
  normalizeProjectEpisodeBasePositioning,
  normalizeProjectSceneAnalysisEra,
  normalizeProjectSceneAnalysisSafety,
  normalizeProjectEpisodeGlobalStyle,
  normalizeProjectEpisodeTone,
  normalizeProjectEpisodeLighting,
  normalizeProjectEpisodeQuality
} from "../projectOptionConfig";
import { processPrompt } from "../../../lib/promptUtils";
import { entityNameAppearsInText, entityTokenMatchesName, normalizeEntityToken } from "../../../lib/entityToken";
import SettingsPage from "../../Settings";
import { confirmUiMessage, promptUiMessage } from "../../../lib/uiMessage";
import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, DEFAULT_CANON_IDENTITY_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint, resolveProjectVideoSoundEnabled } from "../editorConstants";
const stripStackedProductionScriptTitleSuffixes = (title) => {
  const raw = String(title || "").trim();
  if (!raw) return "";
  const cleaned = raw.replace(/(?:·\s*实拍\s*（\s*真人剧[^·]*)+$/g, "").trim();
  return cleaned || raw;
};
export const ProjectOverview = ({ id, project: initialProject = null, onProjectUpdate, onRefreshEpisodes, onJumpToEpisode, onTabChange, episodes = [], uiLang = "en", mode = "overview", tabMediaRefreshSignal = 0, isTabActive = true, onMediaRefreshRequest = null }) => {
  const functionApiConfigs = useFunctionApis();
  const [selectedScriptAnalysisApiId, setSelectedScriptAnalysisApiId] = useState(() => {
    return Number(localStorage.getItem("func_api_script_analysis") || 0) || null;
  });
  useEffect(() => {
    const apiList = Array.isArray(functionApiConfigs?.script_analysis) ? functionApiConfigs.script_analysis : [];
    if (apiList.length <= 0) return;
    const currentId = Number(selectedScriptAnalysisApiId || 0);
    const hasCurrent = currentId > 0 && apiList.some((item) => Number(item?.system_api_id || 0) === currentId);
    if (hasCurrent) return;
    const storageId = Number(localStorage.getItem("func_api_script_analysis") || 0);
    const hasStorage = storageId > 0 && apiList.some((item) => Number(item?.system_api_id || 0) === storageId);
    const fallbackId = hasStorage ? storageId : Number((apiList.find((item) => !item?.is_fallback) || apiList[0])?.system_api_id || 0);
    if (fallbackId > 0) {
      setSelectedScriptAnalysisApiId(fallbackId);
      localStorage.setItem("func_api_script_analysis", String(fallbackId));
    }
  }, [functionApiConfigs?.script_analysis, selectedScriptAnalysisApiId]);
  useEffect(() => {
    const handleFunctionApiChanged = (event) => {
      if (String(event?.detail?.storageKey || "") !== "func_api_script_analysis") return;
      const nextId = Number(event?.detail?.value || 0) || null;
      setSelectedScriptAnalysisApiId(nextId);
    };
    window.addEventListener("aistory:function-api-changed", handleFunctionApiChanged);
    return () => window.removeEventListener("aistory:function-api-changed", handleFunctionApiChanged);
  }, []);
  const buildScriptAnalysisApiPayload = useCallback((payload = {}) => ({
    ...payload,
    function_name: "script_analysis",
    system_api_id: Number(selectedScriptAnalysisApiId || 0) || null
  }), [selectedScriptAnalysisApiId]);
  const t = useCallback((zh, en) => uiLang === "zh" ? zh : en, [uiLang]);
  const resolveProjectSeedFromInfo = (payload) => {
    const src = payload && typeof payload === "object" ? payload : {};
    const generation = src.generation && typeof src.generation === "object" ? src.generation : {};
    const candidate = src.generation_seed ?? src.seed ?? generation.seed ?? null;
    const parsed = Number(candidate);
    if (!Number.isFinite(parsed) || parsed <= 0) return "";
    return String(Math.trunc(parsed));
  };
  const [project, setProject] = useState(() => initialProject && String(initialProject.id) === String(id) ? initialProject : null);
  const { addLog } = useLog();
  const [info, setInfo] = useState({
    script_title: "",
    expected_duration: "",
    series_episode: "",
    base_positioning: "\u73B0\u4EE3\u804C\u573A / Modern Workplace",
    type: "\u5B9E\u62CD\uFF08\u771F\u4EBA\u5267/\u7535\u5F71\u611F8K\uFF09 / Live Action (Live-Action Drama/Cinematic 8K)",
    Global_Style: "",
    tech_params: {
      visual_standard: {
        horizontal_resolution: "720",
        vertical_resolution: "1280",
        frame_rate: "24",
        aspect_ratio: "9:16",
        quality: "\u8D85\u9AD8 / Ultra High",
        image_size: "2K",
        video_resolution: "720"
      }
    },
    tone: "",
    lighting: "",
    language: "\u82F1\u6587 / English",
    season_occurrence: "",
    video_sound: true,
    borrowed_films: [],
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
      logline: "",
      theme: "",
      core_conflict: "",
      background: "",
      characters: "",
      setup: "",
      development: "",
      turning_points: "",
      climax: "",
      resolution: "",
      suspense: "",
      foreshadowing: "",
      wild_creative_notes: "",
      extra_notes: ""
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
      extra_notes: ""
    },
    ...PROJECT_SCENE_ANALYSIS_DEFAULTS
  });
  const [isSceneAnalysisDimensionsCollapsed, setIsSceneAnalysisDimensionsCollapsed] = useState(true);
  const [globalStoryInput, setGlobalStoryInput] = useState({
    episodes_count: 30,
    episode_duration_minutes: 1,
    script_mode: "\u77ED\u5267\u5FEB\u8282\u594F / Short Drama",
    target_audience: "\u7537\u9891\u8DEF\u7EBF / Male-Oriented",
    logline: "",
    theme: "",
    core_conflict: "",
    background: "",
    characters: "",
    setup: "",
    development: "",
    turning_points: "",
    climax: "",
    resolution: "",
    suspense: "",
    foreshadowing: "",
    wild_creative_notes: "",
    extra_notes: ""
  });
  const [promoInput, setPromoInput] = useState({
    promo_type: "\u4F01\u4E1A\u5BA3\u4F20 / Corporate Promotion",
    episodes_count: 1,
    campaign_objective: "",
    target_audience: "",
    key_message: "",
    core_highlights: "",
    credibility_proof: "",
    hook_opening: "",
    conversion_cta: "",
    channel_context: "",
    constraints: ""
  });
  const [promoFrameworkViewMode, setPromoFrameworkViewMode] = useState("preview");
  const [storyFrameworkViewMode, setStoryFrameworkViewMode] = useState("preview");
  const [targetEpisodeNumberForGen, setTargetEpisodeNumberForGen] = useState("");
  const [hasSetDefaultEp, setHasSetDefaultEp] = useState(false);
  useEffect(() => {
    if (episodes) {
      let defaultEp = 1;
      if (episodes.length > 0) {
        const getEpNum = (e, i) => Number(e.episode_number) || parseEpisodeNumberFromText(e.title) || i + 1;
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
  }, [episodes, hasSetDefaultEp]);
  const [isGeneratingGlobalStory, setIsGeneratingGlobalStory] = useState(false);
  const [isStructuringCreativeInput, setIsStructuringCreativeInput] = useState(false);
  const [isFetchingMarketResearch, setIsFetchingMarketResearch] = useState(false);
  const [trendingDramasReport, setTrendingDramasReport] = useState(null);
  const [industryAnalysisReport, setIndustryAnalysisReport] = useState(null);
  const [marketIntelHistory, setMarketIntelHistory] = useState([]);
  const [selectedIndustryReportId, setSelectedIndustryReportId] = useState("");
  const [selectedTrendingReportId, setSelectedTrendingReportId] = useState("");
  const [isLoadingMarketIntelHistory, setIsLoadingMarketIntelHistory] = useState(false);
  const [isGeneratingEpisodeScripts, setIsGeneratingEpisodeScripts] = useState(false);
  const [isStoppingEpisodeScripts, setIsStoppingEpisodeScripts] = useState(false);
  const [episodeScriptsProgress, setEpisodeScriptsProgress] = useState(null);
  const [showEpisodeScriptsProgressModal, setShowEpisodeScriptsProgressModal] = useState(false);
  const [isAnalyzingNovel, setIsAnalyzingNovel] = useState(false);
  const [isImportingStoryPackage, setIsImportingStoryPackage] = useState(false);
  const [novelImportText, setNovelImportText] = useState("");
  const [showGlobalStoryGuide, setShowGlobalStoryGuide] = useState(false);
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [projectTab, setProjectTab] = useState(mode === "generator" ? "story_generator" : "overview");
  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    cost: true,
    management: false,
    tech: false,
    review: false
  });
  const toggleSection = (section) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
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
    phase: "idle",
    message: ""
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
    message_text: "",
    entity_decision: "pending",
    shot_decision: "pending",
    entity_feedback: "",
    shot_feedback: ""
  });
  const [quickReviewDraft, setQuickReviewDraft] = useState({
    reviewer_user: "",
    title: "",
    request_message: "",
    entity_required: true,
    shot_required: true
  });
  const [costEstimation, setCostEstimation] = useState(() => {
    const cached = initialProject?.global_info?.cost_estimation;
    return cached && typeof cached === "object" ? cached : null;
  });
  const [isCostLoading, setIsCostLoading] = useState(false);
  const [isCostRefreshing, setIsCostRefreshing] = useState(false);
  const [costError, setCostError] = useState("");
  const setGeneratorAutosaveState = useCallback((phase, message = "") => {
    if (autosaveFeedbackTimerRef.current) {
      clearTimeout(autosaveFeedbackTimerRef.current);
      autosaveFeedbackTimerRef.current = null;
    }
    setGeneratorAutosaveFeedback({ phase, message });
    if (phase === "saved") {
      autosaveFeedbackTimerRef.current = setTimeout(() => {
        setGeneratorAutosaveFeedback({ phase: "idle", message: "" });
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
    if (mode !== "generator") {
      setProjectTab("overview");
      return;
    }
    setProjectTab((prev) => {
      if (prev === "promo_generator") return "promo_generator";
      if (prev === "trending_dramas" || prev === "industry_analysis" || prev === "market_research") {
        return "story_generator";
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
      console.warn("Failed to load project review panel", reviewErr);
      setProjectReviewThreads([]);
    } finally {
      setIsReviewPanelLoading(false);
    }
  }, [id]);
  const loadProjectCost = useCallback(async ({ forceRecompute = false } = {}) => {
    if (!id || mode !== "overview") return null;
    if (forceRecompute) {
      setIsCostRefreshing(true);
    } else {
      setIsCostLoading(true);
    }
    setCostError("");
    try {
      const payload = forceRecompute ? await recomputeProjectCostEstimation(id) : await getProjectCostEstimation(id);
      const normalized = payload && typeof payload === "object" ? payload : null;
      setCostEstimation(normalized);
      return normalized;
    } catch (error) {
      console.warn("Failed to load project cost estimation", error);
      setCostError(error?.response?.data?.detail || error?.message || "Failed to load project cost estimation");
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
      console.warn("Failed to poll episode scripts status", error);
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
    if (!id || mode !== "generator") {
      if (episodeScriptsStatusTimerRef.current && !isGeneratingEpisodeScripts) {
        clearInterval(episodeScriptsStatusTimerRef.current);
        episodeScriptsStatusTimerRef.current = null;
      }
      return;
    }
    let cancelled = false;
    const hydrateEpisodeScriptsStatus = async () => {
      const status = await pollEpisodeScriptsStatus();
      if (cancelled || !status || typeof status !== "object") return;
      if (status.running) {
        setShowEpisodeScriptsProgressModal(true);
        if (!episodeScriptsStatusTimerRef.current) {
          episodeScriptsStatusTimerRef.current = setInterval(pollEpisodeScriptsStatus, 3e3);
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
    if (!id || mode !== "overview" || !expandedSections.review) return;
    loadProjectReviewPanel();
  }, [expandedSections.review, id, mode, loadProjectReviewPanel]);
  useEffect(() => {
    if (!id || mode !== "overview" || !expandedSections.review) return void 0;
    const refreshIfVisible = () => {
      if (document.visibilityState !== "visible") return;
      loadProjectReviewPanel();
    };
    const intervalId = window.setInterval(refreshIfVisible, 3e4);
    document.addEventListener("visibilitychange", refreshIfVisible);
    window.addEventListener("focus", refreshIfVisible);
    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", refreshIfVisible);
      window.removeEventListener("focus", refreshIfVisible);
    };
  }, [expandedSections.review, id, mode, loadProjectReviewPanel]);
  useEffect(() => {
    if (!expandedSections.review) return;
    fetchMe().then((user) => {
      setCurrentUserId(Number(user?.id || 0) || null);
    }).catch(() => {
      setCurrentUserId(null);
    });
  }, [expandedSections.review]);
  const quickReviewUnreadCount = useMemo(
    () => projectReviewThreads.filter((thread) => !!thread?.has_unread).length,
    [projectReviewThreads]
  );
  const handleCreateQuickProjectReview = async () => {
    if (!id) return;
    const reviewerUser = String(quickReviewDraft.reviewer_user || "").trim();
    if (!reviewerUser) {
      alert(t("\u8BF7\u5148\u8F93\u5165\u5BA1\u6838\u4EBA\u7528\u6237\u540D\u6216\u90AE\u7BB1\u3002", "Please enter reviewer username or email first."));
      return;
    }
    if (!quickReviewDraft.entity_required && !quickReviewDraft.shot_required) {
      alert(t("\u81F3\u5C11\u9700\u8981\u9009\u62E9\u8D44\u4EA7\u5BA1\u6838\u6216\u955C\u5934\u5BA1\u6838\u3002", "Please enable asset review or shot review."));
      return;
    }
    setIsReviewPanelSubmitting(true);
    try {
      await createProjectReviewThread(id, {
        reviewer_user: reviewerUser,
        title: quickReviewDraft.title,
        request_message: quickReviewDraft.request_message,
        scope_type: "all_current",
        entity_required: !!quickReviewDraft.entity_required,
        shot_required: !!quickReviewDraft.shot_required
      });
      setQuickReviewDraft({
        reviewer_user: "",
        title: "",
        request_message: "",
        entity_required: true,
        shot_required: true
      });
      await loadProjectReviewPanel();
      alert(t("\u5BA1\u6838\u8BF7\u6C42\u5DF2\u53D1\u8D77\u3002", "Review request created."));
    } catch (err) {
      console.error("Failed to create quick project review", err);
      alert(err?.response?.data?.detail || t("\u53D1\u8D77\u5BA1\u6838\u5931\u8D25\u3002", "Failed to create review request."));
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
        message_text: "",
        entity_decision: "pending",
        shot_decision: "pending",
        entity_feedback: "",
        shot_feedback: ""
      });
      await loadProjectReviewPanel();
    } catch (err) {
      console.error("Failed to load quick review thread detail", err);
      alert(err?.response?.data?.detail || t("\u52A0\u8F7D\u5BA1\u6838\u8BE6\u60C5\u5931\u8D25\u3002", "Failed to load review details."));
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
      console.error("Failed to load quick review round messages", err);
      alert(err?.response?.data?.detail || t("\u52A0\u8F7D\u8F6E\u6B21\u6D88\u606F\u5931\u8D25\u3002", "Failed to load round messages."));
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
      message_type: "message"
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
      alert(t("\u5BA1\u6838\u56DE\u590D\u5DF2\u53D1\u9001\u3002", "Review reply sent."));
    } catch (err) {
      console.error("Failed to create quick review reply", err);
      alert(err?.response?.data?.detail || t("\u53D1\u9001\u5BA1\u6838\u56DE\u590D\u5931\u8D25\u3002", "Failed to send review reply."));
    } finally {
      setIsReviewPanelSubmitting(false);
    }
  };
  const [canonName, setCanonName] = useState("");
  const [canonIdentityCategories, setCanonIdentityCategories] = useState(DEFAULT_CANON_IDENTITY_CATEGORIES);
  const [canonSelectedIdentityIds, setCanonSelectedIdentityIds] = useState([]);
  const [canonCustomIdentity, setCanonCustomIdentity] = useState("");
  const [canonBody, setCanonBody] = useState("");
  const [canonExtra, setCanonExtra] = useState("");
  const [canonCustomTags, setCanonCustomTags] = useState("");
  const [canonTagCategories, setCanonTagCategories] = useState(DEFAULT_CANON_TAG_CATEGORIES);
  const [canonTagEditMode, setCanonTagEditMode] = useState(false);
  const [canonSelectedTagIds, setCanonSelectedTagIds] = useState([]);
  const [isGeneratingCanon, setIsGeneratingCanon] = useState(false);
  const [showCanonModal, setShowCanonModal] = useState(false);
  const renderCanonMarkdownFromProfiles = (profiles) => {
    const items = Array.isArray(profiles) ? profiles : [];
    const blocks = [];
    for (const it of items) {
      if (!it || typeof it !== "object") continue;
      const nm = String(it.name || "").trim();
      if (!nm) continue;
      const md = String(it.description_md || "").trim();
      if (md) {
        blocks.push(md);
      } else {
        blocks.push(`### ${nm} (Canonical)
- Identity: ${it.identity || ""}
`);
      }
    }
    return blocks.join("\n\n").trim();
  };
  const handleDeleteCanonCharacter = async (characterName) => {
    const name = String(characterName || "").trim();
    if (!id || !name) return;
    const ok = await confirmUiMessage(`Delete "${name}" from Character Canon? You can re-generate it later.`);
    if (!ok) return;
    try {
      const current = Array.isArray(info.character_profiles) ? info.character_profiles : [];
      const nextProfiles = current.filter((p) => p && typeof p === "object" ? String(p.name || "").trim() !== name : true);
      await updateProjectCharacterProfiles(id, nextProfiles);
      setInfo((prev) => {
        const merged = { ...prev };
        merged.character_profiles = nextProfiles;
        merged.character_canon_md = renderCanonMarkdownFromProfiles(nextProfiles);
        return merged;
      });
    } catch (e) {
      console.error("[Character Canon] Delete failed:", e);
      alert(`Delete failed: ${e?.message || "Unknown error"}`);
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
      const DEPRECATED_CANON_CATEGORY_KEYS = /* @__PURE__ */ new Set(["combat"]);
      const LEGACY_SEXY_OPTION_IDS = /* @__PURE__ */ new Set([
        "sexy_1",
        "sexy_2",
        "sexy_3",
        "sexy_4",
        "sexy_m1",
        "sexy_m2"
      ]);
      const mergeCategoriesByKey = (savedCats, defaultCats) => {
        const byKey = /* @__PURE__ */ new Map();
        for (const c of savedCats || []) {
          if (!c?.key) continue;
          if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
          byKey.set(c.key, c);
        }
        const mergeOne = (savedCat, defCat) => {
          if (!savedCat) return defCat;
          const categoryKey = savedCat.key || defCat?.key;
          let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
          if (categoryKey === "sexy") {
            savedOptions = savedOptions.filter((o) => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
          }
          const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
          const seenIds = new Set(savedOptions.map((o) => o?.id).filter(Boolean));
          const mergedOptions = [...savedOptions];
          for (const opt of defOptions) {
            if (!opt?.id) continue;
            if (!seenIds.has(opt.id)) mergedOptions.push(opt);
          }
          return {
            ...savedCat,
            key: savedCat.key || defCat?.key,
            title: savedCat.title || defCat?.title,
            options: mergedOptions
          };
        };
        const merged = [];
        for (const def of defaultCats || []) {
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
  }, []);
  const toggleCanonTagId = (tagId) => {
    setCanonSelectedTagIds((prev) => prev.includes(tagId) ? prev.filter((t2) => t2 !== tagId) : [...prev, tagId]);
  };
  const toggleCanonIdentityId = (identityId) => {
    setCanonSelectedIdentityIds((prev) => prev.includes(identityId) ? prev.filter((t2) => t2 !== identityId) : [...prev, identityId]);
  };
  const canonSelectedTagStrings = () => {
    const selected = [];
    for (const cat of canonTagCategories || []) {
      for (const opt of cat.options || []) {
        if (canonSelectedTagIds.includes(opt.id)) {
          selected.push(canonOptionValue(opt));
        }
      }
    }
    return selected;
  };
  const canonSelectedIdentityStrings = () => {
    const selected = [];
    for (const cat of canonIdentityCategories || []) {
      for (const opt of cat.options || []) {
        if (canonSelectedIdentityIds.includes(opt.id)) {
          selected.push(canonOptionValue(opt));
        }
      }
    }
    return selected;
  };
  const newCanonOptionId = (prefix2 = "opt") => `${prefix2}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const updateCanonCategoryTitle = (catKey, title) => {
    setCanonTagCategories((prev) => (prev || []).map((c) => c.key === catKey ? { ...c, title } : c));
  };
  const updateCanonOption = (catKey, optId, patch) => {
    setCanonTagCategories((prev) => (prev || []).map((c) => {
      if (c.key !== catKey) return c;
      return {
        ...c,
        options: (c.options || []).map((o) => o.id === optId ? { ...o, ...patch } : o)
      };
    }));
  };
  const addCanonOption = (catKey) => {
    const newId = newCanonOptionId(catKey);
    setCanonTagCategories((prev) => (prev || []).map((c) => {
      if (c.key !== catKey) return c;
      return { ...c, options: [...c.options || [], { id: newId, label: "\u65B0\u6807\u7B7E", detail: "\u7EC6\u8282\u63CF\u8FF0" }] };
    }));
  };
  const removeCanonOption = (catKey, optId) => {
    setCanonSelectedTagIds((prev) => prev.filter((id2) => id2 !== optId));
    setCanonTagCategories((prev) => (prev || []).map((c) => {
      if (c.key !== catKey) return c;
      return { ...c, options: (c.options || []).filter((o) => o.id !== optId) };
    }));
  };
  const updateIdentityCategoryTitle = (catKey, title) => {
    setCanonIdentityCategories((prev) => (prev || []).map((c) => c.key === catKey ? { ...c, title } : c));
  };
  const updateIdentityOption = (catKey, optId, patch) => {
    setCanonIdentityCategories((prev) => (prev || []).map((c) => {
      if (c.key !== catKey) return c;
      return {
        ...c,
        options: (c.options || []).map((o) => o.id === optId ? { ...o, ...patch } : o)
      };
    }));
  };
  const addIdentityOption = (catKey) => {
    const newId = newCanonOptionId(catKey);
    setCanonIdentityCategories((prev) => (prev || []).map((c) => {
      if (c.key !== catKey) return c;
      return { ...c, options: [...c.options || [], { id: newId, label: "\u65B0\u8EAB\u4EFD", detail: "\u7EC6\u8282\u63CF\u8FF0" }] };
    }));
  };
  const removeIdentityOption = (catKey, optId) => {
    setCanonSelectedIdentityIds((prev) => prev.filter((id2) => id2 !== optId));
    setCanonIdentityCategories((prev) => (prev || []).map((c) => {
      if (c.key !== catKey) return c;
      return { ...c, options: (c.options || []).filter((o) => o.id !== optId) };
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
              if (field === "type") return t("\u7C7B\u578B", "Type");
              if (field === "country_region") return t("\u56FD\u5BB6\u5730\u57DF", "Country/Region");
              if (field === "language") return t("\u8BED\u8A00", "Language");
              return String(field || "");
            }).filter(Boolean).join(" / ");
            await confirmUiMessage(
              `${t("\u9879\u76EE\u57FA\u672C\u4FE1\u606F\u7F3A\u5931\uFF0C\u8BF7\u5148\u8BBE\u7F6E\uFF1A", "Project basic info is missing, please set: ")}${labels}
${t("\u5C06\u4E3A\u4F60\u81EA\u52A8\u8DF3\u8F6C\u5230\u9879\u76EE\u6982\u89C8\u9875\u3002", "You will be redirected to Project Overview.")}`
            );
            setProjectTab("overview");
            if (onTabChange) onTabChange("overview");
            try {
              window.scrollTo({ top: 0, behavior: "smooth" });
            } catch {
            }
          }
        } catch (healthErr) {
          console.warn("Project health reminder failed:", healthErr);
        }
        if (data.global_info) {
          const merged = {
            ...info,
            ...data.global_info,
            tech_params: {
              visual_standard: {
                ...info.tech_params.visual_standard,
                ...data.global_info.tech_params?.visual_standard || {}
              }
            }
          };
          if (!merged.script_title || String(merged.script_title).trim().length === 0) {
            if (data?.title && String(data.title).trim().length > 0) {
              merged.script_title = String(data.title).trim();
            }
          }
          merged.script_title = stripStackedProductionScriptTitleSuffixes(merged.script_title);
          merged.type = normalizeProjectEpisodeType(merged.type);
          merged.language = normalizeProjectEpisodeLanguage(merged.language);
          merged.base_positioning = normalizeProjectEpisodeBasePositioning(merged.base_positioning);
          merged.era = normalizeProjectSceneAnalysisEra(merged.era);
          merged.broadcast_safety_level = normalizeProjectSceneAnalysisSafety(merged.broadcast_safety_level);
          merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
          merged.tone = normalizeProjectEpisodeTone(merged.tone);
          merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
          merged.video_sound = resolveProjectVideoSoundEnabled(merged);
          merged.generation_seed = resolveProjectSeedFromInfo(merged);
          merged.project_share_users = normalizeUserListValues(merged.project_share_users);
          merged.project_reviewer_users = normalizeUserListValues(merged.project_reviewer_users);
          if (merged.tech_params?.visual_standard) {
            merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
          }
          setInfo(merged);
          if (merged.story_generator_global_input && typeof merged.story_generator_global_input === "object") {
            setGlobalStoryInput((prev) => ({
              ...prev,
              ...merged.story_generator_global_input,
              episode_duration_minutes: Number(merged.story_generator_global_input.episode_duration_minutes) > 0 ? Number(merged.story_generator_global_input.episode_duration_minutes) : 1
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
                search_meta: legacy.search_meta
              });
            }
          }
          if (merged.promo_generator_input && typeof merged.promo_generator_input === "object") {
            setPromoInput((prev) => ({
              ...prev,
              ...merged.promo_generator_input
            }));
          }
          skipNextGlobalStoryAutosaveRef.current = true;
          skipNextPromoAutosaveRef.current = true;
          skipNextGeneratorResultAutosaveRef.current = true;
          const canonDraft = merged.character_canon_input;
          if (canonDraft && typeof canonDraft === "object") {
            if (typeof canonDraft.name === "string") setCanonName(canonDraft.name);
            if (Array.isArray(canonDraft.selected_identity_ids)) setCanonSelectedIdentityIds(canonDraft.selected_identity_ids);
            if (Array.isArray(canonDraft.selected_tag_ids)) setCanonSelectedTagIds(canonDraft.selected_tag_ids);
            if (typeof canonDraft.custom_identity === "string") setCanonCustomIdentity(canonDraft.custom_identity);
            if (typeof canonDraft.body_features === "string") setCanonBody(canonDraft.body_features);
            if (typeof canonDraft.custom_style_tags === "string") setCanonCustomTags(canonDraft.custom_style_tags);
            if (typeof canonDraft.extra_notes === "string") setCanonExtra(canonDraft.extra_notes);
          }
          if (merged.character_canon_tag_categories) {
            const normalized = normalizeCanonTagCategories(merged.character_canon_tag_categories);
            if (normalized) {
              const DEPRECATED_CANON_CATEGORY_KEYS = /* @__PURE__ */ new Set(["combat"]);
              const LEGACY_SEXY_OPTION_IDS = /* @__PURE__ */ new Set([
                "sexy_1",
                "sexy_2",
                "sexy_3",
                "sexy_4",
                "sexy_m1",
                "sexy_m2"
              ]);
              const mergeCategoriesByKey = (savedCats, defaultCats) => {
                const byKey = /* @__PURE__ */ new Map();
                for (const c of savedCats || []) {
                  if (!c?.key) continue;
                  if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                  byKey.set(c.key, c);
                }
                const mergeOne = (savedCat, defCat) => {
                  if (!savedCat) return defCat;
                  const categoryKey = savedCat.key || defCat?.key;
                  let savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                  if (categoryKey === "sexy") {
                    savedOptions = savedOptions.filter((o) => o?.id && !LEGACY_SEXY_OPTION_IDS.has(o.id));
                  }
                  const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                  const seenIds = new Set(savedOptions.map((o) => o?.id).filter(Boolean));
                  const mergedOptions = [...savedOptions];
                  for (const opt of defOptions) {
                    if (!opt?.id) continue;
                    if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                  }
                  return {
                    ...savedCat,
                    key: savedCat.key || defCat?.key,
                    title: savedCat.title || defCat?.title,
                    options: mergedOptions
                  };
                };
                const mergedCats2 = [];
                for (const def of defaultCats || []) {
                  const saved = byKey.get(def.key);
                  mergedCats2.push(mergeOne(saved, def));
                  byKey.delete(def.key);
                }
                for (const rest of byKey.values()) {
                  if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                  mergedCats2.push(rest);
                }
                return mergedCats2;
              };
              const mergedCats = mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES);
              setCanonTagCategories(mergedCats);
              try {
                localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(mergedCats));
              } catch {
              }
            }
          }
          if (merged.character_canon_identity_categories) {
            const normalized = normalizeCanonTagCategories(merged.character_canon_identity_categories);
            if (normalized) {
              const DEPRECATED_CANON_CATEGORY_KEYS = /* @__PURE__ */ new Set(["combat"]);
              const mergeCategoriesByKey = (savedCats, defaultCats) => {
                const byKey = /* @__PURE__ */ new Map();
                for (const c of savedCats || []) {
                  if (!c?.key) continue;
                  if (DEPRECATED_CANON_CATEGORY_KEYS.has(c.key)) continue;
                  byKey.set(c.key, c);
                }
                const mergeOne = (savedCat, defCat) => {
                  if (!savedCat) return defCat;
                  const savedOptions = Array.isArray(savedCat.options) ? savedCat.options : [];
                  const defOptions = Array.isArray(defCat?.options) ? defCat.options : [];
                  const seenIds = new Set(savedOptions.map((o) => o?.id).filter(Boolean));
                  const mergedOptions = [...savedOptions];
                  for (const opt of defOptions) {
                    if (!opt?.id) continue;
                    if (!seenIds.has(opt.id)) mergedOptions.push(opt);
                  }
                  return {
                    ...savedCat,
                    key: savedCat.key || defCat?.key,
                    title: savedCat.title || defCat?.title,
                    options: mergedOptions
                  };
                };
                const mergedCats2 = [];
                for (const def of defaultCats || []) {
                  const saved = byKey.get(def.key);
                  mergedCats2.push(mergeOne(saved, def));
                  byKey.delete(def.key);
                }
                for (const rest of byKey.values()) {
                  if (rest?.key && DEPRECATED_CANON_CATEGORY_KEYS.has(rest.key)) continue;
                  mergedCats2.push(rest);
                }
                return mergedCats2;
              };
              const mergedCats = mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES);
              setCanonIdentityCategories(mergedCats);
              try {
                localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(mergedCats));
              } catch {
              }
            }
          }
          skipNextCanonAutosaveRef.current = true;
          skipNextCanonCategoriesAutosaveRef.current = true;
        }
        if (data?.global_info?.cost_estimation && typeof data.global_info.cost_estimation === "object") {
          setCostEstimation(data.global_info.cost_estimation);
        }
      } catch (e) {
        console.error("Failed to load project", e);
      }
    };
    load();
  }, [id, t]);
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
          identity_categories: normalizedIdentity
        });
        try {
          localStorage.setItem(CANON_TAG_STORAGE_KEY, JSON.stringify(normalizedTags));
        } catch {
        }
        try {
          localStorage.setItem(CANON_IDENTITY_STORAGE_KEY, JSON.stringify(normalizedIdentity));
        } catch {
        }
      } catch (e) {
        console.error("[Character Canon Categories] Auto-save failed:", e);
      }
    }, 800);
    return () => {
      if (canonCategoriesAutosaveTimerRef.current) {
        clearTimeout(canonCategoriesAutosaveTimerRef.current);
      }
    };
  }, [id, canonTagEditMode, canonTagCategories, canonIdentityCategories]);
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
          name: canonName || "",
          selected_tag_ids: Array.isArray(canonSelectedTagIds) ? canonSelectedTagIds : [],
          selected_identity_ids: Array.isArray(canonSelectedIdentityIds) ? canonSelectedIdentityIds : [],
          custom_identity: canonCustomIdentity || "",
          body_features: canonBody || "",
          custom_style_tags: canonCustomTags || "",
          extra_notes: canonExtra || ""
        };
        await saveProjectCharacterCanonInput(id, payload);
      } catch (e) {
        console.error("[Character Canon] Auto-save failed:", e);
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
    canonExtra
  ]);
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
      setGeneratorAutosaveState("saving", t("\u81EA\u52A8\u4FDD\u5B58\u4E2D...", "Auto-saving..."));
      try {
        const payload = {
          mode: "global",
          generator_kind: "story",
          episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
          episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1,
          script_mode: globalStoryInput.script_mode,
          target_audience: globalStoryInput.target_audience,
          logline: globalStoryInput.logline,
          theme: globalStoryInput.theme,
          core_conflict: globalStoryInput.core_conflict,
          background: globalStoryInput.background,
          characters: globalStoryInput.characters,
          setup: globalStoryInput.setup,
          development: globalStoryInput.development,
          turning_points: globalStoryInput.turning_points,
          climax: globalStoryInput.climax,
          resolution: globalStoryInput.resolution,
          suspense: globalStoryInput.suspense,
          foreshadowing: globalStoryInput.foreshadowing,
          wild_creative_notes: globalStoryInput.wild_creative_notes,
          extra_notes: globalStoryInput.extra_notes
        };
        await saveProjectStoryGeneratorGlobalInput(id, payload);
        setGeneratorAutosaveState("saved", t("\u6545\u4E8B\u8F93\u5165\u5DF2\u81EA\u52A8\u4FDD\u5B58", "Story input auto-saved"));
      } catch (e) {
        console.error("[Global Story Generator] Auto-save failed:", e);
        setGeneratorAutosaveState("error", t("\u81EA\u52A8\u4FDD\u5B58\u5931\u8D25", "Auto-save failed"));
      }
    }, 800);
    return () => {
      if (globalStoryAutosaveTimerRef.current) {
        clearTimeout(globalStoryAutosaveTimerRef.current);
      }
    };
  }, [id, globalStoryInput, isGeneratingGlobalStory, setGeneratorAutosaveState, t]);
  useEffect(() => {
    if (!id) return;
    if (mode !== "generator" || projectTab !== "promo_generator") return;
    if (isGeneratingGlobalStory) return;
    if (skipNextPromoAutosaveRef.current) {
      skipNextPromoAutosaveRef.current = false;
      return;
    }
    if (promoAutosaveTimerRef.current) {
      clearTimeout(promoAutosaveTimerRef.current);
    }
    promoAutosaveTimerRef.current = setTimeout(async () => {
      setGeneratorAutosaveState("saving", t("\u81EA\u52A8\u4FDD\u5B58\u4E2D...", "Auto-saving..."));
      try {
        const payload = {
          mode: "global",
          generator_kind: "promo",
          promo_type: promoInput.promo_type,
          episodes_count: Number(promoInput.episodes_count || 0) || 0,
          campaign_objective: promoInput.campaign_objective || "",
          target_audience: promoInput.target_audience || "",
          key_message: promoInput.key_message || "",
          core_highlights: promoInput.core_highlights || "",
          credibility_proof: promoInput.credibility_proof || "",
          hook_opening: promoInput.hook_opening || "",
          conversion_cta: promoInput.conversion_cta || "",
          channel_context: promoInput.channel_context || "",
          constraints: promoInput.constraints || ""
        };
        await saveProjectStoryGeneratorGlobalInput(id, payload);
        setGeneratorAutosaveState("saved", t("\u5BA3\u4F20\u8F93\u5165\u5DF2\u81EA\u52A8\u4FDD\u5B58", "Promo input auto-saved"));
      } catch (e) {
        console.error("[Promo Generator] Auto-save failed:", e);
        setGeneratorAutosaveState("error", t("\u81EA\u52A8\u4FDD\u5B58\u5931\u8D25", "Auto-save failed"));
      }
    }, 800);
    return () => {
      if (promoAutosaveTimerRef.current) {
        clearTimeout(promoAutosaveTimerRef.current);
      }
    };
  }, [id, mode, projectTab, promoInput, isGeneratingGlobalStory, setGeneratorAutosaveState, t]);
  useEffect(() => {
    if (!id) return;
    if (mode !== "generator") return;
    if (isGeneratingGlobalStory) return;
    if (skipNextGeneratorResultAutosaveRef.current) {
      skipNextGeneratorResultAutosaveRef.current = false;
      return;
    }
    if (generatorResultAutosaveTimerRef.current) {
      clearTimeout(generatorResultAutosaveTimerRef.current);
    }
    generatorResultAutosaveTimerRef.current = setTimeout(async () => {
      setGeneratorAutosaveState("saving", t("\u81EA\u52A8\u4FDD\u5B58\u4E2D...", "Auto-saving..."));
      try {
        const baseGlobalInfo = project?.global_info && typeof project.global_info === "object" ? project.global_info : {};
        const global_info = {
          ...baseGlobalInfo,
          story_dna_global_md: info.story_dna_global_md || "",
          promo_dna_global_md: info.promo_dna_global_md || "",
          character_relationships: info.character_relationships || ""
        };
        await updateProject(id, { global_info });
        setGeneratorAutosaveState("saved", t("\u751F\u6210\u7ED3\u679C\u5DF2\u81EA\u52A8\u4FDD\u5B58", "Generated content auto-saved"));
      } catch (e) {
        console.error("[Generator Result] Auto-save failed:", e);
        setGeneratorAutosaveState("error", t("\u81EA\u52A8\u4FDD\u5B58\u5931\u8D25", "Auto-save failed"));
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
    t
  ]);
  const handleSave = async () => {
    try {
      const resolvedVideoSound = resolveProjectVideoSoundEnabled(info);
      const seedParsed = Number(info.generation_seed);
      const resolvedSeed = Number.isFinite(seedParsed) && seedParsed > 0 ? Math.trunc(seedParsed) : null;
      const global_info = {
        ...info,
        script_title: stripStackedProductionScriptTitleSuffixes(info.script_title),
        project_share_users: normalizeUserListValues(info.project_share_users),
        project_reviewer_users: normalizeUserListValues(info.project_reviewer_users),
        video_sound: resolvedVideoSound,
        project_generation_defaults: {
          ...info.project_generation_defaults || {},
          sound: resolvedVideoSound,
          video_resolution: normalizeProjectVideoResolution(
            info.tech_params?.visual_standard?.video_resolution || info.project_generation_defaults?.video_resolution
          ) || "720"
        },
        tech_params: {
          ...info.tech_params || {},
          visual_standard: {
            ...info.tech_params?.visual_standard || {},
            sound: resolvedVideoSound,
            video_resolution: normalizeProjectVideoResolution(
              info.tech_params?.visual_standard?.video_resolution || info.project_generation_defaults?.video_resolution
            ) || "720"
          }
        },
        story_generator_global_input: {
          ...globalStoryInput,
          episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
          episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1
        },
        promo_generator_input: {
          ...promoInput,
          episodes_count: Number(promoInput.episodes_count || 0) || 0
        },
        character_canon_input: {
          name: canonName || "",
          selected_tag_ids: Array.isArray(canonSelectedTagIds) ? canonSelectedTagIds : [],
          selected_identity_ids: Array.isArray(canonSelectedIdentityIds) ? canonSelectedIdentityIds : [],
          custom_identity: canonCustomIdentity || "",
          body_features: canonBody || "",
          custom_style_tags: canonCustomTags || "",
          extra_notes: canonExtra || ""
        }
      };
      if (resolvedSeed !== null) {
        global_info.generation_seed = resolvedSeed;
      }
      await updateProject(id, {
        global_info,
        share_users: global_info.project_share_users,
        reviewer_users: global_info.project_reviewer_users
      });
      await loadProjectCost({ forceRecompute: true });
      alert("Project info saved!");
      if (onProjectUpdate) onProjectUpdate();
    } catch (e) {
      console.error("Failed to save", e);
      alert(`Failed to save: ${e?.message || "Unknown error"}`);
    }
  };
  const handleGeneratePromoFramework = async () => {
    if (globalStoryGenerationInFlightRef.current || isGeneratingGlobalStory) return;
    globalStoryGenerationInFlightRef.current = true;
    setIsGeneratingGlobalStory(true);
    try {
      const episodesCount = Number(promoInput.episodes_count || 0) || 0;
      if (episodesCount <= 0) {
        alert("Please set a valid Episodes Count for Promo Generator.");
        return;
      }
      const payload = {
        mode: "global",
        generator_kind: "promo",
        episodes_count: episodesCount,
        script_title: info.script_title,
        expected_duration: info.expected_duration,
        type: promoInput.promo_type || info.type,
        language: info.language,
        base_positioning: info.base_positioning,
        Global_Style: info.Global_Style,
        background: [
          `Campaign Objective: ${promoInput.campaign_objective || ""}`,
          `Target Audience: ${promoInput.target_audience || ""}`,
          `Channel Context: ${promoInput.channel_context || ""}`
        ].join("\n"),
        setup: [
          `Hook Opening: ${promoInput.hook_opening || ""}`,
          `Core Message: ${promoInput.key_message || ""}`
        ].join("\n"),
        development: [
          `Core Highlights: ${promoInput.core_highlights || ""}`,
          `Credibility Proof: ${promoInput.credibility_proof || ""}`
        ].join("\n"),
        turning_points: `Differentiation & Persuasion Pivot: ${promoInput.key_message || ""}`,
        climax: `Flagship Demonstration / Emotional Peak: ${promoInput.core_highlights || ""}`,
        resolution: `Conversion CTA: ${promoInput.conversion_cta || ""}`,
        suspense: `Retention Hook for Next Episode / Segment: ${promoInput.conversion_cta || ""}`,
        foreshadowing: `Brand/Message anchors to repeat: ${promoInput.key_message || ""}`,
        extra_notes: [
          `Promo Type: ${promoInput.promo_type || ""}`,
          `Constraints: ${promoInput.constraints || ""}`
        ].join("\n")
      };
      const updated = await generateProjectStoryGlobal(id, buildScriptAnalysisApiPayload(payload));
      setProject(updated);
      const responseGlobalInfo = updated?.global_info && typeof updated.global_info === "object" ? updated.global_info : {};
      const returnedMarkdown = String(
        responseGlobalInfo.promo_dna_global_md || responseGlobalInfo.story_dna_global_md || updated?.promo_dna_global_md || updated?.story_dna_global_md || ""
      );
      setInfo((prev) => {
        const merged = {
          ...prev,
          ...responseGlobalInfo,
          promo_dna_global_md: returnedMarkdown || prev.promo_dna_global_md || "",
          promo_generator_input: {
            ...promoInput,
            episodes_count: episodesCount
          },
          tech_params: {
            visual_standard: {
              ...prev?.tech_params?.visual_standard || {},
              ...responseGlobalInfo.tech_params?.visual_standard || {}
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
      setGlobalStoryInput((prev) => ({
        ...prev,
        episodes_count: episodesCount
      }));
      setPromoFrameworkViewMode("preview");
      await updateProject(id, {
        global_info: {
          ...updated?.global_info || info || {},
          promo_generator_input: {
            ...promoInput,
            episodes_count: episodesCount
          }
        }
      });
      alert("Promo framework generated and saved. You can now generate episode scripts.");
    } catch (e) {
      console.error(e);
      const readable = formatProviderModelEndpointError(e);
      alert(`Failed to generate promo framework:
${readable}`);
    } finally {
      setIsGeneratingGlobalStory(false);
      globalStoryGenerationInFlightRef.current = false;
    }
  };
  const persistStoryGeneratorInputPatch = async (patch = {}) => {
    await saveProjectStoryGeneratorGlobalInput(id, {
      mode: "global",
      generator_kind: "story",
      episodes_count: Number(globalStoryInput.episodes_count || 0) || 0,
      episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1,
      script_mode: globalStoryInput.script_mode,
      target_audience: globalStoryInput.target_audience,
      logline: globalStoryInput.logline,
      theme: globalStoryInput.theme,
      core_conflict: globalStoryInput.core_conflict,
      background: globalStoryInput.background,
      characters: globalStoryInput.characters,
      setup: globalStoryInput.setup,
      development: globalStoryInput.development,
      turning_points: globalStoryInput.turning_points,
      climax: globalStoryInput.climax,
      resolution: globalStoryInput.resolution,
      suspense: globalStoryInput.suspense,
      foreshadowing: globalStoryInput.foreshadowing,
      wild_creative_notes: globalStoryInput.wild_creative_notes,
      extra_notes: globalStoryInput.extra_notes,
      trending_ai_short_dramas_report: trendingDramasReport,
      ai_short_drama_industry_report: industryAnalysisReport,
      ...patch
    });
  };
  const loadMarketIntelHistory = useCallback(async () => {
    if (!id) return [];
    setIsLoadingMarketIntelHistory(true);
    try {
      const data = await listMarketIntelReports(id, { limit: 100 });
      const items = Array.isArray(data?.items) ? data.items : [];
      setMarketIntelHistory(items);
      const industryItems = items.filter((item) => item.report_kind === "industry_analysis");
      const trendingItems = items.filter((item) => item.report_kind === "trending_dramas");
      const pickLatestId = (list, currentId) => {
        if (currentId && list.some((item) => String(item.id) === String(currentId))) {
          return String(currentId);
        }
        return list[0]?.id ? String(list[0].id) : "";
      };
      setSelectedIndustryReportId((prev) => pickLatestId(industryItems, prev));
      setSelectedTrendingReportId((prev) => pickLatestId(trendingItems, prev));
      return items;
    } catch (err) {
      console.warn("[Market Research] load history failed:", err);
      setMarketIntelHistory([]);
      return [];
    } finally {
      setIsLoadingMarketIntelHistory(false);
    }
  }, [id]);
  const handleSelectMarketIntelReport = useCallback(async (reportId, kind) => {
    const nextId = String(reportId || "").trim();
    if (!id || !nextId) return;
    if (kind === "industry_analysis") setSelectedIndustryReportId(nextId);
    if (kind === "trending_dramas") setSelectedTrendingReportId(nextId);
    try {
      const report = await getMarketIntelReport(id, nextId);
      if (kind === "industry_analysis") {
        setIndustryAnalysisReport(report);
      } else if (kind === "trending_dramas") {
        setTrendingDramasReport(report);
      }
    } catch (err) {
      console.warn("[Market Research] load report failed:", err);
      alert(`${t("\u52A0\u8F7D\u5386\u53F2\u62A5\u544A\u5931\u8D25", "Failed to load historical report")}: ${formatProviderModelEndpointError(err)}`);
    }
  }, [id, t]);
  useEffect(() => {
    if (mode !== "market_research" || !id) return;
    let cancelled = false;
    (async () => {
      const items = await loadMarketIntelHistory();
      if (cancelled) return;
      const industryLatest = items.find((item) => item.report_kind === "industry_analysis");
      const trendingLatest = items.find((item) => item.report_kind === "trending_dramas");
      if (industryLatest?.id && !industryAnalysisReport?.markdown) {
        try {
          const report = await getMarketIntelReport(id, industryLatest.id);
          if (!cancelled) {
            setIndustryAnalysisReport(report);
            setSelectedIndustryReportId(String(industryLatest.id));
          }
        } catch (e) {
        }
      }
      if (trendingLatest?.id && !trendingDramasReport?.markdown) {
        try {
          const report = await getMarketIntelReport(id, trendingLatest.id);
          if (!cancelled) {
            setTrendingDramasReport(report);
            setSelectedTrendingReportId(String(trendingLatest.id));
          }
        } catch (e) {
        }
      }
    })();
    return () => {
      cancelled = true;
    };
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
        fetchTrendingAiShortDramas(id, { ...payload, limit: 12 })
      ]);
      if (industryResult.status === "fulfilled") {
        industryReport = industryResult.value;
        setIndustryAnalysisReport(industryReport);
        if (industryReport?.id) setSelectedIndustryReportId(String(industryReport.id));
        setGlobalStoryInput((prev) => ({
          ...prev,
          ai_short_drama_industry_report: industryReport
        }));
      } else {
        console.error(industryResult.reason);
        errors.push(`${t("\u884C\u4E1A\u5206\u6790", "Industry analysis")}: ${formatProviderModelEndpointError(industryResult.reason)}`);
      }
      if (trendingResult.status === "fulfilled") {
        trendingReport = trendingResult.value;
        setTrendingDramasReport(trendingReport);
        if (trendingReport?.id) setSelectedTrendingReportId(String(trendingReport.id));
        setGlobalStoryInput((prev) => ({
          ...prev,
          trending_ai_short_dramas_report: trendingReport
        }));
      } else {
        console.error(trendingResult.reason);
        errors.push(`${t("\u70ED\u95E8\u699C\u5355", "Trending list")}: ${formatProviderModelEndpointError(trendingResult.reason)}`);
      }
      if (industryReport || trendingReport) {
        try {
          await persistStoryGeneratorInputPatch({
            ...industryReport ? { ai_short_drama_industry_report: industryReport } : {},
            ...trendingReport ? { trending_ai_short_dramas_report: trendingReport } : {}
          });
        } catch (saveErr) {
          console.warn("[Market Research] save report failed:", saveErr);
        }
        try {
          await loadMarketIntelHistory();
        } catch (histErr) {
          console.warn("[Market Research] refresh history failed:", histErr);
        }
      }
      if (errors.length > 0) {
        alert(`${t("\u90E8\u5206\u5E02\u573A\u60C5\u62A5\u83B7\u53D6\u5931\u8D25", "Some market research requests failed")}:
${errors.join("\n")}`);
      }
    } finally {
      setIsFetchingMarketResearch(false);
    }
  };
  const handleAppendMarketResearchToWildIdeas = () => {
    const blocks = [];
    if (industryAnalysisReport?.markdown) {
      const period = industryAnalysisReport.report_period || industryAnalysisReport.report_month || "";
      const header = t(
        `\u3010${period} AI\u77ED\u5267\u70ED\u699C\u9898\u6750\u53D8\u5316\u53C2\u8003\u3011
${industryAnalysisReport.summary || ""}
`,
        `[${period} AI Short Drama Hot-List Genre Shift Reference]
${industryAnalysisReport.summary || ""}
`
      );
      blocks.push(`${header}
${String(industryAnalysisReport.markdown || "").trim()}`.trim());
    }
    if (trendingDramasReport?.markdown) {
      const period = trendingDramasReport.report_period || trendingDramasReport.report_month || "";
      const header = t(
        `\u3010${period} AI\u77ED\u5267\u70ED\u699C\u53C2\u8003\u3011
${trendingDramasReport.summary || ""}
`,
        `[${period} AI Short Drama Trending Reference]
${trendingDramasReport.summary || ""}
`
      );
      blocks.push(`${header}
${String(trendingDramasReport.markdown || "").trim()}`.trim());
    }
    if (blocks.length === 0) return;
    const block = blocks.join("\n\n");
    const nextNotes = globalStoryInput.wild_creative_notes ? `${String(globalStoryInput.wild_creative_notes).trim()}

${block}` : block;
    setGlobalStoryInput((prev) => ({
      ...prev,
      wild_creative_notes: nextNotes
    }));
    void persistStoryGeneratorInputPatch({ wild_creative_notes: nextNotes }).catch((err) => {
      console.warn("[Market Research] append to wild ideas save failed:", err);
    });
    if (mode === "market_research" && typeof onTabChange === "function") {
      onTabChange("generator");
    }
  };
  const handleStructureCreativeInput = async () => {
    const creativeText = String(globalStoryInput.wild_creative_notes || "").trim();
    if (!creativeText) {
      alert(t("\u8BF7\u5148\u5728\u300C\u5929\u9A6C\u884C\u7A7A\u300D\u8F93\u5165\u6846\u4E2D\u5199\u4E0B\u521B\u610F\u8111\u6D1E\u3002", "Please write your wild ideas in the brainstorm box first."));
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
        language: info.language
      }));
      const structureFields = [
        "logline",
        "theme",
        "core_conflict",
        "background",
        "characters",
        "setup",
        "development",
        "turning_points",
        "climax",
        "resolution",
        "suspense",
        "foreshadowing",
        "extra_notes"
      ];
      setGlobalStoryInput((prev) => {
        const next = { ...prev, wild_creative_notes: prev.wild_creative_notes };
        structureFields.forEach((key) => {
          if (structured && Object.prototype.hasOwnProperty.call(structured, key)) {
            next[key] = String(structured[key] ?? "").trim();
          }
        });
        return next;
      });
      const snippetCount = structured?.prefill_meta?.search_meta?.snippet_count;
      const searchNote = Number(snippetCount) > 0 ? t(`\uFF08\u5DF2\u53C2\u8003 ${snippetCount} \u6761\u9AD8\u6F6E/\u540D\u573A\u9762/\u753B\u9762/\u5BF9\u767D/\u52A8\u4F5C\u68C0\u7D22\u7D20\u6750\uFF09`, ` (informed by ${snippetCount} climax/iconic-scene reference snippets)`) : "";
      alert(t("\u5DF2\u63D0\u53D6\u5173\u952E\u8981\u7D20\u3001\u68C0\u7D22\u9AD8\u6F6E\u4E0E\u540D\u573A\u9762\u53C2\u8003\u7D20\u6750\u5E76\u9884\u586B I1\u2013I9 \u5B57\u6BB5\uFF0C\u8BF7\u91CD\u70B9\u6838\u5BF9 I7a \u9AD8\u6F6E\u540D\u573A\u9762\u3002", "Key elements extracted, climax/iconic references searched, and I1\u2013I9 prefilled. Review I7a climax scenes carefully.") + searchNote);
    } catch (e) {
      console.error(e);
      const readable = formatProviderModelEndpointError(e);
      alert(`${t("\u7ED3\u6784\u5316\u5931\u8D25", "Structuring failed")}:
${readable}`);
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
        mode: "global",
        generator_kind: "story",
        episodes_count: Number(globalStoryInput.episodes_count || 0),
        episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1,
        script_mode: globalStoryInput.script_mode,
        target_audience: globalStoryInput.target_audience,
        // Project Overview / Basic Information (forward to LLM)
        script_title: info.script_title,
        expected_duration: info.expected_duration,
        type: info.type,
        language: info.language,
        base_positioning: info.base_positioning,
        Global_Style: info.Global_Style,
        logline: globalStoryInput.logline,
        theme: globalStoryInput.theme,
        core_conflict: globalStoryInput.core_conflict,
        background: globalStoryInput.background,
        characters: globalStoryInput.characters,
        setup: globalStoryInput.setup,
        development: globalStoryInput.development,
        turning_points: globalStoryInput.turning_points,
        climax: globalStoryInput.climax,
        resolution: globalStoryInput.resolution,
        suspense: globalStoryInput.suspense,
        foreshadowing: globalStoryInput.foreshadowing,
        wild_creative_notes: globalStoryInput.wild_creative_notes,
        extra_notes: globalStoryInput.extra_notes
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
              ...updated.global_info.tech_params?.visual_standard || {}
            }
          }
        };
        merged.type = normalizeProjectEpisodeType(merged.type);
        merged.language = normalizeProjectEpisodeLanguage(merged.language);
        merged.base_positioning = normalizeProjectEpisodeBasePositioning(merged.base_positioning);
        merged.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.Global_Style);
        merged.tone = normalizeProjectEpisodeTone(merged.tone);
        merged.lighting = normalizeProjectEpisodeLighting(merged.lighting);
        merged.script_title = stripStackedProductionScriptTitleSuffixes(merged.script_title);
        if (merged.tech_params?.visual_standard) {
          merged.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.tech_params.visual_standard.quality);
        }
        setInfo(merged);
      }
      alert("Global story framework generated and saved to Overview.");
    } catch (e) {
      console.error(e);
      const readable = formatProviderModelEndpointError(e);
      alert(`Failed to generate global story:
${readable}`);
    } finally {
      setIsGeneratingGlobalStory(false);
      globalStoryGenerationInFlightRef.current = false;
    }
  };
  const handleExportStoryGeneratorPackage = async () => {
    try {
      const pkg = await exportProjectStoryGlobalPackage(id);
      const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safeName = String(project?.title || `project_${id}`).replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, "_").slice(0, 60);
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
    storyPackageFileInputRef.current.value = "";
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
        throw new Error("Invalid JSON file.");
      }
      const payload = {
        project_overview: parsed?.project_overview || {},
        basic_information: parsed?.basic_information || {},
        character_canon_project: parsed?.character_canon_project || {},
        story_generator_global_project: parsed?.story_generator_global_project || {},
        story_generator_global_structured: parsed?.story_generator_global_structured || {},
        story_generator_global_input: parsed?.story_generator_global_input || {},
        story_dna_global_md: parsed?.story_dna_global_md || ""
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
              ...updated.global_info.tech_params?.visual_standard || {}
            }
          }
        };
        setInfo(merged);
        setStoryFrameworkViewMode("preview");
        if (updated.global_info.story_generator_global_input && typeof updated.global_info.story_generator_global_input === "object") {
          skipNextGlobalStoryAutosaveRef.current = true;
          setGlobalStoryInput((prev) => ({
            ...prev,
            ...updated.global_info.story_generator_global_input,
            episode_duration_minutes: Number(updated.global_info.story_generator_global_input.episode_duration_minutes) > 0 ? Number(updated.global_info.story_generator_global_input.episode_duration_minutes) : 1
          }));
          if (updated.global_info.story_generator_global_input.trending_ai_short_dramas_report) {
            setTrendingDramasReport(updated.global_info.story_generator_global_input.trending_ai_short_dramas_report);
          }
          if (updated.global_info.story_generator_global_input.ai_short_drama_industry_report) {
            setIndustryAnalysisReport(updated.global_info.story_generator_global_input.ai_short_drama_industry_report);
          }
        }
        const importedCanonDraft = updated.global_info.character_canon_input;
        if (importedCanonDraft && typeof importedCanonDraft === "object") {
          if (typeof importedCanonDraft.name === "string") setCanonName(importedCanonDraft.name);
          if (Array.isArray(importedCanonDraft.selected_identity_ids)) setCanonSelectedIdentityIds(importedCanonDraft.selected_identity_ids);
          if (Array.isArray(importedCanonDraft.selected_tag_ids)) setCanonSelectedTagIds(importedCanonDraft.selected_tag_ids);
          if (typeof importedCanonDraft.custom_identity === "string") setCanonCustomIdentity(importedCanonDraft.custom_identity);
          if (typeof importedCanonDraft.body_features === "string") setCanonBody(importedCanonDraft.body_features);
          if (typeof importedCanonDraft.custom_style_tags === "string") setCanonCustomTags(importedCanonDraft.custom_style_tags);
          if (typeof importedCanonDraft.extra_notes === "string") setCanonExtra(importedCanonDraft.extra_notes);
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
      alert("Story Generator package imported and saved to this project.");
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
      addLog?.("Cannot generate episode scripts: missing project id.", "error");
      alert("Cannot generate episode scripts: missing project id.");
      episodeScriptsGenerationInFlightRef.current = false;
      return;
    }
    const generatorKind = projectTab === "promo_generator" ? "promo" : "story";
    const n = Number(
      projectTab === "promo_generator" ? promoInput.episodes_count || 0 : globalStoryInput.episodes_count || 0
    );
    if (!specificEpisode && (!n || Number.isNaN(n) || n <= 0)) {
      alert("Please set a valid Episodes Count first.");
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
    episodeScriptsStatusTimerRef.current = setInterval(pollEpisodeScriptsStatus, 3e3);
    pollEpisodeScriptsStatus();
    try {
      const overwriteExisting = true;
      const modeLabel = retryFailedOnly ? "retry-failed-only" : specificEpisode ? `generate-episode-${specificEpisode}` : "overwrite-all-default";
      if (overwriteExisting && !specificEpisode) {
        const ok = await confirmUiMessage("\u9ED8\u8BA4\u4F1A\u8986\u76D6\u76EE\u6807\u8303\u56F4\u5185\u5DF2\u6709\u5206\u96C6\u5267\u672C\uFF0C\u662F\u5426\u7EE7\u7EED\uFF1F", "This will overwrite existing episode scripts in the target range by default. Continue?");
        if (!ok) {
          addLog?.("Force Start canceled.", "warning");
          return;
        }
      } else if (specificEpisode) {
        const ok = await confirmUiMessage(`\u786E\u5B9A\u8981\u5355\u72EC\u751F\u6210\u7B2C ${specificEpisode} \u96C6\u7684\u5267\u672C\u5417\uFF1F\u8FD9\u4F1A\u8986\u76D6\u5DF2\u6709\u5185\u5BB9\u3002`, `Are you sure you want to regenerate episode ${specificEpisode}? This will overwrite existing script.`);
        if (!ok) {
          addLog?.("Single Episode Generation canceled.", "warning");
          return;
        }
      }
      addLog?.(`Generating episode scripts (${modeLabel}, target 1..${n})... (This may take several minutes)`, "process");
      addLog?.(
        `[DEBUG][Before API] Generate Episode Scripts payload: ${JSON.stringify({ generator_kind: generatorKind, episodes_count: n, episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1, script_mode: globalStoryInput.script_mode, script_title: info?.script_title || project?.title || "", overwrite_existing: overwriteExisting, retry_failed_only: retryFailedOnly, episode_number: specificEpisode })}`,
        "info"
      );
      const reqPayload = {
        generator_kind: generatorKind,
        episodes_count: n,
        episode_duration_minutes: Number(globalStoryInput.episode_duration_minutes) > 0 ? Number(globalStoryInput.episode_duration_minutes) : 1,
        script_mode: globalStoryInput.script_mode,
        target_audience: globalStoryInput.target_audience,
        script_title: String(info?.script_title || project?.title || "").trim(),
        overwrite_existing: overwriteExisting,
        retry_failed_only: retryFailedOnly
      };
      if (specificEpisode) {
        reqPayload.episode_number = Number(specificEpisode);
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
          errors_count: Array.isArray(res?.errors) ? res.errors.length : 0
        })}`,
        "info"
      );
      const dbg = res?.debug_context || {};
      addLog?.(
        `[DEBUG][Input Confirm] Character relationships imported: ${dbg.has_character_relationships ? "YES" : "NO"}; Character source: ${dbg.character_canon_source || "unknown"}; Global DNA len: ${dbg.global_story_dna_length ?? 0}; Character canon len: ${dbg.character_canon_length ?? 0}`,
        "info"
      );
      const created = Number(res?.episodes_created ?? 0);
      const errors = Array.isArray(res?.errors) ? res.errors : [];
      const results = Array.isArray(res?.results) ? res.results : [];
      const generatedCount = Number(res?.episodes_generated ?? results.filter((r) => r?.generated === true).length);
      const generated = Number.isFinite(generatedCount) ? generatedCount : results.filter((r) => r?.generated === true).length;
      const skipped = results.filter((r) => r?.skipped === true).length;
      const generatedEpisodeIds = results.filter((item) => item?.generated && Number(item?.episode_id || 0) > 0).map((item) => Number(item.episode_id));
      const summary = `Generated: ${generated}, Skipped: ${skipped}, Created Episodes: ${created}, Errors: ${errors.length}`;
      if (errors.length > 0) {
        addLog?.(`Episode script generation finished. ${summary}`, "warning");
        alert(`Episode script generation finished. ${summary}`);
      } else {
        addLog?.(`Episode script generation finished. ${summary}`, "success");
        alert(`Episode script generation finished. ${summary}`);
      }
      if (onProjectUpdate) {
        await onProjectUpdate();
      }
      if (onRefreshEpisodes) {
        await onRefreshEpisodes({ invalidateEpisodeIds: generatedEpisodeIds });
      }
      if (specificEpisode) {
        const generatedSingle = results.find((item) => {
          if (!item || typeof item !== "object") return false;
          const num = Number(item.episode_number || 0);
          const eid = Number(item.episode_id || 0);
          return num === Number(specificEpisode) && eid > 0 && Boolean(item.generated);
        }) || results.find((item) => {
          if (!item || typeof item !== "object") return false;
          const eid = Number(item.episode_id || 0);
          return eid > 0 && Boolean(item.generated);
        });
        const resolvedEpisodeId = Number(generatedSingle?.episode_id || 0);
        const resolvedTitle = String(generatedSingle?.episode_title || "").trim();
        if (resolvedEpisodeId > 0 && onJumpToEpisode) {
          addLog?.(
            `[Single Episode] Jumping to generated episode_id=${resolvedEpisodeId}${resolvedTitle ? ` title=${resolvedTitle}` : ""}`,
            "info"
          );
          onJumpToEpisode(resolvedEpisodeId, { forceReload: true });
        }
      }
    } catch (e) {
      console.error(e);
      const detail = e?.response?.data?.detail || e?.response?.data?.message || e?.message || String(e);
      addLog?.(`Episode script generation failed: ${detail}`, "error");
      alert(`Failed to generate episode scripts: ${detail}`);
    } finally {
      if (episodeScriptsStatusTimerRef.current) {
        clearInterval(episodeScriptsStatusTimerRef.current);
        episodeScriptsStatusTimerRef.current = null;
      }
      setIsGeneratingEpisodeScripts(false);
      setShowEpisodeScriptsProgressModal(false);
      setEpisodeScriptsProgress((prev) => {
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
      setEpisodeScriptsProgress((prev) => {
        if (!prev || typeof prev !== "object") return prev;
        return {
          ...prev,
          running: false,
          stop_requested: true,
          force_stopped: true,
          status: "canceled",
          message: res?.message || "Force stopped"
        };
      });
      setIsGeneratingEpisodeScripts(false);
      if (episodeScriptsStatusTimerRef.current) {
        clearInterval(episodeScriptsStatusTimerRef.current);
        episodeScriptsStatusTimerRef.current = null;
      }
      addLog?.(res?.message || "Force stopped episode scripts task.", "warning");
      await pollEpisodeScriptsStatus();
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message || String(e);
      addLog?.(`Stop episode scripts failed: ${detail}`, "error");
      alert(`Failed to stop episode scripts: ${detail}`);
    } finally {
      setIsStoppingEpisodeScripts(false);
    }
  };
  const handleGenerateProjectCanon = async () => {
    if (projectCanonGenerationInFlightRef.current || isGeneratingCanon) return;
    projectCanonGenerationInFlightRef.current = true;
    const name = (canonName || "").trim();
    if (!name) {
      alert("\u8BF7\u8F93\u5165\u89D2\u8272\u540D\u79F0");
      projectCanonGenerationInFlightRef.current = false;
      return;
    }
    const custom = (canonCustomTags || "").split(/[,，\n]/).map((t2) => t2.trim()).filter(Boolean);
    const selectedStrings = canonSelectedTagStrings();
    const style_tags = Array.from(/* @__PURE__ */ new Set([...selectedStrings || [], ...custom]));
    const identityCustom = (canonCustomIdentity || "").split(/[,，\n]/).map((t2) => t2.trim()).filter(Boolean);
    const identityStrings = canonSelectedIdentityStrings();
    const identityMerged = Array.from(/* @__PURE__ */ new Set([...identityStrings || [], ...identityCustom]));
    const identity = identityMerged.join(" / ");
    setIsGeneratingCanon(true);
    try {
      const updated = await generateProjectCharacterProfile(id, buildScriptAnalysisApiPayload({
        name,
        identity,
        body_features: canonBody || "",
        style_tags,
        extra_notes: canonExtra || ""
      }));
      setProject(updated);
      if (updated?.global_info) {
        const merged = {
          ...info,
          ...updated.global_info,
          tech_params: {
            visual_standard: {
              ...info.tech_params.visual_standard,
              ...updated.global_info.tech_params?.visual_standard || {}
            }
          }
        };
        setInfo(merged);
      }
      setShowCanonModal(false);
      alert("Character Canon generated and appended in Overview.");
    } catch (e) {
      console.error(e);
      alert(`Failed to generate Character Canon: ${e.message}`);
    } finally {
      setIsGeneratingCanon(false);
      projectCanonGenerationInFlightRef.current = false;
    }
  };
  const updateField = (key, value) => {
    setInfo((prev) => ({
      ...prev,
      [key]: key === "type" ? normalizeProjectEpisodeType(value) : key === "language" ? normalizeProjectEpisodeLanguage(value) : key === "base_positioning" ? normalizeProjectEpisodeBasePositioning(value) : key === "Global_Style" ? normalizeProjectEpisodeGlobalStyle(value) : key === "tone" ? normalizeProjectEpisodeTone(value) : key === "lighting" ? normalizeProjectEpisodeLighting(value) : key === "project_share_users" || key === "project_reviewer_users" ? normalizeUserListValues(value) : value
    }));
  };
  const updateTech = (key, value) => {
    setInfo((prev) => {
      const prevVisual = prev?.tech_params?.visual_standard || {};
      const nextValue = key === "quality" ? normalizeProjectEpisodeQuality(value) : key === "video_resolution" ? normalizeProjectVideoResolution(value) || "720" : value;
      const nextVisual = {
        ...prevVisual,
        [key]: nextValue
      };
      if (key === "aspect_ratio" || key === "image_size") {
        const preset = getResolutionByAspectAndImageSize(
          key === "aspect_ratio" ? nextValue : nextVisual.aspect_ratio,
          key === "image_size" ? nextValue : nextVisual.image_size
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
          visual_standard: nextVisual
        }
      };
    });
  };
  const handleBorrowedFilmsChange = (str) => {
    const arr = str.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
    setInfo((prev) => ({ ...prev, borrowed_films: arr }));
  };
  const isGeneratorMode = mode === "generator";
  const episodeScriptResults = isGeneratorMode && Array.isArray(episodeScriptsProgress?.results) ? episodeScriptsProgress.results : [];
  const episodesInRun = isGeneratorMode ? Number(episodeScriptsProgress?.episodes_in_run || 0) : 0;
  const processedCount = isGeneratorMode ? Number(episodeScriptsProgress?.processed || 0) : 0;
  const progressPercent = episodesInRun > 0 ? Math.min(100, Math.round(processedCount / episodesInRun * 100)) : 0;
  const episodeScriptsRunning = Boolean(episodeScriptsProgress?.running) || isGeneratingEpisodeScripts;
  const episodeScriptsStopRequested = Boolean(episodeScriptsProgress?.stop_requested);
  const storyGeneratorInheritedInfo = useMemo(() => {
    const resolvedScriptTitle = String(info?.script_title || project?.title || "").trim();
    const resolvedType = String(info?.type || "").trim();
    const resolvedLanguage = String(info?.language || "").trim();
    const resolvedBasePositioning = String(info?.base_positioning || "").trim();
    const resolvedGlobalStyle = String(info?.Global_Style || "").trim();
    return [
      { label: t("\u5267\u672C\u6807\u9898", "Script Title"), value: resolvedScriptTitle },
      { label: t("\u7C7B\u578B", "Type"), value: resolvedType },
      { label: t("\u8BED\u8A00", "Language"), value: resolvedLanguage },
      { label: t("\u5267\u672C\u6A21\u5F0F (\u57FA\u7840\u5B9A\u4F4D)", "Script Mode (Base Positioning)"), value: resolvedBasePositioning },
      { label: t("\u5168\u5C40\u98CE\u683C", "Global Style"), value: resolvedGlobalStyle }
    ];
  }, [info?.script_title, info?.type, info?.language, info?.base_positioning, info?.Global_Style, project?.title, t]);
  const storyGeneratorMissingInfo = useMemo(() => {
    const missing = [];
    if (!String(info?.script_title || project?.title || "").trim()) missing.push(t("\u5267\u672C\u6807\u9898", "Script Title"));
    if (!String(info?.type || "").trim()) missing.push(t("\u7C7B\u578B", "Type"));
    if (!String(info?.language || "").trim()) missing.push(t("\u8BED\u8A00", "Language"));
    if (!String(info?.base_positioning || "").trim()) missing.push(t("\u5267\u672C\u6A21\u5F0F (\u57FA\u7840\u5B9A\u4F4D)", "Script Mode (Base Positioning)"));
    if (!String(info?.Global_Style || "").trim()) missing.push(t("\u5168\u5C40\u98CE\u683C", "Global Style"));
    return missing;
  }, [info?.script_title, info?.type, info?.language, info?.base_positioning, info?.Global_Style, project?.title, t]);
  const episodeTitleByNumber = useMemo(() => {
    if (!isGeneratorMode) return /* @__PURE__ */ new Map();
    const titleMap = /* @__PURE__ */ new Map();
    (Array.isArray(episodes) ? episodes : []).forEach((ep, index) => {
      const parsedNumber = Number(ep?.episode_number) > 0 ? Number(ep?.episode_number) : parseEpisodeNumberFromText(ep?.title) || index + 1;
      if (!parsedNumber || titleMap.has(parsedNumber)) return;
      titleMap.set(parsedNumber, String(ep?.title || "").trim());
    });
    return titleMap;
  }, [episodes, isGeneratorMode]);
  const episodeResultRows = useMemo(() => {
    if (!isGeneratorMode || !episodeScriptsProgress || episodesInRun <= 0) return [];
    const byEpisodeNumber = /* @__PURE__ */ new Map();
    for (const item of episodeScriptResults) {
      const num = Number(item?.episode_number || 0);
      if (!num) continue;
      byEpisodeNumber.set(num, item);
    }
    const resultEpisodeNumbers = Array.from(byEpisodeNumber.keys()).filter((n) => Number.isFinite(n) && n > 0).sort((a, b) => a - b);
    const plannedEpisodeNumbers = resultEpisodeNumbers.length > 0 ? resultEpisodeNumbers : Array.from({ length: episodesInRun }, (_, idx) => idx + 1);
    const rows = [];
    for (const i of plannedEpisodeNumbers) {
      const row = byEpisodeNumber.get(i);
      const knownTitle = episodeTitleByNumber.get(i);
      if (row) {
        rows.push({
          episode_number: i,
          episode_id: row?.episode_id,
          project_episode_title: row?.project_episode_title || knownTitle || t(`\u7B2C ${i} \u96C6`, `Episode ${i}`),
          episode_title: row?.episode_title || knownTitle || t(`\u7B2C ${i} \u96C6`, `Episode ${i}`),
          llm_episode_number: row?.llm_episode_number,
          title_mismatch: Boolean(row?.title_mismatch),
          status: row?.status || (row?.generated ? "generated" : row?.skipped ? "skipped" : row?.error ? "failed" : "unknown"),
          output_chars: row?.output_chars,
          error: row?.error,
          reason: row?.reason
        });
      } else {
        rows.push({
          episode_number: i,
          episode_title: knownTitle || t(`\u7B2C ${i} \u96C6`, `Episode ${i}`),
          status: "pending"
        });
      }
    }
    return rows;
  }, [episodeScriptsProgress, episodeScriptResults, episodesInRun, episodeTitleByNumber, isGeneratorMode, t]);
  const failedEpisodeRows = useMemo(() => {
    if (!isGeneratorMode || episodeResultRows.length === 0) return [];
    return episodeResultRows.filter((item) => item?.status === "failed" && item?.episode_id);
  }, [episodeResultRows, isGeneratorMode]);
  const shouldComputeCostPanel = mode === "overview" && expandedSections.cost;
  const episodeCostChart = useMemo(() => {
    if (!shouldComputeCostPanel) return { rows: [], maxStage: 0 };
    const rows = costEstimation && typeof costEstimation === "object" && Array.isArray(costEstimation.episode_costs) ? costEstimation.episode_costs : [];
    const normalized = rows.map((item, idx) => {
      const overviewCost = Number(item?.overview_cost || 0);
      const hasSuggestedField = Object.prototype.hasOwnProperty.call(item || {}, "suggested_cost");
      const suggestedCost = Number(hasSuggestedField ? item?.suggested_cost || 0 : item?.budget_cost || 0);
      const budgetCost = Number(hasSuggestedField ? item?.budget_cost || 0 : item?.execution_cost || 0);
      const currentEstimatedCost = Number(item?.current_estimated_cost || item?.total_cost || 0);
      const episodeNo = Number(item?.episode_number || idx + 1);
      return {
        episode_number: Number.isFinite(episodeNo) ? episodeNo : idx + 1,
        episode_title: String(item?.episode_title || ""),
        overview_cost: Number.isFinite(overviewCost) ? overviewCost : 0,
        suggested_cost: Number.isFinite(suggestedCost) ? suggestedCost : 0,
        budget_cost: Number.isFinite(budgetCost) ? budgetCost : 0,
        current_stage: String(item?.current_stage || ""),
        current_estimated_cost: Number.isFinite(currentEstimatedCost) ? currentEstimatedCost : 0
      };
    });
    const maxStage = normalized.reduce((acc, row) => Math.max(acc, row.overview_cost, row.suggested_cost, row.budget_cost), 0);
    return { rows: normalized, maxStage };
  }, [costEstimation, shouldComputeCostPanel]);
  const costExecutionSuggestions = useMemo(() => {
    if (!shouldComputeCostPanel) return [];
    const suggestions = costEstimation && typeof costEstimation === "object" && Array.isArray(costEstimation.execution_suggestions) ? costEstimation.execution_suggestions : [];
    return suggestions.filter((item) => typeof item === "string" && item.trim().length > 0);
  }, [costEstimation, shouldComputeCostPanel]);
  const hasNewCostSchema = useMemo(() => {
    if (!shouldComputeCostPanel) return false;
    if (!costEstimation || typeof costEstimation !== "object") return false;
    if (Object.prototype.hasOwnProperty.call(costEstimation?.summary || {}, "suggested_estimate")) return true;
    const firstRow = Array.isArray(costEstimation?.episode_costs) ? costEstimation.episode_costs[0] : null;
    return !!(firstRow && Object.prototype.hasOwnProperty.call(firstRow, "suggested_cost"));
  }, [costEstimation, shouldComputeCostPanel]);
  const costStageLabel = useCallback((stageKey) => {
    const key = String(stageKey || "").trim();
    if (key === "overview") return t("\u6982\u8981\u6210\u672C", "Overview Cost");
    if (key === "suggested") return t("\u5EFA\u8BAE\u6210\u672C", "Suggested Cost");
    if (key === "budget") return hasNewCostSchema ? t("\u9884\u7B97\u6210\u672C", "Budget Cost") : t("\u5EFA\u8BAE\u6210\u672C", "Suggested Cost");
    if (key === "execution") return t("\u9884\u7B97\u6210\u672C", "Budget Cost");
    return key || t("\u6982\u8981\u6210\u672C", "Overview Cost");
  }, [hasNewCostSchema, t]);
  useTabMediaRefreshEffect({
    tabMediaRefreshSignal,
    isTabActive,
    onRefresh: () => {
      if (typeof onProjectUpdate === "function") {
        void onProjectUpdate();
      }
      if (typeof onRefreshEpisodes === "function") {
        void onRefreshEpisodes();
      }
    }
  });
  if (!project) return /* @__PURE__ */ React.createElement("div", { className: "p-8 text-muted-foreground" }, t("\u52A0\u8F7D\u4E2D...", "Loading..."));
  const prefix = "proj-";
  const generatorTabs = [
    { id: "story_generator", label: t("\u6545\u4E8B\u751F\u6210\u5668", "Story Generator") },
    { id: "promo_generator", label: t("\u5BA3\u4F20\u7247\u751F\u6210\u5668", "Promo Generator") }
  ];
  const industryHistoryOptions = marketIntelHistory.filter((item) => item.report_kind === "industry_analysis");
  const trendingHistoryOptions = marketIntelHistory.filter((item) => item.report_kind === "trending_dramas");
  const formatMarketIntelOptionLabel = (item) => {
    const month = item.report_month || item.report_period || "";
    const when = item.fetched_at || item.created_at || "";
    return [month, when].filter(Boolean).join(" \xB7 ") || `#${item.id}`;
  };
  return /* @__PURE__ */ React.createElement("div", { className: "p-4 sm:p-6 lg:p-8 w-full h-full overflow-y-auto" }, /* @__PURE__ */ React.createElement(
    MarkdownHelpModal,
    {
      open: manualModalOpen,
      initialDocKey: "generation",
      onClose: () => setManualModalOpen(false),
      uiLang
    }
  ), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center mb-8" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-4" }, /* @__PURE__ */ React.createElement("h2", { className: "text-2xl font-bold" }, mode === "generator" ? t("\u751F\u6210\u5668", "Generators") : mode === "market_research" ? t("\u884C\u4E1A\u5206\u6790 & \u70ED\u699C", "Industry & Trending") : t("\u9879\u76EE\u603B\u89C8", "Project Overview")), mode === "overview" && /* @__PURE__ */ React.createElement("div", { className: "flex items-center px-3 py-1 rounded-full bg-primary/20 border border-primary/30 text-primary text-sm font-medium" }, t("\u9636\u6BB5", "Stage"), ": ", info?.workflow_stage === "montage" || info?.workflow_stage === "shots" ? t("\u5206\u955C", "Shots") : info?.workflow_stage === "subjects" ? t("\u8D44\u4EA7", "Assets") : t("\u5267\u672C", "Script"))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col items-stretch sm:items-end gap-2 w-full sm:w-auto" }, mode !== "market_research" && /* @__PURE__ */ React.createElement(
    TabMediaRefreshButton,
    {
      onClick: () => onMediaRefreshRequest?.(),
      uiLang,
      className: "w-full sm:w-auto"
    }
  ), mode === "market_research" && /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto" }, /* @__PURE__ */ React.createElement(
    FunctionApiSelector,
    {
      functionName: "script_analysis",
      configs: functionApiConfigs,
      label: t("\u5267\u672C\u5206\u6790 API", "Script Analysis API"),
      value: selectedScriptAnalysisApiId,
      onChange: setSelectedScriptAnalysisApiId,
      className: "sm:justify-end"
    }
  )), mode === "generator" && /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => setManualModalOpen(true),
      className: "px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20 border border-white/10 flex items-center justify-center gap-2 w-full sm:w-auto",
      title: t("\u67E5\u770B\u751F\u6210\u5267\u672C\u64CD\u4F5C\u624B\u518C", "View script generation manual")
    },
    /* @__PURE__ */ React.createElement(Info, { className: "w-4 h-4" }),
    " ",
    t("\u751F\u6210\u5267\u672C\u64CD\u4F5C\u624B\u518C", "Script Generation Manual")
  ), mode !== "market_research" && /* @__PURE__ */ React.createElement("button", { onClick: handleSave, className: "px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center justify-center gap-2 w-full sm:w-auto" }, /* @__PURE__ */ React.createElement(SettingsIcon, { className: "w-4 h-4" }), " ", t("\u4FDD\u5B58\u4FEE\u6539", "Save Changes")), mode === "generator" && generatorAutosaveFeedback.phase !== "idle" && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: `text-xs px-3 py-1 rounded-full border ${generatorAutosaveFeedback.phase === "error" ? "border-red-400/40 text-red-200 bg-red-500/10" : generatorAutosaveFeedback.phase === "saved" ? "border-emerald-400/40 text-emerald-200 bg-emerald-500/10" : "border-white/20 text-white/80 bg-white/5"}`
    },
    generatorAutosaveFeedback.phase === "saving" && /* @__PURE__ */ React.createElement(Loader2, { className: "w-3 h-3 inline-block mr-1 animate-spin" }),
    generatorAutosaveFeedback.message
  ))), mode === "generator" && /* @__PURE__ */ React.createElement("div", { className: "mb-6 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "sm:hidden" }, /* @__PURE__ */ React.createElement("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/80" }, t("\u751F\u6210\u5668\u6A21\u5757", "Generator Mode")), /* @__PURE__ */ React.createElement(
    "select",
    {
      value: projectTab,
      onChange: (e) => setProjectTab(e.target.value),
      className: "w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none transition-colors focus:border-primary/40"
    },
    generatorTabs.map((tab) => /* @__PURE__ */ React.createElement("option", { key: `generator-tab-select-${tab.id}`, value: tab.id }, tab.label))
  )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" }, /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto no-scrollbar" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 min-w-max" }, generatorTabs.map((tab) => /* @__PURE__ */ React.createElement(
    "button",
    {
      key: `generator-tab-${tab.id}`,
      onClick: () => setProjectTab(tab.id),
      className: `shrink-0 px-4 py-2 rounded-lg text-sm font-bold ${projectTab === tab.id ? "bg-white text-black" : "bg-white/10 text-white hover:bg-white/20"}`
    },
    tab.label
  )))), /* @__PURE__ */ React.createElement(
    FunctionApiSelector,
    {
      functionName: "script_analysis",
      configs: functionApiConfigs,
      label: t("\u5267\u672C\u5206\u6790 API", "Script Analysis API"),
      value: selectedScriptAnalysisApiId,
      onChange: setSelectedScriptAnalysisApiId,
      className: "sm:justify-end"
    }
  ))), mode === "generator" && // Keeping generator container if it has its own needs
  /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 gap-6 sm:gap-8 w-full" }), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-6 sm:gap-8 w-full" }, mode === "overview" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => toggleSection("basic"),
      className: "w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
    },
    /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u57FA\u672C\u4FE1\u606F", "Basic Information")),
    /* @__PURE__ */ React.createElement(ChevronDown, { className: `w-5 h-5 transition-transform ${expandedSections.basic ? "rotate-180" : ""}` })
  ), /* @__PURE__ */ React.createElement(AnimatePresence, { initial: false }, expandedSections.basic && /* @__PURE__ */ React.createElement(
    motion.div,
    {
      initial: { height: 0, opacity: 0 },
      animate: { height: "auto", opacity: 1 },
      exit: { height: 0, opacity: 0 },
      transition: { duration: 0.3, ease: "easeInOut" },
      className: "border-t border-white/10"
    },
    /* @__PURE__ */ React.createElement("div", { className: "p-4 sm:p-6 space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 gap-4" }, /* @__PURE__ */ React.createElement(InputGroup, { idPrefix: prefix, label: t("\u5267\u672C\u6807\u9898", "Script Title"), value: info.script_title, onChange: (v) => updateField("script_title", v), placeholder: t("\u4F8B\u5982\uFF1A\u6211\u7684\u79D1\u5E7B\u53F2\u8BD7", "e.g. My Sci-Fi Epic") }), /* @__PURE__ */ React.createElement(InputGroup, { idPrefix: prefix, label: t("\u9884\u671F\u65F6\u957F(\u79D2)", "Expected Duration (s)"), type: "number", min: "1", value: info.expected_duration || "", onChange: (v) => updateField("expected_duration", v), placeholder: "60" })), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" }, /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u7C7B\u578B", "Type"),
        value: info.type,
        onChange: (v) => updateField("type", v),
        list: PROJECT_EP_TYPE_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u56FD\u5BB6\u5730\u57DF", "Country/Region"),
        value: info.country_region,
        onChange: (v) => updateField("country_region", v),
        list: PROJECT_EP_COUNTRY_REGION_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u8BED\u8A00", "Language"),
        value: info.language,
        onChange: (v) => updateField("language", v),
        list: PROJECT_EP_LANGUAGE_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u5267\u672C\u6A21\u5F0F (\u57FA\u7840\u5B9A\u4F4D)", "Script Mode (Base Positioning)"),
        value: info.base_positioning,
        onChange: (v) => updateField("base_positioning", v),
        list: PROJECT_EP_BASE_POSITIONING_OPTIONS,
        placeholder: t("\u4F8B\u5982\uFF1A\u90FD\u5E02\u7231\u60C5 / \u79D1\u5E7B", "e.g. Urban Romance / Sci-Fi")
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u5E74\u4EE3", "Era"),
        value: info.era,
        onChange: (v) => updateField("era", v),
        list: PROJECT_SCENE_ANALYSIS_ERA_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u53D1\u751F\u5B63\u8282", "Season Occurrence"),
        value: info.season_occurrence,
        onChange: (v) => updateField("season_occurrence", v),
        list: PROJECT_EP_SEASON_OCCURRENCE_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u955C\u5934\u504F\u597D", "Lens Preference"),
        value: info.lens_preference,
        onChange: (v) => updateField("lens_preference", v),
        list: PROJECT_EP_LENS_PREFERENCE_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u753B\u5E45\u6BD4\u4F8B", "Aspect Ratio"),
        value: info.tech_params?.visual_standard?.aspect_ratio,
        onChange: (v) => updateTech("aspect_ratio", v),
        list: PROJECT_ASPECT_RATIO_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u64AD\u51FA\u5B89\u5168\u7B49\u7EA7", "Broadcast Safety Level"),
        value: info.broadcast_safety_level,
        onChange: (v) => updateField("broadcast_safety_level", v),
        list: PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u521B\u4F5C\u529B", "Creativity"),
        value: info.creativity,
        onChange: (v) => updateField("creativity", v),
        list: PROJECT_EP_CREATIVITY_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 mt-[28px] pl-1" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        id: "hasExistingAssetsOverview",
        checked: info.has_existing_assets !== false,
        onChange: (e) => updateField("has_existing_assets", e.target.checked),
        className: "w-4 h-4 text-primary focus:ring-primary/30 rounded border-white/20 bg-background"
      }
    ), /* @__PURE__ */ React.createElement("label", { htmlFor: "hasExistingAssetsOverview", className: "text-sm font-semibold text-primary/95 cursor-pointer" }, t("\u6709\u73B0\u6709\u8D44\u4EA7", "Has Existing Assets")))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-1" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold" }, t("\u89C6\u9891\u58F0\u97F3", "Video Sound")), /* @__PURE__ */ React.createElement(
      "select",
      {
        className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none",
        value: resolveProjectVideoSoundEnabled(info) ? "on" : "off",
        onChange: (e) => updateField("video_sound", e.target.value !== "off")
      },
      /* @__PURE__ */ React.createElement("option", { value: "on" }, t("\u6709", "Enabled")),
      /* @__PURE__ */ React.createElement("option", { value: "off" }, t("\u65E0", "Disabled"))
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u8865\u5145\u8BF4\u660E", "Additional Notes")), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none",
        value: info.notes,
        onChange: (e) => updateField("notes", e.target.value),
        placeholder: t("\u5176\u4ED6\u9700\u8981\u8865\u5145\u7684\u91CD\u8981\u4FE1\u606F...", "Any other important information...")
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u5206\u4EAB\u4EBA\uFF08\u53EF\u9009\uFF0C\u53EF\u591A\u4E2A\uFF09", "Share Users (Optional, Multiple)")), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none",
        value: formatUserListForTextarea(info.project_share_users),
        onChange: (e) => updateField("project_share_users", e.target.value),
        placeholder: t("\u8F93\u5165\u7528\u6237\u540D\u6216\u90AE\u7BB1\uFF0C\u652F\u6301\u9017\u53F7\u3001\u5206\u53F7\u6216\u6362\u884C\u5206\u9694", "Enter usernames or emails, separated by commas, semicolons, or new lines")
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "mt-2 text-xs text-muted-foreground" }, formatManagedUserHint(info.project_share_users, t))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u5BA1\u6838\u4EBA\uFF08\u53EF\u9009\uFF0C\u53EF\u591A\u4E2A\uFF09", "Reviewer Users (Optional, Multiple)")), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none",
        value: formatUserListForTextarea(info.project_reviewer_users),
        onChange: (e) => updateField("project_reviewer_users", e.target.value),
        placeholder: t("\u8F93\u5165\u7528\u6237\u540D\u6216\u90AE\u7BB1\uFF0C\u4FDD\u5B58\u65F6\u6821\u9A8C\u662F\u5426\u5B58\u5728", "Enter usernames or emails. Existence will be validated on save")
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "mt-2 text-xs text-muted-foreground" }, formatManagedUserHint(info.project_reviewer_users, t)))))
  ))), mode === "overview" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => toggleSection("cost"),
      className: "w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
    },
    /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3" }, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u6210\u672C\u8BC4\u4F30\u4E0E\u6267\u884C\u5EFA\u8BAE", "Cost Estimation & Execution Advice")), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-muted-foreground hidden sm:inline" }, t("\u57FA\u4E8E\u9879\u76EE\u5C5E\u6027\u81EA\u52A8\u8BA1\u7B97", "Auto-calculated from project attributes"))),
    /* @__PURE__ */ React.createElement(ChevronDown, { className: `w-5 h-5 transition-transform ${expandedSections.cost ? "rotate-180" : ""}` })
  ), /* @__PURE__ */ React.createElement(AnimatePresence, { initial: false }, expandedSections.cost && /* @__PURE__ */ React.createElement(
    motion.div,
    {
      initial: { height: 0, opacity: 0 },
      animate: { height: "auto", opacity: 1 },
      exit: { height: 0, opacity: 0 },
      transition: { duration: 0.3, ease: "easeInOut" },
      className: "border-t border-white/10"
    },
    /* @__PURE__ */ React.createElement("div", { className: "p-4 sm:p-6 space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, costEstimation ? /* @__PURE__ */ React.createElement(React.Fragment, null, t("\u5F53\u524D\u9636\u6BB5\u4F30\u7B97", "Current Stage Estimate"), ": ", /* @__PURE__ */ React.createElement("span", { className: "text-white font-semibold" }, Number(costEstimation?.summary?.current_estimate || 0).toLocaleString()), /* @__PURE__ */ React.createElement("span", { className: "ml-3" }, t("\u5F53\u524D\u9636\u6BB5", "Current Stage"), ": ", /* @__PURE__ */ React.createElement("span", { className: "text-white font-semibold" }, costStageLabel(costEstimation?.summary?.current_stage || "overview"))), /* @__PURE__ */ React.createElement("span", { className: "ml-3" }, t("\u603B\u500D\u7387", "Total Multiplier"), ": ", /* @__PURE__ */ React.createElement("span", { className: "text-white font-semibold" }, Number(costEstimation?.project_multiplier || 1).toFixed(3), "x"))) : t("\u5F53\u524D\u672A\u7F13\u5B58\u6210\u672C\u5FEB\u7167\uFF0C\u53EF\u6309\u9700\u52A0\u8F7D\u6216\u91CD\u7B97\u3002", "No cached cost snapshot yet. Load or recompute on demand.")), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => loadProjectCost({ forceRecompute: !!costEstimation }),
        disabled: isCostRefreshing || isCostLoading,
        className: `px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 ${isCostRefreshing || isCostLoading ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`
      },
      isCostRefreshing || isCostLoading ? /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }) : /* @__PURE__ */ React.createElement(RefreshCw, { className: "w-4 h-4" }),
      isCostRefreshing ? t("\u91CD\u7B97\u4E2D...", "Recomputing...") : isCostLoading ? t("\u52A0\u8F7D\u4E2D...", "Loading...") : costEstimation ? t("\u91CD\u7B97\u6210\u672C", "Recompute Cost") : t("\u52A0\u8F7D\u6210\u672C", "Load Cost")
    )), costError && /* @__PURE__ */ React.createElement("div", { className: "rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200" }, costError), isCostLoading && !costEstimation && /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u52A0\u8F7D\u6210\u672C\u8BC4\u4F30\u4E2D...", "Loading cost estimation...")), !isCostLoading && !costEstimation && !costError && /* @__PURE__ */ React.createElement("div", { className: "rounded-lg border border-white/10 bg-black/20 px-3 py-3 text-sm text-muted-foreground" }, t("\u5F53\u524D\u5C55\u793A\u4F18\u5148\u4F7F\u7528\u9879\u76EE\u5DF2\u4FDD\u5B58\u7684\u6210\u672C\u5FEB\u7167\uFF1B\u5982\u9700\u6700\u65B0\u503C\uFF0C\u8BF7\u70B9\u51FB\u201C\u52A0\u8F7D\u6210\u672C\u201D\u6216\u76F4\u63A5\u201C\u91CD\u7B97\u6210\u672C\u201D\u3002", 'The panel prefers a saved project cost snapshot. Click "Load Cost" for the cached snapshot or recompute for the latest values.')), costEstimation && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-white/10 bg-black/20 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-3" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold" }, t("\u5206\u96C6\u6210\u672C\u56FE", "Per-Episode Cost Chart")), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 text-[11px] text-muted-foreground" }, /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-1" }, /* @__PURE__ */ React.createElement("span", { className: "inline-block w-2.5 h-2.5 rounded-sm bg-sky-400" }), t("\u6982\u8981\u6210\u672C", "Overview Cost")), /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-1" }, /* @__PURE__ */ React.createElement("span", { className: "inline-block w-2.5 h-2.5 rounded-sm bg-emerald-400" }), t("\u5EFA\u8BAE\u6210\u672C", "Suggested Cost")), /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-1" }, /* @__PURE__ */ React.createElement("span", { className: "inline-block w-2.5 h-2.5 rounded-sm bg-amber-400" }), t("\u9884\u7B97\u6210\u672C", "Budget Cost")))), /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, episodeCostChart.rows.length > 0 ? episodeCostChart.rows.map((row) => {
      const ovPct = episodeCostChart.maxStage > 0 ? Math.max(4, row.overview_cost / episodeCostChart.maxStage * 100) : 4;
      const sgPct = episodeCostChart.maxStage > 0 ? Math.max(4, row.suggested_cost / episodeCostChart.maxStage * 100) : 4;
      const bgPct = episodeCostChart.maxStage > 0 ? Math.max(4, row.budget_cost / episodeCostChart.maxStage * 100) : 4;
      return /* @__PURE__ */ React.createElement("div", { key: `episode-cost-${row.episode_number}`, className: "space-y-1" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between text-xs" }, /* @__PURE__ */ React.createElement("span", { className: "text-muted-foreground" }, t("\u7B2C", "Ep. "), row.episode_number, row.episode_title ? ` \xB7 ${row.episode_title}` : ""), /* @__PURE__ */ React.createElement("span", { className: "text-white font-semibold" }, row.current_estimated_cost.toLocaleString(), " (", costStageLabel(row.current_stage || "overview"), ")")), /* @__PURE__ */ React.createElement("div", { className: "space-y-1" }, /* @__PURE__ */ React.createElement("div", { className: "h-2 rounded-full bg-white/10 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "h-full rounded-full", style: { width: `${ovPct}%`, backgroundColor: "#38bdf8" } })), /* @__PURE__ */ React.createElement("div", { className: "h-2 rounded-full bg-white/10 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "h-full rounded-full", style: { width: `${sgPct}%`, backgroundColor: "#34d399" } })), /* @__PURE__ */ React.createElement("div", { className: "h-2 rounded-full bg-white/10 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "h-full rounded-full", style: { width: `${bgPct}%`, backgroundColor: "#f59e0b" } }))));
    }) : /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, t("\u6682\u65E0\u5206\u96C6\u6210\u672C\u6570\u636E\uFF0C\u8BF7\u5148\u751F\u6210\u5206\u96C6\u5E76\u91CD\u7B97\u6210\u672C\u3002", "No per-episode cost data yet. Generate episodes and recompute cost.")))), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-white/10 bg-black/20 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold mb-3" }, t("\u6267\u884C\u5EFA\u8BAE", "Execution Suggestions")), /* @__PURE__ */ React.createElement("div", { className: "space-y-2 text-sm text-primary/95" }, costExecutionSuggestions.length > 0 ? costExecutionSuggestions.map((item, idx) => /* @__PURE__ */ React.createElement("div", { key: `cost-suggestion-${idx}`, className: "rounded-lg bg-white/5 border border-white/10 px-3 py-2" }, idx + 1, ". ", item)) : /* @__PURE__ */ React.createElement("div", { className: "text-muted-foreground" }, t("\u6682\u65E0\u5EFA\u8BAE\u3002", "No suggestions yet."))))))
  ))), mode === "overview" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => toggleSection("management"),
      className: "w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
    },
    /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u9879\u76EE\u7BA1\u7406", "Project Management")),
    /* @__PURE__ */ React.createElement(ChevronDown, { className: `w-5 h-5 transition-transform ${expandedSections.management ? "rotate-180" : ""}` })
  ), /* @__PURE__ */ React.createElement(AnimatePresence, { initial: false }, expandedSections.management && /* @__PURE__ */ React.createElement(
    motion.div,
    {
      initial: { height: 0, opacity: 0 },
      animate: { height: "auto", opacity: 1 },
      exit: { height: 0, opacity: 0 },
      transition: { duration: 0.3, ease: "easeInOut" },
      className: "border-t border-white/10"
    },
    /* @__PURE__ */ React.createElement("div", { className: "p-4 sm:p-6 space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u8BA1\u5212\u5B8C\u6210\u65F6\u95F4", "Planned Completion Time"),
        value: info.planned_completion_time,
        onChange: (v) => updateField("planned_completion_time", v),
        placeholder: t("\u4F8B\u5982\uFF1A2026-12-31", "e.g., 2026-12-31")
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u9879\u76EE\u9884\u7B97", "Budget"),
        value: info.budget,
        onChange: (v) => updateField("budget", v),
        placeholder: t("\u4F8B\u5982\uFF1A100\u4E07", "e.g., 1M")
      }
    )))
  ))), mode === "overview" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => toggleSection("tech"),
      className: "w-full flex items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
    },
    /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 text-left" }, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary m-0" }, t("\u6280\u672F\u4E0E\u89C6\u89C9\u53C2\u6570", "Technical & Visual Parameters")), /* @__PURE__ */ React.createElement("span", { className: "text-xs font-medium text-muted-foreground normal-case whitespace-nowrap hidden sm:block" }, t("\u5EFA\u8BAE\u4E0D\u6539\u52A8\uFF0C\u5F85\u5927\u6A21\u578B\u56DE\u586B\u3002", "Recommended to keep unchanged, waiting for LLM backfill."))),
    /* @__PURE__ */ React.createElement(ChevronDown, { className: `w-5 h-5 shrink-0 transition-transform ${expandedSections.tech ? "rotate-180" : ""}` })
  ), /* @__PURE__ */ React.createElement(AnimatePresence, { initial: false }, expandedSections.tech && /* @__PURE__ */ React.createElement(
    motion.div,
    {
      initial: { height: 0, opacity: 0 },
      animate: { height: "auto", opacity: 1 },
      exit: { height: 0, opacity: 0 },
      transition: { duration: 0.3, ease: "easeInOut" },
      className: "border-t border-white/10"
    },
    /* @__PURE__ */ React.createElement("div", { className: "p-4 sm:p-6 space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u6A2A\u5411\u5206\u8FA8\u7387", "H. Resolution"),
        value: info.tech_params?.visual_standard?.horizontal_resolution,
        onChange: (v) => updateTech("horizontal_resolution", v),
        placeholder: "1080",
        list: ["720", "1080", "1920", "3840"]
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u7EB5\u5411\u5206\u8FA8\u7387", "V. Resolution"),
        value: info.tech_params?.visual_standard?.vertical_resolution,
        onChange: (v) => updateTech("vertical_resolution", v),
        placeholder: "2160",
        list: ["2160", "1920", "1080", "720"]
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4" }, /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u56FE\u50CF\u5C3A\u5BF8", "Image Size"),
        value: info.tech_params?.visual_standard?.image_size,
        onChange: (v) => updateTech("image_size", v),
        list: ["0.5K", "1K", "2K", "4K"]
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u89C6\u9891\u5206\u8FA8\u7387", "Video Resolution"),
        value: normalizeProjectVideoResolution(info.tech_params?.visual_standard?.video_resolution) || "720",
        onChange: (v) => updateTech("video_resolution", v),
        list: PROJECT_VIDEO_RESOLUTION_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u89C6\u9891\u751F\u6210\u504F\u597D", "Video Gen Preference"),
        value: info.video_generation_preference,
        onChange: (v) => updateField("video_generation_preference", v),
        list: (PROJECT_EP_VIDEO_GEN_PREFERENCE_OPTIONS, PROJECT_EP_CREATIVITY_OPTIONS)
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u5E27\u7387", "Frame Rate"),
        value: info.tech_params?.visual_standard?.frame_rate,
        onChange: (v) => updateTech("frame_rate", v),
        list: ["24", "30", "60"]
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u8D28\u91CF\u7B49\u7EA7", "Quality"),
        value: info.tech_params?.visual_standard?.quality,
        onChange: (v) => updateTech("quality", v),
        list: PROJECT_EP_QUALITY_OPTIONS
      }
    )), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u9879\u76EE Seed", "Project Seed"),
        value: info.generation_seed,
        onChange: (v) => updateField("generation_seed", String(v || "").replace(/[^0-9]/g, "")),
        placeholder: t("\u4F8B\u5982\uFF1A12345678", "e.g. 12345678")
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u5168\u5C40\u98CE\u683C", "Global Style"),
        value: info.Global_Style,
        onChange: (v) => updateField("Global_Style", v),
        multi: true,
        list: PROJECT_EP_GLOBAL_STYLE_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u501F\u9274\u5F71\u7247\uFF08\u53C2\u8003\uFF09", "Borrowed Films (Ref)")), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none",
        value: info.borrowed_films.join(", "),
        onChange: (e) => handleBorrowedFilmsChange(e.target.value),
        placeholder: t("\u7528\u9017\u53F7\u5206\u9694\uFF0C\u4F8B\u5982\uFF1A\u94F6\u7FFC\u6740\u624B, \u9ED1\u5BA2\u5E1D\u56FD", "Use commas to separate, e.g. Blade Runner, Matrix")
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u8272\u8C03", "Tone"),
        value: info.tone,
        onChange: (v) => updateField("tone", v),
        multi: true,
        list: PROJECT_EP_TONE_OPTIONS
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u5149\u7167", "Lighting"),
        value: info.lighting,
        onChange: (v) => updateField("lighting", v),
        multi: true,
        list: PROJECT_EP_LIGHTING_OPTIONS
      }
    )), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u767E\u5B57\u5267\u60C5\u603B\u7ED3", "Plot Summary (100 chars)"),
        value: info.plot_summary,
        onChange: (v) => updateField("plot_summary", v),
        multi: true,
        placeholder: t("80-120\u5B57\u6982\u62EC\u6838\u5FC3\u5267\u60C5\u3001\u4EBA\u7269\u5173\u7CFB\u4E0E\u60C5\u611F\u8D70\u5411", "80-120 chars summarizing plot, relationships, and emotional arc")
      }
    ), /* @__PURE__ */ React.createElement(
      InputGroup,
      {
        idPrefix: prefix,
        label: t("\u914D\u4E50\u63A8\u8350", "Music Recommendation"),
        value: info.music_recommendation,
        onChange: (v) => updateField("music_recommendation", v),
        multi: true,
        placeholder: t("\u914D\u4E50\u98CE\u683C\u3001\u60C5\u7EEA\u57FA\u8C03\u3001\u53C2\u8003\u66F2\u76EE/\u4F5C\u66F2\u5BB6\u53CA\u4E3B\u8981\u4F7F\u7528\u573A\u666F", "Score style, mood, reference tracks/composers, and key usage scenes")
      }
    ))
  ))), mode === "overview" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 rounded-xl overflow-hidden xl:col-span-2" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => toggleSection("review"),
      className: "w-full flex items-start sm:items-center justify-between p-4 sm:p-6 bg-white/5 hover:bg-white/10 transition-colors"
    },
    /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row sm:items-center gap-3 text-left" }, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary m-0" }, t("\u9879\u76EE\u5BA1\u6838\u534F\u4F5C", "Project Review Collaboration")), /* @__PURE__ */ React.createElement("p", { className: "m-0 text-sm text-muted-foreground hidden sm:block" }, t("\u53EF\u76F4\u63A5\u4ECE\u9879\u76EE\u603B\u89C8\u53D1\u8D77\u8D44\u4EA7/\u955C\u5934\u5BA1\u6838\uFF0C\u4E0D\u5FC5\u56DE\u5230\u9879\u76EE\u5217\u8868\u3002", "Create asset and shot review requests directly from project overview without returning to the project list."))),
    /* @__PURE__ */ React.createElement(ChevronDown, { className: `w-5 h-5 shrink-0 mt-1 sm:mt-0 transition-transform ${expandedSections.review ? "rotate-180" : ""}` })
  ), /* @__PURE__ */ React.createElement(AnimatePresence, { initial: false }, expandedSections.review && /* @__PURE__ */ React.createElement(
    motion.div,
    {
      initial: { height: 0, opacity: 0 },
      animate: { height: "auto", opacity: 1 },
      exit: { height: 0, opacity: 0 },
      transition: { duration: 0.3, ease: "easeInOut" },
      className: "border-t border-white/10"
    },
    /* @__PURE__ */ React.createElement("div", { className: "p-4 sm:p-6 space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between pb-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "rounded-full border border-white/10 px-3 py-1 text-xs text-muted-foreground" }, t(`\u7EBF\u7A0B ${projectReviewThreads.length}`, `Threads ${projectReviewThreads.length}`)), /* @__PURE__ */ React.createElement("span", { className: `rounded-full px-3 py-1 text-xs font-semibold ${quickReviewUnreadCount > 0 ? "bg-amber-500 text-black" : "border border-white/10 text-muted-foreground"}` }, t(`\u672A\u8BFB ${quickReviewUnreadCount}`, `Unread ${quickReviewUnreadCount}`)))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr_1.05fr]" }, /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-white/10 bg-black/20 p-4 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold" }, t("\u5FEB\u901F\u53D1\u8D77\u5BA1\u6838", "Quick Review Request")), /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
      "input",
      {
        value: quickReviewDraft.reviewer_user,
        onChange: (e) => setQuickReviewDraft((prev) => ({ ...prev, reviewer_user: e.target.value })),
        placeholder: t("\u8F93\u5165\u5BA1\u6838\u4EBA\u7528\u6237\u540D\u6216\u90AE\u7BB1", "Enter reviewer username or email"),
        className: "w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
      }
    )), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: quickReviewDraft.title,
        onChange: (e) => setQuickReviewDraft((prev) => ({ ...prev, title: e.target.value })),
        placeholder: t("\u5BA1\u6838\u6807\u9898\uFF0C\u53EF\u9009", "Review title, optional"),
        className: "w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
      }
    ), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        value: quickReviewDraft.request_message,
        onChange: (e) => setQuickReviewDraft((prev) => ({ ...prev, request_message: e.target.value })),
        placeholder: t("\u5199\u660E\u672C\u6B21\u5BA1\u6838\u76EE\u6807\u3001\u6CE8\u610F\u70B9\u4E0E\u622A\u6B62\u8981\u6C42", "Describe goals, focus points, and deadline expectations for this review"),
        className: "w-full h-28 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-4 text-sm text-muted-foreground" }, /* @__PURE__ */ React.createElement("label", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        checked: !!quickReviewDraft.entity_required,
        onChange: (e) => setQuickReviewDraft((prev) => ({ ...prev, entity_required: e.target.checked }))
      }
    ), t("\u8D44\u4EA7\u5BA1\u6838", "Asset Review")), /* @__PURE__ */ React.createElement("label", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        checked: !!quickReviewDraft.shot_required,
        onChange: (e) => setQuickReviewDraft((prev) => ({ ...prev, shot_required: e.target.checked }))
      }
    ), t("\u955C\u5934\u5BA1\u6838", "Shot Review"))), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: handleCreateQuickProjectReview,
        disabled: isReviewPanelSubmitting || isReviewPanelLoading,
        className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-2 ${isReviewPanelSubmitting || isReviewPanelLoading ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`
      },
      isReviewPanelSubmitting ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u53D1\u8D77\u4E2D...", "Creating...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Users, { className: "w-4 h-4" }), " ", t("\u53D1\u8D77\u5BA1\u6838", "Create Review"))
    ), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u53EF\u76F4\u63A5\u8F93\u5165\u4EFB\u610F\u5DF2\u5B58\u5728\u7528\u6237\u7684\u7528\u6237\u540D\u6216\u90AE\u7BB1\uFF1B\u82E5\u9879\u76EE\u4F5C\u8005\u6307\u5B9A\u4E86\u65B0\u5BA1\u6838\u4EBA\uFF0C\u7CFB\u7EDF\u4F1A\u81EA\u52A8\u6388\u4E88 reviewer \u8BBF\u95EE\u3002", "You can directly enter any existing username or email; when the project owner assigns a new reviewer, reviewer access will be granted automatically."))), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-white/10 bg-black/20 p-4 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold" }, t("\u6700\u8FD1\u5BA1\u6838\u7EBF\u7A0B", "Recent Review Threads")), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: loadProjectReviewPanel,
        disabled: isReviewPanelLoading,
        className: "px-3 py-1.5 rounded-lg text-xs font-medium bg-white/10 text-white hover:bg-white/20 disabled:opacity-50"
      },
      isReviewPanelLoading ? t("\u5237\u65B0\u4E2D...", "Refreshing...") : t("\u5237\u65B0", "Refresh")
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 gap-4 xl:grid-cols-[0.85fr_1.15fr]" }, /* @__PURE__ */ React.createElement("div", { className: "space-y-2 max-h-96 overflow-auto pr-1" }, isReviewPanelLoading && projectReviewThreads.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, t("\u52A0\u8F7D\u4E2D...", "Loading...")) : projectReviewThreads.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, t("\u6682\u65E0\u5BA1\u6838\u7EBF\u7A0B", "No review threads yet")) : projectReviewThreads.slice(0, 8).map((thread) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: `editor-review-thread-${thread.id}`,
        onClick: () => loadQuickReviewThreadDetail(thread.id),
        className: `w-full rounded-lg border p-3 text-left transition ${Number(selectedQuickReviewThreadId) === Number(thread.id) ? "border-primary/40 bg-primary/10" : "border-white/10 bg-black/30 hover:bg-white/5"}`
      },
      /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("div", { className: "truncate text-sm font-medium text-white" }, thread.title || `${t("\u5BA1\u6838\u7EBF\u7A0B", "Review Thread")} #${thread.id}`), /* @__PURE__ */ React.createElement("div", { className: "mt-1 text-xs text-muted-foreground" }, thread.requester_username || "-", " \u2192 ", thread.reviewer_username || "-")), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col items-end gap-1" }, thread.has_unread && /* @__PURE__ */ React.createElement("span", { className: "rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-semibold text-black" }, t("\u672A\u8BFB", "Unread")), /* @__PURE__ */ React.createElement("span", { className: "rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-muted-foreground" }, thread.status || "open")))
    ))), /* @__PURE__ */ React.createElement("div", { className: "rounded-lg border border-white/10 bg-black/30 p-3" }, !selectedQuickReviewThreadId ? /* @__PURE__ */ React.createElement("div", { className: "flex min-h-56 items-center justify-center text-sm text-muted-foreground" }, t("\u9009\u62E9\u4E00\u4E2A\u5BA1\u6838\u7EBF\u7A0B\u67E5\u770B\u8BE6\u60C5\u5E76\u76F4\u63A5\u56DE\u590D\u3002", "Select a review thread to inspect details and reply directly.")) : (() => {
      const selectedThread = projectReviewThreads.find((item) => Number(item.id) === Number(selectedQuickReviewThreadId));
      const selectedRound = selectedQuickReviewRounds.find((item) => Number(item.id) === Number(selectedQuickReviewRoundId)) || selectedQuickReviewRounds[selectedQuickReviewRounds.length - 1] || null;
      const amReviewer = Number(currentUserId || 0) === Number(selectedThread?.reviewer_user_id || 0);
      return /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "border-b border-white/10 pb-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white" }, selectedThread?.title || `${t("\u5BA1\u6838\u7EBF\u7A0B", "Review Thread")} #${selectedThread?.id || ""}`), isQuickReviewDetailLoading && /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin text-muted-foreground" })), /* @__PURE__ */ React.createElement("div", { className: "mt-1 text-xs text-muted-foreground" }, selectedThread?.requester_username || "-", " \u2192 ", selectedThread?.reviewer_username || "-")), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, selectedQuickReviewRounds.map((round) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: `editor-round-${round.id}`,
          onClick: () => handleSelectQuickReviewRound(round.id),
          className: `rounded-full px-3 py-1 text-xs transition ${Number(selectedQuickReviewRoundId) === Number(round.id) ? "bg-primary text-primary-foreground" : "bg-white/10 text-muted-foreground hover:text-white"}`
        },
        "#",
        round.round_no
      ))), selectedRound && /* @__PURE__ */ React.createElement("div", { className: "rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-muted-foreground space-y-2" }, selectedRound.request_message && /* @__PURE__ */ React.createElement("div", null, selectedRound.request_message), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-4" }, selectedRound.entity_required && /* @__PURE__ */ React.createElement("span", null, t("\u8D44\u4EA7", "Asset"), ": ", selectedRound.entity_decision || "pending"), selectedRound.shot_required && /* @__PURE__ */ React.createElement("span", null, t("\u955C\u5934", "Shot"), ": ", selectedRound.shot_decision || "pending")), selectedRound.entity_feedback && /* @__PURE__ */ React.createElement("div", null, t("\u8D44\u4EA7\u610F\u89C1", "Asset feedback"), ": ", selectedRound.entity_feedback), selectedRound.shot_feedback && /* @__PURE__ */ React.createElement("div", null, t("\u955C\u5934\u610F\u89C1", "Shot feedback"), ": ", selectedRound.shot_feedback)), /* @__PURE__ */ React.createElement("div", { className: "max-h-48 space-y-2 overflow-auto pr-1" }, selectedQuickReviewMessages.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, t("\u6682\u65E0\u6D88\u606F", "No messages")) : selectedQuickReviewMessages.map((message) => /* @__PURE__ */ React.createElement("div", { key: `editor-review-msg-${message.id}`, className: "rounded-lg border border-white/10 bg-black/20 p-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-2 text-xs text-muted-foreground" }, /* @__PURE__ */ React.createElement("span", null, message.sender_username || "-"), /* @__PURE__ */ React.createElement("span", null, message.sender_role === "reviewer" ? t("\u5BA1\u6838\u65B9", "Reviewer") : t("\u53D1\u8D77\u65B9", "Requester"))), message.message_text && /* @__PURE__ */ React.createElement("div", { className: "mt-1 text-sm text-white" }, message.message_text), /* @__PURE__ */ React.createElement("div", { className: "mt-2 grid gap-1 text-xs text-muted-foreground" }, message.entity_decision && message.entity_decision !== "pending" && /* @__PURE__ */ React.createElement("div", null, t("\u8D44\u4EA7\u7ED3\u8BBA", "Asset decision"), ": ", message.entity_decision), message.shot_decision && message.shot_decision !== "pending" && /* @__PURE__ */ React.createElement("div", null, t("\u955C\u5934\u7ED3\u8BBA", "Shot decision"), ": ", message.shot_decision), message.entity_feedback && /* @__PURE__ */ React.createElement("div", null, t("\u8D44\u4EA7\u610F\u89C1", "Asset feedback"), ": ", message.entity_feedback), message.shot_feedback && /* @__PURE__ */ React.createElement("div", null, t("\u955C\u5934\u610F\u89C1", "Shot feedback"), ": ", message.shot_feedback))))), selectedRound && /* @__PURE__ */ React.createElement("div", { className: "space-y-3 border-t border-white/10 pt-3" }, /* @__PURE__ */ React.createElement(
        "textarea",
        {
          value: quickReviewReplyDraft.message_text,
          onChange: (e) => setQuickReviewReplyDraft((prev) => ({ ...prev, message_text: e.target.value })),
          placeholder: amReviewer ? t("\u586B\u5199\u5BA1\u6838\u56DE\u590D\u4E0E\u7ED3\u8BBA", "Add review reply and decisions") : t("\u586B\u5199\u8865\u5145\u8BF4\u660E\u6216\u56DE\u5E94", "Add follow-up notes or response"),
          className: "w-full h-24 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
        }
      ), amReviewer && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 gap-3 md:grid-cols-2" }, selectedRound.entity_required && /* @__PURE__ */ React.createElement(
        "select",
        {
          value: quickReviewReplyDraft.entity_decision,
          onChange: (e) => setQuickReviewReplyDraft((prev) => ({ ...prev, entity_decision: e.target.value })),
          className: "rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
        },
        /* @__PURE__ */ React.createElement("option", { value: "pending" }, t("\u8D44\u4EA7\u5F85\u5B9A", "Asset pending")),
        /* @__PURE__ */ React.createElement("option", { value: "approved" }, t("\u8D44\u4EA7\u901A\u8FC7", "Asset approved")),
        /* @__PURE__ */ React.createElement("option", { value: "conditional" }, t("\u8D44\u4EA7\u6709\u6761\u4EF6\u901A\u8FC7", "Asset conditional")),
        /* @__PURE__ */ React.createElement("option", { value: "rejected" }, t("\u8D44\u4EA7\u4E0D\u901A\u8FC7", "Asset rejected"))
      ), selectedRound.shot_required && /* @__PURE__ */ React.createElement(
        "select",
        {
          value: quickReviewReplyDraft.shot_decision,
          onChange: (e) => setQuickReviewReplyDraft((prev) => ({ ...prev, shot_decision: e.target.value })),
          className: "rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
        },
        /* @__PURE__ */ React.createElement("option", { value: "pending" }, t("\u955C\u5934\u5F85\u5B9A", "Shot pending")),
        /* @__PURE__ */ React.createElement("option", { value: "approved" }, t("\u955C\u5934\u901A\u8FC7", "Shot approved")),
        /* @__PURE__ */ React.createElement("option", { value: "conditional" }, t("\u955C\u5934\u6709\u6761\u4EF6\u901A\u8FC7", "Shot conditional")),
        /* @__PURE__ */ React.createElement("option", { value: "rejected" }, t("\u955C\u5934\u4E0D\u901A\u8FC7", "Shot rejected"))
      )), selectedRound.entity_required && /* @__PURE__ */ React.createElement(
        "textarea",
        {
          value: quickReviewReplyDraft.entity_feedback,
          onChange: (e) => setQuickReviewReplyDraft((prev) => ({ ...prev, entity_feedback: e.target.value })),
          placeholder: t("\u8D44\u4EA7\u5BA1\u6838\u610F\u89C1", "Asset review feedback"),
          className: "w-full h-20 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
        }
      ), selectedRound.shot_required && /* @__PURE__ */ React.createElement(
        "textarea",
        {
          value: quickReviewReplyDraft.shot_feedback,
          onChange: (e) => setQuickReviewReplyDraft((prev) => ({ ...prev, shot_feedback: e.target.value })),
          placeholder: t("\u955C\u5934\u5BA1\u6838\u610F\u89C1", "Shot review feedback"),
          className: "w-full h-20 resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none"
        }
      )), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: handleCreateQuickReviewReply,
          disabled: isReviewPanelSubmitting,
          className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-2 ${isReviewPanelSubmitting ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`
        },
        isReviewPanelSubmitting ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u53D1\u9001\u4E2D...", "Sending...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, t("\u53D1\u9001\u56DE\u590D", "Send Reply"))
      )));
    })())), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u66F4\u5B8C\u6574\u7684\u8F6E\u6B21\u7BA1\u7406\u3001\u72B6\u6001\u53D8\u66F4\u548C\u5F52\u6863\u4ECD\u5728\u9879\u76EE\u5217\u8868\u7684\u201C\u9879\u76EE\u534F\u4F5C\u201D\u5DE5\u4F5C\u53F0\u4E2D\u3002", "Full round management, status changes, and archiving remain in the project collaboration workspace on the project list page.")))))
  ))), mode === "generator" && projectTab === "story_generator" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 p-4 sm:p-6 rounded-xl space-y-4 xl:col-span-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u6545\u4E8B\u751F\u6210\u5668\uFF08\u5168\u5C40 / \u9879\u76EE\uFF09", "Story Generator (Global / Project)")), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleGenerateGlobalStory,
      disabled: isGeneratingGlobalStory,
      className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingGlobalStory ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`,
      title: t("\u751F\u6210\u56FD\u9645\u5316\u7206\u6B3E\u6545\u4E8B\u6846\u67B6\u5E76\u4FDD\u5B58\u5230\u9879\u76EE\u603B\u89C8", "Generate an international-blockbuster story framework and store it in project Overview")
    },
    isGeneratingGlobalStory ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u751F\u6210\u4E2D...", "Generating...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Sparkles, { className: "w-4 h-4" }), " ", t("\u751F\u6210\u5168\u5C40\u6846\u67B6", "Generate Global Framework"))
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleGenerateEpisodeScripts,
      disabled: episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts,
      className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`,
      title: t("\u4ECE\u5168\u5C40\u6846\u67B6 + \u9879\u76EE\u89D2\u8272\u8BBE\u5B9A\u751F\u6210\u5206\u96C6\u5267\u672C\uFF0C\u81EA\u52A8\u521B\u5EFA\u7F3A\u5931\u5206\u96C6\u5E76\u5199\u5165\u5BF9\u5E94\u5206\u96C6", "Generate episode scripts from Global Framework + Project Character Canon, create missing episodes, and save each script into its episode")
    },
    episodeScriptsRunning ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u751F\u6210\u4E2D...", "Generating...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Wand2, { className: "w-4 h-4" }), " ", t("\u5168\u91CF\u751F\u6210\u5206\u96C6", "Generate All"))
  ), /* @__PURE__ */ React.createElement("div", { className: "flex items-center bg-white/5 rounded-lg overflow-hidden border border-white/10" }, /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "number",
      min: "1",
      placeholder: t("\u5355\u96C6", "Ep#"),
      className: "w-16 px-2 py-2 bg-transparent text-sm text-center outline-none text-white placeholder-white/30",
      value: targetEpisodeNumberForGen,
      onChange: (e) => setTargetEpisodeNumberForGen(e.target.value),
      disabled: episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts
    }
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => handleGenerateEpisodeScripts({ specificEpisode: targetEpisodeNumberForGen }),
      disabled: !targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts,
      className: `px-3 py-2 text-sm font-bold flex items-center bg-white/10 hover:bg-white/20 transition-colors ${!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts ? "opacity-50 cursor-not-allowed" : "text-blue-300"}`,
      title: t("\u4EC5\u751F\u6210\u586B\u5199\u7684\u5355\u4E2A\u96C6\u6570", "Generate only the specified episode number")
    },
    t("\u5355\u96C6\u751F\u6210", "Gen Single")
  )), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleStopEpisodeScripts,
      disabled: isStoppingEpisodeScripts,
      className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isStoppingEpisodeScripts ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-red-500/20 text-red-200 hover:bg-red-500/30"}`,
      title: t("\u5F3A\u5236\u505C\u6B62\u5F53\u524D\u6279\u91CF\u5206\u96C6\u5267\u672C\u4EFB\u52A1", "Force stop current batch episode scripts task")
    },
    isStoppingEpisodeScripts ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u505C\u6B62\u4E2D...", "Stopping...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(X, { className: "w-4 h-4" }), " ", t("\u5F3A\u5236\u505C\u6B62", "Force Stop"))
  ))), episodeScriptsProgress && /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20 space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground uppercase tracking-wide" }, t("\u5206\u96C6\u5267\u672C\u8FDB\u5EA6\u5FEB\u7167", "Episode Scripts Progress Snapshot")), /* @__PURE__ */ React.createElement("div", { className: "h-2 rounded bg-white/10 overflow-hidden" }, /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "h-2 bg-primary",
      style: { width: `${progressPercent}%` }
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "text-sm text-white flex flex-wrap gap-x-4 gap-y-1" }, /* @__PURE__ */ React.createElement("span", null, t("\u72B6\u6001", "Status"), ": ", /* @__PURE__ */ React.createElement("b", null, episodeScriptsProgress.running ? t("\u8FD0\u884C\u4E2D", "Running") : t("\u7A7A\u95F2", "Idle"))), episodeScriptsProgress.stop_requested ? /* @__PURE__ */ React.createElement("span", null, t("\u505C\u6B62\u8BF7\u6C42", "Stop Requested"), ": ", /* @__PURE__ */ React.createElement("b", null, t("\u662F", "Yes"))) : null, /* @__PURE__ */ React.createElement("span", null, t("\u5DF2\u5904\u7406", "Processed"), ": ", /* @__PURE__ */ React.createElement("b", null, processedCount), " / ", /* @__PURE__ */ React.createElement("b", null, episodesInRun)), /* @__PURE__ */ React.createElement("span", null, t("\u5DF2\u751F\u6210", "Generated"), ": ", /* @__PURE__ */ React.createElement("b", null, episodeScriptsProgress.generated || 0)), /* @__PURE__ */ React.createElement("span", null, t("\u5931\u8D25", "Failed"), ": ", /* @__PURE__ */ React.createElement("b", null, episodeScriptsProgress.failed || 0)), /* @__PURE__ */ React.createElement("span", null, t("\u8DF3\u8FC7", "Skipped"), ": ", /* @__PURE__ */ React.createElement("b", null, episodeScriptsProgress.skipped || 0))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 pt-1" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => setShowEpisodeScriptsProgressModal(true),
      className: "px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20"
    },
    t("\u67E5\u770B\u8BE6\u60C5", "View Details")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: pollEpisodeScriptsStatus,
      className: "px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-1.5"
    },
    /* @__PURE__ */ React.createElement(RefreshCw, { className: "w-3.5 h-3.5" }),
    " ",
    t("\u5237\u65B0", "Refresh")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleStopEpisodeScripts,
      disabled: isStoppingEpisodeScripts,
      className: `px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1.5 ${isStoppingEpisodeScripts ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-red-500/20 text-red-200 hover:bg-red-500/30"}`
    },
    isStoppingEpisodeScripts ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-3.5 h-3.5 animate-spin" }), " ", t("\u505C\u6B62\u4E2D...", "Stopping...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(X, { className: "w-3.5 h-3.5" }), " ", t("\u5F3A\u5236\u505C\u6B62", "Force Stop"))
  ))), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2 rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white" }, t("\u81EA\u52A8\u7EE7\u627F\u7684\u9879\u76EE\u4FE1\u606F", "Inherited Project Info")), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground mt-1" }, t("\u6545\u4E8B\u751F\u6210\u5668\u4F1A\u81EA\u52A8\u8BFB\u53D6\u9879\u76EE\u6982\u89C8\u91CC\u7684\u57FA\u7840\u4FE1\u606F\uFF0C\u8FD9\u91CC\u53EA\u9700\u8981\u8865\u6545\u4E8B\u9AA8\u67B6\uFF0C\u4E0D\u9700\u8981\u91CD\u590D\u8F93\u5165\u5DF2\u6709\u9879\u76EE\u5B57\u6BB5\u3002", "The Story Generator automatically reuses Project Overview info. Only fill the story skeleton here; no need to repeat existing project fields."))), storyGeneratorMissingInfo.length > 0 ? /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => {
        setProjectTab("overview");
        if (onTabChange) onTabChange("overview");
      },
      className: "px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20"
    },
    t("\u53BB\u9879\u76EE\u6982\u89C8\u8865\u9F50", "Complete in Overview")
  ) : null), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm" }, storyGeneratorInheritedInfo.map((item) => /* @__PURE__ */ React.createElement("div", { key: item.label, className: "rounded-lg border border-white/10 bg-black/20 px-3 py-2" }, /* @__PURE__ */ React.createElement("div", { className: "text-[11px] uppercase tracking-wide text-muted-foreground" }, item.label), /* @__PURE__ */ React.createElement("div", { className: item.value ? "text-white mt-1" : "text-muted-foreground mt-1" }, item.value || t("\u672A\u8BBE\u7F6E\uFF0C\u5C06\u53EA\u5728\u7F3A\u5931\u65F6\u81EA\u52A8\u63A8\u65AD", "Not set. It will only be inferred when still missing.")))))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u8F7D\u4F53\u89C4\u683C / \u96C6\u6570", "Format / Episodes")), /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "number",
      min: "1",
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
      value: globalStoryInput.episodes_count,
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, episodes_count: e.target.value })),
      placeholder: t("\u4F8B\u5982\uFF1A20", "e.g. 20")
    }
  )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u6BCF\u96C6\u65F6\u957F\uFF08\u5206\u949F\uFF09", "Episode Duration (min)")), /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "number",
      min: "1",
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
      value: globalStoryInput.episode_duration_minutes,
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, episode_duration_minutes: e.target.value })),
      placeholder: t("\u4F8B\u5982\uFF1A1", "e.g. 1")
    }
  )), /* @__PURE__ */ React.createElement(
    InputGroup,
    {
      idPrefix: prefix,
      label: t("\u4EA7\u54C1\u89C4\u683C\u4E0E\u8282\u594F", "Product Format"),
      value: globalStoryInput.script_mode,
      onChange: (v) => setGlobalStoryInput((prev) => ({ ...prev, script_mode: v })),
      list: [
        "\u77ED\u5267\u5FEB\u8282\u594F / Short Drama",
        "\u7535\u5F71 / Feature Film",
        "\u901A\u7528\u8FDE\u7EED\u5267 / General Series"
      ]
    }
  ), /* @__PURE__ */ React.createElement(
    InputGroup,
    {
      idPrefix: prefix,
      label: t("\u53D7\u4F17\u5B9A\u4F4D", "Target Audience"),
      value: globalStoryInput.target_audience,
      onChange: (v) => setGlobalStoryInput((prev) => ({ ...prev, target_audience: v })),
      list: [
        "\u7537\u9891\u8DEF\u7EBF / Male-Oriented",
        "\u5973\u9891\u8DEF\u7EBF / Female-Oriented",
        "\u5168\u53D7\u4F17 / General Audience"
      ]
    }
  ), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2 text-xs text-muted-foreground mb-1" }, t("\u5927\u6A21\u578B\u5C06\u6839\u636E\u3010\u4EA7\u54C1\u89C4\u683C\u3011\u4E25\u683C\u5957\u7528\u4E0D\u540C\u7684\u5DE5\u4E1A\u5316\u53D9\u4E8B\u8282\u594F\u4E0E\u8D77\u627F\u8F6C\u5408\u7ED3\u6784\uFF0C\u5E76\u9488\u5BF9\u3010\u53D7\u4F17\u5B9A\u4F4D\u3011\u6781\u5316\u6838\u5FC3\u770B\u70B9\u4E0E\u5F20\u529B\u3002", "The AI will apply distinct rhythmic and structural pacing based on the chosen Product Format and polarize constraints based on target audience."))), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2 rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold block" }, t("\u5929\u9A6C\u884C\u7A7A\u7684\u60F3\u6CD5", "Wild Ideas & Creative Prompt")), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground/80 mt-1" }, t("\u5148\u628A\u8111\u6D77\u4E2D\u7684\u753B\u9762\u3001\u53F0\u8BCD\u3001\u602A\u5FF5\u5934\u5012\u5728\u8FD9\u91CC\uFF1B\u70B9\u300C\u7ED3\u6784\u5316\u9884\u586B\u300D\u4F1A\u5148\u63D0\u53D6\u5173\u952E\u8981\u7D20\uFF0C\u518D\u641C\u7D22\u7ECF\u5178\u540D\u573A\u9762/\u70ED\u95E8\u6865\u6BB5/\u70ED\u95E8\u8BDD\u9898\uFF0C\u6700\u540E\u9884\u586B I1\u2013I9\u3002", "Pour raw scenes, lines, and quirky ideas here; Structure extracts key elements, searches classic scenes/tropes/hot topics, then prefills I1\u2013I9."))), /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: handleStructureCreativeInput,
      disabled: isStructuringCreativeInput || isGeneratingGlobalStory,
      className: `shrink-0 px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 ${isStructuringCreativeInput || isGeneratingGlobalStory ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-primary/20 text-primary hover:bg-primary/30"}`,
      title: t("\u63D0\u53D6\u5173\u952E\u8981\u7D20 \u2192 \u641C\u7D22\u9AD8\u6F6E/\u540D\u573A\u9762\u53C2\u8003\uFF08\u753B\u9762\xB7\u5BF9\u767D\xB7\u52A8\u4F5C\uFF09\u2192 \u9884\u586B I1\u2013I9", "Extract key elements \u2192 search climax/iconic references (visual/dialogue/action) \u2192 prefill I1\u2013I9")
    },
    isStructuringCreativeInput ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-3.5 h-3.5 animate-spin" }), " ", t("\u68C0\u7D22\u5206\u6790\u4E2D...", "Researching...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Wand2, { className: "w-3.5 h-3.5" }), " ", t("\u7ED3\u6784\u5316\u9884\u586B", "Structure & Prefill"))
  )), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-32 resize-none placeholder:text-white/25",
      value: globalStoryInput.wild_creative_notes,
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, wild_creative_notes: e.target.value })),
      placeholder: t(
        "\u5C3D\u60C5\u8F93\u5165\u8111\u6D1E\u4E0E\u540D\u573A\u9762\u8BBE\u60F3\uFF0C\u4F8B\u5982\uFF1A\u7EDD\u75C7\u6740\u624B\u66FF\u5973\u513F\u590D\u4EC7\uFF1B\u53CC\u91CD\u4EBA\u683C\u6740\u4EBA\u524D\u5FC5\u542C\u8D1D\u591A\u82AC\uFF1B\u5F00\u5934\u76F4\u5347\u673A\u53CD\u6740\uFF1B\u9AD8\u6F6E\u96E8\u4E2D\u5DE5\u5382\u5144\u5F1F\u53CD\u76EE\u3001\u7ECF\u5178\u53F0\u8BCD\u300C\u6211\u4EEC\u90FD\u56DE\u4E0D\u53BB\u4E86\u300D\u2026",
        'Wild ideas + iconic scenes: dying assassin avenges daughter; dual-personality killer listens to Beethoven; helicopter opening; rainy factory climax with line "We can never go back"\u2026'
      )
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2 rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white" }, t("\u8111\u6D1E\u6807\u51C6\u8F93\u5165\uFF08I1\u2013I9\uFF09", "Creative Input (I1\u2013I9)")), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground mt-1" }, t("\u5148\u586B I1\u2013I3 \u5B9A\u8C03\uFF0C\u518D\u586B\u4E16\u754C\u3001\u4EBA\u7269\u4E0E\u5267\u60C5\uFF1B\u672A\u5F52\u7C7B\u788E\u7247\u653E I9\u3002\u6BCF\u680F\u4E0B\u65B9\u6709\u7B80\u8981\u793A\u4F8B\uFF08\u7070\u8272\uFF09\uFF0C\u53EF\u4F5C placeholder \u53C2\u8003\u3002", "Fill I1\u2013I3 first, then world/characters/plot; fragments in I9. Each field has a brief example below."))), [
    {
      id: "logline",
      label: t("I1 \u9AD8\u6982\u5FF5 Logline", "I1 Logline / High Concept"),
      hint: t(
        "\u9AD8\u6982\u5FF5 = 3 \u79D2\u8BA9\u4EBA\u61C2\u300C\u8FD9\u662F\u4EC0\u4E48\u6545\u4E8B\u3001\u72EC\u7279\u5728\u54EA\u3001\u4E3A\u4EC0\u4E48\u8981\u770B\u300D\u3002\u5199\u72EC\u7279\u94A9\u5B50+\u56F0\u5883/\u76EE\u6807+\u53D8\u6570\uFF1B\u4E0D\u5199\u4E3B\u9898\uFF08I2\uFF09\u548C\u77DB\u76FE\u7EC6\u8282\uFF08I3\uFF09\u3002",
        "High concept = in 3 seconds: what story, what's unique, why watch. Hook + dilemma/goal + twist; not theme (I2) or conflict detail (I3)."
      ),
      example: t(
        "\u4F8B\uFF1A\u80FD\u770B\u89C1\u300C\u6B7B\u4EA1\u5012\u8BA1\u65F6\u300D\u7684\u5B9E\u4E60\u5F8B\u5E08\uFF0C\u5FC5\u987B\u5728\u88AB\u5F53\u6210\u75AF\u5B50\u4E4B\u524D\uFF0C\u6551\u4E0B\u5C06\u88AB\u8C0B\u6740\u7684\u4E0A\u53F8\u3002",
        "e.g. An intern lawyer who sees death countdowns must save her boss from murder before being labeled insane."
      ),
      rows: 2
    },
    {
      id: "theme",
      label: t("I2 \u4E3B\u9898\u4E0E\u4E3B\u63A7\u601D\u60F3", "I2 Theme / Controlling Idea"),
      hint: t("\u672C\u5267\u6700\u7EC8\u8981\u8BC1\u660E\u4EC0\u4E48\u4EF7\u503C/\u4EBA\u6027\u547D\u9898\uFF08Controlling Idea\uFF09", "What value or human truth the story ultimately proves"),
      example: t(
        "\u4F8B\uFF1A\u5F53\u771F\u76F8\u4E0E\u5FE0\u8BDA\u51B2\u7A81\u65F6\uFF0C\u9009\u62E9\u771F\u76F8\u624D\u80FD\u6551\u4EBA\uFF1B\u5305\u5E87\u53EA\u4F1A\u8BA9\u7CFB\u7EDF\u4E00\u8D77\u5D29\u584C\u3002",
        "e.g. When truth conflicts with loyalty, only truth saves lives; cover-ups collapse the system."
      ),
      rows: 2
    },
    {
      id: "core_conflict",
      label: t("I3 \u6838\u5FC3\u77DB\u76FE\xB7\u8D4C\u6CE8", "I3 Core Conflict & Stakes"),
      hint: t("\u4E0D\u53EF\u8C03\u548C\u5BF9\u7ACB + \u5931\u8D25\u4EE3\u4EF7 + \u884C\u52A8\u4E3A\u4F55\u9002\u5F97\u5176\u53CD\uFF08Gap\uFF09", "Irreconcilable opposition + stakes + why actions backfire"),
      example: t(
        "\u4F8B\uFF1A\u6797\u4E00 vs \u96C6\u56E2\u5C01\u53E3\u4F53\u7CFB+\u771F\u51F6\uFF1B\u8D4C\u6CE8\uFF1A\u804C\u4E1A\u4E0E\u751F\u547D\uFF1B\u6BCF\u67E5\u4E00\u6B65\u5BA1\u8BA1\u903C\u8FD1\u4E00\u6B65\uFF0C\u8C03\u67E5\u672C\u8EAB\u89E6\u53D1\u706D\u53E3\u3002",
        "e.g. Lin vs corporate cover-up + killer; stakes: career and life; each probe triggers audit and retaliation."
      ),
      rows: 3
    },
    {
      id: "background",
      label: t("I4 \u4E16\u754C\u4E0E\u80CC\u666F", "I4 World & Background"),
      hint: t("\u65F6\u4EE3/\u5730\u70B9/\u89C4\u5219/\u524D\u53F2/\u89C6\u89C9\u57FA\u8C03", "Era, place, rules, backstory, visual tone"),
      example: t(
        "\u4F8B\uFF1A2026 \u4E0A\u6D77\u8DE8\u56FD\u5F8B\u6240\uFF1B\u804C\u7EA7\u95E8\u7981+24h \u5BA1\u8BA1\uFF1B\u51B7\u5CFB\u90FD\u5E02\u5199\u5B9E\u3002",
        "e.g. 2026 Shanghai megafirm; tiered access + 24h audit logs; cold urban realism."
      ),
      rows: 3
    },
    {
      id: "characters",
      label: t("I5 \u6838\u5FC3\u4EBA\u7269", "I5 Characters & Relationships"),
      hint: t("\u4E3B\u89D2/\u5BF9\u624B/\u5173\u7CFB\uFF1B\u53EF\u5199 Ghost\xB7Need\xB7Want \u79CD\u5B50", "Protagonist, antagonist, ties; Ghost/Need/Want seeds"),
      example: t(
        "\u4F8B\uFF1A\u6797\u4E00\uFF1A\u5B9E\u4E60\u6CD5\u52A1\uFF0CNeed \u8FB9\u754C\uFF0CWant \u7559\u4EFB\u3002\u5468\u8587\uFF1A\u76DF\u53CB\u2192\u5BF9\u624B\u3002",
        "e.g. Lin Yi: intern, Need boundaries, Want to stay. Zhou Wei: ally\u2192foe."
      ),
      rows: 3
    }
  ].map((field) => /* @__PURE__ */ React.createElement("div", { key: field.id }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, field.label), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground/80 mb-0.5" }, field.hint), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-primary/70 mb-1.5 italic" }, field.example), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25",
      rows: field.rows,
      placeholder: field.example,
      value: globalStoryInput[field.id] || "",
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, [field.id]: e.target.value }))
    }
  ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-3" }, [
    {
      id: "setup",
      label: t("I6a \u5F00\u5C40\u4E0E\u6FC0\u52B1", "I6a Opening & Inciting"),
      hint: t("\u5F00\u573A\u753B\u9762 + \u6FC0\u52B1\u4E8B\u4EF6 + \u6253\u7834\u65E5\u5E38", "Opening image + inciting incident"),
      example: t(
        "\u4F8B\uFF1A\u6668\u4F1A\u9001\u6587\u4EF6\u8BEF\u62FF\u5361\u5957\u2192\u603B\u88C1\u7535\u68AF\u5F00\u95E8\u2192\u770B\u89C1\u672A\u7F72\u540D\u89E3\u96C7\u4FE1\u3002",
        "e.g. Wrong badge case at morning handoff \u2192 CEO elevator opens \u2192 unsigned termination letter."
      ),
      rows: 3
    },
    {
      id: "development",
      label: t("I6b \u4E2D\u6BB5\u5347\u7EA7", "I6b Mid Arc Escalation"),
      hint: t("\u53D7\u632B\u3001\u52A0\u7801\u3001\u526F\u7EBF\u3001\u538B\u529B\u5347\u7EA7", "Setbacks, escalation, B-story"),
      example: t(
        "\u4F8B\uFF1A\u4EBA\u4E8B\u7EA6\u8C08\u5047\u914D\u5408\u2192\u6697\u4E2D\u6BD4\u5BF9\u4FE1\u7EB8\u2192\u5468\u8587\u6697\u4E2D\u89C2\u5BDF\u3002",
        "e.g. HR interview feigned compliance \u2192 secret paper match \u2192 Zhou Wei watches."
      ),
      rows: 3
    },
    {
      id: "turning_points",
      label: t("I6c \u8F6C\u6298\u4E0E\u4E2D\u70B9", "I6c Turning Points"),
      hint: t("\u4E2D\u70B9\u53CD\u8F6C\u3001\u771F\u76F8\u63ED\u9732\u3001\u5C40\u52BF\u5931\u63A7", "Midpoint reversal, reveal, loss of control"),
      example: t(
        "\u4F8B\uFF1A\u4E2D\u70B9\uFF1A\u4FE1\u7EB8\u6765\u81EA\u603B\u88C1\u529E\uFF1B\u4FE1\u4EFB\u5D29\u584C\uFF1B\u4FDD\u5B89\u641C\u8EAB\u903C\u8FD1\u3002",
        "e.g. Midpoint: letter paper from CEO office; trust breaks; security search closes in."
      ),
      rows: 3
    }
  ].map((field) => /* @__PURE__ */ React.createElement("div", { key: field.id }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, field.label), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground/80 mb-0.5" }, field.hint), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-primary/70 mb-1.5 italic" }, field.example), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25",
      rows: field.rows,
      placeholder: field.example,
      value: globalStoryInput[field.id] || "",
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, [field.id]: e.target.value }))
    }
  )))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3" }, [
    {
      id: "climax",
      label: t("I7a \u9AD8\u6F6E\u4E0E\u540D\u573A\u9762", "I7a Climax & Must-Have Scenes"),
      hint: t("\u5FC5\u987B\u62CD\u51FA\u7684\u9AD8\u6F6E\u540D\u573A\u9762\uFF1A\u753B\u9762\u6784\u56FE\u3001\u5173\u952E\u5BF9\u767D\u3001\u52A8\u4F5C\u8D70\u4F4D", "Must-have climax/iconic scenes: visuals, key lines, action blocking"),
      example: t(
        "\u4F8B\uFF1A\u96E8\u591C\u5929\u53F0\u5BF9\u5CD9\uFF0C\u5DE5\u724C\u4F5C\u94A5\uFF0C\u5F53\u4F17\u64AD\u653E\u5077\u62CD\u89C6\u9891\u6362\u751F\u5B58\u3002",
        "e.g. Rainy rooftop standoff; badge as key; plays hidden video publicly to survive."
      ),
      rows: 3
    },
    {
      id: "resolution",
      label: t("I7b \u7ED3\u5C40\u4E0E\u6536\u5C3E", "I7b Ending & Resolution"),
      hint: t("\u7EC8\u5C40\u6001\u3001\u4EE3\u4EF7\u3001\u65B0\u5E38\u6001\u3001\u7EED\u96C6\u7559\u767D", "Final state, cost, new normal, sequel hook"),
      example: t(
        "\u4F8B\uFF1A\u771F\u51F6\u66DD\u5149\u4F46\u6797\u4E00\u88AB\u884C\u4E1A\u5C01\u6740\uFF1B\u7559\u767D\uFF1A\u5DE5\u724C\u6743\u9650\u8C01\u5F00\u7684\u3002",
        "e.g. Killer exposed but Lin blacklisted; hook: who granted badge access?"
      ),
      rows: 3
    }
  ].map((field) => /* @__PURE__ */ React.createElement("div", { key: field.id }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, field.label), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground/80 mb-0.5" }, field.hint), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-primary/70 mb-1.5 italic" }, field.example), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25",
      rows: field.rows,
      placeholder: field.example,
      value: globalStoryInput[field.id] || "",
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, [field.id]: e.target.value }))
    }
  )))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3" }, [
    {
      id: "suspense",
      label: t("I8a \u6838\u5FC3\u60AC\u5FF5", "I8a Core Suspense"),
      hint: t("\u89C2\u4F17\u8D2F\u7A7F\u5168\u5267\u60F3\u8FFD\u95EE\u7684\u95EE\u9898\uFF08\u4E0E I3 \u5BF9\u6297\u7ED3\u6784\u4E92\u8865\uFF09", "Core questions driving the season"),
      example: t(
        "\u4F8B\uFF1A\u8C01\u5199\u4E86\u89E3\u96C7\u4FE1\uFF1F\u8C01\u7ED9\u4E86\u6797\u4E00\u603B\u88C1\u6743\u9650\uFF1F",
        "e.g. Who wrote the letter? Who gave Lin CEO-level access?"
      ),
      rows: 2
    },
    {
      id: "foreshadowing",
      label: t("I8b \u4F0F\u7B14\u4E0E\u5FC5\u7559\u5143\u7D20", "I8b Foreshadowing & Must-Keep"),
      hint: t("\u5FC5\u4FDD\u7559\u53F0\u8BCD/\u9053\u5177/\u53CD\u8F6C/\u56DE\u6536\u7EA6\u675F", "Must-keep lines, props, payoffs"),
      example: t(
        "\u4F8B\uFF1A\u955C\u524D\u5DE5\u724C\u7279\u5199\uFF1B\u53F0\u8BCD\u300C\u8FD9\u6247\u95E8\u8BA4\u7684\u4E0D\u662F\u6211\u300D\uFF1B\u5DE5\u724C\u7EC8\u96C6\u518D\u89E6\u53D1\u95E8\u7981\u3002",
        `e.g. Mirror badge shot; line "This door knows a name I haven't met"; badge triggers access in finale.`
      ),
      rows: 2
    }
  ].map((field) => /* @__PURE__ */ React.createElement("div", { key: field.id }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, field.label), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground/80 mb-0.5" }, field.hint), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-primary/70 mb-1.5 italic" }, field.example), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full resize-none placeholder:text-white/25",
      rows: field.rows,
      placeholder: field.example,
      value: globalStoryInput[field.id] || "",
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, [field.id]: e.target.value }))
    }
  )))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("I9 \u81EA\u7531\u8111\u6D1E\u8865\u5145", "I9 Raw Creative Fragments")), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground/80 mb-0.5" }, t("\u753B\u9762/\u53F0\u8BCD/\u602A\u5FF5\u5934\u7B49\u672A\u5F52\u7C7B\u788E\u7247\uFF1B\u53EF\u7559\u7A7A", "Unsorted scenes, lines, ideas; optional")), /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-primary/70 mb-1.5 italic" }, t("\u4F8B\uFF1A\u5F00\u5934\u5012\u53D9\u5DE5\u724C\u7279\u5199\uFF1B\u96C6\u672B\u4FDD\u5B89\u4E0A\u95E8\u65AD\u70B9\uFF1B\u5144\u5F1F\u53CD\u76EE\u53F0\u8BCD\u300C\u6211\u4EEC\u90FD\u56DE\u4E0D\u53BB\u4E86\u300D\u3002", 'e.g. Cold-open badge close-up; cliffhanger security at door; line "We can never go back".')), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none placeholder:text-white/25",
      value: globalStoryInput.extra_notes,
      onChange: (e) => setGlobalStoryInput((prev) => ({ ...prev, extra_notes: e.target.value })),
      placeholder: t("\u4F8B\uFF1A\u5F00\u5934\u5012\u53D9\u5DE5\u724C\u7279\u5199\uFF1B\u96C6\u672B\u4FDD\u5B89\u4E0A\u95E8\u65AD\u70B9\u2026", "e.g. Cold-open badge close-up; cliffhanger security at door\u2026")
    }
  ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-1" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold block" }, t("\u5DF2\u751F\u6210\u5168\u5C40\u6846\u67B6\uFF08Markdown\uFF09", "Generated Global Framework (Markdown)")), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-1 bg-black/20 border border-white/10 rounded-md p-1" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => setStoryFrameworkViewMode("preview"),
      className: `px-2 py-1 rounded text-xs font-bold ${storyFrameworkViewMode === "preview" ? "bg-white text-black" : "text-white/80 hover:bg-white/10"}`
    },
    t("\u9884\u89C8", "Preview")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => setStoryFrameworkViewMode("edit"),
      className: `px-2 py-1 rounded text-xs font-bold ${storyFrameworkViewMode === "edit" ? "bg-white text-black" : "text-white/80 hover:bg-white/10"}`
    },
    t("\u7F16\u8F91", "Edit")
  ))), storyFrameworkViewMode === "edit" ? /* @__PURE__ */ React.createElement(
    "textarea",
    {
      ref: (el) => {
        if (el) {
          el.style.height = "auto";
          el.style.height = el.scrollHeight + "px";
        }
      },
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full min-h-[12rem] resize-none overflow-hidden",
      value: info.story_dna_global_md || "",
      onChange: (e) => updateField("story_dna_global_md", e.target.value),
      placeholder: t("\uFF08\u751F\u6210\u540E\uFF0C\u5168\u5C40\u6846\u67B6\u4F1A\u663E\u793A\u5728\u8FD9\u91CC\u3002\u4F60\u53EF\u4EE5\u7F16\u8F91\u540E\u4FDD\u5B58\u4FEE\u6539\u3002\uFF09", "(After generation, the global framework will appear here. You can edit it and Save Changes.)")
    }
  ) : /* @__PURE__ */ React.createElement("div", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-3 min-h-[12rem] overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1" }, (info.story_dna_global_md || "").trim() ? /* @__PURE__ */ React.createElement(ReactMarkdown, null, info.story_dna_global_md) : /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, t("\uFF08\u751F\u6210\u540E\uFF0C\u5168\u5C40\u6846\u67B6\u4F1A\u663E\u793A\u5728\u8FD9\u91CC\u3002\uFF09", "(After generation, the global framework will appear here.)")))), /* @__PURE__ */ React.createElement("div", { className: "mt-4 border border-white/10 rounded-xl bg-black/20 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between" }, /* @__PURE__ */ React.createElement("h4", { className: "text-sm font-bold text-white flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Activity, { className: "w-4 h-4 text-primary" }), " ", t("\u5267\u672C\u9875\u9762\u8BCA\u65AD\u4E0E\u72B6\u6001\u9762\u677F", "Generation Status & Diagnosis"))), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u57FA\u4E8E\u5F53\u524D\u8F93\u5165\u4E0E\u751F\u6210\u7684\u8BCA\u65AD\u8FFD\u8E2A\u3002", "Current status and output diagnostic tracking.")), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 text-sm" }, /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/30" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u5168\u5C40\u6846\u67B6\u72B6\u6001", "Framework Status")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, info.story_dna_global_md ? t("\u5DF2\u5EFA\u7ACB", "Established") : t("\u5F85\u8865\u5145", "Missing"))), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/30" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u521B\u610F\u6807\u51C6\u8F93\u5165(I1-I9)", "Creative I1-I9")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, globalStoryInput.logline ? t("\u5DF2\u586B\u6838\u5FC3", "Core Filled") : t("\u5F85\u7EC6\u5316", "Needs Detail"))), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/30" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u4E3B\u7EBF\u5206\u96C6\u751F\u6210", "Episodes Gen")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress?.running ? t("\u8FD0\u884C\u4E2D", "Running") : t("\u95F2\u7F6E\u72B6\u6001", "Idle"))), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/30" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u751F\u6210\u5206\u96C6\u6570\u91CF", "Episodes Target")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, globalStoryInput.episodes_count || 0, " \u96C6"))))), (mode === "market_research" || mode === "generator" && projectTab === "market_research") && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2" }, /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Layers, { className: "w-4 h-4 text-violet-300" }), t("\u8FD1\u4E24\u6708 AI \u77ED\u5267\u5E02\u573A\u60C5\u62A5", "AI Short Drama Market Intelligence (Last 2 Months)")), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground mt-1" }, t("\u4E00\u952E\u5E76\u884C\u62C9\u53D6\uFF1A\u70ED\u699C\u9898\u6750\u53D8\u5316\u5206\u6790 + \u70ED\u95E8\u4F5C\u54C1\u699C\u5355\uFF08\u542B\u9AD8\u6F6E/\u540D\u573A\u9762\xB7\u753B\u9762\xB7\u5BF9\u767D\xB7\u52A8\u4F5C\uFF09\u3002\u8054\u7F51\u68C0\u7D22\u540E\u7531\u5267\u672C\u5206\u6790 LLM \u5206\u522B\u6C47\u603B\uFF0C\u5E76\u6309\u65F6\u95F4\u5199\u5165\u6570\u636E\u5E93\uFF08\u641C\u7D22\u7ED3\u679C\u5FEB\u7167\uFF0C\u9700\u4EBA\u5DE5\u6838\u5BF9\uFF09\u3002", "One-click parallel fetch: genre-shift analysis + trending list with climax/iconic scenes. Web search + LLM synthesis; results are time-indexed and persisted (snapshot; verify before use)."))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 shrink-0" }, industryAnalysisReport?.markdown || trendingDramasReport?.markdown ? /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: handleAppendMarketResearchToWildIdeas,
      className: "px-3 py-2 rounded-lg text-xs font-bold bg-white/10 text-white hover:bg-white/20"
    },
    t("\u5F15\u7528\u5230\u5929\u9A6C\u884C\u7A7A", "Append to Wild Ideas")
  ) : null, /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: handleFetchMarketResearch,
      disabled: isFetchingMarketResearch || isGeneratingGlobalStory,
      className: `px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 ${isFetchingMarketResearch || isGeneratingGlobalStory ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-violet-500/20 text-violet-100 hover:bg-violet-500/30"}`
    },
    isFetchingMarketResearch ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-3.5 h-3.5 animate-spin" }), " ", t("\u83B7\u53D6\u4E2D...", "Fetching...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(RefreshCw, { className: "w-3.5 h-3.5" }), " ", t("\u83B7\u53D6\u884C\u4E1A\u5206\u6790\u4E0E\u70ED\u699C", "Fetch Industry & Trending"))
  ))), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-sky-500/20 bg-sky-500/5 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Layers, { className: "w-4 h-4 text-sky-300" }), t("\u70ED\u699C\u9898\u6750\u53D8\u5316\u5206\u6790", "Hot-List Genre Shift Analysis")), /* @__PURE__ */ React.createElement(
    "select",
    {
      value: selectedIndustryReportId,
      onChange: (e) => handleSelectMarketIntelReport(e.target.value, "industry_analysis"),
      disabled: isLoadingMarketIntelHistory || industryHistoryOptions.length === 0,
      className: "rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none disabled:opacity-50"
    },
    industryHistoryOptions.length === 0 ? /* @__PURE__ */ React.createElement("option", { value: "" }, t("\u6682\u65E0\u5386\u53F2", "No history")) : industryHistoryOptions.map((item) => /* @__PURE__ */ React.createElement("option", { key: `industry-hist-${item.id}`, value: String(item.id) }, formatMarketIntelOptionLabel(item)))
  )), industryAnalysisReport?.markdown ? /* @__PURE__ */ React.createElement("div", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-3 max-h-[28rem] overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 text-sm" }, /* @__PURE__ */ React.createElement(ReactMarkdown, null, industryAnalysisReport.markdown), industryAnalysisReport.disclaimer ? /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground mt-3 not-prose" }, industryAnalysisReport.disclaimer) : null) : /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, isFetchingMarketResearch ? t("\u6B63\u5728\u751F\u6210\u9898\u6750\u53D8\u5316\u5206\u6790...", "Generating genre-shift analysis...") : t("\u70B9\u51FB\u4E0A\u65B9\u6309\u94AE\u540E\uFF0C\u5C06\u5728\u6B64\u663E\u793A\u70ED\u699C\u53D8\u5316\u4E0E\u9898\u6750\u8D8B\u52BF\u3002", "Genre-shift analysis will appear here after fetch."))), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white flex items-center gap-2" }, /* @__PURE__ */ React.createElement(TrendingUp, { className: "w-4 h-4 text-amber-300" }), t("\u70ED\u95E8\u4F5C\u54C1\u699C\u5355\uFF08\u9AD8\u6F6E/\u540D\u573A\u9762\uFF09", "Trending List (Climax & Iconic Scenes)")), /* @__PURE__ */ React.createElement(
    "select",
    {
      value: selectedTrendingReportId,
      onChange: (e) => handleSelectMarketIntelReport(e.target.value, "trending_dramas"),
      disabled: isLoadingMarketIntelHistory || trendingHistoryOptions.length === 0,
      className: "rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none disabled:opacity-50"
    },
    trendingHistoryOptions.length === 0 ? /* @__PURE__ */ React.createElement("option", { value: "" }, t("\u6682\u65E0\u5386\u53F2", "No history")) : trendingHistoryOptions.map((item) => /* @__PURE__ */ React.createElement("option", { key: `trending-hist-${item.id}`, value: String(item.id) }, formatMarketIntelOptionLabel(item)))
  )), trendingDramasReport?.markdown ? /* @__PURE__ */ React.createElement("div", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-3 max-h-[28rem] overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 text-sm" }, /* @__PURE__ */ React.createElement(ReactMarkdown, null, trendingDramasReport.markdown), trendingDramasReport.disclaimer ? /* @__PURE__ */ React.createElement("div", { className: "text-[11px] text-muted-foreground mt-3 not-prose" }, trendingDramasReport.disclaimer) : null) : /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, isFetchingMarketResearch ? t("\u6B63\u5728\u751F\u6210\u70ED\u95E8\u699C\u5355...", "Generating trending list...") : t("\u70B9\u51FB\u4E0A\u65B9\u6309\u94AE\u540E\uFF0C\u5C06\u5728\u6B64\u663E\u793A\u6700\u70ED/\u65B0\u4E0A\u699C\u4F5C\u54C1\u53CA\u5176\u9AD8\u6F6E\u540D\u573A\u9762\u3001\u7ECF\u5178\u5BF9\u767D\u4E0E\u753B\u9762\u52A8\u4F5C\u770B\u70B9\u3002", "Trending dramas with climax/iconic scenes, dialogue, and visual-action highlights will appear here after fetch."))))), mode === "generator" && projectTab === "promo_generator" && /* @__PURE__ */ React.createElement("div", { className: "bg-card border border-white/10 p-6 rounded-xl space-y-4 xl:col-span-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u5BA3\u4F20\u7247\u751F\u6210\u5668\uFF08\u4F01\u4E1A / \u4EA7\u54C1 / \u6587\u65C5\uFF09", "Promo Generator (Corporate / Product / Tourism)")), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleGeneratePromoFramework,
      disabled: isGeneratingGlobalStory,
      className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingGlobalStory ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`
    },
    isGeneratingGlobalStory ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u751F\u6210\u4E2D...", "Generating...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Sparkles, { className: "w-4 h-4" }), " ", t("\u751F\u6210\u5BA3\u4F20\u6846\u67B6", "Generate Promo Framework"))
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleGenerateEpisodeScripts,
      disabled: episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts,
      className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-white/10 text-white hover:bg-white/20"}`
    },
    episodeScriptsRunning ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u751F\u6210\u4E2D...", "Generating...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Wand2, { className: "w-4 h-4" }), " ", t("\u5168\u91CF\u751F\u6210\u5206\u96C6", "Generate All"))
  ), /* @__PURE__ */ React.createElement("div", { className: "flex items-center bg-white/5 rounded-lg overflow-hidden border border-white/10" }, /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "number",
      min: "1",
      placeholder: t("\u5355\u96C6", "Ep#"),
      className: "w-16 px-2 py-2 bg-transparent text-sm text-center outline-none text-white placeholder-white/30",
      value: targetEpisodeNumberForGen,
      onChange: (e) => setTargetEpisodeNumberForGen(e.target.value),
      disabled: episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts
    }
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => handleGenerateEpisodeScripts({ specificEpisode: targetEpisodeNumberForGen }),
      disabled: !targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts,
      className: `px-3 py-2 text-sm font-bold flex items-center bg-white/10 hover:bg-white/20 transition-colors ${!targetEpisodeNumberForGen || episodeScriptsRunning || isGeneratingGlobalStory || isStoppingEpisodeScripts ? "opacity-50 cursor-not-allowed" : "text-blue-300"}`,
      title: t("\u4EC5\u751F\u6210\u586B\u5199\u7684\u5355\u4E2A\u96C6\u6570", "Generate only the specified episode number")
    },
    t("\u5355\u96C6\u751F\u6210", "Gen Single")
  )))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement(
    InputGroup,
    {
      idPrefix: prefix,
      label: t("\u5BA3\u4F20\u7C7B\u578B", "Promo Type"),
      value: promoInput.promo_type,
      onChange: (v) => setPromoInput((prev) => ({ ...prev, promo_type: v })),
      list: [
        "\u4F01\u4E1A\u5BA3\u4F20 / Corporate Promotion",
        "\u5546\u54C1\u5BA3\u4F20 / Product Promotion",
        "\u6587\u65C5\u5BA3\u4F20 / Cultural Tourism Promotion"
      ]
    }
  ), /* @__PURE__ */ React.createElement(
    InputGroup,
    {
      idPrefix: prefix,
      label: t("\u96C6\u6570", "Episodes Count"),
      value: String(promoInput.episodes_count || ""),
      onChange: (v) => setPromoInput((prev) => ({ ...prev, episodes_count: Number(v || 0) })),
      list: ["1", "3", "5", "6", "8", "10", "12"]
    }
  ), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u4F20\u64AD\u76EE\u6807", "Campaign Objective")), /* @__PURE__ */ React.createElement("textarea", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none", value: promoInput.campaign_objective, onChange: (e) => setPromoInput((prev) => ({ ...prev, campaign_objective: e.target.value })) })), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u76EE\u6807\u53D7\u4F17", "Target Audience")), /* @__PURE__ */ React.createElement("textarea", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none", value: promoInput.target_audience, onChange: (e) => setPromoInput((prev) => ({ ...prev, target_audience: e.target.value })) })), /* @__PURE__ */ React.createElement("div", { className: "sm:col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, t("\u6838\u5FC3\u4FE1\u606F", "Key Message")), /* @__PURE__ */ React.createElement("textarea", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none", value: promoInput.key_message, onChange: (e) => setPromoInput((prev) => ({ ...prev, key_message: e.target.value })) }))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-1" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold block" }, t("\u5DF2\u751F\u6210\u5BA3\u4F20\u6846\u67B6\uFF08Markdown\uFF09", "Generated Promo Framework (Markdown)")), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-1 bg-black/20 border border-white/10 rounded-md p-1" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => setPromoFrameworkViewMode("preview"),
      className: `px-2 py-1 rounded text-xs font-bold ${promoFrameworkViewMode === "preview" ? "bg-white text-black" : "text-white/80 hover:bg-white/10"}`
    },
    t("\u9884\u89C8", "Preview")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => setPromoFrameworkViewMode("edit"),
      className: `px-2 py-1 rounded text-xs font-bold ${promoFrameworkViewMode === "edit" ? "bg-white text-black" : "text-white/80 hover:bg-white/10"}`
    },
    t("\u7F16\u8F91", "Edit")
  ))), promoFrameworkViewMode === "edit" ? /* @__PURE__ */ React.createElement(
    "textarea",
    {
      ref: (el) => {
        if (el) {
          el.style.height = "auto";
          el.style.height = el.scrollHeight + "px";
        }
      },
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full min-h-[14rem] resize-none overflow-hidden",
      value: info.promo_dna_global_md || "",
      onChange: (e) => updateField("promo_dna_global_md", e.target.value),
      placeholder: t("\uFF08\u751F\u6210\u540E\uFF0C\u5BA3\u4F20\u7247\u5168\u5C40\u6846\u67B6\u4F1A\u663E\u793A\u5728\u8FD9\u91CC\u3002\u4F60\u53EF\u4EE5\u7F16\u8F91\u540E\u4FDD\u5B58\u4FEE\u6539\u3002\uFF09", "(After generation, promo global framework will appear here. You can edit it and Save Changes.)")
    }
  ) : /* @__PURE__ */ React.createElement("div", { className: "bg-black/30 border border-white/10 rounded-md px-3 py-3 h-56 overflow-y-auto custom-scrollbar prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1" }, (info.promo_dna_global_md || "").trim() ? /* @__PURE__ */ React.createElement(ReactMarkdown, null, info.promo_dna_global_md) : /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground" }, t("\uFF08\u751F\u6210\u540E\uFF0C\u5BA3\u4F20\u7247\u5168\u5C40\u6846\u67B6\u4F1A\u663E\u793A\u5728\u8FD9\u91CC\u3002\uFF09", "(After generation, promo global framework will appear here.)")))))), showEpisodeScriptsProgressModal && /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4", onClick: () => setShowEpisodeScriptsProgressModal(false) }, /* @__PURE__ */ React.createElement("div", { className: "bg-[#0f0f10] border border-white/10 rounded-xl w-full max-w-6xl max-h-[90vh] overflow-hidden", onClick: (e) => e.stopPropagation() }, /* @__PURE__ */ React.createElement("div", { className: "px-5 py-4 border-b border-white/10 flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u5206\u96C6\u5267\u672C\u8FDB\u5EA6\u4E2D\u5FC3", "Episode Scripts Progress Center")), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u5B9E\u65F6\u8DDF\u8E2A\u6BCF\u4E2A\u5206\u96C6\u5E76\u67E5\u770B\u751F\u6210\u7ED3\u679C\u3002", "Track each episode in real time and review generation results."))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: handleStopEpisodeScripts,
      disabled: isStoppingEpisodeScripts,
      className: `px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-1.5 ${isStoppingEpisodeScripts ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-red-500/20 text-red-200 hover:bg-red-500/30"}`
    },
    isStoppingEpisodeScripts ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-3.5 h-3.5 animate-spin" }), " ", t("\u505C\u6B62\u4E2D...", "Stopping...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(X, { className: "w-3.5 h-3.5" }), " ", t("\u5F3A\u5236\u505C\u6B62", "Force Stop"))
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: pollEpisodeScriptsStatus,
      className: "px-3 py-1.5 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-1.5"
    },
    /* @__PURE__ */ React.createElement(RefreshCw, { className: "w-3.5 h-3.5" }),
    " ",
    t("\u5237\u65B0", "Refresh")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      className: "p-2 rounded-md hover:bg-white/10 text-white/80",
      onClick: () => setShowEpisodeScriptsProgressModal(false),
      title: t("\u5173\u95ED", "Close")
    },
    /* @__PURE__ */ React.createElement(X, { size: 18 })
  ))), /* @__PURE__ */ React.createElement("div", { className: "p-5 space-y-4 overflow-y-auto max-h-[calc(90vh-80px)]" }, episodeScriptsProgress ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-7 gap-3 text-sm" }, /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u6A21\u5F0F", "Mode")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress.mode || "full")), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u72B6\u6001", "Status")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress.running ? t("\u8FD0\u884C\u4E2D", "Running") : t("\u7A7A\u95F2", "Idle"))), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u505C\u6B62\u8BF7\u6C42", "Stop Requested")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress.stop_requested ? t("\u662F", "Yes") : t("\u5426", "No"))), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u5DF2\u5904\u7406", "Processed")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, processedCount, " / ", episodesInRun)), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u5DF2\u751F\u6210", "Generated")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress.generated || 0)), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u5931\u8D25", "Failed")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress.failed || 0)), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg p-3 bg-black/20" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, t("\u8DF3\u8FC7", "Skipped")), /* @__PURE__ */ React.createElement("div", { className: "font-bold text-white" }, episodeScriptsProgress.skipped || 0))), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between text-xs text-muted-foreground" }, /* @__PURE__ */ React.createElement("span", null, t("\u603B\u4F53\u8FDB\u5EA6", "Overall Progress")), /* @__PURE__ */ React.createElement("span", null, progressPercent, "%")), /* @__PURE__ */ React.createElement("div", { className: "h-2 rounded bg-white/10 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "h-2 bg-primary", style: { width: `${progressPercent}%` } }))), failedEpisodeRows.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "border border-red-500/30 rounded-lg p-3 bg-red-500/10" }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-red-200 mb-2" }, t("\u5931\u8D25\u5206\u96C6\uFF08\u70B9\u51FB\u8DF3\u8F6C\uFF09", "Failed Episodes (click to jump)")), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, failedEpisodeRows.map((item, idx) => /* @__PURE__ */ React.createElement(
    "button",
    {
      key: `${item.episode_id}_${idx}`,
      onClick: () => {
        if (onJumpToEpisode && item.episode_id) onJumpToEpisode(item.episode_id);
      },
      className: "px-2 py-1 rounded text-xs bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-100",
      title: item.error || t("\u8DF3\u8F6C\u5230\u5206\u96C6", "Jump to episode")
    },
    buildEpisodeDisplayLabel({
      episodeNumber: item?.episode_number,
      title: item?.episode_title,
      fallbackNumber: Number(item?.episode_number || 0) || null
    })
  )))), /* @__PURE__ */ React.createElement("div", { className: "border border-white/10 rounded-lg overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-12 bg-white/5 text-xs text-muted-foreground px-3 py-2" }, /* @__PURE__ */ React.createElement("div", { className: "col-span-1" }, "#"), /* @__PURE__ */ React.createElement("div", { className: "col-span-4" }, t("\u5206\u96C6", "Episode")), /* @__PURE__ */ React.createElement("div", { className: "col-span-2" }, t("\u72B6\u6001", "Status")), /* @__PURE__ */ React.createElement("div", { className: "col-span-3" }, t("\u7ED3\u679C", "Result")), /* @__PURE__ */ React.createElement("div", { className: "col-span-2 text-right" }, t("\u64CD\u4F5C", "Action"))), /* @__PURE__ */ React.createElement("div", { className: "max-h-[38vh] overflow-y-auto" }, episodeResultRows.length > 0 ? episodeResultRows.map((row, idx) => {
    const status = String(row?.status || "pending");
    const statusClass = status === "generated" ? "bg-green-500/20 text-green-200 border-green-500/30" : status === "failed" ? "bg-red-500/20 text-red-200 border-red-500/30" : status === "skipped" ? "bg-yellow-500/20 text-yellow-200 border-yellow-500/30" : "bg-white/10 text-white/80 border-white/20";
    const resultText = row?.error || row?.reason || (row?.output_chars ? `${row.output_chars} ${t("\u5B57\u7B26", "chars")}` : status === "pending" ? t("\u7B49\u5F85\u4E2D", "Waiting") : "-");
    const titleMismatchSuffix = row?.title_mismatch ? ` \xB7 ${t("\u6807\u9898/\u7F16\u53F7\u4E0D\u4E00\u81F4", "Title/number mismatch")}` : "";
    const statusLabel = status === "generated" ? t("\u5DF2\u751F\u6210", "Generated") : status === "failed" ? t("\u5931\u8D25", "Failed") : status === "skipped" ? t("\u8DF3\u8FC7", "Skipped") : status === "pending" ? t("\u5F85\u5904\u7406", "Pending") : status;
    return /* @__PURE__ */ React.createElement("div", { key: `${row?.episode_number || idx}_${idx}`, className: "grid grid-cols-12 px-3 py-2 text-sm border-t border-white/5 items-center" }, /* @__PURE__ */ React.createElement("div", { className: "col-span-1 text-white/90" }, row?.episode_number || "-"), /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "col-span-4 text-white/90 truncate",
        title: `${buildEpisodeDisplayLabel({
          episodeNumber: row?.episode_number,
          title: row?.episode_title,
          fallbackNumber: Number(row?.episode_number || 0) || null
        })}${titleMismatchSuffix}`
      },
      buildEpisodeDisplayLabel({
        episodeNumber: row?.episode_number,
        title: row?.episode_title,
        fallbackNumber: Number(row?.episode_number || 0) || null
      }),
      titleMismatchSuffix
    ), /* @__PURE__ */ React.createElement("div", { className: "col-span-2" }, /* @__PURE__ */ React.createElement("span", { className: `px-2 py-0.5 rounded text-xs border ${statusClass}` }, statusLabel)), /* @__PURE__ */ React.createElement("div", { className: "col-span-3 text-xs text-white/70 truncate", title: resultText }, resultText), /* @__PURE__ */ React.createElement("div", { className: "col-span-2 text-right" }, row?.episode_id ? /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => onJumpToEpisode && onJumpToEpisode(row.episode_id),
        className: "px-2 py-1 rounded text-xs bg-white/10 text-white hover:bg-white/20"
      },
      t("\u6253\u5F00", "Open")
    ) : /* @__PURE__ */ React.createElement("span", { className: "text-xs text-white/40" }, "-")));
  }) : /* @__PURE__ */ React.createElement("div", { className: "px-3 py-6 text-center text-sm text-muted-foreground" }, t("\u6682\u65E0\u5206\u96C6\u8FD0\u884C\u8BB0\u5F55\u3002", "No episode run records yet."))))) : /* @__PURE__ */ React.createElement("div", { className: "text-sm text-muted-foreground py-10 text-center" }, t("\u6682\u65E0\u751F\u6210\u72B6\u6001\u3002\u70B9\u51FB\u201C\u751F\u6210\u5206\u96C6\u5267\u672C\u201D\u5F00\u59CB\u8DDF\u8E2A\u3002", "No generation status yet. Start \u201CGenerate Episode Scripts\u201D to begin tracking."))))), showCanonModal && /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-[#0f0f10] border border-white/10 rounded-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto custom-scrollbar" }, /* @__PURE__ */ React.createElement("div", { className: "p-6 space-y-5" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-semibold text-primary" }, t("\u89D2\u8272\u8BBE\u5B9A\u96C6\uFF08\u9879\u76EE\uFF09", "Character Canon (Project)")), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-muted-foreground" }, "\u9009\u62E9\u8EAB\u4EFD\u6807\u7B7E + \u5916\u89C2/\u98CE\u683C\u6807\u7B7E\uFF0C\u751F\u6210\u540E\u4F1A\u8FFD\u52A0\u5230\u9879\u76EE Canon\u3002")), /* @__PURE__ */ React.createElement(
    "button",
    {
      className: "p-2 rounded-md hover:bg-white/10 text-white/80",
      onClick: closeCanonModal,
      title: t("\u5173\u95ED", "Close")
    },
    /* @__PURE__ */ React.createElement(X, { size: 18 })
  )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, "\u89D2\u8272\u540D\u79F0"), /* @__PURE__ */ React.createElement(
    "input",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
      value: canonName,
      onChange: (e) => setCanonName(e.target.value),
      placeholder: "\u4F8B\u5982\uFF1A\u6797\u5A1C / Lina"
    }
  )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, "\u81EA\u5B9A\u4E49\u8EAB\u4EFD\uFF08\u53EF\u9009\uFF0C\u9017\u53F7/\u6362\u884C\u5206\u9694\uFF09"), /* @__PURE__ */ React.createElement(
    "input",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
      value: canonCustomIdentity,
      onChange: (e) => setCanonCustomIdentity(e.target.value),
      placeholder: "\u4F8B\u5982\uFF1A\u5931\u5FC6 / \u9ED1\u5BA2 / \u7EE7\u627F\u4EBA"
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "md:col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, "\u8EAB\u6750/\u4F53\u6001/\u8EAB\u4F53\u7279\u5F81\uFF08\u53EF\u9009\uFF09"), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-16 resize-none",
      value: canonBody,
      onChange: (e) => setCanonBody(e.target.value),
      placeholder: "\u4F8B\u5982\uFF1A\u9AD8\u6311\u3001\u80A9\u9888\u7EBF\u6E05\u6670\u3001\u8D70\u8DEF\u5F88\u7A33\u3001\u77ED\u53D1\u2026"
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "md:col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, "\u81EA\u5B9A\u4E49\u98CE\u683C\u6807\u7B7E\uFF08\u53EF\u9009\uFF0C\u9017\u53F7/\u6362\u884C\u5206\u9694\uFF09"), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-16 resize-none",
      value: canonCustomTags,
      onChange: (e) => setCanonCustomTags(e.target.value),
      placeholder: "\u4F8B\u5982\uFF1A\u51B7\u8273\u3001\u9ED1\u897F\u88C5\u3001\u7425\u73C0\u773C\u3001\u96E8\u591C\u9713\u8679\u2026"
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "md:col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-muted-foreground uppercase font-bold mb-1 block" }, "\u989D\u5916\u5907\u6CE8\uFF08\u53EF\u9009\uFF09"), /* @__PURE__ */ React.createElement(
    "textarea",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none",
      value: canonExtra,
      onChange: (e) => setCanonExtra(e.target.value),
      placeholder: "\u4F8B\u5982\uFF1A\u955C\u5934\u8868\u73B0\u3001\u7981\u5FCC\u3001\u8BED\u6C14/\u52A8\u4F5C\u4E60\u60EF\u2026"
    }
  ))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "text-sm text-white/80" }, "\u8EAB\u4EFD\u6807\u7B7E"), /* @__PURE__ */ React.createElement(
    "button",
    {
      className: `px-3 py-1.5 rounded-md text-xs font-bold flex items-center gap-2 ${canonTagEditMode ? "bg-primary text-black" : "bg-white/10 text-white hover:bg-white/20"}`,
      onClick: () => setCanonTagEditMode((v) => !v),
      title: t("\u5207\u6362\u5206\u7C7B\u7F16\u8F91\u6A21\u5F0F", "Toggle edit mode for categories")
    },
    /* @__PURE__ */ React.createElement(Edit3, { className: "w-3.5 h-3.5" }),
    " ",
    canonTagEditMode ? "\u7F16\u8F91\u4E2D" : "\u7F16\u8F91\u6807\u7B7E"
  )), /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, (canonIdentityCategories || []).map((cat) => /* @__PURE__ */ React.createElement("div", { key: cat.key, className: "border border-white/10 rounded-lg p-4 bg-white/[0.02]" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-3" }, canonTagEditMode ? /* @__PURE__ */ React.createElement(
    "input",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
      value: cat.title,
      onChange: (e) => updateIdentityCategoryTitle(cat.key, e.target.value)
    }
  ) : /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white" }, cat.title), canonTagEditMode && /* @__PURE__ */ React.createElement(
    "button",
    {
      className: "px-3 py-2 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2",
      onClick: () => addIdentityOption(cat.key)
    },
    /* @__PURE__ */ React.createElement(Plus, { size: 14 }),
    " \u65B0\u589E"
  )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-2" }, (cat.options || []).map((opt) => {
    const selected = canonSelectedIdentityIds.includes(opt.id);
    return /* @__PURE__ */ React.createElement("div", { key: opt.id, className: `border rounded-lg p-3 flex gap-3 ${selected ? "border-primary/60 bg-primary/10" : "border-white/10 bg-black/20"}` }, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "flex-1 text-left",
        onClick: () => !canonTagEditMode && toggleCanonIdentityId(opt.id),
        title: canonTagEditMode ? "\u7F16\u8F91\u6A21\u5F0F\u4E0B\u4E0D\u53EF\u9009\u62E9" : "\u70B9\u51FB\u9009\u62E9"
      },
      canonTagEditMode ? /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, /* @__PURE__ */ React.createElement(
        "input",
        {
          className: "bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
          value: opt.label,
          onChange: (e) => updateIdentityOption(cat.key, opt.id, { label: e.target.value })
        }
      ), /* @__PURE__ */ React.createElement(
        "input",
        {
          className: "bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs text-white/90 focus:border-primary/50 focus:outline-none w-full",
          value: opt.detail,
          onChange: (e) => updateIdentityOption(cat.key, opt.id, { detail: e.target.value })
        }
      )) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white flex items-center gap-2" }, selected ? /* @__PURE__ */ React.createElement(Check, { size: 16, className: "text-primary" }) : /* @__PURE__ */ React.createElement("span", { className: "w-4" }), opt.label), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-white/60 mt-1" }, opt.detail))
    ), canonTagEditMode && /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "p-2 rounded-md hover:bg-white/10 text-white/70",
        onClick: () => removeIdentityOption(cat.key, opt.id),
        title: t("\u5220\u9664", "Delete")
      },
      /* @__PURE__ */ React.createElement(Trash2, { size: 16 })
    ));
  }))))), /* @__PURE__ */ React.createElement("div", { className: "text-sm text-white/80" }, "\u5916\u89C2/\u98CE\u683C\u6807\u7B7E"), /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, (canonTagCategories || []).map((cat) => /* @__PURE__ */ React.createElement("div", { key: cat.key, className: "border border-white/10 rounded-lg p-4 bg-white/[0.02]" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-3" }, canonTagEditMode ? /* @__PURE__ */ React.createElement(
    "input",
    {
      className: "bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
      value: cat.title,
      onChange: (e) => updateCanonCategoryTitle(cat.key, e.target.value)
    }
  ) : /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white" }, cat.title), canonTagEditMode && /* @__PURE__ */ React.createElement(
    "button",
    {
      className: "px-3 py-2 rounded-md text-xs font-bold bg-white/10 text-white hover:bg-white/20 flex items-center gap-2",
      onClick: () => addCanonOption(cat.key)
    },
    /* @__PURE__ */ React.createElement(Plus, { size: 14 }),
    " \u65B0\u589E"
  )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-2" }, (cat.options || []).map((opt) => {
    const selected = canonSelectedTagIds.includes(opt.id);
    return /* @__PURE__ */ React.createElement("div", { key: opt.id, className: `border rounded-lg p-3 flex gap-3 ${selected ? "border-primary/60 bg-primary/10" : "border-white/10 bg-black/20"}` }, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "flex-1 text-left",
        onClick: () => !canonTagEditMode && toggleCanonTagId(opt.id),
        title: canonTagEditMode ? "\u7F16\u8F91\u6A21\u5F0F\u4E0B\u4E0D\u53EF\u9009\u62E9" : "\u70B9\u51FB\u9009\u62E9"
      },
      canonTagEditMode ? /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, /* @__PURE__ */ React.createElement(
        "input",
        {
          className: "bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:border-primary/50 focus:outline-none w-full",
          value: opt.label,
          onChange: (e) => updateCanonOption(cat.key, opt.id, { label: e.target.value })
        }
      ), /* @__PURE__ */ React.createElement(
        "input",
        {
          className: "bg-black/30 border border-white/10 rounded-md px-2 py-1 text-xs text-white/90 focus:border-primary/50 focus:outline-none w-full",
          value: opt.detail,
          onChange: (e) => updateCanonOption(cat.key, opt.id, { detail: e.target.value })
        }
      )) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "text-sm font-semibold text-white flex items-center gap-2" }, selected ? /* @__PURE__ */ React.createElement(Check, { size: 16, className: "text-primary" }) : /* @__PURE__ */ React.createElement("span", { className: "w-4" }), opt.label), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-white/60 mt-1" }, opt.detail))
    ), canonTagEditMode && /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "p-2 rounded-md hover:bg-white/10 text-white/70",
        onClick: () => removeCanonOption(cat.key, opt.id),
        title: t("\u5220\u9664", "Delete")
      },
      /* @__PURE__ */ React.createElement(Trash2, { size: 16 })
    ));
  }))))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-end gap-2 pt-2" }, canonTagEditMode && /* @__PURE__ */ React.createElement(
    "button",
    {
      className: "px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20",
      onClick: async () => {
        const normalizedTags = normalizeCanonTagCategories(canonTagCategories);
        const normalizedIdentity = normalizeCanonTagCategories(canonIdentityCategories);
        const ok1 = normalizedTags ? persistCanonTagCategories(normalizedTags) : false;
        const ok2 = normalizedIdentity ? persistCanonIdentityCategories(normalizedIdentity) : false;
        let okDb = true;
        try {
          if (!id) throw new Error("Missing project id");
          if (!normalizedTags || !normalizedIdentity) throw new Error("Invalid categories");
          await saveProjectCharacterCanonCategories(id, {
            tag_categories: normalizedTags,
            identity_categories: normalizedIdentity
          });
        } catch (e) {
          okDb = false;
          console.error("[Character Canon Categories] Save failed:", e);
        }
        alert(ok1 && ok2 && okDb ? t("\u5DF2\u4FDD\u5B58\u6807\u7B7E\u914D\u7F6E\uFF08\u6570\u636E\u5E93+localStorage\uFF09", "Tag configuration saved (database + localStorage)") : t("\u4FDD\u5B58\u5931\u8D25", "Save failed"));
      }
    },
    /* @__PURE__ */ React.createElement(Save, { className: "w-4 h-4 inline-block mr-2" }),
    " ",
    t("\u4FDD\u5B58\u6807\u7B7E\u914D\u7F6E", "Save Tag Configuration")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      className: "px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20",
      onClick: closeCanonModal,
      disabled: isGeneratingCanon
    },
    t("\u5173\u95ED", "Close")
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      className: `px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isGeneratingCanon ? "bg-white/5 text-muted-foreground cursor-not-allowed" : "bg-primary text-black hover:bg-primary/90"}`,
      onClick: handleGenerateProjectCanon,
      disabled: isGeneratingCanon
    },
    isGeneratingCanon ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Loader2, { className: "w-4 h-4 animate-spin" }), " ", t("\u751F\u6210\u4E2D...", "Generating...")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Sparkles, { className: "w-4 h-4" }), " ", t("\u751F\u6210\u5E76\u8FFD\u52A0", "Generate & Append"))
  ))))));
};
