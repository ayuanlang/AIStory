
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
    getFullUrl, createInitialFrameTrimState, clampFrameTrimPercent, normalizeFrameTrimMargins, brokenMediaUrls, brokenSceneImageUrls, warmMediaUrls, shouldBypassBrokenMediaCache, rememberBrokenMediaUrl, isBrokenMediaUrl, rememberWarmMediaUrl, isWarmMediaUrl, getSafeMediaUrl, extractImageJobResultUrl, rememberBrokenSceneImageUrl, isBrokenSceneImageUrl, normalizeBatchParallelLimit, normalizeAsciiSubjectSeparatorsForDeps, normalizeSubjectNameForDeps, normalizeSubjectKeyForDeps, normalizeAsciiSubjectSeparators, normalizeSubjectName, normalizeSubjectKey, normalizeImportSubjectKey, IMG_PLACEHOLDER_SRC, parseVisualDependencies, SafeImage, SafeAudio, normalizeMediaRefList, areMediaRefListsEqual, collectMatchedEntitiesFromPrompt, collectMatchedEntityImageUrlsFromPrompt, SCENE_SUBJECT_TYPE_LABELS, getSceneSubjectStatusKey, splitSceneSubjectNames, normalizeSceneSubjectDefaultType, parseTypedSceneSubjectToken, extractSceneSubjectRefsFromField, buildSceneSubjectNameCandidates, extractSceneSubjectRefs, findMatchingEntityByType, findMissingSceneSubjectRefs, findCrossTypeEntityMatches, buildSceneSubjectPlaceholderPayload, createMissingSceneSubjectPlaceholders, collectMatchedSubjectImageUrlsFromPrompt, resolveUnifiedVideoMode, buildAutoVideoRefList, resolveShotVideoPosterUrl, LazyHoverVideo, InViewVideo, ManagedVideoPlayer, parseEpisodeNumberFromText, normalizeEpisodeTitleForDisplay, buildEntityNegativePrompt, normalizeImageSizeOption, normalizeAspectRatioOption, parseAspectRatioParts, parseAspectRatioValue, reduceAspectRatioParts, buildAspectRatioString, inferImageSizeFromResolution, getEpisodePreferredImageSize, getEpisodePreferredAspectRatio, getProjectPreferredImageSize, getProjectPreferredAspectRatio, buildShotDiptychPlan, getShotDiptychLayoutLabel, buildShotDiptychLayoutInstruction, buildShotDiptychAspectContract, getShotDiptychSeamTrimPx, getShotDiptychSeamBiasPx, getShotDiptychFallbackCropPx, JOINT_DIPTYCH_SPLIT_UPLOAD_VERSION, SHOT_FRAME_ASSET_UPLOAD_VERSION, hashStableText, buildJointShotDiptychUploadIdempotencyKey, buildShotFrameAssetUploadIdempotencyKey, collectSupportedAspectRatioOptions, collectSupportedImageSizeOptions, selectBestShotDiptychRequestAspectRatio, selectBestSupportedImageSize, resolveShotPanelExportResolution, resolveShotDiptychRequestResolution, getResolutionByAspectAndImageSize, SHOT_IMAGE_CFG_MIN, SHOT_IMAGE_CFG_MAX, SHOT_IMAGE_CFG_STEP, SHOT_IMAGE_CFG_FALLBACK, clampShotImageCfg, resolveShotImageCfgDefault, extractDialogueOnlyFromPrompt, inferLanguageCodeFromProjectLanguage, buildVoicePromptWithEntityContext, buildEpisodeDisplayLabel, mergeEntityPoolWithSubjectIndex
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
    fetchProjectSubjectInventoryPrompt,
    recomputeEpisodeCostEstimation,
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
const isDummySubject = (itemName) => {
    if (!itemName) return false;
    const lcName = String(itemName).trim().toLowerCase().replace(/[\s_\-]/g, '');
    return ['subjectindex', 'subjectsindex', 'sceneanalysis', 'entities', 'character', 'characters', 'prop', 'props', 'environment', 'environments', 'role', 'roles', 'item', 'items', 'scene', 'scenes', '角色', '道具', '场景', '人物', '环境', '物件'].includes(lcName);
};

