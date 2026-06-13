
import FunctionApiSelector from '../../../components/FunctionApiSelector';
import { useFunctionApis } from '../../../components/useFunctionApis';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { MediaPickerModal, AssetHoverMetaOverlay } from './MediaModals';
import AiEntityCreateDialog from './AiEntityCreateDialog';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../../../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../../../lib/store';
import LogPanel from '../../../components/LogPanel';
import ProjectStatusBar from '../../../components/ProjectStatusBar';
import { ImagePlus, Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, Paintbrush, Cpu, Timer, History } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL, ASSET_BASE_URL } from '../../../config';
import { setUiLang as setGlobalUiLang } from '../../../lib/uiLang';

import {
    getFullUrl, createInitialFrameTrimState, clampFrameTrimPercent, normalizeFrameTrimMargins, brokenMediaUrls, brokenSceneImageUrls, warmMediaUrls, shouldBypassBrokenMediaCache, rememberBrokenMediaUrl, isBrokenMediaUrl, rememberWarmMediaUrl, isWarmMediaUrl, getSafeMediaUrl, extractImageJobResultUrl, rememberBrokenSceneImageUrl, isBrokenSceneImageUrl, normalizeBatchParallelLimit, normalizeAsciiSubjectSeparatorsForDeps, normalizeSubjectNameForDeps, normalizeSubjectKeyForDeps, normalizeAsciiSubjectSeparators, normalizeSubjectName, normalizeSubjectKey, normalizeImportSubjectKey, IMG_PLACEHOLDER_SRC, parseVisualDependencies, SafeImage, SafeAudio, normalizeMediaRefList, areMediaRefListsEqual, collectMatchedEntitiesFromPrompt, collectMatchedEntityImageUrlsFromPrompt, SCENE_SUBJECT_TYPE_LABELS, getSceneSubjectStatusKey, splitSceneSubjectNames, normalizeSceneSubjectDefaultType, parseTypedSceneSubjectToken, extractSceneSubjectRefsFromField, buildSceneSubjectNameCandidates, extractSceneSubjectRefs, findMatchingEntityByType, findMissingSceneSubjectRefs, findCrossTypeEntityMatches, buildSceneSubjectPlaceholderPayload, createMissingSceneSubjectPlaceholders, collectMatchedSubjectImageUrlsFromPrompt, resolveUnifiedVideoMode, buildAutoVideoRefList, resolveShotVideoPosterUrl, LazyHoverVideo, InViewVideo, ManagedVideoPlayer, parseEpisodeNumberFromText, normalizeEpisodeTitleForDisplay, buildEntityNegativePrompt, normalizeImageSizeOption, normalizeAspectRatioOption, parseAspectRatioParts, parseAspectRatioValue, reduceAspectRatioParts, buildAspectRatioString, inferImageSizeFromResolution, getEpisodePreferredImageSize, getEpisodePreferredAspectRatio, getProjectPreferredImageSize, getProjectPreferredAspectRatio, buildShotDiptychPlan, getShotDiptychLayoutLabel, buildShotDiptychLayoutInstruction, buildShotDiptychAspectContract, getShotDiptychSeamTrimPx, getShotDiptychSeamBiasPx, getShotDiptychFallbackCropPx, JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION, SHOT_FRAME_ASSET_UPLOAD_VERSION, hashStableText, buildJointShotDiptychUploadIdempotencyKey, buildShotFrameAssetUploadIdempotencyKey, collectSupportedAspectRatioOptions, collectSupportedImageSizeOptions, selectBestShotDiptychRequestAspectRatio, selectBestSupportedImageSize, resolveShotPanelExportResolution, resolveShotDiptychRequestResolution, getResolutionByAspectAndImageSize, SHOT_IMAGE_CFG_MIN, SHOT_IMAGE_CFG_MAX, SHOT_IMAGE_CFG_STEP, SHOT_IMAGE_CFG_FALLBACK, clampShotImageCfg, resolveShotImageCfgDefault, extractDialogueOnlyFromPrompt, inferLanguageCodeFromProjectLanguage, buildVoicePromptWithEntityContext, buildEpisodeDisplayLabel
} from '../editorHelpers';

import { generateEntityFromText, generateEntityFromImage, generateEntityDerived } from '../../../services/api';
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
    updateEntity,
    deleteEntity,
    deleteAllEntities,
    generateImage,
    submitImageGenerationJob,
    getImageGenerationJobStatus,
    generateVideo,
    generateVoice,
    fetchAssets,
    deleteAsset, 
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
    analyzeAssetImage,
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

const toRenderableText = (value) => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return value.trim();
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    try {
        const serialized = JSON.stringify(value);
        return serialized === '{}' || serialized === '[]' ? '' : serialized;
    } catch {
        return '';
    }
};

const parseDependencyEntityId = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return '';

    const directIdMatch = raw.match(/^\d+$/);
    if (directIdMatch) return directIdMatch[0];

    const prefixedIdMatch = raw.match(/^(?:existing[_ \s]*id|entity[_ \s]*id|id)\s*[:#=]\s*(\d+)$/i);
    if (prefixedIdMatch) return String(prefixedIdMatch[1] || '').trim();

    return '';
};

const resolveDependencyEntity = (dependencyToken, entities) => {
    const rawToken = String(dependencyToken || '').trim();
    if (!rawToken) return null;

    const normalizedToken = normalizeEntityToken(rawToken);
    const resolvedEntityId = parseDependencyEntityId(rawToken);

    return (Array.isArray(entities) ? entities : []).find((entity) => {
        if (!entity) return false;

        const entityId = String(entity.id || '').trim();
        const entityName = normalizeEntityToken(entity.name || '');
        const entityNameEn = normalizeEntityToken(entity.name_en || '');

        if (resolvedEntityId && entityId && entityId === resolvedEntityId) return true;
        if (entityId && entityId === rawToken) return true;
        if (normalizedToken && entityName && entityName === normalizedToken) return true;
        if (normalizedToken && entityNameEn && entityNameEn === normalizedToken) return true;

        return false;
    }) || null;
};

export const SubjectLibrary = ({ projectId, project, currentEpisode, uiLang = 'zh', userBatchParallelLimit = 3, onImportText = null }) => {
    const SUBJECT_BATCH_RUNTIME_STORAGE_KEY = 'aistory.subjectBatchRuntime.v1';
    const IMAGE_JOB_CACHE_PURGE_VERSION = '20260324';
    const IMAGE_JOB_CACHE_PURGE_MARKER_KEY = `aistory.imageJobCachePurge.${IMAGE_JOB_CACHE_PURGE_VERSION}`;
    const SUBJECT_BATCH_RUNTIME_TTL_MS = 1000 * 60 * 60 * 6;
    const SUBJECT_BATCH_RUNTIME_STALE_MS = 1000 * 60 * 5;
    const SUBJECT_BATCH_WATCHDOG_INTERVAL_MS = 1000 * 5;
    const SUBJECT_IMAGE_JOB_OWNER_PAGE = 'subject-library';
    const SUBJECT_IMAGE_JOB_MAX_STATUS_FAILURES = 3;
    const SUBJECT_IMAGE_JOB_PERSIST_WAIT_MS = 1000 * 60 * 4;
    const SUBJECT_IMAGE_JOB_PERSIST_LOG_INTERVAL_MS = 1000 * 15;
    const functionApiConfigs = useFunctionApis();
    const createSubjectBatchTaskState = useCallback(() => ({
        running: false,
        progress: null,
        scopeKey: '',
        updatedAt: 0,
    }), []);

    const normalizeSubjectBatchTask = useCallback((rawTask) => {
        const now = Date.now();
        if (!rawTask || typeof rawTask !== 'object') {
            return createSubjectBatchTaskState();
        }

        const updatedAt = Number(rawTask.updatedAt || 0) || 0;
        if (updatedAt > 0 && (now - updatedAt) > SUBJECT_BATCH_RUNTIME_TTL_MS) {
            return createSubjectBatchTaskState();
        }

        return {
            running: Boolean(rawTask.running),
            progress: rawTask.progress && typeof rawTask.progress === 'object' ? rawTask.progress : null,
            scopeKey: String(rawTask.scopeKey || ''),
            updatedAt,
        };
    }, [createSubjectBatchTaskState]);

    const readSubjectBatchRuntimeStorage = useCallback(() => {
        try {
            const raw = localStorage.getItem(SUBJECT_BATCH_RUNTIME_STORAGE_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            return {
                generate: normalizeSubjectBatchTask(parsed.generate),
                analyze: normalizeSubjectBatchTask(parsed.analyze),
                reconstruct: normalizeSubjectBatchTask(parsed.reconstruct),
            };
        } catch {
            return null;
        }
    }, [normalizeSubjectBatchTask]);

    const writeSubjectBatchRuntimeStorage = useCallback((runtime) => {
        try {
            if (!runtime || typeof runtime !== 'object') {
                localStorage.removeItem(SUBJECT_BATCH_RUNTIME_STORAGE_KEY);
                return;
            }

            const payload = {
                generate: normalizeSubjectBatchTask(runtime.generate),
                analyze: normalizeSubjectBatchTask(runtime.analyze),
                reconstruct: normalizeSubjectBatchTask(runtime.reconstruct),
            };

            const hasRunning = Boolean(payload.generate.running || payload.analyze.running || payload.reconstruct.running);
            if (!hasRunning) {
                localStorage.removeItem(SUBJECT_BATCH_RUNTIME_STORAGE_KEY);
                return;
            }

            localStorage.setItem(SUBJECT_BATCH_RUNTIME_STORAGE_KEY, JSON.stringify(payload));
        } catch {
            // ignore storage failures
        }
    }, [normalizeSubjectBatchTask]);

    const persistedRuntime = readSubjectBatchRuntimeStorage();

    if (!window.__AISTORY_SUBJECT_BATCH_RUNTIME__) {
        window.__AISTORY_SUBJECT_BATCH_RUNTIME__ = {
            generate: persistedRuntime?.generate || createSubjectBatchTaskState(),
            analyze: persistedRuntime?.analyze || createSubjectBatchTaskState(),
            reconstruct: persistedRuntime?.reconstruct || createSubjectBatchTaskState(),
            listeners: new Set(),
        };
    }

    const subjectBatchRuntime = window.__AISTORY_SUBJECT_BATCH_RUNTIME__;
    const getSubjectBatchSnapshot = useCallback(() => ({
        generate: { ...subjectBatchRuntime.generate },
        analyze: { ...subjectBatchRuntime.analyze },
        reconstruct: { ...subjectBatchRuntime.reconstruct },
    }), [subjectBatchRuntime]);
    const emitSubjectBatchRuntime = useCallback(() => {
        writeSubjectBatchRuntimeStorage(subjectBatchRuntime);
        const snapshot = getSubjectBatchSnapshot();
        subjectBatchRuntime.listeners.forEach((listener) => {
            try {
                listener(snapshot);
            } catch {
                // ignore listener errors
            }
        });
    }, [getSubjectBatchSnapshot, subjectBatchRuntime, writeSubjectBatchRuntimeStorage]);
    const updateSubjectBatchTask = useCallback((task, patch) => {
        if (!subjectBatchRuntime[task]) return;
        subjectBatchRuntime[task] = {
            ...subjectBatchRuntime[task],
            ...(patch || {}),
            updatedAt: Date.now(),
        };
        emitSubjectBatchRuntime();
    }, [emitSubjectBatchRuntime, subjectBatchRuntime]);
    const subscribeSubjectBatchRuntime = useCallback((listener) => {
        subjectBatchRuntime.listeners.add(listener);
        return () => {
            subjectBatchRuntime.listeners.delete(listener);
        };
    }, [subjectBatchRuntime]);

    const { addLog: onLog } = useLog();
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);

    const subjectBatchScopeKey = String(projectId || '');
    const SUBJECT_BATCH_PARALLEL_LIMIT = userBatchParallelLimit;
    const isMountedRef = useRef(false);
    const [subTab, setSubTab] = useState('character');
    const [createMode, setCreateMode] = useState('manual');
    const [entityListLoading, setEntityListLoading] = useState(false);
    const [entities, setEntities] = useState([]);
    const [allEntities, setAllEntities] = useState([]); // Store ALL entities for cross-reference
    const [entityEpisodeScope, setEntityEpisodeScope] = useState(() => (currentEpisode?.id ? 'current' : 'all'));
    const [selectedEntity, setSelectedEntity] = useState(null);
    const [showImageModal, setShowImageModal] = useState(false);
    const [imageModalTab, setImageModalTab] = useState('library'); // library, upload, generate
    const [generating, setGenerating] = useState(false);
    const [uploadState, setUploadState] = useState('idle'); // idle, uploading, analyzing, completed
    const [prompt, setPrompt] = useState('');
    const [promptDrafts, setPromptDrafts] = useState({ cn: '', en: '' });
    const [promptSubmitLangPref, setPromptSubmitLangPref] = useState(() => getPromptSubmitLanguagePreference());
    const [tempPromptSubmitLang, setTempPromptSubmitLang] = useState('');
    const [showPromptLangMenu, setShowPromptLangMenu] = useState(false);
    const [refImage, setRefImage] = useState(null);
    const [isUploadingRef, setIsUploadingRef] = useState(false);
    const [refSelectionMode, setRefSelectionMode] = useState(null); // 'assets'
    const [assets, setAssets] = useState([]);
    const [assetsLoading, setAssetsLoading] = useState(false);
    const [assetKeyword, setAssetKeyword] = useState('');
    const [assetEpisodeFilter, setAssetEpisodeFilter] = useState('all');
    const [assetProjectFilter, setAssetProjectFilter] = useState('all');
    const [assetImageTypeFilter, setAssetImageTypeFilter] = useState('all');
    const [assetNameFilter, setAssetNameFilter] = useState('');
    const [includeHistoricalEpisodeAssets, setIncludeHistoricalEpisodeAssets] = useState(false);
    const [imageSelectAction, setImageSelectAction] = useState('direct_use');
    const [viewingEntity, setViewingEntity] = useState(null);
    const [historyList, setHistoryList] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [showHistoryModal, setShowHistoryModal] = useState(false);

    const handleLoadHistory = async (entityId) => {
        try {
            setHistoryLoading(true);
            setShowHistoryModal(true);
            setHistoryList([]);
            const url = `${API_URL}/entities/${entityId}/history`;
            const header = { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } };
            const f_resp = await fetch(url, header);
            if (!f_resp.ok) throw new Error(`HTTP error! status: ${f_resp.status}`);
            const resp = await f_resp.json();
            setHistoryList(Array.isArray(resp) ? resp : []);
        } catch (e) {
            console.error('Failed to load history', e);
            onLog?.('Failed to load history', 'error');
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleRestoreHistory = async (historyId) => {
        if (!confirm(t('确定要恢复到此历史版本吗？', 'Are you sure you want to restore this history version?'))) return;
        try {
            const url = `${API_URL}/entities/history/${historyId}/restore`;
            const header = { method: 'POST', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } };
            const resp = await fetch(url, header);
            if(resp.ok) {
                onLog?.('Restored history successfully', 'success');
                setShowHistoryModal(false);
                fetchEntities();
            } else {
                onLog?.('Failed to restore history', 'error');
            }
        } catch(e) {
            onLog?.(`Error restoring history: ${e}`, 'error');
        }
    };

    const handleSyncFromOld = async (oldId, newId) => {
        if (!confirm(t('将把源实体的当前状态覆盖到此实体，确定吗？', 'Warning: This will overwrite this entity with the source entity state. Continue?'))) return;
        try {
            const url = `${API_URL}/entities/sync`;
            const header = { 
                method: 'POST', 
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_entity_id: oldId, target_entity_id: newId })
            };
            const resp = await fetch(url, header);
            if(resp.ok) {
                onLog?.('Sync completed successfully', 'success');
                fetchEntities();
            } else {
                onLog?.('Sync failed', 'error');
            }
        } catch(e) {
            onLog?.(`Error syncing: ${e}`, 'error');
        }
    };

    const [viewingEntityTab, setViewingEntityTab] = useState('generate');
    const [entityMediaRefTab, setEntityMediaRefTab] = useState('video');
    const [entityMediaRefUploading, setEntityMediaRefUploading] = useState(false);
    const [entityRefAudioPrompt, setEntityRefAudioPrompt] = useState('');
    const [isGeneratingEntityRefAudio, setIsGeneratingEntityRefAudio] = useState(false);
    const [entityRefAudioPromptByEntity, setEntityRefAudioPromptByEntity] = useState({});
    const [entityRefAudioProfileByEntity, setEntityRefAudioProfileByEntity] = useState({});
    const [entityRefAudioTone, setEntityRefAudioTone] = useState('');
    const [entityRefAudioPace, setEntityRefAudioPace] = useState('');
    const [entityRefAudioEmotion, setEntityRefAudioEmotion] = useState('');
    const [entityRefAudioFunctionByTab, setEntityRefAudioFunctionByTab] = useState({
        video: 'generate_entity_reference_audio_video',
        audio: 'generate_entity_reference_audio_audio',
    });
    const [advancedInstruction, setAdvancedInstruction] = useState('');
    const [isAdvancedOptimizing, setIsAdvancedOptimizing] = useState(false);

    const ENTITY_REF_AUDIO_TONE_OPTIONS = useMemo(() => ([
        { value: '中高音（清晰明亮）', label: t('中高音（清晰明亮）', 'Mid-high (clear and bright)') },
        { value: '中音（自然平衡）', label: t('中音（自然平衡）', 'Mid (natural and balanced)') },
        { value: '中低音（沉稳克制）', label: t('中低音（沉稳克制）', 'Mid-low (calm and restrained)') },
    ]), [t]);

    const ENTITY_REF_AUDIO_PACE_OPTIONS = useMemo(() => ([
        { value: '慢速（0.85x）', label: t('慢速（0.85x）', 'Slow (0.85x)') },
        { value: '中速偏慢（0.9x）', label: t('中速偏慢（0.9x）', 'Medium-slow (0.9x)') },
        { value: '中速（1.0x）', label: t('中速（1.0x）', 'Medium (1.0x)') },
    ]), [t]);

    const ENTITY_REF_AUDIO_EMOTION_OPTIONS = useMemo(() => ([
        { value: '克制、安抚、轻微紧张', label: t('克制、安抚、轻微紧张', 'Restrained, reassuring, slightly tense') },
        { value: '温柔、坚定、可信赖', label: t('温柔、坚定、可信赖', 'Warm, steady, trustworthy') },
        { value: '冷静、果断、低压感', label: t('冷静、果断、低压感', 'Calm, decisive, low-pressure') },
    ]), [t]);

    const resolveDefaultEntityRefAudioProfile = useCallback((entity) => {
        const normalizedGender = String(entity?.gender || '').trim().toLowerCase();
        const isMale = ['male', 'man', 'boy', 'masculine', 'm', '男', '男性'].some((token) => normalizedGender.includes(token));
        return {
            tone: isMale ? '中低音（沉稳克制）' : '中高音（清晰明亮）',
            pace: '中速偏慢（0.9x）',
            emotion: '克制、安抚、轻微紧张',
        };
    }, []);

    const buildDefaultEntityRefAudioPrompt = useCallback((entity, profileOverrides = null) => {
        const normalizedGender = String(entity?.gender || '').trim().toLowerCase();
        const isMale = ['male', 'man', 'boy', 'masculine', 'm', '男', '男性'].some((token) => normalizedGender.includes(token));
        const genderCn = isMale ? '男' : '女';
        const genderEn = isMale ? 'male' : 'female';

        const defaultProfile = resolveDefaultEntityRefAudioProfile(entity);
        const activeProfile = {
            tone: String(profileOverrides?.tone || '').trim() || defaultProfile.tone,
            pace: String(profileOverrides?.pace || '').trim() || defaultProfile.pace,
            emotion: String(profileOverrides?.emotion || '').trim() || defaultProfile.emotion,
        };

        const ageRaw = String(entity?.age || entity?.age_group || entity?.ageRange || '').trim();
        const ageCn = ageRaw || (isMale ? '28岁' : '25岁');
        const ageEn = ageRaw || (isMale ? '28 years old' : '25 years old');

        const identityRaw = String(entity?.role || entity?.archetype || entity?.type || '').trim();
        const identityCn = identityRaw || (isMale ? '守夜人' : '巡夜人');
        const identityEn = identityRaw || (isMale ? 'night watchman' : 'night patrol officer');

        const pitchCn = activeProfile.tone;
        const pitchEn = activeProfile.tone;
        const paceCn = activeProfile.pace;
        const paceEn = activeProfile.pace;
        const emotionCn = activeProfile.emotion;
        const emotionEn = activeProfile.emotion;
        const sampleTextCn = isMale
            ? '夜色渐深，他把门向里关上，压低声音说：“别怕，我在这里。”'
            : '夜色渐深，她把门向里关上，压低声音说：“别怕，我在这里。”';
        const sampleTextEn = isMale
            ? 'As night falls, he closes the door inward and says in a low voice: "Do not be afraid, I am here."'
            : 'As night falls, she closes the door inward and says in a low voice: "Do not be afraid, I am here."';

        return t(
            `【配音设定】\n- 性别：${genderCn}\n- 年龄：${ageCn}\n- 身份：${identityCn}\n- 音调：${pitchCn}\n- 语速：中速偏慢（约0.9x）\n- 情绪：克制、安抚、带轻微紧张\n- 断句与重音：在“别怕”和“我在这里”前各停顿0.2秒并轻微重读\n- 发音：咬字清晰，口气自然，不夸张\n\n【示例台词】\n${sampleTextCn}`,
            `【配音设定】\n- 性别：${genderCn}\n- 年龄：${ageCn}\n- 身份：${identityCn}\n- 音调：${pitchCn}\n- 语速：${paceCn}\n- 情绪：${emotionCn}\n- 断句与重音：在“别怕”和“我在这里”前各停顿0.2秒并轻微重读\n- 发音：咬字清晰，口气自然，不夸张\n\n【示例台词】\n${sampleTextCn}`,
            `[Voice Direction]\n- Gender: ${genderEn}\n- Age: ${ageEn}\n- Identity: ${identityEn}\n- Pitch: ${pitchEn}\n- Pace: ${paceEn}\n- Emotion: ${emotionEn}\n- Pauses and emphasis: pause 0.2s before "Do not be afraid" and "I am here", with gentle emphasis\n- Pronunciation: clear articulation, natural delivery, no exaggeration\n\n[Sample Line]\n${sampleTextEn}`
        );
    }, [resolveDefaultEntityRefAudioProfile, t]);

    const ENTITY_REF_AUDIO_FUNCTION_OPTIONS = useMemo(() => ([
        { value: 'generate_entity_reference_audio_video', label: t('视频页路由', 'Video-tab Route') },
        { value: 'generate_entity_reference_audio_audio', label: t('音频页路由', 'Audio-tab Route') },
        { value: 'generate_entity_reference_audio', label: t('兼容路由', 'Legacy Route') },
    ]), [t]);

    const entityRefAudioPromptStorageKey = useMemo(() => {
        const pid = String(projectId || '').trim();
        return pid ? `aistory.entityRefAudioPromptByEntity.${pid}` : 'aistory.entityRefAudioPromptByEntity.global';
    }, [projectId]);

    const entityRefAudioFunctionStorageKey = useMemo(() => {
        const pid = String(projectId || '').trim();
        return pid ? `aistory.entityRefAudioFunctionByTab.${pid}` : 'aistory.entityRefAudioFunctionByTab.global';
    }, [projectId]);

    const entityRefAudioProfileStorageKey = useMemo(() => {
        const pid = String(projectId || '').trim();
        return pid ? `aistory.entityRefAudioProfileByEntity.${pid}` : 'aistory.entityRefAudioProfileByEntity.global';
    }, [projectId]);

    useEffect(() => {
        try {
            const raw = localStorage.getItem(entityRefAudioPromptStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                setEntityRefAudioPromptByEntity(parsed);
            }
        } catch {}
    }, [entityRefAudioPromptStorageKey]);

    useEffect(() => {
        try {
            const cleaned = Object.fromEntries(
                Object.entries(entityRefAudioPromptByEntity || {}).filter(([k, v]) => String(k || '').trim() && String(v || '').trim())
            );
            if (Object.keys(cleaned).length === 0) {
                localStorage.removeItem(entityRefAudioPromptStorageKey);
            } else {
                localStorage.setItem(entityRefAudioPromptStorageKey, JSON.stringify(cleaned));
            }
        } catch {}
    }, [entityRefAudioPromptByEntity, entityRefAudioPromptStorageKey]);

    useEffect(() => {
        try {
            const raw = localStorage.getItem(entityRefAudioProfileStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                setEntityRefAudioProfileByEntity(parsed);
            }
        } catch {}
    }, [entityRefAudioProfileStorageKey]);

    useEffect(() => {
        try {
            const cleaned = Object.fromEntries(
                Object.entries(entityRefAudioProfileByEntity || {}).filter(([k, v]) => String(k || '').trim() && v && typeof v === 'object')
            );
            if (Object.keys(cleaned).length === 0) {
                localStorage.removeItem(entityRefAudioProfileStorageKey);
            } else {
                localStorage.setItem(entityRefAudioProfileStorageKey, JSON.stringify(cleaned));
            }
        } catch {}
    }, [entityRefAudioProfileByEntity, entityRefAudioProfileStorageKey]);

    useEffect(() => {
        try {
            const raw = localStorage.getItem(entityRefAudioFunctionStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                setEntityRefAudioFunctionByTab((prev) => ({
                    ...prev,
                    ...(String(parsed.video || '').trim() ? { video: String(parsed.video).trim() } : {}),
                    ...(String(parsed.audio || '').trim() ? { audio: String(parsed.audio).trim() } : {}),
                }));
            }
        } catch {}
    }, [entityRefAudioFunctionStorageKey]);

    useEffect(() => {
        try {
            localStorage.setItem(entityRefAudioFunctionStorageKey, JSON.stringify({
                video: String(entityRefAudioFunctionByTab?.video || 'generate_entity_reference_audio_video').trim(),
                audio: String(entityRefAudioFunctionByTab?.audio || 'generate_entity_reference_audio_audio').trim(),
            }));
        } catch {}
    }, [entityRefAudioFunctionByTab, entityRefAudioFunctionStorageKey]);

    useEffect(() => {
        const currentEntityKey = String(viewingEntity?.id || '').trim();
        if (!currentEntityKey) {
            setEntityRefAudioPrompt('');
            setEntityRefAudioTone('');
            setEntityRefAudioPace('');
            setEntityRefAudioEmotion('');
            return;
        }
        const defaultProfile = resolveDefaultEntityRefAudioProfile(viewingEntity);
        const savedProfile = entityRefAudioProfileByEntity?.[currentEntityKey] || {};
        const activeProfile = {
            tone: String(savedProfile?.tone || '').trim() || defaultProfile.tone,
            pace: String(savedProfile?.pace || '').trim() || defaultProfile.pace,
            emotion: String(savedProfile?.emotion || '').trim() || defaultProfile.emotion,
        };
        setEntityRefAudioTone(activeProfile.tone);
        setEntityRefAudioPace(activeProfile.pace);
        setEntityRefAudioEmotion(activeProfile.emotion);
        const saved = String(entityRefAudioPromptByEntity?.[currentEntityKey] || '').trim();
        setEntityRefAudioPrompt(saved || buildDefaultEntityRefAudioPrompt(viewingEntity, activeProfile));
    }, [buildDefaultEntityRefAudioPrompt, entityRefAudioProfileByEntity, entityRefAudioPromptByEntity, resolveDefaultEntityRefAudioProfile, viewingEntity]);
    
    // Analyzing state mapping (entityId -> timestamp)
    const subjectAnalyzingStorageKey = useMemo(() => {
        const pid = String(projectId || '').trim();
        return pid ? `aistory.analyzingEntities.${pid}` : '';
    }, [projectId]);
    const [analyzingEntities, setAnalyzingEntities] = useState({});

    useEffect(() => {
        if (!subjectAnalyzingStorageKey) return;
        try {
            const raw = localStorage.getItem(subjectAnalyzingStorageKey);
            if (raw) setAnalyzingEntities(JSON.parse(raw));
        } catch { }
    }, [subjectAnalyzingStorageKey]);

    const persistAnalyzingEntities = useCallback((nextState) => {
        setAnalyzingEntities(nextState);
        if (!subjectAnalyzingStorageKey) return;
        try {
            if (Object.keys(nextState).length === 0) {
                localStorage.removeItem(subjectAnalyzingStorageKey);
            } else {
                localStorage.setItem(subjectAnalyzingStorageKey, JSON.stringify(nextState));
            }
        } catch { }
    }, [subjectAnalyzingStorageKey]);

    const analyzingEntitiesRef = useRef(analyzingEntities);
    useEffect(() => {
        analyzingEntitiesRef.current = analyzingEntities;
    }, [analyzingEntities]);

    const getEntityAnalysisTime = (entity) => {
        try {
            const attrs = entity?.custom_attributes ? (typeof entity.custom_attributes === 'string' ? JSON.parse(entity.custom_attributes) : entity.custom_attributes) : {};
            if (attrs?.analysis_result?.status === 'error') {
                return 'ERROR_' + (attrs?.analysis_result?.timestamp || Date.now()); // Ensure mismatch so it gets picked up
            }
            return attrs?.analysis_result?.timestamp || '';
        } catch {
            return '';
        }
    };

    useEffect(() => {
        const checkPoll = async () => {
            const currentAnalyzing = analyzingEntitiesRef.current;
            const analyzingIds = Object.keys(currentAnalyzing);
            if (analyzingIds.length === 0) return;

            try {
                const latestEntities = await fetchEntities(projectId, { include_project_null_episode: true });
                let changed = false;
                const updatesToApply = [];
                setAnalyzingEntities(prev => {
                    const next = { ...prev };
                    analyzingIds.forEach(id => {
                        const latest = latestEntities.find(e => String(e.id) === id);
                        const trackingData = next[id];
                        if (!trackingData) return;

                        const initialAnalysisTime = trackingData?.initialAnalysisTime;
                        const startedAt = trackingData?.startedAt || Date.now();

                        // If entity no longer exists, timeout 45s passed, or if analysis time changed
                        if (!latest) {
                            delete next[id];
                            changed = true;
                        } else if (getEntityAnalysisTime(latest) !== initialAnalysisTime) {
                            delete next[id];
                            changed = true;
                            updatesToApply.push({ id, latest });
                        } else if (Date.now() - startedAt > 300000) {
                            // Timeout safety catch (5 minutes)
                            delete next[id];
                            changed = true;
                            if (onLog) onLog(`Subject analysis timed out for ${latest.name}`, "warning");
                        }
                    });

                    if (changed && subjectAnalyzingStorageKey) {
                        try {
                            if (Object.keys(next).length === 0) localStorage.removeItem(subjectAnalyzingStorageKey);
                            else localStorage.setItem(subjectAnalyzingStorageKey, JSON.stringify(next));
                        } catch {}
                    }
                    return changed ? next : prev;
                });
                
                updatesToApply.forEach(({ id, latest }) => {
                    let isError = false;
                    let errMsg = "Unknown error";
                    try {
                        const attrs = typeof latest.custom_attributes === 'string' ? JSON.parse(latest.custom_attributes) : (latest.custom_attributes || {});
                        if (attrs?.analysis_result?.status === 'error') {
                            isError = true;
                            errMsg = attrs?.analysis_result?.message || errMsg;
                        }
                    } catch(e) {}
                    
                    setSelectedEntity(curr => String(curr?.id) === id ? latest : curr);
                    setAllEntities(curr => curr.map(e => String(e.id) === id ? latest : e));
                    setEntities(curr => curr.map(e => String(e.id) === id ? latest : e));
                    setViewingEntity(curr => String(curr?.id) === id ? latest : curr);
                    
                    if (isError) {
                        if (onLog) onLog(`Subject analysis failed for ${latest.name}: ${errMsg}`, "error");
                        showSubjectNotification(`Subject analysis failed for ${latest.name}: ${errMsg}`, "error");
                    } else {
                        if (onLog) onLog(`Subject analysis completed in background: ${latest.name}`, "success");
                    }
                });
            } catch (e) { console.error(e); }
        };

        const timer = setInterval(() => { void checkPoll(); }, 4000);
        return () => clearInterval(timer);
    }, [projectId, fetchEntities, subjectAnalyzingStorageKey, onLog]);
    const [isAdvancedLocalModifying, setIsAdvancedLocalModifying] = useState(false);
    const [isBatchGeneratingEntities, setIsBatchGeneratingEntities] = useState(false);
    const [isStoppingBatchGenerateEntities, setIsStoppingBatchGenerateEntities] = useState(false);
    const [batchEntityProgress, setBatchEntityProgress] = useState(null);
    const [isBatchAnalyzingEntities, setIsBatchAnalyzingEntities] = useState(false);
    const [batchAnalyzeProgress, setBatchAnalyzeProgress] = useState(null);
    const [isBatchReconstructingEntities, setIsBatchReconstructingEntities] = useState(false);
    const [batchReconstructProgress, setBatchReconstructProgress] = useState(null);
    const [isReconstructingEntity, setIsReconstructingEntity] = useState(false);
    const [reconstructProgress, setReconstructProgress] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });
    const [subjectNotification, setSubjectNotification] = useState(null);
    const [subjectImageJobs, setSubjectImageJobs] = useState({});
    const [stoppingSubjectImageJobs, setStoppingSubjectImageJobs] = useState({});
    const [subjectGenerationHistory, setSubjectGenerationHistory] = useState([]);
    const [subjectGenerationHistoryLoading, setSubjectGenerationHistoryLoading] = useState(false);
    const [subjectGenerationHistoryDeletingId, setSubjectGenerationHistoryDeletingId] = useState('');
    const [showAiEntityCreateModal, setShowAiEntityCreateModal] = useState(false);
    const [isGeneratingRow, setIsGeneratingRow] = useState(false);
    const [isAiEntityCreating, setIsAiEntityCreating] = useState(false);
    const [aiEntityCreateReport, setAiEntityCreateReport] = useState(null);
    const [aiReuseEntityTypeFilter, setAiReuseEntityTypeFilter] = useState('all');
    const [isAiUploadAnalyzing, setIsAiUploadAnalyzing] = useState(false);
    const [aiUploadedAsset, setAiUploadedAsset] = useState(null);
    const [aiUploadedAssetAnalysis, setAiUploadedAssetAnalysis] = useState('');
    const [aiEntityCreateForm, setAiEntityCreateForm] = useState({
        type: 'character',
        name: '',
        nameEn: '',
        attributes: '',
        reuseEntityIds: [],
    });
    const subjectImageJobsRef = useRef({});
    const subjectHistoryJobPresenceRef = useRef({});
    const subjectImageJobPollingRef = useRef(false);
    const subjectImageJobPollTokenRef = useRef(0);
    const subjectImageJobTerminalLogRef = useRef(new Set());
    const subjectBatchGenerateStopRequestedRef = useRef(false);
    const subjectBatchGenerateSessionRef = useRef('');
    const subjectBatchGenerateActiveJobsRef = useRef(new Map());
    const subjectBatchAnalyzeStopRequestedRef = useRef(false);
    const subjectBatchAnalyzeSessionRef = useRef('');
    const subjectBatchReconstructStopRequestedRef = useRef(false);
    const subjectBatchReconstructSessionRef = useRef('');
    const subjectBatchReconstructActiveJobsRef = useRef(new Map());

    const normalizeAiEntityType = useCallback((rawType) => {
        const stable = String(rawType || '').trim().toLowerCase();
        if (stable.includes('char') || stable === '角色') return 'character';
        if (stable.includes('env') || stable.includes('scene') || stable === '环境') return 'environment';
        if (stable.includes('prop') || stable === '道具') return 'prop';
        if (stable.includes('poster') || stable.includes('cover') || stable === '海报' || stable === '封面') return 'poster';
        return 'character';
    }, []);

    const fetchEntityDesignSystemPrompt = useCallback(async (entityType) => {
        const stableType = normalizeAiEntityType(entityType);
        const typePromptPath = stableType === 'prop'
            ? 'skills/scene_analysis_feature_stack/entity_design_prop.md'
            : stableType === 'environment'
                ? 'skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md'
                : stableType === 'poster'
                    ? 'skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md'
                    : 'skills/scene_analysis_feature_stack/entity_design_character.md';
        const [commonPromptRes, typePromptRes] = await Promise.all([
            fetchPrompt('skills/scene_analysis_feature_stack/entity_design_common.md').catch(() => null),
            fetchPrompt(typePromptPath).catch(() => null),
        ]);
        return [commonPromptRes?.content, typePromptRes?.content]
            .map((value) => String(value || '').trim())
            .filter(Boolean)
            .join('\n\n');
    }, [normalizeAiEntityType]);

    const getAiEntityTypePromptHint = useCallback((entityType) => {
        const stableType = normalizeAiEntityType(entityType);
        if (stableType === 'character') {
            return t(
                '建议输入：角色定位、年龄区间、外形特征、服装元素、身份职业、情绪气质、动作特征、与其他角色关系。',
                'Suggestions: role positioning, age range, visual traits, costume elements, identity/profession, mood/temperament, action characteristics, and relationship to other characters.'
            );
        }
        if (stableType === 'prop') {
            return t(
                '建议输入：道具材质、尺寸、年代风格、磨损状态、关键用途、交互方式、危险等级或功能限制。',
                'Suggestions: prop material, scale, period style, wear condition, key usage, interaction style, and risk/function constraints.'
            );
        }
        if (stableType === 'environment') {
            return t(
                '建议输入：空间类型、场景时间、主色温、光照氛围、建筑/陈设风格、可拍摄机位特征、与剧情关系。',
                'Suggestions: space type, scene time, color temperature, lighting mood, architecture/decor style, camera-friendly characteristics, and narrative relationship.'
            );
        }
        return t(
            '建议输入：海报构图重点、主体阵列、视觉风格关键词、文案语气、版式密度、品牌或作品辨识元素。',
            'Suggestions: poster composition focus, subject arrangement, visual style keywords, copy tone, layout density, and branding/story identity elements.'
        );
    }, [normalizeAiEntityType, t]);

    const buildEntityIndexToken = useCallback((entityType, entityName) => {
        const stableType = normalizeAiEntityType(entityType);
        const stableName = String(entityName || '').trim();
        if (!stableName) return '';
        if (stableType === 'character') return `CHAR:[@${stableName}]`;
        if (stableType === 'environment') return `ENV:[${stableName}]`;
        if (stableType === 'prop') return `PROP:[${stableName}]`;
        return `COVER:[${stableName}]`;
    }, [normalizeAiEntityType]);

    const isAiReuseEntityAllowed = useCallback((targetType, candidateType) => {
        const stableTarget = normalizeAiEntityType(targetType);
        const stableCandidate = normalizeAiEntityType(candidateType);
        if (stableTarget === 'poster') return true;
        return stableTarget === stableCandidate;
    }, [normalizeAiEntityType]);

    const buildManualSubjectIndexInput = useCallback((formState) => {
        const stableType = normalizeAiEntityType(formState?.type);
        const stableName = String(formState?.name || '').trim();
        const stableNameEn = String(formState?.nameEn || '').trim();
        const stableAttributes = String(formState?.attributes || '').trim();
        const subjectToken = buildEntityIndexToken(stableType, stableName || stableNameEn || 'Unnamed Subject');

        const selectedRefs = (Array.isArray(formState?.reuseEntityIds) ? formState.reuseEntityIds : [])
            .map((id) => (allEntities || []).find((entity) => String(entity?.id || '') === String(id || '')))
            .filter((entity) => isAiReuseEntityAllowed(stableType, entity?.type))
            .filter(Boolean)
            .map((entity) => {
                const primary = buildEntityIndexToken(entity.type, entity.name || entity.name_en || String(entity.id));
                const secondary = entity.name_en || entity.name || '';
                return secondary && secondary.toLowerCase() !== String(entity.name || '').toLowerCase() 
                    ? `${primary} (${secondary})` 
                    : primary;
            });

        const lines = [
            'Subject Index (Manual Asset Addition Request)',
            '---',
            `[Target Type] ${stableType}`,
            `[Target Subject] ${subjectToken}`,
            stableNameEn ? `[Target Subject EN] ${stableNameEn}` : '',
            '[Entity Attributes]',
            stableAttributes,
            '[Action Characteristics]',
            stableAttributes,
            '[Existing Subjects For Reuse (Optional)]',
            selectedRefs.length > 0 ? selectedRefs.map((line, idx) => `${idx + 1}. ${line}`).join('\n') : '(none)',
            '---',
            'Please return only import-ready SUBJECTS_JSON with keys: characters, props, environments, covers, posters.',
        ].filter(Boolean);

        return lines.join('\n');
    }, [allEntities, buildEntityIndexToken, isAiReuseEntityAllowed, normalizeAiEntityType]);

    const importSubjectsJsonDirectly = useCallback(async (subjectsJson) => {
        const payload = (subjectsJson && typeof subjectsJson === 'object') ? subjectsJson : {};
        const sectionToType = {
            characters: 'character',
            props: 'prop',
            environments: 'environment',
            covers: 'poster',
            posters: 'poster',
        };
        const normalizeImportEntityKey = (type, rawName) => {
            const stableType = String(type || '').trim().toLowerCase();
            const stableName = String(rawName || '').trim().toLowerCase();
            if (!stableType || !stableName) return '';
            return `${stableType}::${stableName}`;
        };
        const existingEntityMap = new Map();
        for (const entity of (allEntities || [])) {
            const stableType = String(entity?.type || '').trim().toLowerCase();
            if (!stableType) continue;
            const keyA = normalizeImportEntityKey(stableType, entity?.name);
            const keyB = normalizeImportEntityKey(stableType, entity?.name_en);
            if (keyA) existingEntityMap.set(keyA, entity);
            if (keyB) existingEntityMap.set(keyB, entity);
        }
        const existingNameKeySet = new Set(existingEntityMap.keys());

        const importedSubjectCounts = { character: 0, prop: 0, environment: 0, poster: 0 };
        const createdSubjectItems = [];
        const skippedSubjectItems = [];

        for (const [section, entityType] of Object.entries(sectionToType)) {
            const rows = Array.isArray(payload?.[section]) ? payload[section] : [];
            for (const row of rows) {
                const name = String(row?.name || row?.name_cn || row?.label || '').trim();
                const nameEn = String(row?.name_en || '').trim();
                if (!name && !nameEn) continue;
                const keyA = normalizeImportEntityKey(entityType, name);
                const keyB = normalizeImportEntityKey(entityType, nameEn);
                if ((keyA && existingNameKeySet.has(keyA)) || (keyB && existingNameKeySet.has(keyB))) {
                    const reusedEntity = (keyA && existingEntityMap.get(keyA)) || (keyB && existingEntityMap.get(keyB)) || null;
                    // If matched entity belongs to this episode or is project-global without episodes, skip.
                    // But if it belongs to a previous/different episode, we CLONE it instead of skipping so Sync works!
                    if (reusedEntity && currentEpisode?.id && reusedEntity.episode_id !== currentEpisode.id) {
                        row.old_id = reusedEntity.id;
                        row.description_cn = row.description_cn || reusedEntity.description_cn || reusedEntity.description || '';
                        row.base_name_en = row.base_name_en || reusedEntity.base_name_en || reusedEntity.name_en || '';
                        row.role = row.role || reusedEntity.role || '';
                        row.archetype = row.archetype || reusedEntity.archetype || reusedEntity.action_characteristics || '';
                        row.gender = row.gender || reusedEntity.gender || '';
                        row.appearance_cn = row.appearance_cn || reusedEntity.appearance_cn || '';
                        row.clothing = row.clothing || reusedEntity.clothing || '';
                        row.atmosphere = row.atmosphere || reusedEntity.atmosphere || '';
                        row.visual_params = row.visual_params || reusedEntity.visual_params || '';
                        row.narrative_description = row.narrative_description || reusedEntity.narrative_description || '';
                        // proceed to create
                    } else {
                        skippedSubjectItems.push({
                            type: entityType,
                            name: name || nameEn,
                            reason: 'exists',
                            reusedEntityId: reusedEntity?.id || null,
                            reusedEntityName: reusedEntity?.name || reusedEntity?.name_en || null,
                            reusedImageUrl: reusedEntity?.image_url || null,
                            reusedDependencyPolicy: 'current_project_asset_or_latest_episode',
                        });
                        continue;
                    }
                }

                const payloadRow = {
                    name: name || nameEn,
                    name_en: nameEn || undefined,
                    base_name_en: String(row?.base_name_en || '').trim() || nameEn || undefined,
                    type: entityType,
                    episode_id: currentEpisode?.id || undefined,
                    description: String(row?.description_cn || row?.description || row?.entity_attributes || '').trim(),
                    role: String(row?.role || '').trim() || undefined,
                    archetype: String(row?.archetype || row?.action_characteristics || '').trim() || undefined,
                    gender: String(row?.gender || '').trim() || undefined,
                    appearance_cn: String(row?.appearance_cn || '').trim() || undefined,
                    clothing: String(row?.clothing || '').trim() || undefined,
                    action_characteristics: String(row?.action_characteristics || row?.archetype || '').trim() || undefined,
                    atmosphere: String(row?.atmosphere || '').trim() || undefined,
                    visual_params: String(row?.visual_params || '').trim() || undefined,
                    narrative_description: String(row?.narrative_description || '').trim() || undefined,
                    custom_attributes: {
                        source: 'subject_library_manual_entity_design',
                        ...(row?.id || row?.old_id ? { cloned_from_entity_id: parseInt(row.id || row.old_id) || undefined } : {})
                    },
                };

                const created = await createEntity(projectId, payloadRow);
                createdSubjectItems.push(created);
                importedSubjectCounts[entityType] += 1;
                if (keyA) existingNameKeySet.add(keyA);
                if (keyB) existingNameKeySet.add(keyB);
            }
        }

        return { importedSubjectCounts, createdSubjectItems, skippedSubjectItems };
    }, [allEntities, currentEpisode?.id, projectId]);

    const formatAiEntityCreateReport = useCallback((importReport) => {
        const imported = importReport?.importedSubjectCounts || {};
        const createdSubjectItems = Array.isArray(importReport?.createdSubjectItems) ? importReport.createdSubjectItems : [];
        const skippedSubjectItems = Array.isArray(importReport?.skippedSubjectItems) ? importReport.skippedSubjectItems : [];

        const byType = {
            character: Number(imported.character || 0),
            prop: Number(imported.prop || 0),
            environment: Number(imported.environment || 0),
            poster: Number(imported.poster || 0),
        };
        const importedTotal = byType.character + byType.prop + byType.environment + byType.poster;

        const skippedReasonStats = skippedSubjectItems.reduce((acc, item) => {
            const reason = String(item?.reason || 'unknown').trim().toLowerCase();
            acc[reason] = (acc[reason] || 0) + 1;
            return acc;
        }, {});

        const reasonLabel = (reason) => {
            if (reason === 'exists') return t('已存在实体，复用跳过', 'Already exists, reused and skipped');
            if (reason === 'unknown') return t('未知原因', 'Unknown reason');
            return reason;
        };

        const skippedReasonLines = Object.entries(skippedReasonStats)
            .map(([reason, count]) => `- ${reasonLabel(reason)}: ${count}`);

        const skippedItemPreview = skippedSubjectItems
            .slice(0, 12)
            .map((item, idx) => {
                const itemType = String(item?.type || '').trim() || 'unknown';
                const itemName = String(item?.name || '').trim() || 'unnamed';
                const itemReason = reasonLabel(String(item?.reason || 'unknown').trim().toLowerCase());
                const reusedTarget = String(item?.reusedEntityName || '').trim() || (item?.reusedEntityId ? `#${item.reusedEntityId}` : '');
                const reusedLine = reusedTarget
                    ? t(` -> 复用依赖: ${reusedTarget}`, ` -> reused dependency: ${reusedTarget}`)
                    : '';
                return `${idx + 1}. [${itemType}] ${itemName} (${itemReason})${reusedLine}`;
            });

        const createdPreview = createdSubjectItems
            .slice(0, 12)
            .map((item, idx) => `${idx + 1}. [${String(item?.type || '').trim() || 'unknown'}] ${String(item?.name || item?.name_en || item?.id || '').trim()}`);

        const summary = t(
            `AI 新增实体完成：新增 ${importedTotal}，跳过 ${skippedSubjectItems.length}。`,
            `AI entity creation completed: imported ${importedTotal}, skipped ${skippedSubjectItems.length}.`
        );

        const details = [
            summary,
            '',
            t('导入统计：', 'Import counts:'),
            `- ${t('角色', 'character')}: ${byType.character}`,
            `- ${t('道具', 'prop')}: ${byType.prop}`,
            `- ${t('环境', 'environment')}: ${byType.environment}`,
            `- ${t('海报', 'poster')}: ${byType.poster}`,
            '',
            t('跳过原因统计：', 'Skipped reason counts:'),
            ...(skippedReasonLines.length > 0 ? skippedReasonLines : [`- ${t('无', 'none')}`]),
            '',
            t('新增条目（最多12条）：', 'Created items (up to 12):'),
            ...(createdPreview.length > 0 ? createdPreview : [`- ${t('无', 'none')}`]),
            '',
            t('跳过条目（最多12条）：', 'Skipped items (up to 12):'),
            ...(skippedItemPreview.length > 0 ? skippedItemPreview : [`- ${t('无', 'none')}`]),
        ].join('\n');

        return { summary, details };
    }, [t]);
    const subjectImageJobStorageKey = useMemo(() => {
        const pid = String(projectId || '').trim();
        return pid ? `aistory.subjectImageJobs.${pid}` : '';
    }, [projectId]);
    const SUBJECT_IMAGE_JOB_TTL_MS = 1000 * 60 * 60 * 6;
    const SUBJECT_IMAGE_JOB_MAX_RUNNING_MS = 1000 * 60 * 20;

    const isEphemeralProviderMediaUrl = useCallback((url) => {
        const rawUrl = String(url || '').trim();
        if (!rawUrl) return false;
        try {
            const parsed = new URL(rawUrl, window.location.origin);
            return /^file\d*\.aitohumanize\.com$/i.test(String(parsed.hostname || '').trim());
        } catch {
            return false;
        }
    }, []);

    const getTempMediaFilenameFromUrl = useCallback((url) => {
        const rawUrl = String(url || '').trim();
        if (!rawUrl) return '';
        try {
            const parsed = new URL(rawUrl, window.location.origin);
            const pathname = String(parsed.pathname || '').trim();
            if (!pathname) return '';
            const parts = pathname.split('/').filter(Boolean);
            return String(parts[parts.length - 1] || '').trim();
        } catch {
            return '';
        }
    }, []);

    const buildSubjectJobMeta = useCallback((entityId, jobKind = 'generate', base = {}) => ({
        ownerPage: SUBJECT_IMAGE_JOB_OWNER_PAGE,
        ownerScopeType: 'project',
        ownerScopeId: String(projectId || '').trim(),
        ownerEntityId: String(entityId || '').trim(),
        jobKind: jobKind === 'reconstruct' ? 'reconstruct' : 'generate',
        previousStableImageUrl: String(base?.previousStableImageUrl || '').trim(),
        statusFailureCount: Math.max(0, Number(base?.statusFailureCount || 0) || 0),
        lastStatusError: String(base?.lastStatusError || '').trim(),
        lastPolledAt: Number(base?.lastPolledAt || 0) || 0,
        persistWaitStartedAt: Number(base?.persistWaitStartedAt || 0) || 0,
        lastPersistWaitLogAt: Number(base?.lastPersistWaitLogAt || 0) || 0,
    }), [projectId]);

    const describeSubjectJobOwner = useCallback((payload, entityId) => {
        const stableEntityId = String(payload?.ownerEntityId || entityId || '').trim() || 'unknown-entity';
        const stableScopeId = String(payload?.ownerScopeId || projectId || '').trim() || 'unknown-project';
        const stableJobKind = payload?.jobKind === 'reconstruct' ? 'reconstruct' : 'generate';
        return `subject-library/project:${stableScopeId}/entity:${stableEntityId}/${stableJobKind}`;
    }, [projectId]);

    const extractSubjectHistoryField = useCallback((item, fieldName) => {
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

    const normalizeSubjectGenerationHistory = useCallback((items) => {
        const list = Array.isArray(items) ? items : [];
        return list
            .map((item) => {
                const result = item?.result;
                const resultUrl = typeof result === 'string'
                    ? String(result).trim()
                    : String(result?.url || result?.result_url || result?.image_url || '').trim();
                const jobKind = String(extractSubjectHistoryField(item, 'jobKind') || '').trim().toLowerCase();
                return {
                    ...item,
                    entityId: String(extractSubjectHistoryField(item, 'entity_id') || extractSubjectHistoryField(item, 'ownerEntityId') || '').trim(),
                    projectId: String(extractSubjectHistoryField(item, 'project_id') || extractSubjectHistoryField(item, 'ownerScopeId') || '').trim(),
                    subjectName: String(extractSubjectHistoryField(item, 'subject_name') || extractSubjectHistoryField(item, 'entity_name') || '').trim(),
                    resultUrl,
                    displayLabel: jobKind === 'reconstruct' ? t('主体重构', 'Subject Reconstruction') : t('主体生图', 'Subject Image Generation'),
                    createdAtMs: Date.parse(String(item?.created_at || item?.started_at || item?.finished_at || '')) || 0,
                    model: extractSubjectHistoryField(item, 'model') || extractSubjectHistoryField(item, 'source_model'),
                    duration: extractSubjectHistoryField(item, 'duration'),
                };
            })
            .sort((a, b) => (b.createdAtMs || 0) - (a.createdAtMs || 0));
    }, [extractSubjectHistoryField, t]);

    const fetchSubjectGenerationHistory = useCallback(async (entity) => {
        const stableEntityId = String(entity?.id || entity || '').trim();
        const stableProjectId = String(projectId || '').trim();
        if (!stableEntityId) {
            setSubjectGenerationHistory([]);
            return;
        }

        setSubjectGenerationHistoryLoading(true);
        try {
            const pageSize = 120;
            const maxPages = 8;
            const matched = [];

            for (let page = 0; page < maxPages; page += 1) {
                const data = await fetchAssets({
                    type: 'image',
                    entity_id: stableEntityId,
                    project_id: stableProjectId || undefined,
                    episode_id: currentEpisode?.id || undefined,
                    current_project_asset: 'all',
                    skip: page * pageSize,
                    limit: pageSize,
                });
                const rows = Array.isArray(data) ? data : [];
                if (!rows.length) break;

                const pageMatched = rows.filter((item) => {
                    const meta = item?.meta_info && typeof item.meta_info === 'object' ? item.meta_info : {};
                    const itemEntityId = String(
                        meta?.entity_id
                        || meta?.ownerEntityId
                        || item?.entity_id
                        || item?.ownerEntityId
                        || ''
                    ).trim();
                    if (itemEntityId !== stableEntityId) return false;

                    if (stableProjectId) {
                        const itemProjectId = String(
                            meta?.project_id
                            || meta?.ownerScopeId
                            || item?.project_id
                            || item?.projectId
                            || ''
                        ).trim();
                        if (itemProjectId && itemProjectId !== stableProjectId) return false;
                    }

                    return String(item.type).toLowerCase() === 'image';
                });

                matched.push(...pageMatched);
                if (matched.length >= 24 || rows.length < pageSize) break;
            }

            const filtered = matched.map((item) => {
                const meta = item?.meta_info && typeof item.meta_info === 'object' ? item.meta_info : {};
                return {
                    id: item.id,
                    job_id: item.id,
                    status: 'completed',
                    resultUrl: item.url,
                    displayLabel: item.remark || t('主体生图', 'Subject Image Generation'),
                    createdAtMs: Date.parse(item.created_at || '') || 0,
                    created_at: item.created_at,
                    kind: 'asset',
                    model: meta?.model || meta?.source_model,
                    duration: meta?.duration
                };
            }).sort((a, b) => (b.createdAtMs || 0) - (a.createdAtMs || 0));
            setSubjectGenerationHistory(filtered.slice(0, 12));
        } catch (e) {
            onLog?.(`Failed to load subject generation history: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
            setSubjectGenerationHistory([]);
        } finally {
            setSubjectGenerationHistoryLoading(false);
        }
    }, [currentEpisode?.id, onLog, t, projectId]);

    useEffect(() => {
        if (!selectedEntity?.id) {
            setSubjectGenerationHistory([]);
            return;
        }
        fetchSubjectGenerationHistory(selectedEntity);
    }, [fetchSubjectGenerationHistory, selectedEntity]);

    const handleDeleteSubjectGenerationHistoryItem = useCallback(async (item) => {
        const assetId = String(item?.id || '').trim();
        if (!assetId || !selectedEntity?.id) return;

        setSubjectGenerationHistoryDeletingId(assetId);
        try {
            await deleteAsset(assetId);
            await fetchSubjectGenerationHistory(selectedEntity);
            onLog?.(t('主体历史图片已删除。', 'Subject history image deleted.'), 'warning');
        } catch (e) {
            onLog?.(t('删除历史图片失败：', 'Failed to delete subject history image: ') + (e?.response?.data?.detail || e?.message || 'unknown error'), 'error');
        } finally {
            setSubjectGenerationHistoryDeletingId('');
        }
    }, [fetchSubjectGenerationHistory, onLog, selectedEntity, t]);

    const showSubjectNotification = useCallback((message, type = 'success') => {
        setSubjectNotification({ message, type });
        setTimeout(() => setSubjectNotification(null), 3000);
    }, []);

    const openAiEntityCreateModal = useCallback(() => {
        setAiEntityCreateReport(null);
        setAiReuseEntityTypeFilter('all');
        setIsAiUploadAnalyzing(false);
        setAiUploadedAsset(null);
        setAiUploadedAssetAnalysis('');
        setAiEntityCreateForm({
            type: normalizeAiEntityType(subTab),
            name: '',
            nameEn: '',
            attributes: '',
            reuseEntityIds: [],
        });
        setShowAiEntityCreateModal(true);
    }, [normalizeAiEntityType, subTab]);

    useEffect(() => {
        const targetType = normalizeAiEntityType(aiEntityCreateForm?.type);
        if (targetType !== 'poster') {
            setAiReuseEntityTypeFilter(targetType);
        }

        const allowedIds = new Set(
            (allEntities || [])
                .filter((entity) => isAiReuseEntityAllowed(targetType, entity?.type))
                .map((entity) => String(entity?.id || '').trim())
                .filter(Boolean)
        );

        setAiEntityCreateForm((prev) => {
            const nextIds = (Array.isArray(prev?.reuseEntityIds) ? prev.reuseEntityIds : [])
                .map((id) => String(id || '').trim())
                .filter((id) => allowedIds.has(id));
            const prevIds = Array.isArray(prev?.reuseEntityIds) ? prev.reuseEntityIds.map((id) => String(id || '').trim()) : [];
            if (nextIds.length === prevIds.length && nextIds.every((id, idx) => id === prevIds[idx])) {
                return prev;
            }
            return { ...prev, reuseEntityIds: nextIds };
        });
    }, [aiEntityCreateForm?.type, allEntities, isAiReuseEntityAllowed, normalizeAiEntityType]);

    const aiReusableEntities = useMemo(() => {
        const targetType = normalizeAiEntityType(aiEntityCreateForm?.type);
        const effectiveFilter = targetType === 'poster' ? aiReuseEntityTypeFilter : targetType;
        const filteredByType = (allEntities || []).filter((entity) => {
            if (!isAiReuseEntityAllowed(targetType, entity?.type)) return false;
            if (effectiveFilter === 'all') return true;
            return normalizeAiEntityType(entity?.type) === effectiveFilter;
        });
        return filteredByType;
    }, [aiEntityCreateForm?.type, aiReuseEntityTypeFilter, allEntities, isAiReuseEntityAllowed, normalizeAiEntityType]);

    const handleAiEntityAssetUploadAndAnalyze = useCallback(async (file) => {
        if (!file) return;
        setIsAiUploadAnalyzing(true);
        setAiUploadedAssetAnalysis('');
        try {
            const uploadedAsset = await uploadAsset(file, {
                asset_type: 'subject',
                remark: `ai_entity_modal_upload:${String(aiEntityCreateForm?.type || '').trim()}`,
            });
            setAiUploadedAsset(uploadedAsset);

            const analysisResp = await analyzeAssetImage(uploadedAsset?.id);
            const analysisText = String(analysisResp?.result || '').trim();
            setAiUploadedAssetAnalysis(analysisText);

            if (analysisText) {
                setAiEntityCreateForm((prev) => {
                    const prevAttrs = String(prev?.attributes || '').trim();
                    const injected = `${t('参考资产反推结果', 'Reference asset reverse-analysis')}:\n${analysisText}`;
                    const nextAttrs = prevAttrs
                        ? `${prevAttrs}\n\n${injected}`
                        : injected;
                    return { ...prev, attributes: nextAttrs };
                });
                showSubjectNotification(t('资产反推完成，已回填到属性描述。', 'Asset reverse-analysis completed and appended to attributes.'), 'success');
            } else {
                showSubjectNotification(t('资产反推返回为空，请手动补充属性描述。', 'Asset reverse-analysis returned empty. Please add attributes manually.'), 'warning');
            }
        } catch (error) {
            const detail = error?.response?.data?.detail || error?.message || String(error);
            setAiUploadedAssetAnalysis(`${t('资产反推失败：', 'Asset reverse-analysis failed: ')}${detail}`);
            showSubjectNotification(`${t('上传或反推失败：', 'Upload or reverse-analysis failed: ')}${detail}`, 'error');
        } finally {
            setIsAiUploadAnalyzing(false);
        }
    }, [aiEntityCreateForm?.type, analyzeAssetImage, showSubjectNotification, t]);

    const handleSubmitAiEntityCreate = useCallback(async () => {
        const stableName = String(aiEntityCreateForm?.name || '').trim();
        const stableAttrs = String(aiEntityCreateForm?.attributes || '').trim();
        if (!stableName) {
            alert(t('请先填写实体名称。', 'Please enter an entity name first.'));
            return;
        }
        if (!stableAttrs) {
            alert(t('请先填写属性描述。', 'Please enter the attribute description first.'));
            return;
        }

        setIsAiEntityCreating(true);
        setAiEntityCreateReport(null);
        try {
            const systemPrompt = String(await fetchEntityDesignSystemPrompt(aiEntityCreateForm?.type) || '').trim();
            if (!systemPrompt && onLog) {
                onLog('entity design common+type prompts are empty or unavailable, continuing with default routing.', 'warning');
            }

            const stableTargetType = normalizeAiEntityType(aiEntityCreateForm?.type);
            const sanitizedReuseEntityIds = (Array.isArray(aiEntityCreateForm?.reuseEntityIds) ? aiEntityCreateForm.reuseEntityIds : [])
                .map((id) => String(id || '').trim())
                .filter(Boolean)
                .filter((id) => {
                    const entity = (allEntities || []).find((item) => String(item?.id || '').trim() === id);
                    return isAiReuseEntityAllowed(stableTargetType, entity?.type);
                });
            const sanitizedForm = { ...aiEntityCreateForm, reuseEntityIds: sanitizedReuseEntityIds };
            const inputText = buildManualSubjectIndexInput(sanitizedForm);
            const scriptAnalysisApiId = Number(localStorage.getItem('func_api_script_analysis') || 0) || null;

            const result = await analyzeScene(
                inputText,
                systemPrompt || null,
                null,
                currentEpisode?.id || null,
                null,
                null,
                null,
                projectId,
                'script_analysis',
                scriptAnalysisApiId,
                'entity_design'
            );

            const backendSubjectsJson = (result?.subjects_json && typeof result.subjects_json === 'object')
                ? result.subjects_json
                : null;
            const analyzedText = String(result?.analysis || result?.text || result?.result || '').trim();

            let importReport = null;
            if (typeof onImportText === 'function') {
                importReport = await onImportText(analyzedText || JSON.stringify(backendSubjectsJson || {}, null, 2), 'json', {
                    onLog,
                    projectId,
                    episodeId: currentEpisode?.id || null,
                    subjectsJson: backendSubjectsJson || null,
                    suppressAlerts: true,
                });
            } else if (backendSubjectsJson) {
                importReport = await importSubjectsJsonDirectly(backendSubjectsJson);
            }

            if (projectId) {
                const latest = await fetchEntities(projectId, {
                    include_project_null_episode: true,
                });
                const processedLatest = Array.isArray(latest) ? latest.map(item => {
                    if (item.type === 'environment' && (item.name === '封面海报' || item.name_en === 'Cover Poster')) {
                        return { ...item, type: 'poster' };
                    }
                    return item;
                }) : [];
                setAllEntities(processedLatest);
            }

            const report = formatAiEntityCreateReport(importReport || {});
            const imported = importReport?.importedSubjectCounts || {};
            const importedTotal = Number(imported.character || 0) + Number(imported.prop || 0) + Number(imported.environment || 0) + Number(imported.poster || 0);
            const skippedItems = Array.isArray(importReport?.skippedSubjectItems) ? importReport.skippedSubjectItems : [];

            if (projectId) {
                try {
                    const auditPayload = {
                        action: 'AI_ENTITY_IMPORT',
                        details: JSON.stringify({
                            source: 'subject_library_manual_entity_design',
                            project_id: projectId,
                            episode_id: currentEpisode?.id || null,
                            imported_counts: imported,
                            imported_total: importedTotal,
                            skipped_total: skippedItems.length,
                            skipped_reused: skippedItems
                                .filter((item) => String(item?.reason || '').trim().toLowerCase() === 'exists')
                                .slice(0, 100)
                                .map((item) => ({
                                    type: item?.type || null,
                                    name: item?.name || null,
                                    reason: item?.reason || null,
                                    reused_entity_id: item?.reusedEntityId || null,
                                    reused_entity_name: item?.reusedEntityName || null,
                                    reused_image_url: item?.reusedImageUrl || null,
                                    reused_dependency_policy: item?.reusedDependencyPolicy || null,
                                })),
                        }),
                    };
                    await recordSystemLogAction(auditPayload);
                } catch (e) {
                    onLog?.(t('导入审计日志写入失败（不影响导入结果）。', 'Import audit log write failed (import result unchanged).'), 'warning');
                }
            }

            setAiEntityCreateReport(report.details);
            showSubjectNotification(report.summary, importedTotal > 0 ? 'success' : 'warning');
            onLog?.(report.details, importedTotal > 0 ? 'success' : 'warning');
        } catch (error) {
            const message = error?.response?.data?.detail || error?.message || String(error);
            const reportText = t(`AI 新增实体失败：${message}`, `AI entity creation failed: ${message}`);
            setAiEntityCreateReport(reportText);
            showSubjectNotification(reportText, 'error');
            onLog?.(reportText, 'error');
        } finally {
            setIsAiEntityCreating(false);
        }
    }, [
        aiEntityCreateForm,
        allEntities,
        buildManualSubjectIndexInput,
        currentEpisode?.id,
        fetchEntityDesignSystemPrompt,
        importSubjectsJsonDirectly,
        isAiReuseEntityAllowed,
        normalizeAiEntityType,
        onImportText,
        onLog,
        projectId,
        showSubjectNotification,
        formatAiEntityCreateReport,
        t,
    ]);

    const forceClearSubjectImageJob = useCallback(async (entityId, payload, reason) => {
        const stableEntityId = String(entityId || payload?.ownerEntityId || '').trim();
        const stableJobId = String(payload?.jobId || '').trim();
        const ownerLabel = describeSubjectJobOwner(payload, stableEntityId);
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

        updateSubjectImageJobsAndStorage((prev) => {
            const next = { ...(prev || {}) };
            delete next[stableEntityId];
            return next;
        });
        setStoppingSubjectImageJobs((prev) => {
            const next = { ...(prev || {}) };
            delete next[stableEntityId];
            return next;
        });

        if (onLog) {
            onLog(
                t(
                    `已强制清理主体任务：${ownerLabel}，原因：${reasonText}`,
                    `Subject job force-cleared: ${ownerLabel}. Reason: ${reasonText}`
                ),
                'warning'
            );
        }
    }, [deleteGenerationJob, describeSubjectJobOwner, onLog, stopGenerationJob, t]);

    const setLocalSubjectImageJobState = useCallback((entityId, patch = {}) => {
        const stableEntityId = String(entityId || '').trim();
        if (!stableEntityId) return;

        updateSubjectImageJobsAndStorage(prev => ({
            ...(prev || {}),
            [stableEntityId]: {
                ...(prev?.[stableEntityId] || {}),
                ...patch,
            },
        }));
    }, []);

    const clearLocalSubjectImageJobState = useCallback((entityId) => {
        const stableEntityId = String(entityId || '').trim();
        if (!stableEntityId) return;

        updateSubjectImageJobsAndStorage(prev => {
            const next = { ...(prev || {}) };
            delete next[stableEntityId];
            return next;
        });
        setStoppingSubjectImageJobs(prev => {
            const next = { ...(prev || {}) };
            delete next[stableEntityId];
            return next;
        });
    }, []);

    const shouldLogSubjectJobTerminal = useCallback((jobId, outcome) => {
        const stableJobId = String(jobId || '').trim();
        const stableOutcome = String(outcome || '').trim().toLowerCase();
        if (!stableJobId || !stableOutcome) return true;
        const dedupeKey = `${stableJobId}:${stableOutcome}`;
        if (subjectImageJobTerminalLogRef.current.has(dedupeKey)) {
            return false;
        }
        subjectImageJobTerminalLogRef.current.add(dedupeKey);
        return true;
    }, []);

    const isSubjectBatchStopSignal = useCallback((error) => {
        return String(error?.message || '').trim() === '__subject_batch_stop__';
    }, []);

    const trackSubjectBatchImageJob = useCallback((kind, entity, jobId) => {
        const stableJobId = String(jobId || '').trim();
        const stableEntityId = String(entity?.id || '').trim();
        if (!stableJobId || !stableEntityId) return;
        const previousStableImageUrl = String(entity?.image_url || '').trim();

        const targetMap = kind === 'reconstruct'
            ? subjectBatchReconstructActiveJobsRef.current
            : subjectBatchGenerateActiveJobsRef.current;

        targetMap.set(stableEntityId, stableJobId);
        updateSubjectImageJobsAndStorage(prev => ({
            ...(prev || {}),
            [stableEntityId]: {
                ...(prev?.[stableEntityId] || {}),
                jobId: stableJobId,
                status: 'queued',
                startedAt: Date.now(),
                entityName: entity?.name || entity?.name_en || stableEntityId,
                ...buildSubjectJobMeta(stableEntityId, kind, { previousStableImageUrl }),
            },
        }));
    }, [buildSubjectJobMeta]);

    const untrackSubjectBatchImageJob = useCallback((kind, entityId) => {
        const stableEntityId = String(entityId || '').trim();
        if (!stableEntityId) return;
        const targetMap = kind === 'reconstruct'
            ? subjectBatchReconstructActiveJobsRef.current
            : subjectBatchGenerateActiveJobsRef.current;
        targetMap.delete(stableEntityId);
    }, []);

    const forceStopTrackedSubjectBatchImageJobs = useCallback(async (kind) => {
        const targetMap = kind === 'reconstruct'
            ? subjectBatchReconstructActiveJobsRef.current
            : subjectBatchGenerateActiveJobsRef.current;
        const entries = Array.from(targetMap.entries());
        targetMap.clear();
        if (entries.length === 0) return 0;

        await Promise.allSettled(entries.map(async ([, jobId]) => {
            const stableJobId = String(jobId || '').trim();
            if (!stableJobId) return;
            await stopGenerationJob('image', stableJobId, { force: true });
        }));

        updateSubjectImageJobsAndStorage(prev => {
            const next = { ...(prev || {}) };
            entries.forEach(([entityId]) => {
                delete next[String(entityId)];
            });
            return next;
        });

        return entries.length;
    }, [stopGenerationJob]);

    const clearPendingSubjectBatchImagePlaceholders = useCallback(() => {
        updateSubjectImageJobsAndStorage(prev => {
            const next = { ...(prev || {}) };
            let changed = false;

            Object.entries(next).forEach(([entityId, job]) => {
                const stableJobId = String(job?.jobId || '').trim();
                const status = String(job?.status || '').trim().toLowerCase();
                if (stableJobId) {
                    return;
                }
                if (status === 'queued' || status === 'running' || status === 'persisting') {
                    delete next[entityId];
                    changed = true;
                }
            });

            return changed ? next : prev;
        });
        setStoppingSubjectImageJobs(prev => {
            const next = { ...(prev || {}) };
            let changed = false;
            Object.keys(next).forEach((entityId) => {
                const stableEntityId = String(entityId || '').trim();
                if (!stableEntityId) return;
                delete next[stableEntityId];
                changed = true;
            });
            return changed ? next : prev;
        });
    }, []);

    const normalizeSubjectImageJobs = useCallback((raw) => {
        if (!raw || typeof raw !== 'object') return {};
        const now = Date.now();
        const cleaned = {};
        Object.entries(raw).forEach(([entityId, value]) => {
            const stableEntityId = String(entityId || '').trim();
            const jobId = String(value?.jobId || '').trim();
            const startedAt = Number(value?.startedAt || 0) || now;
            if (!stableEntityId || !jobId) return;
            if ((now - startedAt) > SUBJECT_IMAGE_JOB_TTL_MS) return;
            const jobKind = value?.jobKind === 'reconstruct' ? 'reconstruct' : 'generate';
            cleaned[stableEntityId] = {
                jobId,
                startedAt,
                entityName: String(value?.entityName || '').trim(),
                status: String(value?.status || '').trim(),
                ...buildSubjectJobMeta(stableEntityId, jobKind, value),
            };
        });
        return cleaned;
    }, [SUBJECT_IMAGE_JOB_TTL_MS, buildSubjectJobMeta]);

    const readSubjectImageJobsStorage = useCallback(() => {
        if (!subjectImageJobStorageKey) return {};
        try {
            const raw = localStorage.getItem(subjectImageJobStorageKey);
            if (!raw) return {};
            return normalizeSubjectImageJobs(JSON.parse(raw));
        } catch {
            return {};
        }
    }, [normalizeSubjectImageJobs, subjectImageJobStorageKey]);

    const writeSubjectImageJobsStorage = useCallback((jobs) => {
        if (!subjectImageJobStorageKey) return;
        try {
            const normalized = normalizeSubjectImageJobs(jobs);
            if (Object.keys(normalized).length === 0) {
                localStorage.removeItem(subjectImageJobStorageKey);
                return;
            }
            localStorage.setItem(subjectImageJobStorageKey, JSON.stringify(normalized));
        } catch {
            // ignore storage failures
        }
    }, [normalizeSubjectImageJobs, subjectImageJobStorageKey]);

    const updateSubjectImageJobsAndStorage = useCallback((updater) => {
        setSubjectImageJobs(prev => {
            const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater };
            writeSubjectImageJobsStorage(next);
            return next;
        });
        // Run against local storage immediately to ensure state persists after component unmounts
        if (!subjectImageJobStorageKey) return;
        try {
            const raw = localStorage.getItem(subjectImageJobStorageKey);
            let current = {};
            if (raw) {
                current = JSON.parse(raw);
            }
            const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
            writeSubjectImageJobsStorage(next);
        } catch {
            // ignore
        }
    }, [setSubjectImageJobs, subjectImageJobStorageKey, writeSubjectImageJobsStorage]);

    useEffect(() => {
        if (!window?.localStorage) return;
        try {
            if (window.localStorage.getItem(IMAGE_JOB_CACHE_PURGE_MARKER_KEY) === '1') return;

            const imageJobPrefixes = [
                'aistory.subjectImageJobs.',
                'aistory.shotImageJobs.',
                'aistory.shotVideoJobs.',
                'aistory.shotGenerationState.',
            ];

            const keysToRemove = [];
            for (let index = 0; index < window.localStorage.length; index += 1) {
                const key = String(window.localStorage.key(index) || '');
                if (!key) continue;
                if (key === SUBJECT_BATCH_RUNTIME_STORAGE_KEY || imageJobPrefixes.some((prefix) => key.startsWith(prefix))) {
                    keysToRemove.push(key);
                }
            }

            keysToRemove.forEach((key) => {
                window.localStorage.removeItem(key);
            });
            window.localStorage.setItem(IMAGE_JOB_CACHE_PURGE_MARKER_KEY, '1');
        } catch {
            // ignore storage failures
        }

        subjectBatchGenerateActiveJobsRef.current.clear();
        subjectBatchReconstructActiveJobsRef.current.clear();
        if (window.__AISTORY_SUBJECT_BATCH_RUNTIME__) {
            window.__AISTORY_SUBJECT_BATCH_RUNTIME__.generate = createSubjectBatchTaskState();
            window.__AISTORY_SUBJECT_BATCH_RUNTIME__.analyze = createSubjectBatchTaskState();
            window.__AISTORY_SUBJECT_BATCH_RUNTIME__.reconstruct = createSubjectBatchTaskState();
            emitSubjectBatchRuntime();
        }
        updateSubjectImageJobsAndStorage({});
        setStoppingSubjectImageJobs({});
    }, [createSubjectBatchTaskState, emitSubjectBatchRuntime]);

    const resolvedPromptSubmitLang = useMemo(() => {
        return 'cn';
    }, []);

    const effectivePromptSubmitLang = useMemo(() => {
        return 'cn';
    }, []);

    const promptLangText = useCallback((lang) => {
        return lang === 'cn' ? t('中文', 'Chinese') : t('英文', 'English');
    }, [t]);

    const promptLangPrefText = useCallback((pref) => {
        if (pref === 'cn') return t('中文', 'Chinese');
        if (pref === 'auto') return t('跟随界面语言', 'Follow UI');
        return t('英文', 'English');
    }, [t]);

    const getSubjectImageJobEntry = useCallback((entityOrId) => {
        const stableEntityId = String(entityOrId?.id || entityOrId || '').trim();
        if (!stableEntityId) return null;
        return subjectImageJobs[stableEntityId] || null;
    }, [subjectImageJobs]);

    const isSubjectImageActionLocked = useCallback((entityOrId) => {
        const stableEntityId = String(entityOrId?.id || entityOrId || '').trim();
        if (!stableEntityId) return false;
        return Boolean(subjectImageJobs[stableEntityId] || stoppingSubjectImageJobs[stableEntityId]);
    }, [stoppingSubjectImageJobs, subjectImageJobs]);

    const notifySubjectImageActionLocked = useCallback((entityOrId) => {
        const stableEntityId = String(entityOrId?.id || entityOrId || '').trim();
        const entityName = String(entityOrId?.name || entityOrId?.name_en || stableEntityId).trim() || stableEntityId;
        const message = t(
            `主体图片任务运行中，暂时不能更换或移除图片：${entityName}`,
            `Subject image job is running. Image changes are temporarily disabled: ${entityName}`
        );
        showSubjectNotification(message, 'warning');
        onLog?.(message, 'warning');
    }, [onLog, showSubjectNotification, t]);

    const getResolvedEntityGlobalStyleText = useCallback(() => {
        const info = currentEpisode?.episode_info?.e_global_info;
        const projectInfo = project?.global_info;
        return String(
            info?.Global_Style
            || info?.global_style
            || projectInfo?.Global_Style
            || projectInfo?.global_style
            || ''
        ).trim();
    }, [currentEpisode?.episode_info?.e_global_info, project?.global_info]);

    const prependEntityGlobalStyleToPromptHead = useCallback((text, options = {}) => {
        const rawText = String(text || '').trim();
        if (!rawText) return rawText;

        const { injectIfMissing = true } = options || {};
        const globalStyle = getResolvedEntityGlobalStyleText();
        if (!globalStyle) return rawText;

        const tokenPattern = /[\[【]\s*(global style|global_style)\s*[\]】]/ig;
        const replaced = rawText.replace(tokenPattern, `[Global Style](${globalStyle})`);
        if (replaced !== rawText) return replaced;
        if (!injectIfMissing) return rawText;

        if (/\[Global Style\]\s*\(/i.test(rawText)) return rawText;
        if (rawText.toLowerCase().startsWith(globalStyle.toLowerCase())) return rawText;

        return `[Global Style](${globalStyle}). ${rawText}`;
    }, [getResolvedEntityGlobalStyleText]);

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

    const getEntityPromptByLang = useCallback((entity, lang) => {
        if (!entity) return '';
        if (lang === 'cn') {
            return String(entity.generation_prompt_cn || entity.generation_prompt_en || '').trim();
        }
        return String(entity.generation_prompt_en || entity.generation_prompt_cn || '').trim();
    }, []);

    const buildProcessedEntityPrompt = useCallback((entity, lang) => {
        if (!entity) return '';

        let rawPrompt = getEntityPromptByLang(entity, lang);
        if (!rawPrompt && entity.description) {
            const match = entity.description.match(/Prompt:\s*(.*)/);
            if (match && match[1]) {
                rawPrompt = match[1].trim();
            }
        }

        const epInfo = currentEpisode?.episode_info || {};
        let processed = processPrompt(rawPrompt, epInfo, allEntities) || '';
        const infoSource = epInfo.e_global_info || epInfo;
        const suffixes = [
            infoSource?.type,
            infoSource?.lighting,
            infoSource?.tech_params?.visual_standard?.quality,
        ].filter(Boolean);
        if (suffixes.length > 0) {
            processed += (processed ? ', ' : '') + suffixes.join(', ');
        }

        return prependEntityGlobalStyleToPromptHead(processed, { injectIfMissing: true });
    }, [allEntities, currentEpisode?.episode_info, getEntityPromptByLang, prependEntityGlobalStyleToPromptHead]);

    const applySubjectEntityImageLocally = useCallback((entityId, imageUrl) => {
        const stableEntityId = String(entityId || '').trim();
        const stableImageUrl = String(imageUrl || '').trim();
        if (!stableEntityId || !stableImageUrl || !isMountedRef.current) return;

        setAllEntities(prev => prev.map(item => String(item?.id) === stableEntityId ? { ...item, image_url: stableImageUrl } : item));
        setEntities(prev => prev.map(item => String(item?.id) === stableEntityId ? { ...item, image_url: stableImageUrl } : item));
        setViewingEntity(prev => (String(prev?.id || '') === stableEntityId ? { ...prev, image_url: stableImageUrl } : prev));
        setSelectedEntity(prev => (String(prev?.id || '') === stableEntityId ? { ...prev, image_url: stableImageUrl } : prev));
        if (showImageModal && String(selectedEntity?.id || '') === stableEntityId) {
            setShowImageModal(false);
        }
    }, [selectedEntity?.id, showImageModal]);

    const clearSubjectEntityImageLocally = useCallback((entityId) => {
        const stableEntityId = String(entityId || '').trim();
        if (!stableEntityId || !isMountedRef.current) return;

        const applyClear = (item) => (String(item?.id || '') === stableEntityId ? { ...item, image_url: null } : item);
        setAllEntities(prev => prev.map(applyClear));
        setEntities(prev => prev.map(applyClear));
        setViewingEntity(prev => (String(prev?.id || '') === stableEntityId ? { ...prev, image_url: null } : prev));
        setSelectedEntity(prev => (String(prev?.id || '') === stableEntityId ? { ...prev, image_url: null } : prev));
        if (showImageModal && String(selectedEntity?.id || '') === stableEntityId) {
            setShowImageModal(false);
        }
    }, [selectedEntity?.id, showImageModal]);

    const refreshPersistedSubjectEntityImage = useCallback(async (entityId) => {
        const stableEntityId = String(entityId || '').trim();
        if (!projectId || !stableEntityId) return '';

        const latestEntities = await fetchEntities(projectId, {
            include_project_null_episode: true,
        });
        const latestEntity = (Array.isArray(latestEntities) ? latestEntities : []).find((item) => String(item?.id || '') === stableEntityId);
        const recoveredUrl = String(latestEntity?.image_url || '').trim();
        if (!recoveredUrl || isEphemeralProviderMediaUrl(recoveredUrl)) {
            return '';
        }

        applySubjectEntityImageLocally(stableEntityId, recoveredUrl);
        return recoveredUrl;
    }, [applySubjectEntityImageLocally, fetchEntities, isEphemeralProviderMediaUrl, projectId]);

    const awaitPersistedSubjectEntityImage = useCallback(async (entityId, options = {}) => {
        const stableEntityId = String(entityId || '').trim();
        if (!stableEntityId) return '';

        const initialUrl = String(options?.initialUrl || '').trim();
        if (initialUrl && !isEphemeralProviderMediaUrl(initialUrl)) {
            return initialUrl;
        }

        const timeoutMsRaw = Number(options?.timeoutMs || 0) || 0;
        const intervalMsRaw = Number(options?.intervalMs || 0) || 0;
        const timeoutMs = Math.max(3000, timeoutMsRaw || 120000);
        const intervalMs = Math.max(1000, intervalMsRaw || 2500);
        const entityLabel = String(options?.entityName || stableEntityId).trim() || stableEntityId;
        const tempFilename = getTempMediaFilenameFromUrl(options?.initialUrl);
        const tempFileLabel = tempFilename ? `（临时文件：${tempFilename}）` : '';
        const deadline = Date.now() + timeoutMs;

        let recoveredUrl = '';
        while (Date.now() < deadline) {
            try {
                recoveredUrl = await refreshPersistedSubjectEntityImage(stableEntityId);
            } catch (refreshErr) {
                console.warn('Failed to refresh persisted subject entity image', refreshErr);
            }
            if (recoveredUrl) {
                return recoveredUrl;
            }
            await new Promise((resolve) => setTimeout(resolve, intervalMs));
        }

        if (onLog) {
            onLog(
                t(
                    `等待主体稳定图片地址超时：${entityLabel}${tempFileLabel}`,
                    `Timed out waiting for durable subject image URL: ${entityLabel}${tempFileLabel}`
                ),
                'warning'
            );
        }
        return '';
    }, [getTempMediaFilenameFromUrl, isEphemeralProviderMediaUrl, onLog, refreshPersistedSubjectEntityImage, t]);

    const applyGenerateBatchState = useCallback((running, progress) => {
        if (!isMountedRef.current) return;
        setIsBatchGeneratingEntities(Boolean(running));
        setBatchEntityProgress(progress || null);
    }, []);

    const applyAnalyzeBatchState = useCallback((running, progress) => {
        if (!isMountedRef.current) return;
        setIsBatchAnalyzingEntities(Boolean(running));
        setBatchAnalyzeProgress(progress || null);
    }, []);

    const applyReconstructBatchState = useCallback((running, progress) => {
        if (!isMountedRef.current) return;
        setIsBatchReconstructingEntities(Boolean(running));
        setBatchReconstructProgress(progress || null);
    }, []);

    const updateGenerateBatchRuntimeState = useCallback((running, progress) => {
        updateSubjectBatchTask('generate', {
            running: Boolean(running),
            progress: progress || null,
            scopeKey: subjectBatchScopeKey,
        });
        applyGenerateBatchState(running, progress);
    }, [applyGenerateBatchState, subjectBatchScopeKey]);

    const updateAnalyzeBatchRuntimeState = useCallback((running, progress) => {
        updateSubjectBatchTask('analyze', {
            running: Boolean(running),
            progress: progress || null,
            scopeKey: subjectBatchScopeKey,
        });
        applyAnalyzeBatchState(running, progress);
    }, [applyAnalyzeBatchState, subjectBatchScopeKey]);

    const updateReconstructBatchRuntimeState = useCallback((running, progress) => {
        updateSubjectBatchTask('reconstruct', {
            running: Boolean(running),
            progress: progress || null,
            scopeKey: subjectBatchScopeKey,
        });
        applyReconstructBatchState(running, progress);
    }, [applyReconstructBatchState, subjectBatchScopeKey]);

    const hasSubjectBatchJobState = useCallback((jobKind) => {
        const stableJobKind = String(jobKind || '').trim();
        if (!stableJobKind) return false;

        return Object.values(subjectImageJobs || {}).some((job) => {
            if (!job || typeof job !== 'object') return false;
            const currentJobKind = String(job?.jobKind || 'generate').trim();
            return currentJobKind === stableJobKind;
        });
    }, [subjectImageJobs]);

    const clearSubjectBatchRuntimeUi = useCallback((task) => {
        const stableTask = String(task || '').trim();
        if (stableTask === 'generate') {
            updateGenerateBatchRuntimeState(false, null);
            setIsStoppingBatchGenerateEntities(false);
            return;
        }
        if (stableTask === 'analyze') {
            updateAnalyzeBatchRuntimeState(false, null);
            return;
        }
        if (stableTask === 'reconstruct') {
            updateReconstructBatchRuntimeState(false, null);
        }
    }, [updateAnalyzeBatchRuntimeState, updateGenerateBatchRuntimeState, updateReconstructBatchRuntimeState]);

    const tryHealSubjectBatchRuntime = useCallback((options = {}) => {
        const {
            task,
            uiRunning,
            sessionRef,
            activeJobsRef,
            jobKind,
            stopRequestedRef,
            snapshot = null,
            staleMs = 0,
            allowSessionReset = false,
        } = options;

        const stableTask = String(task || '').trim();
        if (!stableTask || !uiRunning) return false;

        if (!allowSessionReset && String(sessionRef?.current || '').trim()) {
            return false;
        }

        if (activeJobsRef?.current?.size > 0) {
            return false;
        }

        if (jobKind && hasSubjectBatchJobState(jobKind)) {
            return false;
        }

        if (staleMs > 0) {
            const taskState = snapshot?.[stableTask] || createSubjectBatchTaskState();
            const updatedAt = Number(taskState?.updatedAt || 0) || 0;
            if (!taskState?.running) return false;
            if (updatedAt <= 0 || (Date.now() - updatedAt) <= staleMs) {
                return false;
            }
        }

        // Guard: if the global runtime object still shows this task as recently
        // running, do NOT heal — the batch loop is still alive in a background
        // closure even though the component remounted with fresh refs.
        const globalTaskState = subjectBatchRuntime?.[stableTask];
        if (globalTaskState?.running) {
            const globalUpdatedAt = Number(globalTaskState?.updatedAt || 0) || 0;
            if (globalUpdatedAt > 0 && (Date.now() - globalUpdatedAt) < SUBJECT_BATCH_RUNTIME_STALE_MS) {
                return false;
            }
        }

        if (sessionRef) {
            sessionRef.current = '';
        }
        if (stopRequestedRef) {
            stopRequestedRef.current = false;
        }

        clearSubjectBatchRuntimeUi(stableTask);
        return true;
    }, [clearSubjectBatchRuntimeUi, createSubjectBatchTaskState, hasSubjectBatchJobState, subjectBatchRuntime]);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        const applySnapshot = (snapshot) => {
            const generateTask = snapshot?.generate || createSubjectBatchTaskState();
            const analyzeTask = snapshot?.analyze || createSubjectBatchTaskState();
            const reconstructTask = snapshot?.reconstruct || createSubjectBatchTaskState();

            if (generateTask.scopeKey === subjectBatchScopeKey && generateTask.running) {
                applyGenerateBatchState(true, generateTask.progress || null);
            } else {
                applyGenerateBatchState(false, null);
            }

            if (analyzeTask.scopeKey === subjectBatchScopeKey && analyzeTask.running) {
                applyAnalyzeBatchState(true, analyzeTask.progress || null);
            } else {
                applyAnalyzeBatchState(false, null);
            }

            if (reconstructTask.scopeKey === subjectBatchScopeKey && reconstructTask.running) {
                applyReconstructBatchState(true, reconstructTask.progress || null);
            } else {
                applyReconstructBatchState(false, null);
            }
        };

        applySnapshot(getSubjectBatchSnapshot());
        return subscribeSubjectBatchRuntime(applySnapshot);
    }, [applyAnalyzeBatchState, applyGenerateBatchState, applyReconstructBatchState, subjectBatchScopeKey]);

    useEffect(() => {
        tryHealSubjectBatchRuntime({
            task: 'generate',
            uiRunning: isBatchGeneratingEntities,
            sessionRef: subjectBatchGenerateSessionRef,
            activeJobsRef: subjectBatchGenerateActiveJobsRef,
            jobKind: 'generate',
            stopRequestedRef: subjectBatchGenerateStopRequestedRef,
        });
    }, [isBatchGeneratingEntities, tryHealSubjectBatchRuntime]);

    useEffect(() => {
        tryHealSubjectBatchRuntime({
            task: 'analyze',
            uiRunning: isBatchAnalyzingEntities,
            sessionRef: subjectBatchAnalyzeSessionRef,
            stopRequestedRef: subjectBatchAnalyzeStopRequestedRef,
        });
    }, [isBatchAnalyzingEntities, tryHealSubjectBatchRuntime]);

    useEffect(() => {
        tryHealSubjectBatchRuntime({
            task: 'reconstruct',
            uiRunning: isBatchReconstructingEntities,
            sessionRef: subjectBatchReconstructSessionRef,
            activeJobsRef: subjectBatchReconstructActiveJobsRef,
            jobKind: 'reconstruct',
            stopRequestedRef: subjectBatchReconstructStopRequestedRef,
        });
    }, [isBatchReconstructingEntities, tryHealSubjectBatchRuntime]);

    useEffect(() => {
        const hasTopLevelBatchUi = isBatchGeneratingEntities || isBatchAnalyzingEntities || isBatchReconstructingEntities;
        if (!hasTopLevelBatchUi) return;

        const timer = window.setInterval(() => {
            const snapshot = getSubjectBatchSnapshot();
            tryHealSubjectBatchRuntime({
                task: 'generate',
                uiRunning: isBatchGeneratingEntities,
                sessionRef: subjectBatchGenerateSessionRef,
                activeJobsRef: subjectBatchGenerateActiveJobsRef,
                jobKind: 'generate',
                stopRequestedRef: subjectBatchGenerateStopRequestedRef,
                snapshot,
                staleMs: SUBJECT_BATCH_RUNTIME_STALE_MS,
                allowSessionReset: true,
            });

            tryHealSubjectBatchRuntime({
                task: 'analyze',
                uiRunning: isBatchAnalyzingEntities,
                sessionRef: subjectBatchAnalyzeSessionRef,
                stopRequestedRef: subjectBatchAnalyzeStopRequestedRef,
                snapshot,
                staleMs: SUBJECT_BATCH_RUNTIME_STALE_MS,
                allowSessionReset: true,
            });

            tryHealSubjectBatchRuntime({
                task: 'reconstruct',
                uiRunning: isBatchReconstructingEntities,
                sessionRef: subjectBatchReconstructSessionRef,
                activeJobsRef: subjectBatchReconstructActiveJobsRef,
                jobKind: 'reconstruct',
                stopRequestedRef: subjectBatchReconstructStopRequestedRef,
                snapshot,
                staleMs: SUBJECT_BATCH_RUNTIME_STALE_MS,
                allowSessionReset: true,
            });
        }, SUBJECT_BATCH_WATCHDOG_INTERVAL_MS);

        return () => {
            window.clearInterval(timer);
        };
    }, [
        getSubjectBatchSnapshot,
        isBatchAnalyzingEntities,
        isBatchGeneratingEntities,
        isBatchReconstructingEntities,
        tryHealSubjectBatchRuntime,
    ]);

    useEffect(() => {
        updateSubjectImageJobsAndStorage(readSubjectImageJobsStorage());
    }, [readSubjectImageJobsStorage]);

    useEffect(() => {
        writeSubjectImageJobsStorage(subjectImageJobs);
    }, [subjectImageJobs, writeSubjectImageJobsStorage]);

    useEffect(() => {
        subjectImageJobsRef.current = subjectImageJobs || {};
    }, [subjectImageJobs]);

    // Load Assets
    const loadAssets = useCallback(async (options = {}) => {
        setAssetsLoading(true);
        try {
            const parseAssetMeta = (asset) => {
                if (!asset || typeof asset !== 'object') return {};
                let meta = asset.meta_info;
                for (let i = 0; i < 3; i += 1) {
                    if (typeof meta !== 'string') break;
                    const text = meta.trim();
                    if (!text) {
                        meta = {};
                        break;
                    }
                    try {
                        meta = JSON.parse(text);
                    } catch {
                        break;
                    }
                }
                return meta && typeof meta === 'object' && !Array.isArray(meta) ? meta : {};
            };

            const isImageType = (value) => {
                const stable = String(value || '').trim().toLowerCase();
                if (!stable) return false;
                return stable === 'image'
                    || stable.includes('image')
                    || stable.includes('frame')
                    || stable.includes('photo');
            };

            const pageSize = 200;
            const maxPages = 25;
            const allRows = [];

            for (let page = 0; page < maxPages; page += 1) {
                const data = await fetchAssets({
                    project_id: projectId || undefined,
                    include_project_null_episode: true,
                    current_project_asset: 'all',
                    skip: page * pageSize,
                    limit: pageSize,
                });
                const rows = Array.isArray(data) ? data : [];
                if (!rows.length) break;
                allRows.push(...rows);
                if (rows.length < pageSize) break;
            }

            const uniqueById = new Map();
            allRows.forEach((row) => {
                const key = String(row?.id || '').trim();
                if (!key || uniqueById.has(key)) return;
                uniqueById.set(key, {
                    ...row,
                    meta_info: parseAssetMeta(row),
                });
            });

            const imageAssets = Array.from(uniqueById.values()).filter((a) => isImageType(a?.type));
            setAssets(imageAssets);

            const currentProjectKey = String(projectId || '').trim();
            if (!currentProjectKey) return;

            const hasCurrentProjectAssets = imageAssets.some((asset) => {
                const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
                return String(meta.project_id || '').trim() === currentProjectKey;
            });
            if (hasCurrentProjectAssets) {
                setAssetProjectFilter(currentProjectKey);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setAssetsLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        const trackedEntityIds = Array.from(new Set([
            String(selectedEntity?.id || '').trim(),
            String(viewingEntity?.id || '').trim(),
        ].filter(Boolean)));

        if (trackedEntityIds.length === 0) {
            subjectHistoryJobPresenceRef.current = {};
            return;
        }

        const prevPresence = subjectHistoryJobPresenceRef.current || {};
        const nextPresence = {};
        const refreshEntityIds = [];

        trackedEntityIds.forEach((entityId) => {
            const hasRunningJob = Boolean(subjectImageJobs?.[entityId]);
            nextPresence[entityId] = hasRunningJob;

            const hadRunningJob = Boolean(prevPresence[entityId]);
            if (hadRunningJob && !hasRunningJob) {
                refreshEntityIds.push(entityId);
            }
        });

        subjectHistoryJobPresenceRef.current = nextPresence;

        if (refreshEntityIds.length > 0) {
            refreshEntityIds.forEach((entityId) => {
                [0, 1500, 4000].forEach((delayMs) => {
                    window.setTimeout(() => {
                        void fetchSubjectGenerationHistory(entityId);
                    }, delayMs);
                });
            });
        }
    }, [fetchSubjectGenerationHistory, selectedEntity?.id, subjectImageJobs, viewingEntity?.id]);

    useEffect(() => {
        if (Object.keys(subjectImageJobs || {}).length === 0) return;

        let disposed = false;
        const pollToken = subjectImageJobPollTokenRef.current + 1;
        subjectImageJobPollTokenRef.current = pollToken;

        const isActivePoll = () => !disposed && subjectImageJobPollTokenRef.current === pollToken;
        const getCurrentJobEntry = (entityId, expectedJobId = '') => {
            const stableEntityId = String(entityId || '').trim();
            if (!stableEntityId) return null;
            const currentEntry = subjectImageJobsRef.current?.[stableEntityId] || null;
            if (!currentEntry) return null;
            const stableExpectedJobId = String(expectedJobId || '').trim();
            if (!stableExpectedJobId) return currentEntry;
            return String(currentEntry?.jobId || '').trim() === stableExpectedJobId ? currentEntry : null;
        };

        const pollOnce = async () => {
            if (disposed || subjectImageJobPollingRef.current) return;
            subjectImageJobPollingRef.current = true;
            try {
                const completed = [];
                const statusUpdates = {};
                const jobEntries = Object.entries(subjectImageJobsRef.current || {});
                if (jobEntries.length === 0 || !isActivePoll()) {
                    return;
                }
                for (const [entityId, job] of jobEntries) {
                    const jobId = String(job?.jobId || '').trim();
                    if (!jobId) {
                        if (!getCurrentJobEntry(entityId)) {
                            continue;
                        }
                        const localStatus = String(job?.status || '').trim().toLowerCase();
                        if (localStatus === 'queued' || localStatus === 'running' || localStatus === 'persisting') {
                            continue;
                        }
                        completed.push(entityId);
                        continue;
                    }

                    let statusResp = null;
                    try {
                        statusResp = await getImageGenerationJobStatus(jobId);
                    } catch (statusErr) {
                        const detail = String(statusErr?.response?.data?.detail || statusErr?.message || 'unknown error').trim();
                        const nextFailureCount = Math.max(0, Number(job?.statusFailureCount || 0) || 0) + 1;
                        if (nextFailureCount >= SUBJECT_IMAGE_JOB_MAX_STATUS_FAILURES) {
                            await forceClearSubjectImageJob(
                                entityId,
                                job,
                                `status polling failed ${nextFailureCount}/${SUBJECT_IMAGE_JOB_MAX_STATUS_FAILURES}: ${detail}`
                            );
                        } else {
                            statusUpdates[String(entityId)] = {
                                statusFailureCount: nextFailureCount,
                                lastStatusError: detail,
                                lastPolledAt: Date.now(),
                            };
                            if (isActivePoll() && getCurrentJobEntry(entityId, jobId) && onLog) {
                                onLog(
                                    t(
                                        `主体任务状态查询失败（${nextFailureCount}/${SUBJECT_IMAGE_JOB_MAX_STATUS_FAILURES}）：${job?.entityName || entityId} - ${detail}`,
                                        `Subject job status polling failed (${nextFailureCount}/${SUBJECT_IMAGE_JOB_MAX_STATUS_FAILURES}): ${job?.entityName || entityId} - ${detail}`
                                    ),
                                    'warning'
                                );
                            }
                        }
                        continue;
                    }

                    const status = String(statusResp?.status || '').trim().toLowerCase();
                    const generatedUrl = extractImageJobResultUrl(statusResp);
                    if (generatedUrl) {
                        const currentJob = getCurrentJobEntry(entityId, jobId);
                        if (!currentJob) {
                            continue;
                        }
                        const canPersistGeneratedUrl = !isEphemeralProviderMediaUrl(generatedUrl);
                        if (canPersistGeneratedUrl) {
                            try {
                                await updateEntity(Number(entityId), { image_url: generatedUrl });
                            } catch {
                                // Best effort; local refresh still updates UX.
                            }
                        }
                        if (canPersistGeneratedUrl && currentJob) {
                            clearLocalSubjectImageJobState(entityId);
                            applySubjectEntityImageLocally(entityId, generatedUrl);
                            if (isActivePoll() && shouldLogSubjectJobTerminal(jobId, 'success') && onLog) {
                                onLog(t(`主体生成完成：${job?.entityName || entityId}`, `Subject generation completed: ${job?.entityName || entityId}`), 'success');
                            }
                            void loadAssets({ includeHistoricalEpisodeAssets: false });
                            continue;
                        }

                        let recoveredUrl = '';
                        try {
                            recoveredUrl = await refreshPersistedSubjectEntityImage(entityId);
                        } catch (refreshErr) {
                            console.warn('Failed to refresh entity after temporary image result URL', refreshErr);
                        }

                        if (recoveredUrl) {
                            if (getCurrentJobEntry(entityId, jobId)) {
                                clearLocalSubjectImageJobState(entityId);
                            }
                            if (isActivePoll() && shouldLogSubjectJobTerminal(jobId, 'success') && onLog) {
                                onLog(t(`主体生成完成：${job?.entityName || entityId}`, `Subject generation completed: ${job?.entityName || entityId}`), 'success');
                            }
                            void loadAssets({ includeHistoricalEpisodeAssets: false });
                            continue;
                        }

                        const now = Date.now();
                        const persistWaitStartedAt = Number(job?.persistWaitStartedAt || 0) || now;
                        const lastPersistWaitLogAt = Number(job?.lastPersistWaitLogAt || 0) || 0;
                        const persistWaitElapsed = now - persistWaitStartedAt;

                        if ((now - lastPersistWaitLogAt) >= SUBJECT_IMAGE_JOB_PERSIST_LOG_INTERVAL_MS && isActivePoll() && getCurrentJobEntry(entityId, jobId) && onLog) {
                            onLog(
                                t(
                                    `主体任务返回了临时图片地址，正在等待稳定图片入库：${job?.entityName || entityId}`,
                                    `Subject job returned a temporary image URL; waiting for durable image persistence: ${job?.entityName || entityId}`
                                ),
                                'process'
                            );
                        }

                        if (persistWaitElapsed >= SUBJECT_IMAGE_JOB_PERSIST_WAIT_MS) {
                            if (getCurrentJobEntry(entityId, jobId)) {
                                clearLocalSubjectImageJobState(entityId);
                            }
                            if (isActivePoll() && onLog) {
                                onLog(
                                    t(
                                        `主体任务已完成，但在等待稳定图片超时后仍未拿到可持久化地址：${job?.entityName || entityId}`,
                                        `Subject job finished, but no durable image URL was available before the persistence wait timed out: ${job?.entityName || entityId}`
                                    ),
                                    'warning'
                                );
                            }
                            continue;
                        }

                        statusUpdates[String(entityId)] = {
                            status: 'persisting',
                            lastPolledAt: now,
                            statusFailureCount: 0,
                            lastStatusError: '',
                            persistWaitStartedAt,
                            lastPersistWaitLogAt: now,
                        };
                        continue;
                    }

                    if (status === 'queued' || status === 'running') {
                        if (!isActivePoll() || !getCurrentJobEntry(entityId, jobId)) {
                            continue;
                        }
                        const startedAtMs = Number(job?.startedAt || 0) || 0;
                        if (startedAtMs > 0 && (Date.now() - startedAtMs) > SUBJECT_IMAGE_JOB_MAX_RUNNING_MS) {
                            await forceClearSubjectImageJob(
                                entityId,
                                job,
                                `running longer than ${Math.round(SUBJECT_IMAGE_JOB_MAX_RUNNING_MS / 60000)} minutes`
                            );
                            continue;
                        }
                        statusUpdates[String(entityId)] = {
                            status,
                            statusFailureCount: 0,
                            lastStatusError: '',
                            lastPolledAt: Date.now(),
                        };
                        continue;
                    }

                    if (status === 'succeeded' || status === 'completed') {
                        let recoveredUrl = '';
                        if (projectId) {
                            try {
                                recoveredUrl = await refreshPersistedSubjectEntityImage(entityId);
                            } catch (refreshErr) {
                                console.warn('Failed to refresh entity after succeeded image job without result URL', refreshErr);
                            }
                        }
                        if (recoveredUrl) {
                            if (getCurrentJobEntry(entityId, jobId)) {
                                clearLocalSubjectImageJobState(entityId);
                            }
                            if (isActivePoll() && shouldLogSubjectJobTerminal(jobId, 'success') && onLog) {
                                onLog(t(`主体生成完成：${job?.entityName || entityId}`, `Subject generation completed: ${job?.entityName || entityId}`), 'success');
                            }
                            void loadAssets({ includeHistoricalEpisodeAssets: false });
                            continue;
                        }

                        const now = Date.now();
                        const persistWaitStartedAt = Number(job?.persistWaitStartedAt || 0) || now;
                        const lastPersistWaitLogAt = Number(job?.lastPersistWaitLogAt || 0) || 0;
                        const persistWaitElapsed = now - persistWaitStartedAt;

                        if ((now - lastPersistWaitLogAt) >= SUBJECT_IMAGE_JOB_PERSIST_LOG_INTERVAL_MS && isActivePoll() && getCurrentJobEntry(entityId, jobId) && onLog) {
                            onLog(
                                t(
                                    `主体任务已完成，正在等待稳定图片入库：${job?.entityName || entityId}`,
                                    `Subject job completed and is waiting for durable image persistence: ${job?.entityName || entityId}`
                                ),
                                'process'
                            );
                        }

                        if (persistWaitElapsed >= SUBJECT_IMAGE_JOB_PERSIST_WAIT_MS) {
                            if (getCurrentJobEntry(entityId, jobId)) {
                                clearLocalSubjectImageJobState(entityId);
                            }
                            if (isActivePoll() && onLog) {
                                onLog(
                                    t(
                                        `主体任务状态为完成，但等待稳定图片超时：${job?.entityName || entityId}`,
                                        `Subject job reported completed, but timed out waiting for a durable image URL: ${job?.entityName || entityId}`
                                    ),
                                    'warning'
                                );
                            }
                            continue;
                        }

                        statusUpdates[String(entityId)] = {
                            status: 'persisting',
                            lastPolledAt: now,
                            statusFailureCount: 0,
                            lastStatusError: '',
                            persistWaitStartedAt,
                            lastPersistWaitLogAt: now,
                        };
                        continue;
                    }

                    if (status === 'failed' || status === 'canceled' || status === 'cancelled' || status === 'error') {
                        if (getCurrentJobEntry(entityId, jobId)) {
                            clearLocalSubjectImageJobState(entityId);
                        }
                        if (isActivePoll() && shouldLogSubjectJobTerminal(jobId, 'failed') && onLog) {
                            onLog(t(`主体生成失败：${job?.entityName || entityId} - ${statusResp?.error || status}`, `Subject generation failed: ${job?.entityName || entityId} - ${statusResp?.error || status}`), 'error');
                        }
                        continue;
                    }
                }

                if (isActivePoll() && Object.keys(statusUpdates).length > 0) {
                    updateSubjectImageJobsAndStorage(prev => {
                        const base = { ...(prev || {}) };
                        let changed = false;
                        for (const [entityId, patch] of Object.entries(statusUpdates)) {
                            const existing = base[String(entityId)];
                            if (!existing) continue;
                            const nextEntry = {
                                ...existing,
                                ...patch,
                            };
                            const patchChanged = Object.keys(nextEntry).some((key) => nextEntry[key] !== existing[key]);
                            if (!patchChanged) continue;
                            base[String(entityId)] = {
                                ...nextEntry,
                            };
                            changed = true;
                        }
                        return changed ? base : prev;
                    });
                }

                if (isActivePoll() && completed.length > 0) {
                    updateSubjectImageJobsAndStorage(prev => {
                        const next = { ...(prev || {}) };
                        completed.forEach((entityId) => {
                            delete next[String(entityId)];
                        });
                        return next;
                    });
                }
            } finally {
                subjectImageJobPollingRef.current = false;
            }
        };

        void pollOnce();
        const timer = setInterval(() => {
            void pollOnce();
        }, 2500);

        return () => {
            disposed = true;
            if (subjectImageJobPollTokenRef.current === pollToken) {
                subjectImageJobPollTokenRef.current += 1;
            }
            clearInterval(timer);
        };
    }, [SUBJECT_IMAGE_JOB_MAX_RUNNING_MS, SUBJECT_IMAGE_JOB_MAX_STATUS_FAILURES, SUBJECT_IMAGE_JOB_PERSIST_LOG_INTERVAL_MS, SUBJECT_IMAGE_JOB_PERSIST_WAIT_MS, applySubjectEntityImageLocally, clearLocalSubjectImageJobState, extractImageJobResultUrl, forceClearSubjectImageJob, isEphemeralProviderMediaUrl, loadAssets, onLog, projectId, refreshPersistedSubjectEntityImage, subjectImageJobs, t]);

    const openMediaPicker = (callback, context = {}) => {
        setPickerConfig({ isOpen: true, callback, context });
    };

    // Load entities - NOW FETCHES ALL and filters locally
    const loadEntities = useCallback(async () => {
        if (!projectId) return [];
        setEntityListLoading(true);
        try {
            const data = await fetchEntities(projectId, {
                include_project_null_episode: true,
            });
            const processedData = Array.isArray(data) ? data.map(item => {
                if (item.type === 'environment' && (item.name === '封面海报' || item.name_en === 'Cover Poster')) {
                    return { ...item, type: 'poster' };
                }
                return item;
            }) : [];
            setAllEntities(processedData);
            return processedData;
        } catch (e) {
            console.error(e);
            return [];
        } finally {
            setEntityListLoading(false);
        }
    }, [projectId]);

    const awaitShotGenerationEntities = useCallback(async () => {
        if (!projectId) return Array.isArray(entities) ? entities : [];
        if (Array.isArray(entities) && entities.length > 0 && !entityListLoading) {
            return entities;
        }
        const loaded = await loadEntities();
        if (Array.isArray(loaded) && loaded.length > 0) {
            return loaded;
        }
        return Array.isArray(entities) ? entities : [];
    }, [entities, entityListLoading, loadEntities, projectId]);

    useEffect(() => {
        loadEntities();
    }, [loadEntities]);

    useEffect(() => {
        setEntityEpisodeScope(currentEpisode?.id ? 'current' : 'all');
    }, [currentEpisode?.id]);

    const scopedEntities = useMemo(() => {
        const baseEntities = (allEntities || []);
        if (entityEpisodeScope !== 'current') {
            return baseEntities;
        }
        const currentEpisodeId = String(currentEpisode?.id || '').trim();
        if (!currentEpisodeId) {
            return baseEntities;
        }
        return baseEntities.filter((entity) => String(entity?.episode_id || '').trim() === currentEpisodeId);
    }, [allEntities, currentEpisode?.id, entityEpisodeScope]);

    // Local Filtering based on subTab + episode scope
    useEffect(() => {
        setEntities(scopedEntities.filter(e => e.type === subTab));
    }, [scopedEntities, subTab]);

    const subjectCategoryStats = useMemo(() => {
        return scopedEntities.reduce((stats, entity) => {
            const entityType = String(entity?.type || '').toLowerCase();
            if (Object.prototype.hasOwnProperty.call(stats, entityType)) {
                stats[entityType].total += 1;
                if (entity.image_url) {
                    stats[entityType].generated += 1;
                }
            }
            return stats;
        }, { 
            character: { total: 0, generated: 0 }, 
            environment: { total: 0, generated: 0 }, 
            prop: { total: 0, generated: 0 }, 
            poster: { total: 0, generated: 0 } 
        });
    }, [scopedEntities]);

    // Create Entity
    const [isAnalyzingEntity, setIsAnalyzingEntity] = useState(false);

    const handleAnalyzeEntity = async (entity) => {
        if (!entity || !entity.id || !entity.image_url) {
            alert("No entity or image selected.");
            return;
        }

        const formatEntityAnalysisError = (error) => {
            const detail = error?.response?.data?.detail;
            if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
                const parts = [
                    detail.message,
                    detail.code,
                    detail.stage,
                    (detail.provider || detail.model)
                        ? `provider=${detail.provider || 'unknown'} model=${detail.model || 'unknown'}`
                        : '',
                ].filter(Boolean);
                if (parts.length > 0) return parts.join(' | ');
                try {
                    return JSON.stringify(detail);
                } catch {
                    return error?.message || 'Unknown analysis error';
                }
            }
            return detail || error?.message || 'Unknown analysis error';
        };
        
        setIsAnalyzingEntity(true);
        if (onLog) onLog(`Analyzing image for subject ${entity.name} in background...`, "process");
        
        try {
            persistAnalyzingEntities({ ...analyzingEntities, [String(entity.id)]: { startedAt: Date.now(), initialAnalysisTime: getEntityAnalysisTime(entity) } });
            const updated = await analyzeEntityImage(entity.id, 'script_analysis', null, { background: true });
            if (updated) {
                persistAnalyzingEntities(prev => ({ ...prev, [String(entity.id)]: { startedAt: Date.now(), initialAnalysisTime: getEntityAnalysisTime(updated) } }));
            }
            setSelectedEntity(prev => (prev?.id === updated.id ? updated : prev));
            setViewingEntity(prev => (prev?.id === updated.id ? updated : prev));
            setEntities(prev => prev.map(e => String(e.id) === String(updated.id) ? updated : e));
            setAllEntities(prev => prev.map(e => String(e.id) === String(updated.id) ? updated : e));
            if (onLog) onLog("Subject analysis started in background.", "success");
            return updated;
        } catch (e) {
            console.error(e);
            alert("Analysis failed: " + formatEntityAnalysisError(e));
            if (onLog) onLog("Analysis failed.", "error");
            return null;
        } finally {
            setIsAnalyzingEntity(false);
        }
    };

    const collectAssetUrlTokens = useCallback((rawUrl) => {
        const tokens = new Set();
        const stableRaw = String(rawUrl || '').trim();
        if (!stableRaw) return tokens;

        const pushToken = (value) => {
            const stable = String(value || '').trim().toLowerCase();
            if (!stable) return;
            tokens.add(stable);
        };

        pushToken(stableRaw);

        let parsedPath = '';
        try {
            const parsed = new URL(stableRaw, window.location.origin);
            parsedPath = decodeURIComponent(String(parsed.pathname || '')).trim();
        } catch {
            try {
                parsedPath = decodeURIComponent(stableRaw).trim();
            } catch {
                parsedPath = stableRaw;
            }
        }

        if (!parsedPath) return tokens;

        pushToken(parsedPath);
        const stripped = parsedPath.replace(/^\/+/, '');
        pushToken(stripped);

        if (parsedPath.includes('/uploads/')) {
            const idx = parsedPath.indexOf('/uploads/');
            const tail = parsedPath.slice(idx + '/uploads/'.length);
            pushToken(tail);
            pushToken(`uploads/${tail}`);
        }

        if (stripped.startsWith('uploads/')) {
            pushToken(stripped.slice('uploads/'.length));
        }

        const segments = parsedPath.split('/').filter(Boolean);
        if (segments.length > 0) {
            pushToken(segments[segments.length - 1]);
        }

        return tokens;
    }, []);

    const buildUploadedImageTokenSet = useCallback(async () => {
        const tokenSet = new Set();
        const assetRows = await fetchAssets();
        const imageAssets = Array.isArray(assetRows) ? assetRows.filter((item) => String(item?.type || '').toLowerCase() === 'image') : [];
        imageAssets.forEach((asset) => {
            const meta = asset?.meta_info && typeof asset.meta_info === 'object' ? asset.meta_info : {};
            const source = String(meta?.source || '').trim().toLowerCase();
            if (source !== 'file_upload') return;
            const tokens = collectAssetUrlTokens(asset?.url);
            tokens.forEach((token) => tokenSet.add(token));
        });
        return tokenSet;
    }, [collectAssetUrlTokens]);

    const isUserUploadedEntityImage = useCallback((entity, uploadedTokenSet) => {
        if (!entity || !entity.id) return false;
        const imageUrl = String(entity?.image_url || '').trim();
        if (!imageUrl) return false;
        const tokenSet = uploadedTokenSet instanceof Set ? uploadedTokenSet : new Set();
        if (tokenSet.size === 0) return false;
        const tokens = collectAssetUrlTokens(imageUrl);
        for (const token of tokens) {
            if (tokenSet.has(token)) return true;
        }
        return false;
    }, [collectAssetUrlTokens]);

    const getEntityCustomAttributes = useCallback((entity) => {
        const raw = entity?.custom_attributes;
        if (!raw) return {};
        if (typeof raw === 'string') {
            try {
                const parsed = JSON.parse(raw);
                return parsed && typeof parsed === 'object' ? parsed : {};
            } catch {
                return {};
            }
        }
        return typeof raw === 'object' ? raw : {};
    }, []);

    const isEntityAnalyzed = useCallback((entity) => {
        const attrs = getEntityCustomAttributes(entity);
        const analysisResult = attrs?.analysis_result;
        if (!analysisResult) return false;

        if (typeof analysisResult === 'string') {
            return analysisResult.trim().length > 0;
        }

        if (typeof analysisResult !== 'object') {
            return false;
        }

        // As long as analysis_result is an object with keys (e.g. timestamp, content), it is considered analyzed.
        return Object.keys(analysisResult).length > 0;
    }, [getEntityCustomAttributes]);

    const handleBatchAnalyzeExistingSubjects = async () => {
        const runtimeSnapshot = getSubjectBatchSnapshot();
        if (runtimeSnapshot?.analyze?.running && runtimeSnapshot?.analyze?.scopeKey === subjectBatchScopeKey) {
            alert(t('批量提示词反推任务正在运行中，请稍候。', 'Batch prompt reverse task is already running.'));
            return;
        }

        if (runtimeSnapshot?.reconstruct?.running && runtimeSnapshot?.reconstruct?.scopeKey === subjectBatchScopeKey) {
            alert(t('批量参考生图任务正在运行中，请稍候。', 'Batch reference image generation task is already running.'));
            return;
        }

        if (isBatchReconstructingEntities) {
            alert(t('批量参考生图任务正在运行中，请稍候。', 'Batch reference image generation task is already running.'));
            return;
        }

        let uploadedImageTokens = new Set();
        try {
            uploadedImageTokens = await buildUploadedImageTokenSet();
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'Unknown error';
            alert(t(`读取上传资产失败：${detail}`, `Failed to load uploaded assets: ${detail}`));
            return;
        }

        const hasImageEntities = allEntities.filter(item => item?.id && String(item?.image_url || '').trim());
        const targets = hasImageEntities.filter((item) => isUserUploadedEntityImage(item, uploadedImageTokens));
        const skippedSystemCount = Math.max(0, hasImageEntities.length - targets.length);
        if (targets.length === 0) {
            alert(t('当前没有可分析的“用户上传图片”主体。系统生成图片将被自动跳过。', 'No user-uploaded subject images available for analysis. System-generated images are skipped.'));
            return;
        }

        const confirmed = await confirmUiMessage(t(
            `将批量提示词反推并反写 ${targets.length} 个“用户上传图片”主体信息 ${skippedSystemCount > 0 ? `（自动跳过系统生图 ${skippedSystemCount} 个）` : ''}，是否继续？`,
            `Run batch prompt reverse and write back metadata for ${targets.length} user-uploaded subject images${skippedSystemCount > 0 ? ` (skip ${skippedSystemCount} system-generated)` : ''}?`
        ));
        if (!confirmed) return;

        subjectBatchAnalyzeStopRequestedRef.current = false;
        const batchSessionId = `subject-analyze-batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        subjectBatchAnalyzeSessionRef.current = batchSessionId;

        updateAnalyzeBatchRuntimeState(true, { current: 0, total: targets.length, status: t('准备开始...', 'Preparing...') });

        let successCount = 0;
        let failedCount = 0;
        let processedCount = 0;

        try {
            const shouldStopBatchAnalyze = () => (
                subjectBatchAnalyzeSessionRef.current !== batchSessionId
                || subjectBatchAnalyzeStopRequestedRef.current
            );
            let nextTargetIndex = 0;
            const workerCount = Math.max(1, Math.min(SUBJECT_BATCH_PARALLEL_LIMIT, targets.length));

            const runAnalyzeWorker = async () => {
                while (!shouldStopBatchAnalyze()) {
                    const targetIndex = nextTargetIndex;
                    nextTargetIndex += 1;
                    const entity = targets[targetIndex];
                    if (!entity) return;

                    const entityLabel = entity?.name || entity?.name_en || entity?.id;
                    updateAnalyzeBatchRuntimeState(true, {
                        current: Math.min(processedCount + 1, targets.length),
                        total: targets.length,
                        status: t(`AI品控查阅中：`, `Analyzing: ${entityLabel}`),
                    });

                    try {
                        const updated = await analyzeEntityImage(entity.id, 'script_analysis');
                        if (shouldStopBatchAnalyze()) {
                            continue;
                        }
                        setAllEntities(prev => prev.map(e => String(e.id) === String(updated.id) ? updated : e));
                        setEntities(prev => prev.map(e => String(e.id) === String(updated.id) ? updated : e));
                        setViewingEntity(prev => (prev?.id === updated.id ? updated : prev));
                        successCount += 1;
                    } catch (error) {
                        if (shouldStopBatchAnalyze()) {
                            continue;
                        }
                        failedCount += 1;
                        if (onLog) {
                            onLog(
                                t(
                                    `批量提示词反推失败：${entityLabel} - ${error?.response?.data?.detail || error?.message || 'Unknown error'}`,
                                    `Batch prompt reverse failed: ${entityLabel} - ${error?.response?.data?.detail || error?.message || 'Unknown error'}`
                                ),
                                'error'
                            );
                        }
                    } finally {
                        processedCount += 1;
                        updateAnalyzeBatchRuntimeState(true, {
                            current: processedCount,
                            total: targets.length,
                            status: t(`已处理 ${processedCount}/${targets.length}`, `Processed ${processedCount}/${targets.length}`),
                        });
                    }
                }
            };

            await Promise.allSettled(Array.from({ length: workerCount }, () => runAnalyzeWorker()));

            if (subjectBatchAnalyzeSessionRef.current !== batchSessionId || subjectBatchAnalyzeStopRequestedRef.current) {
                const stoppedSummary = t(
                    `批量提示词反推已停止：成功 ${successCount}，失败 ${failedCount}`,
                    `Batch prompt reverse stopped: ${successCount} succeeded, ${failedCount} failed`
                );
                if (onLog) onLog(stoppedSummary, 'warning');
                alert(stoppedSummary);
                return;
            }

            const summary = t(
                `批量提示词反推完成（仅用户上传图片）：成功 ${successCount}，失败 ${failedCount}${skippedSystemCount > 0 ? `，跳过系统生成 ${skippedSystemCount}` : ''}`,
                `Batch prompt reverse complete (uploaded images only): ${successCount} succeeded, ${failedCount} failed${skippedSystemCount > 0 ? `, skipped ${skippedSystemCount} system-generated` : ''}`
            );
            if (onLog) onLog(summary, failedCount > 0 ? 'warning' : 'success');
            alert(summary);
        } finally {
            if (subjectBatchAnalyzeSessionRef.current === batchSessionId) {
                subjectBatchAnalyzeSessionRef.current = '';
            }
            subjectBatchAnalyzeStopRequestedRef.current = false;
            updateAnalyzeBatchRuntimeState(false, null);
        }
    };

    const reconstructEntityAssetCore = useCallback(async (entity, onProgress, runtimeOptions = null) => {
        const progress = typeof onProgress === 'function' ? onProgress : () => {};
        const shouldStop = typeof runtimeOptions?.shouldStop === 'function' ? runtimeOptions.shouldStop : () => false;
        const onJobCreated = typeof runtimeOptions?.onJobCreated === 'function' ? runtimeOptions.onJobCreated : null;

        if (shouldStop()) {
            throw new Error('__subject_batch_stop__');
        }

        const setStep = (step, zh, en, percent) => {
            progress({ step, label: t(zh, en), percent: Number(percent || 0) });
        };

        setStep('analyzing', '正在分析当前图片...', 'Analyzing current image...', 20);
        const analyzed = await analyzeEntityImage(entity.id, 'script_analysis');
        if (shouldStop()) {
            throw new Error('__subject_batch_stop__');
        }
        setViewingEntity(prev => (prev?.id === analyzed.id ? analyzed : prev));
        setEntities(prev => prev.map(e => String(e.id) === String(analyzed.id) ? analyzed : e));
        setAllEntities(prev => prev.map(e => String(e.id) === String(analyzed.id) ? analyzed : e));

        setStep('prompt', '正在整理新的提示词...', 'Refining prompt...', 55);

        const epInfo = currentEpisode?.episode_info || {};
        const preferredImageSize = getEpisodePreferredImageSize(epInfo);
        let rawPrompt = getEntityPromptByLang(analyzed, resolvedPromptSubmitLang);
        if (!rawPrompt && analyzed.description) {
            const match = analyzed.description.match(/Prompt:\s*(.*)/);
            if (match && match[1]) {
                rawPrompt = match[1].trim();
            }
        }

        let finalPrompt = processPrompt(rawPrompt, epInfo, allEntities) || rawPrompt || '';
        const infoSource = epInfo.e_global_info || epInfo;
        const suffixes = [
            infoSource?.type,
            infoSource?.lighting,
            infoSource?.tech_params?.visual_standard?.quality,
        ].filter(Boolean);
        if (suffixes.length > 0) {
            finalPrompt = `${finalPrompt}${finalPrompt ? ', ' : ''}${suffixes.join(', ')}`;
        }
        finalPrompt = prependEntityGlobalStyleToPromptHead(finalPrompt, { injectIfMissing: true });

        const primaryRefUrl = String(analyzed?.image_url || entity?.image_url || '').trim();
        const depUrls = [];
        const deps = parseVisualDependencies(analyzed.visual_dependencies);
        deps.forEach(dep => {
            const target = resolveDependencyEntity(dep, allEntities);
            if (target?.image_url) depUrls.push(target.image_url);
        });
        const combinedRefs = [primaryRefUrl, ...depUrls]
            .map(url => String(url || '').trim())
            .filter(Boolean);
        const uniqueRefs = [...new Set(combinedRefs)];

        if (shouldStop()) {
            throw new Error('__subject_batch_stop__');
        }

        setStep('generating', '正在根据新提示词生成图片...', 'Generating image with new prompt...', 80);
        const asset = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
            function_name: (deps && deps.length > 0) ? 'generate_subjects_i2i' : 'generate_subjects_t2i',
            project_id: projectId,
            episode_id: currentEpisode?.id,
            entity_id: analyzed?.id,
            entity_name: analyzed?.name || analyzed?.name_en,
            subject_name: analyzed?.name || analyzed?.name_en,
            subject_type: analyzed?.type,
            entity_type: analyzed?.type,
            prompt_language: resolvedPromptSubmitLang,
            asset_type: 'subject',
            ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
            negative_prompt: buildEntityNegativePrompt(rawPrompt, analyzed || entity, allEntities),
            ...(onJobCreated ? { on_job_created: onJobCreated } : {})
        });

        if (shouldStop()) {
            throw new Error('__subject_batch_stop__');
        }

        const generatedAssetUrl = extractImageJobResultUrl(asset);
        if (!generatedAssetUrl) {
            throw new Error(t('生成结果缺少图片地址', 'Generated result missing image URL'));
        }

        let resolvedAssetUrl = String(generatedAssetUrl || '').trim();
        if (isEphemeralProviderMediaUrl(resolvedAssetUrl)) {
            if (onLog) {
                onLog(
                    t(
                        `主体重构返回了临时图片地址，正在等待稳定图片入库：${analyzed?.name || analyzed?.name_en || analyzed?.id}`,
                        `Subject reconstruction returned a temporary image URL; waiting for durable image persistence: ${analyzed?.name || analyzed?.name_en || analyzed?.id}`
                    ),
                    'process'
                );
            }
            resolvedAssetUrl = await awaitPersistedSubjectEntityImage(analyzed.id, {
                initialUrl: resolvedAssetUrl,
                entityName: analyzed?.name || analyzed?.name_en || analyzed?.id,
            });
            if (!resolvedAssetUrl) {
                throw new Error(t('等待主体稳定图片地址超时', 'Timed out waiting for durable subject image URL'));
            }
        }

        await updateEntity(analyzed.id, { image_url: resolvedAssetUrl });
        const updatedEntity = { ...analyzed, image_url: resolvedAssetUrl };
        applySubjectEntityImageLocally(analyzed.id, resolvedAssetUrl);

        setStep('done', '重构完成', 'Refactor completed', 100);
        return updatedEntity;
    }, [allEntities, awaitPersistedSubjectEntityImage, currentEpisode?.episode_info, currentEpisode?.id, getEntityPromptByLang, isEphemeralProviderMediaUrl, onLog, prependEntityGlobalStyleToPromptHead, projectId, resolvedPromptSubmitLang, t]);

    const handleBatchAnalyzeAndReconstructSubjects = async () => {
        const runtimeSnapshot = getSubjectBatchSnapshot();
        if (
            (runtimeSnapshot?.generate?.running && runtimeSnapshot?.generate?.scopeKey === subjectBatchScopeKey) ||
            (runtimeSnapshot?.analyze?.running && runtimeSnapshot?.analyze?.scopeKey === subjectBatchScopeKey) ||
            (runtimeSnapshot?.reconstruct?.running && runtimeSnapshot?.reconstruct?.scopeKey === subjectBatchScopeKey) ||
            isBatchGeneratingEntities ||
            isBatchAnalyzingEntities ||
            isReconstructingEntity
        ) {
            alert(t('有其他批量任务正在运行，请稍后。', 'Another batch task is running. Please wait.'));
            return;
        }

        let uploadedImageTokens = new Set();
        try {
            uploadedImageTokens = await buildUploadedImageTokenSet();
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'Unknown error';
            alert(t(`读取上传资产失败：${detail}`, `Failed to load uploaded assets: ${detail}`));
            return;
        }

        const hasImageEntities = allEntities.filter(item => item?.id && String(item?.image_url || '').trim());
        const targets = hasImageEntities.filter((item) => isUserUploadedEntityImage(item, uploadedImageTokens));
        const skippedSystemCount = Math.max(0, hasImageEntities.length - targets.length);
        if (targets.length === 0) {
            alert(t('当前没有可执行“批量参考生图”的用户上传图片主体。', 'No user-uploaded subject images available for batch reference image generation.'));
            return;
        }

        const confirmMessageZh = skippedSystemCount > 0
            ? `将对 ${targets.length} 个“用户上传图片”主体执行“批量参考生图”（自动跳过系统生成 ${skippedSystemCount} 个），是否继续？`
            : `将对 ${targets.length} 个“用户上传图片”主体执行“批量参考生图”，是否继续？`;
        const confirmMessageEn = skippedSystemCount > 0
            ? `Run batch reference image generation for ${targets.length} user-uploaded subject images (skip ${skippedSystemCount} system-generated)?`
            : `Run batch reference image generation for ${targets.length} user-uploaded subject images?`;
        const confirmed = await confirmUiMessage(t(confirmMessageZh, confirmMessageEn));
        if (!confirmed) return;

        subjectBatchReconstructStopRequestedRef.current = false;
        const batchSessionId = `subject-reference-batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        subjectBatchReconstructSessionRef.current = batchSessionId;

        updateReconstructBatchRuntimeState(true, { current: 0, total: targets.length, status: t('准备开始...', 'Preparing...') });

        let successCount = 0;
        let failedCount = 0;
        let processedCount = 0;

        try {
            const shouldStopBatchReconstruct = () => (
                subjectBatchReconstructSessionRef.current !== batchSessionId
                || subjectBatchReconstructStopRequestedRef.current
            );
            let nextTargetIndex = 0;
            const workerCount = Math.max(1, Math.min(SUBJECT_BATCH_PARALLEL_LIMIT, targets.length));

            const runReconstructWorker = async () => {
                while (!shouldStopBatchReconstruct()) {
                    const targetIndex = nextTargetIndex;
                    nextTargetIndex += 1;
                    const entity = targets[targetIndex];
                    if (!entity) return;

                    const entityLabel = entity?.name || entity?.name_en || entity?.id;
                    updateReconstructBatchRuntimeState(true, {
                        current: Math.min(processedCount + 1, targets.length),
                        total: targets.length,
                        status: t(
                            `处理中：${entityLabel}`,
                            `Processing: ${entityLabel}`
                        ),
                    });

                    let createdJobId = '';
                    try {
                        const updated = await reconstructEntityAssetCore(entity, null, {
                            shouldStop: shouldStopBatchReconstruct,
                            onJobCreated: (jobId) => {
                                const stableJobId = String(jobId || '').trim();
                                if (!stableJobId) return;
                                createdJobId = stableJobId;
                                if (shouldStopBatchReconstruct()) {
                                    void stopGenerationJob('image', stableJobId, { force: true });
                                    return;
                                }
                                trackSubjectBatchImageJob('reconstruct', entity, stableJobId);
                            },
                        });

                        if (shouldStopBatchReconstruct()) {
                            continue;
                        }

                        if (!updated?.id) {
                            throw new Error('Reconstructed subject result missing entity payload');
                        }
                        successCount += 1;
                    } catch (error) {
                        if (shouldStopBatchReconstruct() || isSubjectBatchStopSignal(error)) {
                            continue;
                        }
                        failedCount += 1;
                        if (onLog) {
                            onLog(
                                t(
                                    `批量参考生图失败：${entityLabel} - ${error?.response?.data?.detail || error?.message || 'Unknown error'}`,
                                    `Batch reference image generation failed: ${entityLabel} - ${error?.response?.data?.detail || error?.message || 'Unknown error'}`
                                ),
                                'error'
                            );
                        }
                    } finally {
                        if (createdJobId) {
                            untrackSubjectBatchImageJob('reconstruct', entity?.id);
                        }
                        processedCount += 1;
                        updateReconstructBatchRuntimeState(true, {
                            current: processedCount,
                            total: targets.length,
                            status: t(`已处理 ${processedCount}/${targets.length}`, `Processed ${processedCount}/${targets.length}`),
                        });
                    }
                }
            };

            await Promise.allSettled(Array.from({ length: workerCount }, () => runReconstructWorker()));

            if (subjectBatchReconstructSessionRef.current !== batchSessionId || subjectBatchReconstructStopRequestedRef.current) {
                const stoppedSummary = t(
                    `批量参考生图已停止：成功 ${successCount}，失败 ${failedCount}`,
                    `Batch reference image generation stopped: ${successCount} succeeded, ${failedCount} failed`
                );
                if (onLog) onLog(stoppedSummary, 'warning');
                alert(stoppedSummary);
                return;
            }

            const summary = t(
                `批量参考生图完成（仅用户上传图片）：成功 ${successCount}，失败 ${failedCount}${skippedSystemCount > 0 ? `，跳过系统生成 ${skippedSystemCount}` : ''}`,
                `Batch reference image generation complete (uploaded images only): ${successCount} succeeded, ${failedCount} failed${skippedSystemCount > 0 ? `, skipped ${skippedSystemCount} system-generated` : ''}`
            );
            if (onLog) onLog(summary, failedCount > 0 ? 'warning' : 'success');
            alert(summary);
        } finally {
            if (subjectBatchReconstructSessionRef.current === batchSessionId) {
                subjectBatchReconstructSessionRef.current = '';
            }
            subjectBatchReconstructActiveJobsRef.current.clear();
            updateSubjectImageJobsAndStorage(prev => {
                const next = { ...(prev || {}) };
                targets.forEach((entity) => {
                    const stableEntityId = String(entity?.id || '').trim();
                    if (!stableEntityId) return;
                    const existing = next[stableEntityId];
                    if (!existing) return;
                    if (String(existing?.jobKind || 'reconstruct').trim() !== 'reconstruct') return;
                    delete next[stableEntityId];
                });
                return next;
            });
            setStoppingSubjectImageJobs(prev => {
                const next = { ...(prev || {}) };
                targets.forEach((entity) => {
                    const stableEntityId = String(entity?.id || '').trim();
                    if (!stableEntityId) return;
                    delete next[stableEntityId];
                });
                return next;
            });
            clearPendingSubjectBatchImagePlaceholders();
            subjectBatchReconstructStopRequestedRef.current = false;
            updateReconstructBatchRuntimeState(false, null);
        }
    };

    const handleReconstructEntityAsset = async (entity) => {
        if (!entity || !entity.id || !entity.image_url) {
            alert(t('请先为主体选择一张现有图片再重构。', 'Please select an existing subject image before refactoring.'));
            return;
        }

        if (!await confirmUiMessage(t(
            `将基于当前图片分析并重写提示词，然后重新生成 ${entity.name || '该主体'} 的图片。是否继续？`,
            `This will analyze the current image, rewrite prompt, and regenerate image for ${entity.name || 'this subject'}. Continue?`
        ))) return;

        setIsReconstructingEntity(true);
        setReconstructProgress({ step: 'analyzing', label: t('正在分析当前图片...', 'Analyzing current image...'), percent: 20 });
        if (onLog) onLog(`Refactoring subject asset: ${entity.name || entity.name_en || entity.id}`, 'process');

        try {
            await reconstructEntityAssetCore(entity, (progress) => {
                setReconstructProgress(progress);
            });
            if (onLog) onLog(`Subject asset refactor completed: ${entity.name || entity.name_en || entity.id}`, 'success');
        } catch (e) {
            console.error(e);
            alert(t('资产重构失败：', 'Asset refactor failed: ') + (e.response?.data?.detail || e.message));
            if (onLog) onLog(`Subject asset refactor failed: ${entity.name || entity.name_en || entity.id}`, 'error');
        } finally {
            setIsReconstructingEntity(false);
            setTimeout(() => setReconstructProgress(null), 1200);
        }
    };

    const handleCreate = async () => {
        setCreateMode('manual');
        setCreateMode('manual');
        // Create a temporary "New Entity" state to open the modal in "Create Mode"
        // We use a special ID 'new' to signal that this is not yet in DB
        setRefImage(null);
        setViewingEntity({
            id: 'new',
            name: '',
            type: subTab,
            description: '',
            anchor_description: '',
            generation_prompt_en: '',
            generation_prompt_cn: '',
            appearance_cn: '',
            clothing: '',
            visual_params: '',
            atmosphere: '',
            narrative_description: '',
            name_en: '',
            role: '',
            archetype: '',
            gender: '',
            video_url: '',
            audio_url: '',
        });
    };

    // Helper: Update Field (Sync to DB if not new)
    const handleFieldUpdate = (field, value) => {
        if (!viewingEntity) return;
        
        // Always update local viewing state
        setViewingEntity(prev => ({ ...prev, [field]: value }));

        // Only sync to server if it's an existing entity
        if (viewingEntity.id !== 'new') {
            const updated = { ...viewingEntity, [field]: value };
            
            // Optimistic Update
            setEntities(prev => prev.map(ent => String(ent.id) === String(updated.id) ? updated : ent));
            setAllEntities(prev => prev.map(ent => String(ent.id) === String(updated.id) ? updated : ent));
            
            updateEntity(updated.id, { [field]: value }).catch(console.error);
        }
    };

    const ENTITY_MEDIA_REF_CONFIG = useMemo(() => ({
        video: {
            field: 'video_url',
            accept: 'video/*',
            desiredAssetType: 'video',
            label: t('视频参考', 'Video Ref'),
            empty: t('暂无视频参考', 'No video reference yet'),
            placeholder: t('粘贴视频链接...', 'Paste video URL...'),
        },
        audio: {
            field: 'audio_url',
            accept: 'audio/*',
            desiredAssetType: 'audio',
            label: t('音频参考', 'Audio Ref'),
            empty: t('暂无音频参考', 'No audio reference yet'),
            placeholder: t('粘贴音频链接...', 'Paste audio URL...'),
        },
    }), [t]);

    const handlePickEntityMediaRefFromLibrary = useCallback((kind) => {
        const cfg = ENTITY_MEDIA_REF_CONFIG[kind];
        if (!cfg) return;
        openMediaPicker((url) => {
            const stable = String(url || '').trim();
            if (!stable) return;
            handleFieldUpdate(cfg.field, stable);
        }, {
            entityId: viewingEntity?.id,
            desiredAssetType: cfg.desiredAssetType,
            lockAssetType: false,
            allowMultiSelect: false,
            disableShotFilter: true,
            defaultSecondaryKind: 'entity',
        });
    }, [ENTITY_MEDIA_REF_CONFIG, handleFieldUpdate, openMediaPicker, viewingEntity?.id]);

    const handleUploadEntityMediaRef = useCallback(async (kind, file) => {
        if (!file) return;
        const cfg = ENTITY_MEDIA_REF_CONFIG[kind];
        if (!cfg) return;
        setEntityMediaRefUploading(true);
        try {
            const asset = await uploadAsset(file);
            const stable = String(asset?.url || '').trim();
            if (stable) {
                handleFieldUpdate(cfg.field, stable);
            }
        } catch (e) {
            console.error(e);
            alert(t('上传参考文件失败', 'Failed to upload reference file'));
        } finally {
            setEntityMediaRefUploading(false);
        }
    }, [ENTITY_MEDIA_REF_CONFIG, handleFieldUpdate, t]);

    const persistEntityRefAudioPrompt = useCallback((nextPrompt) => {
        const stablePrompt = String(nextPrompt || '');
        setEntityRefAudioPrompt(stablePrompt);
        const currentEntityKey = String(viewingEntity?.id || '').trim();
        if (!currentEntityKey) return;
        setEntityRefAudioPromptByEntity((prev) => ({ ...prev, [currentEntityKey]: stablePrompt }));
    }, [viewingEntity?.id]);

    const persistEntityRefAudioProfile = useCallback((nextProfile) => {
        const currentEntityKey = String(viewingEntity?.id || '').trim();
        if (!currentEntityKey) return;
        setEntityRefAudioProfileByEntity((prev) => ({
            ...prev,
            [currentEntityKey]: {
                tone: String(nextProfile?.tone || '').trim(),
                pace: String(nextProfile?.pace || '').trim(),
                emotion: String(nextProfile?.emotion || '').trim(),
            },
        }));
    }, [viewingEntity?.id]);

    const handleRegenerateEntityRefAudioPrompt = useCallback(() => {
        const nextProfile = {
            tone: String(entityRefAudioTone || '').trim(),
            pace: String(entityRefAudioPace || '').trim(),
            emotion: String(entityRefAudioEmotion || '').trim(),
        };
        persistEntityRefAudioProfile(nextProfile);
        const nextPrompt = buildDefaultEntityRefAudioPrompt(viewingEntity, nextProfile);
        persistEntityRefAudioPrompt(nextPrompt);
        showSubjectNotification(t('已按当前配音要素重建参考文案。', 'Reference prompt rebuilt from current dubbing parameters.'), 'success');
    }, [buildDefaultEntityRefAudioPrompt, entityRefAudioEmotion, entityRefAudioPace, entityRefAudioTone, persistEntityRefAudioProfile, persistEntityRefAudioPrompt, showSubjectNotification, t, viewingEntity]);

    const extractGeneratedAudioUrl = useCallback((payload) => {
        const visited = new Set();
        const queue = [payload];
        const directKeys = ['url', 'audio_url', 'audioUrl', 'result_url', 'resultUrl', 'voice_url', 'file_url', 'fileUrl'];

        while (queue.length > 0) {
            const current = queue.shift();
            if (!current || typeof current !== 'object') continue;
            if (visited.has(current)) continue;
            visited.add(current);

            for (const key of directKeys) {
                const candidate = String(current?.[key] || '').trim();
                if (candidate) return candidate;
            }

            const candidateList = Array.isArray(current?.urls) ? current.urls : [];
            for (const item of candidateList) {
                const candidate = String(item || '').trim();
                if (candidate) return candidate;
            }

            const nestedKeys = ['data', 'result', 'output', 'metadata', 'raw', 'payload'];
            for (const key of nestedKeys) {
                const next = current?.[key];
                if (next && typeof next === 'object') queue.push(next);
            }
        }
        return '';
    }, []);

    const handleGenerateEntityReferenceAudio = useCallback(async (sourceTab = 'audio') => {
        const stablePrompt = String(entityRefAudioPrompt || '').trim();
        if (!stablePrompt) {
            alert(t('请先输入参考音频文案。', 'Please enter reference audio text first.'));
            return;
        }

        const stableTab = sourceTab === 'video' ? 'video' : 'audio';
        const functionName = String(entityRefAudioFunctionByTab?.[stableTab] || '').trim() || (stableTab === 'video' ? 'generate_entity_reference_audio_video' : 'generate_entity_reference_audio_audio');
        const selectedSystemApiId = Number(localStorage.getItem(`func_api_${functionName}`) || 0) || null;

        setIsGeneratingEntityRefAudio(true);
        try {
            const result = await generateVoice(stablePrompt, null, null, {
                function_name: functionName,
                ...(selectedSystemApiId ? { system_api_id: selectedSystemApiId } : {}),
                ...(projectId ? { project_id: projectId } : {}),
            });

            const nextAudioUrl = extractGeneratedAudioUrl(result);
            if (!nextAudioUrl) {
                throw new Error(t('返回结果中未找到音频链接', 'No audio URL found in response'));
            }

            handleFieldUpdate('audio_url', nextAudioUrl);
            showSubjectNotification(t('参考音频生成成功，已自动回填。', 'Reference audio generated and saved to audio URL.'), 'success');
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || String(e);
            showSubjectNotification(`${t('参考音频生成失败：', 'Reference audio generation failed: ')}${detail}`, 'error');
        } finally {
            setIsGeneratingEntityRefAudio(false);
        }
    }, [entityRefAudioFunctionByTab, entityRefAudioPrompt, extractGeneratedAudioUrl, handleFieldUpdate, projectId, showSubjectNotification, t]);

    // Helper: Commit Create (Save manually)
    const handleCommitCreate = async () => {
        if (!viewingEntity || !viewingEntity.name) {
            alert("Name is required");
            return;
        }
        try {
            // Must clone and remove the 'new' ID
            const payload = { ...viewingEntity };
            delete payload.id; 
            payload.episode_id = currentEpisode?.id || undefined;
            
            const newEnt = await createEntity(projectId, payload);
            
            // Update local state with real object (and real ID)
            setAllEntities(prev => [...prev, newEnt]);
            
            // If current tab matches, show it
            if (newEnt.type === subTab) {
                setEntities(prev => [...prev, newEnt]);
            }
            
            // Switch view to the real entity (no longer 'new')
            setViewingEntity(newEnt);
            alert("Subject Created Successfully!");
        } catch (e) {
            console.error(e);
            alert("Failed to create subject: " + e.message);
        }
    };


    // Delete Entity
    const handleDeleteEntity = async (e, entity) => {
        e.stopPropagation();
        if (!await confirmUiMessage(`Are you sure you want to delete ${entity.name}?`)) return;
        try {
            await deleteEntity(entity.id);
            loadEntities();
            if (viewingEntity?.id === entity.id) setViewingEntity(null);
        } catch (e) {
            console.error(e);
            alert(`Failed to delete entity: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleDeleteAllEntities = async () => {
        if (!await confirmUiMessage("WARNING: This will delete ALL subjects/entities in this library. This action cannot be undone. Are you sure?")) return;
        try {
            await deleteAllEntities(projectId);
            loadEntities();
            setViewingEntity(null);
            setRefImage(null);
        } catch (e) {
            console.error(e);
            alert(`Failed to delete all entities: ${e?.message || 'Unknown error'}`);
        }
    };

    function inferPreferredAssetImageType(entity) {
        const entityId = String(entity?.id || '').trim();
        const entityFromTable = entityId
            ? (allEntities || []).find((item) => String(item?.id || '').trim() === entityId)
            : null;

        const candidates = [
            entityFromTable?.type,
            entityFromTable?.entity_type,
            entityFromTable?.subject_type,
            entity?.type,
            entity?.entity_type,
            entity?.subject_type,
            entity?.category,
            subTab,
        ];
        for (const candidate of candidates) {
            const normalized = normalizeEntityAssetType(candidate || '');
            if (normalized !== 'all') return normalized;
        }
        return 'all';
    }
    
    // Open Image Modal
    const handleOpenImageModal = (entity, defaultTab = 'library') => {
        if (defaultTab !== 'generate' && isSubjectImageActionLocked(entity)) {
            notifySubjectImageActionLocked(entity);
            return;
        }
        setSelectedEntity(entity);
        setImageModalTab(defaultTab); // This might cause render before prompt is set?
        setImageSelectAction('direct_use');
        setTempPromptSubmitLang('');
        setShowPromptLangMenu(false);
        setAssetKeyword('');
        const currentEpisodeId = String(currentEpisode?.id || entity?.episode_id || '').trim();
        setAssetEpisodeFilter(currentEpisodeId ? `ep:${currentEpisodeId}` : 'all');
        const preferredType = inferPreferredAssetImageType(entity);
        setAssetImageTypeFilter(preferredType !== 'all' ? preferredType : 'all');
        if (onLog) {
            const entityFromTable = (allEntities || []).find((item) => String(item?.id || '').trim() === String(entity?.id || '').trim());
            onLog(
                `Asset picker defaults: entity=${entity?.name || entity?.name_en || entity?.id}, raw_type=${String(entity?.type || entity?.entity_type || entity?.subject_type || '').trim() || 'N/A'}, table_type=${String(entityFromTable?.type || entityFromTable?.entity_type || entityFromTable?.subject_type || '').trim() || 'N/A'}, preferred_type=${preferredType}, episode_filter=${currentEpisodeId ? `ep:${currentEpisodeId}` : 'all'}`,
                'process'
            );
        }
        setAssetNameFilter('');
        setIncludeHistoricalEpisodeAssets(false);
        const currentProjectKey = String(projectId || '').trim();
        setAssetProjectFilter(currentProjectKey || 'all');
        
        const cnPrompt = buildProcessedEntityPrompt(entity, 'cn');
        const enPrompt = buildProcessedEntityPrompt(entity, 'en');

        setPromptDrafts({ cn: cnPrompt, en: enPrompt });
        setPrompt(cnPrompt);
        setShowImageModal(true); // Show AFTER setting everything

        setRefImage(null);
        setRefSelectionMode(null); 
        loadAssets({ includeHistoricalEpisodeAssets: false });
    };

    useEffect(() => {
        if (!showImageModal || imageModalTab !== 'generate') return;
        const currentDraft = String(promptDrafts?.cn || '').trim();
        setPrompt(currentDraft);
    }, [imageModalTab, showImageModal, promptDrafts]);

    useEffect(() => {
        if (!showImageModal) return;
        if (!selectedEntity?.id) return;
        if (!isSubjectImageActionLocked(selectedEntity)) return;
        if (imageModalTab === 'generate') return;
        setImageModalTab('generate');
    }, [imageModalTab, isSubjectImageActionLocked, selectedEntity, showImageModal]);

    useEffect(() => {
        if (!showImageModal) return;
        loadAssets();
    }, [showImageModal, loadAssets]);

    const activeAssetLibraryEntity = useMemo(() => {
        if (showImageModal) return selectedEntity;
        if (refSelectionMode === 'assets') return viewingEntity;
        return selectedEntity || viewingEntity || null;
    }, [refSelectionMode, selectedEntity, showImageModal, viewingEntity]);

    useEffect(() => {
        if (!showImageModal && refSelectionMode !== 'assets') {
            assetLibraryContextResetRef.current = '';
            return;
        }
        const currentEpisodeId = String(currentEpisode?.id || activeAssetLibraryEntity?.episode_id || '').trim();
        const resetKey = [
            showImageModal ? 'image-modal' : 'design-ref-assets',
            String(activeAssetLibraryEntity?.id || '').trim(),
            currentEpisodeId,
        ].join('::');
        if (assetLibraryContextResetRef.current === resetKey) return;
        assetLibraryContextResetRef.current = resetKey;
        
        const preferredType = activeAssetLibraryEntity ? (String(activeAssetLibraryEntity?.type || '').toLowerCase() === 'environment' ? 'environment' : (String(activeAssetLibraryEntity?.type || '').toLowerCase() === 'prop' ? 'prop' : 'character')) : 'all';
        const desiredType = preferredType !== 'all' ? preferredType : 'all';

        setAssetEpisodeFilter(currentEpisodeId ? `ep:${currentEpisodeId}` : 'all');
        setAssetImageTypeFilter(desiredType);
        setIncludeHistoricalEpisodeAssets(false);
        setAssetNameFilter('');
        loadAssets({ includeHistoricalEpisodeAssets: false });
    }, [activeAssetLibraryEntity, allEntities, currentEpisode?.id, refSelectionMode, showImageModal, loadAssets, subTab]);

    useEffect(() => {
        if (refSelectionMode !== 'assets') return;
        if (assets.length > 0) return; // already loaded
        loadAssets();
    }, [refSelectionMode, assets.length, loadAssets]);

    const getAssetMeta = useCallback((asset) => {
        if (!asset || typeof asset !== 'object') return {};
        let meta = asset.meta_info;
        for (let i = 0; i < 3; i += 1) {
            if (typeof meta !== 'string') break;
            const text = meta.trim();
            if (!text) {
                meta = {};
                break;
            }
            try {
                meta = JSON.parse(text);
            } catch {
                break;
            }
        }
        if (!meta || typeof meta !== 'object' || Array.isArray(meta)) return {};

        const merged = {};
        const visit = (node) => {
            if (!node || typeof node !== 'object' || Array.isArray(node)) return;
            Object.entries(node).forEach(([k, v]) => {
                if (v === null || v === undefined) return;
                if (typeof v === 'object' && !Array.isArray(v)) {
                    visit(v);
                    return;
                }
                if (!(k in merged)) merged[k] = v;
            });
        };
        visit(meta);
        return merged;
    }, []);

    const pickAssetMetaValue = useCallback((meta, keys = []) => {
        if (!meta || typeof meta !== 'object') return '';
        const toKey = (value) => String(value || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '');
        const lookup = {};
        Object.entries(meta).forEach(([k, v]) => {
            if (v === null || v === undefined) return;
            lookup[toKey(k)] = v;
        });
        for (const key of keys) {
            const stable = toKey(key);
            if (!stable) continue;
            const raw = lookup[stable];
            const text = String(raw || '').trim();
            if (!text) continue;
            if (['null', 'undefined', 'nan'].includes(text.toLowerCase())) continue;
            return text;
        }
        return '';
    }, []);

    const normalizeEntityAssetType = useCallback((value) => {
        const stable = String(value || '').trim().toLowerCase();
        if (!stable) return 'all';
        if (
            ['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(stable)
            || stable.includes('char')
            || stable.includes('role')
            || stable.includes('角色')
            || stable.includes('人物')
        ) return 'character';
        if (
            ['prop', 'props', '道具', '物件'].includes(stable)
            || stable.includes('prop')
            || stable.includes('道具')
            || stable.includes('物件')
        ) return 'prop';
        if (
            ['environment', 'environments', 'scene', 'scenes', 'poster', '背景', '场景', '环境', '封面'].includes(stable)
            || stable.includes('env')
            || stable.includes('scene')
            || stable.includes('poster')
            || stable.includes('背景')
            || stable.includes('场景')
            || stable.includes('环境')
            || stable.includes('封面')
        ) return 'environment';
        return 'all';
    }, []);

    const isImageAssetType = useCallback((value) => {
        const stable = String(value || '').trim().toLowerCase();
        if (!stable) return false;
        return stable === 'image'
            || stable.includes('image')
            || stable.includes('frame')
            || stable.includes('photo');
    }, []);

    const getAssetProjectId = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const idVal = pickAssetMetaValue(meta, ['project_id', 'projectId', 'owner_project_id', 'ownerProjectId']) || asset?.project_id;
        return String(idVal || '').trim();
    }, [getAssetMeta, pickAssetMetaValue]);

    const getAssetProjectLabel = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const projectId = String(pickAssetMetaValue(meta, ['project_id', 'projectId', 'owner_project_id', 'ownerProjectId']) || '').trim();
        const projectTitle = String(pickAssetMetaValue(meta, ['project_title', 'projectTitle', 'owner_project_title', 'ownerProjectTitle']) || '').trim();
        if (projectTitle && projectId) return `${projectTitle} (#${projectId})`;
        if (projectTitle) return projectTitle;
        if (projectId) return `Project #${projectId}`;
        return t('未标注项目', 'Unassigned Project');
    }, [getAssetMeta, pickAssetMetaValue, t]);

    const getAssetEntityId = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        return String(
            pickAssetMetaValue(meta, [
                'entity_id',
                'entityId',
                'subject_id',
                'subjectId',
                'character_id',
                'characterId',
                'owner_entity_id',
                'ownerEntityId',
            ]) || asset?.entity_id || asset?.character_id || ''
        ).trim();
    }, [getAssetMeta, pickAssetMetaValue]);

    const resolveAssetEntity = useCallback((asset) => {
        const entityId = getAssetEntityId(asset);
        if (!entityId) return null;
        return (allEntities || []).find((entity) => String(entity?.id || '').trim() === entityId) || null;
    }, [allEntities, getAssetEntityId]);

    const resolveAssetImageUrlEntity = useCallback((asset) => {
        const assetTokens = collectAssetUrlTokens(asset?.url);
        if (!(assetTokens instanceof Set) || assetTokens.size === 0) return null;
        return (allEntities || []).find((entity) => {
            const imageUrl = String(entity?.image_url || '').trim();
            if (!imageUrl) return false;
            const entityTokens = collectAssetUrlTokens(imageUrl);
            for (const token of entityTokens) {
                if (assetTokens.has(token)) return true;
            }
            return false;
        }) || null;
    }, [allEntities, collectAssetUrlTokens]);

    const getAssetEpisodeId = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const entityRecord = resolveAssetEntity(asset) || resolveAssetImageUrlEntity(asset);
        const episodeId = pickAssetMetaValue(meta, ['episode_id', 'episodeId', 'owner_episode_id', 'ownerEpisodeId']) || asset?.episode_id || entityRecord?.episode_id;
        return String(episodeId || '').trim();
    }, [getAssetMeta, pickAssetMetaValue, resolveAssetEntity, resolveAssetImageUrlEntity]);

    const getAssetEpisodeLabel = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const entityRecord = resolveAssetEntity(asset) || resolveAssetImageUrlEntity(asset);
        const episodeId = String(pickAssetMetaValue(meta, ['episode_id', 'episodeId', 'owner_episode_id', 'ownerEpisodeId']) || asset?.episode_id || entityRecord?.episode_id || '').trim();
        const episodeTitle = String(pickAssetMetaValue(meta, ['episode_title', 'episodeTitle', 'owner_episode_title', 'ownerEpisodeTitle']) || '').trim();
        if (episodeTitle && episodeId) return `${episodeTitle} (#${episodeId})`;
        if (episodeTitle) return episodeTitle;
        if (episodeId) return `${t('分集', 'Episode')} #${episodeId}`;
        return t('未标注分集', 'Unassigned Episode');
    }, [getAssetMeta, pickAssetMetaValue, resolveAssetEntity, resolveAssetImageUrlEntity, t]);

    const normalizeAssetImageType = useCallback((value) => {
        const stable = String(value || '').trim().toLowerCase();
        if (!stable) return '';
        if (['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(stable)) return 'character';
        if (['prop', 'props', '道具', '物件'].includes(stable)) return 'prop';
        if (['environment', 'environments', 'scene', 'scenes', 'poster', '背景', '场景', '环境', '封面'].includes(stable)) return 'environment';
        return stable;
    }, []);

    const getAssetEntityDisplayName = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const entityId = String(
            getAssetEntityId(asset) ||
            ''
        ).trim();

        let entityRecord = null;
        if (entityId) {
            entityRecord = (allEntities || []).find((entity) => String(entity?.id || '').trim() === entityId) || null;
        }
        if (!entityRecord) {
            entityRecord = resolveAssetImageUrlEntity(asset);
        }

        const nameZh = String(
            entityRecord?.name ||
            pickAssetMetaValue(meta, ['entity_name', 'entityName', 'subject_name', 'subjectName', 'character_name', 'characterName', 'owner_entity_name', 'ownerEntityName', 'entity_name_ascii', 'entityNameAscii', 'subject_name_ascii', 'subjectNameAscii', 'character_name_ascii', 'characterNameAscii']) ||
            ''
        ).trim();
        const nameEn = String(
            entityRecord?.name_en ||
            pickAssetMetaValue(meta, ['entity_name_en', 'entityNameEn', 'subject_name_en', 'subjectNameEn', 'character_name_en', 'characterNameEn', 'owner_entity_name_en', 'ownerEntityNameEn', 'entity_name_ascii', 'entityNameAscii', 'subject_name_ascii', 'subjectNameAscii', 'character_name_ascii', 'characterNameAscii']) ||
            ''
        ).trim();

        const isSubset = nameZh && nameEn && (nameZh.toLowerCase().includes(nameEn.toLowerCase()) || nameEn.toLowerCase().includes(nameZh.toLowerCase()));
        if (nameZh && nameEn && !isSubset) return `${nameZh} / ${nameEn}`;
        if (nameZh) return nameZh;
        if (nameEn) return nameEn;
        return '';
    }, [allEntities, getAssetEntityId, getAssetMeta, pickAssetMetaValue, resolveAssetImageUrlEntity]);

    const isExplicitShotAsset = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const frameType = String(
            pickAssetMetaValue(meta, ['asset_type', 'assetType', 'frame_type', 'frameType']) || ''
        ).trim().toLowerCase();
        if (
            frameType.includes('start')
            || frameType.includes('end')
            || frameType.includes('keyframe')
            || frameType.includes('video')
            || frameType.includes('shot')
        ) return true;

        const shotNumber = String(pickAssetMetaValue(meta, ['shot_number', 'shotNumber', 'shot_no', 'shotNo']) || '').trim();
        const shotName = String(pickAssetMetaValue(meta, ['shot_name', 'shotName']) || '').trim();
        if (shotNumber || shotName) return true;

        const assetName = String(asset?.name || asset?.filename || asset?.remark || '').trim().toLowerCase();
        return assetName.includes('分镜') || assetName.includes('storyboard') || assetName.includes('shot_');
    }, [getAssetMeta, pickAssetMetaValue]);

    const getAssetDisplayName = useCallback((asset) => {
        const entityDisplay = getAssetEntityDisplayName(asset);
        if (entityDisplay) return entityDisplay;

        const stableName = String(asset?.name || '').trim();
        if (stableName) return stableName;
        const fileName = String(asset?.filename || '').trim();
        if (fileName) return fileName;
        const remark = String(asset?.remark || '').trim();
        if (remark) return remark;
        return String(asset?.id || '').trim() || t('未命名素材', 'Unnamed asset');
    }, [getAssetEntityDisplayName, t]);

    const getAssetImageType = useCallback((asset) => {
        const meta = getAssetMeta(asset);
        const source = String(pickAssetMetaValue(meta, ['source']) || '').trim().toLowerCase();

        const stableType = String(
            asset?.type
            || pickAssetMetaValue(meta, ['asset_type', 'assetType', 'frame_type', 'frameType', 'content_type', 'contentType'])
            || meta?.mime_type
            || meta?.content_type
            || ''
        ).trim().toLowerCase();
        const url = String(asset?.url || '').trim().toLowerCase();
        if (
            stableType === 'video'
            || stableType.startsWith('video/')
            || String(meta?.asset_type || meta?.frame_type || '').trim().toLowerCase().includes('video')
            || String(meta?.mime_type || meta?.content_type || '').trim().toLowerCase().startsWith('video/')
            || /\.(mp4|mov|mkv|webm|avi|m4v)(\?.*)?$/i.test(url)
        ) {
            return 'video';
        }

        if (isExplicitShotAsset(asset)) return '';

        const entityRecord = resolveAssetEntity(asset) || resolveAssetImageUrlEntity(asset);
        const entityTypeFromTable = normalizeAssetImageType(
            entityRecord?.type
            || entityRecord?.entity_type
            || entityRecord?.subject_type
            || ''
        );
        if (entityTypeFromTable) return entityTypeFromTable;

        const directType = normalizeAssetImageType(String(
            pickAssetMetaValue(meta, [
                'asset_type',
                'assetType',
                'frame_type',
                'frameType',
                'subject_type',
                'subjectType',
                'entity_type',
                'entityType',
                'category',
            ]) ||
            ''
        ));
        if (directType) return directType;

        const entityId = String(
            getAssetEntityId(asset) ||
            asset?.entity_id ||
            ''
        ).trim();
        if (!entityId) return '';

        const fallbackEntityRecord = (allEntities || []).find((entity) => String(entity?.id || '').trim() === entityId) || null;
        const fallbackEntityType = normalizeAssetImageType(fallbackEntityRecord?.type || '');
        if (fallbackEntityType) return fallbackEntityType;

        if (source === 'file_upload') return 'uploaded_asset';
        return '';
    }, [allEntities, getAssetEntityId, getAssetMeta, isExplicitShotAsset, normalizeAssetImageType, pickAssetMetaValue, resolveAssetEntity, resolveAssetImageUrlEntity]);

    const getAssetImageTypeLabel = useCallback((typeName) => {
        const normalized = String(typeName || '').trim().toLowerCase();
        if (normalized === 'character') return t('角色素材', 'Character Assets');
        if (normalized === 'prop') return t('道具素材', 'Prop Assets');
        if (normalized === 'environment') return t('环境素材', 'Environment Assets');
        if (normalized === 'video') return t('视频素材', 'Video Assets');
        if (normalized === 'uploaded_asset') {
            return t('上传资产', 'Uploaded Asset');
        }
        return typeName;
    }, [t]);

    const normalizeEntityLookupKey = useCallback((value) => {
        return String(value || '').trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/gi, '');
    }, []);

    const selectedEntityAliasIds = useMemo(() => {
        const selectedId = String(activeAssetLibraryEntity?.id || '').trim();
        const selectedType = normalizeAssetImageType(activeAssetLibraryEntity?.type || activeAssetLibraryEntity?.entity_type || activeAssetLibraryEntity?.subject_type || '');
        const selectedAttrs = getEntityCustomAttributes(activeAssetLibraryEntity);
        const selectedClonedFromId = String(selectedAttrs?.cloned_from_entity_id || '').trim();
        const nameKeys = new Set(
            [activeAssetLibraryEntity?.name, activeAssetLibraryEntity?.name_en]
                .map(normalizeEntityLookupKey)
                .filter(Boolean)
        );
        const ids = new Set();
        if (selectedId) ids.add(selectedId);
        if (selectedClonedFromId) ids.add(selectedClonedFromId);
        (allEntities || []).forEach((entity) => {
            const entityId = String(entity?.id || '').trim();
            if (!entityId) return;
            const entityType = normalizeAssetImageType(entity?.type || entity?.entity_type || entity?.subject_type || '');
            if (selectedType && entityType && entityType !== selectedType) return;
            const entityAttrs = getEntityCustomAttributes(entity);
            const entityClonedFromId = String(entityAttrs?.cloned_from_entity_id || '').trim();
            const entityNameKeys = [entity?.name, entity?.name_en].map(normalizeEntityLookupKey).filter(Boolean);
            if (
                entityNameKeys.some((key) => nameKeys.has(key))
                || (selectedId && entityClonedFromId === selectedId)
                || (selectedClonedFromId && entityId === selectedClonedFromId)
                || (selectedClonedFromId && entityClonedFromId === selectedClonedFromId)
            ) {
                ids.add(entityId);
                if (entityClonedFromId) ids.add(entityClonedFromId);
            }
        });
        return ids;
    }, [activeAssetLibraryEntity, allEntities, getEntityCustomAttributes, normalizeAssetImageType, normalizeEntityLookupKey]);

    const selectedEntityAliasImageTokens = useMemo(() => {
        const tokenSet = new Set();
        const pushEntityTokens = (entity) => {
            const imageUrl = String(entity?.image_url || '').trim();
            if (!imageUrl) return;
            collectAssetUrlTokens(imageUrl).forEach((token) => tokenSet.add(token));
        };
        pushEntityTokens(activeAssetLibraryEntity);
        (allEntities || []).forEach((entity) => {
            const entityId = String(entity?.id || '').trim();
            if (!entityId || !selectedEntityAliasIds.has(entityId)) return;
            pushEntityTokens(entity);
        });
        return tokenSet;
    }, [activeAssetLibraryEntity, allEntities, collectAssetUrlTokens, selectedEntityAliasIds]);

    const doesAssetMatchSelectedEntityImageUrl = useCallback((asset) => {
        if (!(selectedEntityAliasImageTokens instanceof Set) || selectedEntityAliasImageTokens.size === 0) return false;
        const assetTokens = collectAssetUrlTokens(asset?.url);
        for (const token of assetTokens) {
            if (selectedEntityAliasImageTokens.has(token)) return true;
        }
        return false;
    }, [collectAssetUrlTokens, selectedEntityAliasImageTokens]);

    const doesAssetMatchSelectedEntity = useCallback((asset) => {
        const selectedId = String(activeAssetLibraryEntity?.id || '').trim();
        if (!selectedId) return true;

        const selectedType = normalizeAssetImageType(activeAssetLibraryEntity?.type || activeAssetLibraryEntity?.entity_type || activeAssetLibraryEntity?.subject_type || '');
        const assetType = getAssetImageType(asset);
        if (selectedType && assetType && assetType !== selectedType) return false;

        const assetEntityId = String(getAssetEntityId(asset) || '').trim();
        if (assetEntityId && selectedEntityAliasIds.has(assetEntityId)) return true;
        if (doesAssetMatchSelectedEntityImageUrl(asset)) return true;

        const meta = getAssetMeta(asset);
        const assetNameKeys = new Set([
            pickAssetMetaValue(meta, ['entity_name', 'entityName', 'subject_name', 'subjectName', 'character_name', 'characterName', 'owner_entity_name', 'ownerEntityName', 'entity_name_ascii', 'entityNameAscii', 'subject_name_ascii', 'subjectNameAscii', 'character_name_ascii', 'characterNameAscii']),
            pickAssetMetaValue(meta, ['entity_name_en', 'entityNameEn', 'subject_name_en', 'subjectNameEn', 'character_name_en', 'characterNameEn', 'owner_entity_name_en', 'ownerEntityNameEn', 'entity_name_ascii', 'entityNameAscii', 'subject_name_ascii', 'subjectNameAscii', 'character_name_ascii', 'characterNameAscii']),
            getAssetEntityDisplayName(asset),
        ].map(normalizeEntityLookupKey).filter(Boolean));

        const selectedNameKeys = [activeAssetLibraryEntity?.name, activeAssetLibraryEntity?.name_en]
            .map(normalizeEntityLookupKey)
            .filter(Boolean);

        if (selectedNameKeys.some((key) => assetNameKeys.has(key))) return true;
        return false;
    }, [activeAssetLibraryEntity, doesAssetMatchSelectedEntityImageUrl, getAssetEntityDisplayName, getAssetEntityId, getAssetImageType, getAssetMeta, normalizeAssetImageType, normalizeEntityLookupKey, pickAssetMetaValue, selectedEntityAliasIds]);

    const preferredAssetImageType = useMemo(() => {
        return inferPreferredAssetImageType(activeAssetLibraryEntity);
    }, [activeAssetLibraryEntity, allEntities, subTab]);

    const assetScopedImageTypeOptions = useMemo(() => {
        const options = [
            { value: 'all', label: t('全部素材（兜底）', 'All Materials (Fallback)') },
        ];
        if (preferredAssetImageType && preferredAssetImageType !== 'all') {
            options.unshift({
                value: preferredAssetImageType,
                label: getAssetImageTypeLabel(preferredAssetImageType),
            });
        }
        const hasVideoAssets = Array.isArray(assets) && assets.some((asset) => getAssetImageType(asset) === 'video');
        if (hasVideoAssets && !options.some((item) => item.value === 'video')) {
            options.push({ value: 'video', label: getAssetImageTypeLabel('video') });
        }
        return options;
    }, [assets, getAssetImageType, getAssetImageTypeLabel, preferredAssetImageType, t]);

    const assetPickerDiagRef = useRef('');
    const assetLibraryContextResetRef = useRef('');

    const assetProjectOptions = useMemo(() => {
        const map = new Map();
        for (const asset of assets || []) {
            const projectId = getAssetProjectId(asset);
            if (!projectId) continue;
            if (!map.has(projectId)) {
                map.set(projectId, getAssetProjectLabel(asset));
            }
        }
        return Array.from(map.entries())
            .map(([value, label]) => ({ value, label }))
            .sort((a, b) => a.label.localeCompare(b.label));
    }, [assets, getAssetProjectId, getAssetProjectLabel]);

    const assetEpisodeOptions = useMemo(() => {
        const map = new Map();
        for (const asset of assets || []) {
            const episodeId = getAssetEpisodeId(asset);
            if (!episodeId) continue;
            if (!map.has(episodeId)) {
                map.set(episodeId, getAssetEpisodeLabel(asset));
            }
        }
        return Array.from(map.entries())
            .map(([value, label]) => ({ value: `ep:${value}`, label }))
            .sort((a, b) => String(a.label || '').localeCompare(String(b.label || '')));
    }, [assets, getAssetEpisodeId, getAssetEpisodeLabel]);

    const libraryFilteredAssets = useMemo(() => {
        const sourceAssets = Array.isArray(assets) ? assets : [];
        const nonShotAssets = sourceAssets.filter((asset) => !isExplicitShotAsset(asset));
        const selectedNameKeys = [activeAssetLibraryEntity?.name, activeAssetLibraryEntity?.name_en]
            .map(normalizeEntityLookupKey)
            .filter(Boolean);
        const characterCandidates = nonShotAssets
            .filter((asset) => {
                const imageType = getAssetImageType(asset);
                if (imageType === 'character') return true;
                return imageType === 'uploaded_asset' && preferredAssetImageType === 'character' && doesAssetMatchSelectedEntityImageUrl(asset);
            })
            .slice(0, 12)
            .map((asset) => {
                const meta = getAssetMeta(asset);
                return {
                    id: asset?.id,
                    name: asset?.name || asset?.filename || asset?.remark || '',
                    entityId: getAssetEntityId(asset),
                    episodeId: getAssetEpisodeId(asset),
                    imageType: getAssetImageType(asset),
                    entityName: pickAssetMetaValue(meta, ['entity_name', 'entityName', 'subject_name', 'subjectName', 'character_name', 'characterName', 'owner_entity_name', 'ownerEntityName']) || '',
                    entityNameEn: pickAssetMetaValue(meta, ['entity_name_en', 'entityNameEn', 'subject_name_en', 'subjectNameEn', 'character_name_en', 'characterNameEn', 'owner_entity_name_en', 'ownerEntityNameEn']) || '',
                    matchesById: selectedEntityAliasIds.has(String(getAssetEntityId(asset) || '').trim()),
                    matchesByImageUrl: doesAssetMatchSelectedEntityImageUrl(asset),
                    matchesByName: (() => {
                        const nameKeys = new Set([
                            pickAssetMetaValue(meta, ['entity_name', 'entityName', 'subject_name', 'subjectName', 'character_name', 'characterName']),
                            pickAssetMetaValue(meta, ['entity_name_en', 'entityNameEn', 'subject_name_en', 'subjectNameEn', 'character_name_en', 'characterNameEn']),
                            getAssetEntityDisplayName(asset),
                        ].map(normalizeEntityLookupKey).filter(Boolean));
                        return selectedNameKeys.some((key) => nameKeys.has(key));
                    })(),
                };
            });
                const activeEpisodeId = String(currentEpisode?.id || '').trim();
        const selectedWantedEpisodeId = String(assetEpisodeFilter || '').replace(/^ep:/, '').trim();
        const isCurrentEpisode = assetEpisodeFilter === 'all' || selectedWantedEpisodeId === activeEpisodeId;

        const entityMatchedAssets = (assetImageTypeFilter === 'all' || !isCurrentEpisode)
            ? nonShotAssets 
            : nonShotAssets.filter((asset) => doesAssetMatchSelectedEntity(asset));
        const episodeMatchedAssets = entityMatchedAssets.filter((asset) => {
            const episodeId = getAssetEpisodeId(asset);
            if (assetEpisodeFilter === 'all') return true;
            const wantedEpisodeId = String(assetEpisodeFilter || '').replace(/^ep:/, '').trim();
            return episodeId === wantedEpisodeId;
        });
        const typeMatchedAssets = episodeMatchedAssets.filter((asset) => {
            const imageType = getAssetImageType(asset);
            if (assetImageTypeFilter === 'all') return true;
            if (imageType === 'uploaded_asset' && assetImageTypeFilter === preferredAssetImageType && doesAssetMatchSelectedEntityImageUrl(asset)) {
                return true;
            }
            return imageType === assetImageTypeFilter;
        });

        if (typeof window !== 'undefined') {
            console.log('[设计资产][library-filter-stages]', {
                entity: {
                    id: String(activeAssetLibraryEntity?.id || ''),
                    name: activeAssetLibraryEntity?.name || activeAssetLibraryEntity?.name_en || '',
                    type: String(activeAssetLibraryEntity?.type || activeAssetLibraryEntity?.entity_type || activeAssetLibraryEntity?.subject_type || ''),
                    aliasIds: Array.from(selectedEntityAliasIds),
                    aliasImageTokens: Array.from(selectedEntityAliasImageTokens),
                    selectedNameKeys,
                },
                filters: {
                    assetEpisodeFilter,
                    assetImageTypeFilter,
                },
                counts: {
                    source: sourceAssets.length,
                    nonShot: nonShotAssets.length,
                    entityMatched: entityMatchedAssets.length,
                    episodeMatched: episodeMatchedAssets.length,
                    typeMatched: typeMatchedAssets.length,
                },
                characterCandidates,
                sampleAfterEntity: entityMatchedAssets.slice(0, 8).map((asset) => ({
                    id: asset?.id,
                    name: asset?.name || asset?.filename || asset?.remark || '',
                    entityId: getAssetEntityId(asset),
                    episodeId: getAssetEpisodeId(asset),
                    imageType: getAssetImageType(asset),
                })),
            });
            console.log(
                '[设计资产][library-filter-stages:flat]',
                JSON.stringify({
                    entity: {
                        id: String(activeAssetLibraryEntity?.id || ''),
                        name: activeAssetLibraryEntity?.name || activeAssetLibraryEntity?.name_en || '',
                        type: String(activeAssetLibraryEntity?.type || activeAssetLibraryEntity?.entity_type || activeAssetLibraryEntity?.subject_type || ''),
                        aliasIds: Array.from(selectedEntityAliasIds),
                        aliasImageTokens: Array.from(selectedEntityAliasImageTokens),
                        selectedNameKeys,
                    },
                    filters: {
                        assetEpisodeFilter,
                        assetImageTypeFilter,
                    },
                    counts: {
                        source: sourceAssets.length,
                        nonShot: nonShotAssets.length,
                        entityMatched: entityMatchedAssets.length,
                        episodeMatched: episodeMatchedAssets.length,
                        typeMatched: typeMatchedAssets.length,
                    },
                    characterCandidates,
                    sampleAfterEntity: entityMatchedAssets.slice(0, 8).map((asset) => ({
                        id: asset?.id,
                        name: asset?.name || asset?.filename || asset?.remark || '',
                        entityId: getAssetEntityId(asset),
                        episodeId: getAssetEpisodeId(asset),
                        imageType: getAssetImageType(asset),
                    })),
                })
            );
        }

        return typeMatchedAssets;
    }, [activeAssetLibraryEntity, assets, assetEpisodeFilter, assetImageTypeFilter, doesAssetMatchSelectedEntity, doesAssetMatchSelectedEntityImageUrl, getAssetEntityDisplayName, getAssetEntityId, getAssetEpisodeId, getAssetImageType, getAssetMeta, isExplicitShotAsset, normalizeEntityLookupKey, pickAssetMetaValue, preferredAssetImageType, selectedEntityAliasIds, selectedEntityAliasImageTokens]);

    const assetNameOptions = useMemo(() => {
        return libraryFilteredAssets
            .map((asset) => ({
                value: String(asset?.id || '').trim(),
                label: getAssetDisplayName(asset),
            }))
            .filter((item) => item.value)
            .sort((a, b) => String(a.label || '').localeCompare(String(b.label || '')));
    }, [libraryFilteredAssets, getAssetDisplayName]);

    const selectedLibraryAsset = useMemo(() => {
        if (!assetNameFilter) return libraryFilteredAssets[0] || null;
        return libraryFilteredAssets.find((asset) => String(asset?.id || '').trim() === assetNameFilter) || null;
    }, [libraryFilteredAssets, assetNameFilter]);

    useEffect(() => {
        if ((!showImageModal || imageModalTab !== 'library') && refSelectionMode !== 'assets') return;
        if (!onLog) return;
        const optionValues = assetScopedImageTypeOptions.map((item) => item.value).join('|');
        const diagSignature = [
            String(activeAssetLibraryEntity?.id || ''),
            String(activeAssetLibraryEntity?.type || activeAssetLibraryEntity?.entity_type || activeAssetLibraryEntity?.subject_type || ''),
            String(assetEpisodeFilter || ''),
            String(assetImageTypeFilter || ''),
            String(assets.length || 0),
            String(libraryFilteredAssets.length || 0),
            optionValues,
        ].join('::');
        if (assetPickerDiagRef.current === diagSignature) return;
        assetPickerDiagRef.current = diagSignature;
        onLog(
            `Asset picker diag: entity=${activeAssetLibraryEntity?.name || activeAssetLibraryEntity?.name_en || activeAssetLibraryEntity?.id || 'N/A'}, raw_type=${String(activeAssetLibraryEntity?.type || activeAssetLibraryEntity?.entity_type || activeAssetLibraryEntity?.subject_type || '').trim() || 'N/A'}, preferred_type=${preferredAssetImageType}, options=${optionValues || 'none'}, episode_filter=${assetEpisodeFilter}, type_filter=${assetImageTypeFilter}, assets_total=${assets.length}, assets_matched=${libraryFilteredAssets.length}`,
            'process'
        );
    }, [activeAssetLibraryEntity, assetEpisodeFilter, assetImageTypeFilter, assetScopedImageTypeOptions, assets.length, imageModalTab, libraryFilteredAssets.length, onLog, preferredAssetImageType, refSelectionMode, showImageModal]);

    const filteredAssets = useMemo(() => {
        const keyword = String(assetKeyword || '').trim().toLowerCase();
        return (assets || []).filter((asset) => {
            const projectId = getAssetProjectId(asset);
            if (assetProjectFilter !== 'all' && projectId !== assetProjectFilter) return false;

            const imageType = getAssetImageType(asset);
            if (assetImageTypeFilter !== 'all' && imageType !== assetImageTypeFilter) return false;

            if (!keyword) return true;
            const meta = getAssetMeta(asset);
            const haystack = [
                asset?.name,
                asset?.filename,
                asset?.remark,
                asset?.url,
                getAssetEntityDisplayName(asset),
                meta?.project_title,
                meta?.project_id,
                meta?.entity_name,
                meta?.entity_name_en,
                meta?.subject_name,
                meta?.subject_name_en,
                meta?.asset_type,
                meta?.frame_type,
                meta?.subject_type,
                meta?.entity_type,
                meta?.category,
            ]
                .map(v => String(v || '').toLowerCase())
                .join(' ');
            return haystack.includes(keyword);
        });
    }, [
        assets,
        assetKeyword,
        assetProjectFilter,
        assetImageTypeFilter,
        getAssetProjectId,
        getAssetImageType,
        getAssetEntityDisplayName,
        getAssetMeta,
    ]);

    useEffect(() => {
        // Keep "All Types" as default to avoid silently hiding entity names in the picker.
        if (!showImageModal || imageModalTab !== 'library') return;
    }, [showImageModal, imageModalTab]);

    useEffect(() => {
        if (!showImageModal || imageModalTab !== 'library') return;
        if (!assetNameOptions.length) {
            if (assetNameFilter) setAssetNameFilter('');
            return;
        }
        if (!assetNameOptions.some((item) => item.value === assetNameFilter)) {
            setAssetNameFilter(assetNameOptions[0].value);
        }
    }, [showImageModal, imageModalTab, assetNameOptions, assetNameFilter]);

    const imageLibraryViewportRef = useRef(null);
    const imageRefPickerViewportRef = useRef(null);
    const [imageLibraryViewportSize, setImageLibraryViewportSize] = useState({ width: 0, height: 0 });
    const [imageRefPickerViewportSize, setImageRefPickerViewportSize] = useState({ width: 0, height: 0 });
    const [imageLibraryScrollTop, setImageLibraryScrollTop] = useState(0);
    const [imageRefPickerScrollTop, setImageRefPickerScrollTop] = useState(0);

    const resolveAssetGridColumns = useCallback((width) => {
        if (width >= 1024) return 4;
        if (width >= 640) return 3;
        return 2;
    }, []);

    const imageLibraryColumns = useMemo(() => resolveAssetGridColumns(imageLibraryViewportSize.width), [resolveAssetGridColumns, imageLibraryViewportSize.width]);
    const imageRefPickerColumns = useMemo(() => resolveAssetGridColumns(imageRefPickerViewportSize.width), [resolveAssetGridColumns, imageRefPickerViewportSize.width]);
    const imageLibraryGap = 16;
    const imageRefPickerGap = 8;

    const imageLibraryRowHeight = useMemo(() => {
        const width = Number(imageLibraryViewportSize.width || 0);
        if (!width) return 220;
        const cardWidth = Math.max(80, (width - imageLibraryGap * (imageLibraryColumns - 1)) / imageLibraryColumns);
        return cardWidth + imageLibraryGap;
    }, [imageLibraryViewportSize.width, imageLibraryColumns]);

    const imageRefPickerRowHeight = useMemo(() => {
        const width = Number(imageRefPickerViewportSize.width || 0);
        if (!width) return 160;
        const cardWidth = Math.max(72, (width - imageRefPickerGap * (imageRefPickerColumns - 1)) / imageRefPickerColumns);
        return cardWidth + imageRefPickerGap;
    }, [imageRefPickerViewportSize.width, imageRefPickerColumns]);

    const buildVirtualWindow = useCallback((itemsLength, columns, rowHeight, viewportHeight, scrollTop, overscanRows = 3) => {
        const totalRows = Math.ceil(Math.max(0, itemsLength) / Math.max(1, columns));
        const visibleRows = Math.max(1, Math.ceil(Math.max(1, viewportHeight) / Math.max(1, rowHeight)));
        const startRow = Math.max(0, Math.floor(Math.max(0, scrollTop) / Math.max(1, rowHeight)) - overscanRows);
        const endRow = Math.min(totalRows, startRow + visibleRows + overscanRows * 2);
        const startIndex = startRow * columns;
        const endIndex = Math.min(itemsLength, endRow * columns);
        return {
            startIndex,
            endIndex,
            topSpacerHeight: startRow * rowHeight,
            bottomSpacerHeight: Math.max(0, totalRows - endRow) * rowHeight,
        };
    }, []);

    const imageLibraryWindow = useMemo(() => buildVirtualWindow(
        filteredAssets.length,
        imageLibraryColumns,
        imageLibraryRowHeight,
        imageLibraryViewportSize.height,
        imageLibraryScrollTop,
        3,
    ), [
        filteredAssets.length,
        imageLibraryColumns,
        imageLibraryRowHeight,
        imageLibraryViewportSize.height,
        imageLibraryScrollTop,
        buildVirtualWindow,
    ]);

    const imageRefPickerWindow = useMemo(() => buildVirtualWindow(
        filteredAssets.length,
        imageRefPickerColumns,
        imageRefPickerRowHeight,
        imageRefPickerViewportSize.height,
        imageRefPickerScrollTop,
        2,
    ), [
        filteredAssets.length,
        imageRefPickerColumns,
        imageRefPickerRowHeight,
        imageRefPickerViewportSize.height,
        imageRefPickerScrollTop,
        buildVirtualWindow,
    ]);

    const imageLibraryVisibleAssets = useMemo(() => {
        const { startIndex, endIndex } = imageLibraryWindow;
        return filteredAssets.slice(startIndex, endIndex);
    }, [filteredAssets, imageLibraryWindow]);

    const imageRefPickerVisibleAssets = useMemo(() => {
        const { startIndex, endIndex } = imageRefPickerWindow;
        return filteredAssets.slice(startIndex, endIndex);
    }, [filteredAssets, imageRefPickerWindow]);

    useEffect(() => {
        if (!showImageModal || imageModalTab !== 'library') return;
        const node = imageLibraryViewportRef.current;
        if (!node) return;

        const updateViewport = () => {
            setImageLibraryViewportSize({
                width: node.clientWidth || 0,
                height: node.clientHeight || 0,
            });
        };

        updateViewport();
        let observer;
        if (typeof ResizeObserver !== 'undefined') {
            observer = new ResizeObserver(updateViewport);
            observer.observe(node);
        } else {
            window.addEventListener('resize', updateViewport);
        }

        return () => {
            if (observer) observer.disconnect();
            else window.removeEventListener('resize', updateViewport);
        };
    }, [showImageModal, imageModalTab]);

    useEffect(() => {
        if (!showImageModal || refSelectionMode !== 'assets') return;
        const node = imageRefPickerViewportRef.current;
        if (!node) return;

        const updateViewport = () => {
            setImageRefPickerViewportSize({
                width: node.clientWidth || 0,
                height: node.clientHeight || 0,
            });
        };

        updateViewport();
        let observer;
        if (typeof ResizeObserver !== 'undefined') {
            observer = new ResizeObserver(updateViewport);
            observer.observe(node);
        } else {
            window.addEventListener('resize', updateViewport);
        }

        return () => {
            if (observer) observer.disconnect();
            else window.removeEventListener('resize', updateViewport);
        };
    }, [showImageModal, refSelectionMode]);

    useEffect(() => {
        setImageLibraryScrollTop(0);
        setImageRefPickerScrollTop(0);
        const libraryNode = imageLibraryViewportRef.current;
        if (libraryNode) libraryNode.scrollTop = 0;
        const pickerNode = imageRefPickerViewportRef.current;
        if (pickerNode) pickerNode.scrollTop = 0;
    }, [assetKeyword, assetProjectFilter, assetImageTypeFilter, filteredAssets.length]);

    // Image Handlers
    const handleSelectAsset = async (asset, replaceAnchor = true) => {
        const selectedUrl = String(asset?.url || '').trim();
        if (!selectedUrl) return;

        let extraFields = {};
        if (replaceAnchor) {
            const assetEntityId = getAssetEntityId(asset);
            if (assetEntityId) {
                const sourceEntity = allEntities?.find((e) => String(e.id) === String(assetEntityId));
                if (sourceEntity && typeof sourceEntity.anchor_description === 'string') {
                    extraFields.anchor_description = sourceEntity.anchor_description;
                }
            }
        }

        const updatedEntity = await updateEntityImage(selectedUrl, false, null, {
            skipAnalyze: imageSelectAction === 'rewrite_and_regenerate',
            extraFields
        });
        if (!updatedEntity) return;

        if (imageSelectAction === 'sync_prompt') {
            setShowImageModal(false);
            return;
        }

        if (imageSelectAction === 'rewrite_and_regenerate') {
            setShowImageModal(false);
            await handleReconstructEntityAsset(updatedEntity);
            return;
        }

        setShowImageModal(false);
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploadState('uploading');
        try {
            const asset = await uploadAsset(file);
            // Before calling updateEntityImage, change state to analyzing
            // Actually wait, let's look at updateEntityImage. It does:
            // 1. dbUpdate (fast)
            // 2. if (!skipAnalyze), handleAnalyzeEntity (slow)
            // It calls handleAnalyzeEntity inside updateEntityImage if we don't pass skipAnalyze.
            // But how do we change state to analyzing? Let's do it before updateEntityImage 
            // and assume it spends most of its time in analysis. Or maybe we can split it.
            // Wait, we can just pass skipAnalyze=true to updateEntityImage, and call handleAnalyzeEntity ourselves here! Let's do that!
            const updatedEntity = await updateEntityImage(asset.url, false, null, { skipAnalyze: true });
            
            if (updatedEntity) {
                setUploadState('analyzing');
                const analyzed = await handleAnalyzeEntity(updatedEntity);
                if (!analyzed) {
                    setUploadState('idle');
                    return;
                }
                setUploadState('completed');
                setTimeout(() => {
                    setShowImageModal(false);
                    setUploadState('idle');
                }, 1500);
            } else {
                setUploadState('idle');
            }
        } catch (e) {
            console.error(e);
            setUploadState('idle');
        } 
    };

    const handleGenerate = async (entityOverride = null, customRefs = null, customPrompt = null, extraProviderOptions = null) => {
        const activeEntity = entityOverride || selectedEntity;
        if (generating || !!(activeEntity?.id && subjectImageJobs[String(activeEntity.id)])) return;
        const targetEntityId = Number(activeEntity?.id || 0);
        if (!Number.isFinite(targetEntityId) || targetEntityId <= 0) return;
        const targetEntityName = String(activeEntity?.name || activeEntity?.name_en || targetEntityId);
        const selectedLangPrompt = getEntityPromptByLang(activeEntity, 'cn');
        const draftPrompt = String(promptDrafts?.cn || '').trim();
        const promptToUse = customPrompt || String(draftPrompt || selectedLangPrompt || '').trim();
        if (!promptToUse) return;
        setGenerating(true);
        setShowPromptLangMenu(false);

        // Use shared utility for prompt processing
        const epInfo = currentEpisode?.episode_info || {};
        const preferredImageSize = getEpisodePreferredImageSize(epInfo);
        // prompt likely already has suffixes appended from initialization, 
        // but we run processPrompt again in case user added new variables.
        // Use allEntities for resolution
        const processedPrompt = processPrompt(promptToUse, epInfo, allEntities);
        const finalPrompt = prependEntityGlobalStyleToPromptHead(processedPrompt, { injectIfMissing: true });
        
        // Update UI to show processed prompt (in case var replacement happened)
        setPrompt(finalPrompt);
        setPromptDrafts(prev => ({
            ...prev,
            cn: finalPrompt,
        }));

        try {
            // Resolve Visual Dependencies
            const depUrls = [];
            if (activeEntity && activeEntity.visual_dependencies) {
                 const deps = parseVisualDependencies(activeEntity.visual_dependencies);
                 deps.forEach(dep => {
                     const target = resolveDependencyEntity(dep, allEntities);

                     if (target && target.image_url) {
                         depUrls.push(target.image_url);
                     }
                 });
            }

            // Combine manual ref and auto-refs
            const allRefs = [];
            if (customRefs && customRefs.length > 0) {
                customRefs.forEach(ref => {
                    const url = typeof ref === 'object' ? ref.url : String(ref);
                    if (url) allRefs.push(url);
                });
            } else if (refImage?.url) {
                allRefs.push(refImage.url);
            }
            if (depUrls.length > 0) allRefs.push(...depUrls);
            
            // Deduplicate
            const uniqueRefs = [...new Set(allRefs)];

            if (onLog) {
                onLog(
                    `Subject generation refs: manual_ref=${refImage?.url ? 'yes' : 'no'}, dependency_refs=${depUrls.length}, total_unique=${uniqueRefs.length}`,
                    'process'
                );
            }

            const submitResult = await submitImageGenerationJob(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                function_name: (uniqueRefs && uniqueRefs.length > 0) ? 'generate_subjects_i2i' : 'generate_subjects_t2i',
                project_id: projectId,
                episode_id: currentEpisode?.id,
                entity_id: targetEntityId,
                entity_name: activeEntity?.name || activeEntity?.name_en,
                subject_name: activeEntity?.name || activeEntity?.name_en,
                subject_type: activeEntity?.type,
                entity_type: activeEntity?.type,
                prompt_language: effectivePromptSubmitLang,
                asset_type: 'subject',
                ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                negative_prompt: buildEntityNegativePrompt(finalPrompt, selectedEntity, allEntities),
                ...(extraProviderOptions || {})
            });

            const jobId = String(submitResult?.job_id || '').trim();
            if (!jobId) throw new Error('Missing image job id');

            if (isMountedRef.current) {
                updateSubjectImageJobsAndStorage(prev => ({
                    ...(prev || {}),
                    [String(targetEntityId)]: {
                        jobId,
                        status: 'queued',
                        startedAt: Date.now(),
                        entityName: targetEntityName,
                        ...buildSubjectJobMeta(targetEntityId, 'generate'),
                    },
                }));
            }

            if (onLog) onLog(`Subject generation started in background: entity=${targetEntityName}, job_id=${jobId}`, 'process');
        } catch (e) {
            console.error(e);
            alert("Generation Failed: " + (e.response?.data?.detail || e.message));
        } finally {
            if (isMountedRef.current) {
                setGenerating(false);
            }
        }
    };

    const handleForceStopSubjectImage = useCallback(async (entityOverride = null) => {
        const targetEntity = entityOverride || selectedEntity;
        const targetEntityId = String(targetEntity?.id || '').trim();
        if (!targetEntityId) return;
        if (stoppingSubjectImageJobs[String(targetEntityId)]) return;

        const currentJob = subjectImageJobs[String(targetEntityId)];
        const jobId = String(currentJob?.jobId || '').trim();
        const entityName = currentJob?.entityName || targetEntity?.name || targetEntity?.name_en || targetEntityId;

        setStoppingSubjectImageJobs(prev => ({
            ...(prev || {}),
            [String(targetEntityId)]: true,
        }));

        setGenerating(false);

        if (!jobId) {
            updateSubjectImageJobsAndStorage(prev => {
                const next = { ...(prev || {}) };
                delete next[String(targetEntityId)];
                return next;
            });
            if (onLog) onLog(t(`已清除主体运行状态：${entityName}`, `Cleared subject running state: ${entityName}`), 'warning');
            showSubjectNotification(t('已清除本地主体运行状态', 'Cleared local subject running state'), 'warning');
            setStoppingSubjectImageJobs(prev => {
                const next = { ...(prev || {}) };
                delete next[String(targetEntityId)];
                return next;
            });
            return;
        }

        try {
            const res = await stopGenerationJob('image', jobId, { force: true });
            if (onLog) onLog(res?.message || t(`已请求停止主体任务：${entityName}`, `Stop requested for subject task: ${entityName}`), 'warning');
            showSubjectNotification(t('已请求停止主体任务', 'Subject stop requested'), 'warning');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'unknown error';
            const normalizedDetail = String(detail).trim().toLowerCase();
            const missingJob = normalizedDetail.includes('job not found') || normalizedDetail.includes('not found');
            if (!missingJob) {
                if (onLog) onLog(`${t('停止主体任务失败', 'Failed to stop subject task')}: ${detail}`, 'error');
                showSubjectNotification(`${t('停止失败', 'Stop failed')}: ${detail}`, 'error');
                return;
            }
            if (onLog) onLog(t(`后端主体任务不存在，已清除本地状态：${entityName}`, `Backend subject task no longer exists. Cleared local state: ${entityName}`), 'warning');
            showSubjectNotification(t('后端任务不存在，已解除主体锁定', 'Backend job missing, subject lock cleared'), 'warning');
        } finally {
            setStoppingSubjectImageJobs(prev => {
                const next = { ...(prev || {}) };
                delete next[String(targetEntityId)];
                return next;
            });
        }

        updateSubjectImageJobsAndStorage(prev => {
            const next = { ...(prev || {}) };
            delete next[String(targetEntityId)];
            return next;
        });
    }, [onLog, selectedEntity, showSubjectNotification, stopGenerationJob, stoppingSubjectImageJobs, subjectImageJobs, t]);

    const handleRefUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setIsUploadingRef(true);
        try {
             // We reuse uploadAsset but don't assign to entity yet, just set as refImage
             const asset = await uploadAsset(file);
             setRefImage(asset);
        } catch (e) {
            console.error(e);
        } finally {
            setIsUploadingRef(false);
            if (e.target) e.target.value = null; // reset input
        }
    };

    const updateEntityImage = async (url, closeModal = true, entityOverride = null, options = {}) => {
        const targetEntity = entityOverride || selectedEntity;
        if (!targetEntity) return null;
        if (isSubjectImageActionLocked(targetEntity)) {
            notifySubjectImageActionLocked(targetEntity);
            return null;
        }
        const targetUrl = String(url || '').trim();
        if (!targetUrl) return;
        try {
            const updates = { image_url: targetUrl, ...(options?.extraFields || {}) };
            await updateEntity(targetEntity.id, updates);
            const updatedEntity = { ...targetEntity, ...updates };
            if (selectedEntity && String(selectedEntity.id) === String(updatedEntity.id)) {
                setSelectedEntity(updatedEntity);
            }
            setViewingEntity(prev => (String(prev?.id || '') === String(updatedEntity.id) ? { ...prev, ...updates } : prev));
            setEntities(prev => prev.map(ent => String(ent?.id || '') === String(updatedEntity.id) ? { ...ent, ...updates } : ent));
            setAllEntities(prev => prev.map(ent => String(ent?.id || '') === String(updatedEntity.id) ? { ...ent, ...updates } : ent));
            if (closeModal) {
                setShowImageModal(false);
            }

            if (options?.skipAnalyze !== true) {
                persistAnalyzingEntities({ ...analyzingEntities, [String(updatedEntity.id)]: { startedAt: Date.now(), initialAnalysisTime: getEntityAnalysisTime(updatedEntity) } });
                const analyzedEntity = await analyzeEntityImage(updatedEntity.id, 'script_analysis', null, { background: true });
                if (analyzedEntity) {
                    persistAnalyzingEntities(prev => ({ ...prev, [String(updatedEntity.id)]: { startedAt: Date.now(), initialAnalysisTime: getEntityAnalysisTime(analyzedEntity) } }));
                }
                return analyzedEntity || updatedEntity;
            }

            return updatedEntity;
        } catch (e) {
            console.error(e);
            return null;
        }
    };

    const handleRemoveEntityImage = useCallback(async (entityOverride = null, options = {}) => {
        const targetEntity = entityOverride || selectedEntity;
        const stableEntityId = String(targetEntity?.id || '').trim();
        if (!stableEntityId) return null;
        if (isSubjectImageActionLocked(targetEntity)) {
            notifySubjectImageActionLocked(targetEntity);
            return null;
        }

        const currentImageUrl = String(targetEntity?.image_url || '').trim();
        if (!currentImageUrl) return targetEntity;

        const skipConfirm = Boolean(options?.skipConfirm);
        if (!skipConfirm) {
            const confirmed = await confirmUiMessage(
                t('确认移除该主体当前图片关联？这不会删除素材文件，只会清空主体绑定。', 'Remove the current image association from this subject? The asset file will be kept; only the subject binding will be cleared.')
            );
            if (!confirmed) return null;
        }

        try {
            await updateEntity(Number(stableEntityId), { image_url: null });
            clearSubjectEntityImageLocally(stableEntityId);
            showSubjectNotification(t('已移除主体图片关联', 'Subject image association removed'), 'warning');
            onLog?.(t(`已移除主体图片关联：${targetEntity?.name || targetEntity?.name_en || stableEntityId}`, `Removed subject image association: ${targetEntity?.name || targetEntity?.name_en || stableEntityId}`), 'warning');
            return { ...(targetEntity || {}), image_url: null };
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || e?.message || t('未知错误', 'Unknown error');
            showSubjectNotification(`${t('移除图片失败', 'Failed to remove image')}: ${detail}`, 'error');
            return null;
        }
    }, [clearSubjectEntityImageLocally, confirmUiMessage, isSubjectImageActionLocked, onLog, selectedEntity, showSubjectNotification, t]);

    const handleBatchGenerateEntities = async () => {
        const MIN_BATCH_IMAGE_PROMPT_CHARS = 5;
        const runtimeSnapshot = getSubjectBatchSnapshot();
        if (runtimeSnapshot?.generate?.running && runtimeSnapshot?.generate?.scopeKey === subjectBatchScopeKey) {
            alert(t('批量生图任务正在运行中，请稍候。', 'Batch image generation task is already running.'));
            return;
        }

        const toGenerate = allEntities.filter(e => !e.image_url);
        if (toGenerate.length === 0) {
            alert("All entities already have images!");
            return;
        }

        if (!await confirmUiMessage(`Batch generate images for ${toGenerate.length} entities? This will respect dependency order.`)) return;

        let scenesToScan = [];
        try {
            if (entityEpisodeScope === 'all') {
                const eps = await fetchEpisodes(projectId).catch(() => []);
                const scenesPromises = eps.map(ep => fetchScenes(ep.id).catch(() => []));
                const allEpsScenes = await Promise.all(scenesPromises);
                scenesToScan = allEpsScenes.flat();
            } else if (currentEpisode?.id) {
                scenesToScan = await fetchScenes(currentEpisode.id).catch(() => []);
            }
        } catch (err) {
            console.warn("Failed to fetch scenes for calculating entity rank", err);
        }

        let sceneRankMap = new Map();
        scenesToScan.forEach((sc, sceneIndex) => {
            const scText = sc.scene_text || '';
            const envName = sc.environment_name || '';
            const chars = sc.linked_characters || '';
            const props = sc.key_props || '';
            const scAll = scText + ' ' + envName + ' ' + chars + ' ' + props;
            
            const refs = extractSceneSubjectRefs(sc) || [];
            const refNames = refs.map(r => String(r.name || '').toLowerCase());

            toGenerate.forEach(e => {
                if (sceneRankMap.has(e.id)) return;
                const eNameLower = String(e.name || '').toLowerCase();
                const eNameEnLower = String(e.name_en || '').toLowerCase();

                const isRefInScene = refNames.includes(eNameLower) || refNames.includes(eNameEnLower);
                const matchName = e.name && scAll.includes(e.name);
                const matchNameEn = e.name_en && scAll.includes(e.name_en);
                if (isRefInScene || matchName || matchNameEn) {
                    sceneRankMap.set(e.id, sceneIndex);
                }
            });
        });

        toGenerate.sort((a, b) => {
            const rankA = sceneRankMap.has(a.id) ? sceneRankMap.get(a.id) : 999999;
            const rankB = sceneRankMap.has(b.id) ? sceneRankMap.get(b.id) : 999999;
            return rankA - rankB;
        });

        subjectBatchGenerateStopRequestedRef.current = false;
        const batchSessionId = `subject-batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        subjectBatchGenerateSessionRef.current = batchSessionId;
        setIsStoppingBatchGenerateEntities(false);

        updateGenerateBatchRuntimeState(true, { current: 0, total: toGenerate.length, status: 'Initializing...' });
        const batchStartedAt = Date.now();
        updateSubjectImageJobsAndStorage(prev => {
            const next = { ...(prev || {}) };
            toGenerate.forEach((entity) => {
                const stableEntityId = String(entity?.id || '').trim();
                if (!stableEntityId) return;
                next[stableEntityId] = {
                    ...(next[stableEntityId] || {}),
                    status: 'queued',
                    startedAt: Number(next[stableEntityId]?.startedAt || 0) || batchStartedAt,
                    entityName: entity?.name || entity?.name_en || stableEntityId,
                    ...buildSubjectJobMeta(stableEntityId, 'generate', next[stableEntityId]),
                };
            });
            return next;
        });

        // Determine Dependency Map
        const nameMap = new Map();
        allEntities.forEach(e => {
            const normName = normalizeEntityToken(e.name || '');
            const normNameEn = normalizeEntityToken(e.name_en || '');
            if (normName) nameMap.set(normName, e);
            if (normNameEn) nameMap.set(normNameEn, e);
        });

        // Current status of images (starts with existing)
        // We use a mutable URL map to track latest URLs during the batch process
        const urlMap = new Map();
        allEntities.forEach(e => {
            if (e.image_url) urlMap.set(e.id, e.image_url);
        });

        let queue = [...toGenerate];
        let processedCount = 0;
        let skippedPromptCount = 0;
        
        // Helper to check if entity is ready (all its deps have images)
        const isReady = (ent) => {
            const deps = parseVisualDependencies(ent.visual_dependencies);
            if (deps.length === 0) return true;
            
            return deps.every(depRaw => {
                const dep = normalizeEntityToken(depRaw);
                const target = resolveDependencyEntity(depRaw, allEntities) || nameMap.get(dep) || null;

                if (!target) return true; // External/Unknown dep doesn't block
                return urlMap.has(target.id);
            });
        };

        try {
            const shouldStopBatchGenerate = () => (
                subjectBatchGenerateSessionRef.current !== batchSessionId
                || subjectBatchGenerateStopRequestedRef.current
            );
            const workerLimit = Math.max(1, SUBJECT_BATCH_PARALLEL_LIMIT);
            const activeTasks = new Map();

            const getSceneContextLabel = () => {
                if (currentSceneRank == null) return '';
                if (currentSceneRank >= 99999) return t(' (全局/跨场景素材)', ' (Global/Cross-scene assets)');
                if (scenesToScan.length > 0) {
                    return t(` (场景 ${currentSceneRank + 1}/${scenesToScan.length})`, ` (Scene ${currentSceneRank + 1}/${scenesToScan.length})`);
                }
                return '';
            };

            const updateGenerateActiveStatus = () => {
                if (activeTasks.size === 0) return;
                const activeLabels = Array.from(activeTasks.values())
                    .map(({ entity }) => entity?.name || entity?.name_en || entity?.id)
                    .filter(Boolean)
                    .join(', ');
                updateGenerateBatchRuntimeState(true, {
                    current: Math.min(processedCount + 1, toGenerate.length),
                    total: toGenerate.length,
                    status: t(`生成中${getSceneContextLabel()}：${activeLabels}`, `Generating${getSceneContextLabel()}: ${activeLabels}`),
                });
            };

            const runGenerateEntity = async (entity) => {
                if (shouldStopBatchGenerate()) {
                    return { entity, stopped: true };
                }
                const epInfo = currentEpisode?.episode_info || {};
                const preferredImageSize = getEpisodePreferredImageSize(epInfo);
                let basePrompt = getEntityPromptByLang(entity, resolvedPromptSubmitLang)
                    || entity.description
                    || `A ${entity.type} named ${entity.name}.`;

                if (!basePrompt || basePrompt.trim().length < 2) {
                    basePrompt = `${entity.type} ${entity.name}`;
                }

                const finalPrompt = prependEntityGlobalStyleToPromptHead(
                    String(processPrompt(basePrompt, epInfo, allEntities) || '').trim(),
                    { injectIfMissing: true }
                );
                if (finalPrompt.length < MIN_BATCH_IMAGE_PROMPT_CHARS) {
                    return { entity, skippedPrompt: true };
                }

                const depUrls = [];
                const deps = parseVisualDependencies(entity.visual_dependencies);
                deps.forEach(dep => {
                    const target = resolveDependencyEntity(dep, allEntities);

                    if (target && urlMap.has(target.id)) {
                        depUrls.push(urlMap.get(target.id));
                    }
                });
                const uniqueRefs = [...new Set(depUrls)];

                if (onLog) {
                    onLog(
                        `Batch subject refs: entity=${entity?.name || entity?.name_en || entity?.id}, dependency_refs=${depUrls.length}, total_unique=${uniqueRefs.length}`,
                        'process'
                    );
                }

                let createdJobId = '';
                try {
                    const res = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                        function_name: (uniqueRefs && uniqueRefs.length > 0) ? 'generate_subjects_i2i' : 'generate_subjects_t2i',
                        project_id: projectId,
                        episode_id: currentEpisode?.id,
                        entity_id: entity?.id,
                        entity_name: entity?.name || entity?.name_en,
                        subject_name: entity?.name || entity?.name_en,
                        subject_type: entity?.type,
                        entity_type: entity?.type,
                        prompt_language: resolvedPromptSubmitLang,
                        asset_type: 'subject',
                        ...(preferredImageSize ? { image_size: preferredImageSize } : {}),
                        negative_prompt: buildEntityNegativePrompt(basePrompt, entity, allEntities),
                        on_job_created: (jobId) => {
                            const stableJobId = String(jobId || '').trim();
                            if (!stableJobId) return;
                            createdJobId = stableJobId;
                            if (shouldStopBatchGenerate()) {
                                void stopGenerationJob('image', stableJobId, { force: true });
                                return;
                            }
                            trackSubjectBatchImageJob('generate', entity, stableJobId);
                        },
                    });

                    if (shouldStopBatchGenerate()) {
                        return { entity, stopped: true };
                    }

                    const generatedImageUrl = extractImageJobResultUrl(res);
                    if (!generatedImageUrl) {
                        throw new Error('Generated result missing image URL');
                    }

                    let resolvedImageUrl = String(generatedImageUrl || '').trim();
                    if (isEphemeralProviderMediaUrl(resolvedImageUrl)) {
                        const tempFilename = getTempMediaFilenameFromUrl(resolvedImageUrl);
                        const tempFileLabel = tempFilename ? `（临时文件：${tempFilename}）` : '';
                        onLog?.(
                            t(
                                `批量主体生图返回了临时图片地址，正在等待稳定图片入库：${entity?.name || entity?.name_en || entity?.id}${tempFileLabel}`,
                                `Batch subject generation returned a temporary image URL; waiting for durable image persistence: ${entity?.name || entity?.name_en || entity?.id}${tempFileLabel}`
                            ),
                            'process'
                        );
                        resolvedImageUrl = await awaitPersistedSubjectEntityImage(entity.id, {
                            initialUrl: resolvedImageUrl,
                            entityName: entity?.name || entity?.name_en || entity?.id,
                        });
                        if (!resolvedImageUrl) {
                            throw new Error('Timed out waiting for durable subject image URL');
                        }
                    }

                    await updateEntity(entity.id, { image_url: resolvedImageUrl });
                    return {
                        entity,
                        updatedEnt: { ...entity, image_url: resolvedImageUrl },
                        imageUrl: resolvedImageUrl,
                    };
                } finally {
                    if (createdJobId) {
                        untrackSubjectBatchImageJob('generate', entity?.id);
                    }
                }
            };

            let currentSceneRank = null;
            let currentSceneBatchLimit = workerLimit;

            const startNextGenerateTask = () => {
                const nextEntity = queue.find(e => isReady(e)) || (activeTasks.size === 0 ? queue[0] : null);
                if (!nextEntity) {
                    return false;
                }
                
                const topRank = sceneRankMap.has(nextEntity.id) ? sceneRankMap.get(nextEntity.id) : 999999;
                if (topRank !== currentSceneRank) {
                    currentSceneRank = topRank;
                    const sameRankItems = queue.filter(e => isReady(e) && (sceneRankMap.has(e.id) ? sceneRankMap.get(e.id) : 999999) === topRank);
                    currentSceneBatchLimit = Math.max(workerLimit, sameRankItems.length);
                }

                if (shouldStopBatchGenerate() || activeTasks.size >= currentSceneBatchLimit || queue.length === 0) {
                    return false;
                }

                queue = queue.filter(item => item.id !== nextEntity.id);
                const entityId = String(nextEntity?.id || '');
                setLocalSubjectImageJobState(entityId, {
                    status: 'running',
                    startedAt: Date.now(),
                    entityName: nextEntity?.name || nextEntity?.name_en || entityId,
                    ...buildSubjectJobMeta(entityId, 'generate'),
                });
                const wrappedPromise = runGenerateEntity(nextEntity)
                    .then((value) => ({ entityId, entity: nextEntity, status: 'fulfilled', value }))
                    .catch((reason) => ({ entityId, entity: nextEntity, status: 'rejected', reason }));
                activeTasks.set(entityId, { entity: nextEntity, promise: wrappedPromise });
                updateGenerateActiveStatus();
                return true;
            };

            while (queue.length > 0 || activeTasks.size > 0) {
                while (!shouldStopBatchGenerate() && startNextGenerateTask()) {
                    // Fill available concurrency slots immediately.
                }

                if (activeTasks.size === 0) {
                    break;
                }

                const settledTask = await Promise.race(Array.from(activeTasks.values()).map(item => item.promise));
                activeTasks.delete(settledTask.entityId);

                const entity = settledTask.entity;
                processedCount += 1;

                if (settledTask.status === 'fulfilled') {
                    if (settledTask.value?.stopped) {
                        // stop requested; ignore and let outer loop exit cleanly
                        clearLocalSubjectImageJobState(entity.id);
                    } else if (settledTask.value?.skippedPrompt) {
                        skippedPromptCount += 1;
                        clearLocalSubjectImageJobState(entity.id);
                        onLog?.(
                            t(
                                `批量生图跳过：${entity?.name || entity?.name_en || entity?.id} 的提示词少于 ${MIN_BATCH_IMAGE_PROMPT_CHARS} 字符。`,
                                `Batch image generation skipped: prompt for ${entity?.name || entity?.name_en || entity?.id} is shorter than ${MIN_BATCH_IMAGE_PROMPT_CHARS} chars.`
                            ),
                            'warning'
                        );
                    } else if (settledTask.value?.imageUrl) {
                        urlMap.set(entity.id, settledTask.value.imageUrl);
                        applySubjectEntityImageLocally(entity.id, settledTask.value.imageUrl);
                        clearLocalSubjectImageJobState(entity.id);
                    }
                } else if (subjectBatchGenerateSessionRef.current === batchSessionId) {
                    console.error(`Batch Gen Error for ${entity.name}`, settledTask.reason);
                    onLog?.(
                        t(
                            `批量生图失败：${entity?.name || entity?.name_en || entity?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`,
                            `Batch image generation failed: ${entity?.name || entity?.name_en || entity?.id} - ${settledTask.reason?.response?.data?.detail || settledTask.reason?.message || 'Unknown error'}`
                        ),
                        'error'
                    );
                    updateSubjectImageJobsAndStorage(prev => {
                        const stableEntityId = String(entity?.id || '').trim();
                        const existing = prev?.[stableEntityId];
                        if (!stableEntityId || !existing || String(existing?.jobId || '').trim()) {
                            return prev;
                        }
                        const next = { ...(prev || {}) };
                        delete next[stableEntityId];
                        return next;
                    });
                }

                updateGenerateBatchRuntimeState(true, {
                    current: processedCount,
                    total: toGenerate.length,
                    status: t(`已处理 ${processedCount}/${toGenerate.length}${getSceneContextLabel()}`, `Processed ${processedCount}/${toGenerate.length}${getSceneContextLabel()}`),
                });
                updateGenerateActiveStatus();
            }
            if (subjectBatchGenerateSessionRef.current !== batchSessionId || subjectBatchGenerateStopRequestedRef.current) {
                alert(t('批量生图已停止。', 'Batch image generation stopped.'));
            } else if (skippedPromptCount > 0) {
                alert(`Batch Generation Complete! Skipped ${skippedPromptCount} item(s) due to short prompt (<${MIN_BATCH_IMAGE_PROMPT_CHARS} chars).`);
            } else {
                alert("Batch Generation Complete!");
            }
        } catch (e) {
            console.error(e);
            alert("Batch Generation Failed: " + e.message);
        } finally {
            if (subjectBatchGenerateSessionRef.current === batchSessionId) {
                subjectBatchGenerateSessionRef.current = '';
            }
            subjectBatchGenerateActiveJobsRef.current.clear();
            updateSubjectImageJobsAndStorage(prev => {
                const next = { ...(prev || {}) };
                toGenerate.forEach((entity) => {
                    const stableEntityId = String(entity?.id || '').trim();
                    if (!stableEntityId) return;
                    const existing = next[stableEntityId];
                    if (!existing) return;
                    if (String(existing?.jobKind || 'generate').trim() !== 'generate') return;
                    delete next[stableEntityId];
                });
                return next;
            });
            setStoppingSubjectImageJobs(prev => {
                const next = { ...(prev || {}) };
                toGenerate.forEach((entity) => {
                    const stableEntityId = String(entity?.id || '').trim();
                    if (!stableEntityId) return;
                    delete next[stableEntityId];
                });
                return next;
            });
            clearPendingSubjectBatchImagePlaceholders();
            updateGenerateBatchRuntimeState(false, null);
            subjectBatchGenerateStopRequestedRef.current = false;
            setIsStoppingBatchGenerateEntities(false);
        }
    };

    const handleStopSubjectBatchTasks = async () => {
        const hasRunningTask = isBatchGeneratingEntities || isBatchAnalyzingEntities || isBatchReconstructingEntities;
        if (!hasRunningTask) return;

        setIsStoppingBatchGenerateEntities(true);
        subjectImageJobPollTokenRef.current += 1;
        let forcedStoppedJobCount = 0;

        if (isBatchGeneratingEntities) {
            subjectBatchGenerateStopRequestedRef.current = true;
            subjectBatchGenerateSessionRef.current = '';
            forcedStoppedJobCount += await forceStopTrackedSubjectBatchImageJobs('generate');
            updateGenerateBatchRuntimeState(false, null);
        }

        if (isBatchAnalyzingEntities) {
            subjectBatchAnalyzeStopRequestedRef.current = true;
            subjectBatchAnalyzeSessionRef.current = '';
            updateAnalyzeBatchRuntimeState(false, null);
        }

        if (isBatchReconstructingEntities) {
            subjectBatchReconstructStopRequestedRef.current = true;
            subjectBatchReconstructSessionRef.current = '';
            forcedStoppedJobCount += await forceStopTrackedSubjectBatchImageJobs('reconstruct');
            updateReconstructBatchRuntimeState(false, null);
        }

        clearPendingSubjectBatchImagePlaceholders();

        setIsStoppingBatchGenerateEntities(false);
        if (onLog) onLog(t('已请求停止当前批量任务。', 'Stop requested for current batch task.'), 'warning');
        showSubjectNotification(
            forcedStoppedJobCount > 0
                ? t(`已请求停止当前批量任务，并强制停止 ${forcedStoppedJobCount} 个已提交图片任务。`, `Stop requested for current batch task. Force-stopped ${forcedStoppedJobCount} submitted image jobs.`)
                : t('已请求停止当前批量任务。未提交的后续任务将不再继续。', 'Stop requested for current batch task. Pending unsubmitted tasks will not continue.'),
            'warning'
        );
    };

    const hasRunningSubjectBatchTask = isBatchGeneratingEntities || isBatchAnalyzingEntities || isBatchReconstructingEntities;

    useEffect(() => {
        const preloadTargets = (Array.isArray(entities) ? entities : [])
            .map((item) => String(item?.image_url || '').trim())
            .filter(Boolean)
            .slice(0, 18);

        if (!preloadTargets.length) return;

        const timers = [];
        preloadTargets.forEach((url, idx) => {
            if (isWarmMediaUrl(url) || isBrokenMediaUrl(url)) return;
            const timer = setTimeout(() => {
                try {
                    const img = new window.Image();
                    img.decoding = 'async';
                    img.src = getFullUrl(url);
                    img.onload = () => rememberWarmMediaUrl(url);
                    img.onerror = () => rememberBrokenMediaUrl(url);
                } catch {
                    // Ignore preload failures and let normal rendering continue.
                }
            }, idx * 70);
            timers.push(timer);
        });

        return () => {
            timers.forEach((timer) => clearTimeout(timer));
        };
    }, [entities, subTab]);

    const handleGenerateEntityFromText = async (entityName, textDesc) => {
        try {
            setIsGeneratingRow(true);
            await generateEntityFromText(projectId, entityName, textDesc);
            await loadEntities();
            setShowAiEntityCreateModal(false);
        } catch (e) {
            console.error(e);
            alert("生成失败: " + String(e));
        } finally {
            setIsGeneratingRow(false);
        }
    };

    const handleGenerateEntityFromImage = async (entityName, imageFile) => {
        try {
            setIsGeneratingRow(true);
            await generateEntityFromImage(projectId, entityName, imageFile);
            await loadEntities();
            setShowAiEntityCreateModal(false);
        } catch (e) {
            console.error(e);
            alert("生成失败: " + String(e));
        } finally {
            setIsGeneratingRow(false);
        }
    };

    const handleGenerateDerivedEntity = async (entityName, baseEntityId, textDesc) => {
        try {
            setIsGeneratingRow(true);
            await generateEntityDerived(projectId, entityName, baseEntityId, textDesc);
            await loadEntities();
            setShowAiEntityCreateModal(false);
        } catch (e) {
            console.error(e);
            alert("生成失败: " + String(e));
        } finally {
            setIsGeneratingRow(false);
        }
    };

    return (
        <div className="p-6 h-full flex flex-col w-full relative">
            {subjectNotification && (
                <div className={`absolute top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-2xl border text-sm max-w-md ${subjectNotification.type === 'error' ? 'bg-red-500/90 border-red-300/40 text-white' : subjectNotification.type === 'warning' ? 'bg-amber-500/90 border-amber-300/40 text-black' : subjectNotification.type === 'info' ? 'bg-sky-500/90 border-sky-300/40 text-white' : 'bg-emerald-500/90 border-emerald-300/40 text-white'}`}>
                    {subjectNotification.message}
                </div>
            )}
            <div className="flex justify-between items-start mb-6 gap-4">
                <div className="flex flex-col gap-3">
                    <div className="flex gap-1.5 bg-gradient-to-r from-white/10 via-white/5 to-white/10 border border-white/15 p-1.5 rounded-xl self-start shadow-[0_0_0_1px_rgba(255,255,255,0.05)]">
                        <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary font-mono mr-1">
                            {t('合计', 'Total')}: {scopedEntities.filter(e => e.image_url).length}/{scopedEntities.length}
                        </span>
                        {[
                            { key: 'character', label: t('角色', 'Char'), title: t('角色', 'Characters') },
                            { key: 'environment', label: t('环境', 'Env'), title: t('环境', 'Environments') },
                            { key: 'prop', label: t('道具', 'Prop'), title: t('道具', 'Props') },
                            { key: 'poster', label: t('海报', 'Poster'), title: t('封面海报', 'Cover Poster') },
                        ].map(({ key, label, title }) => {
                            const stat = subjectCategoryStats[key] || { total: 0, generated: 0 };
                            return (
                            <button
                                key={key}
                                onClick={() => setSubTab(key)}
                                className={`px-5 py-2.5 text-xs font-extrabold uppercase rounded-lg transition-all border ${subTab === key ? "bg-primary text-black border-primary shadow-[0_0_16px_rgba(255,210,64,0.35)]" : "bg-black/20 border-white/10 hover:bg-white/10 text-muted-foreground hover:text-white"}`}
                                title={title}
                            >
                                {label} ({stat.generated}/{stat.total})
                            </button>
                        )})}
                        <div className="flex items-center ml-2 border-l border-white/20 pl-2 gap-2">
                            <FunctionApiSelector functionName="generate_subjects_t2i" configs={functionApiConfigs} label={t("文生图: ", "T2I: ")} />
                            <FunctionApiSelector functionName="generate_subjects_i2i" configs={functionApiConfigs} label={t("图生图: ", "I2I: ")} />
                        </div>
                        <div className="flex items-center ml-2 border-l border-white/20 pl-2 gap-2">
                            <select
                                value={entityEpisodeScope}
                                onChange={(e) => setEntityEpisodeScope(e.target.value)}
                                className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs font-bold text-white outline-none transition-colors hover:bg-white/10"
                            >
                                <option value="current">{t('当前分集', 'Current Episode')}</option>
                                <option value="all">{t('整个项目', 'Whole Project')}</option>
                            </select>
                        </div>
                        <div className="flex items-center ml-2 border-l border-white/20 pl-2 gap-2">
                             <button 
                                onClick={handleBatchGenerateEntities}
                                disabled={isBatchGeneratingEntities || isBatchReconstructingEntities}
                                className="bg-[#111114] border border-white/10 rounded px-2 py-1 text-xs text-white outline-none hover:border-primary/50 disabled:opacity-50 transition-colors whitespace-nowrap"
                                title={t('批量生成全部实体（遵循依赖）', 'Batch Generate All Entities (Respects Dependencies)')}
                            >
                                 {isBatchGeneratingEntities ? (
                                     <span className="whitespace-nowrap">{t('批处理中', 'Batching')} {batchEntityProgress ? `${batchEntityProgress.current}/${batchEntityProgress.total}` : '...'}</span>
                                 ) : (
                                     <span className="whitespace-nowrap">{t('批量生图', 'Batch Generate Images')}</span>
                                 )}
                            </button>
                            <button
                                onClick={handleStopSubjectBatchTasks}
                                disabled={!hasRunningSubjectBatchTask || isStoppingBatchGenerateEntities}
                                className="bg-[#111114] border border-white/10 rounded px-2 py-1 text-xs text-red-500 outline-none hover:border-red-500/50 disabled:opacity-50 transition-colors whitespace-nowrap"
                                title={t('停止当前批量任务（支持批量生图/批量提示词反推/批量参考生图）', 'Stop current batch task (supports batch generation / prompt reverse / reference generation)')}
                            >
                                {isStoppingBatchGenerateEntities ? (
                                    <span className="whitespace-nowrap">{t('停止中', 'Stopping')}</span>
                                ) : (
                                    <span className="whitespace-nowrap">{t('停止', 'Stop')}</span>
                                )}
                            </button>
                             <button 
                                onClick={handleDeleteAllEntities}
                                className="bg-[#111114] border border-white/10 rounded px-2 py-1 text-xs text-white hover:text-red-400 outline-none hover:border-red-500/50 transition-colors flex items-center justify-center"
                                title={t('删除全部主体资产', 'Delete All Subjects')}
                            >
                                <Trash2 size={16} />
                            </button>
                            <button
                                onClick={openAiEntityCreateModal}
                                className="bg-[#111114] border border-white/10 rounded px-2 py-1 text-white outline-none hover:border-primary/50 transition-colors flex items-center justify-center"
                                title={t('按 subjects index + entity_design 自动新增实体', 'Add entities via subjects index + entity_design')}
                                aria-label={t('新增资产', 'Add Asset')}
                            >
                                <Plus size={16} />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Batch Status Bar */}
            {isBatchGeneratingEntities && batchEntityProgress && (
                <div className="mb-4 bg-primary/10 border border-primary/20 rounded-lg p-3 flex items-center justify-between text-xs text-primary">
                    <span className="font-bold flex items-center gap-2">
                         <RefreshCw className="animate-spin" size={12} />
                         {batchEntityProgress.status}
                    </span>
                    <span className="font-mono">{Math.round((batchEntityProgress.current / batchEntityProgress.total) * 100)}%</span>
                </div>
            )}
            {isBatchAnalyzingEntities && batchAnalyzeProgress && (
                <div className="mb-4 bg-indigo-500/10 border border-indigo-400/20 rounded-lg p-3 flex items-center justify-between text-xs text-indigo-200">
                    <span className="font-bold flex items-center gap-2">
                        <RefreshCw className="animate-spin" size={12} />
                        {batchAnalyzeProgress.status}
                    </span>
                    <span className="font-mono">{Math.round((batchAnalyzeProgress.current / batchAnalyzeProgress.total) * 100)}%</span>
                </div>
            )}
            {isBatchReconstructingEntities && batchReconstructProgress && (
                <div className="mb-4 bg-violet-500/10 border border-violet-400/20 rounded-lg p-3 flex items-center justify-between text-xs text-violet-100">
                    <span className="font-bold flex items-center gap-2">
                        <RefreshCw className="animate-spin" size={12} />
                        {batchReconstructProgress.status}
                    </span>
                    <span className="font-mono">{Math.round((batchReconstructProgress.current / batchReconstructProgress.total) * 100)}%</span>
                </div>
            )}
            
            <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6 w-full">
                
                
                {(() => {
                    const dependedKeys = new Set();
                    (allEntities || entities || []).forEach(ent => {
                        const deps = parseVisualDependencies(ent?.visual_dependencies);
                        if (deps && deps.length > 0) {
                            deps.forEach(dep => {
                                const key = normalizeSubjectKeyForDeps(dep);
                                if (key) dependedKeys.add(key);
                            });
                        }
                    });

                    return entities.map((entity, entityIndex) => {
                        const trackedJob = subjectImageJobs[String(entity.id)];
                        const isBatchPending = !trackedJob && isBatchGeneratingEntities && !entity.image_url;
                        const imageActionLocked = isSubjectImageActionLocked(entity) || isBatchPending;
                        const hasRunningSubjectImageJob = Boolean(trackedJob) || isBatchPending;
                        const isAnalyzing = Boolean(analyzingEntities[String(entity.id)]);
                        let attrs = {};
                        try {
                            attrs = entity.custom_attributes
                                ? (typeof entity.custom_attributes === 'string'
                                    ? JSON.parse(entity.custom_attributes)
                                    : entity.custom_attributes)
                                : {};
                        } catch {
                            attrs = {};
                        }
                        return (
                        <div
                            key={entity.id}
                            onClick={() => { setViewingEntity(entity); setViewingEntityTab('generate'); setAdvancedInstruction(''); setRefImage(null); }}
                            className={`bg-card/90 border rounded-2xl overflow-hidden relative group w-full cursor-pointer hover:border-primary/40 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgb(0,0,0,0.5)] shadow-[0_4px_20px_rgb(0,0,0,0.3)] transition-all duration-300 min-h-[260px] flex flex-col ${(() => {
                                const deps = parseVisualDependencies(entity.visual_dependencies);
                                const hasDependencies = deps && deps.length > 0;
                                const isDependedOn = dependedKeys.has(normalizeSubjectKeyForDeps(entity.name)) || (entity.name_en && dependedKeys.has(normalizeSubjectKeyForDeps(entity.name_en)));
                                const isCharacter = entity.type === 'character';
                                if (hasDependencies || isDependedOn) {
                                    return (hasDependencies && isCharacter) ? 'border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.05)]' : (isDependedOn && !hasDependencies ? 'border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.05)]' : 'border-sky-500/40 shadow-[0_0_10px_rgba(14,165,233,0.05)]');
                                }
                                return 'border-white/10';
                            })()}`}
                        >
                        <div className="relative aspect-video w-full overflow-hidden bg-black">
                            {(trackedJob || isBatchPending) && (
                                <div className="absolute top-2 left-2 z-30 px-2 py-1 rounded-md bg-amber-500/20 border border-amber-400/40 text-amber-100 text-[10px] font-bold flex items-center gap-1">
                                    {stoppingSubjectImageJobs[String(entity.id)] ? <Loader2 className="animate-spin" size={10} /> : <RefreshCw className="animate-spin" size={10} />}
                                    {stoppingSubjectImageJobs[String(entity.id)]
                                        ? t('停止中', 'Stopping')
                                        : isBatchPending
                                            ? t('排队中', 'Queued')
                                        : String(trackedJob?.status || '').toLowerCase() === 'persisting'
                                            ? t('同步中', 'Syncing')
                                        : String(trackedJob?.status || '').toLowerCase() === 'running'
                                            ? t('运行中', 'Running')
                                            : String(trackedJob?.status || '').toLowerCase() === 'queued'
                                                ? t('排队中', 'Queued')
                                                : t('生成中', 'Generating')}
                                </div>
                            )}
                            {(!trackedJob && !isBatchPending && isAnalyzing) && (
                                <div className="absolute inset-0 z-40 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center">
                                    <Loader2 className="animate-spin text-primary w-6 h-6 mb-1" />
                                    <span className="text-primary/90 text-xs font-bold">{t('分析中...', 'Analyzing...')}</span>
                                </div>
                            )}
                            {trackedJob && hasRunningSubjectImageJob && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        void handleForceStopSubjectImage(entity);
                                    }}
                                    disabled={Boolean(stoppingSubjectImageJobs[String(entity.id)])}
                                    className="absolute top-2 right-2 z-30 inline-flex items-center gap-1 rounded-md bg-red-500/80 hover:bg-red-500 text-white px-2 py-1 text-[10px] font-bold backdrop-blur-md disabled:opacity-60 disabled:cursor-not-allowed"
                                    title={t('停止该主体的后台图片任务', 'Stop this subject background image task')}
                                >
                                    {stoppingSubjectImageJobs[String(entity.id)] ? <Loader2 className="animate-spin" size={10} /> : <X size={10} />}
                                    <span>{stoppingSubjectImageJobs[String(entity.id)] ? t('停止中', 'Stopping') : t('停止', 'Stop')}</span>
                                </button>
                            )}

                            {(() => {
                                let isOssTemp = false;
                                const urlStr = String(entity.image_url || '').toLowerCase();
                                const isStableOss = urlStr.startsWith('/') || /qiniu|clouddn\.com|backblaze|\.bkt\.|aistory/.test(urlStr);

                                if (isStableOss) {
                                    isOssTemp = false;
                                } else {
                                    try {
                                        const attrs = entity.custom_attributes ? (typeof entity.custom_attributes === 'string' ? JSON.parse(entity.custom_attributes) : entity.custom_attributes) : {};
                                        if (attrs && attrs.oss_uploaded_success === false) {
                                            isOssTemp = true;
                                        }
                                    } catch(e) {}
                                    if (!isOssTemp && entity.image_url && typeof isEphemeralProviderMediaUrl === 'function' && isEphemeralProviderMediaUrl(entity.image_url)) {
                                        isOssTemp = true;
                                    }
                                }
                                return (isOssTemp || isEntityAnalyzed(entity)) ? (
                                    <div className="absolute bottom-2 left-2 z-30 flex items-center gap-1">
                                        {isEntityAnalyzed(entity) && (
                                            <div 
                                                className="inline-flex items-center gap-1 rounded bg-emerald-500/90 text-emerald-950 px-1.5 py-0.5 text-[10px] font-bold shadow" 
                                                title={t('该实体已完成图片分析', 'This entity has completed image analysis')}
                                            >
                                                <Sparkles size={12} />
                                                <span>{t('已分析', 'Analyzed')}</span>
                                            </div>
                                        )}
                                        {isOssTemp && (
                                            <div 
                                                className="inline-flex items-center gap-1 rounded bg-amber-500/90 text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow" 
                                                title={t('图片未持久化到OSS，目前为临时地址。', 'Image not yet persisted to OSS, using temporary link.')}
                                            >
                                                <AlertTriangle size={12} />
                                                <span>{t('临时图片', 'Temp')}</span>
                                            </div>
                                        )}
                                    </div>
                                ) : null;
                            })()}
                            {entity.image_url ? (
                                <SafeImage
                                    src={entity.image_url}
                                    alt={entity.name}
                                    className="absolute inset-0 object-contain object-center w-full h-full"
                                    loading={entityIndex < 8 ? 'eager' : 'lazy'}
                                    fetchpriority={entityIndex < 4 ? 'high' : 'auto'}
                                    fallback={<div className="absolute inset-0 flex items-center justify-center bg-white/5"><Users className="text-white/20" size={48} /></div>}
                                />
                            ) : entity.video_url ? (
                                <video
                                    src={getSafeMediaUrl(getFullUrl(entity.video_url))}
                                    className="absolute inset-0 object-contain w-full h-full"
                                    preload="metadata"
                                    muted
                                    playsInline
                                />
                            ) : (
                                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-white/5 px-4 text-center">
                                    <Users className="text-white/20" size={48} />
                                    <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/55">{t('未绑定图片', 'No Linked Image')}</div>
                                    <div className="text-[10px] text-white/35">{t('可重新选择或生成主体图', 'Select or generate a subject image')}</div>
                                </div>
                            )}
                            {/* video / audio badge */}
                            {(entity.video_url || entity.audio_url) && (
                                <div className="absolute top-2 left-2 z-20 flex gap-1">
                                    {entity.video_url && !entity.image_url && (
                                        <span className="inline-flex items-center gap-0.5 rounded bg-blue-500/80 text-white px-1.5 py-0.5 text-[10px] font-bold" title={entity.video_url}>
                                            <Video size={10} /> {t('视频', 'Video')}
                                        </span>
                                    )}
                                    {entity.audio_url && (
                                        <span className="inline-flex items-center gap-0.5 rounded bg-purple-500/80 text-white px-1.5 py-0.5 text-[10px] font-bold" title={entity.audio_url}>
                                            🎵 {t('音频', 'Audio')}
                                        </span>
                                    )}
                                </div>
                            )}
                            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent z-10 pointer-events-none"></div>

                            <div className={`absolute right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2 flex-wrap justify-end p-1 max-w-[80%] ${hasRunningSubjectImageJob ? 'top-12' : 'top-2'}`}>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); handleOpenImageModal(entity, 'library'); }}
                                    disabled={imageActionLocked}
                                    className="p-1.5 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md disabled:opacity-50 disabled:cursor-not-allowed"
                                    title={imageActionLocked ? t('图片任务运行中，不能更换图片', 'Image job is running; image changes are disabled') : t('更换图片（素材库/上传）', 'Change Image (Library/Upload)')}
                                >
                                    <ImagePlus size={16} />
                                </button>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setViewingEntity(entity); setViewingEntityTab('generate'); setRefImage(null); handleGenerate(entity, null, getEntityPromptByLang(entity, effectivePromptSubmitLang)); }}
                                    disabled={imageActionLocked}
                                    className="p-1.5 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md disabled:opacity-50 disabled:cursor-not-allowed"
                                    title={t('生成图片', 'Generate Image')}
                                >
                                    <Wand2 size={16} />
                                </button>
                                
                                
                                {attrs?.cloned_from_entity_id && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleSyncFromOld(attrs?.cloned_from_entity_id, entity.id); }}
                                        className="p-1.5 bg-yellow-500/80 hover:bg-yellow-600 rounded-full text-white backdrop-blur-md"
                                        title={t('从源实体同步', 'Sync from Source')}
                                    >
                                        <RefreshCw size={16} />
                                    </button>
                                )}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        void handleRemoveEntityImage(entity);
                                    }}
                                    disabled={imageActionLocked || !entity.image_url}
                                    className="p-1.5 bg-amber-500/80 hover:bg-amber-500 rounded-full text-white backdrop-blur-md disabled:opacity-50 disabled:cursor-not-allowed"
                                    title={imageActionLocked ? t('图片任务运行中，不能移除图片', 'Image job is running; image removal is disabled') : t('移除图片关联', 'Remove image association')}
                                >
                                    <Unlink size={16} />
                                </button>
                                
                                <button 
                                    onClick={(e) => handleDeleteEntity(e, entity)}
                                    className="p-1.5 bg-red-500/80 hover:bg-red-600 rounded-full text-white backdrop-blur-md"
                                    title={t('删除实体', 'Delete Entity')}
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>

                        <div className="p-3 border-t border-white/10 flex-1 flex flex-col">
                            <div className="flex items-start justify-between gap-2">
                                <div className="font-bold text-white capitalize truncate">{entity.name}</div>
                                {(() => {
                                    const dependencies = parseVisualDependencies(entity.visual_dependencies);
                                    const hasDependencies = dependencies && dependencies.length > 0;
                                    const isDependedOn = dependedKeys.has(normalizeSubjectKeyForDeps(entity.name)) || (entity.name_en && dependedKeys.has(normalizeSubjectKeyForDeps(entity.name_en)));
                                    const isCharacter = entity.type === 'character';

                                    return (hasDependencies || isDependedOn) ? (
                                        <div className="flex items-center gap-1.5 shrink-0 overflow-hidden flex-wrap justify-end max-w-[65%]">
                                            {hasDependencies && (
                                                <span className={`shrink-0 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border ${isCharacter ? 'border-amber-300/40 text-amber-200 bg-amber-500/20' : 'border-sky-300/40 text-sky-200 bg-sky-500/20'}`} title={dependencies.join(', ')}>
                                                    <LinkIcon size={10} />
                                                    {isCharacter ? t('角色依赖', 'Role Dependency') : t('有依赖', 'Has Dependency')}
                                                </span>
                                            )}
                                            {isDependedOn && (
                                                <span className="shrink-0 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border border-emerald-300/40 text-emerald-200 bg-emerald-500/20" title={t('作为其它资产的源', 'Source for other assets')}>
                                                    <LinkIcon size={10} />
                                                    {t('被依赖', 'Depended')}
                                                </span>
                                            )}
                                        </div>
                                    ) : null;
                                })()}
                            </div>
                            <div className="text-[10px] text-white/55 uppercase tracking-[0.16em] mt-1">{subTab}</div>
                            <div className="mt-3 text-[10px] text-white/45 uppercase tracking-[0.16em]">{t('Subject介绍', 'Subject Intro')}</div>
                            <div className="text-xs text-white/70 mt-1 line-clamp-3 leading-relaxed min-h-[3.5rem]">
                                {String(entity.description || '').trim() || t('暂无介绍，点击卡片可编辑主体描述。', 'No intro yet. Click the card to edit subject description.')}
                            </div>
                        </div>
                    </div>
                    );
                })})()}

                {entityListLoading && entities.length === 0 && Array.from({ length: 8 }).map((_, idx) => (
                    <div
                        key={`subject-skeleton-${idx}`}
                        className="border border-white/10 rounded-xl bg-white/[0.02] animate-pulse overflow-hidden"
                    >
                        <div className="aspect-video bg-white/10" />
                        <div className="p-3">
                            <div className="h-4 rounded bg-white/10 w-2/3 mb-2" />
                            <div className="h-3 rounded bg-white/10 w-1/3 mb-3" />
                            <div className="h-3 rounded bg-white/10 w-full mb-1.5" />
                            <div className="h-3 rounded bg-white/10 w-5/6" />
                        </div>
                    </div>
                ))}
            </div>

            {entityListLoading && entities.length === 0 && (
                <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {t('主体加载中...', 'Loading subjects...')}
                </div>
            )}

            <AnimatePresence>
                {showAiEntityCreateModal && (
                    <AiEntityCreateDialog
                        isOpen={showAiEntityCreateModal}
                        onClose={() => setShowAiEntityCreateModal(false)}
                        onGenerateText={handleGenerateEntityFromText}
                        onGenerateImage={handleGenerateEntityFromImage}
                        onGenerateDerived={handleGenerateDerivedEntity}
                        entities={allEntities}
                        isGeneratingRow={isGeneratingRow}
                    />
                )}
            </AnimatePresence>

            {/* Entity Detail Modal */}
            <AnimatePresence>
                {viewingEntity && (
                    (() => {
                        const viewingEntityImageLocked = isSubjectImageActionLocked(viewingEntity);
                        return (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-8" onClick={() => { setViewingEntity(null); setRefImage(null); }}>
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-[#1e1e1e] border border-white/10 rounded-2xl w-full max-w-5xl h-[80vh] flex shadow-2xl overflow-hidden"
                        >
                            {/* Left: Image */}
                            <div className="w-1/2 bg-black relative flex items-center justify-center">
                                {viewingEntity.image_url ? (
                                    <SafeImage src={viewingEntity.image_url} alt={viewingEntity.name} className="w-full h-full object-contain" fallback={<div className="w-full h-full flex flex-col items-center justify-center text-white/20"><Users size={64} /><span className="mt-4 text-sm font-bold uppercase">{t('无图片', 'No Image')}</span></div>} />
                                ) : (
                                    <div className="flex flex-col items-center justify-center px-8 text-center text-white/20">
                                        <Users size={64} />
                                        <span className="mt-4 text-sm font-bold uppercase tracking-[0.18em]">{t('图片已移除', 'Image Unlinked')}</span>
                                        <span className="mt-2 text-xs text-white/45">{t('当前主体未绑定图片，可重新选择素材或直接生成新图。', 'This subject has no linked image. Select media again or generate a new one.')}</span>
                                    </div>
                                )}
                                
                                {viewingEntity.id !== 'new' && (
                                    <div className="absolute top-4 left-4 flex gap-2 z-10">
                                         
                                         <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setViewingEntity(null); 
                                                handleOpenImageModal(viewingEntity, 'library');
                                            }}
                                            disabled={viewingEntityImageLocked}
                                            className="p-3 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                                          title={viewingEntityImageLocked ? t('图片任务运行中，不能更换图片', 'Image job is running; image changes are disabled') : t('更换图片', 'Change Image')}
                                         >
                                             <ImagePlus size={20} />
                                         </button>
                                         <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                void handleRemoveEntityImage(viewingEntity);
                                            }}
                                            disabled={viewingEntityImageLocked || !viewingEntity.image_url}
                                            className="p-3 bg-amber-500/80 hover:bg-amber-500 text-white rounded-full backdrop-blur-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg border border-white/10"
                                                          title={viewingEntityImageLocked ? t('图片任务运行中，不能移除图片', 'Image job is running; image removal is disabled') : t('移除图片关联', 'Remove image association')}
                                         >
                                             <Unlink size={20} />
                                         </button>
                                         
                                         
                                    </div>
                                )}
                            </div>
                            
                            {/* Right: Info */}
                            <div className="w-1/2 flex flex-col h-full bg-[#1e1e1e]">
                                <div className="p-6 border-b border-white/10 flex justify-between items-start">
                                    <div className="flex-1 mr-4">
                                        <input 
                                            value={viewingEntity.name || ''}
                                            onChange={(e) => {
                                                const val = e.target.value;
                                                setViewingEntity(prev => ({ ...prev, name: val }));
                                            }}
                                            onBlur={(e) => handleFieldUpdate('name', e.target.value)}
                                            className="text-3xl font-bold font-serif mb-1 bg-transparent border-b border-transparent hover:border-white/10 focus:border-primary outline-none w-full transition-colors truncate"
                                            placeholder="Entity Name"
                                        />
                                        <input 
                                            value={viewingEntity.name_en || ''} 
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, name_en: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('name_en', e.target.value)}
                                            className="text-lg text-muted-foreground font-mono bg-transparent border-b border-transparent hover:border-white/10 focus:border-primary outline-none w-full transition-colors"
                                            placeholder="English Name"
                                        />
                                    </div>
                                    <button
                                        onClick={() => { setViewingEntity(null); setRefImage(null); }}
                                        className="p-2 hover:bg-white/10 rounded-full text-muted-foreground hover:text-white transition-colors"
                                    >
                                        <X size={24} />
                                    </button>
                                </div>

                                <div className="flex border-b border-white/10 bg-black/20">
                                    {['info', 'video', 'audio', 'generate', 'advanced'].map(tab => (
                                        <button
                                            key={tab}
                                            onClick={() => setViewingEntityTab(tab)}
                                            className={`flex-1 py-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 ${
                                                viewingEntityTab === tab
                                                ? 'border-primary text-primary bg-primary/5'
                                                : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'
                                            }`}
                                        >
                                            {tab === 'info'
                                                ? t('主体信息', 'Info')
                                                : tab === 'video'
                                                    ? t('视频', 'Video')
                                                    : tab === 'audio'
                                                        ? t('音频', 'Audio')
                                                        : tab === 'generate'
                                                            ? t('设计资产', 'Generate Asset')
                                                            : t('修改资产', 'Modify Asset')}
                                        </button>
                                    ))}
                                </div>

                                {reconstructProgress && (
                                    <div className="px-6 py-3 border-b border-white/10 bg-primary/5">
                                        <div className="flex items-center justify-between text-xs mb-2">
                                            <span className="font-bold text-primary flex items-center gap-2">
                                                <RefreshCw className={`${isReconstructingEntity ? 'animate-spin' : ''}`} size={12} />
                                                {reconstructProgress.label}
                                            </span>
                                            <span className="font-mono text-primary">{reconstructProgress.percent}%</span>
                                        </div>
                                        <div className="w-full h-1.5 rounded-full bg-black/30 overflow-hidden">
                                            <div className="h-full bg-primary transition-all duration-300" style={{ width: `${reconstructProgress.percent}%` }} />
                                        </div>
                                    </div>
                                )}
                                
                                <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                                    {viewingEntityImageLocked && (
                                        <div className="rounded border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 flex items-center justify-between gap-3">
                                            <div className="flex items-center gap-2">
                                                {stoppingSubjectImageJobs[String(viewingEntity.id)] ? <Loader2 className="animate-spin" size={12} /> : <RefreshCw className="animate-spin" size={12} />}
                                                {stoppingSubjectImageJobs[String(viewingEntity.id)]
                                                    ? t('该主体停止请求发送中，请稍候。', 'Stop request is being sent for this subject. Please wait.')
                                                    : String(subjectImageJobs[String(viewingEntity.id)]?.status || '').toLowerCase() === 'persisting'
                                                        ? t('该主体已完成生成，正在等待稳定图片同步到素材库。', 'This subject finished generating and is waiting for the durable image to sync back into the library.')
                                                    : String(subjectImageJobs[String(viewingEntity.id)]?.status || '').toLowerCase() === 'running'
                                                        ? t('该主体正在运行中，即使关闭窗口也会继续。', 'This subject is running in background and will continue even if you close this window.')
                                                        : String(subjectImageJobs[String(viewingEntity.id)]?.status || '').toLowerCase() === 'queued'
                                                            ? t('该主体正在排队中，开始后将自动运行。', 'This subject is queued and will run automatically once started.')
                                                            : t('该主体正在生成中，即使关闭窗口也会继续。', 'This subject is generating in background and will continue even if you close this window.')}
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => handleForceStopSubjectImage(viewingEntity)}
                                                disabled={Boolean(stoppingSubjectImageJobs[String(viewingEntity.id)])}
                                                className="shrink-0 inline-flex items-center gap-1 rounded border border-red-400/30 bg-red-500/15 px-2 py-1 text-[11px] font-bold text-red-100 hover:bg-red-500/25 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                                                title={t('强制停止该主体的后台图片任务，并解除当前运行状态', 'Force-stop this subject background image task and clear the current running state')}
                                            >
                                                {stoppingSubjectImageJobs[String(viewingEntity.id)] ? <Loader2 className="animate-spin" size={12} /> : <X size={12} />}
                                                {stoppingSubjectImageJobs[String(viewingEntity.id)] ? t('停止中', 'Stopping') : t('停止', 'Stop')}
                                            </button>
                                        </div>
                                    )}
                                    {viewingEntityTab === 'info' && (
                                        <div className="space-y-6">
                                    {/* Action Buttons */}
                                    <div className="flex gap-2">
                                        {(typeof viewingEntity.custom_attributes === 'string' ? JSON.parse(viewingEntity.custom_attributes) : (viewingEntity.custom_attributes || {})).cloned_from_entity_id && (
                                            <button onClick={() => handleSyncFromOld((typeof viewingEntity.custom_attributes === 'string' ? JSON.parse(viewingEntity.custom_attributes) : (viewingEntity.custom_attributes || {})).cloned_from_entity_id, viewingEntity.id)} className="px-3 py-1.5 bg-yellow-500/20 text-yellow-300 text-xs font-bold rounded-lg border border-yellow-500/30 hover:bg-yellow-500/30 flex items-center justify-center gap-1 transition-colors">
                                                <RefreshCw size={14} />
                                                {t('从源实体同步', 'Sync from Source')}
                                            </button>
                                        )}
                                        
                                        
                                    </div>
                                    {/* Role & Archetype Tags */}
                                    <div className="flex flex-wrap gap-2">
                                        {['role', 'archetype', 'gender'].map(field => (
                                            <input
                                                key={field}
                                                value={viewingEntity[field] || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, [field]: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate(field, e.target.value)}
                                                placeholder={field}
                                                className="px-3 py-1 bg-white/5 text-xs font-bold uppercase tracking-wider rounded-full border border-transparent focus:border-primary outline-none text-center min-w-[60px]"
                                            />
                                        ))}
                                    </div>

                                    {/* Description */}
                                    <div className="space-y-2">
                                        <h4 className="text-xs font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <FileText size={12} /> Description
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.description || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, description: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('description', e.target.value)}
                                            className="w-full text-sm leading-relaxed text-white/80 bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none transition-colors"
                                            placeholder="Enter description..."
                                        />
                                    </div>

                                    {/* Environment Details */}
                                    {viewingEntity.type === 'environment' && (
                                        <div className="space-y-4 p-4 bg-white/5 rounded-lg border border-white/5">
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('氛围', 'Atmosphere')}</h4>
                                                 <input 
                                                    value={viewingEntity.atmosphere || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, atmosphere: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('atmosphere', e.target.value)}
                                                    className="w-full text-sm bg-transparent border-b border-white/10 hover:border-white/30 focus:border-primary p-2 outline-none transition-colors"
                                                    placeholder="Atmosphere (e.g. Dark, Cozy)"
                                                />
                                            </div>
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('视觉参数', 'Visual Params')}</h4>
                                                <textarea 
                                                    value={viewingEntity.visual_params || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, visual_params: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('visual_params', e.target.value)}
                                                    className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none"
                                                    placeholder="Visual parameters..."
                                                />
                                            </div>
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('叙事描述', 'Narrative Description')}</h4>
                                                <textarea 
                                                    value={viewingEntity.narrative_description || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, narrative_description: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('narrative_description', e.target.value)}
                                                    className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none"
                                                    placeholder="Detailed narrative (Description field)..."
                                                />
                                            </div>
                                        </div>
                                    )}

                                    {/* Appearance Details */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('外观', 'Appearance')}</h4>
                                            <textarea 
                                                value={viewingEntity.appearance_cn || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, appearance_cn: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate('appearance_cn', e.target.value)}
                                                className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-20 resize-none"
                                                placeholder="Appearance details..."
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('服装', 'Clothing')}</h4>
                                            <textarea 
                                                value={viewingEntity.clothing || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, clothing: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate('clothing', e.target.value)}
                                                className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-20 resize-none"
                                                placeholder="Clothing details..."
                                            />
                                        </div>
                                    </div>
                                    
                                    {/* Technical / Prompt */}
                                    <div className="space-y-2">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <Wand2 size={10} /> Generation Prompt
                                        </h4>
                                        <div className="grid grid-cols-1 gap-3">
                                            <div>
                                                <div className="text-[10px] font-bold uppercase text-muted-foreground mb-1">{t('中文提示词', 'Chinese Prompt')}</div>
                                                <textarea
                                                    value={viewingEntity.generation_prompt_cn || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, generation_prompt_cn: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('generation_prompt_cn', e.target.value)}
                                                    className="w-full p-3 bg-black/20 rounded-lg border border-white/5 text-xs font-mono text-white/70 focus:text-white/90 focus:border-primary outline-none min-h-[90px] resize-y"
                                                    placeholder={t('输入中文生图提示词...', 'Enter Chinese generation prompt...')}
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* Action Characteristics */}
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <Clapperboard size={10} /> Action Characteristics
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.action_characteristics || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, action_characteristics: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('action_characteristics', e.target.value)}
                                            className="w-full text-sm p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 focus:border-primary outline-none resize-y min-h-[60px]"
                                            placeholder="Action characteristics..."
                                        />
                                    </div>

                                    {/* Anchor Description */}
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <LinkIcon size={10} /> Anchor Description
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.anchor_description || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, anchor_description: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('anchor_description', e.target.value)}
                                            className="w-full text-sm p-3 bg-white/5 rounded-lg border border-white/5 font-mono text-xs hover:border-white/10 focus:border-primary outline-none resize-y min-h-[60px]"
                                            placeholder="Anchor description..."
                                        />
                                    </div>

                                    {/* Dependency Strategy */}
                                    {(() => {
                                        const strategy = viewingEntity.dependency_strategy && typeof viewingEntity.dependency_strategy === 'object'
                                            ? viewingEntity.dependency_strategy
                                            : {};
                                        const strategyTypeText = toRenderableText(strategy.type);
                                        const strategyLogicText = toRenderableText(strategy.logic);

                                        if (!strategyTypeText && !strategyLogicText) {
                                            return null;
                                        }

                                        return (
                                            <div className="space-y-1 pt-2 border-t border-white/5">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                                    <Settings2 size={10} /> Dependency Strategy
                                                </h4>
                                                <div className="bg-white/5 rounded-lg border border-white/5 p-3 text-xs space-y-1">
                                                    {strategyTypeText && (
                                                        <div className="flex gap-2">
                                                            <span className="text-muted-foreground">{t('类型：', 'Type:')}</span>
                                                            <span className="font-bold text-primary">{strategyTypeText}</span>
                                                        </div>
                                                    )}
                                                    {strategyLogicText && (
                                                        <div className="flex gap-2 flex-col sm:flex-row sm:items-baseline">
                                                            <span className="text-muted-foreground whitespace-nowrap">{t('逻辑：', 'Logic:')}</span>
                                                            <span className="text-white/80 italic">{strategyLogicText}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })()}

                                    {/* Visual Dependencies (Editable) */}
                                    <div className="space-y-2 pt-2 border-t border-white/5">
                                         <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('资产参考', 'Asset References')}</h4>
                                         <p className="text-[10px] text-white/40 mb-1">{t('添加主体名称后，生成该主体时会自动引用其图片。', 'Add entity names to use their images as reference when generating this entity.')}</p>
                                         <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                                             <div className="flex flex-wrap gap-2 mb-2">
                                                 {parseVisualDependencies(viewingEntity.visual_dependencies).map((dep, i) => (
                                                     <div key={i} className="px-2 py-1 bg-primary/20 text-primary border border-primary/20 rounded text-xs flex items-center gap-2 group">
                                                         <span className="font-bold">{typeof dep === 'string' ? dep : JSON.stringify(dep)}</span>
                                                         <button 
                                                            onClick={() => {
                                                                 const current = parseVisualDependencies(viewingEntity.visual_dependencies);
                                                                 const newDeps = current.filter(d => d !== dep);
                                                                 handleFieldUpdate('visual_dependencies', newDeps);
                                                            }} 
                                                            className="hover:text-white opacity-50 group-hover:opacity-100"
                                                        >
                                                            <X size={10}/>
                                                        </button>
                                                     </div>
                                                 ))}
                                             </div>
                                             
                                             <div className="relative flex items-center gap-2">
                                                 <input 
                                                     type="text" 
                                                     placeholder="Type Entity Name & Enter..." 
                                                     className="w-full bg-transparent text-xs outline-none text-white/90 placeholder:text-white/20"
                                                     id="dep-input"
                                                     onKeyDown={(e) => {
                                                         if (e.key === 'Enter') {
                                                             const val = e.currentTarget.value.trim();
                                                             if(val) {
                                                                const current = parseVisualDependencies(viewingEntity.visual_dependencies);
                                                                if(!current.includes(val)) {
                                                                     handleFieldUpdate('visual_dependencies', [...current, val]);
                                                                }
                                                                e.currentTarget.value = '';
                                                             }
                                                         }
                                                     }}
                                                 />
                                                 <Plus className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-white" onClick={() => {
                                                     const input = document.getElementById('dep-input');
                                                     if (!input) return;
                                                     const val = input.value.trim();
                                                     if (val) {
                                                         const current = parseVisualDependencies(viewingEntity.visual_dependencies);
                                                         if(!current.includes(val)) {
                                                             handleFieldUpdate('visual_dependencies', [...current, val]);
                                                         }
                                                         input.value = '';
                                                     }
                                                 }}/>
                                             </div>
                                         </div>
                                    </div>

                                    {/* Create Mode Actions */}
                                    {viewingEntity.id === 'new' && (
                                        <div className="mt-8 pt-4 border-t border-white/10 flex justify-end gap-3 sticky bottom-0 bg-[#1e1e1e] pb-2 z-10">
                                            <button 
                                                onClick={() => { setViewingEntity(null); setRefImage(null); }}
                                                className="px-4 py-2 rounded-lg font-bold text-xs text-muted-foreground hover:bg-white/10 transition-colors uppercase"
                                            >
                                                {t('取消', 'Cancel')}
                                            </button>
                                            <button 
                                                onClick={handleCommitCreate}
                                                className="px-6 py-2 rounded-lg font-bold text-xs bg-primary text-black hover:brightness-110 flex items-center gap-2 uppercase tracking-wide shadow-lg shadow-primary/20 transition-all active:scale-95"
                                            >
                                                <Plus size={14} strokeWidth={3} /> {t('创建主体', 'Create Subject')}
                                            </button>
                                        </div>
                                    )}

                                    {/* Attributes Display - Show ALL fields except the ones already shown above */
                                    (() => {
                                        const hiddenFields = ['id', 'project_id', 'image_url', 'video_url', 'audio_url', 'created_at', 'updated_at', 'name', 'name_en', 'description', 
                                            'author_id', 'role', 'archetype', 'gender', 'appearance_cn', 'clothing', 'generation_prompt_cn', 'generation_prompt_en', 'visual_dependencies', 'type', 'project', 'dependency_strategy', 'action_characteristics', 'anchor_description', 'custom_attributes'];
                                        hiddenFields.push('reference_image_urls', 'reference_video_urls', 'reference_audio_urls');
                                        
                                        // Flatten custom_attributes into the view if they exist
                                        let mergedSource = { ...viewingEntity };
                                        if (viewingEntity.custom_attributes && typeof viewingEntity.custom_attributes === 'object') {
                                            mergedSource = { ...viewingEntity.custom_attributes, ...mergedSource };
                                        }

                                        // Merge known extra fields with potentially new ones, excluding standard
                                        const extraFields = Object.entries(mergedSource).filter(([key, val]) => 
                                            !hiddenFields.includes(key) && 
                                            val !== null && 
                                            val !== undefined
                                        );

                                        return (
                                            <div className="space-y-2 pt-4 border-t border-white/5">
                                                <div className="flex justify-between items-center">
                                                    <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('其他属性', 'Other Attributes')}</h4>
                                                    <button 
                                                        onClick={async () => {
                                                            const key = await promptUiMessage("Enter new attribute name:", {
                                                                title: 'Add Attribute',
                                                                confirmText: 'Add',
                                                                cancelText: 'Cancel',
                                                                placeholder: 'attribute_key',
                                                            });
                                                            if (key && !viewingEntity[key] && !hiddenFields.includes(key)) {
                                                                setViewingEntity(prev => ({...prev, [key]: "New Value"}));
                                                                // Auto save? Maybe wait for value edit.
                                                            }
                                                        }}
                                                        className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-white"
                                                    >
                                                        + Add
                                                    </button>
                                                </div>
                                                <div className="grid grid-cols-1 gap-2">
                                                    {extraFields.map(([key, value]) => (
                                                        <div key={key} className="p-3 bg-white/5 rounded-lg text-xs space-y-1 group relative">
                                                            <div className="flex justify-between">
                                                                <span className="opacity-50 font-mono uppercase text-[10px] break-all">{key.replace(/_/g, ' ')}</span>
                                                                <button 
                                                                    onClick={async () => {
                                                                        if(!await confirmUiMessage(`Delete attribute ${key}?`)) return;
                                                                        const updated = { ...viewingEntity };
                                                                        delete updated[key];
                                                                        setViewingEntity(updated);
                                                                        setEntities(prev => prev.map(ent => String(ent.id) === String(updated.id) ? updated : ent));
                                                                        setAllEntities(prev => prev.map(ent => String(ent.id) === String(updated.id) ? updated : ent));
                                                                        // For API, we might need to send null or special flag if backend handles it, 
                                                                        // but typically PUT replaces. If PATCH, we might need to set to null.
                                                                        // Assuming partial update, set to null to delete? Or backend ignores missing?
                                                                        // If backend is SQLModel/Pydantic with extra=ignore, it might persist.
                                                                        // Let's assume we send null to clear.
                                                                        updateEntity(updated.id, { [key]: null }); 
                                                                    }}
                                                                    className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-400 p-1"
                                                                >
                                                                    <Trash2 size={12} />
                                                                </button>
                                                            </div>
                                                            <textarea
                                                                value={typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                                                onChange={(e) => {
                                                                    setViewingEntity(prev => ({ ...prev, [key]: e.target.value }));
                                                                }}
                                                                onBlur={(e) => {
                                                                    let val = e.target.value;
                                                                    // Try to parse JSON if it looks like object
                                                                    if (val.trim().startsWith('{') || val.trim().startsWith('[')) {
                                                                        try { val = JSON.parse(val); } catch(err) {} 
                                                                    }
                                                                    const updated = { ...viewingEntity, [key]: val };
                                                                    setEntities(prev => prev.map(ent => String(ent.id) === String(updated.id) ? updated : ent));
                                                                    setAllEntities(prev => prev.map(ent => String(ent.id) === String(updated.id) ? updated : ent));
                                                                    updateEntity(updated.id, { [key]: val });
                                                                }}
                                                                className="w-full bg-transparent border-none focus:bg-black/20 focus:ring-1 focus:ring-primary rounded p-1 outline-none font-mono resize-y min-h-[40px]" 
                                                            />
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })()}
                                        </div>
                                    )}

                                    {viewingEntityTab === 'video' && (
                                        <div className="space-y-4">
                                            {(() => {
                                                const cfg = ENTITY_MEDIA_REF_CONFIG.video;
                                                const currentVal = String(viewingEntity?.[cfg.field] || '').trim();
                                                return (
                                                    <div className="bg-black/20 p-3 rounded-lg border border-white/5 space-y-3">
                                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('视频参考', 'Video Reference')}</h4>
                                                        {currentVal ? (
                                                            <>
                                                                <video
                                                                    src={getSafeMediaUrl(getFullUrl(currentVal))}
                                                                    controls
                                                                    className="w-full rounded bg-black/40 max-h-56"
                                                                    preload="metadata"
                                                                />
                                                                <div className="flex items-center gap-2">
                                                                    <a
                                                                        href={getFullUrl(currentVal)}
                                                                        target="_blank"
                                                                        rel="noreferrer"
                                                                        className="flex-1 text-[10px] text-white/60 truncate hover:text-white"
                                                                        title={currentVal}
                                                                    >
                                                                        {currentVal}
                                                                    </a>
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => handleFieldUpdate(cfg.field, null)}
                                                                        className="px-2 py-1 rounded text-[10px] font-bold bg-red-500/15 hover:bg-red-500/25 text-red-100 flex-shrink-0"
                                                                    >
                                                                        {t('清除', 'Clear')}
                                                                    </button>
                                                                </div>
                                                            </>
                                                        ) : (
                                                            <div className="text-xs text-muted-foreground">{cfg.empty}</div>
                                                        )}
                                                        <div className="flex flex-wrap gap-2 items-center pt-1 border-t border-white/5">
                                                            <input
                                                                key="video-ref-input"
                                                                type="text"
                                                                defaultValue=""
                                                                onKeyDown={(e) => {
                                                                    if (e.key !== 'Enter') return;
                                                                    e.preventDefault();
                                                                    const v = e.currentTarget.value.trim();
                                                                    if (v) handleFieldUpdate(cfg.field, v);
                                                                    e.currentTarget.value = '';
                                                                }}
                                                                placeholder={cfg.placeholder}
                                                                className="flex-1 min-w-[160px] bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                            />
                                                            <button
                                                                type="button"
                                                                onClick={() => handlePickEntityMediaRefFromLibrary('video')}
                                                                className="px-2 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-white/20 text-white inline-flex items-center gap-1"
                                                            >
                                                                <FolderOpen size={12} /> {t('素材库', 'Library')}
                                                            </button>
                                                            <label className="px-2 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-white/20 text-white inline-flex items-center gap-1 cursor-pointer">
                                                                <Upload size={12} /> {entityMediaRefUploading ? t('上传中...', 'Uploading...') : t('上传', 'Upload')}
                                                                <input
                                                                    type="file"
                                                                    accept={cfg.accept}
                                                                    className="hidden"
                                                                    disabled={entityMediaRefUploading}
                                                                    onChange={(e) => {
                                                                        const file = e.target.files?.[0] || null;
                                                                        if (file) void handleUploadEntityMediaRef('video', file);
                                                                        e.target.value = '';
                                                                    }}
                                                                />
                                                            </label>
                                                        </div>
                                                        <div className="space-y-2 pt-2 border-t border-white/5">
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <div className="text-[10px] font-bold uppercase text-muted-foreground">
                                                                    {t('参考音频生成', 'Reference Audio Generation')}
                                                                </div>
                                                                <select
                                                                    value={entityRefAudioFunctionByTab.video || 'generate_entity_reference_audio_video'}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim() || 'generate_entity_reference_audio_video';
                                                                        setEntityRefAudioFunctionByTab((prev) => ({ ...prev, video: next }));
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1 text-[10px] text-white outline-none focus:border-primary/50"
                                                                    title={t('选择视频页生成参考音频所用路由', 'Select function route for video-tab reference audio generation')}
                                                                >
                                                                    {ENTITY_REF_AUDIO_FUNCTION_OPTIONS.map((opt) => (
                                                                        <option key={`video-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                                <FunctionApiSelector
                                                                    functionName={entityRefAudioFunctionByTab.video || 'generate_entity_reference_audio_video'}
                                                                    configs={functionApiConfigs}
                                                                    label={t('功能API: ', 'Function API: ')}
                                                                />
                                                            </div>
                                                            <textarea
                                                                value={entityRefAudioPrompt}
                                                                onChange={(e) => persistEntityRefAudioPrompt(e.target.value)}
                                                                placeholder={t('输入要生成音频的文案（将写入音频链接）...', 'Enter text for reference audio generation (result will fill audio URL)...')}
                                                                className="w-full min-h-[74px] bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-white focus:border-primary/50 outline-none resize-y"
                                                            />
                                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                                <select
                                                                    value={entityRefAudioTone}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim();
                                                                        setEntityRefAudioTone(next);
                                                                        persistEntityRefAudioProfile({
                                                                            tone: next,
                                                                            pace: entityRefAudioPace,
                                                                            emotion: entityRefAudioEmotion,
                                                                        });
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-primary/50"
                                                                >
                                                                    {ENTITY_REF_AUDIO_TONE_OPTIONS.map((opt) => (
                                                                        <option key={`video-tone-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                                <select
                                                                    value={entityRefAudioPace}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim();
                                                                        setEntityRefAudioPace(next);
                                                                        persistEntityRefAudioProfile({
                                                                            tone: entityRefAudioTone,
                                                                            pace: next,
                                                                            emotion: entityRefAudioEmotion,
                                                                        });
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-primary/50"
                                                                >
                                                                    {ENTITY_REF_AUDIO_PACE_OPTIONS.map((opt) => (
                                                                        <option key={`video-pace-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                                <select
                                                                    value={entityRefAudioEmotion}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim();
                                                                        setEntityRefAudioEmotion(next);
                                                                        persistEntityRefAudioProfile({
                                                                            tone: entityRefAudioTone,
                                                                            pace: entityRefAudioPace,
                                                                            emotion: next,
                                                                        });
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-primary/50"
                                                                >
                                                                    {ENTITY_REF_AUDIO_EMOTION_OPTIONS.map((opt) => (
                                                                        <option key={`video-emotion-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                            </div>
                                                            <div className="flex justify-end gap-2">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleRegenerateEntityRefAudioPrompt()}
                                                                    className="px-3 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-white/20 text-white"
                                                                >
                                                                    {t('按参数重建文案', 'Rebuild Prompt by Params')}
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    disabled={isGeneratingEntityRefAudio}
                                                                    onClick={() => void handleGenerateEntityReferenceAudio('video')}
                                                                    className="px-3 py-1.5 rounded text-xs font-bold bg-primary text-black hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-1"
                                                                >
                                                                    {isGeneratingEntityRefAudio ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
                                                                    {isGeneratingEntityRefAudio ? t('生成中...', 'Generating...') : t('生成参考音频', 'Generate Reference Audio')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    )}

                                    {viewingEntityTab === 'audio' && (
                                        <div className="space-y-4">
                                            {(() => {
                                                const cfg = ENTITY_MEDIA_REF_CONFIG.audio;
                                                const currentVal = String(viewingEntity?.[cfg.field] || '').trim();
                                                return (
                                                    <div className="bg-black/20 p-3 rounded-lg border border-white/5 space-y-3">
                                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground">{t('音频参考', 'Audio Reference')}</h4>
                                                        {currentVal ? (
                                                            <>
                                                                <SafeAudio
                                                                    src={currentVal}
                                                                    controls
                                                                    className="w-full"
                                                                    fallback={<div className="text-xs text-muted-foreground">{t('音频预览不可用', 'Audio preview unavailable')}</div>}
                                                                />
                                                                <div className="flex items-center gap-2">
                                                                    <a
                                                                        href={getFullUrl(currentVal)}
                                                                        target="_blank"
                                                                        rel="noreferrer"
                                                                        className="flex-1 text-[10px] text-white/60 truncate hover:text-white"
                                                                        title={currentVal}
                                                                    >
                                                                        {currentVal}
                                                                    </a>
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => handleFieldUpdate(cfg.field, null)}
                                                                        className="px-2 py-1 rounded text-[10px] font-bold bg-red-500/15 hover:bg-red-500/25 text-red-100 flex-shrink-0"
                                                                    >
                                                                        {t('清除', 'Clear')}
                                                                    </button>
                                                                </div>
                                                            </>
                                                        ) : (
                                                            <div className="text-xs text-muted-foreground">{cfg.empty}</div>
                                                        )}
                                                        <div className="flex flex-wrap gap-2 items-center pt-1 border-t border-white/5">
                                                            <input
                                                                key="audio-ref-input"
                                                                type="text"
                                                                defaultValue=""
                                                                onKeyDown={(e) => {
                                                                    if (e.key !== 'Enter') return;
                                                                    e.preventDefault();
                                                                    const v = e.currentTarget.value.trim();
                                                                    if (v) handleFieldUpdate(cfg.field, v);
                                                                    e.currentTarget.value = '';
                                                                }}
                                                                placeholder={cfg.placeholder}
                                                                className="flex-1 min-w-[160px] bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                            />
                                                            <button
                                                                type="button"
                                                                onClick={() => handlePickEntityMediaRefFromLibrary('audio')}
                                                                className="px-2 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-white/20 text-white inline-flex items-center gap-1"
                                                            >
                                                                <FolderOpen size={12} /> {t('素材库', 'Library')}
                                                            </button>
                                                            <label className="px-2 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-white/20 text-white inline-flex items-center gap-1 cursor-pointer">
                                                                <Upload size={12} /> {entityMediaRefUploading ? t('上传中...', 'Uploading...') : t('上传', 'Upload')}
                                                                <input
                                                                    type="file"
                                                                    accept={cfg.accept}
                                                                    className="hidden"
                                                                    disabled={entityMediaRefUploading}
                                                                    onChange={(e) => {
                                                                        const file = e.target.files?.[0] || null;
                                                                        if (file) void handleUploadEntityMediaRef('audio', file);
                                                                        e.target.value = '';
                                                                    }}
                                                                />
                                                            </label>
                                                        </div>
                                                        <div className="space-y-2 pt-2 border-t border-white/5">
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <div className="text-[10px] font-bold uppercase text-muted-foreground">
                                                                    {t('参考音频生成', 'Reference Audio Generation')}
                                                                </div>
                                                                <select
                                                                    value={entityRefAudioFunctionByTab.audio || 'generate_entity_reference_audio_audio'}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim() || 'generate_entity_reference_audio_audio';
                                                                        setEntityRefAudioFunctionByTab((prev) => ({ ...prev, audio: next }));
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1 text-[10px] text-white outline-none focus:border-primary/50"
                                                                    title={t('选择音频页生成参考音频所用路由', 'Select function route for audio-tab reference audio generation')}
                                                                >
                                                                    {ENTITY_REF_AUDIO_FUNCTION_OPTIONS.map((opt) => (
                                                                        <option key={`audio-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                                <FunctionApiSelector
                                                                    functionName={entityRefAudioFunctionByTab.audio || 'generate_entity_reference_audio_audio'}
                                                                    configs={functionApiConfigs}
                                                                    label={t('功能API: ', 'Function API: ')}
                                                                />
                                                            </div>
                                                            <textarea
                                                                value={entityRefAudioPrompt}
                                                                onChange={(e) => persistEntityRefAudioPrompt(e.target.value)}
                                                                placeholder={t('输入要生成音频的文案（将写入音频链接）...', 'Enter text for reference audio generation (result will fill audio URL)...')}
                                                                className="w-full min-h-[74px] bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-white focus:border-primary/50 outline-none resize-y"
                                                            />
                                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                                <select
                                                                    value={entityRefAudioTone}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim();
                                                                        setEntityRefAudioTone(next);
                                                                        persistEntityRefAudioProfile({
                                                                            tone: next,
                                                                            pace: entityRefAudioPace,
                                                                            emotion: entityRefAudioEmotion,
                                                                        });
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-primary/50"
                                                                >
                                                                    {ENTITY_REF_AUDIO_TONE_OPTIONS.map((opt) => (
                                                                        <option key={`audio-tone-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                                <select
                                                                    value={entityRefAudioPace}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim();
                                                                        setEntityRefAudioPace(next);
                                                                        persistEntityRefAudioProfile({
                                                                            tone: entityRefAudioTone,
                                                                            pace: next,
                                                                            emotion: entityRefAudioEmotion,
                                                                        });
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-primary/50"
                                                                >
                                                                    {ENTITY_REF_AUDIO_PACE_OPTIONS.map((opt) => (
                                                                        <option key={`audio-pace-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                                <select
                                                                    value={entityRefAudioEmotion}
                                                                    onChange={(e) => {
                                                                        const next = String(e.target.value || '').trim();
                                                                        setEntityRefAudioEmotion(next);
                                                                        persistEntityRefAudioProfile({
                                                                            tone: entityRefAudioTone,
                                                                            pace: entityRefAudioPace,
                                                                            emotion: next,
                                                                        });
                                                                    }}
                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-primary/50"
                                                                >
                                                                    {ENTITY_REF_AUDIO_EMOTION_OPTIONS.map((opt) => (
                                                                        <option key={`audio-emotion-${opt.value}`} value={opt.value}>{opt.label}</option>
                                                                    ))}
                                                                </select>
                                                            </div>
                                                            <div className="flex justify-end gap-2">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleRegenerateEntityRefAudioPrompt()}
                                                                    className="px-3 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-white/20 text-white"
                                                                >
                                                                    {t('按参数重建文案', 'Rebuild Prompt by Params')}
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    disabled={isGeneratingEntityRefAudio}
                                                                    onClick={() => void handleGenerateEntityReferenceAudio('audio')}
                                                                    className="px-3 py-1.5 rounded text-xs font-bold bg-primary text-black hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-1"
                                                                >
                                                                    {isGeneratingEntityRefAudio ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
                                                                    {isGeneratingEntityRefAudio ? t('生成中...', 'Generating...') : t('生成参考音频', 'Generate Reference Audio')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    )}

                                    {viewingEntityTab === 'generate' && (
                                        <div className="space-y-6">
                                            {/* Technical / Prompt */}
                                            <div className="space-y-2">
                                                <div className="grid grid-cols-1 gap-3">
                                                    <div>
                                                        <div className="text-[10px] font-bold uppercase text-muted-foreground mb-1">{t('中文提示词', 'Chinese Prompt')}</div>
                                                        <textarea
                                                            value={viewingEntity.generation_prompt_cn || ''}
                                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, generation_prompt_cn: e.target.value }))}
                                                            onBlur={(e) => handleFieldUpdate('generation_prompt_cn', e.target.value)}
                                                            className="w-full p-3 bg-black/20 rounded-lg border border-white/5 text-xs font-mono text-white/70 focus:text-white/90 focus:border-primary outline-none min-h-[90px] resize-y"
                                                            placeholder={t('输入中文生图提示词...', 'Enter Chinese generation prompt...')}
                                                        />
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Fast Generate Section */}
                                    {viewingEntity.id !== 'new' && (
                                        <div className="space-y-4 pt-4 border-t border-white/5">
                                            {/* Auto-detected Visual Dependencies */}
                                            {parseVisualDependencies(viewingEntity?.visual_dependencies).length > 0 && (
                                                <div className="relative">
                                                    <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">{t('资产参考', 'Asset References')}</label>
                                                    <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                                                        {parseVisualDependencies(viewingEntity.visual_dependencies).map((dep, idx) => {
                                                            const depEntity = resolveDependencyEntity(dep, allEntities);

                                                            return (
                                                                <div key={idx} className="flex-shrink-0 w-24 bg-black/40 border border-white/10 rounded-lg p-1.5 flex flex-col gap-1 relative group">
                                                                    <div className="aspect-square bg-black rounded overflow-hidden">
                                                                         {depEntity?.image_url ? (
                                                                             <SafeImage src={depEntity.image_url} alt={dep} className="w-full h-full object-cover" />
                                                                         ) : (
                                                                             <div className="w-full h-full flex items-center justify-center bg-white/5">
                                                                                 <ImageIcon className="w-4 h-4 opacity-40" />
                                                                             </div>
                                                                         )}
                                                                    </div>
                                                                    <div className="text-[10px] truncate font-bold text-white px-0.5" title={dep}>
                                                                        {depEntity ? depEntity.name : dep}
                                                                    </div>
                                                                    {!depEntity && (
                                                                        <div className="text-[8px] text-red-400 px-0.5">
                                                                            {entityListLoading ? t('加载中', 'Loading') : t('未找到', 'Not Found')}
                                                                        </div>
                                                                    )}
                                                                    
                                                                    <div className="absolute inset-0 bg-black/80 opacity-0 group-hover:opacity-100 flex flex-col gap-1 items-center justify-center transition-opacity rounded-lg p-1">
                                                                         {depEntity?.image_url ? (
                                                                             <>
                                                                                <button
                                                                                    title={t('同时更新图片与锚点并退出', 'Reuse asset and exit')}
                                                                                    onClick={async (e) => {
                                                                                        e.preventDefault();
                                                                                        e.stopPropagation();
                                                                                        if (depEntity?.image_url) {
                                                                                            await updateEntityImage(depEntity.image_url, false, viewingEntity, {
                                                                                                skipAnalyze: true,
                                                                                                extraFields: { anchor_description: depEntity.anchor_description }
                                                                                            });
                                                                                            setViewingEntity(null);
                                                                                        }
                                                                                    }}
                                                                                    className="w-full text-[10px] py-1 bg-primary hover:bg-primary/80 border-transparent rounded text-white font-bold"
                                                                                >
                                                                                    {t('复用资产', 'Reuse Asset')}
                                                                                </button>
                                                                                <button
                                                                                    title={t('设为参考图', 'Set as Ref Image')}
                                                                                    onClick={(e) => {
                                                                                        e.preventDefault();
                                                                                        e.stopPropagation();
                                                                                        setRefImage({ url: depEntity.image_url, entity_id: depEntity.id, original_name: depEntity.name });
                                                                                    }}
                                                                                    className="w-full text-[10px] py-1 bg-secondary hover:bg-secondary/80 text-secondary-foreground border border-border rounded font-bold"
                                                                                >
                                                                                    {t('仅用作参考', 'Ref Only')}
                                                                                </button>
                                                                             </>
                                                                         ) : (
                                                                             <div className="text-[10px] text-muted-foreground">{t('无图', 'No Image')}</div>
                                                                         )}
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Reference Image Select */}
                                            <div className="relative">
                                                     <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">{t('参考图（可选）', 'Ref Image (Optional)')}</label>

                                                     {!refImage ? (
                                                         <div className="flex gap-2 items-center">
                                                              <div className="flex-1 flex gap-2">
                                                                  <button
                                                                    onClick={() => setRefSelectionMode(refSelectionMode === 'assets' ? null : 'assets')}
                                                                    className={`p-2 rounded border border-white/10 text-xs font-bold hover:bg-white/10 flex items-center gap-1 ${refSelectionMode === 'assets' ? 'bg-primary/20 text-primary border-primary/50' : 'bg-black/40 text-muted-foreground'}`}
                                                                  >
                                                                      <FolderOpen size={14} /> Assets
                                                                  </button>
                                                                  <div className="relative overflow-hidden min-w-[6rem]">
                                                                      <button className="w-full p-2 bg-black/40 border border-white/10 rounded text-xs font-bold hover:bg-white/10 text-muted-foreground flex items-center gap-1 justify-center disabled:cursor-not-allowed" disabled={isUploadingRef}>
                                                                        {isUploadingRef ? <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : <Upload size={14} />} {isUploadingRef ? t("上传中...", "Uploading...") : t("上传", "Upload")}
                                                                      </button>
                                                                      <input
                                                                        type="file"
                                                                        className="absolute inset-0 opacity-0 cursor-pointer disabled:cursor-not-allowed" disabled={isUploadingRef}
                                                                        accept="image/*"
                                                                        onChange={handleRefUpload}
                                                                      />
                                                                  </div>
                                                              </div>

                                                              <div className="w-1/3 relative">
                                                                  <input
                                                                      type="text"
                                                                      placeholder="URL..."
                                                                      onBlur={(e) => {
                                                                          if (e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                      }}
                                                                      onKeyDown={(e) => {
                                                                            if (e.key === 'Enter' && e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                      }}
                                                                      className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-white focus:border-primary/50 outline-none"
                                                                  />
                                                              </div>
                                                         </div>
                                                     ) : (
                                                         <div className="flex gap-3 bg-black/40 border border-white/10 rounded-lg p-2 items-center relative group">
                                                             <div className="w-10 h-10 bg-black rounded overflow-hidden flex-shrink-0 border border-white/5">
                                                                 <SafeImage src={refImage.url} alt="ref" className="w-full h-full object-cover" />
                                                             </div>
                                                             <div className="flex-1 overflow-hidden">
                                                                 <div className="text-xs font-bold text-white truncate">{refImage.name || 'Reference Image'}</div>
                                                                 <div className="text-[10px] text-muted-foreground flex gap-2">
                                                                     <span>{refImage.dimensions || 'Unknown Size'}</span>
                                                                     {refImage.type && <span className="uppercase">{refImage.type}</span>}
                                                                 </div>
                                                             </div>
                                                             <button
                                                                 onClick={() => setRefImage(null)}
                                                                 className="p-1 hover:bg-white/10 rounded-md text-white/50 hover:text-white"
                                                             >
                                                                 <X size={14} />
                                                             </button>
                                                         </div>
                                                     )}

                                                     {refSelectionMode === 'assets' && !refImage && (
                                                         <div className="absolute bottom-full left-0 right-0 mb-2 z-10 bg-[#09090b] border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col">
                                                             <div className="p-2 border-b border-white/10 flex justify-between items-center bg-black/20">
                                                                 <span className="text-xs font-bold text-muted-foreground ml-2">{t('从素材库选择', 'Select from Assets')}</span>
                                                                 <button onClick={() => setRefSelectionMode(null)}><X size={14} className="text-white/50 hover:text-white"/></button>
                                                             </div>
                                                             <div className="p-3 space-y-3">
                                                                 <div className="grid grid-cols-3 gap-2">
                                                                     <select
                                                                         value={assetEpisodeFilter}
                                                                         onChange={(e) => setAssetEpisodeFilter(e.target.value)}
                                                                         className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                                     >
                                                                         <option value="all">{t('全部分集', 'All Episodes')}</option>
                                                                         {assetEpisodeOptions.map((item) => (
                                                                             <option key={item.value} value={item.value}>{item.label}</option>
                                                                         ))}
                                                                     </select>
                                                                     <select
                                                                         value={assetImageTypeFilter}
                                                                         onChange={(e) => setAssetImageTypeFilter(e.target.value)}
                                                                         className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                                     >
                                                                         {assetScopedImageTypeOptions.map((item) => (
                                                                             <option key={item.value} value={item.value}>{item.label}</option>
                                                                         ))}
                                                                     </select>
                                                                     <select
                                                                         value={assetNameFilter}
                                                                         onChange={(e) => setAssetNameFilter(e.target.value)}
                                                                         disabled={assetNameOptions.length === 0}
                                                                         className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none disabled:opacity-50"
                                                                     >
                                                                         {assetNameOptions.length === 0 ? (
                                                                             <option value="">{t('暂无可选素材', 'No matching assets')}</option>
                                                                         ) : (
                                                                             assetNameOptions.map((item) => (
                                                                                 <option key={item.value} value={item.value}>{item.label}</option>
                                                                             ))
                                                                         )}
                                                                     </select>
                                                                 </div>
                                                                 {assetsLoading ? (
                                                                     <div className="py-6 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                                                                         <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                                         {t('素材加载中...', 'Loading assets...')}
                                                                     </div>
                                                                 ) : selectedLibraryAsset ? (
                                                                     <div className="flex gap-3 items-start">
                                                                         <div className="w-20 h-20 shrink-0 bg-black/40 rounded border border-white/10 overflow-hidden">
                                                                             <SafeImage src={selectedLibraryAsset.url} alt={getAssetDisplayName(selectedLibraryAsset)} className="w-full h-full object-cover" />
                                                                         </div>
                                                                         <div className="flex-1 min-w-0 space-y-1">
                                                                            <div className="text-xs font-semibold text-white break-words leading-snug" title={getAssetDisplayName(selectedLibraryAsset)}>{getAssetDisplayName(selectedLibraryAsset)}</div>
                                                                             <div className="text-[10px] text-muted-foreground">{t('分集：', 'Ep: ')}{getAssetEpisodeLabel(selectedLibraryAsset)}</div>
                                                                             <div className="text-[10px] text-muted-foreground">{t('类型：', 'Type: ')}{getAssetImageTypeLabel(getAssetImageType(selectedLibraryAsset) || '')}</div>
                                                                             <div className="flex gap-2 mt-1">
                                                                                 <button
                                                                                     onClick={async () => {
                                                                                         const depEntityId = getAssetEntityId(selectedLibraryAsset);
                                                                                         const depEntity = allEntities?.find(e => String(e.id) === String(depEntityId));
                                                                                         await updateEntityImage(selectedLibraryAsset.url, false, viewingEntity, {
                                                                                             skipAnalyze: true,
                                                                                             extraFields: { anchor_description: depEntity?.anchor_description }
                                                                                         });
                                                                                         setRefSelectionMode(null);
                                                                                         setViewingEntity(null);
                                                                                     }}
                                                                                     className="px-2 py-1 rounded text-[10px] font-bold bg-primary/80 hover:bg-primary text-white"
                                                                                 >
                                                                                     {t('复用资产', 'Reuse Asset')}
                                                                                 </button>
                                                                                 <button
                                                                                     onClick={() => {
                                                                                         setRefImage(selectedLibraryAsset);
                                                                                         setRefSelectionMode(null);
                                                                                     }}
                                                                                     className="px-2 py-1 rounded text-[10px] font-bold bg-secondary hover:bg-secondary/80 text-secondary-foreground border border-border"
                                                                                 >
                                                                                     {t('仅用作参考', 'Ref Only')}
                                                                                 </button>
                                                                             </div>
                                                                         </div>
                                                                     </div>
                                                                 ) : (
                                                                     <div className="py-6 text-center text-xs text-muted-foreground">{t('暂无符合条件的素材', 'No assets matched')}</div>
                                                                 )}
                                                             </div>
                                                         </div>
                                                     )}
                                            </div>

                                            <div className="rounded-lg border border-white/10 bg-black/20 p-3 space-y-3">
                                                <div className="flex items-center justify-between gap-2">
                                                    <div>
                                                        <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-white/70">{t('生成历史', 'Generation History')}</div>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => fetchSubjectGenerationHistory(viewingEntity)}
                                                        disabled={subjectGenerationHistoryLoading}
                                                        className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10 disabled:opacity-50"
                                                    >
                                                        <RefreshCw className={subjectGenerationHistoryLoading ? 'animate-spin' : ''} size={12} />
                                                        {t('刷新', 'Refresh')}
                                                    </button>
                                                </div>
                                                {subjectGenerationHistoryLoading ? (
                                                    <div className="flex items-center justify-center gap-2 rounded border border-dashed border-white/10 px-3 py-4 text-xs text-muted-foreground">
                                                        <Loader2 className="h-4 w-4 animate-spin" />
                                                    </div>
                                                ) : subjectGenerationHistory.length === 0 ? (
                                                    <div className="rounded border border-dashed border-white/10 px-3 py-4 text-center text-xs text-muted-foreground">
                                                        {t('无历史。', 'No history yet.')}
                                                    </div>
                                                ) : (
                                                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1 custom-scrollbar">
                                                        {subjectGenerationHistory.map((item) => {
                                                            const itemId = String(item?.job_id || item?.id || Math.random()).trim();
                                                            const status = String(item?.status || '').trim().toLowerCase();
                                                            const canPreview = Boolean(item?.resultUrl);
                                                            const isDeleting = subjectGenerationHistoryDeletingId === itemId;
                                                            return (
                                                                <div key={itemId} className="rounded-lg border border-white/10 bg-black/30 p-2.5 flex gap-3">
                                                                    <div className="h-12 w-12 shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/40 flex items-center justify-center">
                                                                        {canPreview ? (
                                                                            <SafeImage src={item.resultUrl} className="h-full w-full object-cover" fallback={<ImageIcon className="h-4 w-4 opacity-40" />} />
                                                                        ) : <ImageIcon className="h-4 w-4 opacity-40" />}
                                                                    </div>
                                                                    <div className="min-w-0 flex-1 space-y-1">
                                                                        <div className="flex items-start justify-between gap-2">
                                                                            <div className="truncate text-xs font-semibold text-white">{item.displayLabel}</div>
                                                                            <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${status === 'completed' ? 'bg-emerald-500/15 text-emerald-200' : 'bg-amber-500/15 text-amber-100'}`}>{status}</span>
                                                                        </div>
                                                                        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                                                                            <button onClick={() => canPreview && updateEntityImage(item.resultUrl, false, viewingEntity)} disabled={!canPreview} className="inline-flex items-center gap-1 rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/80 hover:bg-white/10">
                                                                                <ImageIcon size={10} /> {t('设为当前', 'Use Result')}
                                                                            </button>
                                                                            <button onClick={() => handleDeleteSubjectGenerationHistoryItem(item)} disabled={isDeleting} className="inline-flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-300 hover:bg-red-500/20">
                                                                                <Trash2 size={10} /> {t('删除', 'Delete')}
                                                                            </button>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    </div>
                                    )}

                                    {viewingEntityTab === 'advanced' && (
                                        <div className="flex flex-col h-full space-y-4">
                                            <div className="mb-4">
                                                <h4 className="text-xs font-bold uppercase text-muted-foreground mb-2">{t('修改资产', 'Modify Asset')}</h4>
                                                <p className="text-[10px] text-white/50 mb-4">
                                                    {t('输入具体指令以修改该资产的提示词。提交后将自动应用修改并重新生成图片。', 'Enter specific instructions to modify the prompt. Generation will be triggered automatically.')}
                                                </p>
                                            </div>
                                            <div className="flex-1 min-h-[250px]">
                                                <textarea
                                                    className="w-full h-full text-sm bg-white/5 border border-white/10 rounded-md p-4 text-white placeholder-white/30 resize-y outline-none focus:border-primary/50"
                                                    placeholder={t("输入局部修改指令（例如：把狗的颜色换成黑色）...", "Enter local modification instructions (e.g., change the dog's color to black)...")}
                                                    value={advancedInstruction}
                                                    onChange={e => setAdvancedInstruction(e.target.value)}
                                                />
                                            </div>
                                            <div className="flex items-center gap-2 mt-4 pb-4">
                                                <button
                                                    type="button"
                                                    className="flex-1 bg-white/10 hover:bg-white/20 text-white border-none py-6 flex items-center justify-center gap-2 rounded-md"
                                                    disabled={!advancedInstruction.trim() || isAdvancedOptimizing || isAdvancedLocalModifying || generating}
                                                    onClick={async () => {
                                                        setIsAdvancedLocalModifying(true);
                                                        try {
                                                            const base = viewingEntity?.generation_prompt_cn || "";
                                                            const appended = advancedInstruction.trim();
                                                            const finalPrompt = base ? `${base}. ${appended}, keeping everything else unchanged.` : appended;
                                                            
                                                            setPromptDrafts(prev => ({ ...prev, cn: finalPrompt }));
                                                            setPrompt(finalPrompt);

                                                            // Update Entity
                                                            const updated = { ...viewingEntity, generation_prompt_cn: finalPrompt };
                                                            setViewingEntity(updated);
                                                            updateEntity(updated.id, { generation_prompt_cn: finalPrompt });

                                                            const autoRefs = [];
                                                            if (viewingEntity?.image_url) {
                                                                autoRefs.push({
                                                                    url: viewingEntity.image_url,
                                                                    type: 'image',
                                                                    weight: 0.8
                                                                });
                                                            }

                                                            const extraProviderOptions = {
                                                                is_gemini_multi_turn_edit: true,
                                                                gemini_base_prompt: base,
                                                                gemini_edit_instruction: appended,
                                                            };

                                                            await handleGenerate(viewingEntity, autoRefs, finalPrompt, extraProviderOptions);
                                                        } finally {
                                                            setIsAdvancedLocalModifying(false);
                                                        }
                                                    }}
                                                >
                                                    {isAdvancedLocalModifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Paintbrush className="w-4 h-4" />}
                                                    <span className="font-semibold text-sm">{t('局部修改', 'Local Modify')}</span>
                                                </button>

                                                <button
                                                    type="button"
                                                    className="flex-1 bg-primary/20 hover:bg-primary/30 text-primary border-none py-6 flex flex-col items-center justify-center py-2 h-auto min-h-12 rounded-md"
                                                    disabled={isAdvancedOptimizing || !advancedInstruction.trim() || isAdvancedLocalModifying || generating}
                                                    onClick={async () => {
                                                        setIsAdvancedOptimizing(true);
                                                        if (onLog) onLog(t('正在通过大模型优化提示词...', 'Optimizing prompt using LLM...'), 'process');
                                                        try {
                                                            const base = viewingEntity?.generation_prompt_cn || "";
                                                            const res = await refinePrompt(base, advancedInstruction, 'image');
                                                            if (res && res.refined_prompt) {
                                                                const optimized = res.refined_prompt;
                                                                setPromptDrafts(prev => ({ ...prev, cn: optimized }));
                                                                setPrompt(optimized);

                                                                // Update Entity
                                                                const updated = { ...viewingEntity, generation_prompt_cn: optimized };
                                                                setViewingEntity(updated);
                                                                updateEntity(updated.id, { generation_prompt_cn: optimized });

                                                                const autoRefs = [];
                                                                if (viewingEntity?.image_url) {
                                                                    autoRefs.push({
                                                                        url: viewingEntity.image_url,
                                                                        type: 'image',
                                                                        weight: 0.5
                                                                    });
                                                                }

                                                                if (onLog) onLog(t('已生成新提示词，准备拉起生成...', 'Generated new prompt, ready to regenerate...'), 'info');
                                                                try {
                                                                    await handleGenerate(viewingEntity, autoRefs, optimized);
                                                                    if (onLog) onLog(t('提交成功', 'Submitted successfully'), 'success');
                                                                } catch (err) {
                                                                    if (onLog) onLog(t('生成失败', 'Generation failed'), 'error');
                                                                }
                                                            } else {
                                                                if (onLog) onLog(t('优化失败，请稍后再试', 'Optimization failed, please try again'), 'error');
                                                            }
                                                        } catch (e) {
                                                            console.error("Refine prompt failed", e);
                                                            if (onLog) onLog(t('指令分析失败', 'Instruction analysis failed') + ': ' + e.message, 'error');
                                                        } finally {
                                                            setIsAdvancedOptimizing(false);
                                                        }
                                                    }}
                                                >
                                                    <div className="flex items-center gap-2">
                                                        {isAdvancedOptimizing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                                                        <span className="font-semibold text-sm">{t('重新生成', 'Regenerate')}</span>
                                                    </div>
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                </div>
                                
                                <div className="p-4 border-t border-white/10 bg-black/20 flex justify-end gap-3">
                                    <button 
                                        onClick={(e) => handleDeleteEntity(e, viewingEntity)}
                                        className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-md text-sm font-bold transition-colors flex items-center gap-2"
                                    >
                                        <Trash2 size={16} /> Delete
                                    </button>
                                    {viewingEntityTab === 'generate' && (
                                        <button 
                                            onClick={() => {
                                                handleGenerate(viewingEntity, null, getEntityPromptByLang(viewingEntity, effectivePromptSubmitLang));
                                            }}
                                            disabled={viewingEntityImageLocked || generating}
                                            className="px-4 py-2 bg-primary hover:bg-primary/90 text-black rounded-md text-sm font-bold transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {(generating || viewingEntityImageLocked) ? (
                                                <RefreshCw className="animate-spin" size={16} />
                                            ) : (
                                                <Wand2 size={16} />
                                            )}
                                            {(generating || viewingEntityImageLocked) ? t('生成中...', 'Generating...') : t('生成图片', 'Generate Image')}
                                        </button>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    </div>
                        );
                    })()
                )}
            </AnimatePresence>

            {/* Image Selection Modal */}
            <AnimatePresence>
                {showImageModal && (
                    (() => {
                        const selectedEntityImageLocked = isSubjectImageActionLocked(selectedEntity) || (isBatchGeneratingEntities && !selectedEntity?.image_url && !getSubjectImageJobEntry(selectedEntity));
                        const selectedEntityHasRunningImageJob = Boolean(selectedEntity?.id && getSubjectImageJobEntry(selectedEntity)) || (isBatchGeneratingEntities && !selectedEntity?.image_url && !getSubjectImageJobEntry(selectedEntity));
                        return (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-2xl h-[650px] flex flex-col shadow-2xl overflow-hidden"
                        >
                            <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/20">
                                <h3 className="font-bold text-lg">{t('为主体选择图片', 'Select Image for')} {selectedEntity?.name}</h3>
                                <div className="flex items-center gap-2">
                                    <button
                                        type="button"
                                        onClick={() => void handleRemoveEntityImage(selectedEntity)}
                                        disabled={selectedEntityImageLocked || !selectedEntity?.image_url}
                                        className="inline-flex items-center gap-1 rounded border border-amber-400/25 bg-amber-500/10 px-2.5 py-1.5 text-xs font-bold text-amber-100 hover:bg-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={selectedEntityImageLocked ? t('图片任务运行中，不能移除图片', 'Image job is running; image removal is disabled') : t('移除图片关联', 'Remove image association')}
                                    >
                                        <Unlink size={14} />
                                        {t('移除图片', 'Remove Image')}
                                    </button>
                                    <button onClick={() => setShowImageModal(false)} className="text-white/50 hover:text-white">
                                        <X size={20} />
                                    </button>
                                </div>
                            </div>

                            {selectedEntityImageLocked && (
                                <div className="px-4 py-2 border-b border-amber-400/20 bg-amber-500/10 text-xs text-amber-100">
                                    {t('当前主体图片任务运行中。更换、上传、移除和高级改图操作已暂时锁定；如需处理，请先停止任务。', 'A subject image job is currently running. Replace, upload, remove, and advanced image editing actions are temporarily locked; stop the job first if you need to modify the image.')}
                                </div>
                            )}

                            <div className="flex border-b border-white/10">
                                {['library', 'upload', 'generate', 'advanced'].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setImageModalTab(tab)}
                                        disabled={selectedEntityImageLocked && tab !== 'generate'}
                                        className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${imageModalTab === tab ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'}`}
                                    >
                                        {tab === 'library'
                                            ? t('素材库', 'Library')
                                            : tab === 'upload'
                                                ? t('上传', 'Upload')
                                                : tab === 'generate'
                                                    ? t('生成', 'Generate')
                                                    : t('高级', 'Advanced')}
                                    </button>
                                ))}
                            </div>

                            <div
                                ref={imageLibraryViewportRef}
                                onScroll={(e) => setImageLibraryScrollTop(e.currentTarget.scrollTop || 0)}
                                className="flex-1 overflow-y-auto p-4 custom-scrollbar"
                            >
                                {imageModalTab === 'library' && (
                                    <div className="space-y-4">
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                            <select
                                                value={assetEpisodeFilter}
                                                onChange={(e) => setAssetEpisodeFilter(e.target.value)}
                                                className="bg-black/40 border border-white/10 rounded-md px-2 py-2 text-xs text-white focus:border-primary/50 outline-none"
                                            >
                                                <option value="all">{t('全部分集', 'All Episodes')}</option>
                                                {assetEpisodeOptions.map((item) => (
                                                    <option key={item.value} value={item.value}>{item.label}</option>
                                                ))}
                                            </select>
                                            <select
                                                value={assetImageTypeFilter}
                                                onChange={(e) => setAssetImageTypeFilter(e.target.value)}
                                                className="bg-black/40 border border-white/10 rounded-md px-2 py-2 text-xs text-white focus:border-primary/50 outline-none"
                                            >
                                                {assetScopedImageTypeOptions.map((item) => (
                                                    <option key={item.value} value={item.value}>{item.label}</option>
                                                ))}
                                            </select>
                                            <select
                                                value={assetNameFilter}
                                                onChange={(e) => setAssetNameFilter(e.target.value)}
                                                disabled={assetNameOptions.length === 0}
                                                className="bg-black/40 border border-white/10 rounded-md px-2 py-2 text-xs text-white focus:border-primary/50 outline-none disabled:opacity-50"
                                            >
                                                {assetNameOptions.length === 0 ? (
                                                    <option value="">{t('暂无可选素材', 'No matching assets')}</option>
                                                ) : (
                                                    assetNameOptions.map((item) => (
                                                        <option key={item.value} value={item.value}>{item.label}</option>
                                                    ))
                                                )}
                                            </select>
                                        </div>

                                        <div className="text-[11px] text-muted-foreground">
                                            {t('当前筛选命中素材：', 'Matched assets: ')}{libraryFilteredAssets.length}
                                        </div>

                                        {assetsLoading ? (
                                            <div className="text-center py-16 text-muted-foreground text-sm flex items-center justify-center gap-2">
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                {t('加载素材中...', 'Loading assets...')}
                                            </div>
                                        ) : selectedLibraryAsset ? (
                                            <div className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-3">
                                                <div className="aspect-video sm:aspect-[16/9] bg-black/40 rounded-lg overflow-hidden border border-white/10">
                                                    <SafeImage
                                                        src={selectedLibraryAsset.url}
                                                        alt={getAssetDisplayName(selectedLibraryAsset)}
                                                        className="w-full h-full object-contain"
                                                    />
                                                </div>
                                                <div className="space-y-1.5">
                                                    <div className="text-sm font-semibold text-white break-words leading-snug" title={getAssetDisplayName(selectedLibraryAsset)}>{getAssetDisplayName(selectedLibraryAsset)}</div>
                                                    <div className="text-[11px] text-muted-foreground truncate">
                                                        {t('分集：', 'Episode: ')}{getAssetEpisodeLabel(selectedLibraryAsset)}
                                                    </div>
                                                    <div className="text-[11px] text-muted-foreground truncate">
                                                        {t('类型：', 'Type: ')}{getAssetImageTypeLabel(getAssetImageType(selectedLibraryAsset) || t('未标注', 'Unknown'))}
                                                    </div>
                                                    <div className="text-[11px] text-muted-foreground truncate">
                                                        {t('项目：', 'Project: ')}{getAssetProjectLabel(selectedLibraryAsset)}
                                                    </div>
                                                </div>
                                                <div className="flex gap-2 w-full">
                                                    <button
                                                        onClick={() => {
                                                            if (selectedEntityImageLocked) {
                                                                notifySubjectImageActionLocked(selectedEntity);
                                                                return;
                                                            }
                                                            handleSelectAsset(selectedLibraryAsset, true);
                                                        }}
                                                        disabled={selectedEntityImageLocked}
                                                        title={t('同时使用该素材的图片与其绑定的锚点来替换当前实体', 'Replace image and its associated anchor.')}
                                                        className="flex-1 rounded-md px-1 py-1.5 text-[10px] sm:text-[11px] font-bold bg-primary/80 hover:bg-primary text-white disabled:opacity-50 disabled:cursor-not-allowed"
                                                    >
                                                        {t('替换图与锚点', 'Replace Both')}
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            if (selectedEntityImageLocked) {
                                                                notifySubjectImageActionLocked(selectedEntity);
                                                                return;
                                                            }
                                                            handleSelectAsset(selectedLibraryAsset, false);
                                                        }}
                                                        disabled={selectedEntityImageLocked}
                                                        title={t('仅将该图片作为当前实体的参考图，不修改当前的描点描述', 'Only apply image as a reference without altering the anchor.')}
                                                        className="flex-1 rounded-md px-1 py-1.5 text-[10px] sm:text-[11px] font-bold bg-secondary hover:bg-secondary/80 text-secondary-foreground border border-border disabled:opacity-50 disabled:cursor-not-allowed"
                                                    >
                                                        {t('仅换图', 'Ref Image Only')}
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-center py-16 text-muted-foreground text-sm">
                                                {t('暂无符合条件的图片素材', 'No image assets matched')}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {imageModalTab === 'upload' && (
                                    <div className="flex flex-col items-center justify-center h-full space-y-4">
                                        <div className="p-8 border-2 border-dashed border-white/10 rounded-xl bg-black/20 hover:border-primary/50 hover:bg-primary/5 transition-all w-full max-w-sm flex flex-col items-center justify-center cursor-pointer relative">
                                            <input 
                                                type="file" 
                                                accept="image/*" 
                                                onChange={handleUpload}
                                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                                disabled={uploadState !== 'idle' || selectedEntityImageLocked} 
                                            />
                                            {uploadState !== 'idle' ? (
                                                uploadState === 'completed' ? (
                                                    <CheckCircle className="text-green-500 mb-2" size={32} />
                                                ) : uploadState === 'analyzing' ? (
                                                    <RefreshCw className="animate-spin text-purple-400 mb-2" size={32} />
                                                ) : (
                                                    <RefreshCw className="animate-spin text-blue-400 mb-2" size={32} />
                                                )
                                            ) : (
                                                <Upload className="text-muted-foreground mb-2" size={32} />
                                            )}
                                            <span className={`text-sm font-medium ${
                                                uploadState === 'uploading' ? 'text-blue-400' :
                                                uploadState === 'analyzing' ? 'text-purple-400' :
                                                uploadState === 'completed' ? 'text-green-500' :
                                                'text-muted-foreground'
                                            }`}>
                                                {uploadState === 'uploading' && t('正在上传...', 'Uploading...')}
                                                {uploadState === 'analyzing' && t('正在分析...', 'Analyzing...')}
                                                {uploadState === 'completed' && t('已提交后台分析', 'Submitted to background analysis')}
                                                {uploadState === 'idle' && t('点击或拖拽图片到此处', 'Click or drop image here')}
                                            </span>
                                        </div>
                                        
                                        <div className="w-full max-w-sm mt-8">
                                             <div className="text-xs text-muted-foreground mb-2 uppercase font-bold tracking-wider">{t('或通过 URL 导入', 'Or import from URL')}</div>
                                             <div className="flex gap-2">
                                                <input 
                                                    id="url-import-input"
                                                    type="text" 
                                                    placeholder={t('请输入图片链接（https://...）', 'Enter image URL (https://...)')} 
                                                    className="flex-1 bg-black/40 border border-white/10 rounded-md px-3 py-2 text-sm focus:border-primary/50 outline-none"
                                                    disabled={selectedEntityImageLocked || uploadState !== 'idle'}
                                                    onKeyDown={async (e) => {
                                                        if (e.key === 'Enter') {
                                                            const url = e.target.value;
                                                            if (!url) return;
                                                            setUploadState('analyzing');
                                                            const updatedEntity = await updateEntityImage(url, false, null, { skipAnalyze: true });
                                                            if (updatedEntity) {
                                                                const analyzed = await handleAnalyzeEntity(updatedEntity);
                                                                if (!analyzed) {
                                                                    setUploadState('idle');
                                                                    return;
                                                                }
                                                                setUploadState('completed');
                                                                setTimeout(() => {
                                                                    setShowImageModal(false);
                                                                    setUploadState('idle');
                                                                }, 1500);
                                                            } else {
                                                                setUploadState('idle');
                                                            }
                                                        }
                                                    }}
                                                />
                                                <button 
                                                    disabled={selectedEntityImageLocked || uploadState !== 'idle'} 
                                                    className="p-2 bg-white/10 hover:bg-white/20 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                                                    onClick={async () => {
                                                        const el = document.getElementById('url-import-input');
                                                        const url = el?.value;
                                                        if (!url) return;
                                                        setUploadState('analyzing');
                                                        const updatedEntity = await updateEntityImage(url, false, null, { skipAnalyze: true });
                                                        if (updatedEntity) {
                                                            const analyzed = await handleAnalyzeEntity(updatedEntity);
                                                            if (!analyzed) {
                                                                setUploadState('idle');
                                                                return;
                                                            }
                                                            setUploadState('completed');
                                                            setTimeout(() => {
                                                                setShowImageModal(false);
                                                                setUploadState('idle');
                                                            }, 1500);
                                                        } else {
                                                            setUploadState('idle');
                                                        }
                                                    }}
                                                >
                                                    <LinkIcon size={18} />
                                                </button>
                                             </div>
                                        </div>
                                    </div>
                                )}

                                {imageModalTab === 'advanced' && (
                                    <div className="flex flex-col h-full">
                                        <div className="mb-4">
                                            <h4 className="text-xs font-bold uppercase text-muted-foreground mb-2">{t('高级优化', 'Advanced Refinement')}</h4>
                                            <p className="text-[10px] text-white/50 mb-4">
                                                Use AI to refine or modify the image with step-by-step instructions.
                                            </p>
                                        </div>
                                        <div className="flex-1">
                                            <RefineControl 
                                                originalText={selectedEntity?.generation_prompt_cn || ""}
                                                onUpdate={(txt) => {
                                                    setPrompt(txt);
                                                    setPromptDrafts(prev => ({ ...prev, cn: txt }));
                                                }}
                                                currentImage={selectedEntity?.image_url}
                                                onImageUpdate={updateEntityImage}
                                                projectId={projectId}
                                                featureInjector={(text) => {
                                                    const epInfo = currentEpisode?.episode_info || {};
                                                    const processed = processPrompt(text, epInfo, allEntities);
                                                    return { text: processed, modified: processed !== text };
                                                }}
                                                onPickMedia={(cb) => openMediaPicker(cb, {
                                                    entityId: selectedEntity?.id,
                                                    disableShotFilter: true,
                                                    defaultSecondaryKind: 'entity',
                                                    defaultSubCategory: 'character',
                                                })}
                                                type="image"
                                            />
                                        </div>
                                    </div>
                                )}

                                {imageModalTab === 'generate' && (
                                    <div className="flex flex-col h-full">
                                        {selectedEntityHasRunningImageJob && (
                                            <div className="mb-3 rounded border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 flex items-center justify-between gap-3">
                                                <div className="flex items-center gap-2">
                                                    {stoppingSubjectImageJobs[String(selectedEntity.id)] ? <Loader2 className="animate-spin" size={12} /> : <RefreshCw className="animate-spin" size={12} />}
                                                    {stoppingSubjectImageJobs[String(selectedEntity.id)]
                                                        ? t('该主体停止请求发送中，请稍候。', 'Stop request is being sent for this subject. Please wait.')
                                                        : String(subjectImageJobs[String(selectedEntity.id)]?.status || '').toLowerCase() === 'persisting'
                                                            ? t('该主体已完成生成，正在等待稳定图片同步到素材库。', 'This subject finished generating and is waiting for the durable image to sync back into the library.')
                                                        : String(subjectImageJobs[String(selectedEntity.id)]?.status || '').toLowerCase() === 'running'
                                                            ? t('该主体正在运行中，即使关闭窗口也会继续。', 'This subject is running in background and will continue even if you close this window.')
                                                            : String(subjectImageJobs[String(selectedEntity.id)]?.status || '').toLowerCase() === 'queued'
                                                                ? t('该主体正在排队中，开始后将自动运行。', 'This subject is queued and will run automatically once started.')
                                                                : t('该主体正在生成中，即使关闭窗口也会继续。', 'This subject is generating in background and will continue even if you close this window.')}
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={handleForceStopSubjectImage}
                                                    disabled={Boolean(stoppingSubjectImageJobs[String(selectedEntity.id)])}
                                                    className="shrink-0 inline-flex items-center gap-1 rounded border border-red-400/30 bg-red-500/15 px-2 py-1 text-[11px] font-bold text-red-100 hover:bg-red-500/25 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                                                    title={t('强制停止该主体的后台图片任务，并解除当前运行状态', 'Force-stop this subject background image task and clear the current running state')}
                                                >
                                                    {stoppingSubjectImageJobs[String(selectedEntity.id)] ? <Loader2 className="animate-spin" size={12} /> : <X size={12} />}
                                                    {stoppingSubjectImageJobs[String(selectedEntity.id)] ? t('停止中', 'Stopping') : t('停止', 'Stop')}
                                                </button>
                                            </div>
                                        )}
                                        <textarea
                                            value={prompt}
                                            onChange={(e) => {
                                                const nextText = e.target.value;
                                                setPrompt(nextText);
                                                setPromptDrafts(prev => ({ ...prev, cn: nextText }));
                                            }}
                                            placeholder="Describe the image you want to generate. Use [Global Style] for episode style. Prefer CHAR:[@Name] (or [@Name]) to reference subjects."
                                            className="w-full h-32 bg-black/40 border border-white/10 rounded-lg p-4 text-sm focus:border-primary/50 outline-none resize-none mb-4"
                                        />
                                        
                                        {/* Auto-detected Visual Dependencies */}
                                        {parseVisualDependencies(selectedEntity?.visual_dependencies).length > 0 && (
                                            <div className="mb-4">
                                                <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">{t('资产参考', 'Asset References')}</label>
                                                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                                                    {parseVisualDependencies(selectedEntity.visual_dependencies).map((dep, idx) => {
                                                        const depEntity = resolveDependencyEntity(dep, allEntities);
                                                        
                                                        return (
                                                            <div key={idx} className="flex-shrink-0 w-24 bg-black/40 border border-white/10 rounded-lg p-1.5 flex flex-col gap-1 relative group">
                                                                <div className="aspect-square bg-black rounded overflow-hidden">
                                                                     {depEntity?.image_url ? (
                                                                         <SafeImage src={depEntity.image_url} alt={dep} className="w-full h-full object-cover" />
                                                                     ) : (
                                                                         <div className="w-full h-full flex items-center justify-center bg-white/5">
                                                                             <Users size={16} className="text-white/20"/>
                                                                         </div>
                                                                     )}
                                                                </div>
                                                                <div className="text-[10px] truncate font-bold text-white px-0.5" title={dep}>
                                                                    {depEntity ? depEntity.name : dep}
                                                                </div>
                                                                {!depEntity && (
                                                                    <div className="text-[8px] text-red-400 px-0.5">
                                                                        {entityListLoading ? t('加载中', 'Loading') : t('未找到', 'Not Found')}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                        
                                        {/* Reference Image Select */}
                                        <div className="mb-4 relative">
                                                 <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">{t('参考图（可选）', 'Ref Image (Optional)')}</label>
                                                 
                                                 {!refImage ? (
                                                     <div className="flex gap-2 items-center">
                                                          <div className="flex-1 flex gap-2">
                                                              {/* Selection Buttons */}
                                                              <button 
                                                                onClick={() => setRefSelectionMode(refSelectionMode === 'assets' ? null : 'assets')}
                                                                className={`p-2 rounded border border-white/10 text-xs font-bold hover:bg-white/10 flex items-center gap-1 ${refSelectionMode === 'assets' ? 'bg-primary/20 text-primary border-primary/50' : 'bg-black/40 text-muted-foreground'}`}
                                                              >
                                                                  <FolderOpen size={14} /> Assets
                                                              </button>
                                                              <div className="relative overflow-hidden min-w-[6rem]">
                                                                  <button className="w-full p-2 bg-black/40 border border-white/10 rounded text-xs font-bold hover:bg-white/10 text-muted-foreground flex items-center gap-1 justify-center disabled:cursor-not-allowed" disabled={isUploadingRef}>
                                                                    {isUploadingRef ? <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : <Upload size={14} />} {isUploadingRef ? t("上传中...", "Uploading...") : t("上传", "Upload")}
                                                                  </button>
                                                                  <input 
                                                                    type="file" 
                                                                    className="absolute inset-0 opacity-0 cursor-pointer disabled:cursor-not-allowed" disabled={isUploadingRef} 
                                                                    accept="image/*"
                                                                    onChange={handleRefUpload}
                                                                  />
                                                              </div>
                                                          </div>
                                                          
                                                          {/* URL Input (Fallback) */}
                                                          <div className="w-1/3 relative">
                                                              <input 
                                                                  type="text" 
                                                                  placeholder="URL..." 
                                                                  onBlur={(e) => {
                                                                      if (e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                  }}
                                                                  onKeyDown={(e) => {
                                                                        if (e.key === 'Enter' && e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                  }}
                                                                  className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-white focus:border-primary/50 outline-none"
                                                              />
                                                          </div>
                                                     </div>
                                                 ) : (
                                                     // Selected Preview State
                                                     <div className="flex gap-3 bg-black/40 border border-white/10 rounded-lg p-2 items-center relative group">
                                                         <div className="w-10 h-10 bg-black rounded overflow-hidden flex-shrink-0 border border-white/5">
                                                             <SafeImage src={refImage.url} alt="ref" className="w-full h-full object-cover" />
                                                         </div>
                                                         <div className="flex-1 overflow-hidden">
                                                             <div className="text-xs font-bold text-white truncate">{refImage.name || 'Reference Image'}</div>
                                                             <div className="text-[10px] text-muted-foreground flex gap-2">
                                                                 <span>{refImage.dimensions || 'Unknown Size'}</span>
                                                                 {refImage.type && <span className="uppercase">{refImage.type}</span>}
                                                             </div>
                                                         </div>
                                                         <button 
                                                             onClick={() => setRefImage(null)}
                                                             className="p-1 hover:bg-white/10 rounded-md text-white/50 hover:text-white"
                                                         >
                                                             <X size={14} />
                                                         </button>
                                                     </div>
                                                 )}

                                                 {/* Asset Picker Popover */}
                                                 {refSelectionMode === 'assets' && !refImage && (
                                                     <div className="absolute top-full left-0 right-0 mt-2 z-10 bg-[#09090b] border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col">
                                                         <div className="p-2 border-b border-white/10 flex justify-between items-center bg-black/20">
                                                             <span className="text-xs font-bold text-muted-foreground ml-2">{t('从素材中选择', 'Select from Assets')}</span>
                                                             <button onClick={() => setRefSelectionMode(null)}><X size={14} className="text-white/50 hover:text-white"/></button>
                                                         </div>
                                                         <div className="p-3 space-y-3">
                                                             <div className="grid grid-cols-3 gap-2">
                                                                 <select
                                                                     value={assetEpisodeFilter}
                                                                     onChange={(e) => setAssetEpisodeFilter(e.target.value)}
                                                                     className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                                 >
                                                                     <option value="all">{t('全部分集', 'All Episodes')}</option>
                                                                     {assetEpisodeOptions.map((item) => (
                                                                         <option key={item.value} value={item.value}>{item.label}</option>
                                                                     ))}
                                                                 </select>
                                                                 <select
                                                                     value={assetImageTypeFilter}
                                                                     onChange={(e) => setAssetImageTypeFilter(e.target.value)}
                                                                     className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                                 >
                                                                     {assetScopedImageTypeOptions.map((item) => (
                                                                         <option key={item.value} value={item.value}>{item.label}</option>
                                                                     ))}
                                                                 </select>
                                                                 <select
                                                                     value={assetNameFilter}
                                                                     onChange={(e) => setAssetNameFilter(e.target.value)}
                                                                     disabled={assetNameOptions.length === 0}
                                                                     className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none disabled:opacity-50"
                                                                 >
                                                                     {assetNameOptions.length === 0 ? (
                                                                         <option value="">{t('暂无可选素材', 'No matching assets')}</option>
                                                                     ) : (
                                                                         assetNameOptions.map((item) => (
                                                                             <option key={item.value} value={item.value}>{item.label}</option>
                                                                         ))
                                                                     )}
                                                                 </select>
                                                             </div>
                                                             {assetsLoading ? (
                                                                 <div className="py-6 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                                                                     <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                                     {t('素材加载中...', 'Loading assets...')}
                                                                 </div>
                                                             ) : selectedLibraryAsset ? (
                                                                 <div className="flex gap-3 items-start">
                                                                     <div className="w-20 h-20 shrink-0 bg-black/40 rounded border border-white/10 overflow-hidden">
                                                                         <SafeImage src={selectedLibraryAsset.url} alt={getAssetDisplayName(selectedLibraryAsset)} className="w-full h-full object-cover" />
                                                                     </div>
                                                                     <div className="flex-1 min-w-0 space-y-1">
                                                                        <div className="text-xs font-semibold text-white break-words leading-snug" title={getAssetDisplayName(selectedLibraryAsset)}>{getAssetDisplayName(selectedLibraryAsset)}</div>
                                                                         <div className="text-[10px] text-muted-foreground">{t('分集：', 'Ep: ')}{getAssetEpisodeLabel(selectedLibraryAsset)}</div>
                                                                         <div className="text-[10px] text-muted-foreground">{t('类型：', 'Type: ')}{getAssetImageTypeLabel(getAssetImageType(selectedLibraryAsset) || '')}</div>
                                                                         <button
                                                                             onClick={() => {
                                                                                 setRefImage(selectedLibraryAsset);
                                                                                 setRefSelectionMode(null);
                                                                             }}
                                                                             className="mt-1 px-2.5 py-1 rounded text-xs font-bold bg-primary/80 hover:bg-primary text-white"
                                                                         >
                                                                             {t('选用', 'Use')}
                                                                         </button>
                                                                     </div>
                                                                 </div>
                                                             ) : (
                                                                 <div className="py-6 text-center text-xs text-muted-foreground">{t('暂无符合条件的素材', 'No assets matched')}</div>
                                                             )}
                                                         </div>
                                                     </div>
                                                 )}
                                        </div>

                                        <div className="flex justify-end items-center gap-2">
                                            <button
                                                onClick={handleGenerate}
                                                disabled={generating || selectedEntityHasRunningImageJob || !String(promptDrafts.cn || getEntityPromptByLang(selectedEntity, 'cn') || '').trim()}
                                                className="flex items-center space-x-2 bg-primary text-black px-6 py-2 rounded-lg font-bold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                            >
                                                {generating || selectedEntityHasRunningImageJob ? (
                                                    <RefreshCw className="animate-spin" size={18} />
                                                ) : (
                                                    <Wand2 size={18} />
                                                )}
                                                <span>{(generating || selectedEntityHasRunningImageJob) ? t('生成中...', 'Generating...') : t('生成图片', 'Generate Image')}</span>
                                            </button>
                                        </div>

                                        <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3 space-y-3">
                                            <div className="flex items-center justify-between gap-2">
                                                <div>
                                                    <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-white/70">{t('生成历史', 'Generation History')}</div>
                                                    <div className="text-[11px] text-muted-foreground">{t('显示该主体最近的生图与重构结果。', 'Recent subject image and reconstruction results for this subject.')}</div>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => fetchSubjectGenerationHistory(selectedEntity)}
                                                    disabled={subjectGenerationHistoryLoading || !selectedEntity?.id}
                                                    className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10 disabled:opacity-50"
                                                >
                                                    <RefreshCw className={subjectGenerationHistoryLoading ? 'animate-spin' : ''} size={12} />
                                                    {t('刷新', 'Refresh')}
                                                </button>
                                            </div>
                                            {subjectGenerationHistoryLoading ? (
                                                <div className="flex items-center justify-center gap-2 rounded border border-dashed border-white/10 px-3 py-6 text-xs text-muted-foreground">
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                    {t('正在加载主体生成历史...', 'Loading subject generation history...')}
                                                </div>
                                            ) : subjectGenerationHistory.length === 0 ? (
                                                <div className="rounded border border-dashed border-white/10 px-3 py-6 text-center text-xs text-muted-foreground">
                                                    {t('该主体还没有生成历史。', 'No generation history for this subject yet.')}
                                                </div>
                                            ) : (
                                                <div className="space-y-2 max-h-64 overflow-y-auto pr-1 custom-scrollbar">
                                                    {subjectGenerationHistory.map((item) => {
                                                        const itemId = String(item?.job_id || item?.id || Math.random()).trim();
                                                        const status = String(item?.status || '').trim().toLowerCase();
                                                        const canPreview = Boolean(item?.resultUrl);
                                                        const createdText = item?.created_at ? new Date(item.created_at).toLocaleString() : '-';
                                                        const isDeleting = subjectGenerationHistoryDeletingId === itemId;
                                                        return (
                                                            <div key={itemId} className="rounded-lg border border-white/10 bg-black/30 p-2.5">
                                                                <div className="flex gap-3">
                                                                    <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/40 flex items-center justify-center">
                                                                        {canPreview ? (
                                                                            <SafeImage src={item.resultUrl} className="h-full w-full object-cover" fallback={<ImageIcon className="h-5 w-5 opacity-40" />} />
                                                                        ) : (
                                                                            <ImageIcon className="h-5 w-5 opacity-40" />
                                                                        )}
                                                                    </div>
                                                                    <div className="min-w-0 flex-1 space-y-1">
                                                                        <div className="flex items-start justify-between gap-2">
                                                                            <div className="min-w-0">
                                                                                <div className="truncate text-sm font-semibold text-white">{item.displayLabel}</div>
                                                                                <div className="text-[11px] text-muted-foreground truncate">{item.subjectName || selectedEntity?.name || '-'}</div>
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
                                                                                onClick={() => canPreview && updateEntityImage(item.resultUrl, true, selectedEntity)}
                                                                                disabled={!canPreview}
                                                                                className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/80 hover:bg-white/10 disabled:opacity-40"
                                                                            >
                                                                                <ImageIcon size={12} />
                                                                                {t('设为当前', 'Use Result')}
                                                                            </button>
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
                                                                                onClick={() => handleDeleteSubjectGenerationHistoryItem(item)}
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
                                        
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </div>
                        );
                    })()
                )}
            </AnimatePresence>
            
            <MediaPickerModal 
                isOpen={pickerConfig.isOpen}
                onClose={() => setPickerConfig(prev => ({ ...prev, isOpen: false }))}
                onSelect={(url, type, selectedItems) => {
                    if (pickerConfig.callback) pickerConfig.callback(url, type, selectedItems);
                    setPickerConfig(prev => ({ ...prev, isOpen: false }));
                }}
                projectId={projectId}
                context={{
                    ...(pickerConfig.context || {}),
                    disableShotFilter: true,
                    defaultSecondaryKind: 'entity',
                }}
                entities={allEntities}
                episodeId={currentEpisode?.id}
                uiLang={uiLang}
            />

            {/* History Modal */}
            {showHistoryModal && (
                <div className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-[#1a1b1e] rounded-xl border border-white/10 w-full max-w-lg flex flex-col max-h-[80vh] overflow-hidden shadow-2xl">
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#25262b]">
                            <h3 className="font-bold text-white flex items-center gap-2">
                                <History size={16} className="text-primary" />
                                {t('实体历史', 'Entity History')}
                            </h3>
                            <button onClick={() => setShowHistoryModal(false)} className="text-white/50 hover:text-white/90 transition-colors bg-white/5 hover:bg-white/10 p-1.5 rounded">
                                <X size={16} />
                            </button>
                        </div>
                        <div className="p-4 overflow-y-auto w-full">
                            {historyLoading ? (
                                <div className="py-8 flex justify-center"><Loader2 className="animate-spin text-white/50" /></div>
                            ) : historyList.length === 0 ? (
                                <div className="py-8 text-center text-white/40 text-sm">
                                    {t('暂无历史记录。', 'No history records found.')}
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {historyList.map(h => (
                                        <div key={h.id} className="p-3 bg-white/5 rounded-lg border border-white/10 flex items-center justify-between">
                                            <div className="text-xs text-white/70">
                                                <div className="font-medium text-white mb-0.5">{h.remark || t('普通快照', 'Snapshot')}</div>
                                                <div>{h.created_at ? new Date(h.created_at).toLocaleString() : ''}</div>
                                            </div>
                                            <button 
                                                onClick={() => handleRestoreHistory(h.id)}
                                                className="px-2.5 py-1 bg-primary text-white text-xs font-semibold rounded hover:bg-primary/90"
                                            >
                                                {t('恢复到此版本', 'Restore')}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

