

import PromptMentionTextarea from './PromptMentionTextarea';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import TunePromptAgentModal from "./TunePromptAgentModal";
import { MediaPickerModal, MediaDetailModal } from './MediaModals';
import { ImportModal } from './ImportModal';
import {
    cleanMarkdownTableCells,
    reconcileShotTableRowCells,
    buildShotTableHeaderMap,
    dedupeShotsForDisplay,
    dedupeShotRowsForImport,
} from '../../../lib/sceneTableParser';
import {
    buildShotWritePayloadFromRow,
    findStagingRowByShotId,
    resolveAiShotsStagingRows,
} from '../../../lib/aiShotStagingHelpers';
import FunctionApiSelector from '../../../components/FunctionApiSelector';
import { useFunctionApis } from '../../../components/useFunctionApis';
import { ReferenceManager } from './SceneManager';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../../../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../../../lib/store';
import LogPanel from '../../../components/LogPanel';
import ProjectStatusBar from '../../../components/ProjectStatusBar';
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, CheckCircle2, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, Cpu, Timer, Scissors, RotateCcw, CaptionsOff, VolumeX, Eraser } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL, ASSET_BASE_URL } from '../../../config';
import { setUiLang as setGlobalUiLang } from '../../../lib/uiLang';

import {
    getFullUrl, getMediaUrlWithFallback, canFallbackToAssetProxy, createInitialFrameTrimState, clampFrameTrimPercent, normalizeFrameTrimMargins, brokenMediaUrls, brokenSceneImageUrls, warmMediaUrls, shouldBypassBrokenMediaCache, rememberBrokenMediaUrl, isBrokenMediaUrl, clearBrokenMediaUrl, rememberWarmMediaUrl, isWarmMediaUrl, getSafeMediaUrl, extractImageJobResultUrl, rememberBrokenSceneImageUrl, isBrokenSceneImageUrl, normalizeBatchParallelLimit, normalizeAsciiSubjectSeparatorsForDeps, normalizeSubjectNameForDeps, normalizeSubjectKeyForDeps, normalizeAsciiSubjectSeparators, normalizeSubjectName, normalizeSubjectKey, normalizeImportSubjectKey, IMG_PLACEHOLDER_SRC, parseVisualDependencies, SafeImage, SafeAudio, normalizeMediaRefList, areMediaRefListsEqual, pickBestEntityMatch, collectMatchedEntitiesFromPrompt, collectMatchedEntityImageUrlsFromPrompt, buildShotVideoRefPromptText, buildShotVideoEntityRefSlots, getMissingShotVideoEntityRefSlots, SCENE_SUBJECT_TYPE_LABELS, getSceneSubjectStatusKey, splitSceneSubjectNames, normalizeSceneSubjectDefaultType, parseTypedSceneSubjectToken, extractSceneSubjectRefsFromField, buildSceneSubjectNameCandidates, extractSceneSubjectRefs, findMatchingEntityByType, findMissingSceneSubjectRefs, findCrossTypeEntityMatches, buildSceneSubjectPlaceholderPayload, createMissingSceneSubjectPlaceholders, collectMatchedSubjectImageUrlsFromPrompt, resolveUnifiedVideoMode, ensureShotDefaultVideoMode, buildAutoVideoRefList, resolveShotVideoActiveRefs, buildShotVideoSubmitRefsFromActiveRefs, isVideoMediaRefUrl, resolveShotVideoPosterUrl, LazyHoverVideo, InViewVideo, ManagedVideoPlayer, parseEpisodeNumberFromText, normalizeEpisodeTitleForDisplay, buildEntityNegativePrompt, normalizeImageSizeOption, normalizeAspectRatioOption, parseAspectRatioParts, parseAspectRatioValue, reduceAspectRatioParts, buildAspectRatioString, inferImageSizeFromResolution, getEpisodePreferredImageSize, getEpisodePreferredAspectRatio, getProjectPreferredImageSize, getProjectPreferredAspectRatio, buildShotDiptychPlan, buildMultiPanelGridPlan, buildMultiPanelAspectContract, getShotDiptychLayoutLabel, buildShotDiptychLayoutInstruction, buildShotDiptychAspectContract, getShotDiptychSeamTrimPx, getShotDiptychSeamBiasPx, getShotDiptychFallbackCropPx, JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION, SHOT_FRAME_ASSET_UPLOAD_VERSION, hashStableText, buildJointShotDiptychUploadIdempotencyKey, buildShotFrameAssetUploadIdempotencyKey, collectSupportedAspectRatioOptions, collectSupportedImageSizeOptions, selectBestShotDiptychRequestAspectRatio, selectBestMultiPanelRequestAspectRatio, selectBestSupportedImageSize, resolveShotPanelExportResolution, resolveShotDiptychRequestResolution, getResolutionByAspectAndImageSize, SHOT_IMAGE_CFG_MIN, SHOT_IMAGE_CFG_MAX, SHOT_IMAGE_CFG_STEP, SHOT_IMAGE_CFG_FALLBACK, clampShotImageCfg, resolveShotImageCfgDefault, extractDialogueOnlyFromPrompt, inferLanguageCodeFromProjectLanguage, buildVoicePromptWithEntityContext, buildEpisodeDisplayLabel, isEphemeralProviderMediaUrl, isDurablePersistedMediaUrl, shotVideoNeedsOssPersist, shotStartFrameNeedsOssPersist, shotEndFrameNeedsOssPersist, shotNeedsAnyOssPersist, shotNeedsAnyOssPersistGraceWaitMs, getShotVideoMediaBoundAtMs, extractVideoJobResultUrl, mergeShotVideoOssPersistState, isShotVideoOssPersistComplete, EPHEMERAL_VIDEO_OSS_SYNC_MAX_MS, EPHEMERAL_VIDEO_OSS_SYNC_INTERVAL_MS, EPHEMERAL_VIDEO_OSS_AUTO_RETRY_MIN_AGE_MS,     resolveShotMediaSlotUrl, mediaUrlNeedsOssPersist,     parseShotTechnicalNotes, DEFAULT_VIDEO_REFERENCE_SLOT_LIMIT, useTabMediaRefreshEffect, TabMediaRefreshButton, useMediaReloadTick, triggerMediaReload
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
    backfillEpisodeMediaFromLibrary,
    persistShotMedia,
    cleanupShotVideo,
    getCachedUserPreferences,
    getDraftModePreference,
    markAssetAsCurrentProjectAsset,
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
    isSeedance2VideoBaseModel,
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

const MULTI_PANEL_PRESET_OPTIONS = [
    { key: '2panel', filename: 'multi_panel_image_preset_2panel.txt', labelZh: '二画格', labelEn: '2-Panel', columns: 2, rows: 1 },
    { key: '4panel', filename: 'multi_panel_image_preset_4panel.txt', labelZh: '四画格', labelEn: '4-Panel', columns: 2, rows: 2 },
    { key: '6panel', filename: 'multi_panel_image_preset_6panel.txt', labelZh: '六画格', labelEn: '6-Panel', columns: 3, rows: 2 },
    { key: '9panel', filename: 'multi_panel_image_preset_9panel.txt', labelZh: '九画格', labelEn: '9-Panel', columns: 3, rows: 3 },
];

const MULTI_PANEL_PRESET_FALLBACKS = {
    '2panel': {
        cn: '生成一张 1x2 排布、包含 2 个连续画面的多画格叙事图。两格需保持同一主体、服装、场景与镜头语言连续，展示该镜头从起始到结束的关键瞬间。画面顺序必须明确为从左到右（1→2），并在每一格上方清晰标注对应阿拉伯数字（1、2）。必须严格按照提示词给出的时序与运镜逻辑推进，不得跳时、倒序、并行错序或随意改写镜头运动方向。除这些数字外，不要添加标题、对白气泡、说明文字或无关装饰。',
        en: 'Generate a 1x2 multi-panel narrative image with 2 sequential panels. Keep the same subject, wardrobe, scene, and cinematic language across both panels, showing the shot from opening to closing beat. The panel order must be explicit left-to-right (1->2), and place a clear Arabic numeral above each panel (1, 2). You must strictly follow the prompt\'s timeline and camera-movement logic, with no time skips, reversed order, parallel mis-ordering, or arbitrary changes to camera direction. Do not add titles, speech bubbles, captions, or unrelated decorations beyond these numeric labels.',
    },
    '4panel': {
        cn: '生成一张 2x2 排布、包含 4 个连续画面的多画格叙事图。四格需保持同一主体、服装、场景与镜头语言连续，展示该镜头的关键动作推进。画面顺序必须明确为从左到右、从上到下（1→2→3→4），并在每一格上方清晰标注对应阿拉伯数字（1、2、3、4）。必须严格按照提示词给出的时序与运镜逻辑推进，不得跳时、倒序、并行错序或随意改写镜头运动方向。除这些数字外，不要添加标题、对白气泡、说明文字或无关装饰。',
        en: 'Generate a 2x2 multi-panel narrative image with 4 sequential panels. Keep the same subject, wardrobe, scene, and cinematic language across all panels, showing the key action progression for this shot. The panel order must be explicit in reading order (left-to-right, top-to-bottom: 1->2->3->4), and place a clear Arabic numeral above each panel (1, 2, 3, 4). You must strictly follow the prompt\'s timeline and camera-movement logic, with no time skips, reversed order, parallel mis-ordering, or arbitrary changes to camera direction. Do not add titles, speech bubbles, captions, or unrelated decorations beyond these numeric labels.',
    },
    '6panel': {
        cn: '生成一张 3x2 排布、包含 6 个连续画面的多画格叙事图。六格需保持同一主体、服装、场景与镜头语言连续，清晰展示该镜头从起势、动作发展到收束的过程。画面顺序必须明确为从左到右、从上到下（1→2→3→4→5→6），并在每一格上方清晰标注对应阿拉伯数字（1、2、3、4、5、6）。必须严格按照提示词给出的时序与运镜逻辑推进，不得跳时、倒序、并行错序或随意改写镜头运动方向。除这些数字外，不要添加标题、对白气泡、说明文字或无关装饰。',
        en: 'Generate a 3x2 multi-panel narrative image with 6 sequential panels. Keep the same subject, wardrobe, scene, and cinematic language across all panels, clearly showing the shot progression from setup to action development to resolution. The panel order must be explicit in reading order (left-to-right, top-to-bottom: 1->2->3->4->5->6), and place a clear Arabic numeral above each panel (1, 2, 3, 4, 5, 6). You must strictly follow the prompt\'s timeline and camera-movement logic, with no time skips, reversed order, parallel mis-ordering, or arbitrary changes to camera direction. Do not add titles, speech bubbles, captions, or unrelated decorations beyond these numeric labels.',
    },
    '9panel': {
        cn: '生成一张 3x3 排布、包含 9 个连续画面的多画格叙事图。九格需保持同一主体、服装、场景与镜头语言连续，完整展示该镜头的节奏、动作变化与情绪推进。画面顺序必须明确为从左到右、从上到下（1→2→3→4→5→6→7→8→9），并在每一格上方清晰标注对应阿拉伯数字（1、2、3、4、5、6、7、8、9）。必须严格按照提示词给出的时序与运镜逻辑推进，不得跳时、倒序、并行错序或随意改写镜头运动方向。除这些数字外，不要添加标题、对白气泡、说明文字或无关装饰。',
        en: 'Generate a 3x3 multi-panel narrative image with 9 sequential panels. Keep the same subject, wardrobe, scene, and cinematic language across all panels, fully showing the shot rhythm, action changes, and emotional progression. The panel order must be explicit in reading order (left-to-right, top-to-bottom: 1->2->3->4->5->6->7->8->9), and place a clear Arabic numeral above each panel (1, 2, 3, 4, 5, 6, 7, 8, 9). You must strictly follow the prompt\'s timeline and camera-movement logic, with no time skips, reversed order, parallel mis-ordering, or arbitrary changes to camera direction. Do not add titles, speech bubbles, captions, or unrelated decorations beyond these numeric labels.',
    },
};

const normalizeMultiPanelPresetKey = (value) => {
    const raw = String(value || '').trim();
    return MULTI_PANEL_PRESET_OPTIONS.some((item) => item.key === raw) ? raw : '4panel';
};

const getMultiPanelPresetOption = (value) => {
    const stableKey = normalizeMultiPanelPresetKey(value);
    return MULTI_PANEL_PRESET_OPTIONS.find((item) => item.key === stableKey) || MULTI_PANEL_PRESET_OPTIONS[0];
};

const getMultiPanelPresetFallbackInstruction = (value, lang = 'cn') => {
    const stableKey = normalizeMultiPanelPresetKey(value);
    const stableLang = lang === 'en' ? 'en' : 'cn';
    return MULTI_PANEL_PRESET_FALLBACKS[stableKey]?.[stableLang] || MULTI_PANEL_PRESET_FALLBACKS['4panel'][stableLang];
};

// RefineControl moved to components/RefineControl.jsx
import { processPrompt } from '../../../lib/promptUtils';
import { entityNameAppearsInText, entityTokenMatchesName, normalizeEntityToken } from '../../../lib/entityToken';
import SettingsPage from '../../Settings';
import { confirmUiMessage, promptUiMessage, notifyUiMessage } from '../../../lib/uiMessage';

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
                className="w-full h-[192px] bg-black/30 border border-white/10 rounded p-3 text-sm"
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

export const ShotsView = ({ activeEpisode, projectId, project, onLog, editingShot, setEditingShot, isSuperuser = false, uiLang = 'zh', focusRequest = null, restoreEditingShotId = null, userBatchParallelLimit = 3, tabMediaRefreshSignal = 0, isTabActive = true, onMediaRefreshRequest = null }) => {
        const aspectParts = parseAspectRatioParts(getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9');
    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;
    
    const { generationConfig, saveToolConfig, savedToolConfigs, llmConfig } = useStore();
    const functionApiConfigs = useFunctionApis();
    const [sd2AutoDuration, setSd2AutoDuration] = useState(false);
    const [selectedVideoApiId, setSelectedVideoApiId] = useState(() => {
        try {
            return Number(localStorage.getItem('func_api_generate_videos') || 0) || null;
        } catch {
            return null;
        }
    });
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);

    const selectedGenerateVideosApi = useMemo(() => {
        const apiList = functionApiConfigs?.generate_videos || [];
        if (!apiList.length) return null;
        const matched = apiList.find((item) => Number(item?.system_api_id) === Number(selectedVideoApiId));
        if (matched) return matched;
        return apiList.find((item) => !item?.is_fallback) || apiList[0] || null;
    }, [functionApiConfigs, selectedVideoApiId]);

    const isSelectedVideoApiSeedance2 = useMemo(
        () => isSeedance2VideoBaseModel(selectedGenerateVideosApi?.system_api_base_model),
        [selectedGenerateVideosApi]
    );
    const isSd2AutoDurationActive = isSelectedVideoApiSeedance2 && sd2AutoDuration;

    useEffect(() => {
        const syncSelectedVideoApi = (event) => {
            const detailKey = String(event?.detail?.storageKey || '');
            if (detailKey && detailKey !== 'func_api_generate_videos') return;
            try {
                const next = Number(localStorage.getItem('func_api_generate_videos') || 0) || null;
                setSelectedVideoApiId(next);
            } catch {
                setSelectedVideoApiId(null);
            }
        };
        const handleStorage = (event) => {
            if (event?.key !== 'func_api_generate_videos') return;
            syncSelectedVideoApi({ detail: { storageKey: 'func_api_generate_videos' } });
        };
        window.addEventListener('storage', handleStorage);
        window.addEventListener('aistory:function-api-changed', syncSelectedVideoApi);
        return () => {
            window.removeEventListener('storage', handleStorage);
            window.removeEventListener('aistory:function-api-changed', syncSelectedVideoApi);
        };
    }, []);

    const getShotDurationDisplayValue = useCallback((shotDuration) => {
        if (isSd2AutoDurationActive) return '-1';
        const normalized = String(shotDuration ?? '').trim();
        if (normalized === '-1') return '';
        return normalized || '';
    }, [isSd2AutoDurationActive]);

    const resolveShotVideoDurationParam = useCallback((shotDuration) => {
        if (isSd2AutoDurationActive) {
            return -1;
        }
        const normalized = String(shotDuration ?? '').trim();
        if (normalized === '-1') return 5;
        const tableDuration = parseFloat(shotDuration);
        return Number.isFinite(tableDuration) && tableDuration > 0 ? tableDuration : 5;
    }, [isSd2AutoDurationActive]);

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
    const shotPromptDisplayLang = 'cn';

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
    const shotsRef = useRef([]);
    useEffect(() => {
        shotsRef.current = Array.isArray(shots) ? shots : [];
    }, [shots]);

    const readShotTableDuration = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return '5';
        const tableShot = shotsRef.current.find((item) => String(item?.id) === stableShotId);
        const raw = tableShot?.duration ?? tableShot?.['Duration (s)'] ?? '';
        const normalized = String(raw ?? '').trim();
        if (normalized && normalized !== '-1') return normalized;
        return '5';
    }, []);

    const restoreEditingShotDurationFromTable = useCallback(() => {
        if (!editingShot?.id) return;
        const restore = readShotTableDuration(editingShot.id);
        setEditingShot((prev) => {
            if (!prev) return prev;
            if (String(prev.duration ?? '').trim() === restore) return prev;
            return { ...prev, duration: restore };
        });
    }, [editingShot?.id, readShotTableDuration, setEditingShot]);

    const handleToggleSd2AutoDuration = useCallback((checked) => {
        setSd2AutoDuration(checked);
        if (!checked) {
            restoreEditingShotDurationFromTable();
        }
    }, [restoreEditingShotDurationFromTable]);

    useEffect(() => {
        if (!editingShot?.id || isSd2AutoDurationActive) return;
        const current = String(editingShot.duration ?? '').trim();
        if (current !== '-1') return;
        restoreEditingShotDurationFromTable();
    }, [editingShot?.id, editingShot?.duration, isSd2AutoDurationActive, restoreEditingShotDurationFromTable]);
    const [isShotsLoading, setIsShotsLoading] = useState(false);
    const [hasShotInitialLoadCompleted, setHasShotInitialLoadCompleted] = useState(false);
    const [selectedShotIds, setSelectedShotIds] = useState([]);
    const [isImportOpen, setIsImportOpen] = useState(false);
    // const [editingShot, setEditingShot] = useState(null); // Lifted state

    const [tunePromptModalConfig, setTunePromptModalConfig] = useState({ open: false, targetField: null, initialValue: "" });
    const [projectEntities, setProjectEntities] = useState([]);
    
    // Prefer current-episode entities over project-global / other-episode same-name rows.
    const entities = useMemo(() => {
        const preferred = String(activeEpisode?.id || '').trim();
        const scoped = projectEntities.filter((e) => !e?.episode_id || String(e.episode_id) === preferred);
        if (!preferred) return scoped;
        return [...scoped].sort((a, b) => {
            const aEp = String(a?.episode_id || '').trim() === preferred ? 0 : 1;
            const bEp = String(b?.episode_id || '').trim() === preferred ? 0 : 1;
            return aEp - bEp;
        });
    }, [projectEntities, activeEpisode?.id]);

    const [entityListLoading, setEntityListLoading] = useState(false);
    const projectEntitiesRef = useRef([]);
    const entityLoadPromiseRef = useRef(null);
    
    // NEW: Abort Controller Ref for retries
    const abortGenerationRef = useRef(false);

    // Local Notification for ShotsView (Edit Dialog)
    const [notification, setNotification] = useState(null);
    const [restoringFromStaging, setRestoringFromStaging] = useState(false);
    const showNotification = (message, type = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    };

    const [shotNotePopover, setShotNotePopover] = useState(null);
    const [shotNoteDraft, setShotNoteDraft] = useState('');
    const shotNotePopoverRef = useRef(null);

    useEffect(() => {
        projectEntitiesRef.current = Array.isArray(projectEntities) ? projectEntities : [];
    }, [projectEntities]);

    const loadEntities = useCallback(async () => {
        const resolvedProjectId = projectId || activeEpisode?.project_id;
        if (!resolvedProjectId) return projectEntitiesRef.current;
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
                setProjectEntities(nextEntities);
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
            return loaded.filter(e => !e?.episode_id || String(e.episode_id) === String(activeEpisode?.id));
        }
        return Array.isArray(entities) ? entities : [];
    }, [activeEpisode?.id, activeEpisode?.project_id, entities, entityListLoading, loadEntities, projectId]);

    // Note: Provider selection functionality removed (defaults to Backend Active Settings)


    // AI Prompt Preview Modal State
    const [shotReviewModal, setShotReviewModal] = useState({ open: false, sceneId: null, data: null, loading: false });

    // Media Handling
    const [viewMedia, setViewMedia] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });
    const pickerCallbackRef = useRef(null);
    const [generatingStateByShot, setGeneratingStateByShot] = useState({});
    const [videoStatuses, setVideoStatuses] = useState({});
    const [shotMediaOssPersistBusy, setShotMediaOssPersistBusy] = useState({});
    const [mediaPersistGraceRefreshSeq, setMediaPersistGraceRefreshSeq] = useState(0);
    const activeOssVideoSyncRef = useRef(new Set());
    const [isBatchGenerating, setIsBatchGenerating] = useState(false);
    const [isDraftMode, setIsDraftMode] = useState(() => !!getDraftModePreference());
    const readStoredUsePrevVideo = useCallback(() => {
        try {
            return localStorage.getItem('aiStory_usePrevVideo') === 'true';
        } catch {
            return false;
        }
    }, []);
    const [usePrevVideo, setUsePrevVideo] = useState(() => {
        try {
            return localStorage.getItem('aiStory_usePrevVideo') === 'true';
        } catch {
            return false;
        }
    });
    const [isBatchMenuOpen, setIsBatchMenuOpen] = useState(false);
    const [isPlaylistModalOpen, setIsPlaylistModalOpen] = useState(false);
    const [playlistIndex, setPlaylistIndex] = useState(0);
    const playlistVideoRef = useRef(null);

    const sortShotsForContinuation = useCallback((sourceShots) => {
        return [...(Array.isArray(sourceShots) ? sourceShots : [])].sort((a, b) => {
            const ep = String(activeEpisode?.episode_number || activeEpisode?.id || '').trim();
            // Try to find scene code format from scenes if needed, or fallback.
            const scA = String(a?.scene_code || a?.scene_id || '').trim();
            const shA = String(a?.shot_id || a?.shot_number || a?.id || '').trim();
            const scB = String(b?.scene_code || b?.scene_id || '').trim();
            const shB = String(b?.shot_id || b?.shot_number || b?.id || '').trim();
            const keyA = `${ep}_${scA}_${shA}`;
            const keyB = `${ep}_${scB}_${shB}`;
            return keyA.localeCompare(keyB, undefined, { numeric: true, sensitivity: 'base' });
        });
    }, [activeEpisode?.episode_number, activeEpisode?.id]);

    useEffect(() => {
        const shotPool = [editingShot, ...(shots || [])].filter(Boolean);
        let minWaitMs = 0;
        shotPool.forEach((shot) => {
            const waitMs = shotNeedsAnyOssPersistGraceWaitMs(shot);
            if (waitMs > 0 && (!minWaitMs || waitMs < minWaitMs)) {
                minWaitMs = waitMs;
            }
        });
        if (!minWaitMs) return undefined;
        const timer = setTimeout(() => {
            setMediaPersistGraceRefreshSeq((seq) => seq + 1);
        }, minWaitMs + 100);
        return () => clearTimeout(timer);
    }, [editingShot, shots, mediaPersistGraceRefreshSeq]);

    const _getInMemorySortedShots = () => sortShotsForContinuation(shots || []);

    const resolveContinuationShotPool = useCallback(() => {
        const merged = new Map();
        (Array.isArray(allEpisodeShotsRef.current) ? allEpisodeShotsRef.current : []).forEach((shot) => {
            const id = String(shot?.id || '').trim();
            if (!id) return;
            merged.set(id, shot);
        });
        (Array.isArray(shots) ? shots : []).forEach((shot) => {
            const id = String(shot?.id || '').trim();
            if (!id) return;
            merged.set(id, shot);
        });
        if (editingShot?.id) {
            merged.set(String(editingShot.id), editingShot);
        }
        return Array.from(merged.values());
    }, [editingShot, shots]);

    const isFirstShotInOwnScene = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return false;
        const shotPool = resolveContinuationShotPool();
        const currentShot = shotPool.find((shot) => String(shot?.id || '').trim() === stableShotId);
        const sceneId = String(currentShot?.scene_id || '').trim();
        if (!currentShot || !sceneId) return false;

        const sortedSceneShots = sortShotsForContinuation(
            shotPool.filter((shot) => String(shot?.scene_id || '').trim() === sceneId)
        );
        return String(sortedSceneShots[0]?.id || '').trim() === stableShotId;
    }, [resolveContinuationShotPool, sortShotsForContinuation]);

    useEffect(() => {
        const stableEditingShotId = String(editingShot?.id || '').trim();
        if (!stableEditingShotId) return;
        setUsePrevVideo(isFirstShotInOwnScene(stableEditingShotId) ? false : readStoredUsePrevVideo());
    }, [editingShot?.id, isFirstShotInOwnScene, readStoredUsePrevVideo]);

    const findPrevContinuationShot = useCallback((shotId) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return null;

        const sortedAllShots = sortShotsForContinuation(resolveContinuationShotPool());
        const currentIdx = sortedAllShots.findIndex((shot) => String(shot?.id || '').trim() === stableShotId);
        if (currentIdx <= 0) return null;
        return sortedAllShots[currentIdx - 1] || null;
    }, [resolveContinuationShotPool, sortShotsForContinuation]);

    const resolvePrevContinuationVideoRefs = useCallback((shotId) => {
        if (!usePrevVideo) return [];
        const prevShot = findPrevContinuationShot(shotId);
        const prevVideoUrl = String(prevShot?.video_url || '').trim();
        return prevVideoUrl ? [prevVideoUrl] : [];
    }, [usePrevVideo, findPrevContinuationShot]);

    const handleToggleUsePrevVideo = (checked, targetShotId = null) => {
        if (checked) {
            let stableTargetShotId = '';
            if (targetShotId) {
                stableTargetShotId = String(targetShotId);
            } else if (editingShot) {
                stableTargetShotId = String(editingShot.id);
            }

            if (stableTargetShotId) {
                const prevShot = findPrevContinuationShot(stableTargetShotId);
                if (!prevShot) {
                    notifyUiMessage(t('这是第一镜，且未找到上一场景的可续写镜头。', 'This is the first shot and no previous-scene shot is available for continuation.'), 'warning');
                    return;
                }
                if (!prevShot?.video_url) {
                    notifyUiMessage(t('上一镜头还没有可用于续写的视频内容。', 'The previous shot does not have video content available for continuation yet.'), 'warning');
                    return;
                }
            } else if (selectedShotIds.length > 0) {
                let valid = false;
                for (const sid of selectedShotIds) {
                    const prevShot = findPrevContinuationShot(sid);
                    if (prevShot?.video_url) {
                        valid = true;
                        break;
                    }
                }
                if (!valid) {
                    notifyUiMessage(t('选中的分镜里没有可用于上镜续写的视频内容。', 'None of the selected shots have previous video content available for continuation.'), 'warning');
                    return;
                }
              } else if (shots.length > 0 && !stableTargetShotId) {
                 // Global context without selected shots
                 notifyUiMessage(t('请先选择或编辑一个分镜！', 'Please select or edit a shot first!'), 'warning');
                 // Let it pass or block? We can just let it check but warn.
                 // Actually they might just check it BEFORE selecting shots. So don't block.
            }
        }
        setUsePrevVideo(checked);
        try {
            localStorage.setItem('aiStory_usePrevVideo', String(checked));
        } catch {}
    };

    const [isShotBatchStarting, setIsShotBatchStarting] = useState(false);
    const [isStoppingShotBatch, setIsStoppingShotBatch] = useState(false);
    const [stoppingVideoByShot, setStoppingVideoByShot] = useState({});
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
    const shotBatchStatusErrorStreakRef = useRef(0);
    const shotBatchStartupGuardUntilRef = useRef(0);
    const shotBatchBootstrapUntilRef = useRef(0);
    const isBatchGeneratingRef = useRef(false);
    const batchProgressRef = useRef({ current: 0, total: 0, status: '' });
    const recoverShotBatchInFlightRef = useRef(false);
    const recoverShotBatchLastAtRef = useRef(0);
    const activeResumeVideoJobsRef = useRef(new Set());
    const pausedResumeVideoJobsRef = useRef({});
    const pendingImageJobsRef = useRef({});
    const allEpisodeShotsRef = useRef([]);
    const editingShotRef = useRef(null);
    const jointDiptychApplyInFlightRef = useRef(new Map());
    const appliedJointDiptychResultsRef = useRef(new Map());
    const applyMultiPanelImageResultRef = useRef(null);
    const multiPanelPresetKeyRef = useRef('4panel');
    const generatingStateByShotRef = useRef({});
    const shotLocalBatchSessionRef = useRef('');
    const shotLocalBatchStopRequestedRef = useRef(false);
    const selectedSceneIdRef = useRef('all');
    const shotFiltersHydratedRef = useRef(false);
    const skipShotFiltersPersistRef = useRef(false);
    const [activeSources, setActiveSources] = useState({ Image: 'unset', Video: 'unset' });
    const [activeImageCapabilityProfile, setActiveImageCapabilityProfile] = useState(null);
    const [localKeyframes, setLocalKeyframes] = useState([]);
    const [localPrevShotFrames, setLocalPrevShotFrames] = useState([]);
    const [videoKeyframeExtractCount, setVideoKeyframeExtractCount] = useState('4');
    const [isExtractingVideoKeyframes, setIsExtractingVideoKeyframes] = useState(false);
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
    const shotHistoryPendingRef = useRef(false);
    const GENERATION_STATE_TTL_MS = 1000 * 60 * 60;
    const SHOT_MEDIA_STARTUP_GRACE_MS = 15000;
    const IMAGE_JOB_STATE_TTL_MS = 1000 * 60 * 60;
    const VIDEO_JOB_STATE_TTL_MS = 1000 * 60 * 60;
    const shotsRefreshRequestSeqRef = useRef(0);

    const normalizeGenerationPhase = useCallback((value) => {
        const phase = String(value || '').trim().toLowerCase();
        if (!phase) return '';
        if (['success', 'succeeded', 'completed', 'done'].includes(phase)) return 'succeeded';
        if (['failed', 'error'].includes(phase)) return 'failed';
        if (['canceled', 'cancelled'].includes(phase)) return 'canceled';
        if (['queued', 'pending', 'running', 'processing', 'generating', 'submitted', 'in_progress', 'in-progress'].includes(phase)) return 'running';
        return phase;
    }, []);

    const isTerminalGenerationPhase = useCallback((value) => {
        const normalizedPhase = normalizeGenerationPhase(value);
        return normalizedPhase === 'succeeded' || normalizedPhase === 'failed' || normalizedPhase === 'canceled';
    }, [normalizeGenerationPhase]);

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
        const explicitMediaKindFromItem = String(item?.mediaKind || '').trim().toLowerCase();
        if (explicitMediaKindFromItem) return explicitMediaKindFromItem;

        const explicitMediaKind = String(extractGenerationHistoryField(item, 'ownerMediaKind') || '').trim().toLowerCase();
        if (explicitMediaKind) return explicitMediaKind;

        const topLevelType = String(item?.type || '').trim().toLowerCase();
        if (topLevelType === 'video') return 'video';

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
                    model: extractGenerationHistoryField(item, 'model') || extractGenerationHistoryField(item, 'source_model'),
                    duration: extractGenerationHistoryField(item, 'duration'),
                };
            })
            .sort((a, b) => (b.createdAtMs || 0) - (a.createdAtMs || 0));
    }, [buildGenerationHistoryLabel, extractGenerationHistoryField, resolveGenerationHistoryMediaKind, resolveGenerationHistoryResultUrl]);

    const fetchShotGenerationHistory = useCallback(async (shot) => {
        const stableShotId = String(shot?.id || shot || '').trim();
        const stableProjectId = String(projectId || '').trim();
        if (!stableShotId) {
            setShotGenerationHistory([]);
            return;
        }

        setShotGenerationHistoryLoading(true);
        try {
            const pageSize = 120;
            const maxPages = 10;
            const persistedAssets = [];
            for (let page = 0; page < maxPages; page += 1) {
                const pageRows = await fetchAssets({
                    shot_id: stableShotId,
                    project_id: stableProjectId || undefined,
                    skip: page * pageSize,
                    limit: pageSize,
                });
                const rows = Array.isArray(pageRows) ? pageRows : [];
                if (!rows.length) break;

                const mappedRows = rows
                    .filter((row) => {
                        const meta = row?.meta_info && typeof row.meta_info === 'object' ? row.meta_info : {};
                        const metaShotId = String(meta?.shot_id || row?.shot_id || '').trim();
                        if (metaShotId !== stableShotId) return false;

                        if (stableProjectId) {
                            const metaProjectId = String(meta?.project_id || row?.project_id || '').trim();
                            if (metaProjectId && metaProjectId !== stableProjectId) return false;
                        }

                        const assetType = String(row?.type || '').toLowerCase();
                        return assetType === 'image' || assetType === 'video';
                    })
                    .map((row) => {
                        const meta = row?.meta_info && typeof row.meta_info === 'object' ? row.meta_info : {};
                        const frameType = String(meta?.frame_type || meta?.asset_type || '').toLowerCase();
                        const mediaKind = String(row?.type || '').toLowerCase() === 'video'
                            ? 'video'
                            : (frameType.includes('end') ? 'end' : (frameType.includes('start') ? 'start' : 'image'));
                        return {
                            id: row?.id,
                            job_id: `asset:${row?.id}`,
                            kind: String(row?.type || '').toLowerCase() === 'video' ? 'video' : 'image',
                            type: String(row?.type || '').toLowerCase(),
                            status: 'completed',
                            shotId: stableShotId,
                            projectId: String(meta?.project_id || '').trim(),
                            mediaKind,
                            resultUrl: String(row?.url || '').trim(),
                            displayLabel: mediaKind === 'video'
                                ? t('视频生成', 'Video Generation')
                                : (mediaKind === 'end' ? t('结束帧生成', 'End Frame Generation') : t('起始帧生成', 'Start Frame Generation')),
                            createdAtMs: Date.parse(String(row?.created_at || '')) || 0,
                            created_at: row?.created_at,
                            model: meta?.model || meta?.source_model,
                            duration: meta?.duration,
                        };
                    });

                persistedAssets.push(...mappedRows);
                if (persistedAssets.length >= 40 || rows.length < pageSize) break;
            }

            const merged = [...persistedAssets];
            const dedupMap = new Map();
            merged.forEach((item) => {
                const key = String(item?.job_id || item?.id || '').trim() || `${String(item?.resultUrl || '').trim()}|${String(item?.createdAtMs || 0)}`;
                if (!key) return;
                if (!dedupMap.has(key)) dedupMap.set(key, item);
            });

            const fallbackFromShot = [];
            const shotStartUrl = String(shot?.image_url || '').trim();
            const shotVideoUrl = String(shot?.video_url || '').trim();
            let shotEndUrl = '';
            try {
                const shotTech = JSON.parse(shot?.technical_notes || '{}');
                shotEndUrl = String(shotTech?.end_frame_url || '').trim();
            } catch (_) {
                shotEndUrl = '';
            }

            const shotTs = Date.parse(String(shot?.updated_at || shot?.created_at || '')) || Date.now();
            if (shotStartUrl) {
                fallbackFromShot.push({
                    id: `shot-current-start-${stableShotId}`,
                    job_id: `shot-current-start-${stableShotId}`,
                    kind: 'image',
                    type: 'image',
                    status: 'completed',
                    shotId: stableShotId,
                    projectId: stableProjectId,
                    mediaKind: 'start',
                    resultUrl: shotStartUrl,
                    displayLabel: t('起始帧生成（当前）', 'Start Frame (Current)'),
                    createdAtMs: shotTs,
                });
            }
            if (shotEndUrl) {
                fallbackFromShot.push({
                    id: `shot-current-end-${stableShotId}`,
                    job_id: `shot-current-end-${stableShotId}`,
                    kind: 'image',
                    type: 'image',
                    status: 'completed',
                    shotId: stableShotId,
                    projectId: stableProjectId,
                    mediaKind: 'end',
                    resultUrl: shotEndUrl,
                    displayLabel: t('结束帧生成（当前）', 'End Frame (Current)'),
                    createdAtMs: shotTs,
                });
            }
            if (shotVideoUrl) {
                fallbackFromShot.push({
                    id: `shot-current-video-${stableShotId}`,
                    job_id: `shot-current-video-${stableShotId}`,
                    kind: 'video',
                    type: 'video',
                    status: 'completed',
                    shotId: stableShotId,
                    projectId: stableProjectId,
                    mediaKind: 'video',
                    resultUrl: shotVideoUrl,
                    displayLabel: t('视频生成（当前）', 'Video (Current)'),
                    createdAtMs: shotTs,
                });
            }

            const finalList = Array.from(dedupMap.values())
                .concat(fallbackFromShot)
                .sort((a, b) => (Number(b?.createdAtMs || 0) - Number(a?.createdAtMs || 0)));
            setShotGenerationHistory(finalList.slice(0, 16));
        } catch (e) {
            onLog?.(`Failed to load shot generation history: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
            setShotGenerationHistory([]);
        } finally {
            setShotGenerationHistoryLoading(false);
        }
    }, [fetchAssets, onLog, projectId, t]);

    useEffect(() => {
        if (!editingShot?.id) {
            setShotGenerationHistory([]);
            shotHistoryPendingRef.current = false;
            return;
        }
        fetchShotGenerationHistory(editingShot);
    }, [editingShot, fetchShotGenerationHistory]);

    useEffect(() => {
        const stableShotId = String(editingShot?.id || '').trim();
        if (!stableShotId) {
            shotHistoryPendingRef.current = false;
            return;
        }

        let disposed = false;

        const checkPendingAndRefresh = () => {
            if (disposed) return;

            let pendingImageJobs = {};
            try {
                if (imageJobStateStorageKey) {
                    const rawImage = localStorage.getItem(imageJobStateStorageKey);
                    const parsedImage = rawImage ? JSON.parse(rawImage) : {};
                    pendingImageJobs = parsedImage && typeof parsedImage === 'object' ? parsedImage : {};
                }
            } catch {
                pendingImageJobs = {};
            }
            const hasPendingImage = Object.values(pendingImageJobs || {}).some((payload) => {
                return String(payload?.shotId || '').trim() === stableShotId;
            });

            let pendingVideoJobs = {};
            try {
                if (videoJobStateStorageKey) {
                    const rawVideo = localStorage.getItem(videoJobStateStorageKey);
                    const parsedVideo = rawVideo ? JSON.parse(rawVideo) : {};
                    pendingVideoJobs = parsedVideo && typeof parsedVideo === 'object' ? parsedVideo : {};
                }
            } catch {
                pendingVideoJobs = {};
            }
            const hasPendingVideo = Boolean(pendingVideoJobs?.[stableShotId]);

            const hasPending = hasPendingImage || hasPendingVideo;
            const hadPending = Boolean(shotHistoryPendingRef.current);
            shotHistoryPendingRef.current = hasPending;

            if (hadPending && !hasPending) {
                [0, 1500, 4000].forEach((delayMs) => {
                    window.setTimeout(() => {
                        void fetchShotGenerationHistory(stableShotId);
                    }, delayMs);
                });
            }
        };

        checkPendingAndRefresh();
        const timer = window.setInterval(checkPendingAndRefresh, 1500);

        return () => {
            disposed = true;
            window.clearInterval(timer);
        };
    }, [editingShot?.id, fetchShotGenerationHistory, imageJobStateStorageKey, videoJobStateStorageKey]);

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
        mode === 'keyframes-local' || mode === 'joint-diptych-local' || mode === 'multi-panel-local'
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
        setVideoStatuses(prev => { const n = { ...prev }; delete n[stableShotId]; return n; });
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
            setVideoStatuses(prevStatuses => {
                const nextStatuses = { ...prevStatuses };
                matchedShotIds.forEach((shotId) => {
                    delete nextStatuses[shotId];
                });
                return nextStatuses;
            });
        }

        clearPendingVideoJobsByJobId(stableJobId);
    }, [clearPendingVideoJobsByJobId, readVideoJobStateStorage, setShotGeneratingState]);

    const releaseShotVideoUi = useCallback(({ shotId, jobId } = {}) => {
        const stableShotId = String(shotId || '').trim();
        const stableJobId = String(jobId || '').trim();
        const pending = stableJobId ? readVideoJobStateStorage() : {};
        const matchedShotIds = stableJobId
            ? Object.entries(pending)
                .filter(([, payload]) => String(payload?.jobId || '').trim() === stableJobId)
                .map(([pendingShotId]) => String(pendingShotId || '').trim())
                .filter(Boolean)
            : [];
        const shotIds = Array.from(new Set([stableShotId, ...matchedShotIds].filter(Boolean)));

        shotIds.forEach((id) => {
            setShotGeneratingState(id, 'video', false);
            clearPendingVideoJob(id);
        });
        if (stableJobId) {
            clearPendingVideoJobsByJobId(stableJobId);
            delete pausedResumeVideoJobsRef.current[stableJobId];
        }
        if (shotIds.length > 0) {
            setVideoStatuses(prevStatuses => {
                const nextStatuses = { ...prevStatuses };
                shotIds.forEach((id) => {
                    delete nextStatuses[id];
                });
                return nextStatuses;
            });
        }
    }, [clearPendingVideoJob, clearPendingVideoJobsByJobId, readVideoJobStateStorage, setShotGeneratingState]);

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
        const requestedMode = String(options?.mode || '').trim();
        const nextMode = requestedMode === 'joint_diptych'
            ? 'joint_diptych'
            : (requestedMode === 'multi_panel' ? 'multi_panel' : 'single');
        const next = {
            ...prev,
            [key]: {
                shotId: stableShotId,
                kind: stableKind,
                jobId: stableJobId,
                startedAt: Number(options?.startedAt || 0) || Date.now(),
                mode: nextMode,
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

    const getReadableErrorDetail = useCallback((error, fallback = 'unknown error') => {
        const rawDetail = error?.response?.data?.detail;
        if (typeof rawDetail === 'string' && rawDetail.trim()) return rawDetail.trim();
        if (Array.isArray(rawDetail) && rawDetail.length > 0) {
            return rawDetail
                .map((item) => {
                    if (typeof item === 'string') return item.trim();
                    if (item && typeof item === 'object') {
                        const msg = item?.msg || item?.message || item?.detail;
                        if (typeof msg === 'string' && msg.trim()) return msg.trim();
                        try { return JSON.stringify(item); } catch { return ''; }
                    }
                    return String(item || '').trim();
                })
                .filter(Boolean)
                .join('; ') || fallback;
        }
        if (rawDetail && typeof rawDetail === 'object') {
            const msg = rawDetail?.message || rawDetail?.detail || rawDetail?.msg;
            if (typeof msg === 'string' && msg.trim()) return msg.trim();
            try {
                const serialized = JSON.stringify(rawDetail);
                if (serialized && serialized !== '{}') return serialized;
            } catch {}
        }

        const message = error?.message;
        if (typeof message === 'string' && message.trim()) return message.trim();
        return fallback;
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
                const phase = normalizeGenerationPhase(status?.status);
                const isTerminal = isTerminalGenerationPhase(phase) || Boolean(status?.result?.url || status?.result?.video_url || status?.url || status?.video_url);

                if (!isTerminal) {
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
            if (next.start || next.end || next.video) {
                cleaned[shotId] = next;
                if (!generationMediaBaselineRef.current[String(shotId)]) {
                    generationMediaBaselineRef.current[String(shotId)] = {};
                }
            }
        });
        setGeneratingStateByShot(cleaned);
        writeGenerationStateStorage(cleaned);
        hasHydratedGenerationStateRef.current = true;
    }, [generationStateStorageKey, readGenerationStateStorage, writeGenerationStateStorage]);

    const isFirstGenerationSyncRef = useRef(true);
    useEffect(() => {
        if (!hasHydratedGenerationStateRef.current) return;
        if (isFirstGenerationSyncRef.current) {
            isFirstGenerationSyncRef.current = false;
            const existing = readGenerationStateStorage();
            if (Object.keys(generatingStateByShot || {}).length === 0 && Object.keys(existing || {}).length > 0) {
                return;
            }
        }
        writeGenerationStateStorage(generatingStateByShot);
    }, [generatingStateByShot, writeGenerationStateStorage, readGenerationStateStorage]);

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

    const isShotVideoUiRunning = useCallback((shotId, stateOverride = null) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return false;
        const shotState = (stateOverride && typeof stateOverride === 'object')
            ? stateOverride
            : (generatingStateByShotRef.current?.[stableShotId] || { start: false, end: false, video: false, videoAt: 0 });
        if (!shotState?.video) return false;

        const pendingVideoJobId = getPendingVideoJobId(stableShotId);
        if (pendingVideoJobId) return true;

        const statusText = String(videoStatuses?.[stableShotId] || '').trim();
        if (statusText) {
            const normalizedStatus = normalizeGenerationPhase(statusText);
            if (!isTerminalGenerationPhase(normalizedStatus)) {
                return true;
            }
        }

        const startedAtMs = Number(shotState?.videoAt || 0);
        if (startedAtMs > 0 && (Date.now() - startedAtMs) < SHOT_MEDIA_STARTUP_GRACE_MS) {
            return true;
        }

        return false;
    }, [SHOT_MEDIA_STARTUP_GRACE_MS, getPendingVideoJobId, isTerminalGenerationPhase, normalizeGenerationPhase, videoStatuses]);

    const rawCurrentGeneratingState = editingShot?.id
        ? (generatingStateByShot[String(editingShot.id)] || { start: false, end: false, video: false, startAt: 0, endAt: 0, videoAt: 0 })
        : { start: false, end: false, video: false, startAt: 0, endAt: 0, videoAt: 0 };
    const currentGeneratingState = {
        ...rawCurrentGeneratingState,
        video: editingShot?.id ? isShotVideoUiRunning(editingShot.id, rawCurrentGeneratingState) : false,
    };
    const currentShotGenerating = Boolean(currentGeneratingState.start || currentGeneratingState.end || currentGeneratingState.video);
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
    const [assetDetailPreviewMode, setAssetDetailPreviewMode] = useState('fit');
    const [isEditingVideoPreviewArmed, setIsEditingVideoPreviewArmed] = useState(false);
    const [videoCleanupMenuOpen, setVideoCleanupMenuOpen] = useState(false);
    const [frameTrimModal, setFrameTrimModal] = useState(() => createInitialFrameTrimState());
    const [shotImageCfgDefault, setShotImageCfgDefault] = useState(() => resolveShotImageCfgDefault(getCachedUserPreferences()));
    const [shotImageCfgValue, setShotImageCfgValue] = useState(() => resolveShotImageCfgDefault(getCachedUserPreferences()));
    const [shotAssetsMetaIndex, setShotAssetsMetaIndex] = useState({});
    const [shotAssetsMetaRows, setShotAssetsMetaRows] = useState([]);
    const [shotAssetsMetaLoading, setShotAssetsMetaLoading] = useState(false);
    const [shotAssetsRefreshKey, setShotAssetsRefreshKey] = useState(0);
    const refreshShotAssetsMeta = useCallback(() => setShotAssetsRefreshKey(k => k + 1), []);

    const [editShotRefreshing, setEditShotRefreshing] = useState(false);
    const editShotRefreshingRef = useRef(false);
    const handleRefreshEditShotElements = useCallback(async () => {
        if (editShotRefreshingRef.current) return;
        editShotRefreshingRef.current = true;
        setEditShotRefreshing(true);
        try {
            const shotId = editingShotRef.current?.id;
            await Promise.allSettled([
                loadEntities(),
                shotId ? fetchShot(shotId).then((fullShot) => {
                    if (!fullShot?.id) return;
                    setEditingShot((prev) => {
                        if (!prev || String(prev?.id || '') !== String(fullShot.id)) return prev;
                        return { ...prev, ...fullShot, is_compact: false };
                    });
                }) : Promise.resolve(),
            ]);
            refreshShotAssetsMeta();
            triggerMediaReload();
        } catch (e) {
            console.error('Failed to refresh edit shot elements', e);
        } finally {
            editShotRefreshingRef.current = false;
            setEditShotRefreshing(false);
        }
    }, [loadEntities, refreshShotAssetsMeta, setEditingShot]);

    // Entering the edit-shot drawer: refresh entity refs + force image reload so reference thumbnails are current.
    useEffect(() => {
        if (!editingShot?.id) return;
        void handleRefreshEditShotElements();
    }, [editingShot?.id, handleRefreshEditShotElements]);

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
        if (type === 'video') {
            setIsEditingVideoPreviewArmed(true);
        }
        setTempPromptSubmitLang('');
        setShowPromptLangMenu(false);
        setAssetDetailModal({ open: true, type, keyframeIndex });
        setAssetDetailPreviewMode('fit');
    };

    const closeAssetDetailModal = () => {
        setTempPromptSubmitLang('');
        setShowPromptLangMenu(false);
        setAssetDetailPreviewMode('fit');
        setAssetDetailModal({ open: false, type: 'start', keyframeIndex: -1 });
    };

    useEffect(() => {
        setIsEditingVideoPreviewArmed(Boolean(String(editingShot?.video_url || '').trim()));
    }, [editingShot?.id, editingShot?.video_url]);

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

    const buildAssetUrlTokens = useCallback((value) => {
        const raw = String(value || '').trim();
        if (!raw) return [];
        const tokens = new Set();
        const fullToken = normalizeAssetUrlToken(raw);
        if (fullToken) tokens.add(fullToken);
        try {
            const parsed = new URL(raw, BASE_URL || window.location.origin);
            const pathToken = String(parsed.pathname || '').trim().toLowerCase();
            if (pathToken) tokens.add(pathToken);
            const baseName = pathToken.split('/').pop();
            if (baseName) tokens.add(baseName);
        } catch (e) {
            const noQuery = raw.split('?')[0].split('#')[0];
            const pathPart = String(noQuery || '').trim().toLowerCase();
            if (pathPart) {
                tokens.add(pathPart);
                const baseName = pathPart.split('/').pop();
                if (baseName) tokens.add(baseName);
            }
        }
        return Array.from(tokens);
    }, [normalizeAssetUrlToken]);

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

    const resolveShotAssetByUrl = useCallback((url, preferredType = '', modalType = '') => {
        const expectedType = String(preferredType || '').trim().toLowerCase();
        const stableModalType = String(modalType || '').trim().toLowerCase();
        const stableShotId = String(editingShot?.id || '').trim();

        const sortByCreatedDesc = (rows = []) => {
            return [...rows].sort((left, right) => {
                const l = Date.parse(String(left?.created_at || '')) || 0;
                const r = Date.parse(String(right?.created_at || '')) || 0;
                return r - l;
            });
        };

        const pickByType = (rows = []) => {
            if (!rows.length) return null;
            if (!expectedType) return rows[0] || null;
            return rows.find((asset) => String(asset?.type || '').trim().toLowerCase() === expectedType) || rows[0] || null;
        };

        const tokenCandidates = buildAssetUrlTokens(url);
        const tokenMatches = [];
        const tokenSeenIds = new Set();
        tokenCandidates.forEach((token) => {
            const rows = Array.isArray(shotAssetsMetaIndex[token]) ? shotAssetsMetaIndex[token] : [];
            rows.forEach((asset) => {
                const idKey = String(asset?.id || `${asset?.url || ''}|${asset?.created_at || ''}`);
                if (!idKey || tokenSeenIds.has(idKey)) return;
                tokenSeenIds.add(idKey);
                tokenMatches.push(asset);
            });
        });

        // 调试日志：token 匹配
        if (typeof window !== 'undefined') {
            console.log('[分镜预览][resolveShotAssetByUrl]', {
                url,
                preferredType,
                modalType,
                stableShotId,
                tokenCandidates,
                tokenMatches: tokenMatches.map(a => a.id),
                shotAssetsMetaIndexKeys: Object.keys(shotAssetsMetaIndex),
            });
        }

        const tokenPicked = pickByType(sortByCreatedDesc(tokenMatches));
        if (tokenPicked) {
            if (typeof window !== 'undefined') {
                console.log('[分镜预览][resolveShotAssetByUrl] tokenPicked', tokenPicked.id, tokenPicked);
            }
            return tokenPicked;
        }

        const shotRows = sortByCreatedDesc(
            (Array.isArray(shotAssetsMetaRows) ? shotAssetsMetaRows : []).filter((asset) => {
                const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
                const metaShotId = String(meta?.shot_id || asset?.shot_id || '').trim();
                return !stableShotId || !metaShotId || metaShotId === stableShotId;
            })
        );
        if (typeof window !== 'undefined') {
            console.log('[分镜预览][resolveShotAssetByUrl] shotRows', shotRows.map(a => a.id));
        }
        if (!shotRows.length) return null;

        const classifyFrame = (asset) => {
            const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
            return String(meta?.frame_type || meta?.asset_type || '').trim().toLowerCase();
        };

        if (stableModalType === 'start') {
            const rows = shotRows.filter((asset) => {
                const assetType = String(asset?.type || '').trim().toLowerCase();
                const frameType = classifyFrame(asset);
                if (assetType !== 'image') return false;
                return frameType.includes('start') || frameType.includes('keyframe') || frameType.includes('joint_diptych') || frameType === '';
            });
            if (typeof window !== 'undefined') {
                console.log('[分镜预览][resolveShotAssetByUrl] start rows', rows.map(a => a.id));
            }
            return pickByType(rows);
        }

        if (stableModalType === 'end') {
            const rows = shotRows.filter((asset) => {
                const assetType = String(asset?.type || '').trim().toLowerCase();
                const frameType = classifyFrame(asset);
                if (assetType !== 'image') return false;
                return frameType.includes('end');
            });
            if (typeof window !== 'undefined') {
                console.log('[分镜预览][resolveShotAssetByUrl] end rows', rows.map(a => a.id));
            }
            return pickByType(rows);
        }

        if (stableModalType === 'video') {
            const rows = shotRows.filter((asset) => {
                const assetType = String(asset?.type || '').trim().toLowerCase();
                const frameType = classifyFrame(asset);
                return assetType === 'video' || frameType.includes('video');
            });
            if (typeof window !== 'undefined') {
                console.log('[分镜预览][resolveShotAssetByUrl] video rows', rows.map(a => a.id));
            }
            return pickByType(rows);
        }

        return pickByType(shotRows);
    }, [buildAssetUrlTokens, editingShot?.id, shotAssetsMetaIndex, shotAssetsMetaRows]);

    const buildShotAssetDetail = useCallback((asset, fallbackType = 'image', fallbackUrl = '') => {
        const meta = (asset?.meta_info && typeof asset.meta_info === 'object') ? asset.meta_info : {};
        const { width, height, resolution } = parseResolution(meta);
        const aspectRatio = String(meta.aspect_ratio || meta.aspectRatio || '').trim() || deriveAspectRatio(width, height);
        const resolvedUrl = String(asset?.url || fallbackUrl || '').trim();
        const fallbackName = resolvedUrl ? String(resolvedUrl).split('/').pop() : '';
        const displayName = String(
            asset?.name
            || asset?.asset_name
            || meta?.asset_name
            || meta?.display_name
            || meta?.name
            || meta?.title
            || meta?.original_filename
            || meta?.filename
            || asset?.filename
            || fallbackName
            || ''
        ).trim();
        if (typeof window !== 'undefined') {
            console.log('[分镜预览][buildShotAssetDetail]', {
                assetId: asset?.id,
                displayName,
                url: resolvedUrl,
                meta,
            });
        }
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
            url: resolvedUrl,
            displayName,
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
            setShotAssetsMetaRows([]);
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
                const stableRows = Array.isArray(data) ? data : [];
                stableRows.forEach((asset) => {
                    const tokens = buildAssetUrlTokens(asset?.url);
                    tokens.forEach((token) => {
                        if (!token) return;
                        if (!Array.isArray(nextIndex[token])) nextIndex[token] = [];
                        nextIndex[token].push(asset);
                    });
                });
                setShotAssetsMetaIndex(nextIndex);
                setShotAssetsMetaRows(stableRows);
            } catch (e) {
                console.error('Failed to load shot assets metadata', e);
                if (active) {
                    setShotAssetsMetaIndex({});
                    setShotAssetsMetaRows([]);
                }
            } finally {
                if (active) setShotAssetsMetaLoading(false);
            }
        };

        loadShotAssets();
        return () => {
            active = false;
        };
    }, [buildAssetUrlTokens, editingShot?.id, projectId, shotAssetsRefreshKey]);

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

    const getShotVideoPromptForFrameBase = useCallback((shot, techObj = null) => {
        if (!shot || typeof shot !== 'object') return { text: '', source: '' };
        const tech = techObj && typeof techObj === 'object'
            ? techObj
            : parseTechnicalNotesSafe(shot.technical_notes);

        const cnCandidates = [
            tech.video_prompt_cn,
            shot.video_prompt_cn,
            shot.video_content_cn,
            shot.prompt_cn,
            shot.video_content,
            shot.prompt,
        ];
        const enCandidates = [
            shot.video_content,
            shot.prompt,
            tech.video_prompt_en,
            shot.video_prompt_en,
            tech.video_prompt_cn,
            shot.video_prompt_cn,
            shot.video_content_cn,
            shot.prompt_cn,
        ];
        const candidates = resolvedPromptSubmitLang === 'cn' ? cnCandidates : enCandidates;

        for (const candidate of candidates) {
            const text = String(candidate || '').trim();
            if (text) return { text, source: 'video' };
        }

        return { text: '', source: '' };
    }, [parseTechnicalNotesSafe, resolvedPromptSubmitLang]);

    const buildShotFramePromptFromVideoBase = useCallback((shot, frameRole = 'start', techObj = null, fallbackPrompt = '') => {
        const role = frameRole === 'end' ? 'end' : 'start';
        const videoBase = getShotVideoPromptForFrameBase(shot, techObj);
        const baseText = String(videoBase.text || fallbackPrompt || '').trim();
        if (!baseText) {
            return { text: role === 'end' ? 'End frame' : 'A cinematic shot', source: 'fallback' };
        }

        if (videoBase.source !== 'video') {
            return { text: baseText, source: 'fallback' };
        }

        const text = resolvedPromptSubmitLang === 'cn'
            ? (role === 'end'
                ? [
                    '请以以下视频提示词作为唯一基础提示词，自动抽取适合作为本 shot 结束帧的单张静态画面。只生成一张电影静帧，不生成视频、多宫格、连环图、文字说明或分屏版式。结束帧必须对应视频提示词的终段、最终落点、动作结果或收束定格；保持人物身份、环境锚点、光照、构图、道具状态和实体标签一致，不要改写剧情。',
                    '视频提示词:',
                    baseText,
                ].join('\n')
                : [
                    '请以以下视频提示词作为唯一基础提示词，自动抽取适合作为本 shot 起始帧的单张静态画面。只生成一张电影静帧，不生成视频、多宫格、连环图、文字说明或分屏版式。起始帧必须对应视频提示词的 P1、起始状态、动作起点或镜头开端；保持人物身份、环境锚点、光照、构图、道具状态和实体标签一致，不要改写剧情。',
                    '视频提示词:',
                    baseText,
                ].join('\n'))
            : (role === 'end'
                ? [
                    'Use the following video prompt as the only base prompt and automatically extract one still image suitable for this shot end frame. Generate exactly one cinematic still image, not a video, multi-panel image, comic sequence, text label, or split-screen layout. The end frame must correspond to the final phase, final landing state, action result, or closing hold described in the video prompt. Preserve identity, environment anchors, lighting, composition, prop state, and entity tags without rewriting the story.',
                    'Video prompt:',
                    baseText,
                ].join('\n')
                : [
                    'Use the following video prompt as the only base prompt and automatically extract one still image suitable for this shot start frame. Generate exactly one cinematic still image, not a video, multi-panel image, comic sequence, text label, or split-screen layout. The start frame must correspond to P1, the initial state, action starting point, or opening camera setup described in the video prompt. Preserve identity, environment anchors, lighting, composition, prop state, and entity tags without rewriting the story.',
                    'Video prompt:',
                    baseText,
                ].join('\n'));

        return { text, source: 'video' };
    }, [getShotVideoPromptForFrameBase, resolvedPromptSubmitLang]);

    const normalizeShotPromptDefaults = useCallback((shot) => {
        if (!shot || typeof shot !== 'object') return shot;

        const techObj = parseTechnicalNotesSafe(shot.technical_notes);
        const videoPromptCn = String(
            techObj.video_prompt_cn ||
            shot.video_prompt_cn ||
            shot.video_content_cn ||
            shot.prompt_cn ||
            ''
        ).trim();

        if (!videoPromptCn) return shot;

        const next = { ...shot };
        let changed = false;
        let techChanged = false;

        if (!String(next.start_frame || '').trim()) {
            next.start_frame = videoPromptCn;
            changed = true;
        }

        if (!String(next.end_frame || '').trim()) {
            next.end_frame = videoPromptCn;
            changed = true;
        }

        if (!String(next.video_content || '').trim()) {
            next.video_content = videoPromptCn;
            changed = true;
        }

        if (!String(next.prompt || '').trim()) {
            next.prompt = videoPromptCn;
            changed = true;
        }

        if (!String(techObj.start_frame_cn || '').trim()) {
            techObj.start_frame_cn = videoPromptCn;
            techChanged = true;
        }

        if (!String(techObj.end_frame_cn || '').trim()) {
            techObj.end_frame_cn = videoPromptCn;
            techChanged = true;
        }

        if (techChanged) {
            next.technical_notes = JSON.stringify(techObj);
            changed = true;
        }

        return changed ? next : shot;
    }, [parseTechnicalNotesSafe]);

    const mergeLiveSyncTechnicalNotes = useCallback((currentRaw, latestRaw) => {
        const currentNotes = parseTechnicalNotesSafe(currentRaw);
        const latestNotes = parseTechnicalNotesSafe(latestRaw);
        const syncedKeys = [
            'end_frame_url',
            'end_frame_reused_from_start',
            'start_frame_oss_uploaded',
            'end_frame_oss_uploaded',
            'video_oss_uploaded',
            'start_frame_metadata',
            'end_frame_metadata',
            'video_metadata',
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
        if (!shotFilterStorageKey) {
            shotFiltersHydratedRef.current = false;
            return;
        }
        shotFiltersHydratedRef.current = false;
        try {
            const raw = localStorage.getItem(shotFilterStorageKey);
            if (!raw) {
                setSelectedSceneId('all');
                setSceneCodeFilter('');
                setShotIdFilter('');
                return;
            }
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                skipShotFiltersPersistRef.current = true;
                const restoredSceneId = String(parsed.selectedSceneId || 'all').trim() || 'all';
                setSelectedSceneId(restoredSceneId);
                setSceneCodeFilter(String(parsed.sceneCodeFilter || ''));
                setShotIdFilter(String(parsed.shotIdFilter || ''));
            }
        } catch (e) {
            console.warn('Failed to restore shot filters', e);
        } finally {
            shotFiltersHydratedRef.current = true;
        }
    }, [shotFilterStorageKey]);

    useEffect(() => {
        if (!shotFilterStorageKey || !shotFiltersHydratedRef.current) return;
        if (skipShotFiltersPersistRef.current) {
            skipShotFiltersPersistRef.current = false;
            return;
        }
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
        if (!selectedSceneId || selectedSceneId === 'all' || !scenes.length) return;
        const exists = scenes.some((scene) => String(scene.id) === String(selectedSceneId));
        if (!exists) setSelectedSceneId('all');
    }, [scenes, selectedSceneId]);

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
        const projectInfo = project?.global_info || {};
        const basicInfo = projectInfo?.basic_info || {};
        if (!info && !projectInfo) return "";
        const { includeStyle = true } = options || {};
        const parts = [];
        const projectType = String(
            info?.type
            || basicInfo?.type
            || projectInfo?.type
            || ''
        ).trim();
        if (projectType) parts.push(`Type: ${projectType}`);
        // Append explicit labels so the model understands the context
        const globalStyle = getShotGlobalStyleText();
        if (includeStyle && globalStyle) parts.push(`Style: ${globalStyle}`);
        if (info?.tone) parts.push(`Tone: ${info.tone}`);
        
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

    const closeMediaPicker = useCallback(() => {
        setPickerConfig((prev) => {
            if (!prev?.isOpen && !prev?.callback && !prev?.context) return prev;
            return { isOpen: false, callback: null, context: null };
        });
        pickerCallbackRef.current = null;
    }, []);

    const openMediaPicker = (callback, context = {}) => {
        if (typeof window !== 'undefined') {
            console.log('[分镜][openMediaPicker] context', context);
        }
        pickerCallbackRef.current = callback;
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

            const updatedShot = await updateShot(shotId, payload);
            const nextShot = (updatedShot && typeof updatedShot === 'object')
                ? { ...(currentShot || editingBase || {}), ...updatedShot, ...changes }
                : { ...(currentShot || editingBase || {}), ...changes };
            setShots(prev => prev.map((s) => (String(s?.id || '').trim() === stableShotId ? { ...s, ...nextShot } : s)));

            // Sync editingShot safely
            setEditingShot(prev => {
                if (prev && String(prev?.id || '').trim() === stableShotId) {
                    return { ...prev, ...nextShot };
                }
                return prev;
            });
            return nextShot;
        } catch(e) { 
            console.error("Update Shot Failed", e); 
            onLog?.(`Failed to save changes: ${getReadableErrorDetail(e)}`, "error");
            throw e;
        }
    }

    const persistShotFields = async (updates = {}) => {
        if (!editingShot?.id) return;
        setEditingShot(prev => ({ ...(prev || {}), ...updates }));
        return await onUpdateShot(editingShot.id, updates);
    };

    const persistEditingShotUpdates = async (updates = {}) => {
        if (!editingShot?.id) return;
        setEditingShot(prev => ({ ...(prev || {}), ...updates }));
        return await onUpdateShot(editingShot.id, updates);
    };

    const handleRestoreShotFromAiStaging = useCallback(async () => {
        if (!editingShot?.id || restoringFromStaging) return;

        const sceneId = Number(editingShot.scene_id || 0);
        const displayShotId = String(editingShot.shot_id || '').trim();
        if (!sceneId || !displayShotId) {
            showNotification(t('缺少场景或镜头 ID', 'Missing scene or shot ID'), 'error');
            return;
        }

        if (!await confirmUiMessage(t(
            '从对应场景的 AI 镜头暂存区恢复分镜提示词等信息？已生成的图片、视频等媒体不会被清除。',
            'Restore shot prompts from this scene\'s AI staging area? Generated images, videos, and other media will be preserved.'
        ))) {
            return;
        }

        setRestoringFromStaging(true);
        try {
            const latest = await getSceneLatestAIResult(sceneId);
            const rawText = latest?.raw_text || '';
            const serverContent = Array.isArray(latest?.content) ? latest.content : [];
            const resolved = resolveAiShotsStagingRows(
                rawText,
                serverContent,
                Array.isArray(latest?.warnings) ? latest.warnings : []
            );
            const stagingRow = findStagingRowByShotId(resolved.content, displayShotId);
            if (!stagingRow) {
                showNotification(
                    t(`暂存区未找到镜头 ${displayShotId} 的分镜记录`, `No staging record found for shot ${displayShotId}`),
                    'error'
                );
                return;
            }

            const sceneMeta = scenes.find((scene) => String(scene?.id) === String(sceneId));
            const fallbackSceneCode = String(
                editingShot.scene_code || sceneMeta?.scene_no || sceneMeta?.scene_id || ''
            ).trim();
            const payload = buildShotWritePayloadFromRow(stagingRow, {
                fallbackSceneCode,
                existingTechnicalNotes: editingShot.technical_notes || '',
            });

            await onUpdateShot(editingShot.id, payload);
            showNotification(t('已从 AI 暂存区恢复分镜信息', 'Restored shot info from AI staging area'), 'success');
            onLog?.(
                t(`镜头 ${displayShotId} 已从 AI 暂存区恢复分镜提示词`, `Shot ${displayShotId} prompts restored from AI staging`),
                'success'
            );
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || t('未知错误', 'Unknown error');
            showNotification(t(`恢复分镜失败: ${detail}`, `Restore failed: ${detail}`), 'error');
            onLog?.(t(`恢复分镜失败: ${detail}`, `Restore failed: ${detail}`), 'error');
        } finally {
            setRestoringFromStaging(false);
        }
    }, [editingShot, onLog, onUpdateShot, restoringFromStaging, scenes, showNotification, t]);

    const handleApplyTunedShotPrompt = useCallback(async (refinedPrompt) => {
        if (!editingShot?.id) return;
        const nextPrompt = String(refinedPrompt || '').trim();
        if (!nextPrompt) return;

        const tech = parseTechnicalNotesSafe(editingShot.technical_notes);
        tech.manual_video_prompt = true;

        let updates;
        if (shotPromptDisplayLang === 'cn') {
            tech.video_prompt_cn = nextPrompt;
            if (tech.start_frame_cn || tech.keyframes_cn || tech.end_frame_cn || tech.shot_prompt_cn) {
                tech.shot_prompt_cn = [
                    `起始帧：${String(tech.start_frame_cn || '').trim()}`,
                    `视频：${nextPrompt}`,
                    `关键帧：${String(tech.keyframes_cn || '').trim()}`,
                    `收尾帧：${String(tech.end_frame_cn || '').trim()}`,
                ].join('<br>');
            }
            updates = {
                technical_notes: JSON.stringify(tech),
                prompt_preview_cn: nextPrompt,
            };
        } else {
            updates = {
                ...buildVideoPromptEnUpdates(nextPrompt),
                technical_notes: JSON.stringify(tech),
                prompt_preview_en: nextPrompt,
            };
        }

        setEditingShot((prev) => ({ ...(prev || {}), ...updates }));
        await onUpdateShot(editingShot.id, updates);
    }, [buildVideoPromptEnUpdates, editingShot, onUpdateShot, parseTechnicalNotesSafe, shotPromptDisplayLang]);

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

    const normalizeImageRefList = (refs = []) => normalizeMediaRefList(refs).filter((url) => !isVideoMediaRefUrl(url));

    /** Same image refs as the video "Refs" panel — source of truth for shot image generation defaults. */
    const resolveShotVideoImageRefs = useCallback((shotSnapshot, resolvedEntities = null) => {
        if (!shotSnapshot) return [];

        let tech = {};
        try {
            tech = JSON.parse(shotSnapshot.technical_notes || '{}');
            if (!tech || typeof tech !== 'object') tech = {};
        } catch {
            tech = {};
        }

        const entityPool = Array.isArray(resolvedEntities) ? resolvedEntities : entities;
        const activeRefs = resolveShotVideoActiveRefs({
            shotLike: shotSnapshot,
            techObj: tech,
            entityPool,
            includeAdditionalAutoRefs: false,
            preferredEpisodeId: activeEpisode?.id ?? shotSnapshot?.episode_id ?? null,
        });

        return normalizeImageRefList(activeRefs);
    }, [activeEpisode?.id, entities]);

    /**
     * Default refs for start/end/keyframe/joint image gen = video panel refs.
     * Start/end panel lists are used only after the user manually edits that panel.
     * End frame still prepends the current start frame for continuity when unlocked.
     */
    const resolveDefaultShotImageGenerationRefs = useCallback((shotSnapshot, panel = 'start', resolvedEntities = null) => {
        if (!shotSnapshot) return [];

        let tech = {};
        try {
            tech = JSON.parse(shotSnapshot.technical_notes || '{}');
            if (!tech || typeof tech !== 'object') tech = {};
        } catch {
            tech = {};
        }

        const storageKey = panel === 'end' ? 'end_ref_image_urls' : 'ref_image_urls';
        const userEdited = Boolean(tech[`${storageKey}_user_edited`]);
        const deletedRefs = new Set(
            (Array.isArray(tech.deleted_ref_urls) ? tech.deleted_ref_urls : [])
                .map((url) => String(url || '').trim())
                .filter(Boolean),
        );

        let refs;
        if (userEdited && Array.isArray(tech[storageKey])) {
            refs = normalizeImageRefList(tech[storageKey]);
        } else {
            refs = resolveShotVideoImageRefs(shotSnapshot, resolvedEntities);
        }

        if (panel === 'end' && !userEdited) {
            const currentStartFrame = String(shotSnapshot?.image_url || '').trim();
            if (
                currentStartFrame
                && !deletedRefs.has(currentStartFrame)
                && !refs.includes(currentStartFrame)
            ) {
                refs = [currentStartFrame, ...refs];
            }
        }

        return normalizeImageRefList(refs.filter((url) => !deletedRefs.has(String(url || '').trim())));
    }, [resolveShotVideoImageRefs]);

    const resolveJointShotDiptychRefs = useCallback((shotSnapshot, _rawStartPrompt = '', _rawEndPrompt = '', resolvedEntities = null) => {
        return resolveShotVideoImageRefs(shotSnapshot, resolvedEntities);
    }, [resolveShotVideoImageRefs]);

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

    const cropGeneratedGridPanelToBlob = useCallback(async ({
        image,
        columns,
        rows,
        panelIndex,
        targetAspectRatio,
        exportSize,
    }) => {
        const sourceWidth = Number(image?.naturalWidth || image?.width || 0);
        const sourceHeight = Number(image?.naturalHeight || image?.height || 0);
        const targetRatio = parseAspectRatioValue(targetAspectRatio);

        if (!sourceWidth || !sourceHeight || !targetRatio || !columns || !rows) {
            throw new Error('invalid generated image dimensions for grid split crop');
        }

        const safeColumns = Math.max(1, Number(columns));
        const safeRows = Math.max(1, Number(rows));
        const safeIndex = Math.max(0, Math.min((safeColumns * safeRows) - 1, Number(panelIndex) || 0));
        const columnIndex = safeIndex % safeColumns;
        const rowIndex = Math.floor(safeIndex / safeColumns);
        const cellWidth = sourceWidth / safeColumns;
        const cellHeight = sourceHeight / safeRows;
        const seamTrimX = Math.max(2, Math.min(12, Math.round(cellWidth / 208)));
        const seamTrimY = Math.max(2, Math.min(12, Math.round(cellHeight / 208)));
        const trimX = Math.min(seamTrimX, Math.max(0, Math.round(cellWidth * 0.01)));
        const trimY = Math.min(seamTrimY, Math.max(0, Math.round(cellHeight * 0.01)));

        const panelX = (columnIndex * cellWidth) + trimX;
        const panelY = (rowIndex * cellHeight) + trimY;
        const panelWidth = Math.max(1, cellWidth - (trimX * 2));
        const panelHeight = Math.max(1, cellHeight - (trimY * 2));
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

        const outputWidth = Number(exportSize?.width) > 0 ? Number(exportSize.width) : Math.max(1, Math.round(cropWidth));
        const outputHeight = Number(exportSize?.height) > 0 ? Number(exportSize.height) : Math.max(1, Math.round(cropHeight));
        const canvas = document.createElement('canvas');
        canvas.width = outputWidth;
        canvas.height = outputHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            throw new Error('canvas context unavailable during grid split crop');
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
                    reject(new Error('failed to encode grid split image'));
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
        const legacyStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || shotSnapshot.start_frame || shotSnapshot.video_content || 'A cinematic shot')
            : (shotSnapshot.start_frame || cnStartPrompt || shotSnapshot.video_content || 'A cinematic shot');
        const legacyEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || shotSnapshot.end_frame || 'End frame')
            : (shotSnapshot.end_frame || cnEndPrompt || 'End frame');
        const startFramePrompt = buildShotFramePromptFromVideoBase(shotSnapshot, 'start', techNotes, legacyStartPrompt);
        const endFramePrompt = buildShotFramePromptFromVideoBase(shotSnapshot, 'end', techNotes, legacyEndPrompt);
        const rawStartPrompt = startFramePrompt.text;
        const rawEndPrompt = endFramePrompt.text;

        const normalizedEndPrompt = String(legacyEndPrompt || '').trim().toUpperCase();
        if (endFramePrompt.source !== 'video' && ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt)) {
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
        const legacyStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || stableShot?.start_frame || stableShot?.video_content || 'A cinematic shot')
            : (stableShot?.start_frame || cnStartPrompt || stableShot?.video_content || 'A cinematic shot');
        const legacyEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || stableShot?.end_frame || 'End frame')
            : (stableShot?.end_frame || cnEndPrompt || 'End frame');
        const startFramePrompt = buildShotFramePromptFromVideoBase(stableShot, 'start', techNotes, legacyStartPrompt);
        const endFramePrompt = buildShotFramePromptFromVideoBase(stableShot, 'end', techNotes, legacyEndPrompt);
        const rawStartPrompt = startFramePrompt.text;
        const rawEndPrompt = endFramePrompt.text;

        const normalizedEndPrompt = String(legacyEndPrompt || '').trim().toUpperCase();
        if (endFramePrompt.source !== 'video' && ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt)) {
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
    }, [activeEpisode?.episode_info, activeEpisode?.id, activeImageCapabilityProfile?.aspectRatios, activeImageCapabilityProfile?.imageSizeValues, applyJointShotDiptychResult, awaitShotGenerationEntities, buildEntityNegativePrompt, buildShotFramePromptFromVideoBase, getGlobalContextStr, injectEntityFeatures, onLog, project?.global_info, projectId, resolveJointShotDiptychRefs, resolvedPromptSubmitLang, setPendingJointDiptychImageJob, setShotGeneratingState, showNotification, t]);

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

    const getEditingShotTechNotes = useCallback(() => {
        try {
            const parsed = JSON.parse(editingShot?.technical_notes || '{}');
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch {
            return {};
        }
    }, [editingShot?.technical_notes]);

    const editingShotReviewNotes = useMemo(
        () => String(getEditingShotTechNotes().review_notes || '').trim(),
        [getEditingShotTechNotes],
    );
    const editingShotEditNotes = useMemo(
        () => String(getEditingShotTechNotes().edit_notes || '').trim(),
        [getEditingShotTechNotes],
    );

    const openShotNotePopover = useCallback((kind) => {
        const tech = getEditingShotTechNotes();
        const field = kind === 'review' ? 'review_notes' : 'edit_notes';
        setShotNoteDraft(String(tech[field] || ''));
        setShotNotePopover((prev) => (prev === kind ? null : kind));
    }, [getEditingShotTechNotes]);

    const saveShotNotePopover = useCallback(async () => {
        if (!shotNotePopover) return;
        const field = shotNotePopover === 'review' ? 'review_notes' : 'edit_notes';
        const trimmed = String(shotNoteDraft || '').trim();
        await updateShotTechnicalNotes((techObj) => {
            if (trimmed) {
                techObj[field] = trimmed;
            } else {
                delete techObj[field];
            }
        });
        setShotNotePopover(null);
    }, [shotNoteDraft, shotNotePopover, updateShotTechnicalNotes]);

    useEffect(() => {
        setShotNotePopover(null);
        setShotNoteDraft('');
    }, [editingShot?.id]);

    useEffect(() => {
        if (!shotNotePopover) return undefined;
        const handleClickOutside = (event) => {
            if (shotNotePopoverRef.current && !shotNotePopoverRef.current.contains(event.target)) {
                setShotNotePopover(null);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [shotNotePopover]);

    const renderShotNotePopoverPanel = (kind) => {
        if (shotNotePopover !== kind) return null;
        const isReview = kind === 'review';
        return (
            <div
                className="absolute top-full right-0 mt-1 w-72 rounded-lg border border-white/10 bg-[#111114] shadow-2xl z-[120] p-3 space-y-2"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                    {isReview ? t('审核意见', 'Review Notes') : t('剪辑意见', 'Edit Notes')}
                </div>
                <textarea
                    className="w-full bg-black/30 border border-white/10 rounded p-2 text-xs text-white min-h-[88px] focus:outline-none focus:border-primary/50 resize-y"
                    value={shotNoteDraft}
                    onChange={(e) => setShotNoteDraft(e.target.value)}
                    placeholder={isReview ? t('填写审核意见...', 'Enter review notes...') : t('填写剪辑意见...', 'Enter edit notes...')}
                    autoFocus
                />
                <div className="flex items-center justify-end gap-2">
                    <button
                        type="button"
                        onClick={() => setShotNotePopover(null)}
                        className="px-2 py-1 text-[11px] rounded border border-white/10 text-white/70 hover:bg-white/5"
                    >
                        {t('取消', 'Cancel')}
                    </button>
                    <button
                        type="button"
                        onClick={() => { saveShotNotePopover(); }}
                        className="px-2 py-1 text-[11px] rounded bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30"
                    >
                        {t('保存', 'Save')}
                    </button>
                </div>
            </div>
        );
    };

    const applyVideoModeToShot = async (mode) => {
        await updateShotTechnicalNotes((techObj) => {
            techObj.video_mode_unified = mode;
            if (mode === 'entity_refs') {
                techObj.video_ref_submit_mode = 'entity_refs';
                const videoRefPromptText = buildShotVideoRefPromptText(editingShot, techObj);
                const promptEntityRefs = collectMatchedEntityImageUrlsFromPrompt({
                    promptText: videoRefPromptText,
                    entityPool: entities,
                    includeAssociatedEntities: false,
                    preferredEpisodeId: activeEpisode?.id ?? editingShot?.episode_id ?? null,
                });
                techObj.video_ref_image_urls = normalizeMediaRefList(promptEntityRefs);

                const matchedEntities = collectMatchedEntitiesFromPrompt({
                    promptText: videoRefPromptText,
                    entityPool: entities,
                    includeAssociatedEntities: false,
                    preferredEpisodeId: activeEpisode?.id ?? editingShot?.episode_id ?? null,
                });
                const eMap = {};
                matchedEntities.forEach((entity) => {
                    if (entity?.id && entity?.image_url) {
                        eMap[String(entity.id)] = String(entity.image_url);
                    }
                });
                techObj.entity_url_map = eMap;

            } else {
                techObj.video_gen_mode = mode;
                techObj.video_ref_submit_mode = 'auto';
                const promptEntityRefs = collectMatchedEntityImageUrlsFromPrompt({
                    promptText: buildShotVideoRefPromptText(editingShot, techObj),
                    entityPool: entities,
                    includeAssociatedEntities: false,
                    preferredEpisodeId: activeEpisode?.id ?? editingShot?.episode_id ?? null,
                });
                techObj.video_ref_image_urls = buildAutoVideoRefList(editingShot, techObj, mode, promptEntityRefs);
                
                const autoMap = {};
                entities.forEach(e => {
                    if (e.id && e.image_url) {
                        autoMap[String(e.id)] = String(e.image_url);
                    }
                });
                techObj.entity_url_map = autoMap;
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

    const ensureSceneHasNoExistingShots = async (sceneId) => {
        try {
            const existing = await fetchShots(sceneId);
            const count = Array.isArray(existing) ? existing.length : 0;
            if (count <= 0) return true;

            await confirmUiMessage(
                t(
                    `本场景已存在 ${count} 条分镜，无法重复生成。如需重做，请先删除现有分镜。`,
                    `This scene already has ${count} shot(s). Generation skipped. Delete existing shots first if you need to regenerate.`
                ),
                {
                    title: t('已有分镜', 'Shots Already Exist'),
                    confirmText: t('知道了', 'OK'),
                    cancelText: t('关闭', 'Close'),
                }
            );
            onLog?.(
                t(`场景 ${sceneId} 已有分镜（${count}），跳过生成。`, `Scene ${sceneId} already has ${count} shot(s); generation skipped.`),
                'warning'
            );
            return false;
        } catch (e) {
            const detail = e?.message || String(e);
            onLog?.(`Failed to check existing shots - ${detail}`, 'error');
            notifyUiMessage(t(`检查现有分镜失败：${detail}`, `Failed to check existing shots: ${detail}`), 'error');
            return false;
        }
    };

    const handleGenerateShots = async (sceneId) => {
        if (sceneId === 'all') {
            onLog?.("Please select a specific scene to generate shots.", "warning");
            return;
        }
        const canGenerate = await ensureSceneHasNoExistingShots(sceneId);
        if (!canGenerate) return;

        onLog?.(`Generating shots for Scene ${sceneId}...`, 'info');
        try {
            const result = await generateSceneShots(sceneId, { function_name: 'script_analysis' });
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
        }
    };

    const handleMediaSelect = useCallback((url, type, selectedItems) => {
        if (typeof pickerCallbackRef.current === 'function') {
            pickerCallbackRef.current(url, type, selectedItems);
        }
        closeMediaPicker();
    }, [closeMediaPicker]);

    const refreshShots = useCallback(async () => {
        if (!selectedSceneId || !activeEpisode?.id) return;
        const requestSeq = ++shotsRefreshRequestSeqRef.current;
        setIsShotsLoading(true);

        const getSceneCodeFromShot = (shot) => {
            const explicit = String(shot?.scene_code || '').trim();
            if (explicit) return explicit.toUpperCase();
            const shotId = String(shot?.shot_id || '').trim().toUpperCase();
            const m = shotId.match(/^(EP\d{2}_SC\d{2}[A-Za-z]*)/);
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
            const normalizedAllShots = Array.isArray(allShots) ? allShots.map(normalizeShotPromptDefaults) : [];
            allEpisodeShotsRef.current = normalizedAllShots;

            let filtered = selectedSceneId === 'all'
                ? normalizedAllShots
                : normalizedAllShots.filter(s => String(s.scene_id) === String(selectedSceneId));

            if (normalizedSceneCode) {
                filtered = filtered.filter((shot) => {
                    const sceneCode = getSceneCodeFromShot(shot);
                    return sceneCode.includes(normalizedSceneCode);
                });
            }

            if (normalizedShotId) {
                filtered = filtered.filter((shot) => String(shot?.shot_id || '').toUpperCase().includes(normalizedShotId));
            }

            filtered = dedupeShotsForDisplay(filtered, {
                sceneId: selectedSceneId === 'all' ? null : selectedSceneId,
            });

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
    }, [activeEpisode?.id, selectedSceneId, sceneCodeFilter, shotIdFilter, normalizeShotPromptDefaults]);

    const syncShotVideoAfterOssPersist = useCallback(async ({
        shotId,
        jobId = '',
        initialUrl = '',
        maxWaitMs = EPHEMERAL_VIDEO_OSS_SYNC_MAX_MS,
    } = {}) => {
        const stableShotId = String(shotId || '').trim();
        if (!stableShotId) return false;
        if (activeOssVideoSyncRef.current.has(stableShotId)) return false;
        activeOssVideoSyncRef.current.add(stableShotId);

        try {
        const resolveLocalShot = () => (
            (editingShotRef.current && String(editingShotRef.current?.id) === stableShotId ? editingShotRef.current : null)
            || (shotsRef.current || []).find((item) => String(item?.id) === stableShotId)
            || { id: stableShotId }
        );

        const applyPersistedShot = async (shotRecord) => {
            if (!shotRecord || !isShotVideoOssPersistComplete(shotRecord)) return false;
            const normalized = normalizeShotPromptDefaults(shotRecord);
            const patch = {
                video_url: normalized.video_url,
                technical_notes: normalized.technical_notes,
            };

            setShots((prev) => prev.map((item) => (
                String(item?.id) === stableShotId ? { ...item, ...patch } : item
            )));
            setEditingShot((prev) => (prev && String(prev.id) === stableShotId ? { ...prev, ...patch } : prev));
            setMediaPersistGraceRefreshSeq((seq) => seq + 1);
            refreshShotAssetsMeta();

            try {
                await onUpdateShot(stableShotId, patch);
            } catch (persistErr) {
                console.warn('[syncShotVideoAfterOssPersist] shot persist failed:', persistErr);
            }

            await refreshShots();
            return true;
        };

        const startedAt = Date.now();
        const stableJobId = String(jobId || '').trim();

        while (Date.now() - startedAt < maxWaitMs) {
            if (stableJobId) {
                try {
                    const status = await getVideoGenerationJobStatus(stableJobId);
                    const resultUrl = extractVideoJobResultUrl(status);
                    const resultMeta = status?.result?.metadata && typeof status.result.metadata === 'object'
                        ? status.result.metadata
                        : {};
                    if (
                        resultUrl
                        && (
                            isDurablePersistedMediaUrl(resultUrl, resultMeta)
                            || resultMeta.oss_uploaded_success === true
                        )
                    ) {
                        const merged = mergeShotVideoOssPersistState(resolveLocalShot(), {
                            videoUrl: resultUrl,
                            ossUploaded: true,
                        });
                        if (await applyPersistedShot(merged)) {
                            releaseShotVideoUi({ shotId: stableShotId, jobId: stableJobId });
                            onLog?.(t('视频已写入 OSS，界面已刷新。', 'Video persisted to OSS; UI refreshed.'), 'success');
                            return true;
                        }
                    }
                } catch (syncErr) {
                    console.warn('[syncShotVideoAfterOssPersist] job poll failed:', syncErr);
                }
            }

            try {
                const latestShot = await fetchShot(stableShotId);
                if (latestShot?.id && await applyPersistedShot(latestShot)) {
                    releaseShotVideoUi({ shotId: stableShotId, jobId: stableJobId });
                    onLog?.(t('视频已写入 OSS，界面已刷新。', 'Video persisted to OSS; UI refreshed.'), 'success');
                    return true;
                }
            } catch (syncErr) {
                console.warn('[syncShotVideoAfterOssPersist] fetchShot failed:', syncErr);
            }

            const localShot = resolveLocalShot();
            const localUrl = String(localShot?.video_url || initialUrl || '').trim();
            if (localUrl && isDurablePersistedMediaUrl(localUrl, parseShotTechnicalNotes(localShot?.technical_notes)?.video_metadata)) {
                const merged = mergeShotVideoOssPersistState(localShot, { videoUrl: localUrl, ossUploaded: true });
                if (await applyPersistedShot(merged)) {
                    releaseShotVideoUi({ shotId: stableShotId, jobId: stableJobId });
                    onLog?.(t('视频已写入 OSS，界面已刷新。', 'Video persisted to OSS; UI refreshed.'), 'success');
                    return true;
                }
            }

            await new Promise((resolve) => {
                setTimeout(resolve, EPHEMERAL_VIDEO_OSS_SYNC_INTERVAL_MS);
            });
        }

        return false;
        } finally {
            activeOssVideoSyncRef.current.delete(stableShotId);
        }
    }, [normalizeShotPromptDefaults, onLog, onUpdateShot, refreshShotAssetsMeta, refreshShots, releaseShotVideoUi, t]);

    useEffect(() => {
        setHasShotInitialLoadCompleted(false);
        allEpisodeShotsRef.current = [];
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
                const isMultiPanel = payload?.mode === 'multi_panel';
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
                if (isJointDiptych || isMultiPanel) {
                    setShotGeneratingState(stableShotId, 'start', true);
                    setShotGeneratingState(stableShotId, 'end', true);
                } else {
                    setShotGeneratingState(stableShotId, stableKind, true);
                }

                while (!cancelled) {
                    try {
                        const status = await getImageGenerationJobStatus(jobId);
                        const phase = normalizeGenerationPhase(status?.status);
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

                        if (resultUrl || phase === 'succeeded') {
                            if (isJointDiptych || isMultiPanel) {
                                clearPendingJointDiptychImageJob(stableShotId);
                                clearPendingImageJob(stableShotId, stableKind);
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
                                    } else if (isMultiPanel) {
                                        setShotGeneratingState(stableShotId, 'cropping', true);
                                        let recoveredTech = {};
                                        try {
                                            recoveredTech = JSON.parse(currentShot?.technical_notes || '{}');
                                        } catch {
                                            recoveredTech = {};
                                        }
                                        const recoveredPreset = normalizeMultiPanelPresetKey(
                                            recoveredTech.multi_panel_image_preset || multiPanelPresetKeyRef.current || '4panel'
                                        );
                                        const nextTech = {
                                            ...recoveredTech,
                                            multi_panel_image_url: resultUrl,
                                            multi_panel_image_preset: recoveredPreset,
                                        };
                                        const nextTechNotes = JSON.stringify(nextTech);
                                        try {
                                            await onUpdateShot(stableShotId, { technical_notes: nextTechNotes });
                                        } catch (persistErr) {
                                            console.warn('Failed to persist recovered multi-panel URL before split:', persistErr);
                                        }
                                        const applySplit = applyMultiPanelImageResultRef.current;
                                        if (typeof applySplit !== 'function') {
                                            await onUpdateShot(stableShotId, {
                                                image_url: resultUrl,
                                                technical_notes: nextTechNotes,
                                            });
                                            setEditingShot((prev) => (prev && String(prev.id) === stableShotId
                                                ? { ...prev, image_url: resultUrl, technical_notes: nextTechNotes }
                                                : prev));
                                            onLog?.(t(
                                                `已恢复多画格原图（镜头 ${stableShotId}），请点击「重新拆分」。`,
                                                `Recovered multi-panel source for shot ${stableShotId}; click Re-split to crop panels.`
                                            ), 'warning');
                                        } else {
                                            await applySplit({
                                                shotRecord: { ...(currentShot || {}), technical_notes: nextTechNotes },
                                                compositeUrl: resultUrl,
                                                presetKey: recoveredPreset,
                                                basePrompt: String(recoveredTech.video_prompt_cn || recoveredTech.video_prompt || '').trim(),
                                                promptLanguage: resolvedPromptSubmitLang,
                                            });
                                        }
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
                                        const nextData = { technical_notes: JSON.stringify(tech) };
                                        await onUpdateShot(stableShotId, nextData);
                                        setEditingShot((prev) => {
                                            if (!prev || String(prev.id) !== stableShotId) return prev;
                                            return { ...prev, ...nextData };
                                        });
                                    }
                                    onLog?.(isJointDiptych
                                        ? `Recovered joint start/end generation completed for shot ${stableShotId}.`
                                        : (isMultiPanel
                                            ? `Recovered multi-panel generation completed for shot ${stableShotId}.`
                                            : `Recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} generation completed for shot ${stableShotId}.`), 'success');
                                    refreshShotAssetsMeta();
                                    Promise.resolve(refreshShots()).catch((refreshErr) => {
                                        console.warn('Refresh shots after recovered image job failed:', refreshErr);
                                    });
                                } catch (applyErr) {
                                    console.error('Failed to apply recovered image job result:', applyErr);
                                    onLog?.(isJointDiptych
                                        ? `Failed to apply recovered joint start/end result for shot ${stableShotId}: ${applyErr.message}`
                                        : (isMultiPanel
                                            ? `Failed to apply recovered multi-panel result for shot ${stableShotId}: ${applyErr.message}`
                                            : `Failed to apply recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} result for shot ${stableShotId}: ${applyErr.message}`), 'error');
                                } finally {
                                    if (isJointDiptych || isMultiPanel) {
                                        setShotGeneratingState(stableShotId, 'cropping', false);
                                    }
                                }
                            }
                            break;
                        }

                        if (phase === 'failed' || phase === 'canceled') {
                            if (isJointDiptych || isMultiPanel) {
                                clearPendingJointDiptychImageJob(stableShotId);
                                clearPendingImageJob(stableShotId, stableKind);
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
                                : (isMultiPanel
                                    ? `Recovered multi-panel generation failed for shot ${stableShotId}: ${errMsg}`
                                    : `Recovered ${stableKind === 'end' ? 'end frame' : 'start frame'} generation failed for shot ${stableShotId}: ${errMsg}`), tone);
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
        refreshShotAssetsMeta,
        refreshShots,
        resolvedPromptSubmitLang,
        setPendingImageJob,
        setPendingJointDiptychImageJob,
        setEditingShot,
        setShotGeneratingState,
        t,
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

                let showedGeneratingUi = false;

                try {
                    while (!cancelled) {
                        try {
                            const status = await getVideoGenerationJobStatus(jobId);
                            const phase = normalizeGenerationPhase(status?.status);
                            setVideoStatuses(prev => ({ ...prev, [stableShotId]: String(status?.status || phase).toLowerCase() }));
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

                            if (resultUrl || phase === 'succeeded') {
                                const serverBoundVideoUrl = resultUrl;
                                if (serverBoundVideoUrl) {
                                    const newData = { video_url: serverBoundVideoUrl };
                                    try {
                                        await onUpdateShot(stableShotId, newData);
                                    } catch (persistErr) {
                                        console.warn('Resume video job save failed:', persistErr);
                                    }
                                    setShots((prev) => prev.map((shot) => (
                                        String(shot?.id || '') === stableShotId ? { ...shot, ...newData } : shot
                                    )));
                                    setEditingShot(prev => (prev && String(prev.id) === stableShotId ? { ...prev, ...newData } : prev));
                                    onLog?.(`Recovered video generation completed for shot ${stableShotId}.`, 'success');
                                }
                                if (serverBoundVideoUrl && shotVideoNeedsOssPersist({ id: stableShotId, video_url: serverBoundVideoUrl })) {
                                    const synced = await syncShotVideoAfterOssPersist({
                                        shotId: stableShotId,
                                        jobId,
                                        initialUrl: serverBoundVideoUrl,
                                    });
                                    if (!synced) {
                                        onLog?.(
                                            t(
                                                '警告：恢复的视频仍为临时地址，尚未写入 OSS。请在镜头详情中点击「临时视频」。',
                                                'Warning: recovered video is still a temporary URL and was not stored to OSS. Click "Temp Video" in shot details.'
                                            ),
                                            'warning'
                                        );
                                    }
                                }
                                releaseShotVideoUi({ shotId: stableShotId, jobId });
                                refreshShotAssetsMeta();
                                await refreshShots();
                                break;
                            }

                            if (phase === 'failed' || phase === 'canceled') {
                                const serverBoundVideoUrl = resultUrl;
                                if (serverBoundVideoUrl) {
                                    const newData = { video_url: serverBoundVideoUrl };
                                    try {
                                        await onUpdateShot(stableShotId, newData);
                                    } catch (persistErr) {
                                        console.warn('Resume video job save failed:', persistErr);
                                    }
                                    setShots((prev) => prev.map((shot) => (
                                        String(shot?.id || '') === stableShotId ? { ...shot, ...newData } : shot
                                    )));
                                    setEditingShot(prev => (prev && String(prev.id) === stableShotId ? { ...prev, ...newData } : prev));
                                    onLog?.(`Recovered video generation completed for shot ${stableShotId}.`, 'success');
                                    if (shotVideoNeedsOssPersist({ id: stableShotId, video_url: serverBoundVideoUrl })) {
                                        const synced = await syncShotVideoAfterOssPersist({
                                            shotId: stableShotId,
                                            jobId,
                                            initialUrl: serverBoundVideoUrl,
                                        });
                                        if (!synced) {
                                            onLog?.(
                                                t(
                                                    '警告：恢复的视频仍为临时地址，尚未写入 OSS。请在镜头详情中点击「临时视频」。',
                                                    'Warning: recovered video is still a temporary URL and was not stored to OSS. Click "Temp Video" in shot details.'
                                                ),
                                                'warning'
                                            );
                                        }
                                    }
                                    releaseShotVideoUi({ shotId: stableShotId, jobId });
                                    refreshShotAssetsMeta();
                                    await refreshShots();
                                    break;
                                }

                                releaseShotVideoUi({ shotId: stableShotId, jobId });
                                const errMsg = String(status?.error || 'unknown error');
                                const tone = String(phase).startsWith('cancel') ? 'warning' : 'error';
                                onLog?.(`Recovered video generation failed for shot ${stableShotId}: ${errMsg}`, tone);
                                break;
                            }

                            if (!showedGeneratingUi) {
                                setShotGeneratingState(stableShotId, 'video', true);
                                showedGeneratingUi = true;
                            }
                        } catch (e) {
                            const detail = e?.response?.data?.detail || e?.message || '';
                            const detailLower = String(detail).toLowerCase();
                            if (detailLower.includes('job not found')) {
                                releaseShotVideoUi({ shotId: stableShotId, jobId });
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
        clearPendingVideoJob,
        forceClearShotVideoJob,
        normalizeGenerationPhase,
        onLog,
        onUpdateShot,
        readVideoJobStateStorage,
        releaseShotVideoUi,
        refreshShotAssetsMeta,
        refreshShots,
        setEditingShot,
        setPendingVideoJob,
        setShotGeneratingState,
        syncShotVideoAfterOssPersist,
        t,
        writeVideoJobStateStorage,
    ]);

    useEffect(() => {
        if (!editingShot?.id || !activeEpisode?.id) return;

        let cancelled = false;
        const stableShotId = String(editingShot.id || '').trim();

        const reconcile = async () => {
            if (!stableShotId) return;

            await syncShotMediaRuntimeState({
                shotId: stableShotId,
                mediaKey: 'video',
                preferPoolLookup: false,
            });
            if (cancelled) return;
            await syncShotMediaRuntimeState({
                shotId: stableShotId,
                mediaKey: 'start',
                preferPoolLookup: false,
            });
            if (cancelled) return;
            await syncShotMediaRuntimeState({
                shotId: stableShotId,
                mediaKey: 'end',
                preferPoolLookup: false,
            });
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
        // Runs rebindShotMediaAssets automatically when an episode is activated
        if (!projectId || !activeEpisode?.id) return;
        const key = `${projectId}:${activeEpisode.id}`;
        if (mediaRebindAttemptedRef.current === key) return;
        mediaRebindAttemptedRef.current = key;

        let cancelled = false;
        (async () => {
            try {
                const res = await backfillEpisodeMediaFromLibrary(
                    Number(projectId),
                    Number(activeEpisode.id),
                    { include_shots: true, include_entities: false, limit: 10000, overwrite_existing: false },
                );

                const rebound = Number(res?.bound_shots || 0);

                const updatedShots = Number(res?.updated_shots || 0);
                if (!cancelled && (rebound > 0 || updatedShots > 0)) {
                    onLog?.(`Recovered ${rebound} historical media-slot links. Updated ${updatedShots} shots.`, 'success');

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
        if (!activeEpisode?.id) return;
        const episodeId = activeEpisode.id;
        let cancelled = false;

        (async () => {
            try {
                const data = await fetchScenes(episodeId);
                if (!cancelled) setScenes(data);
            } catch (e) {
                console.error(e);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [activeEpisode?.id]);

    useEffect(() => {
        refreshShots();
    }, [refreshShots]);

    const mediaReloadTick = useMediaReloadTick();

    useTabMediaRefreshEffect({
        tabMediaRefreshSignal,
        isTabActive,
        onRefresh: async () => {
            await refreshShots();
            refreshShotAssetsMeta();
        },
    });

    useEffect(() => {
        if (!activeEpisode?.id) return;
        const resolvedProjectId = projectId || activeEpisode?.project_id;
        if (!resolvedProjectId) return;

        let cancelled = false;
        const scheduleLoad = () => {
            if (cancelled) return;
            void loadEntities();
        };

        if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
            const idleId = window.requestIdleCallback(scheduleLoad, { timeout: 1500 });
            return () => {
                cancelled = true;
                window.cancelIdleCallback(idleId);
            };
        }

        const timerId = window.setTimeout(scheduleLoad, 0);
        return () => {
            cancelled = true;
            window.clearTimeout(timerId);
        };
    }, [activeEpisode?.id, activeEpisode?.project_id, loadEntities, projectId]);

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
                const currentStartToken = normalizeAssetUrlToken(currentStartUrl);
                const currentEndToken = normalizeAssetUrlToken(currentEndUrl);
                const currentVideoToken = normalizeAssetUrlToken(currentVideoUrl);
                const baseStartToken = normalizeAssetUrlToken(String(base.start || ''));
                const baseEndToken = normalizeAssetUrlToken(String(base.end || ''));
                const baseVideoToken = normalizeAssetUrlToken(String(base.video || ''));
                const hasFreshStartUrl = Boolean(currentStartToken) && currentStartToken !== baseStartToken;
                const hasFreshEndUrl = Boolean(currentEndToken) && currentEndToken !== baseEndToken;
                const hasFreshVideoUrl = Boolean(currentVideoToken) && currentVideoToken !== baseVideoToken;

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
    }, [shots, hasActiveGeneration, writeGenerationStateStorage, getShotEndFrameUrl, normalizeAssetUrlToken]);

    useEffect(() => {
        if (!editingShot?.id || (shots || []).length === 0) return;
        const latest = (shots || []).find((item) => String(item?.id) === String(editingShot.id));
        if (!latest) return;

        setEditingShot((prev) => {
            if (!prev || String(prev.id) !== String(latest.id)) return prev;

            const nextTechnicalNotes = mergeLiveSyncTechnicalNotes(prev.technical_notes, latest.technical_notes);
            const prevImageUrl = String(prev.image_url || '').trim();
            const latestImageUrl = String(latest.image_url || '').trim();
            const prevVideoUrl = String(prev.video_url || '').trim();
            const latestVideoUrl = String(latest.video_url || '').trim();
            const imageAssetChanged = normalizeAssetUrlToken(prevImageUrl) !== normalizeAssetUrlToken(latestImageUrl);
            const videoAssetChanged = normalizeAssetUrlToken(prevVideoUrl) !== normalizeAssetUrlToken(latestVideoUrl);

            const mediaChanged =
                imageAssetChanged ||
                videoAssetChanged ||
                nextTechnicalNotes.changed;

            if (!mediaChanged) return prev;

            return {
                ...prev,
                image_url: imageAssetChanged ? latestImageUrl : prevImageUrl,
                video_url: videoAssetChanged ? latestVideoUrl : prevVideoUrl,
                technical_notes: nextTechnicalNotes.value,
            };
        });
    }, [editingShot?.id, mergeLiveSyncTechnicalNotes, normalizeAssetUrlToken, setEditingShot, shots]);

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
        let shotTableHeaders = [];

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
                 let cols = cleanMarkdownTableCells(line);

                 if (isHeader) {
                     headerFound = true;
                     shotTableHeaders = cols;
                     headerMap = buildShotTableHeaderMap(shotTableHeaders);
                     onLog?.("Parsed Headers: " + Object.keys(headerMap).join(", "), "info");
                     continue;
                 }
                 
                 if (headerFound) {
                     if (shotTableHeaders.length > 0) {
                         cols = reconcileShotTableRowCells(cols, shotTableHeaders);
                     }
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
            const { rows: dedupedParsedShots, warnings: dedupeWarnings } = dedupeShotRowsForImport(parsedShots, {
                sceneId: selectedSceneId,
            });
            dedupeWarnings.forEach((msg) => onLog?.(`Import dedupe: ${msg}`, 'warning'));
            parsedShots.length = 0;
            parsedShots.push(...dedupedParsedShots);

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
                    const videoPromptCnFallback = videoPromptCnRaw || combinedFallback.video_prompt_cn;

                    if (promptCnRaw || startFrameCnRaw || videoPromptCnRaw || keyframesCnRaw || endFrameCnRaw) {
                        let techObj = {};
                        try {
                            techObj = s.technical_notes ? JSON.parse(s.technical_notes) : {};
                            if (!techObj || typeof techObj !== 'object') techObj = {};
                        } catch (e) {
                            techObj = {};
                        }
                        const finalVideoCn = videoPromptCnFallback;
                        const finalStartCn = startFrameCnRaw || combinedFallback.start_frame_cn || finalVideoCn;
                        const finalKeyframesCn = keyframesCnRaw || combinedFallback.keyframes_cn;
                        const finalEndCn = endFrameCnRaw || combinedFallback.end_frame_cn || finalVideoCn;

                        if (finalVideoCn) {
                            if (!String(s.start_frame || '').trim()) s.start_frame = finalVideoCn;
                            if (!String(s.end_frame || '').trim()) s.end_frame = finalVideoCn;
                            if (!String(s.video_content || '').trim()) s.video_content = finalVideoCn;
                            if (!String(s.prompt || '').trim()) s.prompt = finalVideoCn;
                        }

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
                        setShots(
                            dedupeShotsForDisplay(
                                sceneSpecific.map(normalizeShotPromptDefaults),
                                { sceneId: selectedSceneId },
                            ),
                        );
                    }
                } catch(e) { console.error("Post-import fetch failed", e); }

            } else {
                 onLog?.('Import completed but no shots created.', 'warning');
            }
        } else {
             onLog?.('No valid shots data found.', 'warning');
        }
    };

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

    useEffect(() => {
        if (!editingShot) return;

        const tech = JSON.parse(editingShot.technical_notes || '{}');
        const legacyUrls = Array.isArray(tech.prev_shot_frames) ? tech.prev_shot_frames : [];
        const mappedImages = (tech.prev_shot_frame_images && typeof tech.prev_shot_frame_images === 'object')
            ? tech.prev_shot_frame_images
            : {};

        let parsed = [];
        const mappedTimes = Object.keys(mappedImages).sort((a, b) => {
            const aNum = Number.parseFloat(String(a).replace(/s$/i, ''));
            const bNum = Number.parseFloat(String(b).replace(/s$/i, ''));
            if (Number.isFinite(aNum) && Number.isFinite(bNum)) return aNum - bNum;
            return String(a).localeCompare(String(b));
        });

        if (mappedTimes.length > 0) {
            parsed = mappedTimes.map((time, idx) => ({
                id: idx,
                time,
                prompt: `Prev-shot extract #${idx + 1}`,
                url: mappedImages[time],
            }));
        } else if (legacyUrls.length > 0) {
            parsed = legacyUrls.map((url, idx) => ({
                id: idx,
                time: `F${idx + 1}`,
                prompt: `Prev-shot extract #${idx + 1}`,
                url,
            }));
        }

        setLocalPrevShotFrames(parsed);
    }, [editingShot?.id, editingShot?.technical_notes]);

    const reconstructPrevShotFrames = async (currentList, newTechOverride = null) => {
        const tech = JSON.parse(editingShot.technical_notes || '{}');

        tech.prev_shot_frames = currentList.map((item) => item.url).filter(Boolean);

        const imgMap = {};
        currentList.forEach((item) => {
            if (item.url) imgMap[item.time] = item.url;
        });
        tech.prev_shot_frame_images = imgMap;

        if (newTechOverride) {
            Object.assign(tech, newTechOverride);
        }

        const newData = {
            technical_notes: JSON.stringify(tech),
        };

        await onUpdateShot(editingShot.id, newData);
        setEditingShot((prev) => (prev && String(prev.id) === String(editingShot.id) ? { ...prev, technical_notes: newData.technical_notes } : prev));
    };

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

    const applyMultiPanelImageResult = useCallback(async ({ shotRecord, compositeUrl, presetKey, basePrompt = '', promptLanguage = 'cn' }) => {
        const stableShot = shotRecord || editingShot || null;
        const targetShotId = String(stableShot?.id || '').trim();
        const stableCompositeUrl = String(compositeUrl || '').trim();
        const presetOption = getMultiPanelPresetOption(presetKey);
        const panelCount = Math.max(1, Number(presetOption?.columns || 1) * Number(presetOption?.rows || 1));
        if (!targetShotId || !stableCompositeUrl) {
            throw new Error('Missing shot context for multi-panel split');
        }

        const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
        const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
        const exportSize = resolveShotPanelExportResolution(preferredAspectRatio, preferredImageSize);
        const directUrl = getFullUrl(stableCompositeUrl);
        const isLocalOrigin = directUrl.startsWith(window.location.origin) || directUrl.startsWith('blob:') || directUrl.startsWith('data:');
        const fetchUrl = isLocalOrigin
            ? directUrl
            : `${API_URL}/assets/proxy?url=${encodeURIComponent(directUrl)}`;

        let compositeBlob = null;
        let lastDownloadError = null;
        for (let attempt = 1; attempt <= 3; attempt += 1) {
            try {
                const compositeResp = await fetch(fetchUrl);
                if (!compositeResp.ok) {
                    throw new Error(`Failed to download multi-panel image (${compositeResp.status})`);
                }
                compositeBlob = await compositeResp.blob();
                if (!compositeBlob || compositeBlob.size <= 0) {
                    throw new Error('Failed to download multi-panel image (empty body)');
                }
                lastDownloadError = null;
                break;
            } catch (downloadError) {
                lastDownloadError = downloadError;
                if (attempt < 3) {
                    await new Promise((resolve) => setTimeout(resolve, 700 * attempt));
                }
            }
        }
        if (!compositeBlob) {
            throw (lastDownloadError instanceof Error
                ? lastDownloadError
                : new Error('Failed to download multi-panel image'));
        }

        const compositeImage = await loadImageElementFromBlob(compositeBlob);
        const durationValue = Number(stableShot?.duration || 0);
        const effectiveDuration = Number.isFinite(durationValue) && durationValue > 0 ? durationValue : panelCount;
        const autoPromptBase = String(basePrompt || '').trim() || (promptLanguage === 'en' ? 'Keyframe split from multi-panel preset' : '从多画格预设自动拆分的关键帧');
        const uploadedPanels = [];

        for (let index = 0; index < panelCount; index += 1) {
            const blob = await cropGeneratedGridPanelToBlob({
                image: compositeImage,
                columns: presetOption.columns,
                rows: presetOption.rows,
                panelIndex: index,
                targetAspectRatio: preferredAspectRatio,
                exportSize,
            });

            const isStart = index === 0;
            const isEnd = index === panelCount - 1;
            const frameRole = isStart ? 'start' : (isEnd ? 'end' : `keyframe_${index}`);
            const assetType = isStart ? 'start_frame' : (isEnd ? 'end_frame' : 'keyframe');
            const autoPrompt = `${autoPromptBase} #${index + 1}`;
            const uploadIdempotencyKey = buildShotFrameAssetUploadIdempotencyKey({
                operation: 'multi_panel_split',
                shotId: targetShotId,
                frameRole,
                sourceUrl: stableCompositeUrl,
            });

            const uploaded = await uploadAsset(
                new File([blob], `shot_${targetShotId}_${frameRole}_${index + 1}_${Date.now()}.jpg`, { type: 'image/jpeg' }),
                {
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: targetShotId,
                    shot_number: isStart || isEnd
                        ? stableShot?.shot_id
                        : `${stableShot?.shot_id}_KF_${index + 1}`,
                    shot_name: stableShot?.shot_name,
                    asset_type: assetType,
                    source_asset_url: stableCompositeUrl,
                    idempotency_key: uploadIdempotencyKey,
                    remark: `Multi-panel split ${frameRole} ${index + 1}`,
                }
            );

            const uploadedUrl = String(uploaded?.url || '').trim();
            if (!uploadedUrl) {
                throw new Error(`Failed to upload split panel ${index + 1}`);
            }

            uploadedPanels.push({ index, url: uploadedUrl, prompt: autoPrompt });
        }

        const startUrl = String(uploadedPanels[0]?.url || '').trim();
        const endUrl = String(uploadedPanels[panelCount - 1]?.url || '').trim();
        const middlePanels = panelCount > 2 ? uploadedPanels.slice(1, -1) : [];
        const nextList = middlePanels.map((panel, midIdx) => ({
            id: Date.now() + midIdx + 1,
            time: `${Math.max(0.1, Number((((panel.index + 1) * effectiveDuration) / (panelCount + 1)).toFixed(1)))}s`,
            prompt: panel.prompt,
            url: panel.url,
        }));
        const nextCnMap = promptLanguage === 'cn'
            ? Object.fromEntries(nextList.map((item) => [item.time, item.prompt]))
            : {};

        try {
            await Promise.all([startUrl, endUrl, ...nextList.map((item) => item.url)].filter(Boolean).map((url) => new Promise((resolve) => {
                const img = new Image();
                img.onload = () => {
                    if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(url);
                    resolve();
                };
                img.onerror = resolve;
                img.src = getFullUrl(url);
            })));
        } catch (_) {}

        let existingTech = {};
        try {
            existingTech = JSON.parse(stableShot?.technical_notes || '{}');
            if (!existingTech || typeof existingTech !== 'object') existingTech = {};
        } catch {
            existingTech = {};
        }

        const textParts = nextList.map((item) => `[Time: ${item.time}] ${item.prompt}`);
        const newKeyframesText = textParts.length > 0 ? textParts.join('\n') : 'NO';
        const imgMap = {};
        nextList.forEach((item) => { if (item.url) imgMap[item.time] = item.url; });

        const nextTech = {
            ...existingTech,
            end_frame_url: endUrl,
            end_frame_reused_from_start: panelCount === 1,
            keyframes: nextList.map((item) => item.url).filter(Boolean),
            keyframe_images: imgMap,
            multi_panel_image_url: stableCompositeUrl,
            multi_panel_image_preset: normalizeMultiPanelPresetKey(presetKey),
            multi_panel_last_split_source_url: stableCompositeUrl,
            keyframe_prompt_cn_map: nextCnMap,
        };

        const nextPatch = {
            image_url: startUrl,
            keyframes: newKeyframesText,
            technical_notes: JSON.stringify(nextTech),
        };

        await onUpdateShot(targetShotId, nextPatch);
        setShots((prevShots) => prevShots.map((shot) => (String(shot?.id || '') === targetShotId ? { ...shot, ...nextPatch } : shot)));
        setEditingShot((prev) => (String(prev?.id || '') === targetShotId ? { ...prev, ...nextPatch } : prev));
        if (String(editingShot?.id || '') === targetShotId) {
            setLocalKeyframes(nextList);
        }
        refreshShotAssetsMeta();
        return { startUrl, endUrl, keyframes: nextList, shotPatch: nextPatch };
    }, [activeEpisode?.episode_info, activeEpisode?.id, cropGeneratedGridPanelToBlob, editingShot?.id, loadImageElementFromBlob, onUpdateShot, project?.global_info, projectId, refreshShotAssetsMeta]);
    applyMultiPanelImageResultRef.current = applyMultiPanelImageResult;

    const generateAssetWithLang = async (assetType, keyframeIndex = -1, options = {}) => {
        if (!editingShot) return;
        const shotState = generatingStateByShot[String(editingShot.id)] || { start: false, end: false, video: false };
        const isVideoGenerating = isShotVideoUiRunning(editingShot.id, shotState);
        if (shotState.start || shotState.end || isVideoGenerating) return;
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
            
            const keyframeRefs = resolveShotVideoImageRefs(editingShot, entities);
            // Generate
            const res = await generateImage(fullPrompt, null, keyframeRefs.length > 0 ? keyframeRefs : null, { function_name: 'generate_shot_images',
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
            return pickBestEntityMatch(entList, cleanKey, activeEpisode?.id ?? null);
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
                    const anchor = entity.anchor_description || '';
                    const isSubject = isSubjectEntity(entity);
                    const refNo = isSubject ? subjectRefIndexMap.get(String(entity?.id || '')) : null;

                    if (injectedEntities.has(cleanKey)) {
                        const refText = refNo ? `ref_image_url: #${refNo}` : '';
                        console.log(`[injectEntityFeatures] Re-injected ${cleanKey} -> ${refText}`);
                        return refNo ? `${match}(${refText})` : match;
                    }

                    injectedEntities.add(cleanKey);
                    const anchorWithRef = [
                        anchor,
                        (isSubject && refNo) ? `ref_image_url: #${refNo}` : ''
                    ].filter(Boolean).join(' | ');
                    console.log(`[injectEntityFeatures] Injected ${cleanKey} -> ${anchorWithRef}`);
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
        const sortedArray = _getInMemorySortedShots();
        const currentIdx = sortedArray.findIndex(s => s.id === shotId);
        if (currentIdx <= 0) return null;
        try {
            const prevShot = sortedArray[currentIdx - 1];
            const prevTech = JSON.parse(prevShot.technical_notes || '{}');
            return prevTech.end_frame_url || null;
        } catch (e) {
            return null;
        }
    };

    const findPrevShotRecord = (shotId) => {
        const sortedArray = _getInMemorySortedShots();
        const currentIdx = sortedArray.findIndex((s) => s.id === shotId);
        if (currentIdx <= 0) return null;
        return sortedArray[currentIdx - 1] || null;
    };

    const getPrevShotEndPromptText = (shotId, langKey = 'cn') => {
        const prevShot = findPrevShotRecord(shotId);
        if (!prevShot) return '';
        let prevTech = {};
        try {
            prevTech = JSON.parse(prevShot.technical_notes || '{}');
            if (!prevTech || typeof prevTech !== 'object') prevTech = {};
        } catch (_) {
            prevTech = {};
        }

        const cnPrompt = String(prevTech.end_frame_cn || '').trim();
        const enPrompt = String(prevShot.end_frame || '').trim();
        const fallbackPrompt = String(prevTech.video_prompt_cn || prevShot.video_content || prevShot.prompt || '').trim();

        if (langKey === 'en') {
            return enPrompt || cnPrompt || fallbackPrompt;
        }
        return cnPrompt || enPrompt || fallbackPrompt;
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
        const legacyStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || shotSnapshot.start_frame || shotSnapshot.video_content || "A cinematic shot")
            : (shotSnapshot.start_frame || cnStartPrompt || shotSnapshot.video_content || "A cinematic shot");
        const rawPrompt = promptOverride
            || buildShotFramePromptFromVideoBase(shotSnapshot, 'start', techNotes, legacyStartPrompt).text;
        const isManual = techNotes.manual_start_frame === true;

        const { text: submitPrompt } = injectEntityFeatures(rawPrompt, isManual, resolvedEntities);

        onLog?.('Generating Start Frame...', 'info');
        
        try {
             if (abortGenerationRef.current) {
                 onLog?.('Start Frame generation stopped by user.', 'warning');
                 return;
             }
                const refs = resolveDefaultShotImageGenerationRefs(shotSnapshot, 'start', resolvedEntities);
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

                    if (typeof clearBrokenMediaUrl === 'function') clearBrokenMediaUrl(res.url);
                    clearPendingImageJob(targetShotId, 'start');
                    // Save original prompt to DB (user view), but image was generated with context
                    const newData = { image_url: res.url, start_frame: rawPrompt };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev)); 
                    onLog?.('Start Frame Generated', 'success');
                    showNotification('Start Frame Generated', 'success');
                    notifyShotMediaOssPersistWarning({ ...shotSnapshot, ...newData }, 'start');
                    refreshShotAssetsMeta();
                    Promise.resolve(refreshShots()).catch(() => {});
                } else {
                    throw new Error("No image URL returned");
                }
        } catch (e) {
            console.error('Start Frame generation failed:', e);
            if (isClientInterruptionError(e)) {
                const recovered = await tryRecoverShotMediaAfterInterruption({
                    shotId: targetShotId,
                    mediaKey: 'start',
                });
                if (recovered) {
                    keepRunningUi = true;
                    clearPendingImageJob(targetShotId, 'start');
                    setShotGeneratingState(targetShotId, 'start', false);
                    return;
                }
            }
            if (createdImageJobId) {
                clearPendingImageJob(targetShotId, 'start');
                createdImageJobId = '';
            }
            onLog?.(`Generation failed: ${e.message}`, 'error');
            showNotification(`Generation failed: ${e.message}`, 'error');
            clearPendingImageJob(targetShotId, 'start');
            setShotGeneratingState(targetShotId, 'start', false);
            throw e;
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
        const legacyEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || shotSnapshot.end_frame || "End frame")
            : (shotSnapshot.end_frame || cnEndPrompt || "End frame");
        const rawPrompt = promptOverride
            || buildShotFramePromptFromVideoBase(shotSnapshot, 'end', techNotes, legacyEndPrompt).text;
        const isManual = techNotes.manual_end_frame === true;

        const { text: submitPrompt } = injectEntityFeatures(rawPrompt, isManual, resolvedEntities);

        onLog?.('Generating End Frame...', 'info');

        try {
             if (abortGenerationRef.current) {
                 onLog?.('End Frame generation stopped by user.', 'warning');
                 return;
             }
                const uniqueRefs = resolveDefaultShotImageGenerationRefs(shotSnapshot, 'end', resolvedEntities);
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

                    if (typeof clearBrokenMediaUrl === 'function') clearBrokenMediaUrl(res.url);
                    clearPendingImageJob(targetShotId, 'end');
                    tech.end_frame_url = res.url;
                    const newData = { technical_notes: JSON.stringify(tech), end_frame: rawPrompt };
                    await onUpdateShot(targetShotId, newData);
                    setEditingShot(prev => (prev && prev.id === targetShotId ? { ...prev, ...newData } : prev));
                    onLog?.('End Frame Generated', 'success');
                    showNotification('End Frame Generated', 'success');
                    notifyShotMediaOssPersistWarning({ ...shotSnapshot, ...newData, technical_notes: JSON.stringify(tech) }, 'end');
                    refreshShotAssetsMeta();
                    Promise.resolve(refreshShots()).catch(() => {});
                } else {
                     throw new Error("No image URL returned");
                }
        } catch (e) {
            console.error('End Frame generation failed:', e);
            if (isClientInterruptionError(e)) {
                const recovered = await tryRecoverShotMediaAfterInterruption({
                    shotId: targetShotId,
                    mediaKey: 'end',
                });
                if (recovered) {
                    keepRunningUi = true;
                    clearPendingImageJob(targetShotId, 'end');
                    setShotGeneratingState(targetShotId, 'end', false);
                    return;
                }
            }
            if (createdImageJobId) {
                clearPendingImageJob(targetShotId, 'end');
                createdImageJobId = '';
            }
            onLog?.(`Generation failed: ${e.message}`, 'error');
            showNotification(`Generation failed: ${e.message}`, 'error');
            clearPendingImageJob(targetShotId, 'end');
            setShotGeneratingState(targetShotId, 'end', false);
            throw e;
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

    const captureFramesFromVideoAtTimes = useCallback(async (videoUrl, timesSec = []) => {
        const sampledTimes = Array.isArray(timesSec)
            ? timesSec
                .map((item) => Number(item))
                .filter((item) => Number.isFinite(item) && item >= 0)
            : [];
        if (sampledTimes.length === 0) {
            throw new Error('no frame timestamps provided');
        }

        const video = document.createElement('video');
        video.crossOrigin = 'anonymous';
        video.preload = 'auto';
        video.muted = true;
        video.playsInline = true;

        const cleanup = () => {
            video.onloadedmetadata = null;
            video.onseeked = null;
            video.onerror = null;
            video.src = '';
        };

        const loadVideoMetadata = (useProxy = false) => new Promise((resolve, reject) => {
            video.onloadedmetadata = () => resolve();
            video.onerror = () => reject(new Error(useProxy ? 'video proxy load error' : 'video load error'));
            video.src = getMediaUrlWithFallback(videoUrl, useProxy);
            try {
                video.load();
            } catch (_) {}
        });

        const waitMetadata = async () => {
            try {
                await loadVideoMetadata(false);
            } catch (directError) {
                if (!canFallbackToAssetProxy(videoUrl)) {
                    throw directError;
                }
                await loadVideoMetadata(true);
            }
        };

        const waitSeek = (targetSec) => new Promise((resolve, reject) => {
            const safeTarget = Math.max(0, Number(targetSec || 0));
            const handleSeeked = () => {
                video.onseeked = null;
                video.onerror = null;
                resolve();
            };
            const handleError = () => {
                video.onseeked = null;
                video.onerror = null;
                reject(new Error('video seek error'));
            };

            if (Math.abs(Number(video.currentTime || 0) - safeTarget) < 0.01) {
                resolve();
                return;
            }

            video.onseeked = handleSeeked;
            video.onerror = handleError;
            video.currentTime = safeTarget;
        });

        const canvas = document.createElement('canvas');
        let width = 0;
        let height = 0;
        try {
            await waitMetadata();
            width = Number(video.videoWidth || 0);
            height = Number(video.videoHeight || 0);
            if (!width || !height) {
                throw new Error('video resolution unavailable');
            }

            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            if (!ctx) {
                throw new Error('canvas context unavailable');
            }

            const results = [];
            for (const ts of sampledTimes) {
                await waitSeek(ts);
                ctx.drawImage(video, 0, 0, width, height);
                const blob = await new Promise((resolve, reject) => {
                    canvas.toBlob((encodedBlob) => {
                        if (!encodedBlob) {
                            reject(new Error('failed to encode frame image'));
                            return;
                        }
                        resolve(encodedBlob);
                    }, 'image/jpeg', 0.94);
                });
                results.push({ time: ts, blob });
            }

            return {
                duration: Number(video.duration || 0),
                width,
                height,
                frames: results,
            };
        } finally {
            cleanup();
        }
    }, []);

    const handleExtractPrevShotFramesFromVideo = useCallback(async () => {
        if (!editingShot?.id) return;

        const shotId = String(editingShot.id || '').trim();
        const prevShot = findPrevContinuationShot(shotId);
        if (!prevShot) {
            const errorMsg = t('未找到上一分镜，无法截取上镜帧。', 'Previous shot not found, cannot extract prev-shot frames.');
            onLog?.(errorMsg, 'error');
            showNotification(errorMsg, 'error');
            return;
        }

        const videoUrlRaw = String(prevShot.video_url || '').trim();
        if (!videoUrlRaw) {
            const errorMsg = t('上一分镜没有已生成视频，无法截取上镜帧。', 'Previous shot has no generated video, cannot extract prev-shot frames.');
            onLog?.(errorMsg, 'error');
            showNotification(errorMsg, 'error');
            return;
        }

        const frameCount = Number.parseInt(String(videoKeyframeExtractCount || '').trim(), 10);
        if (!Number.isFinite(frameCount) || frameCount < 2) {
            const errorMsg = t('截取帧数最少为 2。', 'Frame count must be at least 2.');
            onLog?.(errorMsg, 'error');
            showNotification(errorMsg, 'error');
            return;
        }

        if (localPrevShotFrames.length > 0) {
            const shouldReplace = await confirmUiMessage(t(
                `将用视频截取结果覆盖当前 ${localPrevShotFrames.length} 条上镜帧，是否继续？`,
                `This will replace current ${localPrevShotFrames.length} prev-shot frames with extracted video frames. Continue?`
            ));
            if (!shouldReplace) return;
        }

        setIsExtractingVideoKeyframes(true);
        try {
            const probe = await captureFramesFromVideoAtTimes(videoUrlRaw, [0]);
            const rawDuration = Number(probe?.duration || 0);
            if (!Number.isFinite(rawDuration) || rawDuration <= 0) {
                throw new Error(t('视频时长不可用', 'Video duration unavailable'));
            }

            const safeLastTime = Math.max(0, rawDuration - 0.05);
            const firstSampleTime = safeLastTime > 0.12
                ? Math.min(Math.max(0.08, rawDuration * 0.01), Math.max(0, safeLastTime - 0.04))
                : 0;
            const sampledTimes = Array.from({ length: frameCount }, (_, index) => {
                if (index === 0) return firstSampleTime;
                if (index === frameCount - 1) return safeLastTime;
                return firstSampleTime + ((index / (frameCount - 1)) * (safeLastTime - firstSampleTime));
            });

            const captured = await captureFramesFromVideoAtTimes(videoUrlRaw, sampledTimes);
            const capturedFrames = Array.isArray(captured.frames) ? captured.frames : [];
            if (capturedFrames.length < 2) {
                throw new Error(t('上镜帧截取结果不足 2 帧', 'Extracted prev-shot frames are fewer than 2'));
            }

            const nextList = [];
            for (let index = 0; index < capturedFrames.length; index += 1) {
                const item = capturedFrames[index];
                const frameBlob = item?.blob;
                if (!frameBlob) continue;

                const timeLabel = `${Math.max(0, Number(Number(item?.time || 0).toFixed(2)))}s`;
                const promptLabel = `${t('上一镜视频截取', 'Prev-shot video extract')} #${index + 1}`;
                const uploadIdempotencyKey = buildShotFrameAssetUploadIdempotencyKey({
                    operation: 'prev_shot_frame_extract',
                    shotId,
                    frameRole: `prev_shot_frame_${timeLabel}`,
                    sourceUrl: videoUrlRaw,
                });

                const frameFile = new File(
                    [frameBlob],
                    `shot_${shotId}_prev_shot_frame_${index + 1}_${Date.now()}.jpg`,
                    { type: 'image/jpeg' }
                );

                const uploaded = await uploadAsset(frameFile, {
                    project_id: projectId,
                    episode_id: activeEpisode?.id,
                    shot_id: shotId,
                    shot_number: `${editingShot.shot_id}_PSF_${index + 1}`,
                    shot_name: editingShot.shot_name,
                    asset_type: 'prev_shot_frame',
                    source_asset_url: videoUrlRaw,
                    idempotency_key: uploadIdempotencyKey,
                    remark: `Prev-shot video extracted frame ${index + 1}`,
                });

                if (uploaded?.id) {
                    try {
                        await markAssetAsCurrentProjectAsset(uploaded.id);
                    } catch (error) {
                        console.error('Failed to mark extracted prev-shot frame as project asset:', error);
                    }
                }

                const uploadedUrl = String(uploaded?.url || '').trim();
                if (!uploadedUrl) {
                    throw new Error(`uploaded prev-shot frame ${index + 1} has no url`);
                }

                nextList.push({
                    id: Date.now() + index,
                    time: timeLabel,
                    prompt: promptLabel,
                    url: uploadedUrl,
                });

                try {
                    await new Promise((resolve) => {
                        const img = new Image();
                        img.onload = () => {
                            if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(uploadedUrl);
                            resolve();
                        };
                        img.onerror = resolve;
                        img.src = getFullUrl(uploadedUrl);
                    });
                } catch (_) {}
            }

            if (nextList.length < 2) {
                throw new Error(t('上镜帧截取结果不足 2 帧', 'Extracted prev-shot frames are fewer than 2'));
            }

            const prevShotLabel = String(prevShot.shot_id || prevShot.shot_name || '').trim();
            await reconstructPrevShotFrames(nextList, {
                prev_shot_frame_meta: {
                    source_video_url: videoUrlRaw,
                    source_shot_id: String(prevShot.id || '').trim(),
                    source_shot_label: prevShotLabel,
                },
            });
            setLocalPrevShotFrames(nextList);
            refreshShotAssetsMeta();

            const successMsg = t(
                `已从上一分镜${prevShotLabel ? `（${prevShotLabel}）` : ''}视频均匀截取 ${nextList.length} 帧并保存为上镜帧。`,
                `Extracted ${nextList.length} evenly spaced frames from the previous shot${prevShotLabel ? ` (${prevShotLabel})` : ''} and saved them as prev-shot frames.`
            );
            onLog?.(successMsg, 'success');
            showNotification(successMsg, 'success');
        } catch (e) {
            const detail = getReadableErrorDetail(e);
            onLog?.(`${t('上镜帧截取失败', 'Failed to extract prev-shot frames')}: ${detail}`, 'error');
            showNotification(`${t('上镜帧截取失败', 'Failed to extract prev-shot frames')}: ${detail}`, 'error');
        } finally {
            setIsExtractingVideoKeyframes(false);
        }
    }, [
        activeEpisode?.id,
        captureFramesFromVideoAtTimes,
        confirmUiMessage,
        editingShot,
        findPrevContinuationShot,
        getReadableErrorDetail,
        localPrevShotFrames.length,
        onLog,
        projectId,
        refreshShotAssetsMeta,
        t,
        videoKeyframeExtractCount,
    ]);

    const [multiPanelPresetKey, setMultiPanelPresetKey] = useState('4panel');
    multiPanelPresetKeyRef.current = multiPanelPresetKey;
    const [batchMultiPanelPresetKey, setBatchMultiPanelPresetKey] = useState('4panel');
    const [batchUsePrevEndFrameAsMultiPanelStart, setBatchUsePrevEndFrameAsMultiPanelStart] = useState(false);
    const [multiPanelPresetInstruction, setMultiPanelPresetInstruction] = useState(() => getMultiPanelPresetFallbackInstruction('4panel', 'cn'));
    const [isGeneratingMultiPanelImage, setIsGeneratingMultiPanelImage] = useState(false);
    const [isResplittingMultiPanelImage, setIsResplittingMultiPanelImage] = useState(false);
    const [usePrevEndFrameAsMultiPanelStart, setUsePrevEndFrameAsMultiPanelStart] = useState(false);

    useEffect(() => {
        if (!editingShot) return;
        let nextPresetKey = '4panel';
        let nextUsePrevEndFrameStart = false;
        try {
            const techNotes = JSON.parse(editingShot.technical_notes || '{}');
            nextPresetKey = normalizeMultiPanelPresetKey(techNotes.multi_panel_image_preset || '4panel');
            nextUsePrevEndFrameStart = techNotes.multi_panel_start_from_prev_end === true;
        } catch (_) {}
        setMultiPanelPresetKey((prev) => (prev === nextPresetKey ? prev : nextPresetKey));
        setUsePrevEndFrameAsMultiPanelStart((prev) => (prev === nextUsePrevEndFrameStart ? prev : nextUsePrevEndFrameStart));
    }, [editingShot?.id, editingShot?.technical_notes]);

    useEffect(() => {
        let cancelled = false;
        const langKey = resolvedPromptSubmitLang === 'en' ? 'en' : 'cn';
        const presetOption = getMultiPanelPresetOption(multiPanelPresetKey);
        const fallbackInstruction = getMultiPanelPresetFallbackInstruction(multiPanelPresetKey, langKey);

        setMultiPanelPresetInstruction(fallbackInstruction);

        fetchPrompt(presetOption.filename)
            .then((payload) => {
                if (cancelled) return;
                const content = String(payload?.content || '').trim();
                setMultiPanelPresetInstruction(content || fallbackInstruction);
            })
            .catch((error) => {
                if (cancelled) return;
                console.warn('Failed to load multi-panel preset from backend prompts:', error);
                setMultiPanelPresetInstruction(fallbackInstruction);
            });

        return () => {
            cancelled = true;
        };
    }, [multiPanelPresetKey, resolvedPromptSubmitLang]);

    const loadMultiPanelPresetInstruction = useCallback(async (presetKey, langKey = 'cn') => {
        const stableKey = normalizeMultiPanelPresetKey(presetKey);
        const stableLang = langKey === 'en' ? 'en' : 'cn';
        const presetOption = getMultiPanelPresetOption(stableKey);
        const fallbackInstruction = getMultiPanelPresetFallbackInstruction(stableKey, stableLang);
        try {
            const payload = await fetchPrompt(presetOption.filename);
            const content = String(payload?.content || '').trim();
            return content || fallbackInstruction;
        } catch (error) {
            console.warn('Failed to load multi-panel preset from backend prompts:', error);
            return fallbackInstruction;
        }
    }, []);

    const generateMultiPanelPreviewForShot = useCallback(async ({
        shotSnapshot,
        resolvedEntities: inputEntities,
        presetKey,
        presetInstruction = '',
        usePrevEndFrameStart = false,
        priorEndFrameUrl = '',
        silent = false,
    }) => {
        const stableShot = shotSnapshot || null;
        const targetShotId = String(stableShot?.id || '').trim();
        if (!targetShotId) {
            throw new Error('Missing shot id for multi-panel preview generation');
        }

        const resolvedEntities = Array.isArray(inputEntities) && inputEntities.length > 0
            ? inputEntities
            : await awaitShotGenerationEntities();

        setShotGeneratingState(targetShotId, 'start', true);
        setShotGeneratingState(targetShotId, 'end', true);

        try {
            const techNotes = JSON.parse(stableShot.technical_notes || '{}');
            const cnVideoPrompt = String(techNotes.video_prompt_cn || '').trim();
            const rawVideoPrompt = (resolvedPromptSubmitLang === 'cn'
                ? (cnVideoPrompt || getShotVideoPromptEn(shotSnapshot) || "Video motion")
                : (getShotVideoPromptEn(shotSnapshot) || cnVideoPrompt || "Video motion"));
            const isManual = techNotes.manual_video_prompt === true;

            const { text: submitPrompt } = injectEntityFeatures(rawVideoPrompt, isManual, resolvedEntities);
            let refs = resolveShotVideoImageRefs(shotSnapshot, resolvedEntities);

            const langKey = resolvedPromptSubmitLang === 'en' ? 'en' : 'cn';
            const activePresetKey = normalizeMultiPanelPresetKey(presetKey);
            const presetOption = getMultiPanelPresetOption(activePresetKey);
            const baseInstruction = String(presetInstruction || '').trim() || getMultiPanelPresetFallbackInstruction(activePresetKey, langKey);
            const promptInstruction = langKey === 'en'
                ? `. ${baseInstruction.replace(/^[.。\s]+/, '')}`
                : `。${baseInstruction.replace(/^[.。\s]+/, '')}`;

            let prevEndFrameRefUrl = '';
            let prevEndFrameSummary = '';
            if (usePrevEndFrameStart) {
                prevEndFrameRefUrl = String(priorEndFrameUrl || findPrevShotEndFrameUrl(targetShotId) || '').trim();
                if (!prevEndFrameRefUrl) {
                    throw new Error(t('上一镜不存在可用的结束帧，无法作为多画格起始分镜参考图。', 'The previous shot does not have an end frame available for the multi-panel opening panel.'));
                }

                if (!silent) {
                    onLog?.(t('正在读取上一镜结束帧提示词，并将其作为多画格第一格参考...', 'Reading the previous shot end-frame prompt and using it as panel-one reference...'), 'info');
                }
                const prevEndPromptText = getPrevShotEndPromptText(targetShotId, langKey);
                const normalizeSummary = (value) => {
                    let text = String(value || '').trim();
                    if (!text) return '';
                    text = text.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').replace(/^["'“”]+|["'“”]+$/g, '').trim();
                    return Array.from(text).slice(0, 240).join('');
                };
                prevEndFrameSummary = normalizeSummary(prevEndPromptText);
                if (!prevEndFrameSummary) {
                    throw new Error(t('上一镜结束帧提示词为空，无法注入多画格提示词。', 'The previous-shot end-frame prompt is empty, so it cannot be injected into the multi-panel prompt.'));
                }

                refs = [prevEndFrameRefUrl, ...refs.filter((url) => String(url || '').trim() && String(url || '').trim() !== prevEndFrameRefUrl)];
            }

            if (!silent) {
                onLog?.(`Generating ${presetOption.labelEn} preset image...`, 'info');
            }

            const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
            const prevEndFrameInstruction = usePrevEndFrameStart
                ? (langKey === 'en'
                    ? `\n\nUse reference image #1 as the opening storyboard panel. Panel 1 must begin from that image's same subject identity, framing, camera position, costume, environment, and lighting, then continue the action in later panels. Visual summary for reference image #1: ${prevEndFrameSummary}.`
                    : `\n\n参考图 #1 必须作为本次多画格分镜的开始分镜。第一格需从该图的主体身份、构图、机位、服装、环境与光线直接起步，再在后续分格继续推进动作。参考图 #1 视觉特征：${prevEndFrameSummary}。`)
                : '';
            const preferredImageSize = getProjectPreferredImageSize(project?.global_info, activeEpisode?.episode_info);
            const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
            const multiPanelGridPlan = buildMultiPanelGridPlan(
                preferredAspectRatio,
                presetOption.columns,
                presetOption.rows,
            );
            const requestAspectRatio = selectBestMultiPanelRequestAspectRatio({
                gridPlan: multiPanelGridPlan,
                allowedAspectRatios: activeImageCapabilityProfile?.aspectRatios,
            });
            const exactCombinedAspectRatio = normalizeAspectRatioOption(multiPanelGridPlan?.exactCombinedAspectRatio);
            const requestAspectCandidates = Array.from(new Set([
                exactCombinedAspectRatio,
                requestAspectRatio,
                normalizeAspectRatioOption(preferredAspectRatio),
            ].filter(Boolean)));
            const aspectContract = buildMultiPanelAspectContract(multiPanelGridPlan, langKey);
            const finalPrompt = (isManual ? submitPrompt : (submitPrompt + globalCtx)) + prevEndFrameInstruction + promptInstruction + `\n\n${aspectContract}`;
            const resolveMultiPanelResultUrl = (payload) => {
                if (!payload || typeof payload !== 'object') return '';
                const nested = payload?.data && typeof payload.data === 'object' ? payload.data : null;
                const listUrl = Array.isArray(payload?.results) && payload.results.length > 0
                    ? (payload.results[0]?.url || payload.results[0]?.result_url || payload.results[0]?.image_url || '')
                    : '';
                const nestedListUrl = Array.isArray(nested?.results) && nested.results.length > 0
                    ? (nested.results[0]?.url || nested.results[0]?.result_url || nested.results[0]?.image_url || '')
                    : '';
                const direct = payload.url
                    || payload.result_url
                    || payload.image_url
                    || payload.output_url
                    || payload.media_url
                    || listUrl;
                const nestedDirect = nested?.url
                    || nested?.result_url
                    || nested?.image_url
                    || nested?.output_url
                    || nested?.media_url
                    || nestedListUrl;
                const extracted = extractImageJobResultUrl(payload) || extractImageJobResultUrl(nested);
                return String(direct || nestedDirect || extracted || '').trim();
            };

            let res = null;
            let appliedRequestAspectRatio = '';
            let lastAspectError = null;
            for (const aspectCandidate of requestAspectCandidates) {
                try {
                    if (!silent && requestAspectCandidates.length > 1) {
                        onLog?.(
                            t(
                                `多画格尝试生成比例：${aspectCandidate}`,
                                `Trying multi-panel aspect ratio: ${aspectCandidate}`
                            ),
                            'info'
                        );
                    }
                    const candidateRes = await generateImage(finalPrompt, null, refs.length > 0 ? refs : null, {
                        function_name: 'generate_shot_images',
                        project_id: projectId,
                        episode_id: activeEpisode?.id,
                        shot_id: targetShotId,
                        shot_number: shotSnapshot.shot_id,
                        shot_name: shotSnapshot.shot_name,
                        prompt_language: resolvedPromptSubmitLang,
                        asset_type: 'start_frame',
                        ...(aspectCandidate ? { aspect_ratio: aspectCandidate } : {}),
                        ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                        negative_prompt: buildEntityNegativePrompt(finalPrompt, null, resolvedEntities),
                        on_job_created: (jobId) => {
                            const stableJobId = String(jobId || '').trim();
                            if (!stableJobId) return;
                            setPendingImageJob(targetShotId, 'start', stableJobId, { mode: 'multi_panel' });
                        },
                    });
                    const candidateUrl = resolveMultiPanelResultUrl(candidateRes);
                    if (!candidateRes || !candidateUrl) {
                        throw new Error('No multi-panel image URL returned');
                    }
                    res = candidateRes;
                    appliedRequestAspectRatio = aspectCandidate;
                    break;
                } catch (error) {
                    lastAspectError = error;
                    const detail = String(
                        error?.response?.data?.detail
                        || error?.response?.data?.message
                        || error?.message
                        || ''
                    ).toLowerCase();
                    const isAspectRejected = /aspect|ratio|unsupported|invalid|not support|比例|画幅/.test(detail);
                    if (!isAspectRejected || aspectCandidate === requestAspectCandidates[requestAspectCandidates.length - 1]) {
                        throw error;
                    }
                    if (!silent) {
                        onLog?.(
                            t(
                                `多画格比例 ${aspectCandidate} 不可用，自动回退下一候选。`,
                                `Multi-panel aspect ratio ${aspectCandidate} unavailable, falling back to next candidate.`
                            ),
                            'warning'
                        );
                    }
                }
            }
            if (!res) {
                throw lastAspectError || new Error('No multi-panel image URL returned');
            }

            let finalUrl = resolveMultiPanelResultUrl(res);
            if (!finalUrl) {
                const doneJobId = String(res?.job_id || res?.id || '').trim();
                if (doneJobId) {
                    try {
                        const finalStatus = await getImageGenerationJobStatus(doneJobId);
                        finalUrl = resolveMultiPanelResultUrl(finalStatus);
                    } catch (_) {}
                }
            }
            if (!finalUrl) {
                throw new Error('No multi-panel image URL returned');
            }
            techNotes.multi_panel_image_url = finalUrl;
            techNotes.multi_panel_image_preset = activePresetKey;
            techNotes.multi_panel_request_aspect_ratio = appliedRequestAspectRatio || requestAspectRatio;
            techNotes.multi_panel_request_aspect_candidates = requestAspectCandidates;
            techNotes.multi_panel_target_aspect_ratio = multiPanelGridPlan.targetAspectRatio;
            techNotes.multi_panel_start_from_prev_end = usePrevEndFrameStart;
            if (usePrevEndFrameStart) {
                techNotes.multi_panel_prev_end_ref_url = prevEndFrameRefUrl;
                techNotes.multi_panel_prev_end_ref_summary = prevEndFrameSummary;
            } else {
                delete techNotes.multi_panel_prev_end_ref_url;
                delete techNotes.multi_panel_prev_end_ref_summary;
            }
            const nextStr = JSON.stringify(techNotes);

            // Persist composite URL before split so "Re-split" still works if cropping/download fails.
            try {
                await onUpdateShot(targetShotId, { technical_notes: nextStr });
                setEditingShot((prev) => (prev && String(prev.id) === targetShotId
                    ? { ...prev, technical_notes: nextStr }
                    : prev));
            } catch (persistErr) {
                console.warn('Failed to persist multi-panel composite URL before split:', persistErr);
            }

            setShotGeneratingState(targetShotId, 'start', false);
            setShotGeneratingState(targetShotId, 'end', false);
            setShotGeneratingState(targetShotId, 'cropping', true);

            const splitResult = await applyMultiPanelImageResult({
                shotRecord: { ...stableShot, technical_notes: nextStr },
                compositeUrl: finalUrl,
                presetKey: activePresetKey,
                basePrompt: rawVideoPrompt,
                promptLanguage: resolvedPromptSubmitLang,
            });

            return {
                shotId: targetShotId,
                shotLabel: String(stableShot.shot_id || stableShot.shot_name || `#${targetShotId}`),
                startUrl: splitResult?.startUrl || '',
                endUrl: splitResult?.endUrl || '',
                shotPatch: splitResult?.shotPatch || {},
            };
        } finally {
            clearPendingImageJob(targetShotId, 'start');
            setShotGeneratingState(targetShotId, 'start', false);
            setShotGeneratingState(targetShotId, 'end', false);
            setShotGeneratingState(targetShotId, 'cropping', false);
        }
    }, [
        activeEpisode?.episode_info,
        activeEpisode?.id,
        activeImageCapabilityProfile?.aspectRatios,
        applyMultiPanelImageResult,
        awaitShotGenerationEntities,
        buildEntityNegativePrompt,
        clearPendingImageJob,
        findPrevShotEndFrameUrl,
        getGlobalContextStr,
        getPrevShotEndPromptText,
        getProjectPreferredAspectRatio,
        getProjectPreferredImageSize,
        getShotVideoPromptEn,
        injectEntityFeatures,
        onLog,
        onUpdateShot,
        project?.global_info,
        projectId,
        resolveShotVideoImageRefs,
        resolvedPromptSubmitLang,
        setPendingImageJob,
        setShotGeneratingState,
        t,
    ]);

    const handleGenerateMultiPanelImage = async () => {
        if (!editingShot) return;
        setIsGeneratingMultiPanelImage(true);
        try {
            const resolvedEntities = await awaitShotGenerationEntities();
            await generateMultiPanelPreviewForShot({
                shotSnapshot: editingShot,
                resolvedEntities,
                presetKey: multiPanelPresetKey,
                presetInstruction: multiPanelPresetInstruction,
                usePrevEndFrameStart: usePrevEndFrameAsMultiPanelStart,
            });
            showNotification(t('多画格图已自动裁剪并填入首尾帧与关键帧', 'Multi-panel image was auto-split and filled into start/end frames and keyframes'), 'success');
        } catch (e) {
            onLog?.(`${t('生成多画格图失败', 'Failed to generate multi-panel image')}: ${e.message}`, 'error');
            showNotification(`${t('生成多画格图失败', 'Failed to generate multi-panel image')}: ${e.message}`, 'error');
        } finally {
            setIsGeneratingMultiPanelImage(false);
        }
    };

    const handleResplitMultiPanelImage = async () => {
        if (!editingShot || isResplittingMultiPanelImage) return;
        const shotSnapshot = editingShot;
        const techNotes = getEditingShotTech() || {};
        const explicitCompositeUrl = String(techNotes.multi_panel_image_url || techNotes.storyboard_url || '').trim();
        const startFrameFallbackUrl = String(shotSnapshot?.image_url || '').trim();
        // Recovery path may have written the unsplit composite into image_url only.
        const compositeUrl = explicitCompositeUrl || startFrameFallbackUrl;
        if (!compositeUrl) {
            showNotification(t('当前没有可重新拆分的多画格图', 'No multi-panel image is available to re-split'), 'warning');
            return;
        }

        const cnVideoPrompt = String(techNotes.video_prompt_cn || '').trim();
        const rawVideoPrompt = (resolvedPromptSubmitLang === 'cn'
            ? (cnVideoPrompt || getShotVideoPromptEn(shotSnapshot) || 'Video motion')
            : (getShotVideoPromptEn(shotSnapshot) || cnVideoPrompt || 'Video motion'));

        setIsResplittingMultiPanelImage(true);
        onLog?.(explicitCompositeUrl
            ? 'Re-splitting multi-panel image into keyframes...'
            : t('未找到多画格原图记录，改用当前首帧图重新拆分...', 'No saved multi-panel source found; re-splitting from the current start frame...'), 'info');
        try {
            // Ensure subsequent re-splits use the explicit multi-panel field even when falling back from start frame.
            const shotForSplit = !explicitCompositeUrl
                ? {
                    ...shotSnapshot,
                    technical_notes: JSON.stringify({
                        ...techNotes,
                        multi_panel_image_url: compositeUrl,
                        multi_panel_image_preset: techNotes.multi_panel_image_preset || multiPanelPresetKey,
                    }),
                }
                : shotSnapshot;
            await applyMultiPanelImageResult({
                shotRecord: shotForSplit,
                compositeUrl,
                presetKey: techNotes.multi_panel_image_preset || multiPanelPresetKey,
                basePrompt: rawVideoPrompt,
                promptLanguage: resolvedPromptSubmitLang,
            });
            showNotification(t('已重新拆分并回填首尾帧与关键帧', 'Start/end frames and keyframes were re-split and refilled'), 'success');
        } catch (error) {
            onLog?.(`${t('重新拆分失败', 'Re-split failed')}: ${error?.message || 'unknown error'}`, 'error');
            showNotification(`${t('重新拆分失败', 'Re-split failed')}: ${error?.message || 'unknown error'}`, 'error');
        } finally {
            setIsResplittingMultiPanelImage(false);
        }
    };

    const handleGenerateVideo = async (promptOverride = null) => {
        if (!editingShot) return;
        let shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        const targetGeneratingState = generatingStateByShot[targetShotId] || { start: false, end: false, video: false };
        const isVideoGenerating = isShotVideoUiRunning(targetShotId, targetGeneratingState);
        if (targetGeneratingState.start || targetGeneratingState.end || isVideoGenerating) {
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
        let ignoreAsyncJobCallbacks = false;
        let ignoredAsyncJobCallbackCount = 0;

        onLog?.('Generating Video...', 'info');
        try {
            let tech = JSON.parse(shotSnapshot.technical_notes || '{}');
            const hadUnifiedMode = Boolean(String(tech?.video_mode_unified || '').trim());
            ensureShotDefaultVideoMode(tech);
            if (!hadUnifiedMode) {
                const updatedTechNotes = JSON.stringify(tech);
                await onUpdateShot(targetShotId, { technical_notes: updatedTechNotes });
                shotSnapshot = { ...shotSnapshot, technical_notes: updatedTechNotes };
                setEditingShot((prev) => (prev && prev.id === targetShotId
                    ? { ...prev, technical_notes: updatedTechNotes }
                    : prev));
            }

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
            const videoRefPromptText = buildShotVideoRefPromptText(shotSnapshot, tech);

            if (effectiveVideoMode.includes('entity_refs')) {
                const missingEntityRefSlots = getMissingShotVideoEntityRefSlots(
                    buildShotVideoEntityRefSlots({
                        promptText: videoRefPromptText,
                        entityPool: resolvedEntities,
                        includeAssociatedEntities: false,
                        preferredEpisodeId: activeEpisode?.id ?? shotSnapshot?.episode_id ?? null,
                    })
                );
                if (missingEntityRefSlots.length > 0) {
                    const missingNames = missingEntityRefSlots
                        .map((slot) => slot.name || slot.nameEn)
                        .filter(Boolean)
                        .join('、');
                    const proceed = await confirmUiMessage(t(
                        `检测到 ${missingEntityRefSlots.length} 个参考实体尚未生成参考图${missingNames ? `：${missingNames}` : ''}。缺失的参考图不会提交到视频 API。是否仍要提交？`,
                        `Detected ${missingEntityRefSlots.length} referenced entities without reference images${missingNames ? `: ${missingNames}` : ''}. Missing references will not be sent to the video API. Submit anyway?`
                    ));
                    if (!proceed) {
                        setShotGeneratingState(targetShotId, 'video', false);
                        return;
                    }
                }
            }

            const hasManualVideoRefOverride = Boolean(
                tech.video_ref_image_urls_manual === true
                || tech.video_ref_image_urls_user_edited === true
            );
            const shouldInjectContinuationPrompt = Boolean(usePrevVideo);

            // Always submit the same list as the Refs (Video) panel (WYSIWYG).
            // Do not re-derive from prompt entity matches — that ignored manual adds/removes.
            const activeVideoRefs = resolveShotVideoActiveRefs({
                shotLike: shotSnapshot,
                techObj: tech,
                entityPool: resolvedEntities,
                promptText: videoRefPromptText,
                additionalAutoRefs: resolvePrevContinuationVideoRefs(targetShotId),
                includeAdditionalAutoRefs: !hasManualVideoRefOverride,
                preferredEpisodeId: activeEpisode?.id ?? shotSnapshot?.episode_id ?? null,
            });
            const submitRefPlan = buildShotVideoSubmitRefsFromActiveRefs({
                activeRefs: activeVideoRefs,
                shotLike: shotSnapshot,
                techObj: tech,
                slotLimit: DEFAULT_VIDEO_REFERENCE_SLOT_LIMIT,
            });

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
                    const uploaded = await uploadAsset(file, {
                        project_id: projectId,
                        episode_id: activeEpisode?.id,
                        shot_id: targetShotId,
                    });
                    
                    if (uploaded?.url) return uploaded.url;
                } catch (e) {
                    console.warn('[handleGenerateVideo] Failed to upload local blob to server:', e);
                }
                return url;
            };

            const apiKeyframes = Array.isArray(keyframes) ? keyframes.filter(Boolean) : [];
            const keyframeRequestUrls = effectiveVideoMode === 'keyframes_entity_refs'
                ? apiKeyframes.slice(0, 1)
                : apiKeyframes;

            const resolvedDisplayedRefs = normalizeMediaRefList(
                await Promise.all(submitRefPlan.displayedRefs.map(resolveBlobUrlIfAny))
            );
            let apiSubmitImageUrls = normalizeMediaRefList(
                await Promise.all(submitRefPlan.imageUrls.map(resolveBlobUrlIfAny))
            );
            const apiRefVideoUrls = submitRefPlan.refVideoUrls.length > 0
                ? normalizeMediaRefList(await Promise.all(submitRefPlan.refVideoUrls.map(resolveBlobUrlIfAny)))
                : null;
            let apiLastFrameUrl = submitRefPlan.lastFrameUrl
                ? await resolveBlobUrlIfAny(submitRefPlan.lastFrameUrl)
                : null;

            if (submitRefPlan.truncated > 0) {
                onLog?.(t(
                    `参考图/视频共 ${submitRefPlan.displayedRefs.length} 个，已按上限 ${DEFAULT_VIDEO_REFERENCE_SLOT_LIMIT} 截断 ${submitRefPlan.truncated} 个后再提交。`,
                    `Total refs ${submitRefPlan.displayedRefs.length} exceed limit ${DEFAULT_VIDEO_REFERENCE_SLOT_LIMIT}; truncated ${submitRefPlan.truncated} before submit.`
                ), 'warning');
            }
            
            // Duration Logic: Seedance2 auto duration uses -1; otherwise use shot table duration.
            const durParam = resolveShotVideoDurationParam(editingShot.duration);

            // NEW: Inject Global Context
            const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
            let finalPrompt = isManual ? submitPrompt : (submitPrompt + globalCtx);

            if (effectiveVideoMode === 'entity_refs_start_end') {
                const currentStartFrameUrl = String(shotSnapshot.image_url || '').trim();
                const endRefUrl = String(tech.end_frame_url || '').trim();
                const resolvedStartUrl = await resolveBlobUrlIfAny(currentStartFrameUrl);
                const resolvedEndUrl = await resolveBlobUrlIfAny(endRefUrl);
                
                const startIdx = resolvedDisplayedRefs.indexOf(resolvedStartUrl) + 1;
                const endIdx = resolvedDisplayedRefs.indexOf(resolvedEndUrl) + 1;

                if (startIdx > 0 && endIdx > 0) {
                    finalPrompt = `参考@Image${startIdx} 作为第一帧, ` + finalPrompt + `, 参考@Image${endIdx} 作为最后一帧`;
                } else if (startIdx > 0) {
                    finalPrompt = `参考@Image${startIdx} 作为第一帧, ` + finalPrompt;
                } else if (endIdx > 0) {
                    finalPrompt = finalPrompt + `, 参考@Image${endIdx} 作为最后一帧`;
                }
            }

            onLog?.(
                `Video API payload mode=${effectiveVideoMode}, visible_refs=${resolvedDisplayedRefs.length}, image_urls=${apiSubmitImageUrls.length}, ref_videos=${Array.isArray(apiRefVideoUrls) ? apiRefVideoUrls.length : 0}, last_frame=${apiLastFrameUrl ? 'yes' : 'no'}, keyframes=${Array.isArray(apiKeyframes) ? apiKeyframes.length : 0}, duration=${durParam}`,
                'info'
            );

            let videoTaskPromise = null;
            try {
                videoTaskPromise = generateVideo(finalPrompt, null, null, apiRefVideoUrls, apiLastFrameUrl, durParam, { function_name: 'generate_videos',
                    project_id: projectId,
                    episode_id: activeEpisode?.id ?? shotSnapshot?.episode_id ?? undefined,
                    shot_id: targetShotId,
                    draft_mode: isDraftMode,
                    use_prev_video: shouldInjectContinuationPrompt,
                    shot_number: shotSnapshot.shot_id,
                    shot_name: shotSnapshot.shot_name,
                    ref_mode: effectiveVideoMode,
                    prompt_language: resolvedPromptSubmitLang,
                    asset_type: 'video',
                    ...(apiSubmitImageUrls.length > 0
                        ? { image_urls: apiSubmitImageUrls }
                        : (submitRefPlan.imageUrls.length > 0 ? { ref_image_url: submitRefPlan.imageUrls } : {})),
                    entity_url_map: tech.entity_url_map || undefined,
                    negative_prompt: buildEntityNegativePrompt(rawPrompt, null, resolvedEntities),
                    on_job_created: (jobId) => {
                        if (ignoreAsyncJobCallbacks) {
                            ignoredAsyncJobCallbackCount += 1;
                            return;
                        }
                        createdVideoJobId = String(jobId || '').trim();
                        setPendingVideoJob(targetShotId, jobId);
                        setShotGeneratingState(targetShotId, 'video', true);
                    },
                    on_job_status: (status, data) => {
                        if (ignoreAsyncJobCallbacks) {
                            ignoredAsyncJobCallbackCount += 1;
                            return;
                        }
                        setVideoStatuses(prev => ({ ...prev, [targetShotId]: String(data?.status || status).toLowerCase() }));
                    },
                }, keyframeRequestUrls);
                onLog?.(t('视频请求已发起', 'Video request dispatched'), 'info');
            } catch (videoDispatchError) {
                onLog?.(`${t('视频请求发起失败', 'Video request dispatch failed')}: ${videoDispatchError?.message || 'unknown error'}`, 'error');
                throw videoDispatchError;
            }

            const videoSettled = await Promise.allSettled([videoTaskPromise]);

            if (videoSettled[0].status === 'fulfilled' && videoSettled[0].value) {
                const res = videoSettled[0].value;
                const resolvedVideoUrl = String(res?.url || res?.video_url || '').trim();
                if (!resolvedVideoUrl) {
                    // Some providers finish asynchronously and do not return URL in immediate response.
                    // Force a server resync so UI still updates when the shot record has been updated.
                    ignoreAsyncJobCallbacks = true;
                    releaseShotVideoUi({ shotId: targetShotId, jobId: createdVideoJobId });
                    onLog?.(t('视频任务已完成，正在同步最新镜头数据...', 'Video task completed, syncing latest shot data...'), 'info');
                    refreshShotAssetsMeta();
                    await refreshShots();
                    try {
                        const latestShot = await fetchShot(targetShotId);
                        if (latestShot?.id) {
                            setEditingShot((prev) => {
                                if (!prev || String(prev.id) !== String(targetShotId)) return prev;
                                return { ...prev, ...normalizeShotPromptDefaults(latestShot) };
                            });
                        }
                    } catch (syncErr) {
                        console.warn('Failed to sync latest shot after video completion:', syncErr);
                    }
                    setVideoStatuses(prev => { const n = { ...prev }; delete n[targetShotId]; return n; });
                } else {
                ignoreAsyncJobCallbacks = true;
                if (typeof clearBrokenMediaUrl === 'function') clearBrokenMediaUrl(resolvedVideoUrl);

                try {
                    await new Promise((resolve) => {
                        const v = document.createElement('video');
                        v.muted = true;
                        v.playsInline = true;
                        v.preload = 'auto';
                        let done = false;
                        const finish = () => {
                            if (done) return;
                            done = true;
                            resolve();
                        };
                        v.oncanplay = finish;
                        v.onloadeddata = finish;
                        v.onerror = finish;
                        v.src = getFullUrl(resolvedVideoUrl);
                        v.load();
                        setTimeout(finish, 4000);
                    });
                    if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resolvedVideoUrl);
                } catch(e) {}

                releaseShotVideoUi({ shotId: targetShotId, jobId: createdVideoJobId });
                const newData = { video_url: resolvedVideoUrl, prompt: rawPrompt };
                
                // 1. Force Local State Update IMMEDIATELY (Optimistic/Local)
                const stableTargetShotId = String(targetShotId || '').trim();
                setShots((prev) => prev.map((shot) => (
                    String(shot?.id || '') === stableTargetShotId ? { ...shot, ...newData } : shot
                )));
                setEditingShot(prev => {
                         if (!prev || String(prev.id) !== stableTargetShotId) return prev;
                   return { ...prev, ...newData };
                });
                
                onLog?.('Video Generated', 'success');
                showNotification('Video Generated', 'success');

                // 2. Update Server & Master List (Async persistence)
                try {
                    await onUpdateShot(targetShotId, newData);
                } catch (updateErr) {
                    console.error("Failed to save shot update to backend:", updateErr);
                }

                refreshShotAssetsMeta();
                Promise.resolve(refreshShots()).catch(() => {});
                setVideoStatuses(prev => { const n = {...prev}; delete n[targetShotId]; return n; });

                const needsOssSync = shotVideoNeedsOssPersist({ ...shotSnapshot, ...newData });
                if (needsOssSync) {
                    void syncShotVideoAfterOssPersist({
                        shotId: targetShotId,
                        jobId: createdVideoJobId,
                        initialUrl: resolvedVideoUrl,
                    }).then((synced) => {
                        if (!synced) {
                            notifyShotMediaOssPersistWarning({ ...shotSnapshot, video_url: resolvedVideoUrl }, 'video');
                        }
                    });
                }
                }
            }

            if (videoSettled[0].status === 'rejected') {
                const e = videoSettled[0].reason;
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
                        ignoreAsyncJobCallbacks = true;
                        releaseShotVideoUi({ shotId: targetShotId, jobId: createdVideoJobId });
                        onLog?.(`Generation failed: ${e?.message || 'unknown error'}`, 'error');
                        showNotification(`Generation failed: ${e?.message || 'unknown error'}`, 'error');
                    }
                } else {
                    ignoreAsyncJobCallbacks = true;
                    releaseShotVideoUi({ shotId: targetShotId, jobId: createdVideoJobId });
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
                    ignoreAsyncJobCallbacks = true;
                     releaseShotVideoUi({ shotId: targetShotId, jobId: createdVideoJobId });
                     onLog?.(`Generation failed: ${e.message}`, 'error');
                     showNotification(`Generation failed: ${e.message}`, 'error');
                 }
             } else {
                 ignoreAsyncJobCallbacks = true;
                 releaseShotVideoUi({ shotId: targetShotId, jobId: createdVideoJobId });
                 onLog?.(`Generation failed: ${e.message}`, 'error');
                 showNotification(`Generation failed: ${e.message}`, 'error');
             }
        } finally {
            if (!keepRunningUi) {
                ignoreAsyncJobCallbacks = true;
                setShotGeneratingState(targetShotId, 'video', false);
                setVideoStatuses(prev => { const n = {...prev}; delete n[targetShotId]; return n; });
            }
            if (ignoredAsyncJobCallbackCount > 0 && typeof window !== 'undefined') {
                console.debug('[ShotsView] Ignored stale video job callbacks', {
                    shotId: String(targetShotId || ''),
                    jobId: String(createdVideoJobId || ''),
                    ignoredCount: ignoredAsyncJobCallbackCount,
                });
            }
        }
    };

    const handlePersistShotMediaToOss = useCallback(async (shotLike = null, slot = 'video') => {
        const normalizedSlot = String(slot || 'video').trim().toLowerCase();
        const apiSlot = normalizedSlot === 'start' || normalizedSlot === 'start_frame'
            ? 'start'
            : normalizedSlot === 'end' || normalizedSlot === 'end_frame'
                ? 'end'
                : 'video';
        const targetShot = shotLike || editingShot;
        const targetShotId = String(targetShot?.id || '').trim();
        const sourceUrl = resolveShotMediaSlotUrl(targetShot, apiSlot);
        const needsPersist = apiSlot === 'start'
            ? shotStartFrameNeedsOssPersist(targetShot)
            : apiSlot === 'end'
                ? shotEndFrameNeedsOssPersist(targetShot)
                : shotVideoNeedsOssPersist(targetShot);

        if (!targetShotId || !sourceUrl) {
            showNotification(t('当前镜头没有可补传的素材地址。', 'No media URL available to persist.'), 'warning');
            return false;
        }
        if (!needsPersist) {
            showNotification(t('当前素材已是稳定存储地址。', 'Current media URL is already durable.'), 'info');
            return true;
        }

        const busyKey = `${targetShotId}:${apiSlot}`;
        setShotMediaOssPersistBusy((prev) => ({ ...prev, [busyKey]: true }));
        onLog?.(t('正在补传素材到 OSS...', 'Uploading media to OSS...'), 'info');
        try {
            const result = await persistShotMedia(targetShotId, {
                slot: apiSlot,
                source_url: sourceUrl,
            });
            const persistedUrl = String(result?.persisted_url || '').trim();
            const refreshedShot = result?.shot && typeof result.shot === 'object' ? result.shot : null;
            const mergedShot = {
                ...targetShot,
                ...(refreshedShot || {}),
                ...(apiSlot === 'start' ? { image_url: persistedUrl || refreshedShot?.image_url || targetShot?.image_url } : {}),
                ...(apiSlot === 'video' ? { video_url: persistedUrl || refreshedShot?.video_url || targetShot?.video_url } : {}),
                technical_notes: refreshedShot?.technical_notes ?? targetShot?.technical_notes,
            };
            if (result?.oss_uploaded === true) {
                const tech = parseShotTechnicalNotes(mergedShot.technical_notes);
                if (apiSlot === 'video') {
                    tech.video_oss_uploaded = true;
                    if (tech.video_metadata && typeof tech.video_metadata === 'object') {
                        const meta = { ...tech.video_metadata };
                        delete meta.ephemeral_binding;
                        delete meta.needs_persistence_retry;
                        delete meta.remote_localization_failed;
                        tech.video_metadata = meta;
                    }
                } else if (apiSlot === 'start') {
                    tech.start_frame_oss_uploaded = true;
                } else if (apiSlot === 'end') {
                    tech.end_frame_oss_uploaded = true;
                }
                mergedShot.technical_notes = typeof refreshedShot?.technical_notes === 'object'
                    ? tech
                    : JSON.stringify(tech);
            }
            if (apiSlot === 'end' && persistedUrl) {
                const tech = parseShotTechnicalNotes(mergedShot.technical_notes);
                tech.end_frame_url = persistedUrl;
                mergedShot.technical_notes = JSON.stringify(tech);
            }

            const stillNeedsPersist = apiSlot === 'start'
                ? shotStartFrameNeedsOssPersist(mergedShot)
                : apiSlot === 'end'
                    ? shotEndFrameNeedsOssPersist(mergedShot)
                    : shotVideoNeedsOssPersist(mergedShot);
            if (!persistedUrl) {
                throw new Error(t('补传后仍未获得稳定存储地址，请稍后重试。', 'Persisted URL is still not durable; please retry later.'));
            }
            if (stillNeedsPersist && result?.oss_uploaded !== true) {
                throw new Error(t('补传后仍未获得稳定存储地址，请稍后重试。', 'Persisted URL is still not durable; please retry later.'));
            }

            const patch = apiSlot === 'start'
                ? { image_url: persistedUrl }
                : apiSlot === 'end'
                    ? { technical_notes: mergedShot.technical_notes }
                    : { video_url: persistedUrl };

            setEditingShot((prev) => (prev && String(prev.id) === targetShotId ? { ...prev, ...patch } : prev));
            setMediaPersistGraceRefreshSeq((seq) => seq + 1);
            try {
                await onUpdateShot(targetShotId, patch);
            } catch (updateErr) {
                console.warn('[handlePersistShotMediaToOss] shot update failed:', updateErr);
            }
            refreshShotAssetsMeta();
            Promise.resolve(refreshShots()).catch(() => {});
            onLog?.(t('素材已成功补传到 OSS。', 'Media uploaded to OSS successfully.'), 'success');
            showNotification(t('素材已成功补传到 OSS。', 'Media uploaded to OSS successfully.'), 'success');
            return true;
        } catch (err) {
            const detail = err?.response?.data?.detail || err?.message || t('未知错误', 'unknown error');
            onLog?.(`${t('素材补传 OSS 失败', 'Media OSS upload failed')}: ${detail}`, 'error');
            showNotification(`${t('素材补传 OSS 失败', 'Media OSS upload failed')}: ${detail}`, 'error');
            return false;
        } finally {
            setShotMediaOssPersistBusy((prev) => {
                const next = { ...prev };
                delete next[busyKey];
                return next;
            });
        }
    }, [editingShot, onLog, onUpdateShot, refreshShotAssetsMeta, refreshShots, showNotification, t]);

    const handleTempVideoBadgeClick = useCallback(async (shotLike, event) => {
        if (event) {
            event.stopPropagation();
            event.preventDefault();
        }

        const shotId = String(shotLike?.id || '').trim();
        if (!shotId) return;

        const busyKey = `${shotId}:video`;
        if (shotMediaOssPersistBusy[busyKey]) {
            showNotification(t('正在补传中，请稍候...', 'Upload in progress, please wait...'), 'info');
            return;
        }

        let freshShot = shotLike;
        try {
            const latestShot = await fetchShot(shotId);
            if (latestShot?.id) {
                freshShot = latestShot;
                if (isShotVideoOssPersistComplete(latestShot)) {
                    const patch = {
                        video_url: latestShot.video_url,
                        technical_notes: latestShot.technical_notes,
                    };
                    setEditingShot((prev) => (prev && String(prev.id) === shotId ? { ...prev, ...patch } : prev));
                    setShots((prev) => prev.map((item) => (
                        String(item?.id) === shotId ? { ...item, ...patch } : item
                    )));
                    setMediaPersistGraceRefreshSeq((seq) => seq + 1);
                    showNotification(t('视频已是稳定存储地址。', 'Video is already on durable storage.'), 'info');
                    return;
                }
            }
        } catch (fetchErr) {
            console.warn('[handleTempVideoBadgeClick] fetchShot failed:', fetchErr);
        }

        if (!shotVideoNeedsOssPersist(freshShot)) {
            showNotification(t('当前素材已是稳定存储地址。', 'Current media URL is already durable.'), 'info');
            return;
        }

        const boundMs = getShotVideoMediaBoundAtMs(freshShot);
        if (boundMs) {
            const ageMs = Date.now() - boundMs;
            if (ageMs < EPHEMERAL_VIDEO_OSS_AUTO_RETRY_MIN_AGE_MS) {
                const remainSec = Math.ceil((EPHEMERAL_VIDEO_OSS_AUTO_RETRY_MIN_AGE_MS - ageMs) / 1000);
                showNotification(
                    t(`临时视频绑定未满 1 分钟，请 ${remainSec} 秒后再试。`, `Temporary video was bound less than 1 minute ago; try again in ${remainSec}s.`),
                    'info'
                );
                return;
            }
        }

        await handlePersistShotMediaToOss(freshShot, 'video');
    }, [
        fetchShot,
        handlePersistShotMediaToOss,
        shotMediaOssPersistBusy,
        showNotification,
        t,
    ]);

    const notifyShotMediaOssPersistWarning = useCallback((shotLike, slot = 'video') => {
        const apiSlot = slot === 'start' || slot === 'start_frame'
            ? 'start'
            : slot === 'end' || slot === 'end_frame'
                ? 'end'
                : 'video';
        const needsPersist = apiSlot === 'start'
            ? shotStartFrameNeedsOssPersist(shotLike)
            : apiSlot === 'end'
                ? shotEndFrameNeedsOssPersist(shotLike)
                : shotVideoNeedsOssPersist(shotLike);
        if (!needsPersist) return;

        const labelZh = apiSlot === 'start'
            ? '起始帧图片'
            : apiSlot === 'end'
                ? '结束帧图片'
                : '视频';
        const labelEn = apiSlot === 'start'
            ? 'start frame image'
            : apiSlot === 'end'
                ? 'end frame image'
                : 'video';

        onLog?.(
            apiSlot === 'video'
                ? t(
                    '警告：视频仍为供应商临时地址，尚未持久化到 OSS。请在镜头详情中点击「临时视频」。',
                    'Warning: video is still on a temporary provider URL and was not persisted to OSS. Click "Temp Video" in shot details.'
                )
                : t(
                    `警告：${labelZh}仍为供应商临时地址，尚未持久化到 OSS。请在详情页点击“补传 OSS”。`,
                    `Warning: ${labelEn} is still on a temporary provider URL and was not persisted to OSS. Use "Upload to OSS" in the detail panel.`
                ),
            'warning'
        );
        showNotification(
            apiSlot === 'video'
                ? t('视频未写入 OSS，请点击「临时视频」补传', 'Video not stored to OSS — click "Temp Video" to upload')
                : t(`${labelZh}未写入 OSS，请及时补传`, `${labelEn} not stored to OSS — please upload soon`),
            'warning'
        );
    }, [onLog, showNotification, t]);

    const renderOssPersistWarningPanel = useCallback((shotLike, slot, labels = {}) => {
        const apiSlot = slot === 'start' || slot === 'start_frame'
            ? 'start'
            : slot === 'end' || slot === 'end_frame'
                ? 'end'
                : 'video';
        if (apiSlot === 'video') return null;

        const needsPersist = apiSlot === 'start'
            ? shotStartFrameNeedsOssPersist(shotLike)
            : apiSlot === 'end'
                ? shotEndFrameNeedsOssPersist(shotLike)
                : shotVideoNeedsOssPersist(shotLike);
        if (!needsPersist) return null;

        const stableShotId = String(shotLike?.id || '').trim();
        const busyKey = `${stableShotId}:${apiSlot}`;
        const titleZh = labels.titleZh || (apiSlot === 'start' ? '起始帧尚未持久化到 OSS' : apiSlot === 'end' ? '结束帧尚未持久化到 OSS' : '视频尚未持久化到 OSS');
        const titleEn = labels.titleEn || (apiSlot === 'start' ? 'Start frame not persisted to OSS' : apiSlot === 'end' ? 'End frame not persisted to OSS' : 'Video not persisted to OSS');
        const bodyZh = labels.bodyZh || '当前链接为供应商临时地址，可能会过期。请尽快补传到 OSS。';
        const bodyEn = labels.bodyEn || 'The current link is a temporary provider URL and may expire. Upload it to OSS as soon as possible.';

        return (
            <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 space-y-2">
                <div className="flex items-start gap-2 text-amber-100">
                    <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                    <div className="space-y-1 text-xs leading-relaxed">
                        <div className="font-bold">{t(titleZh, titleEn)}</div>
                        <div>{t(bodyZh, bodyEn)}</div>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => handlePersistShotMediaToOss(shotLike, apiSlot)}
                    disabled={Boolean(shotMediaOssPersistBusy[busyKey])}
                    className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 hover:bg-amber-400 disabled:opacity-60 disabled:cursor-not-allowed text-amber-950 px-3 py-1.5 text-xs font-bold"
                >
                    {shotMediaOssPersistBusy[busyKey] ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                        <Upload className="w-3.5 h-3.5" />
                    )}
                    <span>{shotMediaOssPersistBusy[busyKey] ? t('补传中...', 'Uploading...') : t('补传 OSS', 'Upload to OSS')}</span>
                </button>
            </div>
        );
    }, [handlePersistShotMediaToOss, shotMediaOssPersistBusy, t]);

    const probeVideoUrlReachable = useCallback(async (rawUrl, timeoutMs = 12000) => {
        const normalized = String(rawUrl || '').trim();
        if (!normalized) {
            return { ok: false, reason: 'empty' };
        }

        const candidateUrl = getFullUrl(normalized);
        return await new Promise((resolve) => {
            let settled = false;
            const video = document.createElement('video');
            video.preload = 'metadata';
            video.muted = true;
            video.playsInline = true;

            const finish = (ok, reason = '') => {
                if (settled) return;
                settled = true;
                clearTimeout(timer);
                video.onloadedmetadata = null;
                video.oncanplay = null;
                video.onerror = null;
                try {
                    video.removeAttribute('src');
                    video.load();
                } catch (_) {
                    // noop
                }
                resolve({ ok, reason, checkedUrl: candidateUrl });
            };

            const timer = setTimeout(() => finish(false, 'timeout'), Math.max(1000, Number(timeoutMs) || 12000));
            video.onloadedmetadata = () => finish(true, 'loadedmetadata');
            video.oncanplay = () => finish(true, 'canplay');
            video.onerror = () => finish(false, 'error');

            try {
                video.src = candidateUrl;
                video.load();
            } catch (_) {
                finish(false, 'exception');
            }
        });
    }, []);

    const handleUpscaleCurrentVideo = async () => {
        if (!editingShot) return;
        const shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        const targetGeneratingState = generatingStateByShot[targetShotId] || { start: false, end: false, video: false };
        const isVideoGenerating = isShotVideoUiRunning(targetShotId, targetGeneratingState);
        if (targetGeneratingState.start || targetGeneratingState.end || isVideoGenerating) return;

        const currentVideoUrl = String(shotSnapshot.video_url || '').trim();
        if (!currentVideoUrl) {
            showNotification(t('当前镜头没有可提升质量的视频。', 'No video found for this shot to upscale.'), 'warning');
            return;
        }

        const sourceProbe = await probeVideoUrlReachable(currentVideoUrl);
        if (!sourceProbe?.ok) {
            onLog?.(
                t(
                    '浏览器无法预检当前视频链接，仍将尝试提交 Topaz 提质任务。',
                    'Browser preflight could not reach the current video URL; submitting Topaz upscale anyway.'
                ) + ` (${sourceProbe?.reason || 'unreachable'})`,
                'warning'
            );
        }

        setShotGeneratingState(targetShotId, 'video', true);
        setVideoStatuses((prev) => ({ ...prev, [targetShotId]: 'upscaling' }));

        let createdVideoJobId = '';
        let keepRunningUi = false;
        const stableTargetShotId = String(targetShotId || '').trim();

        try {
            const upscaleTask = generateVideo(
                t('基于当前视频进行2x超分提升', 'Upscale current video with 2x quality boost'),
                'kie',
                null,
                [currentVideoUrl],
                null,
                5,
                {
                    system_api_id: null,
                    project_id: projectId,
                    shot_id: targetShotId,
                    shot_number: shotSnapshot.shot_id,
                    shot_name: shotSnapshot.shot_name,
                    asset_type: 'video',
                    model: 'topaz/video-upscale',
                    video_url: currentVideoUrl,
                    source_video_url: currentVideoUrl,
                    upscale_factor: '2',
                    on_job_created: (jobId) => {
                        createdVideoJobId = String(jobId || '').trim();
                        setPendingVideoJob(targetShotId, jobId);
                        setShotGeneratingState(targetShotId, 'video', true);
                    },
                    on_job_status: (status, data) => {
                        setVideoStatuses((prev) => ({ ...prev, [targetShotId]: String(data?.status || status || 'upscaling').toLowerCase() }));
                    },
                },
                []
            );

            const settled = await Promise.allSettled([upscaleTask]);
            if (settled[0].status === 'fulfilled' && settled[0].value && settled[0].value.url) {
                const res = settled[0].value;
                if (typeof clearBrokenMediaUrl === 'function') clearBrokenMediaUrl(res.url);

                clearPendingVideoJob(targetShotId);
                const newData = { video_url: res.url };

                setShots((prev) => (prev || []).map((shot) => (
                    String(shot?.id || '').trim() === stableTargetShotId ? { ...shot, ...newData } : shot
                )));
                setEditingShot((prev) => {
                    if (!prev || prev.id !== targetShotId) return prev;
                    return { ...prev, ...newData };
                });

                try {
                    await onUpdateShot(targetShotId, newData);
                } catch (updateErr) {
                    console.error('Failed to save upscaled video to backend:', updateErr);
                }

                onLog?.(t('视频清晰度提升完成并已回填。', 'Video upscale completed and backfilled.'), 'success');
                showNotification(t('视频清晰度提升完成', 'Video upscale completed'), 'success');
                refreshShotAssetsMeta();
                Promise.resolve(refreshShots()).catch(() => {});

                if (shotVideoNeedsOssPersist({ ...shotSnapshot, ...newData })) {
                    void syncShotVideoAfterOssPersist({
                        shotId: targetShotId,
                        jobId: createdVideoJobId,
                        initialUrl: res.url,
                    });
                }

                setVideoStatuses((prev) => { const n = { ...prev }; delete n[targetShotId]; return n; });
            }

            if (settled[0].status === 'rejected') {
                const e = settled[0].reason;
                if (isClientInterruptionError(e)) {
                    const recovered = await tryRecoverShotMediaAfterInterruption({ shotId: targetShotId, mediaKey: 'video' });
                    if (recovered || createdVideoJobId) {
                        keepRunningUi = true;
                    } else {
                        clearPendingVideoJob(targetShotId);
                        onLog?.(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                        showNotification(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                    }
                } else {
                    clearPendingVideoJob(targetShotId);
                    onLog?.(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                    showNotification(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                }
            }
        } catch (e) {
            if (isClientInterruptionError(e)) {
                const recovered = await tryRecoverShotMediaAfterInterruption({ shotId: targetShotId, mediaKey: 'video' });
                if (recovered || createdVideoJobId) {
                    keepRunningUi = true;
                } else {
                    clearPendingVideoJob(targetShotId);
                    onLog?.(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                    showNotification(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                }
            } else {
                clearPendingVideoJob(targetShotId);
                onLog?.(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
                showNotification(`${t('视频提质失败', 'Video upscale failed')}: ${e?.message || 'unknown error'}`, 'error');
            }
        } finally {
            if (!keepRunningUi) {
                setShotGeneratingState(targetShotId, 'video', false);
                setVideoStatuses((prev) => { const n = { ...prev }; delete n[targetShotId]; return n; });
            }
        }
    };

    const handleLocalVideoCleanup = async (action) => {
        if (!editingShot) return;
        const shotSnapshot = editingShot;
        const targetShotId = shotSnapshot.id;
        const targetGeneratingState = generatingStateByShot[targetShotId] || { start: false, end: false, video: false };
        const isVideoGenerating = isShotVideoUiRunning(targetShotId, targetGeneratingState);
        if (targetGeneratingState.start || targetGeneratingState.end || isVideoGenerating) return;

        const currentVideoUrl = String(shotSnapshot.video_url || '').trim();
        if (!currentVideoUrl) {
            showNotification(t('当前镜头没有可处理的视频。', 'No video found for this shot to clean up.'), 'warning');
            return;
        }

        const actionKey = String(action || '').trim().toLowerCase();
        const isSubtitle = actionKey === 'remove_subtitle' || actionKey === 'remove_subtitle_and_bgm';
        const isBgm = actionKey === 'remove_bgm' || actionKey === 'remove_subtitle_and_bgm';
        if (!isSubtitle && !isBgm) return;

        const confirmMsg = actionKey === 'remove_subtitle_and_bgm'
            ? t('将用本地 ffmpeg 去除当前视频的字幕与 BGM（音轨），并覆盖镜头视频，是否继续？', 'Locally remove subtitles and BGM (audio) from this video and replace the shot video. Continue?')
            : isSubtitle
                ? t('将用本地 ffmpeg 去除当前视频底部字幕区域（并剥离软字幕轨），是否继续？', 'Locally remove burned-in bottom subtitles (and soft subtitle tracks) from this video. Continue?')
                : t('将用本地 ffmpeg 去除当前视频的 BGM（整条音轨），是否继续？', 'Locally remove BGM (entire audio track) from this video. Continue?');
        if (!await confirmUiMessage(confirmMsg)) return;

        setVideoCleanupMenuOpen(false);
        setShotGeneratingState(targetShotId, 'video', true);
        setVideoStatuses((prev) => ({
            ...prev,
            [targetShotId]: isSubtitle && isBgm ? 'cleaning_both' : (isSubtitle ? 'cleaning_subtitle' : 'cleaning_bgm'),
        }));

        const stableTargetShotId = String(targetShotId || '').trim();
        try {
            const res = await cleanupShotVideo(targetShotId, {
                action: actionKey,
                source_url: currentVideoUrl,
            });
            const nextUrl = String(res?.url || res?.shot?.video_url || '').trim();
            if (!nextUrl) {
                throw new Error(t('清理结果缺少视频地址', 'Cleanup result missing video URL'));
            }
            if (typeof clearBrokenMediaUrl === 'function') clearBrokenMediaUrl(nextUrl);

            const newData = { video_url: nextUrl };
            setShots((prev) => (prev || []).map((shot) => (
                String(shot?.id || '').trim() === stableTargetShotId ? { ...shot, ...newData } : shot
            )));
            setEditingShot((prev) => {
                if (!prev || prev.id !== targetShotId) return prev;
                return { ...prev, ...newData };
            });

            onLog?.(t('本地视频清理完成并已回填。', 'Local video cleanup completed and backfilled.'), 'success');
            showNotification(
                isSubtitle && isBgm
                    ? t('字幕与 BGM 已去除', 'Subtitles and BGM removed')
                    : isSubtitle
                        ? t('字幕已去除', 'Subtitles removed')
                        : t('BGM 已去除', 'BGM removed'),
                'success'
            );
            refreshShotAssetsMeta();
            Promise.resolve(refreshShots()).catch(() => {});
            setIsEditingVideoPreviewArmed(true);
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'unknown error';
            onLog?.(`${t('本地视频清理失败', 'Local video cleanup failed')}: ${detail}`, 'error');
            showNotification(`${t('本地视频清理失败', 'Local video cleanup failed')}: ${detail}`, 'error');
        } finally {
            setShotGeneratingState(targetShotId, 'video', false);
            setVideoStatuses((prev) => { const n = { ...prev }; delete n[targetShotId]; return n; });
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
        const legacyStartPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnStartPrompt || workingShot.start_frame || workingShot.video_content || 'A cinematic shot')
            : (workingShot.start_frame || cnStartPrompt || workingShot.video_content || 'A cinematic shot');
        const legacyEndPrompt = resolvedPromptSubmitLang === 'cn'
            ? (cnEndPrompt || workingShot.end_frame || 'End frame')
            : (workingShot.end_frame || cnEndPrompt || 'End frame');
        const startFramePrompt = buildShotFramePromptFromVideoBase(workingShot, 'start', techNotes, legacyStartPrompt);
        const endFramePrompt = buildShotFramePromptFromVideoBase(workingShot, 'end', techNotes, legacyEndPrompt);
        const rawStartPrompt = startFramePrompt.text;
        const rawEndPrompt = endFramePrompt.text;

        const normalizedEndPrompt = String(legacyEndPrompt || '').trim().toUpperCase();
        const endPromptIsNoLike = endFramePrompt.source !== 'video' && ['NO', 'N/A', 'NONE', 'NULL', 'NA'].includes(normalizedEndPrompt);
        const startPromptIsInherited = isStartFrameInheritPrompt(legacyStartPrompt);
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
                const startRefs = resolveDefaultShotImageGenerationRefs(workingShot, 'start', resolvedEntities);
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
                } else {
                    const isManualEnd = techNotes.manual_end_frame === true;
                    const { text: endSubmitPrompt } = injectEntityFeatures(rawEndPrompt, isManualEnd, resolvedEntities);
                    const endShotContext = { ...workingShot, image_url: startUrl || workingShot.image_url };
                    const endRefs = resolveDefaultShotImageGenerationRefs(endShotContext, 'end', resolvedEntities);
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
    }, [activeEpisode?.episode_info, activeEpisode?.id, activeImageCapabilityProfile?.aspectRatios, activeImageCapabilityProfile?.imageSizeValues, applyJointShotDiptychResult, buildEntityNegativePrompt, buildShotDiptychPlan, buildShotFramePromptFromVideoBase, clearPendingImageJob, clearPendingJointDiptychImageJob, getEpisodePreferredAspectRatio, getEpisodePreferredImageSize, getGlobalContextStr, injectEntityFeatures, isStartFrameInheritPrompt, onUpdateShot, project?.global_info, projectId, resolveDefaultShotImageGenerationRefs, resolveJointShotDiptychRefs, resolveShotPanelExportResolution, resolvedPromptSubmitLang, selectBestShotDiptychRequestAspectRatio, setPendingImageJob, setPendingJointDiptychImageJob, setShotGeneratingState]);

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

    const runLocalMultiPanelPreviewBatch = useCallback(async () => {
        const orderedShots = (Array.isArray(shots) ? shots : []).filter((shot) => Boolean(shot?.id));
        const targetShots = orderedShots;
        if (targetShots.length === 0) {
            alert(t('当前没有可批量处理的镜头。', 'No shots available for batch processing.'));
            return;
        }

        const presetOption = getMultiPanelPresetOption(batchMultiPanelPresetKey);
        const ok = await confirmUiMessage(
            t(
                `将为 ${targetShots.length} 个镜头批量生成分镜预览（${presetOption.labelZh}）。每个镜头会生成多画格图并自动拆分，首格填入起始帧、末格填入结束帧，中间格填入关键帧。系统会本地并发调度，每批最多 ${SHOT_BATCH_PARALLEL_LIMIT} 个。是否继续？`,
                `Generate storyboard previews for ${targetShots.length} shots (${presetOption.labelEn}). Each shot will generate a multi-panel image, split it, fill the first panel into the start frame, the last panel into the end frame, and middle panels into keyframes. The local scheduler will run up to ${SHOT_BATCH_PARALLEL_LIMIT} shots per wave. Continue?`
            )
        );
        if (!ok) return;

        const langKey = resolvedPromptSubmitLang === 'en' ? 'en' : 'cn';
        const presetInstruction = await loadMultiPanelPresetInstruction(batchMultiPanelPresetKey, langKey);
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
            if (existingEndUrl) endUrlMap.set(stableShotId, existingEndUrl);
        });

        shotLocalBatchStopRequestedRef.current = false;
        const batchSessionId = `shot-multi-panel-batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        shotLocalBatchSessionRef.current = batchSessionId;
        if (shotBatchStatusTimerRef.current) {
            clearInterval(shotBatchStatusTimerRef.current);
            shotBatchStatusTimerRef.current = null;
        }
        syncLocalShotBatchRuntime(true, {
            current: 0,
            total: targetShots.length,
            status: t('分镜预览批量任务准备中...', 'Preparing storyboard preview batch...'),
            stopRequested: false,
            currentShotLabel: '',
            currentAssetLabel: t('生成+拆分', 'Generate + Split'),
            mode: 'multi-panel-local',
        });
        onLog?.(t('开始本地分镜预览批量任务（生成后自动拆分回填）。', 'Started local storyboard preview batch (auto-split after generation).'), 'process');

        let completed = 0;
        let success = 0;
        let failed = 0;
        let queue = [...targetShots];

        const isReady = (shot) => {
            if (!batchUsePrevEndFrameAsMultiPanelStart) return true;
            const stableShotId = String(shot?.id || '').trim();
            const prevShotId = prevShotIdByShotId.get(stableShotId);
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

            const updateActiveMultiPanelStatus = () => {
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
                    currentAssetLabel: t('生成+拆分', 'Generate + Split'),
                    mode: 'multi-panel-local',
                });
            };

            const startNextShotTask = () => {
                if (shouldStopShotBatch() || activeTasks.size >= workerLimit || queue.length === 0) {
                    return false;
                }
                const nextShot = queue.find(isReady) || (activeTasks.size === 0 ? queue[0] : null);
                if (!nextShot) return false;

                queue = queue.filter((shot) => String(shot?.id || '').trim() !== String(nextShot?.id || '').trim());
                const shotId = String(nextShot?.id || '');
                const priorEndFrameUrl = endUrlMap.get(prevShotIdByShotId.get(shotId) || '') || '';
                const wrappedPromise = generateMultiPanelPreviewForShot({
                    shotSnapshot: nextShot,
                    resolvedEntities,
                    presetKey: batchMultiPanelPresetKey,
                    presetInstruction,
                    usePrevEndFrameStart: batchUsePrevEndFrameAsMultiPanelStart,
                    priorEndFrameUrl,
                    silent: true,
                })
                    .then((value) => ({ shotId, shot: nextShot, status: 'fulfilled', value }))
                    .catch((reason) => ({ shotId, shot: nextShot, status: 'rejected', reason }));
                activeTasks.set(shotId, { shot: nextShot, promise: wrappedPromise });
                updateActiveMultiPanelStatus();
                return true;
            };

            while (queue.length > 0 || activeTasks.size > 0) {
                while (!shouldStopShotBatch() && activeTasks.size < workerLimit && startNextShotTask()) {}

                if (activeTasks.size === 0) break;

                const settledTask = await Promise.race(Array.from(activeTasks.values()).map((item) => item.promise));
                activeTasks.delete(settledTask.shotId);

                const shot = settledTask.shot;
                completed += 1;
                if (settledTask.status === 'fulfilled') {
                    success += 1;
                    const stableShotId = String(shot?.id || '').trim();
                    const nextPatch = settledTask.value?.shotPatch || {};
                    applyShotPatchToLocalState(shot?.id, nextPatch);
                    if (settledTask.value?.endUrl) {
                        endUrlMap.set(stableShotId, settledTask.value.endUrl);
                    } else if (settledTask.value?.startUrl) {
                        endUrlMap.set(stableShotId, settledTask.value.startUrl);
                    }
                } else {
                    failed += 1;
                    onLog?.(
                        t(
                            `镜头批量分镜预览失败：${shot?.shot_id || shot?.shot_name || shot?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`,
                            `Shot storyboard preview batch failed: ${shot?.shot_id || shot?.shot_name || shot?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`
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
                    currentAssetLabel: t('生成+拆分', 'Generate + Split'),
                    mode: 'multi-panel-local',
                });
                updateActiveMultiPanelStatus();
            }

            if (shotLocalBatchSessionRef.current !== batchSessionId || shotLocalBatchStopRequestedRef.current) {
                onLog?.(t(`分镜预览批量任务已停止：成功 ${success}，失败 ${failed}`, `Storyboard preview batch stopped: ${success} succeeded, ${failed} failed`), 'warning');
                syncLocalShotBatchRuntime(false, {
                    current: completed,
                    total: targetShots.length,
                    status: t(`分镜预览批量已停止：成功 ${success}，失败 ${failed}`, `Storyboard preview batch stopped: ${success} succeeded, ${failed} failed`),
                    stopRequested: true,
                    currentShotLabel: '',
                    currentAssetLabel: t('生成+拆分', 'Generate + Split'),
                    mode: 'multi-panel-local',
                });
                return;
            }

            onLog?.(t(`分镜预览批量完成：成功 ${success}，失败 ${failed}`, `Storyboard preview batch complete: ${success} succeeded, ${failed} failed`), failed > 0 ? 'warning' : 'success');
            syncLocalShotBatchRuntime(false, {
                current: completed,
                total: targetShots.length,
                status: t(`分镜预览批量完成：成功 ${success}，失败 ${failed}`, `Storyboard preview batch complete: ${success} succeeded, ${failed} failed`),
                stopRequested: false,
                currentShotLabel: '',
                currentAssetLabel: t('生成+拆分', 'Generate + Split'),
                mode: 'multi-panel-local',
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
    }, [
        SHOT_BATCH_PARALLEL_LIMIT,
        applyShotPatchToLocalState,
        awaitShotGenerationEntities,
        batchMultiPanelPresetKey,
        batchUsePrevEndFrameAsMultiPanelStart,
        generateMultiPanelPreviewForShot,
        getShotEndFrameUrl,
        isPersistentLocalShotBatchStopRequested,
        loadMultiPanelPresetInstruction,
        onLog,
        refreshShotAssetsMeta,
        refreshShots,
        resolvedPromptSubmitLang,
        shots,
        syncLocalShotBatchRuntime,
        t,
    ]);

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
                current_asset_type: localMode === 'joint-diptych-local'
                    ? 'joint_diptych'
                    : (localMode === 'multi-panel-local' ? 'storyboard_preview' : 'start_end_sequence'),
                current_asset_label: String(localProgress?.currentAssetLabel || ''),
                mode: localMode,
            };
        }
        try {
            const status = await getShotMediaBatchStatus(activeEpisode.id);
            if (!status || typeof status !== 'object') return null;
            shotBatchStatusErrorStreakRef.current = 0;
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
            isBatchGeneratingRef.current = running;
            setIsBatchGenerating(running);
            const nextProgress = {
                current: Number(status.completed || 0),
                total: Number(status.total || 0),
                status: String(status.message || ''),
                stopRequested: Boolean(status.stop_requested),
                currentShotLabel: String(status.current_shot_label || ''),
                currentAssetLabel,
                mode: String(status.mode || 'videos-backend'),
            };
            batchProgressRef.current = nextProgress;
            setBatchProgress(nextProgress);

            if (!running && shotBatchStatusTimerRef.current) {
                clearInterval(shotBatchStatusTimerRef.current);
                shotBatchStatusTimerRef.current = null;
                refreshShots();
            }

            return status;
        } catch (e) {
            shotBatchStatusErrorStreakRef.current = Number(shotBatchStatusErrorStreakRef.current || 0) + 1;
            if (shotBatchStatusErrorStreakRef.current >= SHOT_JOB_MAX_STATUS_FAILURES) {
                isBatchGeneratingRef.current = false;
                setIsBatchGenerating(false);
                setBatchProgress((prev) => ({
                    ...prev,
                    status: t('批量状态查询失败，已停止等待。请手动刷新确认结果。', 'Batch status polling failed. Waiting stopped. Please refresh manually.'),
                    mode: String(prev?.mode || 'videos-backend'),
                }));
                if (shotBatchStatusTimerRef.current) {
                    clearInterval(shotBatchStatusTimerRef.current);
                    shotBatchStatusTimerRef.current = null;
                }
            }
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
                    : (localMode === 'multi-panel-local'
                        ? t('已请求停止当前分镜预览批量任务。', 'Stop requested for current storyboard preview batch.')
                        : t('已请求停止当前关键帧批量任务。', 'Stop requested for current keyframe batch.'));
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
            if (mode === 'multi_panel_preview') {
                await runLocalMultiPanelPreviewBatch();
                return;
            }

            const started = await startShotMediaBatch(activeEpisode.id, {
                mode,
                shot_ids: targetShotIds,
                draft_mode: isDraftMode,
                use_prev_video: mode === 'videos' ? usePrevVideo : false,
                sd2_auto_duration: mode === 'videos' ? sd2AutoDuration : false,
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

    const handleBatchGenerateMultiPanelPreview = async () => {
        await startShotBatchByMode('multi_panel_preview');
    };

    const handleBatchGenerateVideo = async () => {
        await startShotBatchByMode('videos');
    };

    const handleBatchScaleDuration = async () => {
        if (!shots || shots.length === 0) {
            onLog?.(t('无可用镜头', 'No shots available'), 'warning');
            return;
        }

        const scaleStr = await promptUiMessage(
            t('请输入时长缩放比例 (例如 1.5, 对当前列表中所有镜头生效)：', 'Enter duration scale factor (e.g. 1.5, applies to all listed shots):'),
            { defaultValue: '1.0' }
        );
        if (scaleStr === null) return;
        
        const scale = parseFloat(scaleStr);
        if (isNaN(scale) || scale <= 0) {
            onLog?.(t('缩放比例无效', 'Invalid scale factor'), 'error');
            return;
        }

        const updates = [];
        for (const shot of shots) {
            const currentDurStr = shot.duration;
            const d = parseFloat(currentDurStr) || 5; 
            let newD = Math.round(d * scale);
            if (newD < 4) newD = 4;
            if (newD > 15) newD = 15;
            
            if (newD !== d || !currentDurStr) {
                updates.push({ id: shot.id, duration: newD.toString() });
            }
        }

        if (updates.length === 0) {
            onLog?.(t('没有需要更新时长的镜头', 'No shots need duration update'), 'info');
            return;
        }

        if (!await confirmUiMessage(t(
            `确定要将当前列表上的 ${shots.length} 个镜头时长按 ${scale} 倍缩放吗？结果会限制在 4 到 15 秒并取整。\n(实际受影响的镜头有 ${updates.length} 个)`, 
            `Are you sure you want to scale the duration of ${shots.length} listed shots by ${scale}x? Limits are 4 to 15s rounded to int.\n(${updates.length} shots will actually be modified)`
        ))) {
            return;
        }

        setIsShotBatchStarting(true);
        let successCount = 0;
        try {
            for (let i = 0; i < updates.length; i++) {
                const upd = updates[i];
                await onUpdateShot(upd.id, { duration: upd.duration });
                successCount++;
            }
            onLog?.(t(`批量更新时长完成，共更新 ${successCount} 个镜头`, `Batch duration update complete. ${successCount} shots updated.`), 'success');
        } catch (err) {
            console.error(err);
            onLog?.(t(`批量更新时长遇到错误，已更新 ${successCount} 个镜头`, `Batch update error. ${successCount} shots updated.`), 'error');
        } finally {
            setIsShotBatchStarting(false);
        }
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
        return [...(shots || [])].sort((a, b) => {
            const keyA = getShotHierarchyKey(a);
            const keyB = getShotHierarchyKey(b);
            return keyA.localeCompare(keyB, undefined, { numeric: true, sensitivity: 'base' });
        });
    }, [shots, getShotHierarchyKey]);

    const orderedVideoShots = useMemo(() => {
        return (sortedShots || []).filter((shot) => String(shot?.video_url || '').trim());
    }, [sortedShots]);

    const activePlaylistShot = orderedVideoShots[playlistIndex] || null;

    const openOrderedVideoPlaylist = useCallback(() => {
        if (!orderedVideoShots.length) {
            showNotification(t('当前列表没有可播放视频', 'No playable videos in current list'), 'error');
            return;
        }
        setPlaylistIndex(0);
        setIsPlaylistModalOpen(true);
    }, [orderedVideoShots, showNotification, t]);

    const closeOrderedVideoPlaylist = useCallback(() => {
        setIsPlaylistModalOpen(false);
    }, []);

    const playPrevPlaylistVideo = useCallback(() => {
        setPlaylistIndex((prev) => {
            if (!orderedVideoShots.length) return 0;
            return Math.max(0, prev - 1);
        });
    }, [orderedVideoShots.length]);

    const playNextPlaylistVideo = useCallback(() => {
        setPlaylistIndex((prev) => {
            if (!orderedVideoShots.length) return 0;
            return Math.min(orderedVideoShots.length - 1, prev + 1);
        });
    }, [orderedVideoShots.length]);

    const handlePlaylistVideoEnded = useCallback(() => {
        setPlaylistIndex((prev) => {
            if (!orderedVideoShots.length) return 0;
            if (prev >= orderedVideoShots.length - 1) {
                return prev;
            }
            return prev + 1;
        });
    }, [orderedVideoShots.length]);

    useEffect(() => {
        if (!isPlaylistModalOpen) return;
        if (!orderedVideoShots.length) {
            setIsPlaylistModalOpen(false);
            return;
        }
        setPlaylistIndex((prev) => Math.min(Math.max(prev, 0), orderedVideoShots.length - 1));
    }, [isPlaylistModalOpen, orderedVideoShots.length]);

    useEffect(() => {
        if (!isPlaylistModalOpen) return;
        const videoEl = playlistVideoRef.current;
        if (!videoEl) return;
        const playPromise = videoEl.play();
        if (playPromise && typeof playPromise.catch === 'function') {
            playPromise.catch(() => {});
        }
    }, [isPlaylistModalOpen, playlistIndex]);

    useEffect(() => {
        if (!isPlaylistModalOpen) return;
        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                closeOrderedVideoPlaylist();
            } else if (event.key === 'ArrowRight') {
                playNextPlaylistVideo();
            } else if (event.key === 'ArrowLeft') {
                playPrevPlaylistVideo();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [isPlaylistModalOpen, closeOrderedVideoPlaylist, playNextPlaylistVideo, playPrevPlaylistVideo]);

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
             <div className="flex justify-between items-center flex-wrap mb-6 shrink-0 gap-y-4">
                <div className="flex items-center flex-wrap gap-4 w-full">
                    {/* Title & Status */}
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        {t('镜头管理', 'Shot Manager')}
                        <span className="text-sm font-normal text-muted-foreground ml-2">({shots.length})</span>
                        <TabMediaRefreshButton
                            onClick={() => onMediaRefreshRequest?.()}
                            loading={isShotsLoading}
                            uiLang={uiLang}
                            compact
                            className="ml-1"
                        />
                        {hasActiveGeneration && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center gap-1">
                                <Loader2 className="w-3 h-3 animate-spin" />
                                {Object.values(generatingStateByShot || {}).some((s) => s?.cropping) ? t('处理图片中', 'Processing Image') : t('生成中', 'Generating')}
                            </span>
                        )}
                    </h2>

                    {/* Action Bar Groupings */}
                    <div className="flex flex-wrap items-center gap-3">
                        {/* Group 1: Filter */}
                        <div className="flex items-center bg-black/40 border border-white/10 rounded-lg p-1 min-w-[200px]">
                             <select 
                                className="bg-transparent border-none outline-none focus:ring-0 text-sm w-full text-white cursor-pointer px-2 py-1 select-none"
                                value={selectedSceneId || ''}
                                onChange={(e) => setSelectedSceneId(e.target.value)}
                             >
                                <option value="">{t('选择场景...', 'Select a Scene...')}</option>
                                <option value="all">{t('全部场景', 'All Scenes')}</option>
                                {scenes.map(s => (
                                    <option key={s.id} value={s.id}>{s.scene_no} - {s.scene_name || t('未命名', 'Untitled')}</option>
                                ))}
                             </select>
                        </div>

                        {/* Group 2: Selection & Delete */}
                        <div className="flex items-center gap-1 bg-black/40 border border-white/10 rounded-lg p-1 relative">
                            <button
                                onClick={() => toggleSelectAllVisibleShots(true)}
                                className="px-3 py-1.5 hover:bg-white/10 text-white rounded text-xs transition-colors"
                                title={t('全选当前显示镜头', 'Select all visible shots')}
                            >
                                {t('全选', 'Select All')}
                            </button>
                            <button
                                onClick={() => toggleSelectAllVisibleShots(false)}
                                className="px-3 py-1.5 hover:bg-white/10 text-white/80 rounded text-xs transition-colors"
                                title={t('清空已选镜头', 'Clear selected shots')}
                            >
                                {t('清空', 'Clear')}
                            </button>
                            <div className="w-px h-4 bg-white/10 mx-1"></div>
                            <button
                                onClick={handleDeleteSelectedShots}
                                disabled={(selectedShotIds || []).length === 0}
                                className="px-3 py-1.5 hover:bg-red-500/20 text-red-300 rounded text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                title={t('删除已选镜头', 'Delete selected shots')}
                            >
                                {t('删除选中', 'Delete Selected')} ({(selectedShotIds || []).length})
                            </button>
                            <button 
                                onClick={handleDeleteAllShots}
                                className="px-2 py-1.5 hover:bg-red-500/20 text-red-500 rounded text-xs transition-colors ml-1 border border-red-500/20 bg-red-500/10"
                                title={t('删除当前显示的全部镜头', 'Delete All Displayed Shots')}
                            >
                                <Trash2 className="w-3 h-3"/>
                            </button>
                        </div>

                        {/* Group 3: Playlist */}
                        <div className="flex items-center bg-black/40 border border-white/10 rounded-lg p-1">
                            <button
                                onClick={openOrderedVideoPlaylist}
                                disabled={orderedVideoShots.length === 0}
                                className="px-3 py-1.5 bg-sky-500/10 hover:bg-sky-500/20 text-sky-200 rounded text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
                                title={t('按当前卡片顺序连续播放视频', 'Play videos sequentially in current card order')}
                            >
                                <Video className="w-3.5 h-3.5" />
                                {t('连续播放', 'Playlist')} ({orderedVideoShots.length})
                            </button>
                        </div>

                        {/* Group 4: Batch Generate */}
                        <div className="flex items-center bg-black/40 border border-white/10 rounded-lg p-1">
                            <div className="relative inline-flex items-center bg-transparent">
                                        <div className="relative flex items-center">
                                            <button 
                                                onClick={handleBatchGenerate}
                                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                                className={`px-3 py-1.5 rounded-l text-xs flex items-center gap-1 transition-all border-r border-white/10 ${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                                title={t('批量生成缺失的起始/结束帧', 'Batch Generate Missing Start/End Frames')}
                                            >
                                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('批量生成镜头', 'Batch Gen Shots')}</span>
                                            </button>
                                            <button 
                                                onClick={() => setIsBatchMenuOpen(!isBatchMenuOpen)}
                                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                                className={`px-1.5 py-1.5 rounded-r text-xs flex items-center transition-all ${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                            >
                                                <ChevronDown className="w-3 h-3" />
                                            </button>
                                            
                                            {isBatchMenuOpen && (
                                                <>
                                                    <div 
                                                        className="fixed inset-0 z-40"
                                                        onClick={() => setIsBatchMenuOpen(false)}
                                                    />
                                                    <div className="absolute top-full left-0 mt-1 w-48 bg-[#1e1e1e] border border-white/20 rounded shadow-xl z-50 overflow-hidden text-white dropdown-menu-container">
                                                        <button
                                                            onClick={() => { setIsBatchMenuOpen(false); handleBatchGenerate(); }}
                                                            className="w-full text-left px-3 py-2.5 text-xs hover:bg-white/10 flex items-center gap-2"
                                                        >
                                                            <Wand2 className="w-3 h-3 text-muted-foreground"/>
                                                            {t('首尾帧依次 (默认)', 'Sequential Start/End')}
                                                        </button>
                                                        <button
                                                            onClick={() => { setIsBatchMenuOpen(false); handleBatchGenerateJointDiptych(); }}
                                                            className="w-full text-left px-3 py-2.5 text-xs hover:bg-white/10 flex items-center gap-2"
                                                        >
                                                            <PanelsTopLeft className="w-3 h-3 text-muted-foreground"/>
                                                            {t('首尾联生', 'Joint Start/End Diptych')}
                                                        </button>
                                                        <button
                                                            onClick={() => { setIsBatchMenuOpen(false); handleBatchGenerateMultiPanelPreview(); }}
                                                            className="w-full text-left px-3 py-2.5 text-xs hover:bg-white/10 flex items-center gap-2"
                                                            title={t('按当前画格预设为每个镜头生成分镜预览并拆分回填', 'Generate storyboard previews for each shot using the current panel preset, then split and fill frames')}
                                                        >
                                                            <Layers className="w-3 h-3 text-muted-foreground"/>
                                                            {t('分镜预览 (批量)', 'Storyboard Preview (Batch)')}
                                                        </button>
                                                        <button
                                                            onClick={() => { setIsBatchMenuOpen(false); handleBatchGenerateVideo(); }}
                                                            className="w-full text-left px-3 py-2.5 text-xs hover:bg-white/10 flex items-center gap-2"
                                                            title={t('仅处理已有首尾帧且当前无视频的镜头', 'Only shots with existing start/end frames and no current video')}
                                                        >
                                                            <Film className="w-3 h-3 text-muted-foreground"/>
                                                            {t('视频', 'Video')}
                                                        </button>
                                                    </div>
                                                </>
                                            )}
                                        </div>

                                        {isBatchGenerating && (
                                            <button
                                                onClick={handleStopShotBatch}
                                                disabled={isStoppingShotBatch || batchProgress.stopRequested}
                                                className={`ml-1 rounded px-3 py-1.5 text-xs flex items-center gap-1 transition-all ${isStoppingShotBatch ? 'bg-amber-500/20 text-amber-200 cursor-wait' : 'bg-amber-500/10 text-amber-300 hover:bg-amber-500/20'}`}
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

                        {/* Group 4b: Batch Storyboard Preview */}
                        <div className="flex items-center gap-1 bg-black/40 border border-white/10 rounded-lg p-1">
                            <select
                                value={batchMultiPanelPresetKey}
                                onChange={(e) => setBatchMultiPanelPresetKey(normalizeMultiPanelPresetKey(e.target.value))}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className="h-[30px] rounded border border-white/10 bg-black/30 px-2 text-xs text-white min-w-[88px]"
                                title={t('批量分镜预览画格数', 'Panel count for batch storyboard preview')}
                            >
                                {MULTI_PANEL_PRESET_OPTIONS.map((option) => (
                                    <option key={`batch-${option.key}`} value={option.key}>
                                        {t(option.labelZh, option.labelEn)}
                                    </option>
                                ))}
                            </select>
                            <label
                                className="flex items-center gap-1.5 px-2 py-1 text-[11px] text-white/80 cursor-pointer hover:bg-white/5 rounded"
                                title={t('选中后每个镜头会以上一镜结束帧作为首格参考', 'When enabled, each shot uses the previous shot end frame as the opening panel reference')}
                            >
                                <input
                                    type="checkbox"
                                    className="hidden"
                                    checked={batchUsePrevEndFrameAsMultiPanelStart}
                                    disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                    onChange={(e) => setBatchUsePrevEndFrameAsMultiPanelStart(e.target.checked)}
                                />
                                <div className={`flex h-3 w-3 items-center justify-center rounded-sm border ${batchUsePrevEndFrameAsMultiPanelStart ? 'border-primary bg-primary text-black' : 'border-white/30 bg-black/20 text-transparent'}`}>
                                    <Check className="h-2.5 w-2.5" />
                                </div>
                                <span>{t('上镜续接', 'Chain Prev End')}</span>
                            </label>
                            <button
                                onClick={handleBatchGenerateMultiPanelPreview}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={`px-3 py-1.5 rounded text-xs flex items-center gap-1 transition-all ${(isBatchGenerating || isShotBatchStarting) ? 'bg-amber-500/20 text-amber-200 cursor-wait' : 'bg-amber-500/10 text-amber-200 hover:bg-amber-500/20'}`}
                                title={t('为当前列表每个镜头批量生成分镜预览，并拆分填入首尾帧与关键帧', 'Batch-generate storyboard previews for each listed shot, split panels into start/end frames and keyframes')}
                            >
                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Layers className="w-3 h-3"/>}
                                {t('批量分镜预览', 'Batch Storyboard Preview')}
                            </button>
                        </div>

                                                {/* Group 5: Tools */}
                        <div className="flex items-center bg-black/40 border border-white/10 rounded-lg p-1">
                            <button
                                onClick={handleBatchScaleDuration}
                                className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded text-xs transition-colors flex items-center gap-1.5"
                                title={t('对当前列表中的所有镜头等比缩放时长', 'Proportionally scale the duration of all shots in the current list')}
                            >
                                <Timer className="w-3.5 h-3.5" />
                                {t('缩放时长', 'Scale Duration')}
                            </button>
                        </div>

                        {/* Group 6: Checkboxes */}
                        <div className="flex items-center gap-4 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 h-[34px]">
                            <label className="flex items-center gap-1.5 cursor-pointer text-xs group transition-colors" title={t('开启后视频生成的分辨率强制下降到480p（忽略项目配置）', 'Force video resolution to 480p, ignoring project info')}>
                                <div className={`w-3.5 h-3.5 rounded-sm border flex flex-shrink-0 items-center justify-center transition-colors ${isDraftMode ? 'bg-primary border-primary' : 'border-white/30 group-hover:border-white/50 bg-black/20'}`}>
                                    {isDraftMode && <Check className="w-2.5 h-2.5 text-white" />}
                                </div>
                                <input type="checkbox" className="hidden" checked={isDraftMode} onChange={(e) => setIsDraftMode(e.target.checked)} />
                                <span className={isDraftMode ? "text-primary font-medium" : "text-white/80 group-hover:text-white"}>{t('草稿(480p)', 'Draft(480p)')}</span>
                            </label>
                            <div className="w-px h-3 bg-white/10 mx-1"></div>
                            <label className="flex items-center gap-1.5 cursor-pointer text-xs group transition-colors" title={t('开启后会优先沿用上一镜的视频内容，帮助当前镜头继续续写并保持连贯。', 'Continue from the previous shot to keep the current shot visually consistent.')}>
                                <div className={`w-3.5 h-3.5 rounded-sm border flex flex-shrink-0 items-center justify-center transition-colors ${usePrevVideo ? 'bg-primary border-primary' : 'border-white/30 group-hover:border-white/50 bg-black/20'}`}>
                                    {usePrevVideo && <Check className="w-2.5 h-2.5 text-white" />}
                                </div>
                                <input type="checkbox" className="hidden" checked={usePrevVideo} onChange={(e) => handleToggleUsePrevVideo(e.target.checked)} />
                                <span className={usePrevVideo ? "text-primary font-medium" : "text-white/80 group-hover:text-white"}>{t('上镜续写', 'Shot Continuation')}</span>
                            </label>
                            {isSelectedVideoApiSeedance2 && (
                                <>
                                    <div className="w-px h-3 bg-white/10 mx-1"></div>
                                    <label className="flex items-center gap-1.5 cursor-pointer text-xs group transition-colors" title={t('开启后 Seedance2 视频时长传 -1，由模型自动决定；关闭则使用表中 Duration(s) 数值。', 'When enabled, Seedance2 requests use duration -1 for model auto timing; when disabled, use the shot Duration (s) value from the table.')}>
                                        <div className={`w-3.5 h-3.5 rounded-sm border flex flex-shrink-0 items-center justify-center transition-colors ${sd2AutoDuration ? 'bg-primary border-primary' : 'border-white/30 group-hover:border-white/50 bg-black/20'}`}>
                                            {sd2AutoDuration && <Check className="w-2.5 h-2.5 text-white" />}
                                        </div>
                                        <input type="checkbox" className="hidden" checked={sd2AutoDuration} onChange={(e) => handleToggleSd2AutoDuration(e.target.checked)} />
                                        <span className={sd2AutoDuration ? "text-primary font-medium" : "text-white/80 group-hover:text-white"}>{t('sd2自动时长', 'SD2 Auto Duration')}</span>
                                    </label>
                                </>
                            )}
                        </div>
                    </div>
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
                     <div className={`grid ${isPortrait ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6' : 'grid-cols-[repeat(auto-fill,minmax(300px,1fr))]'} gap-6 pb-20`}>
                        {isShotsLoading && !hasShotInitialLoadCompleted && sortedShots.length === 0 && (
                            <div className="col-span-full min-h-[256px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-primary/20 rounded-xl bg-primary/5">
                                <Loader2 className="w-12 h-12 mb-4 animate-spin text-primary" />
                                <p>{t('镜头预装入中...', 'Preloading shots...')}</p>
                            </div>
                        )}
                        {sortedShots.map((shot, idx) => {
                            const shotState = generatingStateByShot[String(shot.id)] || { start: false, end: false, video: false };
                            const isVideoGeneratingThisShot = isShotVideoUiRunning(shot.id, shotState);
                            const isGeneratingThisShot = !!(shotState.start || shotState.end || isVideoGeneratingThisShot);
                            const isCroppingThisShot = !!(shotState.cropping);
                            const shotCardPromptPreview = getShotCardPromptPreview(shot);
                            const shotCardPosterUrl = resolveShotVideoPosterUrl(shot) || shot.image_url || getShotEndFrameUrl(shot);
                            return (
                            <div 
                                key={shot.id} 
                                className="bg-card/90 backdrop-blur-sm rounded-2xl border border-white/10 overflow-hidden group hover:border-primary/40 hover:shadow-[0_8px_30px_rgb(0,0,0,0.5)] shadow-[0_4px_20px_rgb(0,0,0,0.3)] hover:-translate-y-1 transition-all duration-300 cursor-pointer relative"
                                onClick={() => setEditingShot(shot)}
                            >
                                {/* Image / Thumbnail */}
                                <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "" : "aspect-video"} bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden`}>
                                    {shot.video_url ? (
                                        shotCardPosterUrl ? (
                                            <SafeImage
                                                src={shotCardPosterUrl}
                                                alt={shot.shot_name}
                                                loading="lazy"
                                                className="w-full h-full object-contain object-center"
                                                fallback={<div className="flex flex-col items-center gap-2 opacity-50"><Video className="w-8 h-8" /><span className="text-xs">{t('视频待加载', 'Video ready')}</span></div>}
                                            />
                                        ) : (
                                            <div className="flex flex-col items-center gap-2 opacity-50">
                                                <Video className="w-8 h-8" />
                                                <span className="text-xs">{t('视频待加载', 'Video ready')}</span>
                                            </div>
                                        )
                                    ) : shot.image_url ? (
                                        <SafeImage src={shot.image_url} alt={shot.shot_name} loading="lazy" className="w-full h-full object-contain object-center" fallback={<div className="flex flex-col items-center gap-2 opacity-50"><ImageIcon className="w-8 h-8" /><span className="text-xs">{t('无图片', 'No Image')}</span></div>} />
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
                                        className={`absolute top-2 right-2 z-20 flex items-center justify-center w-5 h-5 rounded bg-black/60 border border-white/30 shadow transition-opacity ${selectedShotIdSet.has(Number(shot.id)) ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
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
                                    {shotNeedsAnyOssPersist(shot) && (
                                        shotVideoNeedsOssPersist(shot) ? (
                                            <button
                                                type="button"
                                                onClick={(e) => handleTempVideoBadgeClick(shot, e)}
                                                disabled={Boolean(shotMediaOssPersistBusy[`${String(shot?.id || '').trim()}:video`])}
                                                className="absolute bottom-2 left-2 z-20 inline-flex items-center gap-1 rounded bg-amber-500/90 hover:bg-amber-400 disabled:opacity-70 disabled:cursor-wait text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow cursor-pointer"
                                                title={t('点击检查并补传到 OSS', 'Click to check and upload to OSS')}
                                            >
                                                {shotMediaOssPersistBusy[`${String(shot?.id || '').trim()}:video`] ? (
                                                    <Loader2 size={12} className="animate-spin" />
                                                ) : (
                                                    <AlertTriangle size={12} />
                                                )}
                                                <span>
                                                    {shotMediaOssPersistBusy[`${String(shot?.id || '').trim()}:video`]
                                                        ? t('补传中', 'Uploading')
                                                        : t('临时视频', 'Temp Video')}
                                                </span>
                                            </button>
                                        ) : (
                                            <div
                                                className="absolute bottom-2 left-2 z-20 inline-flex items-center gap-1 rounded bg-amber-500/90 text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow pointer-events-none"
                                                title={t('部分素材未持久化到 OSS', 'Some media not persisted to OSS')}
                                            >
                                                <AlertTriangle size={12} />
                                                <span>{t('临时图片', 'Temp Image')}</span>
                                            </div>
                                        )
                                    )}
                                    <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold pointer-events-none">
                                        {getShotDurationDisplayValue(shot.duration) || '0s'}
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
                                        {getShotDurationDisplayValue(shot.duration) && (
                                            <span className="text-[10px] text-muted-foreground bg-white/5 px-1.5 py-0.5 rounded ml-2 whitespace-nowrap">
                                                {getShotDurationDisplayValue(shot.duration)}
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
                            <div className="col-span-full min-h-[256px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-white/10 rounded-xl">
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

            {isPlaylistModalOpen && (
                <div className="fixed inset-0 z-[120] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={closeOrderedVideoPlaylist}>
                    <div className="w-full max-w-5xl bg-[#0b0b0f] border border-white/15 rounded-xl shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                        <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between gap-3">
                            <div className="min-w-0">
                                <div className="text-sm font-semibold text-white flex items-center gap-2">
                                    <Film className="w-4 h-4 text-primary" />
                                    {t('镜头视频连续播放', 'Shot Video Playlist')}
                                </div>
                                <div className="text-xs text-muted-foreground mt-1">
                                    {orderedVideoShots.length > 0
                                        ? t(
                                            `第 ${Math.min(playlistIndex + 1, orderedVideoShots.length)} / ${orderedVideoShots.length} 条`,
                                            `${Math.min(playlistIndex + 1, orderedVideoShots.length)} / ${orderedVideoShots.length}`
                                        )
                                        : t('无可播放视频', 'No playable video')}
                                </div>
                            </div>
                            <button
                                className="p-2 rounded hover:bg-white/10 text-white/80"
                                onClick={closeOrderedVideoPlaylist}
                                title={t('关闭', 'Close')}
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-4">
                            <div className="w-full bg-black rounded-lg border border-white/10 overflow-hidden flex items-center justify-center min-h-[320px] max-h-[70vh]">
                                {activePlaylistShot ? (
                                    <video
                                        ref={playlistVideoRef}
                                        key={`${activePlaylistShot.id || 'shot'}:${playlistIndex}:${String(activePlaylistShot.video_url || '')}:${mediaReloadTick}`}
                                        src={getFullUrl(activePlaylistShot.video_url)}
                                        controls
                                        autoPlay
                                        playsInline
                                        preload="metadata"
                                        className="w-full max-h-[70vh] object-contain bg-black"
                                        onEnded={handlePlaylistVideoEnded}
                                    />
                                ) : (
                                    <div className="text-sm text-muted-foreground flex items-center gap-2 py-16">
                                        <Video className="w-5 h-5" />
                                        {t('当前没有可播放视频', 'No playable videos in current view')}
                                    </div>
                                )}
                            </div>

                            {activePlaylistShot && (
                                <div className="mt-3 text-xs text-muted-foreground">
                                    <span className="text-primary font-mono mr-2">{activePlaylistShot.shot_id || activePlaylistShot.id}</span>
                                    <span className="text-white/90">{activePlaylistShot.shot_name || t('未命名镜头', 'Untitled Shot')}</span>
                                </div>
                            )}

                            <div className="mt-4 flex items-center justify-between gap-2">
                                <button
                                    onClick={playPrevPlaylistVideo}
                                    disabled={playlistIndex <= 0}
                                    className="px-3 py-1.5 text-xs rounded border border-white/15 bg-white/5 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                    {t('上一个', 'Previous')}
                                </button>
                                <button
                                    onClick={playNextPlaylistVideo}
                                    disabled={playlistIndex >= orderedVideoShots.length - 1}
                                    className="px-3 py-1.5 text-xs rounded border border-primary/40 bg-primary/15 text-primary hover:bg-primary/25 disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                    {t('下一个', 'Next')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

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
                     onClose={closeMediaPicker} 
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
                            <h3 className="font-bold text-lg flex flex-wrap items-center gap-2">
                                {t('编辑镜头', 'Edit Shot')} {editingShot.shot_id}
                                {editingShot.shot_name && <span className="text-base font-normal text-muted-foreground">- {editingShot.shot_name}</span>}
                                <div className="flex items-center gap-1 ml-2 md:gap-2">
                                    <label className="text-xs font-normal text-muted-foreground">Duration(s):</label>
                                    <input 
                                        className={`bg-black/30 border border-white/10 rounded px-2 py-1 text-sm font-normal text-white focus:border-primary/50 focus:outline-none w-16 ${isSd2AutoDurationActive ? 'text-primary border-primary/40' : ''}`}
                                        value={getShotDurationDisplayValue(editingShot.duration)}
                                        onChange={e => {
                                            if (isSd2AutoDurationActive) return;
                                            setEditingShot({...editingShot, duration: e.target.value});
                                        }}
                                        readOnly={isSd2AutoDurationActive}
                                        placeholder="e.g. 5"
                                    />
                                    {isSelectedVideoApiSeedance2 && (
                                        <label className="flex items-center gap-1 cursor-pointer text-[11px] text-muted-foreground hover:text-white/80" title={t('开启后视频生成传 -1 自动时长；关闭则使用左侧 Duration(s)', 'When enabled, video generation sends -1 for auto duration; when disabled, use Duration (s) on the left')}>
                                            <div className={`w-3 h-3 rounded-sm border flex items-center justify-center ${sd2AutoDuration ? 'bg-primary border-primary' : 'border-white/30 bg-black/20'}`}>
                                                {sd2AutoDuration && <Check className="w-2 h-2 text-white" />}
                                            </div>
                                            <input type="checkbox" className="hidden" checked={sd2AutoDuration} onChange={(e) => handleToggleSd2AutoDuration(e.target.checked)} />
                                            <span className={sd2AutoDuration ? 'text-primary' : ''}>{t('sd2自动时长', 'SD2 Auto Duration')}</span>
                                        </label>
                                    )}
                                </div>
                            </h3>
                            <div className="flex items-center gap-2">
                                <FunctionApiSelector functionName="generate_shot_images" configs={functionApiConfigs} label={t('图片模型: ', 'Image: ')} />
                                <div className="flex items-center gap-1" ref={shotNotePopoverRef}>
                                    <FunctionApiSelector functionName="generate_videos" configs={functionApiConfigs} label={t('视频模型: ', 'Video: ')} />
                                    <div className="relative">
                                        <button
                                            type="button"
                                            onClick={(e) => { e.stopPropagation(); openShotNotePopover('review'); }}
                                            className={`p-1.5 rounded-md border transition-colors ${editingShotReviewNotes ? 'border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20' : 'border-white/10 bg-black/20 text-white/50 hover:text-white hover:bg-white/10'}`}
                                            title={editingShotReviewNotes ? t('审核意见（已填写）', 'Review notes (filled)') : t('填写审核意见', 'Add review notes')}
                                            aria-label={t('审核意见', 'Review notes')}
                                        >
                                            <CheckCircle2 className="w-4 h-4" />
                                        </button>
                                        {renderShotNotePopoverPanel('review')}
                                    </div>
                                    <div className="relative">
                                        <button
                                            type="button"
                                            onClick={(e) => { e.stopPropagation(); openShotNotePopover('edit'); }}
                                            className={`p-1.5 rounded-md border transition-colors ${editingShotEditNotes ? 'border-sky-500/40 bg-sky-500/10 text-sky-300 hover:bg-sky-500/20' : 'border-white/10 bg-black/20 text-white/50 hover:text-white hover:bg-white/10'}`}
                                            title={editingShotEditNotes ? t('剪辑意见（已填写）', 'Edit notes (filled)') : t('填写剪辑意见', 'Add edit notes')}
                                            aria-label={t('剪辑意见', 'Edit notes')}
                                        >
                                            <Scissors className="w-4 h-4" />
                                        </button>
                                        {renderShotNotePopoverPanel('edit')}
                                    </div>
                                </div>
                                <TabMediaRefreshButton
                                    onClick={handleRefreshEditShotElements}
                                    loading={editShotRefreshing}
                                    uiLang={uiLang}
                                    compact
                                />
                                <button onClick={() => setEditingShot(null)} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                            </div>
                        </div>
                        <div className="p-4 sm:p-6 space-y-6">

                            <div>
                                <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                                    <label className="text-[10px] uppercase font-bold text-muted-foreground">{t('镜头逻辑（中文）', 'Shot Logic (CN)')}</label>
                                    <button
                                        type="button"
                                        onClick={handleRestoreShotFromAiStaging}
                                        disabled={restoringFromStaging || !editingShot?.scene_id}
                                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-emerald-500/40 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25 text-xs font-medium disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                                        title={t('从场景 AI 镜头暂存区恢复该分镜的提示词等信息（保留已生成图片/视频）', 'Restore prompts from scene AI staging (keeps generated images/videos)')}
                                    >
                                        {restoringFromStaging ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                                        {restoringFromStaging ? t('恢复中…', 'Restoring…') : t('恢复分镜', 'Restore Storyboard')}
                                    </button>
                                </div>
                                <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                    className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs text-white/80 h-[80px] focus:outline-none focus:border-primary/50 cursor-not-allowed opacity-80"
                                    value={editingShot.shot_logic_cn || ''}
                                    readOnly={true}
                                    placeholder={t('镜头逻辑描述（中文）...', 'Shot logic description (Chinese)...')}
                                />
                            </div>

                            {/* 1. Workflow / Media Assets */}
                            <div className="space-y-6">
                                
                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                                    {/* Start Frame */}
                                    <div className={isPortrait ? 'flex items-stretch gap-2.5 h-full' : 'space-y-2'}>
                                        <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full  pr-1 justify-start' : ''}`}>
                                            <div className="flex flex-col min-h-[52px] items-center justify-center gap-1.5">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center justify-center gap-2">
                                                {t('起始帧', 'Start Frame')}
                                            </div>
                                            <div className="flex flex-wrap items-center justify-center gap-1.5 bg-black/40 border border-white/10 rounded-md p-1.5 w-full shadow-sm">
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
                                                        }, { shotId: editingShot.id, shotFrameType: 'start', desiredAssetType: 'image', lockAssetType: false, allowMultiSelect: false });
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
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[216px] shrink-0"
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
                                            pickContext={{ shotId: editingShot?.id, shotFrameType: 'start_ref', desiredAssetType: 'all', lockAssetType: false, allowMultiSelect: true }}
                                            storageKey="ref_image_urls"
                                            defaultAutoRefs={resolveShotVideoImageRefs(editingShot)}
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
                                    <div className={isPortrait ? 'flex items-stretch gap-2.5 h-full' : 'space-y-2'}>
                                        <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full  pr-1 justify-start' : ''}`}>
                                            <div className="flex flex-col min-h-[52px] items-center justify-center gap-1.5">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center justify-center gap-2">
                                                {t('结束帧', 'End Frame')}
                                            </div>
                                            <div className="flex flex-wrap items-center justify-center gap-1.5 bg-black/40 border border-white/10 rounded-md p-1.5 w-full shadow-sm">
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
                                                        }, { shotId: editingShot.id, shotFrameType: 'end', desiredAssetType: 'image', lockAssetType: false, allowMultiSelect: false });
                                                    }}
                                                    disabled={isShotFrameActionLocked('end')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                                                    title={isShotFrameActionLocked('end') ? t('结束帧任务运行中，不能更换图片', 'End frame job is running; image changes are disabled') : t('设置结束帧图片', 'Set end frame image')}
                                                >
                                                    <ImageIcon className="w-3 h-3"/> {t('设置', 'Set')}
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
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[216px] shrink-0"
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
                                            pickContext={{ shotId: editingShot?.id, shotFrameType: 'end_ref', desiredAssetType: 'all', lockAssetType: false, allowMultiSelect: true }}
                                            storageKey="end_ref_image_urls"
                                            defaultAutoRefs={resolveShotVideoImageRefs(editingShot)}
                                            strictPromptOnly={true}
                                        />
                                        </div>
                                    </div>

                                    {/* Final Video Output (Moved Here) */}
                                    <div className={isPortrait ? 'flex items-stretch gap-2.5 h-full' : 'space-y-2'}>
                                        <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full  pr-1 justify-start' : ''}`}>
                                            <div className="flex flex-col min-h-[52px] items-center justify-center gap-1.5">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center justify-center gap-2">
                                                {t('最终视频', 'Final Video')}
                                            </div>

                                            <div className="flex flex-wrap items-center justify-center gap-1.5 bg-black/40 border border-white/10 rounded-md p-1.5 w-full shadow-sm">
                                                <button
                                                    onClick={() => openAssetDetailModal('video')}
                                                    className="bg-white/10 hover:bg-white/20 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={() => openMediaPicker((url) => {
                                                        const changes = { video_url: url };
                                                        onUpdateShot(editingShot.id, changes).catch((e) => {
                                                            console.error('Manual video apply failed:', e);
                                                        });
                                                    }, { type: 'video', shotId: editingShot.id, shotFrameType: 'video', desiredAssetType: 'video', lockAssetType: false, allowMultiSelect: false })}
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
                                                        } catch(e) { return 'entity_refs'; }
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
                                                    <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                    <option value="start_end">{t('起始+结束', 'Start+End')}</option>
                                                    <option value="start">{t('仅起始', 'Start Only')}</option>
                                                    <option value="keyframes_entity_refs">{t('关键帧+实体参考', 'Keyframes+Entity Refs')}</option>
                                                    <option value="entity_refs_start_end">{t('参考图+首尾帧', 'Ref+StartEnd')}</option>
                                                </select>

                                                <label className="flex items-center gap-1 text-[10px] text-gray-300 hover:text-white cursor-pointer select-none ml-1 mr-1">
                                                    <input 
                                                        type="checkbox" 
                                                        className="hidden"
                                                        checked={isDraftMode}
                                                        onChange={(e) => setIsDraftMode(e.target.checked)}
                                                    />
                                                    <div className={`w-2.5 h-2.5 rounded-sm border flex items-center justify-center transition-colors ${isDraftMode ? 'bg-primary border-primary' : 'border-white/30 hover:border-white/50 bg-black/20'}`}>
                                                        {isDraftMode && <Check className="w-2 h-2 text-white" />}
                                                    </div>
                                                    <span className={isDraftMode ? 'text-primary font-medium' : 'text-gray-400 font-medium'}>{t('草稿', 'Draft')}</span>
                                                </label>

                                                <button
                                                    onClick={handleUpscaleCurrentVideo}
                                                    disabled={currentShotGenerating || !String(editingShot?.video_url || '').trim()}
                                                    className={`text-[10px] font-bold px-2 py-1 rounded flex items-center justify-center gap-1 ${currentShotGenerating || !String(editingShot?.video_url || '').trim() ? 'bg-white/10 text-white/40 cursor-not-allowed' : 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'}`}
                                                    title={t('Topaz 视频画质提升 2x', 'Topaz video upscale 2x')}
                                                    aria-label={t('Topaz 视频画质提升 2x', 'Topaz video upscale 2x')}
                                                >
                                                    <Sparkles className="w-3 h-3" />
                                                    <span>2x</span>
                                                </button>

                                                <div className="relative">
                                                    <button
                                                        type="button"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setVideoCleanupMenuOpen((open) => !open);
                                                        }}
                                                        disabled={currentShotGenerating || !String(editingShot?.video_url || '').trim()}
                                                        className={`text-[10px] font-bold px-2 py-1 rounded flex items-center justify-center gap-1 ${currentShotGenerating || !String(editingShot?.video_url || '').trim() ? 'bg-white/10 text-white/40 cursor-not-allowed' : 'bg-amber-500/20 text-amber-200 hover:bg-amber-500/30'}`}
                                                        title={t('本地去除字幕 / BGM', 'Local remove subtitles / BGM')}
                                                        aria-label={t('本地去除字幕 / BGM', 'Local remove subtitles / BGM')}
                                                    >
                                                        <Eraser className="w-3 h-3" />
                                                        <ChevronDown className="w-3 h-3 opacity-70" />
                                                    </button>
                                                    {videoCleanupMenuOpen && (
                                                        <div
                                                            className="absolute right-0 top-full mt-1 z-40 min-w-[148px] rounded-md border border-white/15 bg-[#1a1b1f] shadow-xl overflow-hidden"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            <button
                                                                type="button"
                                                                className="w-full px-3 py-2 text-left text-[11px] text-white/85 hover:bg-white/10 flex items-center gap-2"
                                                                onClick={() => handleLocalVideoCleanup('remove_subtitle')}
                                                            >
                                                                <CaptionsOff className="w-3.5 h-3.5 text-amber-200" />
                                                                {t('去除字幕', 'Remove subtitles')}
                                                            </button>
                                                            <button
                                                                type="button"
                                                                className="w-full px-3 py-2 text-left text-[11px] text-white/85 hover:bg-white/10 flex items-center gap-2"
                                                                onClick={() => handleLocalVideoCleanup('remove_bgm')}
                                                            >
                                                                <VolumeX className="w-3.5 h-3.5 text-amber-200" />
                                                                {t('去除 BGM', 'Remove BGM')}
                                                            </button>
                                                            <button
                                                                type="button"
                                                                className="w-full px-3 py-2 text-left text-[11px] text-white/85 hover:bg-white/10 flex items-center gap-2 border-t border-white/10"
                                                                onClick={() => handleLocalVideoCleanup('remove_subtitle_and_bgm')}
                                                            >
                                                                <Eraser className="w-3.5 h-3.5 text-amber-200" />
                                                                {t('字幕 + BGM', 'Subtitles + BGM')}
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>

                                                <label className="flex items-center gap-1 text-[10px] text-gray-300 hover:text-white cursor-pointer select-none ml-1 mr-2">
                                                    <input 
                                                        type="checkbox" 
                                                        className="hidden"
                                                        checked={usePrevVideo}
                                                        onChange={(e) => handleToggleUsePrevVideo(e.target.checked, editingShot?.id)}
                                                    />
                                                    <div className={`w-2.5 h-2.5 rounded-sm border flex items-center justify-center transition-colors ${usePrevVideo ? 'bg-primary border-primary' : 'border-white/30 hover:border-white/50 bg-black/20'}`}>
                                                        {usePrevVideo && <Check className="w-2 h-2 text-white" />}
                                                    </div>
                                                    <span className={usePrevVideo ? 'text-primary font-medium' : 'text-gray-400 font-medium'}>{t('上镜续写', 'Shot Continuation')}</span>
                                                </label>

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
                                            </div>
                                        </div>

                                        <div 
                                            style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "h-[420px] 2xl:h-[480px] w-auto mx-auto shrink-0" : "aspect-video w-full"} bg-black rounded border border-white/10 relative group overflow-hidden cursor-pointer flex items-center justify-center`}
                                            onClick={() => openAssetDetailModal('video')}
                                        >
                                            {currentGeneratingState.video && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">{t(
                                                        videoStatuses[editingShot.id] === 'upscaling' ? '正在 Topaz 提质...' :
                                                        videoStatuses[editingShot.id] === 'cleaning_subtitle' ? '正在本地去除字幕...' :
                                                        videoStatuses[editingShot.id] === 'cleaning_bgm' ? '正在本地去除 BGM...' :
                                                        videoStatuses[editingShot.id] === 'cleaning_both' ? '正在本地去除字幕与 BGM...' :
                                                        (videoStatuses[editingShot.id] === 'saving' || videoStatuses[editingShot.id] === 'saving_video' || videoStatuses[editingShot.id] === 'save_video') ? '保存视频中...' :
                                                        (videoStatuses[editingShot.id] === 'loading' || videoStatuses[editingShot.id] === 'loading_video' || videoStatuses[editingShot.id] === 'load_video' || videoStatuses[editingShot.id] === 'downloading' || videoStatuses[editingShot.id] === 'downloading_video') ? '加载视频中...' :
                                                        (videoStatuses[editingShot.id] === 'fetching' || videoStatuses[editingShot.id] === 'fetching_video') ? '获取视频中...' :
                                                        '正在生成视频...',
                                                        videoStatuses[editingShot.id] === 'upscaling' ? 'Topaz upscaling...' :
                                                        videoStatuses[editingShot.id] === 'cleaning_subtitle' ? 'Removing subtitles locally...' :
                                                        videoStatuses[editingShot.id] === 'cleaning_bgm' ? 'Removing BGM locally...' :
                                                        videoStatuses[editingShot.id] === 'cleaning_both' ? 'Removing subtitles & BGM locally...' :
                                                        (videoStatuses[editingShot.id] === 'saving' || videoStatuses[editingShot.id] === 'saving_video' || videoStatuses[editingShot.id] === 'save_video') ? 'Saving Video...' :
                                                        (videoStatuses[editingShot.id] === 'loading' || videoStatuses[editingShot.id] === 'loading_video' || videoStatuses[editingShot.id] === 'load_video' || videoStatuses[editingShot.id] === 'downloading' || videoStatuses[editingShot.id] === 'downloading_video') ? 'Loading Video...' :
                                                        (videoStatuses[editingShot.id] === 'fetching' || videoStatuses[editingShot.id] === 'fetching_video') ? 'Fetching Video...' :
                                                        'Generating Video...'
                                                    )}</span>
                                                </div>
                                            )}
                                            {currentGeneratingState.video ? (
                                                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20 overflow-hidden pointer-events-none">
                                                    {resolveShotVideoPosterUrl(editingShot) ? (
                                                        <SafeImage
                                                            src={resolveShotVideoPosterUrl(editingShot)}
                                                            alt={editingShot.shot_name || 'video poster'}
                                                            loading="lazy"
                                                            className="absolute inset-0 w-full h-full object-contain opacity-40 mix-blend-overlay"
                                                        />
                                                    ) : null}
                                                </div>
                                            ) : (editingShot.video_url) ? (
                                                isEditingVideoPreviewArmed ? (
                                                    <ManagedVideoPlayer
                                                        key={`${editingShot.id}:${String(editingShot.video_url || '')}`}
                                                        src={editingShot.video_url}
                                                        poster={resolveShotVideoPosterUrl(editingShot)}
                                                        className="max-w-full max-h-full object-contain"
                                                        wrapperClassName="w-full h-full"
                                                        preload="metadata"
                                                        suspend={assetDetailModal.open && assetDetailModal.type === 'video'}
                                                        hideBusyOverlay={false}
                                                        uiLang={uiLang}
                                                        onClick={(e) => e?.preventDefault?.()}
                                                    />
                                                ) : (
                                                    <button
                                                        type="button"
                                                        className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/20 hover:bg-black/10 transition-colors"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setIsEditingVideoPreviewArmed(true);
                                                        }}
                                                    >
                                                        {resolveShotVideoPosterUrl(editingShot) ? (
                                                            <SafeImage
                                                                src={resolveShotVideoPosterUrl(editingShot)}
                                                                alt={editingShot.shot_name || 'video poster'}
                                                                loading="lazy"
                                                                className="absolute inset-0 w-full h-full object-contain opacity-70"
                                                            />
                                                        ) : null}
                                                        <span className="relative z-10 inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/65 px-4 py-2 text-xs font-medium text-white shadow-lg">
                                                            <Video className="w-4 h-4" />
                                                            {t('点击加载视频预览', 'Click to load video preview')}
                                                        </span>
                                                    </button>
                                                )
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20 flex-col gap-2">
                                                    <Video className="w-10 h-10"/>
                                                    <span className="text-xs">{t('暂无视频', 'No Video')}</span>
                                                </div>
                                            )}
                                             {(editingShot.video_url) && <div className="absolute inset-0 flex items-center justify-center pointer-events-none group-hover:bg-black/10"><Maximize2 className="text-white opacity-0 group-hover:opacity-100 drop-shadow-md"/></div>}
                                             {shotVideoNeedsOssPersist(editingShot) && (
                                                <button
                                                    type="button"
                                                    onClick={(e) => handleTempVideoBadgeClick(editingShot, e)}
                                                    disabled={Boolean(shotMediaOssPersistBusy[`${String(editingShot?.id || '').trim()}:video`])}
                                                    className="absolute bottom-2 left-2 z-20 inline-flex items-center gap-1 rounded bg-amber-500/90 hover:bg-amber-400 disabled:opacity-70 disabled:cursor-wait text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow cursor-pointer"
                                                    title={t('点击检查并补传到 OSS', 'Click to check and upload to OSS')}
                                                >
                                                    {shotMediaOssPersistBusy[`${String(editingShot?.id || '').trim()}:video`] ? (
                                                        <Loader2 className="w-3 h-3 animate-spin" />
                                                    ) : (
                                                        <AlertTriangle size={12} />
                                                    )}
                                                    <span>
                                                        {shotMediaOssPersistBusy[`${String(editingShot?.id || '').trim()}:video`]
                                                            ? t('补传中', 'Uploading')
                                                            : t('临时视频', 'Temp Video')}
                                                    </span>
                                                </button>
                                             )}
                                             
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
                                                            }, { type: 'video', shotId: editingShot.id, shotFrameType: 'video', desiredAssetType: 'video', lockAssetType: false, allowMultiSelect: false });
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

                                        
<div className="flex justify-between items-center mb-1 mt-2">
    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('动作 / 运动提示词', 'Action / Motion Prompt')}</div>
    <button 
        onClick={() => setTunePromptModalConfig({ open: true, targetField: 'video', initialValue: shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''; } catch (e) { return ''; } })() : getShotVideoPromptEn(editingShot) })} 
        className="text-[11px] flex items-center gap-1 text-primary hover:text-primary-foreground hover:bg-primary/50 px-2 py-0.5 rounded transition-colors"
    >
        ✨ {t('AI 提示词修改', 'AI Prompt Tuning')}
    </button>
</div>
<PromptMentionTextarea entities={entities} uiLang={uiLang}
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[216px] shrink-0"
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
                                            pickContext={{ shotId: editingShot?.id, shotFrameType: 'video_ref', desiredAssetType: 'all', lockAssetType: false, allowMultiSelect: true }}
                                            additionalAutoRefs={resolvePrevContinuationVideoRefs(editingShot?.id)}
                                            storageKey="video_ref_image_urls"
                                            strictPromptOnly
                                            maxSubmitRefSlots={DEFAULT_VIDEO_REFERENCE_SLOT_LIMIT}
                                        />
                                        </div>
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}
                                <div className="space-y-4 border-t border-white/10 pt-4">
                                    {(() => {
                                        let tech = {};
                                        try {
                                            tech = JSON.parse(editingShot.technical_notes || '{}');
                                        } catch (e) {}
                                        const explicitMultiPanelUrl = String(tech.multi_panel_image_url || tech.storyboard_url || '').trim();
                                        const startFrameFallbackUrl = String(editingShot?.image_url || '').trim();
                                        const multiPanelUrl = explicitMultiPanelUrl || startFrameFallbackUrl;
                                        const multiPanelUrlIsStartFrameFallback = !explicitMultiPanelUrl && Boolean(startFrameFallbackUrl);
                                        const canResplitMultiPanel = Boolean(multiPanelUrl);
                                        const currentPresetOption = getMultiPanelPresetOption(tech.multi_panel_image_preset || multiPanelPresetKey);
                                        const multiPanelStartsFromPrevEnd = tech.multi_panel_start_from_prev_end === true;
                                        const multiPanelPrevEndRefUrl = String(tech.multi_panel_prev_end_ref_url || '').trim();
                                        const multiPanelPrevEndRefSummary = String(tech.multi_panel_prev_end_ref_summary || '').trim();
                                        const prevShotFrameMeta = (tech.prev_shot_frame_meta && typeof tech.prev_shot_frame_meta === 'object')
                                            ? tech.prev_shot_frame_meta
                                            : {};
                                        const prevShotFrameSourceLabel = String(prevShotFrameMeta.source_shot_label || '').trim();

                                        return (
                                            <>
                                                <div className="space-y-3">
                                                    <div>
                                                        <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                            {t('关键帧（时间线）', 'Keyframes (Timeline)')}
                                                            <span className="bg-white/10 text-white px-1.5 rounded-full text-[9px]">
                                                                {localKeyframes.length}
                                                            </span>
                                                        </div>
                                                        <div className="text-xs text-muted-foreground mt-1">{t('多画格图会自动拆分并填入起始帧、结束帧与关键帧。', 'Multi-panel images are automatically split and filled into start frame, end frame, and keyframes.')}</div>
                                                    </div>
                                                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                                                        <div className="rounded-lg border border-white/10 bg-black/15 p-3 space-y-2">
                                                            <div className="text-[10px] uppercase font-bold text-muted-foreground">{t('分镜预览', 'Storyboard Preview')}</div>
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <select
                                                                    value={multiPanelPresetKey}
                                                                    onChange={async (e) => {
                                                                        const nextPresetKey = normalizeMultiPanelPresetKey(e.target.value);
                                                                        setMultiPanelPresetKey(nextPresetKey);
                                                                        const nextTech = { ...tech, multi_panel_image_preset: nextPresetKey };
                                                                        const nextTechNotes = JSON.stringify(nextTech);
                                                                        setEditingShot((prev) => ({ ...(prev || {}), technical_notes: nextTechNotes }));
                                                                        try {
                                                                            await onUpdateShot(editingShot.id, { technical_notes: nextTechNotes });
                                                                        } catch (error) {
                                                                            onLog?.(`${t('保存多画格预设失败', 'Failed to save multi-panel preset')}: ${error?.message || 'unknown error'}`, 'error');
                                                                        }
                                                                    }}
                                                                    className="h-9 rounded border border-white/10 bg-black/30 px-3 text-sm text-white"
                                                                    title={t('选择多画格预设', 'Choose multi-panel preset')}
                                                                >
                                                                    {MULTI_PANEL_PRESET_OPTIONS.map((option) => (
                                                                        <option key={option.key} value={option.key}>
                                                                            {t(option.labelZh, option.labelEn)}
                                                                        </option>
                                                                    ))}
                                                                </select>
                                                                <label
                                                                    className="flex items-center gap-2 rounded border border-white/10 bg-black/20 px-3 py-2 text-xs text-white/80 cursor-pointer hover:bg-white/5"
                                                                    title={t('选中后自动取上一镜结束帧作为首参考图，并直接读取上一镜结束帧提示词注入多画格提示词，要求第一格从该参考图开始。', 'Use the previous shot end frame as the first ref, read the previous end-frame prompt directly, inject it into the multi-panel prompt, and force panel 1 to start from that image.')}
                                                                >
                                                                    <input
                                                                        type="checkbox"
                                                                        className="hidden"
                                                                        checked={usePrevEndFrameAsMultiPanelStart}
                                                                        onChange={async (e) => {
                                                                            const checked = e.target.checked;
                                                                            setUsePrevEndFrameAsMultiPanelStart(checked);
                                                                            try {
                                                                                const nextTech = { ...tech, multi_panel_start_from_prev_end: checked };
                                                                                if (!checked) {
                                                                                    delete nextTech.multi_panel_prev_end_ref_url;
                                                                                    delete nextTech.multi_panel_prev_end_ref_summary;
                                                                                }
                                                                                const nextTechNotes = JSON.stringify(nextTech);
                                                                                setEditingShot((prev) => ({ ...(prev || {}), technical_notes: nextTechNotes }));
                                                                                await onUpdateShot(editingShot.id, { technical_notes: nextTechNotes });
                                                                            } catch (error) {
                                                                                onLog?.(`${t('保存多画格起始参考设置失败', 'Failed to save multi-panel opening ref setting')}: ${error?.message || 'unknown error'}`, 'error');
                                                                            }
                                                                        }}
                                                                    />
                                                                    <div className={`flex h-3.5 w-3.5 items-center justify-center rounded-sm border ${usePrevEndFrameAsMultiPanelStart ? 'border-primary bg-primary text-black' : 'border-white/30 bg-black/20 text-transparent'}`}>
                                                                        <Check className="h-3 w-3" />
                                                                    </div>
                                                                    <span>{t('以上镜结束帧开始', 'Start From Prev End Frame')}</span>
                                                                </label>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleGenerateMultiPanelImage()}
                                                                    disabled={isGeneratingMultiPanelImage}
                                                                    title={t('按当前视频提示词生成并自动拆分到关键帧', 'Generate from the current video prompt and auto-split into keyframes')}
                                                                    className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${isGeneratingMultiPanelImage ? 'bg-white/10 text-white/40 cursor-wait' : 'bg-white/10 text-white/80 hover:bg-white/20'}`}
                                                                >
                                                                    {isGeneratingMultiPanelImage ? t('生成中...', 'Generating...') : t('生成并拆分', 'Generate + Split')}
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleResplitMultiPanelImage()}
                                                                    disabled={!canResplitMultiPanel || isResplittingMultiPanelImage}
                                                                    title={multiPanelUrlIsStartFrameFallback
                                                                        ? t('未保存多画格原图记录时，将用当前首帧图按所选预设重新拆分', 'If no saved multi-panel source exists, re-split using the current start frame and selected preset')
                                                                        : t('基于当前多画格图重新切分并重建关键帧', 'Re-split the current multi-panel image and rebuild keyframes')}
                                                                    className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${(!canResplitMultiPanel || isResplittingMultiPanelImage) ? 'bg-amber-500/10 text-amber-300/50 cursor-not-allowed' : 'bg-amber-500/20 text-amber-200 hover:bg-amber-500/30'}`}
                                                                >
                                                                    {isResplittingMultiPanelImage ? t('重新拆分中...', 'Re-splitting...') : t('重新拆分', 'Re-split')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                        <div className="rounded-lg border border-white/10 bg-black/15 p-3 space-y-2">
                                                            <div className="text-[10px] uppercase font-bold text-muted-foreground">{t('分镜截取（用于下镜参考）', 'Storyboard Extract (Next-Shot Ref)')}</div>
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <div className="flex items-center gap-2 rounded border border-white/10 bg-black/20 px-2 py-1.5">
                                                                    <span className="text-[11px] text-white/80">{t('截取帧数', 'Frame Count')}</span>
                                                                    <input
                                                                        type="number"
                                                                        min={2}
                                                                        step={1}
                                                                        value={videoKeyframeExtractCount}
                                                                        onChange={(e) => setVideoKeyframeExtractCount(e.target.value)}
                                                                        className="w-16 h-7 rounded border border-white/10 bg-black/40 px-2 text-xs text-white outline-none focus:border-sky-400/60"
                                                                        title={t('按输入帧数从上一分镜视频均匀截取（至少 2）', 'Extract evenly spaced frames from the previous shot video by frame count (minimum 2)')}
                                                                    />
                                                                    <button
                                                                        type="button"
                                                                        onClick={handleExtractPrevShotFramesFromVideo}
                                                                        disabled={isExtractingVideoKeyframes}
                                                                        title={t('从上一分镜视频均匀截取上镜帧（含首尾帧），不影响关键帧', 'Extract evenly spaced prev-shot frames from the previous shot video (including first and last), without modifying keyframes')}
                                                                        className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${isExtractingVideoKeyframes ? 'bg-sky-500/10 text-sky-200/50 cursor-wait' : 'bg-sky-500/20 text-sky-200 hover:bg-sky-500/30'}`}
                                                                    >
                                                                        {isExtractingVideoKeyframes ? t('截取中...', 'Extracting...') : t('截取上镜帧', 'Extract Prev-Shot Frames')}
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                                {multiPanelStartsFromPrevEnd ? (
                                                    <div className="rounded-lg border border-sky-400/20 bg-sky-500/10 px-3 py-2.5 text-xs text-sky-50">
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-sky-100">
                                                                {t('首格参考', 'Opening Ref')}
                                                            </span>
                                                            <span className="text-sky-50/85">
                                                                {t('当前多画格会以上一镜结束帧作为开始分镜。', 'This multi-panel run starts from the previous shot end frame.')}
                                                            </span>
                                                        </div>
                                                        {multiPanelPrevEndRefSummary ? (
                                                            <div className="mt-2 rounded border border-white/10 bg-black/15 px-2.5 py-2 text-white/85">
                                                                <span className="mr-2 text-[10px] font-bold uppercase tracking-[0.1em] text-sky-100">{t('图片摘要', 'Image Summary')}</span>
                                                                <span>{multiPanelPrevEndRefSummary}</span>
                                                            </div>
                                                        ) : null}
                                                        {multiPanelPrevEndRefUrl ? (
                                                            <div className="mt-2 flex flex-wrap items-center gap-2">
                                                                <span className="text-white/55 truncate max-w-full">{t('来源：上一镜结束帧', 'Source: previous shot end frame')}</span>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => window.open(getFullUrl(multiPanelPrevEndRefUrl), '_blank', 'noopener,noreferrer')}
                                                                    className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10"
                                                                >
                                                                    <LinkIcon size={12} />
                                                                    {t('查看参考图', 'View Ref')}
                                                                </button>
                                                            </div>
                                                        ) : null}
                                                    </div>
                                                ) : null}
                                                <div className="space-y-2">
                                                    <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                        {t('上镜帧', 'Prev-Shot Frames')}
                                                        <span className="bg-sky-400/15 text-sky-100 px-1.5 rounded-full text-[9px]">
                                                            {localPrevShotFrames.length}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {t('从上一分镜视频截取的参考帧，单独保存，不会回填到关键帧。', 'Reference frames extracted from the previous shot video, stored separately and not written into keyframes.')}
                                                        {prevShotFrameSourceLabel ? (
                                                            <span className="ml-1 text-white/55">
                                                                {t('来源：', 'Source: ')}{prevShotFrameSourceLabel}
                                                            </span>
                                                        ) : null}
                                                    </div>
                                                    <div className="flex gap-4 overflow-x-auto pb-2 min-h-[140px] snap-x">
                                                        {localPrevShotFrames.length === 0 && (
                                                            <div className="text-xs text-muted-foreground italic p-2 w-full text-center border-dashed border border-white/10 rounded">
                                                                {t('暂无上镜帧。使用上方「截取上镜帧」从上一分镜视频提取。', 'No prev-shot frames yet. Use "Extract Prev-Shot Frames" above to extract from the previous shot video.')}
                                                            </div>
                                                        )}
                                                        {localPrevShotFrames.map((frame, idx) => (
                                                            <div key={`psf-${idx}-${frame.time}`} className="relative w-[220px] flex-shrink-0 bg-sky-500/5 rounded border border-sky-400/15 p-2 space-y-2 snap-center group">
                                                                <div className="flex justify-between items-center text-[10px]">
                                                                    <div className="flex items-center gap-1">
                                                                        <span className="text-sky-200/80 font-bold">T=</span>
                                                                        <span className="text-white/85">{frame.time}</span>
                                                                    </div>
                                                                    <div className="flex gap-1">
                                                                        {frame.url ? (
                                                                            <button
                                                                                type="button"
                                                                                onClick={() => window.open(getFullUrl(frame.url), '_blank', 'noopener,noreferrer')}
                                                                                className="px-1.5 py-0.5 bg-white/10 hover:bg-white/20 text-white rounded"
                                                                            >
                                                                                {t('查看', 'View')}
                                                                            </button>
                                                                        ) : null}
                                                                        <button
                                                                            type="button"
                                                                            onClick={async () => {
                                                                                const updated = [...localPrevShotFrames];
                                                                                updated.splice(idx, 1);
                                                                                setLocalPrevShotFrames(updated);
                                                                                await reconstructPrevShotFrames(updated);
                                                                            }}
                                                                            className="p-1 hover:bg-red-500/20 text-muted-foreground hover:text-red-500 rounded transition-colors"
                                                                        >
                                                                            <Trash2 className="w-3 h-3" />
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                                <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border border-white/10 relative overflow-hidden flex items-center justify-center`}>
                                                                    {frame.url ? (
                                                                        <SafeImage src={frame.url} className="max-w-full max-h-full object-contain" />
                                                                    ) : (
                                                                        <div className="absolute inset-0 flex items-center justify-center opacity-20">
                                                                            <ImageIcon className="w-6 h-6" />
                                                                        </div>
                                                                    )}
                                                                </div>
                                                                <div className="text-[10px] text-white/60 truncate">{frame.prompt}</div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                                {multiPanelUrl ? (
                                                    <div className="rounded-lg border border-white/10 bg-black/15 px-3 py-2">
                                                        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                                                            <div className="flex items-center gap-2 min-w-0">
                                                                <Layers className="w-3.5 h-3.5 text-amber-200 shrink-0" />
                                                                <span className="text-muted-foreground uppercase font-bold shrink-0">{t(`${currentPresetOption.labelZh}预设图`, `${currentPresetOption.labelEn} Preset Image`)}</span>
                                                                <span className="text-white/60 truncate">
                                                                    {multiPanelUrlIsStartFrameFallback
                                                                        ? t('当前首帧可作为多画格拆分来源', 'Current start frame can be used as the multi-panel split source')
                                                                        : t('已作为关键帧拆分来源', 'Used as the split source for keyframes')}
                                                                </span>
                                                            </div>
                                                            <div className="flex flex-wrap gap-2">
                                                                <button type="button" onClick={() => window.open(getFullUrl(multiPanelUrl), '_blank', 'noopener,noreferrer')} className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10">
                                                                    <LinkIcon size={12} />
                                                                    {t('查看原图', 'View Source')}
                                                                </button>
                                                                {explicitMultiPanelUrl ? (
                                                                    <button
                                                                        type="button"
                                                                        onClick={async () => {
                                                                            const nextTech = { ...tech };
                                                                            delete nextTech.multi_panel_image_url;
                                                                            delete nextTech.multi_panel_image_preset;
                                                                            delete nextTech.multi_panel_last_split_source_url;
                                                                            delete nextTech.storyboard_url;
                                                                            const nextStr = JSON.stringify(nextTech);
                                                                            setEditingShot(prev => ({ ...(prev || {}), technical_notes: nextStr }));
                                                                            await onUpdateShot(editingShot.id, { technical_notes: nextStr });
                                                                        }}
                                                                        className="inline-flex items-center gap-1 rounded border border-red-400/20 bg-red-500/10 px-2 py-1 text-[11px] text-red-100 hover:bg-red-500/20"
                                                                    >
                                                                        <Trash2 size={12} />
                                                                        {t('删除原图记录', 'Delete Source Record')}
                                                                    </button>
                                                                ) : null}
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </>
                                        );
                                    })()}
                                    
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
                                                            onClick={() => openMediaPicker((url, type, selectedItems) => {
                                                                const pickedUrls = (selectedItems && selectedItems.length > 0)
                                                                    ? selectedItems.map((item) => item?.url).filter(Boolean)
                                                                    : (url ? [url] : []);
                                                                if (pickedUrls.length === 0) return;

                                                                const updated = [...localKeyframes];
                                                                pickedUrls.forEach((pickedUrl, offset) => {
                                                                    const targetIndex = idx + offset;
                                                                    if (!updated[targetIndex]) return;
                                                                    updated[targetIndex].url = pickedUrl;
                                                                });
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }, { shotId: editingShot?.id, shotFrameType: 'keyframe', desiredAssetType: 'image', lockAssetType: false, allowMultiSelect: true })}
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
                                                    className="w-full bg-black/20 border border-white/10 rounded p-1.5 text-[10px] h-[120px] focus:border-primary/50 outline-none resize-none"
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
                                            .replace(/^(CHAR|ENV|PROP|VEFX|SFX)\s*:\s*/i, '')
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
                                                    Available({entities.length}): {entities.map(e => {
                                                        const nameZh = String(e.name || '').trim();
                                                        const nameEn = String(e.name_en || '').trim();
                                                        const isSubset = nameZh && nameEn && (nameZh.toLowerCase().includes(nameEn.toLowerCase()) || nameEn.toLowerCase().includes(nameZh.toLowerCase()));
                                                        return `${e.name}${nameEn && !isSubset ? `/${e.name_en}` : ''}`;
                                                    }).slice(0, 15).join(', ')}
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
                                    <div className="w-full max-w-[96rem] h-[94vh] bg-[#09090b] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden">
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
                                                const currentMultiPanelPresetOption = getMultiPanelPresetOption(tech.multi_panel_image_preset || multiPanelPresetKey);
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

                                                const linkedAsset = resolveShotAssetByUrl(detailUrl, detailType, modalType);
                                                const linkedAssetDetail = buildShotAssetDetail(linkedAsset, detailType, detailUrl);
                                                const detailPreviewUrl = String(linkedAssetDetail?.url || detailUrl || '').trim();
                                                const linkedAssetMeta = linkedAssetDetail.rawMeta;
                                                const persistedStartMeta = (tech.start_frame_metadata && typeof tech.start_frame_metadata === 'object') ? tech.start_frame_metadata : null;
                                                const persistedEndMeta = (tech.end_frame_metadata && typeof tech.end_frame_metadata === 'object') ? tech.end_frame_metadata : null;
                                                const persistedVideoMeta = (tech.video_metadata && typeof tech.video_metadata === 'object') ? tech.video_metadata : null;
                                                const hasLinkedAssetMeta = Boolean(linkedAssetMeta && Object.keys(linkedAssetMeta).length > 0);
                                                const resolvedShotMediaMeta = hasLinkedAssetMeta
                                                    ? linkedAssetMeta
                                                    : (modalType === 'start'
                                                        ? persistedStartMeta
                                                        : (modalType === 'end'
                                                            ? persistedEndMeta
                                                            : (modalType === 'video' ? persistedVideoMeta : null)));
                                                const shotConfiguredDuration = getShotDurationDisplayValue(editingShot?.duration);

                                                const effectiveAssetDetail = (() => {
                                                    const hasBuiltDetail = Boolean(
                                                        linkedAssetDetail.resolution
                                                        || linkedAssetDetail.fileSize
                                                        || linkedAssetDetail.model
                                                        || linkedAssetDetail.aspectRatio
                                                        || linkedAssetDetail.duration
                                                    );
                                                    if (hasBuiltDetail) return linkedAssetDetail;
                                                    if (resolvedShotMediaMeta && Object.keys(resolvedShotMediaMeta).length > 0) {
                                                        return buildShotAssetDetail(
                                                            {
                                                                meta_info: resolvedShotMediaMeta,
                                                                url: detailPreviewUrl,
                                                                type: detailType,
                                                            },
                                                            detailType,
                                                            detailPreviewUrl
                                                        );
                                                    }
                                                    return linkedAssetDetail;
                                                })();

                                                const renderAssetMetaStrip = (assetDetail = effectiveAssetDetail) => {
                                                    const mediaType = String(assetDetail.type || detailType || '').trim().toLowerCase();
                                                    const items = [
                                                        { label: t('分辨率', 'Resolution'), value: assetDetail.resolution },
                                                        { label: t('画幅比', 'Aspect Ratio'), value: assetDetail.aspectRatio },
                                                        { label: t('文件大小', 'File Size'), value: assetDetail.fileSize },
                                                        { label: t('生成模型', 'Model'), value: assetDetail.model },
                                                        {
                                                            label: t('提供商', 'Provider'),
                                                            value: assetDetail.providerAlias || assetDetail.provider,
                                                        },
                                                        ...(mediaType === 'video'
                                                            ? [{ label: t('时长', 'Duration'), value: assetDetail.duration }]
                                                            : []),
                                                        ...(assetDetail.format
                                                            ? [{ label: t('格式', 'Format'), value: assetDetail.format }]
                                                            : []),
                                                    ].filter((item) => {
                                                        const value = String(item.value || '').trim();
                                                        return value && value !== '-';
                                                    });

                                                    return (
                                                        <div className="border-t border-white/10 bg-black/75 backdrop-blur-sm px-4 py-2.5 shrink-0">
                                                            {shotAssetsMetaLoading ? (
                                                                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                                                    <Loader2 className="w-3 h-3 animate-spin" />
                                                                    {t('加载元数据...', 'Loading metadata...')}
                                                                </div>
                                                            ) : items.length > 0 ? (
                                                                <div className="flex flex-wrap gap-x-5 gap-y-1.5">
                                                                    {items.map(({ label, value }) => (
                                                                        <div key={label} className="flex items-baseline gap-1.5 text-[11px] min-w-0">
                                                                            <span className="text-white/45 shrink-0">{label}</span>
                                                                            <span className="text-white/90 font-mono truncate max-w-[220px]" title={String(value)}>
                                                                                {value}
                                                                            </span>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            ) : (
                                                                <div className="text-[11px] text-white/40">
                                                                    {t('暂无分辨率/模型等元数据', 'No resolution/model metadata yet')}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                };

                                                const renderAssetMetaPanel = (assetDetail = effectiveAssetDetail, rawMeta = linkedAssetMeta, titleText = t('资产元数据', 'Asset Metadata')) => (
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
                                                        warning: busy
                                                            ? 'bg-amber-500/10 text-amber-300/50 cursor-wait'
                                                            : disabled
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
        
        const stableTargetShotId = String(editingShot.id || '').trim();

        try {
            // Force local state update immediately so any view derived from `shots`
            // (e.g. the continuous-play/playlist modal) reflects the newly selected
            // version right away, instead of only the `editingShot` detail state.
            setShots((prev) => (prev || []).map((shot) => (
                String(shot?.id || '').trim() === stableTargetShotId ? { ...shot, ...updates } : shot
            )));
            setEditingShot((prev) => {
                if (!prev) return prev;
                return { ...prev, ...updates };
            });

            if (onUpdateShot) {
                await onUpdateShot(editingShot.id, updates);
            }
            showNotification(t('已选用为当前', 'Applied as current'), 'success');

            // Reconcile with the backend so the shot list (source of truth for the
            // playlist) never drifts out of sync with the detail view.
            refreshShotAssetsMeta?.();
            Promise.resolve(refreshShots?.()).catch(() => {});
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
                                                                                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
                                                                                        <span>{createdText}</span>
                                                                                        {item.model && (
                                                                                            <span className="flex items-center gap-1">
                                                                                                <Cpu size={10} className="opacity-50" />
                                                                                                <span className="opacity-80 max-w-[100px] truncate" title={item.model}>{item.model}</span>
                                                                                            </span>
                                                                                        )}
                                                                                        {item.duration && (
                                                                                            <span className="flex items-center gap-1">
                                                                                                <Timer size={10} className="opacity-50" />
                                                                                                <span className="opacity-80">{Number(item.duration).toFixed(1)}s</span>
                                                                                            </span>
                                                                                        )}
                                                                                    </div>
                                                                                    <div className="flex flex-wrap items-center gap-2 pt-1">
                                                                                        <button
                                                                                            type="button"
                                                                                            onClick={() => canPreview && window.open(getFullUrl(item.resultUrl), '_blank', 'noopener,noreferrer')}
                                                                                            disabled={!canPreview}
                                                                                            className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10 disabled:opacity-40"
                                                                                        >
                                                                                            <LinkIcon size={12} />
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

                                                const isOriginalPreview = assetDetailPreviewMode === 'original';
                                                const previewShellClass = isOriginalPreview
                                                    ? 'h-[46vh] xl:h-[58vh] bg-black/60 rounded border overflow-hidden flex flex-col relative transition-colors'
                                                    : 'h-[46vh] xl:h-[58vh] bg-black/40 rounded border overflow-hidden flex flex-col relative transition-colors';
                                                const previewContentClass = isOriginalPreview
                                                    ? 'flex-1 min-h-0 overflow-auto p-4 flex items-start justify-center'
                                                    : 'flex-1 min-h-0 overflow-hidden flex items-center justify-center relative';
                                                const imagePreviewClass = isOriginalPreview
                                                    ? 'max-w-none max-h-none w-auto h-auto shadow-lg rounded'
                                                    : 'max-w-full max-h-full object-contain shadow-lg rounded';
                                                const videoPreviewClass = isOriginalPreview
                                                    ? 'w-auto h-auto max-w-none max-h-none shadow-lg rounded'
                                                    : 'w-full h-full object-contain shadow-lg rounded';
                                                const renderPreviewModeToggle = () => (
                                                    <button
                                                        type="button"
                                                        onClick={() => setAssetDetailPreviewMode((prev) => (prev === 'fit' ? 'original' : 'fit'))}
                                                        className="absolute top-3 right-3 z-20 rounded-full border border-white/15 bg-black/70 px-3 py-1.5 text-[11px] font-medium text-white/90 hover:bg-black/85"
                                                    >
                                                        {isOriginalPreview ? t('适配视窗', 'Fit View') : t('原始尺寸', 'Original Size')}
                                                    </button>
                                                );

                                                if (modalType === 'start') {
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)] gap-4">
                                                            <div className="space-y-3 min-w-0">
                                                                <div className={`${previewShellClass} ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`}>
                                                                    {renderPreviewModeToggle()}
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
                                                                    <div className={previewContentClass}>
                                                                        {detailPreviewUrl ? <SafeImage src={detailPreviewUrl} className={imagePreviewClass} fallback={<ImageIcon className="w-8 h-8 opacity-30" />} /> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                    </div>
                                                                    {renderAssetMetaStrip()}
                                                                </div>
                                                                {renderInfoPanel(t('当前素材信息', 'Current Asset Info'), [
                                                                    { label: t('素材名', 'Asset Name'), value: effectiveAssetDetail.displayName || '-' },
                                                                    { label: t('图片 URL', 'Image URL'), value: editingShot.image_url || '-', breakAll: true },
                                                                    { label: t('参考图数量', 'Ref Count'), value: String(Array.isArray(tech.ref_image_urls) ? tech.ref_image_urls.length : 0) },
                                                                ])}
                                                                {renderOssPersistWarningPanel(editingShot, 'start')}
                                                            </div>
                                                            <div className="space-y-3 min-w-0">
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
                                                                        className="w-full h-[256px] bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={startPromptTextEn}
                                                                        onChange={(e) => {
                                                                            setEditingShot({...editingShot, start_frame: e.target.value});
                                                                        }}
                                                                    />
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                        {t('中文提示词', 'Prompt (CN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-[256px] bg-black/30 border border-white/10 rounded p-3 text-sm"
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
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => { persistEditingShotUpdates(updates); }} title={t('参考图', 'Refs')} promptText={shotPromptDisplayLang === 'cn' ? startPromptTextCn : startPromptTextEn} uiLang={uiLang} onPickMedia={openMediaPicker} pickContext={{ shotId: editingShot?.id, shotFrameType: 'start_ref', desiredAssetType: 'all', lockAssetType: false, allowMultiSelect: true }} storageKey="ref_image_urls" defaultAutoRefs={resolveShotVideoImageRefs(editingShot)} strictPromptOnly={true} />
                                                                {imageCfgControl}
                                                                {renderGenerationHistoryPanel()}
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                if (modalType === 'end') {
                                                    return (
                                                        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)] gap-4">
                                                                <div className="space-y-3 min-w-0">
                                                                    <div className={`${previewShellClass} ${currentGeneratingState.end ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`}>
                                                                        {renderPreviewModeToggle()}
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
                                                                    <div className={previewContentClass}>
                                                                        {detailPreviewUrl ? <SafeImage src={detailPreviewUrl} className={imagePreviewClass} fallback={<ImageIcon className="w-8 h-8 opacity-30" />} /> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                    </div>
                                                                    {renderAssetMetaStrip()}
                                                                </div>
                                                                {renderInfoPanel(t('当前素材信息', 'Current Asset Info'), [
                                                                    { label: t('素材名', 'Asset Name'), value: effectiveAssetDetail.displayName || '-' },
                                                                    { label: t('结束帧 URL', 'End Frame URL'), value: endFrameUrl || '-', breakAll: true },
                                                                    { label: t('参考图数量', 'Ref Count'), value: String(Array.isArray(tech.end_ref_image_urls) ? tech.end_ref_image_urls.length : 0) },
                                                                ])}
                                                                {renderOssPersistWarningPanel(editingShot, 'end')}
                                                            </div>
                                                            <div className="space-y-3 min-w-0">
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
                                                                </div>
                                                                <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-4">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">
                                                                        {t('英文提示词', 'Prompt (EN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-[256px] bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                        value={endPromptTextEn}
                                                                        onChange={(e) => {
                                                                            handleManualEndFrameInputChange(e.target.value);
                                                                        }}
                                                                    />
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                        {t('中文提示词', 'Prompt (CN)')}
                                                                    </div>
                                                                    <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                        className="w-full h-[256px] bg-black/30 border border-white/10 rounded p-3 text-sm"
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
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => { persistEditingShotUpdates(updates); }} title={t('参考图', 'Refs')} promptText={shotPromptDisplayLang === 'cn' ? endPromptTextCn : endPromptTextEn} uiLang={uiLang} onPickMedia={openMediaPicker} pickContext={{ shotId: editingShot?.id, shotFrameType: 'end_ref', desiredAssetType: 'all', lockAssetType: false, allowMultiSelect: true }} storageKey="end_ref_image_urls" defaultAutoRefs={resolveShotVideoImageRefs(editingShot)} strictPromptOnly={true} />
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
                                                        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)] gap-4">
                                                            <div className="space-y-3 min-w-0">
                                                                <div className={`${previewShellClass} border-white/10`}>
                                                                    {renderPreviewModeToggle()}
                                                                    {currentGeneratingState.video && (
                                                                        <div className="absolute inset-0 z-10 bg-black/60 flex items-center justify-center flex-col gap-2">
                                                                            <Loader2 className="w-6 h-6 animate-spin text-primary" />
                                                                            <span className="text-xs text-white/80">{t(
                                                                                videoStatuses[editingShot.id] === 'upscaling' ? '正在 Topaz 提质...' :
                                                                                videoStatuses[editingShot.id] === 'cleaning_subtitle' ? '正在本地去除字幕...' :
                                                                                videoStatuses[editingShot.id] === 'cleaning_bgm' ? '正在本地去除 BGM...' :
                                                                                videoStatuses[editingShot.id] === 'cleaning_both' ? '正在本地去除字幕与 BGM...' :
                                                                                (videoStatuses[editingShot.id] === 'saving' || videoStatuses[editingShot.id] === 'saving_video' || videoStatuses[editingShot.id] === 'save_video') ? '保存视频中...' :
                                                                                (videoStatuses[editingShot.id] === 'loading' || videoStatuses[editingShot.id] === 'loading_video' || videoStatuses[editingShot.id] === 'load_video' || videoStatuses[editingShot.id] === 'downloading' || videoStatuses[editingShot.id] === 'downloading_video') ? '加载视频中...' :
                                                                                (videoStatuses[editingShot.id] === 'fetching' || videoStatuses[editingShot.id] === 'fetching_video') ? '获取视频中...' :
                                                                                '正在生成视频...',
                                                                                videoStatuses[editingShot.id] === 'upscaling' ? 'Topaz upscaling...' :
                                                                                videoStatuses[editingShot.id] === 'cleaning_subtitle' ? 'Removing subtitles locally...' :
                                                                                videoStatuses[editingShot.id] === 'cleaning_bgm' ? 'Removing BGM locally...' :
                                                                                videoStatuses[editingShot.id] === 'cleaning_both' ? 'Removing subtitles & BGM locally...' :
                                                                                (videoStatuses[editingShot.id] === 'saving' || videoStatuses[editingShot.id] === 'saving_video' || videoStatuses[editingShot.id] === 'save_video') ? 'Saving Video...' :
                                                                                (videoStatuses[editingShot.id] === 'loading' || videoStatuses[editingShot.id] === 'loading_video' || videoStatuses[editingShot.id] === 'load_video' || videoStatuses[editingShot.id] === 'downloading' || videoStatuses[editingShot.id] === 'downloading_video') ? 'Loading Video...' :
                                                                                (videoStatuses[editingShot.id] === 'fetching' || videoStatuses[editingShot.id] === 'fetching_video') ? 'Fetching Video...' :
                                                                                'Generating Video...'
                                                                            )}</span>
                                                                        </div>
                                                                    )}
                                                                    <div className={previewContentClass}>
                                                                        {editingShot.video_url ? (
                                                                            <ManagedVideoPlayer
                                                                                key={`${editingShot.id}:${String(editingShot.video_url || '')}`}
                                                                                src={detailPreviewUrl || editingShot.video_url}
                                                                                poster={resolveShotVideoPosterUrl(editingShot)}
                                                                                className={videoPreviewClass}
                                                                                wrapperClassName="w-full h-full"
                                                                                preload="metadata"
                                                                                suspend={Boolean(currentGeneratingState.video)}
                                                                                hideBusyOverlay={Boolean(currentGeneratingState.video)}
                                                                                uiLang={uiLang}
                                                                            />
                                                                        ) : <Video className="w-8 h-8 opacity-30" />}
                                                                    </div>
                                                                    {renderAssetMetaStrip()}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('素材名', 'Asset Name')}: {effectiveAssetDetail.displayName || '-'}</div>
                                                                <div className="text-xs text-muted-foreground break-all">{t('视频 URL', 'Video URL')}: {editingShot.video_url || '-'}</div>
                                                                {modalType === 'video' && renderOssPersistWarningPanel(editingShot, 'video', {
                                                                    bodyZh: '当前链接为供应商临时地址（如 volces TOS 签名 URL），可能会过期。请尽快补传到 OSS。',
                                                                    bodyEn: 'The current link is a temporary provider URL (e.g. volces TOS signed URL) and may expire. Upload it to OSS as soon as possible.',
                                                                })}
                                                                <div className="text-xs text-muted-foreground break-all">{t('配音 URL', 'Voice URL')}: {String(tech.voiceover_url || '') || '-'}</div>
                                                                <div className="space-y-1 rounded-lg border border-white/10 bg-black/20 p-3">
                                                                    <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('素材实际时长', 'Asset Duration')}</div>
                                                                    <div className="text-sm text-white">{effectiveAssetDetail.duration || '-'}</div>
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
                                                                        onChange={(e) => {
                                                                            if (isSd2AutoDurationActive) return;
                                                                            setEditingShot(prev => ({ ...(prev || {}), duration: e.target.value }));
                                                                        }}
                                                                        readOnly={isSd2AutoDurationActive}
                                                                        className={`w-full bg-black/30 border border-white/10 rounded p-2 text-sm text-white ${isSd2AutoDurationActive ? 'text-primary border-primary/40' : ''}`}
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
                                                            </div>
                                                            <div className="space-y-3 min-w-0">
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    {assetDetailModal.type === 'video' && (
                                                                        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer select-none">
                                                                            <input 
                                                                                type="checkbox" 
                                                                                checked={isDraftMode}
                                                                                onChange={(e) => setIsDraftMode(e.target.checked)}
                                                                                className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                                                                            />
                                                                            {t('草稿(480p)', 'Draft (480p)')}
                                                                        </label>
                                                                    )}
                                                                    {renderDetailActionButton({
                                                                        label: t('Topaz 提质 2x', 'Topaz Upscale 2x'),
                                                                        busyLabel: t('Topaz 提质中...', 'Topaz upscaling...'),
                                                                        onClick: handleUpscaleCurrentVideo,
                                                                        disabled: currentShotGenerating || !String(editingShot?.video_url || '').trim(),
                                                                        busy: currentShotGenerating && videoStatuses[editingShot.id] === 'upscaling',
                                                                        variant: 'success',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('去除字幕', 'Remove Subtitles'),
                                                                        busyLabel: t('去字幕中...', 'Removing subtitles...'),
                                                                        onClick: () => handleLocalVideoCleanup('remove_subtitle'),
                                                                        disabled: currentShotGenerating || !String(editingShot?.video_url || '').trim(),
                                                                        busy: currentShotGenerating && videoStatuses[editingShot.id] === 'cleaning_subtitle',
                                                                        variant: 'warning',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('去除 BGM', 'Remove BGM'),
                                                                        busyLabel: t('去 BGM 中...', 'Removing BGM...'),
                                                                        onClick: () => handleLocalVideoCleanup('remove_bgm'),
                                                                        disabled: currentShotGenerating || !String(editingShot?.video_url || '').trim(),
                                                                        busy: currentShotGenerating && videoStatuses[editingShot.id] === 'cleaning_bgm',
                                                                        variant: 'warning',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('生成视频', 'Generate Video'),
                                                                        busyLabel: t(
                                                                            (videoStatuses[editingShot.id] === 'saving' || videoStatuses[editingShot.id] === 'saving_video' || videoStatuses[editingShot.id] === 'save_video') ? '保存视频中...' :
                                                                            (videoStatuses[editingShot.id] === 'loading' || videoStatuses[editingShot.id] === 'loading_video' || videoStatuses[editingShot.id] === 'load_video' || videoStatuses[editingShot.id] === 'downloading' || videoStatuses[editingShot.id] === 'downloading_video') ? '加载视频中...' :
                                                                            (videoStatuses[editingShot.id] === 'fetching' || videoStatuses[editingShot.id] === 'fetching_video') ? '获取视频中...' :
                                                                            '视频生成中...',
                                                                            (videoStatuses[editingShot.id] === 'saving' || videoStatuses[editingShot.id] === 'saving_video' || videoStatuses[editingShot.id] === 'save_video') ? 'Saving Video...' :
                                                                            (videoStatuses[editingShot.id] === 'loading' || videoStatuses[editingShot.id] === 'loading_video' || videoStatuses[editingShot.id] === 'load_video' || videoStatuses[editingShot.id] === 'downloading' || videoStatuses[editingShot.id] === 'downloading_video') ? 'Loading Video...' :
                                                                            (videoStatuses[editingShot.id] === 'fetching' || videoStatuses[editingShot.id] === 'fetching_video') ? 'Fetching Video...' :
                                                                            'Generating Video...'
                                                                        ),
                                                                        onClick: () => generateAssetWithLang('video'),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu('video')}
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
                                                                        <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                                        <option value="start_end">{t('起始+结束', 'Start+End')}</option>
                                                                        <option value="start">{t('仅起始', 'Start Only')}</option>
                                                                        <option value="keyframes_entity_refs">{t('关键帧+实体参考', 'Keyframes+Entity Refs')}</option>
                                                                        <option value="entity_refs_start_end">{t('参考图+首尾帧', 'Ref+StartEnd')}</option>
                                                                    </select>
                                                                </div>
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                    {t('中文提示词', 'Prompt (CN)')}
                                                                </div>
                                                                <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                    className="w-full h-[256px] bg-black/30 border border-white/10 rounded p-3 text-sm"
                                                                    value={videoPromptTextCn}
                                                                    onChange={(e) => {
                                                                        updateTechField('video_prompt_cn', e.target.value);
                                                                    }}
                                                                />
                                                                <div className="text-[11px] text-muted-foreground uppercase font-bold mt-4">
                                                                    {t('英文提示词', 'Prompt (EN)')}
                                                                </div>
                                                                <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                    className="w-full h-[256px] bg-black/30 border border-white/10 rounded p-3 text-sm"
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
                                                                <ReferenceManager shot={editingShot} entities={entities} onUpdate={(updates) => { persistEditingShotUpdates(updates); }} title={t('参考图', 'Refs')} promptText={`${getShotVideoPromptEn(editingShot) || ''}\n${(() => { try { return String(JSON.parse(editingShot.technical_notes || '{}')?.video_prompt_cn || ''); } catch (e) { return ''; } })()}`} uiLang={uiLang} onPickMedia={openMediaPicker} pickContext={{ shotId: editingShot?.id, shotFrameType: 'video_ref', desiredAssetType: 'all', lockAssetType: false, allowMultiSelect: true }} additionalAutoRefs={resolvePrevContinuationVideoRefs(editingShot?.id)} storageKey="video_ref_image_urls" strictPromptOnly maxSubmitRefSlots={DEFAULT_VIDEO_REFERENCE_SLOT_LIMIT} />
                                                                {renderGenerationHistoryPanel()}
                                                            </div>
                                                        </div>
                                                    );
                                                }

                                                return (
                                                    <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
                                                        <div className="space-y-3">
                                                            <div className="h-[46vh] xl:h-[58vh] bg-black/40 rounded border border-white/10 overflow-hidden flex flex-col">
                                                                <div className="flex-1 min-h-0 flex items-center justify-center">
                                                                    {keyframe?.url ? <SafeImage src={keyframe.url} className="max-w-full max-h-full object-contain" fallback={<ImageIcon className="w-8 h-8 opacity-30" />} /> : <ImageIcon className="w-8 h-8 opacity-30" />}
                                                                </div>
                                                                {renderAssetMetaStrip()}
                                                            </div>
                                                            {renderInfoPanel(t('当前素材信息', 'Current Asset Info'), [
                                                                { label: t('关键帧时间', 'Keyframe Time'), value: keyframe?.time || '-' },
                                                                { label: t('关键帧 URL', 'Keyframe URL'), value: keyframe?.url || '-', breakAll: true },
                                                            ])}
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
                                                            <PromptMentionTextarea entities={entities} uiLang={uiLang} className="w-full h-[448px] bg-black/30 border border-white/10 rounded p-3 text-sm" value={keyframe?.prompt || ''} onChange={(e) => {
                                                                const updated = [...localKeyframes];
                                                                if (!updated[assetDetailModal.keyframeIndex]) return;
                                                                updated[assetDetailModal.keyframeIndex].prompt = e.target.value;
                                                                setLocalKeyframes(updated);
                                                            }} />
                                                            <div className="text-[11px] text-muted-foreground uppercase font-bold">{t('中文对照提示词', 'Prompt (CN)')}</div>
                                                            <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                                                className="w-full h-[384px] bg-black/30 border border-white/10 rounded p-3 text-sm"
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
                                            <PromptMentionTextarea entities={entities} uiLang={uiLang} className="w-full bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px] h-[176px]" value={shot["Video Content"] || shot.video_content || ''} onChange={e => {
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

            <TunePromptAgentModal
                isOpen={Boolean(tunePromptModalConfig.open)}
                onClose={() => setTunePromptModalConfig({ open: false, targetField: null, initialValue: '' })}
                initialValue={tunePromptModalConfig.initialValue || ''}
                promptLang={shotPromptDisplayLang}
                uiLang={uiLang}
                onApply={handleApplyTunedShotPrompt}
                onLog={onLog}
            />

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
