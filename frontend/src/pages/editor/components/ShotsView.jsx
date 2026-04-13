
import FunctionApiSelector, { useFunctionApis } from '../../../components/FunctionApiSelector';
import PromptMentionTextarea from './PromptMentionTextarea';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { MediaPickerModal, MediaDetailModal } from './MediaModals';
import { ImportModal } from './ImportModal';
import { ReferenceManager } from './SceneManager';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../../../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../../../lib/store';
import LogPanel from '../../../components/LogPanel';
import ProjectStatusBar from '../../../components/ProjectStatusBar';
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, CheckCircle2, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, ExternalLink } from 'lucide-react';
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

import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, DEFAULT_CANON_IDENTITY_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint } from '../editorConstants';
const AdvancedModifyFrame = ({ type, promptText, currentImage, onPromptUpdate, onGenerateAsset, currentGenerating, currentImageCfgValue, uiLang }) => {
    const userLang = (strZh, strEn) => uiLang === 'zh' ? strZh : strEn;
    const { addLog } = useLog();
    const [instruction, setInstruction] = useState('');
    const [isLocalModifying, setIsLocalModifying] = useState(false);
    const [isRegenerating, setIsRegenerating] = useState(false);

    const handleLocalModify = async () => {
        setIsLocalModifying(true);
        try {
            const base = promptText || "";
            const appended = instruction.trim();
            const finalPrompt = base ? `${base}. ${appended}, keeping everything else unchanged.` : appended;
            onPromptUpdate(finalPrompt);
            
            addLog(userLang('已生成新提示词，准备拉起局部修改...', 'Generated new prompt, ready to local modify...'), 'info');
            setTimeout(() => {
                const autoRefs = [];
                if (currentImage) {
                    autoRefs.push(currentImage);
                }
                
                onGenerateAsset(type, -1, { 
                    cfg: currentImageCfgValue,
                    is_gemini_multi_turn_edit: true,
                    gemini_base_prompt: base,
                    gemini_edit_instruction: appended,
                    auto_refs: autoRefs,
                    finalPrompt: finalPrompt
                });
            }, 100);
        } finally {
            setIsLocalModifying(false);
        }
    };

    const handleRegenerate = async () => {
        setIsRegenerating(true);
        addLog(userLang('正在通过大模型优化提示词...', 'Optimizing prompt using LLM...'), 'process');
        try {
            const base = promptText || "";
            const res = await refinePrompt(base, instruction, 'image');
            if (res && res.refined_prompt) {
                const optimized = res.refined_prompt;
                onPromptUpdate(optimized);
                
                addLog(userLang('已生成新提示词，准备拉起生成...', 'Generated new prompt, ready to regenerate...'), 'info');
                setTimeout(() => {
                    onGenerateAsset(type, -1, { cfg: currentImageCfgValue, finalPrompt: optimized });
                }, 100);
            } else {
                addLog(userLang('优化失败，请稍后再试', 'Optimization failed, please try again'), 'error');
            }
        } catch (e) {
            console.error("Refine prompt failed", e);
            addLog(userLang('指令分析失败', 'Instruction analysis failed') + ': ' + e.message, 'error');
        } finally {
            setIsRegenerating(false);
            setInstruction('');
        }
    };

    return (
        <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-4 mt-3">
            <div className="text-[11px] text-muted-foreground uppercase font-bold mb-2">{userLang('脚本修改与重新生成', 'Modify Script & Regenerate')}</div>
            <PromptMentionTextarea entities={[]} uiLang={uiLang}
                className="w-full h-24 bg-black/30 border border-white/10 rounded p-3 text-sm"
                placeholder={userLang("输入剧本修改与重新生成指令（例如：把狗的颜色换成黑色）...", "Enter instructions to modify script and regenerate (e.g., change the dog's color to black)...")}
                value={instruction}
                onChange={e => setInstruction(e.target.value)}
            />
            <div className="flex items-center gap-2 mt-2">
                <button
                    type="button"
                    className="flex-1 bg-white/10 hover:bg-white/20 text-white border-none py-2 flex items-center justify-center gap-2 rounded-md"
                    disabled={!instruction.trim() || isRegenerating || isLocalModifying || currentGenerating}
                    onClick={handleLocalModify}
                >
                    {isLocalModifying ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span className="font-semibold text-sm">{userLang('局部修改', 'Local Modify')}</span>
                </button>

                <button
                    type="button"
                    className="flex-1 bg-primary/20 hover:bg-primary/30 text-primary border-none py-2 flex items-center justify-center gap-2 rounded-md"
                    disabled={!instruction.trim() || isRegenerating || isLocalModifying || currentGenerating}
                    onClick={handleRegenerate}
                >
                    {isRegenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                    <span className="font-semibold text-sm">{userLang('重新生成', 'Regenerate')}</span>
                </button>
            </div>
        </div>
    );
};

export const ShotsView = ({ activeEpisode, projectId, project, onLog, editingShot, setEditingShot, isSuperuser = false, uiLang = 'zh', focusRequest = null, restoreEditingShotId = null, userBatchParallelLimit = 3 }) => {
    const functionApiConfigs = useFunctionApis();
        const aspectParts = parseAspectRatioParts(getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9');
    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;
    
    const { generationConfig, saveToolConfig, savedToolConfigs, llmConfig } = useStore();
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const [promptSubmitLangPref, setPromptSubmitLangPref] = useState(() => getPromptSubmitLanguagePreference());
    const [tempPromptSubmitLang, setTempPromptSubmitLang] = useState('');
    const [showPromptLangMenu, setShowPromptLangMenu] = useState(false);
    
    const promptLangText = useCallback((lang) => {
        return lang === 'cn' ? t('中文', 'Chinese') : t('英文', 'English');
    }, [t]);

    const promptLangPrefText = useCallback((pref) => {
        if (pref === 'cn') return t('中文', 'Chinese');
        if (pref === 'auto') return t('跟随界面语言', 'Follow UI');
        return t('英文', 'English');
    }, [t]);

    const renderPromptLangMenu = (menuId) => {
        const isOpen = showPromptLangMenu === menuId;
        return (
            <div className="flex bg-black/40 border border-white/20 rounded text-[10px] items-stretch">
                <div className="px-2 bg-black/40 text-muted-foreground border-r border-white/10 flex items-center justify-center">
                    {t('提交语言', 'Submit Lang')}
                </div>
                <div
                    className="px-2 min-w-[70px] text-sky-400 flex items-center justify-center cursor-pointer hover:bg-white/5 relative"
                    onClick={(e) => {
                        e.stopPropagation();
                        setShowPromptLangMenu(isOpen ? false : menuId);
                    }}
                >
                    {tempPromptSubmitLang ? promptLangText(tempPromptSubmitLang) : promptLangPrefText(promptSubmitLangPref)}
                    <ChevronDown className="w-3 h-3 ml-1 opacity-50" />
                    {isOpen && (
                        <div className="absolute top-full right-0 mt-1 w-32 bg-gray-900 border border-white/20 rounded shadow-xl z-[999] overflow-hidden py-1">
                            <div className="px-3 py-1.5 text-[9px] font-bold text-muted-foreground uppercase bg-black/40">
                                {t('单次覆盖 (不保存)', 'Temp Override')}
                            </div>
                            <div className={`px-3 py-1.5 cursor-pointer hover:bg-white/10 ${tempPromptSubmitLang === 'en' ? 'text-sky-400 bg-sky-500/10' : 'text-white'}`} onClick={(e) => { e.stopPropagation(); setTempPromptSubmitLang('en'); setShowPromptLangMenu(false); }}>
                                {t('临时英文', 'Temp EN')} {tempPromptSubmitLang === 'en' && '✓'}
                            </div>
                            <div className={`px-3 py-1.5 cursor-pointer hover:bg-white/10 ${tempPromptSubmitLang === 'cn' ? 'text-sky-400 bg-sky-500/10' : 'text-white'}`} onClick={(e) => { e.stopPropagation(); setTempPromptSubmitLang('cn'); setShowPromptLangMenu(false); }}>
                                {t('临时中文', 'Temp CN')} {tempPromptSubmitLang === 'cn' && '✓'}
                            </div>
                            <div className="h-px bg-white/10 my-1"></div>
                            <div className="px-3 py-1.5 text-[9px] font-bold text-muted-foreground uppercase bg-black/40">
                                {t('全局默认', 'Global Default')}
                            </div>
                            <div className={`px-3 py-1.5 cursor-pointer hover:bg-white/10 flex items-center justify-between ${tempPromptSubmitLang === '' ? 'text-sky-400 bg-sky-500/10' : 'text-white'}`} onClick={(e) => { e.stopPropagation(); setTempPromptSubmitLang(''); setShowPromptLangMenu(false); }}>
                                <span className="truncate" title={promptLangPrefText(promptSubmitLangPref)}>{t('跟随全局', 'Follow Global')} ({promptLangPrefText(promptSubmitLangPref)})</span>
                                {tempPromptSubmitLang === '' && '✓'}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const resolvedPromptSubmitLang = useMemo(() => {
        if (tempPromptSubmitLang) return tempPromptSubmitLang;
        return resolvePromptSubmitLanguage(uiLang, promptSubmitLangPref);
    }, [promptSubmitLangPref, uiLang, tempPromptSubmitLang]);
    const effectivePromptSubmitLang = resolvedPromptSubmitLang;
    const shotPromptDisplayLang = resolvedPromptSubmitLang === 'cn' ? 'cn' : 'en';

    const getShotCardPromptPreview = useCallback((shot) => {
        if (!shot || typeof shot !== 'object') return '';

        const compactCnPreview = String(shot?.prompt_preview_cn || '').trim();
        const compactEnPreview = String(shot?.prompt_preview_en || '').trim();

        let tech = {};
        try {
            tech = JSON.parse(shot.technical_notes || '{}');
            if (!tech || typeof tech !== 'object') tech = {};
        } catch (e) {
            tech = {};
        }

        const cnCandidates = [
            compactCnPreview,
            shot.shot_logic_cn,
            tech.video_prompt_cn,
            shot.prompt_cn,
            shot.video_content_cn,
            shot.video_content,
            shot.prompt,
            shot.start_frame,
            shot.end_frame,
        ];
        const enCandidates = [
            compactEnPreview,
            shot.video_content,
            shot.prompt,
            shot.start_frame,
            shot.end_frame,
            tech.video_prompt_cn,
            shot.prompt_cn,
            shot.video_content_cn,
            shot.shot_logic_cn,
        ];

        const pickFirstNonEmpty = (items) => {
            for (const item of items) {
                const text = String(item || '').trim();
                if (text) return text;
            }
            return '';
        };

        return shotPromptDisplayLang === 'cn'
            ? pickFirstNonEmpty(cnCandidates)
            : pickFirstNonEmpty(enCandidates);
    }, [shotPromptDisplayLang]);
    const [scenes, setScenes] = useState([]);
    const [selectedSceneId, setSelectedSceneId] = useState('all');
    const [sceneCodeFilter, setSceneCodeFilter] = useState('');
    const [shotIdFilter, setShotIdFilter] = useState('');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [shots, setShots] = useState([]);
    const [isShotsLoading, setIsShotsLoading] = useState(false);
    const [hasShotInitialLoadCompleted, setHasShotInitialLoadCompleted] = useState(false);
    const [selectedShotIds, setSelectedShotIds] = useState([]);
    const [isImportOpen, setIsImportOpen] = useState(false);
    // const [editingShot, setEditingShot] = useState(null); // Lifted state
    const [entities, setEntities] = useState([]);
    const [entityListLoading, setEntityListLoading] = useState(false);
    const entitiesRef = useRef([]);
    const entityLoadPromiseRef = useRef(null);
    
    // NEW: Abort Controller Ref for retries
    const abortGenerationRef = useRef(false);

    // Local Notification for ShotsView (Edit Dialog)
    const [notification, setNotification] = useState(null);
    const showNotification = (message, type = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    };

    useEffect(() => {
        entitiesRef.current = Array.isArray(entities) ? entities : [];
    }, [entities]);

    const loadEntities = useCallback(async () => {
        const resolvedProjectId = projectId || activeEpisode?.project_id;
        if (!resolvedProjectId) return entitiesRef.current;
        if (entityLoadPromiseRef.current) return entityLoadPromiseRef.current;

        const request = (async () => {
            setEntityListLoading(true);
            try {
                const data = await fetchEntities(resolvedProjectId);
                const nextEntities = Array.isArray(data) ? data.map(item => {
                    if (item.type === 'environment' && (item.name === '封面海报' || item.name_en === 'Cover Poster')) {
                        return { ...item, type: 'poster' };
                    }
                    return item;
                }) : [];
                setEntities(nextEntities);
                return nextEntities;
            } catch (e) {
                console.error(e);
                return [];
            } finally {
                setEntityListLoading(false);
                entityLoadPromiseRef.current = null;
            }
        })();

        entityLoadPromiseRef.current = request;
        return request;
    }, [activeEpisode?.project_id, projectId]);

    const awaitShotGenerationEntities = useCallback(async () => {
        const resolvedProjectId = projectId || activeEpisode?.project_id;
        if (!resolvedProjectId) return Array.isArray(entities) ? entities : [];
        if (Array.isArray(entities) && entities.length > 0 && !entityListLoading) {
            return entities;
        }
        const loaded = await loadEntities();
        if (Array.isArray(loaded) && loaded.length > 0) {
            return loaded;
        }
        return Array.isArray(entities) ? entities : [];
    }, [activeEpisode?.project_id, entities, entityListLoading, loadEntities, projectId]);

    useEffect(() => {
        loadEntities();
    }, [loadEntities]);


    // Note: Provider selection functionality removed (defaults to Backend Active Settings)
    // Code for local state imageProvider/videoProvider removed.


    // AI Prompt Preview Modal State
    const [shotPromptModal, setShotPromptModal] = useState({ open: false, sceneId: null, data: null, loading: false });
    const [shotReviewModal, setShotReviewModal] = useState({ open: false, sceneId: null, data: null, loading: false });
    const [voicePromptConfirmModal, setVoicePromptConfirmModal] = useState({
        open: false,
        shotId: null,
        prompt: '',
        systemPrompt: '',
        loadingSystemPrompt: false,
        languageCode: '',
        projectLanguage: '',
        submitting: false,
    });

    // Media Handling
    const [viewMedia, setViewMedia] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });
    const [generatingStateByShot, setGeneratingStateByShot] = useState({});
    const [isBatchGenerating, setIsBatchGenerating] = useState(false);
    const [isShotBatchStarting, setIsShotBatchStarting] = useState(false);
    const [isStoppingShotBatch, setIsStoppingShotBatch] = useState(false);
    const [isManualRebindingMedia, setIsManualRebindingMedia] = useState(false);
    const [stoppingVideoByShot, setStoppingVideoByShot] = useState({});
    const [voiceGeneratingByShot, setVoiceGeneratingByShot] = useState({});
    const [translatingPromptField, setTranslatingPromptField] = useState('');
    const [batchProgress, setBatchProgress] = useState({
        current: 0,
        total: 0,
        status: '',
        stopRequested: false,
        currentShotLabel: '',
        currentAssetLabel: '',
        mode: '',
    }); // Progress tracking
    const [isShotBatchProgressDismissed, setIsShotBatchProgressDismissed] = useState(false);
    const SHOT_MEDIA_BATCH_KIND = 'shot-media-batch';
    const SHOT_BATCH_RUNTIME_TTL_MS = 1000 * 60 * 60 * 6;
    const SHOT_BATCH_PARALLEL_LIMIT = userBatchParallelLimit;
    const shotBatchStatusTimerRef = useRef(null);
    const shotBatchStartupGuardUntilRef = useRef(0);
    const shotBatchBootstrapUntilRef = useRef(0);
    const isBatchGeneratingRef = useRef(false);
    const batchProgressRef = useRef({ current: 0, total: 0, status: '' });
    const recoverShotBatchInFlightRef = useRef(false);
    const recoverShotBatchLastAtRef = useRef(0);
    const activeResumeVideoJobsRef = useRef(new Set());
    const pausedResumeVideoJobsRef = useRef({});
    const pendingImageJobsRef = useRef({});
    const shotsRef = useRef([]);
    const editingShotRef = useRef(null);
    const jointDiptychApplyInFlightRef = useRef(new Map());
    const appliedJointDiptychResultsRef = useRef(new Map());
    const generatingStateByShotRef = useRef({});
    const shotLocalBatchSessionRef = useRef('');
    const shotLocalBatchStopRequestedRef = useRef(false);
    const selectedSceneIdRef = useRef('all');
    const [activeSources, setActiveSources] = useState({ Image: 'unset', Video: 'unset' });
    const [activeImageCapabilityProfile, setActiveImageCapabilityProfile] = useState(null);
    const [localKeyframes, setLocalKeyframes] = useState([]);
    const generationStateStorageKey = useMemo(() => {
        if (!activeEpisode?.id) return '';
        return `aistory.shotGenerationState.${activeEpisode.id}`;
    }, [activeEpisode?.id]);
    const SHOT_JOB_OWNER_PAGE = 'shot-editor';
    const SHOT_JOB_MAX_STATUS_FAILURES = 3;
    const imageJobStateStorageKey = useMemo(() => {
        if (!activeEpisode?.id) return '';
        return `aistory.shotImageJobs.${activeEpisode.id}`;
    }, [activeEpisode?.id]);
    const videoJobStateStorageKey = useMemo(() => {
        if (!activeEpisode?.id) return '';
        return `aistory.shotVideoJobs.${activeEpisode.id}`;
    }, [activeEpisode?.id]);
    const restoreEditingAttemptedRef = useRef(false);
    const hasHydratedGenerationStateRef = useRef(false);
    const mediaRebindAttemptedRef = useRef('');
    const generationMediaBaselineRef = useRef({});
    const startFrameAutoInheritRef = useRef('');
    const [shotGenerationHistory, setShotGenerationHistory] = useState([]);
    const [shotGenerationHistoryLoading, setShotGenerationHistoryLoading] = useState(false);
    const [shotGenerationHistoryDeletingId, setShotGenerationHistoryDeletingId] = useState('');
    const GENERATION_STATE_TTL_MS = 1000 * 60 * 60;
    const SHOT_MEDIA_STARTUP_GRACE_MS = 15000;
    const IMAGE_JOB_STATE_TTL_MS = 1000 * 60 * 60;
    const VIDEO_JOB_STATE_TTL_MS = 1000 * 60 * 60;
    const shotsRefreshRequestSeqRef = useRef(0);

    const resolveShotSceneId = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return '';
        const currentShot = (shotsRef.current || []).find((item) => String(item?.id || '') === stableShotId)
            || (editingShotRef.current && String(editingShotRef.current?.id || '') === stableShotId ? editingShotRef.current : null);
        return String(currentShot?.scene_id || '').trim();
    }, []);

    const buildShotJobMeta = useCallback((shotId, mediaKind, base = {}) => ({
        ownerPage: SHOT_JOB_OWNER_PAGE,
        ownerScopeType: 'episode',
        ownerScopeId: String(activeEpisode?.id || '').trim(),
        ownerSceneId: String(base?.ownerSceneId || resolveShotSceneId(shotId) || '').trim(),
        ownerShotId: String(shotId || '').trim(),
        ownerMediaKind: mediaKind === 'video' ? 'video' : (mediaKind === 'end' ? 'end' : 'start'),
        statusFailureCount: Math.max(0, Number(base?.statusFailureCount || 0) || 0),
        lastStatusError: String(base?.lastStatusError || '').trim(),
        lastPolledAt: Number(base?.lastPolledAt || 0) || 0,
    }), [activeEpisode?.id, resolveShotSceneId]);

    const describeShotJobOwner = useCallback((payload, shotId, mediaKind) => {
        const stableShotId = String(payload?.ownerShotId || shotId || '').trim() || 'unknown-shot';
        const stableEpisodeId = String(payload?.ownerScopeId || activeEpisode?.id || '').trim() || 'unknown-episode';
        const stableSceneId = String(payload?.ownerSceneId || resolveShotSceneId(stableShotId) || '').trim();
        const stableMediaKind = payload?.ownerMediaKind === 'video'
            ? 'video'
            : (payload?.ownerMediaKind === 'end' ? 'end' : (mediaKind === 'video' ? 'video' : (mediaKind === 'end' ? 'end' : 'start')));
        return `shot-editor/episode:${stableEpisodeId}${stableSceneId ? `/scene:${stableSceneId}` : ''}/shot:${stableShotId}/${stableMediaKind}`;
    }, [activeEpisode?.id, resolveShotSceneId]);

    const extractGenerationHistoryField = useCallback((item, fieldName) => {
        if (!item || typeof item !== 'object') return '';
        const metadata = item?.metadata && typeof item.metadata === 'object' ? item.metadata : {};
        const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
        const context = item?.context && typeof item.context === 'object' ? item.context : {};
        const directValue = item?.[fieldName];
        if (directValue !== undefined && directValue !== null && String(directValue).trim() !== '') return directValue;
        const metaValue = metadata?.[fieldName];
        if (metaValue !== undefined && metaValue !== null && String(metaValue).trim() !== '') return metaValue;
        const payloadValue = payload?.[fieldName];
        if (payloadValue !== undefined && payloadValue !== null && String(payloadValue).trim() !== '') return payloadValue;
        const contextValue = context?.[fieldName];
        if (contextValue !== undefined && contextValue !== null && String(contextValue).trim() !== '') return contextValue;
        return '';
    }, []);

    const resolveGenerationHistoryResultUrl = useCallback((item) => {
        const result = item?.result;
        if (typeof result === 'string') return String(result).trim();
        if (result && typeof result === 'object') {
            return String(result.url || result.result_url || result.image_url || result.video_url || '').trim();
        }
        return '';
    }, []);

    const resolveGenerationHistoryMediaKind = useCallback((item) => {
        const explicitMediaKind = String(extractGenerationHistoryField(item, 'ownerMediaKind') || '').trim().toLowerCase();
        if (explicitMediaKind) return explicitMediaKind;
        const assetType = String(extractGenerationHistoryField(item, 'asset_type') || '').trim().toLowerCase();
        if (assetType.includes('end')) return 'end';
        if (assetType.includes('start')) return 'start';
        if (assetType.includes('subject')) return 'subject';
        if (assetType.includes('video')) return 'video';
        return String(item?.kind || '').trim().toLowerCase() || 'image';
    }, [extractGenerationHistoryField]);

    const buildGenerationHistoryLabel = useCallback((item) => {
        const mediaKind = resolveGenerationHistoryMediaKind(item);
        if (mediaKind === 'video') return t('视频生成', 'Video Generation');
        if (mediaKind === 'end') return t('结束帧生成', 'End Frame Generation');
        if (mediaKind === 'start') return t('起始帧生成', 'Start Frame Generation');
        if (mediaKind === 'subject') {
            const jobKind = String(extractGenerationHistoryField(item, 'jobKind') || '').trim().toLowerCase();
            return jobKind === 'reconstruct' ? t('主体重构', 'Subject Reconstruction') : t('主体生图', 'Subject Image Generation');
        }
        return t('图片生成', 'Image Generation');
    }, [extractGenerationHistoryField, resolveGenerationHistoryMediaKind, t]);

    const normalizeScopedGenerationHistory = useCallback((items) => {
        const list = Array.isArray(items) ? items : [];
        return list
            .map((item) => {
                const resultUrl = resolveGenerationHistoryResultUrl(item);
                return {
                    ...item,
                    entityId: String(extractGenerationHistoryField(item, 'entity_id') || extractGenerationHistoryField(item, 'ownerEntityId') || '').trim(),
                    shotId: String(extractGenerationHistoryField(item, 'shot_id') || extractGenerationHistoryField(item, 'ownerShotId') || '').trim(),
                    projectId: String(extractGenerationHistoryField(item, 'project_id') || extractGenerationHistoryField(item, 'ownerScopeId') || '').trim(),
                    shotName: String(extractGenerationHistoryField(item, 'shot_name') || '').trim(),
                    subjectName: String(extractGenerationHistoryField(item, 'subject_name') || extractGenerationHistoryField(item, 'entity_name') || '').trim(),
                    mediaKind: resolveGenerationHistoryMediaKind(item),
                    resultUrl,
                    displayLabel: buildGenerationHistoryLabel(item),
                    createdAtMs: Date.parse(String(item?.created_at || item?.started_at || item?.finished_at || '')) || 0,
                };
            })
            .sort((a, b) => (b.createdAtMs || 0) - (a.createdAtMs || 0));
    }, [buildGenerationHistoryLabel, extractGenerationHistoryField, resolveGenerationHistoryMediaKind, resolveGenerationHistoryResultUrl]);

    const fetchShotGenerationHistory = useCallback(async (shot) => {
        const stableShotId = String(shot?.id || shot || '').trim();
        if (!stableShotId) {
            setShotGenerationHistory([]);
            return;
        }

        setShotGenerationHistoryLoading(true);
        try {
            const [imagePool, videoPool] = await Promise.all([
                getGenerationJobPool({ kind: 'image', running_only: false, limit: 300 }),
                getGenerationJobPool({ kind: 'video', running_only: false, limit: 300 }),
            ]);
            const normalized = normalizeScopedGenerationHistory([
                ...(Array.isArray(imagePool?.items) ? imagePool.items : []),
                ...(Array.isArray(videoPool?.items) ? videoPool.items : []),
            ]);
            const filtered = normalized.filter((item) => {
                if (item.projectId && String(projectId || '').trim() && item.projectId !== String(projectId || '').trim()) {
                    return false;
                }
                return item.shotId === stableShotId;
            });
            setShotGenerationHistory(filtered.slice(0, 16));
        } catch (e) {
            onLog?.(`Failed to load shot generation history: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
            setShotGenerationHistory([]);
        } finally {
            setShotGenerationHistoryLoading(false);
        }
    }, [getGenerationJobPool, normalizeScopedGenerationHistory, onLog, projectId]);

    useEffect(() => {
        if (!editingShot?.id) {
            setShotGenerationHistory([]);
            return;
        }
        fetchShotGenerationHistory(editingShot);
    }, [editingShot, fetchShotGenerationHistory]);

    const handleDeleteShotGenerationHistoryItem = useCallback(async (item) => {
        const kind = String(item?.kind || '').trim();
        const jobId = String(item?.job_id || '').trim();
        if (!kind || !jobId || !editingShot?.id) return;

        setShotGenerationHistoryDeletingId(jobId);
        try {
            await deleteGenerationJob(kind, jobId);
            await fetchShotGenerationHistory(editingShot);
            onLog?.(t('镜头历史任务记录已删除。', 'Shot history item deleted.'), 'warning');
        } catch (e) {
            onLog?.(t('删除镜头历史失败：', 'Failed to delete shot history item: ') + (e?.response?.data?.detail || e?.message || 'unknown error'), 'error');
        } finally {
            setShotGenerationHistoryDeletingId('');
        }
    }, [deleteGenerationJob, editingShot, fetchShotGenerationHistory, onLog, t]);

    const createShotBatchProgressState = useCallback(() => ({
        current: 0,
        total: 0,
        status: '',
        stopRequested: false,
        currentShotLabel: '',
        currentAssetLabel: '',
        mode: '',
    }), []);

    const isLocalShotBatchMode = useCallback((mode) => (
        mode === 'keyframes-local' || mode === 'joint-diptych-local'
    ), []);

    const getShotBatchRuntimeStorageKey = useCallback((episodeId, sceneId) => {
        if (!episodeId) return '';
        const scope = String(sceneId || 'all').trim() || 'all';
        return `aistory:shot-batch-progress:${episodeId}:scene:${scope}`;
    }, []);

    const loadShotBatchRuntime = useCallback((episodeId, sceneId) => {
        try {
            const key = getShotBatchRuntimeStorageKey(episodeId, sceneId);
            if (!key || !window?.localStorage) return null;
            const raw = window.localStorage.getItem(key);
            if (!raw) return null;

            const parsed = JSON.parse(raw);
            const updatedAt = Number(parsed?.updatedAt || 0);
            if (!Number.isFinite(updatedAt) || updatedAt <= 0) return null;
            if ((Date.now() - updatedAt) > SHOT_BATCH_RUNTIME_TTL_MS) {
                window.localStorage.removeItem(key);
                return null;
            }

            return {
                running: Boolean(parsed?.running),
                progress: {
                    current: Number(parsed?.current || 0),
                    total: Number(parsed?.total || 0),
                    status: String(parsed?.status || ''),
                    stopRequested: Boolean(parsed?.stopRequested),
                    currentShotLabel: String(parsed?.currentShotLabel || ''),
                    currentAssetLabel: String(parsed?.currentAssetLabel || ''),
                    mode: String(parsed?.mode || ''),
                },
            };
        } catch (_) {
            return null;
        }
    }, [getShotBatchRuntimeStorageKey, SHOT_BATCH_RUNTIME_TTL_MS]);

    const saveShotBatchRuntime = useCallback((episodeId, sceneId, running, progress) => {
        try {
            const key = getShotBatchRuntimeStorageKey(episodeId, sceneId);
            if (!key || !window?.localStorage) return;

            const payload = {
                running: Boolean(running),
                current: Number(progress?.current || 0),
                total: Number(progress?.total || 0),
                status: String(progress?.status || ''),
                stopRequested: Boolean(progress?.stopRequested),
                currentShotLabel: String(progress?.currentShotLabel || ''),
                currentAssetLabel: String(progress?.currentAssetLabel || ''),
                mode: String(progress?.mode || ''),
                updatedAt: Date.now(),
            };
            window.localStorage.setItem(key, JSON.stringify(payload));
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getShotBatchRuntimeStorageKey]);

    const syncLocalShotBatchRuntime = useCallback((running, progress, sceneIdOverride) => {
        const episodeId = activeEpisode?.id;
        if (!episodeId) return;
        const stableSceneId = sceneIdOverride ?? selectedSceneIdRef.current;
        const nextProgress = progress || createShotBatchProgressState();
        saveShotBatchRuntime(episodeId, stableSceneId, running, nextProgress);
        isBatchGeneratingRef.current = Boolean(running);
        batchProgressRef.current = nextProgress;
        setIsBatchGenerating(Boolean(running));
        setBatchProgress(nextProgress);
    }, [activeEpisode?.id, createShotBatchProgressState, saveShotBatchRuntime]);

    const isPersistentLocalShotBatchStopRequested = useCallback((sceneIdOverride) => {
        const episodeId = activeEpisode?.id;
        if (!episodeId) return false;
        const stableSceneId = sceneIdOverride ?? selectedSceneIdRef.current;
        const restored = loadShotBatchRuntime(episodeId, stableSceneId);
        return Boolean(restored?.progress?.stopRequested);
    }, [activeEpisode?.id, loadShotBatchRuntime]);

    const getPersistentLocalShotBatchRuntime = useCallback((sceneIdOverride) => {
        const episodeId = activeEpisode?.id;
        if (!episodeId) return null;
        const stableSceneId = String((sceneIdOverride ?? selectedSceneIdRef.current) || 'all').trim() || 'all';
        const restored = loadShotBatchRuntime(episodeId, stableSceneId);
        if (!restored?.running || !isLocalShotBatchMode(restored?.progress?.mode)) return null;
        return {
            ...restored,
            sceneId: stableSceneId,
        };
    }, [activeEpisode?.id, isLocalShotBatchMode, loadShotBatchRuntime]);

    const extractEpisodeIdFromJobPoolItem = useCallback((item) => {
        const direct = Number(item?.episode_id || item?.episodeId || 0);
        if (Number.isFinite(direct) && direct > 0) return direct;
        const metadata = (item?.metadata && typeof item.metadata === 'object') ? item.metadata : {};
        const payload = (item?.payload && typeof item.payload === 'object') ? item.payload : {};
        const context = (item?.context && typeof item.context === 'object') ? item.context : {};
        const nested = Number(
            metadata?.episode_id
            || payload?.episode_id
            || context?.episode_id
            || metadata?.episodeId
            || payload?.episodeId
            || context?.episodeId
            || 0
        );
        return Number.isFinite(nested) && nested > 0 ? nested : 0;
    }, []);

    const recoverShotBatchFromJobPool = useCallback(async () => {
        if (!activeEpisode?.id) return false;
        const now = Date.now();
        if (recoverShotBatchInFlightRef.current) return false;
        if ((now - Number(recoverShotBatchLastAtRef.current || 0)) < 4000) return false;

        recoverShotBatchInFlightRef.current = true;
        recoverShotBatchLastAtRef.current = now;
        try {
            const data = await getGenerationJobPool({
                kind: SHOT_MEDIA_BATCH_KIND,
                running_only: true,
                limit: 200,
            });
            const items = Array.isArray(data?.items) ? data.items : [];
            if (items.length === 0) return false;

            const currentEpisodeId = Number(activeEpisode.id || 0);
            const matched = items.find((item) => extractEpisodeIdFromJobPoolItem(item) === currentEpisodeId)
                || items.find((item) => String(item?.status || '').toLowerCase() === 'running')
                || items[0];
            if (!matched) return false;

            if (String(matched?.status || '').toLowerCase() !== 'running') return false;

            setIsBatchGenerating(true);
            setBatchProgress((prev) => ({
                ...prev,
                status: String(prev?.status || t('检测到任务池中的批量视频任务，正在恢复进度...', 'Detected running batch media task in job pool, restoring progress...')),
            }));
            return true;
        } catch (_) {
            return false;
        } finally {
            recoverShotBatchInFlightRef.current = false;
        }
    }, [SHOT_MEDIA_BATCH_KIND, activeEpisode?.id, extractEpisodeIdFromJobPoolItem, t]);

    useEffect(() => {
        const syncPromptSubmitLangPref = () => {
            setPromptSubmitLangPref(getPromptSubmitLanguagePreference());
        };

        syncPromptSubmitLangPref();
        window.addEventListener('storage', syncPromptSubmitLangPref);
        window.addEventListener('focus', syncPromptSubmitLangPref);
        return () => {
            window.removeEventListener('storage', syncPromptSubmitLangPref);
            window.removeEventListener('focus', syncPromptSubmitLangPref);
        };
    }, []);

    const getShotEndFrameUrl = useCallback((shot) => {
        const direct = String(shot?.end_frame_url || '').trim();
        if (direct) return direct;
        try {
            const tech = JSON.parse(shot?.technical_notes || '{}');
            return String(tech?.end_frame_url || '');
        } catch (e) {
            return '';
        }
    }, []);

    const getBatchVideoEligibleShots = useCallback((shotList) => {
        return (Array.isArray(shotList) ? shotList : []).filter((shot) => {
            if (!shot || !shot.id) return false;
            const startFrameUrl = String(shot?.image_url || '').trim();
            const endFrameUrl = String(getShotEndFrameUrl(shot) || '').trim();
            const videoUrl = String(shot?.video_url || '').trim();
            if (videoUrl) return false;
            return Boolean(startFrameUrl || endFrameUrl);
        });
    }, [getShotEndFrameUrl]);

    const normalizeGeneratingState = useCallback((raw) => {
        if (!raw || typeof raw !== 'object') return {};
        const normalized = {};
        Object.entries(raw).forEach(([shotId, value]) => {
            if (!shotId || !value || typeof value !== 'object') return;
            const start = !!value.start;
            const end = !!value.end;
            const video = !!value.video;
            if (!start && !end && !video) return;
            normalized[shotId] = {
                start,
                end,
                video,
                startAt: Number(value.startAt) || 0,
                endAt: Number(value.endAt) || 0,
                videoAt: Number(value.videoAt) || 0,
            };
        });
        return normalized;
    }, []);

    const readGenerationStateStorage = useCallback(() => {
        if (!generationStateStorageKey) return {};
        try {
            const raw = localStorage.getItem(generationStateStorageKey);
            if (!raw) return {};
            const parsed = JSON.parse(raw);
            return normalizeGeneratingState(parsed);
        } catch (e) {
            console.warn('Failed to read shot generation state', e);
            return {};
        }
    }, [generationStateStorageKey, normalizeGeneratingState]);

    const writeGenerationStateStorage = useCallback((state) => {
        if (!generationStateStorageKey) return;
        try {
            const normalized = normalizeGeneratingState(state);
            if (Object.keys(normalized).length === 0) {
                localStorage.removeItem(generationStateStorageKey);
                return;
            }
            localStorage.setItem(generationStateStorageKey, JSON.stringify(normalized));
        } catch (e) {
            console.warn('Failed to write shot generation state', e);
        }
    }, [generationStateStorageKey, normalizeGeneratingState]);

    const applyGeneratingStateChange = useCallback((state, shotId, key, value) => {
        if (!shotId) return state;
        const now = Date.now();
        const prev = state[shotId] || { start: false, end: false, video: false, startAt: 0, endAt: 0, videoAt: 0 };
        const previousValue = Boolean(prev[key]);
        const previousAt = Number(prev[`${key}At`] || 0);
        const nextAt = value
            ? (previousValue ? previousAt : now)
            : 0;

        if (previousValue === Boolean(value) && previousAt === nextAt) {
            return state;
        }

        const next = {
            ...prev,
            [key]: value,
            [`${key}At`]: nextAt,
        };
        if (!next.start && !next.end && !next.video) {
            const { [shotId]: _, ...rest } = state;
            return rest;
        }
        return { ...state, [shotId]: next };
    }, []);

    const setStoredShotGeneratingState = useCallback((shotId, key, value) => {
        const prev = readGenerationStateStorage();
        const next = applyGeneratingStateChange(prev, String(shotId), key, value);
        writeGenerationStateStorage(next);
    }, [applyGeneratingStateChange, readGenerationStateStorage, writeGenerationStateStorage]);

    const setShotGeneratingState = useCallback((shotId, key, value) => {
        if (!shotId) return;
        const stableShotId = String(shotId);

        if (value === true) {
            const matchedShot = (shots || []).find((item) => String(item?.id) === stableShotId)
                || (editingShot && String(editingShot?.id) === stableShotId ? editingShot : null);
            const prevBase = generationMediaBaselineRef.current[stableShotId] || {};
            const nextBase = { ...prevBase };
            if (key === 'start') nextBase.start = String(matchedShot?.image_url || '');
            if (key === 'end') nextBase.end = String(getShotEndFrameUrl(matchedShot));
            if (key === 'video') nextBase.video = String(matchedShot?.video_url || '');
            generationMediaBaselineRef.current[stableShotId] = nextBase;
        } else {
            const prevBase = generationMediaBaselineRef.current[stableShotId] || {};
            if (prevBase && Object.prototype.hasOwnProperty.call(prevBase, key)) {
                const nextBase = { ...prevBase };
                delete nextBase[key];
                if (Object.keys(nextBase).length === 0) {
                    delete generationMediaBaselineRef.current[stableShotId];
                } else {
                    generationMediaBaselineRef.current[stableShotId] = nextBase;
                }
            }
        }

        setStoredShotGeneratingState(stableShotId, key, value);
        setGeneratingStateByShot(prev => {
            return applyGeneratingStateChange(prev, stableShotId, key, value);
        });
    }, [applyGeneratingStateChange, setStoredShotGeneratingState, shots, editingShot, getShotEndFrameUrl]);

    useEffect(() => {
        shotsRef.current = Array.isArray(shots) ? shots : [];
    }, [shots]);

    useEffect(() => {
        editingShotRef.current = editingShot || null;
    }, [editingShot]);

    useEffect(() => {
        if (!editingShot?.id || !editingShot?.is_compact) {
            return undefined;
        }

        let cancelled = false;

        const hydrateEditingShot = async () => {
            try {
                const fullShot = await fetchShot(editingShot.id);
                if (cancelled || !fullShot?.id) return;
                setEditingShot((prev) => {
                    if (!prev || String(prev?.id || '') !== String(fullShot.id)) {
                        return prev;
                    }
                    return { ...prev, ...fullShot, is_compact: false };
                });
            } catch (e) {
                console.error('Failed to hydrate shot detail', e);
            }
        };

        hydrateEditingShot();
        return () => {
            cancelled = true;
        };
    }, [editingShot?.id, editingShot?.is_compact, setEditingShot]);

    useEffect(() => {
        selectedSceneIdRef.current = String(selectedSceneId || 'all');
    }, [selectedSceneId]);

    useEffect(() => {
        generatingStateByShotRef.current = generatingStateByShot || {};
    }, [generatingStateByShot]);

    const readVideoJobStateStorage = useCallback(() => {
        if (!videoJobStateStorageKey) return {};
        try {
            const raw = localStorage.getItem(videoJobStateStorageKey);
            if (!raw) return {};
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return {};

            const now = Date.now();
            const cleaned = {};
            Object.entries(parsed).forEach(([shotId, payload]) => {
                const jobId = String(payload?.jobId || '').trim();
                const startedAt = Number(payload?.startedAt || 0);
                if (!shotId || !jobId) return;
                if (startedAt > 0 && (now - startedAt) > VIDEO_JOB_STATE_TTL_MS) return;
                cleaned[String(shotId)] = {
                    jobId,
                    startedAt: startedAt || now,
                    ...buildShotJobMeta(String(shotId), 'video', payload),
                };
            });
            return cleaned;
        } catch (e) {
            console.warn('Failed to read shot video job state', e);
            return {};
        }
    }, [VIDEO_JOB_STATE_TTL_MS, buildShotJobMeta, videoJobStateStorageKey]);

    const normalizeImageJobState = useCallback((raw) => {
        if (!raw || typeof raw !== 'object') return {};
        const now = Date.now();
        const cleaned = {};
        Object.entries(raw).forEach(([jobKey, payload]) => {
            const stableKey = String(jobKey || '').trim();
            const stableShotId = String(payload?.shotId || '').trim();
            const stableKind = payload?.kind === 'end' ? 'end' : 'start';
            const stableJobId = String(payload?.jobId || '').trim();
            const startedAt = Number(payload?.startedAt || 0);
            if (!stableKey || !stableShotId || !stableJobId) return;
            if (startedAt > 0 && (now - startedAt) > IMAGE_JOB_STATE_TTL_MS) return;

            // Extract the original mode to handle joint diptych correctly across reloads
            const originalMode = payload?.mode === 'joint_diptych' ? 'joint_diptych' : 'single';

            cleaned[stableKey] = {
                shotId: stableShotId,
                kind: stableKind,
                jobId: stableJobId,
                startedAt: startedAt || now,
                mode: originalMode,
                ...buildShotJobMeta(stableShotId, stableKind, payload),
            };
        });
        return cleaned;
    }, [IMAGE_JOB_STATE_TTL_MS, buildShotJobMeta]);

    const readImageJobStateStorage = useCallback(() => {
        if (!imageJobStateStorageKey) return {};
        try {
            const raw = localStorage.getItem(imageJobStateStorageKey);
            if (!raw) return {};
            const parsed = JSON.parse(raw);
            return normalizeImageJobState(parsed);
        } catch (e) {
            console.warn('Failed to read shot image job state', e);
            return {};
        }
    }, [imageJobStateStorageKey, normalizeImageJobState]);

    const writeImageJobStateStorage = useCallback((state) => {
        if (!imageJobStateStorageKey) return;
        try {
            const normalized = normalizeImageJobState(state);
            pendingImageJobsRef.current = { ...normalized };
            if (Object.keys(normalized).length === 0) {
                localStorage.removeItem(imageJobStateStorageKey);
                return;
            }
            localStorage.setItem(imageJobStateStorageKey, JSON.stringify(normalized));
        } catch (e) {
            console.warn('Failed to write shot image job state', e);
        }
    }, [imageJobStateStorageKey, normalizeImageJobState]);

    const writeVideoJobStateStorage = useCallback((state) => {
        if (!videoJobStateStorageKey) return;
        try {
            const normalized = state && typeof state === 'object' ? state : {};
            if (Object.keys(normalized).length === 0) {
                localStorage.removeItem(videoJobStateStorageKey);
                return;
            }
            localStorage.setItem(videoJobStateStorageKey, JSON.stringify(normalized));
        } catch (e) {
            console.warn('Failed to write shot video job state', e);
        }
    }, [videoJobStateStorageKey]);

    const setPendingVideoJob = useCallback((shotId, jobId, options = {}) => {
        const stableShotId = String(shotId || '').trim();
        const stableJobId = String(jobId || '').trim();
        if (!stableShotId || !stableJobId) return;
        const prev = readVideoJobStateStorage();
        const next = {
            ...prev,
            [stableShotId]: {
                jobId: stableJobId,
                startedAt: Number(options?.startedAt || 0) || Date.now(),
                ...buildShotJobMeta(stableShotId, 'video', options),
            },
        };
        writeVideoJobStateStorage(next);
    }, [buildShotJobMeta, readVideoJobStateStorage, writeVideoJobStateStorage]);

    const clearPendingVideoJob = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return;
        const prev = readVideoJobStateStorage();
        if (!Object.prototype.hasOwnProperty.call(prev, stableShotId)) return;
        const next = { ...prev };
        delete next[stableShotId];
        writeVideoJobStateStorage(next);
    }, [readVideoJobStateStorage, writeVideoJobStateStorage]);

    const releaseShotVideoUiByShotId = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return;
        clearPendingVideoJob(stableShotId);
        setShotGeneratingState(stableShotId, 'video', false);
    }, [clearPendingVideoJob, setShotGeneratingState]);

    const clearPendingVideoJobsByJobId = useCallback((jobId) => {
        const stableJobId = String(jobId || '').trim();
        if (!stableJobId) return;
        const prev = readVideoJobStateStorage();
        const next = {};
        let changed = false;
        Object.entries(prev).forEach(([shotId, payload]) => {
            const existingJobId = String(payload?.jobId || '').trim();
            if (existingJobId === stableJobId) {
                changed = true;
                return;
            }
            next[shotId] = payload;
        });
        if (changed) {
            writeVideoJobStateStorage(next);
        }
    }, [readVideoJobStateStorage, writeVideoJobStateStorage]);

    const releaseShotVideoUiByJobId = useCallback((jobId) => {
        const stableJobId = String(jobId || '').trim();
        if (!stableJobId) return;
        const prev = readVideoJobStateStorage();
        const matchedShotIds = Object.entries(prev)
            .filter(([, payload]) => String(payload?.jobId || '').trim() === stableJobId)
            .map(([shotId]) => String(shotId || '').trim())
            .filter(Boolean);

        if (matchedShotIds.length > 0) {
            matchedShotIds.forEach((shotId) => {
                setShotGeneratingState(shotId, 'video', false);
            });
        }

        clearPendingVideoJobsByJobId(stableJobId);
    }, [clearPendingVideoJobsByJobId, readVideoJobStateStorage, setShotGeneratingState]);

    const getPendingVideoJobId = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return '';
        const all = readVideoJobStateStorage();
        return String(all?.[stableShotId]?.jobId || '').trim();
    }, [readVideoJobStateStorage]);

    const setPendingImageJob = useCallback((shotId, kind, jobId, options = {}) => {
        const stableShotId = String(shotId || '').trim();
        const stableKind = kind === 'end' ? 'end' : 'start';
        const stableJobId = String(jobId || '').trim();
        if (!stableShotId || !stableJobId) return;
        const prev = readImageJobStateStorage();
        const key = `${stableShotId}:${stableKind}`;
        const next = {
            ...prev,
            [key]: {
                shotId: stableShotId,
                kind: stableKind,
                jobId: stableJobId,
                startedAt: Number(options?.startedAt || 0) || Date.now(),
                mode: options?.mode === 'joint_diptych' ? 'joint_diptych' : 'single',
                ...buildShotJobMeta(stableShotId, stableKind, options),
            },
        };
        writeImageJobStateStorage(next);
    }, [buildShotJobMeta, readImageJobStateStorage, writeImageJobStateStorage]);

    const getPendingImageJobId = useCallback((shotId, kind) => {
        const stableShotId = String(shotId || '').trim();
        const stableKind = kind === 'end' ? 'end' : 'start';
        if (!stableShotId) return '';
        const key = `${stableShotId}:${stableKind}`;
        const inMemory = pendingImageJobsRef.current[key];
        if (inMemory && typeof inMemory === 'object') {
            return String(inMemory.jobId || '').trim();
        }
        if (typeof inMemory === 'string') {
            return String(inMemory || '').trim();
        }
        const all = readImageJobStateStorage();
        return String(all?.[key]?.jobId || '').trim();
    }, [readImageJobStateStorage]);

    const getPendingImageJobPayload = useCallback((shotId, kind) => {
        const stableShotId = String(shotId || '').trim();
        const stableKind = kind === 'end' ? 'end' : 'start';
        if (!stableShotId) return null;
        const key = `${stableShotId}:${stableKind}`;
        const inMemory = pendingImageJobsRef.current[key];
        if (inMemory && typeof inMemory === 'object') {
            return inMemory;
        }
        const all = readImageJobStateStorage();
        return all?.[key] || null;
    }, [readImageJobStateStorage]);

    const clearPendingImageJob = useCallback((shotId, kind) => {
        const stableShotId = String(shotId || '').trim();
        const stableKind = kind === 'end' ? 'end' : 'start';
        if (!stableShotId) return;
        const key = `${stableShotId}:${stableKind}`;
        const prev = readImageJobStateStorage();
        if (!Object.prototype.hasOwnProperty.call(prev, key)) {
            delete pendingImageJobsRef.current[key];
            return;
        }
        const next = { ...prev };
        delete next[key];
        writeImageJobStateStorage(next);
    }, [readImageJobStateStorage, writeImageJobStateStorage]);

    const setPendingJointDiptychImageJob = useCallback((shotId, jobId, options = {}) => {
        const stableShotId = String(shotId || '').trim();
        const stableJobId = String(jobId || '').trim();
        if (!stableShotId || !stableJobId) return;
        const prev = readImageJobStateStorage();
        const startedAt = Number(options?.startedAt || 0) || Date.now();
        const next = {
            ...prev,
            [`${stableShotId}:start`]: {
                shotId: stableShotId,
                kind: 'start',
                jobId: stableJobId,
                startedAt,
                mode: 'joint_diptych',
                ...buildShotJobMeta(stableShotId, 'start', options),
            },
            [`${stableShotId}:end`]: {
                shotId: stableShotId,
                kind: 'end',
                jobId: stableJobId,
                startedAt,
                mode: 'joint_diptych',
                ...buildShotJobMeta(stableShotId, 'end', options),
            },
        };
        writeImageJobStateStorage(next);
    }, [buildShotJobMeta, readImageJobStateStorage, writeImageJobStateStorage]);

    const clearPendingJointDiptychImageJob = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return;
        clearPendingImageJob(stableShotId, 'start');
        clearPendingImageJob(stableShotId, 'end');
    }, [clearPendingImageJob]);

    const forceClearShotImageJob = useCallback(async ({ shotId, kind, payload, reason }) => {
        const stableShotId = String(shotId || payload?.ownerShotId || '').trim();
        const stableKind = kind === 'end' ? 'end' : 'start';
        const stableJobId = String(payload?.jobId || '').trim();
        const isJointDiptych = payload?.mode === 'joint_diptych';
        const ownerLabel = describeShotJobOwner(payload, stableShotId, stableKind);
        const reasonText = String(reason || 'forced clear').trim();

        if (stableJobId) {
            try {
                await stopGenerationJob('image', stableJobId, { force: true });
            } catch {
                // Best effort stop.
            }
            try {
                await deleteGenerationJob('image', stableJobId);
            } catch {
                // Best effort delete.
            }
        }

        if (isJointDiptych) {
            clearPendingJointDiptychImageJob(stableShotId);
            setShotGeneratingState(stableShotId, 'start', false);
            setShotGeneratingState(stableShotId, 'end', false);
            setShotGeneratingState(stableShotId, 'cropping', false);
        } else {
            clearPendingImageJob(stableShotId, stableKind);
            setShotGeneratingState(stableShotId, stableKind, false);
        }

        onLog?.(`Shot image job force-cleared: ${ownerLabel}. Reason: ${reasonText}`, 'warning');
    }, [clearPendingImageJob, clearPendingJointDiptychImageJob, deleteGenerationJob, describeShotJobOwner, onLog, setShotGeneratingState, stopGenerationJob]);

    const forceClearShotVideoJob = useCallback(async ({ shotId, payload, reason }) => {
        const stableShotId = String(shotId || payload?.ownerShotId || '').trim();
        const stableJobId = String(payload?.jobId || '').trim();
        const ownerLabel = describeShotJobOwner(payload, stableShotId, 'video');
        const reasonText = String(reason || 'forced clear').trim();

        if (stableJobId) {
            try {
                await stopGenerationJob('video', stableJobId, { force: true });
            } catch {
                // Best effort stop.
            }
            try {
                await deleteGenerationJob('video', stableJobId);
            } catch {
                // Best effort delete.
            }
            delete pausedResumeVideoJobsRef.current[stableJobId];
        }

        clearPendingVideoJob(stableShotId);
        setShotGeneratingState(stableShotId, 'video', false);
        onLog?.(`Shot video job force-cleared: ${ownerLabel}. Reason: ${reasonText}`, 'warning');
    }, [clearPendingVideoJob, deleteGenerationJob, describeShotJobOwner, onLog, setShotGeneratingState, stopGenerationJob]);

    const clearPendingImageJobsByJobId = useCallback((jobId) => {
        const stableJobId = String(jobId || '').trim();
        if (!stableJobId) return;
        const prev = readImageJobStateStorage();
        const next = {};
        let changed = false;
        Object.entries(prev).forEach(([key, payload]) => {
            const existingJobId = String(payload?.jobId || '').trim();
            if (existingJobId === stableJobId) {
                changed = true;
                return;
            }
            next[key] = payload;
        });
        if (changed) {
            writeImageJobStateStorage(next);
        }
    }, [readImageJobStateStorage, writeImageJobStateStorage]);

    const releaseShotImageUiByShotId = useCallback((shotId, kind) => {
        const stableShotId = String(shotId || '').trim();
        const stableKind = kind === 'end' ? 'end' : 'start';
        if (!stableShotId) return;
        clearPendingImageJob(stableShotId, stableKind);
        setShotGeneratingState(stableShotId, stableKind, false);
    }, [clearPendingImageJob, setShotGeneratingState]);

    const releaseShotJointDiptychUiByShotId = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return;
        clearPendingJointDiptychImageJob(stableShotId);
        setShotGeneratingState(stableShotId, 'start', false);
        setShotGeneratingState(stableShotId, 'end', false);
        setShotGeneratingState(stableShotId, 'cropping', false);
    }, [clearPendingJointDiptychImageJob, setShotGeneratingState]);

    const clearLocalShotBatchUiState = useCallback((sceneIdOverride) => {
        const stableSceneId = String((sceneIdOverride ?? selectedSceneIdRef.current) || 'all').trim() || 'all';
        const prev = readGenerationStateStorage();
        const next = {};

        Object.entries(prev || {}).forEach(([shotId, value]) => {
            const stableShotId = String(shotId || '').trim();
            const shotSceneId = String(resolveShotSceneId(stableShotId) || '').trim();
            const matchesScene = stableSceneId === 'all' || (shotSceneId && shotSceneId === stableSceneId);
            if (!matchesScene) {
                next[stableShotId] = value;
                return;
            }

            const keepVideo = Boolean(value?.video);
            if (keepVideo) {
                next[stableShotId] = {
                    ...value,
                    start: false,
                    end: false,
                    startAt: 0,
                    endAt: 0,
                };
            }
        });

        writeGenerationStateStorage(next);
        generatingStateByShotRef.current = next;
        setGeneratingStateByShot(next);
    }, [readGenerationStateStorage, resolveShotSceneId, writeGenerationStateStorage]);

    const forceStopLocalShotBatchJobs = useCallback(async ({ sceneIdOverride, mode, reason }) => {
        const stableEpisodeId = String(activeEpisode?.id || '').trim();
        if (!stableEpisodeId) return 0;
        const stableSceneId = String((sceneIdOverride ?? selectedSceneIdRef.current) || 'all').trim() || 'all';
        const stableMode = String(mode || '').trim();
        const allImageJobs = readImageJobStateStorage();
        const handledKeys = new Set();
        let stoppedCount = 0;

        const entries = Object.entries(allImageJobs || {});
        for (const [key, payload] of entries) {
            if (!payload || typeof payload !== 'object') continue;
            if (handledKeys.has(key)) continue;

            const ownerScopeId = String(payload?.ownerScopeId || '').trim();
            const ownerSceneId = String(payload?.ownerSceneId || '').trim();
            const stableShotId = String(payload?.shotId || payload?.ownerShotId || '').trim();
            const payloadMode = payload?.mode === 'joint_diptych' ? 'joint_diptych' : 'single';
            const matchesEpisode = ownerScopeId === stableEpisodeId;
            const matchesScene = stableSceneId === 'all' || (ownerSceneId && ownerSceneId === stableSceneId) || (stableShotId && String(resolveShotSceneId(stableShotId) || '').trim() === stableSceneId);
            const matchesMode = stableMode === 'joint-diptych-local' ? payloadMode === 'joint_diptych' : payloadMode === 'single';

            if (!matchesEpisode || !matchesScene || !matchesMode || !stableShotId) continue;

            if (payloadMode === 'joint_diptych') {
                handledKeys.add(`${stableShotId}:start`);
                handledKeys.add(`${stableShotId}:end`);
                await forceClearShotImageJob({
                    shotId: stableShotId,
                    kind: 'start',
                    payload,
                    reason,
                });
                stoppedCount += 1;
                continue;
            }

            handledKeys.add(key);
            await forceClearShotImageJob({
                shotId: stableShotId,
                kind: payload?.kind === 'end' ? 'end' : 'start',
                payload,
                reason,
            });
            stoppedCount += 1;
        }

        clearLocalShotBatchUiState(stableSceneId);
        return stoppedCount;
    }, [activeEpisode?.id, clearLocalShotBatchUiState, forceClearShotImageJob, readImageJobStateStorage, resolveShotSceneId]);

    const releaseShotImageUiByJobId = useCallback((jobId) => {
        const stableJobId = String(jobId || '').trim();
        if (!stableJobId) return;
        const prev = readImageJobStateStorage();
        Object.entries(prev || {}).forEach(([key, payload]) => {
            if (String(payload?.jobId || '').trim() !== stableJobId) return;
            const [shotId, kind] = String(key || '').split(':');
            if (shotId) {
                setShotGeneratingState(shotId, kind === 'end' ? 'end' : 'start', false);
            }
        });
        clearPendingImageJobsByJobId(stableJobId);
    }, [clearPendingImageJobsByJobId, readImageJobStateStorage, setShotGeneratingState]);

    const isMissingJobError = useCallback((error) => {
        const detail = String(error?.response?.data?.detail || error?.message || '').trim().toLowerCase();
        return detail.includes('job not found') || detail.includes('not found');
    }, []);

    const isClientInterruptionError = useCallback((error) => {
        const detail = String(
            error?.code || error?.name || error?.message || error?.response?.data?.detail || ''
        ).trim().toLowerCase();
        return (
            detail.includes('canceled')
            || detail.includes('cancelled')
            || detail.includes('aborted')
            || detail.includes('econnaborted')
            || detail.includes('network error')
            || detail.includes('timeout')
        );
    }, []);

    const findMatchingShotMediaJobInPool = useCallback(async ({ shotId, kind, assetType = '' }) => {
        const stableShotId = String(shotId || '').trim();
        const stableKind = String(kind || '').trim().toLowerCase();
        const stableAssetType = String(assetType || '').trim().toLowerCase();
        if (!stableShotId || !stableKind) return null;

        const data = await getGenerationJobPool({
            kind: stableKind,
            running_only: true,
            limit: 200,
        });
        const items = Array.isArray(data?.items) ? data.items : [];
        const projectIdText = String(projectId || '').trim();

        return items.find((item) => {
            const itemShotId = String(item?.shot_id || '').trim();
            const itemProjectId = String(item?.project_id || '').trim();
            const itemAssetType = String(item?.asset_type || '').trim().toLowerCase();

            if (!itemShotId || itemShotId !== stableShotId) return false;
            if (projectIdText && itemProjectId && itemProjectId !== projectIdText) return false;
            if (stableKind === 'image' && stableAssetType && itemAssetType && itemAssetType !== stableAssetType) return false;
            return true;
        }) || null;
    }, [projectId]);

    const syncShotMediaRuntimeState = useCallback(async ({
        shotId,
        mediaKey,
        preferPoolLookup = true,
        releaseIfMissing = true,
    }) => {
        const stableShotId = String(shotId || '').trim();
        const stableMediaKey = mediaKey === 'video' ? 'video' : (mediaKey === 'end' ? 'end' : 'start');
        if (!stableShotId) {
            return { state: 'idle', jobId: '', source: 'none' };
        }

        const isVideo = stableMediaKey === 'video';
        const assetType = stableMediaKey === 'end' ? 'end_frame' : (stableMediaKey === 'start' ? 'start_frame' : '');
        const shotState = generatingStateByShotRef.current[String(stableShotId)] || { start: false, end: false, video: false };
        const hasGeneratingFlag = Boolean(shotState?.[stableMediaKey]);
        const startedAtMs = Number(shotState?.[`${stableMediaKey}At`] || 0);
        const withinStartupGrace = Boolean(
            hasGeneratingFlag
            && startedAtMs > 0
            && (Date.now() - startedAtMs) < SHOT_MEDIA_STARTUP_GRACE_MS
        );

        const getJobId = () => (
            isVideo
                ? getPendingVideoJobId(stableShotId)
                : getPendingImageJobId(stableShotId, stableMediaKey)
        );

        const setJobId = (jobId) => {
            const stableJobId = String(jobId || '').trim();
            if (!stableJobId) return;
            if (isVideo) {
                setPendingVideoJob(stableShotId, stableJobId);
            } else {
                setPendingImageJob(stableShotId, stableMediaKey, stableJobId);
            }
            setShotGeneratingState(stableShotId, stableMediaKey, true);
        };

        const releaseUi = () => {
            if (isVideo) {
                releaseShotVideoUiByShotId(stableShotId);
            } else {
                releaseShotImageUiByShotId(stableShotId, stableMediaKey);
            }
        };

        const readStatus = async (jobId) => {
            const stableJobId = String(jobId || '').trim();
            if (!stableJobId) return { state: 'idle', jobId: '', source: 'none' };

            try {
                const status = isVideo
                    ? await getVideoGenerationJobStatus(stableJobId)
                    : await getImageGenerationJobStatus(stableJobId);
                const phase = String(status?.status || '').trim().toLowerCase();

                if (phase === 'queued' || phase === 'running') {
                    setShotGeneratingState(stableShotId, stableMediaKey, true);
                    return { state: 'running', jobId: stableJobId, source: 'local', phase };
                }

                if (releaseIfMissing) {
                    releaseUi();
                }
                return { state: 'terminal', jobId: stableJobId, source: 'local', phase };
            } catch (error) {
                if (isMissingJobError(error)) {
                    return { state: 'missing', jobId: stableJobId, source: 'local' };
                }
                return { state: 'unknown', jobId: stableJobId, source: 'local', error };
            }
        };

        const localJobId = getJobId();
        if (localJobId) {
            const localState = await readStatus(localJobId);
            if (localState.state === 'running' || localState.state === 'terminal' || localState.state === 'unknown') {
                return localState;
            }
        }

        if (!preferPoolLookup && !hasGeneratingFlag) {
            return { state: 'idle', jobId: localJobId, source: 'none' };
        }

        try {
            const matched = await findMatchingShotMediaJobInPool({
                shotId: stableShotId,
                kind: isVideo ? 'video' : 'image',
                assetType,
            });
            const matchedJobId = String(matched?.job_id || '').trim();
            if (matchedJobId) {
                setJobId(matchedJobId);
                return { state: 'running', jobId: matchedJobId, source: 'pool' };
            }
        } catch (error) {
            return { state: 'unknown', jobId: localJobId, source: 'pool', error };
        }

        if (withinStartupGrace) {
            setShotGeneratingState(stableShotId, stableMediaKey, true);
            return { state: 'running', jobId: localJobId, source: 'bootstrap' };
        }

        if (releaseIfMissing && (hasGeneratingFlag || localJobId)) {
            releaseUi();
        }

        return { state: 'idle', jobId: '', source: 'none' };
    }, [
        findMatchingShotMediaJobInPool,
        getPendingImageJobId,
        getPendingVideoJobId,
        isMissingJobError,
        releaseShotImageUiByShotId,
        releaseShotVideoUiByShotId,
        setPendingImageJob,
        setPendingVideoJob,
        setShotGeneratingState,
        SHOT_MEDIA_STARTUP_GRACE_MS,
    ]);

    const tryRecoverShotMediaAfterInterruption = useCallback(async ({ shotId, mediaKey }) => {
        const stableShotId = String(shotId || '').trim();
        const stableMediaKey = mediaKey === 'video' ? 'video' : (mediaKey === 'end' ? 'end' : 'start');
        if (!stableShotId) return false;

        const resolved = await syncShotMediaRuntimeState({
            shotId: stableShotId,
            mediaKey: stableMediaKey,
            preferPoolLookup: true,
            releaseIfMissing: false,
        });

        if (resolved?.state !== 'running') return false;

        const mediaLabel = stableMediaKey === 'video'
            ? t('视频', 'Video')
            : stableMediaKey === 'end'
                ? t('结束帧', 'End Frame')
                : t('起始帧', 'Start Frame');
        const jobSuffix = resolved?.jobId ? ` job_id=${resolved.jobId}` : '';

        onLog?.(
            `${mediaLabel}${t('提交响应中断，但已恢复后端运行任务。', ' submit response was interrupted, but the backend running task was recovered.')}${jobSuffix}`,
            'warning'
        );
        showNotification(t('已恢复后台运行任务', 'Recovered background running task'), 'info');
        return true;
    }, [onLog, showNotification, syncShotMediaRuntimeState, t]);

    useEffect(() => {
        pendingImageJobsRef.current = readImageJobStateStorage();
    }, [activeEpisode?.id, readImageJobStateStorage]);

    useEffect(() => {
        hasHydratedGenerationStateRef.current = false;
        if (!generationStateStorageKey) {
            setGeneratingStateByShot({});
            hasHydratedGenerationStateRef.current = true;
            return;
        }
        const restored = readGenerationStateStorage();
        const now = Date.now();
        const cleaned = {};
        Object.entries(restored).forEach(([shotId, state]) => {
            const next = { ...state };
            if (next.start && next.startAt && now - next.startAt > GENERATION_STATE_TTL_MS) {
                next.start = false;
                next.startAt = 0;
            }
            if (next.end && next.endAt && now - next.endAt > GENERATION_STATE_TTL_MS) {
                next.end = false;
                next.endAt = 0;
            }
            if (next.video && next.videoAt && now - next.videoAt > GENERATION_STATE_TTL_MS) {
                next.video = false;
                next.videoAt = 0;
            }
            if (next.start || next.end || next.video) cleaned[shotId] = next;
        });
        setGeneratingStateByShot(cleaned);
        writeGenerationStateStorage(cleaned);
        hasHydratedGenerationStateRef.current = true;
    }, [generationStateStorageKey, readGenerationStateStorage, writeGenerationStateStorage]);

    useEffect(() => {
        if (!hasHydratedGenerationStateRef.current) return;
        writeGenerationStateStorage(generatingStateByShot);
    }, [generatingStateByShot, writeGenerationStateStorage]);

    useEffect(() => {
        if (!activeEpisode?.id) {
            setIsBatchGenerating(false);
            setBatchProgress(createShotBatchProgressState());
            return;
        }
        const restored = loadShotBatchRuntime(activeEpisode.id, selectedSceneId);
        if (!restored) {
            setIsBatchGenerating(false);
            setBatchProgress(createShotBatchProgressState());
            return;
        }
        if (restored.running && isLocalShotBatchMode(restored.progress?.mode)) {
            setIsBatchGenerating(true);
            setBatchProgress(restored.progress || createShotBatchProgressState());
            return;
        }
        setIsBatchGenerating(Boolean(restored.running));
        setBatchProgress(restored.progress || createShotBatchProgressState());
    }, [activeEpisode?.id, selectedSceneId, loadShotBatchRuntime, createShotBatchProgressState, isLocalShotBatchMode]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        saveShotBatchRuntime(activeEpisode.id, selectedSceneId, isBatchGenerating, batchProgress);
    }, [activeEpisode?.id, selectedSceneId, isBatchGenerating, batchProgress, saveShotBatchRuntime]);

    useEffect(() => {
        if (!activeEpisode?.id) return undefined;
        const mode = String(batchProgress?.mode || '');
        const isDetachedLocalBatch = isLocalShotBatchMode(mode) && Boolean(isBatchGenerating) && !shotLocalBatchSessionRef.current;
        if (!isDetachedLocalBatch) return undefined;

        const syncDetachedState = () => {
            const restored = loadShotBatchRuntime(activeEpisode.id, selectedSceneId);
            if (restored) {
                const nextRunning = Boolean(restored.running);
                const nextProgress = restored.progress || createShotBatchProgressState();
                isBatchGeneratingRef.current = nextRunning;
                batchProgressRef.current = nextProgress;
                setIsBatchGenerating(nextRunning);
                setBatchProgress((prev) => {
                    const prevSerialized = JSON.stringify(prev || {});
                    const nextSerialized = JSON.stringify(nextProgress || {});
                    return prevSerialized === nextSerialized ? prev : nextProgress;
                });
            }

            const storedGeneratingState = readGenerationStateStorage();
            setGeneratingStateByShot((prev) => {
                const prevSerialized = JSON.stringify(prev || {});
                const nextSerialized = JSON.stringify(storedGeneratingState || {});
                return prevSerialized === nextSerialized ? prev : storedGeneratingState;
            });
        };

        syncDetachedState();
        const intervalId = window.setInterval(syncDetachedState, 1000);
        return () => window.clearInterval(intervalId);
    }, [activeEpisode?.id, batchProgress?.mode, createShotBatchProgressState, isBatchGenerating, isLocalShotBatchMode, loadShotBatchRuntime, readGenerationStateStorage, selectedSceneId]);

    useEffect(() => {
        isBatchGeneratingRef.current = Boolean(isBatchGenerating);
    }, [isBatchGenerating]);

    useEffect(() => {
        batchProgressRef.current = batchProgress || { current: 0, total: 0, status: '' };
    }, [batchProgress]);

    const currentGeneratingState = editingShot?.id
        ? (generatingStateByShot[String(editingShot.id)] || { start: false, end: false, video: false, startAt: 0, endAt: 0, videoAt: 0 })
        : { start: false, end: false, video: false };
    const currentShotGenerating = Boolean(currentGeneratingState.start || currentGeneratingState.end || currentGeneratingState.video);
    const currentVoiceGenerating = editingShot?.id
        ? !!voiceGeneratingByShot[String(editingShot.id)]
        : false;
    const isShotFrameActionLocked = useCallback(
        (frameType) => Boolean(currentGeneratingState?.[frameType === 'end' ? 'end' : 'start']),
        [currentGeneratingState]
    );
    const notifyShotFrameActionLocked = useCallback(
        (frameType) => {
            showNotification(
                frameType === 'end'
                    ? t('结束帧任务运行中，暂时不能更换或删除图片。', 'End frame job is running; image replacement and removal are temporarily disabled.')
                    : t('起始帧任务运行中，暂时不能更换或删除图片。', 'Start frame job is running; image replacement and removal are temporarily disabled.'),
                'warning'
            );
        },
        [showNotification, t]
    );
    const hasActiveGeneration = useMemo(
        () => Object.values(generatingStateByShot || {}).some(s => !!(s?.start || s?.end || s?.video || s?.cropping)),
        [generatingStateByShot]
    );

    const [assetDetailModal, setAssetDetailModal] = useState({ open: false, type: 'start', keyframeIndex: -1 });
    const [frameTrimModal, setFrameTrimModal] = useState(() => createInitialFrameTrimState());
    const [shotImageCfgDefault, setShotImageCfgDefault] = useState(() => resolveShotImageCfgDefault(getCachedUserPreferences()));
    const [shotImageCfgValue, setShotImageCfgValue] = useState(() => resolveShotImageCfgDefault(getCachedUserPreferences()));
    const [shotAssetsMetaIndex, setShotAssetsMetaIndex] = useState({});
    const [shotAssetsMetaLoading, setShotAssetsMetaLoading] = useState(false);
    const [shotAssetsRefreshKey, setShotAssetsRefreshKey] = useState(0);
    const refreshShotAssetsMeta = useCallback(() => setShotAssetsRefreshKey(k => k + 1), []);

    const syncShotImageCfgFromSettings = useCallback(() => {
        const nextDefault = resolveShotImageCfgDefault(getCachedUserPreferences());
        setShotImageCfgDefault(nextDefault);
        setShotImageCfgValue(nextDefault);
        return nextDefault;
    }, []);

    const openAssetDetailModal = (type, keyframeIndex = -1) => {
        if (type === 'start' || type === 'end' || type === 'keyframe') {
            syncShotImageCfgFromSettings();
        }
        setTempPromptSubmitLang('');
        setShowPromptLangMenu(false);
        setAssetDetailModal({ open: true, type, keyframeIndex });
    };

    const closeAssetDetailModal = () => {
        setTempPromptSubmitLang('');
        setShowPromptLangMenu(false);
        setAssetDetailModal({ open: false, type: 'start', keyframeIndex: -1 });
    };

    const closeFrameTrimModal = useCallback(() => {
        setFrameTrimModal(createInitialFrameTrimState());
    }, []);

    const openFrameTrimModal = useCallback((type) => {
        let tech = {};
        try {
            tech = JSON.parse(editingShot?.technical_notes || '{}');
        } catch (e) {
            tech = {};
        }

        const sourceUrl = type === 'end'
            ? String(tech?.end_frame_url || '').trim()
            : String(editingShot?.image_url || '').trim();

        if (!sourceUrl) {
            showNotification(
                type === 'end'
                    ? t('当前没有可裁边的结束帧。', 'There is no end frame to trim.')
                    : t('当前没有可裁边的起始帧。', 'There is no start frame to trim.'),
                'warning'
            );
            return;
        }

        setFrameTrimModal({
            open: true,
            type: type === 'end' ? 'end' : 'start',
            sourceUrl,
            topPct: 0,
            rightPct: 0,
            bottomPct: 0,
            leftPct: 0,
            saving: false,
        });
    }, [editingShot?.image_url, editingShot?.technical_notes, showNotification, t]);

    const normalizeAssetUrlToken = useCallback((value) => {
        const raw = String(value || '').trim();
        if (!raw) return '';
        try {
            const parsed = new URL(raw, BASE_URL || window.location.origin);
            return `${parsed.origin}${parsed.pathname}`.toLowerCase();
        } catch (e) {
            return raw.split('?')[0].split('#')[0].toLowerCase();
        }
    }, []);

    const updateFrameTrimMargin = useCallback((key, value) => {
        setFrameTrimModal((prev) => ({
            ...prev,
            [key]: clampFrameTrimPercent(value),
        }));
    }, []);

    const loadImageElementFromBlob = useCallback((blob) => {
        return new Promise((resolve, reject) => {
            const objectUrl = URL.createObjectURL(blob);
            const image = new Image();

            const cleanup = () => {
                URL.revokeObjectURL(objectUrl);
            };

            image.onload = () => {
                cleanup();
                resolve(image);
            };
            image.onerror = () => {
                cleanup();
                reject(new Error('failed to load generated image for splitting'));
            };
            image.src = objectUrl;
        });
    }, []);

    const applyFrameTrimToShot = useCallback(async () => {
        if (!editingShot?.id || !frameTrimModal?.open || frameTrimModal?.saving) return;

        const targetType = frameTrimModal.type === 'end' ? 'end' : 'start';
        const normalizedMargins = normalizeFrameTrimMargins(frameTrimModal);
        const widthRatio = normalizedMargins.widthPct / 100;
        const heightRatio = normalizedMargins.heightPct / 100;

        if (widthRatio <= 0 || heightRatio <= 0) {
            showNotification(t('裁边范围无效，请调整四边数值。', 'Invalid trim area. Adjust the edge values and try again.'), 'warning');
            return;
        }

        setFrameTrimModal((prev) => ({ ...prev, saving: true }));
        setShotGeneratingState(editingShot.id, targetType, true);

        try {
            const sourceResp = await fetch(getFullUrl(frameTrimModal.sourceUrl));
            if (!sourceResp.ok) {
                throw new Error(`failed to download source image (${sourceResp.status})`);
            }

            const sourceBlob = await sourceResp.blob();
            const sourceImage = await loadImageElementFromBlob(sourceBlob);
            const sourceWidth = Number(sourceImage?.naturalWidth || sourceImage?.width || 0);
            const sourceHeight = Number(sourceImage?.naturalHeight || sourceImage?.height || 0);

            if (!sourceWidth || !sourceHeight) {
                throw new Error('source image dimensions unavailable');
            }

            const cropX = Math.max(0, Math.round(sourceWidth * (normalizedMargins.leftPct / 100)));
            const cropY = Math.max(0, Math.round(sourceHeight * (normalizedMargins.topPct / 100)));
            const cropWidth = Math.max(1, Math.round(sourceWidth * widthRatio));
            const cropHeight = Math.max(1, Math.round(sourceHeight * heightRatio));

            const canvas = document.createElement('canvas');
            canvas.width = cropWidth;
            canvas.height = cropHeight;
            const ctx = canvas.getContext('2d');
            if (!ctx) {
                throw new Error('canvas context unavailable');
            }
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(sourceImage, cropX, cropY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);

            const trimmedBlob = await new Promise((resolve, reject) => {
                canvas.toBlob((blob) => {
                    if (!blob) {
                        reject(new Error('failed to encode trimmed image'));
                        return;
                    }
                    resolve(blob);
                }, 'image/jpeg', 0.95);
            });

            const trimmedFile = new File(
                [trimmedBlob],
                `shot_${editingShot.id}_${targetType}_trimmed_${Date.now()}.jpg`,
                { type: 'image/jpeg' }
            );
            const trimUploadIdempotencyKey = buildShotFrameAssetUploadIdempotencyKey({
                operation: 'trim',
                shotId: editingShot.id,
                frameRole: targetType,
                sourceUrl: frameTrimModal.sourceUrl,
                margins: normalizedMargins,
            });

            const uploaded = await uploadAsset(trimmedFile, {
                project_id: projectId,
                episode_id: activeEpisode?.id,
                shot_id: editingShot.id,
                shot_number: editingShot.shot_id,
                shot_name: editingShot.shot_name,
                asset_type: targetType === 'end' ? 'end_frame' : 'start_frame',
                source_asset_url: frameTrimModal.sourceUrl,
                idempotency_key: trimUploadIdempotencyKey,
                remark: targetType === 'end' ? 'Trimmed end frame asset' : 'Trimmed start frame asset',
            });

            const nextUrl = String(uploaded?.url || '').trim();
            if (!nextUrl) {
                throw new Error('trimmed asset upload returned no url');
            }

            if (targetType === 'end') {
                let tech = {};
                try {
                    tech = JSON.parse(editingShot.technical_notes || '{}');
                    if (!tech || typeof tech !== 'object') tech = {};
                } catch (e) {
                    tech = {};
                }
                tech.end_frame_url = nextUrl;
                tech.video_gen_mode = 'start_end';
                const newData = { technical_notes: JSON.stringify(tech) };
                await onUpdateShot(editingShot.id, newData);
                setEditingShot((prev) => (prev ? { ...prev, ...newData } : prev));
            } else {
                const newData = { image_url: nextUrl };
                await onUpdateShot(editingShot.id, newData);
                setEditingShot((prev) => (prev ? { ...prev, ...newData } : prev));
            }

            refreshShotAssetsMeta();
            closeFrameTrimModal();
            onLog?.(targetType === 'end'
                ? t('结束帧裁边并回填完成。', 'End frame trimmed and applied.')
                : t('起始帧裁边并回填完成。', 'Start frame trimmed and applied.'), 'success');
            showNotification(targetType === 'end'
                ? t('结束帧裁边完成', 'End frame trimmed')
                : t('起始帧裁边完成', 'Start frame trimmed'), 'success');
        } catch (e) {
            const detail = e?.message || 'unknown error';
            onLog?.(`${t('裁边失败', 'Trim failed')}: ${detail}`, 'error');
            showNotification(`${t('裁边失败', 'Trim failed')}: ${detail}`, 'error');
            setFrameTrimModal((prev) => ({ ...prev, saving: false }));
        } finally {
            setShotGeneratingState(editingShot.id, targetType, false);
        }
    }, [activeEpisode?.id, closeFrameTrimModal, editingShot, frameTrimModal, loadImageElementFromBlob, onLog, onUpdateShot, projectId, refreshShotAssetsMeta, setShotGeneratingState, showNotification, t, uploadAsset]);

    const formatBytes = useCallback((bytesValue) => {
        const num = Number(bytesValue);
        if (!Number.isFinite(num) || num <= 0) {
            const text = String(bytesValue || '').trim();
            return text;
        }
        if (num >= 1024 * 1024 * 1024) return `${(num / 1024 / 1024 / 1024).toFixed(2)} GB`;
        if (num >= 1024 * 1024) return `${(num / 1024 / 1024).toFixed(2)} MB`;
        if (num >= 1024) return `${(num / 1024).toFixed(2)} KB`;
        return `${num} B`;
    }, []);

    const deriveAspectRatio = useCallback((width, height) => {
        const w = Number(width);
        const h = Number(height);
        if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return '';
        const gcd = (a, b) => {
            let x = Math.abs(Math.round(a));
            let y = Math.abs(Math.round(b));
            while (y) {
                const temp = y;
                y = x % y;
                x = temp;
            }
            return x || 1;
        };
        const divisor = gcd(w, h);
        return `${Math.round(w / divisor)}:${Math.round(h / divisor)}`;
    }, []);

    const parseResolution = useCallback((meta = {}) => {
        const width = Number(meta.width);
        const height = Number(meta.height);
        if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
            return { width, height, resolution: `${Math.round(width)}x${Math.round(height)}` };
        }
        const resolutionText = String(meta.resolution || '').trim();
        if (resolutionText) {
            const matched = resolutionText.match(/(\d+)\s*[xX]\s*(\d+)/);
            if (matched) {
                const parsedWidth = Number(matched[1]);
                const parsedHeight = Number(matched[2]);
                if (Number.isFinite(parsedWidth) && Number.isFinite(parsedHeight) && parsedWidth > 0 && parsedHeight > 0) {
                    return { width: parsedWidth, height: parsedHeight, resolution: `${parsedWidth}x${parsedHeight}` };
                }
            }
            return { width: null, height: null, resolution: resolutionText };
        }
        return { width: null, height: null, resolution: '' };
    }, []);

    const resolveShotAssetByUrl = useCallback((url, preferredType = '') => {
        const token = normalizeAssetUrlToken(url);
        if (!token) return null;
        const candidates = Array.isArray(shotAssetsMetaIndex[token]) ? shotAssetsMetaIndex[token] : [];
        if (candidates.length === 0) return null;
        const expectedType = String(preferredType || '').trim().toLowerCase();
        if (expectedType) {
            const matched = candidates.find((asset) => String(asset?.type || '').trim().toLowerCase() === expectedType);
            if (matched) return matched;
        }
        return candidates[0] || null;
    }, [normalizeAssetUrlToken, shotAssetsMetaIndex]);

    const buildShotAssetDetail = useCallback((asset, fallbackType = 'image', fallbackUrl = '') => {
        const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
        const { width, height, resolution } = parseResolution(meta);
        const aspectRatio = String(meta.aspect_ratio || meta.aspectRatio || '').trim() || deriveAspectRatio(width, height);
        const fileSize =
            String(meta.file_size_display || '').trim()
            || String(meta.size_display || '').trim()
            || formatBytes(meta.file_size_bytes)
            || formatBytes(meta.size)
            || formatBytes(meta.size_bytes)
            || String(meta.size || '').trim();
        const durationRaw = meta.duration;
        let durationText = '';
        if (durationRaw !== undefined && durationRaw !== null && String(durationRaw).trim() !== '') {
            const durationNum = Number(durationRaw);
            if (Number.isFinite(durationNum) && durationNum > 0) {
                durationText = `${Number(durationNum.toFixed(2))}s`;
            } else {
                durationText = String(durationRaw).trim();
            }
        }

        return {
            type: String(asset?.type || fallbackType || '').trim().toLowerCase(),
            url: String(asset?.url || fallbackUrl || '').trim(),
            filename: String(asset?.filename || '').trim(),
            createdAt: asset?.created_at ? new Date(asset.created_at).toLocaleString() : '',
            resolution,
            aspectRatio,
            fileSize,
            format: String(meta.format || '').trim(),
            duration: durationText,
            source: String(meta.source || '').trim(),
            provider: String(meta.provider || '').trim(),
            providerAlias: String(meta.provider_alias || '').trim(),
            model: String(meta.model || '').trim(),
            rawMeta: meta,
        };
    }, [deriveAspectRatio, formatBytes, parseResolution]);

    useEffect(() => {
        if (!editingShot?.id) {
            setShotAssetsMetaIndex({});
            setShotAssetsMetaLoading(false);
            return;
        }

        let active = true;
        const loadShotAssets = async () => {
            setShotAssetsMetaLoading(true);
            try {
                const params = { shot_id: editingShot.id, limit: 300 };
                if (projectId) params.project_id = projectId;
                const data = await fetchAssets(params);
                if (!active) return;

                const nextIndex = {};
                (Array.isArray(data) ? data : []).forEach((asset) => {
                    const token = normalizeAssetUrlToken(asset?.url);
                    if (!token) return;
                    if (!Array.isArray(nextIndex[token])) nextIndex[token] = [];
                    nextIndex[token].push(asset);
                });
                setShotAssetsMetaIndex(nextIndex);
            } catch (e) {
                console.error('Failed to load shot assets metadata', e);
                if (active) setShotAssetsMetaIndex({});
            } finally {
                if (active) setShotAssetsMetaLoading(false);
            }
        };

        loadShotAssets();
        return () => {
            active = false;
        };
    }, [editingShot?.id, normalizeAssetUrlToken, projectId, shotAssetsRefreshKey]);

    const overwriteShotField = useCallback((field, value, extra = {}) => {
        const nextValue = String(value ?? '');
        setEditingShot(prev => ({ ...(prev || {}), [field]: nextValue, ...extra }));
    }, []);

    const overwriteTechField = useCallback((key, value) => {
        const nextValue = String(value ?? '');
        setEditingShot(prev => {
            const current = prev || {};
            let techObj = {};
            try { techObj = JSON.parse(current.technical_notes || '{}'); } catch (e) {}
            techObj[key] = nextValue;
            return { ...current, technical_notes: JSON.stringify(techObj) };
        });
    }, []);

    const getShotVideoPromptEn = useCallback((shot) => {
        if (!shot || typeof shot !== 'object') return '';
        const primary = shot.video_content;
        if (primary !== undefined && primary !== null && String(primary) !== '') return String(primary);
        const legacy = shot.prompt;
        if (legacy !== undefined && legacy !== null) return String(legacy);
        return '';
    }, []);

    const buildVideoPromptEnUpdates = useCallback((value, extra = {}) => {
        const nextValue = String(value ?? '');
        return { video_content: nextValue, prompt: nextValue, ...extra };
    }, []);

    const parseTechnicalNotesSafe = useCallback((rawValue) => {
        try {
            const parsed = JSON.parse(rawValue || '{}');
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (e) {
            return {};
        }
    }, []);

    const mergeLiveSyncTechnicalNotes = useCallback((currentRaw, latestRaw) => {
        const currentNotes = parseTechnicalNotesSafe(currentRaw);
        const latestNotes = parseTechnicalNotesSafe(latestRaw);
        const syncedKeys = [
            'end_frame_url',
            'end_frame_reused_from_start',
            'keyframes',
            'keyframe_images',
            'voiceover_url',
            'voiceover_metadata',
            'voiceover_plan',
            'voiceover_plan_prompts',
        ];

        let changed = false;
        const nextNotes = { ...currentNotes };

        syncedKeys.forEach((key) => {
            const nextValue = latestNotes[key];
            const prevValue = currentNotes[key];
            if (nextValue === undefined) {
                if (Object.prototype.hasOwnProperty.call(nextNotes, key)) {
                    delete nextNotes[key];
                    changed = true;
                }
                return;
            }
            if (JSON.stringify(prevValue) !== JSON.stringify(nextValue)) {
                nextNotes[key] = nextValue;
                changed = true;
            }
        });

        return {
            changed,
            value: changed ? JSON.stringify(nextNotes) : String(currentRaw || '{}'),
        };
    }, [parseTechnicalNotesSafe]);

    const overwriteKeyframeCnMap = useCallback((timeKey, value) => {
        if (!timeKey) return;
        const nextValue = String(value ?? '');
        setEditingShot(prev => {
            const current = prev || {};
            let techObj = {};
            try { techObj = JSON.parse(current.technical_notes || '{}'); } catch (e) {}
            const nextMap = { ...(techObj.keyframe_prompt_cn_map || {}) };
            nextMap[timeKey] = nextValue;
            techObj.keyframe_prompt_cn_map = nextMap;
            return { ...current, technical_notes: JSON.stringify(techObj) };
        });
    }, []);

    const shotFilterStorageKey = useMemo(() => {
        if (!activeEpisode?.id) return '';
        return `aistory.shotFilters.${activeEpisode.id}`;
    }, [activeEpisode?.id]);

    useEffect(() => {
        if (!shotFilterStorageKey) return;
        try {
            const raw = localStorage.getItem(shotFilterStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                setSelectedSceneId(String(parsed.selectedSceneId || 'all'));
                setSceneCodeFilter(String(parsed.sceneCodeFilter || ''));
                setShotIdFilter(String(parsed.shotIdFilter || ''));
            }
        } catch (e) {
            console.warn('Failed to restore shot filters', e);
        }
    }, [shotFilterStorageKey]);

    useEffect(() => {
        if (!shotFilterStorageKey) return;
        try {
            localStorage.setItem(shotFilterStorageKey, JSON.stringify({
                selectedSceneId,
                sceneCodeFilter,
                shotIdFilter,
            }));
        } catch (e) {
            console.warn('Failed to persist shot filters', e);
        }
    }, [shotFilterStorageKey, selectedSceneId, sceneCodeFilter, shotIdFilter]);

    useEffect(() => {
        const sceneId = focusRequest?.sceneId;
        if (!sceneId) return;
        setSelectedSceneId(String(sceneId));
        setSceneCodeFilter('');
        setShotIdFilter('');
    }, [focusRequest?.nonce]);

    // Helper: Construct Global Context String from Episode Info
    const getShotGlobalStyleText = () => {
        const info = activeEpisode?.episode_info?.e_global_info;
        const projectInfo = project?.global_info;
        return String(
            info?.Global_Style
            || info?.global_style
            || projectInfo?.Global_Style
            || projectInfo?.global_style
            || ''
        ).trim();
    };

    const getGlobalContextStr = (options = {}) => {
        const info = activeEpisode?.episode_info?.e_global_info;
        if (!info) return "";
        const { includeStyle = true } = options || {};
        const parts = [];
        // Append explicit labels so the model understands the context
        const globalStyle = getShotGlobalStyleText();
        if (includeStyle && globalStyle) parts.push(`Style: ${globalStyle}`);
        if (info.tone) parts.push(`Tone: ${info.tone}`);
        
        return parts.length > 0 ? " | " + parts.join(", ") : "";
    };

    const prependEntityGlobalStyleToPromptHead = useCallback((text, options = {}) => {
        const rawText = String(text || '').trim();
        if (!rawText) return rawText;

        const { injectIfMissing = true } = options || {};
        const globalStyle = getShotGlobalStyleText();
        if (!globalStyle) return rawText;

        const tokenPattern = /[\[【]\s*(global style|global_style)\s*[\]】]/ig;
        const replaced = rawText.replace(tokenPattern, `[Global Style](${globalStyle})`);
        if (replaced !== rawText) return replaced;
        if (!injectIfMissing) return rawText;

        if (/\[Global Style\]\s*\(/i.test(rawText)) return rawText;
        if (rawText.toLowerCase().startsWith(globalStyle.toLowerCase())) return rawText;

        return `[Global Style](${globalStyle}). ${rawText}`;
    }, [activeEpisode?.episode_info?.e_global_info, project?.global_info]);

    const applyGlobalStyleToPrompt = useCallback((text, options = {}) => {
        return prependEntityGlobalStyleToPromptHead(text, options);
    }, [prependEntityGlobalStyleToPromptHead]);

    const openMediaPicker = (callback, context = {}) => {
        setPickerConfig({ isOpen: true, callback, context });
    };

    const refreshActiveSources = useCallback(async () => {
        try {
            const [settings, systemSettings] = await Promise.all([
                getSettings(),
                getSystemSettings(),
            ]);
            setActiveSources({
                Image: getSettingSourceByCategory(settings, 'Image'),
                Video: getSettingSourceByCategory(settings, 'Video'),
            });

            const activeImageSetting = (Array.isArray(settings) ? settings : [])
                .filter((item) => item?.category === 'Image' && item?.is_active)
                .sort((left, right) => Number(left?.id || 0) - Number(right?.id || 0))
                .pop();
            const activeImageSystemApiId = Number(
                activeImageSetting?.system_api_id
                || activeImageSetting?.config?.use_system_setting_id
                || 0
            );

            let activeImageModel = null;
            for (const group of (Array.isArray(systemSettings) ? systemSettings : [])) {
                if (String(group?.category || '').trim() !== 'Image') continue;
                for (const row of (Array.isArray(group?.models) ? group.models : [])) {
                    const rowId = Number(row?.id || 0);
                    if (activeImageSystemApiId > 0) {
                        if (rowId === activeImageSystemApiId) {
                            activeImageModel = row;
                            break;
                        }
                        continue;
                    }
                    if (row?.is_active) {
                        activeImageModel = row;
                        break;
                    }
                }
                if (activeImageModel) break;
            }

            setActiveImageCapabilityProfile(activeImageModel ? {
                id: Number(activeImageModel?.id || 0) || null,
                provider: String(activeImageModel?.provider || '').trim(),
                model: String(activeImageModel?.model || '').trim(),
                aspectRatios: collectSupportedAspectRatioOptions(
                    activeImageModel?.modality?.aspect_ratios || activeImageModel?.aspect_ratios || []
                ),
                imageSizeValues: collectSupportedImageSizeOptions(
                    activeImageModel?.modality?.image_size_values || activeImageModel?.image_size_values || []
                ),
            } : null);
        } catch (e) {
            console.error('Failed to load active setting sources in ShotsView', e);
            setActiveImageCapabilityProfile(null);
        }
    }, []);

    useEffect(() => {
        if (editingShot) {
            refreshActiveSources();
        }
    }, [editingShot?.id, refreshActiveSources]);

    useEffect(() => {
        if (!isSettingsOpen) {
            refreshActiveSources();
        }
    }, [isSettingsOpen, refreshActiveSources]);

    async function onUpdateShot(shotId, changes) {
        try {
            const stableShotId = String(shotId || '').trim();
            const currentShot = shots.find((s) => String(s?.id || '').trim() === stableShotId);
            const editingBase = (editingShot && String(editingShot?.id || '').trim() === stableShotId) ? editingShot : null;

            // Important: avoid sending full stale shot object during async generation flows.
            // Only send required fields + explicit changes to prevent overwriting already-generated media URLs.
            const payload = {
                shot_number: changes?.shot_number
                    ?? currentShot?.shot_number
                    ?? editingBase?.shot_number
                    ?? "1",
                description: changes?.description
                    ?? currentShot?.description
                    ?? editingBase?.description
                    ?? "",
                ...changes,
            };

            await updateShot(shotId, payload);
            setShots(prev => prev.map((s) => (String(s?.id || '').trim() === stableShotId ? { ...s, ...changes } : s)));

            // Sync editingShot safely
            setEditingShot(prev => {
                if (prev && String(prev?.id || '').trim() === stableShotId) {
                    return { ...prev, ...changes };
                }
                return prev;
            });
        } catch(e) { 
            console.error("Update Shot Failed", e); 
            onLog?.("Failed to save changes", "error");
        }
    }

    const persistShotFields = async (updates = {}) => {
        if (!editingShot?.id) return;
        setEditingShot(prev => ({ ...(prev || {}), ...updates }));
        await onUpdateShot(editingShot.id, updates);
    };

    const persistEditingShotUpdates = async (updates = {}) => {
        if (!editingShot?.id) return;
        setEditingShot(prev => ({ ...(prev || {}), ...updates }));
        await onUpdateShot(editingShot.id, updates);
    };

    const buildAssetDetailSavePatch = useCallback((shotRecord, modalType) => {
        if (!shotRecord || typeof shotRecord !== 'object') return {};

        const technicalNotes = String(shotRecord.technical_notes || '').trim() || '{}';

        if (modalType === 'start') {
            return {
                start_frame: shotRecord.start_frame || '',
                technical_notes: technicalNotes,
            };
        }

        if (modalType === 'end') {
            return {
                end_frame: shotRecord.end_frame || '',
                technical_notes: technicalNotes,
            };
        }

        if (modalType === 'video') {
            return {
                video_content: shotRecord.video_content || '',
                prompt: shotRecord.prompt || shotRecord.video_content || '',
                duration: shotRecord.duration || '',
                technical_notes: technicalNotes,
            };
        }

        return {};
    }, []);

    const resolveShotStartFrameRefs = (shotSnapshot, rawPrompt, resolvedEntities) => {
        let refs = [];
        try {
            const noteStr = shotSnapshot?.technical_notes || '{}';
            const tech = JSON.parse(noteStr);
            const isManualMode = Array.isArray(tech.ref_image_urls);
            const isUserEdited = Boolean(tech.ref_image_urls_user_edited);
            const isLockedManual = isManualMode && isUserEdited;
            const autoMatches = getSuggestedRefImages(shotSnapshot, rawPrompt, true, resolvedEntities);

            if (isLockedManual) {
                refs = [...tech.ref_image_urls];
            } else if (isManualMode) {
                const deletedRefs = tech.deleted_ref_urls || [];
                refs = autoMatches.filter(url => !deletedRefs.includes(url));
            } else {
                refs = [...new Set(autoMatches)];
            }
        } catch (e) {
            console.error('Error determining start frame refs:', e);
        }

        return refs.filter(Boolean);
    };

    const resolveShotEndFrameRefs = (shotSnapshot, rawPrompt, resolvedEntities) => {
        let refs = [];
        try {
            const noteStr = shotSnapshot?.technical_notes || '{}';
            const tech = JSON.parse(noteStr);
            const isManualMode = Array.isArray(tech.end_ref_image_urls);
            const isUserEdited = Boolean(tech.end_ref_image_urls_user_edited);
            const isLockedManual = isManualMode && isUserEdited;
            const deletedRefs = Array.isArray(tech.deleted_ref_urls) ? tech.deleted_ref_urls : [];

            const matchedEntities = collectMatchedEntitiesFromPrompt({
                promptText: rawPrompt,
                associatedEntities: '',
                entityPool: Array.isArray(resolvedEntities) ? resolvedEntities : entities,
                includeAssociatedEntities: false,
            });
            const autoMatches = matchedEntities
                .map((entity) => String(entity?.image_url || '').trim())
                .filter(Boolean);
            const environmentRefSet = new Set(
                matchedEntities
                    .filter((entity) => {
                        const entityType = String(entity?.type || '').trim().toLowerCase();
                        return entityType.includes('environment') || entityType.includes('env') || entityType.includes('scene');
                    })
                    .map((entity) => String(entity?.image_url || '').trim())
                    .filter(Boolean)
            );

            if (isLockedManual) {
                refs = [...tech.end_ref_image_urls];
            } else if (isManualMode) {
                refs = autoMatches.filter((url) => !deletedRefs.includes(url));
            } else {
                refs = [...autoMatches];
            }

            const currentStartFrame = String(shotSnapshot?.image_url || '').trim();
            if (!isLockedManual && currentStartFrame && !refs.includes(currentStartFrame) && !deletedRefs.includes(currentStartFrame)) {
                refs.unshift(currentStartFrame);
            }

            if (currentStartFrame && refs.includes(currentStartFrame) && environmentRefSet.size > 0) {
                refs = refs.filter((url) => {
                    const normalized = String(url || '').trim();
                    if (!normalized) return false;
                    if (normalized === currentStartFrame) return true;
                    return !environmentRefSet.has(normalized);
                });
            }
        } catch (e) {
            console.error('Error determining end frame refs:', e);
        }

        return normalizeMediaRefList(refs);
    };

    const resolveJointShotDiptychRefs = useCallback((shotSnapshot, rawStartPrompt = '', rawEndPrompt = '', resolvedEntities = null) => {
        const entityPool = Array.isArray(resolvedEntities) ? resolvedEntities : entities;
        const startPromptEntityRefs = collectMatchedEntityImageUrlsFromPrompt({
            promptText: rawStartPrompt,
            associatedEntities: shotSnapshot?.associated_entities || '',
            entityPool,
            includeAssociatedEntities: false,
        });
        const endPromptEntityRefs = collectMatchedEntityImageUrlsFromPrompt({
            promptText: rawEndPrompt,
            associatedEntities: shotSnapshot?.associated_entities || '',
            entityPool,
            includeAssociatedEntities: false,
        });

        return normalizeMediaRefList([
            ...startPromptEntityRefs,
            ...endPromptEntityRefs,
        ]);
    }, [entities]);

    const cropGeneratedPanelToBlob = useCallback(async ({
        image,
        layout,
        panelIndex,
        frameRole = 'start',
        targetAspectRatio,
        exportSize,
    }) => {
        const sourceWidth = Number(image?.naturalWidth || image?.width || 0);
        const sourceHeight = Number(image?.naturalHeight || image?.height || 0);
        const targetRatio = parseAspectRatioValue(targetAspectRatio);

        if (!sourceWidth || !sourceHeight || !targetRatio) {
            throw new Error('invalid generated image dimensions for split crop');
        }

        let panelX = 0;
        let panelY = 0;
        let panelWidth = sourceWidth;
        let panelHeight = sourceHeight;
        const seamTrimPx = getShotDiptychSeamTrimPx(layout, sourceWidth, sourceHeight);
        const seamBiasPx = getShotDiptychSeamBiasPx(layout, sourceWidth, sourceHeight);
        const fallbackCrop = getShotDiptychFallbackCropPx(layout, sourceWidth, sourceHeight, targetAspectRatio, frameRole);
        const innerTrimPx = seamTrimPx + fallbackCrop.seamExtraPx;
        const outerTrimPx = fallbackCrop.outerTrimPx;

        if (layout === 'horizontal') {
            const halfWidth = sourceWidth / 2;
            if (panelIndex === 0) {
                panelX = Math.max(0, outerTrimPx);
                panelWidth = Math.max(1, Math.floor(halfWidth - innerTrimPx - outerTrimPx));
            } else {
                panelX = Math.min(sourceWidth - 1, Math.ceil(halfWidth + innerTrimPx));
                panelWidth = Math.max(1, sourceWidth - panelX - outerTrimPx);
            }
        } else {
            const halfHeight = sourceHeight / 2;
            if (panelIndex === 0) {
                panelY = Math.max(0, outerTrimPx);
                panelHeight = Math.max(1, Math.floor(halfHeight - innerTrimPx - outerTrimPx));
            } else {
                panelY = Math.min(sourceHeight - 1, Math.ceil(halfHeight + innerTrimPx));
                panelHeight = Math.max(1, sourceHeight - panelY - outerTrimPx);
            }
        }

        const panelRatio = panelWidth / panelHeight;
        let cropWidth = panelWidth;
        let cropHeight = panelHeight;
        let cropX = panelX;
        let cropY = panelY;

        if (panelRatio > targetRatio) {
            cropWidth = panelHeight * targetRatio;
            cropX = panelX + ((panelWidth - cropWidth) / 2);
        } else if (panelRatio < targetRatio) {
            cropHeight = panelWidth / targetRatio;
            cropY = panelY + ((panelHeight - cropHeight) / 2);
        }

        if (layout === 'horizontal' && cropWidth < panelWidth) {
            const availableShiftX = Math.max(0, panelWidth - cropWidth);
            const effectiveBiasPx = seamBiasPx + fallbackCrop.seamExtraPx;
            const biasedCropX = panelIndex === 0
                ? (cropX - Math.min(effectiveBiasPx, availableShiftX / 2))
                : (cropX + Math.min(effectiveBiasPx, availableShiftX / 2));
            cropX = Math.min(panelX + availableShiftX, Math.max(panelX, biasedCropX));
        }
        if (layout === 'vertical' && cropHeight < panelHeight) {
            const availableShiftY = Math.max(0, panelHeight - cropHeight);
            const effectiveBiasPx = seamBiasPx + fallbackCrop.seamExtraPx;
            const biasedCropY = panelIndex === 0
                ? (cropY - Math.min(effectiveBiasPx, availableShiftY / 2))
                : (cropY + Math.min(effectiveBiasPx, availableShiftY / 2));
            cropY = Math.min(panelY + availableShiftY, Math.max(panelY, biasedCropY));
        }

        const outputWidth = Number(exportSize?.width) > 0 ? Number(exportSize.width) : Math.max(1, Math.round(cropWidth));
        const outputHeight = Number(exportSize?.height) > 0 ? Number(exportSize.height) : Math.max(1, Math.round(cropHeight));
        const canvas = document.createElement('canvas');
        canvas.width = outputWidth;
        canvas.height = outputHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            throw new Error('canvas context unavailable during split crop');
        }
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        ctx.drawImage(
            image,
            cropX,
            cropY,
            cropWidth,
            cropHeight,
            0,
            0,
            outputWidth,
            outputHeight,
        );

        return new Promise((resolve, reject) => {
            canvas.toBlob((blob) => {
                if (!blob) {
                    reject(new Error('failed to encode split image'));
                    return;
                }
                resolve(blob);
            }, 'image/jpeg', 0.94);
        });
    }, []);

    const applyJointShotDiptychResult = useCallback(async ({ shotRecord, compositeUrl }) => {
        const stableShot = shotRecord || null;
        const targetShotId = String(stableShot?.id || '').trim();
        const stableCompositeUrl = String(compositeUrl || '').trim();
        if (!targetShotId) {
            throw new Error('Missing shot context for joint diptych result');
        }
        if (!stableCompositeUrl) {
            throw new Error('Missing composite URL for joint diptych result');
        }

        const applyKey = `${targetShotId}::${stableCompositeUrl}`;
        const completedResult = appliedJointDiptychResultsRef.current.get(applyKey);
        if (completedResult) {
            return completedResult;
        }

        const inflightResult = jointDiptychApplyInFlightRef.current.get(applyKey);
        if (inflightResult) {
            return await inflightResult;
        }

        const runApply = (async () => {
            const latestShot = (shotsRef.current || []).find((item) => String(item?.id || '') === targetShotId)
                || (editingShotRef.current && String(editingShotRef.current?.id || '') === targetShotId ? editingShotRef.current : null)
                || stableShot;

            let latestTechNotes = {};
            try {
                latestTechNotes = JSON.parse(latestShot?.technical_notes || '{}');
            } catch {
                latestTechNotes = {};
            }

            if (
                String(latestShot?.image_url || '').trim()
                && String(latestTechNotes?.end_frame_url || '').trim()
                && String(latestTechNotes?.joint_diptych_last_composite_url || '').trim() === stableCompositeUrl
            ) {
                const existingData = {
                    image_url: String(latestShot?.image_url || '').trim(),
                    technical_notes: JSON.stringify(latestTechNotes),
                };
                appliedJointDiptychResultsRef.current.set(applyKey, existingData);
                return existingData;
            }

            const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
            const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
            const diptychPlan = buildShotDiptychPlan(preferredAspectRatio);
            const exportSize = resolveShotPanelExportResolution(diptychPlan.targetAspectRatio, preferredImageSize);

            const directUrl = getFullUrl(stableCompositeUrl);
            const isLocalOrigin = directUrl.startsWith(window.location.origin) || directUrl.startsWith('blob:') || directUrl.startsWith('data:');
            // Use backend proxy for external URLs to bypass CORS restrictions during Canvas processing
            // MUST use API_URL instead of getFullUrl here to hit current environment's backend proxy,
            // otherwise ASSET_BASE_URL resolution will incorrectly point to remote staging server on local dev.
            const fetchUrl = isLocalOrigin 
                ? directUrl 
                : `${API_URL}/assets/proxy?url=${encodeURIComponent(directUrl)}`;

            const compositeResp = await fetch(fetchUrl);
            if (!compositeResp.ok) {
                throw new Error(`Failed to download composite image (${compositeResp.status})`);
            }
            const compositeBlob = await compositeResp.blob();
            const compositeImage = await loadImageElementFromBlob(compositeBlob);

            const startBlob = await cropGeneratedPanelToBlob({
                image: compositeImage,
                layout: diptychPlan.layout,
                panelIndex: 0,
                frameRole: 'start',
                targetAspectRatio: diptychPlan.targetAspectRatio,
                exportSize,
            });
            const endBlob = await cropGeneratedPanelToBlob({
                image: compositeImage,
                layout: diptychPlan.layout,
                panelIndex: 1,
                frameRole: 'end',
                targetAspectRatio: diptychPlan.targetAspectRatio,
                exportSize,
            });

            try {
                const startBlobUrl = URL.createObjectURL(startBlob);
                const endBlobUrl = URL.createObjectURL(endBlob);
                
                if (typeof rememberWarmMediaUrl === 'function') {
                    rememberWarmMediaUrl(startBlobUrl);
                    rememberWarmMediaUrl(endBlobUrl);
                }

                setEditingShot((prev) => {
                    if (!prev || String(prev.id) !== targetShotId) return prev;
                    let existingTech = {};
                    try { existingTech = JSON.parse(prev.technical_notes || '{}'); } catch {}
                    existingTech.end_frame_url = endBlobUrl;
                    return { ...prev, image_url: startBlobUrl, technical_notes: JSON.stringify(existingTech) };
                });
                
                setShots((prevShots) =>
                    prevShots.map((s) => {
                        if (String(s?.id || '') !== targetShotId) return s;
                        let existingTech = {};
                        try { existingTech = JSON.parse(s.technical_notes || '{}'); } catch {}
                        existingTech.end_frame_url = endBlobUrl;
                        return { ...s, image_url: startBlobUrl, technical_notes: JSON.stringify(existingTech) };
                    })
                );
            } catch (optErr) {
                console.warn('Failed optimistic object URL assignment:', optErr);
            }

            const startUploadIdempotencyKey = buildJointShotDiptychUploadIdempotencyKey({
                shotId: targetShotId,
                frameRole: 'start',
                compositeUrl: stableCompositeUrl,
                layout: diptychPlan.layout,
                targetAspectRatio: diptychPlan.targetAspectRatio,
                exportSize,
            });
            const endUploadIdempotencyKey = buildJointShotDiptychUploadIdempotencyKey({
                shotId: targetShotId,
                frameRole: 'end',
                compositeUrl: stableCompositeUrl,
                layout: diptychPlan.layout,
                targetAspectRatio: diptychPlan.targetAspectRatio,
                exportSize,
            });
            const compositeUploadIdempotencyKey = buildJointShotDiptychUploadIdempotencyKey({
                shotId: targetShotId,
                frameRole: 'composite',
                compositeUrl: stableCompositeUrl,
                layout: diptychPlan.layout,
                targetAspectRatio: diptychPlan.targetAspectRatio,
                exportSize,
            });

            // Upload the original composite image to the asset library, per user request
            const compositeUploadP = uploadAsset(
                new File([compositeBlob], `shot_${targetShotId}_joint_diptych_composite_${Date.now()}.jpg`, { type: 'image/jpeg' }),
                {
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: targetShotId,
                    shot_number: latestShot?.shot_id,
                    shot_name: latestShot?.shot_name,
                    asset_type: 'joint_diptych_composite',
                    source_asset_url: stableCompositeUrl,
                    idempotency_key: compositeUploadIdempotencyKey,
                    remark: 'Joint diptych composite image',
                }
            ).catch(err => console.warn('Silent failure uploading joint diptych composite asset:', err));

            const startUpload = await uploadAsset(
                new File([startBlob], `shot_${targetShotId}_start_diptych_${Date.now()}.jpg`, { type: 'image/jpeg' }),
                {
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: targetShotId,
                    shot_number: latestShot?.shot_id,
                    shot_name: latestShot?.shot_name,
                    asset_type: 'start_frame',
                    source_asset_url: stableCompositeUrl,
                    idempotency_key: startUploadIdempotencyKey,
                    remark: 'Joint diptych split start frame',
                }
            );
            const endUpload = await uploadAsset(
                new File([endBlob], `shot_${targetShotId}_end_diptych_${Date.now()}.jpg`, { type: 'image/jpeg' }),
                {
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: targetShotId,
                    shot_number: latestShot?.shot_id,
                    shot_name: latestShot?.shot_name,
                    asset_type: 'end_frame',
                    source_asset_url: stableCompositeUrl,
                    idempotency_key: endUploadIdempotencyKey,
                    remark: 'Joint diptych split end frame',
                }
            );

            const startUrl = String(startUpload?.url || '').trim();
            const endUrl = String(endUpload?.url || '').trim();
            if (!startUrl || !endUrl) {
                throw new Error('Failed to upload split start/end frame assets');
            }
            
            await compositeUploadP;

            try {
                const preloadUrl = (url) => new Promise((resolve) => {
                    if (!url) return resolve();
                    const img = new Image();
                    img.onload = () => {
                        if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(url);
                        resolve();
                    };
                    img.onerror = resolve;
                    img.src = getFullUrl(url);
                });
                await Promise.all([preloadUrl(startUrl), preloadUrl(endUrl)]);
            } catch (e) {
                console.warn('Failed to preload split frames, continuing...', e);
            }

            let techNotes = {};
            try {
                techNotes = JSON.parse(latestShot?.technical_notes || '{}');
            } catch {
                techNotes = {};
            }
            techNotes.end_frame_url = endUrl;
            techNotes.video_gen_mode = 'start_end';
            techNotes.end_frame_reused_from_start = false;
            techNotes.joint_diptych_last_composite_url = stableCompositeUrl;

            const nextData = {
                image_url: startUrl,
                technical_notes: JSON.stringify(techNotes),
            };

            await onUpdateShot(targetShotId, nextData);
            setEditingShot(prev => (prev && String(prev.id) === targetShotId ? { ...prev, ...nextData } : prev));
            refreshShotAssetsMeta();
            appliedJointDiptychResultsRef.current.set(applyKey, nextData);
            return nextData;
        })();

        jointDiptychApplyInFlightRef.current.set(applyKey, runApply);
        try {
            return await runApply;
        } finally {
            jointDiptychApplyInFlightRef.current.delete(applyKey);
        }
    }, [activeEpisode?.episode_info, onUpdateShot, project?.global_info, projectId, cropGeneratedPanelToBlob, loadImageElementFromBlob, refreshShotAssetsMeta]);

    const handleGenerateShotDiptychFrames = async (cfgOverride = null) => {
        if (!editingShot) return;

        const shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        if (!targetShotId) return;
        let createdImageJobId = '';

        const techNotes = JSON.parse(shotSnapshot.technical_notes || '{}');
        const cnStartPrompt = String(techNotes.start_frame_cn || '').trim();
        const cnEndPrompt = String(techNotes.end_frame_cn || '').trim();
        const rawStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || shotSnapshot.start_frame || shotSnapshot.video_content || 'A cinematic shot')
            : (shotSnapshot.start_frame || cnStartPrompt || shotSnapshot.video_content || 'A cinematic shot');
        const rawEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || shotSnapshot.end_frame || 'End frame')
            : (shotSnapshot.end_frame || cnEndPrompt || 'End frame');

        const normalizedEndPrompt = String(rawEndPrompt || '').trim().toUpperCase();
        if (['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt)) {
            showNotification(
                t('当前结束帧被配置为复用起始帧，无法执行首尾联合生图。', 'End frame is configured to reuse the start frame, so joint start/end generation is unavailable.'),
                'warning'
            );
            return;
        }

        setShotGeneratingState(targetShotId, 'start', true);
        setShotGeneratingState(targetShotId, 'end', true);
        abortGenerationRef.current = false;

        try {
            const resolvedEntities = await awaitShotGenerationEntities();
            if (abortGenerationRef.current) return;

            const isManualStart = techNotes.manual_start_frame === true;
            const isManualEnd = techNotes.manual_end_frame === true;
            const { text: startSubmitPrompt } = injectEntityFeatures(rawStartPrompt, isManualStart, resolvedEntities);
            const { text: endSubmitPrompt } = injectEntityFeatures(rawEndPrompt, isManualEnd, resolvedEntities);

            const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
            const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
            const diptychPlan = buildShotDiptychPlan(preferredAspectRatio);
            const requestAspectRatio = selectBestShotDiptychRequestAspectRatio({
                diptychPlan,
                allowedAspectRatios: activeImageCapabilityProfile?.aspectRatios,
            });
            const requestImageSize = selectBestSupportedImageSize(
                preferredImageSize,
                activeImageCapabilityProfile?.imageSizeValues,
            );
            const exportSize = resolveShotPanelExportResolution(diptychPlan.targetAspectRatio, requestImageSize);
            const requestResolution = resolveShotDiptychRequestResolution(diptychPlan, exportSize);
            const combinedRefs = resolveJointShotDiptychRefs(
                shotSnapshot,
                rawStartPrompt,
                rawEndPrompt,
                resolvedEntities,
            );
            const layoutInstructionCn = buildShotDiptychLayoutInstruction(diptychPlan, 'cn');
            const layoutInstructionEn = buildShotDiptychLayoutInstruction(diptychPlan, 'en');
            const aspectContractCn = buildShotDiptychAspectContract(diptychPlan, 'cn');
            const aspectContractEn = buildShotDiptychAspectContract(diptychPlan, 'en');

            const combinedPrompt = resolvedPromptSubmitLang === 'cn'
                ? [
                    `生成一张单画布两宫格分镜图，后期会拆分为起始帧和结束帧。最终输出总共只能有两格，不能多于两格，也不能把下面任意一段提示词各自再扩展成两宫格。第一段提示词只负责第一格，第二段提示词只负责第二格。${layoutInstructionCn} ${aspectContractCn} 两格要像同一场景连续发生的两个瞬间，保持同一 shot 的人物身份、环境、光照和空间连续性。`,
                    `两格之间不得出现任何可见分隔设计或拼贴感：不要白线、黑线、边框、留白、间隔条、接缝高光、接缝阴影，也不要让高对比硬边落在中缝附近。人物脸部、手部、关键道具和主要动作不要贴近中缝或外边缘；不要出现第三格、文字、编号、气泡或版式元素。整张图必须像一次完成的电影画面，不像海报拼版或分屏设计。`,
                        `第一格（起始帧专用，仅这一格使用，不得扩展到第二格或再生成额外分格）：${startSubmitPrompt}`,
                        `第二格（结束帧专用，仅这一格使用，不得扩展到第一格或再生成额外分格）：${endSubmitPrompt}`,
                ].join('\n\n')
                : [
                    `Create one single-canvas two-panel storyboard image for later split delivery into the shot start frame and end frame. The final output must contain exactly two panels in total, not two panels per prompt. The first prompt applies only to panel A, and the second prompt applies only to panel B. Do not expand either prompt into its own diptych or generate any extra panel. ${layoutInstructionEn} ${aspectContractEn} Both panels must feel like consecutive moments from the same shot, with consistent identity, environment, lighting, and scene geography.`,
                    `The boundary between panels must be invisible. Do not add divider lines, borders, gaps, blank strips, seam highlights, seam shadows, collage styling, text, numbering, speech bubbles, or any third panel. Avoid placing faces, hands, hero props, or key motion near the seam or outer edges. The whole image must read as one cinematic composition, not a poster layout or split-screen graphic.`,
                        `Panel A only (Start Frame only; use this prompt for this panel alone, not for panel B and not for another diptych): ${startSubmitPrompt}`,
                        `Panel B only (End Frame only; use this prompt for this panel alone, not for panel A and not for another diptych): ${endSubmitPrompt}`,
                ].join('\n\n');

            const shouldApplyGlobalCtx = !(isManualStart && isManualEnd);
            const globalCtx = shouldApplyGlobalCtx
                ? getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(combinedPrompt) })
                : '';
            const finalPrompt = shouldApplyGlobalCtx ? `${combinedPrompt}${globalCtx}` : combinedPrompt;
            const jointNegativePrompt = [
                buildEntityNegativePrompt(`${rawStartPrompt}\n${rawEndPrompt}`, null, resolvedEntities),
                'more than two panels, extra frame, uneven split, unequal panel size, asymmetric panel, panel A larger, panel B larger, visible divider line, center divider, separator, seam line, white seam, black seam, bright seam, high-contrast center edge, hard center edge, abrupt center transition, empty gap, blank strip, whitespace strip, spacer band, border, frame, collage seam, contact sheet, text label, numbering, caption, comic bubble',
            ].filter(Boolean).join(', ');

            onLog?.(t('正在联合生成首尾帧两宫格...', 'Generating joint start/end diptych...'), 'info');

            const res = await generateImage(finalPrompt, null, combinedRefs.length > 0 ? combinedRefs : null, { function_name: 'generate_shot_images',
                project_id: projectId,
                episode_id: activeEpisode?.id,
                shot_id: targetShotId,
                shot_number: shotSnapshot.shot_id,
                shot_name: shotSnapshot.shot_name,
                prompt_language: resolvedPromptSubmitLang,
                asset_type: 'start_frame',
                mode: 'joint_diptych',
                aspect_ratio: requestAspectRatio,
                ...(requestResolution?.width ? { width: requestResolution.width } : {}),
                ...(requestResolution?.height ? { height: requestResolution.height } : {}),
                ...(cfgOverride ? { cfg: cfgOverride } : {}),
                ...(requestImageSize ? { image_size: requestImageSize } : {}),
                negative_prompt: jointNegativePrompt,
                on_job_created: (jobId) => {
                    createdImageJobId = String(jobId || '').trim();
                    if (!createdImageJobId) return;
                    setPendingJointDiptychImageJob(targetShotId, createdImageJobId);
                    setShotGeneratingState(targetShotId, 'start', true);
                    setShotGeneratingState(targetShotId, 'end', true);
                },
            });

            if (!res?.url) {
                throw new Error('No composite image URL returned');
            }
            clearPendingJointDiptychImageJob(targetShotId);
            if (abortGenerationRef.current) return;
            setShotGeneratingState(targetShotId, 'cropping', true);
            await applyJointShotDiptychResult({
                shotRecord: {
                    ...shotSnapshot,
                    start_frame: rawStartPrompt,
                    end_frame: rawEndPrompt,
                },
                compositeUrl: res.url,
            });
            onLog?.(t('首尾帧两宫格已生成并拆分回填。', 'Joint start/end diptych generated, split, and applied.'), 'success');
            showNotification(t('已生成并拆分回填首尾帧', 'Start/end frames generated and split successfully'), 'success');
        } catch (e) {
            console.error('Joint shot diptych generation failed:', e);
            if (createdImageJobId) {
                clearPendingJointDiptychImageJob(targetShotId);
                createdImageJobId = '';
            }
            onLog?.(`${t('首尾联生失败', 'Joint start/end generation failed')}: ${e?.message || 'Unknown error'}`, 'error');
            showNotification(`${t('首尾联生失败', 'Joint start/end generation failed')}: ${e?.message || 'Unknown error'}`, 'error');
        } finally {
            clearPendingJointDiptychImageJob(targetShotId);
            setShotGeneratingState(targetShotId, 'start', false);
            setShotGeneratingState(targetShotId, 'end', false);
      setShotGeneratingState(targetShotId, 'cropping', false);
        }
    };

    const generateShotDiptychBatchItem = useCallback(async ({ shotSnapshot, resolvedEntities, cfgOverride = null, silent = false }) => {
        const stableShot = shotSnapshot || null;
        const targetShotId = String(stableShot?.id || '').trim();
        if (!targetShotId) {
            throw new Error('Missing shot id for joint diptych generation');
        }

        let techNotes = {};
        try {
            techNotes = JSON.parse(stableShot?.technical_notes || '{}');
        } catch {
            techNotes = {};
        }

        const cnStartPrompt = String(techNotes.start_frame_cn || '').trim();
        const cnEndPrompt = String(techNotes.end_frame_cn || '').trim();
        const rawStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || stableShot?.start_frame || stableShot?.video_content || 'A cinematic shot')
            : (stableShot?.start_frame || cnStartPrompt || stableShot?.video_content || 'A cinematic shot');
        const rawEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || stableShot?.end_frame || 'End frame')
            : (stableShot?.end_frame || cnEndPrompt || 'End frame');

        const normalizedEndPrompt = String(rawEndPrompt || '').trim().toUpperCase();
        if (['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt)) {
            throw new Error('End frame is configured to reuse the start frame, so joint start/end generation is unavailable');
        }

        let createdImageJobId = '';
        setShotGeneratingState(targetShotId, 'start', true);
        setShotGeneratingState(targetShotId, 'end', true);

        try {
            const entityList = Array.isArray(resolvedEntities) ? resolvedEntities : await awaitShotGenerationEntities();
            const isManualStart = techNotes.manual_start_frame === true;
            const isManualEnd = techNotes.manual_end_frame === true;
            const { text: startSubmitPrompt } = injectEntityFeatures(rawStartPrompt, isManualStart, entityList);
            const { text: endSubmitPrompt } = injectEntityFeatures(rawEndPrompt, isManualEnd, entityList);

            const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
            const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
            const diptychPlan = buildShotDiptychPlan(preferredAspectRatio);
            const requestAspectRatio = selectBestShotDiptychRequestAspectRatio({
                diptychPlan,
                allowedAspectRatios: activeImageCapabilityProfile?.aspectRatios,
            });
            const requestImageSize = selectBestSupportedImageSize(
                preferredImageSize,
                activeImageCapabilityProfile?.imageSizeValues,
            );
            const exportSize = resolveShotPanelExportResolution(diptychPlan.targetAspectRatio, requestImageSize);
            const requestResolution = resolveShotDiptychRequestResolution(diptychPlan, exportSize);
            const combinedRefs = resolveJointShotDiptychRefs(
                stableShot,
                rawStartPrompt,
                rawEndPrompt,
                entityList,
            );
            const layoutInstructionCn = buildShotDiptychLayoutInstruction(diptychPlan, 'cn');
            const layoutInstructionEn = buildShotDiptychLayoutInstruction(diptychPlan, 'en');
            const aspectContractCn = buildShotDiptychAspectContract(diptychPlan, 'cn');
            const aspectContractEn = buildShotDiptychAspectContract(diptychPlan, 'en');

            const combinedPrompt = resolvedPromptSubmitLang === 'cn'
                ? [
                    `生成一张单画布两宫格分镜图，后期会拆分为起始帧和结束帧。最终输出总共只能有两格，不能多于两格，也不能把下面任意一段提示词各自再扩展成两宫格。第一段提示词只负责第一格，第二段提示词只负责第二格。${layoutInstructionCn} ${aspectContractCn} 两格要像同一场景连续发生的两个瞬间，保持同一 shot 的人物身份、环境、光照和空间连续性。`,
                    `两格之间不得出现任何可见分隔设计或拼贴感：不要白线、黑线、边框、留白、间隔条、接缝高光、接缝阴影，也不要让高对比硬边落在中缝附近。人物脸部、手部、关键道具和主要动作不要贴近中缝或外边缘；不要出现第三格、文字、编号、气泡或版式元素。整张图必须像一次完成的电影画面，不像海报拼版或分屏设计。`,
                    `第一格（起始帧专用，仅这一格使用，不得扩展到第二格或再生成额外分格）：${startSubmitPrompt}`,
                    `第二格（结束帧专用，仅这一格使用，不得扩展到第一格或再生成额外分格）：${endSubmitPrompt}`,
                ].join('\n\n')
                : [
                    `Create one single-canvas two-panel storyboard image for later split delivery into the shot start frame and end frame. The final output must contain exactly two panels in total, not two panels per prompt. The first prompt applies only to panel A, and the second prompt applies only to panel B. Do not expand either prompt into its own diptych or generate any extra panel. ${layoutInstructionEn} ${aspectContractEn} Both panels must feel like consecutive moments from the same shot, with consistent identity, environment, lighting, and scene geography.`,
                    `The boundary between panels must be invisible. Do not add divider lines, borders, gaps, blank strips, seam highlights, seam shadows, collage styling, text, numbering, speech bubbles, or any third panel. Avoid placing faces, hands, hero props, or key motion near the seam or outer edges. The whole image must read as one cinematic composition, not a poster layout or split-screen graphic.`,
                    `Panel A only (Start Frame only; use this prompt for this panel alone, not for panel B and not for another diptych): ${startSubmitPrompt}`,
                    `Panel B only (End Frame only; use this prompt for this panel alone, not for panel A and not for another diptych): ${endSubmitPrompt}`,
                ].join('\n\n');

            const shouldApplyGlobalCtx = !(isManualStart && isManualEnd);
            const globalCtx = shouldApplyGlobalCtx
                ? getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(combinedPrompt) })
                : '';
            const finalPrompt = shouldApplyGlobalCtx ? `${combinedPrompt}${globalCtx}` : combinedPrompt;
            const jointNegativePrompt = [
                buildEntityNegativePrompt(`${rawStartPrompt}\n${rawEndPrompt}`, null, entityList),
                'more than two panels, extra frame, uneven split, unequal panel size, asymmetric panel, panel A larger, panel B larger, visible divider line, center divider, separator, seam line, white seam, black seam, bright seam, high-contrast center edge, hard center edge, abrupt center transition, empty gap, blank strip, whitespace strip, spacer band, border, frame, collage seam, contact sheet, text label, numbering, caption, comic bubble',
            ].filter(Boolean).join(', ');

            if (!silent) {
                onLog?.(t('正在联合生成首尾帧两宫格...', 'Generating joint start/end diptych...'), 'info');
            }

            const res = await generateImage(finalPrompt, null, combinedRefs.length > 0 ? combinedRefs : null, { function_name: 'generate_shot_images',
                project_id: projectId,
                episode_id: activeEpisode?.id,
                shot_id: targetShotId,
                shot_number: stableShot?.shot_id,
                shot_name: stableShot?.shot_name,
                prompt_language: resolvedPromptSubmitLang,
                asset_type: 'start_frame',
                mode: 'joint_diptych',
                aspect_ratio: requestAspectRatio,
                ...(requestResolution?.width ? { width: requestResolution.width } : {}),
                ...(requestResolution?.height ? { height: requestResolution.height } : {}),
                ...(cfgOverride ? { cfg: cfgOverride } : {}),
                ...(requestImageSize ? { image_size: requestImageSize } : {}),
                negative_prompt: jointNegativePrompt,
                on_job_created: (jobId) => {
                    createdImageJobId = String(jobId || '').trim();
                    if (!createdImageJobId) return;
                    setPendingJointDiptychImageJob(targetShotId, createdImageJobId);
                    setShotGeneratingState(targetShotId, 'start', true);
                    setShotGeneratingState(targetShotId, 'end', true);
                },
            });

            if (!res?.url) {
                throw new Error('No composite image URL returned');
            }
            clearPendingJointDiptychImageJob(targetShotId);
            setShotGeneratingState(targetShotId, 'cropping', true);
            const nextData = await applyJointShotDiptychResult({
                shotRecord: {
                    ...stableShot,
                    start_frame: rawStartPrompt,
                    end_frame: rawEndPrompt,
                },
                compositeUrl: res.url,
            });
            if (!silent) {
                onLog?.(t('首尾帧两宫格已生成并拆分回填。', 'Joint start/end diptych generated, split, and applied.'), 'success');
                showNotification(t('已生成并拆分回填首尾帧', 'Start/end frames generated and split successfully'), 'success');
            }
            return {
                shotId: targetShotId,
                shotLabel: String(stableShot?.shot_id || stableShot?.shot_name || `#${targetShotId}`),
                shotPatch: nextData,
            };
        } finally {
            if (createdImageJobId) {
                clearPendingJointDiptychImageJob(targetShotId);
            }
            setShotGeneratingState(targetShotId, 'start', false);
            setShotGeneratingState(targetShotId, 'end', false);
        }
    }, [activeEpisode?.episode_info, activeEpisode?.id, activeImageCapabilityProfile?.aspectRatios, activeImageCapabilityProfile?.imageSizeValues, applyJointShotDiptychResult, awaitShotGenerationEntities, buildEntityNegativePrompt, getGlobalContextStr, injectEntityFeatures, onLog, project?.global_info, projectId, resolveJointShotDiptychRefs, resolvedPromptSubmitLang, setPendingJointDiptychImageJob, setShotGeneratingState, showNotification, t]);

    const handleManualEndFrameInputChange = (nextValue) => {
        if (!editingShot) return;
        let tech = {};
        try {
            tech = JSON.parse(editingShot.technical_notes || '{}');
        } catch (e) {
            tech = {};
        }

        tech.manual_end_frame = true;

        const normalizedEndPrompt = String(nextValue || '').trim().toUpperCase();
        const shouldReuseStartAsEnd = ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt);
        const currentStartFrameUrl = String(editingShot.image_url || '').trim();
        const previousEndFrameUrl = String(tech.end_frame_url || '').trim();
        const shouldSyncEndMeta = shouldReuseStartAsEnd && currentStartFrameUrl && previousEndFrameUrl !== currentStartFrameUrl;

        if (shouldSyncEndMeta) {
            tech.end_frame_url = currentStartFrameUrl;
            tech.end_frame_reused_from_start = true;
        }

        const updatedTechNotes = JSON.stringify(tech);
        setEditingShot(prev => (prev ? { ...prev, end_frame: nextValue, technical_notes: updatedTechNotes } : prev));

        if (shouldSyncEndMeta && editingShot.id) {
            onUpdateShot(editingShot.id, { end_frame: nextValue, technical_notes: updatedTechNotes }).catch(() => {});
            onLog?.(t('结束帧为 NO，已将结束帧 URL 同步为起始帧 URL。', 'End frame is NO; synced End Frame URL to Start Frame URL.'), 'info');
        }
    };

    const resolveVideoModeFromTech = (techObj = {}) => resolveUnifiedVideoMode(techObj);

    const updateShotTechnicalNotes = async (mutator) => {
        if (!editingShot?.id || typeof mutator !== 'function') return;
        let techObj = {};
        try { techObj = JSON.parse(editingShot.technical_notes || '{}'); } catch (e) {}
        mutator(techObj);
        const serialized = JSON.stringify(techObj);
        setEditingShot(prev => ({ ...(prev || {}), technical_notes: serialized }));
        await onUpdateShot(editingShot.id, { technical_notes: serialized });
    };

    const applyVideoModeToShot = async (mode) => {
        await updateShotTechnicalNotes((techObj) => {
            techObj.video_mode_unified = mode;
            if (mode === 'entity_refs') {
                techObj.video_ref_submit_mode = 'entity_refs';
                
                // Clear original auto/manual images and replace with Associated Entities images
                const cleanName = (s) => String(s || '').replace(/[\[\]【】"''“”‘’]/g, '').replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '').replace(/^@+/, '').trim();
                const normalizeForMatch = (s) => cleanName(s).replace(/[_\-]+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
                const rawNames = (editingShot.associated_entities || '').split(/[,，]/);
                const names = rawNames.map(cleanName).filter(Boolean);
                const normalizedNames = names.map(normalizeForMatch).filter(Boolean);
                
                const matches = entities.filter(e => normalizedNames.some(n => {
                    const cn = normalizeForMatch(e.name || '');
                    let en = normalizeForMatch(e.name_en || '');
                    if (!en && e.description) {
                        const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                        if (enMatch && enMatch[1]) {
                            const complexEn = enMatch[1].trim();
                            en = normalizeForMatch(complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0]); 
                        }
                    }
                    if (cn === n || en === n) return true;
                    if (cn && (cn.includes(n) || n.includes(cn))) return true;
                    if (en && (en.includes(n) || n.includes(en))) return true;
                    return false;
                }));

                let envMatches = [];
                const currentScene = scenes.find(s => s.id == editingShot.scene_id);
                if (currentScene) {
                    const rawLoc = cleanName((currentScene.location || currentScene.environment_name || '').replace(/[\[\]]/g, ''));
                    const rawLocNorm = normalizeForMatch(rawLoc);
                    if (rawLocNorm) {
                        const envs = entities.filter(e => {
                            const cn = normalizeForMatch(e.name || '');
                            let en = normalizeForMatch(e.name_en || '');
                            if (!en && e.description) {
                                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                if (enMatch && enMatch[1]) en = normalizeForMatch(enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0]); 
                            }
                            if (cn && (cn.includes(rawLocNorm) || rawLocNorm.includes(cn))) return true;
                            if (en && (en.includes(rawLocNorm) || rawLocNorm.includes(en))) return true;
                            return false;
                        });
                        envMatches = envs.filter(env => !matches.find(m => m.id === env.id));
                    }
                }

                const allMatches = [...matches, ...envMatches];
                const entityImages = allMatches.map(e => e.image_url).filter(Boolean);
                techObj.video_ref_image_urls = Array.from(new Set(entityImages));

            } else {
                techObj.video_gen_mode = mode;
                techObj.video_ref_submit_mode = 'auto';
                const promptEntityRefs = collectMatchedSubjectImageUrlsFromPrompt({
                    promptText: `${getShotVideoPromptEn(editingShot) || ''}\n${String(techObj.video_prompt_cn || '').trim()}`,
                    entityPool: entities,
                });
                techObj.video_ref_image_urls = buildAutoVideoRefList(editingShot, techObj, mode, promptEntityRefs);
            }
            techObj.video_ref_image_urls_manual = false;
            techObj.video_ref_image_urls_user_edited = false;
        });
    };

    const persistTechField = async (key, value) => {
        const nextValue = String(value ?? '');
        await updateShotTechnicalNotes((techObj) => {
            techObj[key] = nextValue;
        });
    };

    const persistKeyframeCnMap = async (timeKey, value) => {
        if (!timeKey) return;
        const nextValue = String(value ?? '');
        await updateShotTechnicalNotes((techObj) => {
            const nextMap = { ...(techObj.keyframe_prompt_cn_map || {}) };
            nextMap[timeKey] = nextValue;
            techObj.keyframe_prompt_cn_map = nextMap;
        });
    };

    const editingShotExtraColumns = useMemo(() => {
        if (!editingShot) return {};
        try {
            const tech = JSON.parse(editingShot.technical_notes || '{}');
            const raw = tech?.shot_extra_columns;
            if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
            const out = {};
            Object.entries(raw).forEach(([k, v]) => {
                const key = String(k || '').trim();
                if (!key) return;
                out[key] = String(v ?? '');
            });
            return out;
        } catch (e) {
            return {};
        }
    }, [editingShot?.id, editingShot?.technical_notes]);

    const setEditingShotExtraColumns = (nextColumns) => {
        setEditingShot(prev => {
            if (!prev) return prev;
            let tech = {};
            try {
                tech = JSON.parse(prev.technical_notes || '{}');
            } catch (e) {
                tech = {};
            }

            const cleaned = {};
            Object.entries(nextColumns || {}).forEach(([k, v]) => {
                const key = String(k || '').trim();
                if (!key) return;
                cleaned[key] = String(v ?? '');
            });

            if (Object.keys(cleaned).length > 0) {
                tech.shot_extra_columns = cleaned;
            } else {
                delete tech.shot_extra_columns;
            }

            return { ...prev, technical_notes: JSON.stringify(tech) };
        });
    };

    const handleGenerateShots = async (sceneId) => {
        if (sceneId === 'all') {
            onLog?.("Please select a specific scene to generate shots.", "warning");
            return;
        }
        setShotPromptModal({ open: true, sceneId: sceneId, data: null, loading: true });
        try {
            const data = await fetchSceneShotsPrompt(sceneId);
            setShotPromptModal({ open: true, sceneId: sceneId, data: data, loading: false });
        } catch (e) {
             onLog?.(`Failed to fetch prompt preview - ${e.message}`, 'error');
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
        }
    };

    const handleConfirmGenerateShots = async () => {
         const { sceneId, data } = shotPromptModal;
         if (!await confirmUiMessage("This will overwrite existing shots for this scene. Continue?")) return;
         
         setShotPromptModal(prev => ({ ...prev, loading: true }));
         onLog?.(`Generating shots for Scene ${sceneId}...`, 'info');
         try {
             // Now returns { content: [], timestamp }
             const result = await generateSceneShots(sceneId, { function_name: 'script_analysis', 
                 user_prompt: data.user_prompt,
                 system_prompt: data.system_prompt 
             });
             const generatedRows = Array.isArray(result?.content) ? result.content : [];
             const generatedRaw = String(result?.raw_text || '').trim();
             const generatedWarnings = Array.isArray(result?.warnings) ? result.warnings.map(w => String(w || '').trim()).filter(Boolean) : [];
             if (generatedRows.length === 0) {
                 if (generatedRaw) {
                     const rawPreview = generatedRaw.replace(/\s+/g, ' ').slice(0, 300);
                     onLog?.(`Generate Shots returned 0 parsed rows. Raw preview: ${rawPreview}`, 'warning');
                     console.warn('[ShotsView] Generate Shots parse-empty with raw_text preview', {
                         sceneId,
                         rawLen: generatedRaw.length,
                         rawPreview,
                     });
                     throw new Error(`Generate Shots returned 0 parsed rows; raw preview: ${rawPreview}`);
                 }
                 throw new Error('Generate Shots returned empty result (no rows and no raw text)');
             }
             onLog?.(`Shot list generated for Scene ${sceneId}. Please Review/Apply.`, 'success');
             generatedWarnings.forEach((msg) => onLog?.(msg, 'warning'));
             
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
             
             setShotReviewModal({
                 open: true,
                 sceneId: sceneId,
                 data: generatedRows,
                 loading: false
             });

             try {
                 onLog?.(`Auto-importing shots for Scene ${sceneId}...`, 'info');
                 await applySceneAIResult(sceneId, { content: generatedRows });
                 onLog?.(`Auto-import finished for Scene ${sceneId}.`, 'success');
             } catch (e) {
                 onLog?.(`Auto-import failed - ${(e?.response?.data?.detail || e?.message)}`, 'error');
             }
             
         } catch (e) {
             console.error(e);
             onLog?.(`Failed to generate shots - ${e.message}`, 'error');
             alert("Failed to generate shots: " + e.message);
             setShotPromptModal(prev => ({ ...prev, loading: false }));
         }
    };

    const handleMediaSelect = (url, type, selectedItems) => {
        if (pickerConfig.callback) {
            pickerConfig.callback(url, type, selectedItems);
        }
        setPickerConfig({ isOpen: false, callback: null });
    };

    const refreshShots = useCallback(async () => {
        if (!selectedSceneId || !activeEpisode?.id) return;
        const requestSeq = ++shotsRefreshRequestSeqRef.current;
        setIsShotsLoading(true);

        const getSceneCodeFromShot = (shot) => {
            const explicit = String(shot?.scene_code || '').trim();
            if (explicit) return explicit.toUpperCase();
            const shotId = String(shot?.shot_id || '').trim().toUpperCase();
            const m = shotId.match(/^(EP\d{2}_SC\d{2})/);
            return m ? m[1] : '';
        };
        
        try {
            const normalizedSceneCode = String(sceneCodeFilter || '').trim().toUpperCase();
            const normalizedShotId = String(shotIdFilter || '').trim().toUpperCase();

            // Optimized: Fetch all shots for the EPISODE.
            // This satisfies the requirement to select based on Project/Episode, and associate via Scene ID locally.
            // Also fixes issues where unlinked shots or imports were hidden.
            const allShots = await fetchEpisodeShots(activeEpisode.id, {
                compact: true,
                scene_code: normalizedSceneCode || undefined,
                shot_id: normalizedShotId || undefined,
            });

            let filtered = selectedSceneId === 'all'
                ? allShots
                : allShots.filter(s => String(s.scene_id) === String(selectedSceneId));

            if (normalizedSceneCode) {
                filtered = filtered.filter((shot) => {
                    const sceneCode = getSceneCodeFromShot(shot);
                    return sceneCode.includes(normalizedSceneCode);
                });
            }

            if (normalizedShotId) {
                filtered = filtered.filter((shot) => String(shot?.shot_id || '').toUpperCase().includes(normalizedShotId));
            }

            if (requestSeq === shotsRefreshRequestSeqRef.current) {
                setShots(filtered);
                setHasShotInitialLoadCompleted(true);
            }

                // Legacy Auto-Sync Check (Optional, but kept for script-to-shot workflow convenience)
                if (filtered.length === 0 && (activeEpisode?.scene_content || activeEpisode?.shot_content)) {
                     // Only if we truly have 0 matching shots, maybe try to parses content
                     // Check if we haven't already synced (prevent loops)
                     // Here we just log or optionally call sync. 
                     // We'll keep it simple for now as user asked to remove "sync logic".
                     // But if user relies on auto-generation... 
                     // Let's assume 'remove sync logic' refers to the strict scene_code matching.
                }
        } catch (e) {
            console.error("Failed to refresh shots", e);
            if (requestSeq === shotsRefreshRequestSeqRef.current) {
                setHasShotInitialLoadCompleted(true);
            }
        } finally {
            if (requestSeq === shotsRefreshRequestSeqRef.current) {
                setIsShotsLoading(false);
            }
        }
    }, [activeEpisode?.id, selectedSceneId, sceneCodeFilter, shotIdFilter]);

    useEffect(() => {
        setHasShotInitialLoadCompleted(false);
    }, [activeEpisode?.id]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        let cancelled = false;

        const resumePendingImageJobs = async () => {
            const normalizedPending = readImageJobStateStorage();
            pendingImageJobsRef.current = { ...normalizedPending };

            const entries = Object.entries(normalizedPending);
            if (entries.length === 0) return;

            const processedJointJobs = new Set();

            for (const [, payload] of entries) {
                if (cancelled) break;

                const stableShotId = String(payload?.shotId || '').trim();
                const stableKind = payload?.kind === 'end' ? 'end' : 'start';
                const jobId = String(payload?.jobId || '').trim();
                const isJointDiptych = payload?.mode === 'joint_diptych';
                if (!stableShotId || !jobId) {
                    clearPendingImageJob(stableShotId, stableKind);
                    continue;
                }
                if (isJointDiptych && processedJointJobs.has(jobId)) {
                    continue;
                }
                if (isJointDiptych) {
                    processedJointJobs.add(jobId);
                }

                let errorStreak = 0;
                let waitMs = 2500;
                if (isJointDiptych) {
                    setShotGeneratingState(stableShotId, 'start', true);
                    setShotGeneratingState(stableShotId, 'end', true);
                } else {
                    setShotGeneratingState(stableShotId, stableKind, true);
                }

                while (!cancelled) {
                    try {
                        const status = await getImageGenerationJobStatus(jobId);
                        const phase = String(status?.status || '').toLowerCase();
                        const resultUrl = extractImageJobResultUrl(status);
                        errorStreak = 0;
                        waitMs = 2500;
                        if (Number(payload?.statusFailureCount || 0) > 0) {
                            if (isJointDiptych) {
                                setPendingJointDiptychImageJob(stableShotId, jobId, {
                                    startedAt: payload?.startedAt,
                                    statusFailureCount: 0,
                                    lastStatusError: '',
                                    lastPolledAt: Date.now(),
                                });
                            } else {
                                setPendingImageJob(stableShotId, stableKind, jobId, {
                                    startedAt: payload?.startedAt,
                                    mode: payload?.mode,
                                    statusFailureCount: 0,
                                    lastStatusError: '',
                                    lastPolledAt: Date.now(),
                                });
                            }
                        }

                        if (resultUrl || phase === 'succeeded' || phase === 'completed') {
                            if (isJointDiptych) {
                                clearPendingJointDiptychImageJob(stableShotId);
                                setShotGeneratingState(stableShotId, 'start', false);
                                setShotGeneratingState(stableShotId, 'end', false);
    setShotGeneratingState(stableShotId, 'cropping', false);
                            } else {
                                clearPendingImageJob(stableShotId, stableKind);
                                setShotGeneratingState(stableShotId, stableKind, false);
                            }

                            if (resultUrl) {
                                const currentShot = (shotsRef.current || []).find((item) => String(item?.id) === stableShotId)
                                    || (editingShotRef.current && String(editingShotRef.current?.id) === stableShotId ? editingShotRef.current : null);
                                    
                                try {
                                    if (isJointDiptych) {
                                        setShotGeneratingState(stableShotId, 'cropping', true);
                                        await applyJointShotDiptychResult({ shotRecord: currentShot, compositeUrl: resultUrl });
                                    } else if (stableKind === 'start') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = () => {
                                                    if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resultUrl);
                                                    resolve();
                                                };
                                                img.onerror = resolve;
                                                img.src = getFullUrl(resultUrl);
                                            });
                                        } catch (e) {}
                                        const nextData = { image_url: resultUrl };
                                        await onUpdateShot(stableShotId, nextData);
                                        setEditingShot((prev) => (prev && String(prev.id) === stableShotId ? { ...prev, ...nextData } : prev));
                                    } else {
                                        let tech = {};
                                        try {
                                            tech = JSON.parse(currentShot?.technical_notes || '{}');
                                        } catch {
                                            tech = {};
                                        }
                                        tech.end_frame_url = resultUrl;
                                        tech.video_gen_mode = 'start_end';
                                        const nextData = { technical_notes: JSON.stringify(tech) };
                                        await onUpdateShot(stableShotId, nextData);
                                        setEditingShot((prev) => {
                                            if (!prev || String(prev.id) !== stableShotId) return prev;
                                            return { ...prev, ...nextData };
                                        });
                                    }
                                    onLog?.(isJointDiptych
                                        ? `Recovered joint start/end generation completed for shot ${stableShotId}.`
                                        : `Recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} generation completed for shot ${stableShotId}.`, 'success');
                                    refreshShotAssetsMeta();
                                    Promise.resolve(refreshShots()).catch((refreshErr) => {
                                        console.warn('Refresh shots after recovered image job failed:', refreshErr);
                                    });
                                } catch (applyErr) {
                                    console.error('Failed to apply recovered image job result:', applyErr);
                                    onLog?.(isJointDiptych
                                        ? `Failed to apply recovered joint start/end result for shot ${stableShotId}: ${applyErr.message}`
                                        : `Failed to apply recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} result for shot ${stableShotId}: ${applyErr.message}`, 'error');
                                }
                            }
                            break;
                        }

                        if (phase === 'failed' || phase === 'error' || phase === 'canceled' || phase === 'cancelled') {
                            if (isJointDiptych) {
                                clearPendingJointDiptychImageJob(stableShotId);
                                setShotGeneratingState(stableShotId, 'start', false);
                                setShotGeneratingState(stableShotId, 'end', false);
    setShotGeneratingState(stableShotId, 'cropping', false);
                            } else {
                                clearPendingImageJob(stableShotId, stableKind);
                                setShotGeneratingState(stableShotId, stableKind, false);
                            }
                            const errMsg = String(status?.error || 'unknown error');
                            const tone = String(phase).startsWith('cancel') ? 'warning' : 'error';
                            onLog?.(isJointDiptych
                                ? `Recovered joint start/end generation failed for shot ${stableShotId}: ${errMsg}`
                                : `Recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} generation failed for shot ${stableShotId}: ${errMsg}`, tone);
                            break;
                        }
                    } catch (e) {
                        const detail = e?.response?.data?.detail || e?.message || '';
                        const detailLower = String(detail).toLowerCase();
                        if (detailLower.includes('job not found')) {
                            if (isJointDiptych) {
                                clearPendingJointDiptychImageJob(stableShotId);
                                setShotGeneratingState(stableShotId, 'start', false);
                                setShotGeneratingState(stableShotId, 'end', false);
    setShotGeneratingState(stableShotId, 'cropping', false);
                            } else {
                                clearPendingImageJob(stableShotId, stableKind);
                                setShotGeneratingState(stableShotId, stableKind, false);
                            }
                            onLog?.(isJointDiptych
                                ? `Recovered joint start/end job missing for shot ${stableShotId}; cleared pending state.`
                                : `Recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} job missing for shot ${stableShotId}; cleared pending state.`, 'warning');
                            break;
                        }

                        errorStreak += 1;
                        waitMs = Math.min(12000, Math.round(waitMs * 1.6));
                        if (errorStreak >= SHOT_JOB_MAX_STATUS_FAILURES) {
                            await forceClearShotImageJob({
                                shotId: stableShotId,
                                kind: stableKind,
                                payload,
                                reason: `status polling failed ${errorStreak}/${SHOT_JOB_MAX_STATUS_FAILURES}: ${detail || 'unknown error'}`,
                            });
                            break;
                        }

                        if (isJointDiptych) {
                            setPendingJointDiptychImageJob(stableShotId, jobId, {
                                startedAt: payload?.startedAt,
                                statusFailureCount: errorStreak,
                                lastStatusError: String(detail || '').trim(),
                                lastPolledAt: Date.now(),
                            });
                        } else {
                            setPendingImageJob(stableShotId, stableKind, jobId, {
                                startedAt: payload?.startedAt,
                                mode: payload?.mode,
                                statusFailureCount: errorStreak,
                                lastStatusError: String(detail || '').trim(),
                                lastPolledAt: Date.now(),
                            });
                        }
                        onLog?.(`Image polling retry ${errorStreak}/${SHOT_JOB_MAX_STATUS_FAILURES} for shot ${stableShotId} (${stableKind}).`, 'warning');
                    }

                    await new Promise((resolve) => setTimeout(resolve, waitMs));
                }
            }
        };

        resumePendingImageJobs();

        return () => {
            cancelled = true;
        };
    }, [
        activeEpisode?.id,
        clearPendingImageJob,
        clearPendingJointDiptychImageJob,
        forceClearShotImageJob,
        extractImageJobResultUrl,
        onLog,
        onUpdateShot,
        applyJointShotDiptychResult,
        readImageJobStateStorage,
        refreshShots,
        setPendingImageJob,
        setPendingJointDiptychImageJob,
        setEditingShot,
        setShotGeneratingState,
    ]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        let cancelled = false;

        const resumePendingVideoJobs = async () => {
            const pending = readVideoJobStateStorage();
            const pendingEntries = Object.entries(pending);
            const normalizedPending = {};
            const seenJobIds = new Set();
            let normalizedChanged = false;
            pendingEntries.forEach(([shotId, payload]) => {
                const stableShotId = String(shotId || '').trim();
                const jobId = String(payload?.jobId || '').trim();
                const startedAt = Number(payload?.startedAt || 0) || Date.now();
                if (!stableShotId || !jobId) {
                    normalizedChanged = true;
                    return;
                }
                if (seenJobIds.has(jobId)) {
                    normalizedChanged = true;
                    return;
                }
                seenJobIds.add(jobId);
                normalizedPending[stableShotId] = { jobId, startedAt };
            });
            if (normalizedChanged) {
                writeVideoJobStateStorage(normalizedPending);
            }

            const entries = Object.entries(normalizedPending);
            if (entries.length === 0) return;

            for (const [shotId, payload] of entries) {
                if (cancelled) break;

                const stableShotId = String(shotId || '').trim();
                const jobId = String(payload?.jobId || '').trim();
                if (!stableShotId || !jobId) {
                    clearPendingVideoJob(stableShotId);
                    continue;
                }

                const pauseUntil = Number(pausedResumeVideoJobsRef.current[jobId] || 0);
                if (pauseUntil > Date.now()) {
                    continue;
                }

                const resumeKey = jobId;
                if (activeResumeVideoJobsRef.current.has(resumeKey)) {
                    continue;
                }
                activeResumeVideoJobsRef.current.add(resumeKey);

                let errorStreak = 0;
                let waitMs = 3000;

                setShotGeneratingState(stableShotId, 'video', true);

                try {
                    while (!cancelled) {
                        try {
                            const status = await getVideoGenerationJobStatus(jobId);
                            const phase = String(status?.status || '').toLowerCase();
                            const resultUrl = String(
                                status?.result?.url
                                || status?.result?.video_url
                                || status?.url
                                || status?.video_url
                                || ''
                            ).trim();
                            errorStreak = 0;
                            waitMs = 3000;
                            if (Number(payload?.statusFailureCount || 0) > 0) {
                                setPendingVideoJob(stableShotId, jobId, {
                                    startedAt: payload?.startedAt,
                                    statusFailureCount: 0,
                                    lastStatusError: '',
                                    lastPolledAt: Date.now(),
                                });
                            }

                            if (resultUrl || phase === 'succeeded' || phase === 'completed') {
                                const serverBoundVideoUrl = resultUrl;
                                if (serverBoundVideoUrl) {
                                    const newData = { video_url: serverBoundVideoUrl };
                                    try {
                                        await onUpdateShot(stableShotId, newData);
                                    } catch (persistErr) {
                                        console.warn('Resume video job save failed:', persistErr);
                                    }
                                    setEditingShot(prev => (prev && String(prev.id) === stableShotId ? { ...prev, ...newData } : prev));
                                    onLog?.(`Recovered video generation completed for shot ${stableShotId}.`, 'success');
                                }
                                delete pausedResumeVideoJobsRef.current[jobId];
                                clearPendingVideoJobsByJobId(jobId);
                                setShotGeneratingState(stableShotId, 'video', false);
                                refreshShotAssetsMeta();
                                await refreshShots();
                                break;
                            }

                            if (phase === 'failed' || phase === 'error' || phase === 'canceled' || phase === 'cancelled') {
                                const serverBoundVideoUrl = resultUrl;
                                if (serverBoundVideoUrl) {
                                    const newData = { video_url: serverBoundVideoUrl };
                                    try {
                                        await onUpdateShot(stableShotId, newData);
                                    } catch (persistErr) {
                                        console.warn('Resume video job save failed:', persistErr);
                                    }
                                    setEditingShot(prev => (prev && String(prev.id) === stableShotId ? { ...prev, ...newData } : prev));
                                    onLog?.(`Recovered video generation completed for shot ${stableShotId}.`, 'success');
                                    delete pausedResumeVideoJobsRef.current[jobId];
                                    clearPendingVideoJobsByJobId(jobId);
                                    setShotGeneratingState(stableShotId, 'video', false);
                                    refreshShotAssetsMeta();
                                    await refreshShots();
                                    break;
                                }

                                clearPendingVideoJobsByJobId(jobId);
                                setShotGeneratingState(stableShotId, 'video', false);
                                const errMsg = String(status?.error || 'unknown error');
                                const tone = String(phase).startsWith('cancel') ? 'warning' : 'error';
                                onLog?.(`Recovered video generation failed for shot ${stableShotId}: ${errMsg}`, tone);
                                break;
                            }
                        } catch (e) {
                            const detail = e?.response?.data?.detail || e?.message || '';
                            const detailLower = String(detail).toLowerCase();
                            if (detailLower.includes('job not found')) {
                                clearPendingVideoJobsByJobId(jobId);
                                setShotGeneratingState(stableShotId, 'video', false);
                                onLog?.(`Recovered video job missing for shot ${stableShotId}; cleared pending state.`, 'warning');
                                break;
                            }

                            errorStreak += 1;
                            waitMs = Math.min(15000, Math.round(waitMs * 1.6));
                            if (errorStreak >= SHOT_JOB_MAX_STATUS_FAILURES) {
                                await forceClearShotVideoJob({
                                    shotId: stableShotId,
                                    payload,
                                    reason: `status polling failed ${errorStreak}/${SHOT_JOB_MAX_STATUS_FAILURES}: ${detail || 'unknown error'}`,
                                });
                                break;
                            }

                            setPendingVideoJob(stableShotId, jobId, {
                                startedAt: payload?.startedAt,
                                statusFailureCount: errorStreak,
                                lastStatusError: String(detail || '').trim(),
                                lastPolledAt: Date.now(),
                            });
                            onLog?.(`Video polling retry ${errorStreak}/${SHOT_JOB_MAX_STATUS_FAILURES} for shot ${stableShotId}.`, 'warning');
                        }

                        await new Promise(resolve => setTimeout(resolve, waitMs));
                    }
                } finally {
                    activeResumeVideoJobsRef.current.delete(resumeKey);
                }
            }
        };

        resumePendingVideoJobs();

        return () => {
            cancelled = true;
        };
    }, [
        activeEpisode?.id,
        clearPendingVideoJobsByJobId,
        forceClearShotVideoJob,
        onLog,
        onUpdateShot,
        readVideoJobStateStorage,
        refreshShots,
        setEditingShot,
        setPendingVideoJob,
        setShotGeneratingState,
        writeVideoJobStateStorage,
    ]);

    useEffect(() => {
        if (!editingShot?.id || !activeEpisode?.id) return;

        let cancelled = false;
        const stableShotId = String(editingShot.id || '').trim();

        const reconcile = async () => {
            if (!stableShotId) return;

            await syncShotMediaRuntimeState({ shotId: stableShotId, mediaKey: 'video' });
            if (cancelled) return;
            await syncShotMediaRuntimeState({ shotId: stableShotId, mediaKey: 'start' });
            if (cancelled) return;
            await syncShotMediaRuntimeState({ shotId: stableShotId, mediaKey: 'end' });
        };

        reconcile();
        return () => {
            cancelled = true;
        };
    }, [
        activeEpisode?.id,
        currentGeneratingState.end,
        currentGeneratingState.start,
        currentGeneratingState.video,
        editingShot?.id,
        syncShotMediaRuntimeState,
    ]);

    const handleManualRebindMediaSlots = useCallback(async () => {
        if (!projectId || !activeEpisode?.id || isManualRebindingMedia) return;

        setIsManualRebindingMedia(true);
        try {
            const payload = {
                project_id: Number(projectId),
                episode_id: Number(activeEpisode.id),
                limit: 10000,
            };

            if (selectedSceneId && selectedSceneId !== 'all') {
                payload.scene_id = Number(selectedSceneId);
            }

            const res = await rebindShotMediaAssets(payload);
            const rebound = Number(res?.bound || 0);
            const updatedShots = Number(res?.updated_shots || 0);
            onLog?.(
                `Media rebind finished: bound ${rebound}, updated shots ${updatedShots}, scanned ${Number(res?.scanned || 0)}.`,
                rebound > 0 ? 'success' : 'info'
            );
            await refreshShots();
        } catch (e) {
            onLog?.(`Media rebind failed: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setIsManualRebindingMedia(false);
        }
    }, [projectId, activeEpisode?.id, selectedSceneId, isManualRebindingMedia, onLog, refreshShots]);

    const setEditingShotTechField = useCallback((key, value) => {
        setEditingShot((prev) => {
            if (!prev) return prev;
            let tech = {};
            try {
                tech = JSON.parse(prev.technical_notes || '{}');
                if (!tech || typeof tech !== 'object') tech = {};
            } catch (e) {
                tech = {};
            }
            tech[key] = value;
            return { ...prev, technical_notes: JSON.stringify(tech) };
        });
    }, [setEditingShot]);

    const getEditingShotTech = useCallback(() => {
        if (!editingShot) return {};
        try {
            const parsed = JSON.parse(editingShot.technical_notes || '{}');
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (e) {
            return {};
        }
    }, [editingShot]);


    const translateFieldToChinese = useCallback(async (type) => {
        if (!editingShot) return;
        const tech = getEditingShotTech() || {};
        let source = '';
        if (type === 'start') source = String(editingShot.start_frame || '');
        else if (type === 'end') source = String(editingShot.end_frame || '');
        else if (type === 'video') source = getShotVideoPromptEn(editingShot) || '';

        source = source.trim();
        if (!source) {
            onLog?.(t('请先填写英文提示词', 'Please enter English prompt text first'), 'warning');
            return;
        }

        const token = `${type}:to-cn`;
        setTranslatingPromptField(token);
        try {
            const res = await translateText(source, 'auto', 'zh');
            let translated = '';
            if (typeof res === 'string') translated = res;
            else if (res?.translated_text) translated = res.translated_text;

            translated = translated.trim();
            if (!translated) throw new Error('empty translation');

            setEditingShot((prev) => {
                if (!prev) return prev;
                let t_obj = {};
                try {
                    t_obj = JSON.parse(prev.technical_notes || '{}');
                } catch(e) { t_obj = {}; }
                if (!t_obj || typeof t_obj !== 'object') t_obj = {};
                
                if (type === 'start') {
                    t_obj.start_frame_cn = translated;
                } else if (type === 'end') {
                    t_obj.end_frame_cn = translated;
                } else if (type === 'video') {
                    t_obj.video_prompt_cn = translated;
                }
                return { ...prev, technical_notes: JSON.stringify(t_obj) };
            });

            onLog?.(t('已完成英译中', 'Translation finished'), 'success');
        } catch (e) {
            console.error(e);
            onLog?.(`${t('翻译失败', 'Translation failed')}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setTranslatingPromptField('');
        }
    }, [editingShot, getEditingShotTech, getShotVideoPromptEn, onLog, t, translateText]);

    const translateFieldToEnglish = useCallback(async (type) => {
        if (!editingShot) return;
        const tech = getEditingShotTech() || {};
        let source = '';
        if (type === 'start') source = String(tech.start_frame_cn || '');
        else if (type === 'end') source = String(tech.end_frame_cn || '');
        else if (type === 'video') source = String(tech.video_prompt_cn || '');

        source = source.trim();
        if (!source) {
            onLog?.(t('请先填写中文提示词', 'Please enter Chinese prompt text first'), 'warning');
            return;
        }

        const token = `${type}:to-en`;
        setTranslatingPromptField(token);
        try {
            const res = await translateText(source, 'zh', 'en');
            let translated = '';
            if (typeof res === 'string') translated = res;
            else if (res?.translated_text) translated = res.translated_text;

            translated = translated.trim();
            if (!translated) throw new Error('empty translation');

            setEditingShot((prev) => {
                if (!prev) return prev;
                
                if (type === 'video') {
                    return { ...prev, ...buildVideoPromptEnUpdates(translated) };
                }
            });

            onLog?.(t('已完成中译英', 'Translation finished'), 'success');
        } catch (e) {
            console.error(e);
            onLog?.(`${t('翻译失败', 'Translation failed')}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setTranslatingPromptField('');
        }
    }, [editingShot, getEditingShotTech, onLog, t, translateText, buildVideoPromptEnUpdates]);

    const translateKeyframeToChinese = useCallback(async (index) => {
        if (!editingShot || index < 0) return;
        const keyframe = localKeyframes[index];
        const source = String(keyframe?.prompt || '').trim();
        if (!source) {
            onLog?.(t('请先填写关键帧英文提示词', 'Please enter keyframe prompt text first'), 'warning');
            return;
        }
        const timeKey = String(keyframe?.time || '').trim();
        if (!timeKey) {
            onLog?.(t('请先填写关键帧时间', 'Please set keyframe time first'), 'warning');
            return;
        }

        const token = `keyframe:${index}:to-cn`;
        setTranslatingPromptField(token);
        try {
            const res = await translateText(source, 'auto', 'zh');
            const translated = String(res?.translated_text || '').trim();
            if (!translated) throw new Error('empty translation');

            setEditingShot((prev) => {
                if (!prev) return prev;
                let tech = {};
                try {
                    tech = JSON.parse(prev.technical_notes || '{}');
                    if (!tech || typeof tech !== 'object') tech = {};
                } catch (e) {
                    tech = {};
                }
                const nextMap = { ...(tech.keyframe_prompt_cn_map || {}) };
                nextMap[timeKey] = translated;
                tech.keyframe_prompt_cn_map = nextMap;
                return { ...prev, technical_notes: JSON.stringify(tech) };
            });

            onLog?.(t('关键帧已翻译为中文', 'Keyframe translated to Chinese'), 'success');
        } catch (e) {
            onLog?.(`${t('关键帧翻译失败', 'Keyframe translation failed')}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setTranslatingPromptField('');
        }
    }, [editingShot, localKeyframes, onLog, t]);

    const translateKeyframeToEnglish = useCallback(async (index) => {
        if (!editingShot || index < 0) return;
        const keyframe = localKeyframes[index];
        const timeKey = String(keyframe?.time || '').trim();
        if (!timeKey) {
            onLog?.(t('请先填写关键帧时间', 'Please set keyframe time first'), 'warning');
            return;
        }

        const tech = getEditingShotTech();
        const cnMap = (tech && typeof tech === 'object' && tech.keyframe_prompt_cn_map && typeof tech.keyframe_prompt_cn_map === 'object')
            ? tech.keyframe_prompt_cn_map
            : {};
        const cnText = String(cnMap[timeKey] || '').trim();

        if (!cnText) {
            onLog?.(t('请先填写关键帧中文提示词', 'Please enter keyframe Chinese prompt first'), 'warning');
            return;
        }

        const token = `keyframe:${index}:to-en`;
        setTranslatingPromptField(token);
        try {
            const res = await translateText(cnText, 'zh', 'en');
            const translated = String(res?.translated_text || '').trim();
            if (!translated) throw new Error('empty translation');

            setLocalKeyframes((prev) => {
                const updated = [...(prev || [])];
                if (!updated[index]) return prev;
                updated[index] = { ...updated[index], prompt: translated };
                return updated;
            });
            onLog?.(t('关键帧已翻译为英文', 'Keyframe translated to English'), 'success');
        } catch (e) {
            onLog?.(`${t('关键帧翻译失败', 'Keyframe translation failed')}: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
        } finally {
            setTranslatingPromptField('');
        }
    }, [editingShot, getEditingShotTech, localKeyframes, onLog, setLocalKeyframes, t]);

    useEffect(() => {
        if (!projectId || !activeEpisode?.id) return;
        const key = `${projectId}:${activeEpisode.id}`;
        if (mediaRebindAttemptedRef.current === key) return;
        mediaRebindAttemptedRef.current = key;

        let cancelled = false;
        (async () => {
            try {
                const res = await rebindShotMediaAssets({
                    project_id: Number(projectId),
                    episode_id: Number(activeEpisode.id),
                    limit: 5000,
                });

                const rebound = Number(res?.bound || 0);
                if (rebound > 0 && !cancelled) {
                    onLog?.(`Recovered ${rebound} historical media-slot links.`, 'success');
                    await refreshShots();
                }
            } catch (e) {
                console.warn('Historical shot-media rebind skipped:', e);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [projectId, activeEpisode?.id, onLog, refreshShots]);

    useEffect(() => {
        if(activeEpisode?.id) {
            fetchScenes(activeEpisode.id).then((data) => {
                setScenes(data);
                // If previously 'all' but couldn't load due to empty scenes, this will re-trigger refreshShots via useEffect[selectedSceneId, refreshShots]
                // because refreshShots depends on 'scenes' if selectedSceneId is 'all'
            }).catch(e => console.error(e));
        }
    }, [activeEpisode]);

    useEffect(() => {
        refreshShots();
    }, [refreshShots]);

    useEffect(() => {
        if (!hasActiveGeneration || !activeEpisode?.id) return;
        const timer = setInterval(() => {
            refreshShots();
        }, 5000);
        return () => clearInterval(timer);
    }, [hasActiveGeneration, activeEpisode?.id, refreshShots]);

    useEffect(() => {
        if (!hasActiveGeneration || (shots || []).length === 0) return;
        setGeneratingStateByShot((prev) => {
            let changed = false;
            const next = { ...prev };

            Object.entries(prev || {}).forEach(([shotId, state]) => {
                const shot = (shots || []).find((item) => String(item?.id) === String(shotId));
                if (!shot) return;
                let updated = { ...state };

                const base = generationMediaBaselineRef.current[String(shotId)] || {};
                const currentStartUrl = String(shot?.image_url || '');
                const currentEndUrl = String(getShotEndFrameUrl(shot));
                const currentVideoUrl = String(shot?.video_url || '');
                const hasFreshStartUrl = Boolean(currentStartUrl) && currentStartUrl !== String(base.start || '');
                const hasFreshEndUrl = Boolean(currentEndUrl) && currentEndUrl !== String(base.end || '');
                const hasFreshVideoUrl = Boolean(currentVideoUrl) && currentVideoUrl !== String(base.video || '');

                if (updated.start && Object.prototype.hasOwnProperty.call(base, 'start') && hasFreshStartUrl) {
                    updated.start = false;
                    updated.startAt = 0;
                }
                if (updated.end && Object.prototype.hasOwnProperty.call(base, 'end') && hasFreshEndUrl) {
                    updated.end = false;
                    updated.endAt = 0;
                }
                if (updated.video && Object.prototype.hasOwnProperty.call(base, 'video') && hasFreshVideoUrl) {
                    updated.video = false;
                    updated.videoAt = 0;
                }
                if (!updated.start && !updated.end && !updated.video) {
                    delete next[shotId];
                    delete generationMediaBaselineRef.current[String(shotId)];
                    changed = true;
                    return;
                }
                if (
                    updated.start !== state.start ||
                    updated.end !== state.end ||
                    updated.video !== state.video ||
                    updated.startAt !== state.startAt ||
                    updated.endAt !== state.endAt ||
                    updated.videoAt !== state.videoAt
                ) {
                    next[shotId] = updated;
                    changed = true;
                }
            });

            if (!changed) return prev;
            writeGenerationStateStorage(next);
            return next;
        });
    }, [shots, hasActiveGeneration, writeGenerationStateStorage, getShotEndFrameUrl]);

    useEffect(() => {
        if (!editingShot?.id || (shots || []).length === 0) return;
        const latest = (shots || []).find((item) => String(item?.id) === String(editingShot.id));
        if (!latest) return;

        setEditingShot((prev) => {
            if (!prev || String(prev.id) !== String(latest.id)) return prev;

            const nextTechnicalNotes = mergeLiveSyncTechnicalNotes(prev.technical_notes, latest.technical_notes);

            const mediaChanged =
                String(prev.image_url || '') !== String(latest.image_url || '') ||
                String(prev.video_url || '') !== String(latest.video_url || '') ||
                nextTechnicalNotes.changed;

            if (!mediaChanged) return prev;

            return {
                ...prev,
                image_url: latest.image_url || '',
                video_url: latest.video_url || '',
                technical_notes: nextTechnicalNotes.value,
            };
        });
    }, [editingShot?.id, mergeLiveSyncTechnicalNotes, setEditingShot, shots]);

    useEffect(() => {
        if (!restoreEditingShotId) return;
        if (restoreEditingAttemptedRef.current) return;
        if (editingShot?.id) {
            restoreEditingAttemptedRef.current = true;
            return;
        }
        if (!Array.isArray(shots) || shots.length === 0) return;

        const restored = shots.find((item) => String(item?.id) === String(restoreEditingShotId));
        if (restored) {
            setEditingShot(restored);
        }
        restoreEditingAttemptedRef.current = true;
    }, [restoreEditingShotId, shots, editingShot?.id, setEditingShot]);


    const handleDeleteAllShots = async () => {
        if (shots.length === 0) return;
        if (!await confirmUiMessage(`Are you sure you want to delete all ${shots.length} shots displayed here? This cannot be undone.`)) return;

        onLog?.("Deleting all shots...", "process");
        try {
            await Promise.all(shots.map(s => deleteShot(s.id)));
            onLog?.(`Successfully deleted ${shots.length} shots.`, "success");
            setShots([]);
            setSelectedShotIds([]);
        } catch (e) {
            console.error(e);
            onLog?.("Error deleting shots", "error");
            refreshShots();
        }
    };

    const handleDeleteSelectedShots = useCallback(async () => {
        const targetIds = (selectedShotIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0);
        if (targetIds.length === 0) {
            onLog?.(t('请先选择要删除的镜头。', 'Select shots to delete first.'), 'warning');
            return;
        }

        if (!await confirmUiMessage(`Are you sure you want to delete ${targetIds.length} selected shots? This cannot be undone.`)) return;

        onLog?.(`Deleting ${targetIds.length} selected shots...`, 'process');
        try {
            await Promise.all(targetIds.map((id) => deleteShot(id)));
            setSelectedShotIds([]);
            onLog?.(`Successfully deleted ${targetIds.length} selected shots.`, 'success');
            await refreshShots();
        } catch (e) {
            console.error(e);
            onLog?.(t('删除选中镜头失败', 'Failed to delete selected shots'), 'error');
            await refreshShots();
        }
    }, [selectedShotIds, onLog, refreshShots, t]);

    const handleSyncScenes = async (onlyForSceneId = null) => {
        // Support pulling from scene_content OR shot_content
        const contentSources = [];
        if (activeEpisode?.scene_content) contentSources.push(activeEpisode.scene_content);
        if (activeEpisode?.shot_content) contentSources.push(activeEpisode.shot_content);

        if (contentSources.length === 0) {
            onLog?.("No scene/shot content to sync from source text.", "warning");
            return;
        }
        
        onLog?.(onlyForSceneId ? "Syncing Logic (Smart Refresh)..." : "Syncing Scenes & Shots...", "process");
        
        // Merge lines from both sources
        let allLines = [];
        contentSources.forEach(txt => {
            allLines = allLines.concat(txt.split('\n'));
        });
        
        const lines = allLines;
        
        // Cache to avoid duplicates and redundant calls
        const sceneShotsCache = {};
        let countShots = 0;

        // 1. Fetch ALL existing scenes from DB first
        let dbScenes = [];
        try { 
            dbScenes = await fetchScenes(activeEpisode.id); 
            // Update UI with fresh scenes immediately to avoid "Missing Scenes" visual
            if (!onlyForSceneId) setScenes(dbScenes);
        } catch(e) { console.error(e); }
        
        // Map: "1" -> SceneObj, "01" -> SceneObj
        const getSceneKey = (num) => String(num).replace(/^0+/, '').replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
        const sceneMap = {};
        dbScenes.forEach(s => { 
            if(s.scene_no) sceneMap[getSceneKey(s.scene_no)] = s; 
        });

        let defaultSceneId = null; // Track created default scene

        // 2. Iterate text lines looking ONLY for Shots
        for (let line of lines) {
             const trimmed = line.trim();
             if (!trimmed.includes('|')) continue;
             if (trimmed.includes('Shot No') || trimmed.includes('Shot ID') || trimmed.includes('镜头ID') || trimmed.includes('---')) continue;
             
             const cols = trimmed.split('|').map(c => c.trim());
             if (cols.length > 0 && cols[0] === '') cols.shift();
             if (cols.length > 0 && cols[cols.length-1] === '') cols.pop();
             if (cols.length < 2) continue; // Not a valid row
             
             const clean = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
             const shotNumRaw = clean(cols[0]); // e.g. "1-1", "1A-1"
             
             // 3. Determine Target Scene from Shot Number Prefix
             // "1-12" -> Scene "1"
             // "1A-5" -> Scene "1A"
             // "2"    -> Scene "2" (if loose)
             let targetSceneId = null;
             
             // Strategy: Look for "-" separator
             const parts = shotNumRaw.split(/[-_]/);
             const scenePrefix = parts.length > 1 ? parts[0] : null; 
             
             if (scenePrefix) {
                 const key = getSceneKey(scenePrefix);
                 if (sceneMap[key]) {
                     targetSceneId = sceneMap[key].id;
                 }
             }

             // Fallback: If no prefix match, try selectedSceneId (if not 'all')
             if (!targetSceneId && selectedSceneId && selectedSceneId !== 'all') {
                 targetSceneId = parseInt(selectedSceneId);
             }

             // Auto-Create Default Scene if Orphaned
             if (!targetSceneId) {
                 if (defaultSceneId) {
                     targetSceneId = defaultSceneId;
                 } else {
                     // Check existing "Default Scene"
                     const existingDefault = dbScenes.find(s => s.scene_name === "Default Scene" || s.scene_no === "DEFAULT");
                     if (existingDefault) {
                         targetSceneId = existingDefault.id;
                         defaultSceneId = existingDefault.id;
                     } else if (dbScenes.length === 0) {
                         // Only create if NO scenes exist (assuming shot-only import)
                         try {
                              // We need to await inside loop, but it's only once
                              // eslint-disable-next-line no-await-in-loop
                              const newScene = await createScene(activeEpisode.id, {
                                  scene_number: "DEFAULT",
                                  title: "Default Scene",
                                  description: "Auto-generated for imported shots",
                                  location: "Unknown",
                                  time_of_day: "Unknown"
                              });
                              dbScenes.push(newScene);
                              setScenes(prev => [...prev, newScene]);
                              targetSceneId = newScene.id;
                              defaultSceneId = newScene.id;
                         } catch(e) {
                             console.error("Failed to create default scene", e);
                         }
                     }
                 }
             }

             // If still no scene, we verify if the USER wants us to create shots purely based on sequence? 
             // Current strict mode: If we can't link, we skip.
             if (!targetSceneId) continue;
             
             // Smart Filter for partial updates
             if (onlyForSceneId && targetSceneId !== onlyForSceneId) continue;

             // 4. Create/Sync Shot
             const currentSceneId = targetSceneId;
             
             // IDEMPOTENCY CHECK
             if (!sceneShotsCache[currentSceneId]) {
                 try {
                     sceneShotsCache[currentSceneId] = await fetchShots(currentSceneId);
                 } catch(e) { sceneShotsCache[currentSceneId] = []; }
             }
             
             const shotData = {
                 shot_id: shotNumRaw.replace(/\*\*/g, ''),
                 shot_name: clean(cols[1]),
                 start_frame: clean(cols[2]),
                 end_frame: clean(cols[3]),
                 video_content: clean(cols[4]),
                 duration: clean(cols[5]),
                 associated_entities: clean(cols[6])
             };
             
             // Duplication Check
             const existingShots = sceneShotsCache[currentSceneId];
             const alreadyExists = existingShots.find(s => {
                 const sNum = String(s.shot_id || '').replace(/\*\*/g, '').replace(/Shot\s*/i, '').trim();
                 const tNum = String(shotData.shot_id || '').replace('Shot', '').trim();
                 return sNum === tNum;
             });
             
             if (!alreadyExists) {
                try {
                    const newShot = await createShot(currentSceneId, shotData);
                    existingShots.push(newShot); 
                    countShots++;
                } catch(e) { console.error("Sync Shot Error", e); }
             }
        }
        
        if (countShots > 0) {
            onLog?.(`Synced ${countShots} shots to ${Object.keys(sceneShotsCache).length} scenes.`, "success");
        } else if (!onlyForSceneId) {
             onLog?.("No new shots found to sync.", "info");
        }

        // Force Refresh UI
        if (!onlyForSceneId) {
            // Re-fetch all scenes to update lists
            try {
                 const currentScenes = await fetchScenes(activeEpisode.id);
                 setScenes(currentScenes);
            } catch(e) { console.error(e); }

            // Using unified refresh logic
            refreshShots();
        }
    };

    const handleImport = async (text) => {
        if (!selectedSceneId) {
             onLog?.("Please select a scene first.", "error");
             return;
        }
        
        onLog?.("Processing Shot Import...", "process");
        const lines = text.split('\n');
        
        const currentScene = scenes.find(s => s.id == selectedSceneId);
        
        const parsedShots = [];
        let headerFound = false;
        let headerMap = {}; // Map normalized header string to column index

        const splitCombinedCnPrompt = (raw) => {
            const textVal = String(raw || '').trim();
            if (!textVal) {
                return {
                    start_frame_cn: '',
                    video_prompt_cn: '',
                    keyframes_cn: '',
                    end_frame_cn: '',
                };
            }
            const lines = textVal
                .split(/\n|<br\s*\/?>/i)
                .map((ln) => String(ln || '').trim())
                .filter(Boolean);

            let start = '';
            let video = '';
            let keyframes = '';
            let end = '';

            lines.forEach((ln) => {
                const lower = ln.toLowerCase();
                if (/^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])/.test(lower) || /^起始帧\s*[:：]/.test(ln)) {
                    start = ln.replace(/^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])/i, '').trim();
                    return;
                }
                if (/^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])/.test(lower) || /^视频(提示词)?\s*[:：]/.test(ln)) {
                    video = ln.replace(/^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])/i, '').trim();
                    return;
                }
                if (/^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])/.test(lower) || /^关键帧\s*[:：]/.test(ln)) {
                    keyframes = ln.replace(/^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])/i, '').trim();
                    return;
                }
                if (/^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])/.test(lower) || /^(收尾帧|结束帧)\s*[:：]/.test(ln)) {
                    end = ln.replace(/^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])/i, '').trim();
                }
            });

            if (!start && !video && !keyframes && !end) {
                return {
                    start_frame_cn: textVal,
                    video_prompt_cn: textVal,
                    keyframes_cn: textVal,
                    end_frame_cn: textVal,
                };
            }

            if (!end && start) end = start;

            return {
                start_frame_cn: start,
                video_prompt_cn: video,
                keyframes_cn: keyframes,
                end_frame_cn: end,
            };
        };

        for (let line of lines) {
             // Skip context header (Project | Episode)
             if (line.includes('Project:') && line.includes('Episode:')) continue;
             
             // Check for possible header row by keywords
             const normLine = line.toLowerCase();
             const isHeader = line.includes('|') && (
                 normLine.includes('shot no') || normLine.includes('shot id') || normLine.includes('镜头id') || normLine.includes('scene id')
             );
             
             // Process Row splitting logic consistently for Header and Data
             if (line.includes('|') && !line.includes('---')) {
                 const cols = line.split('|').map(c => c.trim());
                 if (cols.length > 0 && cols[0] === '') cols.shift();
                 if (cols.length > 0 && cols[cols.length-1] === '') cols.pop();

                 if (isHeader) {
                     headerFound = true;
                     cols.forEach((col, idx) => {
                         // Normalize header key: remove special chars, lowercase
                         const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                         headerMap[key] = idx;
                     });
                     onLog?.("Parsed Headers: " + Object.keys(headerMap).join(", "), "info");
                     continue;
                 }
                 
                 if (headerFound) {
                     const clean = (t) => t ? t.replace(/<br\/?>/gi, '\n') : '';
                     
                     // Helper to get value by possible keys
                     const getVal = (keys, defaultIdx) => {
                         for (const k of keys) {
                             if (headerMap[k] !== undefined && headerMap[k] < cols.length) {
                                 return clean(cols[headerMap[k]]); 
                             }
                         }
                         // Fallback to default index if map logic fails or specific column not found
                         // Only fallback if we don't have a reliable map (e.g. maybe map is empty?)
                         if (Object.keys(headerMap).length === 0 && defaultIdx < cols.length) {
                             return clean(cols[defaultIdx]);
                         }
                         return ''; 
                     };

                     // Determine fallback offset based on column count if map failed (legacy logic)
                     // But if we have map, we rely on it.
                     const useMap = Object.keys(headerMap).length > 0;
                     
                     // Legacy offset logic for fallback
                     let colStart = 2; 
                     let legacySceneCode = '';
                     if (!useMap) {
                        if (cols.length >= 8) {
                            legacySceneCode = clean(cols[2]);
                            colStart = 3;
                        }
                     }
                     
                     let extractedSceneCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                     // Ensure scene_code is populated if import misses it
                     if (!extractedSceneCode && currentScene) {
                         extractedSceneCode = currentScene.scene_no;
                     }

                     const shotData = {
                         shot_id: useMap ? getVal(['shotid', 'shotno', '镜头id', 'id'], 0) : clean(cols[0]),
                         shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                         
                         scene_code: extractedSceneCode,
                         
                         start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                         end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                         video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                         duration: useMap ? getVal(['duration', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                         associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                         shot_logic_cn: (() => {
                             const val = useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)'], 7) : '';
                             return val;
                         })(),
                         keyframes: useMap ? getVal(['keyframes', 'key frames', '关键帧', 'kf'], 8) : '',
                         prompt_cn: useMap ? getVal(['promptcn', 'prompt(cn)', 'cnprompt', '中文提示词', '中文提示', 'prompt中文'], 9) : '',
                         start_frame_cn: useMap ? getVal(['startframecn', 'start_frame_cn', '起始帧中文', '起始帧（中文）'], 10) : '',
                         video_prompt_cn: useMap ? getVal(['videocontentcn', 'video_prompt_cn', '视频内容中文', '视频内容（中文）'], 11) : '',
                         keyframes_cn: useMap ? getVal(['keyframescn', 'keyframes_cn', '关键帧中文', '关键帧（中文）'], 12) : '',
                         end_frame_cn: useMap ? getVal(['endframecn', 'end_frame_cn', '收尾帧中文', '收尾帧（中文）', '结束帧中文', '结束帧（中文）'], 13) : '',

                         // Clear unused
                         shot_type: '',
                         lens: '',
                         framing: '',
                         dialogue: '',
                         technical_notes: ''
                     };
                     
                     // Only push valid rows
                     if (shotData.shot_id && String(shotData.shot_id).trim() !== '') {
                        parsedShots.push(shotData);
                     }
                 }
             }
        }

        if (parsedShots.length > 0) {
            let shouldOverwrite = false;
            // Removed redundant currentScene fetch here
            
            // Check if import sceneCode matches selected scene
            if (currentScene && currentScene.scene_no) {
                const importCode = parsedShots[0].scene_code;
                if (importCode && String(importCode).trim() === String(currentScene.scene_no).trim()) {
                    shouldOverwrite = true;
                }
            }
            
            if (shouldOverwrite && shots.length > 0) {
                 onLog?.(`Scene Code matched (${parsedShots[0].scene_code}). Overwriting existing shots...`, 'warning');
                 try {
                     await Promise.all(shots.map(s => deleteShot(s.id)));
                     setShots([]); 
                 } catch(e) {
                     console.error("Failed to delete existing shots", e);
                     onLog?.("Failed to clear shots. Appending...", "error");
                 }
            }

            let count = 0;
            // Create shots sequentially
            // Use 'selectedSceneId' for physical relationship, but 's.scene_code' ensures logical grouping
            // Note: If s.scene_code is missing, endpoints.py might hide the shot!
            for (const s of parsedShots) {
                 try {
                    // Ensure the shot object has scene_code
                    if (!s.scene_code && currentScene) s.scene_code = currentScene.scene_no;

                    const promptCnRaw = String(s.prompt_cn || '').trim();
                    const startFrameCnRaw = String(s.start_frame_cn || '').trim();
                    const videoPromptCnRaw = String(s.video_prompt_cn || '').trim();
                    const keyframesCnRaw = String(s.keyframes_cn || '').trim();
                    const endFrameCnRaw = String(s.end_frame_cn || '').trim();
                    const combinedFallback = splitCombinedCnPrompt(promptCnRaw);

                    if (promptCnRaw || startFrameCnRaw || videoPromptCnRaw || keyframesCnRaw || endFrameCnRaw) {
                        let techObj = {};
                        try {
                            techObj = s.technical_notes ? JSON.parse(s.technical_notes) : {};
                            if (!techObj || typeof techObj !== 'object') techObj = {};
                        } catch (e) {
                            techObj = {};
                        }
                        const finalStartCn = startFrameCnRaw || combinedFallback.start_frame_cn;
                        const finalVideoCn = videoPromptCnRaw || combinedFallback.video_prompt_cn;
                        const finalKeyframesCn = keyframesCnRaw || combinedFallback.keyframes_cn;
                        const finalEndCn = endFrameCnRaw || combinedFallback.end_frame_cn;

                        if (finalStartCn) techObj.start_frame_cn = finalStartCn;
                        if (finalVideoCn) techObj.video_prompt_cn = finalVideoCn;
                        if (finalKeyframesCn) techObj.keyframes_cn = finalKeyframesCn;
                        if (finalEndCn) techObj.end_frame_cn = finalEndCn;

                        techObj.shot_prompt_cn = [
                            `起始帧：${finalStartCn || ''}`,
                            `视频：${finalVideoCn || ''}`,
                            `关键帧：${finalKeyframesCn || ''}`,
                            `收尾帧：${finalEndCn || ''}`,
                        ].join('<br>');
                        s.technical_notes = JSON.stringify(techObj);
                    }
                    
                    if (count === 0) {
                        if (!s.shot_logic_cn) {
                             onLog?.("Warning: 'Shot Logic (CN)' is empty in the parsed data.", "warning");
                        }
                    }

                          const { prompt_cn, start_frame_cn, video_prompt_cn, keyframes_cn, end_frame_cn, ...createPayload } = s;
                          await createShot(selectedSceneId, createPayload);
                    count++;
                 } catch(e) {
                     console.error("Failed to create shot", e);
                     onLog?.(`Failed to create shot ${s.shot_id || 'unknown'}: ${e.message}`, "error");
                 }
            }

            if (count > 0) {
                onLog?.(`Imported ${count} shots successfully. Refreshing view...`, 'success');
                setIsImportOpen(false);
                
                // FORCE REFRESH: Fetch specifically for current scene to ensure we have data immediately
                // Try refreshing both full episode list and specific scene
                await refreshShots(); 
                
                try {
                    const sceneSpecific = await fetchShots(selectedSceneId);
                    if (sceneSpecific && sceneSpecific.length > 0) {
                        setShots(sceneSpecific);
                    }
                } catch(e) { console.error("Post-import fetch failed", e); }

            } else {
                 onLog?.('Import completed but no shots created.', 'warning');
            }
        } else {
             onLog?.('No valid shots data found.', 'warning');
        }
    };

    // --- Helper: Parsing Entities matches ---
    // Updated Logic: Matches both [Name] and {Name}, allowing specific text source
    const getSuggestedRefImages = useCallback((shot, sourceText = null, strictMode = false, entitySource = null) => {
        if (!shot) return [];
        const entList = Array.isArray(entitySource) ? entitySource : entities;
        
        if (!entList.length) {
            return [];
        }


        // Updated Logic: Matches both [Name] and {Name}, allowing specific text source
        // Now synchronized with ReferenceManager logic for consistent robust matching
        const normalizeName = (s) => normalizeEntityToken(s);
        
        // Associated Entities (Included unless strictMode is true)
        const rawNames1 = strictMode ? [] : (shot.associated_entities || '').split(/[,，]/);
        
        // Prompt Search logic - Unified Regexes from ReferenceManager
        const regexes = [
            /\[([\s\S]+?)\]/g,    // [...]
            /\{([\s\S]+?)\}/g,    // {...}
            /【([\s\S]+?)】/g,     // 【...】
            /｛([\s\S]+?)｝/g,      // ｛...｝
            /(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)/g, // standalone @Name
            // Also keep legacy simple regex for cases without full brackets if needed? 
            // The legacy regex was: /[\[【\{]([^\]】\}\(]+)[\]】\}\(]/g; which was too restrictive.
        ];
        
        // If sourceText is provided, use it. Otherwise use shot fields EXCLUDING description (as per user request)
        let textToScan = sourceText;
        if (!textToScan) {
            const parts = [];
            if (shot.start_frame) parts.push(shot.start_frame);
            if (shot.end_frame) parts.push(shot.end_frame);
            if (shot.video_content) parts.push(shot.video_content);
            if (shot.prompt) parts.push(shot.prompt);
            textToScan = parts.join(' ');
        }

        const rawNames2 = [];
        if (textToScan) {
            regexes.forEach(regex => {
                let match;
                regex.lastIndex = 0;
                while ((match = regex.exec(textToScan)) !== null) {
                    if (match[1] && match[1].trim()) rawNames2.push(match[1]);
                }
            });
            // Legacy Fallback for simple "CharacterName" without brackets? No, usually enforced by [] 
        }
        
        // 3. Match Logic
        const candidates = [...rawNames1, ...rawNames2];
        const normalizedCandidates = candidates.map(normalizeName).filter(Boolean);

        let refs = entList.filter(e => {
            const cn = normalizeName(e.name || '');
            const en = normalizeName(e.name_en || '');
            
            // 3b. English Name extraction from Description (Legacy)
             if (!en && e.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) {
                    const complexEn = enMatch[1];
                    const rawEn = complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0]; 
                    // We don't redefine 'en' here as it's const, use local var if needed or just skip
                }
            }

            // Strict full-name exact check only
            const isMatch = normalizedCandidates.some(n => n === cn || (en && n === en));
            return isMatch;
        }).map(e => e.image_url).filter(Boolean);
        
        return [...new Set(refs)];
    }, [entities]);

    const getPromptMatchedEntities = useCallback((shot, sourceText = '', entitySource = null) => {
        const entityPool = Array.isArray(entitySource) ? entitySource : entities;
        if (!shot || !Array.isArray(entityPool) || entityPool.length === 0) return [];

        const normalizeName = (text) => normalizeEntityToken(text);
        const regexes = [
            /\[([\s\S]+?)\]/g,
            /\{([\s\S]+?)\}/g,
            /【([\s\S]+?)】/g,
            /｛([\s\S]+?)｝/g,
            /(?:^|[\s,，;；])(@[^\s,，;；\]\[\(\)（）\{\}【】]+)/g,
        ];

        const textToScan = String(sourceText || '').trim();
        if (!textToScan) return [];

        const candidateSet = new Set();
        regexes.forEach((regex) => {
            regex.lastIndex = 0;
            let matched;
            while ((matched = regex.exec(textToScan)) !== null) {
                const token = normalizeName(matched?.[1] || '');
                if (token) candidateSet.add(token);
            }
        });

        const candidates = Array.from(candidateSet);
        if (candidates.length === 0) return [];

        return entityPool.filter((entity) => {
            return candidates.some((candidate) => entityTokenMatchesName(entity, candidate));
        });
    }, [entities]);

    const getEndFrameVisibleRefs = useCallback((shot, sourceText = '', entitySource = null) => {
        const tech = JSON.parse(shot?.technical_notes || '{}');
        const isManualMode = Array.isArray(tech.end_ref_image_urls);
        const isUserEdited = Boolean(tech.end_ref_image_urls_user_edited);
        const isLockedManual = isManualMode && isUserEdited;
        const deletedRefs = Array.isArray(tech.deleted_ref_urls) ? tech.deleted_ref_urls : [];

        const matchedEntities = getPromptMatchedEntities(shot, sourceText, entitySource);
        const autoMatches = matchedEntities
            .map((entity) => String(entity?.image_url || '').trim())
            .filter(Boolean);
        const environmentRefSet = new Set(
            matchedEntities
                .filter((entity) => {
                    const entityType = String(entity?.type || '').trim().toLowerCase();
                    return entityType.includes('environment') || entityType.includes('env') || entityType.includes('scene');
                })
                .map((entity) => String(entity?.image_url || '').trim())
                .filter(Boolean)
        );

        let refs = [];
        if (isLockedManual) {
            refs = [...tech.end_ref_image_urls];
        } else if (isManualMode) {
            // Manual but not locked: refresh by current entity images.
            refs = autoMatches.filter((url) => !deletedRefs.includes(url));
        } else {
            refs = [...autoMatches];
        }

        const currentStartFrame = String(shot?.image_url || '').trim();
        if (!isLockedManual && currentStartFrame && !refs.includes(currentStartFrame) && !deletedRefs.includes(currentStartFrame)) {
            refs.unshift(currentStartFrame);
        }

        if (currentStartFrame && refs.includes(currentStartFrame) && environmentRefSet.size > 0) {
            refs = refs.filter((url) => {
                const normalized = String(url || '').trim();
                if (!normalized) return false;
                if (normalized === currentStartFrame) return true;
                return !environmentRefSet.has(normalized);
            });
        }

        return [...new Set(refs.map((url) => String(url || '').trim()).filter(Boolean))];
    }, [getPromptMatchedEntities]);

    // Initialize Reference Images in technical_notes if empty
    useEffect(() => {
        if (editingShot && entities.length > 0) {
            let updates = {};
            let hasUpdates = false;

            // 1. Ref Images Init
            try {
                const tech = JSON.parse(editingShot.technical_notes || '{}');
                if (tech.ref_image_urls === undefined) {
                    // Initialize strictly with Start Frame Prompt (camera_position)
                    const suggested = getSuggestedRefImages(editingShot, editingShot.start_frame);
                    if (suggested.length > 0) {
                        tech.ref_image_urls = suggested;
                        updates.technical_notes = JSON.stringify(tech);
                        hasUpdates = true;
                    }
                }
            } catch (e) { console.error("Error init ref images", e); }

            if (hasUpdates) {
                setEditingShot(prev => ({ ...prev, ...updates }));
            }
        }
    }, [editingShot?.id, entities]); // Only run when shot ID changes or entities load

    // Keyframe State Management

    // Parse keyframes from shot text + technical_notes images
    useEffect(() => {
        if (!editingShot) return;

        const rawText = editingShot.keyframes || "";
        const tech = JSON.parse(editingShot.technical_notes || '{}');
        const legacyUrls = tech.keyframes || [];
        const mappedImages = tech.keyframe_images || {}; // Map: "1.5s": url

        let parsed = [];
        
        // 1. Parse Text Prompts
        if (rawText && rawText !== "NO" && rawText.length > 5) {
            // Regex to find [Time: XX] blocks
            // Assumption: keyframes are separated by [Time: ...]
            // Example: [Time: 1.5s] Desc... [Time: 2.0s] Desc...
            // Or newlines.
            const parts = rawText.split(/\[Time:\s*/i).filter(p => p.trim().length > 0);
            
            parts.forEach((p, idx) => {
                // p will be "1.5s] Description..."
                const closeBracket = p.indexOf(']');
                let time = `KF${idx+1}`;
                let prompt = p;
                
                if (closeBracket > -1) {
                    time = p.substring(0, closeBracket).trim();
                    prompt = p.substring(closeBracket+1).trim();
                } else {
                    // Fallback
                    prompt = "[Time: " + p; 
                }
                
                // Find image
                // Try map first
                let url = mappedImages[time];
                
                // Fallback to legacy array if index matches and no map entry
                if (!url && idx < legacyUrls.length) {
                    url = legacyUrls[idx];
                }

                parsed.push({ id: idx, time, prompt, url });
            });
        }
        
        // 2. Append extra legacy images that didn't match validation text
        if (legacyUrls.length > parsed.length) {
            for (let i = parsed.length; i < legacyUrls.length; i++) {
                parsed.push({ 
                    id: i, 
                    time: `Legacy ${i+1}`, 
                    prompt: "Legacy Keyframe (Image Only)", 
                    url: legacyUrls[i],
                    isLegacy: true
                });
            }
        }
        
        // If empty and not "NO", maybe init one? No, let user add.
        setLocalKeyframes(parsed);
        
    }, [editingShot?.id, editingShot?.keyframes, editingShot?.technical_notes]);

    const handleUpdateKeyframePrompt = (idx, newText) => {
        const updated = [...localKeyframes];
        updated[idx].prompt = newText;
        setLocalKeyframes(updated);
        // Debounced save or save on blur is better, but here we can just wait for a "Save" action or similar
        // Or reconstruct immediately. Reconstructing immediately is safer for consistency.
        reconstructKeyframes(updated);
    };
    
    const reconstructKeyframes = async (currentList, newTechOverride = null) => {
         // Rebuild shot.keyframes String
         // Format: [Time: time] prompt ...
         
         const textParts = currentList
            .filter(k => !k.isLegacy) // Legacy items don't go into text unless converted
            .map(k => `[Time: ${k.time}] ${k.prompt}`);
         
         const newKeyframesText = textParts.length > 0 ? textParts.join('\n') : "NO";
         
         // Rebuild Technical Notes
         const tech = JSON.parse(editingShot.technical_notes || '{}');
         
         // 1. Legacy Array (keep for safety, but sync with list)
         const urls = currentList.map(k => k.url).filter(Boolean);
         tech.keyframes = urls;
         
         // 2. Map (Preferred)
         const imgMap = {};
         currentList.forEach(k => {
             if (k.url) imgMap[k.time] = k.url;
         });
         tech.keyframe_images = imgMap;
         
         if (newTechOverride) {
             Object.assign(tech, newTechOverride);
         }
         
         // Update Local Logic (Optimistic)
         // We don't setLocalKeyframes here because that would trigger re-render loop if we are not careful
         // But we need to update 'editingShot' to trigger persistence
         
         const newData = {
             keyframes: newKeyframesText,
             technical_notes: JSON.stringify(tech)
         };
         
         // Update parent
         await onUpdateShot(editingShot.id, newData);
         // setEditingShot handled by onUpdateShot's internal state update wrapper if we used one, 
         // but local setEditingShot is raw.
         // onUpdateShot does: setShots ... and setEditingShot ...
         // So this will trigger useEffect parse again.
         // This might cause cursor jump in textarea. 
         // Strategy: Only update 'editingShot' if we are sure? 
         // Or rely on the fact that we are editing 'localKeyframes' state for text, and only syncing on Blur?
    };

    const generateAssetWithLang = async (assetType, keyframeIndex = -1, options = {}) => {
        if (!editingShot) return;
        const shotState = generatingStateByShot[String(editingShot.id)] || { start: false, end: false, video: false };
        if (shotState.start || shotState.end || shotState.video) return;
        const cfgOverride = Number(options?.cfg);
        const normalizedCfgOverride = Number.isFinite(cfgOverride) && cfgOverride > 0
            ? clampShotImageCfg(cfgOverride)
            : null;

        if (assetType === 'start') {
            await handleGenerateStartFrame(options.finalPrompt || null, normalizedCfgOverride, options);
            return;
        }

        if (assetType === 'end') {
            await handleGenerateEndFrame(options.finalPrompt || null, normalizedCfgOverride, options);
        }

        if (assetType === 'video') {
            await handleGenerateVideo();
            return;
        }

        if (assetType === 'keyframe') {
            const kf = localKeyframes[keyframeIndex];
            if (!kf) return;
            await handleGenerateKeyframe(keyframeIndex, null, normalizedCfgOverride);
        }
    };

    // Helper for Generating Keyframe
    const handleGenerateKeyframe = async (kfIndex, promptOverride = null, cfgOverride = null) => {
        const kf = localKeyframes[kfIndex];
        if (!kf) return;
        const tech = getEditingShotTech();
        const timeKey = String(kf?.time || '').trim();
        const cnMap = (tech && typeof tech === 'object' && tech.keyframe_prompt_cn_map && typeof tech.keyframe_prompt_cn_map === 'object')
            ? tech.keyframe_prompt_cn_map
            : {};
        const cnPrompt = timeKey ? String(cnMap[timeKey] || '').trim() : '';
        
        // UI Loading State (Local)
        const updated = [...localKeyframes];
        updated[kfIndex].loading = true;
        setLocalKeyframes(updated); // Show spinner
        
        onLog?.(`Generating Keyframe for T=${kf.time}...`, 'info');
        
        try {
            // Prompt Construction
            const promptToUse = promptOverride
                || (resolvedPromptSubmitLang === 'cn' ? (cnPrompt || kf.prompt) : (kf.prompt || cnPrompt));
            const styledPrompt = applyGlobalStyleToPrompt(promptToUse, { injectIfMissing: true });
            const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(styledPrompt) });
            const fullPrompt = styledPrompt + globalCtx;
            const preferredImageSize = getEpisodePreferredImageSize(activeEpisode?.episode_info);
            
            // Generate
            const res = await generateImage(fullPrompt, null, null, { function_name: 'generate_shot_images',
                project_id: projectId,
                episode_id: activeEpisode?.id,
                shot_id: editingShot.id,
                shot_number: `${editingShot.shot_id}_KF_${kf.time}`,
                shot_name: editingShot.shot_name,
                prompt_language: resolvedPromptSubmitLang,
                asset_type: 'keyframe',
                ...(cfgOverride ? { cfg: cfgOverride } : {}),
                ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                negative_prompt: buildEntityNegativePrompt(styledPrompt, null, entities)
            });
            
            if (res && res.url) {
                try {
                    await new Promise((resolve) => {
                        const img = new Image();
                        img.onload = () => {
                            if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(res.url);
                            resolve();
                        };
                        img.onerror = resolve;
                        img.src = getFullUrl(res.url);
                    });
                } catch (preloadErr) {}

                updated[kfIndex].url = res.url;
                if (promptOverride) {
                    updated[kfIndex].prompt = promptOverride;
                }
                updated[kfIndex].loading = false;
                
                // Save
                setLocalKeyframes([...updated]); // Force re-render with image
                await reconstructKeyframes(updated);
                onLog?.(`Keyframe T=${kf.time} Generated.`, 'success');
                refreshShotAssetsMeta();
            }
        } catch(e) {
            console.error(e);
            onLog?.(`Keyframe Gen Failed: ${e.message}`, 'error');
            updated[kfIndex].loading = false;
            setLocalKeyframes(updated);
        }
    };
    
    // --- Entity Injection Helper ---
    // Injects anchor description while keeping original entity token shape.
    function injectEntityFeatures(text, isUserEdited = false, entitySource = null) {
        if (!text) return { text, modified: false };

        const styleAdjustedText = applyGlobalStyleToPrompt(text, { injectIfMissing: true });

        // If the user has manually edited the prompt, we DO NOT inject entity features automatically.
        // We respect the user's exact prompt.
        if (isUserEdited) {
            return { text: styleAdjustedText, modified: styleAdjustedText !== text };
        }

        // In ShotsView, 'entities' contains ALL entities.
        const entList = Array.isArray(entitySource) ? entitySource : entities;

        const isSubjectEntity = (entity) => {
            const typeValue = String(entity?.type || '').trim().toLowerCase();
            return typeValue === 'subject' || typeValue === 'character' || typeValue === 'char';
        };

        const resolveEntityByToken = (cleanKey) => {
            return (Array.isArray(entList) ? entList : []).find((entity) => entityTokenMatchesName(entity, cleanKey));
        };

        const computeSubjectRefIndexMap = (sourceText = '') => {
            const indexMap = new Map();
            const refs = [];
            const matches = String(sourceText || '').match(/[\[【](.*?)[\]】]/g) || [];
            for (const token of matches) {
                const cleanKey = normalizeEntityToken(token);
                const entity = resolveEntityByToken(cleanKey);
                if (!entity) continue;
                if (!isSubjectEntity(entity)) continue;
                const imageUrl = String(entity?.image_url || '').trim();
                if (!imageUrl) continue;
                if (!refs.includes(imageUrl)) {
                    refs.push(imageUrl);
                }
                indexMap.set(String(entity?.id || ''), refs.indexOf(imageUrl) + 1);
            }
            return indexMap;
        };

        const subjectRefIndexMap = computeSubjectRefIndexMap(styleAdjustedText);
        const injectedEntities = new Set();

        const regex = /[\[【](.*?)[\]】]/g;
        let newText = styleAdjustedText;
        let modified = styleAdjustedText !== text;

        newText = newText.replace(regex, (match, name, offset, string) => {
            const cleanKey = normalizeEntityToken(name);

            if (!cleanKey) return match;

            // Check if followed by 's (possessive) -> Skip injection
            const tail = string.slice(offset + match.length);
            if (/^['’]s\b/i.test(tail)) {
                return match;
            }

            // Already injected once: [Token](...)
            if (/^\s*[\(（]/.test(tail)) {
                return match;
            }

            // 1. [Global Style] is injected before entity pass.
            if (cleanKey === 'global style' || cleanKey === 'global_style') {
                return match;
            }

            // 2. Entity Injection
            if (entList.length > 0) {
                const entity = resolveEntityByToken(cleanKey);

                if (entity) {
                    modified = true;
                    const anchor = entity.anchor_description || entity.description || '';
                    const isSubject = isSubjectEntity(entity);
                    const refNo = isSubject ? subjectRefIndexMap.get(String(entity?.id || '')) : null;

                    if (injectedEntities.has(cleanKey)) {
                        return refNo ? `${match}(ref_image_url: #${refNo})` : match;
                    }

                    injectedEntities.add(cleanKey);
                    const anchorWithRef = [
                        anchor,
                        (isSubject && refNo) ? `ref_image_url: #${refNo}` : ''
                    ].filter(Boolean).join(' | ');
                    return anchorWithRef ? `${match}(${anchorWithRef})` : match;
                }
            }

            return match;
        });

        return { text: newText, modified };
    }

    const isStartFrameInheritPrompt = (value) => {
        const token = String(value || '').trim().toUpperCase();
        return token === 'SAME' || token === 'SAP';
    };

    const findPrevShotEndFrameUrl = (shotId) => {
        const currentIdx = shots.findIndex(s => s.id === shotId);
        if (currentIdx <= 0) return null;
        try {
            const prevShot = shots[currentIdx - 1];
            const prevTech = JSON.parse(prevShot.technical_notes || '{}');
            return prevTech.end_frame_url || null;
        } catch (e) {
            return null;
        }
    };

    useEffect(() => {
        if (!editingShot?.id) {
            startFrameAutoInheritRef.current = '';
            return;
        }

        if (!isStartFrameInheritPrompt(editingShot.start_frame)) {
            startFrameAutoInheritRef.current = '';
            return;
        }

        const prevEndUrl = String(findPrevShotEndFrameUrl(editingShot.id) || '').trim();
        if (!prevEndUrl) return;

        const currentStartImage = String(editingShot.image_url || '').trim();
        if (currentStartImage === prevEndUrl) return;

        const syncKey = `${editingShot.id}:${prevEndUrl}`;
        if (startFrameAutoInheritRef.current === syncKey) return;
        startFrameAutoInheritRef.current = syncKey;

        const updates = { image_url: prevEndUrl };
        setEditingShot(prev => (prev && prev.id === editingShot.id ? { ...prev, ...updates } : prev));
        onUpdateShot(editingShot.id, updates).catch((e) => {
            console.warn('Auto inherit start frame failed:', e);
            startFrameAutoInheritRef.current = '';
        });
    }, [editingShot?.id, editingShot?.start_frame, editingShot?.image_url, shots, onUpdateShot, setEditingShot]);

    // --- Generation Handlers ---
    const handleGenerateStartFrame = async (promptOverride = null, cfgOverride = null, extraProviderOptions = {}) => {
        if (!editingShot) return;
        const shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        let createdImageJobId = '';
        let keepRunningUi = false;

        // Check inherit logic - Inherit from previous End Frame
        const currentPrompt = String(promptOverride || shotSnapshot.start_frame || '').trim();
        if (isStartFrameInheritPrompt(currentPrompt)) {
            const prevEndUrl = findPrevShotEndFrameUrl(shotSnapshot.id);

            if (prevEndUrl) {
                try {
                    onLog?.('Inheriting Start Frame from previous shot...', 'info');
                    const newData = { image_url: prevEndUrl };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev));
                    onLog?.('Start Frame inherited successfully', 'success');
                    showNotification('Start Frame inherited from previous shot', 'success');
                    return; // Exit, do not generate
                } catch (err) {
                    console.error("Error inheriting frame", err);
                    showNotification(`Failed to inherit frame: ${err?.message || 'Unknown error'}`, "error");
                }
            } else {
                const noPrevMsg = shots.findIndex(s => s.id === editingShot.id) <= 0
                    ? 'No previous shot to inherit from'
                    : 'Previous shot has no End Frame to inherit';
                showNotification(noPrevMsg, 'warning');
                return;
            }
        }

        setShotGeneratingState(targetShotId, 'start', true);
        abortGenerationRef.current = false; 

        const resolvedEntities = await awaitShotGenerationEntities();

        const techNotes = JSON.parse(shotSnapshot.technical_notes || '{}');
        const cnStartPrompt = String(techNotes.start_frame_cn || '').trim();
        const rawPrompt = promptOverride
            || (resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || shotSnapshot.start_frame || shotSnapshot.video_content || "A cinematic shot")
            : (shotSnapshot.start_frame || cnStartPrompt || shotSnapshot.video_content || "A cinematic shot"));
        const isManual = techNotes.manual_start_frame === true;

        const { text: submitPrompt } = injectEntityFeatures(rawPrompt, isManual, resolvedEntities);

        onLog?.('Generating Start Frame...', 'info');
        
        let success = false;
        let attempts = 0;
        const maxAttempts = 1;

        while (!success && attempts < maxAttempts) {
             if (abortGenerationRef.current) {
                 onLog?.('Start Frame generation stopped by user.', 'warning');
                 break;
             }

             attempts++;
             if (attempts > 1) {
                 onLog?.(`Retrying Start Frame (Attempt ${attempts}/${maxAttempts})...`, 'warning');
                 showNotification(`Retrying Start Frame (Attempt ${attempts}/${maxAttempts})...`, 'info');
             }

             try {
                const refs = resolveShotStartFrameRefs(shotSnapshot, rawPrompt, resolvedEntities);
                if (extraProviderOptions && extraProviderOptions.auto_refs) {
                    refs.push(...extraProviderOptions.auto_refs);
                    delete extraProviderOptions.auto_refs;
                }

                // NEW: Inject Global Context
                const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
                const finalPrompt = isManual ? submitPrompt : (submitPrompt + globalCtx);
                const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
                const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info);

                const res = await generateImage(finalPrompt, null, refs.length > 0 ? refs : null, { function_name: 'generate_shot_images',
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: targetShotId,
                    shot_number: shotSnapshot.shot_id,
                    shot_name: shotSnapshot.shot_name,
                    prompt_language: resolvedPromptSubmitLang,
                    asset_type: 'start_frame',
                    ...(preferredAspectRatio ? { aspect_ratio: preferredAspectRatio } : {}),
                    ...(cfgOverride ? { cfg: cfgOverride } : {}),
                    ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                    ...extraProviderOptions,
                    negative_prompt: buildEntityNegativePrompt(rawPrompt, null, resolvedEntities),
                    on_job_created: (jobId) => {
                        createdImageJobId = String(jobId || '').trim();
                        setPendingImageJob(targetShotId, 'start', jobId);
                        setShotGeneratingState(targetShotId, 'start', true);
                    },
                });
                if (res && res.url) {
                    try {
                        await new Promise((resolve) => {
                            const img = new Image();
                            img.onload = () => {
                                if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(res.url);
                                resolve();
                            };
                            img.onerror = resolve;
                            img.src = getFullUrl(res.url);
                        });
                    } catch (preloadErr) {}

                    clearPendingImageJob(targetShotId, 'start');
                    // Save original prompt to DB (user view), but image was generated with context
                    const newData = { image_url: res.url, start_frame: rawPrompt };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev)); 
                    onLog?.('Start Frame Generated', 'success');
                    showNotification('Start Frame Generated', 'success');
                    refreshShotAssetsMeta();
                    success = true;
                } else {
                    throw new Error("No image URL returned");
                }
            } catch (e) {
                console.error(`Attempt ${attempts} failed:`, e);
                if (isClientInterruptionError(e)) {
                    const recovered = await tryRecoverShotMediaAfterInterruption({
                        shotId: targetShotId,
                        mediaKey: 'start',
                    });
                    if (recovered) {
                        keepRunningUi = true;
                        success = true;
                        break;
                    }
                }
                if (createdImageJobId) {
                    clearPendingImageJob(targetShotId, 'start');
                    createdImageJobId = '';
                }
                if (attempts >= maxAttempts) {
                    onLog?.(`Generation failed after ${maxAttempts} attempts: ${e.message}`, 'error');
                    showNotification(`Generation failed: ${e.message}`, 'error');
                }
            }
        }
        if (!keepRunningUi) {
            clearPendingImageJob(targetShotId, 'start');
            setShotGeneratingState(targetShotId, 'start', false);
        }
    };

    const handleGenerateEndFrame = async (promptOverride = null, cfgOverride = null, extraProviderOptions = {}) => {
        if (!editingShot) return;
        const shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        let createdImageJobId = '';
        let keepRunningUi = false;
        setShotGeneratingState(targetShotId, 'end', true);
        abortGenerationRef.current = false;

        const resolvedEntities = await awaitShotGenerationEntities();

        const techNotes = JSON.parse(shotSnapshot.technical_notes || '{}');
        const cnEndPrompt = String(techNotes.end_frame_cn || '').trim();
        const rawPrompt = promptOverride
            || (resolvedPromptSubmitLang === 'cn'
                ? (cnEndPrompt || shotSnapshot.end_frame || "End frame")
                : (shotSnapshot.end_frame || cnEndPrompt || "End frame"));
        const isManual = techNotes.manual_end_frame === true;

        const { text: submitPrompt } = injectEntityFeatures(rawPrompt, isManual, resolvedEntities);

        onLog?.('Generating End Frame...', 'info');

        let success = false;
        let attempts = 0;
        const maxAttempts = 1;

        while (!success && attempts < maxAttempts) {
             if (abortGenerationRef.current) {
                 onLog?.('End Frame generation stopped by user.', 'warning');
                 break;
             }

             attempts++;
             if (attempts > 1) {
                 onLog?.(`Retrying End Frame (Attempt ${attempts}/${maxAttempts})...`, 'warning');
                 showNotification(`Retrying End Frame (Attempt ${attempts}/${maxAttempts})...`, 'info');
             }

             try {
                const tech = JSON.parse(shotSnapshot.technical_notes || '{}');
                const uniqueRefs = getEndFrameVisibleRefs(shotSnapshot, rawPrompt, resolvedEntities);
                if (extraProviderOptions && extraProviderOptions.auto_refs) {
                    uniqueRefs.push(...extraProviderOptions.auto_refs);
                    delete extraProviderOptions.auto_refs;
                }

                // NEW: Inject Global Context
                const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
                const finalPrompt = isManual ? submitPrompt : (submitPrompt + globalCtx);
                const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
                const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info);

                const res = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, { function_name: 'generate_shot_images',
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: targetShotId,
                    shot_number: shotSnapshot.shot_id,
                    shot_name: shotSnapshot.shot_name,
                    prompt_language: resolvedPromptSubmitLang,
                    asset_type: 'end_frame',
                    ...(preferredAspectRatio ? { aspect_ratio: preferredAspectRatio } : {}),
                    ...(cfgOverride ? { cfg: cfgOverride } : {}),
                    ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                    ...extraProviderOptions,
                    negative_prompt: buildEntityNegativePrompt(rawPrompt, null, resolvedEntities),
                    on_job_created: (jobId) => {
                        createdImageJobId = String(jobId || '').trim();
                        setPendingImageJob(targetShotId, 'end', jobId);
                        setShotGeneratingState(targetShotId, 'end', true);
                    },
                });
                if (res && res.url) {
                    try {
                        await new Promise((resolve) => {
                            const img = new Image();
                            img.onload = () => {
                                if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(res.url);
                                resolve();
                            };
                            img.onerror = resolve;
                            img.src = getFullUrl(res.url);
                        });
                    } catch (preloadErr) {}

                    clearPendingImageJob(targetShotId, 'end');
                    tech.end_frame_url = res.url;
                    tech.video_gen_mode = 'start_end'; // Auto-switch to Start+End
                    const newData = { technical_notes: JSON.stringify(tech), end_frame: rawPrompt };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev));
                    onLog?.('End Frame Generated', 'success');
                    showNotification('End Frame Generated', 'success');
                    refreshShotAssetsMeta();
                    success = true;
                } else {
                     throw new Error("No image URL returned");
                }
            } catch (e) {
                console.error(`Attempt ${attempts} failed:`, e);
                if (isClientInterruptionError(e)) {
                    const recovered = await tryRecoverShotMediaAfterInterruption({
                        shotId: targetShotId,
                        mediaKey: 'end',
                    });
                    if (recovered) {
                        keepRunningUi = true;
                        success = true;
                        break;
                    }
                }
                if (createdImageJobId) {
                    clearPendingImageJob(targetShotId, 'end');
                    createdImageJobId = '';
                }
                if (attempts >= maxAttempts) {
                    onLog?.(`Generation failed after ${maxAttempts} attempts: ${e.message}`, 'error');
                    showNotification(`Generation failed: ${e.message}`, 'error');
                }
            }
        }
        if (!keepRunningUi) {
            clearPendingImageJob(targetShotId, 'end');
            setShotGeneratingState(targetShotId, 'end', false);
        }
    };

    const handleForceStopShotImage = useCallback(async (kind) => {
        const stableKind = kind === 'end' ? 'end' : 'start';
        const stableShotId = String(editingShot?.id || '').trim();
        if (!stableShotId) return;
        const pendingPayload = getPendingImageJobPayload(stableShotId, stableKind);
        const isJointDiptych = pendingPayload?.mode === 'joint_diptych';

        abortGenerationRef.current = true;
        if (isJointDiptych) {
            setShotGeneratingState(stableShotId, 'start', false);
            setShotGeneratingState(stableShotId, 'end', false);
    setShotGeneratingState(stableShotId, 'cropping', false);
        } else {
            setShotGeneratingState(stableShotId, stableKind, false);
        }

        const resolved = await syncShotMediaRuntimeState({
            shotId: stableShotId,
            mediaKey: stableKind,
            releaseIfMissing: false,
        });
        const jobId = String(resolved?.jobId || '').trim();

        if (!jobId) {
            if (isJointDiptych) {
                releaseShotJointDiptychUiByShotId(stableShotId);
            } else {
                releaseShotImageUiByShotId(stableShotId, stableKind);
            }
            onLog?.(t('已停止前端重试循环，并清除本地图片运行状态。未检测到可停止的后端图片任务。', 'Stopped local retry loop and cleared local image running state. No active backend image job found.'), 'warning');
            return;
        }

        try {
            const res = await stopGenerationJob('image', jobId, { force: true });
            onLog?.(res?.message || t('已请求停止图片任务。', 'Image stop requested.'), 'warning');
            showNotification(t('已请求停止图片任务', 'Image stop requested'), 'warning');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'unknown error';
            if (isMissingJobError(e)) {
                if (isJointDiptych) {
                    releaseShotJointDiptychUiByShotId(stableShotId);
                } else {
                    releaseShotImageUiByShotId(stableShotId, stableKind);
                }
                onLog?.(t('后端图片任务已不存在，已清除本地运行状态。', 'Backend image job no longer exists. Cleared local running state.'), 'warning');
                return;
            }
            onLog?.(`${t('停止图片任务失败', 'Failed to stop image task')}: ${detail}`, 'error');
            showNotification(`${t('停止失败', 'Stop failed')}: ${detail}`, 'error');
        } finally {
            if (isJointDiptych) {
                clearPendingJointDiptychImageJob(stableShotId);
            } else {
                clearPendingImageJob(stableShotId, stableKind);
            }
        }
    }, [clearPendingImageJob, clearPendingJointDiptychImageJob, editingShot?.id, getPendingImageJobPayload, isMissingJobError, onLog, releaseShotImageUiByShotId, releaseShotJointDiptychUiByShotId, setShotGeneratingState, syncShotMediaRuntimeState, t]);

    const handleSetEndFrameFromVideoLastFrame = useCallback(async () => {
        if (!editingShot?.id) return;
        const targetShotId = editingShot.id;
        const videoUrlRaw = String(editingShot.video_url || '').trim();
        if (!videoUrlRaw) {
            onLog?.(t('当前镜头没有视频，无法提取尾帧。', 'No shot video found to extract the last frame.'), 'warning');
            return;
        }

        const captureLastFrameBlob = (videoUrl) => new Promise((resolve, reject) => {
            const video = document.createElement('video');

            const cleanup = () => {
                video.onloadedmetadata = null;
                video.onseeked = null;
                video.onerror = null;
                video.src = '';
            };

            const fail = (errorLike) => {
                cleanup();
                reject(errorLike instanceof Error ? errorLike : new Error(String(errorLike || 'capture failed')));
            };

            const capture = () => {
                try {
                    const width = Number(video.videoWidth || 0);
                    const height = Number(video.videoHeight || 0);
                    if (!width || !height) {
                        fail(new Error('video resolution unavailable'));
                        return;
                    }

                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    if (!ctx) {
                        fail(new Error('canvas context unavailable'));
                        return;
                    }

                    ctx.drawImage(video, 0, 0, width, height);
                    canvas.toBlob((blob) => {
                        cleanup();
                        if (!blob) {
                            reject(new Error('failed to encode frame image'));
                            return;
                        }
                        resolve(blob);
                    }, 'image/jpeg', 0.94);
                } catch (e) {
                    fail(e);
                }
            };

            video.crossOrigin = 'anonymous';
            video.preload = 'auto';
            video.muted = true;
            video.playsInline = true;
            video.onerror = () => fail(new Error('video load error'));
            video.onloadedmetadata = () => {
                const duration = Number(video.duration || 0);
                if (!Number.isFinite(duration) || duration <= 0) {
                    capture();
                    return;
                }
                const target = Math.max(0, duration - 0.05);
                if (Math.abs((video.currentTime || 0) - target) < 0.01) {
                    capture();
                    return;
                }
                video.currentTime = target;
            };
            video.onseeked = capture;
            video.src = getFullUrl(videoUrl);
        });

        setShotGeneratingState(targetShotId, 'end', true);
        try {
            const frameBlob = await captureLastFrameBlob(videoUrlRaw);
            const frameFile = new File(
                [frameBlob],
                `shot_${targetShotId}_video_last_frame_${Date.now()}.jpg`,
                { type: 'image/jpeg' }
            );
            const extractUploadIdempotencyKey = buildShotFrameAssetUploadIdempotencyKey({
                operation: 'video_last_frame',
                shotId: targetShotId,
                frameRole: 'end',
                sourceUrl: videoUrlRaw,
            });

            const uploaded = await uploadAsset(frameFile, {
                project_id: projectId,
                episode_id: activeEpisode?.id,
                shot_id: targetShotId,
                shot_number: editingShot.shot_id,
                shot_name: editingShot.shot_name,
                asset_type: 'end_frame',
                source_asset_url: videoUrlRaw,
                idempotency_key: extractUploadIdempotencyKey,
            });
            const extractedUrl = String(uploaded?.url || '').trim();
            if (!extractedUrl) {
                throw new Error('uploaded frame has no url');
            }

            const tech = JSON.parse(editingShot.technical_notes || '{}');
            tech.end_frame_url = extractedUrl;
            tech.video_gen_mode = 'start_end';
            await persistEditingShotUpdates({ technical_notes: JSON.stringify(tech) });

            onLog?.(t('已从视频提取最后一帧并设置为结束帧。', 'Last video frame extracted and set as end frame.'), 'success');
            showNotification(t('已设置结束帧', 'End frame set from video'), 'success');
        } catch (e) {
            const detail = e?.message || 'unknown error';
            onLog?.(`${t('提取视频尾帧失败', 'Failed to extract video last frame')}: ${detail}`, 'error');
            showNotification(t('提取视频尾帧失败', 'Failed to extract video last frame'), 'error');
        } finally {
            setShotGeneratingState(targetShotId, 'end', false);
        }
    }, [editingShot, onLog, persistEditingShotUpdates, projectId, setShotGeneratingState, t]);

    const isVoiceoverSyncEnabled = useMemo(() => {
        try {
            const tech = JSON.parse(editingShot?.technical_notes || '{}');
            return Boolean(tech?.video_generate_voiceover);
        } catch (e) {
            return false;
        }
    }, [editingShot?.technical_notes]);

    const setVoiceoverSyncEnabled = useCallback((enabled) => {
        setEditingShot((prev) => {
            if (!prev) return prev;
            let tech = {};
            try {
                tech = JSON.parse(prev.technical_notes || '{}');
                if (!tech || typeof tech !== 'object') tech = {};
            } catch (e) {
                tech = {};
            }
            tech.video_generate_voiceover = Boolean(enabled);
            return { ...prev, technical_notes: JSON.stringify(tech) };
        });
    }, []);

    const setShotVoiceGenerating = useCallback((shotId, value) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return;
        setVoiceGeneratingByShot((prev) => {
            if (value) return { ...prev, [stableShotId]: true };
            const next = { ...prev };
            delete next[stableShotId];
            return next;
        });
    }, []);

    const buildVoiceGenerationContext = (shot, basePromptOverride = null) => {
        if (!shot) return null;
        const tech = (() => {
            try {
                const parsed = JSON.parse(shot.technical_notes || '{}');
                return parsed && typeof parsed === 'object' ? parsed : {};
            } catch (e) {
                return {};
            }
        })();

        const cnVideoPrompt = String(tech.video_prompt_cn || '').trim();
        const rawPrompt = basePromptOverride
            || (resolvedPromptSubmitLang === 'cn'
                ? (cnVideoPrompt || getShotVideoPromptEn(shot) || 'Video motion')
                : (getShotVideoPromptEn(shot) || cnVideoPrompt || 'Video motion'));
        const isManual = tech.manual_video_prompt === true;
        const { text: submitPrompt } = injectEntityFeatures(rawPrompt, isManual);
        const finalPrompt = isManual
            ? submitPrompt
            : (submitPrompt + getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) }));

        const projectLanguage = String(
            activeEpisode?.episode_info?.e_global_info?.language
            || activeEpisode?.episode_info?.language
            || project?.global_info?.language
            || ''
        ).trim();
        const voiceBuild = buildVoicePromptWithEntityContext(finalPrompt, entities, projectLanguage, uiLang);
        const voicePrompt = String(voiceBuild.voicePrompt || '').trim();

        return {
            shot,
            voicePrompt,
            languageCode: voiceBuild.languageCode,
            projectLanguage: projectLanguage || voiceBuild.languageCode,
        };
    };

    const submitVoiceoverOnly = async (context) => {
        const shot = context?.shot;
        if (!shot?.id) return;

        const targetShotId = shot.id;
        const voicePrompt = String(context?.voicePrompt || '').trim();
        const plannerSystemPrompt = String(context?.plannerSystemPrompt || '').trim();
        const languageCode = String(context?.languageCode || '').trim() || 'en';
        const projectLanguage = String(context?.projectLanguage || '').trim() || languageCode;

        if (!voicePrompt) {
            onLog?.(t('未检测到对白，已取消仅配音生成', 'No dialogue detected, canceled voice-only generation'), 'warning');
            showNotification(t('未检测到可用于配音的对白', 'No dialogue available for voiceover'), 'warning');
            return;
        }

        setShotVoiceGenerating(targetShotId, true);
        try {
            onLog?.(`${t('配音语言约束', 'Voice language constraint')}: ${languageCode}`, 'info');
            onLog?.(t('开始仅生成配音...', 'Generating voiceover only...'), 'info');

            const voiceRes = await generateVoice(voicePrompt, null, null, {
                project_id: projectId,
                shot_id: targetShotId,
                shot_number: shot.shot_id,
                shot_name: shot.shot_name,
                asset_type: 'voiceover',
                use_llm_param_planning: true,
                planner_system_prompt: plannerSystemPrompt || undefined,
                language_code: languageCode,
                project_language: projectLanguage,
            });

            try {
                const planMeta = voiceRes?.voiceover_plan_prompts || {};
                const sysLen = String(planMeta?.system_prompt || '').length;
                const userLen = String(planMeta?.user_prompt || '').length;
                const src = String(planMeta?.template_source || 'unknown');
                const effectiveLen = String(voiceRes?.effective_prompt || '').length;
                onLog?.(
                    `${t('配音规划返回', 'Voice planning response')}: source=${src}, sys=${sysLen}, user=${userLen}, effective=${effectiveLen}`,
                    'info'
                );
            } catch (logErr) {
                console.warn('Voice planning response log failed', logErr);
            }

            const voiceUrl = String(voiceRes?.url || '').trim();
            if (!voiceUrl) {
                onLog?.(t('配音生成完成但未返回音频 URL', 'Voiceover completed but no audio URL returned'), 'warning');
                showNotification(t('配音生成完成但未返回音频 URL', 'Voiceover completed but no audio URL returned'), 'warning');
                return;
            }

            let tech = {};
            try {
                const parsed = JSON.parse(shot.technical_notes || '{}');
                tech = parsed && typeof parsed === 'object' ? parsed : {};
            } catch (e) {
                tech = {};
            }
            const nextTech = { ...tech, voiceover_url: voiceUrl, voiceover_prompt: voicePrompt };
            if (voiceRes?.metadata && typeof voiceRes.metadata === 'object') {
                nextTech.voiceover_metadata = voiceRes.metadata;
            }
            const voiceUpdate = { technical_notes: JSON.stringify(nextTech) };
            setEditingShot((prev) => {
                if (!prev || prev.id !== targetShotId) return prev;
                return { ...prev, ...voiceUpdate };
            });

            refreshShotAssetsMeta();
            onLog?.(t('仅配音生成完成', 'Voice-only generation completed'), 'success');
            showNotification(t('仅配音生成完成', 'Voice-only generation completed'), 'success');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'unknown error';
            onLog?.(`${t('配音生成失败', 'Voiceover generation failed')}: ${detail}`, 'error');
            showNotification(`${t('配音生成失败', 'Voiceover generation failed')}: ${detail}`, 'error');
        } finally {
            setShotVoiceGenerating(targetShotId, false);
        }
    };

    const handleGenerateVoiceoverOnly = async () => {
        if (!editingShot?.id) return;
        const context = buildVoiceGenerationContext(editingShot);
        if (!context) return;

        if (isSuperuser) {
            setVoicePromptConfirmModal({
                open: true,
                shotId: editingShot.id,
                prompt: String(context.voicePrompt || ''),
                systemPrompt: '',
                loadingSystemPrompt: true,
                languageCode: String(context.languageCode || ''),
                projectLanguage: String(context.projectLanguage || ''),
                submitting: false,
            });
            try {
                const res = await fetchPrompt('voice_tts_planner_system.txt');
                const systemPromptText = String(res?.content || '').trim();
                setVoicePromptConfirmModal((prev) => ({
                    ...prev,
                    systemPrompt: systemPromptText,
                    loadingSystemPrompt: false,
                }));
            } catch (e) {
                onLog?.(t('读取配音系统提示词失败，已使用空白值', 'Failed to load voice planner system prompt; using blank value'), 'warning');
                setVoicePromptConfirmModal((prev) => ({
                    ...prev,
                    loadingSystemPrompt: false,
                }));
            }
            onLog?.(t('超级用户模式：请确认配音提示词后再提交。', 'Superuser mode: confirm voice prompt before submitting.'), 'info');
            return;
        }

        await submitVoiceoverOnly(context);
    };

    const handleGenerateVideo = async (promptOverride = null) => {
        if (!editingShot) return;
        const shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        const targetGeneratingState = generatingStateByShot[targetShotId] || { start: false, end: false, video: false };
        if (targetGeneratingState.start || targetGeneratingState.end || targetGeneratingState.video) {
             return; 
        }

        setShotGeneratingState(targetShotId, 'video', true);

        const resolvedEntities = await awaitShotGenerationEntities();

        const techNotes = JSON.parse(shotSnapshot.technical_notes || '{}');
        const cnVideoPrompt = String(techNotes.video_prompt_cn || '').trim();
        const rawPrompt = promptOverride
            || (resolvedPromptSubmitLang === 'cn'
                ? (cnVideoPrompt || getShotVideoPromptEn(shotSnapshot) || "Video motion")
                : (getShotVideoPromptEn(shotSnapshot) || cnVideoPrompt || "Video motion"));
        const isManual = techNotes.manual_video_prompt === true;

        const { text: submitPrompt } = injectEntityFeatures(rawPrompt, isManual, resolvedEntities);

        let createdVideoJobId = '';
        let keepRunningUi = false;

        onLog?.('Generating Video...', 'info');
        try {
            const tech = JSON.parse(shotSnapshot.technical_notes || '{}');
            const keyframes = tech.keyframes || [];

            const normalizedEndPrompt = String(shotSnapshot.end_frame || '').trim().toUpperCase();
            const shouldReuseStartAsEnd = normalizedEndPrompt === 'NO';
            const currentStartFrameUrl = String(shotSnapshot.image_url || '').trim();
            if (shouldReuseStartAsEnd && currentStartFrameUrl) {
                const previousEndUrl = String(tech.end_frame_url || '').trim();
                if (previousEndUrl !== currentStartFrameUrl) {
                    tech.end_frame_url = currentStartFrameUrl;
                    tech.end_frame_reused_from_start = true;
                    const updatedTechNotes = JSON.stringify(tech);
                    await onUpdateShot(targetShotId, { technical_notes: updatedTechNotes });
                    setEditingShot((prev) => (prev && prev.id === targetShotId
                        ? { ...prev, technical_notes: updatedTechNotes }
                        : prev));
                    onLog?.(t('结束帧为 NO，已将结束帧 URL 同步为起始帧 URL。', 'End frame is NO; synced End Frame URL to Start Frame URL.'), 'info');
                }
            }

            const effectiveVideoMode = resolveUnifiedVideoMode(tech);
            const promptEntityRefs = collectMatchedSubjectImageUrlsFromPrompt({
                promptText: `${getShotVideoPromptEn(shotSnapshot) || ''}\n${String(tech.video_prompt_cn || '').trim()}`,
                entityPool: resolvedEntities,
            });
            const uniqueRefs = Array.isArray(tech.video_ref_image_urls)
                ? normalizeMediaRefList(tech.video_ref_image_urls)
                : buildAutoVideoRefList(shotSnapshot, tech, effectiveVideoMode, promptEntityRefs);

            const splitReferenceMediaUrls = (urls) => {
                const imageRefs = [];
                const videoRefs = [];

                (Array.isArray(urls) ? urls : []).forEach((item) => {
                    const rawUrl = String(item || '').trim();
                    if (!rawUrl) return;

                    let pathname = rawUrl;
                    try {
                        pathname = new URL(rawUrl, window.location.origin).pathname || rawUrl;
                    } catch {
                        pathname = rawUrl.split('?')[0].split('#')[0];
                    }

                    const normalizedPath = String(pathname || '').toLowerCase();
                    if (/\.(mp4|webm|mov|m4v|avi|mkv)$/i.test(normalizedPath)) {
                        videoRefs.push(rawUrl);
                    } else {
                        imageRefs.push(rawUrl);
                    }
                });

                return { imageRefs, videoRefs };
            };

            // Resolve local blob URLs before splitting
            const resolveBlobUrlIfAny = async (url) => {
                if (typeof url !== 'string' || !url.startsWith('blob:')) return url;
                try {
                    const res = await fetch(url);
                    const blob = await res.blob();
                    let ext = 'jpg';
                    if (blob.type === 'image/png') ext = 'png';
                    else if (blob.type === 'image/webp') ext = 'webp';
                    
                    const file = new File([blob], `blob_upload_${Date.now()}.${ext}`, { type: blob.type });
                    const uploaded = await uploadAsset(file, { project_id: projectId, shot_id: targetShotId });
                    
                    if (uploaded?.url) return uploaded.url;
                } catch (e) {
                    console.warn('[handleGenerateVideo] Failed to upload local blob to server:', e);
                }
                return url;
            };

            const resolvedUniqueRefs = await Promise.all(uniqueRefs.map(resolveBlobUrlIfAny));

            let apiRefImageUrl = null;
            let apiRefVideoUrls = null;
            let apiLastFrameUrl;
            const apiKeyframes = Array.isArray(keyframes) ? keyframes.filter(Boolean) : [];
            const { imageRefs, videoRefs } = splitReferenceMediaUrls(resolvedUniqueRefs);
            apiRefImageUrl = imageRefs.length > 0 ? imageRefs : null;
            apiRefVideoUrls = videoRefs.length > 0 ? videoRefs : null;
            apiLastFrameUrl = undefined;
            
            // Duration Logic: Use Shot Duration (s) if valid, else default to 5
            const durParam = parseFloat(editingShot.duration) || 5;

            // NEW: Inject Global Context
            const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
            const finalPrompt = isManual ? submitPrompt : (submitPrompt + globalCtx);

            onLog?.(
                `Video API payload mode=${effectiveVideoMode}, visible_refs=${uniqueRefs.length}, ref=${Array.isArray(apiRefImageUrl) ? `list(${apiRefImageUrl.length})` : (apiRefImageUrl ? 'single' : 'none')}, ref_videos=${Array.isArray(apiRefVideoUrls) ? apiRefVideoUrls.length : 0}, last_frame=${apiLastFrameUrl ? 'yes' : 'no'}, keyframes=${Array.isArray(apiKeyframes) ? apiKeyframes.length : 0}, duration=${durParam}`,
                'info'
            );

            let videoTaskPromise = null;
            try {
                videoTaskPromise = generateVideo(finalPrompt, null, apiRefImageUrl, apiRefVideoUrls, apiLastFrameUrl, durParam, { function_name: 'generate_videos',
                    project_id: projectId,
                    shot_id: targetShotId,
                    shot_number: shotSnapshot.shot_id,
                    shot_name: shotSnapshot.shot_name,
                    ref_mode: effectiveVideoMode,
                    prompt_language: resolvedPromptSubmitLang,
                    asset_type: 'video',
                    negative_prompt: buildEntityNegativePrompt(rawPrompt, null, resolvedEntities),
                    on_job_created: (jobId) => {
                        createdVideoJobId = String(jobId || '').trim();
                        setPendingVideoJob(targetShotId, jobId);
                        setShotGeneratingState(targetShotId, 'video', true);
                    },
                }, apiKeyframes);
                onLog?.(t('视频请求已发起', 'Video request dispatched'), 'info');
            } catch (videoDispatchError) {
                onLog?.(`${t('视频请求发起失败', 'Video request dispatch failed')}: ${videoDispatchError?.message || 'unknown error'}`, 'error');
                throw videoDispatchError;
            }

            const shouldGenerateVoiceover = Boolean(tech.video_generate_voiceover);
            let voiceTaskPromise = null;
            let usedVoicePrompt = '';
            if (shouldGenerateVoiceover) {
                const projectLanguage = String(
                    activeEpisode?.episode_info?.e_global_info?.language
                    || activeEpisode?.episode_info?.language
                    || project?.global_info?.language
                    || ''
                ).trim();
                const voiceBuild = buildVoicePromptWithEntityContext(finalPrompt, resolvedEntities, projectLanguage, uiLang);
                usedVoicePrompt = String(voiceBuild.voicePrompt || '').trim();
                if (!usedVoicePrompt) {
                    onLog?.(t('未检测到对白，已跳过配音生成', 'No dialogue detected, skipped voiceover generation'), 'warning');
                } else {
                    onLog?.(`${t('配音语言约束', 'Voice language constraint')}: ${voiceBuild.languageCode}`, 'info');
                    if (Array.isArray(voiceBuild.matchedEntities) && voiceBuild.matchedEntities.length > 0) {
                        const names = voiceBuild.matchedEntities
                            .map((entity) => String(entity?.name_en || entity?.name || '').trim())
                            .filter(Boolean)
                            .join(', ');
                        onLog?.(`${t('配音角色识别', 'Voice role context')}: ${names}`, 'info');
                    }
                    onLog?.(t('开始生成配音...', 'Generating voiceover...'), 'info');
                    voiceTaskPromise = generateVoice(usedVoicePrompt, null, null, {
                        project_id: projectId,
                        shot_id: targetShotId,
                        shot_number: editingShot.shot_id,
                        shot_name: editingShot.shot_name,
                        asset_type: 'voiceover',
                        use_llm_param_planning: true,
                        language_code: voiceBuild.languageCode,
                        project_language: projectLanguage || voiceBuild.languageCode,
                    });
                }
            }

            if (shouldGenerateVoiceover) {
                onLog?.(t('视频与配音已并发发起', 'Video and voiceover requests dispatched concurrently'), 'info');
            }

            const [videoSettled, voiceSettled] = await Promise.allSettled([
                videoTaskPromise,
                voiceTaskPromise || Promise.resolve(null),
            ]);

            if (videoSettled.status === 'fulfilled' && videoSettled.value && videoSettled.value.url) {
                const res = videoSettled.value;
                clearPendingVideoJob(targetShotId);
                const newData = { video_url: res.url, prompt: rawPrompt };
                
                // 1. Force Local State Update IMMEDIATELY (Optimistic/Local)
                setEditingShot(prev => {
                         if (!prev || prev.id !== targetShotId) return prev;
                   return { ...prev, ...newData };
                });
                
                onLog?.('Video Generated', 'success');
                showNotification('Video Generated', 'success');

                // 2. Update Server & Master List (Async persistence)
                try {
                    await onUpdateShot(targetShotId, newData);
                } catch (updateErr) {
                    console.error("Failed to save shot update to backend:", updateErr);
                    // We don't block the UI - the video is here.
                }

                // 3. Refresh asset metadata so resolution/aspect_ratio show immediately
                refreshShotAssetsMeta();
            }

            if (voiceTaskPromise) {
                if (voiceSettled.status === 'fulfilled') {
                    const voiceRes = voiceSettled.value;
                    const voiceUrl = String(voiceRes?.url || '').trim();
                    if (voiceUrl) {
                        const persistedVoicePrompt = usedVoicePrompt || extractDialogueOnlyFromPrompt(finalPrompt) || finalPrompt;
                        const nextTech = { ...tech, voiceover_url: voiceUrl, voiceover_prompt: persistedVoicePrompt };
                        if (voiceRes?.metadata && typeof voiceRes.metadata === 'object') {
                            nextTech.voiceover_metadata = voiceRes.metadata;
                        }
                        const voiceUpdate = { technical_notes: JSON.stringify(nextTech) };
                        setEditingShot(prev => {
                            if (!prev || prev.id !== targetShotId) return prev;
                            return { ...prev, ...voiceUpdate };
                        });

                        // Backend /generate/voice already persists shot technical notes,
                        // including planning fields; avoid racing overwrite from stale local tech.
                        refreshShotAssetsMeta();
                        onLog?.(t('配音生成完成', 'Voiceover generated'), 'success');
                    } else {
                        onLog?.(t('配音生成完成但未返回音频 URL', 'Voiceover completed but no audio URL returned'), 'warning');
                    }
                } else {
                    const voiceErr = voiceSettled.reason;
                    const detail = voiceErr?.response?.data?.detail || voiceErr?.message || 'unknown error';
                    onLog?.(`${t('配音生成失败', 'Voiceover generation failed')}: ${detail}`, 'error');
                }
            }

            if (videoSettled.status === 'rejected') {
                const e = videoSettled.reason;
                if (isClientInterruptionError(e)) {
                    const recovered = await tryRecoverShotMediaAfterInterruption({
                        shotId: targetShotId,
                        mediaKey: 'video',
                    });
                    if (recovered) {
                        keepRunningUi = true;
                    } else if (createdVideoJobId) {
                        onLog?.('Video job is still running on server; it will auto-resume when you return.', 'warning');
                        showNotification('Video job continues in background.', 'info');
                        keepRunningUi = true;
                    } else {
                        clearPendingVideoJob(targetShotId);
                        onLog?.(`Generation failed: ${e?.message || 'unknown error'}`, 'error');
                        showNotification(`Generation failed: ${e?.message || 'unknown error'}`, 'error');
                    }
                } else {
                    clearPendingVideoJob(targetShotId);
                    onLog?.(`Generation failed: ${e?.message || 'unknown error'}`, 'error');
                    showNotification(`Generation failed: ${e?.message || 'unknown error'}`, 'error');
                }
            }
        } catch (e) {
             if (isClientInterruptionError(e)) {
                 const recovered = await tryRecoverShotMediaAfterInterruption({
                     shotId: targetShotId,
                     mediaKey: 'video',
                 });
                 if (recovered) {
                     keepRunningUi = true;
                 } else if (createdVideoJobId) {
                     onLog?.('Video job is still running on server; it will auto-resume when you return.', 'warning');
                     showNotification('Video job continues in background.', 'info');
                     keepRunningUi = true;
                 } else {
                     clearPendingVideoJob(targetShotId);
                     onLog?.(`Generation failed: ${e.message}`, 'error');
                     showNotification(`Generation failed: ${e.message}`, 'error');
                 }
             } else {
                 clearPendingVideoJob(targetShotId);
                 onLog?.(`Generation failed: ${e.message}`, 'error');
                 showNotification(`Generation failed: ${e.message}`, 'error');
             }
        } finally {
            if (!keepRunningUi) {
                setShotGeneratingState(targetShotId, 'video', false);
            }
        }
    };

    const handleForceStopShotVideo = useCallback(async (shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return;
        const resolved = await syncShotMediaRuntimeState({
            shotId: stableShotId,
            mediaKey: 'video',
            releaseIfMissing: false,
        });
        const jobId = String(resolved?.jobId || '').trim();
        if (!jobId) {
            releaseShotVideoUiByShotId(stableShotId);
            onLog?.(t('未找到后端视频任务，已清除当前镜头的本地运行状态。', 'No live backend video job was found. Cleared local running state for this shot.'), 'warning');
            showNotification(t('已清除本地视频运行状态', 'Local video running state cleared'), 'warning');
            return;
        }

        const confirmed = await confirmUiMessage(t(
            `确认强制停止该镜头视频任务？\njob_id: ${jobId}`,
            `Force stop this shot video task?\njob_id: ${jobId}`
        ));
        if (!confirmed) return;

        setStoppingVideoByShot((prev) => ({ ...prev, [stableShotId]: true }));
        try {
            const res = await stopGenerationJob('video', jobId, { force: true });
            releaseShotVideoUiByShotId(stableShotId);
            onLog?.(res?.message || t('已强制停止视频任务。', 'Video task force-stopped.'), 'warning');
            showNotification(t('已强制停止视频任务', 'Video task force-stopped'), 'warning');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'unknown error';
            const detailLower = String(detail).toLowerCase();
            if (detailLower.includes('job not found') || detailLower.includes('not found')) {
                releaseShotVideoUiByShotId(stableShotId);
                onLog?.(t('后端任务已不存在，已清除当前镜头的本地运行状态。', 'Backend job no longer exists. Cleared local running state for this shot.'), 'warning');
                showNotification(t('后端任务不存在，已解除锁定', 'Backend job missing, lock cleared'), 'warning');
                return;
            }
            onLog?.(`${t('停止视频任务失败', 'Failed to stop video task')}: ${detail}`, 'error');
            showNotification(`${t('停止失败', 'Stop failed')}: ${detail}`, 'error');
        } finally {
            setStoppingVideoByShot((prev) => {
                const next = { ...prev };
                delete next[stableShotId];
                return next;
            });
        }
    }, [onLog, releaseShotVideoUiByShotId, syncShotMediaRuntimeState, t]);

    const applyShotPatchToLocalState = useCallback((shotId, patch) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId || !patch || typeof patch !== 'object') return;
        setShots(prev => prev.map((shot) => (String(shot?.id || '') === stableShotId ? { ...shot, ...patch } : shot)));
        setEditingShot(prev => (String(prev?.id || '') === stableShotId ? { ...prev, ...patch } : prev));
    }, []);

    const generateShotKeyframesBatchItem = useCallback(async ({ shotSnapshot, resolvedEntities, priorEndFrameUrl = '' }) => {
        const stableShot = shotSnapshot || null;
        const stableShotId = String(stableShot?.id || '').trim();
        if (!stableShotId) {
            throw new Error('Missing shot id for batch keyframe generation');
        }

        let workingShot = { ...stableShot };
        let techNotes = {};
        try {
            techNotes = JSON.parse(workingShot.technical_notes || '{}');
        } catch {
            techNotes = {};
        }

        const cnStartPrompt = String(techNotes.start_frame_cn || '').trim();
        const cnEndPrompt = String(techNotes.end_frame_cn || '').trim();
        const rawStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || workingShot.start_frame || workingShot.video_content || 'A cinematic shot')
            : (workingShot.start_frame || cnStartPrompt || workingShot.video_content || 'A cinematic shot');
        const rawEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || workingShot.end_frame || 'End frame')
            : (workingShot.end_frame || cnEndPrompt || 'End frame');

        const normalizedEndPrompt = String(rawEndPrompt || '').trim().toUpperCase();
        const endPromptIsNoLike = ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt);
        const startPromptIsInherited = isStartFrameInheritPrompt(rawStartPrompt);
        const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
        const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);

        let startUrl = String(workingShot.image_url || '').trim();
        let endUrl = String(techNotes.end_frame_url || '').trim();

        setShotGeneratingState(stableShotId, 'start', true);
        setShotGeneratingState(stableShotId, 'end', false);

        try {
            if (!startUrl && startPromptIsInherited) {
                const inheritedUrl = String(priorEndFrameUrl || '').trim();
                if (!inheritedUrl) {
                    throw new Error('Previous shot end frame is not ready for SAP inheritance');
                }
                startUrl = inheritedUrl;
                workingShot = { ...workingShot, image_url: inheritedUrl };
            }

            if (!startUrl && !startPromptIsInherited) {
                const isManualStart = techNotes.manual_start_frame === true;
                const { text: startSubmitPrompt } = injectEntityFeatures(rawStartPrompt, isManualStart, resolvedEntities);
                const startRefs = resolveShotStartFrameRefs(workingShot, rawStartPrompt, resolvedEntities);
                const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(startSubmitPrompt) });
                const finalStartPrompt = isManualStart ? startSubmitPrompt : (startSubmitPrompt + globalCtx);
                const startResult = await generateImage(finalStartPrompt, null, startRefs.length > 0 ? startRefs : null, { function_name: 'generate_shot_images',
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: stableShotId,
                    shot_number: workingShot.shot_id,
                    shot_name: workingShot.shot_name,
                    prompt_language: resolvedPromptSubmitLang,
                    asset_type: 'start_frame',
                    ...(preferredAspectRatio ? { aspect_ratio: preferredAspectRatio } : {}),
                    ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                    negative_prompt: buildEntityNegativePrompt(rawStartPrompt, null, resolvedEntities),
                    on_job_created: (jobId) => {
                        const stableJobId = String(jobId || '').trim();
                        if (!stableJobId) return;
                        setPendingImageJob(stableShotId, 'start', stableJobId);
                    },
                });
                if (!startResult?.url) {
                    throw new Error('No start frame image URL returned');
                }
                startUrl = String(startResult.url || '').trim();
                workingShot = { ...workingShot, image_url: startUrl };
            }

            clearPendingImageJob(stableShotId, 'start');
            setShotGeneratingState(stableShotId, 'start', false);
            setShotGeneratingState(stableShotId, 'end', true);

            if (!endUrl) {
                if (endPromptIsNoLike) {
                    if (!startUrl) {
                        throw new Error('Cannot reuse start frame as end frame without a start frame URL');
                    }
                    endUrl = startUrl;
                    techNotes.end_frame_url = endUrl;
                    techNotes.end_frame_reused_from_start = true;
                    techNotes.video_gen_mode = 'start_end';
                } else {
                    const isManualEnd = techNotes.manual_end_frame === true;
                    const { text: endSubmitPrompt } = injectEntityFeatures(rawEndPrompt, isManualEnd, resolvedEntities);
                    const endRefs = getEndFrameVisibleRefs({ ...workingShot, image_url: startUrl || workingShot.image_url }, rawEndPrompt, resolvedEntities);
                    const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(endSubmitPrompt) });
                    const finalEndPrompt = isManualEnd ? endSubmitPrompt : (endSubmitPrompt + globalCtx);
                    const endResult = await generateImage(finalEndPrompt, null, endRefs.length > 0 ? endRefs : null, { function_name: 'generate_shot_images',
                        project_id: projectId,
                        episode_id: activeEpisode?.id,
                        shot_id: stableShotId,
                        shot_number: workingShot.shot_id,
                        shot_name: workingShot.shot_name,
                        prompt_language: resolvedPromptSubmitLang,
                        asset_type: 'end_frame',
                        ...(preferredAspectRatio ? { aspect_ratio: preferredAspectRatio } : {}),
                        ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                        negative_prompt: buildEntityNegativePrompt(rawEndPrompt, null, resolvedEntities),
                        on_job_created: (jobId) => {
                            const stableJobId = String(jobId || '').trim();
                            if (!stableJobId) return;
                            setPendingImageJob(stableShotId, 'end', stableJobId);
                        },
                    });
                    if (!endResult?.url) {
                        throw new Error('No end frame image URL returned');
                    }
                    endUrl = String(endResult.url || '').trim();
                    techNotes.end_frame_url = endUrl;
                    techNotes.end_frame_reused_from_start = false;
                    techNotes.video_gen_mode = 'start_end';
                }
            }

            const nextPatch = {
                ...(startUrl ? { image_url: startUrl } : {}),
                start_frame: rawStartPrompt,
                end_frame: rawEndPrompt,
                technical_notes: JSON.stringify(techNotes),
            };
            await onUpdateShot(stableShotId, nextPatch);
            return {
                shotId: stableShotId,
                shotLabel: String(workingShot.shot_id || workingShot.shot_name || `#${stableShotId}`),
                shotPatch: nextPatch,
                startUrl,
                endUrl,
            };
        } finally {
            clearPendingJointDiptychImageJob(stableShotId);
            clearPendingImageJob(stableShotId, 'start');
            clearPendingImageJob(stableShotId, 'end');
            setShotGeneratingState(stableShotId, 'start', false);
            setShotGeneratingState(stableShotId, 'end', false);
    setShotGeneratingState(stableShotId, 'cropping', false);
        }
    }, [activeEpisode?.episode_info, activeEpisode?.id, activeImageCapabilityProfile?.aspectRatios, activeImageCapabilityProfile?.imageSizeValues, applyJointShotDiptychResult, buildEntityNegativePrompt, buildShotDiptychPlan, clearPendingImageJob, clearPendingJointDiptychImageJob, getEndFrameVisibleRefs, getEpisodePreferredAspectRatio, getEpisodePreferredImageSize, getGlobalContextStr, injectEntityFeatures, isStartFrameInheritPrompt, onUpdateShot, project?.global_info, projectId, resolveJointShotDiptychRefs, resolveShotPanelExportResolution, resolveShotStartFrameRefs, resolvedPromptSubmitLang, selectBestShotDiptychRequestAspectRatio, setPendingImageJob, setPendingJointDiptychImageJob, setShotGeneratingState]);

    const runLocalKeyframeBatch = useCallback(async () => {
        const orderedShots = (Array.isArray(shots) ? shots : []).filter((shot) => Boolean(shot?.id));
        const targetShots = orderedShots.filter((shot) => {
            const currentStartUrl = String(shot?.image_url || '').trim();
            const currentEndUrl = String(getShotEndFrameUrl(shot) || '').trim();
            const rawEndPrompt = String(shot?.end_frame || '').trim().toUpperCase();
            const treatsEndAsStart = ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(rawEndPrompt) && currentStartUrl;
            return !currentStartUrl || !(currentEndUrl || treatsEndAsStart);
        });

        if (targetShots.length === 0) {
            alert(t('当前所有镜头都已有起始帧和结束帧。', 'All shots already have start and end frames.'));
            return;
        }

        const ok = await confirmUiMessage(
            t(
                `将为 ${targetShots.length} 个镜头批量生成缺失关键帧。系统会按依赖关系分批执行，每批最多 ${SHOT_BATCH_PARALLEL_LIMIT} 个，并对每个 shot 按“先起始帧、后结束帧”的顺序执行。是否继续？`,
                `Generate missing keyframes for ${targetShots.length} shots. The scheduler will respect dependencies, run up to ${SHOT_BATCH_PARALLEL_LIMIT} shots per wave, and process each shot in start-frame then end-frame order. Continue?`
            )
        );
        if (!ok) return;

        const resolvedEntities = await awaitShotGenerationEntities();
        const prevShotIdByShotId = new Map();
        orderedShots.forEach((shot, index) => {
            const stableShotId = String(shot?.id || '').trim();
            const prevShot = index > 0 ? orderedShots[index - 1] : null;
            prevShotIdByShotId.set(stableShotId, String(prevShot?.id || '').trim());
        });

        const endUrlMap = new Map();
        orderedShots.forEach((shot) => {
            const stableShotId = String(shot?.id || '').trim();
            const existingEndUrl = String(getShotEndFrameUrl(shot) || '').trim();
            const normalizedEndPrompt = String(shot?.end_frame || '').trim().toUpperCase();
            const startUrl = String(shot?.image_url || '').trim();
            if (existingEndUrl) {
                endUrlMap.set(stableShotId, existingEndUrl);
            } else if (['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt) && startUrl) {
                endUrlMap.set(stableShotId, startUrl);
            }
        });

        shotLocalBatchStopRequestedRef.current = false;
        const batchSessionId = `shot-keyframe-batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        shotLocalBatchSessionRef.current = batchSessionId;
        if (shotBatchStatusTimerRef.current) {
            clearInterval(shotBatchStatusTimerRef.current);
            shotBatchStatusTimerRef.current = null;
        }
        syncLocalShotBatchRuntime(true, {
            current: 0,
            total: targetShots.length,
            status: t('关键帧批量任务准备中...', 'Preparing keyframe batch...'),
            stopRequested: false,
            currentShotLabel: '',
            currentAssetLabel: t('起始帧 → 结束帧', 'Start Frame -> End Frame'),
            mode: 'keyframes-local',
        });
        onLog?.(t('开始本地关键帧批量任务。', 'Started local keyframe batch.'), 'process');

        let completed = 0;
        let success = 0;
        let failed = 0;
        let queue = [...targetShots];

        const isReady = (shot) => {
            const rawStartPrompt = String(shot?.start_frame || shot?.video_content || '').trim();
            if (!isStartFrameInheritPrompt(rawStartPrompt)) return true;
            const prevShotId = prevShotIdByShotId.get(String(shot?.id || '').trim());
            if (!prevShotId) return true;
            return Boolean(endUrlMap.get(prevShotId));
        };

        try {
            const shouldStopShotBatch = () => (
                shotLocalBatchSessionRef.current !== batchSessionId
                || shotLocalBatchStopRequestedRef.current
                || isPersistentLocalShotBatchStopRequested(selectedSceneIdRef.current)
            );
            const workerLimit = Math.max(1, SHOT_BATCH_PARALLEL_LIMIT);
            const activeTasks = new Map();

            const updateActiveKeyframeStatus = () => {
                if (activeTasks.size === 0) return;
                const activeLabels = Array.from(activeTasks.values())
                    .map(({ shot }) => shot?.shot_id || shot?.shot_name || shot?.id)
                    .filter(Boolean)
                    .join(', ');
                syncLocalShotBatchRuntime(true, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`处理中：${activeLabels}`, `Processing: ${activeLabels}`),
                    stopRequested: Boolean(shotLocalBatchStopRequestedRef.current),
                    currentShotLabel: activeLabels,
                    currentAssetLabel: t('起始帧 → 结束帧', 'Start Frame -> End Frame'),
                    mode: 'keyframes-local',
                });
            };

            const runShotKeyframeTask = async (shot) => generateShotKeyframesBatchItem({
                shotSnapshot: shot,
                resolvedEntities,
                priorEndFrameUrl: endUrlMap.get(prevShotIdByShotId.get(String(shot?.id || '').trim()) || '') || '',
            });

            const startNextShotTask = () => {
                if (shouldStopShotBatch() || activeTasks.size >= workerLimit || queue.length === 0) {
                    return false;
                }

                const nextShot = queue.find(isReady) || (activeTasks.size === 0 ? queue[0] : null);
                if (!nextShot) {
                    return false;
                }

                queue = queue.filter((shot) => String(shot?.id || '').trim() !== String(nextShot?.id || '').trim());
                const shotId = String(nextShot?.id || '');
                const wrappedPromise = runShotKeyframeTask(nextShot)
                    .then((value) => ({ shotId, shot: nextShot, status: 'fulfilled', value }))
                    .catch((reason) => ({ shotId, shot: nextShot, status: 'rejected', reason }));
                activeTasks.set(shotId, { shot: nextShot, promise: wrappedPromise });
                updateActiveKeyframeStatus();
                return true;
            };

            while (queue.length > 0 || activeTasks.size > 0) {
                while (!shouldStopShotBatch() && activeTasks.size < workerLimit && startNextShotTask()) {
                    // Fill all available keyframe concurrency slots immediately.
                }

                if (activeTasks.size === 0) {
                    break;
                }

                const settledTask = await Promise.race(Array.from(activeTasks.values()).map((item) => item.promise));
                activeTasks.delete(settledTask.shotId);

                const shot = settledTask.shot;
                completed += 1;
                if (settledTask.status === 'fulfilled') {
                    success += 1;
                    const nextPatch = settledTask.value?.shotPatch || {};
                    applyShotPatchToLocalState(shot?.id, nextPatch);
                    const stableShotId = String(shot?.id || '').trim();
                    if (settledTask.value?.endUrl) {
                        endUrlMap.set(stableShotId, settledTask.value.endUrl);
                    } else if (settledTask.value?.startUrl && ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(String(shot?.end_frame || '').trim().toUpperCase())) {
                        endUrlMap.set(stableShotId, settledTask.value.startUrl);
                    }
                } else {
                    failed += 1;
                    onLog?.(
                        t(
                            `镜头批量关键帧失败：${shot?.shot_id || shot?.shot_name || shot?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`,
                            `Shot keyframe batch failed: ${shot?.shot_id || shot?.shot_name || shot?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`
                        ),
                        'error'
                    );
                }

                syncLocalShotBatchRuntime(true, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`已完成 ${completed}/${targetShots.length}`, `Completed ${completed}/${targetShots.length}`),
                    stopRequested: Boolean(shotLocalBatchStopRequestedRef.current),
                    currentShotLabel: String(shot?.shot_id || shot?.shot_name || shot?.id || ''),
                    currentAssetLabel: t('起始帧 → 结束帧', 'Start Frame -> End Frame'),
                    mode: 'keyframes-local',
                });
                updateActiveKeyframeStatus();
            }

            if (shotLocalBatchSessionRef.current !== batchSessionId || shotLocalBatchStopRequestedRef.current) {
                onLog?.(t(`关键帧批量任务已停止：成功 ${success}，失败 ${failed}`, `Keyframe batch stopped: ${success} succeeded, ${failed} failed`), 'warning');
                syncLocalShotBatchRuntime(false, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`关键帧批量已停止：成功 ${success}，失败 ${failed}`, `Keyframe batch stopped: ${success} succeeded, ${failed} failed`),
                    stopRequested: true,
                    currentShotLabel: '',
                    currentAssetLabel: t('起始帧 → 结束帧', 'Start Frame -> End Frame'),
                    mode: 'keyframes-local',
                });
                return;
            }

            onLog?.(t(`关键帧批量完成：成功 ${success}，失败 ${failed}`, `Keyframe batch complete: ${success} succeeded, ${failed} failed`), failed > 0 ? 'warning' : 'success');
            syncLocalShotBatchRuntime(false, {
                current: completed,
                total: targetShots.length,
                status: t(`关键帧批量完成：成功 ${success}，失败 ${failed}`, `Keyframe batch complete: ${success} succeeded, ${failed} failed`),
                stopRequested: false,
                currentShotLabel: '',
                currentAssetLabel: t('起始帧 → 结束帧', 'Start Frame -> End Frame'),
                mode: 'keyframes-local',
            });
        } finally {
            shotLocalBatchSessionRef.current = '';
            shotLocalBatchStopRequestedRef.current = false;
            if (shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
            }
            refreshShots();
            refreshShotAssetsMeta();
        }
    }, [SHOT_BATCH_PARALLEL_LIMIT, activeEpisode?.episode_info, applyShotPatchToLocalState, awaitShotGenerationEntities, generateShotKeyframesBatchItem, getShotEndFrameUrl, isPersistentLocalShotBatchStopRequested, isStartFrameInheritPrompt, onLog, refreshShotAssetsMeta, refreshShots, shots, syncLocalShotBatchRuntime, t]);

    const runLocalJointDiptychBatch = useCallback(async () => {
        const orderedShots = (Array.isArray(shots) ? shots : []).filter((shot) => Boolean(shot?.id));
        const targetShots = orderedShots.filter((shot) => {
            const currentStartUrl = String(shot?.image_url || '').trim();
            const currentEndUrl = String(getShotEndFrameUrl(shot) || '').trim();
            const normalizedEndPrompt = String(shot?.end_frame || '').trim().toUpperCase();
            return !currentStartUrl && !currentEndUrl && !['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt);
        });

        if (targetShots.length === 0) {
            alert(t('当前没有适合首尾联生的镜头。仅会处理起始帧和结束帧都缺失、且结束帧不复用起始帧的镜头。', 'No shots are eligible for joint start/end generation. Only shots missing both start and end frames, with a distinct end frame prompt, are included.'));
            return;
        }

        const ok = await confirmUiMessage(
            t(
                `将为 ${targetShots.length} 个镜头批量执行首尾联生。系统会本地并发调度，每批最多 ${SHOT_BATCH_PARALLEL_LIMIT} 个镜头，只处理起始帧和结束帧都缺失、且结束帧不复用起始帧的镜头。是否继续？`,
                `Run joint start/end diptych generation for ${targetShots.length} shots. The local scheduler will run up to ${SHOT_BATCH_PARALLEL_LIMIT} shots per wave and only include shots missing both start and end frames whose end prompt is not configured to reuse the start frame. Continue?`
            )
        );
        if (!ok) return;

        const resolvedEntities = await awaitShotGenerationEntities();

        shotLocalBatchStopRequestedRef.current = false;
        const batchSessionId = `shot-joint-diptych-batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        shotLocalBatchSessionRef.current = batchSessionId;
        if (shotBatchStatusTimerRef.current) {
            clearInterval(shotBatchStatusTimerRef.current);
            shotBatchStatusTimerRef.current = null;
        }
        syncLocalShotBatchRuntime(true, {
            current: 0,
            total: targetShots.length,
            status: t('首尾联生批量任务准备中...', 'Preparing joint diptych batch...'),
            stopRequested: false,
            currentShotLabel: '',
            currentAssetLabel: t('首尾联生', 'Joint Diptych'),
            mode: 'joint-diptych-local',
        });
        onLog?.(t('开始本地首尾联生批量任务。', 'Started local joint diptych batch.'), 'process');

        let completed = 0;
        let success = 0;
        let failed = 0;
        let queue = [...targetShots];

        try {
            const shouldStopShotBatch = () => (
                shotLocalBatchSessionRef.current !== batchSessionId
                || shotLocalBatchStopRequestedRef.current
                || isPersistentLocalShotBatchStopRequested(selectedSceneIdRef.current)
            );
            const workerLimit = Math.max(1, SHOT_BATCH_PARALLEL_LIMIT);
            const activeTasks = new Map();

            const updateActiveJointStatus = () => {
                if (activeTasks.size === 0) return;
                const activeLabels = Array.from(activeTasks.values())
                    .map(({ shot }) => shot?.shot_id || shot?.shot_name || shot?.id)
                    .filter(Boolean)
                    .join(', ');
                syncLocalShotBatchRuntime(true, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`处理中：${activeLabels}`, `Processing: ${activeLabels}`),
                    stopRequested: Boolean(shotLocalBatchStopRequestedRef.current),
                    currentShotLabel: activeLabels,
                    currentAssetLabel: t('首尾联生', 'Joint Diptych'),
                    mode: 'joint-diptych-local',
                });
            };

            const startNextShotTask = () => {
                if (shouldStopShotBatch() || activeTasks.size >= workerLimit || queue.length === 0) {
                    return false;
                }
                const nextShot = queue.shift();
                if (!nextShot) return false;
                const shotId = String(nextShot?.id || '').trim();
                const wrappedPromise = generateShotDiptychBatchItem({
                    shotSnapshot: nextShot,
                    resolvedEntities,
                    silent: true,
                })
                    .then((value) => ({ shotId, shot: nextShot, status: 'fulfilled', value }))
                    .catch((reason) => ({ shotId, shot: nextShot, status: 'rejected', reason }));
                activeTasks.set(shotId, { shot: nextShot, promise: wrappedPromise });
                updateActiveJointStatus();
                return true;
            };

            while (queue.length > 0 || activeTasks.size > 0) {
                while (!shouldStopShotBatch() && activeTasks.size < workerLimit && startNextShotTask()) {
                    // Fill all local joint-diptych concurrency slots immediately.
                }

                if (activeTasks.size === 0) {
                    break;
                }

                const settledTask = await Promise.race(Array.from(activeTasks.values()).map((item) => item.promise));
                activeTasks.delete(settledTask.shotId);

                const shot = settledTask.shot;
                completed += 1;
                if (settledTask.status === 'fulfilled') {
                    success += 1;
                    const nextPatch = settledTask.value?.shotPatch || {};
                    applyShotPatchToLocalState(shot?.id, nextPatch);
                } else {
                    failed += 1;
                    onLog?.(
                        t(
                            `镜头批量首尾联生失败：${shot?.shot_id || shot?.shot_name || shot?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`,
                            `Shot joint diptych batch failed: ${shot?.shot_id || shot?.shot_name || shot?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`
                        ),
                        'error'
                    );
                }

                syncLocalShotBatchRuntime(true, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`已完成 ${completed}/${targetShots.length}`, `Completed ${completed}/${targetShots.length}`),
                    stopRequested: Boolean(shotLocalBatchStopRequestedRef.current),
                    currentShotLabel: String(shot?.shot_id || shot?.shot_name || shot?.id || ''),
                    currentAssetLabel: t('首尾联生', 'Joint Diptych'),
                    mode: 'joint-diptych-local',
                });
                updateActiveJointStatus();
            }

            if (shotLocalBatchSessionRef.current !== batchSessionId || shotLocalBatchStopRequestedRef.current) {
                onLog?.(t(`首尾联生批量任务已停止：成功 ${success}，失败 ${failed}`, `Joint diptych batch stopped: ${success} succeeded, ${failed} failed`), 'warning');
                syncLocalShotBatchRuntime(false, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`首尾联生批量已停止：成功 ${success}，失败 ${failed}`, `Joint diptych batch stopped: ${success} succeeded, ${failed} failed`),
                    stopRequested: true,
                    currentShotLabel: '',
                    currentAssetLabel: t('首尾联生', 'Joint Diptych'),
                    mode: 'joint-diptych-local',
                });
                return;
            }

            onLog?.(t(`首尾联生批量完成：成功 ${success}，失败 ${failed}`, `Joint diptych batch complete: ${success} succeeded, ${failed} failed`), failed > 0 ? 'warning' : 'success');
            syncLocalShotBatchRuntime(false, {
                current: completed,
                total: targetShots.length,
                status: t(`首尾联生批量完成：成功 ${success}，失败 ${failed}`, `Joint diptych batch complete: ${success} succeeded, ${failed} failed`),
                stopRequested: false,
                currentShotLabel: '',
                currentAssetLabel: t('首尾联生', 'Joint Diptych'),
                mode: 'joint-diptych-local',
            });
        } finally {
            shotLocalBatchSessionRef.current = '';
            shotLocalBatchStopRequestedRef.current = false;
            if (shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
            }
            refreshShots();
            refreshShotAssetsMeta();
        }
    }, [SHOT_BATCH_PARALLEL_LIMIT, applyShotPatchToLocalState, awaitShotGenerationEntities, generateShotDiptychBatchItem, getShotEndFrameUrl, isPersistentLocalShotBatchStopRequested, onLog, refreshShotAssetsMeta, refreshShots, shots, syncLocalShotBatchRuntime, t]);

    const pollShotBatchStatus = useCallback(async () => {
        if (!activeEpisode?.id) return null;
        const persistentLocalRuntime = getPersistentLocalShotBatchRuntime(selectedSceneId);
        if ((shotLocalBatchSessionRef.current && isLocalShotBatchMode(batchProgressRef.current?.mode)) || persistentLocalRuntime) {
            const localProgress = shotLocalBatchSessionRef.current && isLocalShotBatchMode(batchProgressRef.current?.mode)
                ? (batchProgressRef.current || createShotBatchProgressState())
                : (persistentLocalRuntime?.progress || createShotBatchProgressState());
            const localMode = String(localProgress?.mode || 'keyframes-local');
            isBatchGeneratingRef.current = true;
            batchProgressRef.current = localProgress;
            setIsBatchGenerating(true);
            setBatchProgress((prev) => {
                const prevSerialized = JSON.stringify(prev || {});
                const nextSerialized = JSON.stringify(localProgress || {});
                return prevSerialized === nextSerialized ? prev : localProgress;
            });
            return {
                running: true,
                total: Number(localProgress?.total || 0),
                completed: Number(localProgress?.current || 0),
                message: String(localProgress?.status || ''),
                stop_requested: Boolean(localProgress?.stopRequested),
                current_shot_label: String(localProgress?.currentShotLabel || ''),
                current_asset_type: localMode === 'joint-diptych-local' ? 'joint_diptych' : 'start_end_sequence',
                current_asset_label: String(localProgress?.currentAssetLabel || ''),
                mode: localMode,
            };
        }
        try {
            const status = await getShotMediaBatchStatus(activeEpisode.id);
            if (!status || typeof status !== 'object') return null;
            const prevProgress = batchProgressRef.current || { current: 0, total: 0, status: '' };

            const nowMs = Date.now();
            const isTransientIdle = !Boolean(status.running) && Number(status.total || 0) <= 0;
            const withinStartupGuard = nowMs < Number(shotBatchStartupGuardUntilRef.current || 0);
            if (isTransientIdle && withinStartupGuard) {
                status.running = true;
                status.total = Number(prevProgress.total || 0);
                status.completed = Number(prevProgress.current || 0);
                status.message = status.message || prevProgress.status || t('批量任务启动中...', 'Batch task is starting...');
            }

            const rawAssetType = String(status.current_asset_type || '').trim().toLowerCase();
            const currentAssetLabel = String(status.current_asset_label || '').trim() || (
                rawAssetType === 'start_frame'
                    ? t('起始帧', 'Start Frame')
                    : rawAssetType === 'end_frame'
                        ? t('结束帧', 'End Frame')
                        : rawAssetType === 'video'
                            ? t('视频', 'Video')
                            : ''
            );

            const running = Boolean(status.running);
            setIsBatchGenerating(running);
            setBatchProgress({
                current: Number(status.completed || 0),
                total: Number(status.total || 0),
                status: String(status.message || ''),
                stopRequested: Boolean(status.stop_requested),
                currentShotLabel: String(status.current_shot_label || ''),
                currentAssetLabel,
                mode: String(status.mode || 'videos-backend'),
            });

            if (!running && shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
                refreshShots();
            }

            return status;
        } catch (e) {
            return null;
        }
    }, [activeEpisode?.id, createShotBatchProgressState, getPersistentLocalShotBatchRuntime, isLocalShotBatchMode, refreshShots, selectedSceneId, t]);

    useEffect(() => {
        if (!activeEpisode?.id) {
            if (shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
            }
            return;
        }
        let cancelled = false;

        const hydrate = async () => {
            let recovered = false;
            if (!isBatchGeneratingRef.current && !isLocalShotBatchMode(batchProgressRef.current?.mode)) {
                recovered = await recoverShotBatchFromJobPool();
            }
            const status = await pollShotBatchStatus();
            if (cancelled) return;

            const shouldKeepPolling = Boolean(status?.running)
                || Boolean(isBatchGeneratingRef.current)
                || Boolean(recovered);

            if (shouldKeepPolling && !shotBatchStatusTimerRef.current) {
                shotBatchStatusTimerRef.current = setInterval(pollShotBatchStatus, 3000);
            }

            if (!shouldKeepPolling && shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
            }
        };

        hydrate();
        return () => {
            cancelled = true;
            if (shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
            }
        };
    }, [activeEpisode?.id, isLocalShotBatchMode, selectedSceneId, pollShotBatchStatus, recoverShotBatchFromJobPool]);

    const handleStopShotBatch = async () => {
        if (!activeEpisode?.id) return;
        setIsStoppingShotBatch(true);
        try {
            if (isLocalShotBatchMode(batchProgressRef.current?.mode)) {
                const localMode = String(batchProgressRef.current?.mode || 'keyframes-local');
                const stopMessage = localMode === 'joint-diptych-local'
                    ? t('已请求停止当前首尾联生批量任务。', 'Stop requested for current joint diptych batch.')
                    : t('已请求停止当前关键帧批量任务。', 'Stop requested for current keyframe batch.');
                shotLocalBatchStopRequestedRef.current = true;
                const nextProgress = {
                    ...(batchProgressRef.current || createShotBatchProgressState()),
                    stopRequested: true,
                    status: stopMessage,
                    mode: localMode,
                };
                syncLocalShotBatchRuntime(false, nextProgress);
                const stoppedJobCount = await forceStopLocalShotBatchJobs({
                    sceneIdOverride: selectedSceneId,
                    mode: localMode,
                    reason: stopMessage,
                });
                onLog?.(
                    stoppedJobCount > 0
                        ? t(`已停止本地批量，并强制结束 ${stoppedJobCount} 个图片任务。`, `Stopped local batch and force-stopped ${stoppedJobCount} image jobs.`)
                        : t('已停止本地批量，并清除运行中的界面状态。', 'Stopped local batch and cleared running UI state.'),
                    'warning'
                );
                return;
            }

            const res = await stopShotMediaBatch(activeEpisode.id);
            setBatchProgress((prev) => ({
                ...prev,
                stopRequested: true,
                status: res?.message || prev.status || t('已强制停止当前镜头批处理。', 'Current shot batch force-stopped.'),
                currentAssetLabel: prev.currentAssetLabel || '',
                mode: 'videos-backend',
            }));
            await pollShotBatchStatus();
            onLog?.(`Shot batch: ${res?.message || 'stop requested'}`, 'warning');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'stop failed';
            onLog?.(`Stop batch failed: ${detail}`, 'error');
            alert(`Stop batch failed: ${detail}`);
        } finally {
            setIsStoppingShotBatch(false);
        }
    };

    const startShotBatchByMode = async (mode) => {
        if (isShotBatchStarting || isBatchGeneratingRef.current) return;
        if (!activeEpisode?.id) {
            const msg = t('请先选择分集。', 'Please select an episode first.');
            onLog?.(msg, 'warning');
            alert(msg);
            return;
        }

        if (!Array.isArray(shots) || shots.length === 0) {
            const msg = t('当前没有可批量处理的镜头。请先在 Scenes 中生成并应用镜头，或选择包含镜头的场景。', 'No shots available for batch processing. Generate/apply shots from Scenes first, or select a scene that has shots.');
            onLog?.(msg, 'warning');
            alert(msg);
            return;
        }

        const latest = mode === 'videos' ? await pollShotBatchStatus() : null;
        if (latest?.running) {
            alert('A batch task is already running. Please stop it first.');
            return;
        }

        const targetShots = mode === 'videos' ? getBatchVideoEligibleShots(shots) : shots;
        if (mode === 'videos' && targetShots.length === 0) {
            const msg = t('当前没有可批量生成视频的镜头。需要至少已有一张首尾帧，且当前没有视频。', 'No eligible shots for batch video generation. Each shot must already have at least one start/end frame and must not already have a video.');
            onLog?.(msg, 'warning');
            alert(msg);
            return;
        }

        const ok = mode === 'videos'
            ? await confirmUiMessage(t(
                `将为 ${targetShots.length} 个镜头批量生成视频。只会提交至少已有一张首尾帧、且当前没有视频的镜头；后端会按你的账号等级并发执行。是否继续？`,
                `Generate videos for ${targetShots.length} shots. Only shots that already have at least one start/end frame and do not already have a video will be submitted; the backend will run them concurrently based on your user level. Continue?`
            ))
            : true;
        if (!ok) return;

        setIsShotBatchStarting(true);
        try {
            const targetShotIds = targetShots.map((shot) => shot.id).filter(Boolean);
            if (targetShotIds.length === 0) {
                const msg = mode === 'videos'
                    ? t('当前没有可批量生成视频的镜头。需要至少已有一张首尾帧，且当前没有视频。', 'No eligible shots for batch video generation. Each shot must already have at least one start/end frame and must not already have a video.')
                    : t('当前镜头尚未保存到数据库，无法批量执行。请先保存镜头。', 'Current shots are not saved to database yet, cannot run batch. Please save shots first.');
                onLog?.(msg, 'warning');
                alert(msg);
                return;
            }

            if (mode === 'keyframes') {
                await runLocalKeyframeBatch();
                return;
            }
            if (mode === 'joint_diptych') {
                await runLocalJointDiptychBatch();
                return;
            }

            const started = await startShotMediaBatch(activeEpisode.id, {
                mode,
                shot_ids: targetShotIds,
                overwrite_existing: false,
                system_api_id: mode === 'videos' ? (Number(localStorage.getItem('func_api_generate_videos')) || undefined) : undefined,
            });
            shotBatchStartupGuardUntilRef.current = Date.now() + 12000;
            shotBatchBootstrapUntilRef.current = Date.now() + 15000;

            setIsBatchGenerating(true);
            setBatchProgress({
                current: 0,
                total: Number(started?.total || targetShotIds.length),
                status: mode === 'videos' ? 'Video batch started...' : 'Keyframe batch started...',
                stopRequested: false,
                currentShotLabel: '',
                currentAssetLabel: '',
                mode: 'videos-backend',
            });
            onLog?.(
                mode === 'videos'
                    ? 'Background batch video generation started.'
                    : 'Background batch keyframe generation started.',
                'process'
            );

            if (shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
            }
            shotBatchStatusTimerRef.current = setInterval(pollShotBatchStatus, 3000);
            await pollShotBatchStatus();
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'batch start failed';
            onLog?.(`Batch start failed: ${detail}`, 'error');
            alert(`Batch start failed: ${detail}`);
        } finally {
            setIsShotBatchStarting(false);
        }
    };

    const handleBatchGenerate = async () => {
        await startShotBatchByMode('keyframes');
    };

    const handleBatchGenerateJointDiptych = async () => {
        await startShotBatchByMode('joint_diptych');
    };

    const handleBatchGenerateVideo = async () => {
        await startShotBatchByMode('videos');
    };

    const sceneCodeById = useMemo(() => {
        const map = {};
        (scenes || []).forEach((scene) => {
            map[String(scene?.id)] = String(scene?.scene_no || scene?.scene_id || scene?.id || '').trim();
        });
        return map;
    }, [scenes]);

    const getShotUpdatedAtMs = useCallback((shot) => {
        const candidate = shot?.updated_at || shot?.updatedAt || shot?.modified_at || shot?.modifiedAt || shot?.created_at || shot?.createdAt;
        if (!candidate) return 0;
        const parsed = Date.parse(candidate);
        return Number.isFinite(parsed) ? parsed : 0;
    }, []);

    const getShotHierarchyKey = useCallback((shot) => {
        const episodePart = String(activeEpisode?.episode_number || parseEpisodeNumberFromText(activeEpisode?.title) || activeEpisode?.id || '').trim();
        const scenePart = String(sceneCodeById[String(shot?.scene_id)] || shot?.scene_code || shot?.scene_id || '').trim();
        const shotPart = String(shot?.shot_id || shot?.shot_number || shot?.id || '').trim();
        return `${episodePart}_${scenePart}_${shotPart}`;
    }, [activeEpisode?.episode_number, activeEpisode?.title, activeEpisode?.id, sceneCodeById]);

    const sortedShots = useMemo(() => {
        return [...(shots || [])];
    }, [shots]);

    const selectedShotIdSet = useMemo(
        () => new Set((selectedShotIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)),
        [selectedShotIds]
    );

    useEffect(() => {
        const visibleIdSet = new Set((shots || []).map((s) => Number(s?.id || 0)).filter((id) => Number.isFinite(id) && id > 0));
        setSelectedShotIds((prev) => (prev || []).filter((id) => visibleIdSet.has(Number(id))));
    }, [shots]);

    const toggleShotSelection = useCallback((shotId, checked) => {
        const id = Number(shotId || 0);
        if (!Number.isFinite(id) || id <= 0) return;
        setSelectedShotIds((prev) => {
            const set = new Set((prev || []).map((x) => Number(x)).filter((x) => Number.isFinite(x) && x > 0));
            if (checked) set.add(id);
            else set.delete(id);
            return Array.from(set);
        });
    }, []);

    const toggleSelectAllVisibleShots = useCallback((checked) => {
        if (!checked) {
            setSelectedShotIds([]);
            return;
        }
        const ids = (sortedShots || []).map((s) => Number(s?.id || 0)).filter((id) => Number.isFinite(id) && id > 0);
        setSelectedShotIds(Array.from(new Set(ids)));
    }, [sortedShots]);

    const isShotBatchCompleted = !Boolean(isBatchGenerating)
        && Number(batchProgress?.total || 0) > 0
        && Number(batchProgress?.current || 0) >= Number(batchProgress?.total || 0);
    const shouldShowShotBatchProgress = (isBatchGenerating || Number(batchProgress?.total || 0) > 0)
        && (!isShotBatchProgressDismissed || !isShotBatchCompleted);
    const shotBatchProgressPercent = (() => {
        const total = Number(batchProgress?.total || 0);
        const current = Number(batchProgress?.current || 0);
        if (total <= 0) return 0;
        return Math.max(0, Math.min(100, Math.round((current / total) * 100)));
    })();
    const shotBatchProgressSummary = (() => {
        const total = Number(batchProgress?.total || 0);
        if (total <= 0) return '';
        const current = Number(batchProgress?.current || 0);
        const shotSuffix = batchProgress?.currentShotLabel
            ? t(`（镜头 ${batchProgress.currentShotLabel}）`, ` (Shot ${batchProgress.currentShotLabel})`)
            : '';
        const assetSuffix = batchProgress?.currentAssetLabel
            ? t(`（资源 ${batchProgress.currentAssetLabel}）`, ` (Asset ${batchProgress.currentAssetLabel})`)
            : '';
        if (isBatchGenerating) {
            if (batchProgress?.stopRequested) {
                return t(
                    `共 ${total} 个，已请求停止，等待并发任务退出（当前 ${current}/${total}）${shotSuffix}${assetSuffix}`,
                    `Total ${total}, stop requested, waiting for concurrent tasks to exit (current ${current}/${total})${shotSuffix}${assetSuffix}`
                );
            }
            return t(
                `共 ${total} 个，进行到 ${current}/${total}（${shotBatchProgressPercent}%）${shotSuffix}${assetSuffix}`,
                `Total ${total}, processing ${current}/${total} (${shotBatchProgressPercent}%)${shotSuffix}${assetSuffix}`
            );
        }
        return t(
            `共 ${total} 个，已完成 ${current}/${total}${shotSuffix}${assetSuffix}`,
            `Total ${total}, completed ${current}/${total}${shotSuffix}${assetSuffix}`
        );
    })();

    useEffect(() => {
        setIsShotBatchProgressDismissed(false);
    }, [activeEpisode?.id]);

    return (
        <div className="flex flex-col h-full w-full p-6 overflow-hidden">
             {/* Header / Toolbar */}
             <div className="flex justify-between items-center mb-6 shrink-0">
                <div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        {t('镜头管理', 'Shot Manager')}
                        <span className="text-sm font-normal text-muted-foreground ml-2">({shots.length})</span>
                        {hasActiveGeneration && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center gap-1">
                                <Loader2 className="w-3 h-3 animate-spin" />
                                {Object.values(generatingStateByShot || {}).some((s) => s?.cropping) ? t('处理图片中', 'Processing Image') : t('生成中', 'Generating')}
                            </span>
                        )}
                    </h2>
                    <div className="relative">
                         <select 
                            className="bg-black/40 border border-white/20 rounded px-3 py-1.5 text-sm min-w-[200px] text-white"
                            value={selectedSceneId || ''}
                            onChange={(e) => setSelectedSceneId(e.target.value)}
                         >
                            <option value="">{t('选择场景...', 'Select a Scene...')}</option>
                            <option value="all">{t('全部场景', 'All Scenes')}</option>
                        {scenes.map(s => (
                                <option key={s.id} value={s.id}>{s.scene_no} - {s.scene_name || t('未命名', 'Untitled')}</option>
                            ))}
                         </select>
                        <button 
                            onClick={handleDeleteAllShots}
                            className="ml-2 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded text-xs border border-red-500/20"
                            title={t('删除当前显示的全部镜头', 'Delete All Displayed Shots')}
                        >
                            <Trash2 className="w-3 h-3"/>
                        </button>
                        <button
                            onClick={() => toggleSelectAllVisibleShots(true)}
                            className="ml-2 px-2.5 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded text-xs border border-white/20"
                            title={t('全选当前显示镜头', 'Select all visible shots')}
                        >
                            {t('全选', 'Select All')}
                        </button>
                        <button
                            onClick={() => toggleSelectAllVisibleShots(false)}
                            className="ml-1 px-2.5 py-1.5 bg-white/5 hover:bg-white/10 text-white/80 rounded text-xs border border-white/10"
                            title={t('清空已选镜头', 'Clear selected shots')}
                        >
                            {t('清空', 'Clear')}
                        </button>
                        <button
                            onClick={handleDeleteSelectedShots}
                            disabled={(selectedShotIds || []).length === 0}
                            className="ml-1 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded text-xs border border-red-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                            title={t('删除已选镜头', 'Delete selected shots')}
                        >
                            {t('删除选中', 'Delete Selected')} ({(selectedShotIds || []).length})
                        </button>
                        <div className="relative inline-flex items-center ml-2 border border-white/20 rounded overflow-hidden">
                             <button
                                onClick={handleManualRebindMediaSlots}
                                disabled={isManualRebindingMedia || isBatchGenerating || isStoppingShotBatch}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 ${isManualRebindingMedia ? 'bg-white/20 text-white/80 cursor-wait' : 'bg-white/10 text-white hover:bg-white/20'}`}
                                title={t('手动回填历史媒体关联（只补空槽位）', 'Manual historical media rebind (fills empty slots only)')}
                            >
                                {isManualRebindingMedia ? <Loader2 className="w-3 h-3 animate-spin"/> : <RefreshCw className="w-3 h-3"/>}
                                <span>{t('回填', 'Rebind')}</span>
                            </button>
                             <button 
                                onClick={handleBatchGenerate}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 ${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title={t('批量生成缺失的起始/结束帧', 'Batch Generate Missing Start/End Frames')}
                            >
                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('补帧', 'Frames')}</span>
                            </button>
                            <button 
                                onClick={handleBatchGenerateJointDiptych}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 ${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title={t('按镜头批量执行首尾联生', 'Batch Generate Joint Start/End Diptychs')}
                            >
                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <PanelsTopLeft className="w-3 h-3"/>}
                                <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('首尾联生', 'Joint')}</span>
                            </button>
                            <button 
                                onClick={handleBatchGenerateVideo}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 ${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title={t('批量生成视频（仅处理已有首尾帧且当前无视频的镜头）', 'Batch Generate Videos (only shots with existing start/end frames and no current video)')}
                            >
                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>}
                                <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('视频', 'Video')}</span>
                            </button>
                            {isBatchGenerating && (
                                <button
                                    onClick={handleStopShotBatch}
                                    disabled={isStoppingShotBatch || batchProgress.stopRequested}
                                    className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all ${isStoppingShotBatch ? 'bg-amber-500/20 text-amber-200 cursor-wait' : 'bg-amber-500/10 text-amber-300 hover:bg-amber-500/20'}`}
                                    title={t('停止当前批处理任务', 'Stop current batch task')}
                                >
                                    {isStoppingShotBatch ? <Loader2 className="w-3 h-3 animate-spin"/> : <X className="w-3 h-3"/>}
                                    <span>
                                        {isStoppingShotBatch
                                            ? t('停止中...', 'Stopping...')
                                            : (batchProgress.stopRequested ? t('等待退出', 'Waiting to Stop') : t('停止', 'Stop'))}
                                    </span>
                                </button>
                            )}
                        </div>

                    </div>

                </div>
                
                <div className="flex items-center gap-2">
                     {/* Settings Button Moved to Edit Shot View */}
                </div>
            </div>

            {shouldShowShotBatchProgress && (
                <div className={`sticky top-0 z-20 mb-4 rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm shrink-0 backdrop-blur-sm ${
                    isBatchGenerating
                        ? 'border-blue-500/30 bg-blue-500/10 text-blue-100'
                        : batchProgress.stopRequested
                            ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-100'
                            : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                }`}>
                    {isBatchGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    <div className="flex items-center justify-between w-full gap-3">
                        <span>
                            {batchProgress.status || t('批量任务状态已更新。', 'Batch task status updated.')}
                            {batchProgress.stopRequested ? ` · ${t('停止请求中，等待退出', 'Stop requested, waiting for exit')}` : ''}
                            {shotBatchProgressSummary ? ` · ${shotBatchProgressSummary}` : ''}
                        </span>
                        {isShotBatchCompleted && (
                            <button
                                onClick={() => setIsShotBatchProgressDismissed(true)}
                                className="inline-flex items-center justify-center rounded p-1 text-current/80 hover:text-current hover:bg-white/10"
                                title={t('关闭进度条幅', 'Dismiss progress banner')}
                                aria-label={t('关闭进度条幅', 'Dismiss progress banner')}
                            >
                                <X className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Sub-header Actions */}
            <div className="px-4 pb-2 flex justify-end" />
             
             {/* Main Content */}
             <div className="flex-1 overflow-auto custom-scrollbar">
                 {selectedSceneId ? (
                     <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6 pb-20">
                        {isShotsLoading && !hasShotInitialLoadCompleted && sortedShots.length === 0 && (
                            <div className="col-span-full h-64 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-primary/20 rounded-xl bg-primary/5">
                                <Loader2 className="w-12 h-12 mb-4 animate-spin text-primary" />
                                <p>{t('镜头预装入中...', 'Preloading shots...')}</p>
                            </div>
                        )}
                        {sortedShots.map((shot, idx) => {
                            const shotState = generatingStateByShot[String(shot.id)] || { start: false, end: false, video: false };
                            const isGeneratingThisShot = !!(shotState.start || shotState.end || shotState.video);
const isCroppingThisShot = !!(shotState.cropping);
                            const shotCardPromptPreview = getShotCardPromptPreview(shot);
                            return (
                            <div 
                                key={shot.id} 
                                className="bg-card/80 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden group hover:border-primary/50 transition-all cursor-pointer relative"
                                onClick={() => setEditingShot(shot)}
                            >
                                {/* Image / Thumbnail */}
                                <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "" : "aspect-video"} bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden`}>
                                    
                                    {/* Preload End Frame so it's cached exactly like the Start Frame when user opens the shot inspector */}
                                    {getShotEndFrameUrl(shot) && (
                                        <div className="absolute inset-0 opacity-0 pointer-events-none -z-10">
                                            <SafeImage src={getShotEndFrameUrl(shot)} loading="lazy" />
                                        </div>
                                    )}

                                    {shot.video_url ? (
                                        <LazyHoverVideo
                                            key={shot.video_url}
                                            src={shot.video_url}
                                            poster={resolveShotVideoPosterUrl(shot)}
                                            className="w-full h-full flex items-center justify-center"
                                            mediaClassName="w-full h-full object-contain object-center"
                                            muted
                                            loop
                                            playsInline
                                            playOnHover
                                            resetOnLeave
                                        />
                                    ) : shot.image_url ? (
                                        <SafeImage src={shot.image_url} alt={shot.shot_name} className="w-full h-full object-contain object-center" fallback={<div className="flex flex-col items-center gap-2 opacity-50"><ImageIcon className="w-8 h-8" /><span className="text-xs">{t('无图片', 'No Image')}</span></div>} />
                                    ) : (
                                        <div className="flex flex-col items-center gap-2 opacity-50">
                                            <ImageIcon className="w-8 h-8" />
                                            <span className="text-xs">{t('无图片', 'No Image')}</span>
                                        </div>
                                    )}
                                    <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 pointer-events-none">
                                        {shot.shot_id}
                                    </div>
                                    <label
                                        className="absolute top-2 right-2 z-20 flex items-center justify-center w-5 h-5 rounded bg-black/60 border border-white/30 shadow"
                                        onClick={(e) => e.stopPropagation()}
                                        title={t('选择镜头', 'Select shot')}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={selectedShotIdSet.has(Number(shot.id))}
                                            onChange={(e) => toggleShotSelection(shot.id, e.target.checked)}
                                            className="accent-primary"
                                        />
                                    </label>
                                    {shot.video_url && (
                                        <div className="absolute top-2 right-9 bg-black/60 p-1.5 rounded-full text-white border border-white/10 pointer-events-none">
                                            <Video className="w-3 h-3" />
                                        </div>
                                    )}
                                    <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold pointer-events-none">
                                        {shot.duration || '0s'}
                                    </div>
                                    {(isGeneratingThisShot || isCroppingThisShot) && (
                                        <div className="absolute bottom-2 left-2 bg-primary/20 text-primary border border-primary/30 px-2 py-0.5 rounded text-[10px] font-bold pointer-events-none flex items-center gap-1">
                                            <Loader2 className="w-3 h-3 animate-spin" />
                                            {isCroppingThisShot ? t('处理图片中', 'Processing Image') : t('生成中', 'Generating')}
                                        </div>
                                    )}
                                </div>
                                
                                {/* Info - Simplified */}
                                <div className="p-3">
                                    <div className="flex justify-between items-center">
                                        <h3 className="font-bold text-sm text-white line-clamp-2" title={shot.shot_name}>
                                            <span className="text-primary mr-2 font-mono">{shot.shot_id}</span>
                                            {shot.shot_name || t('未命名', 'Untitled')}
                                        </h3>
                                        {/* Optional: Show duration if available, keep it minimal */}
                                        {shot.duration && (
                                            <span className="text-[10px] text-muted-foreground bg-white/5 px-1.5 py-0.5 rounded ml-2 whitespace-nowrap">
                                                {shot.duration}
                                            </span>
                                        )}
                                    </div>
                                    
                                    {/* Display prompt preview with language-aware fallback */}
                                    {shotCardPromptPreview && (
                                        <div className="mt-2 text-xs text-muted-foreground bg-white/5 p-2 rounded line-clamp-3 overflow-hidden text-ellipsis">
                                            {shotCardPromptPreview}
                                        </div>
                                    )}
                                </div>
                            </div>
                            );
                        })}
                        {sortedShots.length === 0 && !isShotsLoading && hasShotInitialLoadCompleted && (
                            <div className="col-span-full h-64 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-white/10 rounded-xl">
                                <Film className="w-12 h-12 mb-4 opacity-20" />
                                <p>{t('该场景暂无镜头。', 'No shots in this scene.')}</p>
                                <button className="text-primary text-sm hover:underline mt-2" onClick={() => setIsImportOpen(true)}>{t('导入镜头表', 'Import Shots Table')}</button>
                            </div>
                        )}
                     </div>
                 ) : (
                     <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                         <Clapperboard className="w-16 h-16 mb-4 opacity-20" />
                         <p className="text-lg font-medium">{t('选择一个场景来管理镜头', 'Select a Scene to manage shots')}</p>
                         <p className="text-sm opacity-50 max-w-md text-center mt-2">
                            Available scenes are loaded from the database. <br/>
                            If your list is empty, make sure you have created scenes in the "Scenes" tab.
                         </p>
                     </div>
                 )}
             </div>

             {/* Import Modal */}
             <ImportModal 
                isOpen={isImportOpen} 
                onClose={() => setIsImportOpen(false)} 
                onImport={handleImport}
                     defaultType="shot"
                     uiLang={uiLang}
             />

             {/* Media Modals */}
             {viewMedia && <MediaDetailModal media={viewMedia} onClose={() => setViewMedia(null)} />}
             <MediaPickerModal 
                isOpen={pickerConfig.isOpen} 
                onClose={() => setPickerConfig({ ...pickerConfig, isOpen: false })} 
                onSelect={handleMediaSelect} 
                projectId={projectId}
                context={pickerConfig.context}
                entities={entities}
                episodeId={activeEpisode?.id}
                uiLang={uiLang}
            />

             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (
                    <motion.div 
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        className="absolute top-0 right-0 w-full h-full bg-[#09090b] border-l border-white/10 z-50 overflow-y-auto shadow-2xl flex flex-col"
                    >
                        {/* Notification Toast for Edit Shot */}
                        {notification && (
                            <div className={`fixed top-4 left-1/2 transform -translate-x-1/2 z-[200] px-6 py-3 rounded-lg shadow-2xl border font-bold flex items-center gap-2 animate-in slide-in-from-top-4 fade-in duration-300 ${
                                notification.type === 'success' ? 'bg-green-500/90 text-white border-green-400' : 'bg-red-500/90 text-white border-red-400'
                            }`}>
                                {notification.type === 'success' ? <CheckCircle size={18} /> : <Info size={18} />}
                                {notification.message}
                            </div>
                        )}

                        <div className="p-3 sm:p-4 border-b border-white/10 flex flex-wrap items-center justify-between gap-2 sticky top-0 bg-[#09090b] z-10">
                            <h3 className="font-bold text-lg flex items-center gap-2">
                                {t('编辑镜头', 'Edit Shot')} {editingShot.shot_id}
                                {editingShot.shot_name && <span className="text-base font-normal text-muted-foreground">- {editingShot.shot_name}</span>}
                            </h3>
                            <div className="flex items-center gap-2">
                                <FunctionApiSelector functionName="generate_shot_images" configs={functionApiConfigs} label={t('图片模型', 'Image Model')} />
                                <FunctionApiSelector functionName="generate_videos" configs={functionApiConfigs} label={t('视频模型', 'Video Model')} />
                                <button
                                    onClick={() => {
                                        const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
                                        window.location.assign(`/settings?tab=default-api-activation&return_to=${returnTo}`);
                                    }}
                                    className="p-2 hover:bg-white/10 text-white rounded-lg border border-white/10 transition-colors"
                                    title={t('打开生成设置', 'Open Generation Settings')}
                                >
                                    <SettingsIcon className="w-5 h-5" />
                                </button>
                                <button onClick={() => setEditingShot(null)} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                            </div>
                        </div>
                        <div className="p-4 sm:p-6 space-y-6">

                            <div>
                                <label className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">{t('镜头逻辑（中文）', 'Shot Logic (CN)')}</label>
                                <PromptMentionTextarea entities={entities} uiLang={uiLang} 
                                    className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs text-white/80 h-20 focus:outline-none focus:border-primary/50"
                                    value={editingShot.shot_logic_cn || ''}
                                    onChange={(e) => setEditingShot({...editingShot, shot_logic_cn: e.target.value})}
                                    placeholder={t('镜头逻辑描述（中文）...', 'Shot logic description (Chinese)...')}
                                />
                            </div>
                            
                            {/* 1. Workflow / Media Assets */}
                            <div className="space-y-6">
                                
                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                                    {/* Start Frame */}
                                    <div className={isPortrait ? 'flex items-stretch gap-2.5 h-full max-h-[650px] 2xl:max-h-[720px] overflow-hidden' : 'space-y-2'}>
                                        <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full overflow-hidden pr-1 justify-center' : ''}`}>
                                            <div className="flex min-h-[52px] items-start justify-between gap-2">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('起始帧', 'Start Frame')}
                                            </div>
                                            <div className="flex flex-wrap items-center justify-end gap-1">
                                                <button
                                                    onClick={() => openAssetDetailModal('start')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={async () => {
                                                        if (isShotFrameActionLocked('start')) {
                                                            notifyShotFrameActionLocked('start');
                                                            return;
                                                        }
                                                        openMediaPicker(async (url) => {
                                                            const newData = { image_url: url };
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            // Auto-save user selection to ensure it counts as "latest selected"
                                                            await onUpdateShot(editingShot.id, newData);
                                                            onLog?.('Start Frame Image set', 'success');
                                                        }, { shotId: editingShot.id, shotFrameType: 'start' });
                                                    }}
                                                    disabled={isShotFrameActionLocked('start')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                                                    title={isShotFrameActionLocked('start') ? t('起始帧任务运行中，不能更换图片', 'Start frame job is running; image changes are disabled') : t('设置起始帧图片', 'Set start frame image')}
                                                >
                                                    <ImageIcon className="w-3 h-3"/> {t('设置', 'Set')}
                                                </button>
                                                {currentGeneratingState.start && (
                                                    <button 
                                                        onClick={() => handleForceStopShotImage('start')}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title={t('停止重试循环', 'Stop Retry Loop')}
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        {t('停止', 'Stop')}
                                                    </button>
                                                )}
                                                <button 
                                                    onClick={() => generateAssetWithLang('start')} 
                                                    disabled={currentShotGenerating}
                                                    className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 ${currentShotGenerating ? 'bg-sky-500/10 text-sky-300/50 cursor-wait' : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500/30'}`}
                                                >
                                                    {currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                    {currentShotGenerating ? t('生成中...', 'Generating...') : t('生成', 'Generate')}
                                                </button>
                                                <button
                                                    onClick={() => handleGenerateShotDiptychFrames(shotImageCfgValue)}
                                                    disabled={currentShotGenerating}
                                                    className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 ${currentShotGenerating ? 'bg-violet-500/10 text-violet-200/40 cursor-wait' : 'bg-violet-500/20 text-violet-200 hover:bg-violet-500/30'}`}
                                                    title={t('把起始帧与结束帧提示词拼成两宫格生图后自动拆分回填', 'Generate a two-panel composite from the start/end prompts, then split and apply both frames automatically')}
                                                >
                                                    {currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Layers className="w-3 h-3"/>}
                                                    {currentShotGenerating ? t('联生中...', 'Joint...') : t('首尾联生', 'Joint')}
                                                </button>
                                            </div>
                                        </div>
                                        {currentGeneratingState.start && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">
                                                <div className="flex items-center gap-2 font-bold uppercase tracking-[0.12em] text-amber-100">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    {t('起始帧生成中', 'Start Frame In Progress')}
                                                </div>
                                                <div className="mt-1 text-amber-50/75">
                                                    {t('当前预览会在生成完成后自动刷新，替换与删除入口已锁定。', 'This preview will refresh automatically when generation completes. Replace and delete actions are locked.')}
                                                </div>
                                            </div>
                                        )}
                                        <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "h-[420px] 2xl:h-[480px] w-auto mx-auto shrink-0" : "aspect-video w-full"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('start')}>
                                            {currentGeneratingState.start && (
                                                <div className="absolute inset-0 bg-black/68 z-10 flex items-center justify-center flex-col gap-3">
                                                    <div className="rounded-full border border-amber-300/30 bg-amber-500/10 p-3">
                                                        <Loader2 className="w-7 h-7 animate-spin text-amber-200"/>
                                                    </div>
                                                    <div className="px-6 text-center">
                                                        <div className="text-sm font-bold uppercase tracking-[0.16em] text-amber-100">{t('正在生成起始帧', 'Generating Start Frame')}</div>
                                                        <div className="mt-1 text-[11px] text-white/75">{t('生成完成后会自动更新这里的画面', 'The preview here will update automatically when generation completes')}</div>
                                                    </div>
                                                </div>
                                            )}
                                            {editingShot.image_url ? (
                                                <>
                                                    <SafeImage
                                                        src={editingShot.image_url}
                                                        className="max-w-full max-h-full object-contain cursor-pointer hover:opacity-90 transition-opacity" 
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            openAssetDetailModal('start');
                                                        }}
                                                        alt={t('起始帧', 'Start Frame')}
                                                    />
                                                    <button 
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
                                                            if (isShotFrameActionLocked('start')) {
                                                                notifyShotFrameActionLocked('start');
                                                                return;
                                                            }
                                                            if(!await confirmUiMessage("Delete Start Frame image?")) return;
                                                            const newData = { image_url: "" };
                                                            await onUpdateShot(editingShot.id, newData);
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            onLog?.('Start Frame Image removed', 'info');
                                                        }}
                                                        disabled={isShotFrameActionLocked('start')}
                                                        className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20 disabled:opacity-40 disabled:cursor-not-allowed"
                                                        title={isShotFrameActionLocked('start') ? t('起始帧任务运行中，不能删除图片', 'Start frame job is running; image removal is disabled') : t('删除起始帧', 'Delete Start Frame')}
                                                    >
                                                        <Trash2 className="w-3 h-3"/>
                                                    </button>
                                                </>
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>
                                            )}
                                        </div>
                                        <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[72px] shrink-0"
                                            placeholder={shotPromptDisplayLang === 'cn' ? t('起始帧提示词（中文）...', 'Start Frame Prompt (CN)...') : t('起始帧提示词...', 'Start Frame Prompt...')}
                                            value={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.start_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.start_frame || '')}
                                            onChange={(e) => {
                                                const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                tech.manual_start_frame = true;
                                                if (shotPromptDisplayLang === 'cn') {
                                                    tech.start_frame_cn = e.target.value;
                                                    setEditingShot({...editingShot, technical_notes: JSON.stringify(tech)});
                                                } else {
                                                    setEditingShot({...editingShot, start_frame: e.target.value, technical_notes: JSON.stringify(tech)});
                                                }
                                            }}
                                        />
                                        </div>
                                        <div className={isPortrait ? "w-[74px] lg:w-[86px] shrink-0 pt-0 flex flex-col h-full overflow-hidden" : "w-full"}>
                                            <ReferenceManager isPortrait={isPortrait} 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图', 'Refs')}
                                            promptText={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.start_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.start_frame || '')}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="ref_image_urls"
                                            strictPromptOnly={true}
                                            onFindPrevFrame={() => {
                                                // Logic to find PREVIOUS shot end frame
                                                const idx = shots.findIndex(s => s.id === editingShot.id);
                                                if (idx > 0) {
                                                    try {
                                                        const prev = shots[idx-1];
                                                        const t = JSON.parse(prev.technical_notes || '{}');
                                                        const url = t.end_frame_url || prev.video_url || prev.image_url;
                                                        if (url) {
                                                            onLog?.("Found previous shot frame: " + prev.shot_id, "success");
                                                            return url;
                                                        } else {
                                                            onLog?.("Previous shot has no media.", "warning");
                                                            return null;
                                                        }
                                                    } catch(e) { return null; }
                                                } else {
                                                    onLog?.("This is the first shot.", "info");
                                                    return null;
                                                }
                                            }}
                                        />
                                        </div>
                                    </div>


                                    {/* End Frame */}
                                    <div className={isPortrait ? 'flex items-stretch gap-2.5 h-full max-h-[650px] 2xl:max-h-[720px] overflow-hidden' : 'space-y-2'}>
                                        <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full overflow-hidden pr-1 justify-center' : ''}`}>
                                            <div className="flex min-h-[52px] items-start justify-between gap-2">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('结束帧', 'End Frame')}
                                            </div>
                                            <div className="flex flex-wrap items-center justify-end gap-1">
                                                <button
                                                    onClick={() => openAssetDetailModal('end')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={() => {
                                                        if (isShotFrameActionLocked('end')) {
                                                            notifyShotFrameActionLocked('end');
                                                            return;
                                                        }
                                                        openMediaPicker(async (url) => {
                                                            const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                            tech.end_frame_url = url;
                                                            const updates = { technical_notes: JSON.stringify(tech) };
                                                            await persistEditingShotUpdates(updates);
                                                        }, { shotId: editingShot.id, shotFrameType: 'end' });
                                                    }}
                                                    disabled={isShotFrameActionLocked('end')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                                                    title={isShotFrameActionLocked('end') ? t('结束帧任务运行中，不能更换图片', 'End frame job is running; image changes are disabled') : t('设置结束帧图片', 'Set end frame image')}
                                                >
                                                    <ImageIcon className="w-3 h-3"/> {t('设置', 'Set')}
                                                </button>
                                                <button
                                                    onClick={handleSetEndFrameFromVideoLastFrame}
                                                    disabled={!editingShot.video_url || currentShotGenerating}
                                                    className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 ${(!editingShot.video_url || currentShotGenerating) ? 'bg-white/10 text-white/40 cursor-not-allowed' : 'bg-amber-500/20 text-amber-200 hover:bg-amber-500/30'}`}
                                                    title={t('从当前视频提取最后一帧', 'Extract last frame from current video')}
                                                >
                                                    <Video className="w-3 h-3"/> {t('取视频尾帧', 'Last Frame')}
                                                </button>
                                                {currentGeneratingState.end && (
                                                    <button 
                                                        onClick={() => handleForceStopShotImage('end')}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title={t('停止重试循环', 'Stop Retry Loop')}
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        {t('停止', 'Stop')}
                                                    </button>
                                                )}
                                                <button 
                                                    onClick={() => generateAssetWithLang('end')} 
                                                    disabled={currentShotGenerating}
                                                    className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 ${currentShotGenerating ? 'bg-sky-500/10 text-sky-300/50 cursor-wait' : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500/30'}`}
                                                >
                                                    {currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                    {currentShotGenerating ? t('生成中...', 'Generating...') : t('生成', 'Generate')}
                                                </button>
                                            </div>
                                        </div>
                                        {currentGeneratingState.end && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">
                                                <div className="flex items-center gap-2 font-bold uppercase tracking-[0.12em] text-amber-100">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    {t('结束帧生成中', 'End Frame In Progress')}
                                                </div>
                                                <div className="mt-1 text-amber-50/75">
                                                    {t('当前预览会在生成完成后自动刷新，替换与删除入口已锁定。', 'This preview will refresh automatically when generation completes. Replace and delete actions are locked.')}
                                                </div>
                                            </div>
                                        )}
                                        <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "h-[420px] 2xl:h-[480px] w-auto mx-auto shrink-0" : "aspect-video w-full"} bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('end')}>
                                            {currentGeneratingState.end && (
                                                <div className="absolute inset-0 bg-black/68 z-10 flex items-center justify-center flex-col gap-3">
                                                    <div className="rounded-full border border-amber-300/30 bg-amber-500/10 p-3">
                                                        <Loader2 className="w-7 h-7 animate-spin text-amber-200"/>
                                                    </div>
                                                    <div className="px-6 text-center">
                                                        <div className="text-sm font-bold uppercase tracking-[0.16em] text-amber-100">{t('正在生成结束帧', 'Generating End Frame')}</div>
                                                        <div className="mt-1 text-[11px] text-white/75">{t('生成完成后会自动更新这里的画面', 'The preview here will update automatically when generation completes')}</div>
                                                    </div>
                                                </div>
                                            )}
                                            {(() => {
                                                const prompt = editingShot.end_frame || '';
                                                let endUrl = null;
                                                let endFrameReusedFromStart = false;
                                                try {
                                                    const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                    endUrl = tech.end_frame_url;
                                                    endFrameReusedFromStart = tech.end_frame_reused_from_start === true;
                                                } catch(e){}

                                                const normalizedEndPrompt = String(prompt || '').trim().toUpperCase();
                                                const isSameAsStart = endFrameReusedFromStart || ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt);

                                                if (!endUrl && isSameAsStart && editingShot.image_url) {
                                                     return (
                                                        <div className="relative w-full h-full group/mirror">
                                                            <SafeImage
                                                                src={editingShot.image_url}
                                                                className="max-w-full max-h-full object-contain opacity-60 group-hover/mirror:opacity-100 transition-opacity cursor-pointer"
                                                                title={t('结束帧当前配置为复用起始帧', 'End frame is currently configured to reuse the start frame')}
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openAssetDetailModal('end');
                                                                }}
                                                            />
                                                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30 group-hover/mirror:opacity-0 transition-opacity">
                                                                <span className="bg-black/50 text-white text-[9px] px-2 py-1 rounded">{t('复用起始帧', 'REUSE START FRAME')}</span>
                                                            </div>
                                                        </div>
                                                     )
                                                }

                                                if (endUrl) {
                                                    return (
                                                        <>
                                                            <SafeImage
                                                                src={endUrl}
                                                                className="max-w-full max-h-full object-contain cursor-pointer hover:opacity-90 transition-opacity"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openAssetDetailModal('end');
                                                                }}
                                                            />
                                                            <button 
                                                                onClick={async (e) => {
                                                                    e.stopPropagation();
                                                                    if (isShotFrameActionLocked('end')) {
                                                                        notifyShotFrameActionLocked('end');
                                                                        return;
                                                                    }
                                                                    if(!await confirmUiMessage("Delete End Frame image?")) return;
                                                                    const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                                    tech.end_frame_url = "";
                                                                    // We also track explicit deletion to avoid auto-regenerating from Start Frame immediately if user doesn't want it
                                                                    if (!tech.deleted_ref_urls) tech.deleted_ref_urls = [];
                                                                    tech.deleted_ref_urls.push(endUrl);
                                                                    
                                                                    const newData = { technical_notes: JSON.stringify(tech) };
                                                                    await onUpdateShot(editingShot.id, newData);
                                                                    setEditingShot(prev => ({...prev, ...newData}));
                                                                    onLog?.('End Frame Image removed', 'info');
                                                                }}
                                                                disabled={isShotFrameActionLocked('end')}
                                                                className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20 disabled:opacity-40 disabled:cursor-not-allowed"
                                                                title={isShotFrameActionLocked('end') ? t('结束帧任务运行中，不能删除图片', 'End frame job is running; image removal is disabled') : t('删除结束帧', 'Delete End Frame')}
                                                            >
                                                                <Trash2 className="w-3 h-3"/>
                                                            </button>
                                                        </>
                                                    );
                                                }

                                                return <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>;
                                            })()}
                                        </div>
                                        
                                        <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[72px] shrink-0"
                                            placeholder={shotPromptDisplayLang === 'cn' ? t('结束帧提示词（中文）...', 'End Frame Prompt (CN)...') : t('结束帧提示词...', 'End Frame Prompt...')}
                                            value={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.end_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.end_frame || '')}
                                            onChange={(e) => {
                                                if (shotPromptDisplayLang === 'cn') {
                                                    const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                    tech.end_frame_cn = e.target.value;
                                                    tech.manual_end_frame = true;
                                                    setEditingShot({ ...editingShot, technical_notes: JSON.stringify(tech) });
                                                } else {
                                                    handleManualEndFrameInputChange(e.target.value);
                                                }
                                            }}
                                        />
                                        </div>
                                        <div className={isPortrait ? "w-[74px] lg:w-[86px] shrink-0 pt-0 flex flex-col h-full overflow-hidden" : "w-full"}>
                                            <ReferenceManager isPortrait={isPortrait} 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图', 'Refs')}
                                            promptText={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.end_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.end_frame || '')}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="end_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                        </div>
                                    </div>

                                    {/* Final Video Output (Moved Here) */}
                                    <div className={isPortrait ? 'flex items-stretch gap-2.5 h-full max-h-[650px] 2xl:max-h-[720px] overflow-hidden' : 'space-y-2'}>
                                        <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full overflow-hidden pr-1 justify-center' : ''}`}>
                                            <div className="flex min-h-[52px] items-start justify-between gap-2">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('最终视频', 'Final Video')}
                                            </div>
                                            
                                            <div className="flex flex-wrap items-center justify-end gap-1">
                                                <label className="inline-flex items-center gap-1.5 text-[10px] text-white/80 whitespace-nowrap">
                                                    <input
                                                        type="checkbox"
                                                        className="accent-sky-400"
                                                        checked={isVoiceoverSyncEnabled}
                                                        onChange={(e) => setVoiceoverSyncEnabled(e.target.checked)}
                                                    />
                                                    {t('配音', 'Voiceover')}
                                                </label>
                                                <button
                                                    onClick={() => openAssetDetailModal('video')}
                                                    className="bg-white/10 hover:bg-white/20 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={() => openMediaPicker((url) => {
                                                        const changes = { video_url: url };
                                                        onUpdateShot(editingShot.id, changes);
                                                    }, { type: 'video' })}
                                                    className="bg-white/10 hover:bg-white/20 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
                                                    title={t('选择或上传视频', 'Select or Upload Video')}
                                                >
                                                    <Upload size={10} /> {t('设置', 'Set')}
                                                </button>

                                                {/* Shot-specific Final Video Mode */}
                                                <select
                                                    value={(() => {
                                                        try {
                                                            const t = JSON.parse(editingShot.technical_notes || '{}');
                                                            return resolveUnifiedVideoMode(t);
                                                        } catch(e) { return 'start_end'; }
                                                    })()}
                                                    onChange={(e) => {
                                                        const nextMode = e.target.value;
                                                        applyVideoModeToShot(nextMode).catch((err) => {
                                                            console.error(err);
                                                            showNotification(t('保存视频模式失败', 'Failed to save video mode'), 'error');
                                                        });
                                                    }}
                                                    className="bg-black/40 border border-white/20 text-[10px] rounded px-1 py-0.5 text-white/70 outline-none hover:bg-white/5"
                                                    title={t('最终视频生成模式', 'Final Video Generation Mode')}
                                                >
                                                    <option value="start_end">{t('起始+结束', 'Start+End')}</option>
                                                    <option value="start">{t('仅起始', 'Start Only')}</option>
                                                    <option value="end">{t('仅结束', 'End Only')}</option>
                                                    <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                </select>

                                                <button 
                                                    onClick={() => generateAssetWithLang('video')} 
                                                    disabled={currentShotGenerating}
                                                    className={`text-[10px] font-bold px-3 py-0.5 rounded flex items-center gap-1 ${currentShotGenerating ? 'bg-primary/50 text-black/50 cursor-wait' : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500/30' }`}
                                                >
                                                    {currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>} 
                                                    {currentShotGenerating ? t('生成中...', 'Generating...') : t('生成', 'Generate')}
                                                </button>
                                                <button
                                                    onClick={() => handleForceStopShotVideo(editingShot?.id)}
                                                    className={`text-[10px] font-bold px-3 py-0.5 rounded flex items-center gap-1 ${Boolean(stoppingVideoByShot[String(editingShot?.id || '')]) ? 'bg-red-500/25 text-red-100' : 'bg-red-500/20 text-red-200 hover:bg-red-500/30'}`}
                                                    title={t('强制停止当前镜头的视频生成任务', 'Force stop current shot video job')}
                                                >
                                                    {Boolean(stoppingVideoByShot[String(editingShot?.id || '')]) ? <Loader2 className="w-3 h-3 animate-spin"/> : null}
                                                    {Boolean(stoppingVideoByShot[String(editingShot?.id || '')]) ? t('停止中...', 'Stopping...') : t('强制停止', 'Force Stop')}
                                                </button>
                                                <button
                                                    onClick={handleGenerateVoiceoverOnly}
                                                    disabled={currentVoiceGenerating}
                                                    className={`text-[10px] font-bold px-3 py-0.5 rounded flex items-center gap-1 ${currentVoiceGenerating ? 'bg-emerald-500/10 text-emerald-200/50 cursor-wait' : 'bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30'}`}
                                                >
                                                    {currentVoiceGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                    {currentVoiceGenerating ? t('配音生成中...', 'Generating voiceover...') : t('仅生成配音', 'Generate Voiceover Only')}
                                                </button>
                                            </div>
                                        </div>

                                        <div 
                                            style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "h-[420px] 2xl:h-[480px] w-auto mx-auto shrink-0" : "aspect-video w-full"} bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center`}
                                            onClick={() => openAssetDetailModal('video')}
                                        >
                                            {currentGeneratingState.video && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">{t('正在生成视频...', 'Generating Video...')}</span>
                                                </div>
                                            )}
                                            {(editingShot.video_url) ? (
                                                <ManagedVideoPlayer
                                                    src={editingShot.video_url}
                                                    poster={resolveShotVideoPosterUrl(editingShot)}
                                                    className="max-w-full max-h-full object-contain"
                                                    wrapperClassName="w-full h-full"
                                                    preload="metadata"
                                                    suspend={assetDetailModal.open && assetDetailModal.type === 'video'}
                                                    uiLang={uiLang}
                                                    onClick={(e) => e?.preventDefault?.()}
                                                />
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20 flex-col gap-2">
                                                    <Video className="w-10 h-10"/>
                                                    <span className="text-xs">{t('暂无视频', 'No Video')}</span>
                                                </div>
                                            )}
                                             {(editingShot.video_url) && <div className="absolute inset-0 flex items-center justify-center pointer-events-none group-hover:bg-black/10"><Maximize2 className="text-white opacity-0 group-hover:opacity-100 drop-shadow-md"/></div>}
                                             
                                             {/* Video Actions Overlay */}
                                             {!currentGeneratingState.video && (
                                                <div className="absolute top-2 right-2 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            openMediaPicker(async (url) => {
                                                                const changes = { video_url: url };
                                                                await onUpdateShot(editingShot.id, changes);
                                                                setEditingShot(prev => ({...prev, ...changes}));
                                                                onLog?.('Video changed', 'success');
                                                            }, { type: 'video' });
                                                        }}
                                                        className="p-1.5 bg-black/60 hover:bg-sky-500/80 text-white rounded-md transition-all shadow"
                                                        title={t('选择或上传视频以替换或回填', 'Select or Upload Video')}
                                                    >
                                                        <Upload className="w-3.5 h-3.5"/>
                                                    </button>
                                                    {editingShot.video_url && (
                                                        <button
                                                            onClick={async (e) => { 
                                                                e.stopPropagation();
                                                                if(!await confirmUiMessage(t('确定要删除当前视频并撤回默认状态吗？', 'Delete current Video?'))) return;
                                                                const newData = { video_url: "" };
                                                                await onUpdateShot(editingShot.id, newData);
                                                                setEditingShot(prev => ({...prev, ...newData}));
                                                                onLog?.('Video removed', 'info');
                                                            }}
                                                            className="p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md transition-all shadow"
                                                            title={t('删除视频，重置为空白状态', 'Delete Video')}
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5"/>
                                                        </button>
                                                    )}
                                                </div>
                                             )}
                                        </div>
                                        {(() => {
                                            let voiceoverUrl = '';
                                            try {
                                                voiceoverUrl = String(JSON.parse(editingShot.technical_notes || '{}')?.voiceover_url || '').trim();
                                            } catch (e) {}
                                            if (!voiceoverUrl) return null;
                                            return (
                                                <div className="rounded border border-white/10 bg-black/20 p-2">
                                                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">{t('配音预览', 'Voiceover Preview')}</div>
                                                    <audio src={getFullUrl(voiceoverUrl)} controls className="w-full" />
                                                </div>
                                            );
                                        })()}

                                        <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[72px] shrink-0"
                                            placeholder={shotPromptDisplayLang === 'cn' ? t('动作 / 运动提示词（中文）...', 'Action / Motion Prompt (CN)...') : t('动作 / 运动提示词...', 'Action / Motion Prompt...')}
                                            value={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''; } catch (e) { return ''; } })() : getShotVideoPromptEn(editingShot)}
                                            onChange={(e) => {
                                                const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                tech.manual_video_prompt = true;
                                                if (shotPromptDisplayLang === 'cn') {
                                                    tech.video_prompt_cn = e.target.value;
                                                    setEditingShot({
                                                        ...editingShot,
                                                        technical_notes: JSON.stringify(tech),
                                                    });
                                                } else {
                                                    setEditingShot({
                                                        ...editingShot,
                                                        ...buildVideoPromptEnUpdates(e.target.value),
                                                        technical_notes: JSON.stringify(tech),
                                                    });
                                                }
                                            }}
                                        />
                                        </div>
                                        <div className={isPortrait ? "w-[74px] lg:w-[86px] shrink-0 pt-0 flex flex-col h-full overflow-hidden" : "w-full"}>
                                            <ReferenceManager isPortrait={isPortrait} 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图', 'Refs')}
                                            promptText={`${getShotVideoPromptEn(editingShot) || ''}\n${(() => { try { return String(JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''); } catch (e) { return ''; } })()}`}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="video_ref_image_urls"
                                            strictPromptOnly={resolveVideoModeFromTech(JSON.parse(editingShot.technical_notes || '{}')) !== 'entity_refs'}
                                        />
                                        </div>
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}
                                <div className="space-y-4 border-t border-white/10 pt-4">
                                     <div className="flex justify-between items-center">
                                        <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                            {t('关键帧（时间线）', 'Keyframes (Timeline)')}
                                            <span className="bg-white/10 text-white px-1.5 rounded-full text-[9px]">
                                                {localKeyframes.length}
                                            </span>
                                        </div>
                                        <button 
                                            onClick={() => {
                                                const newTime = `${(localKeyframes.length + 1) * 1.0}s`;
                                                const newKf = { 
                                                    id: Date.now(), 
                                                    time: newTime, 
                                                    prompt: "[Global Style] ...", 
                                                    url: "" 
                                                };
                                                const newList = [...localKeyframes, newKf];
                                                setLocalKeyframes(newList);
                                                // Trigger save logic? Maybe wait for edit?
                                                // auto-save structure
                                                // reconstructKeyframes(newList); // Optional, maybe let user edit first
                                            }}
                                            className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded flex items-center gap-1"
                                        >
                                            <Plus className="w-3 h-3"/> {t('新增关键帧', 'Add Keyframe')}
                                        </button>
                                    </div>
                                    
                                    <div className="flex gap-4 overflow-x-auto pb-4 min-h-[160px] snap-x">
                                        {localKeyframes.length === 0 && (
                                            <div className="text-xs text-muted-foreground italic p-2 w-full text-center border-dashed border border-white/10 rounded">
                                                {t('尚未定义关键帧。新增一个以开始复杂运动规划。', 'No keyframes defined. Add one to start complex motion planning.')}
                                            </div>
                                        )}
                                        {localKeyframes.map((kf, idx) => (
                                            <div key={idx} className="relative w-[280px] flex-shrink-0 bg-black/20 rounded border border-white/10 p-2 space-y-2 snap-center group">
                                                {/* Header */}
                                                <div className="flex justify-between items-center text-[10px]">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-muted-foreground font-bold">T=</span>
                                                        <input 
                                                            className="bg-transparent border-b border-white/10 w-12 text-center focus:border-primary outline-none text-white"
                                                            value={kf.time}
                                                            onChange={(e) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].time = e.target.value;
                                                                setLocalKeyframes(updated);
                                                            }}
                                                            onBlur={() => reconstructKeyframes(localKeyframes)}
                                                        />
                                                    </div>
                                                    <div className="flex gap-1">
                                                        <button
                                                            onClick={() => openAssetDetailModal('keyframe', idx)}
                                                            className="px-1.5 py-0.5 bg-white/10 hover:bg-white/20 text-white rounded"
                                                        >
                                                            {t('详情', 'Detail')}
                                                        </button>
                                                        <button 
                                                            onClick={() => generateAssetWithLang('keyframe', idx)} 
                                                            className="px-1.5 py-0.5 bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 rounded flex items-center gap-1"
                                                            disabled={kf.loading || currentShotGenerating}
                                                        >
                                                            {kf.loading || currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                            {t('生成', 'Generate')}
                                                        </button>
                                                        <button 
                                                            onClick={() => {
                                                                const updated = [...localKeyframes];
                                                                updated.splice(idx, 1);
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }}
                                                            className="p-1 hover:bg-red-500/20 text-muted-foreground hover:text-red-500 rounded transition-colors"
                                                        >
                                                            <Trash2 className="w-3 h-3"/>
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Image Area */}
                                                <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden group/image cursor-pointer flex items-center justify-center`} onClick={() => openAssetDetailModal('keyframe', idx)}>
                                                    {kf.url ? (
                                                        <>
                                                            <SafeImage
                                                                src={kf.url}
                                                                className="max-w-full max-h-full object-contain cursor-pointer hover:opacity-90"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openAssetDetailModal('keyframe', idx);
                                                                }}
                                                            />
                                                            <button 
                                                                onClick={async (e) => {
                                                                    e.stopPropagation();
                                                                    if(!await confirmUiMessage("Remove image?")) return;
                                                                    const updated = [...localKeyframes];
                                                                    updated[idx].url = "";
                                                                    setLocalKeyframes(updated);
                                                                    reconstructKeyframes(updated);
                                                                }}
                                                                className="absolute top-1 right-1 bg-black/60 text-white p-1 rounded opacity-0 group-hover/image:opacity-100 transition-opacity"
                                                            >
                                                                <Trash2 className="w-3 h-3"/>
                                                            </button>
                                                        </>
                                                    ) : (
                                                        <div className="absolute inset-0 flex items-center justify-center opacity-20">
                                                            <ImageIcon className="w-6 h-6"/>
                                                        </div>
                                                    )}
                                                    
                                                    {/* Quick Set Button Overlay */}
                                                    <div className="absolute bottom-1 right-1 opacity-0 group-hover/image:opacity-100 transition-opacity">
                                                        <button 
                                                            onClick={() => openMediaPicker((url) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].url = url;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            })}
                                                            className="bg-black/60 hover:bg-white/20 text-white text-[9px] px-1.5 py-0.5 rounded flex items-center gap-1 backdrop-blur-sm"
                                                        >
                                                            <Upload className="w-2.5 h-2.5"/> Set
                                                        </button>
                                                    </div>

                                                    {kf.loading && (
                                                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-10">
                                                            <Loader2 className="w-5 h-5 animate-spin text-primary"/>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Prompt Area */}
                                                <PromptMentionTextarea entities={entities} uiLang={uiLang} 
                                                    className="w-full bg-black/20 border border-white/10 rounded p-1.5 text-[10px] h-[60px] focus:border-primary/50 outline-none resize-none"
                                                    placeholder={t('关键帧描述...', 'Keyframe Description...')}
                                                    value={kf.prompt}
                                                    onChange={(e) => {
                                                        const updated = [...localKeyframes];
                                                        updated[idx].prompt = e.target.value;
                                                        setLocalKeyframes(updated);
                                                    }}
                                                    onBlur={() => reconstructKeyframes(localKeyframes)}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>


                                {/* Video Result - REMOVED from here, moved up */}
                            </div>


                            {/* 3. Associated Entities */}
                            <div className="space-y-3 pt-4 border-t border-white/10">
                                <h4 className="text-sm font-bold text-primary flex items-center gap-2"><Users className="w-4 h-4"/> Associated Entities</h4>
                                <div className="bg-black/20 border border-white/10 rounded-xl p-4 flex gap-4 overflow-x-auto min-h-[100px] items-center">
                                    {(() => {
                                        const cleanName = (s) => String(s || '')
                                            .replace(/[\[\]【】"''“”‘’]/g, '')
                                            .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
                                            .replace(/^@+/, '')
                                            .trim();
                                        const normalizeForMatch = (s) => cleanName(s)
                                            .replace(/[_\-]+/g, ' ')
                                            .replace(/\s+/g, ' ')
                                            .trim()
                                            .toLowerCase();
                                        const rawNames = (editingShot.associated_entities || '').split(/[,，]/);
                                        const names = rawNames.map(cleanName).filter(Boolean);
                                        const normalizedNames = names.map(normalizeForMatch).filter(Boolean);
                                        
                                        // Match entity names (English or Chinese)
                                        const matches = entities.filter(e => normalizedNames.some(n => {
                                            const cn = normalizeForMatch(e.name || '');
                                            let en = normalizeForMatch(e.name_en || '');

                                            // Fallback: Try to extract English name from description if name_en is empty
                                            if (!en && e.description) {
                                                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                                if (enMatch && enMatch[1]) {
                                                    const complexEn = enMatch[1].trim();
                                                    en = normalizeForMatch(complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0]); 
                                                }
                                            }

                                            // Exact match check first for better precision
                                            if (cn === n || en === n) return true;
                                            
                                            // Check CN name match (both directions)
                                            if (cn && (cn.includes(n) || n.includes(cn))) return true;
                                            // Check EN name match (both directions)
                                            if (en && (en.includes(n) || n.includes(en))) return true;
                                            return false;
                                        }));

                                        // New Feature: Scene Environment Matching
                                        // Attempt to find current scene environment/location and add to matches if not already there
                                        let envMatches = [];
                                        if (selectedSceneId && selectedSceneId !== 'all') {
                                            // Find current scene from user selection
                                            const currentScene = scenes.find(s => s.id == selectedSceneId);
                                            if (currentScene) {
                                                // Extract location from scene (e.g., "[废弃展区内部 (主视角)]")
                                                // Clean brackets like [ ]
                                                const rawLoc = cleanName((currentScene.location || currentScene.environment_name || '').replace(/[\[\]]/g, ''));
                                                const rawLocNorm = normalizeForMatch(rawLoc);
                                                
                                                if (rawLocNorm) {
                                                    // console.log("Matching Env:", rawLoc);
                                                    const envs = entities.filter(e => {
                                                        // Filter for Environment type entities primarily, but allow others
                                                        // if (e.type !== 'environment') return false; 
                                                        
                                                        const cn = normalizeForMatch(e.name || '');
                                                        let en = normalizeForMatch(e.name_en || '');
                                                        // Fallback EN extract
                                                        if (!en && e.description) {
                                                            const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                                            if (enMatch && enMatch[1]) en = normalizeForMatch(enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0]); 
                                                        }

                                                        // Use looser matching for descriptions/anchors
                                                        // Is the Location string contained in Entity Name? or vice versa?
                                                        if (cn && (cn.includes(rawLocNorm) || rawLocNorm.includes(cn))) return true;
                                                        if (en && (en.includes(rawLocNorm) || rawLocNorm.includes(en))) return true;
                                                        
                                                        return false;
                                                    });
                                                    // console.log("Found Envs:", envs);
                                                    envMatches = envs.filter(env => !matches.find(m => m.id === env.id)); // Dedup
                                                }
                                            }
                                        }

                                        const allMatches = [...matches, ...envMatches];
                                        
                                        if (allMatches.length === 0) return (
                                            <div className="text-xs text-muted-foreground w-full text-center break-words p-2">
                                                No entities matched tags: "{names.join(', ')}". 
                                                <br/>
                                                <span className="opacity-50 text-[10px] block mt-1">
                                                    Available({entities.length}): {entities.map(e => `${e.name}${e.name_en ? `/${e.name_en}` : ''}`).slice(0, 15).join(', ')}
                                                </span>
                                            </div>
                                        );
                                        
                                        return allMatches.map((e, idx) => (
                                            <div key={e.id} className="flex flex-col items-center gap-2 min-w-[70px]">
                                                <div className="w-14 h-14 rounded-full overflow-hidden border border-white/20 bg-black/50 relative">
                                                    {e.image_url ? <SafeImage src={e.image_url} className="w-full h-full object-contain object-center" fallback={<Users className="w-6 h-6 m-auto absolute inset-0 text-muted-foreground opacity-50"/>} /> : <Users className="w-6 h-6 m-auto absolute inset-0 text-muted-foreground opacity-50"/>}
                                                </div>
                                                <span className="text-[10px] text-center line-clamp-1 w-full opacity-80">{e.name}</span>
                                            </div>
                                        ));
                                    })()}
                                </div>
                                {/* Association Tags Input Removed as requested */}
                            </div>

                            {/* Metadata */}
                            <div className="space-y-3 pt-4 border-t border-white/10">
                                <div className="flex items-center justify-between gap-2">
                                    <h4 className="text-sm font-bold text-primary flex items-center gap-2">
                                        <Info className="w-4 h-4" />
                                        {t('扩展列（导入入库）', 'Extra Columns (Imported)')}
                                    </h4>
                                    <button
                                        onClick={() => {
                                            const next = { ...(editingShotExtraColumns || {}) };
                                            let seed = 1;
                                            while (Object.prototype.hasOwnProperty.call(next, `extra_col_${seed}`)) seed += 1;
                                            next[`extra_col_${seed}`] = '';
                                            setEditingShotExtraColumns(next);
                                        }}
                                        className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded flex items-center gap-1"
                                    >
                                        <Plus className="w-3 h-3" /> {t('新增列', 'Add Column')}
                                    </button>
                                </div>

                                {Object.keys(editingShotExtraColumns || {}).length === 0 ? (
                                    <div className="text-xs text-muted-foreground bg-black/20 border border-white/10 rounded p-3">
                                        {t('暂无扩展列。若 markdown 中有新增列，导入后会出现在这里并可编辑。', 'No extra columns yet. If markdown contains new columns, they will appear here and be editable.')}
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {Object.entries(editingShotExtraColumns || {}).map(([k, v]) => (
                                            <div key={`extra-col-${k}`} className="grid grid-cols-[minmax(180px,1fr)_minmax(320px,2fr)_auto] gap-2 items-start">
                                                <input
                                                    className="bg-black/20 border border-white/10 rounded p-2 text-xs"
                                                    value={k}
                                                    onChange={(e) => {
                                                        const nextKey = String(e.target.value || '').trim();
                                                        const current = { ...(editingShotExtraColumns || {}) };
                                                        const curVal = current[k];
                                                        delete current[k];
                                                        if (nextKey) {
                                                            current[nextKey] = curVal;
                                                        }
                                                        setEditingShotExtraColumns(current);
                                                    }}
                                                    placeholder={t('列名', 'Column Name')}
                                                />
                                                <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                    className="bg-black/20 border border-white/10 rounded p-2 text-xs min-h-[60px]"
                                                    value={String(v ?? '')}
                                                    onChange={(e) => {
                                                        const current = { ...(editingShotExtraColumns || {}) };
                                                        current[k] = e.target.value;
                                                        setEditingShotExtraColumns(current);
                                                    }}
                                                    placeholder={t('列值', 'Column Value')}
                                                />
                                                <button
                                                    onClick={() => {
                                                        const current = { ...(editingShotExtraColumns || {}) };
                                                        delete current[k];
                                                        setEditingShotExtraColumns(current);
                                                    }}
                                                    className="p-2 hover:bg-red-500/20 text-muted-foreground hover:text-red-400 rounded"
                                                    title={t('删除列', 'Delete Column')}
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/10 text-xs text-muted-foreground">
                                <InputGroup label="Shot Number" value={editingShot.shot_id} onChange={(v) => { setEditingShot({...editingShot, shot_id: v}) }} />
                                <InputGroup label="Duration (s)" value={editingShot.duration} onChange={v => setEditingShot({...editingShot, duration: v})} />
                            </div>

                            <button 
                                onClick={async () => {
                                    try {
                                        await updateShot(editingShot.id, editingShot);
                                        setShots(shots.map(s => s.id === editingShot.id ? editingShot : s));
                                        setEditingShot(null);
                                        onLog?.("Shot updated.", "success");
                                    } catch(e) {
                                        onLog?.("Update failed.", "error");
                                    }
                                }}
                                className="w-full py-4 bg-primary text-black font-bold rounded-lg hover:bg-primary/90 mt-4"
                            >
                                Save Changes
                            </button>

                            {assetDetailModal.open && (
                                <div className="fixed inset-0 z-[120] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
                                    <div className="w-full max-w-7xl h-[94vh] bg-[#09090b] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden">
                                        <div className="p-4 border-b border-white/10 flex items-center justify-between">
                                            <h4 className="font-bold text-white flex items-center gap-2">
                                                <Info className="w-4 h-4 text-primary" />
                                                {assetDetailModal.type === 'start' && t('起始帧详情', 'Start Frame Detail')}
                                                {assetDetailModal.type === 'end' && t('结束帧详情', 'End Frame Detail')}
                                                {assetDetailModal.type === 'video' && t('视频详情', 'Video Detail')}
                                                {assetDetailModal.type === 'keyframe' && t('关键帧详情', 'Keyframe Detail')}
                                            </h4>
                                            <button onClick={closeAssetDetailModal} className="p-2 hover:bg-white/10 rounded-full"><X className="w-4 h-4"/></button>
                                        </div>

                                        <div className="flex-1 overflow-auto p-4">
                                            {(() => {
                                                let tech = {};
                                                try { tech = JSON.parse(editingShot.technical_notes || '{}'); } catch (e) {}
                                                const updateTechField = (key, value) => {
                                                    const nextTech = { ...tech, [key]: value };
                                                    setEditingShot(prev => ({ ...(prev || {}), technical_notes: JSON.stringify(nextTech) }));
                                                };
                                                const showCnPrompt = shotPromptDisplayLang === 'cn';
                                                const startPromptTextCn = String(tech.start_frame_cn || '');
                                                const startPromptTextEn = String(editingShot.start_frame || '');
                                                const endPromptTextCn = String(tech.end_frame_cn || '');
                                                const endPromptTextEn = String(editingShot.end_frame || '');
                                                const videoPromptTextCn = String(tech.video_prompt_cn || '');
                                                const videoPromptTextEn = getShotVideoPromptEn(editingShot);
                                                const modalType = assetDetailModal.type;
                                                const keyframe = modalType === 'keyframe' ? localKeyframes[assetDetailModal.keyframeIndex] : null;
                                                const endFrameUrl = String(tech.end_frame_url || '');
                                                const showImageCfgControl = modalType === 'start' || modalType === 'end' || modalType === 'keyframe';
                                                const currentImageCfgValue = clampShotImageCfg(shotImageCfgValue, shotImageCfgDefault);
                                                const imageCfgControl = showImageCfgControl ? (
                                                    <div className="space-y-3 rounded-lg border border-amber-400/20 bg-amber-500/5 p-4">
                                                        <div className="flex items-center justify-between gap-3">
                                                            <div>
                                                                <div className="text-[11px] text-amber-200 uppercase font-bold">{t('本次生图强度', 'Image Prompt Strength')}</div>
                                                                <div className="text-xs text-gray-300 mt-1">
                                                                    {t('只影响当前这次生图，不会改动你的全局 Settings。', 'This only affects the current image generation and will not change your global Settings.')}
                                                                </div>
                                                            </div>
                                                            <div className="px-2 py-1 rounded bg-black/30 border border-white/10 text-sm font-mono text-amber-100">
                                                                {currentImageCfgValue.toFixed(1)}
                                                            </div>
                                                        </div>
                                                        <input
                                                            type="range"
                                                            min={SHOT_IMAGE_CFG_MIN}
                                                            max={SHOT_IMAGE_CFG_MAX}
                                                            step={SHOT_IMAGE_CFG_STEP}
                                                            value={currentImageCfgValue}
                                                            onChange={(e) => setShotImageCfgValue(clampShotImageCfg(e.target.value, shotImageCfgDefault))}
                                                            className="w-full accent-amber-400"
                                                        />
                                                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                                                            <span>{t('更自由，更容易出氛围', 'Looser, more atmospheric')}</span>
                                                            <span>{t('更贴近提示词，但可能更硬', 'Closer to prompt, but can feel stiffer')}</span>
                                                        </div>
                                                        <div className="text-xs text-gray-300 leading-6">
                                                            {t(
                                                                `默认值 ${shotImageCfgDefault.toFixed(1)} 来自你的 Settings。想临时提高细节贴合度时，可以往右拖一点；如果画面开始发硬、过度堆细节，就往左收回。`,
                                                                `Default ${shotImageCfgDefault.toFixed(1)} comes from your Settings. Drag right when you want tighter prompt adherence; drag left if the image starts to feel rigid or over-detailed.`
                                                            )}
                                                        </div>
                                                        <div className="flex justify-end">
                                                            <button
                                                                type="button"
                                                                onClick={() => setShotImageCfgValue(shotImageCfgDefault)}
                                                                className="text-xs px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-white/80"
                                                            >
                                                                {t('恢复默认', 'Reset to Default')}
                                                            </button>
                                                        </div>
                                                    </div>
                                                ) : null;

                                                let detailUrl = '';
                                                let detailType = 'image';
                                                if (modalType === 'start') {
                                                    detailUrl = String(editingShot.image_url || '');
                                                    detailType = 'image';
                                                } else if (modalType === 'end') {
                                                    detailUrl = endFrameUrl;
                                                    detailType = 'image';
                                                } else if (modalType === 'video') {
                                                    detailUrl = String(editingShot.video_url || '');
                                                    detailType = 'video';
                                                } else {
                                                    detailUrl = String(keyframe?.url || '');
                                                    detailType = 'image';
                                                }

                                                const linkedAsset = resolveShotAssetByUrl(detailUrl, detailType);
                                                const linkedAssetDetail = buildShotAssetDetail(linkedAsset, detailType, detailUrl);
                                                const linkedAssetMeta = linkedAssetDetail.rawMeta;
                                                const shotConfiguredDuration = String(editingShot?.duration ?? '').trim();

                                                const renderAssetMetaPanel = (assetDetail = linkedAssetDetail, rawMeta = linkedAssetMeta, titleText = t('资产元数据', 'Asset Metadata')) => (
                                                    <div className="space-y-2 rounded-lg border border-white/10 bg-black/30 p-3">
                                                        <div className="text-[11px] text-muted-foreground uppercase font-bold">{titleText}</div>
                                                        {shotAssetsMetaLoading && (
                                                            <div className="text-xs text-muted-foreground flex items-center gap-1">
                                                                <Loader2 className="w-3 h-3 animate-spin" />
                                                                {t('加载中...', 'Loading...')}
                                                            </div>
                                                        )}
                                                        <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('分辨率', 'Resolution')}</div>
                                                                <div className="text-white/90">{assetDetail.resolution || '-'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('画幅比', 'Aspect Ratio')}</div>
                                                                <div className="text-white/90">{assetDetail.aspectRatio || '-'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('文件大小', 'File Size')}</div>
                                                                <div className="text-white/90">{assetDetail.fileSize || '-'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('格式', 'Format')}</div>
                                                                <div className="text-white/90">{assetDetail.format || '-'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('时长', 'Duration')}</div>
                                                                <div className="text-white/90">{assetDetail.duration || '-'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('来源', 'Source')}</div>
                                                                <div className="text-white/90">{assetDetail.source || '-'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">Provider</div>
                                                                <div className="text-white/90">
                                                                    {assetDetail.providerAlias || assetDetail.provider || '-'}
                                                                    {assetDetail.providerAlias && assetDetail.provider ? (
                                                                        <span className="ml-1 text-[10px] text-muted-foreground font-mono">({assetDetail.provider})</span>
                                                                    ) : null}
                                                                </div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[10px] text-muted-foreground uppercase">Model</div>
                                                                <div className="text-white/90">{assetDetail.model || '-'}</div>
                                                            </div>
                                                            <div className="col-span-2">
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('文件名', 'Filename')}</div>
                                                                <div className="text-white/90 break-all">{assetDetail.filename || assetDetail.url.split('/').pop() || '-'}</div>
                                                            </div>
                                                            <div className="col-span-2">
                                                                <div className="text-[10px] text-muted-foreground uppercase">{t('创建时间', 'Created At')}</div>
                                                                <div className="text-white/90">{assetDetail.createdAt || '-'}</div>
                                                            </div>
                                                        </div>
                                                        {rawMeta && Object.keys(rawMeta).length > 0 && (
                                                            <details className="pt-1">
                                                                <summary className="text-[10px] uppercase text-muted-foreground cursor-pointer">{t('原始元数据', 'Raw Metadata')}</summary>
                                                                <pre className="mt-2 p-2 rounded border border-white/10 bg-black/40 text-[10px] text-gray-300 overflow-auto max-h-36">{JSON.stringify(rawMeta, null, 2)}</pre>
                                                            </details>
                                                        )}
                                                    </div>
                                                );

                                                const renderInfoPanel = (titleText, rows = []) => (
                                                    <div className="space-y-2 rounded-lg border border-white/10 bg-black/20 p-3">
                                                        <div className="text-[11px] text-muted-foreground uppercase font-bold">{titleText}</div>
                                                        <div className="grid grid-cols-1 gap-2 text-xs">
                                                            {rows.map((row, idx) => (
                                                                <div key={`${titleText}-${idx}`}>
                                                                    <div className="text-[10px] text-muted-foreground uppercase">{row.label}</div>
                                                                    <div className={`text-white/90 ${row.breakAll ? 'break-all' : ''}`}>{row.value || '-'}</div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                );

                                                const renderDetailActionButton = ({
                                                    label,
                                                    busyLabel,
                                                    onClick,
                                                    disabled = false,
                                                    busy = false,
                                                    variant = 'primary',
                                                    title,
                                                }) => {
                                                    const variantClassMap = {
                                                        primary: busy
                                                            ? 'bg-sky-500/10 text-sky-300/50 cursor-wait'
                                                            : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500/30',
                                                        secondary: disabled
                                                            ? 'bg-white/10 text-white/40 cursor-not-allowed'
                                                            : 'bg-white/10 text-white/80 hover:bg-white/20',
                                                        success: busy
                                                            ? 'bg-emerald-500/10 text-emerald-300/50 cursor-wait'
                                                            : 'bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30',
                                                        warning: disabled
                                                            ? 'bg-amber-500/10 text-amber-300/50 cursor-not-allowed'
                                                            : 'bg-amber-500/20 text-amber-200 hover:bg-amber-500/30',
                                                        danger: disabled
                                                            ? 'bg-red-500/10 text-red-300/50 cursor-not-allowed'
                                                            : 'bg-red-500/20 text-red-200 hover:bg-red-500/30',
                                                    };

                                                    return (
                                                        <button
                                                            onClick={onClick}
                                                            disabled={disabled}
                                                            title={title}
                                                            className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${variantClassMap[variant] || variantClassMap.primary}`}
                                                        >
                                                            {busy ? busyLabel : label}
                                                        </button>
                                                    );
                                                };

                                                const renderFrameGeneratingNotice = (frameType) => {
                                                    const stableType = frameType === 'end' ? 'end' : 'start';
                                                    const isRunning = Boolean(currentGeneratingState?.[stableType]);
                                                    if (!isRunning) return null;

                                                    return (
                                                        <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-3 text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">
                                                            <div className="flex items-start gap-3">
                                                                <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-amber-200" />
                                                                <div className="min-w-0">
                                                                    <div className="text-xs font-bold tracking-[0.12em] uppercase text-amber-100">
                                                                        {stableType === 'end'
                                                                            ? t('结束帧生成中', 'End Frame In Progress')
                                                                            : t('起始帧生成中', 'Start Frame In Progress')}
                                                                    </div>
                                                                    <div className="mt-1 text-[11px] leading-5 text-amber-50/80">
                                                                        {stableType === 'end'
                                                                            ? t('当前已锁定结束帧替换、删除与手动回填入口，生成完成后会自动刷新这里的预览。', 'End frame replacement, deletion, and manual apply actions are locked until generation finishes. This preview will refresh automatically when the result is ready.')
                                                                            : t('当前已锁定起始帧替换、删除与手动回填入口，生成完成后会自动刷新这里的预览。', 'Start frame replacement, deletion, and manual apply actions are locked until generation finishes. This preview will refresh automatically when the result is ready.')}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                };

                                                const renderGenerationHistoryPanel = () => {
    const filteredHistory = shotGenerationHistory.filter((item) => {
        const itemKind = resolveGenerationHistoryMediaKind(item);
        
        let targetType = modalType;
        if (modalType === 'keyframe') { 
             targetType = 'start'; 
        }
        
        if (targetType === 'start') {
            return ['start', 'image', 'subject'].includes(itemKind) || !['end', 'video'].includes(itemKind);
        } else if (targetType === 'end') {
            return itemKind === 'end';
        } else if (targetType === 'video') {
            return itemKind === 'video';
        }
        return true;
    });
        

    const handleUseAsCurrent = async (item) => {
        if (!item || !item.resultUrl || !editingShot) return;
        const resultUrl = item.resultUrl;
        
        let updates = {};
        if (modalType === 'start') {
            updates = { image_url: resultUrl };
        } else if (modalType === 'end') {
            const tech = JSON.parse(editingShot.technical_notes || '{}');
            tech['end_frame_url'] = resultUrl;
            tech['end_frame_reused_from_start'] = false;
            updates = { 'technical_notes': JSON.stringify(tech) };
        } else if (modalType === 'video') {
            updates = { 'video_url': resultUrl };
        }
        
        try {
            if (onUpdateShot) {
                await onUpdateShot(editingShot.id, updates);
            }
            setEditingShot((prev) => {
                if (!prev) return prev;
                return { ...prev, ...updates };
            });
            showNotification(t('已选用为当前', 'Applied as current'), 'success');
        } catch (e) {
            if (onLog) onLog(`Failed to apply generated media: ${e.message}`, 'error');
            showNotification(t('选用失败', 'Failed to apply'), 'error');
        }
    };

    return (
                                                    <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-3">
                                                        <div className="flex items-center justify-between gap-2">
                                                            <div>
                                                                <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-white/70">{t('生成历史', 'Generation History')}</div>
                                                                <div className="text-[11px] text-muted-foreground">{t('显示该分镜最近的首帧、尾帧与视频生成记录。', 'Recent start frame, end frame, and video generation records for this shot.')}</div>
                                                            </div>
                                                            <button
                                                                type="button"
                                                                onClick={() => fetchShotGenerationHistory(editingShot)}
                                                                disabled={shotGenerationHistoryLoading || !editingShot?.id}
                                                                className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10 disabled:opacity-50"
                                                            >
                                                                <RefreshCw className={shotGenerationHistoryLoading ? 'animate-spin' : ''} size={12} />
                                                                {t('刷新', 'Refresh')}
                                                            </button>
                                                        </div>
                                                        {shotGenerationHistoryLoading ? (
                                                            <div className="flex items-center justify-center gap-2 rounded border border-dashed border-white/10 px-3 py-6 text-xs text-muted-foreground">
                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                                {t('正在加载镜头生成历史...', 'Loading shot generation history...')}
                                                            </div>
                                                        ) : filteredHistory.length === 0 ? (
                                                            <div className="rounded border border-dashed border-white/10 px-3 py-6 text-center text-xs text-muted-foreground">
                                                                {t('该分镜还没有生成历史。', 'No generation history for this shot yet.')}
                                                            </div>
                                                        ) : (
                                                            <div className="space-y-2 max-h-72 overflow-y-auto pr-1 custom-scrollbar">
                                                                {filteredHistory.map((item) => {
                                                                    const itemId = String(item?.job_id || item?.id || Math.random()).trim();
                                                                    const status = String(item?.status || '').trim().toLowerCase();
                                                                    const canPreview = Boolean(item?.resultUrl);
                                                                    const isVideoItem = item?.mediaKind === 'video' || String(item?.kind || '').trim().toLowerCase() === 'video';
                                                                    const createdText = item?.created_at ? new Date(item.created_at).toLocaleString() : '-';
                                                                    const isDeleting = shotGenerationHistoryDeletingId === itemId;
                                                                    return (
                                                                        <div key={itemId} className="rounded-lg border border-white/10 bg-black/30 p-2.5">
                                                                            <div className="flex gap-3">
                                                                                <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/40 flex items-center justify-center">
                                                                                    {canPreview ? (
                                                                                        isVideoItem ? (
                                                                                            <LazyHoverVideo
                                                                                                src={item.resultUrl}
                                                                                                className="h-full w-full"
                                                                                                mediaClassName="h-full w-full object-cover"
                                                                                                muted
                                                                                                playsInline
                                                                                                preload="metadata"
                                                                                                playOnHover={false}
                                                                                            />
                                                                                        ) : (
                                                                                            <SafeImage src={item.resultUrl} className="h-full w-full object-cover" fallback={<ImageIcon className="h-5 w-5 opacity-40" />} />
                                                                                        )
                                                                                    ) : isVideoItem ? (
                                                                                        <Video className="h-5 w-5 opacity-40" />
                                                                                    ) : (
                                                                                        <ImageIcon className="h-5 w-5 opacity-40" />
                                                                                    )}
                                                                                </div>
                                                                                <div className="min-w-0 flex-1 space-y-1">
                                                                                    <div className="flex items-start justify-between gap-2">
                                                                                        <div className="min-w-0">
                                                                                            <div className="truncate text-sm font-semibold text-white">{item.displayLabel}</div>
                                                                                            <div className="text-[11px] text-muted-foreground truncate">{item.shotName || editingShot?.shot_name || editingShot?.shot_number || '-'}</div>
                                                                                        </div>
                                                                                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${status === 'completed' ? 'bg-emerald-500/15 text-emerald-200' : status === 'failed' ? 'bg-red-500/15 text-red-200' : status === 'canceled' ? 'bg-slate-500/20 text-slate-200' : 'bg-amber-500/15 text-amber-100'}`}>
                                                                                            {status || 'unknown'}
                                                                                        </span>
                                                                                    </div>
                                                                                    <div className="text-[11px] text-muted-foreground">{createdText}</div>
                                                                                    <div className="flex flex-wrap items-center gap-2 pt-1">
                                                                                        <button
                                                                                            type="button"
                                                                                            onClick={() => canPreview && window.open(getFullUrl(item.resultUrl), '_blank', 'noopener,noreferrer')}
                                                                                            disabled={!canPreview}
                                                                                            className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10 disabled:opacity-40"
                                                                                        >
                                                                                            <ExternalLink size={12} />
                                                                                            {t('查看', 'Open')}
                                                                                        </button>
                                                                                        <button
                                                                                            type="button"
                                                                                            onClick={() => handleUseAsCurrent(item)}
            disabled={isDeleting}
            className="inline-flex items-center gap-1 rounded border border-blue-400/20 bg-blue-500/10 px-2 py-1 text-[11px] text-blue-100 hover:bg-blue-500/20 disabled:opacity-50"
        >
            <CheckCircle2 size={12} />
            {t('选用', 'Apply')}
        </button>
        <button
            type="button"
            onClick={() => handleDeleteShotGenerationHistoryItem(item)}
                                                                                            disabled={isDeleting}
                                                                                            className="inline-flex items-center gap-1 rounded border border-red-400/20 bg-red-500/10 px-2 py-1 text-[11px] text-red-100 hover:bg-red-500/20 disabled:opacity-50"
                                                                                        >
                                                                                            {isDeleting ? <Loader2 className="animate-spin" size={12} /> : <Trash2 size={12} />}
                                                                                            {isDeleting ? t('删除中', 'Deleting') : t('删除记录', 'Delete Record')}
                                                                                        </button>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                                };

                                                if (modalType === 'start') {
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                            <div className="space-y-3">
                                                                <div className={`h-[46vh] xl:h-[58vh] bg-black/40 rounded border overflow-hidden flex items-center justify-center relative transition-colors ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`}>
                                                                    {currentGeneratingState.start && (
                                                                        <div className="absolute inset-0 z-10 bg-black/68 flex items-center justify-center flex-col gap-3">
                                                                            <div className="rounded-full border border-amber-300/30 bg-amber-500/10 p-3">
                                                                                <Loader2 className="w-7 h-7 animate-spin text-amber-200" />
                                                                            </div>
                                                                            <div className="text-center px-6">
                                                                                <div className="text-sm font-bold uppercase tracking-[0.16em] text-amber-100">{t('正在生成起始帧', 'Generating Start Frame')}</div>
                                                                                <div className="mt-1 text-xs text-white/75">{t('生成完成后将自动刷新当前预览', 'This preview will refresh automatically when generation completes')}</div>
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                    {editingShot.image_url ? <SafeImage src={editingShot.image_url} className="max-w-full max-h-full object-contain" fallback={<ImageIcon className="w-8 h-8 opacity-30" />} /> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                {renderInfoPanel(t('当前素材信息', 'Current Asset Info'), [
                                                                    { label: t('图片 URL', 'Image URL'), value: editingShot.image_url || '-', breakAll: true },
                                                                    { label: t('参考图数量', 'Ref Count'), value: String(Array.isArray(tech.ref_image_urls) ? tech.ref_image_urls.length : 0) },
                                                                ])}
                                                                {renderAssetMetaPanel(linkedAssetDetail, linkedAssetMeta, t('素材元信息', 'Asset Metadata'))}
                                                            </div>
                                                            <div className="space-y-3">
                                                                {renderFrameGeneratingNotice('start')}
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    {renderDetailActionButton({
                                                                        label: t('生成起始帧', 'Generate Start Frame'),
                                                                        busyLabel: t('起始帧生成中...', 'Generating Start Frame...'),
                                                                        onClick: () => generateAssetWithLang('start', -1, { cfg: currentImageCfgValue }),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu('start')}
                                                                    {renderDetailActionButton({
                                                                        label: t('裁边', 'Trim Edges'),
                                                                        busyLabel: t('裁边处理中...', 'Trimming...'),
                                                                        onClick: () => openFrameTrimModal('start'),
                                                                        disabled: !editingShot.image_url || currentShotGenerating,
                                                                        busy: frameTrimModal.open && frameTrimModal.type === 'start' && frameTrimModal.saving,
                                                                        variant: 'secondary',
                                                                        title: t('裁去当前起始帧四周边缘并回填', 'Trim the current start frame edges and apply the result'),
                                                                    })}
                                                                </div>
                                                                <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-4">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">
                                                                        {t('英文提示词', 'Prompt (EN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={startPromptTextEn}
                                                                        onChange={(e) => {
                                                                            setEditingShot({...editingShot, start_frame: e.target.value});
                                                                        }}
                                                                    />
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                        {t('中文提示词', 'Prompt (CN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={startPromptTextCn}
                                                                        onChange={(e) => {
                                                                            updateTechField('start_frame_cn', e.target.value);
                                                                        }}
                                                                    />
                                                                    <div className="flex items-center gap-2 mt-2 mb-4">
                                                                        {renderDetailActionButton({
                                                                            label: t('翻译成中文', 'To Chinese'),
                                                                            busyLabel: t('翻译中...', 'Translating...'),
                                                                            onClick: () => translateFieldToChinese('start'),
                                                                            disabled: translatingPromptField.startsWith('start:'),
                                                                            busy: translatingPromptField === 'start:to-cn',
                                                                            variant: 'warning'
                                                                        })}
                                                                        {renderDetailActionButton({
                                                                            label: t('翻译成英文', 'To English'),
                                                                            busyLabel: t('翻译中...', 'Translating...'),
                                                                            onClick: () => translateFieldToEnglish('start'),
                                                                            disabled: translatingPromptField.startsWith('start:'),
                                                                            busy: translatingPromptField === 'start:to-en',
                                                                            variant: 'secondary'
                                                                        })}
                                                                    </div>

                                                                    <AdvancedModifyFrame
                                                                        uiLang={uiLang}
                                                                        type="start"
                                                                        promptText={startPromptTextEn}
                                                                        currentImage={editingShot.image_url}
                                                                        currentGenerating={currentShotGenerating}
                                                                        currentImageCfgValue={currentImageCfgValue}
                                                                        onGenerateAsset={generateAssetWithLang}
                                                                        onPromptUpdate={(v) => {
                                                                            setEditingShot({...editingShot, start_frame: v});
                                                                        }}
                                                                    />
                                                                </div>
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => { persistEditingShotUpdates(updates); }} title={t('参考图', 'Refs')} promptText={shotPromptDisplayLang === 'cn' ? startPromptTextCn : startPromptTextEn} uiLang={uiLang} onPickMedia={openMediaPicker} storageKey="ref_image_urls" strictPromptOnly={true} />
                                                                {imageCfgControl}
                                                                {renderGenerationHistoryPanel()}
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                if (modalType === 'end') {
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                            <div className="space-y-3">
                                                                <div className={`h-[46vh] xl:h-[58vh] bg-black/40 rounded border overflow-hidden flex items-center justify-center relative transition-colors ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`}>
                                                                    {currentGeneratingState.end && (
                                                                        <div className="absolute inset-0 z-10 bg-black/68 flex items-center justify-center flex-col gap-3">
                                                                            <div className="rounded-full border border-amber-300/30 bg-amber-500/10 p-3">
                                                                                <Loader2 className="w-7 h-7 animate-spin text-amber-200" />
                                                                            </div>
                                                                            <div className="text-center px-6">
                                                                                <div className="text-sm font-bold uppercase tracking-[0.16em] text-amber-100">{t('正在生成结束帧', 'Generating End Frame')}</div>
                                                                                <div className="mt-1 text-xs text-white/75">{t('生成完成后将自动刷新当前预览', 'This preview will refresh automatically when generation completes')}</div>
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                    {endFrameUrl ? <SafeImage src={endFrameUrl} className="max-w-full max-h-full object-contain" fallback={<ImageIcon className="w-8 h-8 opacity-30" />} /> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                {renderInfoPanel(t('当前素材信息', 'Current Asset Info'), [
                                                                    { label: t('结束帧 URL', 'End Frame URL'), value: endFrameUrl || '-', breakAll: true },
                                                                    { label: t('参考图数量', 'Ref Count'), value: String(Array.isArray(tech.end_ref_image_urls) ? tech.end_ref_image_urls.length : 0) },
                                                                ])}
                                                                {renderAssetMetaPanel(linkedAssetDetail, linkedAssetMeta, t('素材元信息', 'Asset Metadata'))}
                                                            </div>
                                                            <div className="space-y-3">
                                                                {renderFrameGeneratingNotice('end')}
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    {renderDetailActionButton({
                                                                        label: t('生成结束帧', 'Generate End Frame'),
                                                                        busyLabel: t('结束帧生成中...', 'Generating End Frame...'),
                                                                        onClick: () => generateAssetWithLang('end', -1, { cfg: currentImageCfgValue }),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu('end')}
                                                                    {renderDetailActionButton({
                                                                        label: t('裁边', 'Trim Edges'),
                                                                        busyLabel: t('裁边处理中...', 'Trimming...'),
                                                                        onClick: () => openFrameTrimModal('end'),
                                                                        disabled: !endFrameUrl || currentShotGenerating,
                                                                        busy: frameTrimModal.open && frameTrimModal.type === 'end' && frameTrimModal.saving,
                                                                        variant: 'secondary',
                                                                        title: t('裁去当前结束帧四周边缘并回填', 'Trim the current end frame edges and apply the result'),
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('提取视频尾帧', 'Extract Video Last Frame'),
                                                                        busyLabel: t('提取视频尾帧', 'Extract Video Last Frame'),
                                                                        onClick: handleSetEndFrameFromVideoLastFrame,
                                                                        disabled: !editingShot.video_url || currentShotGenerating,
                                                                        variant: 'warning',
                                                                        title: t('从当前视频提取最后一帧', 'Extract last frame from current video'),
                                                                    })}
                                                                </div>
                                                                <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-4">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">
                                                                        {t('英文提示词', 'Prompt (EN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={endPromptTextEn}
                                                                        onChange={(e) => {
                                                                            handleManualEndFrameInputChange(e.target.value);
                                                                        }}
                                                                    />
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                        {t('中文提示词', 'Prompt (CN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={endPromptTextCn}
                                                                        onChange={(e) => {
                                                                            updateTechField('end_frame_cn', e.target.value);
                                                                        }}
                                                                    />
                                                                    <div className="flex items-center gap-2 mt-2 mb-4">
                                                                        {renderDetailActionButton({
                                                                            label: t('翻译成中文', 'To Chinese'),
                                                                            busyLabel: t('翻译中...', 'Translating...'),
                                                                            onClick: () => translateFieldToChinese('end'),
                                                                            disabled: translatingPromptField.startsWith('end:'),
                                                                            busy: translatingPromptField === 'end:to-cn',
                                                                            variant: 'warning'
                                                                        })}
                                                                        {renderDetailActionButton({
                                                                            label: t('翻译成英文', 'To English'),
                                                                            busyLabel: t('翻译中...', 'Translating...'),
                                                                            onClick: () => translateFieldToEnglish('end'),
                                                                            disabled: translatingPromptField.startsWith('end:'),
                                                                            busy: translatingPromptField === 'end:to-en',
                                                                            variant: 'secondary'
                                                                        })}
                                                                    </div>

                                                                    <AdvancedModifyFrame
                                                                        uiLang={uiLang}
                                                                        type="end"
                                                                        promptText={endPromptTextEn}
                                                                        currentImage={endFrameUrl}
                                                                        currentGenerating={currentShotGenerating}
                                                                        currentImageCfgValue={currentImageCfgValue}
                                                                        onGenerateAsset={generateAssetWithLang}
                                                                        onPromptUpdate={handleManualEndFrameInputChange}
                                                                    />
                                                                </div>
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => { persistEditingShotUpdates(updates); }} title={t('参考图', 'Refs')} promptText={shotPromptDisplayLang === 'cn' ? endPromptTextCn : endPromptTextEn} uiLang={uiLang} onPickMedia={openMediaPicker} storageKey="end_ref_image_urls" strictPromptOnly={true} />
                                                                {imageCfgControl}
                                                                {renderGenerationHistoryPanel()}
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                if (modalType === 'video') {
                                                    const pendingVideoJobId = getPendingVideoJobId(editingShot?.id);
                                                    const isStoppingCurrentVideo = Boolean(stoppingVideoByShot[String(editingShot?.id || '')]);
                                                    const voiceoverUrl = String(tech.voiceover_url || '').trim();
                                                    const rawVoiceoverPrompt = String(tech.voiceover_prompt || '').trim();
                                                    const llmDialogueBackfillText = String(
                                                        tech.voiceover_dialogue_text || tech.voiceover_dialogue || ''
                                                    ).trim() || extractDialogueOnlyFromPrompt(rawVoiceoverPrompt) || rawVoiceoverPrompt;
                                                    const voiceAsset = resolveShotAssetByUrl(voiceoverUrl, 'audio');
                                                    const voiceAssetDetail = buildShotAssetDetail(voiceAsset, 'audio', voiceoverUrl);
                                                    const voiceAssetMeta = voiceAssetDetail.rawMeta;
                                                    const voicePersistedMeta = (tech.voiceover_metadata && typeof tech.voiceover_metadata === 'object') ? tech.voiceover_metadata : null;
                                                    const voicePlanMeta = (tech.voiceover_plan && typeof tech.voiceover_plan === 'object') ? tech.voiceover_plan : null;
                                                    const hasVoiceAssetMeta = Boolean(voiceAssetMeta && Object.keys(voiceAssetMeta).length > 0);
                                                    const hasVoicePersistedMeta = Boolean(voicePersistedMeta && Object.keys(voicePersistedMeta).length > 0);
                                                    const resolvedVoiceMeta = hasVoiceAssetMeta ? voiceAssetMeta : voicePersistedMeta;
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                            <div className="space-y-3">
                                                                <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex items-center justify-center relative">
                                                                    {currentGeneratingState.video && (
                                                                        <div className="absolute inset-0 z-10 bg-black/60 flex items-center justify-center flex-col gap-2">
                                                                            <Loader2 className="w-6 h-6 animate-spin text-primary" />
                                                                            <span className="text-xs text-white/80">{t('正在生成视频...', 'Generating Video...')}</span>
                                                                        </div>
                                                                    )}
                                                                    {editingShot.video_url ? (
                                                                        <ManagedVideoPlayer
                                                                            src={editingShot.video_url}
                                                                            poster={resolveShotVideoPosterUrl(editingShot)}
                                                                            className="max-w-full max-h-full object-contain"
                                                                            wrapperClassName="w-full h-full"
                                                                            preload="metadata"
                                                                            uiLang={uiLang}
                                                                        />
                                                                    ) : <Video className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('视频 URL', 'Video URL')}: {editingShot.video_url || '-'}</div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('配音 URL', 'Voice URL')}: {String(tech.voiceover_url || '') || '-'}</div>
                                                                <div className="space-y-1 rounded-lg border border-white/10 bg-black/20 p-3">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('素材实际时长', 'Asset Duration')}</div>
                                                                    <div className="text-sm text-white">{linkedAssetDetail.duration || '-'}</div>
                                                                    <div className="text-[11px] text-muted-foreground">
                                                                        {t('这里显示当前视频素材元数据里的实际时长。', 'This is the actual duration read from the current video asset metadata.')}
                                                                    </div>
                                                                </div>
                                                                <div className="space-y-1 rounded-lg border border-white/10 bg-black/20 p-3">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('Shot 配置时长（秒）', 'Shot Duration Setting (s)')}</div>
                                                                    <input
                                                                        type="number"
                                                                        min="0"
                                                                        step="0.1"
                                                                        value={shotConfiguredDuration}
                                                                        onChange={(e) => setEditingShot(prev => ({ ...(prev || {}), duration: e.target.value }))}
                                                                        className="w-full bg-black/30 border border-white/10 rounded p-2 text-sm text-white"
                                                                        placeholder="5"
                                                                    />
                                                                    <div className="text-[11px] text-muted-foreground">
                                                                        {t('保存后会写回当前 shot 的 Duration 字段，并作为后续视频生成默认时长。', 'Saving writes back to the shot Duration field and uses it as the default for later video generation.')}
                                                                    </div>
                                                                </div>
                                                                <div className="text-xs text-muted-foreground">{t('模式', 'Mode')}: {resolveUnifiedVideoMode(tech)}</div>
                                                                {(voiceoverUrl || llmDialogueBackfillText) && (
                                                                    <div className="space-y-2 rounded-lg border border-white/10 bg-black/30 p-3">
                                                                        <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('配音预览', 'Voiceover Preview')}</div>
                                                                        {voiceoverUrl ? (
                                                                            <SafeAudio src={voiceoverUrl} controls className="w-full" fallback={<div className="text-xs text-muted-foreground">{t('配音文件不可用', 'Voiceover file unavailable')}</div>} />
                                                                        ) : (
                                                                            <div className="text-xs text-muted-foreground">{t('暂无配音音频', 'No voiceover audio yet')}</div>
                                                                        )}
                                                                        {llmDialogueBackfillText && (
                                                                            <div className="space-y-1 pt-1">
                                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold">
                                                                                    {t('大模型抽取对话回填', 'LLM Dialogue Backfill')}
                                                                                </div>
                                                                                <textarea
                                                                                    className="w-full min-h-[92px] bg-black/40 border border-white/10 rounded p-2 text-xs leading-relaxed text-white/90 resize-y"
                                                                                    value={llmDialogueBackfillText}
                                                                                    readOnly
                                                                                />
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                                {voiceoverUrl && renderAssetMetaPanel(voiceAssetDetail, resolvedVoiceMeta, t('配音元信息', 'Voice Metadata'))}
                                                                {voicePlanMeta && !hasVoiceAssetMeta && !hasVoicePersistedMeta && (
                                                                    <div className="space-y-2 rounded-lg border border-white/10 bg-black/30 p-3">
                                                                        <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('配音规划参数', 'Voice Planning Metadata')}</div>
                                                                        <pre className="mt-1 p-2 rounded border border-white/10 bg-black/40 text-[10px] text-gray-300 overflow-auto max-h-36">{JSON.stringify(voicePlanMeta, null, 2)}</pre>
                                                                    </div>
                                                                )}
                                                                {renderAssetMetaPanel()}
                                                            </div>
                                                            <div className="space-y-3">
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    {renderDetailActionButton({
                                                                        label: t('生成视频', 'Generate Video'),
                                                                        busyLabel: t('视频生成中...', 'Generating Video...'),
                                                                        onClick: () => generateAssetWithLang('video'),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu('video')}
                                                                    {renderDetailActionButton({
                                                                        label: t('生成配音', 'Generate Voiceover'),
                                                                        busyLabel: t('配音生成中...', 'Generating Voiceover...'),
                                                                        onClick: handleGenerateVoiceoverOnly,
                                                                        disabled: currentVoiceGenerating,
                                                                        busy: currentVoiceGenerating,
                                                                        variant: 'success',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('强制停止', 'Force Stop'),
                                                                        busyLabel: t('停止中...', 'Stopping...'),
                                                                        onClick: () => handleForceStopShotVideo(editingShot?.id),
                                                                        disabled: false,
                                                                        busy: isStoppingCurrentVideo,
                                                                        variant: 'danger',
                                                                        title: t('强制停止当前镜头的视频生成任务', 'Force stop current shot video job'),
                                                                    })}
                                                                </div>
                                                                <label className="inline-flex items-center gap-2 text-xs text-white/80">
                                                                    <input
                                                                        type="checkbox"
                                                                        className="accent-sky-400"
                                                                        checked={isVoiceoverSyncEnabled}
                                                                        onChange={(e) => setVoiceoverSyncEnabled(e.target.checked)}
                                                                    />
                                                                    {t('配音', 'Voiceover')}
                                                                </label>
                                                                <div className="flex items-center justify-between">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('生成模式', 'Generation Mode')}</div>
                                                                    <select
                                                                        value={resolveVideoModeFromTech(tech)}
                                                                        onChange={(e) => {
                                                                            const nextMode = e.target.value;
                                                                            applyVideoModeToShot(nextMode).catch((err) => {
                                                                                console.error(err);
                                                                                showNotification(t('保存视频模式失败', 'Failed to save video mode'), 'error');
                                                                            });
                                                                        }}
                                                                        className="bg-black/40 border border-white/20 text-[10px] rounded px-2 py-1 text-white/80 outline-none hover:bg-white/5"
                                                                    >
                                                                        <option value="start_end">{t('起始+结束', 'Start+End')}</option>
                                                                        <option value="start">{t('仅起始', 'Start Only')}</option>
                                                                        <option value="end">{t('仅结束', 'End Only')}</option>
                                                                        <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                                    </select>
                                                                </div>
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                    {t('中文提示词', 'Prompt (CN)')}
                                                                </div>
                                                                <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                    className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                    value={videoPromptTextCn}
                                                                    onChange={(e) => {
                                                                        updateTechField('video_prompt_cn', e.target.value);
                                                                    }}
                                                                />
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                    {t('英文提示词', 'Prompt (EN)')}
                                                                </div>
                                                                <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                    className="w-full h-32 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                    value={videoPromptTextEn}
                                                                    onChange={(e) => {
                                                                        setEditingShot({ ...editingShot, ...buildVideoPromptEnUpdates(e.target.value) });
                                                                    }}
                                                                />
                                                                <div className="flex items-center gap-2 mt-2 mb-4">
                                                                    {renderDetailActionButton({
                                                                        label: t('翻译成中文', 'To Chinese'),
                                                                        busyLabel: t('翻译中...', 'Translating...'),
                                                                        onClick: () => translateFieldToChinese('video'),
                                                                        disabled: translatingPromptField.startsWith('video:'),
                                                                        busy: translatingPromptField === 'video:to-cn',
                                                                        variant: 'warning'
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('翻译成英文', 'To English'),
                                                                        busyLabel: t('翻译中...', 'Translating...'),
                                                                        onClick: () => translateFieldToEnglish('video'),
                                                                        disabled: translatingPromptField.startsWith('video:'),
                                                                        busy: translatingPromptField === 'video:to-en',
                                                                        variant: 'secondary'
                                                                    })}
                                                                </div>
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => { persistEditingShotUpdates(updates); }} title={t('参考图', 'Refs')} promptText={`${getShotVideoPromptEn(editingShot) || ''}\n${(() => { try { return String(JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''); } catch (e) { return ''; } })()}`} uiLang={uiLang} onPickMedia={openMediaPicker} storageKey="video_ref_image_urls" strictPromptOnly={resolveVideoModeFromTech(tech) !== 'entity_refs'} />
                                                                {renderGenerationHistoryPanel()}
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                return (
                                                    <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                        <div className="space-y-3">
                                                            <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex items-center justify-center">
                                                                {keyframe?.url ? <SafeImage src={keyframe.url} className="max-w-full max-h-full object-contain" fallback={<ImageIcon className="w-8 h-8 opacity-30" />} /> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                            </div>
                                                            {renderInfoPanel(t('当前素材信息', 'Current Asset Info'), [
                                                                { label: t('关键帧时间', 'Keyframe Time'), value: keyframe?.time || '-' },
                                                                { label: t('关键帧 URL', 'Keyframe URL'), value: keyframe?.url || '-', breakAll: true },
                                                            ])}
                                                            {renderAssetMetaPanel()}
                                                        </div>
                                                        <div className="space-y-3">
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <input className="bg-black/30 border border-white/10 rounded px-2 py-1 text-xs w-20" value={keyframe?.time || ''} onChange={(e) => {
                                                                    const updated = [...localKeyframes];
                                                                    if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                    updated[assetDetailModal.keyframeIndex].time = e.target.value;
                                                                    setLocalKeyframes(updated);
                                                                }} />
                                                                {renderDetailActionButton({
                                                                    label: t('生成关键帧', 'Generate Keyframe'),
                                                                    busyLabel: t('关键帧生成中...', 'Generating Keyframe...'),
                                                                    onClick: () => generateAssetWithLang('keyframe', assetDetailModal.keyframeIndex, { cfg: currentImageCfgValue }),
                                                                    disabled: !!keyframe?.loading || currentShotGenerating,
                                                                    busy: !!keyframe?.loading || currentShotGenerating,
                                                                    variant: 'primary',
                                                                })}
                                                                {renderPromptLangMenu('keyframe')}
                                                                {renderDetailActionButton({
                                                                    label: t('翻译成中文', 'To Chinese'),
                                                                    busyLabel: t('翻译中...', 'Translating...'),
                                                                    onClick: () => translateKeyframeToChinese(assetDetailModal.keyframeIndex),
                                                                    disabled: translatingPromptField.startsWith(`keyframe:${assetDetailModal.keyframeIndex}:`),
                                                                    busy: translatingPromptField === `keyframe:${assetDetailModal.keyframeIndex}:to-cn`,
                                                                    variant: 'warning',
                                                                })}
                                                                {renderDetailActionButton({
                                                                    label: t('翻译成英文', 'To English'),
                                                                    busyLabel: t('翻译中...', 'Translating...'),
                                                                    onClick: () => translateKeyframeToEnglish(assetDetailModal.keyframeIndex),
                                                                    disabled: translatingPromptField.startsWith(`keyframe:${assetDetailModal.keyframeIndex}:`),
                                                                    busy: translatingPromptField === `keyframe:${assetDetailModal.keyframeIndex}:to-en`,
                                                                    variant: 'secondary',
                                                                })}
                                                            </div>
                                                            <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('英文提示词', 'Prompt (EN)')}</div>
                                                            <PromptMentionTextarea entities={entities} uiLang={uiLang} className="w-full h-56 bg-black/30 border border-white/10 rounded p-3 text-sm" value={keyframe?.prompt || ''} onChange={(e) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].prompt = e.target.value;
                                                                setLocalKeyframes(updated);
                                                            }} />
                                                            <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('中文对照提示词', 'Prompt (CN)')}</div>
                                                            <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                className="w-full h-48 bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                value={(tech.keyframe_prompt_cn_map && keyframe?.time) ? (tech.keyframe_prompt_cn_map[keyframe.time] || '') : ''}
                                                                onChange={(e) => {
                                                                    const nextMap = { ...(tech.keyframe_prompt_cn_map || {}) };
                                                                    if (keyframe?.time) nextMap[keyframe.time] = e.target.value;
                                                                    updateTechField('keyframe_prompt_cn_map', nextMap);
                                                                }}
                                                                placeholder={t('填写关键帧中文对照提示词...', 'Add Chinese counterpart prompt for keyframe...')}
                                                            />
                                                            <RefineControl originalText={keyframe?.prompt || ''} onUpdate={(v) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].prompt = v;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }} type="image" currentImage={keyframe?.url || ''} onImageUpdate={(url) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].url = url;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }} projectId={projectId} shotId={editingShot.id} assetType={`keyframe_${assetDetailModal.keyframeIndex}`} featureInjector={injectEntityFeatures} onPickMedia={openMediaPicker} />
                                                            {imageCfgControl}
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>

                                        <div className="p-4 border-t border-white/10 flex items-center justify-end gap-2 bg-black/20">
                                            <button onClick={closeAssetDetailModal} className="px-4 py-2 rounded hover:bg-white/10 text-sm">{t('关闭', 'Close')}</button>
                                            <button
                                                onClick={async () => {
                                                    try {
                                                        if (assetDetailModal.type === 'keyframe') {
                                                            await reconstructKeyframes(localKeyframes);
                                                        } else {
                                                            const patch = buildAssetDetailSavePatch(editingShot, assetDetailModal.type);
                                                            if (Object.keys(patch).length > 0) {
                                                                await onUpdateShot(editingShot.id, patch);
                                                            }
                                                        }
                                                        onLog?.(t('详情修改已保存', 'Detail changes saved'), 'success');
                                                        closeAssetDetailModal();
                                                    } catch (e) {
                                                        onLog?.(t('保存失败', 'Save failed'), 'error');
                                                    }
                                                }}
                                                className="px-4 py-2 rounded bg-primary text-black font-bold hover:bg-primary/90 text-sm"
                                            >
                                                {t('保存', 'Save')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {frameTrimModal.open && (
                                <div className="fixed inset-0 z-[130] bg-black/85 backdrop-blur-sm flex items-center justify-center p-4">
                                    <div className="w-full max-w-5xl bg-[#09090b] border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col">
                                        <div className="p-4 border-b border-white/10 flex items-center justify-between">
                                            <div>
                                                <h4 className="font-bold text-white flex items-center gap-2">
                                                    <Crop className="w-4 h-4 text-primary" />
                                                    {frameTrimModal.type === 'end'
                                                        ? t('结束帧裁边', 'End Frame Trim')
                                                        : t('起始帧裁边', 'Start Frame Trim')}
                                                </h4>
                                                <div className="text-xs text-muted-foreground mt-1">
                                                    {t('调整四边裁切比例，保存后会生成新素材并自动回填当前帧。', 'Adjust the trim on each edge. Saving will create a new asset and apply it to the current frame.')}
                                                </div>
                                            </div>
                                            <button
                                                onClick={frameTrimModal.saving ? undefined : closeFrameTrimModal}
                                                disabled={frameTrimModal.saving}
                                                className="p-2 hover:bg-white/10 rounded-full disabled:opacity-50"
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>

                                        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_380px] gap-0">
                                            <div className="p-4 border-b xl:border-b-0 xl:border-r border-white/10 bg-black/30">
                                                <div className="relative min-h-[420px] h-[52vh] rounded-lg border border-white/10 bg-black/60 overflow-hidden flex items-center justify-center">
                                                    <img
                                                        src={getFullUrl(frameTrimModal.sourceUrl)}
                                                        alt={frameTrimModal.type === 'end' ? 'End frame trim preview' : 'Start frame trim preview'}
                                                        className="max-w-full max-h-full object-contain"
                                                    />
                                                    <div
                                                        className="absolute border-2 border-primary shadow-[0_0_0_9999px_rgba(0,0,0,0.62)] transition-all duration-150"
                                                        style={{
                                                            top: `${normalizeFrameTrimMargins(frameTrimModal).topPct}%`,
                                                            right: `${normalizeFrameTrimMargins(frameTrimModal).rightPct}%`,
                                                            bottom: `${normalizeFrameTrimMargins(frameTrimModal).bottomPct}%`,
                                                            left: `${normalizeFrameTrimMargins(frameTrimModal).leftPct}%`,
                                                        }}
                                                    />
                                                </div>
                                            </div>

                                            <div className="p-4 space-y-4 bg-[#101012]">
                                                <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-white/80 space-y-2">
                                                    <div className="font-semibold text-white">{t('当前裁切结果', 'Current Trim Result')}</div>
                                                    <div>{t('保留宽度', 'Remaining Width')}: {normalizeFrameTrimMargins(frameTrimModal).widthPct.toFixed(1)}%</div>
                                                    <div>{t('保留高度', 'Remaining Height')}: {normalizeFrameTrimMargins(frameTrimModal).heightPct.toFixed(1)}%</div>
                                                </div>

                                                {[
                                                    ['topPct', t('上边', 'Top')],
                                                    ['rightPct', t('右边', 'Right')],
                                                    ['bottomPct', t('下边', 'Bottom')],
                                                    ['leftPct', t('左边', 'Left')],
                                                ].map(([key, label]) => (
                                                    <div key={key} className="space-y-2">
                                                        <div className="flex items-center justify-between text-xs">
                                                            <span className="text-white/85 font-medium">{label}</span>
                                                            <span className="text-primary font-mono">{clampFrameTrimPercent(frameTrimModal[key]).toFixed(1)}%</span>
                                                        </div>
                                                        <input
                                                            type="range"
                                                            min="0"
                                                            max="45"
                                                            step="0.5"
                                                            value={clampFrameTrimPercent(frameTrimModal[key])}
                                                            onChange={(e) => updateFrameTrimMargin(key, e.target.value)}
                                                            disabled={frameTrimModal.saving}
                                                            className="w-full accent-primary"
                                                        />
                                                    </div>
                                                ))}

                                                <div className="grid grid-cols-2 gap-2 pt-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => setFrameTrimModal((prev) => ({ ...prev, topPct: 0, rightPct: 0, bottomPct: 0, leftPct: 0 }))}
                                                        disabled={frameTrimModal.saving}
                                                        className="px-3 py-2 rounded-md bg-white/10 hover:bg-white/20 text-sm text-white/85 disabled:opacity-50"
                                                    >
                                                        {t('重置', 'Reset')}
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={applyFrameTrimToShot}
                                                        disabled={frameTrimModal.saving}
                                                        className="px-3 py-2 rounded-md bg-primary text-black font-bold text-sm hover:bg-primary/90 disabled:opacity-60"
                                                    >
                                                        {frameTrimModal.saving ? t('保存中...', 'Saving...') : t('保存并回填', 'Save and Apply')}
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
             </AnimatePresence>

             {shotPromptModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary"/> Generate AI Shots</h3>
                            <button onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {shotPromptModal.loading && !shotPromptModal.data ? (
                                <div className="flex items-center justify-center h-40"><Loader2 className="animate-spin text-primary" size={32}/></div>
                            ) : (
                                <>
                                    <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-xs text-blue-200 flex items-start gap-2">
                                        <Info size={14} className="shrink-0 mt-0.5" />
                                        Review and edit the prompt before generation. Only the User Prompt (scenario context) is typically edited.
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">{t('用户提示词（场景内容）', 'User Prompt (Scenario content)')}</label>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono h-64 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.user_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, user_prompt: e.target.value}}))}
                                        />
                                    </div>
                                    
                                     <div className="flex flex-col gap-2">
                                         <div className="flex items-center justify-between">
                                              <label className="text-xs font-bold text-muted-foreground uppercase">{t('系统提示词（指令）', 'System Prompt (Instructions)')}</label>
                                              <span className="text-xs text-muted-foreground px-2 py-1 bg-white/5 rounded">{t('默认/模板', 'Default/Template')}</span>
                                         </div>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono h-32 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.system_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, system_prompt: e.target.value}}))}
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                        
                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button 
                                onClick={() => {
                                    const full = (shotPromptModal.data?.system_prompt || '') + "\n\n" + (shotPromptModal.data?.user_prompt || '');
                                    navigator.clipboard.writeText(full);
                                    onLog?.(t('完整提示词已复制到剪贴板', 'Full prompt copied to clipboard'), "success");
                                }}
                                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-medium flex items-center gap-2 mr-auto"
                            >
                                <Copy size={16}/> {t('复制完整提示词', 'Copy Full Prompt')}
                            </button>
                            <button 
                                onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button 
                                onClick={handleConfirmGenerateShots}
                                disabled={shotPromptModal.loading}
                                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotPromptModal.loading ? <Loader2 className="animate-spin" size={16}/> : <Wand2 size={16}/>}
                                {shotPromptModal.loading ? t('生成中...', 'Generating...') : t('生成镜头', 'Generate Shots')}
                            </button>
                        </div>

                        <div className="mt-2 flex items-center gap-2">
                            <input
                                type="text"
                                value={sceneCodeFilter}
                                onChange={(e) => setSceneCodeFilter(e.target.value)}
                                placeholder={t('筛选场景编码（EPxx_SCyy）', 'Filter Scene Code (EPxx_SCyy)')}
                                className="bg-black/40 border border-white/20 rounded px-2.5 py-1.5 text-xs min-w-[200px] text-white"
                            />
                            <input
                                type="text"
                                value={shotIdFilter}
                                onChange={(e) => setShotIdFilter(e.target.value)}
                                placeholder={t('筛选镜头ID（EPxx_SCyy_SHzz）', 'Filter Shot ID (EPxx_SCyy_SHzz)')}
                                className="bg-black/40 border border-white/20 rounded px-2.5 py-1.5 text-xs w-full sm:w-auto sm:min-w-[220px] text-white"
                            />
                            <button
                                onClick={() => { setSceneCodeFilter(''); setShotIdFilter(''); }}
                                className="px-2.5 py-1.5 bg-white/10 hover:bg-white/20 rounded text-[11px] text-white border border-white/10"
                            >
                                {t('清除镜头筛选', 'Clear Shot Filters')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {voicePromptConfirmModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary" />{t('仅生成配音（超级用户确认）', 'Voice-Only Generation (Superuser Confirmation)')}</h3>
                            <button
                                onClick={() => setVoicePromptConfirmModal({ open: false, shotId: null, prompt: '', systemPrompt: '', loadingSystemPrompt: false, languageCode: '', projectLanguage: '', submitting: false })}
                                disabled={voicePromptConfirmModal.submitting}
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                            <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-xs text-blue-200 flex items-start gap-2">
                                <Info size={14} className="shrink-0 mt-0.5" />
                                {t('超级用户模式：请确认或编辑配音提示词，确认后再提交。', 'Superuser mode: review or edit the voice prompt before submitting.')}
                            </div>
                            <div className="text-xs text-muted-foreground">
                                {t('语言代码', 'Language Code')}: {voicePromptConfirmModal.languageCode || '-'}
                            </div>
                            <div className="flex flex-col gap-2">
                                <label className="text-xs font-bold text-muted-foreground uppercase">{t('系统提示词（配音规划）', 'System Prompt (Voice Planner)')}</label>
                                <textarea
                                    className="w-full min-h-[180px] bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono focus:outline-none focus:border-primary/50 resize-y"
                                    value={voicePromptConfirmModal.systemPrompt}
                                    onChange={(e) => setVoicePromptConfirmModal((prev) => ({ ...prev, systemPrompt: e.target.value }))}
                                    disabled={voicePromptConfirmModal.submitting || voicePromptConfirmModal.loadingSystemPrompt}
                                />
                            </div>
                            {voicePromptConfirmModal.loadingSystemPrompt && (
                                <div className="text-xs text-blue-300">{t('正在加载系统提示词模板...', 'Loading system prompt template...')}</div>
                            )}
                            <textarea
                                className="w-full min-h-[260px] bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono focus:outline-none focus:border-primary/50 resize-y"
                                value={voicePromptConfirmModal.prompt}
                                onChange={(e) => setVoicePromptConfirmModal((prev) => ({ ...prev, prompt: e.target.value }))}
                                disabled={voicePromptConfirmModal.submitting}
                            />
                        </div>

                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button
                                onClick={() => setVoicePromptConfirmModal({ open: false, shotId: null, prompt: '', systemPrompt: '', loadingSystemPrompt: false, languageCode: '', projectLanguage: '', submitting: false })}
                                disabled={voicePromptConfirmModal.submitting}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                onClick={async () => {
                                    const targetShotId = voicePromptConfirmModal.shotId;
                                    const shot = (editingShot && editingShot.id === targetShotId)
                                        ? editingShot
                                        : (shots || []).find((item) => item?.id === targetShotId);
                                    if (!shot) {
                                        showNotification(t('未找到镜头，无法提交配音生成', 'Shot not found, cannot submit voice generation'), 'error');
                                        return;
                                    }

                                    const promptText = String(voicePromptConfirmModal.prompt || '').trim();
                                    if (!promptText) {
                                        showNotification(t('提示词为空，请先填写', 'Prompt is empty, please fill it first'), 'warning');
                                        return;
                                    }

                                    setVoicePromptConfirmModal((prev) => ({ ...prev, submitting: true }));
                                    try {
                                        await submitVoiceoverOnly({
                                            shot,
                                            voicePrompt: promptText,
                                            plannerSystemPrompt: String(voicePromptConfirmModal.systemPrompt || '').trim(),
                                            languageCode: voicePromptConfirmModal.languageCode,
                                            projectLanguage: voicePromptConfirmModal.projectLanguage,
                                        });
                                        setVoicePromptConfirmModal({ open: false, shotId: null, prompt: '', systemPrompt: '', loadingSystemPrompt: false, languageCode: '', projectLanguage: '', submitting: false });
                                    } finally {
                                        setVoicePromptConfirmModal((prev) => (prev.open ? { ...prev, submitting: false } : prev));
                                    }
                                }}
                                disabled={voicePromptConfirmModal.submitting}
                                className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {voicePromptConfirmModal.submitting ? <Loader2 className="animate-spin" size={16} /> : <Wand2 size={16} />}
                                {voicePromptConfirmModal.submitting ? t('提交中...', 'Submitting...') : t('确认并生成配音', 'Confirm and Generate Voiceover')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {shotReviewModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-[90vw] h-[90vh] flex flex-col shadow-2xl">
                         <div className="p-4 border-b border-white/10 flex justify-between items-center bg-black/40">
                            <h3 className="font-bold flex items-center gap-2"><TableIcon size={16} className="text-primary"/> {t('审核 AI 生成镜头', 'Review AI Generated Shots')}</h3>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground bg-yellow-500/10 text-yellow-500 px-2 py-1 rounded">{t('暂存区', 'Staging Area')}</span>
                                <button onClick={() => setShotReviewModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                            </div>
                        </div>
                        
                        <div className="flex-1 overflow-hidden relative bg-[#121212]">
                            <div className="absolute inset-0 overflow-auto p-4 custom-scrollbar">
                                <div className="md:hidden space-y-3">
                                    {(shotReviewModal.data || []).map((shot, idx) => (
                                        <div key={`review-mobile-${idx}`} className="bg-white/5 border border-white/10 rounded-lg p-3 space-y-2.5">
                                            <div className="text-[11px] font-bold text-white/90 truncate">
                                                {(shot['Shot ID'] || shot.shot_id || `#${idx + 1}`)} · {(shot['Shot Name'] || shot.shot_name || t('未命名镜头', 'Untitled Shot'))}
                                            </div>
                                            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{t('内容', 'Content')}</div>
                                            <PromptMentionTextarea entities={entities} uiLang={uiLang} className="w-full bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px] min-h-[88px]" value={shot["Video Content"] || shot.video_content || ''} onChange={e => {
                                                const newData = [...shotReviewModal.data];
                                                newData[idx] = { ...shot, "Video Content": e.target.value };
                                                setShotReviewModal(prev => ({...prev, data: newData}));
                                            }} placeholder={t('内容', 'Content')} />
                                            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{t('基础字段', 'Basic Fields')}</div>
                                            <div className="grid grid-cols-2 gap-2">
                                                <input className="bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px]" value={shot["Duration (s)"] || shot.duration || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Duration (s)": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} placeholder={t('时长', 'Duration')} />
                                                <input className="bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px]" value={shot["Shot Logic (CN)"] || shot.shot_logic_cn || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot Logic (CN)": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} placeholder={t('逻辑', 'Logic')} />
                                            </div>
                                            <button onClick={() => {
                                                const newData = shotReviewModal.data.filter((_, i) => i !== idx);
                                                setShotReviewModal(prev => ({...prev, data: newData}));
                                            }} className="w-full px-2 py-2.5 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-200 text-[12px] font-semibold">{t('删除', 'Delete')}</button>
                                        </div>
                                    ))}
                                </div>
                                <table className="hidden md:table w-full min-w-[900px] text-xs text-left border-collapse">
                                    <thead className="sticky top-0 bg-[#252525] z-10 shadow-md">
                                        <tr>
                                            <th className="p-2 border-b border-white/10 font-bold text-white/70">{t('镜头 ID', 'Shot ID')}</th>
                                            <th className="p-2 border-b border-white/10 font-bold text-white/70">{t('镜头名称', 'Shot Name')}</th>
                                            <th className="p-2 border-b border-white/10 font-bold text-white/70">{t('内容', 'Content')}</th>
                                            <th className="p-2 border-b border-white/10 font-bold text-white/70">{t('时长', 'Duration')}</th>
                                            <th className="hidden md:table-cell p-2 border-b border-white/10 font-bold text-white/70">{t('关联实体', 'Entities')}</th>
                                            <th className="hidden md:table-cell p-2 border-b border-white/10 font-bold text-white/70">{t('逻辑', 'Logic')}</th>
                                            <th className="hidden lg:table-cell p-2 border-b border-white/10 font-bold text-white/70">{t('关键帧', 'Keyframes')}</th>
                                            <th className="p-2 border-b border-white/10 w-10"></th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {(shotReviewModal.data || []).map((shot, idx) => (
                                            <tr key={idx} className="hover:bg-white/5 group">
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Shot ID"] || shot.shot_id || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot ID": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Shot Name"] || shot.shot_name || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot Name": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1"><textarea className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded resize-y min-h-[40px]" value={shot["Video Content"] || shot.video_content || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Video Content": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1 w-20"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Duration (s)"] || shot.duration || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Duration (s)": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="hidden md:table-cell p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Associated Entities"] || shot.associated_entities || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Associated Entities": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="hidden md:table-cell p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Shot Logic (CN)"] || shot.shot_logic_cn || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Shot Logic (CN)": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="hidden lg:table-cell p-1"><input className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded" value={shot["Keyframes"] || shot.keyframes || ''} onChange={e => {
                                                    const newData = [...shotReviewModal.data];
                                                    newData[idx] = { ...shot, "Keyframes": e.target.value };
                                                    setShotReviewModal(prev => ({...prev, data: newData}));
                                                }} /></td>
                                                <td className="p-1 text-center">
                                                    <button onClick={() => {
                                                        const newData = shotReviewModal.data.filter((_, i) => i !== idx);
                                                        setShotReviewModal(prev => ({...prev, data: newData}));
                                                    }} className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500"><Trash2 size={14}/></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                  <button onClick={() => {
                                     const newData = [...(shotReviewModal.data || []), { "Shot ID": (shotReviewModal.data?.length||0)+1, "Video Content": "" }];
                                     setShotReviewModal(prev => ({...prev, data: newData}));
                                }} className="mt-4 w-full md:w-auto px-3 py-2 bg-white/5 hover:bg-white/10 rounded flex items-center justify-center gap-2 text-xs font-semibold">
                                    <Plus size={14}/> {t('新增一行', 'Add Row')}
                                </button>
                            </div>
                        </div>

                        <div className="p-4 border-t border-white/10 flex flex-col sm:flex-row justify-end gap-3 bg-black/20">
                             <button
                                onClick={async () => {
                                    try {
                                        await updateSceneLatestAIResult(shotReviewModal.sceneId, shotReviewModal.data);
                                        onLog?.(t('暂存草稿已保存。', 'Staged draft saved.'), "success");
                                    } catch(e) {
                                        onLog?.(t('保存草稿失败。', 'Failed to save draft.'), "error");
                                    }
                                }}
                                className="w-full sm:w-auto px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm font-medium"
                            >
                                {t('保存草稿', 'Save Draft')}
                            </button>
                             <button 
                                onClick={async () => {
                                    if(!await confirmUiMessage(t('应用这些镜头吗？这会替换现有镜头。', 'Apply these shots? This will replace existing shots.'))) return;
                                    setShotReviewModal(prev => ({...prev, loading: true}));
                                    try {
                                        await applySceneAIResult(shotReviewModal.sceneId, { content: shotReviewModal.data });
                                        onLog?.(t('镜头已应用到数据库。', 'Shots applied to database.'), "success");
                                        setShotReviewModal({open: false, sceneId: null, data: null, loading: false});
                                        if (typeof refreshShots === 'function') refreshShots();
                                    } catch(e) {
                                        onLog?.(t('应用镜头失败: ', 'Failed to apply shots: ') + e.message, "error");
                                        setShotReviewModal(prev => ({...prev, loading: false}));
                                    }
                                }}
                                disabled={shotReviewModal.loading}
                                className="w-full sm:w-auto px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm font-medium flex items-center justify-center gap-2"
                            >
                                {shotReviewModal.loading ? <Loader2 className="animate-spin" size={16}/> : <CheckCircle size={16}/>}
                                {t('应用到场景', 'Apply to Scene')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isSettingsOpen && (
                 <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-8">
                     <div className="bg-[#09090b] w-full max-w-6xl h-[90vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col relative overflow-hidden">
                          <button 
                             onClick={() => setIsSettingsOpen(false)}
                             className="absolute top-4 right-4 z-50 p-2 bg-black/60 rounded-full hover:bg-white/10 text-white border border-white/10"
                             title={t('关闭设置', 'Close Settings')}
                         >
                             <X size={20}/>
                         </button>
                         <div className="flex-1 overflow-auto custom-scrollbar">
                             <SettingsPage />
                         </div>
                     </div>
                 </div>
             )}
        </div>
    );
};