export const ScriptEditor = ({ activeEpisode, projectId, project, onUpdateScript, onUpdateEpisodeInfo, onLog, onImportText, onSwitchToScenes, uiLang = 'zh' }) => {
    const functionApiConfigs = useFunctionApis('script_analysis');
    const navigate = useNavigate();
    const [segments, setSegments] = useState([]);
    const [showMerged, setShowMerged] = useState(false);
    const [mergedContent, setMergedContent] = useState('');
    const [rawContent, setRawContent] = useState('');
    const [llmResultContent, setLlmResultContent] = useState('');
    const [llmRawResultContent, setLlmRawResultContent] = useState('');
    const [llmAssetRawResultContent, setLlmAssetRawResultContent] = useState('');
    const [analysisRuntimeMeta, setAnalysisRuntimeMeta] = useState(null);
    const [isRawMode, setIsRawMode] = useState(false);
    const [analysisAttentionNotes, setAnalysisAttentionNotes] = useState('');
    const [isSavingAnalysisAttentionNotes, setIsSavingAnalysisAttentionNotes] = useState(false);
    const [availableSubjectAssets, setAvailableSubjectAssets] = useState([]);
    const [selectedReuseSubjectIds, setSelectedReuseSubjectIds] = useState([]);
    const [reuseSubjectTypeFilter, setReuseSubjectTypeFilter] = useState('all');
    const [reuseSubjectKeyword, setReuseSubjectKeyword] = useState('');
    const [isLoadingSubjectAssets, setIsLoadingSubjectAssets] = useState(false);
    const [isSavingReuseSubjects, setIsSavingReuseSubjects] = useState(false);
    const [analysisFlowStatus, setAnalysisFlowStatus] = useState({ phase: 'idle', message: '' });
    const [analysisUiReport, setAnalysisUiReport] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isRecomputingEpisodeCost, setIsRecomputingEpisodeCost] = useState(false);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [subjectIndexText, setSubjectIndexText] = useState('');
    const [adaptationText, setAdaptationText] = useState('');
    const [isEditingSubjectIndex, setIsEditingSubjectIndex] = useState(false);
    const [isRetryingPhase2, setIsRetryingPhase2] = useState(false);
    const [systemPrompt, setSystemPrompt] = useState('');
    const [userPrompt, setUserPrompt] = useState('');
    const [isSuperuser, setIsSuperuser] = useState(false);
    const isSuperuserRef = useRef(false);
    const SUBJECT_INDEX_PARSE_ERROR = '第一阶段未解析到完整的 Subject Index 区块，请确认返回结果中包含完整的 Subject Index 内容（如标题区块或 subject_no=... 条目）后重试。';

    const extractAnalysisSections = useCallback((rawText) => {
        const authoritativeSubjectText = String(rawText || '');
        let extractedText = '';
        let extractedAdaptationText = '';
        let hasStructuredSubjectIndex = false;

        if (!authoritativeSubjectText) {
            return {
                authoritativeSubjectText,
                subjectIndexText: '',
                adaptationText: '',
                hasStructuredSubjectIndex: false,
            };
        }

        const adaptMatch = authoritativeSubjectText.match(/\*\*\s*剧本改编(?:补充说明)?\s*\*\*[:：]?\s*([\s\S]*?)(?=\n(?:-{3,}|###?|\|)|$)/i)
            || authoritativeSubjectText.match(/###?\s*剧本改编(?:补充说明)?\s*\n([\s\S]*?)(?=\n(?:-{3,}|###?|\|)|$)/i)
            || authoritativeSubjectText.match(/剧本改编(?:补充说明)?[:：\n]\s*([\s\S]*?)(?=\n(?:-{3,}|###?|\|)|$)/i);
        if (adaptMatch) {
            extractedAdaptationText = (adaptMatch[1] || adaptMatch[2] || adaptMatch[3] || '').trim();
        }

        const dashMatch = authoritativeSubjectText.match(/-{5,}\s*\n([\s\S]*?)\n\s*-{5,}/);
        if (dashMatch && dashMatch[1].trim()) {
            extractedText = dashMatch[1].trim();
            hasStructuredSubjectIndex = true;
        } else {
            const match = authoritativeSubjectText.match(/(?:###?|##)\s*(?:Subject Index|角色|道具|场景|设计资产|Entities)[\s\S]*/i);
            if (match) {
                extractedText = match[0];
                hasStructuredSubjectIndex = true;
            } else {
                const pipeMatch = authoritativeSubjectText.match(/(?:^|\n)\s*(subject_no\s*=\s*S\d+[\s\S]*)/i);
                if (pipeMatch && String(pipeMatch[1] || '').trim()) {
                    extractedText = String(pipeMatch[1] || '').trim();
                    hasStructuredSubjectIndex = true;
                } else {
                    extractedText = authoritativeSubjectText;
                }
            }
        }

        return {
            authoritativeSubjectText,
            subjectIndexText: extractedText,
            adaptationText: extractedAdaptationText,
            hasStructuredSubjectIndex,
        };
    }, []);

    useEffect(() => {
        isSuperuserRef.current = isSuperuser;
    }, [isSuperuser]);

    useEffect(() => {
        if (!activeEpisode) return;
        const authoritativeSubjectText = llmRawResultContent || llmResultContent || activeEpisode.ai_scene_analysis_result || '';
        if (authoritativeSubjectText) {
            const { subjectIndexText: extractedText, adaptationText: extractedAdaptationText } = extractAnalysisSections(authoritativeSubjectText);

            // 剧本分析界面的修改是持久化的，不再从llm直接回填与持久化：
            // 我们只进行UI展现刷新（用户自行通过编辑决定保存）
            if (extractedText !== subjectIndexText) {
                setSubjectIndexText(extractedText);
            }
            if (extractedAdaptationText !== adaptationText) {
                setAdaptationText(extractedAdaptationText);
            }
        }
    }, [llmRawResultContent, llmResultContent, activeEpisode?.ai_scene_analysis_result, activeEpisode?.ai_scene_analysis_subject_index, activeEpisode?.ai_scene_analysis_adaptation, activeEpisode?.id, adaptationText, extractAnalysisSections, subjectIndexText]);

    const [subjectConsistencyReport, setSubjectConsistencyReport] = useState(null);
    const [subjectConsistencyResultText, setSubjectConsistencyResultText] = useState('');
    const [subjectRecoveryModal, setSubjectRecoveryModal] = useState({
        open: false,
        status: 'idle',
        missing: [],
        message: '',
        details: '',
    });
    const [isRecoveringMissingSubjects, setIsRecoveringMissingSubjects] = useState(false);
    const [isCheckingCoreCoverage, setIsCheckingCoreCoverage] = useState(false);
    const [isCheckingSubjectConsistency, setIsCheckingSubjectConsistency] = useState(false);
    const [isImportingEntities, setIsImportingEntities] = useState(false);
    const [activeAnalysisTaskId, setActiveAnalysisTaskId] = useState('');
    const [isStoppingAnalysisTask, setIsStoppingAnalysisTask] = useState(false);
    const [workspaceOpStatus, setWorkspaceOpStatus] = useState({
        running: false,
        action: '',
        progress: 0,
        message: '',
    });
    const [jsonEntityDetailModal, setJsonEntityDetailModal] = useState({
        open: false,
        groupKey: '',
        groupLabelZh: '',
        groupLabelEn: '',
        item: null,
    });
    const [coreCoverageReport, setCoreCoverageReport] = useState(null);
    const [coreCoverageResultText, setCoreCoverageResultText] = useState('');
    const [postAnalysisCheckModal, setPostAnalysisCheckModal] = useState({
        open: false,
        status: 'idle',
        message: '',
        guidance: [],
    });
    const [pendingSwitchAfterPostChecks, setPendingSwitchAfterPostChecks] = useState(false);
    const [analysisHeartbeatTick, setAnalysisHeartbeatTick] = useState(0);
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);

    const formatDurationMs = useCallback((ms) => {
        const value = Number(ms || 0);
        if (!Number.isFinite(value) || value <= 0) return '0s';
        if (value < 1000) return `${Math.round(value)}ms`;
        return `${(value / 1000).toFixed(1)}s`;
    }, []);

    const computeAnalysisPhaseTimings = useCallback((marks) => {
        const toNumber = (v) => {
            const n = Number(v || 0);
            return Number.isFinite(n) && n > 0 ? n : 0;
        };
        const diffMs = (start, end) => {
            const s = toNumber(start);
            const e = toNumber(end);
            if (!s || !e || e < s) return null;
            return Math.max(0, e - s);
        };

        const submitStartedAt = toNumber(marks?.submitStartedAt);
        const analyzeStartedAt = toNumber(marks?.analyzeStartedAt);
        const llmReturnedAt = toNumber(marks?.llmReturnedAt);
        const importStartedAt = toNumber(marks?.importStartedAt);
        const importFinishedAt = toNumber(marks?.importFinishedAt);
        const persistStartedAt = toNumber(marks?.persistStartedAt);
        const persistFinishedAt = toNumber(marks?.persistFinishedAt);
        const completedAt = toNumber(marks?.completedAt) || Date.now();

        const latestPrePostAt = Math.max(
            llmReturnedAt,
            importFinishedAt,
            persistFinishedAt,
            persistStartedAt,
            importStartedAt,
            analyzeStartedAt,
            submitStartedAt
        );

        return {
            submitMs: diffMs(submitStartedAt, analyzeStartedAt),
            llmMs: diffMs(analyzeStartedAt, llmReturnedAt),
            importMs: diffMs(importStartedAt, importFinishedAt),
            persistMs: diffMs(persistStartedAt, persistFinishedAt),
            postProcessMs: diffMs(latestPrePostAt, completedAt),
            totalMs: diffMs(submitStartedAt, completedAt),
        };
    }, []);

    useEffect(() => {
        if (!isAnalyzing || analysisFlowStatus?.phase !== 'analyzing') {
            setAnalysisHeartbeatTick(0);
            return;
        }

        const timer = setInterval(() => {
            setAnalysisHeartbeatTick(prev => prev + 1);
        }, 1000);

        return () => clearInterval(timer);
    }, [isAnalyzing, analysisFlowStatus?.phase]);

    const analysisHeartbeatElapsedMs = useMemo(() => {
        if (!isAnalyzing || analysisFlowStatus?.phase !== 'analyzing') return 0;
        const startedAt = Number(analysisUiReport?.startedAt || 0);
        if (!Number.isFinite(startedAt) || startedAt <= 0) return 0;
        return Math.max(0, Date.now() - startedAt);
    }, [isAnalyzing, analysisFlowStatus?.phase, analysisUiReport?.startedAt, analysisHeartbeatTick]);

    const showAnalysisWarningStatus = useCallback((warnings = []) => {
        const uniqueWarnings = [...new Set((warnings || []).map(w => String(w || '').trim()).filter(Boolean))];
        if (uniqueWarnings.length === 0) return;
        const warningSummary = uniqueWarnings[0];
        const hasMore = uniqueWarnings.length > 1;
        setAnalysisFlowStatus({
            phase: 'warning',
            message: hasMore
                ? `${t('分析返回告警：', 'Analysis warning: ')}${warningSummary} (+${uniqueWarnings.length - 1})`
                : `${t('分析返回告警：', 'Analysis warning: ')}${warningSummary}`,
        });
        setTimeout(() => {
            setAnalysisFlowStatus(prev => (prev?.phase === 'warning' ? { phase: 'idle', message: '' } : prev));
        }, 8000);
    }, [t]);

    useEffect(() => {
        if (isAnalyzing) return;

        const reportStatus = String(analysisUiReport?.status || '').trim().toLowerCase();
        if (!reportStatus || reportStatus === 'running') return;

        setAnalysisFlowStatus((prev) => {
            const prevPhase = String(prev?.phase || '').trim().toLowerCase();
            const prevMessage = String(prev?.message || '').trim();

            if (reportStatus === 'completed') {
                if (prevPhase === 'completed' || prevPhase === 'warning' || prevPhase === 'failed') return prev;
                return {
                    phase: 'completed',
                    message: prevMessage || t('🎉 剧本分析与场景构建已完成，快来看看吧！', 'Analysis and import completed.'),
                };
            }

            if (reportStatus === 'warning') {
                if (prevPhase === 'warning') return prev;
                return {
                    phase: 'warning',
                    message: prevMessage || String(analysisUiReport?.warning || '').trim() || t('分析已结束，但有告警需要处理。', 'Analysis finished with warnings that need review.'),
                };
            }

            if (reportStatus === 'failed') {
                if (prevPhase === 'failed') return prev;
                return {
                    phase: 'failed',
                    message: prevMessage || String(analysisUiReport?.error || '').trim() || t('分析失败。', 'Analysis failed.'),
                };
            }

            return prev;
        });
    }, [analysisUiReport?.error, analysisUiReport?.status, analysisUiReport?.warning, isAnalyzing, t]);

    const localizeAnalysisWarningCode = useCallback((code) => {
        const normalized = String(code || '').trim();
        if (!normalized) return '';
        if (normalized === 'ANALYSIS_OUTPUT_TRUNCATED') {
            return t('AI Script Analysis 的最后一段输出在长度上限处停止，当前结果未通过完整性校验。', 'The final AI Script Analysis segment stopped at the length limit, and the result did not pass integrity checks.');
        }
        if (normalized === 'ANALYSIS_OUTPUT_CONTINUED') {
            return t('AI Script Analysis 曾因长度上限分段，系统已自动续写；是否最终完整以结果校验为准。', 'AI Script Analysis hit a length limit and auto-continuation was applied; final completeness depends on integrity checks.');
        }
        if (normalized === 'ANALYSIS_JSON_INVALID') {
            return t('AI Script Analysis 检测到结构片段损坏。', 'AI Script Analysis detected invalid structured fragments.');
        }
        if (normalized === 'ANALYSIS_SUBJECTS_UNVERIFIED') {
            return '';
        }
        if (normalized === 'ANALYSIS_SUBJECTS_INCOMPLETE') {
            return '';
        }
        if (normalized === 'ANALYSIS_LLM_CALL_FAILED_RETRIED') {
            return t('生成期间 AI 走神了一小下，不过我们已经帮您自动重连啦。请稍微留意一下最终的报告详情哦。', 'LLM call failures occurred during scene analysis; the system retried/fallback to continue. Please review result details and warnings.');
        }
        return '';
    }, [t]);

    const isLogOnlyAnalysisWarningCode = useCallback((code) => {
        const normalized = String(code || '').trim().toUpperCase();
        return normalized === 'ANALYSIS_OUTPUT_TRUNCATED' || normalized === 'ANALYSIS_OUTPUT_CONTINUED';
    }, []);

    const isLogOnlyAnalysisWarningMessage = useCallback((message) => {
        const normalized = String(message || '').trim().toLowerCase();
        if (!normalized) return false;
        return (
            normalized.includes('analysis_output_truncated')
            || normalized.includes('analysis_output_continued')
            || normalized.includes('response hit a length limit')
            || normalized.includes('split by length limits and auto-continuation was applied')
            || normalized.includes('hit a length limit and auto-continuation was applied')
        );
    }, []);

    const collectAnalysisWarnings = useCallback((result, options = {}) => {
        const { includeLogOnly = true } = options || {};
        const warningCodes = [
            ...(Array.isArray(result?.warning_codes) ? result.warning_codes : []),
            ...(Array.isArray(result?.meta?.integrity?.warning_codes) ? result.meta.integrity.warning_codes : []),
        ];
        const localizedByCode = warningCodes
            .filter((code) => includeLogOnly || !isLogOnlyAnalysisWarningCode(code))
            .map(localizeAnalysisWarningCode)
            .map(msg => String(msg || '').trim())
            .filter(Boolean);

        const fallbackRawWarnings = [
            ...(Array.isArray(result?.warnings) ? result.warnings : []),
            ...(Array.isArray(result?.meta?.integrity?.warnings) ? result.meta.integrity.warnings : []),
        ]
            .map(w => String(w || '').trim())
            .filter(Boolean)
            .filter((warning) => includeLogOnly || !isLogOnlyAnalysisWarningMessage(warning));

        return [...new Set([...localizedByCode, ...fallbackRawWarnings])];
    }, [isLogOnlyAnalysisWarningCode, isLogOnlyAnalysisWarningMessage, localizeAnalysisWarningCode]);

    const localizeAnalysisFailureMessage = useCallback((rawMessage) => {
        const stable = String(rawMessage || '').trim();
        if (!stable) {
            return t('剧本分析返回告警：结果需要人工复核，但已允许继续加载。', 'Scene analysis returned warnings: the result needs manual review, but loading can continue.');
        }

        const normalized = stable.toLowerCase();
        if (normalized.includes('prohibited_content')) {
            return '出现供应商政策不允许内容';
        }
        if (stable.includes('第一阶段未解析到完整的 Subject Index 区块')) {
            return t('大模型开小差了，请选择其他AI。', 'The model got distracted. Please choose another AI.');
        }
        if (
            normalized.includes('剧本分析结果不可用')
            || normalized.includes('请直接重新执行 ai 剧本分析')
            || normalized.includes('please directly rerun AI script analysis')
        ) {
            return t(
                '剧本分析返回告警：结果需要人工复核，但不再阻断原文、Markdown 与 JSON 的加载。',
                'Scene analysis returned warnings: the result needs manual review, but no longer blocks loading raw text, markdown, or JSON.'
            );
        }
        if (
            normalized.includes('analysis_structure_incomplete')
            || normalized.includes('scene analysis output failed structural consistency checks')
            || normalized.includes('missing required sections')
        ) {
            return t(
                '剧本分析返回告警：本次返回缺少部分必要结构段，请人工复核；系统仍会继续加载已返回的原文、Markdown 与 JSON。',
                'Scene analysis returned warnings: some required sections are missing. Please review manually; the system will still load returned raw text, markdown, and JSON.'
            );
        }
        if (
            normalized.includes('analysis_output_truncated')
            || normalized.includes('truncated')
        ) {
            return t(
                '剧本分析返回告警：续写后结果仍可能不完整，请人工复核；系统将继续加载已返回内容。',
                'Scene analysis returned warnings: the result may still be incomplete after continuation. Please review manually; the system will continue loading returned content.'
            );
        }
        if (
            normalized.includes('analysis_json_invalid')
            || normalized.includes('json invalid')
            || normalized.includes('json 不完整')
        ) {
            return t(
                '剧本分析返回告警：本次返回的部分结构片段损坏，请人工复核；系统会尽可能继续解析并加载可用内容。',
                'Scene analysis returned warnings: some structured fragments are invalid. Please review manually; the system will keep parsing and loading usable content where possible.'
            );
        }
        return stable;
    }, [t]);

    const extractAnalysisRuntimeMeta = useCallback((meta) => {
        if (!meta || typeof meta !== 'object') return null;
        const integrity = (meta.integrity && typeof meta.integrity === 'object') ? meta.integrity : {};
        const segments = Array.isArray(meta.segments) ? meta.segments : [];
        const providerLimitHints = Array.isArray(meta.provider_limit_hints) ? meta.provider_limit_hints : [];
        const finishReason = String(meta.finish_reason || '').trim() || '-';
        const incompleteAfterContinuation = !!(
            integrity.truncation_suspected ||
            integrity.ended_with_length ||
            meta.continuation_stopped_by_max_segments
        );
        return {
            finishReason,
            segmentsCount: segments.length,
            incompleteAfterContinuation,
            maxSegmentsStop: !!meta.continuation_stopped_by_max_segments,
            requestedCap: meta.requested_output_cap_tokens ?? meta.config_max_tokens_effective ?? '-',
            completionTokens: meta.completion_tokens ?? '-',
            capReachedSuspected: !!meta.output_cap_reached_suspected,
            providerLimitHints,
        };
    }, []);

    const isEpisodeOnePage = useMemo(() => {
        const title = String(activeEpisode?.title || '').trim().toLowerCase();
        if (!title) return false;
        return /episode\s*1\b/.test(title) || /第\s*1\s*集/.test(title);
    }, [activeEpisode?.title]);

    const extractJsonFromLlmText = (text) => {
        if (!text || typeof text !== 'string') return '';

        const tryParse = (candidate) => {
            if (!candidate || typeof candidate !== 'string') return null;
            const s = candidate.trim();
            if (!s) return null;
            try {
                return JSON.parse(s);
            } catch {
                return null;
            }
        };

        const trimmed = text.trim();

        // Case 1: whole response is JSON
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            const obj = tryParse(trimmed);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        // Case 2: fenced code block ```json ... ```
        const fenceRe = /```(?:json)?\s*([\s\S]*?)```/gi;
        let match;
        while ((match = fenceRe.exec(text)) !== null) {
            const candidate = (match[1] || '').trim();
            if (!candidate) continue;
            const obj = tryParse(candidate);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        // Case 3: heuristic substring between outermost braces/brackets
        const braceStart = trimmed.indexOf('{');
        const braceEnd = trimmed.lastIndexOf('}');
        if (braceStart !== -1 && braceEnd > braceStart) {
            const candidate = trimmed.slice(braceStart, braceEnd + 1);
            const obj = tryParse(candidate);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        const bracketStart = trimmed.indexOf('[');
        const bracketEnd = trimmed.lastIndexOf(']');
        if (bracketStart !== -1 && bracketEnd > bracketStart) {
            const candidate = trimmed.slice(bracketStart, bracketEnd + 1);
            const obj = tryParse(candidate);
            if (obj !== null) return JSON.stringify(obj, null, 2);
        }

        return '';
    };

    const llmJsonResultContent = useMemo(() => extractJsonFromLlmText(llmRawResultContent || llmResultContent), [llmRawResultContent, llmResultContent]);

    const extractJsonObjectsFromText = (text) => {
        if (!text || typeof text !== 'string') return [];

        const objs = [];

        const tryPush = (candidate) => {
            if (!candidate || typeof candidate !== 'string') return;
            const s = candidate.trim();
            if (!s) return;
            try {
                objs.push(JSON.parse(s));
            } catch {
                // ignore
            }
        };

        const trimmed = text.trim();

        // Whole text JSON
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            tryPush(trimmed);
        }

        // Fenced blocks (prefer these)
        const fenceRe = /```(?:json)?\s*([\s\S]*?)```/gi;
        let match;
        while ((match = fenceRe.exec(text)) !== null) {
            tryPush(match[1]);
        }

        // If we didn't get anything, do a simple brace-scan for objects.
        if (objs.length === 0) {
            let braceCount = 0;
            let startIndex = -1;
            let inString = false;

            for (let i = 0; i < text.length; i++) {
                const ch = text[i];
                const prev = i > 0 ? text[i - 1] : '';

                if (ch === '"' && prev !== '\\') {
                    inString = !inString;
                }
                if (inString) continue;

                if (ch === '{') {
                    if (braceCount === 0) startIndex = i;
                    braceCount++;
                } else if (ch === '}') {
                    braceCount--;
                    if (braceCount === 0 && startIndex !== -1) {
                        const candidate = text.slice(startIndex, i + 1);
                        tryPush(candidate);
                        startIndex = -1;
                    }
                }
            }
        }

        // De-dupe by JSON string
        const seen = new Set();
        const unique = [];
        for (const o of objs) {
            try {
                const k = JSON.stringify(o);
                if (!seen.has(k)) {
                    seen.add(k);
                    unique.push(o);
                }
            } catch {
                // ignore
            }
        }
        return unique;
    };

    const getAnalysisEntitiesPayloadFromJsonText = (jsonText) => {
        const objects = extractJsonObjectsFromText(jsonText);
        const normalizeKey = (key) => String(key || '').toLowerCase().replace(/[\s_\-]/g, '');

        const pickArrayByAliases = (obj, aliases) => {
            if (!obj || typeof obj !== 'object') return [];
            const aliasSet = new Set((aliases || []).map(normalizeKey));
            for (const [k, v] of Object.entries(obj)) {
                if (!Array.isArray(v)) continue;
                if (aliasSet.has(normalizeKey(k))) return v;
            }
            return [];
        };

        const splitByTypeFromArray = (arr) => {
            const payload = { characters: [], props: [], environments: [], posters: [] };
            for (const item of arr || []) {
                if (!item || typeof item !== 'object') continue;
                if (isDummySubject(item.name) || isDummySubject(item.subject_name_exact) || isDummySubject(item.name_en)) continue;
                const type = normalizeKey(item.type || item.subject_type || item.entity_type || '');
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

        const cleanArray = (arr) => (arr || []).filter(item => !isDummySubject(item?.name) && !isDummySubject(item?.name_en) && !isDummySubject(item?.subject_name_exact));

        const normalizePayload = (obj) => {
            if (!obj || typeof obj !== 'object') return null;

            let characters = pickArrayByAliases(obj, ['characters', 'character', 'chars', 'subjects', 'people', 'roles', '人物', '角色']);
            let props = pickArrayByAliases(obj, ['props', 'prop', 'items', '道具', '物件']);
            let environments = pickArrayByAliases(obj, ['environments', 'environment', 'envs', 'env', 'scenes', '场景', '环境']);
            let posters = pickArrayByAliases(obj, ['poster', 'posters', 'cover', 'covers', '海报', '封面']);
            
            characters = cleanArray(characters);
            props = cleanArray(props);
            environments = cleanArray(environments);
            posters = cleanArray(posters);

            if (characters.length || props.length || environments.length || posters.length) {
                return { characters, props, environments, posters };
            }

            // Support wrappers like { entities: [...] } / { subjects: [...] }
            const entityArray = pickArrayByAliases(obj, ['entities', 'entity', 'subjectlist', 'subjects']);
            if (entityArray.length) {
                const split = splitByTypeFromArray(entityArray);
                if (split.characters.length || split.props.length || split.environments.length || split.posters.length) {
                    return split;
                }
            }

            // Support wrappers like { entities: { characters: [...] } }
            for (const key of ['entities', 'entity', 'subjects', 'subject']) {
                const nested = obj[key];
                if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
                    const nestedPayload = normalizePayload(nested);
                    if (nestedPayload) return nestedPayload;
                }
            }

            return {
                characters: [],
                props: [],
                environments: [],
                posters: [],
            };
        };

        // First try direct objects.
        for (const obj of objects) {
            const direct = normalizePayload(obj);
            if (direct && (direct.characters.length || direct.props.length || direct.environments.length || direct.posters.length)) return direct;
        }

        // Then search nested wrappers (e.g. { part3: { characters: [...] } }).
        const queue = [...objects];
        const seen = new WeakSet();
        while (queue.length > 0) {
            const cur = queue.shift();
            if (!cur || typeof cur !== 'object') continue;
            if (seen.has(cur)) continue;
            seen.add(cur);

            const nested = normalizePayload(cur);
            if (nested && (nested.characters.length || nested.props.length || nested.environments.length || nested.posters.length)) return nested;

            if (Array.isArray(cur)) {
                for (const item of cur) {
                    if (item && typeof item === 'object') queue.push(item);
                }
            } else {
                for (const value of Object.values(cur)) {
                    if (value && typeof value === 'object') queue.push(value);
                }
            }
        }

        return null;
    };

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
        const emptyPayload = { characters: [], props: [], environments: [] };

        const getEntitiesPayloadFromSubjectIndexTableLocal = (sourceText) => {
            const raw = String(sourceText || '');
            if (!raw.trim()) return null;

            const sectionMatch = raw.match(/###\s*Subject\s*Index[\s\S]*?(?=\n###\s+|$)/i);
            const section = sectionMatch ? sectionMatch[0] : raw;

            // Fallback: numbered Subject Index list lines.
            const listLineRe = /`([^`]*subject_type\s*=\s*[^`]*subject_name_exact\s*=\s*[^`]*)`/gi;
            const payload = { characters: [], props: [], environments: [] };
            const seen = new Set();
            let lineMatch;
            while ((lineMatch = listLineRe.exec(section)) !== null) {
                const body = String(lineMatch[1] || '');
                const typeMatch = body.match(/subject_type\s*=\s*([^|\n`]+)/i);
                const nameMatch = body.match(/subject_name_exact\s*=\s*([^|\n`]+)/i);
                const typeToken = String(typeMatch?.[1] || '').trim().toLowerCase();
                const subjectName = String(nameMatch?.[1] || '').trim();
                if (!typeToken || !subjectName || isDummySubject(subjectName)) continue;

                let type = '';
                if (typeToken.includes('character') || typeToken.includes('角色') || typeToken.includes('人物') || typeToken.includes('char')) type = 'character';
                else if (typeToken.includes('prop') || typeToken.includes('道具') || typeToken.includes('item')) type = 'prop';
                else if (typeToken.includes('environment') || typeToken.includes('场景') || typeToken.includes('环境') || typeToken.includes('env')) type = 'environment';
                if (!type) continue;

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

            if (payload.characters.length || payload.props.length || payload.environments.length) return payload;
            return null;
        };

        const normalizeName = (item) => normalizeEntityToken(
            item?.subject_name_exact || item?.name || item?.subject_name || item?.name_en || item?.name_zh || ''
        );

        const mergePayload = (base, patch, onlyMissingTypes = false) => {
            const out = {
                characters: Array.isArray(base?.characters) ? [...base.characters] : [],
                props: Array.isArray(base?.props) ? [...base.props] : [],
                environments: Array.isArray(base?.environments) ? [...base.environments] : [],
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

            const canMergeCharacters = !onlyMissingTypes || out.characters.length === 0;
            const canMergeProps = !onlyMissingTypes || out.props.length === 0;
            const canMergeEnvironments = !onlyMissingTypes || out.environments.length === 0;

            if (canMergeCharacters) mergeList(out.characters, Array.isArray(patch?.characters) ? patch.characters : []);
            if (canMergeProps) mergeList(out.props, Array.isArray(patch?.props) ? patch.props : []);
            if (canMergeEnvironments) mergeList(out.environments, Array.isArray(patch?.environments) ? patch.environments : []);
            return out;
        };

        const hasAny = (payload) =>
            (Array.isArray(payload?.characters) && payload.characters.length > 0)
            || (Array.isArray(payload?.props) && payload.props.length > 0)
            || (Array.isArray(payload?.environments) && payload.environments.length > 0);

        let merged = { ...emptyPayload };
        const sources = [];

        const parsedPayload = getAnalysisEntitiesPayloadFromJsonText(text);
        if (hasAny(parsedPayload)) {
            merged = mergePayload(merged, parsedPayload);
            sources.push('entities_json');
        }

        const fragmentPayload = {
            characters: extractNamedJsonArrayFromRawText(text, 'characters'),
            props: extractNamedJsonArrayFromRawText(text, 'props'),
            environments: extractNamedJsonArrayFromRawText(text, 'environments'),
        };
        if (hasAny(fragmentPayload)) {
            merged = mergePayload(merged, fragmentPayload);
            sources.push('json_key_fragments');
        }

        const subjectIndexPayload = getEntitiesPayloadFromSubjectIndexTableLocal(text);
        if (hasAny(subjectIndexPayload)) {
            merged = mergePayload(merged, subjectIndexPayload, true);
            sources.push('subject_index_fallback');
        }

        if (!hasAny(merged)) return null;
        return {
            payload: merged,
            source: sources.join('+') || 'unknown',
        };
    };

    const llmEntitiesPayload = useMemo(() => {
        const sourceText = llmRawResultContent || llmResultContent;
        const merged = getMergedEntitiesPayloadFromText(sourceText);
        if (merged?.payload) return merged.payload;
        return getAnalysisEntitiesPayloadFromJsonText(sourceText);
    }, [llmRawResultContent, llmResultContent]);

    const extractAnalysisTextFromResult = useCallback((result) => {
        if (typeof result === 'string') return result;
        if (result == null) return '';

        const asText = (value) => {
            if (typeof value === 'string') return value;
            if (value == null) return '';
            if (typeof value === 'object') {
                if (typeof value.result === 'string') return value.result;
                if (typeof value.analysis === 'string') return value.analysis;
                if (typeof value.content === 'string') return value.content;
                try {
                    return JSON.stringify(value, null, 2);
                } catch (_) {
                    return String(value);
                }
            }
            return String(value);
        };

        const directResult = asText(result?.result);
        if (directResult) return directResult;
        const directAnalysis = asText(result?.analysis);
        if (directAnalysis) return directAnalysis;
        const directContent = asText(result?.content);
        if (directContent) return directContent;
        return asText(result);
    }, []);

    const llmEntityGroups = useMemo(() => {
        const payload = llmEntitiesPayload || {};
        const characters = Array.isArray(payload.characters) ? payload.characters : [];
        const environments = Array.isArray(payload.environments) ? payload.environments : [];
        const props = Array.isArray(payload.props) ? payload.props : [];
        return [
            { key: 'character', labelZh: '角色', labelEn: 'Characters', icon: Users, items: characters },
            { key: 'environment', labelZh: '场景', labelEn: 'Environments', icon: Film, items: environments },
            { key: 'prop', labelZh: '道具', labelEn: 'Props', icon: Layers, items: props },
        ];
    }, [llmEntitiesPayload]);

    const totalLlmEntityCount = useMemo(() => {
        return llmEntityGroups.reduce((sum, group) => sum + (Array.isArray(group.items) ? group.items.length : 0), 0);
    }, [llmEntityGroups]);

    const subjectTypeGenerationStats = useMemo(() => {
        const getGeneratedCount = (items) => {
            return (items || []).filter((item) => {
                const imageUrl = String(item?.image_url || item?.image || item?.asset_url || '').trim();
                return imageUrl.length > 0;
            }).length;
        };

        const getTotalCount = (key) => {
            const group = llmEntityGroups.find((item) => item.key === key);
            return Array.isArray(group?.items) ? group.items.length : 0;
        };

        const characterTotal = getTotalCount('character');
        const environmentTotal = getTotalCount('environment');
        const propTotal = getTotalCount('prop');

        const characterGenerated = getGeneratedCount(llmEntityGroups.find((item) => item.key === 'character')?.items || []);
        const environmentGenerated = getGeneratedCount(llmEntityGroups.find((item) => item.key === 'environment')?.items || []);
        const propGenerated = getGeneratedCount(llmEntityGroups.find((item) => item.key === 'prop')?.items || []);

        return {
            character: { generated: characterGenerated, total: characterTotal },
            environment: { generated: environmentGenerated, total: environmentTotal },
            prop: { generated: propGenerated, total: propTotal },
        };
    }, [llmEntityGroups]);

    const getEntityDependencies = useCallback((item) => {
        if (!item || typeof item !== 'object') return [];

        const candidates = [];
        const pushValue = (val) => {
            const text = String(val || '').trim();
            if (!text) return;
            const normalized = normalizeEntityToken(text);
            if (normalized === 'none' || normalized === 'null' || normalized === '[]' || normalized === 'n/a') return;
            candidates.push(text);
        };

        const visualDeps = item.visual_dependencies;
        if (Array.isArray(visualDeps)) {
            visualDeps.forEach(pushValue);
        } else if (typeof visualDeps === 'string') {
            visualDeps.split(/[\n,，;；]/).forEach(pushValue);
        }

        const dedup = [];
        const seen = new Set();
        for (const dep of candidates) {
            const key = normalizeEntityToken(dep) || dep.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);
            dedup.push(dep);
        }
        return dedup;
    }, []);

    const getProjectVisualBackfillFromJsonText = (jsonText) => {
        const objects = extractJsonObjectsFromText(jsonText);
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
        for (const obj of objects) {
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
            const toneRaw = findValueByAliases(obj, ['tone']);
            const lightingRaw = findValueByAliases(obj, ['lighting']);

            const payload = {
                Global_Style: toNonEmptyString(globalStyleRaw),
                borrowed_films: toStringArray(borrowedFilmsRaw),
                tone: toNonEmptyString(toneRaw),
                lighting: toNonEmptyString(lightingRaw),
            };

            if (payload.Global_Style || payload.borrowed_films.length > 0 || payload.tone || payload.lighting) {
                return payload;
            }
        }

        return null;
    };

    const extractSubjectsFromMarkdownTable = (markdownText) => {
        const parsed = parseMarkdownTable(markdownText);
        if (!parsed) return [];

        const found = new Map();
        const patterns = [
            { type: 'character', regex: /CHAR:\s*\[@([^\]]+)\]/gi },
            { type: 'character', regex: /CHAR:\s*\[([^\]]+)\]/gi },
            { type: 'prop', regex: /PROP:\s*\[([^\]]+)\]/gi },
        ];

        const envCellPatterns = [
            /ENV:\s*\[([^\]]+)\]/gi,
        ];

        const norm = (value) => String(value || '').toLowerCase().replace(/[\s_\-./()]/g, '');
        const environmentNameIdx = (parsed.headers || []).findIndex((h) => {
            const n = norm(h);
            return n.includes('environmentname') || n.includes('环境名') || n.includes('场景名');
        });

        for (const row of parsed.rows || []) {
            for (const cell of row || []) {
                const cellText = String(cell || '');
                for (const pattern of patterns) {
                    pattern.regex.lastIndex = 0;
                    let match;
                    while ((match = pattern.regex.exec(cellText)) !== null) {
                        const normalized = normalizeSubjectName(match[1]);
                        const key = normalizeSubjectKey(normalized);
                        if (!normalized || !key) continue;
                        const dedupKey = `${pattern.type}:${key}`;
                        if (!found.has(dedupKey)) {
                            found.set(dedupKey, { type: pattern.type, name: normalized, key });
                        }
                    }
                }
            }

            // Environment consistency must primarily follow the markdown "Environment Name" column.
            if (environmentNameIdx >= 0) {
                const envCell = String((row || [])[environmentNameIdx] || '');
                for (const pattern of envCellPatterns) {
                    pattern.lastIndex = 0;
                    let match;
                    while ((match = pattern.exec(envCell)) !== null) {
                        const normalized = normalizeSubjectName(match[1]);
                        const key = normalizeSubjectKey(normalized);
                        if (!normalized || !key) continue;
                        const dedupKey = `environment:${key}`;
                        if (!found.has(dedupKey)) {
                            found.set(dedupKey, { type: 'environment', name: normalized, key });
                        }
                    }
                }

                envCell
                    .split(/[\n,，;；]/)
                    .map((v) => String(v || '').trim())
                    .filter(Boolean)
                    .forEach((envName) => {
                        if (/^env\s*:\s*\[[^\]]+\]$/i.test(envName)) return;
                        const key = normalizeSubjectKey(envName);
                        if (!key) return;
                        const dedupKey = `environment:${key}`;
                        if (!found.has(dedupKey)) {
                            found.set(dedupKey, { type: 'environment', name: normalizeSubjectName(envName), key });
                        }
                    });
            }
        }

        return Array.from(found.values());
    };

    const formatSubjectRef = (type, name) => {
        const cleanName = normalizeSubjectName(name);
        if (!cleanName) return '';
        if (type === 'character') return `CHAR:[@${cleanName}]`;
        if (type === 'prop') return `PROP:[${cleanName}]`;
        if (type === 'environment') return `ENV:[${cleanName}]`;
        return cleanName;
    };

    const escapeRegExp = (text) => String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    const buildSubjectConsistencyReport = (rawText) => {
        const markdownSource = normalizeLlmMarkdownTable(rawText || llmResultContent || '');
        const markdownSubjects = extractSubjectsFromMarkdownTable(markdownSource);
        const mergedPayload = getMergedEntitiesPayloadFromText(rawText || llmRawResultContent || llmResultContent);
        const entitiesPayload = mergedPayload?.payload || getAnalysisEntitiesPayloadFromJsonText(rawText || llmRawResultContent || llmResultContent);

        if (!entitiesPayload) {
            return {
                ok: false,
                message: t('未检测到可解析的实体 JSON。', 'No parseable entities JSON detected.'),
                missing: [],
                extra: [],
                markdownSubjects,
                jsonSubjects: [],
                markdownSource,
            };
        }

        const toPairs = (items, type) => {
            const pairs = [];
            for (const item of (items || [])) {
                const variants = [
                    item?.subject_name_exact,
                    item?.name,
                    item?.name_en,
                    item?.subject_name,
                    item?.id,
                ];
                for (const variant of variants) {
                    const display = normalizeSubjectName(variant);
                    const key = normalizeSubjectKey(variant);
                    if (!display || !key) continue;
                    pairs.push({ type, display, key });
                }
            }
            return pairs;
        };

        const jsonSubjectPairs = [
            ...toPairs(entitiesPayload.characters, 'character'),
            ...toPairs(entitiesPayload.props, 'prop'),
            ...toPairs(entitiesPayload.environments, 'environment'),
        ];

        const jsonByTypeKey = {
            character: new Set(jsonSubjectPairs.filter(v => v.type === 'character').map(v => v.key)),
            prop: new Set(jsonSubjectPairs.filter(v => v.type === 'prop').map(v => v.key)),
            environment: new Set(jsonSubjectPairs.filter(v => v.type === 'environment').map(v => v.key)),
        };

        const missingRefs = markdownSubjects.filter((ref) => !jsonByTypeKey[ref.type]?.has(ref.key));
        const missing = missingRefs.map((ref) => formatSubjectRef(ref.type, ref.name)).filter(Boolean);
        const ok = missing.length === 0;
        const message = ok
            ? t('一致：Markdown 中提到的 subject 均存在于 JSON entities。', 'Consistent: all markdown-mentioned subjects exist in JSON entities.')
            : t('告警：存在 Markdown 中提到但 JSON 缺失的 subject，请人工复核。', 'Warning: some subjects mentioned in markdown are missing in JSON entities. Please review manually.');

        const jsonSubjects = jsonSubjectPairs.map((item) => formatSubjectRef(item.type, item.display)).filter(Boolean);
        const markdownSubjectDisplay = markdownSubjects.map((item) => formatSubjectRef(item.type, item.name)).filter(Boolean);

        return { ok, message, missing, extra: [], markdownSubjects: markdownSubjectDisplay, jsonSubjects, markdownSource };
    };

    const buildRecoveryScriptFromMissingSubjects = (markdownSource, missingSubjects) => {
        const parsed = parseMarkdownTable(markdownSource || '');
        if (!parsed || !Array.isArray(parsed.rows) || parsed.rows.length === 0) {
            return String(markdownSource || '').trim();
        }

        const norm = (value) => normalizeSubjectKey(value);
        const findCol = (patterns) => {
            const idx = parsed.headers.findIndex((h) => patterns.some(p => norm(h).includes(p)));
            return idx >= 0 ? idx : -1;
        };

        const sceneNameIdx = findCol(['scenename', '场景名']);
        const coreInfoIdx = findCol(['coresceneinfo', '核心场景信息']);
        const originalIdx = findCol(['originalscripttext', '原始剧本文本', 'original']);

        const hitRows = [];
        for (const row of parsed.rows) {
            const rowText = row.map(v => String(v || '')).join(' ');
            const matched = (missingSubjects || []).some((subject) => {
                const raw = String(subject || '').trim();
                if (!raw) return false;
                const charMatch = raw.match(/^CHAR:\s*\[@?([^\]]+)\]$/i);
                const propMatch = raw.match(/^PROP:\s*\[([^\]]+)\]$/i);
                const envMatch = raw.match(/^ENV:\s*\[([^\]]+)\]$/i);
                const plainName = normalizeSubjectName(charMatch?.[1] || propMatch?.[1] || envMatch?.[1] || raw);
                const escaped = escapeRegExp(plainName);
                const comparableKey = normalizeSubjectKey(plainName);
                const normalizedRowText = normalizeSubjectKey(rowText);
                const patterns = [
                    new RegExp(`CHAR:\\s*\\[@${escaped}\\]`, 'i'),
                    new RegExp(`CHAR:\\s*\\[${escaped}\\]`, 'i'),
                    new RegExp(`PROP:\\s*\\[${escaped}\\]`, 'i'),
                    new RegExp(`ENV:\\s*\\[${escaped}\\]`, 'i'),
                    new RegExp(`\\[@${escaped}\\]`, 'i'),
                    new RegExp(`@${escaped}\\b`, 'i'),
                ];
                return patterns.some(re => re.test(rowText)) || Boolean(comparableKey && normalizedRowText && normalizedRowText.includes(comparableKey));
            });
            if (!matched) continue;

            const sceneName = sceneNameIdx >= 0 ? String(row[sceneNameIdx] || '').trim() : '';
            const coreInfo = coreInfoIdx >= 0 ? String(row[coreInfoIdx] || '').trim() : '';
            const original = originalIdx >= 0 ? String(row[originalIdx] || '').trim() : '';
            const snippet = [sceneName ? `Scene: ${sceneName}` : '', coreInfo ? `Core: ${coreInfo}` : '', original ? `Script: ${original}` : '']
                .filter(Boolean)
                .join('\n');
            if (snippet) hitRows.push(snippet);
        }

        const unique = Array.from(new Set(hitRows.map(s => s.trim()).filter(Boolean)));
        if (unique.length === 0) return String(markdownSource || '').trim();
        return unique.map((s, i) => `# Missing Subject Scene ${i + 1}\n${s}`).join('\n\n');
    };

    const buildSubjectOnlyRecoveryPrompt = (basePrompt = '') => {
        const recoveryMode = `\n\n[Subject Recovery Mode - Mandatory]\n` +
            `You must only generate missing subject-related entities from the provided missing-scene snippets.\n` +
            `Do NOT regenerate script/scene table content.\n` +
            `Output only Part 2A/2B/2C JSON in the same schema as the first pass.\n` +
            `Focus on entities referenced by missing markdown subjects and keep strict name consistency.`;
        return `${String(basePrompt || '').trim()}${recoveryMode}`;
    };

    const buildIssueDrivenSupplementPrompt = (basePrompt = '', issues = []) => {
        const normalizedIssues = Array.from(new Set((issues || []).map(v => String(v || '').trim()).filter(Boolean)));
        const issueBlock = normalizedIssues.length > 0
            ? normalizedIssues.map((item, idx) => `${idx + 1}. ${item}`).join('\n')
            : '1. General consistency and completeness check required.';

        const supplementMode = `\n\n[Issue-driven Supplement Mode - Mandatory]\n` +
            `Use the provided text as the current generated analysis draft (NOT original screenplay).\n` +
            `You MUST patch missing entities/structure/problems according to the issue list below.\n` +
            `Comprehensively audit missing content and entities using [Last Generated Analysis Output] plus the three optional sections ([Subject Check Result], [Core Coverage Check Result], [Episode 1 AI Script Analysis Attention Notes]); prioritize explicitly identified gaps and regenerate the output parts accordingly.\n` +
            `Do NOT output explanations, apologies, or meta commentary.\n` +
            `Return a fully corrected final output in the required scene_analysis format.\n` +
            `Issue List:\n${issueBlock}`;
        return `${String(basePrompt || '').trim()}${supplementMode}`;
    };

    const mergeAnalysisAttentionNotesWithIssues = (existingNotes = '', issues = []) => {
        const normalizedIssues = Array.from(new Set((issues || []).map(v => String(v || '').trim()).filter(Boolean)));
        if (normalizedIssues.length === 0) return String(existingNotes || '').trim();

        const base = String(existingNotes || '').trim();
        const block = [
            '[Auto Follow-up Issues]',
            ...normalizedIssues.map((item, idx) => `${idx + 1}. ${item}`),
        ].join('\n');

        if (!base) return block;
        if (base.includes('[Auto Follow-up Issues]')) {
            return base.replace(/\[Auto Follow-up Issues\][\s\S]*$/m, block).trim();
        }
        return `${base}\n\n${block}`.trim();
    };

    const collectFollowupIssues = (subjectReport, warnings = [], extraIssues = []) => {
        const issues = [];

        if (subjectReport && !subjectReport.ok) {
            const missing = Array.isArray(subjectReport.missing) ? subjectReport.missing.filter(Boolean) : [];
            if (missing.length > 0) {
                issues.push(`Subject Index/Entities mismatch: missing subjects in JSON -> ${missing.join(', ')}`);
            } else {
                issues.push('Subject Index/Entities consistency check failed.');
            }
        }

        const normalizedWarnings = (warnings || []).map(v => String(v || '').trim()).filter(Boolean);
        for (const warning of normalizedWarnings) {
            issues.push(`Analysis warning: ${warning}`);
        }

        for (const item of (extraIssues || [])) {
            const text = String(item || '').trim();
            if (text) issues.push(text);
        }

        return Array.from(new Set(issues));
    };

    const saveEpisodeInfoFields = async (fields = {}) => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        const mergedEpisodeInfo = {
            ...(activeEpisode?.episode_info || {}),
            ...fields,
        };
        await onUpdateEpisodeInfo(activeEpisode.id, { episode_info: mergedEpisodeInfo });
    };

    const saveSubjectCheckResultValue = async (nextText) => {
        await saveEpisodeInfoFields({
            subject_check_result: String(nextText || '').trim(),
        });
    };

    const saveCoreCoverageCheckResultValue = async (nextText) => {
        await saveEpisodeInfoFields({
            core_coverage_check_result: String(nextText || '').trim(),
        });
    };

    const persistFirstPassIssuesToAttentionNotes = async (subjectReport, warnings = [], extraIssues = []) => {
        const followupIssues = collectFollowupIssues(subjectReport, warnings, extraIssues);
        if (followupIssues.length === 0) return [];

        const mergedAttentionNotes = mergeAnalysisAttentionNotesWithIssues(analysisAttentionNotes, followupIssues);
        if (mergedAttentionNotes !== String(analysisAttentionNotes || '').trim()) {
            setAnalysisAttentionNotes(mergedAttentionNotes);
            try {
                await saveAnalysisAttentionNotesValue(mergedAttentionNotes);
                if (onLog) onLog('First-pass issues were written to analysis attention notes.', 'info');
            } catch (saveErr) {
                if (onLog) onLog(`Failed to persist first-pass issues: ${saveErr?.message || saveErr}`, 'warning');
            }
        }

        return followupIssues;
    };

    const buildSupplementSubmissionInput = ({ generatedContent = '', subjectCheckText = '', coreCoverageText = '', attentionNotes = '' }) => {
        const base = String(generatedContent || '').trim();
        const subject = String(subjectCheckText || '').trim();
        const core = String(coreCoverageText || '').trim();
        const notes = String(attentionNotes || '').trim();

        const projectInfo = (project?.global_info && typeof project.global_info === 'object')
            ? project.global_info
            : {};
        const getInfoValue = (keys = []) => {
            for (const key of keys) {
                const value = String(projectInfo?.[key] || '').trim();
                if (value) return value;
            }
            return '';
        };
        const borrowedFilms = Array.isArray(projectInfo?.borrowed_films)
            ? projectInfo.borrowed_films.map(v => String(v || '').trim()).filter(Boolean)
            : [];

        const basicInfoLines = [];
        const title = getInfoValue(['script_title', 'title']);
        const seriesEpisode = getInfoValue(['series_episode', 'episode']);
        const type = getInfoValue(['type']);
        const language = getInfoValue(['language']);
        const basePositioning = getInfoValue(['base_positioning']);
        const globalStyle = getInfoValue(['Global_Style', 'global_style']);
        const tone = getInfoValue(['tone']);
        const lighting = getInfoValue(['lighting']);
        if (title) basicInfoLines.push(`Title: ${title}`);
        if (seriesEpisode) basicInfoLines.push(`Series/Episode: ${seriesEpisode}`);
        if (type) basicInfoLines.push(`Type: ${type}`);
        if (language) basicInfoLines.push(`Language: ${language}`);
        if (basePositioning) basicInfoLines.push(`Base Positioning: ${basePositioning}`);
        if (globalStyle) basicInfoLines.push(`Global Style: ${globalStyle}`);
        if (tone) basicInfoLines.push(`Tone: ${tone}`);
        if (lighting) basicInfoLines.push(`Lighting: ${lighting}`);
        if (borrowedFilms.length > 0) basicInfoLines.push(`Borrowed Films: ${borrowedFilms.join(', ')}`);

        const projectBasicInfoBlock = basicInfoLines.length > 0
            ? `[Project Basic Info]\n${basicInfoLines.join('\n')}`
            : '';

        const sections = [
            '[Last Generated Analysis Output]\n' + base,
        ];

        if (projectBasicInfoBlock) sections.push(projectBasicInfoBlock);

        if (subject) sections.push('[Subject Check Result]\n' + subject);
        if (core) sections.push('[Core Coverage Check Result]\n' + core);
        if (notes) sections.push('[Episode 1 AI Script Analysis Attention Notes]\n' + notes);

        return sections.join('\n\n');
    };

    const mergeEntitiesPayload = (basePayload, patchPayload) => {
        const base = basePayload || { characters: [], props: [], environments: [] };
        const patch = patchPayload || { characters: [], props: [], environments: [] };

        const mergeBy = (a, b, keyOf) => {
            const out = [];
            const seen = new Set();
            for (const item of [...(a || []), ...(b || [])]) {
                const key = keyOf(item);
                if (!key || seen.has(key)) continue;
                seen.add(key);
                out.push(item);
            }
            return out;
        };

        return {
            characters: mergeBy(base.characters, patch.characters, (item) => normalizeSubjectKey(item?.subject_name_exact || item?.name || item?.subject_name || item?.name_en || item?.name_zh || '')),
            props: mergeBy(base.props, patch.props, (item) => normalizeSubjectKey(item?.subject_name_exact || item?.name || item?.subject_name || item?.name_en || item?.name_zh || '')),
            environments: mergeBy(base.environments, patch.environments, (item) => normalizeSubjectKey(item?.subject_name_exact || item?.name || item?.subject_name || item?.name_en || item?.name_zh || '')),
        };
    };

    const autoRecoverMissingSubjects = async (rawText, missingSubjects) => {
        if (!activeEpisode?.id || isRecoveringMissingSubjects) return null;
        const normalizedMissing = Array.from(new Set((missingSubjects || []).map(v => String(v || '').trim()).filter(Boolean)));
        if (normalizedMissing.length === 0) return null;

        setIsRecoveringMissingSubjects(true);
        setSubjectRecoveryModal({
            open: true,
            status: 'running',
            missing: normalizedMissing,
            message: t('检测到 Subject 缺失，正在自动补全...', 'Missing subjects detected. Auto-recovering...'),
            details: '',
        });

        try {
            const markdownSource = normalizeLlmMarkdownTable(rawText || llmResultContent || '');
            const recoveryScript = buildRecoveryScriptFromMissingSubjects(markdownSource, normalizedMissing);

            let promptContent = '';
            try {
                const promptRes = await fetchPrompt('skills/scene_analysis_feature_stack/entity_design.md');
                promptContent = promptRes?.content || '';
            } catch {
                try {
                    const fallbackRes = await fetchPrompt('scene_analysis_subject_recovery_lite.txt');
                    promptContent = fallbackRes?.content || '';
                } catch {
                    try {
                        const fallbackRes2 = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning.md');
                        promptContent = fallbackRes2?.content || '';
                    } catch {
                        promptContent = '';
                    }
                }
            }
            const recoveryPrompt = buildSubjectOnlyRecoveryPrompt(promptContent);

            if (onLog) onLog(`Auto recovery started for missing subjects: [${normalizedMissing.join(', ')}]`, 'process');
            const recoveryResult = await analyzeScene(
                recoveryScript,
                recoveryPrompt,
                null,
                activeEpisode.id,
                analysisAttentionNotes,
                selectedReuseSubjectAssets,
                null,
                projectId,
                null,
                functionApiConfigs.selectedApi?.system_api_id
            );

            const recoveryText = recoveryResult?.result || recoveryResult?.analysis || (typeof recoveryResult === 'string' ? recoveryResult : JSON.stringify(recoveryResult, null, 2));
            const baseEntities = getAnalysisEntitiesPayloadFromJsonText(rawText || llmRawResultContent || llmResultContent) || { characters: [], props: [], environments: [] };
            const patchEntities = getAnalysisEntitiesPayloadFromJsonText(recoveryText || '');

            if (!patchEntities) {
                setSubjectRecoveryModal({
                    open: true,
                    status: 'failed',
                    missing: normalizedMissing,
                    message: t('自动补全未返回可解析的实体 JSON。', 'Auto recovery returned no parseable entities JSON.'),
                    details: '',
                });
                if (onLog) onLog('Auto recovery failed: no parseable entities JSON.', 'warning');
                return null;
            }

            const mergedEntities = mergeEntitiesPayload(baseEntities, patchEntities);

            const mergedRawSections = [];
            if (markdownSource) mergedRawSections.push(markdownSource);
            mergedRawSections.push(JSON.stringify(mergedEntities, null, 2));
            const mergedRaw = mergedRawSections.join('\n\n');

            setLlmRawResultContent(mergedRaw);
            setLlmResultContent(normalizeLlmMarkdownTable(mergedRaw));
            lastLoadedAnalysisRef.current = mergedRaw;
            await persistLlmResultContent(mergedRaw);

            const rerun = buildSubjectConsistencyReport(mergedRaw);
            setSubjectConsistencyReport(rerun);

            if (rerun.ok) {
                setSubjectRecoveryModal({
                    open: true,
                    status: 'success',
                    missing: normalizedMissing,
                    message: t('缺失 Subject 已自动补全并通过复检。', 'Missing subjects were auto-recovered and passed re-check.'),
                    details: '',
                });
                if (onLog) onLog('Auto recovery completed and consistency re-check passed.', 'success');
            } else {
                setSubjectRecoveryModal({
                    open: true,
                    status: 'partial',
                    missing: rerun.missing || [],
                    message: t('自动补全完成，但复检仍有缺失 Subject。', 'Auto recovery finished, but re-check still has missing subjects.'),
                    details: (rerun.missing || []).join(', '),
                });
                if (onLog) onLog(`Auto recovery finished with remaining missing subjects: [${(rerun.missing || []).join(', ')}]`, 'warning');
            }
            return rerun;
        } catch (error) {
            setSubjectRecoveryModal({
                open: true,
                status: 'failed',
                missing: normalizedMissing,
                message: t('自动补全失败。', 'Auto recovery failed.'),
                details: String(error?.message || ''),
            });
            if (onLog) onLog(`Auto recovery failed: ${error.message}`, 'error');
            return null;
        } finally {
            setIsRecoveringMissingSubjects(false);
        }
    };

    const runSubjectConsistencyCheck = (rawText = null, options = {}) => {
        const silent = Boolean(options?.silent);
        const persist = options?.persist !== false;
        const report = buildSubjectConsistencyReport(rawText || llmRawResultContent || llmResultContent);
        setSubjectConsistencyReport(report);
        const subjectText = [
            `[${t('结论', 'Verdict')}] ${report.ok ? t('通过', 'Passed') : t('告警', 'Warning')}`,
            report.message || '',
            report.missing?.length ? `${t('缺失', 'Missing')}: ${report.missing.join(', ')}` : '',
            report.extra?.length ? `${t('额外', 'Extra')}: ${report.extra.join(', ')}` : '',
        ].filter(Boolean).join('\n');
        setSubjectConsistencyResultText(subjectText);
        if (persist) {
            void saveSubjectCheckResultValue(subjectText);
        }
        if (!silent && onLog) {
            if (report.ok) onLog(`Subject consistency check passed (${report.markdownSubjects.length} matched).`, 'success');
            else if (report.missing?.length) onLog(`Subject consistency warning: missing [${report.missing.join(', ')}]`, 'warning');
            else onLog('Subject consistency warning: no entities JSON.', 'warning');
        }
        return report;
    };

    const handleRunSubjectConsistencyCheck = async () => {
        setIsCheckingSubjectConsistency(true);
        setWorkspaceOpStatus({
            running: true,
            action: 'subject_consistency',
            progress: 35,
            message: t('✅ 即将完成！最后为您核对一下角色和道具...', 'Checking subject consistency...'),
        });
        try {
            const report = runSubjectConsistencyCheck();
            if (!report) {
                setSubjectConsistencyResultText(t('未生成 Subject 一致性结果。', 'No Subject consistency result generated.'));
            }
            setWorkspaceOpStatus({
                running: false,
                action: 'subject_consistency',
                progress: 100,
                message: report?.ok
                    ? t('出场名单核对无误！', 'Subject consistency check passed.')
                    : t('出场名单核对完啦，不过发现了几个小问题。', 'Subject consistency check completed with warnings.'),
            });
            setTimeout(() => {
                setWorkspaceOpStatus(prev => (prev.action === 'subject_consistency' ? { running: false, action: '', progress: 0, message: '' } : prev));
            }, 1400);
        } finally {
            setIsCheckingSubjectConsistency(false);
        }
    };

    const maybeAlertIncompleteSubjectsImport = useCallback((analysisResult, analyzedText = '') => {
        const warningCodes = [
            ...(Array.isArray(analysisResult?.warning_codes) ? analysisResult.warning_codes : []),
            ...(Array.isArray(analysisResult?.meta?.integrity?.warning_codes) ? analysisResult.meta.integrity.warning_codes : []),
        ].map((code) => String(code || '').trim().toUpperCase()).filter(Boolean);

        const relevantCodes = warningCodes.filter((code) => (
            code === 'ANALYSIS_JSON_INVALID'
            || code === 'ANALYSIS_STRUCTURE_INCOMPLETE'
        ));

        const reasonLines = [
            ...relevantCodes.map((code) => localizeAnalysisWarningCode(code)).filter(Boolean),
        ];
        const uniqueReasons = [...new Set(reasonLines.map((line) => String(line || '').trim()).filter(Boolean))];

        if (uniqueReasons.length === 0) return;

        const alertMessage = [
            t(
                '本次剧本分析返回的 subjects JSON 可能不完整。系统已继续导入可解析内容，请立即人工复核。',
                'The subjects JSON returned by this scene analysis may be incomplete. The system imported the parseable content, but manual review is required.'
            ),
            ...uniqueReasons.map((line) => `- ${line}`),
        ].join('\n');

        if (lastSubjectsImportIncompleteAlertRef.current === alertMessage) return;

        lastSubjectsImportIncompleteAlertRef.current = alertMessage;
        if (onLog) onLog(`Subjects import warning:\n${alertMessage}`, 'warning');
        // alert(alertMessage);
    }, [localizeAnalysisWarningCode, onLog, t]);

    const ensureSubjectsImportedBeforePostChecks = useCallback(async (analysisResult, importReport = null) => {
        const subjectsJson = (analysisResult?.subjects_json && typeof analysisResult.subjects_json === 'object')
            ? analysisResult.subjects_json
            : null;
        if (!subjectsJson || typeof onImportText !== 'function') {
            return importReport;
        }

        const expectedCount =
            (Array.isArray(subjectsJson.characters) ? subjectsJson.characters.length : 0)
            + (Array.isArray(subjectsJson.props) ? subjectsJson.props.length : 0)
            + (Array.isArray(subjectsJson.environments) ? subjectsJson.environments.length : 0);
        if (expectedCount <= 0) {
            return importReport;
        }

        const importedCounts = importReport?.importedSubjectCounts || {};
        const createdCount =
            Number(importedCounts.character || 0)
            + Number(importedCounts.prop || 0)
            + Number(importedCounts.environment || 0);
        const skippedCount = Array.isArray(importReport?.skippedSubjectItems)
            ? importReport.skippedSubjectItems.length
            : 0;
        const handledCount = createdCount + skippedCount;

        if (handledCount >= expectedCount) {
            return importReport;
        }

        onLog?.(
            `Subjects import pre-check: expected=${expectedCount}, handled=${handledCount}. Running explicit subjects_json import before consistency/supplement checks.`,
            'warning'
        );

        const subjectsImportReport = await onImportText(
            JSON.stringify(subjectsJson, null, 2),
            'json',
            { suppressAlerts: true }
        );

        const mergedImportedCounts = {
            character: (Number(importedCounts.character || 0) + Number(subjectsImportReport?.importedSubjectCounts?.character || 0)),
            prop: (Number(importedCounts.prop || 0) + Number(subjectsImportReport?.importedSubjectCounts?.prop || 0)),
            environment: (Number(importedCounts.environment || 0) + Number(subjectsImportReport?.importedSubjectCounts?.environment || 0)),
        };

        return {
            ...(importReport && typeof importReport === 'object' ? importReport : {}),
            importedSubjectCounts: mergedImportedCounts,
            createdSubjectItems: [
                ...(Array.isArray(importReport?.createdSubjectItems) ? importReport.createdSubjectItems : []),
                ...(Array.isArray(subjectsImportReport?.createdSubjectItems) ? subjectsImportReport.createdSubjectItems : []),
            ],
            skippedSubjectItems: [
                ...(Array.isArray(importReport?.skippedSubjectItems) ? importReport.skippedSubjectItems : []),
                ...(Array.isArray(subjectsImportReport?.skippedSubjectItems) ? subjectsImportReport.skippedSubjectItems : []),
            ],
            subjectsImportPrecheck: {
                expectedCount,
                handledCountBefore: handledCount,
                reranExplicitImport: true,
            },
        };
    }, [onImportText, onLog]);

    const handleImportEntities = async () => {
        const payload = getAnalysisEntitiesPayloadFromJsonText(llmRawResultContent || llmResultContent);
        if (!payload) {
            if (onLog) onLog('No entities JSON (characters/props/environments) found.', 'warning');
            alert(t('未检测到可导入的实体 JSON（characters/props/environments）。', 'No importable entities JSON found (characters/props/environments).'));
            return;
        }

        setIsImportingEntities(true);
        setWorkspaceOpStatus({
            running: true,
            action: 'import_entities',
            progress: 20,
            message: t('🎨 正在提炼剧本里的核心角色与场景...', 'Importing entities...'),
        });
        try {
            const ok = await doImportText(JSON.stringify(payload, null, 2), 'json');
            setWorkspaceOpStatus({
                running: false,
                action: 'import_entities',
                progress: ok ? 100 : 0,
                message: ok
                    ? t('实体导入完成。', 'Entities import completed.')
                    : t('实体导入失败。', 'Entities import failed.'),
            });
            setTimeout(() => {
                setWorkspaceOpStatus(prev => (prev.action === 'import_entities' ? { running: false, action: '', progress: 0, message: '' } : prev));
            }, 1400);
        } finally {
            setIsImportingEntities(false);
        }
    };

    const parseCoreCoverageReport = (rawText) => {
        const dedupeMissingPoints = (points) => {
            const seen = new Set();
            const out = [];
            for (const item of points || []) {
                const text = String(item || '').trim();
                if (!text) continue;
                const key = text.toLowerCase();
                if (seen.has(key)) continue;
                seen.add(key);
                out.push(text);
            }
            return out;
        };

        const formatMissingPoint = (value) => {
            if (value == null) return '';
            if (typeof value === 'string') return value.trim();
            if (Array.isArray(value)) {
                return value.map(item => formatMissingPoint(item)).filter(Boolean).join(' | ');
            }
            if (typeof value === 'object') {
                const sceneId = String(
                    value.scene_id ?? value.sceneId ?? value['Scene ID'] ?? value['场景ID'] ?? value['场景id'] ?? ''
                ).trim();
                const detailRaw =
                    value.missing_detail
                    ?? value.missing_point
                    ?? value.missing_points
                    ?? value.missing_items
                    ?? value.detail
                    ?? value.reason
                    ?? value.issue
                    ?? value.desc
                    ?? value.description
                    ?? value['缺失点']
                    ?? value['未覆盖点']
                    ?? value['说明']
                    ?? '';

                let detail = '';
                if (Array.isArray(detailRaw)) {
                    detail = detailRaw.map(v => String(v || '').trim()).filter(Boolean).join(' | ');
                } else if (detailRaw && typeof detailRaw === 'object') {
                    try {
                        detail = JSON.stringify(detailRaw);
                    } catch {
                        detail = '';
                    }
                } else {
                    detail = String(detailRaw || '').trim();
                }

                if (sceneId && detail) return `${sceneId}: ${detail}`;
                if (detail) return detail;
                if (sceneId) {
                    return `${sceneId}: ${t('未提供具体缺失说明', 'No specific uncovered detail provided')}`;
                }

                try {
                    return JSON.stringify(value);
                } catch {
                    return '';
                }
            }
            return String(value).trim();
        };

        const text = String(rawText || '').trim();
        const jsonText = extractJsonFromLlmText(text);
        if (jsonText) {
            try {
                const parsed = JSON.parse(jsonText);
                const normalized = String(parsed?.is_covered || parsed?.covered || parsed?.result || '').trim();
                const isCovered = normalized === '是' || /^yes$/i.test(normalized) || normalized === 'true';
                const missingPointsRaw = Array.isArray(parsed?.missing_points)
                    ? parsed.missing_points.map(v => formatMissingPoint(v)).filter(Boolean)
                    : [];
                const missingPoints = dedupeMissingPoints(missingPointsRaw);
                return {
                    ok: true,
                    isCovered,
                    verdict: isCovered ? t('是', 'Yes') : t('否', 'No'),
                    missingPoints,
                    raw: text,
                };
            } catch {
                // fall through
            }
        }

        const isCovered = /(?:^|\b)(是|yes|true)(?:\b|$)/i.test(text) && !/(?:^|\b)(否|no|false)(?:\b|$)/i.test(text);
        const lines = text.split('\n').map(v => String(v || '').trim()).filter(Boolean);
        const missingPoints = dedupeMissingPoints(
            lines.filter(line => {
                if (!line) return false;
                if (/缺失|未覆盖|missing/i.test(line)) return true;
                if (/^[\-•\d]/.test(line)) return true;
                // Common scene-id style rows: EP01_SC01: ...
                if (/^[A-Za-z]{1,8}\d{1,3}_SC\d{1,3}\s*:/i.test(line)) return true;
                return false;
            })
        );
        return {
            ok: Boolean(text),
            isCovered,
            verdict: isCovered ? t('是', 'Yes') : t('否', 'No'),
            missingPoints,
            raw: text,
        };
    };

    const runCoreCoverageCheck = async (markdownText = null, options = {}) => {
        const suppressAlert = Boolean(options?.suppressAlert);
        const suppressLog = Boolean(options?.suppressLog);
        const persist = options?.persist !== false;
        const candidateSources = [
            { label: 'input_markdown', text: markdownText },
            { label: 'scene_list_workspace', text: llmMarkdownTableText },
            { label: 'input_normalized', text: normalizeLlmMarkdownTable(markdownText || '') },
            { label: 'raw_normalized', text: normalizeLlmMarkdownTable(llmRawResultContent || '') },
            { label: 'input_scene_block', text: extractScenesTableBlock(markdownText || '') },
            { label: 'raw_scene_block', text: extractScenesTableBlock(llmRawResultContent || '') },
            { label: 'llm_result_text', text: llmResultContent },
            { label: 'llm_raw_text', text: llmRawResultContent },
        ];

        let parsed = null;
        let coreCoverageSource = '';
        let sourceLabel = '';
        for (const candidate of candidateSources) {
            const text = String(candidate?.text || '').trim();
            if (!text) continue;
            const currentParsed = parseMarkdownTable(text);
            if (!currentParsed) continue;
            parsed = currentParsed;
            coreCoverageSource = text;
            sourceLabel = candidate.label;
            break;
        }

        // Last fallback: if Scene List table is already rendered in workspace state, rebuild markdown from it.
        if (!parsed && llmMarkdownTable && Array.isArray(llmMarkdownTable.headers) && Array.isArray(llmMarkdownTable.rows)) {
            const rebuilt = buildMarkdownTable(llmMarkdownTable.headers, llmMarkdownTable.rows);
            const rebuiltParsed = parseMarkdownTable(rebuilt);
            if (rebuiltParsed) {
                parsed = rebuiltParsed;
                coreCoverageSource = rebuilt;
                sourceLabel = 'scene_list_rebuilt';
            }
        }

        if (!parsed || !Array.isArray(parsed.rows) || parsed.rows.length === 0) {
            setCoreCoverageResultText(t(
                '校验未执行：未检测到可解析的 Markdown 表格。',
                'Check not executed: no parseable markdown table detected.'
            ));
            if (persist) {
                void saveCoreCoverageCheckResultValue(t(
                    '校验未执行：未检测到可解析的 Markdown 表格。',
                    'Check not executed: no parseable markdown table detected.'
                ));
            }
            if (!suppressAlert) {
                alert(t('未检测到可解析的 Markdown 表格。', 'No parseable markdown table detected.'));
            }
            return null;
        }

        const norm = (value) => String(value || '').toLowerCase().replace(/[\s_\-./()]/g, '');
        const findCol = (patterns) => parsed.headers.findIndex((h) => {
            const n = norm(h);
            return patterns.some(p => n.includes(p));
        });

        const episodeIdIdx = findCol(['episodeid', '集id', '集编号']);
        const sceneIdIdx = findCol(['sceneid', '场景id']);
        const sceneNoIdx = findCol(['sceneno', '场次']);
        const coreInfoIdx = findCol(['coresceneinfo', '核心场景信息']);
        const originalIdx = findCol(['originalscripttext', '原始剧本文本', 'scripttext', 'original']);

        if (sceneIdIdx < 0 || coreInfoIdx < 0 || originalIdx < 0) {
            setCoreCoverageResultText(t(
                '校验未执行：表格缺少必要列（Scene ID / Core Scene Info / Original Script Text）。',
                'Check not executed: missing required columns (Scene ID / Core Scene Info / Original Script Text).'
            ));
            if (persist) {
                void saveCoreCoverageCheckResultValue(t(
                    '校验未执行：表格缺少必要列（Scene ID / Core Scene Info / Original Script Text）。',
                    'Check not executed: missing required columns (Scene ID / Core Scene Info / Original Script Text).'
                ));
            }
            if (!suppressAlert) {
                alert(t('表格缺少必要列（Scene ID / Core Scene Info / Original Script Text）。', 'Missing required columns (Scene ID / Core Scene Info / Original Script Text).'));
            }
            return null;
        }

        const rowsPayload = parsed.rows.map((row) => ({
            episode_id: episodeIdIdx >= 0 ? String(row[episodeIdIdx] || '').trim() : '',
            scene_id: String(row[sceneIdIdx] || '').trim(),
            scene_no: sceneNoIdx >= 0 ? String(row[sceneNoIdx] || '').trim() : '',
            core_scene_info: String(row[coreInfoIdx] || '').trim(),
            original_script_text: String(row[originalIdx] || '').trim(),
        })).filter(item => item.scene_id && (item.core_scene_info || item.original_script_text));

        if (rowsPayload.length === 0) {
            setCoreCoverageResultText(t(
                '校验未执行：未找到可用于校验的场景行。',
                'Check not executed: no scene rows available for coverage check.'
            ));
            if (persist) {
                void saveCoreCoverageCheckResultValue(t(
                    '校验未执行：未找到可用于校验的场景行。',
                    'Check not executed: no scene rows available for coverage check.'
                ));
            }
            if (!suppressAlert) {
                alert(t('未找到可用于校验的场景行。', 'No scene rows available for coverage check.'));
            }
            return null;
        }

        const systemPrompt = [
            'You are a strict coverage auditor for screenplay adaptation.',
            'Task: Compare each row\'s Core Scene Info against Original Script Text and determine whether coverage is complete.',
            'Output STRICT JSON only (no markdown, no explanation):',
            '{"is_covered":"是|否","missing_points":["..."]}',
            'Rules:',
            '- Return "是" only when ALL rows are fully covered.',
            '- If any gap exists, return "否" and list concrete missing points in missing_points.',
            '- Each missing point should include scene_id and concise uncovered detail.',
            '- If "是", missing_points must be [].',
        ].join('\n');

        const userPrompt = [
            'Rows to audit:',
            JSON.stringify(rowsPayload, null, 2),
        ].join('\n\n');

        setIsCheckingCoreCoverage(true);
        setCoreCoverageReport(null);
        setWorkspaceOpStatus({
            running: true,
            action: 'core_coverage',
            progress: 30,
            message: t('🔍 正在检查重要剧情是否都已涵盖...', 'Checking core coverage...'),
        });
        if (!suppressLog && onLog) {
            onLog(`Core coverage source selected: ${sourceLabel || 'unknown'}`, 'info');
        }
        try {
            // Coverage check is an auxiliary audit call and must not overwrite episode ai_scene_analysis_result.
            const result = await analyzeScene(userPrompt, systemPrompt, null, null, null, null, null, projectId, null, functionApiConfigs.selectedApi?.system_api_id);
            const analyzedText = extractAnalysisTextFromResult(result);
            const report = parseCoreCoverageReport(analyzedText);
            setCoreCoverageReport(report);
            const coverageText = [
                `${t('覆盖结论', 'Coverage Verdict')}: ${report.verdict}`,
                !report.isCovered && Array.isArray(report.missingPoints) && report.missingPoints.length > 0
                    ? `${t('未覆盖点：', 'Missing Points:')}\n- ${report.missingPoints.join('\n- ')}`
                    : '',
                report.raw ? `${t('原始校验输出', 'Raw Check Output')}:\n${report.raw}` : '',
            ].filter(Boolean).join('\n\n');
            setCoreCoverageResultText(coverageText);
            if (persist) {
                void saveCoreCoverageCheckResultValue(coverageText);
            }
            setWorkspaceOpStatus({
                running: false,
                action: 'core_coverage',
                progress: 100,
                message: report.isCovered
                    ? t('剧情要点已全部包含，完美！', 'Core coverage check passed.')
                    : t('剧情核对完成，好像漏掉了一些细节。', 'Core coverage check completed with uncovered points.'),
            });
            setTimeout(() => {
                setWorkspaceOpStatus(prev => (prev.action === 'core_coverage' ? { running: false, action: '', progress: 0, message: '' } : prev));
            }, 1400);
            if (!suppressLog && onLog) {
                onLog(
                    report.isCovered
                        ? 'Core Scene Info coverage check: YES (fully covered).'
                        : `Core Scene Info coverage check: NO (${report.missingPoints.length} missing points).`,
                    report.isCovered ? 'success' : 'warning'
                );
            }
            return report;
        } catch (e) {
            console.error(e);
            setCoreCoverageResultText(
                `${t('校验失败', 'Check failed')}: ${String(e?.message || 'Unknown error')}`
            );
            if (persist) {
                void saveCoreCoverageCheckResultValue(`${t('校验失败', 'Check failed')}: ${String(e?.message || 'Unknown error')}`);
            }
            setWorkspaceOpStatus({
                running: false,
                action: 'core_coverage',
                progress: 0,
                message: t('Core 覆盖校验失败。', 'Core coverage check failed.'),
            });
            if (!suppressLog && onLog) onLog(`Core coverage check failed: ${e.message}`, 'error');
            if (!suppressAlert) {
                alert(t('Core Scene Info 覆盖校验失败：', 'Core Scene Info coverage check failed: ') + (e?.message || 'Unknown error'));
            }
            return null;
        } finally {
            setIsCheckingCoreCoverage(false);
        }
    };

    const closePostAnalysisCheckModal = () => {
        setPostAnalysisCheckModal({ open: false, status: 'idle', message: '', guidance: [] });
        if (pendingSwitchAfterPostChecks && typeof onSwitchToScenes === 'function') {
            onSwitchToScenes();
            setAnalysisFlowStatus({
                phase: 'completed',
                message: t('已自动帮您切换到场景表，请根据刚才的检查结果进行微调。', 'Check results confirmed, switched to Scenes.'),
            });
        }
        setPendingSwitchAfterPostChecks(false);
    };

    const handlePostCheckRerunAnalysis = async () => {
        setPendingSwitchAfterPostChecks(false);
        setPostAnalysisCheckModal({ open: false, status: 'idle', message: '', guidance: [] });
        if (onLog) onLog('Post-check action: rerun AI Script Analysis.', 'info');
        await handleAnalysisClick();
    };

    const handlePostCheckGoToScenes = () => {
        setPendingSwitchAfterPostChecks(false);
        setPostAnalysisCheckModal({ open: false, status: 'idle', message: '', guidance: [] });
        if (typeof onSwitchToScenes === 'function') {
            onSwitchToScenes();
            setAnalysisFlowStatus({
                phase: 'completed',
                message: t('已自动帮您切换到场景表，请根据刚才的检查结果进行微调。', 'Switched to Scenes. Update content based on check results.'),
            });
        }
        if (onLog) onLog('Post-check action: switched to Scenes for manual fixes.', 'info');
    };

    const runPostAnalysisChecksAndPrompt = async (analyzedText = '') => {
        setPostAnalysisCheckModal({
            open: true,
            status: 'running',
            message: t('🧹 正在检查角色和场景名称是否前后一致...', 'Running check: Subject Consistency...'),
            guidance: [],
        });

        const subjectReport = runSubjectConsistencyCheck(analyzedText || '', { silent: true });

        const passedSubject = Boolean(subjectReport?.ok);
        const summary = passedSubject
            ? t('登场角色和道具核对完全一致！您可以放心关掉此窗口继续啦。', 'Subject consistency check completed and passed. Review the result, then close this dialog to continue.')
            : t('登场角色和道具核对完毕。有几个地方需要您瞧瞧，确认后关掉窗口就行。', 'Subject consistency check completed. Review the result (including warnings), then close this dialog to continue.');

        const guidance = [];
        if (!passedSubject) {
            guidance.push(
                t(
                    'Subject 一致性未通过：说明角色/道具/环境索引可能不完整或不一致，建议重新执行 AI Script Analysis。',
                    'Subject consistency failed: subject index/entities may be incomplete or inconsistent; rerun AI Script Analysis is recommended.'
                )
            );
        }
        setPostAnalysisCheckModal({
            open: true,
            status: 'done',
            message: summary,
            guidance,
        });

        if (onLog) {
            onLog(
                `Post-analysis check completed: subject=${passedSubject ? 'pass' : 'fail'}`,
                passedSubject ? 'success' : 'warning'
            );
        }
    };

    const collectMarkdownTableBlocks = (text) => {
        const source = String(text || '');
        const lines = source.split('\n');
        const blocks = [];
        let current = [];

        const flush = () => {
            if (current.length >= 2) {
                blocks.push(current.join('\n').trim());
            }
            current = [];
        };

        for (const rawLine of lines) {
            const line = String(rawLine || '').trim();
            if (line.startsWith('|') && line.includes('|')) {
                current.push(line);
            } else {
                flush();
            }
        }
        flush();

        return blocks;
    };

    const validateAutoSceneTableImport = (text) => {
        const blocks = collectMarkdownTableBlocks(text);

        if (blocks.length === 0) {
            return {
                ok: false,
                reason: t('未检测到可导入的 Scenes Markdown 表格。', 'No importable Scenes markdown table detected.'),
            };
        }
        const splitCells = (line) => {
            const cells = String(line || '').split('|').map(c => c.trim());
            if (cells[0] === '') cells.shift();
            if (cells[cells.length - 1] === '') cells.pop();
            return cells;
        };
        const normalize = (value) => String(value || '').toLowerCase().replace(/[\s_\-./()]/g, '');
        const isSeparatorLine = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);
        const findColIdx = (normalizedHeaders, patterns) => normalizedHeaders.findIndex((h) => patterns.some(p => h.includes(p)));
        const esc = (val) => String(val || '').replace(/\|/g, '\\|').replace(/\n/g, '<br>');

        let outputHeaders = null;
        let outputHeaderMap = null;
        const outputRows = [];
        let acceptedTables = 0;
        let droppedTables = 0;
        let droppedRows = 0;

        for (const block of blocks) {
            const lines = String(block || '').split('\n').map(v => String(v || '').trim()).filter(Boolean);
            if (lines.length < 2) {
                droppedTables += 1;
                continue;
            }

            const headers = splitCells(lines[0]);
            const normalizedHeaders = headers.map(normalize);
            const sceneIdIdx = findColIdx(normalizedHeaders, ['sceneid', '场景id']);
            const coreInfoIdx = findColIdx(normalizedHeaders, ['coresceneinfo', '核心场景信息']);
            const originalIdx = findColIdx(normalizedHeaders, ['originalscripttext', '原始剧本文本', 'scripttext']);

            if (sceneIdIdx < 0 || coreInfoIdx < 0 || originalIdx < 0) {
                droppedTables += 1;
                continue;
            }

            acceptedTables += 1;
            if (!outputHeaders) {
                outputHeaders = headers;
                outputHeaderMap = new Map(normalizedHeaders.map((h, idx) => [h, idx]));
            }

            const sourceHeaderMap = new Map(normalizedHeaders.map((h, idx) => [h, idx]));
            for (let i = 1; i < lines.length; i++) {
                const line = lines[i];
                if (isSeparatorLine(line)) continue;

                const cells = splitCells(line);
                while (cells.length < headers.length) cells.push('');

                const sceneId = String(cells[sceneIdIdx] || '').trim();
                const coreInfo = String(cells[coreInfoIdx] || '').trim();
                const originalText = String(cells[originalIdx] || '').trim();
                if (!sceneId || (!coreInfo && !originalText)) {
                    droppedRows += 1;
                    continue;
                }

                const mappedRow = outputHeaders.map((h) => {
                    const key = normalize(h);
                    const idx = sourceHeaderMap.has(key) ? sourceHeaderMap.get(key) : -1;
                    return idx >= 0 ? String(cells[idx] || '') : '';
                });
                outputRows.push(mappedRow);
            }
        }

        if (!outputHeaders || outputRows.length === 0) {
            return {
                ok: false,
                reason: t('未找到合格的 Scenes 表数据（可能缺少必需列或有效行）。', 'No valid Scenes table data found (required columns or valid rows may be missing).'),
            };
        }

        const headerLine = `| ${outputHeaders.map(esc).join(' | ')} |`;
        const sepLine = `| ${outputHeaders.map(() => '---').join(' | ')} |`;
        const rowLines = outputRows.map((r) => `| ${r.map(esc).join(' | ')} |`);
        const tableText = [headerLine, sepLine, ...rowLines].join('\n');

        let warning = '';
        if (droppedTables > 0 || droppedRows > 0 || blocks.length > 1) {
            warning = t(
                `已过滤非法数据：保留 ${acceptedTables} 张合格表，丢弃 ${droppedTables} 张不合格表、${droppedRows} 行不合格数据。`,
                `Invalid data filtered: kept ${acceptedTables} valid table(s), dropped ${droppedTables} invalid table(s) and ${droppedRows} invalid row(s).`
            );
        }

        return { ok: true, tableText, warning };
    };

    const doImportText = async (text, importType = 'auto', importOptions = {}) => {
        if (typeof onImportText !== 'function') {
            if (onLog) onLog('Import is not available in this context.', 'warning');
            return false;
        }
        try {
            const payload = (typeof text === 'string') ? text : String(text || '');
            if (importType === 'auto') {
                const check = validateAutoSceneTableImport(payload);
                if (check.ok) {
                    if (check.warning && onLog) onLog(check.warning, 'warning');
                } else {
                    // Do not block import here; allow downstream JSON/script/shot detection to run.
                    if (onLog) onLog(`Auto scene-table check skipped: ${check.reason}`, 'warning');
                }
            }

            const importResult = await onImportText(payload, importType, importOptions);
            return importResult || true;
        } catch (e) {
            if (onLog) onLog(`Import failed: ${e.message}`, 'error');
            alert(t('导入失败：', 'Import failed: ') + (e?.message || e));
            return false;
        }
    };

    const runAutoImportAndSwitchToScenes = async (analyzedText, options = {}) => {
        if (autoImportRunningRef.current) {
            if (onLog) onLog('Skipped duplicate auto-import run while another import is already active in this view.', 'warning');
            return null;
        }
        autoImportRunningRef.current = true;
        try {
            const switchToScenes = options?.switchToScenes !== false;
            const importOptions = (options && typeof options.importOptions === 'object') ? options.importOptions : {};
            if (typeof onImportText !== 'function') {
                if (onLog) onLog('Import is not available in this context.', 'warning');
                setAnalysisFlowStatus({
                    phase: 'completed',
                    message: t('分析完成（当前上下文不支持自动导入）', 'Analysis completed (auto import is not available in this context)'),
                });
                return null;
            }

            setAnalysisFlowStatus({
                phase: 'saving_scenes',
                message: t('🎬 AI导演已交稿，正在为您排版整理...', 'LLM response received, auto-importing...'),
            });

            if (onLog) onLog('Auto-importing analysis result...', 'process');       
            const check = validateAutoSceneTableImport(analyzedText || '');
            if (check.ok && check.warning && onLog) onLog(check.warning, 'warning');
            if (!check.ok && onLog) onLog(`Auto scene-table check skipped: ${check.reason}`, 'warning');

            // Keep full analysis payload so entities JSON can be imported in the same run.
            const importReport = await onImportText(analyzedText || '', 'auto', importOptions);
            if (onLog) onLog('Auto-import finished.', 'success');

            if (switchToScenes && typeof onSwitchToScenes === 'function') {
                onSwitchToScenes();
            }

            return importReport || null;
        } finally {
            autoImportRunningRef.current = false;
        }
    };

    

    

    const parseMarkdownTable = (text) => {
        if (!text || typeof text !== 'string') return null;
        const lines = text
            .split('\n')
            .map(l => l.trim())
            .filter(l => l.startsWith('|') && l.includes('|'));

        if (lines.length < 2) return null;

        const cleanCells = (line) => {
            let cols = line.split('|').map(c => c.trim());
            if (cols.length > 0 && cols[0] === "") cols.shift();
            if (cols.length > 0 && cols[cols.length - 1] === "") cols.pop();

            return cols.map(c => (c || '')
                .replace(/\\\|/g, '|')
                .replace(/<br\s*\/?>/gi, '\n')
            );
        };

        const isSeparatorLine = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);

        const headerLine = lines[0];
        const sepLine = lines[1];
        if (isSeparatorLine(headerLine) || !isSeparatorLine(sepLine)) return null;

        const headers = cleanCells(headerLine);
        if (headers.length === 0) return null;

        const rows = [];
        for (let i = 2; i < lines.length; i++) {
            const line = lines[i];
            if (isSeparatorLine(line)) continue;
            const cells = cleanCells(line);
            if (cells.length === 0) continue;
            while (cells.length < headers.length) cells.push('');
            rows.push(cells.slice(0, headers.length));
        }

        return { headers, rows };
    };

    const buildMarkdownTable = (headers, rows) => {
        const esc = (val) => (val || '')
            .replace(/\|/g, '\\|')
            .replace(/\n/g, '<br>');

        const headerLine = `| ${headers.map(esc).join(' | ')} |`;
        const sepLine = `| ${headers.map(() => '---').join(' | ')} |`;
        const rowLines = (rows || []).map(r => {
            const safe = [...r];
            while (safe.length < headers.length) safe.push('');
            return `| ${safe.slice(0, headers.length).map(esc).join(' | ')} |`;
        });
        return [headerLine, sepLine, ...rowLines].join('\n');
    };

    const extractScenesTableBlock = useCallback((text) => {
        if (!text || typeof text !== 'string') return '';

        const fullText = String(text);
        const headingMatch = fullText.match(/###\s*Part\s*1\s*:\s*Scenes\s*Table[^\n]*/i);
        const scopedText = headingMatch ? fullText.slice(headingMatch.index) : fullText;
        const lines = scopedText.split('\n');

        let started = false;
        const tableLines = [];

        for (const rawLine of lines) {
            const line = String(rawLine || '');
            const trimmed = line.trim();

            if (!started) {
                if (trimmed.startsWith('|') && trimmed.includes('|')) {
                    started = true;
                    tableLines.push(trimmed);
                }
                continue;
            }

            if (trimmed.startsWith('|') && trimmed.includes('|')) {
                tableLines.push(trimmed);
                continue;
            }

            if (tableLines.length >= 2) break;
        }

        return tableLines.join('\n').trim();
    }, []);

    const normalizeLlmMarkdownTable = useCallback((text) => {
        const sceneTableText = extractScenesTableBlock(text);
        const parsed = parseMarkdownTable(sceneTableText);
        if (!parsed) return '';

        const normalizeHeader = (h) => String(h || '').toLowerCase().replace(/[\s_.\-]/g, '');
        const sceneNoColIdx = parsed.headers.findIndex((h) => {
            const n = normalizeHeader(h);
            return n.includes('sceneno') || n.includes('场次序号') || n === '场次';
        });

        const normalizedRows = (parsed.rows || []).map((row, idx) => {
            const next = [...row];
            if (sceneNoColIdx >= 0) {
                while (next.length <= sceneNoColIdx) next.push('');
                next[sceneNoColIdx] = String(idx + 1);
            }
            return next;
        });

        return buildMarkdownTable(parsed.headers, normalizedRows);
    }, [extractScenesTableBlock, parseMarkdownTable, buildMarkdownTable]);

    const llmMarkdownTableText = useMemo(() => normalizeLlmMarkdownTable(llmResultContent), [llmResultContent, normalizeLlmMarkdownTable]);
    const llmMarkdownTable = useMemo(() => parseMarkdownTable(llmMarkdownTableText), [llmMarkdownTableText]);
    const llmSceneCount = useMemo(() => {
        const rows = Array.isArray(llmMarkdownTable?.rows) ? llmMarkdownTable.rows : [];
        return rows.length;
    }, [llmMarkdownTable]);

    const mergeEditedSceneTableIntoRaw = useCallback((rawText, editedTableText) => {
        const normalizedEditedTable = String(editedTableText || '').trim();
        const currentRaw = String(rawText || '');

        if (!normalizedEditedTable) return currentRaw;

        const existingTableBlock = extractScenesTableBlock(currentRaw);
        if (existingTableBlock) {
            const idx = currentRaw.indexOf(existingTableBlock);
            if (idx >= 0) {
                return `${currentRaw.slice(0, idx)}${normalizedEditedTable}${currentRaw.slice(idx + existingTableBlock.length)}`;
            }
        }

        const trimmedRaw = currentRaw.trim();
        if (!trimmedRaw) return normalizedEditedTable;
        return `${normalizedEditedTable}\n\n${trimmedRaw}`;
    }, [extractScenesTableBlock]);

    const llmSceneSubjectStats = useMemo(() => {
        const headers = Array.isArray(llmMarkdownTable?.headers) ? llmMarkdownTable.headers : [];
        const rows = Array.isArray(llmMarkdownTable?.rows) ? llmMarkdownTable.rows : [];
        if (!headers.length || !rows.length) return [];

        const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_.\-]/g, '');
        const findCol = (aliases) => headers.findIndex((h) => aliases.some((a) => normalizeHeader(h).includes(a)));

        const linkedCharactersIdx = findCol(['linkedcharacters', '关联角色', '角色']);
        const keyPropsIdx = findCol(['keyprops', '关键道具', '道具']);
        const environmentNameIdx = findCol(['environmentname', '环境名', '场景名']);

        const collectMatches = (text, regex, transform) => {
            const out = new Set();
            if (!text) return out;
            regex.lastIndex = 0;
            let match;
            while ((match = regex.exec(text)) !== null) {
                const value = transform(match);
                if (value) out.add(value);
            }
            return out;
        };

        return rows.map((row) => {
            const rowText = (row || []).map((cell) => String(cell || '')).join('\n');

            const characterSet = collectMatches(
                rowText,
                /CHAR:\s*\[@([^\]]+)\]|\[@([^\]]+)\]/gi,
                (m) => String(m[1] || m[2] || '').trim()
            );

            const propSet = collectMatches(
                rowText,
                /PROP:\s*\[([^\]]+)\]/gi,
                (m) => String(m[1] || '').trim()
            );

            const environmentSet = collectMatches(
                rowText,
                /ENV:\s*\[([^\]]+)\]/gi,
                (m) => String(m[1] || '').trim()
            );

            const splitAndPush = (set, value) => {
                String(value || '')
                    .split(/[\n,，;；]/)
                    .map((v) => String(v || '').trim())
                    .filter(Boolean)
                    .forEach((v) => set.add(v));
            };

            if (linkedCharactersIdx >= 0) splitAndPush(characterSet, row[linkedCharactersIdx]);
            if (keyPropsIdx >= 0) splitAndPush(propSet, row[keyPropsIdx]);
            if (environmentNameIdx >= 0) splitAndPush(environmentSet, row[environmentNameIdx]);

            return {
                characterCount: characterSet.size,
                environmentCount: environmentSet.size,
                propCount: propSet.size,
                characterNames: Array.from(characterSet).join(', '),
                environmentNames: Array.from(environmentSet).join(', '),
                propNames: Array.from(propSet).join(', '),
            };
        });
    }, [llmMarkdownTable]);

    const llmSceneSubjectDedupStats = useMemo(() => {
        const rows = Array.isArray(llmMarkdownTable?.rows) ? llmMarkdownTable.rows : [];
        const headers = Array.isArray(llmMarkdownTable?.headers) ? llmMarkdownTable.headers : [];
        const characterMap = new Map();
        const environmentMap = new Map();
        const propMap = new Map();

        const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_.\-]/g, '');
        const environmentNameIdx = headers.findIndex((h) => {
            const key = normalizeHeader(h);
            return key.includes('environmentname') || key.includes('环境名') || key.includes('场景名');
        });

        const addMatch = (targetMap, rawName) => {
            const display = normalizeSubjectName(rawName);
            const key = normalizeSubjectKey(rawName);
            if (!display || !key) return;
            if (!targetMap.has(key)) targetMap.set(key, display);
        };

        for (const row of rows) {
            const rowText = (row || []).map((cell) => String(cell || '')).join('\n');

            const charRe = /CHAR:\s*\[@([^\]]+)\]|\[@([^\]]+)\]/gi;
            charRe.lastIndex = 0;
            let charMatch;
            while ((charMatch = charRe.exec(rowText)) !== null) {
                addMatch(characterMap, charMatch[1] || charMatch[2] || '');
            }

            const envRe = /ENV:\s*\[([^\]]+)\]/gi;
            envRe.lastIndex = 0;
            let envMatch;
            while ((envMatch = envRe.exec(rowText)) !== null) {
                addMatch(environmentMap, envMatch[1] || '');
            }

            if (environmentNameIdx >= 0) {
                String(row?.[environmentNameIdx] || '')
                    .split(/[\n,，;；]/)
                    .map(v => String(v || '').trim())
                    .filter(Boolean)
                    .forEach((name) => addMatch(environmentMap, name));
            }

            const propRe = /PROP:\s*\[([^\]]+)\]/gi;
            propRe.lastIndex = 0;
            let propMatch;
            while ((propMatch = propRe.exec(rowText)) !== null) {
                addMatch(propMap, propMatch[1] || '');
            }
        }

        const character = characterMap.size;
        const environment = environmentMap.size;
        const prop = propMap.size;

        return {
            character,
            environment,
            prop,
            total: character + environment + prop,
        };
    }, [llmMarkdownTable]);

    const handleMerge = () => {
        const fullText = segments
            .map(seg => seg.content || '')
            .filter(t => t.trim().length > 0)
            .join('\n\n');
        setMergedContent(fullText);
        setShowMerged(true);
    };

    useEffect(() => {
        if (activeEpisode?.script_content) {
            setRawContent(activeEpisode.script_content);
        } else {
            setRawContent('');
        }

        setSubjectIndexText(activeEpisode?.ai_scene_analysis_subject_index || '');
        setAdaptationText(activeEpisode?.ai_scene_analysis_adaptation || '');
        setLlmAssetRawResultContent(activeEpisode?.ai_entity_design_result || activeEpisode?.ai_scene_analysis_subject_index || '');
        setAnalysisAttentionNotes(String(activeEpisode?.episode_info?.analysis_attention_notes || ''));
        setSubjectConsistencyResultText(String(activeEpisode?.episode_info?.subject_check_result || ''));
        setCoreCoverageResultText(String(activeEpisode?.episode_info?.core_coverage_check_result || ''));
        const persistedIds = activeEpisode?.episode_info?.reuse_subject_asset_ids;
        if (Array.isArray(persistedIds)) {
            setSelectedReuseSubjectIds(persistedIds.map(x => String(x)));
        } else {
            setSelectedReuseSubjectIds([]);
        }

        const stored = activeEpisode?.ai_scene_analysis_result;
        const storedText = typeof stored === 'string' ? stored : '';
        setLlmRawResultContent(storedText);
        setLlmResultContent(normalizeLlmMarkdownTable(storedText));

        if (!activeEpisode?.script_content) {
            setSegments([]);
            setIsRawMode(true);
            return;
        }

        const content = activeEpisode.script_content;
        
        // Mode 1: Markdown Table parser
        const hasTableStructure = /\|\s*Paragraph ID\s*\|/.test(content) || /\|\s*Content \(Revised\)\s*\|/.test(content);
        
        if (hasTableStructure) {
             const lines = content.split('\n').map(l => l.trim()).filter(l => l.includes('|'));
             const parsed = [];
             
             const headerIdx = lines.findIndex(l => l.includes("Paragraph ID") || l.includes("Content (Revised)"));
             if (headerIdx === -1) {
                 setSegments([]);
                 setIsRawMode(true);
                 return;
             }

             for (let i = headerIdx + 1; i < lines.length; i++) {
                 const line = lines[i];
                 if (line.includes('---')) continue; 
                 
                 let cols = line.split('|').map(c => c.trim());
                 if (cols.length > 0 && cols[0] === "") cols.shift();
                 if (cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                 
                 if (cols.length >= 6) {
                      parsed.push({
                         id: cols[0],
                         title: cols[1],
                         content: cols[2].replace(/<br\s*\/?>/gi, '\n'),
                         original: cols[3].replace(/<br\s*\/?>/gi, '\n'),
                         narrative_role: cols[4].replace(/<br\s*\/?>/gi, '\n'),
                         analysis: cols[5].replace(/<br\s*\/?>/gi, '\n')
                      });
                 }
             }
             if (parsed.length > 0) {
                 setSegments(parsed);
                 setIsRawMode(false);
             } else {
                 setSegments([]);
                 setIsRawMode(true);
             }
             return;
        }

        // Mode 2: Legacy parser
        const chunks = content.split(/## Segment (\d+)/).filter(Boolean);
        const parsed = [];
        
        // Basic heuristic to check if it matches legacy format at all
        let isLegacy = false;
        
        for (let i = 0; i < chunks.length; i += 2) {
            const id = chunks[i];
            const body = chunks[i+1] || "";
            if (!/^\d+$/.test(id)) continue;

            isLegacy = true; 
            const roleMatch = body.match(/\*\*Narrative Role:\*\*\s*([\s\S]*?)(?=\*\*Analysis:|\n##|$)/);
            const analysisMatch = body.match(/\*\*Analysis:\*\*\s*([\s\S]*?)(?=$)/);
            
            let narratives = roleMatch ? roleMatch[1].trim() : "";
            let analysis = analysisMatch ? analysisMatch[1].trim() : "";
            
            let mainContent = body;
            if (roleMatch) mainContent = mainContent.replace(roleMatch[0], '');
            if (analysisMatch) mainContent = mainContent.replace(analysisMatch[0], '');
            
            mainContent = mainContent.trim();
            const lines = mainContent.split('\n').filter(l => l.trim().length > 0);
            
            const title = (lines.length > 0 && lines[0].length < 50) ? lines[0] : "Untitled Segment";
            const textBody = (lines.length > 0 && lines[0].length < 50) ? lines.slice(1).join('\n') : lines.join('\n');

            parsed.push({ 
                id, 
                title, 
                content: textBody, 
                original: '',
                narrative_role: narratives, 
                analysis: analysis 
            });
        }
        
        if (isLegacy && parsed.length > 0) {
            setSegments(parsed);
            setIsRawMode(false);
        } else {
            setSegments([]);
            setIsRawMode(true);
        }
    }, [activeEpisode]);

    useEffect(() => {
        let mounted = true;
        const loadAssets = async () => {
            if (!isEpisodeOnePage || !projectId) {
                if (mounted) setAvailableSubjectAssets([]);
                return;
            }
            setIsLoadingSubjectAssets(true);
            try {
                const entities = await fetchEntities(projectId);
                if (!mounted) return;
                setAvailableSubjectAssets(Array.isArray(entities) ? entities : []);
            } catch (e) {
                console.error(e);
                if (mounted) setAvailableSubjectAssets([]);
            } finally {
                if (mounted) setIsLoadingSubjectAssets(false);
            }
        };
        loadAssets();
        return () => { mounted = false; };
    }, [isEpisodeOnePage, projectId]);

    

    const reuseSubjectTypeOptions = useMemo(() => {
        const types = new Set();
        for (const asset of availableSubjectAssets || []) {
            const t = String(asset?.type || '').trim();
            if (t) types.add(t);
        }
        return Array.from(types).sort((a, b) => a.localeCompare(b));
    }, [availableSubjectAssets]);

    const filteredSubjectAssets = useMemo(() => {
        const normalizedKeyword = String(reuseSubjectKeyword || '').trim().toLowerCase();
        return (availableSubjectAssets || []).filter(asset => {
            const typeValue = String(asset?.type || '').trim();
            const passType = reuseSubjectTypeFilter === 'all' || typeValue === reuseSubjectTypeFilter;
            if (!passType) return false;

            if (!normalizedKeyword) return true;

            const haystack = [
                asset?.name,
                asset?.description,
                asset?.narrative_description,
                asset?.anchor_description,
                asset?.type,
            ]
                .map(v => String(v || '').toLowerCase())
                .join(' ');

            return haystack.includes(normalizedKeyword);
        });
    }, [availableSubjectAssets, reuseSubjectKeyword, reuseSubjectTypeFilter]);

    const hasActiveReuseSubjectFilters = useMemo(() => {
        return reuseSubjectTypeFilter !== 'all' || String(reuseSubjectKeyword || '').trim().length > 0;
    }, [reuseSubjectTypeFilter, reuseSubjectKeyword]);

    const toggleReuseSubject = (assetId) => {
        const key = String(assetId);
        setSelectedReuseSubjectIds(prev => {
            const has = prev.includes(key);
            if (has) return prev.filter(v => v !== key);
            return [...prev, key];
        });
    };

    const clearReuseSubjectFilters = () => {
        setReuseSubjectTypeFilter('all');
        setReuseSubjectKeyword('');
    };

    const handleSaveReuseSubjects = async () => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        setIsSavingReuseSubjects(true);
        try {
            const mergedEpisodeInfo = {
                ...(activeEpisode?.episode_info || {}),
                reuse_subject_asset_ids: selectedReuseSubjectIds,
            };
            await onUpdateEpisodeInfo(activeEpisode.id, { episode_info: mergedEpisodeInfo });
            if (onLog) onLog('Episode 1 reusable subject assets saved.', 'success');
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Failed to save reusable subjects: ${e.message}`, 'error');
        } finally {
            setIsSavingReuseSubjects(false);
        }
    };

    const persistLlmResultContent = async (content, resultField = 'ai_scene_analysis_result') => {
        if (!activeEpisode?.id) return;
        if (!onUpdateEpisodeInfo) return;

        try {
            await onUpdateEpisodeInfo(activeEpisode.id, { [resultField]: content || '' });
        } catch (e) {
            console.error("Failed to persist LLM result", e);
            if (onLog) onLog(`Failed to save LLM result: ${e.message}`);
        }
    };

    // Keep the "LLM 返回结果" box in sync with DB-saved ai_scene_analysis_result.
    // Important: don't clobber local edits while user is typing.
    const lastLoadedAnalysisRef = useRef(null);
    const llmRawAutoSaveTimerRef = useRef(null);
    const llmRawAutoSaveArmedRef = useRef(false);
    const analysisResumeInFlightRef = useRef(false);
    const phase2ResolverRef = useRef(null);
    const analysisStopRequestedRef = useRef(false);
    const analysisRunInFlightRef = useRef(false);
    const autoImportRunningRef = useRef(false);
    const lastSubjectsImportIncompleteAlertRef = useRef('');
    const ANALYSIS_TASK_MAX_AGE_MS = 60 * 60 * 1000;
    const ANALYSIS_TASK_MARKER_TTL_MS = 120 * 60 * 1000;
    const AI_SHOTS_TASK_MARKER_TTL_MS = 45 * 60 * 1000;

    const isTaskCanceledError = useCallback((error) => {
        if (!error) return false;
        if (error?.isCanceled) return true;
        const code = Number(error?.errorCode || error?.response?.status || 0);
        if (code === 499) return true;
        const text = String(error?.message || error?.response?.data?.detail || '').toLowerCase();
        return text.includes('cancel') || text.includes('取消');
    }, []);

    const getAnalysisTaskStorageKey = useCallback((episodeId) => {
        if (!episodeId) return '';
        return `aistory:scene-analysis-task:${episodeId}`;
    }, []);

    const loadAnalysisTaskMarker = useCallback((episodeId) => {
        try {
            const key = getAnalysisTaskStorageKey(episodeId);
            if (!key || !window?.localStorage) return null;
            const raw = window.localStorage.getItem(key);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            const taskId = String(parsed?.taskId || '').trim();
            const startedAt = Number(parsed?.startedAt || 0);
            if (!taskId) return null;
            if (!Number.isFinite(startedAt) || startedAt <= 0) return { taskId, startedAt: Date.now() };
            // Align marker TTL with task polling timeout to avoid endless resume loops after reload.
            if ((Date.now() - startedAt) > ANALYSIS_TASK_MARKER_TTL_MS) {
                window.localStorage.removeItem(key);
                return null;
            }
            return { taskId, startedAt };
        } catch (_) {
            return null;
        }
    }, [ANALYSIS_TASK_MARKER_TTL_MS, getAnalysisTaskStorageKey]);

    const saveAnalysisTaskMarker = useCallback((episodeId, marker) => {
        try {
            const key = getAnalysisTaskStorageKey(episodeId);
            if (!key || !window?.localStorage) return;
            const taskId = String(marker?.taskId || '').trim();
            if (!taskId) return;
            const payload = {
                taskId,
                startedAt: Number(marker?.startedAt || Date.now()),
            };
            window.localStorage.setItem(key, JSON.stringify(payload));
            setActiveAnalysisTaskId(taskId);
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAnalysisTaskStorageKey]);

    const clearAnalysisTaskMarker = useCallback((episodeId) => {
        try {
            const key = getAnalysisTaskStorageKey(episodeId);
            if (!key || !window?.localStorage) return;
            window.localStorage.removeItem(key);
            setActiveAnalysisTaskId('');
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAnalysisTaskStorageKey]);

    const handleStopAnalysisTask = useCallback(async () => {
        if (!activeEpisode?.id) return;
        const marker = loadAnalysisTaskMarker(activeEpisode.id);
        const taskId = String(activeAnalysisTaskId || marker?.taskId || '').trim();
        if (!taskId) {
            setAnalysisFlowStatus({
                phase: 'warning',
                message: t('当前没有正在运行的场景推演任务需要被终止。', 'No running analysis task found to stop.'),
            });
            return;
        }

        setIsStoppingAnalysisTask(true);
        analysisStopRequestedRef.current = true;
        try {
            await stopAsyncTask(taskId);
            clearAnalysisTaskMarker(activeEpisode.id);
            setAnalysisFlowStatus({
                phase: 'warning',
                message: t('已请求停止当前剧本分析任务。', 'Stop requested for the current scene analysis task.'),
            });
            if (onLog) onLog(`Scene analysis stop requested: task_id=${taskId}`, 'warning');
        } catch (e) {
            setAnalysisFlowStatus({
                phase: 'warning',
                message: t(`停止任务失败：${e?.message || e}`, `Failed to stop task: ${e?.message || e}`),
            });
            if (onLog) onLog(`Failed to stop scene analysis task: ${e?.message || e}`, 'error');
            analysisStopRequestedRef.current = false;
        } finally {
            setIsStoppingAnalysisTask(false);
            setIsAnalyzing(false);
        }
    }, [activeAnalysisTaskId, activeEpisode?.id, clearAnalysisTaskMarker, loadAnalysisTaskMarker, onLog, t]);
    const refreshAnalysisFromDB = useCallback(async ({ resultField = 'ai_scene_analysis_result' } = {}) => {
        if (!projectId || !activeEpisode?.id) return;
        try {
            const eps = await fetchEpisodes(projectId);
            const fresh = (eps || []).find(e => e.id === activeEpisode.id);
            const dbText = String((fresh && fresh[resultField]) || '');

            // Only update if user hasn't diverged from last loaded content.
            if (resultField === 'ai_entity_design_result') {
                const current = llmAssetRawResultContent || '';
                if (dbText && dbText !== current) {
                    setLlmAssetRawResultContent(dbText);
                }
            } else {
                const current = llmRawResultContent || '';
                const lastLoaded = lastLoadedAnalysisRef.current;
                const userHasEdited = lastLoaded !== null && current !== lastLoaded;

                if (!userHasEdited) {
                    if (dbText && dbText !== current) {
                        setLlmRawResultContent(dbText);
                        setLlmResultContent(normalizeLlmMarkdownTable(dbText));
                    }
                    lastLoadedAnalysisRef.current = dbText;
                }
            }
        } catch (e) {
            // non-fatal
            console.warn('[ScriptEditor] Failed to refresh analysis from DB', e);
        }
    }, [projectId, activeEpisode?.id, llmAssetRawResultContent, llmRawResultContent, normalizeLlmMarkdownTable]);

    const waitForEpisodeAnalysisResultUpdate = useCallback(async ({ baselineText = '', timeoutMs = 600000, intervalMs = 3500, resultField = 'ai_scene_analysis_result' } = {}) => {
        if (!projectId || !activeEpisode?.id) return '';
        const base = String(baselineText || '').trim();
        const deadline = Date.now() + Math.max(30000, Number(timeoutMs || 600000));

        while (Date.now() < deadline) {
            try {
                const eps = await fetchEpisodes(projectId);
                const fresh = (eps || []).find(e => e.id === activeEpisode.id);
                // Dynamically check the target field
                const dbText = String((fresh && fresh[resultField]) || '').trim();
                if (dbText && dbText !== base) {
                    return dbText;
                }
            } catch (_) {
                // Non-fatal polling fallback; keep waiting.
            }
            await new Promise(resolve => setTimeout(resolve, Math.max(1500, Number(intervalMs || 3500))));
        }
        return '';
    }, [projectId, activeEpisode?.id]);

    const awaitAnalyzeSceneWithRecovery = useCallback(async (invokeAnalyze, { startedAt = Date.now(), baselineText = '', resultField = 'ai_scene_analysis_result' } = {}) => {
        let settled = false;
        let resolvedValue = null;
        let resolvedError = null;

        const analyzePromise = Promise.resolve()
            .then(() => invokeAnalyze())
            .then((value) => {
                settled = true;
                resolvedValue = value;
            })
            .catch((err) => {
                settled = true;
                resolvedError = err;
            });

        // 重新计算超时时间，确保从每次调用开始计时，至少给足60分钟以处理深度回退和排队延迟
        const actualStartedAt = Date.now(); 
        const deadline = actualStartedAt + 60 * 60 * 1000;
        while (!settled && Date.now() < deadline) {
            const recoveredText = await waitForEpisodeAnalysisResultUpdate({
                baselineText,
                timeoutMs: 8000,
                intervalMs: 3000,
                resultField,
            });
            if (recoveredText) {
                if (onLog) {
                    onLog('Recovered AI Script Analysis result from episode storage while async task polling was delayed.', 'warning');
                }
                return {
                    success: true,
                    result: recoveredText,
                    meta: {
                        saved_to_episode: true,
                        recovered_from_episode_poll: true,
                    },
                    warnings: [t('后端任务轮询延迟，已从分集已保存结果继续流程。', 'Task polling lag detected; continued using episode-saved analysis result.')],
                    warning_codes: ['ANALYSIS_TASK_POLLING_LAG_RECOVERED'],
                };
            }
        }

        if (!settled) {
            throw new Error('AI Script Analysis timed out while waiting for async task result (resume deadline reached).');
        }
        await analyzePromise;
        if (resolvedError) throw resolvedError;
        if (settled) return resolvedValue;
        throw new Error('AI Script Analysis timed out while waiting for async task result.');
    }, [onLog, t, waitForEpisodeAnalysisResultUpdate]);

    const selectedReuseSubjectAssets = useMemo(() => {
        if (!Array.isArray(availableSubjectAssets) || availableSubjectAssets.length === 0) return [];
        const selected = new Set((selectedReuseSubjectIds || []).map(v => String(v)));
        return availableSubjectAssets
            .filter(asset => selected.has(String(asset.id)))
            .map(asset => ({
                id: asset.id,
                name: asset.name || '',
                type: asset.type || '',
                description: asset.description || asset.narrative_description || '',
                anchor_description: asset.anchor_description || '',
            }));
    }, [availableSubjectAssets, selectedReuseSubjectIds]);

    const runPostImportSceneSubjectPipeline = useCallback(async (importReport, explicitText = null, options = {}) => {
        const importedSceneRows = Array.isArray(importReport?.importedSceneRows) ? importReport.importedSceneRows : [];
        const emptyReport = {
            checkedSceneCount: importedSceneRows.length,
            missingSceneCount: 0,
            missingItemCount: 0,
            missingSceneReports: [],
            supplementReport: {
                createdItems: [], skippedItems: [], failedItems: [], sceneReports: [],
                countsByType: { character: 0, prop: 0, environment: 0 },
            },
            importedSubjectCounts: { character: 0, prop: 0, environment: 0 },
        };

        onLog?.(`[Phase 2 Debug] checking early return condition: projectId=${projectId}, importedSceneRows count=${importedSceneRows.length}`);

        if (!projectId) {
            onLog?.(`[Phase 2 Debug] aborting! Because projectId is empty.`);
            return emptyReport;
        }

                const authoritativeSubjectText = explicitText || llmRawResultContent || llmResultContent || activeEpisode?.ai_scene_analysis_result || '';
                const extractedSections = extractAnalysisSections(authoritativeSubjectText);
                let subjectIndexText = extractedSections.subjectIndexText || "";
                let adaptationText = extractedSections.adaptationText || "";

                    if (adaptationText) {
                            onLog?.(`[Asset Gen Tracking] Extracted Script Adaptation (length: ${adaptationText.length})`);
                    }

          onLog?.(`[Asset Gen Tracking] Initial authoritativeText length: ${authoritativeSubjectText.length}`);

          if (authoritativeSubjectText.includes("PROHIBITED_CONTENT")) {
              throw new Error("出现供应商政策不允许内容");
          }

        // Try to match the block wrapped by at least 5 dashes: ---------
        if (extractedSections.hasStructuredSubjectIndex) {
            onLog?.(`[Asset Gen Tracking] Extracted Subject Index (length: ${subjectIndexText.length})`);
        } else {
            onLog?.(`[Asset Gen Tracking] Error: Failed to find Subject Index header or dashes! Aborting asset generation.`, 'error');
            throw new Error(SUBJECT_INDEX_PARSE_ERROR);
        }

        // Phase 2 Preparation: Save extracted subjectIndexText to episode and set UI state
        if (subjectIndexText.trim() || adaptationText.trim()) {
              if (subjectIndexText.trim()) setSubjectIndexText(subjectIndexText);
              const updatePayload = {};
              if (subjectIndexText.trim()) updatePayload.ai_scene_analysis_subject_index = subjectIndexText.trim();
              if (adaptationText.trim()) updatePayload.ai_scene_analysis_adaptation = adaptationText.trim();
              
              try {
                  await updateEpisode(activeEpisode.id, updatePayload);
                  onLog?.(`[Phase 2] Saved analysis meta (index len: ${subjectIndexText.length}, adaptation len: ${adaptationText.length})`);
              } catch (error) {
                  onLog?.(`[Phase 2] Warning: Failed to save analysis meta to episode: ${error.message}`);
              }
          }

        if (!subjectIndexText.trim()) {
            console.log("No Subject Index found in the analysis result. Skipping asset generation.");
            return emptyReport;
        }

        setAnalysisFlowStatus({
            phase: "generating_assets",
            message: t("✨ 正在为您生成对应的人物和场景资产...", "Generating design assets from Subject Index..."),
        });

        try {
            onLog?.(`[Asset Gen Tracking] Preparing to fetch 'entity_design.md'`);
            const promptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design.md").catch(() => null);
            let promptContent = promptRes?.content || "";
            if (!promptContent) {
                onLog?.(`[Asset Gen Tracking] Warning: 'entity_design.md' prompt is empty or failed to load.`);
            }

            let finalPromptContent = promptContent;
            let finalSubjectIndexText = subjectIndexText;

            // Inject Project Info Context for Phase 2
            const projectInfo = (project?.global_info && typeof project?.global_info === 'object') ? project.global_info : {};
            const normalizeInfoKey = (key) => String(key || '').toLowerCase().replace(/[\s\-]/g, '_').trim();
            const getInfoValue = (aliases = []) => {
                const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
                for (const [k, v] of Object.entries(projectInfo)) {
                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                    const text = String(v || '').trim();
                    if (text) return text;
                }
                return '';
            };

            const language = getInfoValue(['language', 'project_language', 'lang']);
            const getInfoArray = (aliases = []) => {
                const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
                for (const [k, v] of Object.entries(projectInfo)) {
                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                    if (Array.isArray(v)) {
                        const arr = v.map(item => String(item || '').trim()).filter(Boolean);
                        if (arr.length) return arr;
                    }
                    if (typeof v === 'string') {
                        const arr = v.split(/[\n,，;；]/).map(item => item.trim()).filter(Boolean);
                        if (arr.length) return arr;
                    }
                }
                return [];
            };
            const visualParams = (projectInfo?.tech_params && typeof projectInfo.tech_params === 'object' && projectInfo.tech_params.visual_standard) ? projectInfo.tech_params.visual_standard : {};
            const getVisualValue = (aliases = []) => {
                const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
                for (const [k, v] of Object.entries(visualParams || {})) {
                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                    const text = String(v || '').trim();
                    if (text) return text;
                }
                for (const [k, v] of Object.entries(projectInfo)) {
                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                    const text = String(v || '').trim();
                    if (text) return text;
                }
                return '';
            };
            const borrowedFilms = getInfoArray(['borrowed_films', 'borrowedFilms', 'reference_films', 'referenceFilms']);

            const metaParts = [
                'Project Context (prepend and treat as high-priority constraints for generating design assets):',
                '[Basic Info]'
            ];
            const title = getInfoValue(['script_title', 'title']);
            const episode = getInfoValue(['series_episode', 'episode']);
            const type = getInfoValue(['type']);
            const basePositioning = getInfoValue(['base_positioning']);
            if (title) metaParts.push(`Title: ${title}`);
            if (episode) metaParts.push(`Episode: ${episode}`);
            if (type) metaParts.push(`Type: ${type}`);
            if (basePositioning) metaParts.push(`Base Positioning: ${basePositioning}`);
            if (language) {
                metaParts.push(`Language: ${language}`);
            } else {
                 metaParts.push(`Language Warning: project language is empty. You MUST infer one target natural language from script context and keep all natural-language descriptions consistently in that single language.`);
            }
            metaParts.push('[Technical & Visual Parameters]');
            const aspectRatio = getVisualValue(['aspect_ratio']);
            const imageSize = getVisualValue(['image_size']);
            const horizontalResolution = getVisualValue(['horizontal_resolution']);
            const verticalResolution = getVisualValue(['vertical_resolution']);
            const frameRate = getVisualValue(['frame_rate']);
            const quality = getVisualValue(['quality']);
            const globalStyle = getInfoValue(['Global_Style', 'global_style', 'style']);
            const tone = getInfoValue(['tone', 'mood']);
            const lighting = getInfoValue(['lighting', 'light']);
            
            if (aspectRatio) metaParts.push(`Aspect Ratio: ${aspectRatio}`);
            if (imageSize) metaParts.push(`Image Size: ${imageSize}`);
            if (horizontalResolution) metaParts.push(`Horizontal Resolution: ${horizontalResolution}`);
            if (verticalResolution) metaParts.push(`Vertical Resolution: ${verticalResolution}`);
            if (frameRate) metaParts.push(`Frame Rate: ${frameRate}`);
            if (quality) metaParts.push(`Quality: ${quality}`);
            if (globalStyle) metaParts.push(`Global Style: ${globalStyle}`);
            if (borrowedFilms.length > 0) metaParts.push(`Borrowed Films: ${borrowedFilms.join(', ')}`);
            if (tone) metaParts.push(`Tone: ${tone}`);
            if (lighting) metaParts.push(`Lighting: ${lighting}`);
            
            const eraField = getInfoValue(['era', 'era_setting', 'period', 'time_setting']);
            const regionField = getInfoValue(['region_culture', 'region', 'country', 'country_region']);
            const shotPrefField = getInfoValue(['shot_preference', 'lens_preference', 'camera_preference']);
            const broadcastSafetyField = getInfoValue(['broadcast_security_level', 'broadcast_safety_level', 'safety_level', 'broadcast_safety']);

            if (eraField) metaParts.push(`Era / Period: ${eraField}`);
            if (regionField) metaParts.push(`Region / Country: ${regionField}`);
            if (shotPrefField) metaParts.push(`Shot / Lens Preference: ${shotPrefField}`);
            if (broadcastSafetyField) metaParts.push(`Broadcast Security Level: ${broadcastSafetyField}`);
            
            metaParts.push('Use this project context as first-class constraints before generating the subjects.');

            if (Object.keys(projectInfo).length > 0) {
                finalSubjectIndexText = `${metaParts.join('\n')}\n\n[Subject Index extracted from Phase 1]\n${finalSubjectIndexText}`;
            }

            const isUserSuper = isSuperuser || isSuperuserRef.current; // Capture current state or use ref if we had one
            if (isUserSuper) {
                setSystemPrompt(finalPromptContent);
                setUserPrompt(finalSubjectIndexText);
                setShowAnalysisModal(true);
                
                onLog?.(`[Asset Gen Tracking] Waiting for Superuser to confirm entity_design prompt...`);
                // Wait for the modal submit
                const confirmed = await new Promise(resolve => {
                    phase2ResolverRef.current = resolve;
                });
                
                if (!confirmed || typeof confirmed !== 'object') {
                    onLog?.(`[Asset Gen Tracking] Superuser aborted second pass phase.`);
                    return emptyReport;
                }
                
                finalPromptContent = confirmed.systemPrompt || finalPromptContent;
                finalSubjectIndexText = confirmed.userPrompt || finalSubjectIndexText;
            }

            onLog?.(`[Asset Gen Tracking] Launching second LLM call for 'subject_generation'`);

            const phase1SystemApiId = Number(functionApiConfigs?.selectedApi?.system_api_id || 0)
                || Number(localStorage.getItem('func_api_script_analysis') || 0)
                || null;
            if (phase1SystemApiId) {
                onLog?.(`[Phase 2] Reusing Phase 1 system_api_id=${phase1SystemApiId} for subject_generation.`, 'info');
            } else {
                onLog?.('[Phase 2] Phase 1 system_api_id is missing; fallback routing may select a different API.', 'warning');
            }

            const result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    finalSubjectIndexText, 
                    finalPromptContent, 
                    null, 
                    activeEpisode?.id || null, 
                    analysisAttentionNotes, 
                    selectedReuseSubjectAssets, 
                    {
                        onTaskCreated: (taskId) => {
                            setActiveAnalysisTaskId(String(taskId || '').trim());
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt: Date.now(), phase: 2 });
                        }
                    }, 
                    projectId,
                    "subject_generation",
                    phase1SystemApiId,
                    "2_pass_generate_assets"
                ),
                { startedAt: Date.now(), baselineText: activeEpisode?.ai_entity_design_result || '', resultField: 'ai_entity_design_result' }
            );

            const analyzedText = extractAnalysisTextFromResult(result);
            setLlmAssetRawResultContent(analyzedText);

            const savedByBackend = !!(result?.meta?.saved_to_episode);
            try {
                if (!savedByBackend) {
                    onLog?.('[Asset Gen Tracking] Persisting second-pass raw output to ai_entity_design_result...', 'process');
                    await persistLlmResultContent(analyzedText || '', 'ai_entity_design_result');
                } else {
                    await refreshAnalysisFromDB({ resultField: 'ai_entity_design_result' });
                }
            } catch (persistErr) {
                onLog?.(`[Asset Gen Tracking] Phase 2 raw output save warning: ${persistErr?.message || persistErr}`, 'warning');
            }

            if (analyzedText) {
                // Safeguard: make sure we are not importing plain text phase 1 by mistake
                const hasValidSubjectJsonBlock = /"characters"\s*:\s*\[|"props"\s*:\s*\[|"environments"\s*:\s*\[|"posters"\s*:\s*\[/i.test(analyzedText);
                const backendSubjectsJson = result?.subjects_json;
                
                if (!hasValidSubjectJsonBlock && !backendSubjectsJson) {
                    onLog?.(`[Asset Gen Tracking] Warning: AI did not return a valid Entities JSON block. Skipping import to prevent overwriting index.`, "warning");
                    throw new Error("AI 引擎在整理出场名单时开小差了，未能返回标准数据表。请点击查阅原文检查，是否可以手动重新生成。");
                } else {
                    // Automatically import the generated subjects
                    const sceneImportReport = await doImportText(analyzedText, 'json', {
                        onLog,
                        projectId,
                        episodeId: activeEpisode?.id,
                        subjectsJson: backendSubjectsJson || null,
                        suppressAlerts: true,
                    });

                    const createdLen = sceneImportReport?.createdSubjectItems?.length || sceneImportReport?.createdEntities?.length || 0;
                    const matchedLen = sceneImportReport?.skippedSubjectItems?.length || sceneImportReport?.matchedEntities?.length || 0;
                    onLog?.(`[Asset Gen Tracking] Asset import completed. Created/Updated: ${createdLen}, Matched/Skipped: ${matchedLen}`);

                    return {
                        checkedSceneCount: importedSceneRows.length,
                        missingSceneCount: 0,
                        missingItemCount: createdLen + matchedLen,
                        supplementReport: {
                            createdItems: sceneImportReport?.createdSubjectItems || [],
                            skippedItems: sceneImportReport?.skippedSubjectItems || [],
                            failedItems: [],
                        },
                        importedSubjectCounts: sceneImportReport?.importedSubjectCounts,
                        dbPersistedCounts: sceneImportReport?.dbPersistedCounts,
                        dbRunInsertedCounts: sceneImportReport?.dbRunInsertedCounts,
                    };
                }
            }

        } catch (error) {
            console.error("Asset generation step failed:", error);
            onLog?.(`Asset generation failed: ${error.message}`);
            throw error;
        }

        return emptyReport;
    }, [
        projectId, llmRawResultContent, llmResultContent, activeEpisode, t, onLog,
        fetchPrompt, analyzeScene, awaitAnalyzeSceneWithRecovery,
        analysisAttentionNotes, selectedReuseSubjectAssets, extractAnalysisTextFromResult, doImportText,
        isSuperuser, setSystemPrompt, setUserPrompt, setShowAnalysisModal, functionApiConfigs,
        project
    ]);

    

    

    const resumeAnalysisFromTaskMarker = useCallback(async (marker) => {
        if (!activeEpisode?.id || !marker?.taskId) return;
        if (analysisResumeInFlightRef.current || analysisRunInFlightRef.current) return;
        analysisResumeInFlightRef.current = true;

        const startedAt = Date.now(); // Clear previous time on resume/retry
        const remainingTimeoutMs = ANALYSIS_TASK_MAX_AGE_MS;
        if (marker?.phase === 2) {
            setIsAnalyzing(false);
            setIsRetryingPhase2(true);
            setActiveAnalysisTaskId(String(marker?.taskId || '').trim());
            setAnalysisFlowStatus({
                phase: 'generating_assets',
                message: t("✨ 发现有个没完成的第二阶段任务，正在为您继续生成对应的人物和场景资产...", "Resuming Phase 2 asset generation..."),
            });
            try {
                const result = await awaitAnalyzeSceneWithRecovery(
                    () => waitForAsyncTask(marker.taskId, { interval: 2500, timeout: remainingTimeoutMs }),
                    { startedAt, baselineText: activeEpisode?.ai_entity_design_result || '', resultField: 'ai_entity_design_result' }
                );
                const analyzedText = extractAnalysisTextFromResult(result);
                setLlmAssetRawResultContent(analyzedText);

                const savedByBackend = !!(result?.meta?.saved_to_episode);
                try {
                    if (!savedByBackend) {
                        await persistLlmResultContent(analyzedText || '', 'ai_entity_design_result');
                    } else {
                        await refreshAnalysisFromDB({ resultField: 'ai_entity_design_result' });
                    }
                } catch (persistErr) {
                    onLog?.(`[Asset Gen Tracking] Phase 2 recovery save warning: ${persistErr?.message || persistErr}`, 'warning');
                }

                if (analyzedText) {
                    const hasValidSubjectJsonBlock = /"characters"s*:s*\[|"props"s*:s*\[|"environments"s*:s*\[|"posters"s*:s*\[/i.test(analyzedText);
                    const backendSubjectsJson = result?.subjects_json;
                    if (!hasValidSubjectJsonBlock && !backendSubjectsJson) {
                        onLog?.(`[Asset Gen Tracking] Warning: AI did not return a valid Entities JSON block during Phase 2 recovery.`);
                    } else {
                        const sceneImportReport = await doImportText(analyzedText, 'json', {
                            onLog,
                            projectId,
                            episodeId: activeEpisode?.id,
                            subjectsJson: backendSubjectsJson || null,
                            suppressAlerts: true,
                        });
                        
                        setAnalysisUiReport(prev => {
                            const prevImport = prev?.importReport || { importedSceneRows: [] };
                            return {
                                status: 'completed',
                                startedAt,
                                durationMs: Date.now() - startedAt,
                                phaseTimings: null,
                                warning: '',
                                error: '',
                                runtimeMeta: null,
                                importReport: {
                                    ...prevImport,
                                    sceneSubjectPostImportReport: { checkedSceneCount: 0, missingSceneCount: 0, missingItemCount: (sceneImportReport?.createdSubjectItems?.length || 0) + (sceneImportReport?.skippedSubjectItems?.length || 0), missingSceneReports: [], supplementReport: { createdItems: sceneImportReport?.createdSubjectItems || [], skippedItems: sceneImportReport?.skippedSubjectItems || [], failedItems: [], countsByType: { character: 0, prop: 0, environment: 0 } }, importedSubjectCounts: sceneImportReport?.importedSubjectCounts || { character: 0, prop: 0, environment: 0 } },
                                    dbRunInsertedCounts: sceneImportReport?.dbRunInsertedCounts,
                                    dbPersistedCounts: sceneImportReport?.dbPersistedCounts,
                                    importedSubjectCounts: prevImport.importedSubjectCounts ? {
                                        character: (prevImport.importedSubjectCounts.character || 0) + (sceneImportReport?.importedSubjectCounts?.character || 0),
                                        prop: (prevImport.importedSubjectCounts.prop || 0) + (sceneImportReport?.importedSubjectCounts?.prop || 0),
                                        environment: (prevImport.importedSubjectCounts.environment || 0) + (sceneImportReport?.importedSubjectCounts?.environment || 0),
                                    } : sceneImportReport?.importedSubjectCounts,
                                }
                            };
                        });
                        
                        const createdCount = sceneImportReport?.createdSubjectItems?.length || 0;
                        const skippedCount = sceneImportReport?.skippedSubjectItems?.length || 0;
                        setAnalysisFlowStatus({
                            phase: 'completed',
                            message: t(`🎉 恢复成功！系统回溯了进度，顺利为您生成了 ${createdCount} 个全新资产（有 ${skippedCount} 个已存在从而跳过）。`, `Recovery successful. Generated ${createdCount} new assets (skipped ${skippedCount}).`)
                        });
                    }
                } else {
                    setAnalysisFlowStatus({ phase: 'warning', message: t('恢复第二阶段分析失败：未返回有效内容', 'Failed to resume phase 2: returned no content') });
                }
                clearAnalysisTaskMarker(activeEpisode.id);
            } catch (e) {
                console.error("Phase 2 recovery error:", e);
                const friendlyRecoveryError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
                setAnalysisFlowStatus({ phase: 'failed', message: t(`恢复第二阶段分析任务失败：${friendlyRecoveryError}`, `Failed to resume Phase 2 analysis task: ${friendlyRecoveryError}`) });
                clearAnalysisTaskMarker(activeEpisode.id);
            } finally {
                analysisResumeInFlightRef.current = false;
                setIsRetryingPhase2(false);
                setActiveAnalysisTaskId('');
            }
            return;
        }

        
        if (remainingTimeoutMs <= 0) {
            clearAnalysisTaskMarker(activeEpisode.id);
            setAnalysisFlowStatus({
                phase: 'warning',
                message: t('检测到过期的分析任务恢复标记，已自动清理。', 'Detected an expired analysis task marker and cleared it automatically.'),
            });
            analysisResumeInFlightRef.current = false;
            return;
        }
        const phaseMarks = {
            submitStartedAt: startedAt,
            analyzeStartedAt: startedAt,
            llmReturnedAt: 0,
            importStartedAt: 0,
            importFinishedAt: 0,
            persistStartedAt: 0,
            persistFinishedAt: 0,
            completedAt: 0,
        };
        let runtimeMeta = null;
        let importReport = null;
        let postImportSceneSubjectReport = null;
        let importWarningMessage = '';

        setIsAnalyzing(true);
        setActiveAnalysisTaskId(String(marker?.taskId || '').trim());
        analysisStopRequestedRef.current = false;
        setAnalysisFlowStatus({
            phase: 'analyzing',
            message: t('🔄 发现有个没完成的场景任务，接着帮您做完...', 'Detected an in-progress analysis task, reconnecting...'),
        });
        setAnalysisUiReport({
            status: 'running',
            startedAt,
            durationMs: 0,
            phaseTimings: null,
            importReport: null,
            runtimeMeta: null,
            warning: '',
            error: '',
        });

        try {
            const baselineText = String(activeEpisode?.ai_scene_analysis_result || llmRawResultContent || '').trim();
            const result = await awaitAnalyzeSceneWithRecovery(
                () => waitForAsyncTask(marker.taskId, { interval: 2500, timeout: remainingTimeoutMs }),
                { startedAt, baselineText }
            );
            const analyzedText = extractAnalysisTextFromResult(result);
            phaseMarks.llmReturnedAt = Date.now();

            if (result && result.meta) {
                runtimeMeta = extractAnalysisRuntimeMeta(result.meta);
                setAnalysisRuntimeMeta(runtimeMeta);
            } else {
                runtimeMeta = null;
                setAnalysisRuntimeMeta(null);
            }

            const integrityWarnings = collectAnalysisWarnings(result);
            const displayWarnings = collectAnalysisWarnings(result, { includeLogOnly: false });
            if (displayWarnings.length > 0) {
                showAnalysisWarningStatus(displayWarnings);
            }

            setLlmRawResultContent(analyzedText || '');
            setLlmResultContent(normalizeLlmMarkdownTable(analyzedText || ''));
            lastLoadedAnalysisRef.current = analyzedText || '';

            phaseMarks.importStartedAt = Date.now();
            try {
                importReport = await runAutoImportAndSwitchToScenes(analyzedText || '', { 
                    switchToScenes: false,
                    importOptions: { suppressAlerts: true }
                });
                if (!importReport) {
                    importWarningMessage = t('自动导入未返回结果，请检查导入配置或返回格式。', 'Auto-import returned no result. Check import config or response format.');
                    setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
                }
            } catch (importErr) {
                importWarningMessage = t(
                    `自动导入失败：${importErr?.message || importErr}`,
                    `Auto-import failed: ${importErr?.message || importErr}`
                );
                setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            maybeAlertIncompleteSubjectsImport(result, analyzedText || '');

            const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, analyzedText);
            if (importReport && typeof importReport === 'object') {
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.dbRunInsertedCounts) {
                    importReport.dbRunInsertedCounts = postImportSceneSubjectReport.dbRunInsertedCounts;
                }
                if (postImportSceneSubjectReport?.dbPersistedCounts) {
                    importReport.dbPersistedCounts = postImportSceneSubjectReport.dbPersistedCounts;
                }
            }

            const savedByBackend = !!(result?.meta?.saved_to_episode);
            phaseMarks.persistStartedAt = Date.now();
            try {
                if (!savedByBackend) {
                    await persistLlmResultContent(analyzedText || '');
                } else {
                    await refreshAnalysisFromDB();
                }
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }

            try {
                const firstPassReport = buildSubjectConsistencyReport(analyzedText || '');
                setSubjectConsistencyReport(firstPassReport);
                if (!firstPassReport.ok) {
                    setAnalysisFlowStatus({
                        phase: 'warning',
                        message: t('实体一致性检查告警：请查看提示后继续。', 'Entity consistency warning: review the message and continue.'),
                    });
                }
            } catch (_) {
                // non-blocking
            }

            if (analysisRunInFlightRef.current || analysisStopRequestedRef.current) {
                if (onLog) onLog('Resume was superseded by a new analysis run, stopping UI update.', 'warning');
                return;
            }

            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            setAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                warning: importWarningMessage,
                error: '',
            });

            const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
            const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
            const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
            const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
            setAnalysisFlowStatus({
                phase: 'completed',
                message: postImportMissingItems > 0
                    ? (
                        postImportSupplementFailed > 0
                            ? t(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`)
                            : t(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`)
                    )
                    : t('✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.'),
            });

            clearAnalysisTaskMarker(activeEpisode.id);
        } catch (e) {
            const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            setAnalysisFlowStatus(
                canceled
                    ? { phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') }
                    : { phase: 'failed', message: t(`恢复分析任务失败：${e?.message || e}`, `Failed to resume analysis task: ${e?.message || e}`) }
            );
            setAnalysisUiReport({
                status: canceled ? 'warning' : 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                warning: canceled ? t('分析任务已由用户停止。', 'Analysis task was stopped by user.') : '',
                error: canceled ? '' : (e?.message || String(e || '')),
            });
            clearAnalysisTaskMarker(activeEpisode.id);
        } finally {
            analysisResumeInFlightRef.current = false;
            if (!analysisRunInFlightRef.current) {
                setIsAnalyzing(false);
                setActiveAnalysisTaskId('');
                analysisStopRequestedRef.current = false;
            }
        }
    }, [
        activeEpisode?.id,
        ANALYSIS_TASK_MAX_AGE_MS,
        buildSubjectConsistencyReport,
        clearAnalysisTaskMarker,
        collectAnalysisWarnings,
        computeAnalysisPhaseTimings,
        extractAnalysisRuntimeMeta,
        isTaskCanceledError,
        normalizeLlmMarkdownTable,
        persistLlmResultContent,
        refreshAnalysisFromDB,
        runAutoImportAndSwitchToScenes,
        showAnalysisWarningStatus,
        t,
            doImportText,
        setLlmAssetRawResultContent,
        setIsRetryingPhase2,
        projectId,
        onLog,
]);

    useEffect(() => {
        return () => {
            analysisStopRequestedRef.current = true;
        };
    }, []);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        if (isAnalyzing || analysisResumeInFlightRef.current) return;
        const marker = loadAnalysisTaskMarker(activeEpisode.id);
        if (!marker?.taskId) return;
        resumeAnalysisFromTaskMarker(marker);
    }, [activeEpisode?.id]);

    useEffect(() => {
        // On episode change/remount, prefer parent-provided field; fallback to DB refresh.
        const initial = activeEpisode?.ai_scene_analysis_result || '';
        setLlmRawResultContent(initial);
        setLlmResultContent(normalizeLlmMarkdownTable(initial));
        setSubjectConsistencyResultText(String(activeEpisode?.episode_info?.subject_check_result || ''));
        setCoreCoverageResultText(String(activeEpisode?.episode_info?.core_coverage_check_result || ''));
        setAnalysisRuntimeMeta(null);
        lastLoadedAnalysisRef.current = initial;
        if (!initial) {
            refreshAnalysisFromDB();
        }
    }, [activeEpisode?.id, normalizeLlmMarkdownTable]);

    const handleLlmCellChange = (rowIdx, colIdx, value) => {
        const parsed = parseMarkdownTable(llmMarkdownTableText || llmResultContent);
        if (!parsed) {
            const normalized = normalizeLlmMarkdownTable(value);
            setLlmResultContent(normalized);
            setLlmRawResultContent(prev => mergeEditedSceneTableIntoRaw(prev || llmRawResultContent || '', normalized));
            return;
        }

        const nextRows = parsed.rows.map(r => [...r]);
        if (!nextRows[rowIdx]) return;
        nextRows[rowIdx][colIdx] = value;
        const nextText = normalizeLlmMarkdownTable(buildMarkdownTable(parsed.headers, nextRows));
        setLlmResultContent(nextText);
        setLlmRawResultContent(prev => mergeEditedSceneTableIntoRaw(prev || llmRawResultContent || '', nextText));
    };

    const handlePersistLlmWorkspace = async () => {
        const normalizedTable = normalizeLlmMarkdownTable(llmResultContent || llmMarkdownTableText || '');
        const mergedRaw = mergeEditedSceneTableIntoRaw(llmRawResultContent || '', normalizedTable);
        setLlmRawResultContent(mergedRaw);
        lastLoadedAnalysisRef.current = mergedRaw;
        await persistLlmResultContent(mergedRaw);
    };

    const handleLlmRawContentChange = (value) => {
        const raw = String(value || '');
        llmRawAutoSaveArmedRef.current = true;
        setLlmRawResultContent(raw);
        setLlmResultContent(normalizeLlmMarkdownTable(raw));
    };

    const handleSaveLlmRawContent = async () => {
        const raw = String(llmRawResultContent || '');
        lastLoadedAnalysisRef.current = raw;
        await persistLlmResultContent(raw);
    };

    useEffect(() => {
        if (!activeEpisode?.id) return;
        if (!llmRawAutoSaveArmedRef.current) return;

        if (llmRawAutoSaveTimerRef.current) {
            clearTimeout(llmRawAutoSaveTimerRef.current);
        }

        llmRawAutoSaveTimerRef.current = setTimeout(async () => {
            const raw = String(llmRawResultContent || '');
            lastLoadedAnalysisRef.current = raw;
            await persistLlmResultContent(raw);
        }, 1200);

        return () => {
            if (llmRawAutoSaveTimerRef.current) {
                clearTimeout(llmRawAutoSaveTimerRef.current);
                llmRawAutoSaveTimerRef.current = null;
            }
        };
    }, [llmRawResultContent, activeEpisode?.id]);

    const handleSegmentChange = (idx, field, value) => {
        const newSegments = [...segments];
        newSegments[idx] = { ...newSegments[idx], [field]: value };
        setSegments(newSegments);
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        if (onLog) onLog("Saving Script...");

        let fullContent = rawContent;

        if (!isRawMode && segments.length > 0) {
            const header = `| Paragraph ID | Title | Content (Revised) | Content (Original) | Narrative Function | Analysis & Adaptation Notes |\n|---|---|---|---|---|---|`;
            const rows = segments.map(seg => {
                const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
                return `| ${seg.id} | ${clean(seg.title)} | ${clean(seg.content)} | ${clean(seg.original)} | ${clean(seg.narrative_role)} | ${clean(seg.analysis)} |`;
            }).join('\n');
            fullContent = header + '\n' + rows;
        }
        
        // console.log("Saving Content:", fullContent.substring(0, 100) + "...");

        try {
            await onUpdateScript(activeEpisode.id, fullContent);
            if (onLog) onLog(`Script saved. Length: ${fullContent.length}`);
            // If we just saved from Raw Mode, keep it in sync but don't force parse unless user wants to
            // Actually the Effect will trigger on activeEpisode update if we parent updates it? 
            // Usually onUpdateScript updates parent state? If so, useEffect runs. 
            // If raw text saved, it will probably stay in Raw Mode (parsing fails).
            alert("Script saved successfully!");
        } catch (e) {
             console.error(e);
             if (onLog) onLog(`Script Save Failed: ${e.message}`);
             alert(`Failed to save script: ${e.message}`);
        }
    };
    
    // Character Canon (Authoritative) generator
    const CANON_TAG_STORAGE_KEY = 'aistory_character_canon_tag_categories_v1';
    const CANON_IDENTITY_STORAGE_KEY = 'aistory_character_canon_identity_categories_v1';
    const DEFAULT_CANON_TAG_CATEGORIES = [
        {
            key: 'beauty',
            title: '颜值/美貌（主角塑造）',
            options: [
                { id: 'beauty_1', label: '绝美', detail: '五官精致、比例高级、镜头感强' },
                { id: 'beauty_2', label: '冷艳', detail: '表情克制、眼神有压迫感、气场强' },
                { id: 'beauty_3', label: '甜美', detail: '笑容干净、亲和力强、少年感/少女感' },
                { id: 'beauty_4', label: '高级感', detail: '皮肤质感干净、妆容克制、整体贵气' },
                { id: 'beauty_5', label: '狐狸系', detail: '眼尾上挑、神情慵懒、带一点挑衅感' },
                { id: 'beauty_m1', label: '硬朗帅', detail: '下颌线清晰、骨相立体、眼神坚决' },
                { id: 'beauty_m2', label: '禁欲系', detail: '克制冷淡、距离感强、越看越上头' },
                { id: 'beauty_m3', label: '痞帅', detail: '微挑眉、嘴角不经意上扬、危险又迷人' },
                { id: 'beauty_m4', label: '温柔系', detail: '眼神温和、说话慢半拍、可靠感强' },
            ],
        },
        {
            key: 'skin_tone',
            title: '肤色/质感（常用标签）',
            options: [
                { id: 'skin_1', label: '冷白皮', detail: '冷调白皙，通透干净' },
                { id: 'skin_2', label: '暖白皮', detail: '暖调白皙，亲和柔和' },
                { id: 'skin_3', label: '健康小麦', detail: '小麦色/日晒感，活力与性感' },
                { id: 'skin_4', label: '古铜', detail: '更深一档的日晒肤色，张力强' },
                { id: 'skin_5', label: '奶油肌', detail: '细腻柔光质感，显贵气' },
                { id: 'skin_6', label: '冷感瓷肌', detail: '干净无瑕，光泽克制' },
            ],
        },
        {
            key: 'eye_color',
            title: '眼睛颜色（常用标签）',
            options: [
                { id: 'eye_1', label: '深棕', detail: '沉稳、温柔、耐看' },
                { id: 'eye_2', label: '浅棕/琥珀', detail: '更亮、更抓镜头' },
                { id: 'eye_3', label: '黑色', detail: '压迫感强、眼神锋利' },
                { id: 'eye_4', label: '灰色', detail: '冷感、高级、距离感' },
                { id: 'eye_5', label: '蓝色', detail: '清冷或少年感，辨识度高' },
                { id: 'eye_6', label: '绿色', detail: '稀有感、神秘感强' },
            ],
        },
        {
            key: 'hair_style',
            title: '发型（常用标签）',
            options: [
                { id: 'hair_1', label: '长直发', detail: '干净利落，发丝有光泽' },
                { id: 'hair_2', label: '长卷发', detail: '松弛性感，层次丰富' },
                { id: 'hair_3', label: '高马尾', detail: '利落、青春、行动感' },
                { id: 'hair_4', label: '低马尾', detail: '克制、优雅、职场感' },
                { id: 'hair_5', label: '丸子头', detail: '露出颈部线条，清爽' },
                { id: 'hair_6', label: '短发波波', detail: '轮廓利落，强调脸部线条' },
                { id: 'hair_7', label: '寸头/短寸', detail: '干净硬朗，突出眉骨与眼神' },
                { id: 'hair_8', label: '背头', detail: '成熟强势，精英气场' },
            ],
        },
        {
            key: 'hair_color',
            title: '发色（常用标签）',
            options: [
                { id: 'hcol_1', label: '自然黑', detail: '干净利落，东方感强' },
                { id: 'hcol_2', label: '深棕', detail: '更柔和、更显质感' },
                { id: 'hcol_3', label: '栗棕', detail: '温柔氛围感，显白' },
                { id: 'hcol_4', label: '巧克力棕', detail: '成熟高级，适配职场' },
                { id: 'hcol_5', label: '亚麻棕', detail: '更轻盈的时髦感（可偏冷/偏暖）' },
                { id: 'hcol_6', label: '金发', detail: '辨识度高，镜头更亮' },
                { id: 'hcol_7', label: '银灰', detail: '冷感高级，未来感/神秘感' },
                { id: 'hcol_8', label: '红棕', detail: '热烈、强存在感' },
            ],
        },
        {
            key: 'sexy',
            title: '性感（不露骨，主角塑造）',
            options: [
                { id: 'sexy_shoulder_1', label: '露肩/一字肩', detail: '突出肩线与颈部线条，镜头更“高级性感”' },
                { id: 'sexy_collar_1', label: '露锁骨', detail: '领口略开，锁骨清晰（尺度克制）' },
                { id: 'sexy_collar_2', label: '开领/解一两颗扣', detail: '衬衫/外套微敞，若隐若现但不露骨' },
                { id: 'sexy_collar_3', label: '露锁骨与胸口（开领/浅V）', detail: '开领或浅V领，视觉聚焦颈胸区域（尺度克制）' },
                { id: 'sexy_arm_1', label: '无袖/吊带（露手臂）', detail: '露出上臂线条，更轻熟、更利落' },
                { id: 'sexy_arm_2', label: '挽袖/卷袖（露前臂）', detail: '随性、克制，有一点禁欲张力' },
                { id: 'sexy_leg_1', label: '短裙/短裤（露腿）', detail: '腿部比例突出（注意尺度克制）' },
                { id: 'sexy_leg_2', label: '开衩裙（露腿）', detail: '走动时若隐若现，更“贵气”的性感' },
            ],
        },
        {
            key: 'gender',
            title: '性别（设定）',
            options: [
                { id: 'gender_f', label: '女', detail: '女性角色（可用于镜头与造型提示）' },
                { id: 'gender_m', label: '男', detail: '男性角色（可用于镜头与造型提示）' },
                { id: 'gender_none', label: '无性别/性别不明', detail: '不以性别定义角色，或刻意模糊' },
            ],
        },
        {
            key: 'body',
            title: '身材/比例（主角塑造）',
            options: [
                { id: 'body_1', label: '好身材', detail: '9头身，修长腿' },
                { id: 'body_2', label: '肩颈线', detail: '锁骨清晰，肩线利落' },
                { id: 'body_3', label: '体态', detail: '站姿挺拔，走路带节奏感' },
                { id: 'body_4', label: '肌肉线条', detail: '紧致不夸张，轮廓清晰' },
                { id: 'body_h1', label: '身高：娇小', detail: '约150–160cm，比例更显可爱/脆弱感' },
                { id: 'body_h2', label: '身高：中等', detail: '约160–170cm，日常感强、适配多数场景' },
                { id: 'body_h3', label: '身高：高挑', detail: '约170–180cm，镜头更有存在感与气场' },
                { id: 'body_h4', label: '身高：很高', detail: '约180cm+，压迫感/保护感更强' },
                { id: 'body_shape_1', label: '纤细/骨感', detail: '骨点清晰、线条冷感，适合疏离气质' },
                { id: 'body_shape_2', label: '匀称/健康', detail: '比例自然、肌肉薄而紧，运动感' },
                { id: 'body_shape_3', label: '微肉/丰润', detail: '柔软曲线、亲和力强（尺度克制）' },
                { id: 'body_shape_4', label: '健身型', detail: '肩背与核心发达，动作干净有力量' },
                { id: 'body_shape_5', label: '厚实/壮硕', detail: '骨架大、存在感强，近景更有压迫' },
                { id: 'body_prop_1', label: '腿长', detail: '视觉比例拉长，走路带风' },
                { id: 'body_prop_2', label: '腰线高', detail: '上短下长，镜头更显修长' },
                { id: 'body_prop_3', label: '腰臀比突出', detail: '曲线更明显（不露骨）' },
                { id: 'body_m1', label: '宽肩窄腰', detail: '倒三角轮廓明显，西装很好看' },
                { id: 'body_m2', label: '力量感', detail: '动作不多但很稳，抬手就有压迫感' },
            ],
        },
        {
            key: 'age',
            title: '年龄/阶段（设定）',
            options: [
                { id: 'age_1', label: '少年/少女（16–19）', detail: '青春感强，情绪外露，成长线明显' },
                { id: 'age_2', label: '青年（20–25）', detail: '锐气与试错期，冲劲足' },
                { id: 'age_3', label: '轻熟（26–32）', detail: '自洽、边界感更强，魅力更稳定' },
                { id: 'age_4', label: '成熟（33–40）', detail: '经验与压迫感/掌控感更强' },
                { id: 'age_5', label: '中年（41–55）', detail: '沉稳、城府/担当更明显' },
                { id: 'age_6', label: '长者（56+）', detail: '威望、阅历，气场不靠外放' },
                { id: 'age_7', label: '年龄不详/看不出', detail: '刻意模糊年龄，神秘感与距离感更强' },
            ],
        },
        {
            key: 'wardrobe',
            title: '穿搭/造型（主角塑造）',
            options: [
                { id: 'wardrobe_1', label: '干练', detail: '收腰西装或衬衫+长裤，剪裁利落' },
                { id: 'wardrobe_2', label: '优雅', detail: '简洁连衣裙或套装，配饰克制' },
                { id: 'wardrobe_3', label: '都市时髦', detail: '大衣/风衣+高跟或短靴，层次感' },
                { id: 'wardrobe_4', label: '禁欲风', detail: '高领/长袖/长裤，颜色克制但极有气场' },
                { id: 'wardrobe_5', label: '轻奢', detail: '面料有质感，细节讲究，不浮夸' },
                { id: 'wardrobe_m1', label: '绅士', detail: '合身西装/大衣，领带或领结点到为止' },
                { id: 'wardrobe_m2', label: '冷酷街头', detail: '黑色夹克/皮衣+短靴，线条硬' },
                { id: 'wardrobe_m3', label: '少年感男主', detail: '白衬衫/针织衫/运动外套，干净清爽' },
            ],
        },
        {
            key: 'clothing_items',
            title: '衣着/单品（常用标签）',
            options: [
                { id: 'cloth_1', label: '白衬衫', detail: '干净克制，越简单越高级' },
                { id: 'cloth_2', label: '黑高领', detail: '禁欲、冷感、气场强' },
                { id: 'cloth_3', label: '西装', detail: '合身剪裁，肩线清晰' },
                { id: 'cloth_4', label: '大衣/风衣', detail: '压气场，走路带风' },
                { id: 'cloth_5', label: '丝质/缎面', detail: '微光泽，性感但不露骨' },
                { id: 'cloth_6', label: '皮衣/夹克', detail: '硬朗、叛逆、酷感' },
                { id: 'cloth_7', label: '短裙/开衩', detail: '腿部线条更突出（注意尺度克制）' },
                { id: 'cloth_8', label: '高跟鞋', detail: '气场与身材比例拉长' },
                { id: 'cloth_9', label: '短靴', detail: '利落、都市、行动感' },
                { id: 'cloth_10', label: '配饰克制', detail: '少而精，提升高级感' },
            ],
        },
        {
            key: 'combat_wear',
            title: '战斗服装/战甲（服饰）',
            options: [
                { id: 'cwear_1', label: '战甲/盔甲', detail: '金属/皮革甲胄，防护与威慑感' },
                { id: 'cwear_2', label: '轻甲', detail: '更灵活，线条更贴身、利落' },
                { id: 'cwear_3', label: '战术背心/防弹衣', detail: '现代作战感，功能性口袋与模块' },
                { id: 'cwear_4', label: '制服/作战服', detail: '军警/特勤气质，纪律与专业' },
                { id: 'cwear_5', label: '披风/斗篷', detail: '英雄感/隐匿感，镜头层次更强' },
                { id: 'cwear_6', label: '护臂/护腕', detail: '近战细节，硬朗质感' },
                { id: 'cwear_7', label: '护膝/护腿', detail: '实战磨损感更真实' },
                { id: 'cwear_8', label: '作战靴', detail: '落地更稳，压迫感与行动感兼具' },
                { id: 'cwear_9', label: '战术腰带/枪套', detail: '装备挂载，专业度更高' },
            ],
        },
        {
            key: 'ancient_wear',
            title: '古装服装/服饰',
            options: [
                { id: 'awear_1', label: '汉服（襦裙/交领）', detail: '飘逸层次，古风气质' },
                { id: 'awear_2', label: '长袍/直裾', detail: '文人/谋士感，克制内敛' },
                { id: 'awear_3', label: '官服/朝服', detail: '礼制等级与权力感更明确' },
                { id: 'awear_4', label: '锦衣/华服', detail: '贵气、纹样精致、用料讲究' },
                { id: 'awear_5', label: '夜行衣', detail: '暗色贴身，隐秘与危险感（不强调动作）' },
                { id: 'awear_6', label: '甲胄（古代战甲）', detail: '甲片/扎甲，历史质感强' },
                { id: 'awear_7', label: '披风/披肩', detail: '身份感与镜头层次' },
                { id: 'awear_8', label: '发冠/发簪', detail: '阶层与礼制体现' },
                { id: 'awear_9', label: '腰带/玉佩', detail: '点明身份与品味' },
                { id: 'awear_10', label: '绣鞋/靴', detail: '细节完成度更高，时代感更真' },
            ],
        },
        {
            key: 'hair_makeup',
            title: '妆发/细节（主角塑造）',
            options: [
                { id: 'hm_1', label: '红唇', detail: '饱和但干净的红，气场拉满' },
                { id: 'hm_2', label: '淡妆', detail: '伪素颜，重点是皮肤干净与眼神' },
                { id: 'hm_3', label: '眼妆', detail: '眼尾微上扬，强调眼神锋利/勾人' },
                { id: 'hm_4', label: '长发', detail: '发丝有光泽，发型不凌乱' },
                { id: 'hm_5', label: '短发', detail: '轮廓利落，露出颈部线条' },
                { id: 'hm_m1', label: '寸头/短寸', detail: '干净利落，突出眉骨与眼神' },
                { id: 'hm_m2', label: '胡渣', detail: '微微胡渣，成熟感与危险感' },
            ],
        },
        {
            key: 'vibe',
            title: '气质/表现（主角塑造）',
            options: [
                { id: 'vibe_1', label: '神秘', detail: '信息不一次说完，表情留白' },
                { id: 'vibe_2', label: '冷峻', detail: '少笑，语气短，目光锐利' },
                { id: 'vibe_3', label: '阳光', detail: '笑意自然，语气轻快，亲和力强' },
                { id: 'vibe_4', label: '专业感', detail: '用词准确，动作克制，目标导向' },
                { id: 'vibe_5', label: '强势', detail: '话语有控制力，场面压得住' },
                { id: 'vibe_6', label: '脆弱感', detail: '瞬间的停顿/回避眼神，让人心软' },
            ],
        },
        {
            key: 'nation',
            title: '国籍/地区（设定）',
            options: [
                { id: 'nation_1', label: '中国', detail: '可细分：北方/南方口音与习惯' },
                { id: 'nation_2', label: '日本', detail: '克制礼貌、边界感明显' },
                { id: 'nation_3', label: '韩国', detail: '时尚敏感、表达更直接' },
                { id: 'nation_4', label: '美国', detail: '表达直接、个人主义、行动优先' },
                { id: 'nation_5', label: '英国', detail: '措辞克制、礼貌疏离、幽默冷' },
                { id: 'nation_6', label: '法国', detail: '松弛浪漫、审美挑剔、有锋芒' },
                { id: 'nation_7', label: '意大利', detail: '热情外放、注重衣着与手势' },
            ],
        },
        {
            key: 'ethnicity',
            title: '人种/族裔（设定）',
            options: [
                { id: 'eth_1', label: '东亚', detail: '例如：中/日/韩常见审美与轮廓特点' },
                { id: 'eth_2', label: '白人/欧洲裔', detail: '骨相立体、肤色与发色范围更广' },
                { id: 'eth_3', label: '黑人/非洲裔', detail: '五官张力强、体态与气场更突出' },
                { id: 'eth_4', label: '拉丁裔', detail: '热烈、自信、风格表达更强' },
                { id: 'eth_5', label: '南亚裔', detail: '深邃眼神、配饰审美更鲜明' },
                { id: 'eth_6', label: '中东/阿拉伯裔', detail: '浓眉深眼、轮廓强、气场浓烈' },
                { id: 'eth_7', label: '混血', detail: '特征融合，辨识度高' },
            ],
        },
    ];

    const DEFAULT_CANON_IDENTITY_CATEGORIES = [
        {
            key: 'lead_role',
            title: '主角定位/戏份',
            options: [
                { id: 'lead_f', label: '女主角', detail: '故事核心视角/情感主线' },
                { id: 'lead_m', label: '男主角', detail: '故事核心视角/推动行动线' },
                { id: 'lead_2', label: '第二主角', detail: '重要支线/关键转折' },
                { id: 'antagonist', label: '反派/对立面', detail: '推进冲突与悬念' },
            ],
        },
        {
            key: 'occupation',
            title: '职业/身份',
            options: [
                { id: 'occ_ceo', label: 'CEO/总裁', detail: '强掌控、决策快、社交资源丰富' },
                { id: 'occ_police', label: '刑警/警探', detail: '行动派、观察力强、压力承受高' },
                { id: 'occ_lawyer', label: '律师', detail: '逻辑强、措辞锋利、擅长博弈' },
                { id: 'occ_doctor', label: '医生', detail: '专业冷静、情绪克制、同理心' },
                { id: 'occ_artist', label: '艺术家', detail: '审美敏感、情绪浓、反差感' },
                { id: 'occ_student', label: '大学生', detail: '成长线明显、少年感/少女感' },
                { id: 'occ_model', label: '模特/艺人', detail: '镜头感强、曝光与舆论压力' },
            ],
        },
        {
            key: 'combat_identity',
            title: '战斗身份/背景',
            options: [
                { id: 'cid_1', label: '军人/士兵', detail: '训练有素，服从命令，纪律感强' },
                { id: 'cid_2', label: '特勤/特种', detail: '高压任务，处事克制专业' },
                { id: 'cid_3', label: '雇佣兵', detail: '利益驱动，实战经验丰富' },
                { id: 'cid_4', label: '杀手/刺客', detail: '隐秘、冷静、边界感强' },
                { id: 'cid_5', label: '保镖/护卫', detail: '保护优先，风险评估与站位意识强' },
                { id: 'cid_6', label: '武术家', detail: '以技服人，克制与底线清晰' },
                { id: 'cid_7', label: '赏金猎人', detail: '规则感强，灰色地带的执行者' },
                { id: 'cid_8', label: '黑帮打手', detail: '狠劲、街头经验与威慑' },
            ],
        },
        {
            key: 'ancient_identity',
            title: '古装身份/阵营',
            options: [
                { id: 'aid_1', label: '将军/统帅', detail: '威望与军纪，杀伐果断' },
                { id: 'aid_2', label: '侍卫/禁军', detail: '守护要员/皇权，纪律严' },
                { id: 'aid_3', label: '捕快/衙役', detail: '基层执法，江湖味更浓' },
                { id: 'aid_4', label: '县令/官员', detail: '规则执行者，权力与人情博弈' },
                { id: 'aid_5', label: '世家公子/小姐', detail: '礼制与家族利益牵引，克制体面' },
                { id: 'aid_6', label: '王爷/皇子', detail: '权力中心，处处试探与算计' },
                { id: 'aid_7', label: '宫女/太监', detail: '宫廷生态，信息与生存技巧' },
                { id: 'aid_8', label: '门派弟子/修行者', detail: '师门规矩、江湖恩怨、阵营牵连' },
                { id: 'aid_9', label: '侠客/游侠', detail: '行走江湖，讲义气也有底线' },
            ],
        },
        {
            key: 'status',
            title: '社会身份/阶层',
            options: [
                { id: 'st_elite', label: '上层精英', detail: '资源多、社交圈高、习惯克制' },
                { id: 'st_middle', label: '中产专业人士', detail: '稳健务实、重效率与边界' },
                { id: 'st_grass', label: '草根逆袭', detail: '韧性强、行动强、野心明确' },
                { id: 'st_mysterious', label: '身份成谜', detail: '信息分层揭示，悬念强' },
            ],
        },
        {
            key: 'personality_arc',
            title: '主角弧光/关键词',
            options: [
                { id: 'arc_redemption', label: '救赎', detail: '背负过去，逐步修复与和解' },
                { id: 'arc_growth', label: '成长', detail: '从稚嫩到成熟的可见变化' },
                { id: 'arc_revenge', label: '复仇', detail: '目标明确，情绪压抑与爆发' },
                { id: 'arc_power', label: '权力', detail: '争夺与控制、规则博弈' },
            ],
        },
    ];
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
    const [canonGenerating, setCanonGenerating] = useState(false);
    const [showCanonModal, setShowCanonModal] = useState(false);

    // Script Generator (Scenes)
    const [showSceneGenPanel, setShowSceneGenPanel] = useState(false);
    const [sceneGenCount, setSceneGenCount] = useState(10);
    const [sceneGenNotes, setSceneGenNotes] = useState('');
    const [sceneGenReplaceExisting, setSceneGenReplaceExisting] = useState(true);
    const [sceneGenGenerating, setSceneGenGenerating] = useState(false);
    const [sceneGenStatus, setSceneGenStatus] = useState(null);
    const [isStoppingSceneGen, setIsStoppingSceneGen] = useState(false);
    const sceneGenStartInFlightRef = useRef(false);
    const episodeCanonGenerationInFlightRef = useRef(false);
    const sceneGenStatusTimerRef = useRef(null);

    const canonOptionValue = (opt) => `${opt.label}：${opt.detail}`;

    const normalizeCanonTagCategories = (raw) => {
        if (!Array.isArray(raw)) return null;
        const normalized = raw
            .filter(Boolean)
            .map((cat) => {
                const key = String(cat?.key || '').trim();
                const title = String(cat?.title || '').trim();
                const options = Array.isArray(cat?.options) ? cat.options : [];
                if (!key || !title) return null;
                const normalizedOptions = options
                    .filter(Boolean)
                    .map((opt) => {
                        const id = String(opt?.id || '').trim();
                        const label = String(opt?.label || '').trim();
                        const detail = String(opt?.detail || '').trim();
                        if (!id || !label || !detail) return null;
                        return { id, label, detail };
                    })
                    .filter(Boolean);
                return { key, title, options: normalizedOptions };
            })
            .filter(Boolean);
        return normalized.length > 0 ? normalized : null;
    };

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

    useEffect(() => {
        try {
            const saved = localStorage.getItem(CANON_TAG_STORAGE_KEY);
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

            if (saved) {
                const parsed = JSON.parse(saved);
                const normalized = normalizeCanonTagCategories(parsed);
                if (normalized) {
                    setCanonTagCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_TAG_CATEGORIES));
                    return;
                }
            }
            // No saved or invalid saved -> ensure defaults are used
            setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
        } catch (e) {
            // ignore
            setCanonTagCategories(DEFAULT_CANON_TAG_CATEGORIES);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        try {
            const saved = localStorage.getItem(CANON_IDENTITY_STORAGE_KEY);
            if (!saved) {
                setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
                return;
            }

            const parsed = JSON.parse(saved);
            const normalized = normalizeCanonTagCategories(parsed);

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

            if (normalized) {
                setCanonIdentityCategories(mergeCategoriesByKey(normalized, DEFAULT_CANON_IDENTITY_CATEGORIES));
            } else {
                setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
            }
        } catch (e) {
            // ignore
            setCanonIdentityCategories(DEFAULT_CANON_IDENTITY_CATEGORIES);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
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

    const toggleCanonTagId = (id) => {
        setCanonSelectedTagIds(prev => (
            prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
        ));
    };

    const toggleCanonIdentityId = (id) => {
        setCanonSelectedIdentityIds(prev => (
            prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
        ));
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
        const id = newCanonOptionId(catKey);
        setCanonTagCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id, label: '新标签', detail: '细节描述' }] };
        }));
    };
    const removeCanonOption = (catKey, optId) => {
        setCanonSelectedTagIds(prev => prev.filter(id => id !== optId));
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
        const id = newCanonOptionId(catKey);
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: [...(c.options || []), { id, label: '新身份', detail: '细节描述' }] };
        }));
    };
    const removeIdentityOption = (catKey, optId) => {
        setCanonSelectedIdentityIds(prev => prev.filter(id => id !== optId));
        setCanonIdentityCategories(prev => (prev || []).map(c => {
            if (c.key !== catKey) return c;
            return { ...c, options: (c.options || []).filter(o => o.id !== optId) };
        }));
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

    const closeCanonModal = () => {
        // Best-effort autosave if user was editing tags
        if (canonTagEditMode) {
            const ok = persistCanonTagCategories(canonTagCategories);
            if (ok && onLog) onLog('已保存标签配置（JSON）', 'success');
            const ok2 = persistCanonIdentityCategories(canonIdentityCategories);
            if (ok2 && onLog) onLog('已保存身份标签配置（JSON）', 'success');
        }
        setCanonTagEditMode(false);
        setShowCanonModal(false);
    };

    const pollSceneGenStatus = useCallback(async () => {
        if (!activeEpisode?.id) return null;
        try {
            const status = await getEpisodeScenesGenerationStatus(activeEpisode.id);
            if (status && typeof status === 'object') {
                setSceneGenStatus(status);
                setSceneGenGenerating(Boolean(status.running));
                if (!status.running && sceneGenStatusTimerRef.current) {
                    clearInterval(sceneGenStatusTimerRef.current);
                    sceneGenStatusTimerRef.current = null;
                }
                return status;
            }
        } catch (e) {}
        return null;
    }, [activeEpisode?.id]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        let cancelled = false;

        const probeShotVideoUrl = async (shotId) => {
            try {
                const rows = await fetchEpisodeShots(activeEpisode.id, { compact: true });
                const matched = Array.isArray(rows)
                    ? rows.find((row) => String(row?.id) === String(shotId))
                    : null;
                return String(matched?.video_url || '').trim();
            } catch {
                return '';
            }
        };

        const hydrate = async () => {
            const status = await pollSceneGenStatus();
            if (cancelled || !status) return;
            if (status.running && !sceneGenStatusTimerRef.current) {
                sceneGenStatusTimerRef.current = setInterval(pollSceneGenStatus, 3000);
            }
        };

        hydrate();
        return () => {
            cancelled = true;
            if (sceneGenStatusTimerRef.current) {
                clearInterval(sceneGenStatusTimerRef.current);
                sceneGenStatusTimerRef.current = null;
            }
        };
    }, [activeEpisode?.id, pollSceneGenStatus]);

    const handleStopGenerateScenes = async () => {
        if (!activeEpisode?.id) return;
        setIsStoppingSceneGen(true);
        try {
            const res = await stopEpisodeScenesGeneration(activeEpisode.id);
            setSceneGenStatus((prev) => ({
                ...(prev && typeof prev === 'object' ? prev : {}),
                stop_requested: true,
                message: res?.message || prev?.message || t('已强制停止当前场景批处理。', 'Current scene batch force-stopped.'),
            }));
            await pollSceneGenStatus();
            if (onLog) onLog(`Scene generation: ${res?.message || 'stop requested'}`, 'warning');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || String(e);
            if (onLog) onLog(`Scene generation stop failed: ${detail}`, 'error');
            alert(`Stop failed: ${detail}`);
        } finally {
            setIsStoppingSceneGen(false);
        }
    };

    const handleGenerateScenes = async () => {
        if (!activeEpisode?.id) return;
        if (sceneGenStartInFlightRef.current || sceneGenGenerating || isStoppingSceneGen) return;
        sceneGenStartInFlightRef.current = true;
        const n = Number(sceneGenCount);
        if (Number.isNaN(n) || n <= 0) {
            alert('Please enter a valid scene count.');
            sceneGenStartInFlightRef.current = false;
            return;
        }

        const latest = await pollSceneGenStatus();
        if (latest?.running) {
            if (onLog) onLog('Scene generation is already running. Please stop current task first.', 'warning');
            alert('Scene generation is already running. Please stop current task first.');
            sceneGenStartInFlightRef.current = false;
            return;
        }

        setSceneGenGenerating(true);
        try {
            if (onLog) onLog(`Starting background scene generation (target: ${n})`, 'process');
            await startEpisodeScenesGeneration(activeEpisode.id, {
                scene_count: n,
                extra_notes: sceneGenNotes,
                replace_existing_scenes: !!sceneGenReplaceExisting,
            });
            if (sceneGenStatusTimerRef.current) {
                clearInterval(sceneGenStatusTimerRef.current);
                sceneGenStatusTimerRef.current = null;
            }
            sceneGenStatusTimerRef.current = setInterval(pollSceneGenStatus, 3000);
            await pollSceneGenStatus();
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Scene generation failed: ${e.message}`, 'error');
            alert(`Generation failed: ${e.message}`);
            setSceneGenGenerating(false);
        } finally {
            sceneGenStartInFlightRef.current = false;
        }
    };

    const handleGenerateCanon = async () => {
        if (!activeEpisode?.id) return;
        if (episodeCanonGenerationInFlightRef.current || canonGenerating) return;
        episodeCanonGenerationInFlightRef.current = true;
        const name = (canonName || '').trim();
        if (!name) {
            alert('请输入角色名称');
            episodeCanonGenerationInFlightRef.current = false;
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

        setCanonGenerating(true);
        try {
            if (onLog) onLog(`Generating Character Canon for: ${name}`, 'process');
            const updatedEpisode = await generateEpisodeCharacterProfile(activeEpisode.id, {
                name,
                identity,
                body_features: canonBody,
                style_tags,
                extra_notes: canonExtra,
            });

            if (updatedEpisode?.script_content != null) {
                setRawContent(updatedEpisode.script_content);
            }
            if (onLog) onLog(`Character Canon saved & inserted into script: ${name}`, 'success');
            setShowCanonModal(false);
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Character Canon generation failed: ${e.message}`, 'error');
            alert(`生成失败: ${e.message}`);
        } finally {
            setCanonGenerating(false);
            episodeCanonGenerationInFlightRef.current = false;
        }
    };

    // Check user role on mount
    useEffect(() => {
        fetchMe().then(user => {
            if (user && user.is_superuser) {
                setIsSuperuser(true);
            }
        }).catch(() => {});
    }, []);

    const handleAnalysisClick = async () => {
        if (!rawContent || rawContent.trim().length < 10) {
            alert("Script content is too short for analysis.");
            return;
        }
        if (isAnalyzing || analysisRunInFlightRef?.current || analysisResumeInFlightRef?.current) {
            onLog?.("Already analyzing, duplicate click prevented.");
            return;
        }

        const projectInfo = (project?.global_info && typeof project.global_info === 'object')
            ? project.global_info
            : {};
        const normalizeInfoKey = (key) => String(key || '').toLowerCase().replace(/[\s\-]/g, '_').trim();
        const getInfoValue = (aliases = []) => {
            const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
            for (const [k, v] of Object.entries(projectInfo)) {
                if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                const text = String(v || '').trim();
                if (text) return text;
            }
            return '';
        };
        const projectLanguage = getInfoValue(['language', 'project_language', 'lang']);
        
        setIsAnalyzing(true); // Disable button immediately
        
        if (!projectLanguage) {
            const ok = await confirmUiMessage(t(
                '检测到项目语言为空。建议先在“项目信息”里填写语言，以保证分析输出语言稳定。是否继续分析？',
                'Project language is empty. Set language in Project Info first for stable analysis output. Continue anyway?'
            ));
            if (!ok) {
                setIsAnalyzing(false);
                return;
            }
            if (onLog) onLog('Project language is empty. Analysis continues with warning.', 'warning');
        }

        setAnalysisUiReport(null);
        setAnalysisFlowStatus({ phase: 'idle', message: '' });

        if (isSuperuser) {
            // Fetch default prompt
            try {
                const res = await fetchPrompt("skills/scene_analysis_feature_stack/scene_planning.md");
                setSystemPrompt(res.content);
                
                // Construct full user prompt with metadata visible
                let fullContent = rawContent;
                if (project?.global_info) {
                            const info = projectInfo;
                            const visual = (info?.tech_params && typeof info.tech_params === 'object' && info.tech_params.visual_standard && typeof info.tech_params.visual_standard === 'object')
                                ? info.tech_params.visual_standard
                                : {};
                            const getInfoArray = (aliases = []) => {
                                const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
                                for (const [k, v] of Object.entries(info || {})) {
                                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                                    if (Array.isArray(v)) {
                                        const arr = v.map(item => String(item || '').trim()).filter(Boolean);
                                        if (arr.length) return arr;
                                    }
                                    if (typeof v === 'string') {
                                        const arr = v.split(/[\n,，;；]/).map(item => item.trim()).filter(Boolean);
                                        if (arr.length) return arr;
                                    }
                                }
                                return [];
                            };
                            const getVisualValue = (aliases = []) => {
                                const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
                                for (const [k, v] of Object.entries(visual || {})) {
                                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                                    const text = String(v || '').trim();
                                    if (text) return text;
                                }
                                for (const [k, v] of Object.entries(info || {})) {
                                    if (!normalizedAlias.has(normalizeInfoKey(k))) continue;
                                    const text = String(v || '').trim();
                                    if (text) return text;
                                }
                                return '';
                            };
                            const borrowedFilms = getInfoArray(['borrowed_films', 'borrowedFilms', 'reference_films', 'referenceFilms']);
                            const language = getInfoValue(['language', 'project_language', 'lang']);

                            const metaParts = [
                                'Project Context (prepend and treat as high-priority constraints):',
                                '[Basic Info]',
                            ];
                            const title = getInfoValue(['script_title', 'title']);
                            const episode = getInfoValue(['series_episode', 'episode']);
                            const type = getInfoValue(['type']);
                            const basePositioning = getInfoValue(['base_positioning']);
                            if (title) metaParts.push(`Title: ${title}`);
                            if (episode) metaParts.push(`Episode: ${episode}`);
                            if (type) metaParts.push(`Type: ${type}`);
                            if (basePositioning) metaParts.push(`Base Positioning: ${basePositioning}`);
                            if (language) {
                                metaParts.push(`Language: ${language}`);
                            } else {
                                metaParts.push(`Language: (empty)`);
                                metaParts.push(`Language Warning: project language is empty. You MUST infer one target natural language from script context and keep all natural-language descriptions consistently in that single language.`);
                            }
                            metaParts.push('[Technical & Visual Parameters]');
                            const aspectRatio = getVisualValue(['aspect_ratio']);
                            const imageSize = getVisualValue(['image_size']);
                            const horizontalResolution = getVisualValue(['horizontal_resolution']);
                            const verticalResolution = getVisualValue(['vertical_resolution']);
                            const frameRate = getVisualValue(['frame_rate']);
                            const quality = getVisualValue(['quality']);
                            const globalStyle = getInfoValue(['Global_Style', 'global_style', 'style']);
                            const tone = getInfoValue(['tone', 'mood']);
                            const lighting = getInfoValue(['lighting', 'light']);
                            if (aspectRatio) metaParts.push(`Aspect Ratio: ${aspectRatio}`);
                            if (imageSize) metaParts.push(`Image Size: ${imageSize}`);
                            if (horizontalResolution) metaParts.push(`Horizontal Resolution: ${horizontalResolution}`);
                            if (verticalResolution) metaParts.push(`Vertical Resolution: ${verticalResolution}`);
                            if (frameRate) metaParts.push(`Frame Rate: ${frameRate}`);
                            if (quality) metaParts.push(`Quality: ${quality}`);
                            if (globalStyle) metaParts.push(`Global Style: ${globalStyle}`);
                            if (borrowedFilms.length > 0) metaParts.push(`Borrowed Films: ${borrowedFilms.join(', ')}`);
                            if (tone) metaParts.push(`Tone: ${tone}`);
                            if (lighting) metaParts.push(`Lighting: ${lighting}`);

                            const eraField = getInfoValue(['era', 'era_setting', 'period', 'time_setting']);
                            const regionField = getInfoValue(['region_culture', 'region', 'country', 'country_region']);
                            const shotPrefField = getInfoValue(['shot_preference', 'lens_preference', 'camera_preference']);
                            const broadcastSafetyField = getInfoValue(['broadcast_security_level', 'broadcast_safety_level', 'safety_level', 'broadcast_safety']);
                            if (eraField) metaParts.push(`Era / Period: ${eraField}`);
                            if (regionField) metaParts.push(`Region / Country: ${regionField}`);
                            if (shotPrefField) metaParts.push(`Shot / Lens Preference: ${shotPrefField}`);
                            if (broadcastSafetyField) metaParts.push(`Broadcast Security Level: ${broadcastSafetyField}`);
                            metaParts.push(`Use this project context as first-class constraints before analyzing the script.`);

                     if (metaParts.length > 1) {
                        fullContent = `${metaParts.join('\n')}\n\nScript to Analyze:\n\n${rawContent}`;
                     }
                }

                try {
                    const projectIdForInventory = project?.id;
                    if (projectIdForInventory) {
                        const inventoryObj = await fetchProjectSubjectInventoryPrompt(projectIdForInventory);
                        if (inventoryObj && inventoryObj.inventory_block) {
                            let inventoryStr = `\n\n${inventoryObj.inventory_block.trim()}\n\n${(inventoryObj.inventory_guidance || '').trim()}\n\n`;
                            fullContent = `[Project Existing Subject Index]${inventoryStr}${fullContent}`;
                        }
                    }
                } catch(e) {
                    console.error("Failed to fetch inventory", e);
                }

                setUserPrompt(fullContent);
                setShowAnalysisModal(true);
                setIsAnalyzing(false); // Enable back since we are just showing the modal
            } catch (e) {
                console.error("Failed to fetch system prompt", e);
                // Fallback if fails
                setSystemPrompt("Error loading system prompt.");
                setUserPrompt(rawContent);
                setShowAnalysisModal(true);
                setIsAnalyzing(false);
            }
        } else {
             // Normal user flow
             // executeAnalysis will set it back to true, but we can leave it true since it will continue turning
            executeAnalysis(rawContent);
        }
    };

    const autoSaveScriptBeforeAnalysis = async () => {
        if (!activeEpisode?.id || typeof onUpdateScript !== 'function') return;
        const latestScript = String(rawContent || '');
        const savedScript = String(activeEpisode?.script_content || '');
        if (latestScript === savedScript) return;

        try {
            if (onLog) onLog('Auto-saving script before AI Script Analysis...', 'process');
            await onUpdateScript(activeEpisode.id, latestScript);
            if (onLog) onLog('Script auto-saved before analysis.', 'success');
        } catch (saveError) {
            console.warn('[ScriptEditor] Auto-save before analysis failed:', saveError);
            if (onLog) onLog(`Script auto-save failed (analysis continues): ${saveError.message}`, 'warning');
        }
    };

    const executeAnalysis = async (content, customSystemPrompt = null, skipMetadata = false, retryCount = 0) => {
        // Bypass Phase 1 if subject index is already present!
        if (activeEpisode.ai_scene_analysis_subject_index && activeEpisode.ai_scene_analysis_subject_index.trim()) {
            const bypassConfirmed = true;
            if (bypassConfirmed) {
                // Phase 2 Check: if it already exists, do not initiate again
                if (activeEpisode.ai_entity_design_result && activeEpisode.ai_entity_design_result.trim()) {
                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: "🎉 专属实体资产定制均已存在，无需重复生成！"
                    });
                    if (onLog) onLog("AI Analysis bypassed entirely; both phases are already completed.");
                    return;
                }
                // Phase 2 Check: if it already exists, do not initiate again
                if (activeEpisode.ai_entity_design_result && activeEpisode.ai_entity_design_result.trim()) {
                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: "🎉 专属实体资产定制均已存在，无需重复生成！"
                    });
                    if (onLog) onLog("AI Analysis bypassed entirely; both phases are already completed.");
                    return;
                }
                const startedAt = Date.now();
                setAnalysisUiReport({
                    status: 'running',
                    startedAt,
                    durationMs: 0,
                    phaseTimings: null,
                    importReport: null,
                    runtimeMeta: null,
                    warning: '',
                    error: '',
                });

                setAnalysisFlowStatus({
                    phase: 'processing_output_workspace',
                    message: "🚀 跳过 Phase 1，直接进入资产设计...",
                });

                try {
                    // We just jump straight to Phase 2 logic (runPostImportSceneSubjectPipeline).
                    // We mock an empty import report to keep the pipeline happy.
                    const mockImportReport = { importedSceneRows: [] };
                    const dummyAnalyzedText = activeEpisode.ai_scene_analysis_result || activeEpisode.ai_scene_analysis_subject_index; // Pass something fallback

                    const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(mockImportReport, activeEpisode.ai_scene_analysis_subject_index);

                    const finalImportReport = {
                        ...mockImportReport,
                        sceneSubjectPostImportReport: postImportSceneSubjectReport,
                        dbRunInsertedCounts: postImportSceneSubjectReport?.dbRunInsertedCounts,
                        dbPersistedCounts: postImportSceneSubjectReport?.dbPersistedCounts,
                        importedSubjectCounts: postImportSceneSubjectReport?.importedSubjectCounts,
                    };

                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: "🎉 专属实体资产定制完毕，可随时投产使用！",
                    });

                    setAnalysisUiReport({
                        status: 'completed',
                        startedAt,
                        durationMs: Date.now() - startedAt,
                        phaseTimings: null,
                        importReport: finalImportReport,
                        runtimeMeta: null,
                        warning: '',
                        error: '',
                    });
                } catch (err) {
                    console.error(err);
                    setAnalysisFlowStatus({ phase: 'failed', message: "❌ 资产生成失败: " + err.message });
                    setAnalysisUiReport({
                        status: 'failed',
                        startedAt,
                        durationMs: Date.now() - startedAt,
                        phaseTimings: null,
                        importReport: null,
                        runtimeMeta: null,
                        warning: '',
                        error: err.message,
                    });
                }
                return; // Early return to completely bypass standard analysis flow
            }
        }
        if (analysisRunInFlightRef.current || analysisResumeInFlightRef.current) {
            if (onLog) onLog('Skipped duplicate AI Script Analysis submit while another analysis run is already active.', 'warning');
            return;
        }
        analysisRunInFlightRef.current = true;
        clearAnalysisTaskMarker(activeEpisode?.id);
        const startedAt = Date.now();
        analysisStopRequestedRef.current = false;
        setIsAnalyzing(true);
        setActiveAnalysisTaskId('');
        setAnalysisFlowStatus({
            phase: 'autosaving',
            message: t('💾 正在自动保存您的剧本，保障数据安全...', 'Auto-saving script...'),
        });
        setAnalysisUiReport({
            status: 'running',
            startedAt,
            durationMs: 0,
            phaseTimings: null,
            importReport: null,
            runtimeMeta: null,
            warning: '',
            error: '',
        });
        if (onLog) onLog("Starting AI Script Analysis...", "start");

        let llmReturned = false;
        let runtimeMeta = null;
        let importReport = null;
        let postImportSceneSubjectReport = null;
        let importWarningMessage = '';
        const phaseMarks = {
            submitStartedAt: startedAt,
            analyzeStartedAt: 0,
            llmReturnedAt: 0,
            importStartedAt: 0,
            importFinishedAt: 0,
            persistStartedAt: 0,
            persistFinishedAt: 0,
            completedAt: 0,
        };

        try {
            await autoSaveScriptBeforeAnalysis();

            // Include project metadata if available, unless skipped (baked in)
            const metadata = skipMetadata ? null : (project?.global_info || null);

            setAnalysisFlowStatus({
                phase: 'analyzing',
                message: t('🧠 正在通读剧本并设计场景啦。根据字数和剧情可能要 3~4 分钟，先喝杯水休息下吧~', 'LLM submitted. Waiting for response. Submit timeout is about 300s and total wait can take up to about 600s.'),
            });
            phaseMarks.analyzeStartedAt = Date.now();
            
            const baselineAnalysisText = String(activeEpisode?.ai_scene_analysis_result || '').trim();
            const result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    content,
                    customSystemPrompt,
                    metadata,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            setActiveAnalysisTaskId(String(taskId || '').trim());
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 1 });
                        },
                    },
                    projectId
                ),
                { startedAt, baselineText: baselineAnalysisText }
            );
            const analyzedText = extractAnalysisTextFromResult(result);
            if (analyzedText && analyzedText.includes("PROHIBITED_CONTENT")) {
                throw new Error("出现供应商政策不允许内容");
            }
            llmReturned = true;
            phaseMarks.llmReturnedAt = Date.now();
            setAnalysisFlowStatus({
                phase: 'processing_output_workspace',
                message: t('🚀 分析有了新进展，正在为您整理出炉...', 'LLM returned: saving raw output and filling the analysis Output Workspace...'),
            });
            setAnalysisFlowStatus({
                phase: 'processing_output_workspace',
                message: t('🚀 分析有了新进展，正在为您整理出炉...', 'LLM returned: saving raw output and filling the analysis Output Workspace...'),
            });

            if (result && result.meta) {
                try {
                    const m = result.meta;
                    const usage = m.usage || {};
                    if (onLog) onLog(
                        `AI Analysis meta: sys_chars=${m.system_prompt_chars} user_chars=${m.user_prompt_chars} ` +
                        `est_in=${m.est_input_tokens ?? ''} est_out=${m.est_output_tokens ?? ''} ` +
                        `max_tokens=${m.config_max_tokens_effective ?? m.config_max_tokens ?? ''} ` +
                        `finish=${m.finish_reason ?? ''} output_chars=${m.output_chars ?? ''} ` +
                        `episode_id=${m.request_episode_id ?? ''} saved=${m.saved_to_episode ?? ''} ` +
                        `usage_prompt=${usage.prompt_tokens ?? usage.input_tokens ?? ''} ` +
                        `usage_completion=${usage.completion_tokens ?? usage.output_tokens ?? ''} ` +
                        `usage_total=${usage.total_tokens ?? ''}`,
                        "info"
                    );
                } catch (e) {
                    // ignore meta logging errors
                }
                runtimeMeta = extractAnalysisRuntimeMeta(result.meta);
                setAnalysisRuntimeMeta(runtimeMeta);
            } else {
                runtimeMeta = null;
                setAnalysisRuntimeMeta(null);
            }

            const integrityWarnings = collectAnalysisWarnings(result);
            const displayWarnings = collectAnalysisWarnings(result, { includeLogOnly: false });
            if (integrityWarnings.length > 0) {
                const uniqueWarnings = [...new Set(integrityWarnings.map(w => String(w || '').trim()).filter(Boolean))];
                if (uniqueWarnings.length > 0) {
                    const warningText = uniqueWarnings.join('\n- ');
                    if (onLog) onLog(`AI Script Analysis warning:\n- ${warningText}`, 'warning');
                    if (displayWarnings.length > 0) {
                        showAnalysisWarningStatus(displayWarnings);
                    }
                }
            }

            const analysisSections = extractAnalysisSections(analyzedText || '');
            if (!analysisSections.hasStructuredSubjectIndex) {
                if (onLog) onLog('Missing Subject Index after phase 1 output validation. Skipping auto-import and triggering cleanup retry.', 'warning');
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            setLlmRawResultContent(analyzedText);
            setLlmResultContent(normalizeLlmMarkdownTable(analyzedText));
            lastLoadedAnalysisRef.current = analyzedText;

            const savedByBackend = !!(result?.meta?.saved_to_episode);
            phaseMarks.persistStartedAt = Date.now();
            try {
                if (!savedByBackend) {
                    if (onLog) onLog('Saving raw LLM output to episode analysis field...', 'process');
                    await persistLlmResultContent(analyzedText);
                } else {
                    if (onLog) onLog('LLM raw output already saved by backend. Refreshing local episode cache...', 'info');
                    await refreshAnalysisFromDB();
                }
            } catch (persistErr) {
                if (onLog) onLog(`Raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }
            
            phaseMarks.importStartedAt = Date.now();
            setAnalysisFlowStatus({
                phase: 'saving_scenes',
                message: t('📝 分析框架解构完毕，正在导入您的工作区...', 'Importing Markdown and JSON into workspace...'),
            });
            try {
                importReport = await runAutoImportAndSwitchToScenes(analyzedText, {
                    switchToScenes: false,
                    importOptions: {
                        autoSupplementSceneSubjects: false,
                        suppressAlerts: true,
                        subjectsJson: result?.subjects_json || null,
                    },
                });
                if (!importReport) {
                    importWarningMessage = t('自动导入未返回结果，请检查导入配置或返回格式。', 'Auto-import returned no result. Check import config or response format.');
                    setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
                }
            } catch (importErr) {
                importWarningMessage = t(
                    `自动导入失败：${importErr?.message || importErr}`,
                    `Auto-import failed: ${importErr?.message || importErr}`
                );
                if (onLog) onLog(`Auto-import failed (checks will continue): ${importErr?.message || importErr}`, 'warning');
                setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            importReport = await ensureSubjectsImportedBeforePostChecks(result, importReport);
            maybeAlertIncompleteSubjectsImport(result, analyzedText || '');

            postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, analyzedText);
            if (importReport && typeof importReport === 'object') {
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.dbRunInsertedCounts) {
                    importReport.dbRunInsertedCounts = postImportSceneSubjectReport.dbRunInsertedCounts;
                }
                if (postImportSceneSubjectReport?.dbPersistedCounts) {
                    importReport.dbPersistedCounts = postImportSceneSubjectReport.dbPersistedCounts;
                }
                if (postImportSceneSubjectReport?.importedSubjectCounts) {
                    importReport.importedSubjectCounts = {
                        character: (importReport.importedSubjectCounts?.character || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.character) || 0),
                        prop: (importReport.importedSubjectCounts?.prop || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.prop) || 0),
                        environment: (importReport.importedSubjectCounts?.environment || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.environment) || 0),
                    };
                }
            }

            let firstPassReport = null;
            try {
                firstPassReport = runSubjectConsistencyCheck(analyzedText || '', { silent: true, persist: true });
                if (firstPassReport && !firstPassReport.ok) {
                    setAnalysisFlowStatus({
                        phase: 'warning',
                        message: t('实体一致性检查告警：请查看提示后继续。', 'Entity consistency warning: review the message and continue.'),
                    });
                    setTimeout(() => {
                        setAnalysisFlowStatus(prev => (prev?.phase === 'warning' ? { phase: 'idle', message: '' } : prev));
                    }, 5000);
                }
            } catch (consistencyErr) {
                firstPassReport = buildSubjectConsistencyReport(analyzedText || '');
                setSubjectConsistencyReport(firstPassReport);
                if (onLog) onLog(`Subject consistency check warning: ${consistencyErr?.message || consistencyErr}`, 'warning');
            }

            firstPassReport = firstPassReport || buildSubjectConsistencyReport(analyzedText || '');
            const followupIssues = await persistFirstPassIssuesToAttentionNotes(
                firstPassReport,
                integrityWarnings,
                importWarningMessage ? [importWarningMessage] : []
            );
            if (followupIssues.length > 0) {
                setAnalysisFlowStatus({
                    phase: 'warning',
                    message: t('首轮检测到问题，已写入补充说明。请点击“修正生成结果”。', 'First-pass issues were saved to attention notes. Click "Refine Generated Result" for a second pass.'),
                });
                if (onLog) onLog(`First-pass issues detected (${followupIssues.length}). Waiting for manual supplement submit.`, 'warning');
            }

            setPendingSwitchAfterPostChecks(false);
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            setAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                warning: importWarningMessage,
                error: '',
            });

            const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
            const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
            const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
            const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
            setAnalysisFlowStatus({
                phase: 'completed',
                message: postImportMissingItems > 0
                    ? (
                        postImportSupplementFailed > 0
                            ? t(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`)
                            : t(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`)
                    )
                    : t('✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.'),
            });

            if (onLog) onLog("AI Analysis applied and saved.");
            setShowAnalysisModal(false);
        } catch (e) {
            console.error(e);
            if (e?.message?.includes("第一阶段未解析到完整的 Subject Index 区块") && retryCount < 1) {
                if (onLog) onLog("未检测到 Subject Index，自动清理数据并准备重新发起(1/1)", "warning");
                setAnalysisFlowStatus({ phase: 'warning', message: '未检测到完整实体区块，将在3秒后重置场景并重启分析...' });
                try {
                    const scenes = await fetchScenes(activeEpisode.id);
                    if (scenes && scenes.length > 0) {
                        await Promise.all(scenes.map(s => deleteScene(s.id)));
                    }
                    await updateEpisode(activeEpisode.id, {
                        ai_scene_analysis_result: null,
                        ai_scene_analysis_subject_index: null,
                        ai_entity_design_result: null,
                        ai_scene_analysis_adaptation: null,
                    });
                    setLlmRawResultContent("");
                    setLlmResultContent("");
                    setSubjectIndexText("");
                    setAdaptationText("");
                    analysisRunInFlightRef.current = false;
                    setTimeout(() => {
                          executeAnalysis(content, customSystemPrompt, skipMetadata, retryCount + 1).catch(console.error);
                      }, 3000);
                    return;
                } catch(cleanupErr) {
                    console.error('Failed cleanup during auto retry', cleanupErr);
                }
            }

            const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            const friendlyAnalysisError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            if (canceled) {
                if (onLog) onLog('Analysis task canceled by user.', 'warning');
            } else {
                if (onLog) onLog(`Analysis Failed: ${friendlyAnalysisError}`);
            }
            setAnalysisFlowStatus(
                canceled
                    ? { phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') }
                    : { phase: 'failed', message: t(`分析失败：${friendlyAnalysisError}`, `Analysis failed: ${friendlyAnalysisError}`) }
            );
            setAnalysisUiReport({
                status: canceled ? 'warning' : 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport: importReport,
                runtimeMeta,
                warning: canceled ? t('分析任务已由用户停止。', 'Analysis task was stopped by user.') : '',
                error: canceled ? '' : friendlyAnalysisError,
            });
            if (!canceled) {
                alert(`Analysis failed: ${friendlyAnalysisError}`);
            }
        } finally {
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsAnalyzing(false);
            setActiveAnalysisTaskId('');
            analysisStopRequestedRef.current = false;
            analysisRunInFlightRef.current = false;
        }
    };

    const handleSaveAnalysisAttentionNotes = async () => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        setIsSavingAnalysisAttentionNotes(true);
        try {
            const mergedEpisodeInfo = {
                ...(activeEpisode?.episode_info || {}),
                analysis_attention_notes: analysisAttentionNotes || '',
            };
            await onUpdateEpisodeInfo(activeEpisode.id, { episode_info: mergedEpisodeInfo });
            if (onLog) onLog('Episode 1 analysis attention notes saved.', 'success');
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Failed to save analysis attention notes: ${e.message}`, 'error');
        } finally {
            setIsSavingAnalysisAttentionNotes(false);
        }
    };

    const saveAnalysisAttentionNotesValue = async (nextNotes) => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        const mergedEpisodeInfo = {
            ...(activeEpisode?.episode_info || {}),
            analysis_attention_notes: String(nextNotes || '').trim(),
        };
        await onUpdateEpisodeInfo(activeEpisode.id, { episode_info: mergedEpisodeInfo });
    };

    const handleSupplementSubmitClick = async () => {
        if (isAnalyzing) return;
        const generatedContent = String(llmRawResultContent || llmResultContent || '').trim();
        if (!generatedContent) {
            alert(t('请先完成第一次 AI 剧本分析，再执行“修正生成结果”。', 'Please finish the first AI Script Analysis before running "Refine Generated Result".'));
            return;
        }

        let basePromptForSupplement = '';
        try {
            const promptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning.md');
            basePromptForSupplement = String(promptRes?.content || '').trim();
        } catch {
            basePromptForSupplement = '';
        }

        // Always include original scene-analysis system prompt for second-pass supplement submit.
        // Fallback order: fetched prompt -> current systemPrompt editor content.
        if (!basePromptForSupplement) {
            basePromptForSupplement = String(systemPrompt || '').trim();
        }

        const currentReport = buildSubjectConsistencyReport(generatedContent);
        const followupIssues = collectFollowupIssues(currentReport, [], []);
        const supplementPrompt = buildIssueDrivenSupplementPrompt(basePromptForSupplement, followupIssues);

        const supplementInput = buildSupplementSubmissionInput({
            generatedContent,
            subjectCheckText: subjectConsistencyResultText,
            coreCoverageText: coreCoverageResultText,
            attentionNotes: analysisAttentionNotes,
        });

        // Keep supplement submit behavior aligned with primary scene analysis:
        // superuser previews/edits prompt first, then manually runs submission.
        if (isSuperuser) {
            setAnalysisUiReport(null);
            setAnalysisFlowStatus({ phase: 'idle', message: '' });
            setSystemPrompt(supplementPrompt);
            setUserPrompt(supplementInput);
            setShowAnalysisModal(true);
            if (onLog) onLog('Superuser supplement submit: prompt preview opened before submission.', 'info');
            return;
        }

        if (onLog) onLog('Manual supplement submit started (input=generated analysis output).', 'start');
        await executeAnalysis(supplementInput, supplementPrompt, false);
    };

    const executeAdvancedAnalysis = async (userInput, customSystemPrompt, retryCount = 0) => {
        if (!activeEpisode?.id) {
            alert("No active episode selected.");
            return;
        }

        // Bypass Phase 1 if subject index is already present!
        if (activeEpisode.ai_scene_analysis_subject_index && activeEpisode.ai_scene_analysis_subject_index.trim()) {
            const bypassConfirmed = true;
            if (bypassConfirmed) {
                // Phase 2 Check: if it already exists, do not initiate again
                if (activeEpisode.ai_entity_design_result && activeEpisode.ai_entity_design_result.trim()) {
                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: "🎉 专属实体资产定制均已存在，无需重复生成！"
                    });
                    if (onLog) onLog("AI Analysis bypassed entirely; both phases are already completed.");
                    return;
                }
                // Phase 2 Check: if it already exists, do not initiate again
                if (activeEpisode.ai_entity_design_result && activeEpisode.ai_entity_design_result.trim()) {
                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: "🎉 专属实体资产定制均已存在，无需重复生成！"
                    });
                    if (onLog) onLog("AI Analysis bypassed entirely; both phases are already completed.");
                    return;
                }
                const startedAt = Date.now();
                setAnalysisUiReport({
                    status: 'running',
                    startedAt,
                    durationMs: 0,
                    phaseTimings: null,
                    importReport: null,
                    runtimeMeta: null,
                    warning: '',
                    error: '',
                });

                setAnalysisFlowStatus({
                    phase: 'processing_output_workspace',
                    message: "🚀 跳过 Phase 1，直接进入资产设计...",
                });

                try {
                    // We just jump straight to Phase 2 logic (runPostImportSceneSubjectPipeline).
                    // We mock an empty import report to keep the pipeline happy.
                    const mockImportReport = { importedSceneRows: [] };
                    const dummyAnalyzedText = activeEpisode.ai_scene_analysis_result || activeEpisode.ai_scene_analysis_subject_index; // Pass something fallback

                    const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(mockImportReport, dummyAnalyzedText);

                    const finalImportReport = {
                        ...mockImportReport,
                        sceneSubjectPostImportReport: postImportSceneSubjectReport,
                        dbRunInsertedCounts: postImportSceneSubjectReport?.dbRunInsertedCounts,
                        dbPersistedCounts: postImportSceneSubjectReport?.dbPersistedCounts,
                        importedSubjectCounts: postImportSceneSubjectReport?.importedSubjectCounts,
                    };

                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: "🎉 专属实体资产定制完毕，可随时投产使用！",
                    });

                    setAnalysisUiReport({
                        status: 'completed',
                        startedAt,
                        durationMs: Date.now() - startedAt,
                        phaseTimings: null,
                        importReport: finalImportReport,
                        runtimeMeta: null,
                        warning: '',
                        error: '',
                    });
                } catch (err) {
                    console.error(err);
                    setAnalysisFlowStatus({ phase: 'failed', message: "❌ 资产生成失败: " + err.message });
                    setAnalysisUiReport({
                        status: 'failed',
                        startedAt,
                        durationMs: Date.now() - startedAt,
                        phaseTimings: null,
                        importReport: null,
                        runtimeMeta: null,
                        warning: '',
                        error: err.message,
                    });
                }
                return; // Early return to completely bypass standard analysis flow
            }
        }
        if (analysisRunInFlightRef.current || analysisResumeInFlightRef.current) {
            if (onLog) onLog('Skipped duplicate advanced AI Script Analysis submit while another analysis run is already active.', 'warning');
            return;
        }
        analysisRunInFlightRef.current = true;
        clearAnalysisTaskMarker(activeEpisode?.id);

        const startedAt = Date.now();
        analysisStopRequestedRef.current = false;
        setIsAnalyzing(true);
        setActiveAnalysisTaskId('');
        setAnalysisFlowStatus({
            phase: 'autosaving',
            message: t('💾 正在自动保存您的剧本，保障数据安全...', 'Auto-saving script...'),
        });
        setAnalysisUiReport({
            status: 'running',
            startedAt,
            durationMs: 0,
            phaseTimings: null,
            importReport: null,
            runtimeMeta: null,
            warning: '',
            error: '',
        });
        if (onLog) onLog("Starting Advanced AI Analysis (Superuser)...", "start");

        let llmReturned = false;
        let runtimeMeta = null;
        let importReport = null;
        let postImportSceneSubjectReport = null;
        let importWarningMessage = '';
        const phaseMarks = {
            submitStartedAt: startedAt,
            analyzeStartedAt: 0,
            llmReturnedAt: 0,
            importStartedAt: 0,
            importFinishedAt: 0,
            persistStartedAt: 0,
            persistFinishedAt: 0,
            completedAt: 0,
        };

        try {
            await autoSaveScriptBeforeAnalysis();

            setAnalysisFlowStatus({
                phase: 'analyzing',
                message: t('🧠 正在通读剧本并设计场景啦。根据字数和剧情可能要 3~4 分钟，先喝杯水休息下吧~', 'LLM submitted. Waiting for response. Submit timeout is about 300s and total wait can take up to about 600s.'),
            });
            phaseMarks.analyzeStartedAt = Date.now();

            const baselineAnalysisText = String(llmRawResultContent || activeEpisode?.ai_scene_analysis_result || '').trim();
            const result = await awaitAnalyzeSceneWithRecovery(
                () => analyzeScene(
                    userInput,
                    customSystemPrompt,
                    null,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            setActiveAnalysisTaskId(String(taskId || '').trim());
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 1 });
                        },
                    },
                    projectId
                ),
                { startedAt, baselineText: baselineAnalysisText }
            );
            const analyzedText = extractAnalysisTextFromResult(result);
            if (analyzedText && analyzedText.includes("PROHIBITED_CONTENT")) {
                throw new Error("出现供应商政策不允许内容");
            }
            llmReturned = true;
            phaseMarks.llmReturnedAt = Date.now();

            if (result && result.meta) {
                try {
                    const m = result.meta;
                    const usage = m.usage || {};
                    if (onLog) onLog(
                        `AI Analysis meta: sys_chars=${m.system_prompt_chars} user_chars=${m.user_prompt_chars} ` +
                        `est_in=${m.est_input_tokens ?? ''} est_out=${m.est_output_tokens ?? ''} ` +
                        `max_tokens=${m.config_max_tokens_effective ?? m.config_max_tokens ?? ''} ` +
                        `finish=${m.finish_reason ?? ''} output_chars=${m.output_chars ?? ''} ` +
                        `episode_id=${m.request_episode_id ?? ''} saved=${m.saved_to_episode ?? ''} ` +
                        `usage_prompt=${usage.prompt_tokens ?? usage.input_tokens ?? ''} ` +
                        `usage_completion=${usage.completion_tokens ?? usage.output_tokens ?? ''} ` +
                        `usage_total=${usage.total_tokens ?? ''}`,
                        "info"
                    );
                } catch (e) {
                    // ignore meta logging errors
                }
                runtimeMeta = extractAnalysisRuntimeMeta(result.meta);
                setAnalysisRuntimeMeta(runtimeMeta);
            } else {
                runtimeMeta = null;
                setAnalysisRuntimeMeta(null);
            }

            const integrityWarnings = collectAnalysisWarnings(result);
            const displayWarnings = collectAnalysisWarnings(result, { includeLogOnly: false });
            if (integrityWarnings.length > 0) {
                const uniqueWarnings = [...new Set(integrityWarnings.map(w => String(w || '').trim()).filter(Boolean))];
                if (uniqueWarnings.length > 0) {
                    const warningText = uniqueWarnings.join('\n- ');
                    if (onLog) onLog(`AI Script Analysis warning:\n- ${warningText}`, 'warning');
                    if (displayWarnings.length > 0) {
                        showAnalysisWarningStatus(displayWarnings);
                    }
                }
            }

            const analysisSections = extractAnalysisSections(analyzedText || '');
            if (!analysisSections.hasStructuredSubjectIndex) {
                if (onLog) onLog('Missing Subject Index after phase 1 output validation. Skipping auto-import and triggering cleanup retry.', 'warning');
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            setLlmRawResultContent(analyzedText || "");
            setLlmResultContent(normalizeLlmMarkdownTable(analyzedText || ""));
            lastLoadedAnalysisRef.current = analyzedText || "";

            const savedByBackend = !!(result?.meta?.saved_to_episode);
            phaseMarks.persistStartedAt = Date.now();
            try {
                if (!savedByBackend) {
                    if (onLog) onLog('Saving advanced raw LLM output to episode analysis field...', 'process');
                    await persistLlmResultContent(analyzedText || '');
                } else {
                    if (onLog) onLog('Advanced LLM raw output already saved by backend. Refreshing local episode cache...', 'info');
                    await refreshAnalysisFromDB();
                }
            } catch (persistErr) {
                if (onLog) onLog(`Advanced raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }

            phaseMarks.importStartedAt = Date.now();
            setAnalysisFlowStatus({
                phase: 'saving_scenes',
                message: t('📝 分析框架解构完毕，正在导入您的工作区...', 'Importing Markdown and JSON into workspace...'),
            });
            try {
                importReport = await runAutoImportAndSwitchToScenes(analyzedText || "", {
                    switchToScenes: false,
                    importOptions: {
                        autoSupplementSceneSubjects: false,
                        suppressAlerts: true,
                        subjectsJson: result?.subjects_json || null,
                    },
                });
                if (!importReport) {
                    importWarningMessage = t('自动导入未返回结果，请检查导入配置或返回格式。', 'Auto-import returned no result. Check import config or response format.');
                    setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
                }
            } catch (importErr) {
                importWarningMessage = t(
                    `自动导入失败：${importErr?.message || importErr}`,
                    `Auto-import failed: ${importErr?.message || importErr}`
                );
                if (onLog) onLog(`Auto-import failed (checks will continue): ${importErr?.message || importErr}`, 'warning');
                setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            importReport = await ensureSubjectsImportedBeforePostChecks(result, importReport);
            maybeAlertIncompleteSubjectsImport(result, analyzedText || '');

            postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, analyzedText);
            if (importReport && typeof importReport === 'object') {
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.dbRunInsertedCounts) {
                    importReport.dbRunInsertedCounts = postImportSceneSubjectReport.dbRunInsertedCounts;
                }
                if (postImportSceneSubjectReport?.dbPersistedCounts) {
                    importReport.dbPersistedCounts = postImportSceneSubjectReport.dbPersistedCounts;
                }
                if (postImportSceneSubjectReport?.importedSubjectCounts) {
                    importReport.importedSubjectCounts = {
                        character: (importReport.importedSubjectCounts?.character || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.character) || 0),
                        prop: (importReport.importedSubjectCounts?.prop || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.prop) || 0),
                        environment: (importReport.importedSubjectCounts?.environment || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.environment) || 0),
                    };
                }
            }

            let firstPassReport = null;
            try {
                firstPassReport = runSubjectConsistencyCheck(analyzedText || '', { silent: true, persist: true });
                if (firstPassReport && !firstPassReport.ok) {
                    setAnalysisFlowStatus({
                        phase: 'warning',
                        message: t('实体一致性检查告警：请查看提示后继续。', 'Entity consistency warning: review the message and continue.'),
                    });
                    setTimeout(() => {
                        setAnalysisFlowStatus(prev => (prev?.phase === 'warning' ? { phase: 'idle', message: '' } : prev));
                    }, 5000);
                }
            } catch (consistencyErr) {
                firstPassReport = buildSubjectConsistencyReport(analyzedText || '');
                setSubjectConsistencyReport(firstPassReport);
                if (onLog) onLog(`Subject consistency check warning: ${consistencyErr?.message || consistencyErr}`, 'warning');
            }

            firstPassReport = firstPassReport || buildSubjectConsistencyReport(analyzedText || '');
            const followupIssues = await persistFirstPassIssuesToAttentionNotes(
                firstPassReport,
                integrityWarnings,
                importWarningMessage ? [importWarningMessage] : []
            );
            if (followupIssues.length > 0) {
                setAnalysisFlowStatus({
                    phase: 'warning',
                    message: t('首轮检测到问题，已写入补充说明。请点击“修正生成结果”。', 'First-pass issues were saved to attention notes. Click "Refine Generated Result" for a second pass.'),
                });
                if (onLog) onLog(`First-pass issues detected (${followupIssues.length}). Waiting for manual supplement submit.`, 'warning');
            }

            setPendingSwitchAfterPostChecks(false);
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            setAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                warning: importWarningMessage,
                error: '',
            });

            const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
            const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
            const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
            const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
            setAnalysisFlowStatus({
                phase: 'completed',
                message: postImportMissingItems > 0
                    ? (
                        postImportSupplementFailed > 0
                            ? t(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`)
                            : t(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`)
                    )
                    : t('✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.'),
            });

            setShowAnalysisModal(false);
        } catch (e) {
            console.error(e);
            if (e?.message?.includes("第一阶段未解析到完整的 Subject Index 区块") && retryCount < 1) {
                if (onLog) onLog("未检测到 Subject Index，自动清理数据并准备重新发起(1/1)", "warning");
                setAnalysisFlowStatus({ phase: 'warning', message: '未检测到完整实体区块，将在3秒后重置场景并重启分析...' });
                try {
                    const scenes = await fetchScenes(activeEpisode.id);
                    if (scenes && scenes.length > 0) {
                        await Promise.all(scenes.map(s => deleteScene(s.id)));
                    }
                    await updateEpisode(activeEpisode.id, {
                        ai_scene_analysis_result: null,
                        ai_scene_analysis_subject_index: null,
                        ai_entity_design_result: null,
                        ai_scene_analysis_adaptation: null,
                    });
                    setLlmRawResultContent("");
                    setLlmResultContent("");
                    setSubjectIndexText("");
                    setAdaptationText("");
                    analysisRunInFlightRef.current = false;
                    setTimeout(() => {
                        executeAdvancedAnalysis(userInput, customSystemPrompt, retryCount + 1).catch(console.error);
                    }, 3000);
                    return;
                } catch(cleanupErr) {
                    console.error('Failed cleanup during auto retry', cleanupErr);
                }
            }

            const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            const friendlyAnalysisError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            if (canceled) {
                if (onLog) onLog('Advanced analysis task canceled by user.', 'warning');
            } else {
                if (onLog) onLog(`Advanced analysis failed: ${friendlyAnalysisError}`);
            }
            setAnalysisFlowStatus(
                canceled
                    ? { phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') }
                    : { phase: 'failed', message: t(`分析失败：${friendlyAnalysisError}`, `Analysis failed: ${friendlyAnalysisError}`) }
            );
            setAnalysisUiReport({
                status: canceled ? 'warning' : 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport: importReport,
                runtimeMeta,
                warning: canceled ? t('分析任务已由用户停止。', 'Analysis task was stopped by user.') : '',
                error: canceled ? '' : friendlyAnalysisError,
            });
            if (!canceled) {
                alert(`Analysis failed: ${friendlyAnalysisError}`);
            }
        } finally {
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsAnalyzing(false);
            setActiveAnalysisTaskId('');
            analysisStopRequestedRef.current = false;
            analysisRunInFlightRef.current = false;
        }
    };


    const handleRetryPhase2 = async () => {
        if (!activeEpisode?.id) return;
        setIsRetryingPhase2(true);
        try {
            onLog?.('Retrying Phase 2 (Asset Generation)...', 'process');
            // Re-run the second pass with the (potentially edited) subjectIndexText
            // It will also bust deduplication cache by using sceneAnalysisMode = "2_pass_generate_assets" internally
            const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(
                analysisUiReport?.importReport || {},
                subjectIndexText
            );
            
            // Update the UI report with the new asset counts
            if (analysisUiReport && typeof analysisUiReport === 'object') {
                const newImportReport = {
                    ...analysisUiReport.importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.dbRunInsertedCounts) {
                    newImportReport.dbRunInsertedCounts = postImportSceneSubjectReport.dbRunInsertedCounts;
                }
                if (postImportSceneSubjectReport?.dbPersistedCounts) {
                    newImportReport.dbPersistedCounts = postImportSceneSubjectReport.dbPersistedCounts;
                }
                if (postImportSceneSubjectReport?.importedSubjectCounts) {
                    newImportReport.importedSubjectCounts = {
                        character: (newImportReport.importedSubjectCounts?.character || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.character) || 0),
                        prop: (newImportReport.importedSubjectCounts?.prop || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.prop) || 0),
                        environment: (newImportReport.importedSubjectCounts?.environment || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.environment) || 0),
                    };
                }
                
                setAnalysisUiReport(prev => ({
                    ...prev,
                    importReport: newImportReport,
                }));
                
                const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
                const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
                const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
                const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
                
                setAnalysisFlowStatus({
                    phase: 'completed',
                    message: postImportMissingItems > 0
                        ? (
                            postImportSupplementFailed > 0
                                ? t(`🔄 补全完毕！发现 ${postImportMissingItems} 个需补充资产，成功处理了 ${postImportSupplementCreated} 个（跳过 ${postImportSupplementSkipped} 个，失败 ${postImportSupplementFailed} 个）。`, `Retry completed: ${postImportMissingItems} missing entities detected. Supplement created ${postImportSupplementCreated}, failed ${postImportSupplementFailed}, skipped ${postImportSupplementSkipped}.`)
                                : t(`🔄 补全完毕！发现 ${postImportMissingItems} 个需补充资产，已成功处理 ${postImportSupplementCreated} 个（跳过 ${postImportSupplementSkipped} 个）。`, `Retry completed: ${postImportMissingItems} missing entities detected. Supplement created ${postImportSupplementCreated} (skipped ${postImportSupplementSkipped}).`)
                        )
                        : t('重试✅ 工作圆满完成！未发现缺失的资产。', 'Retry completed: no missing entities detected, workflow finished.'),
                });
                
                onLog?.('Phase 2 Asset Generation Retry Completed.', 'success');
            }
        } catch (error) {
            console.error("Retry Phase 2 failed:", error);
            onLog?.(`Retry Phase 2 failed: ${error.message || String(error)}`, 'error');
            alert(`Retry Phase 2 failed: ${error.message}`);
        } finally {
            setIsRetryingPhase2(false);
        }
    };

    if (!activeEpisode) return <div className="p-8 text-muted-foreground">{t('请选择或创建一个分集开始写作。', 'Select or create an episode to start writing.')}</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    {buildEpisodeDisplayLabel({
                        episodeNumber: activeEpisode?.episode_number,
                        title: activeEpisode?.title,
                    })}
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">
                        {isRawMode ? t('原始编辑器', 'Raw Editor') : `${segments.length} ${t('段', 'Segments')}`}
                    </span>
                </h2>
                <div className="flex items-center gap-2">
                    {isRawMode && (
                        <>
                            <FunctionApiSelector functionName="script_analysis" configs={functionApiConfigs} />
                            <button 
                                onClick={handleAnalysisClick} 
                                disabled={isAnalyzing}
                                className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isAnalyzing ? 'bg-purple-900/50 text-purple-200 cursor-not-allowed' : 'bg-purple-600 text-white hover:bg-purple-500'}`}
                                title={t('分析原始剧本并生成结构', 'Analyze raw script to generate structure')}
                            >
                                {isAnalyzing ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" /> {t('AI正在为您深度拆解剧本...', 'Analyzing...')}
                                    </>
                                ) : (
                                    <>
                                        <Wand2 className="w-4 h-4" /> {t('AI 剧本分析', 'AI Script Analysis')}
                                    </>
                                )}
                            </button>
                            {isAnalyzing && (
                                <button
                                    onClick={handleStopAnalysisTask}
                                    disabled={isStoppingAnalysisTask}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 border ${isStoppingAnalysisTask ? 'bg-white/5 text-muted-foreground border-white/10 cursor-not-allowed' : 'bg-red-500/20 hover:bg-red-500/30 text-red-100 border-red-400/40'}`}
                                    title={t('手动停止当前 AI 剧本分析任务', 'Stop the current AI script analysis task')}
                                >
                                    {isStoppingAnalysisTask ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                                    {isStoppingAnalysisTask ? t('停止中...', 'Stopping...') : t('停止分析', 'Stop Analysis')}
                                </button>
                            )}
                        </>
                    )}
                    {!isRawMode && (
                        <button 
                            onClick={handleMerge} 
                            className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20 flex items-center gap-2"
                            title={t('将所有分段合并为单一剧本', 'Merge all segments into a single script')}
                        >
                            <LayoutList className="w-4 h-4" />
                            {t('合并剧本', 'Merge Script')}
                        </button>
                    )}
                    <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90">{t('保存修改', 'Save Changes')}</button>
                    <button
                        onClick={async () => {
                            if (!projectId || !activeEpisode?.id || isRecomputingEpisodeCost) return;
                            setIsRecomputingEpisodeCost(true);
                            try {
                                await recomputeEpisodeCostEstimation(projectId, activeEpisode.id);
                            } catch (e) {
                                console.error('Episode cost recompute failed', e);
                            } finally {
                                setIsRecomputingEpisodeCost(false);
                            }
                        }}
                        disabled={isRecomputingEpisodeCost || !activeEpisode?.id}
                        className="px-3 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-100 border border-emerald-500/30 rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        title={t('重新估算本集成本', 'Recompute episode cost estimation')}
                    >
                        {isRecomputingEpisodeCost ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        {t('重算成本', 'Recompute Cost')}
                    </button>
                </div>
            </div>

            {(analysisFlowStatus.phase !== 'idle' || analysisUiReport) && (
                <div className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
                    analysisFlowStatus.phase === 'failed'
                        ? 'border-red-500/30 bg-red-500/10 text-red-100'
                        : analysisFlowStatus.phase === 'warning'
                            ? 'border-amber-500/30 bg-amber-500/10 text-amber-100'
                            : analysisFlowStatus.phase === 'completed'
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                                : 'border-purple-500/30 bg-purple-500/10 text-purple-100'
                }`}>
                    <div className="flex items-center justify-between gap-3 mb-3">
                        <div className="flex items-center gap-2 font-semibold">
                            {analysisFlowStatus.phase === 'completed' ? <CheckCircle className="w-4 h-4" /> : analysisFlowStatus.phase === 'failed' ? <X className="w-4 h-4" /> : analysisFlowStatus.phase === 'warning' ? <Info className="w-4 h-4" /> : <Loader2 className="w-4 h-4 animate-spin" />}
                            <span>{t('场景拆解进度', 'AI Script Analysis Status')}</span>
                        </div>
                        {!isAnalyzing && (
                            <button
                                type="button"
                                onClick={() => {
                                    setAnalysisFlowStatus({ phase: 'idle', message: '' });
                                    setAnalysisUiReport(null);
                                }}
                                className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20"
                            >
                                {t('关闭', 'Close')}
                            </button>
                        )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3">
                                                                        {[
                            { key: 'autosaving', label: t('自动保存', 'Auto Save') },
                            { key: 'analyzing', label: t('场景解析', 'Scene Planning') },
                            { key: 'saving_scenes', label: t('保存结构', 'Import Structure') },
                            { key: 'generating_assets', label: t('推演资产', 'Asset Generation') },
                            { key: 'completed', label: t('AI 总结报告', 'Report') },
                        ].map((step, idx) => {
                            const stepOrder = ['autosaving', 'analyzing', 'saving_scenes', 'generating_assets', 'completed'];
                            const phase = analysisFlowStatus.phase || 'idle';
                            const currentIndex = stepOrder.indexOf(phase);
                            const stepIndex = stepOrder.indexOf(step.key);
                            const hasFinalReport = !!(analysisUiReport && analysisUiReport.status !== 'running');
                            const isTerminalWarning = phase === 'warning';
                            const isTerminalFailed = phase === 'failed';
                            const isDone = !isTerminalFailed && (
                                hasFinalReport
                                    ? stepIndex <= 3
                                    : (isTerminalWarning ? stepIndex <= 2 : currentIndex > stepIndex || phase === 'completed')
                            );
                            const isActive = !isTerminalFailed && !isTerminalWarning && currentIndex === stepIndex;
                            const isFailed = isTerminalFailed && step.key === 'analyzing';
                            return (
                                <div
                                    key={step.key}
                                    className={`rounded-lg border px-3 py-2 flex items-center gap-2 ${
                                        isFailed
                                            ? 'border-red-400/50 bg-red-500/20'
                                            : isActive
                                                ? 'border-purple-300/60 bg-purple-400/20'
                                                : isDone
                                                    ? 'border-emerald-300/60 bg-emerald-400/20'
                                                    : 'border-white/15 bg-black/20'
                                    }`}
                                >
                                    <span className="text-[11px] font-bold opacity-80">{idx + 1}</span>
                                    <span className="text-xs leading-tight">{step.label}</span>
                                </div>
                            );
                        })}
                    </div>

                    {analysisFlowStatus.message && (
                        <div className="mb-2 text-xs opacity-95">{analysisFlowStatus.message}</div>
                    )}

                    {isAnalyzing && analysisFlowStatus.phase === 'analyzing' && analysisHeartbeatElapsedMs >= 5000 && (
                        <div className="mb-2 text-[11px] text-amber-200/90">
                            {t('仍在等待后端响应...', 'Still waiting for backend response...')} ({formatDurationMs(analysisHeartbeatElapsedMs)})
                            <span className="ml-2 text-amber-100/80">
                                {t('提交阶段超时约 300s，整体等待最长约 600s；复杂剧本通常需要更久。', 'Submit timeout is about 300s and total wait can take up to about 600s; complex scripts usually take longer.')}
                            </span>
                        </div>
                    )}

                    {isAnalyzing && analysisFlowStatus.phase === 'analyzing' && (
                        <div className="mb-2">
                            <button
                                onClick={handleStopAnalysisTask}
                                disabled={isStoppingAnalysisTask}
                                className={`px-3 py-1.5 rounded-md text-[11px] font-bold border ${isStoppingAnalysisTask ? 'bg-white/5 text-muted-foreground border-white/10 cursor-not-allowed' : 'bg-red-500/20 hover:bg-red-500/30 border-red-400/40 text-red-100'}`}
                            >
                                {isStoppingAnalysisTask ? t('停止中...', 'Stopping...') : t('停止任务', 'Stop Task')}
                            </button>
                        </div>
                    )}

                    {!isAnalyzing && (analysisFlowStatus.phase === 'warning' || analysisFlowStatus.phase === 'failed') && (
                        <div className="mb-2">
                            <button
                                onClick={handleAnalysisClick}
                                className="px-3 py-1.5 rounded-md text-[11px] font-bold bg-white/10 hover:bg-white/20 border border-white/15 text-white"
                            >
                                {t('重试分析', 'Retry Analysis')}
                            </button>
                        </div>
                    )}

                    {analysisUiReport && analysisUiReport.status !== 'running' && (
                        <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm space-y-3 mb-2">
                            <div className="font-bold text-white/90 text-base flex items-center gap-2">
                                <CheckCircle className="w-5 h-5 text-emerald-400" /> {t('阅读与段落梳理完毕！', 'Analysis & Import Completed!')}
                            </div>
                            <div className="text-white/80 space-y-2 bg-black/20 p-3 rounded-md border border-white/5">
                                <div>
                                    <span className="font-medium">✨ {t('资产入库统计', 'Asset Insert Stats')}:</span> {t('本次新增', 'Inserted this run')}
                                    <span className="text-purple-300 font-semibold"> {analysisUiReport.importReport?.dbRunInsertedCounts?.entities?.character ?? analysisUiReport.importReport?.dbPersistedCounts?.entities?.character ?? analysisUiReport.importReport?.importedSubjectCounts?.character ?? 0} </span>{t('位角色', 'characters')}、
                                    <span className="text-emerald-300 font-semibold"> {analysisUiReport.importReport?.dbRunInsertedCounts?.entities?.environment ?? analysisUiReport.importReport?.dbPersistedCounts?.entities?.environment ?? analysisUiReport.importReport?.importedSubjectCounts?.environment ?? 0} </span>{t('个空镜', 'environments')}、
                                    <span className="text-amber-300 font-semibold"> {analysisUiReport.importReport?.dbRunInsertedCounts?.entities?.prop ?? analysisUiReport.importReport?.dbPersistedCounts?.entities?.prop ?? analysisUiReport.importReport?.importedSubjectCounts?.prop ?? 0} </span>{t('个道具', 'props')}
                                    <span className="ml-1 text-white/70">(
                                        {t('当前总量', 'Current total')}:
                                        <span className="text-purple-200 font-semibold"> {analysisUiReport.importReport?.dbPersistedCounts?.entities?.character ?? analysisUiReport.importReport?.importedSubjectCounts?.character ?? 0} </span>{t('角色', 'characters')}、
                                        <span className="text-emerald-200 font-semibold"> {analysisUiReport.importReport?.dbPersistedCounts?.entities?.environment ?? analysisUiReport.importReport?.importedSubjectCounts?.environment ?? 0} </span>{t('空镜', 'environments')}、
                                        <span className="text-amber-200 font-semibold"> {analysisUiReport.importReport?.dbPersistedCounts?.entities?.prop ?? analysisUiReport.importReport?.importedSubjectCounts?.prop ?? 0} </span>{t('道具', 'props')}
                                    )</span>。
                                </div>
                                <div>
                                    <span className="font-medium">🔍 {t('场景画面搭建', 'Scene Construction')}:</span> {t('本次新增', 'Inserted this run')}
                                    <span className="text-white font-semibold"> {analysisUiReport.importReport?.dbRunInsertedCounts?.scenes?.created ?? analysisUiReport.importReport?.dbPersistedCounts?.scenes?.currentEpisode ?? analysisUiReport.importReport?.sceneSubjectPostImportReport?.checkedSceneCount ?? 0} </span>{t('个场景', 'shots')}
                                    <span className="ml-1 text-white/70">({t('当前分集总量', 'Current episode total')}: <span className="text-white font-semibold">{analysisUiReport.importReport?.dbPersistedCounts?.scenes?.currentEpisode ?? analysisUiReport.importReport?.sceneSubjectPostImportReport?.checkedSceneCount ?? 0}</span>)</span>。
                                </div>
                                <div>
                                    <span className="font-medium">⏱️ {t('运行时长', 'Duration')}:</span> <span className="text-blue-300 font-semibold">{formatDurationMs(analysisUiReport.durationMs || analysisUiReport?.phaseTimings?.totalMs)}</span>
                                </div>
                            </div>
                            <div className="text-xs text-white/60 space-y-1 pt-1">
                                <div>
                                    * {t('如果不满意，也可以在刚才的“补充说明”写清要求，点击下方的“修改并调整后重新生成”。', 'Not satisfied? Add notes below and click "Refine" to try again.')}
                                </div>
                            </div>
                            
                            
                        </div>
                    )}
                </div>
            )}

            <div className="flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col">
                <div className="flex-1 overflow-hidden">
                    {isRawMode ? (
                        <div className="h-full w-full flex flex-col overflow-hidden">
                            <div className="px-6 py-3 border-b border-white/10 bg-black/10 flex items-center justify-between">
                                <div className="text-sm text-primary uppercase font-extrabold tracking-wide">{t('输入脚本（Input）', 'Script Input')}</div>
                                <div className="text-[10px] text-muted-foreground">{(rawContent || '').length} {t('字符', 'chars')}</div>
                            </div>
                            <textarea
                                className="w-full flex-1 min-h-[420px] p-6 bg-transparent text-white/90 font-mono text-sm leading-relaxed focus:outline-none custom-scrollbar resize-none"
                                placeholder={t('在这里粘贴或输入你的剧本...', 'Paste or type your script here...')}
                                value={rawContent}
                                onChange={(e) => setRawContent(e.target.value)}
                            />

                            <div className="border-t border-amber-500/20 bg-amber-500/10 px-6 py-4">
                                <div className="font-bold text-amber-300 text-xs mb-2 flex items-center gap-2">
                                    📝 {t('剧本改编补充说明', 'Script Adaptation Notes')}
                                </div>
                                <textarea
                                    className="w-full h-24 p-3 bg-black/50 border border-amber-500/20 rounded-md text-amber-200/90 font-mono text-xs resize-none focus:outline-none custom-scrollbar"
                                    value={adaptationText || ''}
                                    readOnly
                                    placeholder={t('（未运行时为空）', '(Empty when not running)')}
                                />
                            </div>

                            {isEpisodeOnePage && (
                                <div className="border-t border-white/10 px-6 py-4 bg-black/10">
                                    <div className="text-xs font-semibold uppercase text-muted-foreground">Episode 1 · AI Script Analysis 补充说明（可为空）</div>
                                    <div className="text-[11px] text-muted-foreground mt-1 mb-2">
                                        该项可为空。补充要求通常用于特别强调资产生成或关键执行要求；点击 AI Script Analysis 时会作为高优先级约束注入。
                                    </div>
                                    <textarea
                                        value={analysisAttentionNotes}
                                        onChange={(e) => setAnalysisAttentionNotes(e.target.value)}
                                        placeholder="可留空；例如：必须严格按轴线拆分、保留关键道具锚点、避免漏掉反应镜头、环境命名必须 Front/Reverse。"
                                        className="w-full h-24 bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white/90 focus:outline-none focus:border-primary/50 custom-scrollbar resize-none"
                                    />
                                    <div className="mt-2 flex justify-end gap-2">
                                        <button
                                            onClick={handleSupplementSubmitClick}
                                            disabled={isAnalyzing || !String(llmRawResultContent || llmResultContent || '').trim()}
                                            className={`px-3 py-2 rounded-md text-xs font-bold ${isAnalyzing || !String(llmRawResultContent || llmResultContent || '').trim() ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-400/30'}`}
                                            title={t('使用“已生成内容 + 补充说明”执行修正生成结果', 'Refine generated result using existing output + attention notes')}
                                        >
                                            {t('修正生成结果', 'Refine Generated Result')}
                                        </button>
                                        <button
                                            onClick={handleSaveAnalysisAttentionNotes}
                                            disabled={isSavingAnalysisAttentionNotes}
                                            className={`px-3 py-2 rounded-md text-xs font-bold ${isSavingAnalysisAttentionNotes ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                                        >
                                            {isSavingAnalysisAttentionNotes ? t('保存中...', 'Saving...') : t('保存补充说明', 'Save Attention Notes')}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="overflow-auto custom-scrollbar h-full w-full">
                            <table className="w-full text-left border-collapse text-sm">
                                <thead className="bg-white/5 sticky top-0 z-10 backdrop-blur-md">
                                    <tr>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-16">{t('编号', 'ID')}</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-48">{t('标题', 'Title')}</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground min-w-[220px] sm:min-w-[300px]">{t('内容（修订）', 'Content (Revised)')}</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground min-w-[220px] sm:min-w-[300px]">{t('内容（原始）', 'Content (Original)')}</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-48">{t('叙事功能', 'Narrative Function')}</th>
                                        <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-64">{t('从剧本提炼的导演备注', 'Analysis & Adaptation Notes')}</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {segments.map((seg, idx) => (
                                        <tr key={idx} className="hover:bg-white/5 transition-colors group">
                                            <td className="p-4 align-top font-mono text-xs text-muted-foreground">{seg.id}</td>
                                            <td className="p-4 align-top font-bold text-primary">
                                                {seg.title}
                                            </td>
                                            <td className="p-4 align-top">
                                                <textarea 
                                                    className="w-full bg-transparent border-none text-white/90 leading-relaxed font-serif focus:outline-none focus:ring-0 resize-none overflow-hidden"
                                                    style={{ minHeight: '60px' }}
                                                    ref={(el) => {
                                                        if (el) {
                                                            el.style.height = 'auto';
                                                            el.style.height = el.scrollHeight + 'px';
                                                        }
                                                    }}
                                                    onInput={(e) => {
                                                        e.target.style.height = 'auto';
                                                        e.target.style.height = e.target.scrollHeight + 'px';
                                                    }}
                                                    value={seg.content || ''}
                                                    onChange={(e) => handleSegmentChange(idx, 'content', e.target.value)}
                                                />
                                            </td>
                                            <td className="p-4 align-top whitespace-pre-wrap text-muted-foreground leading-relaxed text-xs italic">
                                                {seg.original}
                                            </td>
                                            <td className="p-4 align-top text-xs text-muted-foreground whitespace-pre-wrap">
                                                {seg.narrative_role}
                                            </td>
                                            <td className="p-4 align-top text-xs text-indigo-300/80 bg-white/5 group-hover:bg-white/10 whitespace-pre-wrap">
                                                {seg.analysis}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {isSuperuser && (
                <div className="border-t border-white/10 bg-black/10 shrink-0">
                    <div className="px-6 py-3 border-b border-white/10">
                        <div className="text-sm text-primary uppercase font-extrabold tracking-wide">{t('AI 提炼与草稿区', 'Analysis Output Workspace')}</div>
                    </div>
                    <div className="space-y-0">
                        <div className="border-b border-white/10">
                            <div className="px-6 py-3 flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <div className="text-sm text-white uppercase font-bold tracking-wide">{t('场景列表', 'Scene List')}</div>
                                    <div className="text-[11px] text-muted-foreground mt-1">
                                        {t('场景数', 'Scene Count')}: <span className="font-mono text-white/80">{llmSceneCount}</span>
                                        <span className="ml-3">
                                            {t('Subjects 去重', 'Subjects Dedup')}: <span className="font-mono text-white/80">{llmSceneSubjectDedupStats.total}</span>
                                        </span>
                                        <span className="ml-3 font-mono text-white/70">{t('角色', 'C')} {llmSceneSubjectDedupStats.character}</span>
                                        <span className="ml-2 font-mono text-white/70">{t('场景', 'E')} {llmSceneSubjectDedupStats.environment}</span>
                                        <span className="ml-2 font-mono text-white/70">{t('道具', 'P')} {llmSceneSubjectDedupStats.prop}</span>
                                    </div>
                                    {analysisRuntimeMeta && (
                                        <div className="text-[10px] text-white/60 mt-1">
                                            {t('结束原因', 'Finish')}: {analysisRuntimeMeta.finishReason} · seg: {analysisRuntimeMeta.segmentsCount} · {t('最终不完整', 'Final incomplete')}: {analysisRuntimeMeta.incompleteAfterContinuation ? t('是', 'yes') : t('否', 'no')}
                                            {analysisRuntimeMeta.maxSegmentsStop ? ` · ${t('续写达到上限', 'Continuation hit max segments')}` : ''}
                                            {` · ${t('请求上限', 'Req cap')}: ${analysisRuntimeMeta.requestedCap}`}
                                            {` · ${t('完成token', 'Out tok')}: ${analysisRuntimeMeta.completionTokens}`}
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => {
                                            const textToCopy = llmMarkdownTableText || llmResultContent || '';
                                            navigator.clipboard.writeText(textToCopy);
                                            if (onLog) onLog(t('LLM 返回结果已复制到剪贴板。', 'LLM result copied to clipboard.'), 'success');
                                        }}
                                        className="px-3 py-1.5 rounded-md text-[10px] font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-white/80"
                                        title={t('复制当前 LLM 返回结果', 'Copy current LLM result')}
                                    >
                                        {t('复制', 'Copy')}
                                    </button>
                                </div>
                            </div>
                            <div className="h-[260px] sm:h-[320px] overflow-auto custom-scrollbar px-4 sm:px-6 pb-4 sm:pb-6">
                                {llmMarkdownTable ? (
                                    <table className="w-full text-left border-collapse text-xs font-mono min-w-[720px] sm:min-w-[900px]">
                                        <thead className="sticky top-0 z-10 bg-black/50 backdrop-blur-sm">
                                            <tr>
                                                {llmMarkdownTable.headers.map((header, idx) => (
                                                    <th key={idx} className="p-2 border-b border-white/10 font-medium text-muted-foreground whitespace-nowrap">{header}</th>
                                                ))}
                                                <th className="p-2 border-b border-white/10 font-medium text-muted-foreground whitespace-nowrap">{t('角色数', 'Characters')}</th>
                                                <th className="p-2 border-b border-white/10 font-medium text-muted-foreground whitespace-nowrap">{t('场景数', 'Environments')}</th>
                                                <th className="p-2 border-b border-white/10 font-medium text-muted-foreground whitespace-nowrap">{t('道具数', 'Props')}</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {llmMarkdownTable.rows.map((row, rowIdx) => (
                                                <tr key={rowIdx} className="hover:bg-white/5 transition-colors">
                                                    {llmMarkdownTable.headers.map((_, colIdx) => (
                                                        <td key={colIdx} className="p-1 align-top">
                                                            <textarea
                                                                className="w-full min-h-[34px] bg-transparent border border-transparent hover:border-white/10 focus:border-primary/40 rounded px-1.5 py-1 text-white/90 leading-relaxed focus:outline-none resize-y"
                                                                value={row[colIdx] || ''}
                                                                onChange={(e) => handleLlmCellChange(rowIdx, colIdx, e.target.value)}
                                                                onBlur={handlePersistLlmWorkspace}
                                                            />
                                                        </td>
                                                    ))}
                                                    <td className="p-2 align-top text-[11px] text-white/80 font-mono whitespace-nowrap" title={llmSceneSubjectStats[rowIdx]?.characterNames || ''}>
                                                        {llmSceneSubjectStats[rowIdx]?.characterCount ?? 0}
                                                    </td>
                                                    <td className="p-2 align-top text-[11px] text-white/80 font-mono whitespace-nowrap" title={llmSceneSubjectStats[rowIdx]?.environmentNames || ''}>
                                                        {llmSceneSubjectStats[rowIdx]?.environmentCount ?? 0}
                                                    </td>
                                                    <td className="p-2 align-top text-[11px] text-white/80 font-mono whitespace-nowrap" title={llmSceneSubjectStats[rowIdx]?.propNames || ''}>
                                                        {llmSceneSubjectStats[rowIdx]?.propCount ?? 0}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div className="text-xs text-muted-foreground pt-4">
                                        {t('未检测到可解析的 Markdown 表格。', 'No parseable Markdown table detected.')}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div>
                            <div className="px-6 py-3 flex flex-wrap items-center justify-between gap-3">
                                <div className="text-sm text-white uppercase font-bold tracking-wide">
                                    {t('实体列表', 'Entity List')}
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={handleImportEntities}
                                        disabled={isImportingEntities || isCheckingSubjectConsistency || isCheckingCoreCoverage}
                                        className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold border border-white/10 ${(isImportingEntities || isCheckingSubjectConsistency || isCheckingCoreCoverage) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/5 hover:bg-white/10 text-white/80'}`}
                                        title={t('导入第 3 部分：实体 JSON', 'Import Part 3: entities JSON')}
                                    >
                                        {isImportingEntities ? t('导入中...', 'Importing...') : t('导入实体', 'Import Entities')}
                                    </button>
                                    <button
                                        onClick={handleRunSubjectConsistencyCheck}
                                        disabled={isImportingEntities || isCheckingSubjectConsistency || isCheckingCoreCoverage}
                                        className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold border border-white/10 ${(isImportingEntities || isCheckingSubjectConsistency || isCheckingCoreCoverage) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/5 hover:bg-white/10 text-white/80'}`}
                                        title={t('检查 Markdown 表格中的 subject 与 JSON entities 是否一致', 'Check consistency between markdown subjects and JSON entities')}
                                    >
                                        {isCheckingSubjectConsistency ? t('检查中...', 'Checking...') : t('核对出场名单', 'Check Subject Consistency')}
                                    </button>
                                    <button
                                        onClick={runCoreCoverageCheck}
                                        disabled={isImportingEntities || isCheckingSubjectConsistency || isCheckingCoreCoverage}
                                        className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold border border-white/10 ${(isImportingEntities || isCheckingSubjectConsistency || isCheckingCoreCoverage) ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/5 hover:bg-white/10 text-white/80'}`}
                                        title={t('检查 Core Scene Info 是否覆盖原始剧本内容', 'Check whether Core Scene Info fully covers original script text')}
                                    >
                                        {isCheckingCoreCoverage ? t('校验中...', 'Checking...') : t('校验 Core 覆盖', 'Check Core Coverage')}
                                    </button>
                                </div>
                            </div>

                            {(workspaceOpStatus.running || workspaceOpStatus.message) && (
                                <div className="px-6 pb-3">
                                    <div className="rounded-lg border border-white/10 bg-black/20 p-2.5 text-xs">
                                        <div className="flex items-center justify-between gap-2 mb-1.5">
                                            <div className="flex items-center gap-2 text-white/90">
                                                {workspaceOpStatus.running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5 text-emerald-300" />}
                                                <span>{workspaceOpStatus.message}</span>
                                            </div>
                                            <span className="font-mono text-white/60">{Math.round(Number(workspaceOpStatus.progress || 0))}%</span>
                                        </div>
                                        <div className="h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
                                            <div className="h-full bg-primary transition-all duration-300" style={{ width: `${Math.round(Number(workspaceOpStatus.progress || 0))}%` }} />
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="px-6 pb-4 text-xs text-muted-foreground space-y-1">
                                <div>{t('实体总数', 'Total entities')}: {totalLlmEntityCount}</div>
                                <div>
                                    {t('Subjects 生成统计', 'Subject generation stats')}: 
                                    <span className="ml-1 font-mono text-white/80">{t('角色', 'Characters')} {subjectTypeGenerationStats.character.generated}/{subjectTypeGenerationStats.character.total}</span>
                                    <span className="ml-3 font-mono text-white/80">{t('场景', 'Environments')} {subjectTypeGenerationStats.environment.generated}/{subjectTypeGenerationStats.environment.total}</span>
                                    <span className="ml-3 font-mono text-white/80">{t('道具', 'Props')} {subjectTypeGenerationStats.prop.generated}/{subjectTypeGenerationStats.prop.total}</span>
                                </div>
                            </div>

                            {totalLlmEntityCount === 0 ? (
                                <div className="px-6 pb-6 text-xs text-muted-foreground">
                                    {t('未检测到可解析的实体 JSON（characters / environments / props）。', 'No parseable entities JSON detected (characters / environments / props).')}
                                </div>
                            ) : (
                                <div className="px-6 pb-6 grid grid-cols-1 xl:grid-cols-3 gap-4">
                                    {llmEntityGroups.map((group) => {
                                        const GroupIcon = group.icon;
                                        return (
                                            <div key={group.key} className="rounded-lg border border-white/10 bg-black/20 p-3">
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-white/90">
                                                        <GroupIcon size={14} className="text-primary" />
                                                        <span>{t(group.labelZh, group.labelEn)}</span>
                                                    </div>
                                                    <span className="text-[11px] text-muted-foreground font-mono">{group.items.length}</span>
                                                </div>
                                                <div className="space-y-1.5 max-h-56 overflow-auto custom-scrollbar pr-1">
                                                    {group.items.length === 0 ? (
                                                        <div className="text-[11px] text-muted-foreground">{t('暂无', 'Empty')}</div>
                                                    ) : group.items.map((item, idx) => (
                                                        (() => {
                                                            const dependencies = getEntityDependencies(item);
                                                            const hasDependencies = dependencies.length > 0;
                                                            const isCharacterGroup = group.key === 'character';
                                                            const dependencyPreview = dependencies.slice(0, 3).join(', ');
                                                            const dependencyMore = dependencies.length > 3 ? ` +${dependencies.length - 3}` : '';
                                                            return (
                                                        <button
                                                            key={`${group.key}-${idx}`}
                                                            type="button"
                                                            onClick={() => setJsonEntityDetailModal({
                                                                open: true,
                                                                groupKey: group.key,
                                                                groupLabelZh: group.labelZh,
                                                                groupLabelEn: group.labelEn,
                                                                item,
                                                            })}
                                                            className={`w-full text-left rounded-md border px-2.5 py-2 hover:bg-white/10 transition-colors ${hasDependencies ? (isCharacterGroup ? 'border-amber-400/40 bg-amber-500/10' : 'border-sky-400/30 bg-sky-500/10') : 'border-white/10 bg-white/5'}`}
                                                            title={t('查看完整 JSON', 'View full JSON')}
                                                        >
                                                            <div className="flex items-center justify-between gap-2">
                                                                <div className="text-xs font-semibold text-white/90 truncate" title={item?.name || item?.name_en || ''}>
                                                                    {item?.name || item?.name_en || t('未命名', 'Unnamed')}
                                                                </div>
                                                                {hasDependencies && (
                                                                    <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border ${isCharacterGroup ? 'border-amber-300/40 text-amber-200 bg-amber-500/20' : 'border-sky-300/40 text-sky-200 bg-sky-500/20'}`}>
                                                                        <LinkIcon size={10} />
                                                                        {isCharacterGroup ? t('角色依赖', 'Role Dependency') : t('有依赖', 'Has Dependency')}
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <div className="text-[11px] text-white/55 mt-0.5 line-clamp-2">
                                                                {String(item?.description || item?.narrative_description || item?.anchor_description || '').trim() || t('无描述', 'No description')}
                                                            </div>
                                                            {hasDependencies && (
                                                                <div className="text-[10px] mt-1 text-white/75 line-clamp-2" title={dependencies.join(', ')}>
                                                                    {t('依赖', 'Depends on')}: {dependencyPreview}{dependencyMore}
                                                                </div>
                                                            )}
                                                        </button>
                                                            );
                                                        })()
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            <div className="px-6 pb-2 text-[10px] text-muted-foreground uppercase font-bold tracking-wide">{t('第一次调用 LLM 原文（场景解构）', 'Phase 1 LLM Raw Response')}</div>
                            <textarea
                                className="w-full h-44 px-6 pb-6 bg-transparent text-white/70 font-mono text-[11px] leading-relaxed focus:outline-none custom-scrollbar resize-none border-t border-white/5"
                                placeholder={t('第一次 LLM 返回的剧本解构数据会显示在这里。', 'Phase 1 LLM response text is shown here.')}
                                value={llmRawResultContent || ''}
                                onChange={(e) => handleLlmRawContentChange(e.target.value)}
                                onBlur={handleSaveLlmRawContent}
                            />

                            <div className="px-6 pb-2 pt-2 text-[10px] text-muted-foreground uppercase font-bold tracking-wide">{t('第二次调用 LLM 原文（实体资产）', 'Phase 2 LLM Asset Generation Response')}</div>
                            <textarea
                                className="w-full h-44 px-6 pb-6 bg-transparent text-amber-100/70 font-mono text-[11px] leading-relaxed focus:outline-none custom-scrollbar resize-none border-t border-white/5"
                                placeholder={t('第二次 LLM 返回的实体补充生成数据会显示在这里。', 'Phase 2 LLM asset generation response text is shown here.')}
                                value={llmAssetRawResultContent || ''}
                                onChange={(e) => setLlmAssetRawResultContent(e.target.value)}
                            />

                            <div className="rounded-lg border border-white/10 bg-black/20 p-4 mt-4">
                                <div className="font-bold text-white/90 text-sm mb-3 flex items-center gap-2">
                                    📋 {t('Phase 1 Subject Index', 'Phase 1 Subject Index')}
                                </div>
                                <div className="space-y-3">
                                    <textarea 
                                        className="w-full h-32 p-3 bg-black/30 border border-white/10 rounded-md text-white/80 font-mono text-xs resize-none focus:outline-none focus:border-white/20"
                                        value={subjectIndexText}
                                        onChange={(e) => {
                                            if (isEditingSubjectIndex) {
                                                setSubjectIndexText(e.target.value);
                                            }
                                        }}
                                        readOnly={!isEditingSubjectIndex}
                                        placeholder={t('在这里粘贴或编辑 Subject Index 用于第二阶段...', 'Paste or edit Subject Index here for Phase 2...')}
                                    />
                                    <div className="flex gap-2">
                                        <button
                                                onClick={() => setIsEditingSubjectIndex(!isEditingSubjectIndex)}
                                                className="px-3 py-1.5 rounded-md text-xs font-semibold bg-blue-500/20 hover:bg-blue-500/30 border border-blue-400/50 text-blue-300"
                                            >
                                                {isEditingSubjectIndex ? t('完成编辑', 'Done') : t('修改', 'Edit')}
                                            </button>
                                            {isEditingSubjectIndex && (
                                                <button
                                                    onClick={async () => {
                                                        try {
                                                            await updateEpisode(activeEpisode.id, { 
                                                                ai_scene_analysis_subject_index: subjectIndexText 
                                                            });
                                                            onLog?.('Subject Index saved successfully');
                                                            setIsEditingSubjectIndex(false);
                                                        } catch (error) {
                                                            onLog?.(`Failed to save Subject Index: ${error.message}`);
                                                        }
                                                    }}
                                                    className="px-3 py-1.5 rounded-md text-xs font-semibold bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/50 text-emerald-300"
                                                >
                                                    {t('保存', 'Save')}
                                                </button>
                                            )}
                                            <button
                                                onClick={handleRetryPhase2}
                                                disabled={isRetryingPhase2}
                                                className="px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/50 text-amber-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                            >
                                                {isRetryingPhase2 ? (
                                                    <>
                                                        <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
                                                        {t('正在重试...', 'Retrying...')}
                                                    </>
                                                ) : (
                                                    <>
                                                        <RefreshCw className="w-3 h-3 flex-shrink-0" />
                                                        {t('重试第二阶段(资产生成)', 'Retry Phase 2')}
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                        </div>
                    </div>
                </div>
                )}


            </div>

            {jsonEntityDetailModal.open && (
                <div
                    className="fixed inset-0 z-[58] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
                    onClick={() => setJsonEntityDetailModal({ open: false, groupKey: '', groupLabelZh: '', groupLabelEn: '', item: null })}
                >
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-3xl max-h-[80vh] shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Info className="w-5 h-5 text-primary" />
                                {t('实体 JSON 详情', 'Entity JSON Details')}
                                <span className="text-xs font-normal text-muted-foreground">
                                    {t(jsonEntityDetailModal.groupLabelZh, jsonEntityDetailModal.groupLabelEn)}
                                </span>
                            </h3>
                            <button
                                onClick={() => setJsonEntityDetailModal({ open: false, groupKey: '', groupLabelZh: '', groupLabelEn: '', item: null })}
                                className="p-1 rounded hover:bg-white/10 text-white/80"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="p-4">
                            <pre className="max-h-[60vh] overflow-auto custom-scrollbar rounded-lg border border-white/10 bg-black/30 p-4 text-xs text-white/85 font-mono leading-relaxed whitespace-pre-wrap break-words">
{JSON.stringify(jsonEntityDetailModal.item || {}, null, 2)}
                            </pre>
                        </div>
                    </div>
                </div>
            )}

            {postAnalysisCheckModal.open && (
                <div
                    className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
                    onClick={() => {
                        if (postAnalysisCheckModal.status !== 'running') {
                            closePostAnalysisCheckModal();
                        }
                    }}
                >
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-3xl shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                {postAnalysisCheckModal.status === 'running' ? (
                                    <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
                                ) : (
                                    <Info className="w-5 h-5 text-sky-300" />
                                )}
                                {t('剧本角色与场景盘点单', 'AI Script Analysis Subject Check Result')}
                            </h3>
                            <button
                                onClick={closePostAnalysisCheckModal}
                                className={`p-1 rounded-lg transition-colors ${postAnalysisCheckModal.status === 'running' ? 'text-white/30 cursor-not-allowed' : 'hover:bg-white/10 text-white/80'}`}
                                disabled={postAnalysisCheckModal.status === 'running'}
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-4 space-y-3 text-sm">
                            <div className="text-white/90">{postAnalysisCheckModal.message}</div>

                            {Array.isArray(postAnalysisCheckModal.guidance) && postAnalysisCheckModal.guidance.length > 0 && (
                                <div className="rounded-md border border-sky-500/20 bg-sky-500/10 px-3 py-2 text-xs text-sky-100 space-y-1">
                                    {postAnalysisCheckModal.guidance.map((tip, idx) => (
                                        <div key={`guidance-${idx}`}>• {tip}</div>
                                    ))}
                                </div>
                            )}

                            <div className={`rounded-md border px-3 py-2 ${subjectConsistencyReport?.ok ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-amber-500/30 bg-amber-500/10 text-amber-200'}`}>
                                <div className="font-semibold">{t('Check Subject Consistency', 'Check Subject Consistency')}</div>
                                <div className="mt-1 text-xs text-white/80">
                                    {subjectConsistencyReport?.message || t('等待结果...', 'Waiting for result...')}
                                </div>
                                {subjectConsistencyReport?.missing?.length > 0 && (
                                    <div className="mt-1 text-xs">
                                        {t('缺失：', 'Missing: ')}{subjectConsistencyReport.missing.join(', ')}
                                    </div>
                                )}
                            </div>

                            <div className="text-xs text-muted-foreground">
                                {t('请先核对上方的盘点单，确认无误后就可以关掉窗口继续啦。', 'Please review the subject check result above, then close this dialog to continue.')}
                            </div>
                        </div>

                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                            {postAnalysisCheckModal.status === 'done' && subjectConsistencyReport && !subjectConsistencyReport.ok && (
                                <button
                                    onClick={handlePostCheckRerunAnalysis}
                                    className="px-4 py-2 rounded-lg text-sm font-bold bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-500/30"
                                    title={t('建议重跑 AI Script Analysis', 'Recommended: rerun AI Script Analysis')}
                                >
                                    {t('调整后重新生成', 'Rerun Analysis')}
                                </button>
                            )}
                            <button
                                onClick={closePostAnalysisCheckModal}
                                disabled={postAnalysisCheckModal.status === 'running'}
                                className={`px-4 py-2 rounded-lg text-sm font-bold ${postAnalysisCheckModal.status === 'running' ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                            >
                                {t('关闭并继续', 'Close and Continue')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {showAnalysisModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm" onClick={() => {
                    if (phase2ResolverRef.current) {
                        phase2ResolverRef.current(false);
                        phase2ResolverRef.current = null;
                    }
                    setShowAnalysisModal(false);
                }}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-6xl h-[90vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Wand2 className="w-5 h-5 text-purple-500" />
                                {phase2ResolverRef.current ? "Asset Generation Prompt Preview (Superuser)" : "Advanced AI Analysis (Superuser)"}
                            </h3>
                            <button onClick={() => {
                                if (phase2ResolverRef.current) {
                                    phase2ResolverRef.current(false);
                                    phase2ResolverRef.current = null;
                                }
                                setShowAnalysisModal(false);
                            }} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        
                        <div className="flex-1 p-3 sm:p-6 grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 overflow-hidden">
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    System Prompt
                                    <span className="text-xs font-normal opacity-70">{t('定义 AI 角色与规则', 'Define the AI persona & rules')}</span>
                                </label>
                                <textarea
                                    className="flex-1 w-full bg-black/30 border border-white/10 text-white/90 p-3 font-mono text-xs leading-relaxed rounded-lg focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                    value={systemPrompt}
                                    onChange={(e) => setSystemPrompt(e.target.value)}
                                    spellCheck={false}
                                />
                            </div>
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    User Input (Script)
                                    <span className="text-xs font-normal opacity-70">{t('需要处理的内容', 'The content to act upon')}</span>
                                </label>
                                <textarea
                                    className="flex-1 w-full bg-black/30 border border-white/10 text-white/90 p-3 font-mono text-sm leading-relaxed rounded-lg focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                    value={userPrompt}
                                    onChange={(e) => setUserPrompt(e.target.value)}
                                    spellCheck={false}
                                />
                            </div>
                        </div>
                        
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                            {isAnalyzing && (
                                <button
                                    onClick={handleStopAnalysisTask}
                                    disabled={isStoppingAnalysisTask}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors border ${isStoppingAnalysisTask ? 'bg-white/5 text-muted-foreground border-white/10 cursor-not-allowed' : 'bg-red-500/20 hover:bg-red-500/30 text-red-100 border-red-400/40'}`}
                                >
                                    {isStoppingAnalysisTask ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                                    {isStoppingAnalysisTask ? t('停止中...', 'Stopping...') : t('停止任务', 'Stop Task')}
                                </button>
                            )}
                             <button
                                onClick={() => {
                                    const fullText = `[System Instruction]\n${systemPrompt}\n\n[User Input]\n${userPrompt}`;
                                    navigator.clipboard.writeText(fullText);
                                    if(onLog) onLog(t('完整提示词已复制到剪贴板。', 'Copied full prompt to clipboard.'));
                                    alert(t('完整提示词已复制！', 'Full prompt copied!'));
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg font-medium transition-colors text-white border border-white/10"
                             >
                                <Copy className="w-4 h-4" /> {t('复制完整提示词', 'Copy Full Prompt')}
                             </button>
                             <button 
                                          onClick={() => {
                                              if (phase2ResolverRef.current) {
                                                  const resolver = phase2ResolverRef.current;
                                                  phase2ResolverRef.current = null;
                                                  resolver({ systemPrompt, userPrompt });
                                              } else {
                                                  executeAdvancedAnalysis(userPrompt, systemPrompt);
                                              }
                                              setShowAnalysisModal(false);
                                          }}
                                disabled={isAnalyzing && !phase2ResolverRef.current}
                                className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                             >
                                {(isAnalyzing && !phase2ResolverRef.current) ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                                          {phase2ResolverRef.current ? t('确认并继续', 'Confirm & Continue') : t('开始提取场景', 'Run Analysis')}
                             </button>
                        </div>
                    </div>
                </div>
            )}

            {subjectRecoveryModal.open && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
                    onClick={() => {
                        if (subjectRecoveryModal.status !== 'running') {
                            setSubjectRecoveryModal(prev => ({ ...prev, open: false }));
                        }
                    }}
                >
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                {subjectRecoveryModal.status === 'running' ? (
                                    <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
                                ) : subjectRecoveryModal.status === 'success' ? (
                                    <CheckCircle className="w-5 h-5 text-emerald-400" />
                                ) : (
                                    <Info className="w-5 h-5 text-amber-300" />
                                )}
                                {t('Subject 自动补全', 'Subject Auto Recovery')}
                            </h3>
                            <button
                                onClick={() => {
                                    if (subjectRecoveryModal.status !== 'running') {
                                        setSubjectRecoveryModal(prev => ({ ...prev, open: false }));
                                    }
                                }}
                                className={`p-1 rounded-lg transition-colors ${subjectRecoveryModal.status === 'running' ? 'text-white/30 cursor-not-allowed' : 'hover:bg-white/10 text-white/80'}`}
                                disabled={subjectRecoveryModal.status === 'running'}
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="p-4 space-y-3 text-sm">
                            <div className="text-white/90">{subjectRecoveryModal.message}</div>
                            {Array.isArray(subjectRecoveryModal.missing) && subjectRecoveryModal.missing.length > 0 && (
                                <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                                    {t('缺失 Subject：', 'Missing subjects:')} {subjectRecoveryModal.missing.join(', ')}
                                </div>
                            )}
                            {subjectRecoveryModal.details && (
                                <div className="text-xs text-white/70 bg-white/5 border border-white/10 rounded-md px-3 py-2 whitespace-pre-wrap">
                                    {subjectRecoveryModal.details}
                                </div>
                            )}
                        </div>
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                            <button
                                onClick={() => setSubjectRecoveryModal(prev => ({ ...prev, open: false }))}
                                disabled={subjectRecoveryModal.status === 'running'}
                                className={`px-4 py-2 rounded-lg text-sm font-bold ${subjectRecoveryModal.status === 'running' ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                            >
                                {t('关闭', 'Close')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {showMerged && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setShowMerged(false)}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <ScrollText className="w-5 h-5 text-primary" />
                                Merged Script
                            </h3>
                            <button onClick={() => setShowMerged(false)} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="flex-1 p-4 sm:p-6 overflow-hidden">
                            <textarea
                                className="w-full h-full bg-black/30 border border-white/10 text-white p-3 sm:p-4 font-serif text-base sm:text-lg leading-relaxed rounded-lg focus:outline-none focus:border-primary/50 resize-none custom-scrollbar"
                                value={mergedContent}
                                readOnly
                            />
                        </div>
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                             <button 
                                onClick={() => {
                                    navigator.clipboard.writeText(mergedContent);
                                    alert("Script copied to clipboard!");
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors text-white"
                             >
                                <Copy className="w-4 h-4" /> Copy to Clipboard
                             </button>
                             <button 
                                onClick={() => setShowMerged(false)}
                                className="px-4 py-2 bg-primary text-black rounded-lg font-bold hover:bg-primary/90"
                             >
                                Close
                             </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

