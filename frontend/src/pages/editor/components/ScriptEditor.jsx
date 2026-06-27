
import FunctionApiSelector from '../../../components/FunctionApiSelector';
import { useFunctionApis } from '../../../components/useFunctionApis';
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useLog } from '../../../context/LogContext';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../../../lib/store';
import LogPanel from '../../../components/LogPanel';
import LLMResultPanel from './LLMResultPanel';
import ProjectStatusBar from '../../../components/ProjectStatusBar';
import { Briefcase, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles, Square, CheckSquare, MoreHorizontal, Crop, Unlink, PanelsTopLeft, AlertTriangle, Bot } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL, ASSET_BASE_URL } from '../../../config';
import { setUiLang as setGlobalUiLang } from '../../../lib/uiLang';
import { getEpisodeAnalysisRun, releaseEpisodeAnalysisRun, trackEpisodeAnalysisRun, updateEpisodeAnalysisRun } from '../../../lib/analysisRunRegistry';

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
    fetchEpisode, 
    createEpisode, 
    updateEpisode,
    updateEpisodeSegments,
    deleteEpisode,
    fetchScenes, 
    createScene,
    updateScene, 
    deleteScene,
    purgeEpisodeScenes,
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
    isAsyncTaskPollInFlight,
    api,
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
    getSceneAnalysisFlowRegistry,
    runScriptAnalysisFlowAnalyzeNode,
    getCachedUserPreferences,
    fetchProjectSubjectInventoryPrompt,
    recomputeEpisodeCostEstimation,
    syncSceneUnitsProgress,
    resetSceneOrchestrationProgress,
    getEpisodeProgressSnapshot,
} from '../../../services/api';
import { entityNameAppearsInText, entityTokenMatchesName, normalizeEntityToken } from '../../../lib/entityToken';

const SCENE_ORCHESTRATION_PHASE_LOG_TYPES = {
    queued: 'info',
    llm_submit: 'process',
    llm_returned: 'info',
    importing: 'process',
    imported: 'success',
    failed: 'error',
};

const deriveSceneOrchestrationPhase = (unit) => {
    if (!unit) return 'unknown';
    const explicit = String(unit.orchestration_phase || '').trim().toLowerCase();
    if (explicit) return explicit;
    const importStatus = String(unit.import_status || '').trim().toLowerCase();
    const parseStatus = String(unit.parse_status || '').trim().toLowerCase();
    if (importStatus === 'success') return 'imported';
    if (importStatus === 'importing') return 'importing';
    if (importStatus === 'llm_returned') return 'llm_returned';
    if (importStatus === 'llm_running' || importStatus === 'running') return 'llm_submit';
    if (importStatus === 'failed' || parseStatus === 'failed') return 'failed';
    if (importStatus === 'queued') return 'queued';
    return importStatus || 'unknown';
};

const buildSceneOrchestrationPhaseMessage = (sceneId, phase, { sceneOrder, totalScenes, errorCode, t }) => {
    const orderLabel = sceneOrder && totalScenes ? ` (${sceneOrder}/${totalScenes})` : '';
    switch (phase) {
        case 'llm_submit':
            return t(
                `[场景编排] ${sceneId}${orderLabel} 已提交 LLM，等待返回...`,
                `[Scene beats] ${sceneId}${orderLabel} submitted to LLM, waiting for response...`
            );
        case 'llm_returned':
            return t(
                `[场景编排] ${sceneId}${orderLabel} LLM 已返回，校验通过`,
                `[Scene beats] ${sceneId}${orderLabel} LLM returned and passed validation`
            );
        case 'importing':
            return t(
                `[场景编排] ${sceneId}${orderLabel} 正在导入工作区...`,
                `[Scene beats] ${sceneId}${orderLabel} importing into workspace...`
            );
        case 'imported':
            return t(
                `[场景编排] ${sceneId}${orderLabel} 导入完成`,
                `[Scene beats] ${sceneId}${orderLabel} import completed`
            );
        case 'failed':
            return t(
                `[场景编排] ${sceneId}${orderLabel} 失败${errorCode ? `：${errorCode}` : ''}`,
                `[Scene beats] ${sceneId}${orderLabel} failed${errorCode ? `: ${errorCode}` : ''}`
            );
        default:
            return '';
    }
};

const createSceneOrchestrationProgressPoller = ({
    getSnapshot,
    episodeId,
    sceneUnits,
    onPhase,
    intervalMs = 2000,
}) => {
    const reportedByScene = new Map();
    let stopped = false;
    const totalScenes = Array.isArray(sceneUnits) ? sceneUnits.length : 0;

    const pollOnce = async () => {
        if (stopped || !episodeId) return;
        try {
            const snapshot = await getSnapshot(episodeId);
            const rows = Array.isArray(snapshot?.scene_units) ? snapshot.scene_units : [];
            const byId = Object.fromEntries(
                rows.map((row) => [String(row.scene_id || '').trim(), row]).filter(([sceneId]) => sceneId)
            );
            for (const unit of sceneUnits || []) {
                const sceneId = String(unit?.sceneId || unit?.scene_id || '').trim();
                if (!sceneId) continue;
                const row = byId[sceneId];
                if (!row) continue;
                const phase = deriveSceneOrchestrationPhase(row);
                const reported = reportedByScene.get(sceneId) || new Set();
                if (reported.has(phase)) continue;
                reported.add(phase);
                reportedByScene.set(sceneId, reported);
                onPhase({
                    sceneId,
                    phase,
                    sceneOrder: row.scene_order ?? unit?.sceneOrder,
                    totalScenes,
                    errorCode: row.parse_error_code,
                });
            }
        } catch (_) {
            // polling is best-effort
        }
    };

    const timer = setInterval(pollOnce, intervalMs);
    pollOnce();
    return () => {
        stopped = true;
        clearInterval(timer);
    };
};

/** Max automatic fallback reruns for scene beats / asset generation (excluding the initial run). */
const MAX_ANALYSIS_FALLBACK_ATTEMPTS = 2;


const TERMINAL_ASYNC_TASK_STATUSES = new Set([
    'completed', 'success', 'succeeded', 'done', 'finished',
    'failed', 'error', 'timeout', 'canceled', 'cancelled', 'stopped',
]);

const peekAsyncTaskTerminalStatus = async (taskId) => {
    const id = String(taskId || '').trim();
    if (!id) return null;
    try {
        const res = await api.get(`/tasks/${id}`, { params: { _ts: Date.now() }, timeout: 15000 });
        const status = String(res?.data?.status || '').trim().toLowerCase();
        return TERMINAL_ASYNC_TASK_STATUSES.has(status) ? status : null;
    } catch (error) {
        const status = Number(error?.response?.status || 0);
        const detail = String(error?.response?.data?.detail || error?.message || '').trim().toLowerCase();
        if (status === 404 || detail.includes('task not found') || detail.includes('not found')) {
            return 'not_found';
        }
        return null;
    }
};

const isEpisodeAnalysisTaskLive = (episodeId, {
    loadAnalysisTaskMarker,
    isAnalyzing = false,
    isRetryingPhase2 = false,
    analysisRunInFlight = false,
    analysisResumeInFlight = false,
    phase2GenerationInFlight = false,
} = {}) => {
    const id = Number(episodeId || 0);
    if (!id) return false;

    if (isAnalyzing || isRetryingPhase2) return true;
    if (analysisRunInFlight || analysisResumeInFlight || phase2GenerationInFlight) return true;

    const marker = typeof loadAnalysisTaskMarker === 'function' ? loadAnalysisTaskMarker(id) : null;
    const markerTaskId = String(marker?.taskId || '').trim();
    if (markerTaskId && isAsyncTaskPollInFlight(markerTaskId)) return true;

    const activeRun = getEpisodeAnalysisRun(id);
    const runTaskId = String(activeRun?.taskId || markerTaskId || '').trim();
    if (activeRun?.promise && runTaskId && isAsyncTaskPollInFlight(runTaskId)) return true;

    return false;
};

const firstPositiveFiniteNumber = (...values) => {
    for (const value of values) {
        const numberValue = Number(value);
        if (Number.isFinite(numberValue) && numberValue > 0) return numberValue;
    }
    return 0;
};

const resolveCompletenessStatus = (analysisCount, importedCount) => {
    const expected = Number(analysisCount || 0);
    const actual = Number(importedCount || 0);
    if (expected <= 0 && actual <= 0) return 'none';
    if (expected <= 0 && actual > 0) return 'extra';
    if (actual >= expected) return 'ok';
    if (actual > 0) return 'partial';
    return 'missing';
};

const syncScenePostImportCheckedCount = (importReport, postImportSceneSubjectReport) => {
    const importedRows = Array.isArray(importReport?.importedSceneRows) ? importReport.importedSceneRows.length : 0;
    const importStatsTotal = Number(importReport?.importStats?.scenesCreated || 0) + Number(importReport?.importStats?.scenesUpdated || 0);
    const resolvedCheckedSceneCount = firstPositiveFiniteNumber(
        importedRows,
        importStatsTotal,
        importReport?.dbPersistedCounts?.scenes?.currentEpisode,
        postImportSceneSubjectReport?.checkedSceneCount,
    );
    if (!postImportSceneSubjectReport || typeof postImportSceneSubjectReport !== 'object') {
        return resolvedCheckedSceneCount > 0 ? { checkedSceneCount: resolvedCheckedSceneCount } : postImportSceneSubjectReport;
    }
    return {
        ...postImportSceneSubjectReport,
        checkedSceneCount: resolvedCheckedSceneCount,
    };
};

const resolveImportReportSceneCount = (importReport, scenePostReport, dbSceneCount = null) => firstPositiveFiniteNumber(
    dbSceneCount,
    importReport?.dbPersistedCounts?.scenes?.currentEpisode,
    Array.isArray(importReport?.importedSceneRows) ? importReport.importedSceneRows.length : null,
    (Number(importReport?.importStats?.scenesCreated || 0) + Number(importReport?.importStats?.scenesUpdated || 0)) || null,
    importReport?.importStats?.scenesCreated,
    importReport?.dbRunInsertedCounts?.scenes?.created,
    scenePostReport?.checkedSceneCount,
);

const normalizeAssetReportType = (value) => {
    const key = String(value || '').trim().toLowerCase();
    if (['character', 'characters', 'role', 'roles', '人物', '角色'].includes(key)) return 'character';
    if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(key)) return 'prop';
    if (['environment', 'environments', 'env', 'scene', 'scenes', '空镜', '场景', '环境'].includes(key)) return 'environment';
    if (['poster', 'posters', 'cover', 'covers', 'cover_poster', '海报', '封面'].includes(key)) return 'poster';
    return key;
};

const toPositiveCount = (value) => {
    const count = Number(value);
    return Number.isFinite(count) && count > 0 ? count : 0;
};

const countAssetItemsByType = (items, type) => {
    if (!Array.isArray(items)) return 0;
    return items.reduce((count, item) => (
        count + (normalizeAssetReportType(item?.type || item?.entity_type || item?.subject_type) === type ? 1 : 0)
    ), 0);
};

const resolveImportReportAssetInsertedCount = (importReport, type) => {
    const scenePostReport = importReport?.sceneSubjectPostImportReport || {};
    const supplementReport = scenePostReport?.supplementReport || {};
    return Math.max(
        toPositiveCount(importReport?.dbRunInsertedCounts?.entities?.[type]),
        toPositiveCount(importReport?.importedSubjectCounts?.[type]),
        toPositiveCount(scenePostReport?.importedSubjectCounts?.[type]),
        toPositiveCount(supplementReport?.countsByType?.[type]),
        countAssetItemsByType(importReport?.createdSubjectItems, type),
        countAssetItemsByType(supplementReport?.createdItems, type),
    );
};

const resolveImportReportAssetSkippedCount = (importReport, type) => {
    const scenePostReport = importReport?.sceneSubjectPostImportReport || {};
    const supplementReport = scenePostReport?.supplementReport || {};
    return Math.max(
        countAssetItemsByType(importReport?.skippedSubjectItems, type),
        countAssetItemsByType(supplementReport?.skippedItems, type),
    );
};

const ASSET_CATEGORY_SUBTASK_KEYS = {
    characters: ['characters', 'character'],
    props: ['props', 'prop'],
    environments: ['environments', 'environment'],
    posters: ['posters', 'poster', 'covers', 'cover', 'environments', 'environment'],
};

const isAssetCategorySatisfiedBySubtaskReports = (subtaskReports, categoryKey) => {
    const aliases = ASSET_CATEGORY_SUBTASK_KEYS[String(categoryKey || '').trim()] || [String(categoryKey || '').trim().toLowerCase()];
    if (!Array.isArray(subtaskReports) || subtaskReports.length === 0) return false;
    return subtaskReports.some((report) => {
        const reportKey = String(report?.key || '').trim().toLowerCase();
        if (!aliases.includes(reportKey)) return false;
        const status = String(report?.status || '').trim().toLowerCase();
        if (status !== 'ok') return false;
        return Number(report?.created || 0) + Number(report?.skipped || 0) > 0;
    });
};

const resolveSubtaskImportHandledCount = (scenePostReport, categoryKey = '') => {
    const subtaskReports = Array.isArray(scenePostReport?.subtaskReports) ? scenePostReport.subtaskReports : [];
    const aliases = ASSET_CATEGORY_SUBTASK_KEYS[String(categoryKey || '').trim()] || [String(categoryKey || '').trim().toLowerCase()];
    return subtaskReports.reduce((sum, report) => {
        const reportKey = String(report?.key || '').trim().toLowerCase();
        if (!aliases.includes(reportKey)) return sum;
        return sum + toPositiveCount(report?.created) + toPositiveCount(report?.skipped);
    }, 0);
};

const resolveImportReportAssetHandledCount = (importReport, type, categoryKey = '') => {
    const scenePostReport = importReport?.sceneSubjectPostImportReport || {};
    const supplementReport = scenePostReport?.supplementReport || {};
    const inserted = resolveImportReportAssetInsertedCount(importReport, type);
    const skipped = resolveImportReportAssetSkippedCount(importReport, type);
    const subtaskHandled = categoryKey ? resolveSubtaskImportHandledCount(scenePostReport, categoryKey) : 0;
    const supplementHandled = countAssetItemsByType(supplementReport?.createdItems, type)
        + countAssetItemsByType(supplementReport?.skippedItems, type);
    return Math.max(
        inserted,
        skipped,
        inserted + skipped,
        subtaskHandled,
        supplementHandled,
        toPositiveCount(importReport?.dbPersistedCounts?.entities?.[type]),
        toPositiveCount(scenePostReport?.importedSubjectCounts?.[type]),
    );
};

const resolveWorkflowImportReport = (analysisUiReport, episodeId) => {
    if (analysisUiReport?.importReport && typeof analysisUiReport.importReport === 'object') {
        return analysisUiReport.importReport;
    }
    const snapshot = loadAnalysisSessionSnapshot(episodeId);
    const persistedReport = snapshot?.progressUi?.uiReport?.importReport;
    if (persistedReport && typeof persistedReport === 'object') {
        return persistedReport;
    }
    return {};
};

const collectEntityPayloadNameCandidates = (item = {}) => {
    const names = [
        item?.subject_name_exact,
        item?.subject_name_zh,
        item?.subject_name,
        item?.name,
        item?.name_zh,
        item?.name_en,
    ]
        .map((value) => String(value || '').trim())
        .filter(Boolean);
    return Array.from(new Set(names));
};

const countEntityPayloadItemsCoveredInDb = (items, entityType, dbEntities) => {
    if (!Array.isArray(items) || items.length === 0) return 0;
    const normalizedType = normalizeAssetReportType(entityType);
    const entities = (Array.isArray(dbEntities) ? dbEntities : []).filter(
        (entity) => normalizeAssetReportType(entity?.type) === normalizedType
    );
    if (entities.length === 0) return 0;
    return items.reduce((count, item) => {
        const names = collectEntityPayloadNameCandidates(item);
        if (!names.length) return count;
        const matched = entities.some((entity) => (
            names.some((name) => entityTokenMatchesName(entity, name))
        ));
        return count + (matched ? 1 : 0);
    }, 0);
};

const countDbEntitiesByType = (entityType, dbEntities) => {
    const normalizedType = normalizeAssetReportType(entityType);
    return (Array.isArray(dbEntities) ? dbEntities : []).filter(
        (entity) => normalizeAssetReportType(entity?.type) === normalizedType,
    ).length;
};

const countSubjectIndexEntriesCoveredInDb = (entries, entityType, dbEntities) => {
    if (!Array.isArray(entries) || entries.length === 0) return 0;
    const normalizedType = normalizeAssetReportType(entityType);
    const entities = (Array.isArray(dbEntities) ? dbEntities : []).filter(
        (entity) => normalizeAssetReportType(entity?.type) === normalizedType
    );
    if (entities.length === 0) return 0;
    return entries.reduce((count, entry) => {
        const rawName = String(entry?.name || '').trim();
        if (!rawName) return count;
        const nameCandidates = rawName
            .split(/\s*\/\s*/)
            .map((part) => String(part || '').trim())
            .filter(Boolean);
        if (!nameCandidates.includes(rawName)) nameCandidates.unshift(rawName);
        const matched = entities.some((entity) => (
            nameCandidates.some((candidate) => entityTokenMatchesName(entity, candidate))
            || entityTokenMatchesName(entity, rawName)
        ));
        return count + (matched ? 1 : 0);
    }, 0);
};

const buildCompletedAnalysisUiReport = (payload = {}) => {
    const importReport = (payload?.importReport && typeof payload.importReport === 'object')
        ? payload.importReport
        : null;
    const scenePostReport = importReport?.sceneSubjectPostImportReport;
    const resolvedSceneImportCount = importReport
        ? resolveImportReportSceneCount(importReport, scenePostReport, null)
        : 0;
    const subtaskReports = Array.isArray(scenePostReport?.subtaskReports) ? scenePostReport.subtaskReports : [];
    const resolvedAssetHandledCounts = importReport
        ? {
            character: resolveImportReportAssetHandledCount(importReport, 'character', 'characters'),
            prop: resolveImportReportAssetHandledCount(importReport, 'prop', 'props'),
            environment: resolveImportReportAssetHandledCount(importReport, 'environment', 'environments'),
            poster: resolveImportReportAssetHandledCount(importReport, 'poster', 'posters'),
        }
        : null;
    const stage3SubtasksOk = subtaskReports.length > 0
        && subtaskReports.every((report) => String(report?.status || '').trim().toLowerCase() === 'ok');
    return {
        ...payload,
        resolvedSceneImportCount,
        resolvedAssetHandledCounts,
        stage3SubtasksOk,
    };
};

const fetchEpisodeSceneCountWithRetry = async (fetchScenesFn, episodeId, { retries = 3, delayMs = 400 } = {}) => {
    const id = Number(episodeId || 0);
    if (!id || typeof fetchScenesFn !== 'function') return 0;
    for (let attempt = 0; attempt < retries; attempt += 1) {
        const scenes = await fetchScenesFn(id).catch(() => []);
        const count = Array.isArray(scenes) ? scenes.length : 0;
        if (count > 0) return count;
        if (attempt < retries - 1) {
            await new Promise((resolve) => setTimeout(resolve, delayMs));
        }
    }
    return 0;
};

const waitForEpisodeSceneCount = async (
    fetchScenesFn,
    episodeId,
    minCount,
    { retries = 15, delayMs = 600 } = {},
) => {
    const expected = Math.max(0, Number(minCount) || 0);
    const id = Number(episodeId || 0);
    if (!id || expected <= 0 || typeof fetchScenesFn !== 'function') {
        return 0;
    }
    let lastCount = 0;
    for (let attempt = 0; attempt < retries; attempt += 1) {
        const scenes = await fetchScenesFn(id).catch(() => []);
        lastCount = Array.isArray(scenes) ? scenes.length : 0;
        if (lastCount >= expected) {
            return lastCount;
        }
        if (attempt < retries - 1) {
            await new Promise((resolve) => setTimeout(resolve, delayMs));
        }
    }
    return lastCount;
};

const mergeSceneImportReports = (reports = []) => {
    const validReports = (Array.isArray(reports) ? reports : []).filter((item) => item && typeof item === 'object');
    if (!validReports.length) return null;
    const mergedImportedSceneRows = validReports.flatMap((report) => (
        Array.isArray(report.importedSceneRows) ? report.importedSceneRows : []
    ));
    const mergedScenes = validReports.flatMap((report) => (
        Array.isArray(report.scenes) ? report.scenes : []
    ));
    const mergedImportedCounts = validReports.reduce((acc, report) => {
        const counts = report?.importedSubjectCounts || {};
        acc.character += Number(counts.character || 0);
        acc.prop += Number(counts.prop || 0);
        acc.environment += Number(counts.environment || 0);
        acc.poster += Number(counts.poster || 0);
        return acc;
    }, { character: 0, prop: 0, environment: 0, poster: 0 });
    return {
        ...validReports[validReports.length - 1],
        scenes: mergedScenes,
        importedSceneRows: mergedImportedSceneRows,
        importedSubjectCounts: mergedImportedCounts,
        createdSubjectItems: validReports.flatMap((report) => (
            Array.isArray(report.createdSubjectItems) ? report.createdSubjectItems : []
        )),
        skippedSubjectItems: validReports.flatMap((report) => (
            Array.isArray(report.skippedSubjectItems) ? report.skippedSubjectItems : []
        )),
        perSceneImportCount: validReports.length,
    };
};

const assertWorkspaceSceneImportComplete = ({
    importReport,
    expectedSceneCount,
    dbSceneCount,
    t,
}) => {
    const expected = Math.max(0, Number(expectedSceneCount) || 0);
    if (expected <= 0) return;
    const resolvedCount = firstPositiveFiniteNumber(
        dbSceneCount,
        resolveImportReportSceneCount(importReport, importReport?.sceneSubjectPostImportReport, dbSceneCount),
    );
    if (resolvedCount >= expected) return;
    throw new Error(t(
        `场景导入未完成：期望 ${expected} 场，工作区仅 ${resolvedCount || 0} 场。请检查导入日志后重试。`,
        `Scene import incomplete: expected ${expected} scene(s), workspace has ${resolvedCount || 0}. Check import logs and retry.`
    ));
};

const runAnalysisPipelineIntegrityGate = async ({
    t,
    onLog,
    fetchScenesFn,
    fetchEntitiesFn,
    projectId,
    episodeId,
    importReport,
    postImportSceneSubjectReport,
    expectedSceneCount,
    subjectIndexText,
}) => {
    const failures = [];

    if (!String(subjectIndexText || '').trim()) {
        failures.push(t('Subject Index 未生成或未持久化', 'Subject Index was not generated or persisted'));
    }

    const expected = Math.max(1, Number(expectedSceneCount) || 0);
    const dbSceneCount = await waitForEpisodeSceneCount(
        fetchScenesFn,
        episodeId,
        expected,
        { retries: 10, delayMs: 500 },
    );
    try {
        assertWorkspaceSceneImportComplete({
            importReport,
            expectedSceneCount: expected,
            dbSceneCount,
            t,
        });
    } catch (sceneErr) {
        failures.push(String(sceneErr?.message || sceneErr || ''));
    }

    const subtaskReports = Array.isArray(postImportSceneSubjectReport?.subtaskReports)
        ? postImportSceneSubjectReport.subtaskReports
        : [];
    const failedSubtasks = subtaskReports.filter(
        (report) => String(report?.status || '').trim().toLowerCase() !== 'ok'
    );
    if (failedSubtasks.length > 0) {
        failures.push(t(
            `视觉资产子任务失败：${failedSubtasks.map((item) => item?.key || 'unknown').join(', ')}`,
            `Visual asset subtasks failed: ${failedSubtasks.map((item) => item?.key || 'unknown').join(', ')}`
        ));
    }

    const supplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
    if (supplementFailed > 0 && subtaskReports.length === 0) {
        failures.push(t(
            `资产入库存在 ${supplementFailed} 项失败`,
            `${supplementFailed} asset import item(s) failed`
        ));
    }

    if (projectId && fetchEntitiesFn && String(subjectIndexText || '').trim()) {
        const entities = await fetchEntitiesFn(projectId).catch(() => []);
        const entityCount = Array.isArray(entities) ? entities.length : 0;
        const importedCounts = postImportSceneSubjectReport?.importedSubjectCounts || importReport?.importedSubjectCounts || {};
        const handledAssets = Number(importedCounts.character || 0)
            + Number(importedCounts.prop || 0)
            + Number(importedCounts.environment || 0)
            + Number(importedCounts.poster || 0);
        if (subtaskReports.length > 0 && entityCount <= 0 && handledAssets <= 0) {
            failures.push(t(
                '视觉资产生成已完成但未检测到项目实体记录',
                'Visual asset generation finished but no project entities were found'
            ));
        }
    }

    if (failures.length > 0) {
        const message = failures.filter(Boolean).join('；');
        onLog?.(`[Integrity Gate] ${message}`, 'error');
        throw new Error(t(
            `分析管线完整性检查未通过：${message}`,
            `Analysis pipeline integrity check failed: ${message}`
        ));
    }

    onLog?.(
        t(
            `[Integrity Gate] 完整性检查通过：${dbSceneCount} 场已入库，Subject Index 与视觉资产任务均已完成。`,
            `[Integrity Gate] Integrity check passed: ${dbSceneCount} scene(s) in workspace; Subject Index and visual asset tasks completed.`
        ),
        'success'
    );
    return { dbSceneCount, ok: true };
};

const getAnalysisSessionStorageKey = (episodeId) => {
    const id = Number(episodeId || 0);
    return id > 0 ? `aistory:analysis-session:${id}` : '';
};

const loadAnalysisSessionSnapshot = (episodeId) => {
    try {
        const key = getAnalysisSessionStorageKey(episodeId);
        if (!key || !window?.localStorage) return null;
        let raw = window.localStorage.getItem(key);
        if (!raw && window?.sessionStorage) {
            raw = window.sessionStorage.getItem(key);
            if (raw) {
                window.localStorage.setItem(key, raw);
                window.sessionStorage.removeItem(key);
            }
        }
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (_) {
        return null;
    }
};

const slimAnalysisUiReportForSnapshot = (uiReport) => {
    if (!uiReport || typeof uiReport !== 'object') return null;
    return {
        status: uiReport.status,
        startedAt: uiReport.startedAt,
        durationMs: uiReport.durationMs,
        warning: uiReport.warning,
        error: uiReport.error,
        reviewIssues: Array.isArray(uiReport.reviewIssues) ? uiReport.reviewIssues : [],
        runTag: uiReport.runTag,
        resolvedSceneImportCount: uiReport.resolvedSceneImportCount,
        resolvedAssetHandledCounts: uiReport.resolvedAssetHandledCounts,
        stage3SubtasksOk: uiReport.stage3SubtasksOk,
    };
};

const saveAnalysisSessionSnapshot = (episodeId, snapshot) => {
    try {
        const key = getAnalysisSessionStorageKey(episodeId);
        if (!key || !window?.localStorage || !snapshot || typeof snapshot !== 'object') return;
        window.localStorage.setItem(key, JSON.stringify(snapshot));
        try {
            window.sessionStorage?.removeItem(key);
        } catch (_) {
            // Ignore sessionStorage cleanup failures.
        }
    } catch (_) {
        // Ignore localStorage failures.
    }
};

const clearAnalysisSessionProgressSnapshot = (episodeId) => {
    try {
        const id = Number(episodeId || 0);
        if (!id) return;
        const prev = loadAnalysisSessionSnapshot(id);
        if (!prev || typeof prev !== 'object') return;
        saveAnalysisSessionSnapshot(id, {
            ...prev,
            progressUi: {
                dismissed: false,
                flowStatus: { phase: 'idle', message: '' },
                flowHistory: [],
                uiReport: null,
            },
            savedAt: Date.now(),
        });
    } catch (_) {
        // Ignore localStorage failures.
    }
};

const isPersistedAnalysisProgressRunning = (progressUi) => {
    if (!progressUi || progressUi.dismissed === true) return false;
    const flowStatus = (progressUi.flowStatus && typeof progressUi.flowStatus === 'object')
        ? progressUi.flowStatus
        : { phase: 'idle', message: '' };
    const uiReport = (progressUi.uiReport && typeof progressUi.uiReport === 'object') ? progressUi.uiReport : null;
    const flowHistory = Array.isArray(progressUi.flowHistory) ? progressUi.flowHistory : [];
    const phase = String(flowStatus?.phase || 'idle').trim().toLowerCase();
    const reportStatus = String(uiReport?.status || '').trim().toLowerCase();
    if (reportStatus === 'running') return true;
    if (phase && !['idle', 'completed', 'failed', 'warning'].includes(phase)) return true;
    if (flowHistory.some((item) => !item?.endedAt)) return true;
    return false;
};

const hasPersistedEntityDesignPayload = (rawText) => {
    const text = String(rawText || '').trim();
    if (!text) return false;
    return /"characters"\s*:\s*\[|"props"\s*:\s*\[|"environments"\s*:\s*\[|"posters"\s*:\s*\[|"covers"\s*:\s*\[/i.test(text);
};

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
import SettingsPage from '../../Settings';
import { confirmUiMessage, promptUiMessage } from '../../../lib/uiMessage';

// Character Canon (Authoritative) generator (shared)

import { CANON_TAG_STORAGE_KEY, CANON_IDENTITY_STORAGE_KEY, PROJECT_SCENE_ANALYSIS_OVERVIEW_FIELDS, DEFAULT_CANON_TAG_CATEGORIES, DEFAULT_CANON_IDENTITY_CATEGORIES, canonOptionValue, normalizeCanonTagCategories, normalizeUserListValues, formatUserListForTextarea, formatManagedUserHint } from '../editorConstants';
const isDummySubject = (itemName) => {
    if (!itemName) return false;
    const lcName = String(itemName).trim().toLowerCase().replace(/[\s_\-]/g, '');
    return ['subjectindex', 'subjectsindex', 'sceneanalysis', 'entities', 'character', 'characters', 'prop', 'props', 'environment', 'environments', 'role', 'roles', 'item', 'items', 'scene', 'scenes', '角色', '道具', '场景', '人物', '环境', '物件'].includes(lcName);
};

const SUBJECT_INDEX_STANDARD_HEADERS = [
    'subject_no',
    'subject_type',
    'subject_name_zh',
    'subject_name_en',
    'base_entity',
    'dependency_reference',
    'entity_attributes',
    'script_entity_coverage',
];

const SUBJECT_INDEX_LONG_TEXT_FIELDS = new Set([
    'entity_attributes',
    'script_entity_coverage',
    'description',
    'description_cn',
    'narrative_description',
]);

const SUBJECT_INDEX_FIELD_LABELS = {
    subject_no: { zh: '编号', en: 'Subject No' },
    subject_type: { zh: '类型', en: 'Type' },
    subject_name_zh: { zh: '中文名', en: 'Name (ZH)' },
    subject_name_en: { zh: '英文名', en: 'Name (EN)' },
    base_entity: { zh: '基准实体', en: 'Base Entity' },
    dependency_reference: { zh: '依赖引用', en: 'Dependency Reference' },
    entity_attributes: { zh: '实体属性', en: 'Entity Attributes' },
    script_entity_coverage: { zh: '剧本覆盖', en: 'Script Coverage' },
};

const resolveSubjectFieldValueByAliases = (fields, aliases = []) => {
    if (!fields || typeof fields !== 'object') return '';
    const normalizedMap = {};
    Object.entries(fields).forEach(([key, value]) => {
        const stableKey = String(key || '').trim();
        if (!stableKey) return;
        normalizedMap[stableKey] = String(value ?? '');
        normalizedMap[stableKey.toLowerCase()] = String(value ?? '');
        normalizedMap[stableKey.toLowerCase().replace(/[^a-z0-9_\u4e00-\u9fa5]+/g, '_')] = String(value ?? '');
    });
    for (const alias of aliases) {
        const stableAlias = String(alias || '').trim();
        if (!stableAlias) continue;
        const candidates = [
            stableAlias,
            stableAlias.toLowerCase(),
            stableAlias.toLowerCase().replace(/[^a-z0-9_\u4e00-\u9fa5]+/g, '_'),
        ];
        for (const candidate of candidates) {
            if (Object.prototype.hasOwnProperty.call(normalizedMap, candidate)) {
                return String(normalizedMap[candidate] ?? '').trim();
            }
        }
    }
    return '';
};

const normalizeSubjectIndexEntryFields = (rawFields = {}, entry = {}) => {
    const merged = {};
    if (rawFields && typeof rawFields === 'object') {
        Object.entries(rawFields).forEach(([key, value]) => {
            const stableKey = String(key || '').trim();
            if (!stableKey) return;
            merged[stableKey] = String(value ?? '').trim();
        });
    }

    const aliasGroups = {
        subject_no: ['subject_no', 'id', '编号'],
        subject_type: ['subject_type', 'type', '类型', '类别'],
        subject_name_zh: ['subject_name_zh', 'subject_name_exact', 'subject_name', 'name', '名称', '名字'],
        subject_name_en: ['subject_name_en', 'name_en', 'english_name', 'en_name'],
        base_entity: ['base_entity', 'base_entity_zh', '基准实体'],
        dependency_reference: ['dependency_reference', 'dependency', '依赖引用'],
        entity_attributes: ['entity_attributes', 'attributes', '实体属性'],
        script_entity_coverage: ['script_entity_coverage', 'coverage', '剧本覆盖'],
    };

    const resolved = {};
    Object.entries(aliasGroups).forEach(([canonical, aliases]) => {
        let value = String(merged[canonical] || '').trim();
        if (!value) {
            value = resolveSubjectFieldValueByAliases(merged, aliases);
        }
        if (!value && canonical === 'subject_name_zh') {
            value = String(entry?.name || '').trim();
        }
        if (!value && canonical === 'subject_no') {
            value = String(entry?.subjectNo || '').trim();
        }
        if (!value && canonical === 'subject_type') {
            value = String(entry?.type || '').trim();
        }
        resolved[canonical] = value;
    });

    SUBJECT_INDEX_STANDARD_HEADERS.forEach((header) => {
        if (!Object.prototype.hasOwnProperty.call(resolved, header)) {
            resolved[header] = '';
        }
    });

    Object.entries(merged).forEach(([key, value]) => {
        const stableKey = String(key || '').trim();
        if (!stableKey || SUBJECT_INDEX_STANDARD_HEADERS.includes(stableKey)) return;
        resolved[stableKey] = String(value ?? '').trim();
    });

    return resolved;
};

const SUBJECT_CONSISTENCY_CHECK_ENABLED = false;

const createSkippedSubjectConsistencyReport = () => ({
    ok: true,
    message: '',
    missing: [],
    extra: [],
    markdownSubjects: [],
    jsonSubjects: [],
    markdownSource: '',
    skipped: true,
});

export const ScriptEditor = ({ activeEpisode, projectId, project, onUpdateScript, onUpdateEpisodeInfo, onRefreshEpisodes, onLog, onImportText, onSwitchToScenes, assetRerunRequest = null, onAssetRerunRequestConsumed = null, uiLang = 'zh' }) => {
    const functionApiConfigs = useFunctionApis('script_analysis');
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
    const [diagnosticsEpisodeSceneCount, setDiagnosticsEpisodeSceneCount] = useState(0);
    const [selectedReuseSubjectIds, setSelectedReuseSubjectIds] = useState([]);
    const [reuseSubjectTypeFilter, setReuseSubjectTypeFilter] = useState('all');
    const [reuseSubjectKeyword, setReuseSubjectKeyword] = useState('');
    const [isLoadingSubjectAssets, setIsLoadingSubjectAssets] = useState(false);
    const [isSavingReuseSubjects, setIsSavingReuseSubjects] = useState(false);
    const [analysisFlowStatus, setAnalysisFlowStatus] = useState({ phase: 'idle', message: '' });
    const [analysisFlowStatusHistory, setAnalysisFlowStatusHistory] = useState([]);
    const [analysisUiReport, setAnalysisUiReport] = useState(null);
    const [analysisReviewIssues, setAnalysisReviewIssues] = useState([]);
    const analysisFallbackRetryRef = useRef({
        episodeId: null,
        sceneBeatsAttempts: 0,
        assetAttempts: 0,
        sceneRegenAttempts: 0,
        running: false,
    });
    const autoZeroReportHandledRef = useRef({ key: '', handledAt: 0 });
    const analysisTimerStartedAtRef = useRef(0);
    const lastSceneImportSuccessRef = useRef({ episodeId: null, count: 0, at: 0 });
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isRecomputingEpisodeCost, setIsRecomputingEpisodeCost] = useState(false);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [manualModalOpen, setManualModalOpen] = useState(false);
    const [analysisModalMode, setAnalysisModalMode] = useState('stage1');
    const [subjectIndexText, setSubjectIndexText] = useState('');
    const [adaptationText, setAdaptationText] = useState('');
    const [isEditingSubjectIndex, setIsEditingSubjectIndex] = useState(false);
    const [isRetryingPhase2, setIsRetryingPhase2] = useState(false);
    const [systemPrompt, setSystemPrompt] = useState('');
    const [userPrompt, setUserPrompt] = useState('');
    const [isSuperuser, setIsSuperuser] = useState(false);
    const isSuperuserRef = useRef(false);
    const rawContentRef = useRef('');
    const lastEpisodeSyncScriptKeyRef = useRef('');
    const lastEpisodeReuseSubjectIdsKeyRef = useRef('');
    const lastEpisodeSegmentsScriptKeyRef = useRef('');
    rawContentRef.current = rawContent;
    const SUBJECT_INDEX_PARSE_ERROR = '第二阶段返回未完成或被截断，未解析到完整的资产清单区块；当前结果不能继续作为完整分析使用。请重新执行，或切换模型后重试。';

    const hasSubjectIndexStructure = useCallback((candidateText) => {
        const candidate = String(candidateText || '').trim();
        if (!candidate) return false;
        if (/(?:^|\n)\s*(?:#{0,6}\s*)?(?:第二部分[:：]?\s*修改后的剧本|Second\s*Part[:：]?\s*Adapted\s*Script|\[SCENES_BLOCK_START\])/im.test(candidate)) {
            return false;
        }
        return (
            /(?:^|\n)\s*subject_no\s*=\s*S?\d+/i.test(candidate)
            || /(?:^|\n)\s*subject_type\s*=\s*(?:character|prop|environment|cover_poster)/i.test(candidate)
            || /(?:^|\n)\s*\|[^\n]*subject_no[^\n]*subject_type[^\n]*\|/i.test(candidate)
            || /(?:^|\n)\s*\|?\s*S\d{3,}\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)/i.test(candidate)
            || /(?:^|\n)\s*\|?\s*[A-Za-z]+\d+\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)/i.test(candidate)
            || /(?:^|\n)\s*(?:#{0,6}\s*)?(?:\*\*)?\s*(?:Subject Index|Subjects? Index|资产清单|实体清单|设计资产索引)\s*(?:\*\*)?\s*(?:\n|$)/i.test(candidate)
        );
    }, []);

        const extractAnalysisSections = useCallback((rawText) => {
        let authoritativeSubjectText = String(rawText || '');
        // Erase any <think> blocks before doing regex to prevent huge text matching failures
        authoritativeSubjectText = authoritativeSubjectText.replace(/<think>[\s\S]*?<\/think>\n*/gi, '').trim();

        let extractedText = '';
        let extractedAdaptationText = '';
        let hasStructuredSubjectIndex = false;

                const looksLikeSubjectIndex = (candidateText) => {
            const candidate = String(candidateText || '');
            return hasSubjectIndexStructure(candidate);
        };

        const trimSubjectIndexSection = (candidateText) => {
            let candidate = String(candidateText || '').replace(/\r\n/g, '\n').trim();
            if (!candidate) return '';

            const subjectHeaderMatch = candidate.match(/(?:^|\n)\s*(?:#{0,6}\s*)?(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)\s*(?:\*\*)?\s*\n?/i);
            if (subjectHeaderMatch?.index >= 0) {
                candidate = candidate.slice(subjectHeaderMatch.index).trim();
            }

            const endMarkers = [
                /^\s*-{4,}\s*$/im,
                /^\s*(?:###?\s*)?(?:Project\s*Visual\s*Backfill|第三部分|Final\s*Consistency\s*Report|一致性检查)\b/im,
                /^\s*\{\s*"project_visual_backfill"\s*:/im,
                /^\s*(?:(?:##|###)\s*(?:-1\)|Scenes?|场景列表))/im,
                /^\s*(?:###?\s*(?:-1\)\s*类型研判|Scenes|场景列表))/im,
                /^\s*(?:###?\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|Scene\s*Arrangement|场景分析结果|场景表)\b/im,
                /^###?\s*(?:(?:第二|第一)部分)?\s*(?:Adapted\s*Script|参考改编|修改(?:后?)的剧本)/im
            ];

            let endIndex = -1;
            for (const pattern of endMarkers) {
                const match = pattern.exec(candidate);
                if (!match || typeof match.index !== 'number' || match.index <= 0) continue;
                // If it matched within the first 15 chars, it probably matched our own header mistakenly or there's no actual table content
                if (match.index < 15) continue;
                endIndex = endIndex < 0 ? match.index : Math.min(endIndex, match.index);
            }

            if (endIndex > 0) {
                candidate = candidate.slice(0, endIndex).trim();
            }

            return candidate.trim();
        };

        if (!authoritativeSubjectText) {
            return {
                authoritativeSubjectText,
                subjectIndexText: '',
                adaptationText: '',
                hasStructuredSubjectIndex: false,
            };
        }

        const adaptMatch = authoritativeSubjectText.match(/\*\*\s*剧本改编(?:补 充说明)?\s*\*\*[:：]?\s*([\s\S]*?)(?=\n(?:-{3,}|###?|\|)|$)/i)
            || authoritativeSubjectText.match(/###?\s*剧本改编(?:补充说明)?\s*\n([\s\S]*?)(?=\n(?:-{3,}|###?|\|)|$)/i)
            || authoritativeSubjectText.match(/剧本改编(?:补充说明)?[:：\n]\s*([\s\S]*?)(?=\n(?:-{3,}|###?|\|)|$)/i);
        if (adaptMatch) {
            extractedAdaptationText = (adaptMatch[1] || adaptMatch[2] || adaptMatch[3] || '').trim();
        }

        const hasDownstreamMarker = (
            /subject_type\s*=\s*cover_poster/i.test(authoritativeSubjectText)
            || /project_visual_backfill/i.test(authoritativeSubjectText)
            || /"characters"\s*:\s*\[/i.test(authoritativeSubjectText)
            || /"environments"\s*:\s*\[/i.test(authoritativeSubjectText)
            || /"props"\s*:\s*\[/i.test(authoritativeSubjectText)
            || /Final\s+Consistency\s+Report/i.test(authoritativeSubjectText)
        );

        const dashMatch = authoritativeSubjectText.match(/-{4,}\s*\n([\s\S]*?)\n\s*-{4,}/);
        if (dashMatch && looksLikeSubjectIndex(dashMatch[1])) {
            extractedText = trimSubjectIndexSection(dashMatch[1]);
            hasStructuredSubjectIndex = !!extractedText;
        } else {
            const match = authoritativeSubjectText.match(/(?:^|\b|\s)#{0,6}\s*(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)\s*(?:\*\*)?\s*\n[\s\S]*/i)
                || authoritativeSubjectText.match(/#{1,6}\s*(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)[\s\S]*/i)
                || authoritativeSubjectText.match(/(?:^|\b|\s)(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)[\s\S]*/i);
            if (match) {
                extractedText = trimSubjectIndexSection(match[0]);
                hasStructuredSubjectIndex = !!extractedText;
            } else {
                const pipeMatch = authoritativeSubjectText.match(/(?:^|\n)\s*(subject_no\s*=\s*[A-Za-z]?\d+[\s\S]*)/i);
                if (pipeMatch && String(pipeMatch[1] || '').trim()) {
                    extractedText = trimSubjectIndexSection(String(pipeMatch[1] || ''));
                    hasStructuredSubjectIndex = !!extractedText;
                } else {
                    const subjectTypeLine = authoritativeSubjectText.match(/(?:^|\n)(.*subject_type\s*=\s*(?:character|prop|environment|cover_poster).*(?:\|.*)+)/i);
                    if (subjectTypeLine && String(subjectTypeLine[1] || '').trim()) {
                        const idx = authoritativeSubjectText.indexOf(subjectTypeLine[1]);
                        extractedText = trimSubjectIndexSection(authoritativeSubjectText.slice(idx));
                        hasStructuredSubjectIndex = !!extractedText;
                    } else if (looksLikeSubjectIndex(authoritativeSubjectText)) {
                        extractedText = trimSubjectIndexSection(authoritativeSubjectText);
                        hasStructuredSubjectIndex = !!extractedText;
                    }
                }
            }
        }

        if (!hasStructuredSubjectIndex && looksLikeSubjectIndex(authoritativeSubjectText)) {
            extractedText = trimSubjectIndexSection(authoritativeSubjectText);
            hasStructuredSubjectIndex = !!extractedText;
        }

        const trailingConsistencyReport = extractedText.match(/(?:\n-{3,}\n*)?###?\s*(?:Final\s*Consistency\s*Report|一致性检查)[\s\S]*/i);
        if (trailingConsistencyReport) {
            extractedText = extractedText.replace(trailingConsistencyReport[0], '').trim();
        }

        const validatedSubjectIndex = hasStructuredSubjectIndex && hasSubjectIndexStructure(extractedText)
            ? extractedText
            : '';

        return {
            authoritativeSubjectText,
            subjectIndexText: validatedSubjectIndex,
            adaptationText: extractedAdaptationText,
            hasStructuredSubjectIndex: !!validatedSubjectIndex,
        };
    }, [hasSubjectIndexStructure]);

    const extractPureSubjectIndexText = useCallback((rawText) => {
        const source = String(rawText || '').trim();
        if (!source) return '';

        const sections = extractAnalysisSections(source);
        if (sections?.hasStructuredSubjectIndex && String(sections.subjectIndexText || '').trim()) {
            const extracted = String(sections.subjectIndexText || '').trim();
            return hasSubjectIndexStructure(extracted) ? extracted : '';
        }

        const fallbackSceneStart = source.search(/(?:^|\n)\s*(?:#{0,6}\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|Scene\s*Arrangement|场景分析结果|场景表|场景列表|###?\s*-1\)\s*类型研判)\b/i);
        if (fallbackSceneStart > 0) {
            const sliced = source.slice(0, fallbackSceneStart).trim();
            return hasSubjectIndexStructure(sliced) ? sliced : '';
        }

        return hasSubjectIndexStructure(source) ? source : '';
    }, [extractAnalysisSections, hasSubjectIndexStructure]);

    const normalizeSubjectIndexTypeForAssetTask = useCallback((rawType) => {
        const type = String(rawType || '').trim().toLowerCase().replace(/[\s_-]+/g, '_');
        if (!type) return '';
        if (['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(type)) return 'character';
        if (['prop', 'props', 'item', 'items', 'object', 'objects', '道具', '物件'].includes(type)) return 'prop';
        if (['environment', 'environments', 'env', 'scene', 'scenes', '场景', '环境'].includes(type)) return 'environment';
        if (['cover_poster', 'coverposter', 'poster', 'posters', 'cover', 'covers', '封面', '封面海报', '海报'].includes(type)) return 'cover_poster';
        return type;
    }, []);

    const getSubjectIndexTypesForAssetTask = useCallback((assetTaskKey) => {
        const key = String(assetTaskKey || '').trim().toLowerCase();
        if (key === 'characters') return new Set(['character']);
        if (key === 'props') return new Set(['prop']);
        if (key === 'environments' || key === 'posters' || key === 'covers') return new Set(['environment', 'cover_poster']);
        return null;
    }, []);

    const detectSubjectIndexLineType = useCallback((line) => {
        const rawLine = String(line || '');
        const trimmed = rawLine.trim();
        if (!trimmed) return { isSubjectRow: false, type: '' };

        const keyValueTypeMatch = trimmed.match(/\bsubject_type\s*=\s*([^|`\n]+)/i);
        const keyValueSubjectMatch = trimmed.match(/\bsubject_no\s*=\s*([^|`\n]+)/i);
        if (keyValueTypeMatch && (keyValueSubjectMatch || /\bsubject_name_(?:zh|en|exact)\s*=/i.test(trimmed))) {
            return {
                isSubjectRow: true,
                type: normalizeSubjectIndexTypeForAssetTask(keyValueTypeMatch[1]),
            };
        }

        const normalizedPipeLine = trimmed.replace(/^\s*>\s*/, '').replace(/^[-*+]\s+/, '').trim();
        if (normalizedPipeLine.includes('|')) {
            const cells = normalizedPipeLine.replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
            const firstCell = String(cells[0] || '').trim();
            const secondCell = String(cells[1] || '').trim();
            const isHeaderOrSeparator = /subject_no/i.test(firstCell)
                || /subject_type/i.test(secondCell)
                || /^:?-{2,}:?$/.test(firstCell)
                || /^:?-{2,}:?$/.test(secondCell);
            if (isHeaderOrSeparator) return { isSubjectRow: false, type: '' };
            if (firstCell && secondCell) {
                return {
                    isSubjectRow: true,
                    type: normalizeSubjectIndexTypeForAssetTask(secondCell),
                };
            }
        }

        return { isSubjectRow: false, type: '' };
    }, [normalizeSubjectIndexTypeForAssetTask]);

    const filterSubjectIndexTextForAssetTask = useCallback((subjectIndexSourceText, assetTaskKey, targetEntityTypes = null) => {
        const source = String(subjectIndexSourceText || '').replace(/<think>[\s\S]*?<\/think>\n*/gi, '').trim();
        let allowedTypes = getSubjectIndexTypesForAssetTask(assetTaskKey);
        const requestedTargets = Array.isArray(targetEntityTypes)
            ? Array.from(new Set(targetEntityTypes.map((item) => String(item || '').trim().toLowerCase()).filter(Boolean)))
            : [];
        if (String(assetTaskKey || '').trim().toLowerCase() === 'environments' && requestedTargets.length > 0) {
            const scopedTypes = new Set();
            if (requestedTargets.some((item) => ['environment', 'environments', 'env', 'scene', 'scenes'].includes(item))) scopedTypes.add('environment');
            if (requestedTargets.some((item) => ['poster', 'posters', 'cover', 'covers', 'cover_poster'].includes(item))) scopedTypes.add('cover_poster');
            if (scopedTypes.size > 0) allowedTypes = scopedTypes;
        }
        if (!source || !allowedTypes) {
            return { text: source, totalRows: 0, keptRows: 0 };
        }

        let totalRows = 0;
        let keptRows = 0;
        const filteredLines = source.split('\n').filter((line) => {
            const detected = detectSubjectIndexLineType(line);
            if (!detected.isSubjectRow) return true;
            totalRows += 1;
            if (allowedTypes.has(detected.type)) {
                keptRows += 1;
                return true;
            }
            return false;
        });

        return {
            text: filteredLines.join('\n').trim(),
            totalRows,
            keptRows,
        };
    }, [detectSubjectIndexLineType, getSubjectIndexTypesForAssetTask]);

    const isSplitStage1Prompt = useCallback((promptText) => {
        const text = String(promptText || '');
        if (!text.trim()) return false;
        return /Skill\s*1-1\s*:\s*剧本改编与整体规划/i.test(text)
            || /三阶段工作流[\s\S]{0,120}第一阶段/i.test(text)
            || /本提示词专门负责[\s\S]{0,80}第一阶段/i.test(text);
    }, []);

    const extractStage1AdaptedScriptBody = useCallback((stage1Text) => {
        const text = String(stage1Text || '').replace(/\r\n/g, '\n').trim();
        if (!text) return '';

        const extractScenesBlockOnly = (inputText) => {
            const source = String(inputText || '');
            if (!source.trim()) return '';
            // Accept optional markdown inline-code wrapping around markers.
            const startRegex = /`?\[SCENES_BLOCK_START\]`?/i;
            const endRegex = /`?\[SCENES_BLOCK_END\]`?/i;
            const startMatch = startRegex.exec(source);
            if (!startMatch) return '';
            const startIdx = startMatch.index;
            const afterStart = source.slice(startIdx + startMatch[0].length);
            const endMatch = endRegex.exec(afterStart);
            if (!endMatch) {
                return source.slice(startIdx).trim();
            }
            const endIdxAbs = startIdx + startMatch[0].length + endMatch.index + endMatch[0].length;
            return source.slice(startIdx, endIdxAbs).trim();
        };

        const trimScriptBody = (candidateText) => {
            let candidate = String(candidateText || '').trim();
            if (!candidate) return '';

            // Prefer strict scene block markers when available:
            // keep only [SCENES_BLOCK_START] ... [SCENES_BLOCK_END].
            const strictBlock = extractScenesBlockOnly(candidate);
            if (strictBlock) return strictBlock;

            const sceneHeadingMatch = candidate.match(/^\s*(?:\*\*)?\s*(?:【场景\s*[^\n]+】|\*\*【场景\s*[^\n]+】\*\*|Scene\s*\d+\s*[:：]|\[Scene\s*\d+[^\n]*\])/im);
            if (sceneHeadingMatch?.index >= 0) {
                candidate = candidate.slice(sceneHeadingMatch.index).trim();
            }

            const endMarkerMatch = candidate.match(/^\s*(?:###\s*Subject\s*Index|###\s*Part\s*1|###\s*Project\s*Visual\s*Backfill|\[Project Metadata\]|\[Reusable Subject Assets)/im);
            const fallbackEndMarkerMatch = candidate.match(/^\s*(?:###\s*第三部分|##\s*第三部分|第三部分[:：]?\s*Project\s*Visual\s*Backfill|[-]{5,}\s*$|\{\s*"project_visual_backfill"\s*:)/im);
            if (endMarkerMatch?.index >= 0) {
                candidate = candidate.slice(0, endMarkerMatch.index).trim();
            } else if (fallbackEndMarkerMatch?.index >= 0) {
                candidate = candidate.slice(0, fallbackEndMarkerMatch.index).trim();
            }

            return candidate;
        };

        const sectionPatterns = [
            /^.*?(?:###\s*第二部分[:：]?\s*修改后的剧本.*?\n)(.*)$/is,
            /^.*?(?:##\s*第二部分[:：]?\s*修改后的剧本.*?\n)(.*)$/is,
            /^.*?(?:第二部分[:：]?\s*修改后的剧本.*?\n)(.*)$/is,
            /^.*?(?:###\s*Second\s*Part[:：]?\s*Adapted\s*Script.*?\n)(.*)$/is,
            /^.*?(?:##\s*Second\s*Part[:：]?\s*Adapted\s*Script.*?\n)(.*)$/is,
            /^.*?(?:Adapted\s*Script\s*[-(（].*?\n)(.*)$/is,
        ];

        for (const pattern of sectionPatterns) {
            const match = text.match(pattern);
            if (!match) continue;
            const extracted = trimScriptBody(match[1] || '');
            if (extracted) return extracted;
        }

        const fallbackAdaptation = trimScriptBody(extractAnalysisSections(text)?.adaptationText || '');
        if (fallbackAdaptation) return fallbackAdaptation;

        const strictBlockFromFullText = extractScenesBlockOnly(text);
        if (strictBlockFromFullText) return strictBlockFromFullText;

        return '';
    }, [extractAnalysisSections]);

    const extractProjectVisualBackfillJsonText = useCallback((rawText) => {
        const text = String(rawText || '').trim();
        if (!text) return '';

        const fenceRegex = /```(?:json)?\s*([\s\S]*?)```/gi;
        let match;
        while ((match = fenceRegex.exec(text)) !== null) {
            const candidate = String(match[1] || '').trim();
            if (!candidate) continue;
            try {
                const parsed = JSON.parse(candidate);
                if (parsed && typeof parsed === 'object' && parsed.project_visual_backfill && typeof parsed.project_visual_backfill === 'object') {
                    return JSON.stringify(parsed, null, 2);
                }
            } catch {
                // ignore invalid fenced JSON
            }
        }

        let braceDepth = 0;
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
                if (braceDepth === 0) startIndex = i;
                braceDepth += 1;
            } else if (ch === '}') {
                braceDepth -= 1;
                if (braceDepth === 0 && startIndex !== -1) {
                    const candidate = text.slice(startIndex, i + 1).trim();
                    startIndex = -1;
                    try {
                        const parsed = JSON.parse(candidate);
                        if (parsed && typeof parsed === 'object' && parsed.project_visual_backfill && typeof parsed.project_visual_backfill === 'object') {
                            return JSON.stringify(parsed, null, 2);
                        }
                    } catch {
                        // ignore invalid object candidate
                    }
                }
            }
        }

        return '';
    }, []);

    const buildStage2UserInputFromStage1 = useCallback((stage1Text, reuseSubjectAssets = []) => {
        const adaptedScriptText = extractStage1AdaptedScriptBody(stage1Text);
        const stage1VisualBackfillJson = extractProjectVisualBackfillJsonText(stage1Text);
        const stage2InputParts = [
            '请执行第二阶段的第一步：“资产清单”生成（Assets Extraction）。基于“优化后剧本”提取实体并建立资产库；项目信息与第一阶段产出的“全局风格”作为补充约束一并生效；如与原始剧本存在任何差异，一律以上游结果为准。',
        ];

        const projectContextSection = buildStage1ProjectContextSection();
        if (projectContextSection) {
            stage2InputParts.push(projectContextSection);
        }

        if (Array.isArray(reuseSubjectAssets) && reuseSubjectAssets.length > 0) {
            const reuseLines = [
                '[Reusable Subject Assets - High Priority]',
                'Reuse these existing subjects whenever they already match the current script. Do not rename them arbitrarily.',
            ];
            reuseSubjectAssets.forEach((item) => {
                if (!item || typeof item !== 'object') return;
                const name = String(item.name || '').trim();
                if (!name) return;
                const detailParts = [`name=${name}`];
                if (item.type) detailParts.push(`type=${String(item.type).trim()}`);
                if (item.description) detailParts.push(`description=${String(item.description).trim()}`);
                if (item.anchor_description) detailParts.push(`anchors=${String(item.anchor_description).trim()}`);
                reuseLines.push(`- ${detailParts.join(' | ')}`);
            });
            if (reuseLines.length > 2) {
                stage2InputParts.push(reuseLines.join('\n'));
            }
        }

        if (stage1VisualBackfillJson) {
            stage2InputParts.push(`[全局风格 - 第二阶段补充约束]\n${stage1VisualBackfillJson}`);
        }
        // Keep SCENES_BLOCK as the last section so nothing appears after [SCENES_BLOCK_END].
        stage2InputParts.push(`[优化后剧本 - 第二阶段权威输入]\n${adaptedScriptText || ''}`);

        return {
            adaptedScriptText,
            userInput: stage2InputParts.filter(part => String(part || '').trim()).join('\n\n'),
        };
    }, [extractProjectVisualBackfillJsonText, extractStage1AdaptedScriptBody, project?.global_info]);

    // 专门用于 Stage 2.2 (Beats Generation) 的 userInput 构建 - 避免混淆 "第一步" vs "第二步"
    const buildStage2_2UserInputFromStage1 = useCallback((stage1Text, adaptedScriptOverride = null) => {
        const adaptedScriptText = adaptedScriptOverride != null
            ? String(adaptedScriptOverride || '').trim()
            : String(
                activeEpisode?.ai_scene_analysis_adaptation
                || extractStage1AdaptedScriptBody(stage1Text)
                || ''
            ).trim();
        const stage1VisualBackfillJson = extractProjectVisualBackfillJsonText(stage1Text);
        const stage2_2InputParts = [
            '请执行第二阶段的第二步：视听推演与节拍拆解（Beat Generation & Scene Breakdown）。基于上游提取的"资产清单"和"优化后剧本"，生成标准化的《Scenes Table》——包含每一个可视场景的环境、角色、道具布局与动作节拍序列。',
        ];

        const projectContextSection = buildStage1ProjectContextSection();
        if (projectContextSection) {
            stage2_2InputParts.push(projectContextSection);
        }

        if (stage1VisualBackfillJson) {
            stage2_2InputParts.push(`[全局风格 - Stage 2.2补充约束]\n${stage1VisualBackfillJson}`);
        }
        // Keep SCENES_BLOCK as the last section so nothing appears after [SCENES_BLOCK_END].
        stage2_2InputParts.push(`[优化后剧本 - Stage 2.2权威输入]\n${adaptedScriptText || ''}`);

        return stage2_2InputParts.filter(part => String(part || '').trim()).join('\n\n');
    }, [activeEpisode?.ai_scene_analysis_adaptation, extractProjectVisualBackfillJsonText, extractStage1AdaptedScriptBody, project?.global_info]);

    const SCENES_BLOCK_START_TOKEN = '[SCENES_BLOCK_START]';
    const SCENES_BLOCK_END_TOKEN = '[SCENES_BLOCK_END]';

    const parseSceneUnitsFromScriptMarkers = useCallback((scriptText) => {
        const text = String(scriptText || '').replace(/\r\n/g, '\n');
        if (!text.trim()) return [];

        const startRegex = /`?\[SCENES_BLOCK_START\]`?/i;
        const endRegex = /`?\[SCENES_BLOCK_END\]`?/i;
        const startMatch = startRegex.exec(text);
        if (!startMatch) return [];

        const afterStart = text.slice(startMatch.index + startMatch[0].length);
        const endMatch = endRegex.exec(afterStart);
        if (!endMatch) return [];

        const blockText = afterStart.slice(0, endMatch.index);
        if (!String(blockText || '').trim()) return [];

        const sceneStartPattern = /\[SCENE_START:([^\]\s]+)\]/g;
        const sceneEndPattern = /\[SCENE_END:([^\]\s]+)\]/;
        const units = [];
        const seenSceneIds = new Set();
        let cursor = 0;

        while (true) {
            sceneStartPattern.lastIndex = cursor;
            const startUnitMatch = sceneStartPattern.exec(blockText);
            if (!startUnitMatch) break;

            const sceneId = String(startUnitMatch[1] || '').trim();
            if (!sceneId) {
                throw new Error('Scene marker parse error: empty scene_id in SCENE_START');
            }
            if (seenSceneIds.has(sceneId)) {
                throw new Error(`Scene marker parse error: duplicate scene_id ${sceneId}`);
            }
            seenSceneIds.add(sceneId);

            const afterStartMarker = blockText.slice(startUnitMatch.index + startUnitMatch[0].length);
            const endUnitMatch = sceneEndPattern.exec(afterStartMarker);
            if (!endUnitMatch) {
                throw new Error(`Scene marker parse error: missing SCENE_END for ${sceneId}`);
            }
            const endSceneId = String(endUnitMatch[1] || '').trim();
            if (endSceneId !== sceneId) {
                throw new Error(`Scene marker parse error: SCENE_START/END mismatch (${sceneId} vs ${endSceneId})`);
            }

            const sceneBody = afterStartMarker.slice(0, endUnitMatch.index).trim();
            units.push({
                sceneId,
                sceneOrder: units.length + 1,
                sceneText: sceneBody,
                markerStartToken: startUnitMatch[0],
                markerEndToken: endUnitMatch[0],
            });
            cursor = startUnitMatch.index + startUnitMatch[0].length + endUnitMatch.index + endUnitMatch[0].length;
        }

        const trailing = blockText.slice(cursor).trim();
        if (trailing && /\[SCENE_(?:START|END):/i.test(trailing)) {
            throw new Error('Scene marker parse error: unmatched trailing content after scene markers');
        }
        return units;
    }, []);

    const wrapSceneUnitAsScriptBlock = useCallback((unit) => {
        if (!unit) return '';
        return [
            SCENES_BLOCK_START_TOKEN,
            unit.markerStartToken,
            unit.sceneText,
            unit.markerEndToken,
            SCENES_BLOCK_END_TOKEN,
        ].join('\n');
    }, []);

    const extractSceneDisplayLabel = useCallback((unit) => {
        const sceneId = String(unit?.sceneId || '').trim();
        const firstLine = String(unit?.sceneText || '')
            .split('\n')
            .map((line) => String(line || '').trim())
            .find(Boolean) || '';
        const nameMatch = firstLine.match(/【场景\s*\d+[：:]\s*([^】]+)】/)
            || firstLine.match(/\*\*【场景\s*[^】]+】\*\*/)
            || firstLine.match(/Scene\s*\d+\s*[:：]\s*(.+)$/i);
        const sceneName = nameMatch
            ? String(nameMatch[1] || nameMatch[0] || '').replace(/[*【】]/g, '').trim()
            : '';
        if (sceneId && sceneName) return `${sceneId} · ${sceneName}`;
        return sceneId || sceneName || (uiLang === 'zh' ? '未命名场景' : 'Unnamed scene');
    }, [uiLang]);

    const extractAdaptedScriptFromStage2_2UserInputBody = useCallback((bodyText) => {
        const text = String(bodyText || '');
        const markerMatch = text.match(/\[优化后剧本[^\]]*\]\s*\n([\s\S]*)$/);
        if (markerMatch) {
            return String(markerMatch[1] || '').trim();
        }
        const startRegex = /`?\[SCENES_BLOCK_START\]`?/i;
        const startMatch = startRegex.exec(text);
        if (startMatch) {
            return text.slice(startMatch.index).trim();
        }
        return '';
    }, []);

    const buildStage2_2SubjectIndexSection = useCallback((subjectIndexText) => {
        const stableText = String(extractPureSubjectIndexText(subjectIndexText) || '').trim();
        if (!stableText) return '';
        return [
            '[Stage 2-1 Subject Index - REQUIRED INPUT]',
            'The following Subject Index is authoritative for Stage 2.2.',
            'Do not rename / merge / invent entities. Keep ENV/CHAR/PROP names byte-identical.',
            '```subject_index',
            stableText,
            '```',
        ].join('\n');
    }, [extractPureSubjectIndexText]);

    useEffect(() => {
        isSuperuserRef.current = isSuperuser;
    }, [isSuperuser]);

    useEffect(() => {
        if (!activeEpisode) return;

        const persistedSubjectIndexText = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
        const persistedAdaptationText = String(activeEpisode?.ai_scene_analysis_adaptation || '').trim();
        const extractedSubjectIndex = extractPureSubjectIndexText(persistedSubjectIndexText);
        const authoritativeAdaptationText = llmRawResultContent || llmResultContent || activeEpisode.ai_scene_analysis_result || '';
        const extractedAdaptationText = persistedAdaptationText || (
            /(?:###?\s*第二部分[:：]?\s*修改后的剧本|###?\s*Second\s*Part[:：]?\s*Adapted\s*Script|【场景\s*|Scene\s*\d+)/i.test(authoritativeAdaptationText)
                ? String(extractStage1AdaptedScriptBody(authoritativeAdaptationText) || '').trim()
                : ''
        );

        setSubjectIndexText((prev) => (extractedSubjectIndex !== prev ? extractedSubjectIndex : prev));
        setAdaptationText((prev) => (extractedAdaptationText !== prev ? extractedAdaptationText : prev));
    }, [
        llmRawResultContent,
        llmResultContent,
        activeEpisode?.ai_scene_analysis_result,
        activeEpisode?.ai_scene_analysis_subject_index,
        activeEpisode?.ai_scene_analysis_adaptation,
        activeEpisode?.id,
        extractPureSubjectIndexText,
        extractStage1AdaptedScriptBody,
    ]);

    const [subjectConsistencyReport, setSubjectConsistencyReport] = useState(null);
    const [subjectConsistencyResultText, setSubjectConsistencyResultText] = useState('');
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
    const [phase2RerunModal, setPhase2RerunModal] = useState({
        open: false,
        mode: 'all',
        category: 'characters',
        subjectKey: '',
        query: '',
        deletedSubjectKeys: {},
        subjectEdits: {},
        editingSubjectKey: '',
    });
    const [sceneBeatsRerunModal, setSceneBeatsRerunModal] = useState({
        open: false,
        mode: 'all',
        sceneId: '',
    });
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

    const analysisAssetCounts = useMemo(() => {
        const importReport = analysisUiReport?.importReport || {};
        const toCount = (value) => {
            const count = Number(value);
            return Number.isFinite(count) && count > 0 ? count : 0;
        };
        const normalizeReportType = (value) => {
            const key = String(value || '').trim().toLowerCase();
            if (['character', 'characters', 'role', 'roles', '人物', '角色'].includes(key)) return 'character';
            if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(key)) return 'prop';
            if (['environment', 'environments', 'env', 'scene', 'scenes', '空镜', '场景', '环境'].includes(key)) return 'environment';
            return key;
        };
        const countCreatedItemsByType = (items, type) => {
            if (!Array.isArray(items)) return 0;
            return items.reduce((count, item) => {
                return count + (normalizeReportType(item?.type || item?.entity_type || item?.subject_type) === type ? 1 : 0);
            }, 0);
        };
        const scenePostReport = importReport?.sceneSubjectPostImportReport || {};
        const supplementReport = scenePostReport?.supplementReport || {};
        const insertedEntityCount = (type) => {
            const candidates = [
                toCount(importReport?.dbRunInsertedCounts?.entities?.[type]),
                toCount(importReport?.importedSubjectCounts?.[type]),
                toCount(scenePostReport?.importedSubjectCounts?.[type]),
                toCount(supplementReport?.countsByType?.[type]),
                countCreatedItemsByType(importReport?.createdSubjectItems, type),
                countCreatedItemsByType(supplementReport?.createdItems, type),
            ];
            return Math.max(...candidates);
        };
        const totalEntityCount = (type) => {
            const dbPersistedCount = toCount(importReport?.dbPersistedCounts?.entities?.[type]);
            if (dbPersistedCount > 0) return dbPersistedCount;
            return Math.max(
                toCount(importReport?.importedSubjectCounts?.[type]),
                toCount(scenePostReport?.importedSubjectCounts?.[type]),
                countCreatedItemsByType(importReport?.createdSubjectItems, type),
                countCreatedItemsByType(supplementReport?.createdItems, type)
            );
        };

        return {
            inserted: {
                character: insertedEntityCount('character'),
                environment: insertedEntityCount('environment'),
                prop: insertedEntityCount('prop'),
            },
            total: {
                character: totalEntityCount('character'),
                environment: totalEntityCount('environment'),
                prop: totalEntityCount('prop'),
            },
        };
    }, [analysisUiReport]);

    const displayedReviewIssues = useMemo(() => {
        if (Array.isArray(analysisReviewIssues) && analysisReviewIssues.length > 0) {
            return analysisReviewIssues;
        }
        if (Array.isArray(analysisUiReport?.reviewIssues) && analysisUiReport.reviewIssues.length > 0) {
            return analysisUiReport.reviewIssues;
        }
        return [];
    }, [analysisReviewIssues, analysisUiReport?.reviewIssues]);

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

    const beginAnalysisTimer = useCallback((startedAt = Date.now()) => {
        const ts = Number(startedAt || Date.now());
        analysisTimerStartedAtRef.current = Number.isFinite(ts) && ts > 0 ? ts : Date.now();
        setAnalysisHeartbeatTick(0);
    }, []);

    useEffect(() => {
        if (!isAnalyzing) {
            setAnalysisHeartbeatTick(0);
            analysisTimerStartedAtRef.current = 0;
            return;
        }

        const timer = setInterval(() => {
            setAnalysisHeartbeatTick(prev => prev + 1);
        }, 1000);

        return () => clearInterval(timer);
    }, [isAnalyzing]);

    const analysisHeartbeatElapsedMs = useMemo(() => {
        if (!isAnalyzing) return 0;
        const startedAt = Number(
            analysisTimerStartedAtRef.current
            || analysisUiReport?.startedAt
            || 0
        );
        if (!Number.isFinite(startedAt) || startedAt <= 0) return 0;
        return Math.max(0, Date.now() - startedAt);
    }, [isAnalyzing, analysisUiReport?.startedAt, analysisHeartbeatTick]);

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
    }, [t]);

    useEffect(() => {
        const phase = String(analysisFlowStatus?.phase || '').trim();
        const message = String(analysisFlowStatus?.message || '').trim();
        const highlightHint = String(analysisFlowStatus?.highlightHint || '').trim();

        if (!phase || phase === 'idle' || !message) return;

        setAnalysisFlowStatusHistory((prev) => {
            const lastItem = prev[prev.length - 1];
            if (lastItem && lastItem.phase === phase && lastItem.message === message) {
                if (highlightHint && highlightHint !== String(lastItem.highlightHint || '').trim()) {
                    return [...prev.slice(0, -1), { ...lastItem, highlightHint }];
                }
                return prev;
            }
            const now = Date.now();
            const next = [...prev];
            if (next.length > 0) {
                const prevLast = next[next.length - 1];
                if (!Number.isFinite(Number(prevLast?.endedAt))) {
                    next[next.length - 1] = { ...prevLast, endedAt: now };
                }
            }
            next.push({
                id: `${now}-${prev.length}`,
                phase,
                message,
                highlightHint,
                createdAt: now,
                endedAt: null,
            });
            return next.length > 80 ? next.slice(-80) : next;
        });
    }, [analysisFlowStatus?.phase, analysisFlowStatus?.message, analysisFlowStatus?.highlightHint]);

    useEffect(() => {
        latestAnalysisProgressUiRef.current = {
            flowStatus: analysisFlowStatus,
            flowHistory: analysisFlowStatusHistory,
            uiReport: analysisUiReport,
        };
    }, [analysisFlowStatus, analysisFlowStatusHistory, analysisUiReport]);

    useEffect(() => {
        if (isAnalyzing) return;
        const reportStatus = String(analysisUiReport?.status || '').trim().toLowerCase();
        const phase = String(analysisFlowStatus?.phase || '').trim().toLowerCase();
        const isTerminal = phase === 'completed' || phase === 'warning' || phase === 'failed' || (reportStatus && reportStatus !== 'running');
        if (!isTerminal) return;
        setAnalysisFlowStatusHistory((prev) => {
            if (!Array.isArray(prev) || prev.length === 0) return prev;
            const last = prev[prev.length - 1];
            if (Number.isFinite(Number(last?.endedAt))) return prev;
            const now = Date.now();
            return [...prev.slice(0, -1), { ...last, endedAt: now }];
        });
    }, [analysisFlowStatus?.phase, analysisUiReport?.status, isAnalyzing]);

    const getBusinessPhaseLabel = useCallback((phase) => {
        const key = String(phase || '').trim().toLowerCase();
        const map = {
            script_opt: t('剧本整理与可拍化', 'Script adaptation and shootability planning'),
            extract_assets: t('角色道具场景清单整理', 'Character/prop/environment list preparation'),
            scene_beats: t('场景拆解与节拍规划', 'Scene breakdown and beat planning'),
            storyboard: t('镜头任务准备', 'Storyboard task preparation'),
            assets_gen: t('视觉资产生成', 'Visual asset generation'),
            completed: t('分析总结与入库完成', 'Analysis summary and import completed'),
            warning: t('结果需人工复核', 'Result needs manual review'),
            failed: t('本轮处理失败', 'This run failed'),
            running: t('处理中', 'In progress'),
        };
        return map[key] || key || t('步骤', 'Step');
    }, [t]);

    const toBusinessHistoryMessage = useCallback((rawMessage) => {
        let text = String(rawMessage || '').trim();
        if (!text) return '';
        const replacements = [
            [/\bLLM\b/gi, t('AI引擎', 'AI engine')],
            [/\bSubject Index\b/gi, t('角色/道具/场景清单', 'Character/prop/environment list')],
            [/\bscene_markdown\b/gi, t('场景拆解内容', 'scene breakdown content')],
            [/\bscript_optimization\b/gi, t('剧本整理阶段', 'script adaptation stage')],
            [/\bassets_extraction\b/gi, t('资产清单整理阶段', 'asset list stage')],
            [/\bcover_poster\b/gi, t('封面海报', 'cover poster')],
            [/\bproject_visual_backfill\b/gi, t('项目视觉基调信息', 'project visual baseline info')],
            [/\bJSON\b/g, t('结构化结果', 'structured result')],
            [/\bAPI\b/g, t('服务接口', 'service API')],
        ];
        replacements.forEach(([pattern, value]) => {
            text = text.replace(pattern, value);
        });
        return text;
    }, [t]);

    const formatHistoryClock = useCallback((value) => {
        const num = Number(value);
        if (!Number.isFinite(num) || num <= 0) return '';
        return new Date(num).toLocaleTimeString([], { hour12: false });
    }, []);

    const finalizeAnalysisFlowHistoryForPhase = useCallback((phase, finalMessage = '') => {
        const targetPhase = String(phase || '').trim();
        if (!targetPhase) return;
        const completionMessage = String(finalMessage || '').trim();
        setAnalysisFlowStatusHistory((prev) => {
            if (!Array.isArray(prev) || prev.length === 0) return prev;
            const now = Date.now();
            let lastOpenIdx = -1;
            prev.forEach((item, idx) => {
                if (String(item?.phase || '').trim() === targetPhase && !Number.isFinite(Number(item?.endedAt))) {
                    lastOpenIdx = idx;
                }
            });
            if (lastOpenIdx < 0) return prev;
            return prev.map((item, idx) => {
                if (String(item?.phase || '').trim() !== targetPhase) return item;
                if (Number.isFinite(Number(item?.endedAt))) return item;
                return {
                    ...item,
                    ...(idx === lastOpenIdx && completionMessage ? { message: completionMessage } : {}),
                    endedAt: now,
                };
            });
        });
    }, []);

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
        if (normalized === 'ANALYSIS_SUBJECT_INDEX_POSTER_ROW_MISSING') {
            return t('Subject Index 缺少封面海报行。第二阶段资产清单必须包含唯一且置尾的 cover_poster/poster 条目。', 'Subject Index is missing the cover poster row. Stage 2 asset extraction must include one final cover_poster/poster row.');
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
        const normalized = stable.toLowerCase();
        if (!normalized) {
            return '';
        }
        if (stable.startsWith('{') && stable.includes('SCENE_MARKDOWN_PARTIAL_FAILURE')) {
            try {
                const parsed = JSON.parse(stable);
                const failedScenes = Array.isArray(parsed?.failed_scenes) ? parsed.failed_scenes : [];
                const failedCount = Number(parsed?.failed_count) || failedScenes.length;
                const totalCount = Number(parsed?.total_count) || failedCount;
                const sceneDetails = failedScenes
                    .map((item) => {
                        const sceneId = String(item?.scene_id || '').trim();
                        const errorCode = String(item?.error_code || 'SCENE_MARKDOWN_ORCHESTRATION_FAILED').trim();
                        return sceneId ? `${sceneId}(${errorCode})` : errorCode;
                    })
                    .filter(Boolean)
                    .join(', ');
                return t(
                    `场景编排失败：${failedCount}/${totalCount} 场未通过校验。${sceneDetails ? `失败场景：${sceneDetails}。` : ''}常见原因：LLM 未返回含 Scene ID 的 Scenes Table、Scene ID 不匹配，或返回了 Subject Index。系统将尝试逐场重试。`,
                    `Scene beats orchestration failed: ${failedCount}/${totalCount} scene(s) did not pass validation.${sceneDetails ? ` Failed scenes: ${sceneDetails}.` : ''} Common causes: missing Scenes Table with Scene ID, Scene ID mismatch, or Subject Index returned instead. Sequential per-scene retry will be attempted.`
                );
            } catch (_) {
                // fall through to generic handling
            }
        }
        if (
            normalized.includes('scene_markdown_partial_failure')
            || normalized.includes('scene_markdown_orchestration_failed')
        ) {
            return t(
                '场景编排失败：后端并行编排未返回有效的 Scenes Table。请检查 Stage 2.1 资产清单是否完整，或稍后重试单场重排。',
                'Scene beats orchestration failed: backend parallel orchestration did not return valid Scenes Table output. Verify Stage 2.1 Subject Index is complete, or retry a single scene.'
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

    const isProviderPolicyViolationError = useCallback((error) => {
        const raw = [
            error?.message,
            error?.response?.data?.detail,
            error?.response?.data?.message,
            error?.detail,
        ]
            .map(item => String(item || '').trim())
            .filter(Boolean)
            .join(' ')
            .toLowerCase();

        if (!raw) return false;
        return (
            raw.includes('prohibited_content')
            || raw.includes('prohibited content')
            || raw.includes('供应商政策不允许')
            || raw.includes('policy')
        );
    }, []);

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
                try {
                    const repaired = repairJSON(s);
                    if (repaired && typeof repaired === 'object') {
                        objs.push(repaired);
                    }
                } catch {
                    // ignore
                }
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

    const countSubjectsPayloadItems = useCallback((payload) => {
        if (!payload || typeof payload !== 'object') return 0;
        return ['characters', 'props', 'environments', 'posters', 'covers'].reduce((sum, key) => (
            sum + (Array.isArray(payload[key]) ? payload[key].length : 0)
        ), 0);
    }, []);

    const normalizePosterBucketsInSubjectsPayload = useCallback((payload) => {
        if (!payload || typeof payload !== 'object') return payload;
        const posters = Array.isArray(payload.posters) ? payload.posters : [];
        const covers = Array.isArray(payload.covers) ? payload.covers : [];
        if (!posters.length && !covers.length) return payload;

        const seen = new Set();
        const merged = [];
        for (const item of [...posters, ...covers]) {
            if (!item || typeof item !== 'object') continue;
            const dedupeKey = [
                String(item.subject_no || '').trim().toLowerCase(),
                String(item.name || item.subject_name_exact || '').trim().toLowerCase(),
                String(item.name_en || '').trim().toLowerCase(),
            ].join('|');
            if (seen.has(dedupeKey)) continue;
            seen.add(dedupeKey);
            merged.push(item);
        }
        if (!merged.length) return payload;
        return {
            ...payload,
            posters: merged,
            covers: merged,
        };
    }, []);

    const resolveSubjectsJsonFromAnalyzeResult = useCallback((result, analysisText) => {
        const backendJson = (result?.subjects_json && typeof result.subjects_json === 'object')
            ? result.subjects_json
            : null;
        const textJson = String(analysisText || '').trim()
            ? (getAnalysisEntitiesPayloadFromJsonText(analysisText) || null)
            : null;

        const normalizedBackend = normalizePosterBucketsInSubjectsPayload(backendJson);
        const normalizedText = normalizePosterBucketsInSubjectsPayload(textJson);
        const backendCount = countSubjectsPayloadItems(normalizedBackend);
        const textCount = countSubjectsPayloadItems(normalizedText);

        if (backendCount > 0) return normalizedBackend;
        if (textCount > 0) return normalizedText;
        return normalizedBackend || normalizedText || {};
    }, [countSubjectsPayloadItems, getAnalysisEntitiesPayloadFromJsonText, normalizePosterBucketsInSubjectsPayload]);

    const repairJSON = (jsonStr) => {
        try {
            return JSON.parse(jsonStr);
        } catch (e) {
            // Regex to match "key": value where value is unquoted
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
                        .replace(/\n/g, '\\n'); // Avoid actual newlines in string
                    
                    return `"${key}": "${safeValue}"`;
                }
            );
            try {
                return JSON.parse(repaired);
            } catch(e2) {
                return [];
            }
        }
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
        const directResultContent = asText(result?.result_content);
        if (directResultContent) return directResultContent;
        const directAnalysis = asText(result?.analysis);
        if (directAnalysis) return directAnalysis;
        const directContent = asText(result?.content);
        if (directContent) return directContent;
        const nestedDataResult = asText(result?.data?.result);
        if (nestedDataResult) return nestedDataResult;
        const nestedDataContent = asText(result?.data?.content);
        if (nestedDataContent) return nestedDataContent;
        return asText(result);
    }, []);

    const buildCanonicalAssetDesignJsonText = useCallback((subjectsJson) => {
        if (!subjectsJson || typeof subjectsJson !== 'object') return '';
        try {
            const rawJsonText = JSON.stringify(subjectsJson, null, 2);
            const normalizedPayload = getAnalysisEntitiesPayloadFromJsonText(rawJsonText);
            const dataToUse = normalizedPayload || subjectsJson;
            // If all arrays are empty, return '' so fallback can use raw text
            if (!dataToUse || Object.values(dataToUse).every(arr => Array.isArray(arr) ? arr.length === 0 : !arr)) {
                return '';
            }
            return JSON.stringify(dataToUse, null, 2);
        } catch (_) {
            return '';
        }
    }, [getAnalysisEntitiesPayloadFromJsonText]);

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
            const plotSummaryRaw = findValueByAliases(obj, ['plot_summary', 'plotSummary', 'story_summary', 'storySummary', '剧情总结']);
            const musicRecommendationRaw = findValueByAliases(obj, ['music_recommendation', 'musicRecommendation', 'score_recommendation', 'scoreRecommendation', '配乐推荐']);

            const payload = {
                Global_Style: toNonEmptyString(globalStyleRaw),
                borrowed_films: toStringArray(borrowedFilmsRaw),
                tone: toNonEmptyString(toneRaw),
                lighting: toNonEmptyString(lightingRaw),
                plot_summary: toNonEmptyString(plotSummaryRaw),
                music_recommendation: toNonEmptyString(musicRecommendationRaw),
            };

            if (payload.Global_Style || payload.borrowed_films.length > 0 || payload.tone || payload.lighting || payload.plot_summary || payload.music_recommendation) {
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
        if (!SUBJECT_CONSISTENCY_CHECK_ENABLED) {
            return createSkippedSubjectConsistencyReport();
        }
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
        const originalIdx = findCol(['originalscripttext', '原始剧本文本', 'original', 'adaptedscripttext', '改编剧本', '改编剧本文本']);

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

    const buildIssueDrivenSupplementPrompt = (basePrompt = '', issues = []) => {
        const normalizedIssues = Array.from(new Set((issues || []).map(v => String(v || '').trim()).filter(Boolean)));
        const issueBlock = normalizedIssues.length > 0
            ? normalizedIssues.map((item, idx) => `${idx + 1}. ${item}`).join('\n')
            : '1. General consistency and completeness check required.';

        const supplementMode = `\n\n[Issue-driven Supplement Mode - Mandatory]\n` +
            `Use the provided text as the current generated analysis draft (NOT original screenplay).\n` +
            `You MUST patch missing entities/structure/problems according to the issue list below.\n` +
            `Comprehensively audit missing content and entities using [Last Generated Analysis Output] plus the optional sections ([Subject Check Result], [Episode 1 AI Script Analysis Attention Notes]); prioritize explicitly identified gaps and regenerate the output parts accordingly.\n` +
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

        if (SUBJECT_CONSISTENCY_CHECK_ENABLED && subjectReport && !subjectReport.ok) {
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

    const localizeFollowupIssueForDisplay = useCallback((issue) => {
        const text = String(issue || '').trim();
        if (!text) return '';
        const missingMatch = text.match(/missing subjects in JSON\s*->\s*(.+)$/i);
        if (missingMatch?.[1]) {
            return t(
                `实体一致性：场景/清单提到但资产 JSON 缺失：${missingMatch[1]}`,
                `Entity consistency: mentioned in scenes/list but missing in asset JSON: ${missingMatch[1]}`
            );
        }
        if (/Subject Index\/Entities consistency check failed/i.test(text)) {
            return t('实体一致性：角色/道具/场景清单与资产 JSON 不一致。', 'Entity consistency: subject list does not match asset JSON.');
        }
        if (/^Analysis warning:\s*/i.test(text)) {
            return text.replace(/^Analysis warning:\s*/i, `${t('分析告警', 'Analysis warning')}: `);
        }
        return text;
    }, [t]);

    const buildAnalysisReviewIssues = useCallback((subjectReport, followupIssues = []) => {
        const fromFollowup = (followupIssues || [])
            .map((item) => localizeFollowupIssueForDisplay(item))
            .filter(Boolean);
        if (fromFollowup.length > 0) {
            return Array.from(new Set(fromFollowup));
        }
        if (SUBJECT_CONSISTENCY_CHECK_ENABLED && subjectReport && !subjectReport.ok) {
            const missing = Array.isArray(subjectReport.missing) ? subjectReport.missing.filter(Boolean) : [];
            if (missing.length > 0) {
                return [t(
                    `实体一致性：场景/清单提到但资产 JSON 缺失：${missing.join('、')}`,
                    `Entity consistency: mentioned in scenes/list but missing in asset JSON: ${missing.join(', ')}`
                )];
            }
            if (subjectReport.message) return [String(subjectReport.message).trim()];
        }
        return [];
    }, [localizeFollowupIssueForDisplay, t]);

    const buildAnalysisReviewWarningMessage = useCallback((issues, { maxItems = 8 } = {}) => {
        const list = (issues || []).map((item) => String(item || '').trim()).filter(Boolean);
        if (list.length === 0) return '';
        const shown = list.slice(0, maxItems);
        const lines = shown.map((item, idx) => `${idx + 1}. ${item}`);
        const more = list.length > maxItems
            ? `\n${t(`（另有 ${list.length - maxItems} 项未展开）`, `(+${list.length - maxItems} more not shown)`)}`
            : '';
        return `${t('检测到以下问题，建议核对后点击「修正生成结果」重跑：', 'Issues detected. Review them and click "Refine Generated Result" to rerun:')}\n${lines.join('\n')}${more}`;
    }, [t]);

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

    const persistFirstPassIssuesToAttentionNotes = async (subjectReport, warnings = [], extraIssues = []) => {
        const followupIssues = collectFollowupIssues(subjectReport, warnings, extraIssues);
        if (followupIssues.length === 0) return [];

        const mergedAttentionNotes = mergeAnalysisAttentionNotesWithIssues(analysisAttentionNotes, followupIssues);
        if (mergedAttentionNotes !== String(analysisAttentionNotes || '').trim()) {
            setAnalysisAttentionNotes(mergedAttentionNotes);
            try {
                await saveAnalysisAttentionNotesValue(mergedAttentionNotes);
                if (onLog) onLog('First-pass issues were recorded in the local review notes.', 'info');
            } catch (saveErr) {
                if (onLog) onLog(`Failed to persist first-pass issues: ${saveErr?.message || saveErr}`, 'warning');
            }
        }

        return followupIssues;
    };

    const publishAnalysisReviewFindings = useCallback(async ({
        subjectReport = null,
        integrityWarnings = [],
        importWarningMessage = '',
    } = {}) => {
        const followupIssues = await persistFirstPassIssuesToAttentionNotes(
            subjectReport,
            integrityWarnings,
            importWarningMessage ? [importWarningMessage] : []
        );
        const reviewIssues = buildAnalysisReviewIssues(subjectReport, followupIssues);
        setAnalysisReviewIssues(reviewIssues);
        if (reviewIssues.length > 0) {
            const message = buildAnalysisReviewWarningMessage(reviewIssues);
            setAnalysisFlowStatus({ phase: 'warning', message });
            if (onLog) {
                onLog(`Analysis review issues (${reviewIssues.length}):\n${reviewIssues.map((item, idx) => `${idx + 1}. ${item}`).join('\n')}`, 'warning');
            }
        }
        return { followupIssues, reviewIssues };
    }, [analysisAttentionNotes, buildAnalysisReviewIssues, buildAnalysisReviewWarningMessage, onLog]);

    const buildSupplementSubmissionInput = ({ generatedContent = '', subjectCheckText = '', attentionNotes = '' }) => {
        const base = String(generatedContent || '').trim();
        const subject = String(subjectCheckText || '').trim();
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
        if (notes) sections.push('[Episode 1 AI Script Analysis Attention Notes]\n' + notes);

        return sections.join('\n\n');
    };

    function buildStage1ProjectContextSection() {
        const info = (project?.global_info && typeof project.global_info === 'object') ? project.global_info : {};
        if (!info || Object.keys(info).length === 0) return '';

        const visual = (info?.tech_params && typeof info.tech_params === 'object' && info.tech_params.visual_standard && typeof info.tech_params.visual_standard === 'object')
            ? info.tech_params.visual_standard
            : {};
        const normalizeInfoKey = (key) => String(key || '').toLowerCase().replace(/[\s\-]/g, '_').trim();
        const getInfoValue = (aliases = []) => {
            const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
            for (const [key, value] of Object.entries(info || {})) {
                if (!normalizedAlias.has(normalizeInfoKey(key))) continue;
                const text = String(value || '').trim();
                if (text) return text;
            }
            return '';
        };
        const getInfoArray = (aliases = []) => {
            const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
            for (const [key, value] of Object.entries(info || {})) {
                if (!normalizedAlias.has(normalizeInfoKey(key))) continue;
                if (Array.isArray(value)) {
                    const items = value.map((item) => String(item || '').trim()).filter(Boolean);
                    if (items.length > 0) return items;
                }
                if (typeof value === 'string') {
                    const items = value.split(/[\n,，;；]/).map((item) => item.trim()).filter(Boolean);
                    if (items.length > 0) return items;
                }
            }
            return [];
        };
        const getVisualValue = (aliases = []) => {
            const normalizedAlias = new Set((aliases || []).map(normalizeInfoKey));
            for (const [key, value] of Object.entries(visual || {})) {
                if (!normalizedAlias.has(normalizeInfoKey(key))) continue;
                const text = String(value || '').trim();
                if (text) return text;
            }
            for (const [key, value] of Object.entries(info || {})) {
                if (!normalizedAlias.has(normalizeInfoKey(key))) continue;
                const text = String(value || '').trim();
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
            metaParts.push('Language: (empty)');
            metaParts.push('Language Warning: project language is empty. You MUST infer one target natural language from script context and keep all natural-language descriptions consistently in that single language.');
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
        metaParts.push('Use this project context as first-class constraints before analyzing the script.');

        return metaParts.length > 1 ? metaParts.join('\n') : '';
    }

    const ensureStage1ProjectContextInjected = useCallback((inputText) => {
        const scriptText = String(inputText || '').trim();
        if (!scriptText) return '';
        if (scriptText.startsWith('Project Context (prepend and treat as high-priority constraints):')) {
            return scriptText;
        }

        const projectContextSection = buildStage1ProjectContextSection();
        if (!projectContextSection) return scriptText;
        return `${projectContextSection}\n\nScript to Analyze:\n\n${scriptText}`;
    }, [project?.global_info]);

    const runSubjectConsistencyCheck = (rawText = null, options = {}) => {
        if (!SUBJECT_CONSISTENCY_CHECK_ENABLED) {
            return createSkippedSubjectConsistencyReport();
        }
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
        const hasSceneBeats = Boolean(getStageOutputContent('stage2', 'scene_markdown'));
        if (hasSceneBeats) {
            if (onLog) onLog('Post-check action: rerun all scene beats (sync orchestration).', 'info');
            await executeSceneBeatsRerun({ mode: 'all' });
            return;
        }
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
        const splitCells = (line, headerRow) => reconcileSceneTableRowCells(
            cleanMarkdownTableCells(line),
            Array.isArray(headerRow) && headerRow.length > 0 ? headerRow : cleanMarkdownTableCells(line)
        );
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

            const headers = cleanMarkdownTableCells(lines[0]);
            const normalizedHeaders = headers.map(normalize);
            const sceneIdIdx = findColIdx(normalizedHeaders, ['sceneid', '场景id']);
            const sceneNoIdx = findColIdx(normalizedHeaders, ['sceneno', '场次序号', '场次']);
            const sceneNameIdx = findColIdx(normalizedHeaders, ['scenename', '场景名', '场景名称']);
            const coreInfoIdx = findColIdx(normalizedHeaders, ['coresceneinfo', '核心场景信息']);
            const originalIdx = findColIdx(normalizedHeaders, ['originalscripttext', '原始剧本文本', 'scripttext', 'adaptedscripttext', '改编剧本', '改编剧本文本']);

            if (sceneIdIdx < 0 && sceneNoIdx < 0 && sceneNameIdx < 0) {
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

                const cells = splitCells(line, headers);
                const sceneId = String(cells[sceneIdIdx] || '').trim();
                const sceneNo = String(sceneNoIdx >= 0 ? (cells[sceneNoIdx] || '') : '').trim();
                const sceneName = String(sceneNameIdx >= 0 ? (cells[sceneNameIdx] || '') : '').trim();
                let coreInfo = String(coreInfoIdx >= 0 ? (cells[coreInfoIdx] || '') : '').trim();
                let originalText = String(originalIdx >= 0 ? (cells[originalIdx] || '') : '').trim();

                // LLM rows may include unescaped "|" in long markdown cells; avoid over-dropping valid rows.
                if (!coreInfo && !originalText && cells.length > headers.length) {
                    const startIdx = Math.max(0, coreInfoIdx >= 0 ? coreInfoIdx : (sceneNameIdx >= 0 ? sceneNameIdx + 1 : 0));
                    const endIdx = Math.min(cells.length, headers.length);
                    const mergedTail = cells.slice(startIdx, endIdx).join(' | ').trim();
                    if (mergedTail) {
                        if (!coreInfo) coreInfo = mergedTail;
                        if (!originalText) originalText = mergedTail;
                    }
                }

                if (!sceneId && !sceneNo && !sceneName) {
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

    const resetAutoSubjectsImportCache = useCallback(() => {
        lastAutoSubjectsImportRef.current = { signature: '', result: null };
    }, []);

    const buildSubjectsImportSignature = useCallback((payload) => {
        if (!payload || typeof payload !== 'object') return '';
        try {
            return JSON.stringify({
                characters: Array.isArray(payload.characters) ? payload.characters : [],
                props: Array.isArray(payload.props) ? payload.props : [],
                environments: Array.isArray(payload.environments) ? payload.environments : [],
                posters: Array.isArray(payload.posters) ? payload.posters : [],
                covers: Array.isArray(payload.covers) ? payload.covers : [],
            });
        } catch (_) {
            return '';
        }
    }, []);

    const importSubjectsJsonWithDedupe = useCallback(async (text, options = {}) => {
        const importOptions = (options && typeof options.importOptions === 'object') ? options.importOptions : {};
        const subjectsJson = (options?.subjectsJson && typeof options.subjectsJson === 'object')
            ? normalizePosterBucketsInSubjectsPayload(options.subjectsJson)
            : normalizePosterBucketsInSubjectsPayload(getAnalysisEntitiesPayloadFromJsonText(text));
        const importReason = String(options?.reason || 'auto-subjects-import').trim() || 'auto-subjects-import';
        const signature = buildSubjectsImportSignature(subjectsJson);

        if (signature && lastAutoSubjectsImportRef.current.signature === signature) {
            onLog?.(`[Asset Gen Tracking] Skipped duplicate subjects import (${importReason}); identical payload already imported in this run.`, 'info');
            return lastAutoSubjectsImportRef.current.result || {
                ok: true,
                changed: false,
                importedSubjectCounts: { character: 0, prop: 0, environment: 0, poster: 0 },
                createdSubjectItems: [],
                skippedSubjectItems: [],
            };
        }

        const importResult = await doImportText(text, 'json', {
            ...importOptions,
            subjectsJson: subjectsJson || importOptions.subjectsJson || null,
            suppressAlerts: importOptions.suppressAlerts !== false,
        });

        if (signature && importResult) {
            lastAutoSubjectsImportRef.current = { signature, result: importResult };
        }

        return importResult;
    }, [buildSubjectsImportSignature, doImportText, getAnalysisEntitiesPayloadFromJsonText, normalizePosterBucketsInSubjectsPayload, onLog]);

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
            + (Array.isArray(subjectsJson.environments) ? subjectsJson.environments.length : 0)
            + (Array.isArray(subjectsJson.posters) ? subjectsJson.posters.length : 0)
            + (Array.isArray(subjectsJson.covers) ? subjectsJson.covers.length : 0);
        if (expectedCount <= 0) {
            return importReport;
        }

        const importedCounts = importReport?.importedSubjectCounts || {};
        const createdCount =
            Number(importedCounts.character || 0)
            + Number(importedCounts.prop || 0)
            + Number(importedCounts.environment || 0)
            + Number(importedCounts.poster || 0);
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

        const subjectsImportReport = await importSubjectsJsonWithDedupe(
            JSON.stringify(subjectsJson, null, 2),
            {
                reason: 'precheck-subjects-json',
                subjectsJson,
                importOptions: { suppressAlerts: true },
            }
        );

        const mergedImportedCounts = {
            character: (Number(importedCounts.character || 0) + Number(subjectsImportReport?.importedSubjectCounts?.character || 0)),
            prop: (Number(importedCounts.prop || 0) + Number(subjectsImportReport?.importedSubjectCounts?.prop || 0)),
            environment: (Number(importedCounts.environment || 0) + Number(subjectsImportReport?.importedSubjectCounts?.environment || 0)),
            poster: (Number(importedCounts.poster || 0) + Number(subjectsImportReport?.importedSubjectCounts?.poster || 0)),
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
    }, [importSubjectsJsonWithDedupe, onImportText, onLog]);

    const runAutoImportAndSwitchToScenes = async (analyzedText, options = {}) => {
        if (autoImportRunningRef.current) {
            if (onLog) onLog('Skipped duplicate auto-import run while another import is already active in this view.', 'warning');
            return null;
        }
        autoImportRunningRef.current = true;
        try {
            const switchToScenes = options?.switchToScenes !== false;
            const importOptions = (options && typeof options.importOptions === 'object') ? options.importOptions : {};
            const replaceExistingScenes = options?.replaceExistingScenes !== false
                && importOptions?.replaceExistingScenes !== false;
            if (typeof onImportText !== 'function') {
                if (onLog) onLog('Import is not available in this context.', 'warning');
                setAnalysisFlowStatus({
                    phase: 'completed',
                    message: t('分析完成（当前上下文不支持自动导入）', 'Analysis completed (auto import is not available in this context)'),
                });
                return null;
            }

            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('🎬 AI导演已交稿，正在校验场景编排结果...', 'LLM response received, validating scene beats result...'),
            });

            if (onLog) onLog('Auto-importing analysis result...', 'process');       
            const check = validateAutoSceneTableImport(analyzedText || '');
            if (check.ok && check.warning && onLog) onLog(check.warning, 'warning');
            if (!check.ok && onLog) onLog(`Auto scene-table check skipped: ${check.reason}`, 'warning');

            if (replaceExistingScenes && activeEpisode?.id) {
                try {
                    await purgeEpisodeWorkspaceScenes('auto-import-replace');
                } catch (clearErr) {
                    onLog?.(`Pre-import scene purge warning: ${clearErr?.message || clearErr}`, 'warning');
                }
            }

            // Prefer importing the validated scene table only. This prevents
            // Subject Index text from being misidentified as scene rows.
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('🧩 场景编排校验通过，正在导入场景到工作区...', 'Scene beats validated, importing scenes to workspace...'),
            });

            const importReport = check.ok
                ? await onImportText(check.tableText || '', 'scene', { ...importOptions, skipDbVerify: true, replaceExistingScenes: false })
                : await onImportText(analyzedText || '', 'auto', { ...importOptions, skipDbVerify: true, replaceExistingScenes: false });
            if (onLog) onLog('Auto-import finished.', 'success');
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('✅ 场景编排导入完成，正在整理后续状态...', 'Scene beats import completed, finalizing post-process state...'),
            });

            const subjectsJson = importOptions?.subjectsJson || getAnalysisEntitiesPayloadFromJsonText(analyzedText || '');
            const signature = buildSubjectsImportSignature(subjectsJson);
            
            const importedCounts = importReport?.importedSubjectCounts || {};
            const createdCount = Number(importedCounts.character || 0) + Number(importedCounts.prop || 0) + Number(importedCounts.environment || 0);
            const skippedCount = Array.isArray(importReport?.skippedSubjectItems) ? importReport.skippedSubjectItems.length : 0;
            const handledCount = createdCount + skippedCount;
            
            const expectedCount = (Array.isArray(subjectsJson?.characters) ? subjectsJson.characters.length : 0) +
                                  (Array.isArray(subjectsJson?.props) ? subjectsJson.props.length : 0) +
                                  (Array.isArray(subjectsJson?.environments) ? subjectsJson.environments.length : 0);

            if (signature && handledCount >= expectedCount && expectedCount > 0) {
                lastAutoSubjectsImportRef.current = {
                    signature,
                    result: importReport || {},
                };
            }

            if (switchToScenes && typeof onSwitchToScenes === 'function') {
                onSwitchToScenes();
            }

            const importedSceneCount = resolveImportReportSceneCount(importReport, importReport?.sceneSubjectPostImportReport, null);
            if (importedSceneCount > 0 && activeEpisode?.id) {
                lastSceneImportSuccessRef.current = {
                    episodeId: Number(activeEpisode.id),
                    count: importedSceneCount,
                    at: Date.now(),
                };
            }

            return importReport || null;
        } finally {
            autoImportRunningRef.current = false;
        }
    };

    const ensureSceneTableConsistencyBeforePhase2 = useCallback(async (analysisText, options = {}) => {
        const stableEpisodeId = activeEpisode?.id;
        if (!stableEpisodeId) {
            return {
                checked: false,
                hasSceneMarkdown: false,
                isConsistent: true,
                repaired: false,
                reason: 'no_episode',
            };
        }

        const stableAnalysisText = String(analysisText || '').trim();
        const sceneCheck = validateAutoSceneTableImport(stableAnalysisText);
        if (!sceneCheck.ok || !String(sceneCheck.tableText || '').trim()) {
            if (sceneCheck.reason && onLog) {
                onLog(`Scene markdown precheck skipped: ${sceneCheck.reason}`, 'info');
            }
            const dbScenesWithoutMarkdown = await fetchScenes(stableEpisodeId).catch(() => []);
            const dbSceneCountWithoutMarkdown = Array.isArray(dbScenesWithoutMarkdown) ? dbScenesWithoutMarkdown.length : 0;
            if (dbSceneCountWithoutMarkdown > 0) {
                if (onLog) onLog(`Scene markdown precheck: no parseable markdown text, but episode already has ${dbSceneCountWithoutMarkdown} scene(s) in DB.`, 'info');
                return {
                    checked: true,
                    hasSceneMarkdown: true,
                    isConsistent: true,
                    repaired: false,
                    reason: 'db_scenes_already_imported',
                    dbCount: dbSceneCountWithoutMarkdown,
                };
            }
            return {
                checked: true,
                hasSceneMarkdown: false,
                isConsistent: true,
                repaired: false,
                reason: 'no_complete_scene_markdown',
            };
        }

        const parsed = parseMarkdownTable(sceneCheck.tableText);
        const headers = Array.isArray(parsed?.headers) ? parsed.headers : [];
        const rows = Array.isArray(parsed?.rows) ? parsed.rows : [];
        if (!headers.length || !rows.length) {
            const dbScenesUnparseable = await fetchScenes(stableEpisodeId).catch(() => []);
            const dbSceneCountUnparseable = Array.isArray(dbScenesUnparseable) ? dbScenesUnparseable.length : 0;
            if (dbSceneCountUnparseable > 0) {
                if (onLog) onLog(`Scene markdown precheck: markdown table unparseable, but episode already has ${dbSceneCountUnparseable} scene(s) in DB.`, 'info');
                return {
                    checked: true,
                    hasSceneMarkdown: true,
                    isConsistent: true,
                    repaired: false,
                    reason: 'db_scenes_already_imported',
                    dbCount: dbSceneCountUnparseable,
                };
            }
            return {
                checked: true,
                hasSceneMarkdown: false,
                isConsistent: true,
                repaired: false,
                reason: 'scene_markdown_unparseable',
            };
        }

        const normalizeKey = (value) => String(value || '').toLowerCase().replace(/\s+/g, '').trim();
        const findHeaderIndex = (aliases = []) => {
            const normalizedAliases = aliases.map(normalizeKey);
            return headers.findIndex((h) => normalizedAliases.includes(normalizeKey(h)));
        };

        const sceneIdIdx = findHeaderIndex(['Scene ID', '场景ID']);
        const sceneNoIdx = findHeaderIndex(['Scene No.', 'Scene No', '场次序号', '场次']);
        const sceneNameIdx = findHeaderIndex(['Scene Name', '场景名', '场景名称']);

        const normalizeSceneToken = (value) => String(value || '').trim().toLowerCase();
        const markdownKeys = rows.map((row) => {
            const sceneId = sceneIdIdx >= 0 ? normalizeSceneToken(row?.[sceneIdIdx]) : '';
            const sceneNo = sceneNoIdx >= 0 ? normalizeSceneToken(row?.[sceneNoIdx]) : '';
            const sceneName = sceneNameIdx >= 0 ? normalizeSceneToken(row?.[sceneNameIdx]) : '';
            if (sceneId) return `id:${sceneId}`;
            if (sceneNo) return `no:${sceneNo}`;
            return `name:${sceneName}`;
        }).filter((token) => token !== 'name:' && token !== 'no:' && token !== 'id:');

        const dbScenes = await fetchScenes(stableEpisodeId).catch(() => []);
        const dbKeys = (Array.isArray(dbScenes) ? dbScenes : []).map((scene) => {
            const sceneId = normalizeSceneToken(scene?.scene_id || scene?.scene_code || '');
            const sceneNo = normalizeSceneToken(scene?.scene_no || '');
            const sceneName = normalizeSceneToken(scene?.scene_name || scene?.location || '');
            if (sceneId) return `id:${sceneId}`;
            if (sceneNo) return `no:${sceneNo}`;
            return `name:${sceneName}`;
        }).filter((token) => token !== 'name:' && token !== 'no:' && token !== 'id:');

        const uniqueMarkdown = [...new Set(markdownKeys)];
        const uniqueDb = [...new Set(dbKeys)];
        const dbSet = new Set(uniqueDb);
        const markdownSet = new Set(uniqueMarkdown);

        const missingInDb = uniqueMarkdown.filter((k) => !dbSet.has(k));
        const extraInDb = uniqueDb.filter((k) => !markdownSet.has(k));
        const isConsistent = missingInDb.length === 0 && extraInDb.length === 0 && uniqueMarkdown.length === uniqueDb.length;

        if (isConsistent) {
            if (onLog) onLog(`Scene markdown precheck passed: markdown=${uniqueMarkdown.length}, db=${uniqueDb.length}.`, 'success');
            return {
                checked: true,
                hasSceneMarkdown: true,
                isConsistent: true,
                repaired: false,
                reason: 'already_consistent',
                markdownCount: uniqueMarkdown.length,
                dbCount: uniqueDb.length,
            };
        }

        const preflightOnly = options?.preflightOnly === true || options?.setRunningReport === false;
        const countAligned = uniqueMarkdown.length > 0 && uniqueMarkdown.length === uniqueDb.length;
        if (preflightOnly) {
            const reason = isConsistent
                ? 'already_consistent'
                : (uniqueDb.length > 0
                    ? (countAligned ? 'preflight_count_aligned' : 'preflight_db_scenes_present')
                    : 'preflight_inconsistent');
            if (onLog) {
                onLog(
                    `Scene markdown precheck (preflight): markdown=${uniqueMarkdown.length}, db=${uniqueDb.length}, consistent=${isConsistent ? 1 : 0}, missing=${missingInDb.length}, extra=${extraInDb.length}.`,
                    isConsistent ? 'success' : 'info'
                );
            }
            return {
                checked: true,
                hasSceneMarkdown: uniqueMarkdown.length > 0,
                isConsistent,
                repaired: false,
                reason,
                markdownCount: uniqueMarkdown.length,
                dbCount: uniqueDb.length,
            };
        }

        const stageNotice = t(
            '检测到 Scene Markdown 与场景数据表不一致：将清理旧场景并按 Markdown 重新导入。',
            'Detected mismatch between scene markdown and scene table: clearing old scenes and re-importing from markdown.'
        );
        setAnalysisFlowStatus({ phase: 'scene_beats', message: stageNotice });
        if (onLog) {
            onLog(`${stageNotice} markdown=${uniqueMarkdown.length}, db=${uniqueDb.length}, missing=${missingInDb.length}, extra=${extraInDb.length}`, 'warning');
        }

        const shouldSetRunningReport = options?.setRunningReport !== false;
        if (shouldSetRunningReport) {
            const restartStartedAt = Date.now();
            beginAnalysisTimer(restartStartedAt);
            setAnalysisUiReport(prev => ({
                status: 'running',
                startedAt: restartStartedAt,
                durationMs: 0,
                phaseTimings: prev?.phaseTimings || null,
                importReport: prev?.importReport || null,
                runtimeMeta: prev?.runtimeMeta || null,
                warning: stageNotice,
                error: '',
            }));
        }

        const staleScenes = await fetchScenes(stableEpisodeId);
        if (Array.isArray(staleScenes) && staleScenes.length > 0) {
            try {
                const { purgeEpisodeScenes: purgeEpisodeScenesApi } = await import('../../../services/api');
                await purgeEpisodeScenesApi(stableEpisodeId, { clearProgress: false });
                if (onLog) onLog(`Scene markdown repair: purged ${staleScenes.length} existing scene(s) before re-import.`, 'info');
            } catch (purgeErr) {
                await Promise.all(staleScenes.map((scene) => deleteScene(scene.id)));
                if (onLog) onLog(`Scene markdown repair purge fallback: soft-deleted ${staleScenes.length} scene(s).`, 'warning');
            }
        }

        const repairImportReport = await doImportText(sceneCheck.tableText, 'scene', {
            suppressAlerts: true,
            autoSupplementSceneSubjects: false,
        });

        const repairedDbScenes = await fetchScenes(stableEpisodeId).catch(() => []);
        if (onLog) {
            onLog(`Scene markdown repair import finished: before=${uniqueDb.length}, after=${Array.isArray(repairedDbScenes) ? repairedDbScenes.length : 0}.`, 'success');
        }

        return {
            checked: true,
            hasSceneMarkdown: true,
            isConsistent: false,
            repaired: true,
            reason: 'reimported_from_markdown',
            markdownCount: uniqueMarkdown.length,
            dbCount: uniqueDb.length,
            repairedCount: Array.isArray(repairedDbScenes) ? repairedDbScenes.length : 0,
            importReport: repairImportReport || null,
        };
    }, [activeEpisode?.id, beginAnalysisTimer, deleteScene, doImportText, fetchScenes, onLog, parseMarkdownTable, t, validateAutoSceneTableImport]);

    

    

    function splitMarkdownTableRow(line) {
        let s = String(line || '').trim();
        if (!s) return [];
        if (s.startsWith('|')) s = s.slice(1);
        if (s.endsWith('|')) s = s.slice(0, -1);

        const cells = [];
        let buf = [];
        let escaped = false;
        for (const ch of s) {
            if (escaped) {
                buf.push(ch);
                escaped = false;
                continue;
            }
            if (ch === '\\') {
                escaped = true;
                continue;
            }
            if (ch === '|') {
                cells.push(buf.join('').trim());
                buf = [];
                continue;
            }
            buf.push(ch);
        }
        if (escaped) buf.push('\\');
        cells.push(buf.join('').trim());
        return cells;
    }

    function normalizeSceneTableHeaderKey(header) {
        return String(header || '').toLowerCase().replace(/[\s_.\-]/g, '');
    }

    function cleanMarkdownTableCells(line) {
        return splitMarkdownTableRow(line).map((cell) => String(cell || '')
            .replace(/\\\|/g, '|')
            .replace(/<br\s*\/?>/gi, '\n'));
    }

    function reconcileSceneTableRowCells(cells, headers) {
        const headerCount = Array.isArray(headers) ? headers.length : 0;
        if (!headerCount) return Array.isArray(cells) ? [...cells] : [];

        let row = Array.isArray(cells) ? [...cells] : [];
        while (row.length < headerCount) row.push('');
        if (row.length === headerCount) {
            return row.slice(0, headerCount);
        }

        const coreInfoIdx = headers.findIndex((header) => {
            const normalized = normalizeSceneTableHeaderKey(header);
            return normalized.includes('coresceneinfo') || normalized.includes('核心场景信息');
        });
        const mergeStartIdx = coreInfoIdx >= 0 ? coreInfoIdx : Math.min(5, headerCount - 1);
        const overflow = row.length - headerCount;
        const mergeEndIdx = mergeStartIdx + overflow + 1;
        const merged = [
            ...row.slice(0, mergeStartIdx),
            row.slice(mergeStartIdx, mergeEndIdx).join('|'),
            ...row.slice(mergeEndIdx),
        ];
        while (merged.length < headerCount) merged.push('');
        if (merged.length > headerCount) {
            const tailCount = headerCount - mergeStartIdx - 1;
            return [
                ...merged.slice(0, mergeStartIdx),
                merged.slice(mergeStartIdx, merged.length - tailCount).join('|'),
                ...merged.slice(merged.length - tailCount),
            ].slice(0, headerCount);
        }
        return merged.slice(0, headerCount);
    }

    function parseMarkdownTable(text) {
        if (!text || typeof text !== 'string') return null;
        const lines = text
            .split('\n')
            .map(l => l.trim())
            .filter(l => l.startsWith('|') && l.includes('|'));

        if (lines.length < 2) return null;

        const isSeparatorLine = (line) => /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);

        const headerLine = lines[0];
        const sepLine = lines[1];
        if (isSeparatorLine(headerLine) || !isSeparatorLine(sepLine)) return null;

        const headers = cleanMarkdownTableCells(headerLine);
        if (headers.length === 0) return null;

        const rows = [];
        for (let i = 2; i < lines.length; i++) {
            const line = lines[i];
            if (isSeparatorLine(line)) continue;
            const cells = reconcileSceneTableRowCells(cleanMarkdownTableCells(line), headers);
            if (cells.length === 0) continue;
            rows.push(cells);
        }

        return { headers, rows };
    }

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

        const toTableCandidate = (line) => {
            const raw = String(line || '').trim();
            if (!raw) return '';
            if (raw.startsWith('|') && raw.includes('|')) return raw;
            const firstPipeIdx = raw.indexOf('|');
            if (firstPipeIdx < 0) return '';
            const sliced = raw.slice(firstPipeIdx).trim();
            return sliced.startsWith('|') && sliced.includes('|') ? sliced : '';
        };

        const blocks = [];
        let current = [];
        const flush = () => {
            if (current.length >= 2) blocks.push(current.join('\n').trim());
            current = [];
        };

        for (const rawLine of lines) {
            const candidate = toTableCandidate(rawLine);
            if (candidate) {
                current.push(candidate);
            } else {
                flush();
            }
        }
        flush();

        if (blocks.length <= 0) return '';

        const hasSceneIdHeader = (blockText) => {
            const firstLine = String(blockText || '').split('\n')[0] || '';
            const normalized = firstLine.toLowerCase().replace(/[\s_.\-]/g, '');
            return normalized.includes('sceneid') || normalized.includes('场景id');
        };

        const preferred = blocks.find(hasSceneIdHeader);
        return String(preferred || blocks[0] || '').trim();
    }, []);

    const normalizeLlmMarkdownTable = useCallback((text) => {
        const sceneTableText = extractScenesTableBlock(text);
        const parsed = parseMarkdownTable(sceneTableText);
        if (!parsed) return '';

        const normalizeHeader = (h) => String(h || '').toLowerCase().replace(/[\s_.\-]/g, '');

        // Guard: the extracted table must have a Scene ID column to qualify as a Scenes Table.
        // Without this check, Subject Index tables (subject_no / subject_type / ...) would be
        // mistakenly stored as the scene_markdown result.
        const hasSceneIdCol = parsed.headers.some((h) => {
            const n = normalizeHeader(h);
            return n.includes('sceneid') || n.includes('场景id');
        });
        
        if (!hasSceneIdCol) {
            return '';
        }

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

    const mergeStage2_2SceneTableOutputs = useCallback((sceneOutputs) => {
        const outputs = Array.isArray(sceneOutputs) ? sceneOutputs : [];
        let mergedHeaders = null;
        const mergedRows = [];

        for (const rawOutput of outputs) {
            const sceneTableText = extractScenesTableBlock(rawOutput);
            const parsed = parseMarkdownTable(sceneTableText);
            if (!parsed?.headers?.length) continue;
            if (!mergedHeaders) {
                mergedHeaders = parsed.headers;
            }
            for (const row of parsed.rows || []) {
                const nextRow = [...row];
                while (nextRow.length < mergedHeaders.length) nextRow.push('');
                mergedRows.push(nextRow.slice(0, mergedHeaders.length));
            }
        }

        if (!mergedHeaders || mergedRows.length === 0) return '';
        const tableText = buildMarkdownTable(mergedHeaders, mergedRows);
        return `### Part 1: Scenes Table\n\n${tableText}`.trim();
    }, [buildMarkdownTable, extractScenesTableBlock, parseMarkdownTable]);

    const alignTableRowToHeaders = useCallback((row, sourceHeaders, targetHeaders) => {
        const source = Array.isArray(row) ? row : [];
        const srcHeaders = Array.isArray(sourceHeaders) ? sourceHeaders : [];
        const dstHeaders = Array.isArray(targetHeaders) ? targetHeaders : [];
        const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_.\-]/g, '');
        return dstHeaders.map((header) => {
            const normalized = normalizeHeader(header);
            const sourceIdx = srcHeaders.findIndex((item) => normalizeHeader(item) === normalized);
            if (sourceIdx < 0) return '';
            return String(source[sourceIdx] ?? '').trim();
        });
    }, []);

    const mergeSceneTableRowBySceneId = useCallback((existingText, patchText, sceneId) => {
        const targetSceneId = String(sceneId || '').trim();
        const existingTableText = extractScenesTableBlock(existingText);
        const patchTableText = extractScenesTableBlock(patchText);
        const existingParsed = parseMarkdownTable(existingTableText);
        const patchParsed = parseMarkdownTable(patchTableText);
        if (!existingParsed?.headers?.length || !patchParsed?.rows?.length) {
            return String(patchText || existingText || '').trim();
        }

        const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_.\-]/g, '');
        const findSceneIdIdx = (headers) => (headers || []).findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('sceneid') || normalized.includes('场景id');
        });

        const existingSceneIdIdx = findSceneIdIdx(existingParsed.headers);
        const patchSceneIdIdx = findSceneIdIdx(patchParsed.headers);
        const patchRow = (patchParsed.rows || []).find((row) => {
            if (patchSceneIdIdx < 0) return true;
            return String(row[patchSceneIdIdx] || '').trim() === targetSceneId;
        }) || patchParsed.rows[0];

        const alignedRow = alignTableRowToHeaders(patchRow, patchParsed.headers, existingParsed.headers);
        if (existingSceneIdIdx >= 0 && targetSceneId) {
            while (alignedRow.length <= existingSceneIdIdx) alignedRow.push('');
            alignedRow[existingSceneIdIdx] = targetSceneId;
        }
        const nextRows = [...(existingParsed.rows || [])];
        const sceneNoIdx = existingParsed.headers.findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('sceneno') || normalized.includes('场次序号') || normalized === '场次';
        });
        let replaceIdx = existingSceneIdIdx >= 0
            ? nextRows.findIndex((row) => String(row[existingSceneIdIdx] || '').trim() === targetSceneId)
            : -1;
        if (replaceIdx < 0 && sceneNoIdx >= 0) {
            replaceIdx = nextRows.findIndex((row) => String(row[sceneNoIdx] || '').trim() === targetSceneId);
        }

        if (replaceIdx >= 0) {
            nextRows[replaceIdx] = alignedRow;
        } else {
            nextRows.push(alignedRow);
        }

        if (sceneNoIdx >= 0) {
            nextRows.forEach((row, index) => {
                while (row.length <= sceneNoIdx) row.push('');
                row[sceneNoIdx] = String(index + 1);
            });
        }

        return `### Part 1: Scenes Table\n\n${buildMarkdownTable(existingParsed.headers, nextRows)}`.trim();
    }, [alignTableRowToHeaders, buildMarkdownTable, extractScenesTableBlock, parseMarkdownTable]);

    const patchSceneTableRowIdentity = useCallback((tableText, { sceneId, sceneOrder } = {}) => {
        const targetSceneId = String(sceneId || '').trim();
        const sceneTableText = extractScenesTableBlock(tableText);
        const parsed = parseMarkdownTable(sceneTableText);
        if (!parsed?.headers?.length || !parsed?.rows?.length) {
            return String(tableText || '').trim();
        }

        const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_.\-]/g, '');
        const sceneIdIdx = parsed.headers.findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('sceneid') || normalized.includes('场景id');
        });
        const sceneNoIdx = parsed.headers.findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('sceneno') || normalized.includes('场次序号') || normalized === '场次';
        });

        const row = [...(parsed.rows[0] || [])];
        while (row.length < parsed.headers.length) row.push('');
        if (targetSceneId && sceneIdIdx >= 0) row[sceneIdIdx] = targetSceneId;
        if (sceneOrder != null && sceneNoIdx >= 0) row[sceneNoIdx] = String(sceneOrder);

        return `### Part 1: Scenes Table\n\n${buildMarkdownTable(parsed.headers, [row])}`.trim();
    }, [buildMarkdownTable, extractScenesTableBlock, parseMarkdownTable]);

    const splitSceneMarkdownTableBySceneId = useCallback((tableText) => {
        const sceneTableText = extractScenesTableBlock(tableText);
        const parsed = parseMarkdownTable(sceneTableText);
        if (!parsed?.headers?.length || !Array.isArray(parsed.rows) || parsed.rows.length === 0) {
            return {};
        }

        const normalizeHeader = (value) => String(value || '').toLowerCase().replace(/[\s_.\-]/g, '');
        const sceneIdIdx = parsed.headers.findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('sceneid') || normalized.includes('场景id');
        });
        const sceneNoIdx = parsed.headers.findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('sceneno') || normalized.includes('场次序号') || normalized === '场次';
        });
        const sceneNameIdx = parsed.headers.findIndex((header) => {
            const normalized = normalizeHeader(header);
            return normalized.includes('scenename') || normalized.includes('场景名') || normalized.includes('场景名称');
        });

        const byScene = {};
        parsed.rows.forEach((row, index) => {
            const sceneId = sceneIdIdx >= 0 ? String(row[sceneIdIdx] || '').trim() : '';
            const sceneNo = sceneNoIdx >= 0 ? String(row[sceneNoIdx] || '').trim() : '';
            const sceneName = sceneNameIdx >= 0 ? String(row[sceneNameIdx] || '').trim() : '';
            const stableSceneId = sceneId || sceneNo || `SCENE_${index + 1}`;
            const singleTable = buildMarkdownTable(parsed.headers, [row]);
            byScene[stableSceneId] = {
                scene_id: stableSceneId,
                scene_order: index + 1,
                scene_name: sceneName,
                scene_no: sceneNo,
                markdown: `### Part 1: Scenes Table\n\n#### ${sceneName || stableSceneId}\n\n${singleTable}`.trim(),
                updated_at: new Date().toISOString(),
            };
        });
        return byScene;
    }, [buildMarkdownTable, extractScenesTableBlock, parseMarkdownTable]);

    const extractPerSceneOutputsFromResult = useCallback((result) => {
        const items = result?.per_scene_outputs || result?.data?.per_scene_outputs;
        if (!Array.isArray(items) || !items.length) return [];
        return items.map((item) => ({
            sceneId: String(item?.scene_id || item?.sceneId || '').trim(),
            sceneOrder: Number(item?.scene_order ?? item?.sceneOrder ?? 0) || 0,
            markdown: String(item?.markdown || item?.scene_markdown || '').trim(),
        })).filter((item) => item.sceneId && item.markdown);
    }, []);

    const buildSceneMarkdownPatchFromPerSceneOutputs = useCallback((perSceneOutputs, sceneUnits = []) => {
        const unitsById = Object.fromEntries(
            (Array.isArray(sceneUnits) ? sceneUnits : [])
                .map((unit) => [String(unit?.sceneId || '').trim(), unit])
                .filter(([sceneId]) => sceneId)
        );
        const patchMap = {};
        (Array.isArray(perSceneOutputs) ? perSceneOutputs : []).forEach((item) => {
            const sceneId = String(item?.sceneId || '').trim();
            if (!sceneId) return;
            const unit = unitsById[sceneId];
            const patchedText = patchSceneTableRowIdentity(item.markdown, {
                sceneId,
                sceneOrder: item.sceneOrder || unit?.sceneOrder,
            });
            const splitPatch = splitSceneMarkdownTableBySceneId(patchedText);
            const patchEntry = splitPatch[sceneId] || Object.values(splitPatch)[0];
            patchMap[sceneId] = {
                ...(patchEntry && typeof patchEntry === 'object' ? patchEntry : {}),
                scene_id: sceneId,
                scene_order: item.sceneOrder || unit?.sceneOrder || patchEntry?.scene_order,
                scene_name: extractSceneDisplayLabel(unit) || patchEntry?.scene_name,
                markdown: patchedText,
                updated_at: new Date().toISOString(),
            };
        });
        return patchMap;
    }, [extractSceneDisplayLabel, patchSceneTableRowIdentity, splitSceneMarkdownTableBySceneId]);

    const importScenesFromPerScenePatchMap = useCallback(async (patchMap, options = {}) => {
        const entries = Object.entries(patchMap || {}).sort((left, right) => {
            const leftOrder = Number(left?.[1]?.scene_order) || 0;
            const rightOrder = Number(right?.[1]?.scene_order) || 0;
            if (leftOrder !== rightOrder) return leftOrder - rightOrder;
            return String(left[0]).localeCompare(String(right[0]));
        });
        if (options?.replaceExistingScenes && activeEpisode?.id) {
            try {
                await purgeEpisodeScenes(activeEpisode.id, { clearProgress: false });
                onLog?.('Cleared existing episode scenes before per-scene import.', 'info');
            } catch (clearErr) {
                onLog?.(`Pre-import per-scene purge warning: ${clearErr?.message || clearErr}`, 'warning');
            }
        }
        let lastReport = null;
        const sceneReports = [];
        for (const [sceneId, entry] of entries) {
            const importText = String(entry?.markdown || '').trim();
            if (!importText) continue;
            onLog?.(
                t(`[场景导入] ${sceneId} 正在导入工作区...`, `[Scene import] ${sceneId} importing into workspace...`),
                'process'
            );
            const sceneImportReport = await doImportText(importText, 'scene', {
                suppressAlerts: true,
                autoSupplementSceneSubjects: false,
                ...options,
            });
            if (!sceneImportReport) {
                throw new Error(t(
                    `[场景导入] ${sceneId} 导入失败：未返回有效结果。`,
                    `[Scene import] ${sceneId} failed: import returned no result.`
                ));
            }
            sceneReports.push(sceneImportReport);
            lastReport = sceneImportReport;
            onLog?.(
                t(`[场景导入] ${sceneId} 导入完成`, `[Scene import] ${sceneId} import completed`),
                'success'
            );
            if (projectId && activeEpisode?.id) {
                try {
                    await syncSceneUnitsProgress({
                        project_id: Number(projectId),
                        episode_id: Number(activeEpisode.id),
                        script_text: importText,
                        partial: true,
                        target_scene_id: sceneId,
                    });
                } catch (syncErr) {
                    onLog?.(`[Scene Units Sync] warning (${sceneId}): ${syncErr?.message || syncErr}`, 'warning');
                }
            }
        }
        if (entries.length > 0 && sceneReports.length === 0) {
            throw new Error(t(
                '逐场场景导入未执行：编排结果缺少可导入的 Markdown。',
                'Per-scene import did not run: orchestration outputs contained no importable markdown.'
            ));
        }
        return mergeSceneImportReports(sceneReports) || lastReport;
    }, [activeEpisode?.id, doImportText, onLog, projectId, purgeEpisodeScenes, syncSceneUnitsProgress, t]);

    const parseSceneMarkdownBySceneMap = useCallback((rawValue) => {
        const text = String(rawValue || '').trim();
        if (!text) return {};
        try {
            const parsed = JSON.parse(text);
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (_) {
            return {};
        }
    }, []);

    const mergeSceneMarkdownBySceneMaps = useCallback((baseMap = {}, patchMap = {}) => {
        const merged = { ...(baseMap && typeof baseMap === 'object' ? baseMap : {}) };
        Object.entries(patchMap || {}).forEach(([sceneId, entry]) => {
            const key = String(sceneId || entry?.scene_id || '').trim();
            if (!key) return;
            merged[key] = {
                ...(merged[key] || {}),
                ...(entry && typeof entry === 'object' ? entry : {}),
                scene_id: key,
                updated_at: new Date().toISOString(),
            };
        });
        return merged;
    }, []);

    const validateStage2_2BeatsOutput = useCallback((rawText, contextLabel = 'Stage 2.2') => {
        const raw = String(rawText || '').trim();
        if (!raw) {
            return {
                ok: false,
                normalizedText: '',
                reason: t(`${contextLabel} 未返回内容。`, `${contextLabel} returned empty content.`),
            };
        }

        const normalizedText = String(normalizeLlmMarkdownTable(raw) || '').trim();
        const directImportCheck = validateAutoSceneTableImport(raw);
        if (!normalizedText && directImportCheck?.ok) {
            return {
                ok: true,
                normalizedText: String(directImportCheck.tableText || '').trim(),
                warning: directImportCheck.warning || '',
            };
        }
        if (!normalizedText) {
            const looksLikeSubjectIndex = /(?:^|\n)\s*(?:#{0,6}\s*)?(?:Subject\s*Index|Subjects?\s*Index|资产清单|实体清单)\b/i.test(raw)
                || /(?:^|\n)\s*\|\s*subject_no\s*\|\s*subject_type\s*\|/i.test(raw)
                || /subject_no\s*=|subject_type\s*=/i.test(raw);
            return {
                ok: false,
                normalizedText: '',
                reason: looksLikeSubjectIndex
                    ? t(`${contextLabel} 返回了资产清单而不是场景编排表。`, `${contextLabel} returned a Subject Index instead of a Scenes Table.`)
                    : t(`${contextLabel} 未检测到含 Scene ID 的 Scenes Table。`, `${contextLabel} did not contain a Scenes Table with a Scene ID column.`),
            };
        }

        const importCheck = validateAutoSceneTableImport(normalizedText);
        if (!importCheck?.ok) {
            return {
                ok: false,
                normalizedText,
                reason: importCheck?.reason || t(`${contextLabel} 场景表缺少导入所需列或有效行。`, `${contextLabel} scene table is missing importable columns or valid rows.`),
            };
        }

        return {
            ok: true,
            normalizedText: String(importCheck.tableText || normalizedText).trim(),
            warning: importCheck.warning || '',
        };
    }, [normalizeLlmMarkdownTable, validateAutoSceneTableImport, t]);

    const logStage2_2Diagnostics = useCallback(({
        phase = 'stage2_2',
        subjectIndexText = '',
        sceneInputText = '',
        finalInputText = '',
        rawOutputText = '',
        normalizedText = '',
    } = {}) => {
        try {
            const subjectIndexChars = String(subjectIndexText || '').length;
            const sceneInputChars = String(sceneInputText || '').length;
            const finalInputChars = String(finalInputText || '').length;
            const rawText = String(rawOutputText || '');
            const normalized = String(normalizedText || '').trim();
            const rawHasSceneIdHeader = /(?:^|\n)\s*\|[^\n]*(?:Scene\s*ID|场景\s*ID|场景ID)[^\n]*\|/i.test(rawText);
            const normalizedRows = Array.isArray(parseMarkdownTable(normalized)?.rows)
                ? parseMarkdownTable(normalized).rows.length
                : 0;
            const importCheck = validateAutoSceneTableImport(normalized || rawText);
            const importRows = importCheck?.ok
                ? (Array.isArray(parseMarkdownTable(importCheck.tableText || '')?.rows)
                    ? parseMarkdownTable(importCheck.tableText || '').rows.length
                    : 0)
                : 0;
            const msg = `[Stage2.2 Debug] phase=${phase} subject_index_chars=${subjectIndexChars} scene_input_chars=${sceneInputChars} final_input_chars=${finalInputChars} raw_has_scene_id_header=${rawHasSceneIdHeader} normalized_rows=${normalizedRows} import_rows=${importRows}`;
            onLog?.(msg, 'info');
            console.info(msg);
        } catch (_) {
            // best-effort diagnostics
        }
    }, [onLog, validateAutoSceneTableImport]);

    const validateStage2_1SubjectIndexOutput = useCallback((rawText, contextLabel = 'Stage 2.1') => {
        const source = String(rawText || '').trim();
        const subjectIndexText = extractPureSubjectIndexText(source);
        if (!subjectIndexText) {
            return {
                ok: false,
                subjectIndexText: '',
                reason: t(`${contextLabel} 未解析到有效资产清单。`, `${contextLabel} did not produce a valid Subject Index.`),
            };
        }

        const normalizeType = (value) => {
            const key = String(value || '').trim().toLowerCase().replace(/[\s\-]+/g, '_');
            if (!key) return '';
            if (['cover_poster', 'coverposter', 'poster', 'posters', 'cover', 'covers', '封面', '封面海报', '海报'].includes(key)) return 'cover_poster';
            if (['character', 'characters', '角色', '人物'].includes(key)) return 'character';
            if (['prop', 'props', '道具', '物件'].includes(key)) return 'prop';
            if (['environment', 'environments', '场景', '环境'].includes(key)) return 'environment';
            return key;
        };

        const detectedTypes = new Set();
        const lines = String(subjectIndexText || '').split('\n');
        for (const rawLine of lines) {
            const line = String(rawLine || '').trim();
            if (!line) continue;

            const kvType = line.match(/\bsubject_type\s*=\s*([^|\n`]+)/i);
            if (kvType?.[1]) {
                detectedTypes.add(normalizeType(kvType[1]));
                continue;
            }

            const normalizedLine = line.replace(/^\s*>\s*/, '').replace(/^\s*[-*+]\s+/, '').trim();
            if (!normalizedLine.includes('|')) continue;
            const parts = normalizedLine.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((x) => String(x || '').trim());
            if (parts.length < 2) continue;
            const firstCol = String(parts[0] || '').trim().toLowerCase();
            const secondCol = String(parts[1] || '').trim();
            if (['subject_no', 'subject_id', 'id', '编号'].includes(firstCol)) continue;
            if (/^:?-{2,}:?$/.test(firstCol) || /^:?-{2,}:?$/.test(secondCol)) continue;
            if (!secondCol) continue;
            detectedTypes.add(normalizeType(parts[1]));
        }

        if (!detectedTypes.has('cover_poster')) {
            return {
                ok: false,
                subjectIndexText,
                reason: t(
                    `${contextLabel} 缺少 cover_poster/poster 类型资产，按规则判定本次提取失败并需要重试。`,
                    `${contextLabel} is missing cover_poster/poster entries. This extraction is considered failed and must retry.`
                ),
            };
        }

        return { ok: true, subjectIndexText };
    }, [extractPureSubjectIndexText, t]);

    const runStage2_1WithValidationRetry = useCallback(async (runAttempt, contextLabel = 'Stage 2.1') => {
        let result = await runAttempt();
        let text = extractAnalysisTextFromResult(result) || '';
        let validation = validateStage2_1SubjectIndexOutput(text, contextLabel);
        for (let fallbackAttempt = 1; !validation.ok && fallbackAttempt <= MAX_ANALYSIS_FALLBACK_ATTEMPTS; fallbackAttempt += 1) {
            onLog?.(`[Stage 2.1] ${validation.reason}`, 'warning');
            setAnalysisFlowStatus({
                phase: 'extract_assets',
                message: t(
                    `Stage 2.1 校验失败，正在自动重试 (${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS})...`,
                    `Stage 2.1 validation failed. Auto-retrying (${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS})...`
                ),
            });
            result = await runAttempt();
            text = extractAnalysisTextFromResult(result) || '';
            validation = validateStage2_1SubjectIndexOutput(text, `${contextLabel} retry ${fallbackAttempt}`);
        }
        if (!validation.ok) {
            throw new Error(validation.reason || `Stage 2.1 failed after ${MAX_ANALYSIS_FALLBACK_ATTEMPTS} automatic retries.`);
        }
        return { result, text, validation };
    }, [extractAnalysisTextFromResult, onLog, t, validateStage2_1SubjectIndexOutput]);

    const llmMarkdownTableText = useMemo(() => normalizeLlmMarkdownTable(llmResultContent), [llmResultContent, normalizeLlmMarkdownTable]);
    const llmMarkdownTable = useMemo(() => parseMarkdownTable(llmMarkdownTableText), [llmMarkdownTableText]);
    const llmSceneCount = useMemo(() => {
        const rows = Array.isArray(llmMarkdownTable?.rows) ? llmMarkdownTable.rows : [];
        return rows.length;
    }, [llmMarkdownTable]);

    const buildStageOutputsObject = useCallback(({ analysisRawText = '', assetRawText = '', stage1RawText = '', stage2RawText = '', stage2_1Text = '', sceneMarkdownByScene = null, replaceSceneMarkdownByScene = false } = {}) => {
        const resolvedAnalysisRawText = String(analysisRawText || '').trim();
        const resolvedAssetRawText = String(assetRawText || '').trim();
        const resolvedStage1RawText = String(stage1RawText || '').trim();
        const resolvedStage2RawText = String(
            stage2RawText || activeEpisode?.ai_scene_analysis_scene_markdown || ''
        ).trim();
        const stage1ScriptInput = String(activeEpisode?.script_content || rawContent || '').trim();
        const projectContextJson = (() => {
            try {
                return project?.global_info ? JSON.stringify(project.global_info, null, 2) : '';
            } catch (_) {
                return '';
            }
        })();

        const isSceneMarkdownTableText = (candidateText) => {
            const candidate = String(candidateText || '');
            if (!candidate.trim()) return false;
            return /(?:^|\n)\s*(?:#{0,6}\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|场景分析结果|场景表)\b/i.test(candidate)
                || /(?:^|\n)\s*\|[^\n]*(?:Scene\s*ID|Scene\s*No\.?|Core\s*Scene\s*Info|Equivalent\s*Duration|场景\s*ID|场景编号|核心场景信息)[^\n]*\|/i.test(candidate);
        };
        const hasExplicitAdaptedScriptSection = (candidateText) => /(?:###?\s*)?(?:第二部分[:：]?\s*修改后的剧本|Second\s*Part[:：]?\s*Adapted\s*Script|Adapted\s*Script\s*[-(（])/i.test(String(candidateText || ''));

        const stage1AdaptedSource = resolvedStage1RawText
            || (hasExplicitAdaptedScriptSection(resolvedAnalysisRawText) && !isSceneMarkdownTableText(resolvedAnalysisRawText) ? resolvedAnalysisRawText : '');
        const persistedAdaptationText = String(activeEpisode?.ai_scene_analysis_adaptation || '').trim();
        const safePersistedAdaptationText = isSceneMarkdownTableText(persistedAdaptationText) ? '' : persistedAdaptationText;

        const stage1AdaptedScript = String(
            (stage1AdaptedSource ? extractStage1AdaptedScriptBody(stage1AdaptedSource) : '') || safePersistedAdaptationText || ''
        ).trim();
        const stage1VisualBackfillJson = String(
            extractProjectVisualBackfillJsonText(resolvedStage1RawText || resolvedAnalysisRawText) || ''
        ).trim();

        const explicitSubjectIndex = String(stage2_1Text || '').trim();
        const persistedSubjectIndex = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
        const rawStage2_1Text = extractPureSubjectIndexText(explicitSubjectIndex || persistedSubjectIndex || '');

        let parsedSubjectIndexText = rawStage2_1Text;
        let parsedSceneArrangementText = '';

        if (rawStage2_1Text) {
            const sections = extractAnalysisSections(rawStage2_1Text);
            if (sections.hasStructuredSubjectIndex && sections.subjectIndexText) {
                parsedSubjectIndexText = sections.subjectIndexText;
            }
            const match = rawStage2_1Text.match(/(?:^|\n)\s*(?:#{0,6}\s*)?(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体|\[Reusable Subject Assets)/i);
            if (match && match.index > 0) {
                parsedSceneArrangementText = rawStage2_1Text.slice(0, match.index).trim();
            }
        }

        const stage2SubjectIndexText = extractPureSubjectIndexText(String(parsedSubjectIndexText || '').trim());

        const stage2SceneMarkdownFromStage2 = (() => {
            if (!isSceneMarkdownTableText(resolvedStage2RawText)) return '';
            const normalized = String(normalizeLlmMarkdownTable(resolvedStage2RawText || '') || '').trim();
            if (normalized) return normalized;
            return String(resolvedStage2RawText || '').trim();
        })();
        let stage2SceneMarkdown = String(stage2SceneMarkdownFromStage2 || '').trim();
        if (parsedSceneArrangementText) {
            if (stage2SceneMarkdown) {
                stage2SceneMarkdown = `${parsedSceneArrangementText}\n\n${stage2SceneMarkdown}`;
            } else {
                stage2SceneMarkdown = parsedSceneArrangementText;
            }
        }

        const persistedBySceneRaw = (() => {
            try {
                const raw = String(activeEpisode?.ai_stage_outputs || '').trim();
                if (!raw) return '';
                const parsed = JSON.parse(raw);
                return String(parsed?.stages?.stage2?.outputs?.scene_markdown_by_scene?.content || '').trim();
            } catch (_) {
                return '';
            }
        })();
        const persistedBySceneMap = parseSceneMarkdownBySceneMap(persistedBySceneRaw);
        const splitBySceneMap = splitSceneMarkdownTableBySceneId(stage2SceneMarkdown);
        const incomingByScene = sceneMarkdownByScene && typeof sceneMarkdownByScene === 'object'
            ? sceneMarkdownByScene
            : splitBySceneMap;
        const resolvedSceneMarkdownByScene = replaceSceneMarkdownByScene
            ? incomingByScene
            : mergeSceneMarkdownBySceneMaps(
                persistedBySceneMap,
                incomingByScene
            );

        const stage2RawTextForSlot = String(resolvedStage2RawText || '').trim();
        const stage2VisualBackfillJson = String(
            extractProjectVisualBackfillJsonText(resolvedStage2RawText) || stage1VisualBackfillJson || ''
        ).trim();

        const stage3EntitiesPayload = getAnalysisEntitiesPayloadFromJsonText(resolvedAssetRawText);
        const stage3AssetDesignJson = stage3EntitiesPayload
            ? JSON.stringify(stage3EntitiesPayload, null, 2)
            : resolvedAssetRawText;

        return {
            version: 1,
            stages: {
                stage1: {
                    key: 'stage1',
                    title: '第一阶段：剧本修改说明 / 优化后剧本 / 全局风格',
                    restartable: true,
                    inputs: {
                        script_content: {
                            key: 'script_content',
                            kind: 'markdown',
                            title: '原始剧本',
                            content: stage1ScriptInput,
                        },
                        project_context: {
                            key: 'project_context',
                            kind: 'json',
                            title: '项目上下文',
                            content: projectContextJson,
                        },
                    },
                    outputs: {
                        adapted_script: {
                            key: 'adapted_script',
                            kind: 'markdown',
                            title: '优化后剧本',
                            content: stage1AdaptedScript,
                        },
                        project_visual_backfill: {
                            key: 'project_visual_backfill',
                            kind: 'json',
                            title: '全局风格',
                            content: stage1VisualBackfillJson,
                        },
                        raw_text: {
                            key: 'raw_text',
                            kind: 'text',
                            title: '第一阶段完整结果',
                            content: resolvedStage1RawText,
                        },
                    },
                },
                stage2: {
                    key: 'stage2',
                    title: '第二阶段：场景分析结果 / 资产清单',
                    restartable: true,
                    inputs: {
                        adapted_script: {
                            key: 'adapted_script',
                            kind: 'markdown',
                            title: '优化后剧本',
                            content: stage1AdaptedScript,
                        },
                        project_visual_backfill: {
                            key: 'project_visual_backfill',
                            kind: 'json',
                            title: '全局风格',
                            content: stage1VisualBackfillJson,
                        },
                    },
                    outputs: {
                        scene_markdown: {
                            key: 'scene_markdown',
                            kind: 'markdown',
                            title: '场景分析结果（合并）',
                            content: stage2SceneMarkdown,
                        },
                        scene_markdown_by_scene: {
                            key: 'scene_markdown_by_scene',
                            kind: 'json',
                            title: '场景分析结果（分场景）',
                            content: JSON.stringify(resolvedSceneMarkdownByScene, null, 2),
                        },
                        subject_index: {
                            key: 'subject_index',
                            kind: 'markdown',
                            title: '资产清单',
                            content: stage2SubjectIndexText,
                        },
                        project_visual_backfill: {
                            key: 'project_visual_backfill',
                            kind: 'json',
                            title: '全局风格',
                            content: stage2VisualBackfillJson,
                        },
                        raw_text: {
                            key: 'raw_text',
                            kind: 'text',
                            title: '第二阶段完整结果',
                            content: stage2RawTextForSlot,
                        },
                    },
                },
                stage3: {
                    key: 'stage3',
                    title: '第三阶段：资产设计',
                    restartable: true,
                    inputs: {
                        subject_index: {
                            key: 'subject_index',
                            kind: 'markdown',
                            title: '资产清单',
                            content: stage2SubjectIndexText,
                        },
                    },
                    outputs: {
                        asset_design_json: {
                            key: 'asset_design_json',
                            kind: 'json',
                            title: '资产设计',
                            content: String(stage3AssetDesignJson || '').trim(),
                        },
                        raw_text: {
                            key: 'raw_text',
                            kind: 'text',
                            title: '第三阶段完整结果',
                            content: resolvedAssetRawText,
                        },
                    },
                },
            },
        };
    }, [activeEpisode?.ai_scene_analysis_adaptation, activeEpisode?.ai_scene_analysis_scene_markdown, activeEpisode?.ai_scene_analysis_subject_index, activeEpisode?.ai_stage_outputs, activeEpisode?.script_content, extractAnalysisSections, extractProjectVisualBackfillJsonText, extractPureSubjectIndexText, extractStage1AdaptedScriptBody, getAnalysisEntitiesPayloadFromJsonText, mergeSceneMarkdownBySceneMaps, normalizeLlmMarkdownTable, parseSceneMarkdownBySceneMap, project?.global_info, rawContent, splitSceneMarkdownTableBySceneId]);

    const parseStageOutputsObject = useCallback((rawValue) => {
        const text = String(rawValue || '').trim();
        if (!text) return null;
        try {
            const parsed = JSON.parse(text);
            if (parsed && typeof parsed === 'object' && parsed.stages && typeof parsed.stages === 'object') {
                return parsed;
            }
        } catch (_) {
            // ignore invalid persisted payload
        }
        return null;
    }, []);

    const currentStageOutputs = useMemo(() => {
        const persisted = parseStageOutputsObject(activeEpisode?.ai_stage_outputs || '');
        if (persisted?.stages?.stage1?.outputs?.adapted_script) {
            const isSceneMarkdownTableText = (candidateText) => {
                const candidate = String(candidateText || '');
                if (!candidate.trim()) return false;
                return /(?:^|\n)\s*(?:#{0,6}\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|场景分析结果|场景表)\b/i.test(candidate)
                    || /(?:^|\n)\s*\|[^\n]*(?:Scene\s*ID|Scene\s*No\.?|Core\s*Scene\s*Info|Equivalent\s*Duration|场景\s*ID|场景编号|核心场景信息)[^\n]*\|/i.test(candidate);
            };
            const adaptedOutput = persisted.stages.stage1.outputs.adapted_script;
            const adaptedContent = String(adaptedOutput.content || '').trim();
            if (isSceneMarkdownTableText(adaptedContent)) {
                const stage1RawText = String(persisted.stages.stage1.outputs.raw_text?.content || '').trim();
                const persistedAdaptationText = String(activeEpisode?.ai_scene_analysis_adaptation || '').trim();
                const recoveredAdaptedScript = stage1RawText && !isSceneMarkdownTableText(stage1RawText)
                    ? String(extractStage1AdaptedScriptBody(stage1RawText) || '').trim()
                    : (isSceneMarkdownTableText(persistedAdaptationText) ? '' : persistedAdaptationText);
                adaptedOutput.content = recoveredAdaptedScript;
            }
        }
        if (persisted && persisted?.stages?.stage2?.outputs?.subject_index) {
             let subjOutput = persisted.stages.stage2.outputs.subject_index.content || '';
             if (!hasSubjectIndexStructure(subjOutput)) {
                 persisted.stages.stage2.outputs.subject_index.content = '';
             } else {
             let sceneOutput = persisted.stages.stage2.outputs.scene_markdown.content || '';
             
             const match = subjOutput.match(/(?:^|\n)\s*(?:#{0,6}\s*)?(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体|\[Reusable Subject Assets)/i);
             if (match && match.index > 0) {
                 const arrangement = subjOutput.slice(0, match.index).trim();
                 persisted.stages.stage2.outputs.subject_index.content = subjOutput.slice(match.index).trim();
                 
                 if (sceneOutput && !sceneOutput.includes(arrangement)) {
                     persisted.stages.stage2.outputs.scene_markdown.content = `${arrangement}\n\n${sceneOutput}`;
                 } else if (!sceneOutput) {
                     persisted.stages.stage2.outputs.scene_markdown.content = arrangement;
                 }
             }
             }
        }
        if (persisted) return persisted;
        return buildStageOutputsObject({
            analysisRawText: '',
            assetRawText: llmAssetRawResultContent || activeEpisode?.ai_entity_design_result || '',
            stage1RawText: activeEpisode?.ai_scene_analysis_adaptation || '',
            stage2RawText: activeEpisode?.ai_scene_analysis_scene_markdown || '',
            stage2_1Text: activeEpisode?.ai_scene_analysis_subject_index || '',
        });
    }, [activeEpisode?.ai_entity_design_result, activeEpisode?.ai_scene_analysis_adaptation, activeEpisode?.ai_scene_analysis_result, activeEpisode?.ai_scene_analysis_scene_markdown, activeEpisode?.ai_scene_analysis_subject_index, activeEpisode?.ai_stage_outputs, buildStageOutputsObject, extractStage1AdaptedScriptBody, hasSubjectIndexStructure, llmAssetRawResultContent, parseStageOutputsObject]);

    const formatArtifactContent = useCallback((content, kind = 'markdown') => {
        const text = String(content || '').trim();
        if (!text) return '';
        if (kind === 'json') {
            return `\`\`\`json\n${text}\n\`\`\``;
        }
        if (kind === 'text') {
            return `\`\`\`text\n${text}\n\`\`\``;
        }
        return text;
    }, []);

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
        if (!activeEpisode) return;

        const scriptContentKey = `${activeEpisode.id || 0}:${String(activeEpisode.script_content || '')}`;
        const analysisBusy = Boolean(
            isAnalyzing
            || isRetryingPhase2
            || analysisRunInFlightRef.current
        );
        if (analysisBusy && lastEpisodeSyncScriptKeyRef.current === scriptContentKey) {
            return;
        }
        lastEpisodeSyncScriptKeyRef.current = scriptContentKey;

        const trimScriptForInputDisplay = (raw) => {
            const text = String(raw || '');
            if (!text.trim()) return '';
            const startMatch = /`?\[SCENES_BLOCK_START\]`?/i.exec(text);
            if (!startMatch) return text;
            const startIdx = startMatch.index;
            const afterStart = text.slice(startIdx + startMatch[0].length);
            const endMatch = /`?\[SCENES_BLOCK_END\]`?/i.exec(afterStart);
            if (!endMatch) {
                return text.slice(startIdx).trim();
            }
            const endAbs = startIdx + startMatch[0].length + endMatch.index + endMatch[0].length;
            return text.slice(startIdx, endAbs).trim();
        };

        const normalizedScriptContent = trimScriptForInputDisplay(activeEpisode?.script_content);
        const hasAuthoritativeScriptContent = Object.prototype.hasOwnProperty.call(activeEpisode, 'script_content')
            && activeEpisode.script_content != null
            && String(activeEpisode.script_content).length > 0;

        if (hasAuthoritativeScriptContent) {
            setRawContent((prev) => (prev === normalizedScriptContent ? prev : normalizedScriptContent));
        } else if (!Object.prototype.hasOwnProperty.call(activeEpisode, 'script_content')) {
            // List endpoint omits script_content; keep local editor state until full episode loads.
        } else if (!rawContentRef.current) {
            setRawContent((prev) => (prev === '' ? prev : ''));
        }

        if (!Object.prototype.hasOwnProperty.call(activeEpisode, 'script_content')) {
            return;
        }

        if (lastEpisodeSegmentsScriptKeyRef.current === scriptContentKey) {
            return;
        }
        lastEpisodeSegmentsScriptKeyRef.current = scriptContentKey;

        if (!activeEpisode?.script_content) {
            setSegments((prev) => (prev.length === 0 ? prev : []));
            setIsRawMode((prev) => (prev ? prev : true));
            return;
        }

        const content = normalizedScriptContent;
        
        // Mode 1: Markdown Table parser
        const hasTableStructure = /\|\s*Paragraph ID\s*\|/.test(content) || /\|\s*Content \(Revised\)\s*\|/.test(content);
        
        if (hasTableStructure) {
             const lines = content.split('\n').map(l => l.trim()).filter(l => l.includes('|'));
             const parsed = [];
             
             const headerIdx = lines.findIndex(l => l.includes("Paragraph ID") || l.includes("Content (Revised)"));
             if (headerIdx === -1) {
                 setSegments((prev) => (prev.length === 0 ? prev : []));
                 setIsRawMode((prev) => (prev ? prev : true));
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
                 setSegments((prev) => (prev.length === 0 ? prev : []));
                 setIsRawMode((prev) => (prev ? prev : true));
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
            setSegments((prev) => (prev.length === 0 ? prev : []));
            setIsRawMode((prev) => (prev ? prev : true));
        }
    }, [
        activeEpisode?.id,
        activeEpisode?.script_content,
        isAnalyzing,
        isRetryingPhase2,
    ]);

    useEffect(() => {
        if (!activeEpisode) return;

        const skipAiArtifactSync = Boolean(
            analysisRunInFlightRef.current
            || isAnalyzing
            || isRetryingPhase2
        );
        if (!skipAiArtifactSync) {
            const nextSubjectIndexText = extractPureSubjectIndexText(String(activeEpisode?.ai_scene_analysis_subject_index || ''));
            const nextAdaptationText = String(activeEpisode?.ai_scene_analysis_adaptation || '');
            const nextAssetRaw = String(activeEpisode?.ai_entity_design_result || '');
            const stored = activeEpisode?.ai_scene_analysis_scene_markdown || activeEpisode?.ai_scene_analysis_result;
            const storedText = typeof stored === 'string' ? stored : '';
            const nextLlmResultContent = normalizeLlmMarkdownTable(storedText);

            setSubjectIndexText((prev) => (prev === nextSubjectIndexText ? prev : nextSubjectIndexText));
            setAdaptationText((prev) => (prev === nextAdaptationText ? prev : nextAdaptationText));
            setLlmAssetRawResultContent((prev) => (prev === nextAssetRaw ? prev : nextAssetRaw));
            setLlmRawResultContent((prev) => (prev === storedText ? prev : storedText));
            setLlmResultContent((prev) => (prev === nextLlmResultContent ? prev : nextLlmResultContent));
        }

        const nextAttentionNotes = String(activeEpisode?.episode_info?.analysis_attention_notes || '');
        const nextConsistencyText = String(activeEpisode?.episode_info?.subject_check_result || '');
        setAnalysisAttentionNotes((prev) => (prev === nextAttentionNotes ? prev : nextAttentionNotes));
        setSubjectConsistencyResultText((prev) => (prev === nextConsistencyText ? prev : nextConsistencyText));

        const persistedIds = activeEpisode?.episode_info?.reuse_subject_asset_ids;
        const reuseIdsKey = `${activeEpisode.id || 0}:${
            Array.isArray(persistedIds)
                ? persistedIds.map((item) => String(item)).join(',')
                : ''
        }`;
        if (reuseIdsKey !== lastEpisodeReuseSubjectIdsKeyRef.current) {
            lastEpisodeReuseSubjectIdsKeyRef.current = reuseIdsKey;
            const nextReuseIds = reuseIdsKey ? reuseIdsKey.split(',').filter(Boolean) : [];
            setSelectedReuseSubjectIds((prev) => {
                if (prev.length === nextReuseIds.length && prev.every((value, index) => value === nextReuseIds[index])) {
                    return prev;
                }
                return nextReuseIds;
            });
        }
    }, [
        activeEpisode?.id,
        activeEpisode?.ai_scene_analysis_subject_index,
        activeEpisode?.ai_scene_analysis_adaptation,
        activeEpisode?.ai_entity_design_result,
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.ai_scene_analysis_result,
        activeEpisode?.episode_info?.analysis_attention_notes,
        activeEpisode?.episode_info?.subject_check_result,
        Array.isArray(activeEpisode?.episode_info?.reuse_subject_asset_ids)
            ? `${activeEpisode.id || 0}:${activeEpisode.episode_info.reuse_subject_asset_ids.map((item) => String(item)).join(',')}`
            : `${activeEpisode?.id || 0}:`,
        isAnalyzing,
        isRetryingPhase2,
        extractPureSubjectIndexText,
        normalizeLlmMarkdownTable,
    ]);

    useEffect(() => {
        let mounted = true;
        const loadAssets = async () => {
            if (!projectId) {
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
    }, [projectId, analysisUiReport?.importReport, isAnalyzing, isRetryingPhase2]);

    useEffect(() => {
        let mounted = true;
        const loadEpisodeSceneCount = async () => {
            if (!activeEpisode?.id) {
                if (mounted) setDiagnosticsEpisodeSceneCount(0);
                return;
            }
            try {
                const scenes = await fetchScenes(activeEpisode.id);
                if (!mounted) return;
                setDiagnosticsEpisodeSceneCount(Array.isArray(scenes) ? scenes.length : 0);
            } catch (_) {
                if (mounted) setDiagnosticsEpisodeSceneCount(0);
            }
        };
        loadEpisodeSceneCount();
        return () => { mounted = false; };
    }, [
        activeEpisode?.id,
        analysisUiReport?.importReport,
        analysisUiReport?.resolvedSceneImportCount,
        isAnalyzing,
        isRetryingPhase2,
    ]);

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

    const persistLlmResultContent = async (content, resultField = 'ai_scene_analysis_result', options = {}) => {
        if (!activeEpisode?.id) return;
        if (!onUpdateEpisodeInfo) return;

        try {
            const nextContent = String(content || '');
            const updatePayload = { [resultField]: nextContent };
            const logSource = String(options?.source || 'unspecified').trim() || 'unspecified';
            const persistedStageOutputs = parseStageOutputsObject(activeEpisode?.ai_stage_outputs || '');
            const persistedStage1RawText = String(persistedStageOutputs?.stages?.stage1?.outputs?.raw_text?.content || '').trim();
            const persistedStage2RawText = String(persistedStageOutputs?.stages?.stage2?.outputs?.raw_text?.content || '').trim();
            const persistedStage2_1Text = String(persistedStageOutputs?.stages?.stage2?.outputs?.subject_index?.content || '').trim();
            const replaceSceneMarkdownByScene = options?.replaceSceneMarkdownByScene === true
                || (
                    options?.replaceSceneMarkdownByScene !== false
                    && (
                        resultField === 'ai_scene_analysis_scene_markdown'
                        || /stage2_2|scene_beats|scene_markdown|stage1/i.test(logSource)
                        || Boolean(options?.sceneMarkdownByScene)
                    )
                );

            if (resultField === 'ai_scene_analysis_result') {
                const isStage1ResultWrite = /stage1/i.test(logSource) && !/stage2|split-combined/i.test(logSource);

                if (isStage1ResultWrite) {
                    const effectiveStage1RawText = String(options?.stage1RawText || nextContent || '').trim();
                    if (effectiveStage1RawText) {
                        latestStage1RawTextRef.current = effectiveStage1RawText;
                    }
                    const hasExplicitAdaptedScriptSection = /(?:###?\s*)?(?:第二部分[:：]?\s*修改后的剧本|Second\s*Part[:：]?\s*Adapted\s*Script|Adapted\s*Script\s*[-(（])/i.test(effectiveStage1RawText);
                    const looksLikeSceneMarkdownTable = /(?:^|\n)\s*(?:#{0,6}\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|场景分析结果|场景表)\b/i.test(effectiveStage1RawText)
                        || /(?:^|\n)\s*\|[^\n]*(?:Scene\s*ID|Scene\s*No\.?|Core\s*Scene\s*Info|Equivalent\s*Duration|场景\s*ID|场景编号|核心场景信息)[^\n]*\|/i.test(effectiveStage1RawText);
                    const canExtractStage1Adaptation = hasExplicitAdaptedScriptSection || (Boolean(effectiveStage1RawText) && !looksLikeSceneMarkdownTable);
                    const adaptationValue = canExtractStage1Adaptation
                        ? String(extractStage1AdaptedScriptBody(effectiveStage1RawText) || '').trim()
                        : '';
                    const stageOutputsPayload = {
                        analysisRawText: '',
                        assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                        stage1RawText: effectiveStage1RawText,
                        stage2RawText: persistedStage2RawText || '',
                        stage2_1Text: latestStage2_1TextRef.current || persistedStage2_1Text || undefined,
                        sceneMarkdownByScene: options?.sceneMarkdownByScene || null,
                        replaceSceneMarkdownByScene: true,
                    };
                    Object.assign(updatePayload, {
                        ai_scene_analysis_adaptation: adaptationValue,
                        ai_stage_outputs: JSON.stringify(buildStageOutputsObject(stageOutputsPayload), null, 2),
                    });
                    delete updatePayload.ai_scene_analysis_result;
                    onLog?.(`[Analysis Writeback] field=stage1 source=${logSource} raw_len=${nextContent.length} adaptation_len=${adaptationValue.length}`, 'info');
                } else {
                latestAnalysisRawTextRef.current = nextContent;
                if (options?.stage2_1Text !== undefined) {
                    latestStage2_1TextRef.current = options.stage2_1Text;
                }
                const explicitStage2RawText = String(options?.stage2RawText || '').trim();
                const effectiveStage2RawText = explicitStage2RawText || nextContent;
                const effectiveStage1RawText = String(options?.stage1RawText || '').trim();
                if (effectiveStage1RawText) {
                    latestStage1RawTextRef.current = effectiveStage1RawText;
                }
                const extractedSections = extractAnalysisSections(nextContent);
                let subjectIndexValue = extractedSections?.hasStructuredSubjectIndex
                    ? String(extractedSections.subjectIndexText || '').trim()
                    : '';
                if (options?.stage2_1Text !== undefined) {
                    subjectIndexValue = String(options.stage2_1Text || '').trim();
                }
                const adaptationSourceText = effectiveStage1RawText || nextContent;
                const hasExplicitAdaptedScriptSection = /(?:###?\s*)?(?:第二部分[:：]?\s*修改后的剧本|Second\s*Part[:：]?\s*Adapted\s*Script|Adapted\s*Script\s*[-(（])/i.test(adaptationSourceText);
                const looksLikeSceneMarkdownTable = /(?:^|\n)\s*(?:#{0,6}\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|场景分析结果|场景表)\b/i.test(adaptationSourceText)
                    || /(?:^|\n)\s*\|[^\n]*(?:Scene\s*ID|Scene\s*No\.?|Core\s*Scene\s*Info|Equivalent\s*Duration|场景\s*ID|场景编号|核心场景信息)[^\n]*\|/i.test(adaptationSourceText);
                const canExtractStage1Adaptation = hasExplicitAdaptedScriptSection || (Boolean(effectiveStage1RawText) && !looksLikeSceneMarkdownTable);
                const extractedAdaptationValue = canExtractStage1Adaptation
                    ? String(extractStage1AdaptedScriptBody(adaptationSourceText) || '').trim()
                    : '';
                const persistedAdaptationValue = String(activeEpisode?.ai_scene_analysis_adaptation || '').trim();
                const persistedAdaptationLooksLikeSceneTable = /(?:^|\n)\s*(?:#{0,6}\s*)?(?:Part\s*1\s*:\s*Scenes?\s*Table|Scenes?\s*Table|场景分析结果|场景表)\b/i.test(persistedAdaptationValue)
                    || /(?:^|\n)\s*\|[^\n]*(?:Scene\s*ID|Scene\s*No\.?|Core\s*Scene\s*Info|Equivalent\s*Duration|场景\s*ID|场景编号|核心场景信息)[^\n]*\|/i.test(persistedAdaptationValue);
                const adaptationValue = extractedAdaptationValue || (persistedAdaptationLooksLikeSceneTable ? '' : persistedAdaptationValue);

                const normalizedSubjectIndexValue = extractPureSubjectIndexText(subjectIndexValue);
                updatePayload.ai_scene_analysis_subject_index = normalizedSubjectIndexValue;
                updatePayload.ai_scene_analysis_adaptation = adaptationValue;
                if (/stage2_2|scene_beats|scene_markdown/i.test(logSource)) {
                    updatePayload.ai_scene_analysis_scene_markdown = nextContent;
                }
                updatePayload.ai_stage_outputs = JSON.stringify(buildStageOutputsObject({
                    analysisRawText: nextContent,
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: effectiveStage1RawText,
                    stage2RawText: effectiveStage2RawText,
                    stage2_1Text: options?.stage2_1Text !== undefined ? extractPureSubjectIndexText(options.stage2_1Text) : extractPureSubjectIndexText(latestStage2_1TextRef.current || normalizedSubjectIndexValue),
                    sceneMarkdownByScene: options?.sceneMarkdownByScene || null,
                    replaceSceneMarkdownByScene,
                }), null, 2);

                onLog?.(`[Analysis Writeback] field=${resultField} source=${logSource} raw_len=${nextContent.length} subject_index_len=${normalizedSubjectIndexValue.length} adaptation_len=${adaptationValue.length}`, 'info');
                }
            } else if (resultField === 'ai_scene_analysis_scene_markdown') {
                latestAnalysisRawTextRef.current = nextContent;
                updatePayload.ai_scene_analysis_scene_markdown = nextContent;
                updatePayload.ai_stage_outputs = JSON.stringify(buildStageOutputsObject({
                    analysisRawText: '',
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: latestStage1RawTextRef.current || persistedStage1RawText || '',
                    stage2RawText: options?.stage2RawText || nextContent,
                    stage2_1Text: latestStage2_1TextRef.current || persistedStage2_1Text || undefined,
                    sceneMarkdownByScene: options?.sceneMarkdownByScene || null,
                    replaceSceneMarkdownByScene,
                }), null, 2);
                onLog?.(`[Analysis Writeback] field=${resultField} source=${logSource} raw_len=${nextContent.length}`, 'info');

                if (options?.syncSceneUnits !== false && projectId && activeEpisode?.id) {
                    try {
                        await syncSceneUnitsProgress({
                            project_id: Number(projectId),
                            episode_id: Number(activeEpisode.id),
                            script_text: nextContent,
                        });
                    } catch (syncErr) {
                        onLog?.(`[Scene Units Sync] warning: ${syncErr?.message || syncErr}`, 'warning');
                    }
                }
            } else if (resultField === 'ai_entity_design_result') {
                latestAssetRawTextRef.current = nextContent;
                updatePayload.ai_stage_outputs = JSON.stringify(buildStageOutputsObject({
                    analysisRawText: '',
                    assetRawText: nextContent,
                    stage1RawText: latestStage1RawTextRef.current || persistedStage1RawText || '',
                    stage2RawText: options?.stage2RawText || persistedStage2RawText || '',
                    stage2_1Text: latestStage2_1TextRef.current || persistedStage2_1Text || undefined
                }), null, 2);

                onLog?.(`[Analysis Writeback] field=ai_stage_outputs source=${logSource} bundle_len=${String(updatePayload.ai_stage_outputs || '').length}`, 'info');
            } else if (resultField === 'ai_scene_analysis_subject_index') {
                const normalizedSubjectIndexValue = extractPureSubjectIndexText(nextContent);
                latestStage2_1TextRef.current = normalizedSubjectIndexValue;
                updatePayload[resultField] = normalizedSubjectIndexValue;
                updatePayload.ai_stage_outputs = JSON.stringify(buildStageOutputsObject({
                    analysisRawText: '',
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: latestStage1RawTextRef.current || persistedStage1RawText || '',
                    stage2RawText: options?.stage2RawText || '',
                    stage2_1Text: normalizedSubjectIndexValue,
                }), null, 2);

                onLog?.(`[Analysis Writeback] field=ai_stage_outputs source=${logSource} bundle_len=${String(updatePayload.ai_stage_outputs || '').length}`, 'info');
            } else {
                onLog?.(`[Analysis Writeback] field=${resultField} source=${logSource} raw_len=${nextContent.length}`, 'info');
            }

            const normalizePersistValue = (value) => {
                if (value === undefined) return '';
                if (value === null) return 'null';
                if (typeof value === 'string') return value;
                try {
                    return JSON.stringify(value);
                } catch (_) {
                    return String(value);
                }
            };
            const payloadSignature = Object.keys(updatePayload)
                .sort()
                .map((key) => `${key}=${normalizePersistValue(updatePayload[key])}`)
                .join('|');

            if (lastPersistPayloadSignatureRef.current[resultField] === payloadSignature) {
                onLog?.(`[Analysis Writeback] skipped duplicate payload field=${resultField} source=${logSource}`, 'info');
                return;
            }

            const payloadAlreadyPersisted = Object.keys(updatePayload).every((key) => {
                const currentValue = normalizePersistValue(activeEpisode?.[key]);
                const nextValue = normalizePersistValue(updatePayload[key]);
                return currentValue === nextValue;
            });
            if (payloadAlreadyPersisted) {
                lastPersistPayloadSignatureRef.current[resultField] = payloadSignature;
                onLog?.(`[Analysis Writeback] skipped no-op payload field=${resultField} source=${logSource}`, 'info');
                return;
            }

            await onUpdateEpisodeInfo(activeEpisode.id, updatePayload);
            lastPersistPayloadSignatureRef.current[resultField] = payloadSignature;
        } catch (e) {
            console.error("Failed to persist LLM result", e);
            if (onLog) onLog(`Failed to save LLM result: ${e.message}`);
        }
    };

    const persistSceneMarkdownBundle = useCallback(async (mergedMarkdown, options = {}) => {
        const merged = String(mergedMarkdown || '').trim();
        if (!merged) return;

        const patchMap = options?.sceneMarkdownByScene && typeof options.sceneMarkdownByScene === 'object'
            ? options.sceneMarkdownByScene
            : splitSceneMarkdownTableBySceneId(merged);

        await persistLlmResultContent(merged, 'ai_scene_analysis_scene_markdown', {
            source: options?.source || 'scene-markdown-bundle',
            stage1RawText: options?.stage1RawText,
            stage2RawText: options?.stage2RawText || merged,
            stage2_1Text: options?.stage2_1Text,
            sceneMarkdownByScene: patchMap,
            replaceSceneMarkdownByScene: options?.replaceSceneMarkdownByScene !== false,
            syncSceneUnits: options?.syncSceneUnits,
        });
    }, [persistLlmResultContent, splitSceneMarkdownTableBySceneId]);

    const persistSceneMarkdownPatch = useCallback(async (sceneMarkdownByScene, options = {}) => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        const patchMap = sceneMarkdownByScene && typeof sceneMarkdownByScene === 'object'
            ? sceneMarkdownByScene
            : {};
        const sceneIds = Object.keys(patchMap).filter((sceneId) => String(sceneId || '').trim());
        if (!sceneIds.length) return;

        try {
            const persistedStageOutputs = parseStageOutputsObject(activeEpisode?.ai_stage_outputs || '');
            const persistedStage1RawText = String(persistedStageOutputs?.stages?.stage1?.outputs?.raw_text?.content || '').trim();
            const persistedStage2RawText = String(persistedStageOutputs?.stages?.stage2?.outputs?.raw_text?.content || '').trim();
            const persistedStage2_1Text = String(persistedStageOutputs?.stages?.stage2?.outputs?.subject_index?.content || '').trim();
            const existingSceneMarkdown = String(activeEpisode?.ai_scene_analysis_scene_markdown || '').trim();
            const logSource = String(options?.source || 'scene-markdown-patch').trim() || 'scene-markdown-patch';

            const updatePayload = {
                ai_stage_outputs: JSON.stringify(buildStageOutputsObject({
                    analysisRawText: existingSceneMarkdown,
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: options?.stage1RawText || latestStage1RawTextRef.current || persistedStage1RawText || '',
                    stage2RawText: persistedStage2RawText || existingSceneMarkdown,
                    stage2_1Text: options?.stage2_1Text !== undefined
                        ? extractPureSubjectIndexText(options.stage2_1Text)
                        : extractPureSubjectIndexText(latestStage2_1TextRef.current || persistedStage2_1Text || activeEpisode?.ai_scene_analysis_subject_index || ''),
                    sceneMarkdownByScene: patchMap,
                    replaceSceneMarkdownByScene: options?.replaceSceneMarkdownByScene === true,
                }), null, 2),
            };

            await onUpdateEpisodeInfo(activeEpisode.id, updatePayload);
            onLog?.(`[Analysis Writeback] field=scene_markdown_by_scene source=${logSource} scenes=${sceneIds.join(',')}`, 'info');
        } catch (error) {
            console.error('Failed to persist per-scene scene markdown patch', error);
            onLog?.(`Failed to save per-scene scene markdown: ${error?.message || error}`, 'error');
            throw error;
        }
    }, [
        activeEpisode?.ai_entity_design_result,
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.ai_scene_analysis_subject_index,
        activeEpisode?.ai_stage_outputs,
        activeEpisode?.id,
        buildStageOutputsObject,
        extractPureSubjectIndexText,
        llmAssetRawResultContent,
        onLog,
        onUpdateEpisodeInfo,
        parseStageOutputsObject,
    ]);

    const persistSubjectIndexEdit = useCallback(async (newVal) => {
        const normalizedValue = extractPureSubjectIndexText(String(newVal || '').trim());
        setSubjectIndexText(normalizedValue);
        latestStage2_1TextRef.current = normalizedValue;
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;

        const persistedStageOutputs = parseStageOutputsObject(activeEpisode?.ai_stage_outputs || '');
        const persistedStage1RawText = String(persistedStageOutputs?.stages?.stage1?.outputs?.raw_text?.content || '').trim();
        const persistedStage2RawText = String(persistedStageOutputs?.stages?.stage2?.outputs?.raw_text?.content || '').trim();
        const existingSceneMarkdown = String(activeEpisode?.ai_scene_analysis_scene_markdown || '').trim();
        const rawJson = String(persistedStageOutputs?.stages?.stage2?.outputs?.scene_markdown_by_scene?.content || '').trim();
        const sceneMarkdownByScene = parseSceneMarkdownBySceneMap(rawJson);

        try {
            await onUpdateEpisodeInfo(activeEpisode.id, {
                ai_scene_analysis_subject_index: normalizedValue,
                ai_stage_outputs: JSON.stringify(buildStageOutputsObject({
                    analysisRawText: existingSceneMarkdown,
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: latestStage1RawTextRef.current || persistedStage1RawText || '',
                    stage2RawText: persistedStage2RawText || existingSceneMarkdown,
                    stage2_1Text: normalizedValue,
                    sceneMarkdownByScene: sceneMarkdownByScene && Object.keys(sceneMarkdownByScene).length > 0
                        ? sceneMarkdownByScene
                        : null,
                    replaceSceneMarkdownByScene: false,
                }), null, 2),
            });
            onLog?.(`[Stage 2 Asset Index] Saved manual edit (len=${normalizedValue.length})`, 'success');
        } catch (error) {
            console.error('Failed to update stage2 subject index', error);
            onLog?.(`Failed to save asset index edit: ${error?.message || error}`, 'error');
            throw error;
        }
    }, [
        activeEpisode?.ai_entity_design_result,
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.ai_stage_outputs,
        activeEpisode?.id,
        buildStageOutputsObject,
        extractPureSubjectIndexText,
        llmAssetRawResultContent,
        onLog,
        onUpdateEpisodeInfo,
        parseSceneMarkdownBySceneMap,
        parseStageOutputsObject,
    ]);

    const clearSceneMarkdownPatchForScenes = useCallback(async (sceneIds, options = {}) => {
        if (!activeEpisode?.id || !onUpdateEpisodeInfo) return;
        const targetIds = (Array.isArray(sceneIds) ? sceneIds : [])
            .map((sceneId) => String(sceneId || '').trim())
            .filter(Boolean);
        if (!targetIds.length) return;

        try {
            const persistedStageOutputs = parseStageOutputsObject(activeEpisode?.ai_stage_outputs || '');
            const persistedStage1RawText = String(persistedStageOutputs?.stages?.stage1?.outputs?.raw_text?.content || '').trim();
            const persistedStage2RawText = String(persistedStageOutputs?.stages?.stage2?.outputs?.raw_text?.content || '').trim();
            const persistedStage2_1Text = String(persistedStageOutputs?.stages?.stage2?.outputs?.subject_index?.content || '').trim();
            const existingSceneMarkdown = String(activeEpisode?.ai_scene_analysis_scene_markdown || '').trim();
            const rawJson = String(persistedStageOutputs?.stages?.stage2?.outputs?.scene_markdown_by_scene?.content || '').trim();
            const currentMap = parseSceneMarkdownBySceneMap(rawJson);
            const nextMap = { ...(currentMap && typeof currentMap === 'object' ? currentMap : {}) };
            targetIds.forEach((sceneId) => {
                delete nextMap[sceneId];
            });
            const logSource = String(options?.source || 'scene-markdown-clear').trim() || 'scene-markdown-clear';
            await onUpdateEpisodeInfo(activeEpisode.id, {
                ai_stage_outputs: JSON.stringify(buildStageOutputsObject({
                    analysisRawText: existingSceneMarkdown,
                    assetRawText: latestAssetRawTextRef.current || activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                    stage1RawText: options?.stage1RawText || latestStage1RawTextRef.current || persistedStage1RawText || '',
                    stage2RawText: persistedStage2RawText || existingSceneMarkdown,
                    stage2_1Text: options?.stage2_1Text !== undefined
                        ? extractPureSubjectIndexText(options.stage2_1Text)
                        : extractPureSubjectIndexText(latestStage2_1TextRef.current || persistedStage2_1Text || activeEpisode?.ai_scene_analysis_subject_index || ''),
                    sceneMarkdownByScene: nextMap,
                }), null, 2),
            });
            onLog?.(`[Analysis Writeback] cleared scene_markdown_by_scene source=${logSource} scenes=${targetIds.join(',')}`, 'info');
        } catch (error) {
            console.error('Failed to clear per-scene scene markdown', error);
            onLog?.(`Failed to clear per-scene scene markdown: ${error?.message || error}`, 'warning');
            throw error;
        }
    }, [
        activeEpisode?.ai_entity_design_result,
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.ai_scene_analysis_subject_index,
        activeEpisode?.ai_stage_outputs,
        activeEpisode?.id,
        buildStageOutputsObject,
        extractPureSubjectIndexText,
        llmAssetRawResultContent,
        onLog,
        onUpdateEpisodeInfo,
        parseSceneMarkdownBySceneMap,
        parseStageOutputsObject,
    ]);

    // Keep the "LLM 返回结果" box in sync with DB-saved ai_scene_analysis_result.
    // Important: don't clobber local edits while user is typing.
    const lastLoadedAnalysisRef = useRef(null);
    const latestAssetRawTextRef = useRef('');
    const latestAnalysisRawTextRef = useRef('');
    const latestStage1RawTextRef = useRef('');
    const latestStage2_1TextRef = useRef('');

    const llmRawAutoSaveTimerRef = useRef(null);
    const llmRawAutoSaveArmedRef = useRef(false);
    const analysisResumeInFlightRef = useRef(false);
    const phase2ResolverRef = useRef(null);
    const assetRerunHandledNonceRef = useRef(null);
    const superuserModalMutexRef = useRef(Promise.resolve());
    const phase2GenerationInFlightRef = useRef(false);
    const sceneBeatsOnlyRerunInFlightRef = useRef(false);
    const analysisStopRequestedRef = useRef(false);
    const activeAnalysisTaskIdsRef = useRef(new Set());
    const analysisRunInFlightRef = useRef(false);
    const analysisResumeCoordinatorRef = useRef({ running: false, episodeId: null });
    const detachedAnalysisRunEpisodeRef = useRef(null);
    const mountResumeReadyRef = useRef(false);
    const analysisProgressDismissedRef = useRef(false);
    const latestAnalysisProgressUiRef = useRef({
        flowStatus: { phase: 'idle', message: '' },
        flowHistory: [],
        uiReport: null,
    });
    const scriptEditorMountedRef = useRef(true);
    const forceRegenerateRef = useRef(false);
    const autoImportRunningRef = useRef(false);
    const latestIsAnalyzingRef = useRef(false);
    const latestActiveEpisodeIdRef = useRef(null);
    const lastScriptLeaveNoticeAtRef = useRef(0);
    const lastTryResumePendingAnalysisAtRef = useRef(0);
    const lastAutoSubjectsImportRef = useRef({ signature: '', result: null });
    const lastSubjectsImportIncompleteAlertRef = useRef('');
    const lastPersistPayloadSignatureRef = useRef({});
    const ANALYSIS_TASK_MAX_AGE_MS = 60 * 60 * 1000;
    const ANALYSIS_TASK_MARKER_TTL_MS = 120 * 60 * 1000;
    const AI_SHOTS_TASK_MARKER_TTL_MS = 45 * 60 * 1000;

    const resetAnalysisFallbackRetryCounts = useCallback((episodeId) => {
        const id = Number(episodeId || 0);
        if (!id) return;
        autoZeroReportHandledRef.current = { key: '', handledAt: 0 };
        analysisFallbackRetryRef.current = {
            episodeId: id,
            sceneBeatsAttempts: 0,
            assetAttempts: 0,
            sceneRegenAttempts: 0,
            running: false,
        };
    }, []);

    const ensureAnalysisFallbackState = useCallback((episodeId) => {
        const id = Number(episodeId || 0);
        if (!id) return null;
        if (analysisFallbackRetryRef.current.episodeId !== id) {
            const snapshot = loadAnalysisSessionSnapshot(id);
            if (snapshot?.fallbackRetry?.episodeId === id) {
                analysisFallbackRetryRef.current = {
                    ...snapshot.fallbackRetry,
                    episodeId: id,
                    running: false,
                };
                if (snapshot?.autoZeroReportHandledKey) {
                    autoZeroReportHandledRef.current = {
                        key: String(snapshot.autoZeroReportHandledKey || ''),
                        handledAt: Number(snapshot.savedAt || Date.now()),
                    };
                }
            } else {
                resetAnalysisFallbackRetryCounts(id);
            }
        }
        return analysisFallbackRetryRef.current;
    }, [resetAnalysisFallbackRetryCounts]);

    const canAttemptAnalysisFallback = useCallback((episodeId, kind) => {
        const state = ensureAnalysisFallbackState(episodeId);
        if (!state) return false;
        const fieldByKind = {
            scene_beats: 'sceneBeatsAttempts',
            asset_gen: 'assetAttempts',
            scene_regen: 'sceneRegenAttempts',
        };
        const field = fieldByKind[kind];
        if (!field) return false;
        return Number(state[field] || 0) < MAX_ANALYSIS_FALLBACK_ATTEMPTS;
    }, [ensureAnalysisFallbackState]);

    const recordAnalysisFallbackAttempt = useCallback((episodeId, kind) => {
        const state = ensureAnalysisFallbackState(episodeId);
        if (!state) return;
        const fieldByKind = {
            scene_beats: 'sceneBeatsAttempts',
            asset_gen: 'assetAttempts',
            scene_regen: 'sceneRegenAttempts',
        };
        const field = fieldByKind[kind];
        if (field) state[field] = Number(state[field] || 0) + 1;
    }, [ensureAnalysisFallbackState]);

    const getAnalysisFallbackRemaining = useCallback((episodeId, kind) => {
        const state = ensureAnalysisFallbackState(episodeId);
        if (!state) return 0;
        const fieldByKind = {
            scene_beats: 'sceneBeatsAttempts',
            asset_gen: 'assetAttempts',
            scene_regen: 'sceneRegenAttempts',
        };
        const field = fieldByKind[kind];
        if (!field) return 0;
        return Math.max(0, MAX_ANALYSIS_FALLBACK_ATTEMPTS - Number(state[field] || 0));
    }, [ensureAnalysisFallbackState]);

    const isTaskCanceledError = useCallback((error) => {
        if (!error) return false;
        if (error?.isCanceled) return true;
        const code = Number(error?.errorCode || error?.response?.status || 0);
        if (code === 499) return true;
        const text = String(error?.message || error?.response?.data?.detail || '').toLowerCase();
        return text.includes('cancel') || text.includes('取消');
    }, []);

    const createAnalysisCanceledError = useCallback(() => {
        const error = new Error(t('用户已中断剧本分析任务。', 'Script analysis was stopped by the user.'));
        error.isCanceled = true;
        error.errorCode = 499;
        return error;
    }, [t]);

    const throwIfAnalysisStopped = useCallback(() => {
        if (analysisStopRequestedRef.current) {
            throw createAnalysisCanceledError();
        }
    }, [createAnalysisCanceledError]);

    const registerActiveAnalysisTask = useCallback((taskId) => {
        const stableTaskId = String(taskId || '').trim();
        if (!stableTaskId) return '';
        activeAnalysisTaskIdsRef.current.add(stableTaskId);
        setActiveAnalysisTaskId(stableTaskId);
        return stableTaskId;
    }, []);

    const persistAnalysisSessionSnapshot = useCallback((episodeId) => {
        const id = Number(episodeId || 0);
        if (!id) return;
        const prev = loadAnalysisSessionSnapshot(id) || {};
        const ui = latestAnalysisProgressUiRef.current;
        const dismissed = analysisProgressDismissedRef.current;
        const progressUi = dismissed
            ? {
                dismissed: true,
                flowStatus: { phase: 'idle', message: '' },
                flowHistory: [],
                uiReport: null,
            }
            : {
                dismissed: false,
                flowStatus: (ui.flowStatus && typeof ui.flowStatus === 'object')
                    ? ui.flowStatus
                    : { phase: 'idle', message: '' },
                flowHistory: Array.isArray(ui.flowHistory) ? ui.flowHistory.slice(-80) : [],
                uiReport: slimAnalysisUiReportForSnapshot(ui.uiReport),
            };
        saveAnalysisSessionSnapshot(id, {
            ...prev,
            episodeId: id,
            autoZeroReportHandledKey: String(autoZeroReportHandledRef.current?.key || ''),
            fallbackRetry: {
                episodeId: id,
                sceneBeatsAttempts: Number(analysisFallbackRetryRef.current?.sceneBeatsAttempts || 0),
                assetAttempts: Number(analysisFallbackRetryRef.current?.assetAttempts || 0),
                sceneRegenAttempts: Number(analysisFallbackRetryRef.current?.sceneRegenAttempts || 0),
                running: false,
            },
            progressUi,
            savedAt: Date.now(),
        });
    }, []);

    const hasPersistableAnalysisProgress = useCallback((flowStatus, flowHistory, uiReport) => {
        if (Array.isArray(flowHistory) && flowHistory.length > 0) return true;
        if (uiReport && typeof uiReport === 'object') return true;
        const phase = String(flowStatus?.phase || '').trim().toLowerCase();
        return Boolean(phase && phase !== 'idle');
    }, []);

    const clearAnalysisProgressUiState = useCallback((episodeId, { persist = true } = {}) => {
        const id = Number(episodeId || activeEpisode?.id || 0);
        analysisTimerStartedAtRef.current = 0;
        setIsAnalyzing(false);
        setActiveAnalysisTaskId('');
        setAnalysisFlowStatus({ phase: 'idle', message: '' });
        setAnalysisFlowStatusHistory([]);
        setAnalysisUiReport(null);
        setAnalysisReviewIssues([]);
        if (persist && id) {
            clearAnalysisSessionProgressSnapshot(id);
        }
    }, [activeEpisode?.id]);

    const restoreAnalysisProgressFromSession = useCallback((episodeId) => {
        const id = Number(episodeId || 0);
        if (!id) return false;
        const snapshot = loadAnalysisSessionSnapshot(id);
        const progressUi = snapshot?.progressUi;
        if (!progressUi || progressUi.dismissed === true) {
            analysisProgressDismissedRef.current = Boolean(progressUi?.dismissed);
            return false;
        }
        const isRunning = isPersistedAnalysisProgressRunning(progressUi);
        analysisProgressDismissedRef.current = false;
        const flowStatus = (progressUi.flowStatus && typeof progressUi.flowStatus === 'object')
            ? progressUi.flowStatus
            : { phase: 'idle', message: '' };
        const flowHistory = Array.isArray(progressUi.flowHistory) ? progressUi.flowHistory : [];
        const uiReport = (progressUi.uiReport && typeof progressUi.uiReport === 'object') ? progressUi.uiReport : null;
        if (!isRunning && !hasPersistableAnalysisProgress(flowStatus, flowHistory, uiReport)) return false;
        setAnalysisFlowStatus(flowStatus);
        setAnalysisFlowStatusHistory(flowHistory);
        if (uiReport) {
            setAnalysisUiReport(uiReport);
            setAnalysisReviewIssues(Array.isArray(uiReport.reviewIssues) ? uiReport.reviewIssues : []);
            if (String(uiReport?.status || '').trim().toLowerCase() === 'running') {
                beginAnalysisTimer(Number(uiReport?.startedAt || Date.now()));
            }
        }
        if (isRunning) {
            setIsAnalyzing(true);
            try {
                const markerKey = id > 0 ? `aistory:scene-analysis-task:${id}` : '';
                const rawMarker = markerKey && window?.localStorage?.getItem(markerKey);
                if (rawMarker) {
                    const parsedMarker = JSON.parse(rawMarker);
                    const taskId = String(parsedMarker?.taskId || '').trim();
                    if (taskId) setActiveAnalysisTaskId(taskId);
                }
            } catch (_) {
                // Ignore marker parse failures during restore.
            }
        }
        return true;
    }, [beginAnalysisTimer, hasPersistableAnalysisProgress]);

    const dismissAnalysisProgressPanel = useCallback(() => {
        analysisProgressDismissedRef.current = true;
        setAnalysisFlowStatus({ phase: 'idle', message: '' });
        setAnalysisFlowStatusHistory([]);
        setAnalysisUiReport(null);
        setAnalysisReviewIssues([]);
        if (activeEpisode?.id) {
            persistAnalysisSessionSnapshot(activeEpisode.id);
        }
    }, [activeEpisode?.id, persistAnalysisSessionSnapshot]);

    useEffect(() => {
        if (!activeEpisode?.id || analysisProgressDismissedRef.current) return;
        if (!hasPersistableAnalysisProgress(analysisFlowStatus, analysisFlowStatusHistory, analysisUiReport)) return;
        const timer = setTimeout(() => {
            persistAnalysisSessionSnapshot(activeEpisode.id);
        }, 400);
        return () => clearTimeout(timer);
    }, [
        activeEpisode?.id,
        analysisFlowStatus,
        analysisFlowStatusHistory,
        analysisUiReport,
        hasPersistableAnalysisProgress,
        persistAnalysisSessionSnapshot,
    ]);

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
            const taskIds = Array.isArray(parsed?.taskIds)
                ? Array.from(new Set(parsed.taskIds.map((item) => String(item || '').trim()).filter(Boolean)))
                : [];
            const startedAt = Number(parsed?.startedAt || 0);
            const phase = Number(parsed?.phase || 1);
            if (!taskId) return null;
            if (!Number.isFinite(startedAt) || startedAt <= 0) return { taskId, taskIds: taskIds.length ? taskIds : [taskId], startedAt: Date.now(), phase };
            // Align marker TTL with task polling timeout to avoid endless resume loops after reload.
            if ((Date.now() - startedAt) > ANALYSIS_TASK_MARKER_TTL_MS) {
                window.localStorage.removeItem(key);
                return null;
            }
            return { taskId, taskIds: taskIds.length ? taskIds : [taskId], startedAt, phase };
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
            let existingTaskIds = [];
            try {
                const existing = JSON.parse(window.localStorage.getItem(key) || '{}');
                existingTaskIds = Array.isArray(existing?.taskIds)
                    ? existing.taskIds.map((item) => String(item || '').trim()).filter(Boolean)
                    : [];
                if (existing?.taskId) existingTaskIds.push(String(existing.taskId || '').trim());
            } catch (_) {
                existingTaskIds = [];
            }
            const taskIds = Array.from(new Set([
                ...existingTaskIds,
                ...Array.from(activeAnalysisTaskIdsRef.current || []),
                taskId,
            ].filter(Boolean)));
            const payload = {
                taskId,
                taskIds,
                startedAt: Number(marker?.startedAt || Date.now()),
                phase: Number(marker?.phase || 1),
            };
            window.localStorage.setItem(key, JSON.stringify(payload));
            registerActiveAnalysisTask(taskId);
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAnalysisTaskStorageKey, registerActiveAnalysisTask]);

    const clearAnalysisTaskMarker = useCallback((episodeId) => {
        try {
            const key = getAnalysisTaskStorageKey(episodeId);
            if (!key || !window?.localStorage) return;
            window.localStorage.removeItem(key);
            activeAnalysisTaskIdsRef.current.clear();
            setActiveAnalysisTaskId('');
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAnalysisTaskStorageKey]);

    const clearStalePhase2AssetMarkerIfDesignExists = useCallback((episodeId, reason = '') => {
        const id = Number(episodeId || 0);
        if (!id) return false;
        const marker = loadAnalysisTaskMarker(id);
        if (!marker?.taskId || Number(marker?.phase) !== 2) return false;

        const designText = String(
            llmAssetRawResultContent
            || activeEpisode?.ai_entity_design_result
            || ''
        ).trim();
        if (!hasPersistedEntityDesignPayload(designText)) return false;

        clearAnalysisTaskMarker(id);
        if (reason && onLog) {
            onLog?.(`[Stage 3 Asset Design] Cleared stale phase-2 marker (${reason}); entity design result already present.`, 'info');
        }
        return true;
    }, [activeEpisode?.ai_entity_design_result, clearAnalysisTaskMarker, llmAssetRawResultContent, loadAnalysisTaskMarker, onLog]);

    const clearStaleAnalysisMarkerIfEpisodeComplete = useCallback(async (episodeId, episode, reason = '') => {
        const id = Number(episodeId || 0);
        if (!id) return false;
        const marker = loadAnalysisTaskMarker(id);
        if (!marker?.taskId) return false;

        const phaseRaw = marker?.phase;
        const phaseKey = String(phaseRaw ?? '1').trim().toLowerCase();
        const episodeRow = episode || (Number(activeEpisode?.id) === id ? activeEpisode : null);

        if (Number(phaseRaw) === 2 || phaseKey === '2') {
            return clearStalePhase2AssetMarkerIfDesignExists(id, reason);
        }

        const scenes = await fetchScenes(id).catch(() => []);
        const sceneCount = Array.isArray(scenes) ? scenes.length : 0;
        const hasSceneMarkdown = Boolean(String(episodeRow?.ai_scene_analysis_scene_markdown || '').trim());
        const hasSceneResult = Boolean(String(episodeRow?.ai_scene_analysis_scene_markdown || episodeRow?.ai_scene_analysis_result || '').trim());
        const hasSubjectIndex = Boolean(String(episodeRow?.ai_scene_analysis_subject_index || '').trim());
        const hasEntityDesign = hasPersistedEntityDesignPayload(episodeRow?.ai_entity_design_result);

        if (phaseKey === 'scene_beats') {
            if (hasSceneMarkdown && sceneCount > 0) {
                clearAnalysisTaskMarker(id);
                if (reason && onLog) {
                    onLog?.(`[Analysis Resume] Cleared stale scene_beats marker (${reason}); scene markdown and DB scenes already present.`, 'info');
                }
                return true;
            }
            return false;
        }

        if (sceneCount > 0 && hasSceneResult && (hasSubjectIndex || hasEntityDesign)) {
            clearAnalysisTaskMarker(id);
            if (reason && onLog) {
                onLog?.(`[Analysis Resume] Cleared stale analysis marker (${reason}); episode already has ${sceneCount} imported scene(s).`, 'info');
            }
            return true;
        }

        return false;
    }, [activeEpisode, clearAnalysisTaskMarker, clearStalePhase2AssetMarkerIfDesignExists, fetchScenes, loadAnalysisTaskMarker, onLog]);

    const bootstrapPendingAnalysisUi = useCallback(() => {
        if (!activeEpisode?.id) return false;

        const activeRun = getEpisodeAnalysisRun(activeEpisode.id);
        const marker = loadAnalysisTaskMarker(activeEpisode.id);
        if (!activeRun?.promise && !marker?.taskId) return false;

        const phase = activeRun?.phase ?? marker?.phase ?? 1;
        const startedAt = Number(activeRun?.startedAt || marker?.startedAt || Date.now());
        const elapsedMs = Math.max(0, Date.now() - startedAt);
        const taskId = String(activeRun?.taskId || marker?.taskId || '').trim();
        const resolvedPhase = phase === 2 ? 'assets_gen' : (phase === 'scene_beats' ? 'scene_beats' : 'script_opt');

        beginAnalysisTimer(startedAt);
        setIsAnalyzing(true);
        if (taskId) setActiveAnalysisTaskId(taskId);
        setAnalysisFlowStatus((prev) => {
            const prevPhase = String(prev?.phase || '').trim().toLowerCase();
            if (prevPhase && prevPhase !== 'idle') return prev;
            return {
                phase: resolvedPhase,
                message: t('后台分析任务进行中，正在恢复连接...', 'Background analysis task in progress, reconnecting...'),
            };
        });
        setAnalysisUiReport((prev) => {
            if (prev?.status === 'running') {
                return { ...prev, durationMs: elapsedMs };
            }
            return {
                status: 'running',
                startedAt,
                durationMs: elapsedMs,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: '',
                error: '',
            };
        });
        return true;
    }, [activeEpisode?.id, beginAnalysisTimer, loadAnalysisTaskMarker, t]);

    const isRecoverableAnalysisError = useCallback((error) => {
        if (!error || isTaskCanceledError(error)) return false;
        const code = String(error?.code || '').toUpperCase();
        const msg = String(error?.message || '').toLowerCase();
        if (code === 'ECONNABORTED') return true;
        if (!error?.response) return true;
        return (
            msg.includes('network error')
            || msg.includes('no response')
            || msg.includes('submit/poll no response')
            || msg.includes('timed out while waiting')
            || msg.includes('task polling timed out')
            || msg.includes('llm task polling timed out')
        );
    }, [isTaskCanceledError]);

    const shouldRetainAnalysisTaskMarker = useCallback(({ pipelineFinished = false, canceled = false, error = null, mounted = true } = {}) => {
        if (pipelineFinished || canceled) return false;
        if (!mounted) return true;
        return isRecoverableAnalysisError(error);
    }, [isRecoverableAnalysisError]);

    const canStopAnalysisTask = useMemo(() => {
        if (isAnalyzing || isRetryingPhase2 || isStoppingAnalysisTask) return true;
        if (String(activeAnalysisTaskId || '').trim()) return true;
        return Boolean(loadAnalysisTaskMarker(activeEpisode?.id)?.taskId);
    }, [activeAnalysisTaskId, activeEpisode?.id, isAnalyzing, isRetryingPhase2, isStoppingAnalysisTask, loadAnalysisTaskMarker]);

    const handleStopAnalysisTask = useCallback(async () => {
        if (!activeEpisode?.id) return;
        const marker = loadAnalysisTaskMarker(activeEpisode.id);
        const taskIds = Array.from(new Set([
            ...Array.from(activeAnalysisTaskIdsRef.current || []),
            String(activeAnalysisTaskId || '').trim(),
            String(marker?.taskId || '').trim(),
            ...(Array.isArray(marker?.taskIds) ? marker.taskIds.map((item) => String(item || '').trim()) : []),
        ].filter(Boolean)));
        if (taskIds.length <= 0) {
            if (isAnalyzing || isRetryingPhase2 || phase2GenerationInFlightRef.current || analysisRunInFlightRef.current) {
                analysisStopRequestedRef.current = true;
                setIsAnalyzing(false);
                setIsRetryingPhase2(false);
                phase2GenerationInFlightRef.current = false;
                analysisRunInFlightRef.current = false;
                setAnalysisFlowStatus({
                    phase: 'warning',
                    message: t('已请求停止当前剧本分析流程。', 'Stop requested for the current script analysis flow.'),
                });
                if (onLog) onLog('Scene analysis stop requested before backend task id was available.', 'warning');
                return;
            }
            setAnalysisFlowStatus({
                phase: 'warning',
                message: t('当前没有正在运行的场景推演任务需要被终止。', 'No running analysis task found to stop.'),
            });
            return;
        }

        setIsStoppingAnalysisTask(true);
        analysisStopRequestedRef.current = true;
        try {
            const stopResults = await Promise.allSettled(taskIds.map((taskId) => stopAsyncTask(taskId)));
            const failedStops = stopResults.filter((item) => item.status === 'rejected');
            clearAnalysisTaskMarker(activeEpisode.id);
            setAnalysisFlowStatus({
                phase: 'warning',
                message: failedStops.length > 0
                    ? t(`已请求停止当前剧本分析任务；${failedStops.length} 个子任务停止请求未确认。`, `Stop requested for the current script analysis task; ${failedStops.length} subtask stop request(s) were not confirmed.`)
                    : t('已请求停止当前剧本分析任务。', 'Stop requested for the current scene analysis task.'),
            });
            if (onLog) onLog(`Scene analysis stop requested: task_ids=${taskIds.join(',')}`, failedStops.length > 0 ? 'warning' : 'info');
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
            setIsRetryingPhase2(false);
            phase2GenerationInFlightRef.current = false;
            analysisRunInFlightRef.current = false;
        }
    }, [activeAnalysisTaskId, activeEpisode?.id, clearAnalysisTaskMarker, isAnalyzing, isRetryingPhase2, loadAnalysisTaskMarker, onLog, t]);
    const refreshAnalysisFromDB = useCallback(async ({ resultField = 'ai_scene_analysis_result' } = {}) => {
        const episodeId = Number(activeEpisode?.id || 0);
        if (!episodeId) return;
        try {
            const fresh = await fetchEpisode(episodeId);
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
    }, [activeEpisode?.id, llmAssetRawResultContent, llmRawResultContent, normalizeLlmMarkdownTable]);

    const refreshAnalysisFromDBRef = useRef(refreshAnalysisFromDB);
    refreshAnalysisFromDBRef.current = refreshAnalysisFromDB;

    const waitForEpisodeAnalysisResultUpdate = useCallback(async ({ baselineText = '', timeoutMs = 600000, intervalMs = 3500, resultField = 'ai_scene_analysis_result', expectedResultKind = '' } = {}) => {
        const sleepMs = Math.max(5000, Number(intervalMs || 3500));
        const episodeId = Number(activeEpisode?.id || 0);
        if (!episodeId) {
            await new Promise(r => setTimeout(r, sleepMs));
            return '';
        }
        if (resultField === 'none') {
            await new Promise(r => setTimeout(r, sleepMs));
            return '';
        }
        const base = String(baselineText || '').trim();
        const deadline = Date.now() + Math.max(30000, Number(timeoutMs || 600000));

        while (Date.now() < deadline) {
            try {
                const fresh = await fetchEpisode(episodeId);
                const dbText = String((fresh && fresh[resultField]) || '').trim();
                
                const expectedKind = String(expectedResultKind || '').trim().toLowerCase();
                const hasSceneBeatsMarker = Boolean(normalizeLlmMarkdownTable(dbText));
                const hasSubjectIndexMarker = /###?\s*Subject\s*Index/i.test(dbText) || /subject_no\s*=\s*/i.test(dbText) || /\|\s*subject_no\s*\|\s*subject_type\s*\|/i.test(dbText);
                const hasAssetDesignMarker = /"characters"\s*:/i.test(dbText) || /"props"\s*:/i.test(dbText) || /"environments"\s*:/i.test(dbText) || /"posters"\s*:/i.test(dbText) || /"covers"\s*:/i.test(dbText);
                const hasValidMarker = resultField === 'ai_scene_analysis_result'
                    ? (expectedKind === 'scene_beats' ? hasSceneBeatsMarker : (hasSceneBeatsMarker || hasSubjectIndexMarker))
                    : (resultField === 'ai_entity_design_result' ? hasAssetDesignMarker : Boolean(dbText));

                if (dbText && dbText !== base && hasValidMarker) {
                    return dbText;
                }
            } catch (_) {
                // Non-fatal polling fallback; keep waiting.
            }
            await new Promise(resolve => setTimeout(resolve, sleepMs));
        }
        return '';
    }, [activeEpisode?.id, normalizeLlmMarkdownTable]);

    const ANALYSIS_EPISODE_RECOVERY_PROBE_MS = 30000;

    const awaitAnalyzeSceneWithRecovery = useCallback(async (invokeAnalyze, { startedAt = Date.now(), baselineText = '', resultField = 'ai_scene_analysis_result', expectedResultKind = '', disableEpisodeRecovery = false } = {}) => {
        throwIfAnalysisStopped();
        if (disableEpisodeRecovery) {
            const value = await invokeAnalyze();
            throwIfAnalysisStopped();
            return value;
        }
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

        const deadline = Date.now() + 60 * 60 * 1000;
        while (!settled && Date.now() < deadline) {
            throwIfAnalysisStopped();
            await new Promise((resolve) => setTimeout(resolve, ANALYSIS_EPISODE_RECOVERY_PROBE_MS));
            if (settled) break;
            const recoveredText = await waitForEpisodeAnalysisResultUpdate({
                baselineText,
                timeoutMs: 15000,
                intervalMs: 6000,
                resultField,
                expectedResultKind,
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
        throwIfAnalysisStopped();
        if (resolvedError) throw resolvedError;
        if (settled) return resolvedValue;
        throw new Error('AI Script Analysis timed out while waiting for async task result.');
    }, [onLog, t, throwIfAnalysisStopped, waitForEpisodeAnalysisResultUpdate]);

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

    const runStage2_2WithValidationRetry = useCallback(async ({
        label = 'Stage 2.2',
        logPhasePrefix = 'advanced',
        finalStage2_2UserInput,
        stage2_2UserInputBody = '',
        stage2_1SubjectIndexText = '',
        stage1SourceText = '',
        startedAt,
        baselineText = '',
        functionName = 'script_analysis_stage_2_2_beats',
        sceneAnalysisModePayload = null,
        targetSceneUnits = null,
        onTaskCreated,
    }) => {
        const stage2_2PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md');
        const finalStage2_2Prompt = stage2_2PromptRes?.content || '';
        let lastError = '';

        const adaptedScriptForSplit = extractAdaptedScriptFromStage2_2UserInputBody(stage2_2UserInputBody || finalStage2_2UserInput);
        if (!String(adaptedScriptForSplit || '').trim()) {
            throw new Error(t(
                '缺少优化后剧本，无法执行场景编排。请确认第一阶段已生成改编剧本后再重试。',
                'Missing adapted script for scene beats orchestration. Complete Stage 1 script optimization first.'
            ));
        }
        let sceneUnits = [];
        try {
            sceneUnits = parseSceneUnitsFromScriptMarkers(adaptedScriptForSplit);
        } catch (parseErr) {
            onLog?.(`[${label}] scene marker parse warning: ${parseErr?.message || parseErr}`, 'warning');
            sceneUnits = [];
        }

        const runSingleStage2_2Attempt = async ({
            attemptLabel,
            attemptUserInputBody,
            attemptFinalUserInput,
            fallbackAttempt = 0,
            disableEpisodeRecovery = false,
        }) => {
            logStage2_2Diagnostics({
                phase: `${logPhasePrefix}-stage2_2-submit`,
                subjectIndexText: stage2_1SubjectIndexText,
                sceneInputText: attemptUserInputBody,
                finalInputText: attemptFinalUserInput,
            });

            const stage2_2ResultObj = await awaitAnalyzeSceneWithRecovery(
                () => runScriptAnalysisFlowAnalyzeNode(
                    'scene_markdown',
                    attemptFinalUserInput,
                    finalStage2_2Prompt,
                    null,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            onTaskCreated?.(taskId);
                        },
                    },
                    projectId,
                    functionName,
                    selectedScriptAnalysisApiId,
                    sceneAnalysisModePayload
                ),
                {
                    startedAt,
                    baselineText,
                    resultField: 'ai_scene_analysis_scene_markdown',
                    expectedResultKind: 'scene_beats',
                    disableEpisodeRecovery,
                }
            );

            if (disableEpisodeRecovery && stage2_2ResultObj?.meta?.recovered_from_episode_poll) {
                throw new Error(t(
                    '场景编排仍在进行中，拒绝使用分集缓存结果。',
                    'Scene beats orchestration is still running; refused to use cached episode result.'
                ));
            }

            const text2_2 = extractAnalysisTextFromResult(stage2_2ResultObj) || '';
            let isUpstreamError2 = false;
            let errMsg2 = '';
            const matchObjStr2 = text2_2.trim().replace(/^\s*```(?:json)?\s*/i, '').replace(/\s*```\s*$/, '');
            if (matchObjStr2.startsWith('{')) {
                try {
                    const parseObj = JSON.parse(matchObjStr2);
                    if (parseObj.code === 500 || parseObj.error || parseObj.msg) {
                        isUpstreamError2 = true;
                        errMsg2 = `上游接口异常 (${attemptLabel})：${parseObj.msg || parseObj.error?.message || matchObjStr2}`;
                    }
                } catch (_) {}
            }
            if (!isUpstreamError2 && /服务器错误|maintained|too many requests|rate limit/i.test(text2_2)) {
                isUpstreamError2 = true;
                errMsg2 = `上游接口熔断或系统维护 (${attemptLabel})：${text2_2.slice(0, 100)}`;
            }
            if (isUpstreamError2) {
                throw new Error(errMsg2);
            }

            const validationLabel = fallbackAttempt > 0 ? `${attemptLabel} retry ${fallbackAttempt}` : attemptLabel;
            const stage2_2Check = validateStage2_2BeatsOutput(text2_2, validationLabel);
            logStage2_2Diagnostics({
                phase: `${logPhasePrefix}-stage2_2-result`,
                subjectIndexText: stage2_1SubjectIndexText,
                sceneInputText: attemptUserInputBody,
                finalInputText: attemptFinalUserInput,
                rawOutputText: text2_2,
                normalizedText: stage2_2Check?.normalizedText || '',
            });
            return { stage2_2Text: text2_2, stage2_2Result: stage2_2ResultObj, stage2_2Check };
        };

        const explicitSceneUnits = Array.isArray(targetSceneUnits)
            ? targetSceneUnits.filter((unit) => unit && String(unit.sceneId || '').trim())
            : [];
        const unitsToProcess = explicitSceneUnits.length > 0 ? explicitSceneUnits : sceneUnits;
        const isSingleExplicitScene = explicitSceneUnits.length === 1;
        const orchestrationSceneCount = isSingleExplicitScene
            ? 1
            : Math.max(sceneUnits.length, unitsToProcess.length, 0);
        const useBackendSceneOrchestration = !isSingleExplicitScene && orchestrationSceneCount > 1;
        const shouldDisableEpisodeRecovery = Boolean(
            sceneAnalysisModePayload === 'scene_beats_only'
            || useBackendSceneOrchestration
            || isSingleExplicitScene
        );

        if (isSingleExplicitScene) {
            const unit = explicitSceneUnits[0];
            const sceneLabel = `${label} [${unit.sceneId}]`;
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t(
                    `正在生成单场场景编排：${unit.sceneId}...`,
                    `Generating scene beats for single scene: ${unit.sceneId}...`
                ),
            });
            const singleSceneBlock = wrapSceneUnitAsScriptBlock(unit);
            const singleSceneBody = [
                `【单场处理模式】本次仅处理 Scene ID \`${unit.sceneId}\`。请仅输出该场景对应的一行 Scenes Table，不要处理其他场景。`,
                buildStage2_2UserInputFromStage1(stage1SourceText, singleSceneBlock),
            ].join('\n\n');
            const singleFinalInput = singleSceneBody;

            for (let fallbackAttempt = 0; fallbackAttempt <= MAX_ANALYSIS_FALLBACK_ATTEMPTS; fallbackAttempt += 1) {
                if (fallbackAttempt > 0) {
                    onLog?.(
                        `[${sceneLabel}] validation failed, auto retry ${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS}...`,
                        'warning'
                    );
                }
                onLog?.(
                    t(`[${sceneLabel}] 正在提交 LLM...`, `[${sceneLabel}] submitting to LLM...`),
                    'process'
                );
                const attempt = await runSingleStage2_2Attempt({
                    attemptLabel: sceneLabel,
                    attemptUserInputBody: singleSceneBody,
                    attemptFinalUserInput: singleFinalInput,
                    fallbackAttempt,
                    disableEpisodeRecovery: shouldDisableEpisodeRecovery,
                });
                if (attempt.stage2_2Check?.ok) {
                    onLog?.(
                        t(`[${sceneLabel}] LLM 已返回，校验通过`, `[${sceneLabel}] LLM returned and passed validation`),
                        'success'
                    );
                    return {
                        stage2_2Text: attempt.stage2_2Check.normalizedText,
                        stage2_2Result: attempt.stage2_2Result,
                        stage2_2Check: attempt.stage2_2Check,
                    };
                }
                lastError = attempt.stage2_2Check?.reason || t(
                    `${sceneLabel} 镜头节拍生成失败：未检测到有效的场景编排表。`,
                    `${sceneLabel} did not return a valid Scenes Table.`
                );
            }
            throw new Error(lastError || `${sceneLabel} failed after ${MAX_ANALYSIS_FALLBACK_ATTEMPTS} automatic retries.`);
        }

        if (useBackendSceneOrchestration) {
            const adaptedForSync = String(adaptedScriptForSplit || '').trim();
            const orchestrationSceneIds = sceneUnits
                .map((unit) => String(unit?.sceneId || '').trim())
                .filter(Boolean);
            onLog?.(`[${label}] backend scene orchestration enabled: ${orchestrationSceneCount} scene(s).`, 'info');
            if (projectId && activeEpisode?.id) {
                try {
                    if (orchestrationSceneIds.length > 0) {
                        await resetSceneOrchestrationProgress({
                            project_id: Number(projectId),
                            episode_id: Number(activeEpisode.id),
                            scene_ids: orchestrationSceneIds,
                        });
                        await clearSceneMarkdownPatchForScenes(orchestrationSceneIds, {
                            source: `${logPhasePrefix}-orchestration-clear`,
                        });
                        onLog?.(`[${label}] cleared stale orchestration data for ${orchestrationSceneIds.length} scene(s).`, 'info');
                    }
                } catch (clearErr) {
                    onLog?.(`[${label}] orchestration pre-clear warning: ${clearErr?.message || clearErr}`, 'warning');
                }
            }
            if (projectId && activeEpisode?.id && adaptedForSync) {
                try {
                    await syncSceneUnitsProgress({
                        project_id: Number(projectId),
                        episode_id: Number(activeEpisode.id),
                        script_text: adaptedForSync,
                        prefer_markers: true,
                    });
                    onLog?.(`[${label}] synced ${orchestrationSceneCount} scene unit(s) before orchestration.`, 'info');
                } catch (syncErr) {
                    onLog?.(`[${label}] scene units sync warning: ${syncErr?.message || syncErr}`, 'warning');
                }
            }
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t(
                    `已同步 ${orchestrationSceneCount} 场，正在由后端并行发起场景编排...`,
                    `Synced ${orchestrationSceneCount} scene(s); launching parallel scene beats on backend...`
                ),
            });

            const reportSceneOrchestrationPhase = ({ sceneId, phase, sceneOrder, totalScenes, errorCode }) => {
                const message = buildSceneOrchestrationPhaseMessage(sceneId, phase, {
                    sceneOrder,
                    totalScenes,
                    errorCode,
                    t,
                });
                if (!message) return;
                onLog?.(message, SCENE_ORCHESTRATION_PHASE_LOG_TYPES[phase] || 'info');
                if (phase === 'llm_submit') {
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t(
                            `场景编排进行中：${sceneId} 已提交 LLM（${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount}）...`,
                            `Scene beats in progress: ${sceneId} submitted (${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount})...`
                        ),
                    });
                } else if (phase === 'llm_returned') {
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t(
                            `场景编排进行中：${sceneId} LLM 已返回（${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount}）...`,
                            `Scene beats in progress: ${sceneId} LLM returned (${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount})...`
                        ),
                    });
                } else if (phase === 'importing') {
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t(
                            `场景编排进行中：${sceneId} 正在导入（${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount}）...`,
                            `Scene beats in progress: ${sceneId} importing (${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount})...`
                        ),
                    });
                } else if (phase === 'imported') {
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t(
                            `场景编排进行中：${sceneId} 已完成（${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount}）`,
                            `Scene beats in progress: ${sceneId} completed (${sceneOrder || '?'}/${totalScenes || orchestrationSceneCount})`
                        ),
                    });
                } else if (phase === 'failed') {
                    setAnalysisFlowStatus({
                        phase: 'warning',
                        message: t(
                            `场景编排失败：${sceneId}${errorCode ? `（${errorCode}）` : ''}`,
                            `Scene beats failed: ${sceneId}${errorCode ? ` (${errorCode})` : ''}`
                        ),
                    });
                }
            };

            const runSequentialSceneFallback = async (reason = '') => {
                if (reason) {
                    onLog?.(`[${label}] ${reason}`, 'warning');
                }
                onLog?.(
                    `[${label}] falling back to sequential per-scene orchestration for ${orchestrationSceneCount} scene(s).`,
                    'warning'
                );
                setAnalysisFlowStatus({
                    phase: 'scene_beats',
                    message: t(
                        `并行编排未成功，正在逐场生成场景编排（共 ${orchestrationSceneCount} 场）...`,
                        `Parallel orchestration did not succeed; generating scene beats sequentially (${orchestrationSceneCount} scenes)...`
                    ),
                });

                const validatedOutputs = [];
                let sequentialLastResult = null;
                for (const unit of sceneUnits) {
                    const sceneId = String(unit?.sceneId || '').trim();
                    if (!sceneId) continue;
                    const sceneLabel = `${label} [${sceneId}]`;
                    const singleSceneBlock = wrapSceneUnitAsScriptBlock(unit);
                    const singleSceneBody = [
                        `【单场处理模式】本次仅处理 Scene ID \`${sceneId}\`。请仅输出该场景对应的一行 Scenes Table，不要处理其他场景。`,
                        buildStage2_2UserInputFromStage1(stage1SourceText, singleSceneBlock),
                    ].join('\n\n');
                    let sceneAttempt = null;
                    for (let fallbackAttempt = 0; fallbackAttempt <= MAX_ANALYSIS_FALLBACK_ATTEMPTS; fallbackAttempt += 1) {
                        if (fallbackAttempt > 0) {
                            onLog?.(
                                `[${sceneLabel}] validation failed, auto retry ${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS}...`,
                                'warning'
                            );
                        }
                        onLog?.(
                            t(`[${sceneLabel}] 正在提交 LLM...`, `[${sceneLabel}] submitting to LLM...`),
                            'process'
                        );
                        const attempt = await runSingleStage2_2Attempt({
                            attemptLabel: sceneLabel,
                            attemptUserInputBody: singleSceneBody,
                            attemptFinalUserInput: singleSceneBody,
                            fallbackAttempt,
                            disableEpisodeRecovery: shouldDisableEpisodeRecovery,
                        });
                        if (attempt.stage2_2Check?.ok) {
                            sceneAttempt = attempt;
                            onLog?.(
                                t(`[${sceneLabel}] LLM 已返回，校验通过`, `[${sceneLabel}] LLM returned and passed validation`),
                                'success'
                            );
                            break;
                        }
                        lastError = attempt.stage2_2Check?.reason || lastError;
                    }
                    if (!sceneAttempt?.stage2_2Check?.ok) {
                        throw new Error(lastError || `${sceneLabel} failed during sequential fallback.`);
                    }
                    sequentialLastResult = sceneAttempt.stage2_2Result;
                    validatedOutputs.push({
                        sceneId,
                        sceneOrder: unit?.sceneOrder,
                        markdown: sceneAttempt.stage2_2Check.normalizedText,
                    });
                }

                const sceneMarkdownPatchMap = buildSceneMarkdownPatchFromPerSceneOutputs(
                    validatedOutputs,
                    sceneUnits
                );
                return {
                    perSceneParallel: true,
                    sceneMarkdownPatchMap,
                    stage2_2Text: mergeStage2_2SceneTableOutputs(validatedOutputs.map((item) => item.markdown)),
                    stage2_2Result: sequentialLastResult,
                    stage2_2Check: { ok: true, normalizedText: '' },
                };
            };

            let parallelOrchestrationFailed = false;
            let stopSceneOrchestrationPolling = null;
            if (activeEpisode?.id) {
                stopSceneOrchestrationPolling = createSceneOrchestrationProgressPoller({
                    getSnapshot: getEpisodeProgressSnapshot,
                    episodeId: Number(activeEpisode.id),
                    sceneUnits,
                    onPhase: reportSceneOrchestrationPhase,
                });
            }
            try {
            for (let fallbackAttempt = 0; fallbackAttempt <= MAX_ANALYSIS_FALLBACK_ATTEMPTS; fallbackAttempt += 1) {
                if (fallbackAttempt > 0) {
                    onLog?.(
                        `[${label}] validation failed, auto retry ${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS}...`,
                        'warning'
                    );
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t(
                            `场景编排校验失败，正在自动重试 (${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS})...`,
                            `Scene beats validation failed. Auto-retrying (${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS})...`
                        ),
                    });
                }
                let attempt;
                try {
                    attempt = await runSingleStage2_2Attempt({
                        attemptLabel: `${label} (sync-orchestration)`,
                        attemptUserInputBody: stage2_2UserInputBody,
                        attemptFinalUserInput: finalStage2_2UserInput,
                        fallbackAttempt,
                        disableEpisodeRecovery: true,
                    });
                } catch (orchErr) {
                    parallelOrchestrationFailed = true;
                    lastError = orchErr?.message || String(orchErr || '');
                    break;
                }
                const perSceneOutputs = extractPerSceneOutputsFromResult(attempt.stage2_2Result);
                if (attempt.stage2_2Result?.meta?.recovered_from_episode_poll) {
                    lastError = t(
                        '并行场景编排未完成，拒绝使用分集缓存结果。',
                        'Parallel scene orchestration is not finished; refused cached episode result.'
                    );
                    continue;
                }
                if (perSceneOutputs.length > 0) {
                    const validatedOutputs = [];
                    let hasInvalidScene = false;
                    for (const item of perSceneOutputs) {
                        const sceneCheck = validateStage2_2BeatsOutput(
                            item.markdown,
                            `${label} [${item.sceneId}]`
                        );
                        if (!sceneCheck.ok) {
                            hasInvalidScene = true;
                            lastError = sceneCheck.reason || lastError;
                            break;
                        }
                        validatedOutputs.push({
                            ...item,
                            markdown: sceneCheck.normalizedText,
                        });
                    }
                    if (!hasInvalidScene && validatedOutputs.length >= orchestrationSceneCount) {
                        const sceneMarkdownPatchMap = buildSceneMarkdownPatchFromPerSceneOutputs(
                            validatedOutputs,
                            sceneUnits
                        );
                        return {
                            perSceneParallel: true,
                            sceneMarkdownPatchMap,
                            stage2_2Text: mergeStage2_2SceneTableOutputs(validatedOutputs.map((item) => item.markdown)),
                            stage2_2Result: attempt.stage2_2Result,
                            stage2_2Check: { ok: true, normalizedText: '' },
                        };
                    }
                    if (!hasInvalidScene && validatedOutputs.length > 0) {
                        lastError = t(
                            `并行场景编排返回 ${validatedOutputs.length}/${orchestrationSceneCount} 场，等待完整结果。`,
                            `Parallel orchestration returned ${validatedOutputs.length}/${orchestrationSceneCount} scenes; waiting for complete result.`
                        );
                        continue;
                    }
                }
                lastError = attempt.stage2_2Check?.reason || lastError || t(
                    `${label} 镜头节拍生成失败：未检测到有效的分场景编排结果。`,
                    `${label} did not return valid per-scene orchestration outputs.`
                );
            }
            } finally {
                stopSceneOrchestrationPolling?.();
            }
            return runSequentialSceneFallback(
                parallelOrchestrationFailed
                    ? t('后端并行编排请求失败，正在逐场重试。', 'Backend parallel orchestration request failed; retrying scenes sequentially.')
                    : t('后端并行编排校验未通过，正在逐场重试。', 'Backend parallel orchestration validation failed; retrying scenes sequentially.')
            );
        }

        for (let fallbackAttempt = 0; fallbackAttempt <= MAX_ANALYSIS_FALLBACK_ATTEMPTS; fallbackAttempt += 1) {
            if (fallbackAttempt > 0) {
                onLog?.(
                    `[${label}] validation failed, auto retry ${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS}...`,
                    'warning'
                );
                setAnalysisFlowStatus({
                    phase: 'scene_beats',
                    message: t(
                        `场景编排校验失败，正在自动重试 (${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS})...`,
                        `Scene beats validation failed. Auto-retrying (${fallbackAttempt}/${MAX_ANALYSIS_FALLBACK_ATTEMPTS})...`
                    ),
                });
            }

            const attempt = await runSingleStage2_2Attempt({
                attemptLabel: label,
                attemptUserInputBody: stage2_2UserInputBody,
                attemptFinalUserInput: finalStage2_2UserInput,
                fallbackAttempt,
                disableEpisodeRecovery: shouldDisableEpisodeRecovery,
            });
            if (attempt.stage2_2Check?.ok) {
                return {
                    stage2_2Text: attempt.stage2_2Check.normalizedText,
                    stage2_2Result: attempt.stage2_2Result,
                    stage2_2Check: attempt.stage2_2Check,
                };
            }
            lastError = attempt.stage2_2Check?.reason || t(`${label} 镜头节拍生成失败：未检测到有效的场景编排表。`, `${label} did not return a valid Scenes Table.`);
        }

        throw new Error(lastError || `${label} failed after ${MAX_ANALYSIS_FALLBACK_ATTEMPTS} automatic retries.`);
    }, [
        activeEpisode?.id,
        analysisAttentionNotes,
        awaitAnalyzeSceneWithRecovery,
        buildSceneMarkdownPatchFromPerSceneOutputs,
        buildStage2_2UserInputFromStage1,
        clearSceneMarkdownPatchForScenes,
        extractAdaptedScriptFromStage2_2UserInputBody,
        extractAnalysisTextFromResult,
        extractPerSceneOutputsFromResult,
        fetchPrompt,
        logStage2_2Diagnostics,
        mergeStage2_2SceneTableOutputs,
        onLog,
        parseSceneUnitsFromScriptMarkers,
        projectId,
        resetSceneOrchestrationProgress,
        selectedReuseSubjectAssets,
        selectedScriptAnalysisApiId,
        setAnalysisFlowStatus,
        syncSceneUnitsProgress,
        t,
        validateStage2_2BeatsOutput,
        wrapSceneUnitAsScriptBlock,
    ]);

    const runPostImportSceneSubjectPipeline = useCallback(async (importReport, explicitText = null, options = {}) => {
        if (sceneBeatsOnlyRerunInFlightRef.current) {
            const importedSceneRows = Array.isArray(importReport?.importedSceneRows) ? importReport.importedSceneRows : [];
            onLog?.('仅场景重排期间，视觉资产流程已按保护策略暂停。', 'info');
            return {
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
        }

        if (phase2GenerationInFlightRef.current) {
            onLog?.('Skipped duplicate Stage 3 asset-design trigger while one is already running.', 'warning');
            return {
                checkedSceneCount: 0,
                missingSceneCount: 0,
                missingItemCount: 0,
                missingSceneReports: [],
                supplementReport: {
                    createdItems: [], skippedItems: [], failedItems: [], sceneReports: [],
                    countsByType: { character: 0, prop: 0, environment: 0 },
                },
                importedSubjectCounts: { character: 0, prop: 0, environment: 0 },
            };
        }

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

        onLog?.(`[Stage 3 Debug] checking early return condition: projectId=${projectId}, importedSceneRows count=${importedSceneRows.length}`);

        if (!projectId) {
            onLog?.(`[Stage 3 Debug] aborting because projectId is empty.`);
            return emptyReport;
        }

                const authoritativeSubjectText = explicitText || llmRawResultContent || llmResultContent || activeEpisode?.ai_scene_analysis_result || '';
                const persistedSubjectIndexText = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
                const extractedSections = extractAnalysisSections(authoritativeSubjectText);
                let subjectIndexText = extractPureSubjectIndexText(options.explicitSubjectIndexText || persistedSubjectIndexText || (extractedSections.hasStructuredSubjectIndex ? (extractedSections.subjectIndexText || "") : ""));
                let adaptationBodyText = String(adaptationText || activeEpisode?.ai_scene_analysis_adaptation || '').trim();
                if (!adaptationBodyText && /(?:###?\s*第二部分[:：]?\s*修改后的剧本|###?\s*Second\s*Part[:：]?\s*Adapted\s*Script|【场景\s*|Scene\s*\d+)/i.test(authoritativeSubjectText)) {
                    adaptationBodyText = String(extractStage1AdaptedScriptBody(authoritativeSubjectText) || '').trim();
                }

                if (adaptationBodyText) {
                    onLog?.(`[Stage 2 Scene Analysis] Extracted optimized script (length: ${adaptationBodyText.length})`);
                }

          onLog?.(`[Stage 3 Asset Design] Initial authoritative text length: ${authoritativeSubjectText.length}`);

        // Try to match the block wrapped by at least 5 dashes: ---------
        if (options?.isRetryPhase2) {
            onLog?.(`[Stage 3 Asset Design] Retry mode enabled. Bypassing asset-index structural check.`);
            // Retry may receive a manually edited Subject Index block without the original Stage 2 wrapper.
            if (!subjectIndexText.trim() && explicitText) {
                const explicitSections = extractAnalysisSections(explicitText);
                subjectIndexText = extractPureSubjectIndexText(explicitSections?.hasStructuredSubjectIndex
                    ? String(explicitSections.subjectIndexText || '').trim()
                    : '');
            }
        } else if (
            String(options.explicitSubjectIndexText || '').trim()
            || subjectIndexText.trim()
            || extractedSections.hasStructuredSubjectIndex
        ) {
            onLog?.(`[Stage 2 Asset Index] Using asset index for Stage 3 (length: ${subjectIndexText.length})`);
        } else {
            onLog?.(`[Stage 3 Asset Design] Error: Failed to find the Stage 2 asset index block. Aborting asset design.`, 'error');
            throw new Error(SUBJECT_INDEX_PARSE_ERROR);
        }

        // Persist authoritative Stage 2 outputs so Stage 3 uses the optimized script and asset index as inputs.
        // Asset reruns must treat the Subject Index as read-only input: category/single reruns often pass a filtered
        // index, and writing that back would shrink the persisted Stage 2 asset manifest.
          if (subjectIndexText.trim() || adaptationBodyText.trim()) {
              if (options?.isRetryPhase2) {
                  onLog?.(`[Stage 2 Outputs] Asset rerun uses read-only asset index; skipped Stage 2 writeback (asset_index_len=${subjectIndexText.length}, optimized_script_len=${adaptationBodyText.length})`, 'info');
              } else {
                  if (subjectIndexText.trim()) setSubjectIndexText(extractPureSubjectIndexText(subjectIndexText));
                  if (adaptationBodyText.trim()) setAdaptationText(adaptationBodyText);
                  const updatePayload = {};
                  if (subjectIndexText.trim()) updatePayload.ai_scene_analysis_subject_index = extractPureSubjectIndexText(subjectIndexText).trim();
                  if (adaptationBodyText.trim()) updatePayload.ai_scene_analysis_adaptation = adaptationBodyText.trim();
                  
                  try {
                      await updateEpisode(activeEpisode.id, updatePayload);
                      onLog?.(`[Stage 2 Outputs] Saved asset index and optimized script (asset_index_len=${subjectIndexText.length}, optimized_script_len=${adaptationBodyText.length})`);
                  } catch (error) {
                      onLog?.(`[Stage 2 Outputs] Warning: Failed to save asset index / optimized script: ${error.message}`);
                  }
              }
          }

        if (!subjectIndexText.trim()) {
            console.log("No asset index found in the analysis result. Skipping Stage 3 asset design.");
            return emptyReport;
        }

        phase2GenerationInFlightRef.current = true;
        if (options?.isRetryPhase2) {
            setIsRetryingPhase2(true);
        }



        const getAssetDesignTaskLabel = (key) => {
            const labels = {
                characters: t('角色', 'Characters'),
                props: t('道具', 'Props'),
                environments: t('环境', 'Environments'),
                posters: t('封面/海报', 'Posters/Covers'),
            };
            return labels[key] || String(key || '');
        };

        const buildAssetReadyHint = (taskKey) => {
            const label = getAssetDesignTaskLabel(taskKey);
            if (!label) return '';
            return t(
                `「${label}」已入库，可前往资产库开始生成`,
                `"${label}" is ready — open the Assets library to start generation`
            );
        };

        const promptFilesRaw = [


            { key: 'characters', nodeKey: 'asset_design_character', path: 'skills/scene_analysis_feature_stack/entity_design_character.md' },


            { key: 'environments', nodeKey: 'asset_design_environment', path: 'skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md' },


            { key: 'props', nodeKey: 'asset_design_prop', path: 'skills/scene_analysis_feature_stack/entity_design_prop.md' }


        ];



        const normalizeTargetEntityTypeKey = (value) => {
            const key = String(value || '').trim().toLowerCase();
            if (!key) return '';
            if (['character', 'characters', 'role', 'roles', '人物', '角色'].includes(key)) return 'characters';
            if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(key)) return 'props';
            if (['environment', 'environments', 'env', 'scene', 'scenes', '场景', '环境'].includes(key)) return 'environments';
            if (['poster', 'posters', 'cover', 'covers', 'cover_poster', '海报', '封面'].includes(key)) return key === 'covers' ? 'covers' : 'posters';
            return key;
        };

        let targetFilters = Array.isArray(options.targetEntityTypes)
            ? Array.from(new Set(options.targetEntityTypes.map(normalizeTargetEntityTypeKey).filter(Boolean)))
            : null;
        const requestedTargetFilters = targetFilters ? [...targetFilters] : null;


        if (targetFilters && (targetFilters.includes('posters') || targetFilters.includes('covers')) && !targetFilters.includes('environments')) {


            targetFilters = [...targetFilters, 'environments'];


        }



        let stage3AutoStart = {
            asset_design_character: true,
            asset_design_prop: true,
            asset_design_environment: true,
        };
        if (!targetFilters) {
            try {
                const flowRegistry = await getSceneAnalysisFlowRegistry();
                const configured = flowRegistry?.stage3_auto_start || flowRegistry?.config?.stage3_auto_start || {};
                stage3AutoStart = { ...stage3AutoStart, ...configured };
                onLog?.(`[Stage 3 Asset Design] Loaded auto-start config: character=${stage3AutoStart.asset_design_character ? 'on' : 'off'}, prop=${stage3AutoStart.asset_design_prop ? 'on' : 'off'}, environment=${stage3AutoStart.asset_design_environment ? 'on' : 'off'}`, 'info');
            } catch (flowErr) {
                onLog?.(`[Stage 3 Asset Design] Failed to load flow auto-start config; using defaults. ${flowErr?.message || flowErr}`, 'warning');
            }
        }

        const promptFiles = promptFilesRaw.filter(p => {
            if (targetFilters) return targetFilters.includes(p.key);
            return stage3AutoStart[p.nodeKey] !== false;
        });

        if (!targetFilters && promptFiles.length === 0) {
            onLog?.('[Stage 3 Asset Design] All Stage 3 auto-start switches are disabled; skipping automatic asset design.', 'info');
            return emptyReport;
        }


        const targetAssetsCount = promptFiles.length;
        const runningAssetTaskLabels = promptFiles.map((p) => getAssetDesignTaskLabel(p.key)).filter(Boolean).join('、');



        setAnalysisFlowStatus({


            phase: "assets_gen",


            message: t(
                `✨ 正在执行第四阶段资产设计 (共 ${targetAssetsCount} 项并发推演${runningAssetTaskLabels ? `：${runningAssetTaskLabels}` : ''})...`,
                `Running Stage 4 asset design (${targetAssetsCount} tasks${runningAssetTaskLabels ? `: ${runningAssetTaskLabels.replace(/、/g, ', ')}` : ''})...`
            ),


        });



        let assetsGenCompletedCount = 0;
        const assetsGenCompletedKeys = [];



        try {
            throwIfAnalysisStopped();


            onLog?.(`[Stage 3 Asset Design] Preparing to fetch ${targetAssetsCount} entity_design prompts`);



            const commonPromptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design_common.md").catch(() => null);
            const commonPromptContent = commonPromptRes?.content || "";

            const promptsData = await Promise.all(
                promptFiles.map(async p => ({
                    ...p,
                    content: commonPromptContent + "\n\n" + ((await fetchPrompt(p.path).catch(() => null))?.content || "")
                }))
            );

            let finalSubjectIndexText = extractPureSubjectIndexText(subjectIndexText);
            
            const designProjectContextSection = buildStage1ProjectContextSection()
                .replace('Project Context (prepend and treat as high-priority constraints):', 'Project Context (prepend and treat as high-priority constraints for generating design assets):')
                .replace('Use this project context as first-class constraints before analyzing the script.', 'Use this project context as first-class constraints before generating the subjects.');

            if (designProjectContextSection) {
                finalSubjectIndexText = `${designProjectContextSection}\n\n[第二阶段资产清单 - 第三阶段权威输入]\n${finalSubjectIndexText}`;
            }

            onLog?.(`[Stage 3 Asset Design] Launching ${targetAssetsCount} asset-design LLM call(s): ${promptFiles.map((p) => p.key).join(', ') || 'none'}.`);

            const phase1SystemApiId = selectedScriptAnalysisApiId;
            if (phase1SystemApiId) {
                onLog?.(`[Stage 3 Asset Design] Reusing Stage 1 system_api_id=${phase1SystemApiId} for script_analysis routing.`, 'info');
            } else {
                onLog?.('[Stage 3 Asset Design] Stage 1 system_api_id is missing; fallback routing may select a different API.', 'warning');
            }

            const phase2StartedAt = Date.now();
            const phase2BatchTraceId = `phase2-assets-${activeEpisode?.id || 'noep'}-${phase2StartedAt}`;

            const hasAnySubjects = (payload) => {
                if (!payload || typeof payload !== 'object') return false;
                return (
                    (Array.isArray(payload.characters) && payload.characters.length > 0)
                    || (Array.isArray(payload.props) && payload.props.length > 0)
                    || (Array.isArray(payload.environments) && payload.environments.length > 0)
                    || (Array.isArray(payload.posters) && payload.posters.length > 0)
                    || (Array.isArray(payload.covers) && payload.covers.length > 0)
                );
            };

            const buildSubtaskSubjectsPayload = (key, sourcePayload) => {
                const input = normalizePosterBucketsInSubjectsPayload(
                    (sourcePayload && typeof sourcePayload === 'object') ? sourcePayload : {}
                );
                const payload = { characters: [], environments: [], props: [], posters: [], covers: [] };
                if (key === 'characters') {
                    payload.characters = Array.isArray(input.characters) ? input.characters : [];
                } else if (key === 'props') {
                    payload.props = Array.isArray(input.props) ? input.props : [];
                } else if (key === 'environments') {
                    payload.environments = Array.isArray(input.environments) ? input.environments : [];
                    payload.posters = Array.isArray(input.posters) ? input.posters : [];
                    payload.covers = Array.isArray(input.covers) ? input.covers : [];
                } else if (key === 'posters') {
                    payload.posters = Array.isArray(input.posters) ? input.posters : [];
                    payload.covers = Array.isArray(input.covers) ? input.covers : [];
                } else {
                    payload.characters = Array.isArray(input.characters) ? input.characters : [];
                    payload.props = Array.isArray(input.props) ? input.props : [];
                    payload.environments = Array.isArray(input.environments) ? input.environments : [];
                    payload.posters = Array.isArray(input.posters) ? input.posters : [];
                    payload.covers = Array.isArray(input.covers) ? input.covers : [];
                }

                const payloadTargetFilters = Array.isArray(requestedTargetFilters) && requestedTargetFilters.length > 0
                    ? requestedTargetFilters
                    : targetFilters;
                if (Array.isArray(payloadTargetFilters) && payloadTargetFilters.length > 0) {
                    const filtered = { characters: [], environments: [], props: [], posters: [], covers: [] };
                    if (payloadTargetFilters.includes('characters')) filtered.characters = payload.characters;
                    if (payloadTargetFilters.includes('props')) filtered.props = payload.props;
                    if (payloadTargetFilters.includes('environments')) filtered.environments = payload.environments;
                    if (payloadTargetFilters.includes('posters') || payloadTargetFilters.includes('covers')) {
                        filtered.posters = payload.posters;
                        filtered.covers = payload.covers;
                    }
                    return filtered;
                }
                return payload;
            };

                        // Run them concurrently
            const results = await Promise.allSettled(
                promptsData.map(async (pData, index) => {
                    throwIfAnalysisStopped();
                    const isPrimary = index === 0;
                    const subtaskTraceId = `${phase2BatchTraceId}-${pData.key || `slot${index + 1}`}`;
                    const subtaskImportSessionId = `import-${subtaskTraceId}`;
                    onLog?.(`[Stage 3 Asset Design] Subtask submit key=${pData.key || `slot${index + 1}`} trace_id=${subtaskTraceId}`, 'info');

                    let specificSubjectIndexText = finalSubjectIndexText;

                    const filteredSubjectIndex = filterSubjectIndexTextForAssetTask(specificSubjectIndexText, pData.key, requestedTargetFilters);
                    specificSubjectIndexText = filteredSubjectIndex.text;
                    if (filteredSubjectIndex.totalRows > 0) {
                        onLog?.(`[Stage 3 Asset Design] Subject Index filtered key=${pData.key || `slot${index + 1}`} kept=${filteredSubjectIndex.keptRows}/${filteredSubjectIndex.totalRows}`, 'info');
                    }
                    const subtaskRequestedTargets = Array.isArray(requestedTargetFilters) && requestedTargetFilters.length > 0
                        ? requestedTargetFilters
                        : (pData.key === 'characters'
                            ? ['characters']
                            : (pData.key === 'props'
                                ? ['props']
                                : (pData.key === 'environments' ? ['environments', 'posters', 'covers'] : [])));
                    const sceneAnalysisModeForSubtask = `2_pass_generate_assets_${pData.key}${subtaskRequestedTargets.length ? `__targets_${subtaskRequestedTargets.join('_')}` : ''}`;

                    return awaitAnalyzeSceneWithRecovery(
                        () => runScriptAnalysisFlowAnalyzeNode(
                            pData.nodeKey || (pData.key === 'characters' ? 'asset_design_character' : (pData.key === 'props' ? 'asset_design_prop' : 'asset_design_environment')),
                            specificSubjectIndexText,  
                            pData.content, 
                            null, 
                            isPrimary ? (activeEpisode?.id || null) : null, // Only bind episode ID on the first one to avoid DB overwrite race conditions
                            analysisAttentionNotes, 
                            selectedReuseSubjectAssets, 
                            {
                                onTaskCreated: (taskId) => {
                                    const stableTaskId = String(taskId || '').trim();
                                    onLog?.(`[Stage 3 Asset Design] Subtask task created key=${pData.key || `slot${index + 1}`} trace_id=${subtaskTraceId} task_id=${stableTaskId}`, 'info');
                                    registerActiveAnalysisTask(stableTaskId);
                                    if (activeEpisode?.id && stableTaskId) {
                                        saveAnalysisTaskMarker(activeEpisode.id, {
                                            taskId: stableTaskId,
                                            startedAt: phase2StartedAt,
                                            phase: 2,
                                        });
                                        updateEpisodeAnalysisRun(activeEpisode.id, {
                                            taskId: stableTaskId,
                                            phase: 2,
                                        });
                                    }
                                },
                                analysisTraceId: subtaskTraceId,
                                analysisFeatures: {
                                    target_entity_types: subtaskRequestedTargets,
                                    asset_task_key: pData.key || `slot${index + 1}`,
                                },
                            }, 
                            projectId,
                            "script_analysis",
                            phase1SystemApiId,
                            sceneAnalysisModeForSubtask
                        ),
                        { startedAt: phase2StartedAt, baselineText: '', resultField: 'none' } // prevent persistence internally by passing no conflict
                    ).then(async (res) => {
                        const responseTraceId = String(res?.meta?.analysis_trace_id || res?.analysis_trace_id || '').trim();
                        throwIfAnalysisStopped();
                        const aText = extractAnalysisTextFromResult(res);
                        const bJson = resolveSubjectsJsonFromAnalyzeResult(res, aText);

                        assetsGenCompletedCount += 1;
                        if (pData.key && !assetsGenCompletedKeys.includes(pData.key)) {
                            assetsGenCompletedKeys.push(pData.key);
                        }
                        onLog?.(`[Stage 3 Asset Design] Subtask completed key=${pData.key || `slot${index + 1}`} trace_id=${subtaskTraceId}${responseTraceId ? ` response_trace_id=${responseTraceId}` : ''}`, 'info');

                        const subtaskPayload = buildSubtaskSubjectsPayload(pData.key, bJson || {});
                        let subtaskImportReport = null;
                        let subtaskImportError = '';
                        const subtaskHasImportableSubjects = hasAnySubjects(subtaskPayload);
                        if (subtaskHasImportableSubjects) {
                            throwIfAnalysisStopped();
                            const subtaskTargetTypes = (() => {
                                if (pData.key === 'characters') return ['characters'];
                                if (pData.key === 'props') return ['props'];
                                if (pData.key === 'environments' && Array.isArray(requestedTargetFilters) && requestedTargetFilters.length > 0) {
                                    return requestedTargetFilters.filter((item) => ['environments', 'posters', 'covers'].includes(item));
                                }
                                if (pData.key === 'environments') return ['environments', 'posters', 'covers'];
                                if (pData.key === 'posters') return ['posters', 'covers'];
                                return undefined;
                            })();

                            try {
                                subtaskImportReport = await importSubjectsJsonWithDedupe(
                                    JSON.stringify(subtaskPayload, null, 2),
                                    {
                                        reason: `phase2-subtask-${pData.key || `slot${index + 1}`}`,
                                        subjectsJson: subtaskPayload,
                                        importOptions: {
                                            onLog,
                                            projectId,
                                            episodeId: activeEpisode?.id,
                                            importSessionId: subtaskImportSessionId,
                                            targetEntityTypes: subtaskTargetTypes,
                                            overwriteExistingSubjects: Boolean(options?.isRetryPhase2),
                                            suppressAlerts: true,
                                        },
                                    }
                                );
                                const subCreated = subtaskImportReport?.createdSubjectItems?.length || 0;
                                const subSkipped = subtaskImportReport?.skippedSubjectItems?.length || 0;
                                onLog?.(`[Stage 3 Asset Design] Subtask import done key=${pData.key || `slot${index + 1}`} trace_id=${subtaskTraceId} created=${subCreated} skipped=${subSkipped}`, 'success');
                            } catch (subImportErr) {
                                subtaskImportError = String(subImportErr?.message || subImportErr || 'unknown import error');
                                onLog?.(`[Stage 3 Asset Design] Subtask import failed key=${pData.key || `slot${index + 1}`} trace_id=${subtaskTraceId}: ${subImportErr?.message || subImportErr}`, 'warning');
                            }
                        } else {
                            onLog?.(`[Stage 3 Asset Design] Subtask has no importable subjects key=${pData.key || `slot${index + 1}`} trace_id=${subtaskTraceId}`, 'warning');
                        }

                        const completedAssetTaskLabels = assetsGenCompletedKeys.map(getAssetDesignTaskLabel).filter(Boolean).join('、');
                        const assetImportReady = Boolean(
                            subtaskHasImportableSubjects
                            && subtaskImportReport
                            && !subtaskImportError
                        );
                        setAnalysisFlowStatus({
                            phase: "assets_gen",
                            message: t(
                                `✨ 第四阶段资产推演中 (${assetsGenCompletedCount}/${targetAssetsCount} 已完成${completedAssetTaskLabels ? `：${completedAssetTaskLabels}` : ''})...`,
                                `Running Stage 4 asset design (${assetsGenCompletedCount}/${targetAssetsCount} completed${completedAssetTaskLabels ? `: ${completedAssetTaskLabels.replace(/、/g, ', ')}` : ''})...`
                            ),
                            highlightHint: assetImportReady ? buildAssetReadyHint(pData.key) : '',
                        });

                        return {
                            key: pData.key,
                            traceId: subtaskTraceId,
                            importSessionId: subtaskImportSessionId,
                            result: res,
                            analysisText: aText,
                            subjectsJson: bJson,
                            hasImportableSubjects: subtaskHasImportableSubjects,
                            subtaskImportReport,
                            subtaskImportError,
                        };
                    });
                })
            );

            throwIfAnalysisStopped();

            const completedAssetTaskLabels = assetsGenCompletedKeys.map(getAssetDesignTaskLabel).filter(Boolean).join('、');
            const assetsGenCompleteMessage = t(
                `✅ 第四阶段资产推演已完成 (${assetsGenCompletedCount}/${targetAssetsCount}${completedAssetTaskLabels ? `：${completedAssetTaskLabels}` : ''})`,
                `Stage 4 asset design completed (${assetsGenCompletedCount}/${targetAssetsCount}${completedAssetTaskLabels ? `: ${completedAssetTaskLabels.replace(/、/g, ', ')}` : ''})`
            );
            finalizeAnalysisFlowHistoryForPhase('assets_gen', assetsGenCompleteMessage);
            setAnalysisFlowStatus({
                phase: 'assets_gen',
                message: assetsGenCompleteMessage,
            });

            // Merge results
            let mergedBackendSubjectsJson = { characters: [], environments: [], props: [], posters: [], covers: [] };
            if (options.targetEntityTypes && Array.isArray(options.targetEntityTypes)) {
                const existingEntities = getAnalysisEntitiesPayloadFromJsonText(
                    activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || ''
                ) || {};
                ['characters', 'environments', 'props', 'posters', 'covers'].forEach(k => {
                    const isTarget = options.targetEntityTypes.includes(k) || ((k === 'posters' || k === 'covers') && (options.targetEntityTypes.includes('posters') || options.targetEntityTypes.includes('covers')));
                    if (!isTarget && existingEntities[k]) {
                        mergedBackendSubjectsJson[k] = existingEntities[k];
                    }
                });
            }
            let rawTextParts = [];
            
            for (let idx = 0; idx < results.length; idx += 1) {
                const r = results[idx];
                if (r.status === 'fulfilled' && r.value.result) {
                    const bJson = r.value.subjectsJson || {};
                    const aText = r.value.analysisText || '';

                                          if (bJson) {
                          if (r.value.key === 'characters' && bJson.characters) mergedBackendSubjectsJson.characters = bJson.characters;
                          if (r.value.key === 'environments') {
                              if (bJson.environments && (!options.targetEntityTypes || options.targetEntityTypes.includes('environments'))) mergedBackendSubjectsJson.environments = bJson.environments;
                              if (bJson.posters && (!options.targetEntityTypes || options.targetEntityTypes.includes('posters') || options.targetEntityTypes.includes('covers'))) mergedBackendSubjectsJson.posters = bJson.posters;
                              if (bJson.covers && (!options.targetEntityTypes || options.targetEntityTypes.includes('covers') || options.targetEntityTypes.includes('posters'))) mergedBackendSubjectsJson.covers = bJson.covers;
                          }
                          if (r.value.key === 'props' && bJson.props) mergedBackendSubjectsJson.props = bJson.props;
                        if (r.value.key === 'posters') {
                            if (bJson.posters && (!options.targetEntityTypes || options.targetEntityTypes.includes('posters') || options.targetEntityTypes.includes('covers'))) mergedBackendSubjectsJson.posters = bJson.posters;
                            if (bJson.covers && (!options.targetEntityTypes || options.targetEntityTypes.includes('covers') || options.targetEntityTypes.includes('posters'))) mergedBackendSubjectsJson.covers = bJson.covers;
                        }
                    }
                    if (aText) {
                        if (r.value.key === 'environments') {
                            let extEnv = bJson?.environments || [];
                            let extPos = bJson?.posters || bJson?.covers || [];
                            if (extEnv.length > 0 || extPos.length > 0) {
                                let wrapObj = {};
                                if (extEnv.length > 0) wrapObj.environments = extEnv;
                                if (extPos.length > 0) wrapObj.posters = extPos;
                                rawTextParts.push(`\n\n\`\`\`json\n${JSON.stringify(wrapObj, null, 2)}\n\`\`\`\n\n`);
                            } else {
                                rawTextParts.push(`\n\n${aText}\n\n`);
                            }
                        } else {
                            let extractedArr = bJson && bJson[r.value.key] ? bJson[r.value.key] : null;
                            if (r.value.key === 'posters' && (!extractedArr || !extractedArr.length) && bJson?.covers) {
                                extractedArr = bJson.covers;
                            }
                            if (extractedArr && extractedArr.length > 0) {
                                rawTextParts.push(`\n\n\`\`\`json\n${JSON.stringify({[r.value.key]: extractedArr}, null, 2)}\n\`\`\`\n\n`);
                            } else {
                                rawTextParts.push(`\n\n${aText}\n\n`);
                            }
                        }
                    }
                } else if (r.status === 'rejected') {
                    const failedKey = promptsData[idx]?.key || `slot${idx + 1}`;
                    const failedTraceId = `${phase2BatchTraceId}-${failedKey}`;
                    onLog?.(`[Stage 3 Asset Design] Warning: task ${failedKey} failed (trace_id=${failedTraceId}): ${r.reason}`, "warning");
                }
            }

            const canonicalAssetDesignText = String(
                buildCanonicalAssetDesignJsonText(mergedBackendSubjectsJson) || rawTextParts.join('\n')
            ).trim();
            setLlmAssetRawResultContent(canonicalAssetDesignText);

            // Override to persist true result manually
            try {
                if (canonicalAssetDesignText) {
                    onLog?.('[Stage 3 Asset Design] Persisting merged 4-part asset-design output to ai_entity_design_result...', 'process');
                    await persistLlmResultContent(canonicalAssetDesignText || '', 'ai_entity_design_result');
                }
            } catch (persistErr) {
                onLog?.(`[Stage 3 Asset Design] Raw output save warning: ${persistErr?.message || persistErr}`, 'warning');
            }

            if (canonicalAssetDesignText) {
                throwIfAnalysisStopped();
                // Safeguard: make sure we are not importing plain text phase 1 by mistake
                const hasValidSubjectJsonBlock = /"characters"\s*:\s*\[|"props"\s*:\s*\[|"environments"\s*:\s*\[|"posters"\s*:\s*\[|"covers"\s*:\s*\[/i.test(canonicalAssetDesignText);
                
                if (!hasValidSubjectJsonBlock && Object.values(mergedBackendSubjectsJson).every(arr => arr.length === 0)) {
                    onLog?.(`[Stage 3 Asset Design] Warning: AI did not return a valid asset-design JSON block. Skipping import to prevent overwriting the Stage 2 asset index.`, "warning");
                    throw new Error("AI 引擎在整理出场名单时开小差了，未能返回标准数据表。请点击查阅原文检查，是否可以手动重新生成。");
                } else {
                    const completedReports = results
                        .filter((item) => item.status === 'fulfilled' && item.value && item.value.subtaskImportReport)
                        .map((item) => item.value.subtaskImportReport);

                    const subtaskReports = results.map((item, idx) => {
                        const fallbackKey = promptsData[idx]?.key || `slot${idx + 1}`;
                        const fallbackTraceId = `${phase2BatchTraceId}-${fallbackKey}`;
                        if (item.status === 'fulfilled' && item.value) {
                            const created = Number(item.value.subtaskImportReport?.createdSubjectItems?.length || 0);
                            const skipped = Number(item.value.subtaskImportReport?.skippedSubjectItems?.length || 0);
                            const hasImportableSubjects = Boolean(item.value.hasImportableSubjects);
                            const status = item.value.subtaskImportError
                                ? 'import_failed'
                                : (hasImportableSubjects || created > 0 || skipped > 0 ? 'ok' : 'incomplete_return');
                            const recommendation = status === 'incomplete_return'
                                ? `LLM 已返回但未解析到可入库的 ${fallbackKey} 资产。建议点击“重跑失败路由”，仅重跑缺失资产类型：${fallbackKey}。`
                                : '';
                            return {
                                key: item.value.key || fallbackKey,
                                traceId: item.value.traceId || fallbackTraceId,
                                importSessionId: item.value.importSessionId || `import-${fallbackTraceId}`,
                                status,
                                created,
                                skipped,
                                error: String(item.value.subtaskImportError || ''),
                                recommendation,
                            };
                        }
                        return {
                            key: fallbackKey,
                            traceId: fallbackTraceId,
                            importSessionId: `import-${fallbackTraceId}`,
                            status: 'llm_failed',
                            created: 0,
                            skipped: 0,
                            error: String(item?.reason || ''),
                        };
                    });

                    const mergedCounts = completedReports.reduce((acc, report) => {
                        acc.character += Number(report?.importedSubjectCounts?.character || 0);
                        acc.prop += Number(report?.importedSubjectCounts?.prop || 0);
                        acc.environment += Number(report?.importedSubjectCounts?.environment || 0);
                        acc.poster += Number(report?.importedSubjectCounts?.poster || 0);
                        return acc;
                    }, { character: 0, prop: 0, environment: 0, poster: 0 });

                    const createdItems = completedReports.flatMap((report) => Array.isArray(report?.createdSubjectItems) ? report.createdSubjectItems : []);
                    const skippedItems = completedReports.flatMap((report) => Array.isArray(report?.skippedSubjectItems) ? report.skippedSubjectItems : []);

                    const failedSubtaskItems = subtaskReports
                        .filter((x) => x.status !== 'ok')
                        .map((x) => ({
                            key: x.key,
                            traceId: x.traceId,
                            importSessionId: x.importSessionId,
                            reason: x.error || x.recommendation || x.status,
                            recommendation: x.recommendation || '',
                        }));
                    const createdLen = createdItems.length;
                    const matchedLen = skippedItems.length;
                    onLog?.(`[Stage 3 Asset Design] Independent subtask imports completed. Created/Updated: ${createdLen}, Matched/Skipped: ${matchedLen}`);
                    if (failedSubtaskItems.length > 0) {
                        const retryTypes = failedSubtaskItems.map((x) => x.key).filter(Boolean).join(', ');
                        onLog?.(`[Stage 3 Asset Design] Incomplete subtask result detected. Retry missing asset type(s): ${retryTypes || 'unknown'}.`, 'warning');
                    }

                    return {
                        checkedSceneCount: importedSceneRows.length,
                        missingSceneCount: 0,
                        missingItemCount: createdLen + matchedLen + failedSubtaskItems.length,
                        supplementReport: {
                            createdItems,
                            skippedItems,
                            failedItems: failedSubtaskItems,
                        },
                        importedSubjectCounts: mergedCounts,
                        subtaskReports,
                    };
                }
            }

        } catch (error) {
            console.error("Stage 3 asset design step failed:", error);
            if (isTaskCanceledError(error) || analysisStopRequestedRef.current) {
                onLog?.('Stage 3 asset design stopped by user.', 'warning');
                throw createAnalysisCanceledError();
            }
            onLog?.(`Stage 3 asset design failed: ${error.message}`);
            throw error;
        } finally {
            phase2GenerationInFlightRef.current = false;
            if (options?.isRetryPhase2) {
                setIsRetryingPhase2(false);
            }
            if (activeEpisode?.id) {
                clearAnalysisTaskMarker(activeEpisode.id);
            }
        }

        return emptyReport;
    }, [
        projectId, llmRawResultContent, llmResultContent, activeEpisode, t, onLog,
        fetchPrompt, analyzeScene, awaitAnalyzeSceneWithRecovery, adaptationText,
        analysisAttentionNotes, selectedReuseSubjectAssets, extractAnalysisTextFromResult, doImportText,
        isSuperuser, setSystemPrompt, setUserPrompt, setShowAnalysisModal, functionApiConfigs,
        project, extractPureSubjectIndexText, filterSubjectIndexTextForAssetTask,
        throwIfAnalysisStopped, registerActiveAnalysisTask, isTaskCanceledError, createAnalysisCanceledError,
        buildStage2_2UserInputFromStage1, clearAnalysisTaskMarker, finalizeAnalysisFlowHistoryForPhase,
        saveAnalysisTaskMarker, updateEpisodeAnalysisRun
    ]);

    

    

    const resumeAnalysisFromTaskMarker = useCallback(async (marker) => {
        if (!activeEpisode?.id || !marker?.taskId) return;
        if (getEpisodeAnalysisRun(activeEpisode.id)?.promise) return;
        if (analysisResumeInFlightRef.current || analysisRunInFlightRef.current) return;
        if (isRetryingPhase2 || phase2GenerationInFlightRef.current || analysisFallbackRetryRef.current.running) return;
        if (isAsyncTaskPollInFlight(marker.taskId)) {
            if (onLog) onLog?.('[Analysis Resume] Task poll already active; skipping duplicate marker resume.', 'info');
            return;
        }

        if (Number(marker?.phase) === 2) {
            if (clearStalePhase2AssetMarkerIfDesignExists(activeEpisode.id, 'resume-guard')) return;
        }
        analysisResumeInFlightRef.current = true;

        const markerStartedAt = Number(marker?.startedAt || 0);
        const startedAt = (Number.isFinite(markerStartedAt) && markerStartedAt > 0) ? markerStartedAt : Date.now();
        const elapsedMs = Math.max(0, Date.now() - startedAt);
        beginAnalysisTimer(startedAt);
        const remainingTimeoutMs = Math.max(0, ANALYSIS_TASK_MAX_AGE_MS - elapsedMs);
        const markerTaskIds = Array.from(new Set([
            String(marker?.taskId || '').trim(),
            ...(Array.isArray(marker?.taskIds) ? marker.taskIds.map((item) => String(item || '').trim()) : []),
        ].filter(Boolean)));
        markerTaskIds.forEach((taskId) => activeAnalysisTaskIdsRef.current.add(taskId));
        if (marker?.phase === 2) {
            setIsAnalyzing(false);
            setIsRetryingPhase2(true);
            setActiveAnalysisTaskId(markerTaskIds[markerTaskIds.length - 1] || String(marker?.taskId || '').trim());
            setAnalysisUiReport({
                status: 'running',
                startedAt,
                durationMs: elapsedMs,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: '',
                error: '',
            });
            setAnalysisFlowStatus({
                phase: 'assets_gen',
                message: t("✨ 发现有个未完成的第三阶段任务，正在继续执行资产设计...", "Resuming Stage 3 asset design..."),
            });
            try {
                const result = await awaitAnalyzeSceneWithRecovery(
                    () => waitForAsyncTask(marker.taskId, { interval: 2500, timeout: remainingTimeoutMs }),
                    { startedAt, baselineText: activeEpisode?.ai_entity_design_result || '', resultField: 'ai_entity_design_result' }
                );
                const analyzedText = extractAnalysisTextFromResult(result);
                const backendSubjectsJson = result?.subjects_json;
                const canonicalAssetDesignText = String(
                    buildCanonicalAssetDesignJsonText(backendSubjectsJson) || analyzedText || ''
                ).trim();
                setLlmAssetRawResultContent(canonicalAssetDesignText);

                const savedByBackend = !!(result?.meta?.saved_to_episode);
                try {
                    if (true || !savedByBackend || (canonicalAssetDesignText && canonicalAssetDesignText !== String(analyzedText || '').trim())) {
                        await persistLlmResultContent(canonicalAssetDesignText || '', 'ai_entity_design_result');
                    } else {
                        // await refreshAnalysisFromDB({ resultField: 'ai_entity_design_result' }); // TEMPORARY DISABLE
                    }
                } catch (persistErr) {
                    onLog?.(`[Stage 3 Asset Design] Recovery save warning: ${persistErr?.message || persistErr}`, 'warning');
                }

                if (canonicalAssetDesignText) {
                    const hasValidSubjectJsonBlock = /"characters"\s*:\s*\[|"props"\s*:\s*\[|"environments"\s*:\s*\[|"posters"\s*:\s*\[|"covers"\s*:\s*\[/i.test(canonicalAssetDesignText);
                    if (!hasValidSubjectJsonBlock && !backendSubjectsJson) {
                        onLog?.(`[Stage 3 Asset Design] Warning: AI did not return a valid asset-design JSON block during recovery.`);
                    } else {
                        const sceneImportReport = await importSubjectsJsonWithDedupe(canonicalAssetDesignText, {
                            reason: 'phase2-entity-design',
                            subjectsJson: backendSubjectsJson || null,
                            importOptions: {
                                onLog,
                                projectId,
                                episodeId: activeEpisode?.id,
                                subjectsJson: backendSubjectsJson || null,
                                suppressAlerts: true,
                            },
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
                    setAnalysisFlowStatus({ phase: 'warning', message: t('恢复第三阶段资产设计失败：未返回有效内容', 'Failed to resume Stage 3 asset design: returned no content') });
                }
                clearAnalysisTaskMarker(activeEpisode.id);
            } catch (e) {
                console.error("Stage 3 recovery error:", e);
                const friendlyRecoveryError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
                const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
                const retainMarker = shouldRetainAnalysisTaskMarker({
                    canceled,
                    error: e,
                    mounted: scriptEditorMountedRef.current,
                });
                if (scriptEditorMountedRef.current) {
                    setAnalysisFlowStatus({ phase: 'failed', message: t(`恢复第三阶段资产设计任务失败：${friendlyRecoveryError}`, `Failed to resume Stage 3 asset design task: ${friendlyRecoveryError}`) });
                    setAnalysisUiReport(prev => ({ ...prev, status: 'error', error: friendlyRecoveryError }));
                }
                if (!retainMarker) {
                    clearAnalysisTaskMarker(activeEpisode.id);
                }
            } finally {
                analysisResumeInFlightRef.current = false;
                setIsRetryingPhase2(false);
                setActiveAnalysisTaskId('');
            }
            return;
        }

        if (String(marker?.phase || '').trim() === 'scene_beats') {
            setIsAnalyzing(true);
            setActiveAnalysisTaskId(markerTaskIds[markerTaskIds.length - 1] || String(marker?.taskId || '').trim());
            analysisStopRequestedRef.current = false;
            setAnalysisUiReport({
                status: 'running',
                startedAt,
                durationMs: elapsedMs,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: '',
                error: '',
            });
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('🔄 发现未完成的场景编排任务，正在继续接收 Stage 2.2 输出...', 'Detected an unfinished scene beats task, resuming Stage 2.2 output...'),
            });
            try {
                const result = await awaitAnalyzeSceneWithRecovery(
                    () => waitForAsyncTask(marker.taskId, { interval: 2500, timeout: remainingTimeoutMs }),
                    {
                        startedAt,
                        baselineText: String(activeEpisode?.ai_scene_analysis_scene_markdown || activeEpisode?.ai_scene_analysis_result || '').trim(),
                        resultField: 'ai_scene_analysis_scene_markdown',
                        expectedResultKind: 'scene_beats',
                    }
                );
                const rawText = extractAnalysisTextFromResult(result) || '';
                const stage2_2Check = validateStage2_2BeatsOutput(rawText, 'Stage 2.2 recovery');
                if (!stage2_2Check.ok) {
                    throw new Error(stage2_2Check.reason || 'Stage 2.2 recovery returned invalid scene table.');
                }
                const validatedBeatsText = stage2_2Check.normalizedText;
                const sceneBeatsRuntimeMeta = result?.meta ? extractAnalysisRuntimeMeta(result.meta) : null;
                setAnalysisRuntimeMeta(sceneBeatsRuntimeMeta);
                setLlmRawResultContent(validatedBeatsText);
                setLlmResultContent(validatedBeatsText);
                lastLoadedAnalysisRef.current = validatedBeatsText;

                const stage2_1Text = String(
                    getStageOutputContent('stage2', 'subject_index')
                    || activeEpisode?.ai_scene_analysis_subject_index
                    || ''
                ).trim();
                await persistSceneMarkdownBundle(validatedBeatsText, {
                    source: 'resume-stage2_2-scene-beats',
                    stage1RawText: buildStage1RestartSourceText(),
                    stage2RawText: [stage2_1Text, validatedBeatsText].filter(Boolean).join('\n\n'),
                    stage2_1Text: stage2_1Text || undefined,
                });

                const sceneBeatsImportReport = await runAutoImportAndSwitchToScenes(validatedBeatsText, {
                    switchToScenes: false,
                    importOptions: {
                        autoSupplementSceneSubjects: false,
                        suppressAlerts: true,
                        subjectsJson: null,
                    },
                });

                setAnalysisUiReport(buildCompletedAnalysisUiReport({
                    status: 'completed',
                    startedAt,
                    durationMs: Date.now() - startedAt,
                    phaseTimings: null,
                    importReport: sceneBeatsImportReport,
                    runtimeMeta: sceneBeatsRuntimeMeta,
                    warning: '',
                    error: '',
                }));
                setAnalysisFlowStatus({
                    phase: 'completed',
                    message: t('场景编排任务已恢复并导入完成。', 'Scene beats task resumed and imported.'),
                });
                clearAnalysisTaskMarker(activeEpisode.id);
            } catch (e) {
                console.error('Stage 2.2 recovery error:', e);
                const friendlyRecoveryError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
                const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
                const retainMarker = shouldRetainAnalysisTaskMarker({
                    canceled,
                    error: e,
                    mounted: scriptEditorMountedRef.current,
                });
                if (scriptEditorMountedRef.current) {
                    setAnalysisFlowStatus({
                        phase: 'failed',
                        message: t(`恢复场景编排任务失败：${friendlyRecoveryError}`, `Failed to resume scene beats task: ${friendlyRecoveryError}`),
                    });
                    setAnalysisUiReport(prev => ({ ...(prev || {}), status: 'error', error: friendlyRecoveryError }));
                }
                if (!retainMarker) {
                    clearAnalysisTaskMarker(activeEpisode.id);
                }
            } finally {
                analysisResumeInFlightRef.current = false;
                setIsAnalyzing(false);
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
        setActiveAnalysisTaskId(markerTaskIds[markerTaskIds.length - 1] || String(marker?.taskId || '').trim());
        analysisStopRequestedRef.current = false;
        setAnalysisFlowStatus({
            phase: 'script_opt',
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
            const savedByBackend = !!(result?.meta?.saved_to_episode);
            let rawResultPersistedEarly = false;

            if (true || !savedByBackend) {
                phaseMarks.persistStartedAt = Date.now();
                try {
                    await persistLlmResultContent(analyzedText || '', 'ai_scene_analysis_result', { source: 'resume-analysis-immediate' });
                    rawResultPersistedEarly = true;
                } catch (persistErr) {
                    onLog?.(`Resume immediate raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                } finally {
                    phaseMarks.persistFinishedAt = Date.now();
                }
            }

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
                    const sceneRegenStarted = await triggerSceneArrangementRegenerationTask(analyzedText || '', {
                        reason: importWarningMessage,
                        source: 'resume-analysis-empty-import',
                    });
                    if (sceneRegenStarted) {
                        importWarningMessage = `${importWarningMessage}；${t('已自动发起单独场景编排任务。', 'Started a separate scene arrangement task automatically.')}`;
                    }
                }
            } catch (importErr) {
                importWarningMessage = t(
                    `自动导入失败：${importErr?.message || importErr}`,
                    `Auto-import failed: ${importErr?.message || importErr}`
                );
                const sceneRegenStarted = await triggerSceneArrangementRegenerationTask(analyzedText || '', {
                    reason: importWarningMessage,
                    source: 'resume-analysis-import-error',
                });
                if (sceneRegenStarted) {
                    importWarningMessage = `${importWarningMessage}；${t('已自动发起单独场景编排任务。', 'Started a separate scene arrangement task automatically.')}`;
                }
                setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            maybeAlertIncompleteSubjectsImport(result, analyzedText || '');

            const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, analyzedText);
            const mergedResumeScenePostReport = syncScenePostImportCheckedCount(importReport, postImportSceneSubjectReport);
            if (importReport && typeof importReport === 'object') {
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: mergedResumeScenePostReport,
                };
                if (mergedResumeScenePostReport?.dbRunInsertedCounts) {
                    importReport.dbRunInsertedCounts = mergedResumeScenePostReport.dbRunInsertedCounts;
                }
                if (mergedResumeScenePostReport?.dbPersistedCounts) {
                    importReport.dbPersistedCounts = mergedResumeScenePostReport.dbPersistedCounts;
                }
            }

            try {
                if (true || !savedByBackend && !rawResultPersistedEarly) {
                    phaseMarks.persistStartedAt = Date.now();
                    await persistLlmResultContent(analyzedText || '', 'ai_scene_analysis_result', { source: 'resume-analysis' });
                } else {
                    if (savedByBackend) {
                        phaseMarks.persistStartedAt = phaseMarks.persistStartedAt || Date.now();
                    }
                    // await refreshAnalysisFromDB(); // TEMPORARY DISABLE
                }
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }

            let resumeReviewIssues = [];
            try {
                const firstPassReport = buildSubjectConsistencyReport(analyzedText || '');
                setSubjectConsistencyReport(firstPassReport);
                const { reviewIssues } = await publishAnalysisReviewFindings({
                    subjectReport: firstPassReport,
                });
                resumeReviewIssues = reviewIssues;
            } catch (_) {
                // non-blocking
            }

            if (analysisRunInFlightRef.current || analysisStopRequestedRef.current) {
                if (onLog) onLog('Resume was superseded by a new analysis run, stopping UI update.', 'warning');
                return;
            }

            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            setAnalysisUiReport(buildCompletedAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                storyboardAutoStarted: aiShotsBatchStarted,
                warning: [importWarningMessage, resumeReviewIssues.length > 0 ? buildAnalysisReviewWarningMessage(resumeReviewIssues) : '']
                    .map((item) => String(item || '').trim())
                    .filter(Boolean)
                    .join('\n\n'),
                reviewIssues: resumeReviewIssues,
                error: '',
            }));

            const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
            const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
            const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
            const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
            
            const appendStoryboardNotice = (baseZh, baseEn) => {
                if (!aiShotsBatchStarted) return t(baseZh, baseEn);
                return t(`${baseZh} 分镜任务已在后台启动。`, `${baseEn} Storyboard generation started in background.`);
            };

            setAnalysisFlowStatus({
                phase: 'completed',
                message: postImportMissingItems > 0
                    ? (
                        postImportSupplementFailed > 0
                            ? appendStoryboardNotice(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`)
                            : appendStoryboardNotice(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`)
                    )
                    : appendStoryboardNotice('✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.'),
            });

            clearAnalysisTaskMarker(activeEpisode.id);
        } catch (e) {
            const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            const retainMarker = shouldRetainAnalysisTaskMarker({
                canceled,
                error: e,
                mounted: scriptEditorMountedRef.current,
            });
            if (scriptEditorMountedRef.current) {
                setAnalysisFlowStatus(
                    canceled
                        ? { phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') }
                        : retainMarker
                            ? { phase: 'warning', message: t('分析连接中断，任务仍在后台运行。返回本页后会自动恢复进度。', 'Analysis connection interrupted. The task is still running; return here to resume progress.') }
                            : { phase: 'failed', message: t(`恢复分析任务失败：${e?.message || e}`, `Failed to resume analysis task: ${e?.message || e}`) }
                );
                setAnalysisUiReport({
                    status: canceled ? 'warning' : retainMarker ? 'warning' : 'failed',
                    startedAt,
                    durationMs: Date.now() - startedAt,
                    phaseTimings,
                    importReport,
                    runtimeMeta,
                    warning: canceled
                        ? t('分析任务已由用户停止。', 'Analysis task was stopped by user.')
                        : retainMarker
                            ? t('分析连接中断，返回本页后会自动恢复进度。', 'Connection interrupted. Return here to resume progress.')
                            : '',
                    error: canceled || retainMarker ? '' : (e?.message || String(e || '')),
                });
            }
            if (!retainMarker) {
                clearAnalysisTaskMarker(activeEpisode.id);
            }
        } finally {
            analysisResumeInFlightRef.current = false;
            if (!analysisRunInFlightRef.current && scriptEditorMountedRef.current) {
                setIsAnalyzing(false);
                setActiveAnalysisTaskId('');
                analysisStopRequestedRef.current = false;
            }
        }
    }, [
        activeEpisode?.id,
        ANALYSIS_TASK_MAX_AGE_MS,
        beginAnalysisTimer,
        buildSubjectConsistencyReport,
        clearAnalysisTaskMarker,
        clearStalePhase2AssetMarkerIfDesignExists,
        collectAnalysisWarnings,
        computeAnalysisPhaseTimings,
        extractAnalysisRuntimeMeta,
        isTaskCanceledError,
        shouldRetainAnalysisTaskMarker,
        normalizeLlmMarkdownTable,
        persistLlmResultContent,
        persistSceneMarkdownBundle,
        refreshAnalysisFromDB,
        runAutoImportAndSwitchToScenes,
        showAnalysisWarningStatus,
        t,
            doImportText,
        setLlmAssetRawResultContent,
        setIsRetryingPhase2,
        isRetryingPhase2,
        projectId,
        onLog,
]);

    useEffect(() => {
        latestIsAnalyzingRef.current = Boolean(isAnalyzing);
        latestActiveEpisodeIdRef.current = activeEpisode?.id || null;
    }, [isAnalyzing, activeEpisode?.id]);

    const resetBootstrapAnalysisUiIfIdle = useCallback(() => {
        const episodeId = activeEpisode?.id;
        if (!episodeId) return;
        const marker = loadAnalysisTaskMarker(episodeId);
        const stillLive = isEpisodeAnalysisTaskLive(episodeId, {
            loadAnalysisTaskMarker,
            analysisResumeInFlight: analysisResumeInFlightRef.current,
            analysisRunInFlight: analysisRunInFlightRef.current,
            phase2GenerationInFlight: phase2GenerationInFlightRef.current,
        });
        if (marker?.taskId || stillLive) return;
        clearAnalysisProgressUiState(episodeId);
    }, [activeEpisode?.id, clearAnalysisProgressUiState, loadAnalysisTaskMarker]);

    const reattachToExistingAnalysisRun = useCallback(async (entry) => {
        if (!activeEpisode?.id || !entry?.promise || analysisResumeInFlightRef.current) return false;
        analysisResumeInFlightRef.current = true;

        const startedAt = Number(entry.startedAt || Date.now());
        const elapsedMs = Math.max(0, Date.now() - startedAt);
        beginAnalysisTimer(startedAt);
        setIsAnalyzing(true);
        if (entry.taskId) {
            setActiveAnalysisTaskId(String(entry.taskId));
        }
        const resolvedPhase = entry.phase === 2 ? 'assets_gen' : (entry.phase === 'scene_beats' ? 'scene_beats' : 'script_opt');
        setAnalysisFlowStatus((prev) => {
            const prevPhase = String(prev?.phase || '').trim().toLowerCase();
            if (prevPhase && prevPhase !== 'idle') return prev;
            return {
                phase: resolvedPhase,
                message: t('正在重新连接分析任务...', 'Reconnecting to in-progress analysis task...'),
            };
        });
        setAnalysisUiReport((prev) => {
            if (prev?.status === 'running') {
                return { ...prev, durationMs: elapsedMs };
            }
            return {
                status: 'running',
                startedAt,
                durationMs: elapsedMs,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: '',
                error: '',
            };
        });

        try {
            await entry.promise;
            await refreshAnalysisFromDB();
            await refreshAnalysisFromDB({ resultField: 'ai_entity_design_result' });
            const marker = loadAnalysisTaskMarker(activeEpisode.id);
            if (!marker?.taskId) {
                setAnalysisFlowStatus((prev) => (prev?.phase === 'completed' ? prev : {
                    phase: 'completed',
                    message: t('分析任务已完成。', 'Analysis task completed.'),
                }));
                setAnalysisUiReport((prev) => ({
                    ...(prev || {}),
                    status: 'completed',
                    startedAt,
                    durationMs: Date.now() - startedAt,
                    error: '',
                }));
            }
        } catch (e) {
            const canceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            const retainMarker = shouldRetainAnalysisTaskMarker({
                canceled,
                error: e,
                mounted: true,
            });
            const friendlyError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
            if (canceled) {
                setAnalysisFlowStatus({ phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') });
            } else if (retainMarker) {
                setAnalysisFlowStatus({
                    phase: 'warning',
                    message: t('分析连接中断，任务仍在后台运行。返回本页后会自动恢复进度。', 'Analysis connection interrupted. The task is still running; return here to resume progress.'),
                });
            } else {
                setAnalysisFlowStatus({
                    phase: 'failed',
                    message: t(`分析失败：${friendlyError}`, `Analysis failed: ${friendlyError}`),
                });
                setAnalysisUiReport((prev) => ({
                    ...(prev || {}),
                    status: 'failed',
                    error: friendlyError,
                }));
            }
        } finally {
            analysisResumeInFlightRef.current = false;
            if (!getEpisodeAnalysisRun(activeEpisode.id)?.promise) {
                setIsAnalyzing(false);
                setActiveAnalysisTaskId('');
            }
        }
        return true;
    }, [
        activeEpisode?.id,
        beginAnalysisTimer,
        isTaskCanceledError,
        loadAnalysisTaskMarker,
        localizeAnalysisFailureMessage,
        refreshAnalysisFromDB,
        shouldRetainAnalysisTaskMarker,
        t,
    ]);

    const tryResumePendingAnalysis = useCallback(async () => {
        if (!activeEpisode?.id) return;
        const episodeId = activeEpisode.id;
        if (analysisResumeCoordinatorRef.current.running && analysisResumeCoordinatorRef.current.episodeId === episodeId) return;
        if (analysisResumeInFlightRef.current || phase2GenerationInFlightRef.current || isRetryingPhase2) return;
        if (analysisFallbackRetryRef.current.running) return;

        const pendingMarker = loadAnalysisTaskMarker(episodeId);
        const activeRun = getEpisodeAnalysisRun(episodeId);
        const hasPendingWork = Boolean(pendingMarker?.taskId || activeRun?.promise);
        if (!hasPendingWork && (isAnalyzing || isRetryingPhase2)) return;

        analysisResumeCoordinatorRef.current = { running: true, episodeId };
        try {
            await clearStaleAnalysisMarkerIfEpisodeComplete(episodeId, activeEpisode, 'resume-precheck');
            clearStalePhase2AssetMarkerIfDesignExists(episodeId, 'resume-precheck');

            let refreshedRun = getEpisodeAnalysisRun(episodeId);
            if (refreshedRun?.promise) {
                const runTaskId = String(refreshedRun.taskId || loadAnalysisTaskMarker(episodeId)?.taskId || '').trim();
                const runLive = analysisRunInFlightRef.current
                    || analysisResumeInFlightRef.current
                    || (runTaskId && isAsyncTaskPollInFlight(runTaskId));
                if (!runLive) {
                    releaseEpisodeAnalysisRun(episodeId, refreshedRun.promise);
                    refreshedRun = null;
                }
            }
            if (refreshedRun?.promise) {
                if (analysisRunInFlightRef.current) {
                    bootstrapPendingAnalysisUi();
                    return;
                }
                if (detachedAnalysisRunEpisodeRef.current !== episodeId) {
                    return;
                }
                detachedAnalysisRunEpisodeRef.current = null;
                await reattachToExistingAnalysisRun(refreshedRun);
                return;
            }

            const marker = loadAnalysisTaskMarker(episodeId);
            if (!marker?.taskId) {
                resetBootstrapAnalysisUiIfIdle();
                return;
            }
            if (Number(marker?.phase) === 2 && clearStalePhase2AssetMarkerIfDesignExists(episodeId, 'pending-resume-guard')) {
                resetBootstrapAnalysisUiIfIdle();
                return;
            }

            const terminalStatus = await peekAsyncTaskTerminalStatus(marker.taskId);
            if (terminalStatus) {
                clearAnalysisTaskMarker(episodeId);
                releaseEpisodeAnalysisRun(episodeId);
                detachedAnalysisRunEpisodeRef.current = null;
                resetBootstrapAnalysisUiIfIdle();
                if (onLog) {
                    const reason = terminalStatus === 'not_found'
                        ? 'backend task no longer exists (server may have restarted)'
                        : `backend task already ${terminalStatus}`;
                    onLog?.(`[Analysis Resume] Cleared stale marker; ${reason}.`, 'info');
                }
                return;
            }

            if (isAsyncTaskPollInFlight(marker.taskId)) {
                bootstrapPendingAnalysisUi();
                return;
            }

            bootstrapPendingAnalysisUi();
            await resumeAnalysisFromTaskMarker(marker);
        } finally {
            analysisResumeCoordinatorRef.current = { running: false, episodeId: null };
        }
    }, [
        activeEpisode,
        activeEpisode?.id,
        bootstrapPendingAnalysisUi,
        clearAnalysisTaskMarker,
        clearStaleAnalysisMarkerIfEpisodeComplete,
        clearStalePhase2AssetMarkerIfDesignExists,
        isAnalyzing,
        isRetryingPhase2,
        loadAnalysisTaskMarker,
        onLog,
        reattachToExistingAnalysisRun,
        resetBootstrapAnalysisUiIfIdle,
        resumeAnalysisFromTaskMarker,
    ]);

    useEffect(() => {
        const episodeId = Number(activeEpisode?.id || 0);
        if (!episodeId) return;

        scriptEditorMountedRef.current = true;
        mountResumeReadyRef.current = false;
        restoreAnalysisProgressFromSession(episodeId);
        bootstrapPendingAnalysisUi();
        let cancelled = false;
        (async () => {
            ensureAnalysisFallbackState(episodeId);
            await clearStaleAnalysisMarkerIfEpisodeComplete(episodeId, activeEpisode, 'mount-precheck');
            if (cancelled) return;
            await tryResumePendingAnalysis();
            if (cancelled) return;
            if (!isEpisodeAnalysisTaskLive(episodeId, {
                loadAnalysisTaskMarker,
                isAnalyzing: latestIsAnalyzingRef.current,
                analysisRunInFlight: analysisRunInFlightRef.current,
                analysisResumeInFlight: analysisResumeInFlightRef.current,
                phase2GenerationInFlight: phase2GenerationInFlightRef.current,
            })) {
                resetBootstrapAnalysisUiIfIdle();
            }
            if (!cancelled) mountResumeReadyRef.current = true;
        })();

        return () => {
            // Keep backend analysis running when this view unmounts (tab/page switch).
            // Explicit cancellation should only happen via the "stop task" action.
            scriptEditorMountedRef.current = false;
            mountResumeReadyRef.current = false;
            cancelled = true;
            const leavingEpisodeId = Number(latestActiveEpisodeIdRef.current || episodeId);
            if (!leavingEpisodeId) return;

            if (getEpisodeAnalysisRun(leavingEpisodeId)?.promise) {
                detachedAnalysisRunEpisodeRef.current = leavingEpisodeId;
            }
            persistAnalysisSessionSnapshot(leavingEpisodeId);
            const stillRunning = isEpisodeAnalysisTaskLive(leavingEpisodeId, {
                loadAnalysisTaskMarker,
                isAnalyzing: latestIsAnalyzingRef.current,
                analysisRunInFlight: analysisRunInFlightRef.current,
                analysisResumeInFlight: analysisResumeInFlightRef.current,
                phase2GenerationInFlight: phase2GenerationInFlightRef.current,
            });
            if (stillRunning && onLog) {
                const now = Date.now();
                if (now - lastScriptLeaveNoticeAtRef.current > 3000) {
                    lastScriptLeaveNoticeAtRef.current = now;
                    onLog?.(
                        '已离开剧本页，分析任务仍在后台运行。返回剧本页后会自动恢复进度；全局日志面板仍可查看后续输出。',
                        'info'
                    );
                }
            }
        };
        // Intentionally keyed by episode id only — avoid re-running cleanup when activeEpisode object reference changes during analysis.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeEpisode?.id]);

    useEffect(() => {
        const refreshPendingAnalysis = () => {
            if (!mountResumeReadyRef.current) return;
            if (document.visibilityState !== 'visible') return;
            const now = Date.now();
            if (now - lastTryResumePendingAnalysisAtRef.current < 5000) return;
            lastTryResumePendingAnalysisAtRef.current = now;
            tryResumePendingAnalysis();
        };
        document.addEventListener('visibilitychange', refreshPendingAnalysis);
        window.addEventListener('focus', refreshPendingAnalysis);
        return () => {
            document.removeEventListener('visibilitychange', refreshPendingAnalysis);
            window.removeEventListener('focus', refreshPendingAnalysis);
        };
    }, [tryResumePendingAnalysis]);

    useEffect(() => {
        // On episode change/remount, prefer parent-provided field; fallback to DB refresh.
        const initial = activeEpisode?.ai_scene_analysis_result || '';
        const normalizedInitial = normalizeLlmMarkdownTable(initial);
        setLlmRawResultContent((prev) => (prev === initial ? prev : initial));
        setLlmResultContent((prev) => (prev === normalizedInitial ? prev : normalizedInitial));
        const nextConsistencyText = String(activeEpisode?.episode_info?.subject_check_result || '');
        setSubjectConsistencyResultText((prev) => (prev === nextConsistencyText ? prev : nextConsistencyText));
        setAnalysisRuntimeMeta((prev) => (prev === null ? prev : null));
        lastLoadedAnalysisRef.current = initial;
        lastEpisodeSegmentsScriptKeyRef.current = '';
        lastEpisodeSyncScriptKeyRef.current = '';
        lastEpisodeReuseSubjectIdsKeyRef.current = '';
        if (!initial) {
            refreshAnalysisFromDBRef.current();
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

    const getCurrentScriptContent = () => {
        let fullContent = rawContent;
        if (!isRawMode && segments.length > 0) {
            const header = `| Paragraph ID | Title | Content (Revised) | Content (Original) | Narrative Function | Analysis & Adaptation Notes |\n|---|---|---|---|---|---|`;
            const rows = segments.map(seg => {
                const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
                return `| ${seg.id} | ${clean(seg.title)} | ${clean(seg.content)} | ${clean(seg.original)} | ${clean(seg.narrative_role)} | ${clean(seg.analysis)} |`;
            }).join('\n');
            fullContent = header + '\n' + rows;
        }
        return fullContent;
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        if (onLog) onLog("Saving Script...");

        let fullContent = getCurrentScriptContent();

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

    async function triggerSceneArrangementRegenerationTask(analysisText, options = {}) {
        const stableEpisodeId = activeEpisode?.id;
        if (!stableEpisodeId) return false;

        const existingDbScenes = await fetchScenes(stableEpisodeId).catch(() => []);
        if (Array.isArray(existingDbScenes) && existingDbScenes.length > 0) {
            onLog?.(
                `Scene arrangement regeneration skipped: episode already has ${existingDbScenes.length} imported scene(s) in DB.`,
                'info'
            );
            return false;
        }

        const isAutomatic = options?.manual !== true;
        if (isAutomatic && !canAttemptAnalysisFallback(stableEpisodeId, 'scene_regen')) {
            onLog?.(
                `[Scene Regen] skipped: auto fallback retry limit reached (max ${MAX_ANALYSIS_FALLBACK_ATTEMPTS}).`,
                'warning'
            );
            return false;
        }

        const sourceText = String(analysisText || '').trim();
        const sceneCheck = validateAutoSceneTableImport(sourceText);
        const normalizedSceneTable = String(normalizeLlmMarkdownTable(sourceText || '') || '').trim();
        const hasSceneArrangementPayload = Boolean(
            (sceneCheck?.ok && String(sceneCheck?.tableText || '').trim())
            || (normalizedSceneTable && /(?:Scene\s*ID|场景\s*ID|场景ID|Scene\s*No\.?|场次|场景名|场景名称)/i.test(normalizedSceneTable))
        );

        if (!hasSceneArrangementPayload) {
            onLog?.(`Scene arrangement regeneration skipped: import issue is not tied to a parseable scene table. source=${options?.source || 'unknown'}`, 'info');
            return false;
        }

        if (sceneGenStartInFlightRef.current || sceneGenGenerating || isStoppingSceneGen) {
            onLog?.('Scene arrangement regeneration skipped: a scene generation task is already starting or stopping.', 'warning');
            return false;
        }

        const latest = await getEpisodeScenesGenerationStatus(stableEpisodeId).catch(() => null);
        if (latest?.running) {
            onLog?.('Scene arrangement regeneration skipped: a scene generation task is already running.', 'warning');
            return false;
        }

        const reasonText = String(options?.reason || 'Scene arrangement import failed').trim();
        const sourceLabel = String(options?.source || 'script-analysis-import').trim();
        const tableText = String(sceneCheck?.tableText || normalizedSceneTable || sourceText).trim();
        const cappedTableText = tableText.length > 12000 ? `${tableText.slice(0, 12000)}\n...[truncated]` : tableText;
        const scriptContext = String(adaptationText || activeEpisode?.ai_scene_analysis_adaptation || activeEpisode?.script_content || rawContent || '').trim();
        const cappedScriptContext = scriptContext.length > 12000 ? `${scriptContext.slice(0, 12000)}\n...[truncated]` : scriptContext;
        const extraNotes = [
            '【自动恢复任务】剧本分析检测到场景编排导入错误，请单独重新生成并入库场景编排。',
            `触发来源：${sourceLabel}`,
            `导入错误：${reasonText}`,
            '要求：基于下方场景编排/剧本分析结果重新生成完整场景列表；保留原剧情顺序、角色出场关系、场景入口/出口状态；生成后替换当前分集旧场景。',
            cappedScriptContext ? `【原始/优化后剧本】\n\n${cappedScriptContext}` : '',
            '【原场景编排/分析结果】',
            cappedTableText,
        ].filter(Boolean).join('\n\n');

        sceneGenStartInFlightRef.current = true;
        setSceneGenGenerating(true);
        setSceneGenStatus((prev) => ({
            ...(prev && typeof prev === 'object' ? prev : {}),
            running: true,
            status: 'starting',
            message: t('检测到场景编排导入异常，正在启动单独重排任务...', 'Scene arrangement import failed. Starting a separate regeneration task...'),
        }));

        try {
            onLog?.(`Scene arrangement import issue detected. Starting separate regeneration task. source=${sourceLabel}`, 'warning');
            if (isAutomatic) {
                recordAnalysisFallbackAttempt(stableEpisodeId, 'scene_regen');
            }
            await startEpisodeScenesGeneration(stableEpisodeId, {
                scene_count: null,
                extra_notes: extraNotes,
                replace_existing_scenes: true,
            });
            if (sceneGenStatusTimerRef.current) {
                clearInterval(sceneGenStatusTimerRef.current);
                sceneGenStatusTimerRef.current = null;
            }
            sceneGenStatusTimerRef.current = setInterval(pollSceneGenStatus, 3000);
            await pollSceneGenStatus();
            onLog?.('Scene arrangement regeneration task started automatically after import failure.', 'success');
            return true;
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || String(e);
            setSceneGenGenerating(false);
            setSceneGenStatus((prev) => ({
                ...(prev && typeof prev === 'object' ? prev : {}),
                running: false,
                status: 'failed',
                message: t('场景编排自动重排任务启动失败。', 'Failed to start the automatic scene arrangement regeneration task.'),
                error: String(detail || ''),
            }));
            onLog?.(`Scene arrangement regeneration task start failed: ${detail}`, 'error');
            return false;
        } finally {
            sceneGenStartInFlightRef.current = false;
        }
    }

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
        const actualContent = getCurrentScriptContent();
        if (!actualContent || actualContent.trim().length < 10) {
            alert("Script content is too short for analysis.");
            return;
        }
        if (isAnalyzing || analysisRunInFlightRef?.current || analysisResumeInFlightRef?.current) {
            onLog?.("Already analyzing, duplicate click prevented.");
            return;
        }

        await autoSaveScriptBeforeAnalysis();

        if (actualContent && actualContent.trim().length > 6000) {
            const ok = await confirmUiMessage(t(
                '检测到剧本内容超过6000字，考虑到大模型可能漏剧情，建议先进行分集处理。是否允许AI帮您自动切分集并保存？(选择“取消”则忽略并继续分析整段内容)',
                'Script length exceeds 6000 characters. Large models might miss plot details. Auto-split it into episodes? (Cancel to proceed analyzing as a whole)'
            ));
            if (ok) {
                if (onLog) onLog("开始调用剧本分隔提示词自动分集...");
                setAnalysisFlowStatus({ phase: 'script_opt', message: t('正在为您深度阅读并切分剧本分集，请耐心等待...', 'Deep reading and splitting script episodes, this may take a while...') });
                try {
                    const { splitEpisodeScript } = await import('../../../services/api');
                    await splitEpisodeScript(projectId, activeEpisode.id, { script_content: actualContent });
                    if (onLog) onLog("分集保存成功，即将刷新！");
                    setAnalysisFlowStatus({ phase: 'completed', message: t('剧本分集成功！即将自动刷新以加载新集数...', 'Script split successfully! Reloading to show new episodes...') });
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } catch (e) {
                    console.error("Script split failed", e);
                    setAnalysisFlowStatus({ phase: 'failed', message: t('剧本分集失败：', 'Split failed: ') + (e.message || e) });
                    alert(t("分集失败: ", "Split failed: ") + (e.message || e));
                }
                return;
            }
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

        if (activeEpisode?.id) {
            const existingScenes = await fetchScenes(activeEpisode.id).catch(() => []);
            const hasExistingStageOutputs = [
                activeEpisode?.ai_scene_analysis_result,
                activeEpisode?.ai_scene_analysis_adaptation,
                activeEpisode?.ai_scene_analysis_subject_index,
                activeEpisode?.ai_scene_analysis_scene_markdown,
                activeEpisode?.ai_entity_design_result,
                activeEpisode?.ai_stage_outputs,
                subjectIndexText,
                adaptationText,
                llmRawResultContent,
                llmAssetRawResultContent,
            ].some((value) => String(value || '').trim());
            const hasExistingScenes = existingScenes && existingScenes.length > 0;
            
            if (hasExistingScenes || hasExistingStageOutputs) {
                const ok = await confirmUiMessage(t(
                    '检测到已存在剧本分析各阶段结果或场景数据。重新分析将清空并覆盖原结果，是否继续重新生成？（选择“取消”则保留并使用原来的结果）',
                    'Existing stage analysis outputs or scenes detected. Regenerating will clear and overwrite previous results. Continue? (Choose Cancel to keep existing results)'
                ));
                if (!ok) {
                    return;
                }
            }
        }

        forceRegenerateRef.current = true;
        analysisProgressDismissedRef.current = false;
        setIsAnalyzing(true);
        beginAnalysisRestartUi(Date.now());

        const projectLanguage = getInfoValue(['language', 'project_language', 'lang']);
        
        if (!projectLanguage) {
            const ok = await confirmUiMessage(t(
                '检测到项目语言为空。建议先在“项目信息”里填写语言，以保证分析输出语言稳定。是否继续分析？',
                'Project language is empty. Set language in Project Info first for stable analysis output. Continue anyway?'
            ));
            if (!ok) {
                setIsAnalyzing(false);
                forceRegenerateRef.current = false;
                return;
            }
            if (onLog) onLog('Project language is empty. Analysis continues with warning.', 'warning');
        }

        const stage1Input = ensureStage1ProjectContextInjected(actualContent);

        try {
            const res = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md');
            executeAdvancedAnalysis(stage1Input, res.content, 0, true);
        } catch (e) {
            console.error("Failed to fetch system prompt", e);
            executeAnalysis(stage1Input, null, true);
        }
    };

    const autoSaveScriptBeforeAnalysis = async () => {
        if (!activeEpisode?.id || typeof onUpdateScript !== 'function') return;
        
        let latestScript = String(getCurrentScriptContent() || '');
        if (!latestScript.trim() && rawContent.trim()) {
            latestScript = rawContent;
        }

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

    async function clearPersistedStageAnalysisFields({ deferWorkspaceUiReset = false } = {}) {
        if (!activeEpisode?.id) return false;

        const stageFieldPayload = {
            ai_scene_analysis_result: '',
            ai_scene_analysis_adaptation: '',
            ai_scene_analysis_subject_index: '',
            ai_scene_analysis_scene_markdown: '',
            ai_entity_design_result: '',
            ai_stage_outputs: '',
            scene_content: '',
            shot_content: '',
        };

        if (typeof onUpdateEpisodeInfo === 'function') {
            await onUpdateEpisodeInfo(activeEpisode.id, stageFieldPayload);
        }

        latestAssetRawTextRef.current = '';
        latestAnalysisRawTextRef.current = '';
        latestStage1RawTextRef.current = '';
        latestStage2_1TextRef.current = '';
        lastPersistPayloadSignatureRef.current = {};

        if (!deferWorkspaceUiReset) {
            setLlmRawResultContent('');
            setLlmResultContent('');
            setLlmAssetRawResultContent('');
            setSubjectIndexText('');
            setAdaptationText('');
            setAnalysisRuntimeMeta(null);
            lastLoadedAnalysisRef.current = null;
        }

        return true;
    }

    function episodeHasPersistedStageAnalysisFields(episodeRow = activeEpisode) {
        if (!episodeRow) return false;
        return [
            episodeRow.ai_scene_analysis_result,
            episodeRow.ai_scene_analysis_adaptation,
            episodeRow.ai_scene_analysis_subject_index,
            episodeRow.ai_scene_analysis_scene_markdown,
            episodeRow.ai_entity_design_result,
            episodeRow.ai_stage_outputs,
        ].some((value) => String(value || '').trim());
    }

    function hasInMemoryStageAnalysisArtifacts() {
        return [
            llmRawResultContent,
            llmResultContent,
            llmAssetRawResultContent,
            subjectIndexText,
            adaptationText,
        ].some((value) => String(value || '').trim());
    }

    async function purgeEpisodeWorkspaceScenes(reason = 'analysis-restart') {
        if (!activeEpisode?.id) return { deleted_scenes: 0, removed_progress_units: 0 };
        try {
            const result = await purgeEpisodeScenes(activeEpisode.id, { clearProgress: true });
            const deletedScenes = Number(result?.deleted_scenes || 0);
            const removedProgress = Number(result?.removed_progress_units || 0);
            if (onLog) {
                onLog(
                    `[Scene Purge] source=${reason} deleted_scenes=${deletedScenes} removed_progress_units=${removedProgress}`,
                    deletedScenes > 0 || removedProgress > 0 ? 'info' : 'process'
                );
            }
            return result || { deleted_scenes: deletedScenes, removed_progress_units: removedProgress };
        } catch (purgeErr) {
            if (onLog) onLog(`[Scene Purge] failed source=${reason}: ${purgeErr?.message || purgeErr}`, 'warning');
            throw purgeErr;
        }
    }

    async function clearAnalysisOutputsForRestart({ preserveProgressUi = false, deferWorkspaceUiReset = false } = {}) {
        if (!activeEpisode?.id) return;

        try {
            if (onLog) onLog('AI Script Analysis restart: clearing existing outputs and scenes...', 'process');

            releaseEpisodeAnalysisRun(activeEpisode.id);
            clearAnalysisTaskMarker(activeEpisode.id);
            resetAnalysisFallbackRetryCounts(activeEpisode.id);
            lastAutoSubjectsImportRef.current = { signature: '', result: null };
            if (!preserveProgressUi) {
                clearAnalysisSessionProgressSnapshot(activeEpisode.id);
                analysisTimerStartedAtRef.current = 0;
            }

            if (projectId && activeEpisode?.id) {
                try {
                    await resetSceneOrchestrationProgress({
                        project_id: Number(projectId),
                        episode_id: Number(activeEpisode.id),
                        scene_ids: [],
                    });
                    if (onLog) onLog('AI Script Analysis restart: reset scene orchestration progress.', 'info');
                } catch (orchErr) {
                    if (onLog) onLog(`AI Script Analysis restart orchestration reset warning: ${orchErr?.message || orchErr}`, 'warning');
                }
            }

            await purgeEpisodeWorkspaceScenes('analysis-restart-clear');

            await clearPersistedStageAnalysisFields({ deferWorkspaceUiReset });

            latestStage1RawTextRef.current = '';
            latestStage2_1TextRef.current = '';
            latestAnalysisRawTextRef.current = '';
            latestAssetRawTextRef.current = '';
            lastPersistPayloadSignatureRef.current = {};

            if (typeof onRefreshEpisodes === 'function') {
                try {
                    await onRefreshEpisodes();
                } catch (refreshErr) {
                    if (onLog) onLog(`AI Script Analysis restart episode refresh warning: ${refreshErr?.message || refreshErr}`, 'warning');
                }
            }

            if (!preserveProgressUi) {
                setAnalysisUiReport(null);
                setAnalysisFlowStatus({ phase: 'idle', message: '' });
            }
        } catch (clearErr) {
            if (onLog) onLog(`AI Script Analysis restart clear warning: ${clearErr?.message || clearErr}`, 'warning');
            throw clearErr;
        }
    }

    async function ensureStageAnalysisFieldsClearedBeforeRun({ forceRegenerate = false, preserveProgressUi = true, deferWorkspaceUiReset = false } = {}) {
        if (!activeEpisode?.id) return false;

        const hasPersistedFields = episodeHasPersistedStageAnalysisFields(activeEpisode);
        const hasInMemoryArtifacts = hasInMemoryStageAnalysisArtifacts();
        if (!hasPersistedFields && !hasInMemoryArtifacts && !forceRegenerate) {
            return false;
        }

        if (onLog) {
            onLog('Detected existing stage analysis outputs. Clearing all previous analysis artifacts before starting a new run...', 'process');
        }
        await clearAnalysisOutputsForRestart({ preserveProgressUi, deferWorkspaceUiReset });
        return true;
    }

    const beginAnalysisRestartUi = useCallback((startedAt = Date.now()) => {
        analysisProgressDismissedRef.current = false;
        beginAnalysisTimer(startedAt);
        setAnalysisFlowStatusHistory([]);
        setAnalysisFlowStatus({
            phase: 'script_opt',
            message: t('正在准备重新分析，请稍候...', 'Preparing to rerun analysis...'),
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
    }, [beginAnalysisTimer, t]);

    const prepareSceneAnalysisResumeState = useCallback(async () => {
        const sceneAnalysisText = String(
            activeEpisode?.ai_scene_analysis_scene_markdown
            || activeEpisode?.ai_scene_analysis_result
            || ''
        ).trim();

        let preflightSceneSyncNotice = '';
        let scenePreflightResult = null;
        try {
            scenePreflightResult = await ensureSceneTableConsistencyBeforePhase2(sceneAnalysisText, {
                setRunningReport: false,
                preflightOnly: true,
            });
            if (scenePreflightResult?.repaired) {
                preflightSceneSyncNotice = t('分析开始前已检测到场景表不一致：旧场景已清理，并按 Markdown Scene 表重新导入。', 'Before analysis started, scene table mismatch was detected: old scenes were cleared and re-imported from markdown scene table.');
            }
        } catch (preflightErr) {
            if (onLog) onLog(`Scene markdown precheck failed (continue analysis): ${preflightErr?.message || preflightErr}`, 'warning');
        }

        let resolvedSubjectIndexText = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
        if (!resolvedSubjectIndexText && sceneAnalysisText) {
            const fallbackSections = extractAnalysisSections(sceneAnalysisText);
            const extractedFallbackIndex = String(fallbackSections?.subjectIndexText || '').trim();
            if (fallbackSections?.hasStructuredSubjectIndex && extractedFallbackIndex) {
                resolvedSubjectIndexText = extractedFallbackIndex;
            }
        }

        const subjectsJsonText = String(activeEpisode?.ai_entity_design_result || '').trim();
        const parsedSubjectsPayload = getAnalysisEntitiesPayloadFromJsonText(subjectsJsonText);
        const subjectsJsonCount = ['characters', 'props', 'environments'].reduce((sum, key) => {
            const items = Array.isArray(parsedSubjectsPayload?.[key]) ? parsedSubjectsPayload[key] : [];
            return sum + items.length;
        }, 0);
        const hasSubjectsJson = subjectsJsonCount > 0;
        const subjectJsonReport = hasSubjectsJson
            ? buildSubjectConsistencyReport([sceneAnalysisText, subjectsJsonText].filter(Boolean).join('\n\n'))
            : null;
        const hasCompleteSubjectsJson = Boolean(hasSubjectsJson && (!subjectJsonReport || subjectJsonReport.ok));
        const hasSceneMarkdown = Boolean(scenePreflightResult?.hasSceneMarkdown);
        const hasSubjectIndex = Boolean(resolvedSubjectIndexText);

        let decision = 'phase1';
        if (hasSceneMarkdown && hasSubjectIndex && hasCompleteSubjectsJson) {
            decision = 'completed';
        } else if (hasSubjectIndex) {
            decision = 'phase2';
        }

        let resumeNotice = '';
        if (decision === 'phase2') {
            resumeNotice = hasSubjectsJson
                ? t('检测到已有 subjects JSON 不完整，将直接重新执行资产设计阶段。', 'Detected incomplete existing subjects JSON. Stage 3 asset design will be rerun directly.')
                : t('未检测到完整的 subjects JSON，将直接重新执行资产设计阶段。', 'No complete subjects JSON was found. Stage 3 asset design will be rerun directly.');
        } else if (decision === 'completed') {
            resumeNotice = t('检测到完整的场景分析结果、资产清单与 subjects JSON，本次启动将直接复用现有结果。', 'Detected complete scene analysis results, asset index, and subjects JSON. This run will reuse the existing results directly.');
        }

        if (onLog) {
            onLog(
                `[Analysis Resume] decision=${decision} sceneMarkdown=${hasSceneMarkdown ? 1 : 0} subjectIndex=${hasSubjectIndex ? 1 : 0} subjectsJson=${hasSubjectsJson ? 1 : 0} completeSubjectsJson=${hasCompleteSubjectsJson ? 1 : 0}`,
                decision === 'phase1' ? 'info' : 'warning'
            );
        }

        return {
            decision,
            preflightSceneSyncNotice,
            resumeNotice,
            sceneAnalysisText,
            resolvedSubjectIndexText,
        };
    }, [
        activeEpisode?.ai_entity_design_result,
        activeEpisode?.ai_scene_analysis_result,
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.ai_scene_analysis_subject_index,
        buildSubjectConsistencyReport,
        ensureSceneTableConsistencyBeforePhase2,
        extractAnalysisSections,
        getAnalysisEntitiesPayloadFromJsonText,
        llmAssetRawResultContent,
        llmRawResultContent,
        llmResultContent,
        onLog,
        subjectIndexText,
        t,
    ]);

    const tryResumeAnalysisFromExistingArtifacts = useCallback(async (resumeState, retryCount = 0) => {
        if (!activeEpisode?.id || !resumeState || resumeState.decision === 'phase1') {
            return false;
        }

        const resolvedSubjectIndexText = String(resumeState?.resolvedSubjectIndexText || '').trim();
        const persistedSubjectIndexText = String(activeEpisode?.ai_scene_analysis_subject_index || '').trim();
        if (resolvedSubjectIndexText && resolvedSubjectIndexText !== persistedSubjectIndexText) {
            try {
                await updateEpisode(activeEpisode.id, {
                    ai_scene_analysis_subject_index: resolvedSubjectIndexText,
                });
                if (subjectIndexText !== resolvedSubjectIndexText) {
                    setSubjectIndexText(resolvedSubjectIndexText);
                }
                if (onLog) onLog('Detected asset index in current page content and persisted it to episode before resuming analysis.', 'info');
            } catch (persistSubjectIndexErr) {
                if (onLog) onLog(`Persist asset index before resume failed (continue): ${persistSubjectIndexErr?.message || persistSubjectIndexErr}`, 'warning');
            }
        }

        const retryResetNotice = retryCount > 0
            ? t('检测到首轮未返回完整资产清单，系统已清空当前分集场景并重新开始分析（资产已保留）。', 'Missing asset index in first attempt. Scenes were reset and analysis restarted from scratch (assets kept).')
            : '';
        const combinedWarning = [retryResetNotice, resumeState?.preflightSceneSyncNotice, resumeState?.resumeNotice]
            .filter(Boolean)
            .join('；');

        if (resumeState.decision === 'completed') {
            setAnalysisFlowStatus({
                phase: 'completed',
                message: '🎉 已检测到完整分析结果，无需重复导入或调用 AI！',
            });
            setAnalysisUiReport(buildCompletedAnalysisUiReport({
                status: 'completed',
                startedAt: Date.now(),
                durationMs: 0,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: combinedWarning,
                error: '',
            }));
            if (onLog) onLog('AI Analysis startup reused existing scene analysis results, asset index, and subjects JSON. No LLM call was needed.', 'success');
            return true;
        }

        if (analysisRunInFlightRef.current || analysisResumeInFlightRef.current) return true;
        analysisRunInFlightRef.current = true;
        setIsAnalyzing(true);
        const startedAt = Date.now();
        setAnalysisUiReport({
            status: 'running',
            startedAt,
            durationMs: 0,
            phaseTimings: null,
            importReport: null,
            runtimeMeta: null,
            warning: combinedWarning,
            error: '',
        });

        setAnalysisFlowStatus({
            phase: 'completed',
            message: '🚀 检测到资产清单已完整，直接进入资产设计...',
        });

        try {
            const mockImportReport = { importedSceneRows: [] };
            const dummyAnalyzedText = String(resumeState?.sceneAnalysisText || resolvedSubjectIndexText || '');
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
                message: '🎉 专属实体资产定制完毕，可随时投产使用！',
            });

            setAnalysisUiReport(buildCompletedAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings: null,
                importReport: finalImportReport,
                runtimeMeta: null,
                warning: combinedWarning,
                error: '',
            }));
        } catch (err) {
            console.error(err);
            setAnalysisFlowStatus({ phase: 'failed', message: '❌ 资产生成失败: ' + err.message });
            setAnalysisUiReport({
                status: 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: combinedWarning,
                error: err.message,
            });
        } finally {
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsAnalyzing(false);
            analysisRunInFlightRef.current = false;
        }

        return true;
    }, [activeEpisode?.ai_scene_analysis_subject_index, activeEpisode?.id, onLog, runPostImportSceneSubjectPipeline, subjectIndexText, t, updateEpisode]);

    const executeAnalysis = async (content, customSystemPrompt = null, skipMetadata = false, retryCount = 0) => {
        const forceRegenerate = forceRegenerateRef.current;
        forceRegenerateRef.current = false;
        const episodeId = activeEpisode?.id;

        if (forceRegenerate && episodeId) {
            releaseEpisodeAnalysisRun(episodeId);
        } else {
            const existingRun = episodeId ? getEpisodeAnalysisRun(episodeId) : null;
            if (existingRun?.promise) {
                return reattachToExistingAnalysisRun(existingRun);
            }
        }
        if (!forceRegenerate && (analysisRunInFlightRef.current || analysisResumeInFlightRef.current)) {
            if (onLog) onLog('Skipped duplicate AI Script Analysis submit while another analysis run is already active.', 'warning');
            return;
        }

        // Before starting a new analysis, ensure any previous dirty state is canceled backend-side.
        if (activeAnalysisTaskId) {
            try {
                const { stopAsyncTask } = await import('../../../services/api');
                await stopAsyncTask(activeAnalysisTaskId);
                if (onLog) onLog(`Stopped existing analysis task ${activeAnalysisTaskId} before starting new one.`, 'info');
            } catch (e) {
                console.warn('Silent failure trying to stop previous task', e);
            }
        }

        const clearedBeforeRun = await ensureStageAnalysisFieldsClearedBeforeRun({
            forceRegenerate,
            preserveProgressUi: true,
            deferWorkspaceUiReset: false,
        });

        const resumeState = (forceRegenerate || clearedBeforeRun)
            ? null
            : await prepareSceneAnalysisResumeState();
        if (!forceRegenerate && !clearedBeforeRun && await tryResumeAnalysisFromExistingArtifacts(resumeState, retryCount)) {
            return;
        }
        const preflightSceneSyncNotice = (forceRegenerate || clearedBeforeRun) ? '' : (resumeState?.preflightSceneSyncNotice || '');

        let analysisPipelineFinished = false;
        let analysisError = null;
        let analysisCanceled = false;

        analysisRunInFlightRef.current = true;
        clearAnalysisTaskMarker(activeEpisode?.id);
        resetAnalysisFallbackRetryCounts(activeEpisode?.id);
        lastAutoSubjectsImportRef.current = { signature: '', result: null };
        const startedAt = Date.now();
        const runAnalysisPipeline = async () => {
        analysisProgressDismissedRef.current = false;
        analysisStopRequestedRef.current = false;
        beginAnalysisTimer(startedAt);
        setIsAnalyzing(true);
        setActiveAnalysisTaskId('');
        setAnalysisFlowStatus({
            phase: 'script_opt',
            message: t('💾 正在自动保存您的剧本，保障数据安全...', 'Auto-saving script...'),
        });
        setAnalysisUiReport({
            status: 'running',
            startedAt,
            durationMs: 0,
            phaseTimings: null,
            importReport: null,
            runtimeMeta: null,
            warning: preflightSceneSyncNotice,
            error: '',
        });
        if (onLog) onLog("Starting AI Script Analysis...", "start");

        let llmReturned = false;
        let runtimeMeta = null;
        let importReport = null;
        let postImportSceneSubjectReport = null;
        let importWarningMessage = '';
        let rawResultPersistedEarly = false;
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
                phase: 'script_opt',
                message: t('🧠 正在通读剧本并设计场景啦。根据字数和剧情可能会花几分钟时间，请喝杯水稍等~', 'LLM submitted. Waiting for response. Total wait can take up to about 10 mins.'),
            });
            phaseMarks.analyzeStartedAt = Date.now();
            
            const baselineAnalysisText = clearedBeforeRun
                ? ''
                : String(activeEpisode?.ai_scene_analysis_result || '').trim();
            const result = await awaitAnalyzeSceneWithRecovery(
                () => runScriptAnalysisFlowAnalyzeNode(
                    'script_optimization',
                    content,
                    customSystemPrompt,
                    metadata,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            const stableTaskId = String(taskId || '').trim();
                            setActiveAnalysisTaskId(stableTaskId);
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId: stableTaskId, startedAt, phase: 1 });
                            updateEpisodeAnalysisRun(episodeId, { taskId: stableTaskId, phase: 1 });
                        },
                    },
                    projectId,
                    'script_analysis',
                    selectedScriptAnalysisApiId
                ),
                { startedAt, baselineText: baselineAnalysisText }
            );
            const analyzedText = extractAnalysisTextFromResult(result);
            
            // --- 第一时间保存对应卡片！---
            const savedByBackend = !!(result?.meta?.saved_to_episode);
            if (true || !savedByBackend) {
                phaseMarks.persistStartedAt = Date.now();
                try {
                    if (onLog) onLog('Persisting raw LLM output immediately after return...', 'process');
                    await persistLlmResultContent(analyzedText || '', 'ai_scene_analysis_result', { source: 'standard-analysis-immediate' });
                    rawResultPersistedEarly = true;
                } catch (persistErr) {
                    if (onLog) onLog(`Immediate raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                } finally {
                    phaseMarks.persistFinishedAt = Date.now();
                }
            }

            // --- 其他处理 ---
            setLlmRawResultContent(analyzedText || "");
            setLlmResultContent(normalizeLlmMarkdownTable(analyzedText || ""));
            lastLoadedAnalysisRef.current = analyzedText || "";
            if (analyzedText && (analyzedText.includes("PROHIBITED_CONTENT") || analyzedText.toLowerCase().includes("prohibited content"))) {
                const msg = t('剧本含有敏感信息（如色情或血腥内容，特别是针对少儿），触发了模型拦截。建议您换用 DeepSeek、豆包等模型重试。', 'Script contains sensitive information (like pornographic or violent content, especially involving minors) triggering policy block. We recommend retrying with DeepSeek or Doubao.');
                alert('⚠️ ' + msg);
                throw new Error("出现供应商政策不允许内容");
            }
            llmReturned = true;
            phaseMarks.llmReturnedAt = Date.now();

            setAnalysisFlowStatus({
                phase: 'completed',
                message: t('🚀 分析有了新进展，正在为您整理出炉...', 'LLM returned: saving raw output and filling the analysis Output Workspace...'),
            });
            setAnalysisFlowStatus({
                phase: 'completed',
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
                if (onLog) onLog('Missing asset index after Stage 2 output validation. Skipping auto-import and triggering cleanup retry.', 'warning');
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            setLlmRawResultContent(analyzedText);
            setLlmResultContent(normalizeLlmMarkdownTable(analyzedText));
            lastLoadedAnalysisRef.current = analyzedText;

            try {
                if (true || !savedByBackend && !rawResultPersistedEarly) {
                    phaseMarks.persistStartedAt = Date.now();
                    if (onLog) onLog('Saving raw LLM output to episode analysis field...', 'process');
                    await persistLlmResultContent(analyzedText, 'ai_scene_analysis_result', { source: 'standard-analysis' });
                } else {
                    if (savedByBackend) {
                        phaseMarks.persistStartedAt = phaseMarks.persistStartedAt || Date.now();
                    }
                    if (onLog) onLog('LLM raw output already saved by backend. Refreshing local episode cache...', 'info');
                    // await refreshAnalysisFromDB(); // TEMPORARY DISABLE
                }
            } catch (persistErr) {
                if (onLog) onLog(`Raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }
            
            phaseMarks.importStartedAt = Date.now();
            setAnalysisFlowStatus({
                phase: 'scene_beats',
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
                    const sceneRegenStarted = await triggerSceneArrangementRegenerationTask(analyzedText, {
                        reason: importWarningMessage,
                        source: 'standard-analysis-empty-import',
                    });
                    if (sceneRegenStarted) {
                        importWarningMessage = `${importWarningMessage}；${t('已自动发起单独场景编排任务。', 'Started a separate scene arrangement task automatically.')}`;
                    }
                }
            } catch (importErr) {
                importWarningMessage = t(
                    `自动导入失败：${importErr?.message || importErr}`,
                    `Auto-import failed: ${importErr?.message || importErr}`
                );
                if (onLog) onLog(`Auto-import failed (checks will continue): ${importErr?.message || importErr}`, 'warning');
                const sceneRegenStarted = await triggerSceneArrangementRegenerationTask(analyzedText, {
                    reason: importWarningMessage,
                    source: 'standard-analysis-import-error',
                });
                if (sceneRegenStarted) {
                    importWarningMessage = `${importWarningMessage}；${t('已自动发起单独场景编排任务。', 'Started a separate scene arrangement task automatically.')}`;
                }
                setAnalysisFlowStatus({ phase: 'warning', message: importWarningMessage });
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            importReport = await ensureSubjectsImportedBeforePostChecks(result, importReport);
            maybeAlertIncompleteSubjectsImport(result, analyzedText || '');

            postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(importReport, analyzedText);
            postImportSceneSubjectReport = syncScenePostImportCheckedCount(importReport, postImportSceneSubjectReport);
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
                          poster: (importReport.importedSubjectCounts?.poster || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.poster) || 0),
                    };
                }
                const stage3SkippedItems = Array.isArray(postImportSceneSubjectReport?.supplementReport?.skippedItems)
                    ? postImportSceneSubjectReport.supplementReport.skippedItems
                    : [];
                if (stage3SkippedItems.length > 0) {
                    importReport.skippedSubjectItems = [
                        ...(Array.isArray(importReport.skippedSubjectItems) ? importReport.skippedSubjectItems : []),
                        ...stage3SkippedItems,
                    ];
                }
            }

            let firstPassReport = null;
            try {
                firstPassReport = runSubjectConsistencyCheck(analyzedText || '', { silent: true, persist: true });
            } catch (consistencyErr) {
                firstPassReport = buildSubjectConsistencyReport(analyzedText || '');
                setSubjectConsistencyReport(firstPassReport);
                if (onLog) onLog(`Subject consistency check warning: ${consistencyErr?.message || consistencyErr}`, 'warning');
            }

            firstPassReport = firstPassReport || buildSubjectConsistencyReport(analyzedText || '');
            const { reviewIssues } = await publishAnalysisReviewFindings({
                subjectReport: firstPassReport,
                integrityWarnings,
                importWarningMessage,
            });

            let aiShotsBatchStarted = false;
            try {
                const flowRegistry = await getSceneAnalysisFlowRegistry();
                const configured = flowRegistry?.stage3_auto_start || flowRegistry?.config?.stage3_auto_start || {};
                const storyboardAutoStart = configured?.storyboard_generation !== false;
                
                if (storyboardAutoStart && Array.isArray(importReport?.scenes) && importReport.scenes.length > 0) {
                    if (onLog) onLog('Auto-starting storyboard generation for newly imported scenes...', 'info');
                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: t('🔄 正在启动分镜自动生成任务...', 'Starting automated storyboard generation...'),
                    });
                    
                    const workflowStarted = await runSceneAnalysisFlowNode({
                        node_key: 'storyboard_generation',
                        project_id: projectId,
                        episode_id: activeEpisode.id,
                        scene_ids: importReport.scenes.map(s => s.id),
                    });
                    
                    aiShotsBatchStarted = !!(workflowStarted?.batch_status || workflowStarted);
                    if (onLog) onLog(`Storyboard generation automatically started.`, 'success');
                }
            } catch (err) {
                if (onLog) onLog(`Failed to auto-start storyboard generation: ${err?.message || err}`, 'warning');
            }

            setPendingSwitchAfterPostChecks(false);
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            const combinedReportWarning = [importWarningMessage, retryResetNotice, preflightSceneSyncNotice]
                .map(item => String(item || '').trim())
                .filter(Boolean)
                .join('；');
            const reviewWarningText = reviewIssues.length > 0 ? buildAnalysisReviewWarningMessage(reviewIssues) : '';

            setAnalysisUiReport(buildCompletedAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                storyboardAutoStarted: aiShotsBatchStarted,
                warning: [combinedReportWarning, reviewWarningText]
                    .map((item) => String(item || '').trim())
                    .filter(Boolean)
                    .join('\n\n'),
                reviewIssues,
                error: '',
            }));

            const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
            const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
            const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
            const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
            const reviewSuffix = reviewIssues.length > 0
                ? t(`（另有 ${reviewIssues.length} 项待复核，见下方问题列表）`, ` (${reviewIssues.length} issue(s) need review; see list below)`)
                : '';
            
            const appendStoryboardNotice = (baseZh, baseEn) => {
                if (!aiShotsBatchStarted) return t(baseZh, baseEn);
                return t(`${baseZh} 分镜任务已在后台启动。`, `${baseEn} Storyboard generation started in background.`);
            };

            setAnalysisFlowStatus({
                phase: 'completed',
                message: (postImportMissingItems > 0
                    ? (
                        postImportSupplementFailed > 0
                            ? appendStoryboardNotice(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`)
                            : appendStoryboardNotice(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`)
                    )
                    : appendStoryboardNotice('✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.')) + reviewSuffix,
            });

            if (onLog) onLog("AI Analysis applied and saved.");
            setShowAnalysisModal(false);
            analysisPipelineFinished = true;
        } catch (e) {
            console.error(e);
            
            analysisError = e;
            analysisCanceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            if (!scriptEditorMountedRef.current) {
                return;
            }
            const friendlyAnalysisError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
            const retainMarker = shouldRetainAnalysisTaskMarker({
                canceled: analysisCanceled,
                error: e,
                mounted: true,
            });
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            if (analysisCanceled) {
                if (onLog) onLog('Analysis task canceled by user.', 'warning');
            } else {
                if (onLog) onLog(`Analysis Failed: ${friendlyAnalysisError}`);
            }
            setAnalysisFlowStatus(
                analysisCanceled
                    ? { phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') }
                    : retainMarker
                        ? { phase: 'warning', message: t('分析连接中断，任务仍在后台运行。返回本页后会自动恢复进度。', 'Analysis connection interrupted. The task is still running; return here to resume progress.') }
                        : { phase: 'failed', message: t(`分析失败：${friendlyAnalysisError}`, `Analysis failed: ${friendlyAnalysisError}`) }
            );
            setAnalysisUiReport({
                status: analysisCanceled ? 'warning' : retainMarker ? 'warning' : 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport: importReport,
                runtimeMeta,
                warning: analysisCanceled
                    ? t('分析任务已由用户停止。', 'Analysis task was stopped by user.')
                    : retainMarker
                        ? t('分析连接中断，返回本页后会自动恢复进度。', 'Connection interrupted. Return here to resume progress.')
                        : '',
                error: analysisCanceled || retainMarker ? '' : friendlyAnalysisError,
            });
            if (!analysisCanceled && !retainMarker) {
                alert(`Analysis failed: ${friendlyAnalysisError}`);
            }
        } finally {
            const retainMarker = shouldRetainAnalysisTaskMarker({
                pipelineFinished: analysisPipelineFinished,
                canceled: analysisCanceled,
                error: analysisError,
                mounted: scriptEditorMountedRef.current,
            });
            if (!retainMarker) {
                clearAnalysisTaskMarker(episodeId);
            }
            analysisRunInFlightRef.current = false;
            if (!scriptEditorMountedRef.current) return;
            setIsAnalyzing(false);
            setActiveAnalysisTaskId('');
            analysisStopRequestedRef.current = false;
        }
        };
        const runPromise = runAnalysisPipeline();

        trackEpisodeAnalysisRun(episodeId, runPromise, { startedAt, kind: 'standard' });
        return runPromise;
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
            const promptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md');
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
            attentionNotes: analysisAttentionNotes,
        });

        if (onLog) onLog('Manual supplement submit started (input=generated analysis output).', 'start');
        await executeAnalysis(supplementInput, supplementPrompt, false);
    };

    const executeAdvancedAnalysis = async (userInput, customSystemPrompt, retryCount = 0, skipMetadata = false) => {
        if (!activeEpisode?.id) {
            alert("No active episode selected.");
            return;
        }

        resetAutoSubjectsImportCache();

        const forceRegenerate = forceRegenerateRef.current;
        forceRegenerateRef.current = false;
        const episodeId = activeEpisode.id;

        if (forceRegenerate) {
            releaseEpisodeAnalysisRun(episodeId);
        } else {
            const existingRun = getEpisodeAnalysisRun(episodeId);
            if (existingRun?.promise) {
                return reattachToExistingAnalysisRun(existingRun);
            }
        }
        if (!forceRegenerate && (analysisRunInFlightRef.current || analysisResumeInFlightRef.current)) {
            if (onLog) onLog('Skipped duplicate advanced AI Script Analysis submit while another analysis run is already active.', 'warning');
            return;
        }

        // Before starting a new analysis, ensure any previous dirty state is canceled backend-side.
        if (activeAnalysisTaskId) {
            try {
                const { stopAsyncTask } = await import('../../../services/api');
                await stopAsyncTask(activeAnalysisTaskId);
                if (onLog) onLog(`Stopped existing advanced analysis task ${activeAnalysisTaskId} before starting new one.`, 'info');
            } catch (e) {
                console.warn('Silent failure trying to stop previous task', e);
            }
        }

        const clearedBeforeRun = await ensureStageAnalysisFieldsClearedBeforeRun({
            forceRegenerate,
            preserveProgressUi: true,
            deferWorkspaceUiReset: false,
        });

        const resumeState = (forceRegenerate || clearedBeforeRun)
            ? null
            : await prepareSceneAnalysisResumeState();
        if (!forceRegenerate && !clearedBeforeRun && await tryResumeAnalysisFromExistingArtifacts(resumeState, retryCount)) {
            return;
        }
        const preflightSceneSyncNotice = (forceRegenerate || clearedBeforeRun) ? '' : (resumeState?.preflightSceneSyncNotice || '');

        let analysisPipelineFinished = false;
        let analysisError = null;
        let analysisCanceled = false;

        analysisRunInFlightRef.current = true;
        clearAnalysisTaskMarker(activeEpisode?.id);
        resetAnalysisFallbackRetryCounts(activeEpisode?.id);

        const startedAt = Date.now();
        const runAnalysisPipeline = async () => {
        analysisProgressDismissedRef.current = false;
        analysisStopRequestedRef.current = false;
        beginAnalysisTimer(startedAt);
        setIsAnalyzing(true);
        setActiveAnalysisTaskId('');
        setAnalysisFlowStatus({
            phase: 'script_opt',
            message: t('💾 正在自动保存您的剧本，保障数据安全...', 'Auto-saving script...'),
        });
        const retryResetNotice = retryCount > 0
            ? t('检测到首轮未返回完整资产清单，系统已清空当前分集场景并重新开始分析（资产已保留）。', 'Missing asset index in first attempt. Scenes were reset and analysis restarted from scratch (assets kept).')
            : '';

        setAnalysisUiReport({
            status: 'running',
            startedAt,
            durationMs: 0,
            phaseTimings: null,
            importReport: null,
            runtimeMeta: null,
            warning: [retryResetNotice, preflightSceneSyncNotice].filter(Boolean).join('；'),
            error: '',
        });
        if (onLog) onLog("Starting Advanced AI Analysis (Superuser)...", "start");

        let llmReturned = false;
        let runtimeMeta = null;
        let importReport = null;
        let postImportSceneSubjectReport = null;
        let importWarningMessage = '';
        let expectedSceneImportCount = 0;
        let stage2SubjectIndexForAssets = '';
        let globalStage2_1Text = '';
        let splitFlowScenesImported = false;
        let finalRawResultPersistedEarly = false;
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
            const metadata = skipMetadata ? null : (project?.global_info || null);

            setAnalysisFlowStatus({
                phase: 'script_opt',
                message: t('🧠 正在通读剧本并设计场景啦。根据字数和剧情可能会花几分钟时间，请喝杯水稍等~', 'LLM submitted. Waiting for response. Total wait can take up to about 10 mins.'),
            });
            phaseMarks.analyzeStartedAt = Date.now();

            const baselineAnalysisText = clearedBeforeRun
                ? ''
                : String(activeEpisode?.ai_scene_analysis_result || '').trim();
            const splitStage1Flow = isSplitStage1Prompt(customSystemPrompt);
            const result = await awaitAnalyzeSceneWithRecovery(
                () => runScriptAnalysisFlowAnalyzeNode(
                    'script_optimization',
                    userInput,
                    customSystemPrompt,
                    metadata,
                    activeEpisode?.id || null,
                    analysisAttentionNotes,
                    selectedReuseSubjectAssets,
                    {
                        onTaskCreated: (taskId) => {
                            const stableTaskId = String(taskId || '').trim();
                            setActiveAnalysisTaskId(stableTaskId);
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId: stableTaskId, startedAt, phase: 1 });
                            updateEpisodeAnalysisRun(episodeId, { taskId: stableTaskId, phase: 1 });
                        },
                    },
                    projectId,
                    'script_analysis',
                    selectedScriptAnalysisApiId
                ),
                { startedAt, baselineText: baselineAnalysisText }
            );
            const analyzedText = extractAnalysisTextFromResult(result);
            
            // --- 第一时间保存对应卡片！---
            const savedByBackend = !!(result?.meta?.saved_to_episode);
            if (true || !savedByBackend) {
                phaseMarks.persistStartedAt = Date.now();
                try {
                    if (onLog) onLog('Persisting advanced raw LLM output immediately after Stage 1 return...', 'process');
                    await persistLlmResultContent(analyzedText || '', 'ai_scene_analysis_result', { source: 'advanced-analysis-stage1-immediate' });
                    finalRawResultPersistedEarly = true;
                } catch (persistErr) {
                    if (onLog) onLog(`Immediate advanced raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                } finally {
                    phaseMarks.persistFinishedAt = Date.now();
                }
            }

            // --- 其他处理 ---
            if (!splitStage1Flow) setLlmRawResultContent(analyzedText || '');
            if (!splitStage1Flow) setLlmResultContent(normalizeLlmMarkdownTable(analyzedText || ''));
            if (!splitStage1Flow) lastLoadedAnalysisRef.current = analyzedText || '';
            if (analyzedText && (analyzedText.includes("PROHIBITED_CONTENT") || analyzedText.toLowerCase().includes("prohibited content"))) {
                const msg = t('剧本含有敏感信息（如色情或血腥内容，特别是针对少儿），触发了模型拦截。建议您换用 DeepSeek、豆包等模型重试。', 'Script contains sensitive information (like pornographic or violent content, especially involving minors) triggering policy block. We recommend retrying with DeepSeek or Doubao.');
                alert('⚠️ ' + msg);
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

            let finalAnalysisText = analyzedText || '';
            let importSourceText = analyzedText || '';
            let parallelSceneMarkdownPatchMap = null;
            let analysisSections = extractAnalysisSections(finalAnalysisText);
            let stage1PhaseRawText = '';
            let stage2PhaseRawText = '';

            if (splitStage1Flow) {
                stage1PhaseRawText = String(analyzedText || '').trim();
                const { adaptedScriptText, userInput: stage2UserInput } = buildStage2UserInputFromStage1(analyzedText || '', selectedReuseSubjectAssets);
                if (!String(adaptedScriptText || '').trim()) {
                    throw new Error('第一阶段未提取到“修改后的剧本”正文，请确认返回结果包含第二部分剧本正文后重试。');
                }

                setAdaptationText(adaptedScriptText);

                // Guard against upstream AI model providers returning backend JSON error strings instead of markdown text.
                let isUpstreamError = false;
                let errMsg = '';
                const matchObjStr = adaptedScriptText.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
                if (matchObjStr.startsWith('{')) {
                    try {
                        const parseObj = JSON.parse(matchObjStr);
                        if (parseObj.code === 500 || parseObj.error || parseObj.msg) {
                            isUpstreamError = true;
                            errMsg = `上游底层大语言模型接口异常 (拦截网关)：${parseObj.msg || parseObj.error?.message || matchObjStr}`;
                        }
                    } catch(e) {}
                }
                if (!isUpstreamError && /服务器错误|maintained|too many requests|rate limit/i.test(adaptedScriptText)) {
                    isUpstreamError = true;
                    errMsg = `上游接口熔断或系统正在维护中，返回了异常拦截页：${adaptedScriptText.slice(0, 100)}`;
                }
                if (isUpstreamError) {
                    throw new Error(errMsg);
                }

                if (onLog) onLog('Stage 1 split prompt detected. Running Stage 2 scene analysis before asset-index validation.', 'info');

                const stage2_1PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_1_assets_extraction.md');
                let finalStage2_1Prompt = stage2_1PromptRes?.content || '';
                let finalStage2_1UserInput = stage2UserInput;

                if (onLog) onLog('Submitting Stage 2.1 (Asset Extraction)...', 'info');

                setAnalysisFlowStatus({
                    phase: 'extract_assets',
                    message: t('📝 正在执行美术提取，拆解核心资产...', 'Running Asset Extraction...'),
                });

                const runStage2_1Attempt = async () => (
                    await awaitAnalyzeSceneWithRecovery(
                        () => runScriptAnalysisFlowAnalyzeNode(
                            'assets_extraction',
                            finalStage2_1UserInput,
                            finalStage2_1Prompt,
                            null,
                            activeEpisode?.id || null,
                            analysisAttentionNotes,
                            selectedReuseSubjectAssets,
                            {
                                onTaskCreated: (taskId) => {
                                    const stableTaskId = String(taskId || '').trim();
                                    setActiveAnalysisTaskId(stableTaskId);
                                    saveAnalysisTaskMarker(activeEpisode?.id, { taskId: stableTaskId, startedAt, phase: 2 });
                                    updateEpisodeAnalysisRun(episodeId, { taskId: stableTaskId, phase: 2 });
                                },
                            },
                            projectId,
                            'script_analysis',
                            selectedScriptAnalysisApiId
                        ),
                        { startedAt: phaseMarks.llmReturnedAt || startedAt, baselineText: baselineAnalysisText }
                    )
                );

                const { result: stage2_1Result, text: stage2_1Text, validation: stage2_1Validation } = await runStage2_1WithValidationRetry(
                    runStage2_1Attempt,
                    'Stage 2.1'
                );
                const stage2_1SubjectIndexText = String(stage2_1Validation.subjectIndexText || '').trim() || extractPureSubjectIndexText(stage2_1Text).trim() || String(stage2_1Text || '').trim();
                globalStage2_1Text = stage2_1SubjectIndexText;
                
                // --- 第一时间保存 Stage 2.1 (提取的美术资产/Subject Index) 对应卡片！---
                try {
                    if (onLog) onLog('Persisting clean Stage 2.1 Subject Index immediately after return...', 'process');
                    await persistLlmResultContent(stage2_1SubjectIndexText, 'ai_scene_analysis_subject_index', {
                        source: 'advanced-analysis-stage2_1-subject-index-immediate'
                    });
                } catch (persistErr) {
                    if (onLog) onLog(`Failed to persist clean Subject Index immediately: ${persistErr?.message || persistErr}`, 'warning');
                }

                if (onLog) onLog('Subject Index 已就绪，开始并发执行：场景编排 + 视觉资产生成（角色/道具/环境）...', 'info');

                setAnalysisFlowStatus({
                    phase: 'scene_beats',
                    message: t(
                        '📝 Subject Index 已生成，正在并发执行场景编排与视觉资产生成...',
                        'Subject Index ready; running scene beats and visual asset generation in parallel...'
                    ),
                });

                stage2SubjectIndexForAssets = globalStage2_1Text || stage2_1SubjectIndexText;

                const importScenesAfterOrchestration = async ({
                    localParallelPatchMap,
                    localImportSourceText,
                    localFinalAnalysisText,
                }) => {
                    phaseMarks.importStartedAt = Date.now();
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t('📝 场景编排已完成，正在导入工作区...', 'Scene beats finished; importing into workspace...'),
                    });
                    if (!expectedSceneImportCount && String(localImportSourceText || localFinalAnalysisText || '').trim()) {
                        const preImportCheck = validateAutoSceneTableImport(localImportSourceText || localFinalAnalysisText || '');
                        if (preImportCheck?.ok) {
                            const parsedPreImportTable = parseMarkdownTable(preImportCheck.tableText || localImportSourceText || localFinalAnalysisText || '');
                            expectedSceneImportCount = Array.isArray(parsedPreImportTable?.rows) ? parsedPreImportTable.rows.length : 0;
                        }
                    }
                    let branchImportReport = null;
                    if (localParallelPatchMap && Object.keys(localParallelPatchMap).length > 0) {
                        branchImportReport = await importScenesFromPerScenePatchMap(localParallelPatchMap, {
                            subjectsJson: result?.subjects_json || null,
                            replaceExistingScenes: true,
                        });
                    } else {
                        branchImportReport = await runAutoImportAndSwitchToScenes(localImportSourceText || localFinalAnalysisText || '', {
                            switchToScenes: false,
                            importOptions: {
                                autoSupplementSceneSubjects: false,
                                suppressAlerts: true,
                                subjectsJson: result?.subjects_json || null,
                            },
                        });
                    }
                    if (!branchImportReport) {
                        throw new Error(t(
                            '自动导入未返回结果，场景未写入工作区。请检查导入配置或返回格式。',
                            'Auto-import returned no result; scenes were not written to the workspace.'
                        ));
                    }
                    const dbSceneCountAfterImport = await waitForEpisodeSceneCount(
                        fetchScenes,
                        activeEpisode?.id,
                        expectedSceneImportCount || 1,
                        { retries: 15, delayMs: 600 },
                    );
                    assertWorkspaceSceneImportComplete({
                        importReport: branchImportReport,
                        expectedSceneCount: expectedSceneImportCount || 1,
                        dbSceneCount: dbSceneCountAfterImport,
                        t,
                    });
                    onLog?.(
                        t(
                            `[场景导入] 工作区校验通过：${dbSceneCountAfterImport}/${expectedSceneImportCount || dbSceneCountAfterImport} 场已入库`,
                            `[Scene import] Workspace verified: ${dbSceneCountAfterImport}/${expectedSceneImportCount || dbSceneCountAfterImport} scene(s) in DB`
                        ),
                        'success'
                    );
                    phaseMarks.importFinishedAt = Date.now();
                    return branchImportReport;
                };

                const runSceneOrchestrationBranch = async () => {
                    let stage2_2UserInputBody = buildStage2_2UserInputFromStage1(stage1PhaseRawText);
                    const finalStage2_2UserInput = stage2_2UserInputBody;
                    const beatsResult = await runStage2_2WithValidationRetry({
                        label: 'Stage 2.2',
                        logPhasePrefix: 'advanced',
                        finalStage2_2UserInput,
                        stage2_2UserInputBody,
                        stage2_1SubjectIndexText,
                        stage1SourceText: stage1PhaseRawText,
                        startedAt: phaseMarks.llmReturnedAt || startedAt,
                        baselineText: baselineAnalysisText,
                        onTaskCreated: (taskId) => {
                            const stableTaskId = String(taskId || '').trim();
                            setActiveAnalysisTaskId(stableTaskId);
                            saveAnalysisTaskMarker(activeEpisode?.id, { taskId: stableTaskId, startedAt, phase: 'scene_beats' });
                            updateEpisodeAnalysisRun(episodeId, { taskId: stableTaskId, phase: 'scene_beats' });
                        },
                    });

                    const {
                        stage2_2Text,
                        perSceneParallel = false,
                        sceneMarkdownPatchMap = null,
                    } = beatsResult || {};

                    let branchParallelPatchMap = null;
                    let branchFinalAnalysisText = '';
                    let branchImportSourceText = '';
                    let branchStage2PhaseRawText = '';

                    if (perSceneParallel && sceneMarkdownPatchMap && Object.keys(sceneMarkdownPatchMap).length > 0) {
                        branchParallelPatchMap = sceneMarkdownPatchMap;
                        expectedSceneImportCount = Object.keys(sceneMarkdownPatchMap).length;
                        branchStage2PhaseRawText = [String(stage2_1Text || '').trim()].filter(Boolean).join('\n\n');
                        phaseMarks.persistStartedAt = Date.now();
                        try {
                            if (onLog) onLog('Persisting per-scene Stage 2.2 outputs immediately after parallel beats return...', 'process');
                            await persistSceneMarkdownPatch(sceneMarkdownPatchMap, {
                                source: 'advanced-analysis-split-per-scene-immediate',
                                stage1RawText: stage1PhaseRawText,
                                stage2_1Text: globalStage2_1Text,
                                replaceSceneMarkdownByScene: true,
                            });
                            const mergedParallelMarkdown = mergeStage2_2SceneTableOutputs(
                                Object.values(sceneMarkdownPatchMap)
                                    .map((entry) => String(entry?.markdown || '').trim())
                                    .filter(Boolean)
                            );
                            if (mergedParallelMarkdown) {
                                branchFinalAnalysisText = mergedParallelMarkdown;
                                branchImportSourceText = mergedParallelMarkdown;
                                await persistSceneMarkdownBundle(mergedParallelMarkdown, {
                                    source: 'advanced-analysis-split-per-scene-merged',
                                    stage1RawText: stage1PhaseRawText,
                                    stage2RawText: [String(stage2_1Text || '').trim(), mergedParallelMarkdown].filter(Boolean).join('\n\n'),
                                    stage2_1Text: globalStage2_1Text,
                                    sceneMarkdownByScene: sceneMarkdownPatchMap,
                                    replaceSceneMarkdownByScene: true,
                                    syncSceneUnits: false,
                                });
                            }
                            finalRawResultPersistedEarly = true;
                        } catch (persistErr) {
                            if (onLog) onLog(`Immediate per-scene Stage 2.2 save warning: ${persistErr?.message || persistErr}`, 'warning');
                        } finally {
                            phaseMarks.persistFinishedAt = Date.now();
                        }
                    } else {
                        branchStage2PhaseRawText = [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\n\n');
                        const stage2_2Check = validateStage2_2BeatsOutput(stage2_2Text || '', 'Stage 2.2');
                        if (!stage2_2Check.ok) {
                            throw new Error(stage2_2Check.reason || 'Stage 2.2 Beats Generation validation failed: returned table lacks Scene ID column (may have received Subject Index instead of Scenes Table). Please retry.');
                        }
                        branchFinalAnalysisText = stage2_2Check.normalizedText;
                        branchImportSourceText = branchFinalAnalysisText;
                        const sceneTableCheck = validateAutoSceneTableImport(branchFinalAnalysisText);
                        if (sceneTableCheck?.ok) {
                            const parsedSceneTable = parseMarkdownTable(sceneTableCheck.tableText || branchFinalAnalysisText);
                            expectedSceneImportCount = Array.isArray(parsedSceneTable?.rows) ? parsedSceneTable.rows.length : 0;
                        }
                        phaseMarks.persistStartedAt = Date.now();
                        try {
                            if (onLog) onLog('Persisting split-flow combined raw LLM output immediately after Beats return...', 'process');
                            await persistLlmResultContent(branchFinalAnalysisText || '', 'ai_scene_analysis_scene_markdown', {
                                source: 'advanced-analysis-split-combined-immediate',
                                stage1RawText: stage1PhaseRawText,
                                stage2RawText: branchStage2PhaseRawText,
                                stage2_1Text: globalStage2_1Text,
                                sceneMarkdownByScene: splitSceneMarkdownTableBySceneId(branchFinalAnalysisText || ''),
                                syncSceneUnits: false,
                            });
                            finalRawResultPersistedEarly = true;
                        } catch (persistErr) {
                            if (onLog) onLog(`Immediate split-flow raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
                        } finally {
                            phaseMarks.persistFinishedAt = Date.now();
                        }
                    }

                    const branchImportReport = await importScenesAfterOrchestration({
                        localParallelPatchMap: branchParallelPatchMap,
                        localImportSourceText: branchImportSourceText,
                        localFinalAnalysisText: branchFinalAnalysisText,
                    });

                    return {
                        beatsResult,
                        branchParallelPatchMap,
                        branchFinalAnalysisText,
                        branchImportSourceText,
                        branchStage2PhaseRawText,
                        branchImportReport,
                    };
                };

                const runAssetDesignBranch = async () => runPostImportSceneSubjectPipeline(
                    null,
                    stage2SubjectIndexForAssets,
                    {
                        explicitSubjectIndexText: stage2SubjectIndexForAssets,
                        parallelWithScenes: true,
                    }
                );

                const [sceneOutcome, assetOutcome] = await Promise.allSettled([
                    runSceneOrchestrationBranch(),
                    runAssetDesignBranch(),
                ]);

                if (sceneOutcome.status !== 'fulfilled') {
                    throw sceneOutcome.reason;
                }
                if (assetOutcome.status !== 'fulfilled') {
                    const assetErr = assetOutcome.reason;
                    onLog?.(`Stage 3 asset design branch failed: ${assetErr?.message || assetErr}`, 'error');
                    throw assetErr instanceof Error ? assetErr : new Error(String(assetErr || 'Stage 3 asset design failed'));
                }

                const sceneBranch = sceneOutcome.value || {};
                parallelSceneMarkdownPatchMap = sceneBranch.branchParallelPatchMap || null;
                finalAnalysisText = sceneBranch.branchFinalAnalysisText || '';
                importSourceText = sceneBranch.branchImportSourceText || finalAnalysisText;
                stage2PhaseRawText = sceneBranch.branchStage2PhaseRawText || stage2PhaseRawText;
                importReport = sceneBranch.branchImportReport || null;
                splitFlowScenesImported = true;
                postImportSceneSubjectReport = assetOutcome.value || null;

                analysisSections = extractAnalysisSections(stage2PhaseRawText);
                analysisSections.hasStructuredSubjectIndex = true;
                analysisSections.subjectIndexText = String(stage2_1Text || '').trim();
            }

            if (!analysisSections.hasStructuredSubjectIndex) {
                if (onLog) onLog('Missing asset index after Stage 2 output validation. Skipping auto-import and triggering cleanup retry.', 'warning');
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            setLlmRawResultContent(finalAnalysisText || '');
            setLlmResultContent(normalizeLlmMarkdownTable(finalAnalysisText || ''));
            lastLoadedAnalysisRef.current = finalAnalysisText || '';

            try {
                if (true || !savedByBackend && !finalRawResultPersistedEarly) {
                    phaseMarks.persistStartedAt = Date.now();
                    if (onLog) onLog('Saving advanced raw LLM output to episode analysis field...', 'process');
                    await persistLlmResultContent(finalAnalysisText || '', 'ai_scene_analysis_scene_markdown', {
                        source: splitStage1Flow ? 'advanced-analysis-split-combined' : 'advanced-analysis',
                        stage1RawText: stage1PhaseRawText,
                        stage2RawText: stage2PhaseRawText,
                        stage2_1Text: globalStage2_1Text || undefined,
                        sceneMarkdownByScene: splitSceneMarkdownTableBySceneId(finalAnalysisText || ''),
                    });
                } else {
                    if (savedByBackend) {
                        phaseMarks.persistStartedAt = phaseMarks.persistStartedAt || Date.now();
                    }
                    if (onLog) onLog('Advanced LLM raw output already saved by backend. Refreshing local episode cache...', 'info');
                    if (onUpdateEpisodeInfo && activeEpisode?.id) {
                        await onUpdateEpisodeInfo(activeEpisode.id, {
                            ai_stage_outputs: JSON.stringify(buildStageOutputsObject({
                                analysisRawText: finalAnalysisText || analyzedText || '',
                                assetRawText: activeEpisode?.ai_entity_design_result || llmAssetRawResultContent || '',
                            }), null, 2),
                        });
                    }
                }
            } catch (persistErr) {
                if (onLog) onLog(`Advanced raw LLM output save warning: ${persistErr?.message || persistErr}`, 'warning');
            } finally {
                phaseMarks.persistFinishedAt = Date.now();
            }

            phaseMarks.importStartedAt = Date.now();
            if (!splitFlowScenesImported) {
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('📝 分析框架解构完毕，正在导入您的工作区...', 'Importing Markdown into workspace...'),
            });
            if (!expectedSceneImportCount && String(importSourceText || finalAnalysisText || '').trim()) {
                const preImportCheck = validateAutoSceneTableImport(importSourceText || finalAnalysisText || '');
                if (preImportCheck?.ok) {
                    const parsedPreImportTable = parseMarkdownTable(preImportCheck.tableText || importSourceText || finalAnalysisText || '');
                    expectedSceneImportCount = Array.isArray(parsedPreImportTable?.rows) ? parsedPreImportTable.rows.length : 0;
                }
            }
            try {
                if (parallelSceneMarkdownPatchMap && Object.keys(parallelSceneMarkdownPatchMap).length > 0) {
                    importReport = await importScenesFromPerScenePatchMap(parallelSceneMarkdownPatchMap, {
                        subjectsJson: result?.subjects_json || null,
                        replaceExistingScenes: true,
                    });
                } else {
                    importReport = await runAutoImportAndSwitchToScenes(importSourceText || finalAnalysisText || '', {
                        switchToScenes: false,
                        importOptions: {
                            autoSupplementSceneSubjects: false,
                            suppressAlerts: true,
                            subjectsJson: result?.subjects_json || null,
                        },
                    });
                }
                if (!importReport) {
                    throw new Error(t(
                        '自动导入未返回结果，场景未写入工作区。请检查导入配置或返回格式。',
                        'Auto-import returned no result; scenes were not written to the workspace.'
                    ));
                }

                const dbSceneCountAfterImport = await waitForEpisodeSceneCount(
                    fetchScenes,
                    activeEpisode?.id,
                    expectedSceneImportCount || 1,
                    { retries: 15, delayMs: 600 },
                );
                assertWorkspaceSceneImportComplete({
                    importReport,
                    expectedSceneCount: expectedSceneImportCount || 1,
                    dbSceneCount: dbSceneCountAfterImport,
                    t,
                });
                onLog?.(
                    t(
                        `[场景导入] 工作区校验通过：${dbSceneCountAfterImport}/${expectedSceneImportCount || dbSceneCountAfterImport} 场已入库`,
                        `[Scene import] Workspace verified: ${dbSceneCountAfterImport}/${expectedSceneImportCount || dbSceneCountAfterImport} scene(s) in DB`
                    ),
                    'success'
                );
            } catch (importErr) {
                importWarningMessage = t(`自动导入失败：${importErr?.message || importErr}`, `Auto-import failed: ${importErr?.message || importErr}`);
                if (onLog) onLog(`Auto-import failed: ${importErr?.message || importErr}`, 'error');
                const sceneRegenStarted = await triggerSceneArrangementRegenerationTask(importSourceText || finalAnalysisText || '', {
                    reason: importWarningMessage,
                    source: 'advanced-analysis-import-error',
                });
                if (sceneRegenStarted) {
                    importWarningMessage = `${importWarningMessage}；${t('已自动发起单独场景编排任务。', 'Started a separate scene arrangement task automatically.')}`;
                }
                setAnalysisFlowStatus({ phase: 'failed', message: importWarningMessage });
                throw importErr instanceof Error ? importErr : new Error(String(importErr || importWarningMessage));
            } finally {
                phaseMarks.importFinishedAt = Date.now();
            }
            }
            importReport = await ensureSubjectsImportedBeforePostChecks(result, importReport);
            maybeAlertIncompleteSubjectsImport(result, finalAnalysisText || '');

            if (!splitStage1Flow && !postImportSceneSubjectReport) {
                setAnalysisFlowStatus({
                    phase: 'asset_generation',
                    message: t('🎨 场景已入库，正在生成视觉资产（角色/道具/环境）...', 'Scenes imported; generating visual assets (characters/props/environments)...'),
                });
                try {
                    postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(
                        importReport,
                        stage2SubjectIndexForAssets || globalStage2_1Text || '',
                        {
                            explicitSubjectIndexText: stage2SubjectIndexForAssets || globalStage2_1Text || '',
                        }
                    );
                } catch (stage3Err) {
                    if (onLog) onLog(`Stage 3 asset design failed: ${stage3Err?.message || stage3Err}`, 'error');
                    throw stage3Err;
                }
            }

            if (importReport && typeof importReport === 'object' && postImportSceneSubjectReport) {
                const mergedScenePostReport = syncScenePostImportCheckedCount(importReport, postImportSceneSubjectReport);
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: mergedScenePostReport,
                };
                if (mergedScenePostReport?.dbRunInsertedCounts) importReport.dbRunInsertedCounts = mergedScenePostReport.dbRunInsertedCounts;
                if (mergedScenePostReport?.dbPersistedCounts) importReport.dbPersistedCounts = mergedScenePostReport.dbPersistedCounts;
                if (mergedScenePostReport?.importedSubjectCounts) {
                    importReport.importedSubjectCounts = {
                        character: (importReport.importedSubjectCounts?.character || 0) + (Number(mergedScenePostReport.importedSubjectCounts.character) || 0),
                        prop: (importReport.importedSubjectCounts?.prop || 0) + (Number(mergedScenePostReport.importedSubjectCounts.prop) || 0),
                        environment: (importReport.importedSubjectCounts?.environment || 0) + (Number(mergedScenePostReport.importedSubjectCounts.environment) || 0),
                        poster: (importReport.importedSubjectCounts?.poster || 0) + (Number(mergedScenePostReport.importedSubjectCounts.poster) || 0),
                    };
                }
                const stage3SkippedItems = Array.isArray(mergedScenePostReport?.supplementReport?.skippedItems)
                    ? mergedScenePostReport.supplementReport.skippedItems
                    : [];
                if (stage3SkippedItems.length > 0) {
                    importReport.skippedSubjectItems = [
                        ...(Array.isArray(importReport.skippedSubjectItems) ? importReport.skippedSubjectItems : []),
                        ...stage3SkippedItems,
                    ];
                }
            }

            let firstPassReport = null;
            try {
                firstPassReport = runSubjectConsistencyCheck(analyzedText || '', { silent: true, persist: true });
            } catch (consistencyErr) {
                firstPassReport = buildSubjectConsistencyReport(analyzedText || '');
                setSubjectConsistencyReport(firstPassReport);
                if (onLog) onLog(`Subject consistency check warning: ${consistencyErr?.message || consistencyErr}`, 'warning');
            }

            firstPassReport = firstPassReport || buildSubjectConsistencyReport(analyzedText || '');

            setAnalysisFlowStatus({
                phase: 'supplement',
                message: t('🔍 全部节点已完成，正在执行完整性检查...', 'All nodes finished; running integrity checks...'),
            });
            await runAnalysisPipelineIntegrityGate({
                t,
                onLog,
                fetchScenesFn: fetchScenes,
                fetchEntitiesFn: fetchEntities,
                projectId,
                episodeId: activeEpisode?.id,
                importReport,
                postImportSceneSubjectReport,
                expectedSceneCount: expectedSceneImportCount,
                subjectIndexText: stage2SubjectIndexForAssets || globalStage2_1Text || activeEpisode?.ai_scene_analysis_subject_index || '',
            });

            const { reviewIssues } = await publishAnalysisReviewFindings({
                subjectReport: firstPassReport,
                integrityWarnings,
                importWarningMessage,
            });

            let aiShotsBatchStarted = false;
            try {
                const flowRegistry = await getSceneAnalysisFlowRegistry();
                const configured = flowRegistry?.stage3_auto_start || flowRegistry?.config?.stage3_auto_start || {};
                const storyboardAutoStart = configured?.storyboard_generation !== false;
                
                if (storyboardAutoStart && Array.isArray(importReport?.scenes) && importReport.scenes.length > 0) {
                    if (onLog) onLog('Auto-starting storyboard generation for newly imported scenes...', 'info');
                    setAnalysisFlowStatus({
                        phase: 'completed',
                        message: t('🔄 正在启动分镜自动生成任务...', 'Starting automated storyboard generation...'),
                    });
                    
                    const workflowStarted = await runSceneAnalysisFlowNode({
                        node_key: 'storyboard_generation',
                        project_id: projectId,
                        episode_id: activeEpisode.id,
                        scene_ids: importReport.scenes.map(s => s.id),
                    });
                    
                    aiShotsBatchStarted = !!(workflowStarted?.batch_status || workflowStarted);
                    if (onLog) onLog(`Storyboard generation automatically started.`, 'success');
                }
            } catch (err) {
                if (onLog) onLog(`Failed to auto-start storyboard generation: ${err?.message || err}`, 'warning');
            }

            setPendingSwitchAfterPostChecks(false);
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            const combinedReportWarning = [importWarningMessage, retryResetNotice, preflightSceneSyncNotice]
                .map(item => String(item || '').trim())
                .filter(Boolean)
                .join('；');
            const advancedReviewWarningText = reviewIssues.length > 0 ? buildAnalysisReviewWarningMessage(reviewIssues) : '';

            setAnalysisUiReport(buildCompletedAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport,
                runtimeMeta,
                storyboardAutoStarted: aiShotsBatchStarted,
                warning: [combinedReportWarning, advancedReviewWarningText]
                    .map((item) => String(item || '').trim())
                    .filter(Boolean)
                    .join('\n\n'),
                reviewIssues,
                error: '',
            }));

            const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
            const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
            const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
            const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
            const advancedReviewSuffix = reviewIssues.length > 0
                ? t(`（另有 ${reviewIssues.length} 项待复核，见下方问题列表）`, ` (${reviewIssues.length} issue(s) need review; see list below)`)
                : '';
            
            const appendStoryboardNotice = (baseZh, baseEn) => {
                if (!aiShotsBatchStarted) return t(baseZh, baseEn);
                return t(`${baseZh} 分镜任务已在后台启动。`, `${baseEn} Storyboard generation started in background.`);
            };

            setAnalysisFlowStatus({
                phase: 'completed',
                message: (postImportMissingItems > 0
                    ? (
                        postImportSupplementFailed > 0
                            ? appendStoryboardNotice(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`)
                            : appendStoryboardNotice(`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`)
                    )
                    : appendStoryboardNotice('✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.')) + advancedReviewSuffix,
            });

            setShowAnalysisModal(false);
            analysisPipelineFinished = true;
        } catch (e) {
            console.error(e);
            
            analysisError = e;
            analysisCanceled = isTaskCanceledError(e) || analysisStopRequestedRef.current;
            if (!scriptEditorMountedRef.current) {
                return;
            }

            const friendlyAnalysisError = localizeAnalysisFailureMessage(e?.message || String(e || ''));
            const retainMarker = shouldRetainAnalysisTaskMarker({
                canceled: analysisCanceled,
                error: e,
                mounted: true,
            });
            phaseMarks.completedAt = Date.now();
            const phaseTimings = computeAnalysisPhaseTimings(phaseMarks);
            if (analysisCanceled) {
                if (onLog) onLog('Advanced analysis task canceled by user.', 'warning');
            } else {
                if (onLog) onLog(`Advanced analysis failed: ${friendlyAnalysisError}`);
            }
            setAnalysisFlowStatus(
                analysisCanceled
                    ? { phase: 'warning', message: t('分析任务已停止。', 'Analysis task was stopped.') }
                    : retainMarker
                        ? { phase: 'warning', message: t('分析连接中断，任务仍在后台运行。返回本页后会自动恢复进度。', 'Analysis connection interrupted. The task is still running; return here to resume progress.') }
                        : { phase: 'failed', message: t(`分析失败：${friendlyAnalysisError}`, `Analysis failed: ${friendlyAnalysisError}`) }
            );
            setAnalysisUiReport({
                status: analysisCanceled ? 'warning' : retainMarker ? 'warning' : 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings,
                importReport: importReport,
                runtimeMeta,
                warning: analysisCanceled
                    ? t('分析任务已由用户停止。', 'Analysis task was stopped by user.')
                    : retainMarker
                        ? t('分析连接中断，返回本页后会自动恢复进度。', 'Connection interrupted. Return here to resume progress.')
                        : '',
                error: analysisCanceled || retainMarker ? '' : friendlyAnalysisError,
            });
            if (!analysisCanceled && !retainMarker) {
                alert(`Analysis failed: ${friendlyAnalysisError}`);
            }
        } finally {
            const retainMarker = shouldRetainAnalysisTaskMarker({
                pipelineFinished: analysisPipelineFinished,
                canceled: analysisCanceled,
                error: analysisError,
                mounted: scriptEditorMountedRef.current,
            });
            if (!retainMarker) {
                clearAnalysisTaskMarker(episodeId);
            }
            analysisRunInFlightRef.current = false;
            if (!scriptEditorMountedRef.current) return;
            setIsAnalyzing(false);
            setActiveAnalysisTaskId('');
            analysisStopRequestedRef.current = false;
        }
        };
        const runPromise = runAnalysisPipeline();

        trackEpisodeAnalysisRun(episodeId, runPromise, { startedAt, kind: 'advanced' });
        return runPromise;
    };

    const getStageOutputContent = useCallback((stageKey, outputKey) => {
        return String(currentStageOutputs?.stages?.[stageKey]?.outputs?.[outputKey]?.content || '').trim();
    }, [currentStageOutputs]);

    const getStageInputContent = useCallback((stageKey, inputKey) => {
        return String(currentStageOutputs?.stages?.[stageKey]?.inputs?.[inputKey]?.content || '').trim();
    }, [currentStageOutputs]);

    const buildStage1RestartSourceText = useCallback(() => {
        const adaptedScript = getStageOutputContent('stage1', 'adapted_script');
        const visualBackfillJson = getStageOutputContent('stage1', 'project_visual_backfill');
        const parts = [];
        if (adaptedScript) {
            parts.push(`### 第二部分：修改后的剧本\n${adaptedScript}`);
        } else {
            const rawText = getStageOutputContent('stage1', 'raw_text');
            if (rawText) return rawText;
        }
        if (visualBackfillJson) {
            parts.push(`### Project Visual Backfill\n\n\`\`\`json\n${visualBackfillJson}\n\`\`\``);
        }
        return parts.join('\n\n').trim();
    }, [getStageOutputContent]);

    const handleImportStageArtifact = useCallback(async ({ content = '', importType = 'auto', label = 'stage output', importOptions = {} } = {}) => {
        const text = String(content || '').trim();
        if (!text) return false;
        onLog?.(`Re-importing ${label}...`, 'process');
        const result = await doImportText(text, importType, importOptions);
        if (result) {
            onLog?.(`Re-imported ${label}.`, 'success');
        }
        return result;
    }, [doImportText, onLog]);

    const handleRestoreAdaptedScript = useCallback(async () => {
        const adaptedScript = getStageOutputContent('stage1', 'adapted_script');
        if (!adaptedScript || !activeEpisode?.id || typeof onUpdateScript !== 'function') return;
        await onUpdateScript(activeEpisode.id, adaptedScript);
        setRawContent(adaptedScript);
        setIsRawMode(true);
        onLog?.('Restored Stage 1 adapted script back into the episode script editor.', 'success');
    }, [activeEpisode?.id, getStageOutputContent, onLog, onUpdateScript]);

    const handleRestartStage2 = async () => {
        if (!activeEpisode?.id || isAnalyzing) return;

        const stage1SourceText = buildStage1RestartSourceText();
        if (!stage1SourceText) {
            alert(t('缺少第一阶段产物，无法从第二阶段重跑。', 'Stage 1 outputs are missing, so Stage 2 cannot restart.'));
            return;
        }

        const { adaptedScriptText, userInput: stage2UserInput } = buildStage2UserInputFromStage1(stage1SourceText, selectedReuseSubjectAssets);
        if (!String(adaptedScriptText || '').trim()) {
            alert(t('第一阶段产物里没有可用的改编剧本，无法从第二阶段重跑。', 'No usable adapted script was found in Stage 1 outputs.'));
            return;
        }

        const startedAt = Date.now();
        let importReport = null;
        let runtimeMeta = null;

        setIsAnalyzing(true);
        analysisRunInFlightRef.current = true;
        analysisStopRequestedRef.current = false;
        setAnalysisFlowStatus({
            phase: 'script_opt',
            message: t('正在读取第一阶段产物并重新执行第二阶段。', 'Re-running Stage 2 from saved Stage 1 outputs.'),
        });

        try {
            resetAutoSubjectsImportCache();
            setAdaptationText(adaptedScriptText);

            await purgeEpisodeWorkspaceScenes('restart-stage2-clear');
            if (typeof onUpdateEpisodeInfo === 'function') {
                await onUpdateEpisodeInfo(activeEpisode.id, {
                    ai_scene_analysis_subject_index: '',
                    ai_scene_analysis_scene_markdown: '',
                    ai_entity_design_result: '',
                    scene_content: '',
                });
            }

            const stage2_1PromptRes = await fetchPrompt('skills/scene_analysis_feature_stack/scene_planning_2_1_assets_extraction.md');
            if (onLog) onLog('Restarting Stage 2.1 (Asset Extraction)...', 'info');
            const runStage2_1Attempt = async () => (
                await awaitAnalyzeSceneWithRecovery(
                    () => runScriptAnalysisFlowAnalyzeNode(
                        'assets_extraction',
                        stage2UserInput,
                        stage2_1PromptRes?.content || '',
                        null,
                        activeEpisode?.id || null,
                        analysisAttentionNotes,
                        selectedReuseSubjectAssets,
                        {
                            onTaskCreated: (taskId) => {
                                setActiveAnalysisTaskId(String(taskId || '').trim());
                                saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 2 });
                            },
                        },
                        projectId,
                        'script_analysis',
                        selectedScriptAnalysisApiId
                    ),
                    { startedAt, baselineText: String(activeEpisode?.ai_scene_analysis_result || '').trim() }
                )
            );

            const { result: stage2_1Result, text: stage2_1Text, validation: stage2_1Validation } = await runStage2_1WithValidationRetry(
                runStage2_1Attempt,
                'Stage 2.1 restart'
            );
            const stage2_1SubjectIndexText = String(stage2_1Validation.subjectIndexText || '').trim() || extractPureSubjectIndexText(stage2_1Text).trim() || String(stage2_1Text || '').trim();
            let globalStage2_1Text = stage2_1SubjectIndexText;
            if (onLog) onLog('清单整理完成（重跑场景），开始并发执行：场景拆解 + 视觉资产生成。', 'info');

            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('📝 正在并发执行：场景拆解与视觉资产生成...', 'Running scene breakdown and visual asset generation in parallel...'),
            });

                        const runStage2_2Task = async () => {
                let stage2_2UserInputBody = buildStage2_2UserInputFromStage1(stage1SourceText);
                let finalStage2_2UserInput = stage2_2UserInputBody;

                return runStage2_2WithValidationRetry({
                    label: 'Stage 2.2 restart',
                    logPhasePrefix: 'restart',
                    finalStage2_2UserInput,
                    stage2_2UserInputBody,
                    stage2_1SubjectIndexText,
                    stage1SourceText,
                    startedAt,
                    baselineText: String(activeEpisode?.ai_scene_analysis_result || '').trim(),
                    onTaskCreated: (taskId) => {
                        setActiveAnalysisTaskId(String(taskId || '').trim());
                        saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 'scene_beats' });
                    },
                });
            };

                        const runStage3Task = async () => {
                try {
                                return await runPostImportSceneSubjectPipeline(null, globalStage2_1Text || stage2_1SubjectIndexText, {
                                    explicitSubjectIndexText: globalStage2_1Text || stage2_1SubjectIndexText
                    });
                } catch (e) {
                    if (onLog) onLog(`Stage 3 background execution failed: ${e?.message || e}`, 'error');
                    return null;
                }
            };

            const beatsPromise = runStage2_2Task();
            const assetsPromise = runStage3Task();

            const beatsResult = await beatsPromise;
            const {
                stage2_2Text,
                stage2_2Result,
                perSceneParallel = false,
                sceneMarkdownPatchMap = null,
            } = beatsResult || {};

            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('✅ 场景编排 LLM 已返回，正在第一时间回写结果...', 'Scene beats LLM returned. Writing back results immediately...'),
            });
            onLog?.('[Task:Stage 2 Restart] [Phase:scene_beats_llm_returned] Stage 2.2 returned. Applying UI update and immediate writeback.', 'info');

            const stage2Text = perSceneParallel
                ? String(stage2_1Text || '').trim()
                : [String(stage2_1Text || '').trim(), String(stage2_2Text || '').trim()].filter(Boolean).join('\n\n');
            let validatedBeatsText = '';
            let restartScenePatchMap = null;

            if (perSceneParallel && sceneMarkdownPatchMap && Object.keys(sceneMarkdownPatchMap).length > 0) {
                restartScenePatchMap = sceneMarkdownPatchMap;
            } else {
                const finalAnalysisText = String(stage2_2Text || '').trim();
                const stage2_2Check = validateStage2_2BeatsOutput(finalAnalysisText, 'Stage 2.2 restart');
                if (!stage2_2Check.ok) {
                    throw new Error(stage2_2Check.reason || 'Stage 2.2 Beats Generation validation failed (restart mode): returned table lacks Scene ID column (may have received Subject Index instead of Scenes Table). Please retry.');
                }
                validatedBeatsText = stage2_2Check.normalizedText;
            }
            
            const stage2Result = {
                ...(stage2_1Result || {}),
                ...(stage2_2Result || {}),
                meta: stage2_2Result?.meta || stage2_1Result?.meta,
                subjects_json: stage2_1Result?.subjects_json || stage2_2Result?.subjects_json,
            };

            const analysisSections = extractAnalysisSections(stage2Text);
            if (!analysisSections.hasStructuredSubjectIndex) {
                throw new Error(SUBJECT_INDEX_PARSE_ERROR);
            }

            if (!restartScenePatchMap) {
                setLlmRawResultContent(validatedBeatsText);
                setLlmResultContent(validatedBeatsText);
                lastLoadedAnalysisRef.current = validatedBeatsText;
            }

            if (stage2Result?.meta) {
                runtimeMeta = extractAnalysisRuntimeMeta(stage2Result.meta);
                setAnalysisRuntimeMeta(runtimeMeta);
            }

            setAnalysisUiReport((prev) => ({
                ...(prev && typeof prev === 'object' ? prev : {}),
                status: 'running',
                startedAt,
                durationMs: Date.now() - startedAt,
                runtimeMeta,
                warning: '',
                error: '',
            }));

            if (restartScenePatchMap) {
                await persistSceneMarkdownPatch(restartScenePatchMap, {
                    source: 'restart-stage2-per-scene',
                    stage1RawText: stage1SourceText,
                    stage2_1Text: stage2_1Text || undefined,
                    replaceSceneMarkdownByScene: true,
                });
            } else {
                await persistSceneMarkdownBundle(validatedBeatsText, {
                    source: 'restart-stage2',
                    stage1RawText: stage1SourceText,
                    stage2RawText: [String(stage2_1Text || '').trim(), String(validatedBeatsText || '').trim()].filter(Boolean).join('\n\n'),
                    stage2_1Text: stage2_1Text || undefined,
                });
            }
            onLog?.('[Task:Stage 2 Restart] [Phase:writeback] Scene beats result persisted with per-scene storage.', 'success');
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('🧩 场景编排已回写，正在导入场景表到工作区...', 'Scene beats written back, importing scene table to workspace...'),
            });

            try {
                if (restartScenePatchMap) {
                    importReport = await importScenesFromPerScenePatchMap(restartScenePatchMap, {
                        replaceExistingScenes: true,
                    });
                } else {
                    importReport = await runAutoImportAndSwitchToScenes(validatedBeatsText, {
                        switchToScenes: false,
                        importOptions: {
                            autoSupplementSceneSubjects: false,
                            suppressAlerts: true,
                            subjectsJson: stage2Result?.subjects_json || null,
                        },
                    });
                }
                if (!importReport) {
                    await triggerSceneArrangementRegenerationTask(validatedBeatsText, {
                        reason: t('自动导入未返回结果，请检查导入配置或返回格式。', 'Auto-import returned no result.'),
                        source: 'stage2-restart-empty-import',
                    });
                }
            } catch (importErr) {
                await triggerSceneArrangementRegenerationTask(validatedBeatsText, {
                    reason: t(`自动导入失败：${importErr?.message || importErr}`, `Auto-import failed: ${importErr?.message || importErr}`),
                    source: 'stage2-restart-import-error',
                });
                throw importErr;
            }
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('✅ 场景编排导入完成，正在继续资产后处理...', 'Scene beats import completed, continuing asset post-processing...'),
            });
            importReport = await ensureSubjectsImportedBeforePostChecks(stage2Result, importReport);
            maybeAlertIncompleteSubjectsImport(stage2Result, validatedBeatsText);

            const assetsOutcome = await assetsPromise
                .then((value) => ({ status: 'fulfilled', value }))
                .catch((reason) => ({ status: 'rejected', reason }));
            const postImportSceneSubjectReport = assetsOutcome.status === 'fulfilled' ? assetsOutcome.value : null;

            if (importReport && typeof importReport === 'object' && postImportSceneSubjectReport) {
                const mergedRestartScenePostReport = syncScenePostImportCheckedCount(importReport, postImportSceneSubjectReport);
                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: mergedRestartScenePostReport,
                };
            }

            setAnalysisUiReport(buildCompletedAnalysisUiReport({
            
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings: null,
                importReport,
                runtimeMeta,
                warning: '',
                error: '',
            }));
            setAnalysisFlowStatus({
                phase: 'completed',
                message: t('已基于第一阶段产物重新完成第二、三阶段。', 'Stage 2 and Stage 3 completed from saved Stage 1 outputs.'),
            });
            onLog?.('Stage 2 restart completed using saved Stage 1 outputs.', 'success');
        } catch (error) {
            const friendlyError = localizeAnalysisFailureMessage(error?.message || String(error));
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`第二阶段重跑失败：${friendlyError}`, `Stage 2 restart failed: ${friendlyError}`),
            });
            setAnalysisUiReport({
                status: 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings: null,
                importReport,
                runtimeMeta,
                warning: '',
                error: friendlyError,
            });
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`第二阶段重跑失败：${friendlyError}`, `Stage 2 restart failed: ${friendlyError}`),
            });
            onLog?.(`Stage 2 restart failed: ${friendlyError}`, 'error');
            alert(t(`第二阶段重跑失败：${friendlyError}`, `Stage 2 restart failed: ${friendlyError}`));
        } finally {
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsAnalyzing(false);
            setActiveAnalysisTaskId('');
            analysisStopRequestedRef.current = false;
            analysisRunInFlightRef.current = false;
        }
    };

    const resolveSceneBeatsRerunCandidates = useCallback(() => {
        const stage1SourceText = buildStage1RestartSourceText();
        const adaptedScriptText = extractStage1AdaptedScriptBody(stage1SourceText);
        if (!String(adaptedScriptText || '').trim()) {
            return { stage1SourceText, candidates: [], error: 'missing_adapted_script' };
        }
        try {
            const candidates = parseSceneUnitsFromScriptMarkers(adaptedScriptText).map((unit) => ({
                ...unit,
                displayLabel: extractSceneDisplayLabel(unit),
            }));
            return { stage1SourceText, candidates, error: candidates.length ? '' : 'no_scene_markers' };
        } catch (error) {
            return {
                stage1SourceText,
                candidates: [],
                error: error?.message || String(error || 'scene_marker_parse_error'),
            };
        }
    }, [buildStage1RestartSourceText, extractSceneDisplayLabel, extractStage1AdaptedScriptBody, parseSceneUnitsFromScriptMarkers]);

    const executeSceneBeatsRerun = useCallback(async ({ mode = 'all', sceneId = '' } = {}) => {
        if (!activeEpisode?.id || isAnalyzing) return;

        const { stage1SourceText, candidates, error: candidateError } = resolveSceneBeatsRerunCandidates();
        if (!stage1SourceText) {
            alert(t('缺少第一阶段产物，无法仅重排场景。', 'Stage 1 outputs are missing, so scene-beats-only rerun cannot start.'));
            return;
        }
        if (candidateError === 'missing_adapted_script') {
            alert(t('第一阶段产物里没有可用的改编剧本，无法仅重排场景。', 'No usable adapted script was found in Stage 1 outputs.'));
            return;
        }
        if (!candidates.length) {
            alert(
                candidateError
                    ? t(`无法按场景分隔符切分剧本：${candidateError}`, `Failed to split script by scene markers: ${candidateError}`)
                    : t('剧本中未找到 [SCENE_START]/[SCENE_END] 场景分隔符，无法按场重排。', 'No [SCENE_START]/[SCENE_END] scene markers found; per-scene rerun is unavailable.')
            );
            return;
        }

        const stage2_1Text = String(
            getStageOutputContent('stage2', 'subject_index')
            || activeEpisode?.ai_scene_analysis_subject_index
            || ''
        ).trim();
        const stage2_1SubjectIndexText = extractPureSubjectIndexText(stage2_1Text).trim() || stage2_1Text;
        if (!stage2_1SubjectIndexText) {
            alert(t('缺少第二阶段资产清单，无法仅重排场景。请先执行资产提取。', 'Missing Stage 2 subject index. Please run asset extraction first.'));
            return;
        }

        const rerunMode = String(mode || 'all').trim().toLowerCase() === 'single' ? 'single' : 'all';
        const targetSceneId = String(sceneId || '').trim();
        const targetSceneUnits = rerunMode === 'single'
            ? candidates.filter((unit) => String(unit.sceneId || '').trim() === targetSceneId)
            : null;
        if (rerunMode === 'single' && !targetSceneUnits?.length) {
            alert(t('未找到所选场景，无法重排。', 'Selected scene was not found; rerun cannot start.'));
            return;
        }

        const startedAt = Date.now();
        let importReport = null;
        let runtimeMeta = null;
        const rerunLabel = rerunMode === 'single'
            ? `Stage 2.2 scene-only rerun [${targetSceneId}]`
            : 'Stage 2.2 scene-only rerun (sync orchestration)';
        const orchestrationSceneCount = rerunMode === 'single' ? 1 : candidates.length;

        analysisProgressDismissedRef.current = false;
        setIsAnalyzing(true);
        analysisRunInFlightRef.current = true;
        analysisStopRequestedRef.current = false;
        setAnalysisFlowStatus({
            phase: 'scene_beats',
            message: rerunMode === 'single'
                ? t(`正在重排单个场景：${targetSceneId}...`, `Rerunning scene beats for ${targetSceneId}...`)
                : t(`正在同步发起全部 ${orchestrationSceneCount} 场场景编排...`, `Sync-launching all ${orchestrationSceneCount} scene beats...`),
        });
        sceneBeatsOnlyRerunInFlightRef.current = true;
        onLog?.(
            rerunMode === 'single'
                ? `进入仅场景重排模式（单场）：${targetSceneId}`
                : `进入仅场景重排模式（全部 ${orchestrationSceneCount} 场，同步发起后端编排）`,
            'info'
        );

        try {
            const rerunSceneIds = rerunMode === 'single'
                ? [targetSceneId]
                : candidates.map((unit) => String(unit.sceneId || '').trim()).filter(Boolean);
            if (projectId && activeEpisode?.id && rerunSceneIds.length > 0) {
                try {
                    await resetSceneOrchestrationProgress({
                        project_id: Number(projectId),
                        episode_id: Number(activeEpisode.id),
                        scene_ids: rerunSceneIds,
                    });
                    await clearSceneMarkdownPatchForScenes(rerunSceneIds, {
                        source: rerunMode === 'single' ? 'restart-scene-beats-only-single-clear' : 'restart-scene-beats-only-all-clear',
                        stage1RawText: stage1SourceText,
                        stage2_1Text: stage2_1Text || undefined,
                    });
                    onLog?.(`已清理 ${rerunSceneIds.length} 场场景编排过程数据，等待 LLM 返回新结果。`, 'info');
                } catch (clearErr) {
                    onLog?.(`场景编排过程数据清理警告：${clearErr?.message || clearErr}`, 'warning');
                }
            }

            const stage2_2UserInputBody = buildStage2_2UserInputFromStage1(stage1SourceText);
            const finalStage2_2UserInput = stage2_2UserInputBody;

            const beatsOutcome = await runStage2_2WithValidationRetry({
                label: rerunLabel,
                logPhasePrefix: rerunMode === 'single' ? 'scene-only-single' : 'scene-only-all',
                finalStage2_2UserInput,
                stage2_2UserInputBody,
                stage2_1SubjectIndexText,
                stage1SourceText,
                targetSceneUnits,
                startedAt,
                baselineText: String(activeEpisode?.ai_scene_analysis_result || '').trim(),
                sceneAnalysisModePayload: 'scene_beats_only',
                onTaskCreated: (taskId) => {
                    setActiveAnalysisTaskId(String(taskId || '').trim());
                    saveAnalysisTaskMarker(activeEpisode?.id, { taskId, startedAt, phase: 'scene_beats' });
                },
            });
            const {
                stage2_2Text,
                stage2_2Result: stage2_2ResultObj,
                perSceneParallel = false,
                sceneMarkdownPatchMap = null,
            } = beatsOutcome || {};

            let validatedBeatsText = stage2_2Text;
            const singleSceneOutputText = String(stage2_2Text || '').trim();
            let singleScenePatchMap = null;
            let singleSceneImportText = '';
            const allScenePatchMap = perSceneParallel ? sceneMarkdownPatchMap : null;

            if (rerunMode === 'single') {
                const singleSceneCheck = validateStage2_2BeatsOutput(singleSceneOutputText, `${rerunLabel} single`);
                if (!singleSceneCheck.ok) {
                    throw new Error(singleSceneCheck.reason || t('单场场景表校验失败，无法回写分集。', 'Single-scene table validation failed; cannot write back to episode.'));
                }
                const targetUnit = targetSceneUnits?.[0];
                singleSceneImportText = patchSceneTableRowIdentity(singleSceneCheck.normalizedText, {
                    sceneId: targetSceneId,
                    sceneOrder: targetUnit?.sceneOrder,
                });
                const splitPatch = splitSceneMarkdownTableBySceneId(singleSceneImportText);
                const patchEntry = splitPatch[targetSceneId] || Object.values(splitPatch)[0];
                singleScenePatchMap = {
                    [targetSceneId]: {
                        ...(patchEntry && typeof patchEntry === 'object' ? patchEntry : {}),
                        scene_id: targetSceneId,
                        scene_order: targetUnit?.sceneOrder ?? patchEntry?.scene_order,
                        scene_name: extractSceneDisplayLabel(targetUnit) || patchEntry?.scene_name,
                        markdown: singleSceneImportText,
                        updated_at: new Date().toISOString(),
                    },
                };
            }

            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('✅ 场景编排 LLM 已返回，正在第一时间回写结果...', 'Scene beats LLM returned. Writing back results immediately...'),
            });
            onLog?.('场景拆解结果已返回，正在更新界面并立即回写。', 'info');

            if (stage2_2ResultObj?.meta) {
                runtimeMeta = extractAnalysisRuntimeMeta(stage2_2ResultObj.meta);
                setAnalysisRuntimeMeta(runtimeMeta);
            }

            if (rerunMode === 'single') {
                await persistSceneMarkdownPatch(singleScenePatchMap, {
                    source: 'restart-scene-beats-only-single',
                    stage1RawText: stage1SourceText,
                    stage2_1Text: stage2_1Text || undefined,
                });
            } else if (allScenePatchMap && Object.keys(allScenePatchMap).length > 0) {
                await persistSceneMarkdownPatch(allScenePatchMap, {
                    source: 'restart-scene-beats-only-all',
                    stage1RawText: stage1SourceText,
                    stage2_1Text: stage2_1Text || undefined,
                    replaceSceneMarkdownByScene: true,
                });
            } else {
                setLlmRawResultContent(validatedBeatsText);
                setLlmResultContent(validatedBeatsText);
                lastLoadedAnalysisRef.current = validatedBeatsText;

                const sceneMarkdownPatch = splitSceneMarkdownTableBySceneId(validatedBeatsText);
                await persistSceneMarkdownBundle(validatedBeatsText, {
                    source: 'restart-scene-beats-only-all',
                    stage1RawText: stage1SourceText,
                    stage2RawText: [String(stage2_1Text || '').trim(), String(validatedBeatsText || '').trim()].filter(Boolean).join('\n\n'),
                    stage2_1Text: stage2_1Text || undefined,
                    sceneMarkdownByScene: sceneMarkdownPatch,
                });
            }
            onLog?.(rerunMode === 'single'
                ? `场景 ${targetSceneId} 拆解结果已回写到分集（仅该场分场景存储）。`
                : (allScenePatchMap && Object.keys(allScenePatchMap).length > 0)
                    ? `全部 ${Object.keys(allScenePatchMap).length} 场场景拆解结果已分别回写到分集（分场景存储）。`
                    : '场景拆解结果已回写到分集记录（含分场景存储）。', 'success');
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: rerunMode === 'single'
                    ? t('🧩 单场结果已回写，正在导入该场景到数据库...', 'Single-scene result saved, importing scene to database...')
                    : t('🧩 场景编排已回写，正在导入场景表到工作区...', 'Scene beats written back, importing scene table to workspace...'),
            });

            if (rerunMode === 'single') {
                importReport = await doImportText(singleSceneImportText, 'scene', {
                    suppressAlerts: true,
                    autoSupplementSceneSubjects: false,
                });
                if (projectId && activeEpisode?.id) {
                    try {
                        await syncSceneUnitsProgress({
                            project_id: Number(projectId),
                            episode_id: Number(activeEpisode.id),
                            script_text: singleSceneImportText,
                            partial: true,
                            target_scene_id: targetSceneId,
                        });
                    } catch (syncErr) {
                        onLog?.(`[Scene Units Sync] warning: ${syncErr?.message || syncErr}`, 'warning');
                    }
                }
            } else if (allScenePatchMap && Object.keys(allScenePatchMap).length > 0) {
                importReport = await importScenesFromPerScenePatchMap(allScenePatchMap, {
                    replaceExistingScenes: rerunMode === 'all',
                });
            } else if (rerunMode === 'all' && orchestrationSceneCount > 1) {
                throw new Error(t(
                    '全部场景重排未获得完整的分场景 LLM 结果，已中止导入以避免写入旧数据。',
                    'All-scene rerun did not receive complete per-scene LLM outputs; import aborted to avoid stale data.'
                ));
            } else {
                importReport = await runAutoImportAndSwitchToScenes(validatedBeatsText, {
                    switchToScenes: false,
                    importOptions: {
                        autoSupplementSceneSubjects: false,
                        suppressAlerts: true,
                        subjectsJson: null,
                    },
                });
            }
            setAnalysisFlowStatus({
                phase: 'scene_beats',
                message: t('✅ 场景编排导入完成，正在更新任务状态...', 'Scene beats import completed, updating task status...'),
            });

            setAnalysisUiReport(buildCompletedAnalysisUiReport({
                status: 'completed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings: null,
                importReport,
                runtimeMeta,
                warning: '',
                error: '',
                runTag: 'scene_beats_only_rerun',
            }));

            setAnalysisFlowStatus({
                phase: 'completed',
                message: rerunMode === 'single'
                    ? t(`场景 ${targetSceneId} 编排已重排完成。`, `Scene ${targetSceneId} beats rerun completed.`)
                    : t(`全部 ${orchestrationSceneCount} 场场景编排已重排完成。`, `All ${orchestrationSceneCount} scene beats reruns completed.`),
            });
            onLog?.(rerunMode === 'single' ? `单场场景重排完成：${targetSceneId}` : `全部场景重排完成（${orchestrationSceneCount} 场，同步编排）`, 'success');
        } catch (error) {
            const friendlyError = localizeAnalysisFailureMessage(error?.message || String(error));
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`场景重排失败：${friendlyError}`, `Scene beats rerun failed: ${friendlyError}`),
            });
            setAnalysisUiReport({
                status: 'failed',
                startedAt,
                durationMs: Date.now() - startedAt,
                phaseTimings: null,
                importReport,
                runtimeMeta,
                warning: '',
                error: friendlyError,
                runTag: 'scene_beats_only_rerun',
            });
            onLog?.(`仅场景重排失败：${friendlyError}`, 'error');
            alert(t(`场景重排失败：${friendlyError}`, `Scene beats rerun failed: ${friendlyError}`));
        } finally {
            sceneBeatsOnlyRerunInFlightRef.current = false;
            onLog?.('已退出仅场景重排模式。', 'info');
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsAnalyzing(false);
            setActiveAnalysisTaskId('');
            analysisStopRequestedRef.current = false;
            analysisRunInFlightRef.current = false;
        }
    }, [
        activeEpisode?.ai_scene_analysis_result,
        activeEpisode?.ai_scene_analysis_subject_index,
        activeEpisode?.id,
        buildStage2_2UserInputFromStage1,
        buildCompletedAnalysisUiReport,
        clearAnalysisTaskMarker,
        clearSceneMarkdownPatchForScenes,
        extractPureSubjectIndexText,
        extractSceneDisplayLabel,
        getStageOutputContent,
        importScenesFromPerScenePatchMap,
        isAnalyzing,
        localizeAnalysisFailureMessage,
        doImportText,
        onLog,
        patchSceneTableRowIdentity,
        persistSceneMarkdownBundle,
        persistSceneMarkdownPatch,
        projectId,
        resolveSceneBeatsRerunCandidates,
        resetSceneOrchestrationProgress,
        runAutoImportAndSwitchToScenes,
        runStage2_2WithValidationRetry,
        saveAnalysisTaskMarker,
        setAnalysisFlowStatus,
        setAnalysisRuntimeMeta,
        splitSceneMarkdownTableBySceneId,
        syncSceneUnitsProgress,
        setAnalysisUiReport,
        setIsAnalyzing,
        setLlmRawResultContent,
        setLlmResultContent,
        splitSceneMarkdownTableBySceneId,
        t,
        validateStage2_2BeatsOutput,
    ]);

    const sceneBeatsRerunCandidates = useMemo(() => {
        const { candidates } = resolveSceneBeatsRerunCandidates();
        return candidates;
    }, [resolveSceneBeatsRerunCandidates, activeEpisode?.id, activeEpisode?.ai_scene_analysis_adaptation, activeEpisode?.ai_stage_outputs]);

    const openSceneBeatsRerunModal = useCallback(() => {
        if (!activeEpisode?.id || isAnalyzing) return;

        const { stage1SourceText, candidates, error: candidateError } = resolveSceneBeatsRerunCandidates();
        if (!stage1SourceText) {
            alert(t('缺少第一阶段产物，无法仅重排场景。', 'Stage 1 outputs are missing, so scene-beats-only rerun cannot start.'));
            return;
        }
        if (candidateError === 'missing_adapted_script') {
            alert(t('第一阶段产物里没有可用的改编剧本，无法仅重排场景。', 'No usable adapted script was found in Stage 1 outputs.'));
            return;
        }
        if (!candidates.length) {
            alert(
                candidateError
                    ? t(`无法按场景分隔符切分剧本：${candidateError}`, `Failed to split script by scene markers: ${candidateError}`)
                    : t('剧本中未找到 [SCENE_START]/[SCENE_END] 场景分隔符，无法按场重排。', 'No [SCENE_START]/[SCENE_END] scene markers found; per-scene rerun is unavailable.')
            );
            return;
        }

        const stage2_1Text = String(
            getStageOutputContent('stage2', 'subject_index')
            || activeEpisode?.ai_scene_analysis_subject_index
            || ''
        ).trim();
        const stage2_1SubjectIndexText = extractPureSubjectIndexText(stage2_1Text).trim() || stage2_1Text;
        if (!stage2_1SubjectIndexText) {
            alert(t('缺少第二阶段资产清单，无法仅重排场景。请先执行资产提取。', 'Missing Stage 2 subject index. Please run asset extraction first.'));
            return;
        }

        setSceneBeatsRerunModal({
            open: true,
            mode: candidates.length === 1 ? 'single' : 'all',
            sceneId: candidates[0]?.sceneId || '',
        });
    }, [
        activeEpisode?.ai_scene_analysis_subject_index,
        activeEpisode?.id,
        extractPureSubjectIndexText,
        getStageOutputContent,
        isAnalyzing,
        resolveSceneBeatsRerunCandidates,
        t,
    ]);

    const confirmSceneBeatsRerunSelection = useCallback(async () => {
        const mode = String(sceneBeatsRerunModal.mode || 'all').trim().toLowerCase() === 'single' ? 'single' : 'all';
        const sceneId = String(sceneBeatsRerunModal.sceneId || '').trim();
        if (mode === 'single' && !sceneId) {
            alert(t('请先选择要重排的场景。', 'Select a scene to rerun first.'));
            return;
        }
        setSceneBeatsRerunModal((prev) => ({ ...prev, open: false }));
        await executeSceneBeatsRerun({ mode, sceneId });
    }, [executeSceneBeatsRerun, sceneBeatsRerunModal.mode, sceneBeatsRerunModal.sceneId, t]);

    const handleRerunSceneBeatsOnly = openSceneBeatsRerunModal;

    const handleRerunFailedAssetSubtasks = useCallback(async () => {
        if (isAnalyzing || phase2GenerationInFlightRef.current) return;

        const subtaskReports = Array.isArray(analysisUiReport?.importReport?.sceneSubjectPostImportReport?.subtaskReports)
            ? analysisUiReport.importReport.sceneSubjectPostImportReport.subtaskReports
            : [];
        const failedReports = subtaskReports.filter((item) => String(item?.status || '').trim().toLowerCase() !== 'ok');

        if (failedReports.length <= 0) {
            onLog?.('No failed subtask route found for rerun.', 'info');
            setAnalysisFlowStatus({
                phase: 'warning',
                message: t('当前没有失败子任务可重跑。', 'No failed subtask route found to rerun.'),
            });
            return;
        }

        const targetTypeSet = new Set();
        failedReports.forEach((item) => {
            const key = String(item?.key || '').trim().toLowerCase();
            if (key === 'characters') targetTypeSet.add('characters');
            else if (key === 'props') targetTypeSet.add('props');
            else if (key === 'environments') {
                targetTypeSet.add('environments');
                targetTypeSet.add('posters');
                targetTypeSet.add('covers');
            } else if (key === 'posters' || key === 'covers') {
                targetTypeSet.add('posters');
                targetTypeSet.add('covers');
            }
        });

        const targetEntityTypes = Array.from(targetTypeSet);
        if (targetEntityTypes.length <= 0) {
            onLog?.('Failed subtask routes were found but no recognized target types were resolved.', 'warning');
            return;
        }

        const subjectIndexFromEpisode = extractPureSubjectIndexText(String(activeEpisode?.ai_scene_analysis_subject_index || '').trim());
        const fallbackSections = extractAnalysisSections(String(llmRawResultContent || llmResultContent || ''));
        const subjectIndexFallback = extractPureSubjectIndexText(String(fallbackSections?.subjectIndexText || '').trim());
        const subjectIndexText = String(subjectIndexFromEpisode || subjectIndexFallback || '').trim();

        if (!subjectIndexText) {
            alert(t('缺少第二阶段资产清单，无法仅重跑失败子任务。请先重新执行第二阶段。', 'Missing Stage 2 subject index. Cannot rerun failed subtask routes only.'));
            return;
        }

        const confirmed = await confirmUiMessage(t(
            `检测到 ${failedReports.length} 条失败路由，将仅重跑：${targetEntityTypes.join(', ')}。是否继续？`,
            `Detected ${failedReports.length} failed routes. Rerun only: ${targetEntityTypes.join(', ')}. Continue?`
        ));
        if (!confirmed) return;

        analysisStopRequestedRef.current = false;
        activeAnalysisTaskIdsRef.current.clear();
        setActiveAnalysisTaskId('');
        setIsRetryingPhase2(true);
        setAnalysisFlowStatus({
            phase: 'assets_gen',
            message: t('正在重跑失败子任务路由（仅失败路由）...', 'Rerunning failed asset subtask routes only...'),
        });

        try {
            const rerunReport = await runPostImportSceneSubjectPipeline(null, subjectIndexText, {
                explicitSubjectIndexText: subjectIndexText,
                isRetryPhase2: true,
                targetEntityTypes,
            });

            setAnalysisUiReport((prev) => {
                const prevReport = (prev && typeof prev === 'object') ? prev : {};
                const prevImport = (prevReport.importReport && typeof prevReport.importReport === 'object') ? prevReport.importReport : {};
                const prevScenePost = (prevImport.sceneSubjectPostImportReport && typeof prevImport.sceneSubjectPostImportReport === 'object')
                    ? prevImport.sceneSubjectPostImportReport
                    : {};
                const nextScenePost = (rerunReport && typeof rerunReport === 'object') ? rerunReport : {};

                const prevSubtasks = Array.isArray(prevScenePost.subtaskReports) ? prevScenePost.subtaskReports : [];
                const nextSubtasks = Array.isArray(nextScenePost.subtaskReports) ? nextScenePost.subtaskReports : [];
                const mergedSubtaskMap = new Map();
                prevSubtasks.forEach((item) => {
                    const key = String(item?.key || item?.traceId || Math.random()).trim();
                    if (key) mergedSubtaskMap.set(key, item);
                });
                nextSubtasks.forEach((item) => {
                    const key = String(item?.key || item?.traceId || Math.random()).trim();
                    if (key) mergedSubtaskMap.set(key, item);
                });

                const mergedImportedCounts = {
                    character: Number(prevImport?.importedSubjectCounts?.character || 0) + Number(nextScenePost?.importedSubjectCounts?.character || 0),
                    prop: Number(prevImport?.importedSubjectCounts?.prop || 0) + Number(nextScenePost?.importedSubjectCounts?.prop || 0),
                    environment: Number(prevImport?.importedSubjectCounts?.environment || 0) + Number(nextScenePost?.importedSubjectCounts?.environment || 0),
                    poster: Number(prevImport?.importedSubjectCounts?.poster || 0) + Number(nextScenePost?.importedSubjectCounts?.poster || 0),
                };

                const prevSupplement = (prevScenePost?.supplementReport && typeof prevScenePost.supplementReport === 'object')
                    ? prevScenePost.supplementReport
                    : {};
                const nextSupplement = (nextScenePost?.supplementReport && typeof nextScenePost.supplementReport === 'object')
                    ? nextScenePost.supplementReport
                    : {};

                const mergedScenePost = {
                    ...prevScenePost,
                    ...nextScenePost,
                    subtaskReports: Array.from(mergedSubtaskMap.values()),
                    supplementReport: {
                        ...prevSupplement,
                        ...nextSupplement,
                        createdItems: [
                            ...(Array.isArray(prevSupplement.createdItems) ? prevSupplement.createdItems : []),
                            ...(Array.isArray(nextSupplement.createdItems) ? nextSupplement.createdItems : []),
                        ],
                        skippedItems: [
                            ...(Array.isArray(prevSupplement.skippedItems) ? prevSupplement.skippedItems : []),
                            ...(Array.isArray(nextSupplement.skippedItems) ? nextSupplement.skippedItems : []),
                        ],
                        failedItems: [
                            ...(Array.isArray(prevSupplement.failedItems) ? prevSupplement.failedItems : []),
                            ...(Array.isArray(nextSupplement.failedItems) ? nextSupplement.failedItems : []),
                        ],
                    },
                };

                return {
                    ...prevReport,
                    status: 'completed',
                    importReport: {
                        ...prevImport,
                        sceneSubjectPostImportReport: mergedScenePost,
                        importedSubjectCounts: mergedImportedCounts,
                        dbPersistedCounts: nextScenePost?.dbPersistedCounts || prevImport?.dbPersistedCounts,
                        dbRunInsertedCounts: nextScenePost?.dbRunInsertedCounts || prevImport?.dbRunInsertedCounts,
                    },
                };
            });

            const created = Number(rerunReport?.supplementReport?.createdItems?.length || 0);
            const skipped = Number(rerunReport?.supplementReport?.skippedItems?.length || 0);
            const failed = Number(rerunReport?.supplementReport?.failedItems?.length || 0);

            setAnalysisFlowStatus({
                phase: failed > 0 ? 'warning' : 'completed',
                message: failed > 0
                    ? t(`失败路由重跑完成：新增 ${created}，跳过 ${skipped}，仍失败 ${failed}。`, `Failed-route rerun completed: created ${created}, skipped ${skipped}, still failed ${failed}.`)
                    : t(`失败路由重跑完成：新增 ${created}，跳过 ${skipped}。`, `Failed-route rerun completed: created ${created}, skipped ${skipped}.`),
            });
            onLog?.(`Failed-route rerun completed: targets=${targetEntityTypes.join(',')} created=${created} skipped=${skipped} failed=${failed}`, failed > 0 ? 'warning' : 'success');
        } catch (error) {
            if (isTaskCanceledError(error) || analysisStopRequestedRef.current) {
                setAnalysisFlowStatus({
                    phase: 'warning',
                    message: t('已中断失败路由重跑。', 'Failed-route rerun was stopped.'),
                });
                onLog?.('Failed-route rerun stopped by user.', 'warning');
                return;
            }
            const detail = String(error?.message || error || 'unknown error');
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`失败路由重跑失败：${detail}`, `Failed-route rerun failed: ${detail}`),
            });
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`失败路由重跑失败：${detail}`, `Failed-route rerun failed: ${detail}`),
            });
            onLog?.(`Failed-route rerun failed: ${detail}`, 'error');
            alert(t(`失败路由重跑失败：${detail}`, `Failed-route rerun failed: ${detail}`));
        } finally {
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsRetryingPhase2(false);
        }
    }, [
        isAnalyzing,
        analysisUiReport,
        activeEpisode?.id,
        activeEpisode?.ai_scene_analysis_subject_index,
        clearAnalysisTaskMarker,
        llmRawResultContent,
        llmResultContent,
        onLog,
        t,
        extractPureSubjectIndexText,
        extractAnalysisSections,
        confirmUiMessage,
        runPostImportSceneSubjectPipeline,
        isTaskCanceledError,
    ]);


    const phase2RetryOptionsRef = useRef({});

    const handleRetryPhase2 = async (options = {}) => {
        if (!activeEpisode?.id) return;
        const autoZeroCaller = Boolean(options?.autoZeroReportRerun);
        if (phase2GenerationInFlightRef.current || (analysisFallbackRetryRef.current.running && !autoZeroCaller)) {
            onLog?.('[Stage 3 Asset Design] Skipped duplicate asset rerun while Stage 3 is already running.', 'warning');
            return;
        }
        if (options?.autoZeroReportRerun) {
            if (!canAttemptAnalysisFallback(activeEpisode.id, 'asset_gen')) {
                onLog?.(
                    `[Auto Zero Report Rerun] skipped: asset fallback retry limit reached (max ${MAX_ANALYSIS_FALLBACK_ATTEMPTS}).`,
                    'warning'
                );
                return;
            }
            recordAnalysisFallbackAttempt(activeEpisode.id, 'asset_gen');
            const reportKey = `${activeEpisode.id}:${analysisUiReport?.startedAt || 0}:${analysisUiReport?.durationMs || 0}:${String(analysisUiReport?.runTag || '').trim().toLowerCase()}`;
            autoZeroReportHandledRef.current = { key: reportKey, handledAt: Date.now() };
            persistAnalysisSessionSnapshot(activeEpisode.id);
        }
        phase2RetryOptionsRef.current = options;
        analysisStopRequestedRef.current = false;
        analysisProgressDismissedRef.current = false;
        activeAnalysisTaskIdsRef.current.clear();
        setActiveAnalysisTaskId('');
        setIsRetryingPhase2(true);
        clearAnalysisTaskMarker(activeEpisode?.id);
        try {
            resetAutoSubjectsImportCache();
            onLog?.(`Retrying Stage 3 asset design... targetTypes: ${options.targetEntityTypes ? options.targetEntityTypes.join(',') : 'all'}`, 'process');
            const resolvedSubjectIndexText = extractPureSubjectIndexText(String(
                options.explicitSubjectIndexText
                || subjectIndexText
                || activeEpisode?.ai_scene_analysis_subject_index
                || getStageOutputContent('stage2', 'subject_index')
                || ''
            ).trim());
            if (!resolvedSubjectIndexText) {
                throw new Error(t('缺少第二阶段资产清单，无法重跑资产生成。', 'Missing Stage 2 subject index. Cannot rerun asset generation.'));
            }

            // Re-run the second pass with the resolved asset index text.
            // It will also bust deduplication cache by using sceneAnalysisMode = "2_pass_generate_assets" internally
            const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(
                analysisUiReport?.importReport || {},
                resolvedSubjectIndexText,
                { isRetryPhase2: true, ...options }
            );
            
            // Update the UI report with the new asset counts
            if (analysisUiReport && typeof analysisUiReport === 'object') {
                const newImportReport = {
                    ...analysisUiReport.importReport,
                    sceneSubjectPostImportReport: syncScenePostImportCheckedCount(
                        analysisUiReport.importReport || {},
                        postImportSceneSubjectReport
                    ),
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
                          poster: (newImportReport.importedSubjectCounts?.poster || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.poster) || 0),
                    };
                }
                const retrySkippedItems = Array.isArray(postImportSceneSubjectReport?.supplementReport?.skippedItems)
                    ? postImportSceneSubjectReport.supplementReport.skippedItems
                    : [];
                if (retrySkippedItems.length > 0) {
                    newImportReport.skippedSubjectItems = [
                        ...(Array.isArray(newImportReport.skippedSubjectItems) ? newImportReport.skippedSubjectItems : []),
                        ...retrySkippedItems,
                    ];
                }
                
                setAnalysisUiReport((prev) => buildCompletedAnalysisUiReport({
                    ...prev,
                    importReport: newImportReport,
                }));
                const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
                const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
                const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
                const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
                const hasActionableMissing = postImportSupplementCreated > 0 || postImportSupplementFailed > 0;
                
                setAnalysisFlowStatus({
                    phase: 'completed',
                    message: hasActionableMissing
                        ? (
                            postImportSupplementFailed > 0
                                ? t(`🔄 补全完毕！成功新建 ${postImportSupplementCreated} 个资产（跳过 ${postImportSupplementSkipped} 个，失败 ${postImportSupplementFailed} 个）。`, `Retry completed: created ${postImportSupplementCreated} new assets (skipped ${postImportSupplementSkipped}, failed ${postImportSupplementFailed}).`)
                                : t(`🔄 补全完毕！成功新建 ${postImportSupplementCreated} 个资产（跳过 ${postImportSupplementSkipped} 个）。`, `Retry completed: created ${postImportSupplementCreated} new assets (skipped ${postImportSupplementSkipped}).`)
                        )
                        : (
                            postImportSupplementSkipped > 0
                                ? t(`✅ 资产已齐全：${postImportSupplementSkipped} 个条目均已存在于资产库，无需重复生成。`, `Assets already complete: ${postImportSupplementSkipped} item(s) already exist in the library.`)
                                : t('重试✅ 工作圆满完成！未发现缺失的资产。', 'Retry completed: no missing entities detected, workflow finished.')
                        ),
                });
                
                onLog?.('Stage 3 asset design retry completed.', 'success');
            }
        } catch (error) {
            if (isTaskCanceledError(error) || analysisStopRequestedRef.current) {
                setAnalysisFlowStatus({
                    phase: 'warning',
                    message: t('已中断资产重跑。', 'Asset rerun was stopped.'),
                });
                onLog?.('Stage 3 asset design retry stopped by user.', 'warning');
                return;
            }
            console.error("Retry Stage 3 asset design failed:", error);
            setAnalysisFlowStatus({
                phase: 'failed',
                message: t(`重跑资产生成失败：${error.message || String(error)}`, `Retry Stage 3 asset design failed: ${error.message || String(error)}`),
            });
            onLog?.(`Retry Stage 3 asset design failed: ${error.message || String(error)}`, 'error');
            alert(`Retry Stage 3 asset design failed: ${error.message}`);
        } finally {
            clearAnalysisTaskMarker(activeEpisode?.id);
            setIsRetryingPhase2(false);
        }
    };

    const assetRerunCategoryOptions = useMemo(() => ([
        { key: 'characters', labelZh: '角色', labelEn: 'Characters', targetEntityTypes: ['characters'] },
        { key: 'props', labelZh: '道具', labelEn: 'Props', targetEntityTypes: ['props'] },
        { key: 'environments', labelZh: '环境', labelEn: 'Environments', targetEntityTypes: ['environments'] },
        { key: 'posters', labelZh: '封面/海报', labelEn: 'Posters/Covers', targetEntityTypes: ['posters', 'covers'] },
    ]), []);

    const resolveSubjectIndexTextForAssetRerun = useCallback(() => {
        const candidateSources = [
            activeEpisode?.ai_scene_analysis_subject_index,
            getStageOutputContent('stage2', 'subject_index'),
            subjectIndexText,
        ];
        for (const raw of candidateSources) {
            const direct = extractPureSubjectIndexText(String(raw || '').trim());
            if (direct) return direct;
        }
        return '';
    }, [
        activeEpisode?.ai_scene_analysis_subject_index,
        extractPureSubjectIndexText,
        getStageOutputContent,
        subjectIndexText,
    ]);

    const mapSubjectIndexTypeToRerunTarget = useCallback((rawType) => {
        const normalizedType = normalizeSubjectIndexTypeForAssetTask(rawType);
        if (normalizedType === 'character') return { category: 'characters', targetEntityTypes: ['characters'] };
        if (normalizedType === 'prop') return { category: 'props', targetEntityTypes: ['props'] };
        if (normalizedType === 'environment') return { category: 'environments', targetEntityTypes: ['environments'] };
        if (normalizedType === 'cover_poster') return { category: 'posters', targetEntityTypes: ['posters', 'covers'] };
        return { category: '', targetEntityTypes: [] };
    }, [normalizeSubjectIndexTypeForAssetTask]);

    const parseSubjectIndexEntriesForAssetRerun = useCallback((sourceText) => {
        const source = String(sourceText || '').replace(/<think>[\s\S]*?<\/think>\n*/gi, '').trim();
        if (!source) return [];

        const cleanHeaderKey = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9_\u4e00-\u9fa5]+/g, '_');
        const pickHeaderIndex = (headers, patterns) => {
            const normalizedHeaders = (headers || []).map(cleanHeaderKey);
            return normalizedHeaders.findIndex((header) => patterns.some((pattern) => pattern.test(header)));
        };
        const cleanCell = (value) => String(value || '').replace(/<br\s*\/?>/gi, ' ').trim();
        const getKeyValue = (line, name) => {
            const match = String(line || '').match(new RegExp(`\\b${name}\\s*=\\s*([^|\\n\`]*)`, 'i'));
            return String(match?.[1] || '').trim();
        };

        const resolveCoreFieldsFromObject = (obj = {}) => {
            const subjectNo = String(
                obj.subject_no ?? obj.id ?? obj['编号'] ?? ''
            ).trim();
            const subjectType = String(
                obj.subject_type ?? obj.type ?? obj['类型'] ?? obj['类别'] ?? ''
            ).trim();
            const subjectName = String(
                obj.subject_name_exact
                ?? obj.subject_name_zh
                ?? obj.subject_name_en
                ?? obj.subject_name
                ?? obj.name
                ?? obj['名称']
                ?? obj['名字']
                ?? ''
            ).trim();
            return { subjectNo, subjectType, subjectName };
        };

        const isTableSeparatorLine = (line) => {
            const trimmed = String(line || '').trim();
            return /\|\s*:?-{3,}:?/.test(trimmed) || /^[\s\|:\-]*$/.test(trimmed);
        };
        const isSubjectIndexHeaderLine = (line) => {
            const normalized = String(line || '').toLowerCase();
            return normalized.includes('subject_no') && normalized.includes('subject_type');
        };
        const buildRowObjectFromHeadersAndCells = (headers, cells) => (
            (headers || []).reduce((acc, header, headerIdx) => {
                const stableHeader = String(header || '').trim();
                if (!stableHeader) return acc;
                acc[stableHeader] = cleanCell(cells[headerIdx]);
                return acc;
            }, {})
        );
        const pushEntryFromPipeCells = ({ headers, cells, sourceLine, sourceBlock, rowIndex }) => {
            const resolvedHeaders = (Array.isArray(headers) && headers.length)
                ? headers
                : [...SUBJECT_INDEX_STANDARD_HEADERS];
            const resolvedCells = reconcileSceneTableRowCells(
                Array.isArray(cells) ? cells : cleanMarkdownTableCells(sourceLine),
                resolvedHeaders
            );
            const typeIdx = pickHeaderIndex(resolvedHeaders, [/subject_?type/, /^type$/, /类型/, /类别/]);
            const noIdx = pickHeaderIndex(resolvedHeaders, [/subject_?no/, /^id$/, /编号/]);
            const nameIdx = pickHeaderIndex(resolvedHeaders, [/subject_?name_?exact/, /subject_?name_?zh/, /subject_?name_?en/, /subject_?name/, /^name$/, /名称/, /名字/]);
            const rawType = typeIdx >= 0 ? cleanCell(resolvedCells[typeIdx]) : cleanCell(resolvedCells[1]);
            const subjectNo = noIdx >= 0 ? cleanCell(resolvedCells[noIdx]) : cleanCell(resolvedCells[0]);
            const name = nameIdx >= 0
                ? cleanCell(resolvedCells[nameIdx])
                : cleanCell(resolvedCells[2] || resolvedCells.find((cell, cellIdx) => cellIdx !== typeIdx && cellIdx !== noIdx && String(cell || '').trim()) || '');
            pushEntry({
                rowObject: buildRowObjectFromHeadersAndCells(resolvedHeaders, resolvedCells),
                fieldOrder: resolvedHeaders,
                rawType,
                subjectNo,
                name,
                sourceLine,
                sourceBlock,
                rowIndex,
            });
        };

        const entries = [];
        const seen = new Set();
        const pushEntry = ({ rowObject = null, fieldOrder = null, rawType, subjectNo, name, sourceLine, sourceBlock, rowIndex }) => {
            const normalizedObject = (rowObject && typeof rowObject === 'object') ? rowObject : {};
            const core = resolveCoreFieldsFromObject(normalizedObject);
            const finalSubjectType = String(rawType || core.subjectType || '').trim();
            const finalSubjectNo = String(subjectNo || core.subjectNo || '').trim();
            const finalName = String(name || core.subjectName || '').trim();

            const mapped = mapSubjectIndexTypeToRerunTarget(finalSubjectType);
            if (!mapped.category || !mapped.targetEntityTypes.length) return;
            const displayName = String(finalName || finalSubjectNo || '').trim();
            if (!displayName || isDummySubject(displayName)) return;
            const key = `${mapped.category}:${normalizeSubjectKey(displayName) || displayName}:${finalSubjectNo || rowIndex || entries.length}`;
            if (seen.has(key)) return;
            seen.add(key);
            entries.push({
                key,
                subjectNo: finalSubjectNo,
                name: displayName,
                type: normalizeSubjectIndexTypeForAssetTask(finalSubjectType),
                category: mapped.category,
                targetEntityTypes: mapped.targetEntityTypes,
                fields: normalizeSubjectIndexEntryFields(normalizedObject, {
                    subjectNo: finalSubjectNo,
                    name: displayName,
                    type: normalizeSubjectIndexTypeForAssetTask(finalSubjectType),
                }),
                fieldOrder: [...SUBJECT_INDEX_STANDARD_HEADERS],
                sourceText: String(sourceBlock || sourceLine || '').trim(),
                sourceLine: String(sourceLine || sourceBlock || '').trim(),
            });
        };

        const parsed = parseMarkdownTable(source);
        if (parsed?.headers?.length && parsed?.rows?.length) {
            const headers = parsed.headers;
            const typeIdx = pickHeaderIndex(headers, [/subject_?type/, /^type$/, /类型/, /类别/]);
            if (typeIdx >= 0) {
                parsed.rows.forEach((row, idx) => {
                    pushEntryFromPipeCells({
                        headers,
                        cells: row,
                        sourceLine: `| ${row.map(cleanCell).join(' | ')} |`,
                        sourceBlock: buildMarkdownTable(headers, [row]),
                        rowIndex: idx,
                    });
                });
            }
        }

        if (!entries.length) {
            const pipeLines = source
                .split('\n')
                .map((line) => String(line || '').trim())
                .filter((line) => line.includes('|'));
            let headers = [...SUBJECT_INDEX_STANDARD_HEADERS];
            const headerLine = pipeLines.find(isSubjectIndexHeaderLine);
            if (headerLine) {
                const parsedHeaders = cleanMarkdownTableCells(headerLine).map((cell) => String(cell || '').trim()).filter(Boolean);
                if (parsedHeaders.length) headers = parsedHeaders;
            }
            pipeLines.forEach((line, idx) => {
                if (isTableSeparatorLine(line) || isSubjectIndexHeaderLine(line)) return;
                if (/\bsubject_(?:no|type)\s*=/i.test(line)) return;
                const cells = reconcileSceneTableRowCells(cleanMarkdownTableCells(line), headers);
                const firstCell = cleanCell(cells[0] || '');
                const secondCell = cleanCell(cells[1] || '');
                if (!firstCell || !secondCell) return;
                if (['subject_no', 'subject_id', 'id', '编号'].includes(firstCell.toLowerCase())) return;
                if (!normalizeSubjectIndexTypeForAssetTask(secondCell)) return;
                pushEntryFromPipeCells({
                    headers,
                    cells,
                    sourceLine: line,
                    sourceBlock: buildMarkdownTable(headers, [cells]),
                    rowIndex: idx,
                });
            });
        }

        source.split('\n').forEach((line, idx) => {
            const detected = detectSubjectIndexLineType(line);
            if (!detected.isSubjectRow) return;
            const normalizedLine = String(line || '').replace(/^\s*>\s*/, '').replace(/^[-*+]\s+/, '').trim();
            const pipeHeaders = [...SUBJECT_INDEX_STANDARD_HEADERS];
            const reconciledCells = normalizedLine.includes('|')
                ? reconcileSceneTableRowCells(cleanMarkdownTableCells(normalizedLine), pipeHeaders)
                : [];
            const rawType = getKeyValue(normalizedLine, 'subject_type') || detected.type || reconciledCells[1] || '';
            const subjectNo = getKeyValue(normalizedLine, 'subject_no') || reconciledCells[0] || '';
            const name = getKeyValue(normalizedLine, 'subject_name_exact')
                || getKeyValue(normalizedLine, 'subject_name_zh')
                || getKeyValue(normalizedLine, 'subject_name_en')
                || reconciledCells[2]
                || reconciledCells.slice(2).find((cell) => cell && !/^subject_/i.test(cell))
                || '';
            const rowObject = {};
            const keyValueMatches = Array.from(normalizedLine.matchAll(/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^|\n`]*)/g));
            if (keyValueMatches.length > 0) {
                keyValueMatches.forEach((match) => {
                    const fieldKey = String(match?.[1] || '').trim();
                    if (!fieldKey) return;
                    rowObject[fieldKey] = String(match?.[2] || '').trim();
                });
                if (rowObject.subject_no == null && subjectNo) rowObject.subject_no = subjectNo;
                if (rowObject.subject_type == null && rawType) rowObject.subject_type = rawType;
                if (rowObject.subject_name_exact == null && name) rowObject.subject_name_exact = name;
                pushEntry({
                    rowObject,
                    fieldOrder: Object.keys(rowObject),
                    rawType,
                    subjectNo,
                    name,
                    sourceLine: line,
                    sourceBlock: line,
                    rowIndex: idx,
                });
                return;
            }
            if (reconciledCells.length >= 2) {
                pushEntryFromPipeCells({
                    headers: pipeHeaders,
                    cells: reconciledCells,
                    sourceLine: line,
                    sourceBlock: buildMarkdownTable(pipeHeaders, [reconciledCells]),
                    rowIndex: idx,
                });
                return;
            }
            pushEntry({
                rowObject: {
                    subject_no: subjectNo,
                    subject_type: rawType,
                    subject_name_exact: name,
                },
                fieldOrder: ['subject_no', 'subject_type', 'subject_name_exact'],
                rawType,
                subjectNo,
                name,
                sourceLine: line,
                sourceBlock: line,
                rowIndex: idx,
            });
        });

        return entries;
    }, [buildMarkdownTable, detectSubjectIndexLineType, mapSubjectIndexTypeToRerunTarget, normalizeSubjectIndexTypeForAssetTask]);

    const phase2RerunSubjectEntries = useMemo(
        () => parseSubjectIndexEntriesForAssetRerun(resolveSubjectIndexTextForAssetRerun()),
        [parseSubjectIndexEntriesForAssetRerun, resolveSubjectIndexTextForAssetRerun]
    );

    const getSubjectFieldValueByAliases = useCallback((fields, aliases = []) => (
        resolveSubjectFieldValueByAliases(fields, aliases)
    ), []);

    const buildFullSubjectIndexTextFromEntries = useCallback((entries) => {
        const rows = (entries || []).map((entry) => {
            const fields = normalizeSubjectIndexEntryFields(entry?.fields, entry);
            return SUBJECT_INDEX_STANDARD_HEADERS.map((header) => String(fields[header] ?? '').trim());
        }).filter((row) => row.some((cell) => String(cell || '').trim()));

        if (!rows.length) return '';
        return `### Subject Index\n\n${buildMarkdownTable(SUBJECT_INDEX_STANDARD_HEADERS, rows)}`.trim();
    }, [buildMarkdownTable]);

    const buildSingleSubjectIndexTextForRerun = useCallback((entry) => {
        const normalizedFields = normalizeSubjectIndexEntryFields(entry?.fields, entry);
        const subjectType = String(entry?.type || normalizedFields.subject_type || '').trim();
        const subjectName = String(
            normalizedFields.subject_name_zh
            || normalizedFields.subject_name_en
            || entry?.name
            || ''
        ).trim();
        if (!subjectType || !subjectName) return '';

        normalizedFields.subject_type = subjectType;
        if (!normalizedFields.subject_name_zh) {
            normalizedFields.subject_name_zh = subjectName;
        }
        if (!normalizedFields.subject_no && entry?.subjectNo) normalizedFields.subject_no = String(entry.subjectNo).trim();

        const extraHeaders = Object.keys(normalizedFields).filter((key) => !SUBJECT_INDEX_STANDARD_HEADERS.includes(key));
        const headers = [...SUBJECT_INDEX_STANDARD_HEADERS, ...extraHeaders];
        const row = headers.map((key) => String(normalizedFields[key] ?? '').trim());
        return buildMarkdownTable(headers, [row]);
    }, [buildMarkdownTable]);

    const phase2RerunDisplayEntries = useMemo(() => {
        const deletedMap = (phase2RerunModal?.deletedSubjectKeys && typeof phase2RerunModal.deletedSubjectKeys === 'object')
            ? phase2RerunModal.deletedSubjectKeys
            : {};
        const editsMap = (phase2RerunModal?.subjectEdits && typeof phase2RerunModal.subjectEdits === 'object')
            ? phase2RerunModal.subjectEdits
            : {};
        return (phase2RerunSubjectEntries || []).reduce((acc, originalEntry) => {
            if (!originalEntry?.key) return acc;
            if (deletedMap[originalEntry.key]) return acc;

            const patch = editsMap[originalEntry.key] || {};
            const nextFields = (patch.fields && typeof patch.fields === 'object')
                ? patch.fields
                : ((originalEntry.fields && typeof originalEntry.fields === 'object') ? originalEntry.fields : {});
            const nextFieldOrder = Array.isArray(patch.fieldOrder) ? patch.fieldOrder : (Array.isArray(originalEntry.fieldOrder) ? originalEntry.fieldOrder : []);
            const nextType = String(getSubjectFieldValueByAliases(nextFields, ['subject_type', 'type', '类型', '类别']) || originalEntry.type || '').trim();
            const nextSubjectNo = String(getSubjectFieldValueByAliases(nextFields, ['subject_no', 'id', '编号']) || originalEntry.subjectNo || '').trim();
            const nextName = String(
                getSubjectFieldValueByAliases(nextFields, ['subject_name_zh', 'subject_name_exact', 'subject_name_en', 'subject_name', 'name', '名称', '名字'])
                || originalEntry.name
                || ''
            ).trim();
            const mapped = mapSubjectIndexTypeToRerunTarget(nextType);
            if (!mapped.category || !mapped.targetEntityTypes?.length) return acc;

            const merged = {
                ...originalEntry,
                subjectNo: nextSubjectNo,
                name: nextName,
                type: nextType,
                category: mapped.category,
                targetEntityTypes: mapped.targetEntityTypes,
                fields: normalizeSubjectIndexEntryFields(nextFields, {
                    ...originalEntry,
                    subjectNo: nextSubjectNo,
                    name: nextName,
                    type: nextType,
                }),
                fieldOrder: [...SUBJECT_INDEX_STANDARD_HEADERS],
            };
            if (!merged.name) return acc;
            const sourceText = buildSingleSubjectIndexTextForRerun(merged)
                || String(originalEntry?.sourceBlock || originalEntry?.sourceLine || '').trim();
            if (!sourceText) return acc;
            acc.push({
                ...merged,
                sourceText,
                sourceLine: String(originalEntry?.sourceLine || '').trim()
                    || `subject_no=${merged.subjectNo || '-'} | subject_type=${merged.type} | subject_name_exact=${merged.name}`,
            });
            return acc;
        }, []);
    }, [
        buildSingleSubjectIndexTextForRerun,
        getSubjectFieldValueByAliases,
        mapSubjectIndexTypeToRerunTarget,
        phase2RerunModal?.deletedSubjectKeys,
        phase2RerunModal?.subjectEdits,
        phase2RerunSubjectEntries,
    ]);

    const filteredPhase2RerunSubjectEntries = useMemo(() => {
        const mode = String(phase2RerunModal.mode || 'all').trim();
        const category = String(phase2RerunModal.category || '').trim();
        const query = String(phase2RerunModal.query || '').trim().toLowerCase();
        return phase2RerunDisplayEntries.filter((item) => {
            if ((mode === 'category' || mode === 'single') && category && item.category !== category) return false;
            if (!query) return true;
            return [item.subjectNo, item.name, item.type, item.sourceLine]
                .some((value) => String(value || '').toLowerCase().includes(query));
        });
    }, [phase2RerunDisplayEntries, phase2RerunModal.category, phase2RerunModal.mode, phase2RerunModal.query]);

    const openPhase2RerunModal = useCallback((patch = {}) => {
        const nextCategory = String(patch.category || phase2RerunModal.category || 'characters').trim();
        const firstSubject = phase2RerunDisplayEntries.find((item) => item.category === nextCategory) || phase2RerunDisplayEntries[0];
        setPhase2RerunModal((prev) => ({
            ...prev,
            open: true,
            mode: patch.mode || prev.mode || 'all',
            category: nextCategory,
            subjectKey: patch.subjectKey || firstSubject?.key || '',
            query: patch.query !== undefined ? String(patch.query || '') : '',
            deletedSubjectKeys: {},
            subjectEdits: {},
            editingSubjectKey: '',
        }));
    }, [phase2RerunDisplayEntries, phase2RerunModal.category]);

    const closePhase2RerunModal = useCallback(() => {
        setPhase2RerunModal((prev) => ({ ...prev, open: false }));
    }, []);

    const resolveAssetRerunPatchFromSceneRequest = useCallback((request) => {
        const missingSubjects = Array.isArray(request?.missingSubjects) ? request.missingSubjects : [];
        if (missingSubjects.length <= 0) {
            return { mode: 'all' };
        }
        const firstMissing = missingSubjects[0] || {};
        const mapped = mapSubjectIndexTypeToRerunTarget(firstMissing.type);
        const category = mapped.category || 'characters';
        const missingName = String(firstMissing.name || '').trim();
        const normalizedMissingName = normalizeSubjectKey(missingName);
        const matched = (phase2RerunSubjectEntries || []).find((entry) => {
            if (category && entry.category !== category) return false;
            const entryKey = normalizeSubjectKey(entry.name);
            if (normalizedMissingName && entryKey === normalizedMissingName) return true;
            return missingName && String(entry.name || '').toLowerCase().includes(missingName.toLowerCase());
        });
        return {
            mode: missingSubjects.length === 1 ? 'single' : 'category',
            category,
            subjectKey: matched?.key || '',
        };
    }, [mapSubjectIndexTypeToRerunTarget, phase2RerunSubjectEntries]);

    useEffect(() => {
        assetRerunHandledNonceRef.current = null;
    }, [activeEpisode?.id]);

    useEffect(() => {
        const nonce = assetRerunRequest?.nonce;
        if (!nonce || assetRerunHandledNonceRef.current === nonce) return;

        assetRerunHandledNonceRef.current = nonce;
        const patch = resolveAssetRerunPatchFromSceneRequest(assetRerunRequest);
        openPhase2RerunModal(patch);
        if (typeof onAssetRerunRequestConsumed === 'function') {
            onAssetRerunRequestConsumed();
        }
        const sceneLabel = String(assetRerunRequest.sceneLabel || '').trim();
        const missingCount = Array.isArray(assetRerunRequest.missingSubjects) ? assetRerunRequest.missingSubjects.length : 0;
        if (missingCount > 0) {
            onLog?.(
                sceneLabel
                    ? t(`场景 ${sceneLabel} 检测到 ${missingCount} 个缺失实体，已打开资产生成重跑。`, `Scene ${sceneLabel}: detected ${missingCount} missing entities. Opened asset generation rerun.`)
                    : t(`检测到 ${missingCount} 个缺失实体，已打开资产生成重跑。`, `Detected ${missingCount} missing entities. Opened asset generation rerun.`),
                'info'
            );
        }
    }, [
        assetRerunRequest,
        onAssetRerunRequestConsumed,
        onLog,
        openPhase2RerunModal,
        resolveAssetRerunPatchFromSceneRequest,
        t,
    ]);

    const handleDeletePhase2RerunEntry = useCallback((entry) => {
        if (!entry?.key) return;
        if (!window.confirm(t(`确定从本次重跑列表中移除「${entry.name || entry.subjectNo || '该实体'}」吗？`, `Remove "${entry.name || entry.subjectNo || 'this entity'}" from this rerun selection?`))) {
            return;
        }
        setPhase2RerunModal((prev) => {
            const nextDeleted = {
                ...((prev.deletedSubjectKeys && typeof prev.deletedSubjectKeys === 'object') ? prev.deletedSubjectKeys : {}),
                [entry.key]: true,
            };
            const nextEdits = { ...((prev.subjectEdits && typeof prev.subjectEdits === 'object') ? prev.subjectEdits : {}) };
            delete nextEdits[entry.key];
            return {
                ...prev,
                deletedSubjectKeys: nextDeleted,
                subjectEdits: nextEdits,
                editingSubjectKey: prev.editingSubjectKey === entry.key ? '' : prev.editingSubjectKey,
                subjectKey: prev.subjectKey === entry.key ? '' : prev.subjectKey,
            };
        });
    }, [t]);

    const beginEditPhase2RerunEntry = useCallback((entry) => {
        if (!entry?.key) return;
        let fields = (entry?.fields && typeof entry.fields === 'object') ? { ...entry.fields } : {};
        const sourceSnippet = String(entry?.sourceBlock || entry?.sourceLine || '').trim();
        if (sourceSnippet) {
            const reparsedEntries = parseSubjectIndexEntriesForAssetRerun(sourceSnippet);
            const reparsed = reparsedEntries.find((item) => item.key === entry.key) || reparsedEntries[0];
            if (reparsed?.fields && typeof reparsed.fields === 'object') {
                fields = { ...reparsed.fields, ...fields };
            }
        }
        const normalizedFields = normalizeSubjectIndexEntryFields(fields, entry);
        setPhase2RerunModal((prev) => ({
            ...prev,
            editingSubjectKey: entry.key,
            subjectEdits: {
                ...((prev.subjectEdits && typeof prev.subjectEdits === 'object') ? prev.subjectEdits : {}),
                [entry.key]: {
                    fields: normalizedFields,
                    fieldOrder: [...SUBJECT_INDEX_STANDARD_HEADERS],
                },
            },
        }));
    }, [parseSubjectIndexEntriesForAssetRerun]);

    const updatePhase2RerunEntryEditField = useCallback((entryKey, fieldKey, value) => {
        if (!entryKey || !fieldKey) return;
        setPhase2RerunModal((prev) => {
            const prevEdits = (prev.subjectEdits && typeof prev.subjectEdits === 'object') ? prev.subjectEdits : {};
            const currentEdit = (prevEdits[entryKey] && typeof prevEdits[entryKey] === 'object') ? prevEdits[entryKey] : {};
            const currentFields = (currentEdit.fields && typeof currentEdit.fields === 'object') ? currentEdit.fields : {};
            return {
                ...prev,
                subjectEdits: {
                    ...prevEdits,
                    [entryKey]: {
                        ...currentEdit,
                        fields: {
                            ...currentFields,
                            [fieldKey]: String(value ?? ''),
                        },
                    },
                },
            };
        });
    }, []);

    const savePhase2RerunEntryEdit = useCallback((entryKey) => {
        if (!entryKey) return;
        const draft = phase2RerunModal?.subjectEdits?.[entryKey] || {};
        const fields = (draft.fields && typeof draft.fields === 'object') ? draft.fields : {};
        const nextName = String(getSubjectFieldValueByAliases(fields, ['subject_name_zh', 'subject_name_exact', 'subject_name_en', 'subject_name', 'name', '名称', '名字'])).trim();
        const nextType = String(getSubjectFieldValueByAliases(fields, ['subject_type', 'type', '类型', '类别'])).trim();
        if (!nextName) {
            alert(t('实体名称不能为空。', 'Entity name cannot be empty.'));
            return;
        }
        const mapped = mapSubjectIndexTypeToRerunTarget(nextType);
        if (!mapped?.category || !mapped?.targetEntityTypes?.length) {
            alert(t('实体类型无效，请选择可识别类型。', 'Invalid entity type. Please choose a supported type.'));
            return;
        }
        setPhase2RerunModal((prev) => ({ ...prev, editingSubjectKey: '' }));
    }, [getSubjectFieldValueByAliases, mapSubjectIndexTypeToRerunTarget, phase2RerunModal?.subjectEdits, t]);

    useEffect(() => {
        if (!phase2RerunModal.open) return;
        if (phase2RerunModal.mode !== 'single') return;
        const currentKey = String(phase2RerunModal.subjectKey || '').trim();
        const exists = currentKey && filteredPhase2RerunSubjectEntries.some((item) => item.key === currentKey);
        if (exists) return;
        const fallback = filteredPhase2RerunSubjectEntries[0] || phase2RerunDisplayEntries.find((item) => item.category === phase2RerunModal.category) || phase2RerunDisplayEntries[0] || null;
        const nextKey = String(fallback?.key || '').trim();
        if (!nextKey && !currentKey) return;
        if (nextKey === currentKey) return;
        setPhase2RerunModal((prev) => ({
            ...prev,
            subjectKey: nextKey,
        }));
    }, [
        filteredPhase2RerunSubjectEntries,
        phase2RerunDisplayEntries,
        phase2RerunModal.category,
        phase2RerunModal.mode,
        phase2RerunModal.open,
        phase2RerunModal.subjectKey,
    ]);

    const confirmPhase2RerunSelection = useCallback(async () => {
        const mode = String(phase2RerunModal.mode || 'all');
        const sourceText = resolveSubjectIndexTextForAssetRerun();
        if (!sourceText) {
            alert(t('缺少第二阶段资产清单，无法重跑资产生成。', 'Missing Stage 2 subject index. Cannot rerun asset generation.'));
            return;
        }

        const editedSubjectIndexText = buildFullSubjectIndexTextFromEntries(phase2RerunDisplayEntries);
        const hasEdits = Object.keys(phase2RerunModal?.subjectEdits || {}).length > 0;
        const hasDeletions = Object.keys(phase2RerunModal?.deletedSubjectKeys || {}).length > 0;
        const resolvedEditedText = editedSubjectIndexText || sourceText;

        let retryOptions = {};
        if (mode === 'category') {
            const option = assetRerunCategoryOptions.find((item) => item.key === phase2RerunModal.category) || assetRerunCategoryOptions[0];
            const category = String(phase2RerunModal.category || option.key || '').trim();
            const categoryEntries = (phase2RerunDisplayEntries || []).filter((item) => item.category === category);
            const categorySubjectIndexText = buildFullSubjectIndexTextFromEntries(categoryEntries);
            retryOptions = {
                targetEntityTypes: option.targetEntityTypes,
                explicitSubjectIndexText: categorySubjectIndexText || resolvedEditedText,
            };
        } else if (mode === 'single') {
            const selected = filteredPhase2RerunSubjectEntries.find((item) => item.key === phase2RerunModal.subjectKey)
                || filteredPhase2RerunSubjectEntries[0]
                || phase2RerunDisplayEntries.find((item) => item.key === phase2RerunModal.subjectKey);
            if (!selected?.sourceText) {
                alert(t('请选择一个资产清单实体后再重跑。', 'Select one subject-index entity before rerunning.'));
                return;
            }
            retryOptions = {
                targetEntityTypes: selected.targetEntityTypes,
                explicitSubjectIndexText: selected.sourceText,
                rerunSubject: {
                    subjectNo: selected.subjectNo,
                    name: selected.name,
                    type: selected.type,
                    fields: normalizeSubjectIndexEntryFields(selected.fields, selected),
                },
            };
        } else {
            retryOptions = { explicitSubjectIndexText: resolvedEditedText };
        }

        setPhase2RerunModal((prev) => ({ ...prev, open: false }));

        if ((hasEdits || hasDeletions) && resolvedEditedText) {
            try {
                setSubjectIndexText(extractPureSubjectIndexText(resolvedEditedText));
                await persistLlmResultContent(resolvedEditedText, 'ai_scene_analysis_subject_index', { source: 'asset-rerun-subject-index-edit' });
            } catch (error) {
                console.warn('Failed to persist edited Subject Index before asset rerun:', error);
            }
        }

        await handleRetryPhase2(retryOptions);
    }, [
        assetRerunCategoryOptions,
        buildFullSubjectIndexTextFromEntries,
        extractPureSubjectIndexText,
        filteredPhase2RerunSubjectEntries,
        handleRetryPhase2,
        persistLlmResultContent,
        phase2RerunDisplayEntries,
        phase2RerunModal.category,
        phase2RerunModal.deletedSubjectKeys,
        phase2RerunModal.mode,
        phase2RerunModal.subjectEdits,
        phase2RerunModal.subjectKey,
        resolveSubjectIndexTextForAssetRerun,
        t,
    ]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        if (isAnalyzing || isRetryingPhase2 || analysisRunInFlightRef.current || phase2GenerationInFlightRef.current) return;
        if (sceneBeatsOnlyRerunInFlightRef.current || autoImportRunningRef.current) return;

        const activeRun = getEpisodeAnalysisRun(activeEpisode.id);
        const pendingMarker = loadAnalysisTaskMarker(activeEpisode.id);
        if (activeRun?.promise || pendingMarker?.taskId || analysisResumeInFlightRef.current) return;

        const reportStatus = String(analysisUiReport?.status || '').trim().toLowerCase();
        const runTag = String(analysisUiReport?.runTag || '').trim().toLowerCase();
        const isSceneBeatsOnlyRerun = runTag === 'scene_beats_only_rerun';
        if (reportStatus !== 'completed') return;

        const fallbackState = ensureAnalysisFallbackState(activeEpisode.id);
        const reportKey = `${activeEpisode.id}:${analysisUiReport?.startedAt || 0}:${analysisUiReport?.durationMs || 0}:${runTag}:sceneAttempts=${Number(fallbackState?.sceneBeatsAttempts || 0)}:assetAttempts=${Number(fallbackState?.assetAttempts || 0)}:resolvedScenes=${Number(analysisUiReport?.resolvedSceneImportCount || 0)}:stage3Ok=${analysisUiReport?.stage3SubtasksOk ? 1 : 0}`;
        if (autoZeroReportHandledRef.current.key === reportKey) return;
        if (analysisFallbackRetryRef.current.running) return;

        analysisFallbackRetryRef.current.running = true;

        (async () => {
            try {
                if (isSceneBeatsOnlyRerun) {
                    onLog?.('[Auto Zero Report Rerun] scene-beats-only rerun completed; skipping asset/scene fallback checks.', 'info');
                    return;
                }

                const importReport = (analysisUiReport?.importReport && typeof analysisUiReport.importReport === 'object')
                    ? analysisUiReport.importReport
                    : {};
                const scenePostReport = (importReport.sceneSubjectPostImportReport && typeof importReport.sceneSubjectPostImportReport === 'object')
                    ? importReport.sceneSubjectPostImportReport
                    : {};

                const snapshotResolvedSceneCount = firstPositiveFiniteNumber(
                    analysisUiReport?.resolvedSceneImportCount,
                    lastSceneImportSuccessRef.current?.episodeId === activeEpisode.id
                        ? lastSceneImportSuccessRef.current?.count
                        : 0,
                    resolveImportReportSceneCount(importReport, scenePostReport, null),
                );
                const dbSceneCount = snapshotResolvedSceneCount > 0
                    ? snapshotResolvedSceneCount
                    : await fetchEpisodeSceneCountWithRetry(fetchScenes, activeEpisode.id);
                const resolvedSceneCount = firstPositiveFiniteNumber(snapshotResolvedSceneCount, dbSceneCount);
                const hasPersistedSceneMarkdown = Boolean(String(activeEpisode?.ai_scene_analysis_scene_markdown || '').trim());

                const subjectIndexText = resolveSubjectIndexTextForAssetRerun();
                const subjectIndexEntries = parseSubjectIndexEntriesForAssetRerun(subjectIndexText);
                const expectedAssetCategories = new Set(
                    (subjectIndexEntries || []).map((entry) => String(entry?.category || '').trim()).filter(Boolean)
                );

                const dbEntities = projectId ? await fetchEntities(projectId).catch(() => []) : [];
                const subtaskReports = Array.isArray(scenePostReport?.subtaskReports) ? scenePostReport.subtaskReports : [];
                const hasEntityDesignPayload = hasPersistedEntityDesignPayload(activeEpisode?.ai_entity_design_result);
                const stage3CompletedOk = Boolean(analysisUiReport?.stage3SubtasksOk)
                    || (subtaskReports.length > 0 && subtaskReports.every(
                        (report) => String(report?.status || '').trim().toLowerCase() === 'ok'
                    ));

                const assetCategorySpecs = [
                    { key: 'characters', labelZh: '角色', targets: ['characters'], reportType: 'character' },
                    { key: 'props', labelZh: '道具', targets: ['props'], reportType: 'prop' },
                    { key: 'environments', labelZh: '场景/环境', targets: ['environments'], reportType: 'environment' },
                    { key: 'posters', labelZh: '封面/海报', targets: ['posters', 'covers'], reportType: 'poster' },
                ];

                const pendingAssetTargets = [];
                const pendingLabels = [];

                if (hasEntityDesignPayload && stage3CompletedOk && expectedAssetCategories.size > 0) {
                    onLog?.('[Auto Zero Report Rerun] Stage 3 completed with persisted entity design; skipping asset auto-rerun.', 'info');
                } else {
                for (const spec of assetCategorySpecs) {
                    if (!expectedAssetCategories.has(spec.key)) continue;

                    if (isAssetCategorySatisfiedBySubtaskReports(subtaskReports, spec.key)) {
                        onLog?.(
                            `[Auto Zero Report Rerun] ${spec.labelZh} Stage 3 subtask ok (created+skipped>0); skipping auto-rerun.`,
                            'info'
                        );
                        continue;
                    }

                    const insertedCount = resolveImportReportAssetInsertedCount(importReport, spec.reportType);
                    const skippedCount = resolveImportReportAssetSkippedCount(importReport, spec.reportType);
                    const handledCount = resolveImportReportAssetHandledCount(importReport, spec.reportType, spec.key);
                    if (handledCount > 0 && (insertedCount > 0 || skippedCount > 0)) {
                        onLog?.(
                            `[Auto Zero Report Rerun] ${spec.labelZh} handled=${handledCount} (created=${insertedCount} skipped=${skippedCount}); skipping auto-rerun.`,
                            'info'
                        );
                        continue;
                    }

                    const categoryEntries = (subjectIndexEntries || []).filter((entry) => entry?.category === spec.key);
                    if (categoryEntries.length > 0 && dbEntities.length > 0) {
                        const coveredCount = countSubjectIndexEntriesCoveredInDb(categoryEntries, spec.reportType, dbEntities);
                        if (coveredCount >= categoryEntries.length) {
                            onLog?.(
                                `[Auto Zero Report Rerun] ${spec.labelZh} already present in DB (${coveredCount}/${categoryEntries.length}); skipping auto-rerun.`,
                                'info'
                            );
                            continue;
                        }
                    }

                    pendingLabels.push(spec.labelZh);
                    spec.targets.forEach((target) => {
                        if (!pendingAssetTargets.includes(target)) pendingAssetTargets.push(target);
                    });
                }
                }

                const shouldRerunScenes = !isSceneBeatsOnlyRerun
                    && resolvedSceneCount === 0
                    && !hasPersistedSceneMarkdown
                    && canAttemptAnalysisFallback(activeEpisode.id, 'scene_beats')
                    && Boolean(buildStage1RestartSourceText())
                    && Boolean(subjectIndexText);

                if (resolvedSceneCount > 0 && onLog) {
                    onLog?.(`[Auto Zero Report Rerun] scene count resolved=${resolvedSceneCount}; skipping scene beats auto-rerun.`, 'info');
                } else if (hasPersistedSceneMarkdown && onLog) {
                    onLog?.('[Auto Zero Report Rerun] scene markdown already persisted; skipping scene beats auto-rerun.', 'info');
                } else if (isSceneBeatsOnlyRerun && onLog) {
                    onLog?.('[Auto Zero Report Rerun] scene-beats-only rerun report; skipping scene beats auto-rerun.', 'info');
                }

                if (pendingAssetTargets.length > 0 && onLog) {
                    onLog?.(
                        `[Auto Zero Report Rerun] zero-count asset categories detected from report: ${pendingLabels.join('、')} (expected from subject index=${expectedAssetCategories.size}).`,
                        'warning'
                    );
                } else if (expectedAssetCategories.size > 0 && onLog) {
                    onLog?.('[Auto Zero Report Rerun] asset categories look healthy (created/skipped/subtasks/DB); skipping asset auto-rerun.', 'info');
                }

                if (!shouldRerunScenes && pendingAssetTargets.length <= 0) return;

                const shouldRerunAssets = pendingAssetTargets.length > 0
                    && canAttemptAnalysisFallback(activeEpisode.id, 'asset_gen');

                if (!shouldRerunScenes && !shouldRerunAssets) {
                    onLog?.(
                        `[Auto Zero Report Rerun] skipped: fallback retry limit reached (max ${MAX_ANALYSIS_FALLBACK_ATTEMPTS} per category).`,
                        'warning'
                    );
                    return;
                }

                if (shouldRerunScenes) {
                    recordAnalysisFallbackAttempt(activeEpisode.id, 'scene_beats');
                    const remaining = getAnalysisFallbackRemaining(activeEpisode.id, 'scene_beats');
                    onLog?.(
                        `[Auto Zero Report Rerun] scenes count is 0, rerunning scene beats (remaining auto retries: ${remaining}).`,
                        'warning'
                    );
                    setAnalysisFlowStatus({
                        phase: 'scene_beats',
                        message: t(
                            `检查报告发现“场景”为 0，正在自动单独重排场景（剩余 ${remaining} 次）...`,
                            `Report found scenes=0. Auto-rerunning scene beats (${remaining} auto retries left)...`
                        ),
                    });
                    await executeSceneBeatsRerun({ mode: 'all' });
                }

                if (shouldRerunAssets) {
                    if (isSceneBeatsOnlyRerun) {
                        onLog?.('[Auto Zero Report Rerun] skipped asset auto-rerun for scene-beats-only rerun report.', 'info');
                        return;
                    }
                    autoZeroReportHandledRef.current = { key: reportKey, handledAt: Date.now() };
                    persistAnalysisSessionSnapshot(activeEpisode.id);
                    const targetEntityTypes = Array.from(new Set(pendingAssetTargets));
                    const remaining = getAnalysisFallbackRemaining(activeEpisode.id, 'asset_gen');
                    onLog?.(
                        `[Auto Zero Report Rerun] asset count is 0, rerunning categories=${targetEntityTypes.join(',')} (remaining auto retries: ${remaining}).`,
                        'warning'
                    );
                    setAnalysisFlowStatus({
                        phase: 'assets_gen',
                        message: t(
                            `检查报告发现 ${pendingLabels.join('、')} 为 0，正在自动单独重跑对应资产类型（剩余 ${remaining} 次）...`,
                            `Report found zero-count asset categories (${pendingLabels.join(', ')}). Auto-rerunning (${remaining} auto retries left)...`
                        ),
                    });
                    await handleRetryPhase2({ targetEntityTypes, autoZeroReportRerun: true });
                }
            } catch (error) {
                const detail = String(error?.message || error || 'unknown error');
                onLog?.(`[Auto Zero Report Rerun] failed: ${detail}`, 'warning');
            } finally {
                autoZeroReportHandledRef.current = { key: reportKey, handledAt: Date.now() };
                analysisFallbackRetryRef.current.running = false;
                persistAnalysisSessionSnapshot(activeEpisode.id);
            }
        })();
    }, [
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.id,
        analysisUiReport,
        buildStage1RestartSourceText,
        canAttemptAnalysisFallback,
        fetchEntities,
        fetchScenes,
        getAnalysisFallbackRemaining,
        handleRetryPhase2,
        executeSceneBeatsRerun,
        isAnalyzing,
        isRetryingPhase2,
        loadAnalysisTaskMarker,
        onLog,
        parseSubjectIndexEntriesForAssetRerun,
        persistAnalysisSessionSnapshot,
        projectId,
        recordAnalysisFallbackAttempt,
        resolveSubjectIndexTextForAssetRerun,
        t,
    ]);

    const phase1AnalysisReport = useMemo(() => {
        if (!analysisUiReport) return null;
        if (analysisFlowStatus?.phase === 'analysis' || analysisFlowStatus?.phase === 'scene') {
            return { status: 'running' };
        }
        if (analysisFlowStatus?.phase === 'failed') return { status: 'error', error: analysisFlowStatus.message || analysisUiReport.error };
        if (analysisUiReport.status === 'completed' || analysisFlowStatus?.phase === 'asset_generation' || analysisFlowStatus?.phase === 'supplement') {
            return { status: 'completed' };
        }
        return { status: analysisUiReport.status, error: analysisUiReport.error, warning: analysisUiReport.warning };
    }, [analysisUiReport, analysisFlowStatus]);

    const phase2AnalysisReport = useMemo(() => {
        if (!analysisUiReport) return null;
        if (analysisFlowStatus?.phase === 'asset_generation' || analysisFlowStatus?.phase === 'supplement') {
            return { status: 'running' };
        }
        if (analysisFlowStatus?.phase === 'failed') return { status: 'error', error: analysisFlowStatus.message || analysisUiReport.error };
        if (analysisUiReport.status === 'completed' && analysisFlowStatus?.phase === 'completed') {
            return { status: 'completed' };
        }
        if (analysisFlowStatus?.phase === 'analysis' || analysisFlowStatus?.phase === 'scene') return null;
        return { status: analysisUiReport.status, error: analysisUiReport.error, warning: analysisUiReport.warning };
    }, [analysisUiReport, analysisFlowStatus]);

    const hasAssetGenerationPrerequisite = Boolean(resolveSubjectIndexTextForAssetRerun());

    const stage1StageCards = useMemo(() => {
        const adaptedScript = getStageOutputContent('stage1', 'adapted_script');
        const visualBackfillJson = getStageOutputContent('stage1', 'project_visual_backfill');

        return [
            {
                key: 'stage1-adapted-script',
                eyebrow: t('第一阶段', 'Stage 1'),
                title: t('优化后剧本', 'Optimized Script'),
                status: adaptedScript ? 'completed' : (String(llmRawResultContent || '').trim() ? 'warning' : 'idle'),
                badge: adaptedScript ? t('可回填', 'Re-importable') : t('待输出', 'Pending'),
                summary: t('单独保存第一阶段产出的优化后剧本，可直接回填到当前剧本编辑区。', 'Stores the Stage 1 optimized script separately and can restore it back into the script editor.'),
                content: adaptedScript,
                actions: [
                    {
                        key: 'reimport-stage1-script',
                        label: t('回填剧本', 'Restore Script'),
                        icon: 'refresh',
                        onClick: handleRestoreAdaptedScript,
                        disabled: isAnalyzing || !adaptedScript,
                        loading: false,
                    },
                    {
                        key: 'restart-stage1-card',
                        label: t('重跑覆盖', 'Rerun & Overwrite'),
                        icon: 'refresh',
                        onClick: handleAnalysisClick,
                        disabled: isAnalyzing,
                        loading: isAnalyzing,
                    },
                ],
                placeholder: t('第一阶段尚未提取到“修改后的剧本”正文。', 'No adapted script extracted from Stage 1 yet.'),
            },
            {
                key: 'stage1-visual-backfill',
                eyebrow: t('第一阶段', 'Stage 1'),
                title: t('全局风格', 'Global Style'),
                status: visualBackfillJson ? 'completed' : 'idle',
                badge: visualBackfillJson ? t('可导入', 'Importable') : t('待输出', 'Pending'),
                summary: t('单独保存第一阶段产出的全局风格，可重新导入项目视觉约束。', 'Stores the Stage 1 global style separately for re-import.'),
                content: formatArtifactContent(visualBackfillJson, 'json'),
                actions: [
                    {
                        key: 'reimport-stage1-visual-backfill',
                        label: t('重新导入', 'Re-import'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: visualBackfillJson,
                            importType: 'json',
                            label: 'stage1 project visual backfill',
                        }),
                        disabled: isAnalyzing || !visualBackfillJson,
                        loading: false,
                    },
                ],
                placeholder: t('第一阶段尚未产出全局风格。', 'No Stage 1 global style yet.'),
            },
        ];
    }, [formatArtifactContent, getStageOutputContent, handleAnalysisClick, handleImportStageArtifact, handleRestoreAdaptedScript, isAnalyzing, llmRawResultContent, t]);

    const stage2SceneMarkdownByScene = useMemo(() => {
        const rawJson = getStageOutputContent('stage2', 'scene_markdown_by_scene');
        const parsed = parseSceneMarkdownBySceneMap(rawJson);
        if (parsed && typeof parsed === 'object' && Object.keys(parsed).length > 0) {
            return parsed;
        }
        const merged = getStageOutputContent('stage2', 'scene_markdown')
            || String(activeEpisode?.ai_scene_analysis_scene_markdown || '').trim();
        return splitSceneMarkdownTableBySceneId(merged);
    }, [
        activeEpisode?.ai_scene_analysis_scene_markdown,
        currentStageOutputs,
        getStageOutputContent,
        parseSceneMarkdownBySceneMap,
        splitSceneMarkdownTableBySceneId,
    ]);

    const workflowCompletenessStats = useMemo(() => {
        const importReport = resolveWorkflowImportReport(analysisUiReport, activeEpisode?.id);
        const scenePostReport = importReport?.sceneSubjectPostImportReport || {};
        const dbEntities = Array.isArray(availableSubjectAssets) ? availableSubjectAssets : [];

        const sceneMarkdownMerged = String(
            getStageOutputContent('stage2', 'scene_markdown')
            || activeEpisode?.ai_scene_analysis_scene_markdown
            || ''
        ).trim();
        const byScene = stage2SceneMarkdownByScene || {};
        const bySceneIds = Object.keys(byScene).filter((sceneId) => {
            const entry = byScene[sceneId];
            const text = String(entry?.markdown || entry || '').trim();
            return Boolean(text);
        });
        const splitSceneMap = sceneMarkdownMerged ? splitSceneMarkdownTableBySceneId(sceneMarkdownMerged) : {};
        const splitSceneIds = Object.keys(splitSceneMap || {}).filter((sceneId) => {
            const text = String(splitSceneMap[sceneId] || '').trim();
            return Boolean(text);
        });
        let analysisSceneCount = Math.max(bySceneIds.length, splitSceneIds.length);
        if (!analysisSceneCount && sceneMarkdownMerged) {
            const parsed = parseMarkdownTable(normalizeLlmMarkdownTable(sceneMarkdownMerged));
            analysisSceneCount = Array.isArray(parsed?.rows) ? parsed.rows.length : 0;
        }

        const importedSceneCount = firstPositiveFiniteNumber(
            analysisUiReport?.resolvedSceneImportCount,
            importReport?.dbPersistedCounts?.scenes?.currentEpisode,
            resolveImportReportSceneCount(importReport, scenePostReport, diagnosticsEpisodeSceneCount),
            diagnosticsEpisodeSceneCount,
        );

        const subjectIndexText = String(resolveSubjectIndexTextForAssetRerun() || '').trim();
        const subjectEntries = parseSubjectIndexEntriesForAssetRerun(subjectIndexText);
        const subjectEntriesByCategory = {
            characters: subjectEntries.filter((entry) => entry?.category === 'characters'),
            props: subjectEntries.filter((entry) => entry?.category === 'props'),
            environments: subjectEntries.filter((entry) => entry?.category === 'environments'),
            posters: subjectEntries.filter((entry) => entry?.category === 'posters'),
        };
        const subjectIndexCounts = {
            character: subjectEntriesByCategory.characters.length,
            prop: subjectEntriesByCategory.props.length,
            environment: subjectEntriesByCategory.environments.length,
            poster: subjectEntriesByCategory.posters.length,
        };

        const assetDesignRaw = String(
            getStageOutputContent('stage3', 'asset_design_json')
            || activeEpisode?.ai_entity_design_result
            || llmAssetRawResultContent
            || ''
        ).trim();
        const assetPayload = getAnalysisEntitiesPayloadFromJsonText(assetDesignRaw) || {};
        const assetDesignItems = {
            character: Array.isArray(assetPayload?.characters) ? assetPayload.characters : [],
            prop: Array.isArray(assetPayload?.props) ? assetPayload.props : [],
            environment: Array.isArray(assetPayload?.environments) ? assetPayload.environments : [],
            poster: [
                ...(Array.isArray(assetPayload?.posters) ? assetPayload.posters : []),
                ...(Array.isArray(assetPayload?.covers) ? assetPayload.covers : []),
            ],
        };
        const assetDesignCounts = {
            character: assetDesignItems.character.length,
            prop: assetDesignItems.prop.length,
            environment: assetDesignItems.environment.length,
            poster: assetDesignItems.poster.length,
        };
        const hasAssetDesignPayload = Object.values(assetDesignCounts).some((count) => count > 0);

        const dbEntityCountsByType = {
            character: countDbEntitiesByType('character', dbEntities),
            prop: countDbEntitiesByType('prop', dbEntities),
            environment: countDbEntitiesByType('environment', dbEntities),
            poster: countDbEntitiesByType('poster', dbEntities),
        };

        const resolveImportedAssetCount = (type, categoryKey, categoryEntries, designItems) => {
            const fromReport = resolveImportReportAssetHandledCount(importReport, type, categoryKey);
            const fromResolved = toPositiveCount(analysisUiReport?.resolvedAssetHandledCounts?.[type]);
            const fromDbMatch = hasAssetDesignPayload
                ? countEntityPayloadItemsCoveredInDb(designItems, type, dbEntities)
                : countSubjectIndexEntriesCoveredInDb(categoryEntries, type, dbEntities);
            const fromDbTotal = toPositiveCount(dbEntityCountsByType[type]);
            return Math.max(fromReport, fromResolved, fromDbMatch, fromDbTotal);
        };

        const buildAssetRow = (key, labelZh, labelEn, categoryKey) => {
            const subjectIndexCount = subjectIndexCounts[key] || 0;
            const designCount = assetDesignCounts[key] || 0;
            const analysisCount = hasAssetDesignPayload
                ? Math.max(designCount, key === 'poster' ? subjectIndexCount : designCount)
                : subjectIndexCount;
            const importedCount = resolveImportedAssetCount(
                key,
                categoryKey,
                subjectEntriesByCategory[categoryKey] || [],
                assetDesignItems[key] || [],
            );
            return {
                key,
                labelZh,
                labelEn,
                analysisCount,
                importedCount,
                status: resolveCompletenessStatus(analysisCount, importedCount),
            };
        };

        const rows = [
            {
                key: 'scenes',
                labelZh: '场景',
                labelEn: 'Scenes',
                analysisCount: analysisSceneCount,
                importedCount: importedSceneCount,
                status: resolveCompletenessStatus(analysisSceneCount, importedSceneCount),
            },
            buildAssetRow('character', '角色', 'Characters', 'characters'),
            buildAssetRow('prop', '道具', 'Props', 'props'),
            buildAssetRow('environment', '环境', 'Environments', 'environments'),
            buildAssetRow('poster', '封面', 'Poster', 'posters'),
        ];

        const visibleRows = rows.filter((row) => row.analysisCount > 0 || row.importedCount > 0);
        const summaryItems = (visibleRows.length > 0 ? visibleRows : rows).map((row) => {
            const statusMeta = {
                ok: { mark: '✓', className: 'text-emerald-300' },
                partial: { mark: '⚠', className: 'text-amber-300' },
                missing: { mark: '⚠', className: 'text-red-300' },
                extra: { mark: '+', className: 'text-sky-300' },
                none: { mark: '—', className: 'text-white/35' },
            }[row.status] || { mark: '—', className: 'text-white/35' };
            return { ...row, mark: statusMeta.mark, className: statusMeta.className };
        });
        const hasAnyData = rows.some((row) => row.analysisCount > 0 || row.importedCount > 0);
        const hasIncomplete = rows.some((row) => ['partial', 'missing'].includes(row.status));

        return {
            summaryItems,
            hasAnyData,
            hasIncomplete,
        };
    }, [
        activeEpisode?.ai_entity_design_result,
        activeEpisode?.ai_scene_analysis_scene_markdown,
        activeEpisode?.id,
        analysisUiReport,
        availableSubjectAssets,
        diagnosticsEpisodeSceneCount,
        getAnalysisEntitiesPayloadFromJsonText,
        getStageOutputContent,
        llmAssetRawResultContent,
        normalizeLlmMarkdownTable,
        parseSubjectIndexEntriesForAssetRerun,
        resolveSubjectIndexTextForAssetRerun,
        splitSceneMarkdownTableBySceneId,
        stage2SceneMarkdownByScene,
    ]);

    const stage2StageCards = useMemo(() => {
        const sceneMarkdownMerged = String(
            getStageOutputContent('stage2', 'scene_markdown')
            || activeEpisode?.ai_scene_analysis_scene_markdown
            || ''
        ).trim();
        const byScene = stage2SceneMarkdownByScene || {};
        const sceneIds = Object.keys(byScene).sort((leftId, rightId) => {
            const leftOrder = Number(byScene[leftId]?.scene_order) || 0;
            const rightOrder = Number(byScene[rightId]?.scene_order) || 0;
            if (leftOrder !== rightOrder) return leftOrder - rightOrder;
            return String(leftId).localeCompare(String(rightId));
        });

        const cards = [];

        if (sceneMarkdownMerged) {
            cards.push({
                key: 'stage2-scene-markdown-merged',
                eyebrow: t('第二阶段', 'Stage 2'),
                title: t('场景分析结果（合并）', 'Scene Analysis (Merged)'),
                status: 'completed',
                badge: t('可导入', 'Importable'),
                summary: t('全部场景合并 Markdown 表，可一次性重新导入。', 'Merged markdown table for all scenes; re-import in one action.'),
                content: sceneMarkdownMerged,
                actions: [
                    {
                        key: 'reimport-stage2-scene-markdown-merged',
                        label: t('全部导入', 'Import All'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: sceneMarkdownMerged,
                            importType: 'scene',
                            label: 'stage2 scene markdown merged',
                        }),
                        disabled: isAnalyzing || !sceneMarkdownMerged,
                        loading: false,
                    },
                    {
                        key: 'restart-stage2-card',
                        label: t('重跑覆盖', 'Rerun & Overwrite'),
                        icon: 'refresh',
                        onClick: handleRerunSceneBeatsOnly,
                        disabled: isAnalyzing || !getStageOutputContent('stage1', 'adapted_script'),
                        loading: isAnalyzing,
                    },
                ],
                placeholder: t('第二阶段尚未生成场景 Markdown。', 'No Stage 2 scene markdown yet.'),
            });
        }

        sceneIds.forEach((sceneId) => {
            const entry = byScene[sceneId] || {};
            const sceneContent = String(entry.markdown || '').trim();
            const sceneLabel = String(entry.scene_name || sceneId).trim() || sceneId;
            cards.push({
                key: `stage2-scene-markdown-${sceneId}`,
                eyebrow: t('第二阶段', 'Stage 2'),
                title: `${t('场景分析', 'Scene Analysis')} · ${sceneLabel}`,
                status: sceneContent ? 'completed' : 'idle',
                badge: sceneContent ? t('可导入', 'Importable') : t('待输出', 'Pending'),
                summary: t('该场的场景 Markdown 表，可单独导入数据库或重跑。', 'Per-scene markdown table; import to DB or rerun individually.'),
                content: sceneContent,
                actions: [
                    {
                        key: `reimport-stage2-scene-${sceneId}`,
                        label: t('导入该场景', 'Import This Scene'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: sceneContent,
                            importType: 'scene',
                            label: `stage2 scene ${sceneId}`,
                        }),
                        disabled: isAnalyzing || !sceneContent,
                        loading: false,
                    },
                    {
                        key: `rerun-stage2-scene-${sceneId}`,
                        label: t('重跑该场景', 'Rerun This Scene'),
                        icon: 'refresh',
                        onClick: () => executeSceneBeatsRerun({ mode: 'single', sceneId }),
                        disabled: isAnalyzing || !getStageOutputContent('stage1', 'adapted_script'),
                        loading: isAnalyzing,
                    },
                ],
                placeholder: t('该场尚未生成场景 Markdown。', 'No scene markdown for this scene yet.'),
            });
        });

        const subjectIndex = extractPureSubjectIndexText(
            String(activeEpisode?.ai_scene_analysis_subject_index || getStageOutputContent('stage2', 'subject_index') || subjectIndexText || '').trim()
        );

        cards.push({
                key: 'stage2-subject-index',
                eyebrow: t('第二阶段', 'Stage 2'),
                title: t('资产清单', 'Asset Index'),
                status: subjectIndex ? 'completed' : 'idle',
                badge: subjectIndex ? t('可导入', 'Importable') : t('待输出', 'Pending'),
                summary: t('单独保存第二阶段的资产清单，可按当前结果重新导入。', 'Stores the Stage 2 asset index separately for re-import.'),
                content: subjectIndex,
                onSave: persistSubjectIndexEdit,
                actions: [
                    {
                        key: 'reimport-stage2-subject-index',
                        label: t('重新导入', 'Re-import'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: subjectIndex,
                            importType: 'auto',
                            label: 'stage2 subject index',
                        }),
                        disabled: isAnalyzing || !subjectIndex,
                        loading: false,
                    },
                    {
                        key: 'restart-stage2-subject-index',
                        label: t('重跑覆盖', 'Rerun & Overwrite'),
                        icon: 'refresh',
                        onClick: handleRestartStage2,
                        disabled: isAnalyzing || !getStageOutputContent('stage1', 'adapted_script'),
                        loading: isAnalyzing,
                    },
                ],
                placeholder: t('第二阶段尚未生成资产清单。', 'No Stage 2 asset index yet.'),
            });

        return cards;
    }, [activeEpisode?.ai_scene_analysis_scene_markdown, activeEpisode?.ai_scene_analysis_subject_index, executeSceneBeatsRerun, extractPureSubjectIndexText, getStageOutputContent, handleImportStageArtifact, handleRerunSceneBeatsOnly, handleRestartStage2, isAnalyzing, persistSubjectIndexEdit, stage2SceneMarkdownByScene, subjectIndexText, t]);

    const stage3StageCards = useMemo(() => {
        const stage3ArtifactJson = getStageOutputContent('stage3', 'asset_design_json');
        const liveStage3RawText = String(llmAssetRawResultContent || activeEpisode?.ai_entity_design_result || '').trim();
        const liveStage3Payload = getAnalysisEntitiesPayloadFromJsonText(liveStage3RawText);
        const assetDesignJson = String(
            stage3ArtifactJson
            || (liveStage3Payload ? JSON.stringify(liveStage3Payload, null, 2) : liveStage3RawText)
            || ''
        ).trim();
        const assetDesignPayload = getAnalysisEntitiesPayloadFromJsonText(assetDesignJson);

        const cards = [];
        
        cards.push({
            key: 'stage3-asset-design-json',
            eyebrow: t('第三阶段', 'Stage 3'),
            title: t('资产设计 - 全部', 'Asset Design (All)'),
            status: assetDesignJson ? 'completed' : 'idle',
            badge: assetDesignJson ? t('可导入', 'Importable') : t('待输出', 'Pending'),
            summary: t('全部的资产设计结果，可重新导入或重跑全部。', 'Shows all Stage 3 asset-design result and supports re-import/rerun.'),
            content: formatArtifactContent(assetDesignJson, 'json'),
            actions: [
                {
                    key: 'reimport-stage3-asset-design',
                    label: t('全部导入', 'Import All'),
                    icon: 'refresh',
                    onClick: () => handleImportStageArtifact({
                        content: assetDesignJson,
                        importType: 'json',
                        label: 'stage3 asset design json',
                        importOptions: {
                            subjectsJson: assetDesignPayload || null,
                            suppressAlerts: false,
                        },
                    }),
                    disabled: isAnalyzing || !assetDesignJson,
                    loading: false,
                },
                {
                    key: 'restart-stage3-card',
                    label: t('选择重跑', 'Choose Rerun'),
                    icon: 'play',
                    onClick: () => openPhase2RerunModal({ mode: 'all' }),
                    disabled: isAnalyzing || isRetryingPhase2 || !hasAssetGenerationPrerequisite,
                    loading: isRetryingPhase2 && (!phase2RetryOptionsRef.current?.targetEntityTypes),
                }
            ],
            placeholder: t('第三阶段尚未返回资产设计结果。', 'No Stage 3 asset design output yet.'),
        });

        const categories = [
            { key: 'characters', labelZh: '角色设计', labelEn: 'Characters', btnZh: '重跑角色', btnEn: 'Regen Characters' },
            { key: 'props', labelZh: '道具设计', labelEn: 'Props', btnZh: '重跑道具', btnEn: 'Regen Props' },
            { key: 'environments', labelZh: '环境设计', labelEn: 'Environments', btnZh: '重跑环境', btnEn: 'Regen Environments' },
            { key: 'posters', labelZh: '封面设计', labelEn: 'Posters', btnZh: '重跑封面', btnEn: 'Regen Posters' },
        ];

        categories.forEach(cat => {
            let catObj = null;
            if (assetDesignPayload && assetDesignPayload[cat.key] && Array.isArray(assetDesignPayload[cat.key]) && assetDesignPayload[cat.key].length > 0) {
                 catObj = { [cat.key]: assetDesignPayload[cat.key] };
                 if (cat.key === 'posters' && assetDesignPayload.covers && Array.isArray(assetDesignPayload.covers) && assetDesignPayload.covers.length > 0) {
                     catObj.covers = assetDesignPayload.covers;
                 }
            } else if (cat.key === 'posters' && assetDesignPayload && assetDesignPayload.covers && Array.isArray(assetDesignPayload.covers) && assetDesignPayload.covers.length > 0) {
                 catObj = { covers: assetDesignPayload.covers };
            }

            const catJson = catObj ? JSON.stringify(catObj, null, 2) : '';

            cards.push({
                key: `stage3-asset-${cat.key}`,
                eyebrow: t('第三阶段局部', 'Stage 3 Partial'),
                title: t(cat.labelZh, cat.labelEn),
                status: catJson ? 'completed' : 'idle',
                badge: catJson ? t('可导入', 'Importable') : t('待输出', 'Pending'),
                summary: t(`局部的${cat.labelZh}结果。`, `Stage 3 ${cat.labelEn} result.`),
                content: formatArtifactContent(catJson, 'json'),
                actions: [
                    {
                        key: `reimport-stage3-${cat.key}`,
                        label: t('局部导入', 'Import Partial'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: catJson,
                            importType: 'json',
                            label: `stage3 ${cat.key} json`,
                            importOptions: {
                                subjectsJson: catObj || null,
                                suppressAlerts: false,
                            },
                        }),
                        disabled: isAnalyzing || !catJson,
                        loading: false,
                    },
                    {
                        key: `restart-stage3-${cat.key}`,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'repeat',
                        onClick: () => handleRetryPhase2({ targetEntityTypes: cat.key === 'posters' ? ['posters', 'covers'] : [cat.key] }),
                        disabled: isAnalyzing || isRetryingPhase2 || !hasAssetGenerationPrerequisite,
                        loading: isRetryingPhase2 && phase2RetryOptionsRef.current?.targetEntityTypes?.includes(cat.key),
                    }
                ],
                placeholder: t(`尚未返回${cat.labelZh}结果。`, `No ${cat.labelEn} output yet.`),
            });
        });

        return cards;
    }, [activeEpisode?.ai_entity_design_result, formatArtifactContent, getAnalysisEntitiesPayloadFromJsonText, getStageOutputContent, handleImportStageArtifact, hasAssetGenerationPrerequisite, handleRetryPhase2, isAnalyzing, isRetryingPhase2, llmAssetRawResultContent, openPhase2RerunModal, t]);

    if (!activeEpisode) return <div className="p-8 text-muted-foreground">{t('请选择或创建一个分集开始写作。', 'Select or create an episode to start writing.')}</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
            <MarkdownHelpModal
                open={manualModalOpen}
                initialDocKey="analysis"
                onClose={() => setManualModalOpen(false)}
                uiLang={uiLang}
            />
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
                    <button
                        type="button"
                        onClick={() => setManualModalOpen(true)}
                        className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-white hover:bg-white/20 border border-white/10 flex items-center gap-2"
                        title={t('查看剧本分析操作手册', 'View script analysis manual')}
                    >
                        <Info className="w-4 h-4" /> {t('剧本分析操作手册', 'Script Analysis Manual')}
                    </button>
                    {isRawMode && (
                        <>
                            <FunctionApiSelector
                                functionName="script_analysis"
                                configs={functionApiConfigs}
                                onChange={setSelectedScriptAnalysisApiId}
                            />
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
                                        <Wand2 className="w-4 h-4" /> {t('AI 剧本分析与生成', 'AI Script Analysis & Generation')}
                                    </>
                                )}
                            </button>
                        </>
                    )}
                    {canStopAnalysisTask && (
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
                </div>
            </div>

            <div className="mb-4 rounded-xl border border-white/10 bg-black/20 p-4">
                <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-sm shrink-0">
                        <div className="w-1 h-5 bg-purple-500 rounded-full"></div>
                        {t('进度诊断面板', 'Workflow Diagnostics')}
                    </div>
                    {(() => {
                        const storyboardAutoStarted = Boolean(analysisUiReport?.storyboardAutoStarted);
                        const storyboardCanStart = Boolean(getStageOutputContent('stage2', 'scene_markdown'));
                        return (
                    <div className="flex-1 w-full flex items-center justify-between relative max-w-3xl px-8 mt-2 md:mt-0">
                        <div className="absolute top-4 left-10 right-10 h-0.5 bg-white/10 -z-10"></div>
                        
                        <div className="flex flex-col items-center gap-2 relative">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold z-10 border ${!!getStageOutputContent('stage1', 'adapted_script') ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]' : 'bg-white/5 border-white/20 text-white/50 backdrop-blur-sm'}`}>
                                {!!getStageOutputContent('stage1', 'adapted_script') ? <Check className="w-4 h-4" /> : 1}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('剧本优化', 'Script Opt')}</span>
                                {!!getStageOutputContent('stage1', 'adapted_script') ? (
                                    <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                ) : (
                                    <span className={`text-[10px] ${isAnalyzing ? 'text-purple-300' : 'text-white/30'}`}>
                                        {isAnalyzing ? (
                                            <span className="flex items-center gap-1">
                                                <Loader2 className="w-3 h-3 animate-spin"/>
                                                {t('处理中', 'Processing')}
                                            </span>
                                        ) : t('等待中', 'Pending')}
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col items-center gap-2 relative">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold z-10 border ${!!getStageOutputContent('stage2', 'subject_index') ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]' : (!!getStageOutputContent('stage1', 'adapted_script') ? 'bg-purple-500/50 border-purple-400 text-white backdrop-blur-sm shadow-[0_0_10px_rgba(168,85,247,0.3)]' : 'bg-white/5 border-white/20 text-white/50 backdrop-blur-sm')}`}>
                                {!!getStageOutputContent('stage2', 'subject_index') ? <Check className="w-4 h-4" /> : 2}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('清单整理', 'List Preparation')}</span>
                                {!!getStageOutputContent('stage2', 'subject_index') ? (
                                     <div className="flex items-center gap-1">
                                         <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                         <button onClick={handleRestartStage2} disabled={isAnalyzing} className="text-[10px] px-1 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 disabled:opacity-50 hover:text-white transition-colors">
                                            {t('重跑', 'Rerun')}
                                         </button>
                                     </div>
                                ) : (
                                    !!getStageOutputContent('stage1', 'adapted_script') ? (
                                        <button onClick={handleRestartStage2} disabled={isAnalyzing} className="text-[10px] px-2 py-0.5 rounded border border-purple-500/50 text-purple-200 bg-purple-500/20 hover:bg-purple-500/30 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1">
                                            {isAnalyzing ? <Loader2 className="w-3 h-3 animate-spin"/> : null}
                                            {isAnalyzing ? t('处理中', 'Processing') : t('可重跑', 'Ready')}
                                        </button>
                                    ) : (
                                        <span className="text-[10px] text-white/30">{t('待上一步完成', 'Wait previous step')}</span>
                                    )
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col items-center gap-2 relative">
                             <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold z-10 border ${!!getStageOutputContent('stage2', 'scene_markdown') ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]' : (!!getStageOutputContent('stage2', 'subject_index') ? 'bg-purple-500/50 border-purple-400 text-white backdrop-blur-sm shadow-[0_0_10px_rgba(168,85,247,0.3)]' : 'bg-white/5 border-white/20 text-white/50 backdrop-blur-sm')}`}>
                                {!!getStageOutputContent('stage2', 'scene_markdown') ? <Check className="w-4 h-4" /> : 3}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('场景拆解', 'Scene Breakdown')}</span>
                                {!!getStageOutputContent('stage2', 'scene_markdown') ? (
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                        <button onClick={handleRerunSceneBeatsOnly} disabled={isAnalyzing} className="text-[10px] px-1 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 disabled:opacity-50 hover:text-white transition-colors">
                                            {t('重排', 'Rerun')}
                                        </button>
                                    </div>
                                ) : (
                                    !!getStageOutputContent('stage2', 'subject_index') ? (
                                        <button onClick={handleRerunSceneBeatsOnly} disabled={isAnalyzing} className="text-[10px] px-2 py-0.5 rounded border border-purple-500/50 text-purple-200 bg-purple-500/20 hover:bg-purple-500/30 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1">
                                            {isAnalyzing ? <Loader2 className="w-3 h-3 animate-spin"/> : null}
                                            {isAnalyzing ? t('处理中', 'Processing') : t('可重跑', 'Ready')}
                                        </button>
                                    ) : (
                                        <span className="text-[10px] text-white/30">{t('待上一步完成', 'Wait previous step')}</span>
                                    )
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col items-center gap-2 relative">
                             <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold z-10 border ${storyboardAutoStarted ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]' : (storyboardCanStart ? 'bg-purple-500/50 border-purple-400 text-white backdrop-blur-sm shadow-[0_0_10px_rgba(168,85,247,0.3)]' : 'bg-white/5 border-white/20 text-white/50 backdrop-blur-sm')}`}>
                                {storyboardAutoStarted ? <Check className="w-4 h-4" /> : 4}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('镜头任务', 'Storyboard Tasks')}</span>
                                {storyboardAutoStarted ? (
                                    <span className="text-[10px] text-emerald-400/80">{t('已启动', 'Started')}</span>
                                ) : (
                                    storyboardCanStart ? (
                                        <span className="text-[10px] text-purple-300">{t('待触发', 'Pending')}</span>
                                    ) : (
                                        <span className="text-[10px] text-white/30">{t('待场景拆解完成', 'Wait scene breakdown')}</span>
                                    )
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col items-center gap-2 relative">
                             <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold z-10 border ${!!getStageOutputContent('stage3', 'asset_design_json') ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]' : (hasAssetGenerationPrerequisite ? 'bg-purple-500/50 border-purple-400 text-white backdrop-blur-sm shadow-[0_0_10px_rgba(168,85,247,0.3)]' : 'bg-white/5 border-white/20 text-white/50 backdrop-blur-sm')}`}>
                                {!!getStageOutputContent('stage3', 'asset_design_json') ? <Check className="w-4 h-4" /> : 5}
                            </div>
                            <div className="flex flex-col items-center gap-1 text-center">
                                <span className="text-xs font-semibold">{t('视觉资产', 'Visual Assets')}</span>
                                {!!getStageOutputContent('stage3', 'asset_design_json') ? (
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] text-emerald-400/80">{t('已完成', 'Ready')}</span>
                                        <button onClick={() => openPhase2RerunModal({ mode: 'all' })} disabled={isAnalyzing || isRetryingPhase2} className="text-[10px] px-1 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 disabled:opacity-50 hover:text-white transition-colors flex items-center gap-1">
                                            {isRetryingPhase2 ? <Loader2 className="w-3 h-3 animate-spin"/> : null}
                                            {t('重跑', 'Rerun')}
                                        </button>
                                    </div>
                                ) : (
                                    hasAssetGenerationPrerequisite ? (
                                         <button onClick={() => openPhase2RerunModal({ mode: 'all' })} disabled={isAnalyzing || isRetryingPhase2} className="text-[10px] px-2 py-0.5 rounded border border-purple-500/50 text-purple-200 bg-purple-500/20 hover:bg-purple-500/30 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1">
                                            {isRetryingPhase2 ? <Loader2 className="w-3 h-3 animate-spin"/> : null}
                                            {isRetryingPhase2 ? t('处理中', 'Processing') : t('可重跑', 'Ready')}
                                        </button>
                                    ) : (
                                        <span className="text-[10px] text-white/30">{t('待清单整理完成', 'Wait list preparation')}</span>
                                    )
                                )}
                            </div>
                        </div>
                    </div>
                        );
                    })()}
                </div>

                {workflowCompletenessStats.hasAnyData && (
                    <div className="mt-3 pt-3 border-t border-white/10 text-[11px] text-white/70 leading-relaxed">
                        <span className="text-white/55 font-semibold mr-2">
                            {t('完整性', 'Completeness')}:
                        </span>
                        {workflowCompletenessStats.summaryItems.map((item, index) => (
                            <span key={item.key} className={`${item.className}${index > 0 ? ' ml-3' : ''}`}>
                                {t(item.labelZh, item.labelEn)} {item.analysisCount}→{item.importedCount}{item.mark}
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {(analysisFlowStatus.phase !== 'idle' || analysisUiReport || analysisFlowStatusHistory.length > 0) && (
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
                                onClick={dismissAnalysisProgressPanel}
                                className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20"
                            >
                                {t('关闭', 'Close')}
                            </button>
                        )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3">
                                                                        {(() => {
                            const storyboardAutoStarted = Boolean(analysisUiReport?.storyboardAutoStarted);
                            return [
                            { key: 'script_opt', label: t('剧本统筹', 'Script Opt') },
                            { key: 'extract_assets', label: t('清单整理', 'List Preparation') },
                            { key: 'scene_beats', label: t('场景拆解', 'Scene Breakdown') },
                            { key: 'storyboard', label: t('镜头任务', 'Storyboard Tasks') },
                            { key: 'assets_gen', label: t('视觉资产', 'Visual Assets') },
                            { key: 'completed', label: t('AI 总结报告', 'Report') },
                        ].map((step, idx) => {
                            const stepOrder = ['script_opt', 'extract_assets', 'scene_beats', 'storyboard', 'assets_gen', 'completed'];
                            const phase = analysisFlowStatus.phase || 'idle';
                            const currentIndex = stepOrder.indexOf(phase);
                            const stepIndex = stepOrder.indexOf(step.key);
                            const hasFinalReport = !!(analysisUiReport && analysisUiReport.status !== 'running');
                            const isTerminalWarning = phase === 'warning';
                            const isTerminalFailed = phase === 'failed';
                            
                            const hasArtifact = (key) => {
                                if (key === 'script_opt') return !!getStageOutputContent('stage1', 'adapted_script');
                                if (key === 'extract_assets') return !!getStageOutputContent('stage2', 'subject_index');
                                if (key === 'scene_beats') return !!getStageOutputContent('stage2', 'scene_markdown');
                                if (key === 'storyboard') return storyboardAutoStarted;
                                if (key === 'assets_gen') return !!getStageOutputContent('stage3', 'asset_design_json');
                                if (key === 'completed') return hasFinalReport;
                                return false;
                            };
                            
                            const isDone = !isTerminalFailed && (
                                hasFinalReport
                                    ? stepIndex <= 4
                                    : (isTerminalWarning ? stepIndex <= 2 : ((currentIndex > stepIndex) || phase === 'completed' || hasArtifact(step.key)))
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
                        });
                        })()}
                    </div>

                    {analysisFlowStatusHistory.length > 0 && (
                        <div className="mb-2 space-y-1.5">
                            {analysisFlowStatusHistory.map((item, index) => {
                                const isLatest = index === analysisFlowStatusHistory.length - 1;
                                const startedTime = formatHistoryClock(item?.createdAt);
                                const endedTime = formatHistoryClock(item?.endedAt);
                                const phaseLabel = getBusinessPhaseLabel(item?.phase);
                                const displayMessage = toBusinessHistoryMessage(item?.message);
                                const highlightHint = String(item?.highlightHint || '').trim();
                                return (
                                    <div key={item.id} className={`text-xs rounded-md px-2.5 py-2 border ${isLatest ? 'border-white/20 bg-black/20 opacity-100' : 'border-white/10 bg-black/10 opacity-90'}`}>
                                        <div className="flex items-start justify-between gap-3">
                                            <span className="font-semibold tracking-wide text-[10px] opacity-80">{phaseLabel}</span>
                                            <span className="text-[10px] opacity-60">
                                                {startedTime
                                                    ? (
                                                        endedTime
                                                            ? `${startedTime} ~ ${endedTime} · #${index + 1}`
                                                            : `${startedTime} ~ ${t('进行中', 'Running')} · #${index + 1}`
                                                    )
                                                    : `#${index + 1}`
                                                }
                                            </span>
                                        </div>
                                        <div className="mt-1 opacity-95 whitespace-pre-wrap">{displayMessage || item.message}</div>
                                        {highlightHint && (
                                            <div className={`mt-1.5 rounded-md border px-2 py-1.5 text-[11px] font-semibold leading-snug ${isLatest ? 'border-emerald-400/50 bg-emerald-500/20 text-emerald-100 shadow-[0_0_12px_rgba(52,211,153,0.15)] animate-pulse' : 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200/90'}`}>
                                                🎨 {highlightHint}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {(isAnalyzing || isRetryingPhase2) && String(analysisFlowStatus?.highlightHint || '').trim() && (
                        <div className="mb-2 rounded-lg border border-emerald-400/45 bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-100 shadow-[0_0_14px_rgba(52,211,153,0.18)] animate-pulse">
                            🎨 {String(analysisFlowStatus.highlightHint).trim()}
                        </div>
                    )}

                    {isAnalyzing && (
                        <div className="mb-2 text-[11px] text-amber-200/90">
                            {t('剧本分析进行中...', 'Script analysis in progress...')} ({formatDurationMs(analysisHeartbeatElapsedMs)})
                            <span className="ml-2 text-amber-100/80">
                                {t('复杂剧本通常需要较长时间。', 'Complex scripts usually take longer.')}
                            </span>
                        </div>
                    )}

                    {canStopAnalysisTask && (
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
                                    <span className="text-purple-300 font-semibold"> {analysisAssetCounts.inserted.character} </span>{t('位角色', 'characters')}、
                                    <span className="text-emerald-300 font-semibold"> {analysisAssetCounts.inserted.environment} </span>{t('个空镜', 'environments')}、
                                    <span className="text-amber-300 font-semibold"> {analysisAssetCounts.inserted.prop} </span>{t('个道具', 'props')}
                                    <span className="ml-1 text-white/70">(
                                        {t('当前总量', 'Current total')}:
                                        <span className="text-purple-200 font-semibold"> {analysisAssetCounts.total.character} </span>{t('角色', 'characters')}、
                                        <span className="text-emerald-200 font-semibold"> {analysisAssetCounts.total.environment} </span>{t('空镜', 'environments')}、
                                        <span className="text-amber-200 font-semibold"> {analysisAssetCounts.total.prop} </span>{t('道具', 'props')}
                                    )</span>。
                                </div>
                                <div>
                                    <span className="font-medium">🔍 {t('场景画面搭建', 'Scene Construction')}:</span> {t('本次新增', 'Inserted this run')}
                                    <span className="text-white font-semibold"> {(analysisUiReport.importReport?.dbRunInsertedCounts?.scenes?.created) || (analysisUiReport.importReport?.importStats?.scenesCreated) || (analysisUiReport.importReport?.sceneSubjectPostImportReport?.checkedSceneCount) || (analysisUiReport.importReport?.dbPersistedCounts?.scenes?.currentEpisode) || 0} </span>{t('个场景', 'shots')}
                                    <span className="ml-1 text-white/70">({t('当前分集总量', 'Current episode total')}: <span className="text-white font-semibold">{analysisUiReport.importReport?.dbPersistedCounts?.scenes?.currentEpisode ?? analysisUiReport.importReport?.sceneSubjectPostImportReport?.checkedSceneCount ?? 0}</span>)</span>。
                                </div>
                                <div>
                                    <span className="font-medium">⏱️ {t('运行时长', 'Duration')}:</span> <span className="text-blue-300 font-semibold">{formatDurationMs(analysisUiReport.durationMs || analysisUiReport?.phaseTimings?.totalMs)}</span>
                                </div>
                                {String(analysisUiReport?.warning || '').trim() && (
                                    <div className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2.5 py-2 text-amber-100 whitespace-pre-wrap">
                                        <span className="font-medium">⚠️ {t('提示', 'Notice')}:</span> {String(analysisUiReport.warning).trim()}
                                    </div>
                                )}
                                {displayedReviewIssues.length > 0 && (
                                    <div className="rounded-md border border-amber-400/35 bg-amber-500/10 px-2.5 py-2 text-amber-100 space-y-2">
                                        <div className="font-medium">⚠️ {t('待复核问题', 'Issues to review')}</div>
                                        <ol className="list-decimal list-inside space-y-1 text-xs whitespace-pre-wrap">
                                            {displayedReviewIssues.map((issue, idx) => (
                                                <li key={`review-issue-${idx}`}>{issue}</li>
                                            ))}
                                        </ol>
                                        <div className="pt-1 space-y-2">
                                            <textarea
                                                value={analysisAttentionNotes}
                                                onChange={(e) => setAnalysisAttentionNotes(e.target.value)}
                                                placeholder={t('可补充修正要求（选填），例如：统一角色命名、补全缺失道具、同一场景不要拆太碎。', 'Optional refinement notes, e.g. unify character names or fill missing props.')}
                                                className="w-full h-20 bg-black/30 border border-amber-400/20 rounded-md px-3 py-2 text-xs text-amber-50 focus:outline-none focus:border-amber-300/40 custom-scrollbar resize-none"
                                            />
                                            <div className="flex flex-wrap justify-end gap-2">
                                                <button
                                                    type="button"
                                                    onClick={handleSupplementSubmitClick}
                                                    disabled={isAnalyzing || !String(llmRawResultContent || llmResultContent || '').trim()}
                                                    className={`px-3 py-1.5 rounded-md text-xs font-bold ${isAnalyzing || !String(llmRawResultContent || llmResultContent || '').trim() ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-400/30'}`}
                                                >
                                                    {t('修正生成结果', 'Refine Generated Result')}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={handleSaveAnalysisAttentionNotes}
                                                    disabled={isSavingAnalysisAttentionNotes}
                                                    className={`px-3 py-1.5 rounded-md text-xs font-bold ${isSavingAnalysisAttentionNotes ? 'bg-white/5 text-muted-foreground cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white border border-white/15'}`}
                                                >
                                                    {isSavingAnalysisAttentionNotes ? t('保存中...', 'Saving...') : t('保存补充说明', 'Save Notes')}
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                            <div className="text-xs text-white/60 space-y-1 pt-1">
                                
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
                        </div>
                    ) : (
        <div className="overflow-auto custom-scrollbar flex-1 w-full">
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
        <div className="flex flex-col gap-4 flex-none max-h-[60vh] mt-4 border-t border-white/10 pt-4 px-6 pb-6 overflow-y-auto custom-scrollbar">
        {/* Stage 1 Panel */}
        <div className="flex-none min-h-[300px]">
            <LLMResultPanel
                title={t('第一阶段：剧本修改说明 / 优化后剧本 / 全局风格', 'Stage 1: Script Notes / Optimized Script / Global Style')}
                t={t}
                stageCards={stage1StageCards}
                placeholder={t('第一阶段产物...', 'Stage 1 outputs...')}
            />
        </div>
        {/* Stage 2 Panel */}
        <div className="flex-none h-auto min-h-[400px]">
            <LLMResultPanel
                title={t('第二阶段：场景分析结果 / 资产清单', 'Stage 2: Scene Analysis Result / Asset Index')}
                t={t}
                stageCards={stage2StageCards}
                placeholder={t('第二阶段产物...', 'Stage 2 outputs...')}
            />
        </div>
        {/* Stage 3 Panel */}
        <div className="flex-none min-h-[300px]">
            <LLMResultPanel
                title={t('第三阶段：资产设计', 'Stage 3: Asset Design')}
                t={t}
                stageCards={stage3StageCards}
                placeholder={t('第三阶段产物...', 'Stage 3 outputs...')}
            />
        </div>
    </div>
        
                </div>
            </div>

            {sceneBeatsRerunModal.open && (
                <div
                    className="fixed inset-0 z-[59] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
                    onClick={() => setSceneBeatsRerunModal((prev) => ({ ...prev, open: false }))}
                >
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-2xl max-h-[84vh] shadow-2xl overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Clapperboard className="w-5 h-5 text-emerald-400" />
                                {t('场景编排重跑选择', 'Scene Beats Rerun')}
                            </h3>
                            <button
                                onClick={() => setSceneBeatsRerunModal((prev) => ({ ...prev, open: false }))}
                                className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-bold transition-colors text-white"
                            >
                                {t('退出', 'Exit')}
                            </button>
                        </div>

                        <div className="p-4 overflow-y-auto custom-scrollbar space-y-4 text-sm">
                            <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-3 text-white/80">
                                <div className="font-semibold text-white">
                                    {t(`已从剧本分隔符识别 ${sceneBeatsRerunCandidates.length} 个场景`, `${sceneBeatsRerunCandidates.length} scene(s) detected from script markers`)}
                                </div>
                                <div className="mt-1 text-xs text-white/55">
                                    {t('按 [SCENE_START] / [SCENE_END] 切分；全部重跑将先同步场景单元，再由后端统一发起 Stage 2.2。', 'Split by [SCENE_START]/[SCENE_END]; rerun all syncs scene units then launches Stage 2.2 orchestration on backend.')}
                                </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                {[
                                    { key: 'all', labelZh: '全部重跑', labelEn: 'Rerun All Scenes' },
                                    { key: 'single', labelZh: '单场重跑', labelEn: 'Rerun One Scene' },
                                ].map((mode) => {
                                    const active = sceneBeatsRerunModal.mode === mode.key;
                                    return (
                                        <button
                                            key={mode.key}
                                            type="button"
                                            onClick={() => {
                                                setSceneBeatsRerunModal((prev) => ({
                                                    ...prev,
                                                    mode: mode.key,
                                                    sceneId: prev.sceneId || sceneBeatsRerunCandidates[0]?.sceneId || '',
                                                }));
                                            }}
                                            className={`rounded-lg border px-3 py-2 text-sm font-bold transition-colors ${active ? 'border-emerald-300/60 bg-emerald-500/25 text-emerald-50' : 'border-white/10 bg-white/5 hover:bg-white/10 text-white/75'}`}
                                        >
                                            {t(mode.labelZh, mode.labelEn)}
                                        </button>
                                    );
                                })}
                            </div>

                            {sceneBeatsRerunModal.mode === 'all' && (
                                <div className="rounded-lg border border-emerald-400/25 bg-emerald-500/10 px-3 py-3 text-emerald-100">
                                    <div className="font-semibold">{t('将同步发起全部场景重跑', 'All scenes will be rerun via sync orchestration')}</div>
                                    <div className="mt-1 text-xs text-emerald-100/75">
                                        {t(`共 ${sceneBeatsRerunCandidates.length} 场，每场单独调用 Stage 2.2 后合并为完整 Scenes Table。`, `${sceneBeatsRerunCandidates.length} scenes; each Stage 2.2 call is merged into the full Scenes Table.`)}
                                    </div>
                                </div>
                            )}

                            {sceneBeatsRerunModal.mode === 'single' && (
                                <div className="space-y-2">
                                    <div className="text-xs font-bold text-white/55 uppercase tracking-wide">{t('选择场景', 'Select Scene')}</div>
                                    <div className="max-h-56 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                        {sceneBeatsRerunCandidates.length > 0 ? sceneBeatsRerunCandidates.map((item) => {
                                            const active = sceneBeatsRerunModal.sceneId === item.sceneId;
                                            return (
                                                <button
                                                    key={item.sceneId}
                                                    type="button"
                                                    onClick={() => setSceneBeatsRerunModal((prev) => ({ ...prev, sceneId: item.sceneId }))}
                                                    className={`w-full text-left rounded-lg border px-3 py-2 transition-colors ${active ? 'border-sky-300/60 bg-sky-500/20 text-sky-50' : 'border-white/10 bg-white/5 hover:bg-white/10 text-white/80'}`}
                                                >
                                                    <div className="text-sm font-semibold">{item.displayLabel || item.sceneId}</div>
                                                    <div className="text-[11px] text-white/50 mt-0.5">
                                                        {t(`场次 ${item.sceneOrder}`, `Scene order ${item.sceneOrder}`)}
                                                    </div>
                                                </button>
                                            );
                                        }) : (
                                            <div className="text-xs text-white/45">{t('没有可重跑的场景。', 'No scenes available to rerun.')}</div>
                                        )}
                                    </div>
                                    <div className="rounded-lg border border-sky-400/25 bg-sky-500/10 px-3 py-3 text-sky-100 text-xs">
                                        {t('仅重跑所选场景，并合并回现有 Scenes Table（其他场景行保持不变）。', 'Only the selected scene is rerun and merged back into the existing Scenes Table.')}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-t border-white/10 bg-white/5 flex items-center justify-between gap-3">
                            <span className="text-xs text-white/45">
                                {t(`可选场景：${sceneBeatsRerunCandidates.length} 个`, `${sceneBeatsRerunCandidates.length} selectable scenes`)}
                            </span>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => setSceneBeatsRerunModal((prev) => ({ ...prev, open: false }))}
                                    className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 hover:bg-white/20 text-white"
                                >
                                    {t('取消', 'Cancel')}
                                </button>
                                <button
                                    type="button"
                                    onClick={confirmSceneBeatsRerunSelection}
                                    disabled={
                                        isAnalyzing
                                        || (sceneBeatsRerunModal.mode === 'single' && !String(sceneBeatsRerunModal.sceneId || '').trim())
                                        || sceneBeatsRerunCandidates.length <= 0
                                    }
                                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isAnalyzing || (sceneBeatsRerunModal.mode === 'single' && !String(sceneBeatsRerunModal.sceneId || '').trim()) || sceneBeatsRerunCandidates.length <= 0 ? 'bg-white/5 text-white/35 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 text-white'}`}
                                >
                                    {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                                    {t('开始重跑', 'Start Rerun')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {phase2RerunModal.open && (
                <div
                    className="fixed inset-0 z-[59] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
                    onClick={closePhase2RerunModal}
                >
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-3xl max-h-[84vh] shadow-2xl overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <RefreshCw className="w-5 h-5 text-purple-400" />
                                {t('资产生成重跑选择', 'Asset Generation Rerun')}
                            </h3>
                            <button
                                onClick={closePhase2RerunModal}
                                className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-bold transition-colors text-white"
                            >
                                {t('退出', 'Exit')}
                            </button>
                        </div>

                        <div className="p-4 overflow-y-auto custom-scrollbar space-y-4 text-sm">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                {[
                                    { key: 'all', labelZh: '全部重跑', labelEn: 'Rerun All' },
                                    { key: 'category', labelZh: '分类重跑', labelEn: 'Rerun Category' },
                                    { key: 'single', labelZh: '单实体重跑', labelEn: 'Rerun One Entity' },
                                ].map((mode) => {
                                    const active = phase2RerunModal.mode === mode.key;
                                    return (
                                        <button
                                            key={mode.key}
                                            type="button"
                                            onClick={() => {
                                                const category = phase2RerunModal.category || 'characters';
                                                const firstSubject = phase2RerunDisplayEntries.find((item) => item.category === category) || phase2RerunDisplayEntries[0];
                                                setPhase2RerunModal((prev) => ({
                                                    ...prev,
                                                    mode: mode.key,
                                                    query: '',
                                                    subjectKey: prev.subjectKey || firstSubject?.key || '',
                                                }));
                                            }}
                                            className={`rounded-lg border px-3 py-2 text-sm font-bold transition-colors ${active ? 'border-purple-300/60 bg-purple-500/25 text-purple-50' : 'border-white/10 bg-white/5 hover:bg-white/10 text-white/75'}`}
                                        >
                                            {t(mode.labelZh, mode.labelEn)}
                                        </button>
                                    );
                                })}
                            </div>

                            {phase2RerunModal.mode === 'all' && (
                                <div className="rounded-lg border border-emerald-400/25 bg-emerald-500/10 px-3 py-3 text-emerald-100">
                                    <div className="font-semibold">{t('将重新生成全部资产类型', 'All asset types will be regenerated')}</div>
                                    <div className="mt-1 text-xs text-emerald-100/75">
                                        {t('包括角色、道具、环境与封面/海报；可在下方编辑 Subject Index 各实体字段。', 'Includes characters, props, environments, posters and covers. Edit Subject Index fields below.')}
                                    </div>
                                </div>
                            )}

                            {(phase2RerunModal.mode === 'category' || phase2RerunModal.mode === 'single') && (
                                <div className="space-y-2">
                                    <div className="text-xs font-bold text-white/55 uppercase tracking-wide">{t('资产类型', 'Asset Type')}</div>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                        {assetRerunCategoryOptions.map((option) => {
                                            const active = phase2RerunModal.category === option.key;
                                            return (
                                                <button
                                                    key={option.key}
                                                    type="button"
                                                    onClick={() => {
                                                        const firstSubject = phase2RerunDisplayEntries.find((item) => item.category === option.key);
                                                        setPhase2RerunModal((prev) => ({
                                                            ...prev,
                                                            category: option.key,
                                                            query: '',
                                                            subjectKey: firstSubject?.key || '',
                                                        }));
                                                    }}
                                                    className={`rounded-lg border px-3 py-2 text-xs font-bold transition-colors ${active ? 'border-sky-300/60 bg-sky-500/25 text-sky-50' : 'border-white/10 bg-white/5 hover:bg-white/10 text-white/75'}`}
                                                >
                                                    {t(option.labelZh, option.labelEn)}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {phase2RerunModal.mode === 'category' && (
                                <div className="rounded-lg border border-sky-400/25 bg-sky-500/10 px-3 py-3 text-sky-100">
                                    <div className="font-semibold">
                                        {t('将仅重跑所选分类', 'Only the selected category will be regenerated')}
                                    </div>
                                    <div className="mt-1 text-xs text-sky-100/75">
                                        {t('系统会从当前 Subject Index 中筛出该分类，再进入资产设计；可在下方编辑各实体字段。', 'The current Subject Index will be filtered to this category before asset design. You can edit entity fields below.')}
                                    </div>
                                </div>
                            )}

                            {(phase2RerunModal.mode === 'all' || phase2RerunModal.mode === 'category' || phase2RerunModal.mode === 'single') && (
                                <div className="space-y-3">
                                    <input
                                        value={phase2RerunModal.query || ''}
                                        onChange={(event) => setPhase2RerunModal((prev) => ({ ...prev, query: event.target.value }))}
                                        placeholder={t('搜索编号或实体名...', 'Search subject number or name...')}
                                        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/90 outline-none focus:border-purple-400/50"
                                    />
                                    <div className="rounded-lg border border-white/10 bg-black/20 max-h-[360px] overflow-y-auto custom-scrollbar divide-y divide-white/5">
                                        {filteredPhase2RerunSubjectEntries.length > 0 ? filteredPhase2RerunSubjectEntries.map((item) => {
                                            const isSingleMode = phase2RerunModal.mode === 'single';
                                            const active = isSingleMode && phase2RerunModal.subjectKey === item.key;
                                            const isEditing = phase2RerunModal.editingSubjectKey === item.key;
                                            const draft = phase2RerunModal.subjectEdits?.[item.key] || {};
                                            const draftFields = (draft.fields && typeof draft.fields === 'object')
                                                ? draft.fields
                                                : normalizeSubjectIndexEntryFields(item.fields, item);
                                            const editableFieldKeys = SUBJECT_INDEX_STANDARD_HEADERS;
                                            return (
                                                <div
                                                    key={item.key}
                                                    className={`w-full text-left px-3 py-2.5 transition-colors ${active ? 'bg-purple-500/25 text-purple-50' : 'hover:bg-white/5 text-white/80'}`}
                                                >
                                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                                        <button
                                                            type="button"
                                                            onClick={() => {
                                                                if (!isSingleMode) return;
                                                                setPhase2RerunModal((prev) => ({ ...prev, subjectKey: item.key }));
                                                            }}
                                                            className={`text-left flex-1 min-w-[180px] ${isSingleMode ? '' : 'cursor-default'}`}
                                                        >
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <span className="font-bold">{item.name}</span>
                                                                {item.subjectNo && <span className="text-[11px] px-1.5 py-0.5 rounded bg-white/10 text-white/65">{item.subjectNo}</span>}
                                                                <span className="text-[11px] px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-100">{item.type}</span>
                                                            </div>
                                                        </button>
                                                        <div className="flex items-center gap-1">
                                                            <button
                                                                type="button"
                                                                onClick={() => beginEditPhase2RerunEntry(item)}
                                                                className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-amber-400/30 bg-amber-500/10 text-amber-100 hover:bg-amber-500/20"
                                                                title={t('编辑 Subject Index 字段', 'Edit Subject Index fields')}
                                                            >
                                                                <Edit3 className="w-3.5 h-3.5" />
                                                                <span className="text-[11px] font-semibold">{t('编辑', 'Edit')}</span>
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDeletePhase2RerunEntry(item)}
                                                                className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-rose-400/30 bg-rose-500/10 text-rose-100 hover:bg-rose-500/20"
                                                                title={t('从本次重跑列表移除', 'Remove from this rerun list')}
                                                            >
                                                                <Trash2 className="w-3.5 h-3.5" />
                                                                <span className="text-[11px] font-semibold">{t('删除', 'Delete')}</span>
                                                            </button>
                                                        </div>
                                                    </div>
                                                    <div className="mt-1 text-[11px] text-white/45 truncate">{item.sourceLine}</div>
                                                    {isEditing && (
                                                        <div className="mt-2 rounded-md border border-white/10 bg-black/20 p-2 space-y-2">
                                                            <div className="text-[11px] text-white/55">
                                                                {t('可编辑 Subject Index 标准字段（编号、类型、中英文名、基准实体、依赖引用、实体属性、剧本覆盖）。', 'Edit standard Subject Index fields: no, type, names, base entity, dependency, attributes, coverage.')}
                                                            </div>
                                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                                {editableFieldKeys.map((fieldKey) => {
                                                                    const stableKey = String(fieldKey || '').trim();
                                                                    if (!stableKey) return null;
                                                                    const rawValue = String(draftFields[stableKey] ?? '');
                                                                    const fieldLabel = SUBJECT_INDEX_FIELD_LABELS[stableKey];
                                                                    const labelText = fieldLabel ? t(fieldLabel.zh, fieldLabel.en) : stableKey;
                                                                    const isLongText = rawValue.length > 80
                                                                        || SUBJECT_INDEX_LONG_TEXT_FIELDS.has(stableKey)
                                                                        || /attributes|coverage|dependency/i.test(stableKey);
                                                                    const spanClass = (stableKey === 'entity_attributes' || stableKey === 'script_entity_coverage')
                                                                        ? 'sm:col-span-2'
                                                                        : '';
                                                                    return (
                                                                        <label key={`${item.key}-${stableKey}`} className={`flex flex-col gap-1 ${spanClass}`}>
                                                                            <span className="text-[11px] text-white/60">{labelText}</span>
                                                                            {isLongText ? (
                                                                                <textarea
                                                                                    value={rawValue}
                                                                                    onChange={(event) => updatePhase2RerunEntryEditField(item.key, stableKey, event.target.value)}
                                                                                    rows={stableKey === 'entity_attributes' ? 5 : 3}
                                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white/90 outline-none focus:border-purple-400/50 resize-y"
                                                                                />
                                                                            ) : (
                                                                                <input
                                                                                    value={rawValue}
                                                                                    onChange={(event) => updatePhase2RerunEntryEditField(item.key, stableKey, event.target.value)}
                                                                                    className="rounded border border-white/15 bg-black/40 px-2 py-1.5 text-xs text-white/90 outline-none focus:border-purple-400/50"
                                                                                />
                                                                            )}
                                                                        </label>
                                                                    );
                                                                })}
                                                            </div>
                                                            <div className="flex items-center justify-end gap-2">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => setPhase2RerunModal((prev) => {
                                                                        const nextEdits = { ...((prev.subjectEdits && typeof prev.subjectEdits === 'object') ? prev.subjectEdits : {}) };
                                                                        delete nextEdits[item.key];
                                                                        return { ...prev, editingSubjectKey: '', subjectEdits: nextEdits };
                                                                    })}
                                                                    className="px-2.5 py-1 text-[11px] rounded border border-white/15 bg-white/5 hover:bg-white/10 text-white/80"
                                                                >
                                                                    {t('取消', 'Cancel')}
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => savePhase2RerunEntryEdit(item.key)}
                                                                    className="px-2.5 py-1 text-[11px] rounded border border-emerald-400/30 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-100 font-semibold"
                                                                >
                                                                    {t('保存', 'Save')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        }) : (
                                            <div className="px-3 py-6 text-center text-sm text-white/45">
                                                {t('当前筛选下没有可编辑的 Subject Index 实体。', 'No editable Subject Index entities under current filters.')}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-t border-white/10 bg-white/5 flex items-center justify-between gap-3">
                            <div className="text-xs text-white/45">
                                {(() => {
                                    const total = phase2RerunDisplayEntries.length;
                                    const mode = String(phase2RerunModal.mode || 'all');
                                    if (mode === 'all') {
                                        return t(`可选实体：${total} 个`, `${total} selectable entities`);
                                    }
                                    const category = String(phase2RerunModal.category || '').trim();
                                    const categoryTotal = category
                                        ? phase2RerunDisplayEntries.filter((item) => item.category === category).length
                                        : total;
                                    const visible = filteredPhase2RerunSubjectEntries.length;
                                    if (visible === categoryTotal) {
                                        return t(`当前分类：${visible} 个`, `${visible} entities in category`);
                                    }
                                    return t(`当前分类：${visible}/${categoryTotal} 个（已筛选）`, `${visible}/${categoryTotal} entities in category (filtered)`);
                                })()}
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={closePhase2RerunModal}
                                    className="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 hover:bg-white/20 text-white border border-white/10"
                                >
                                    {t('取消', 'Cancel')}
                                </button>
                                <button
                                    type="button"
                                    onClick={confirmPhase2RerunSelection}
                                    disabled={isRetryingPhase2 || isAnalyzing || phase2RerunDisplayEntries.length <= 0 || (phase2RerunModal.mode === 'single' && filteredPhase2RerunSubjectEntries.length <= 0)}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isRetryingPhase2 || isAnalyzing || phase2RerunDisplayEntries.length <= 0 || (phase2RerunModal.mode === 'single' && filteredPhase2RerunSubjectEntries.length <= 0) ? 'bg-white/5 text-white/35 cursor-not-allowed' : 'bg-purple-600 hover:bg-purple-500 text-white'}`}
                                >
                                    {isRetryingPhase2 ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                                    {t('确认重跑', 'Confirm Rerun')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

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
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
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
                                className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-colors ${postAnalysisCheckModal.status === 'running' ? 'bg-white/5 text-white/30 cursor-not-allowed' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                                disabled={postAnalysisCheckModal.status === 'running'}
                            >
                                {t('退出', 'Exit')}
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
                <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm">
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-6xl h-[90vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Wand2 className="w-5 h-5 text-purple-500" />
                                {t('高级 AI 剧本分析', 'Advanced AI Analysis')}
                            </h3>
                            <button onClick={() => {
                                if (phase2ResolverRef.current) {
                                    phase2ResolverRef.current(false);
                                    phase2ResolverRef.current = null;
                                }
                                setShowAnalysisModal(false);
                            }} className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-bold transition-colors text-white">
                                {t('退出', 'Exit')}
                            </button>
                        </div>
                        
                        <div className="flex-1 p-3 sm:p-6 grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 overflow-hidden">
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    System Prompt
                                    <span className="text-xs font-normal opacity-70">{t('定义当前阶段的 AI 角色与规则', 'Define the AI role and rules for this stage')}</span>
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
                                    {analysisModalMode === 'stage3'
                                        ? t('User Input (Stage 2 Asset Index)', 'User Input (Stage 2 Asset Index)')
                                        : analysisModalMode === 'stage2'
                                            ? t('User Input (Optimized Script)', 'User Input (Optimized Script)')
                                            : t('User Input (Script)', 'User Input (Script)')}
                                    <span className="text-xs font-normal opacity-70">{t('当前阶段需要处理的权威输入', 'The authoritative input for the current stage')}</span>
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
                            {canStopAnalysisTask && (
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
                                    if (phase2ResolverRef.current) {
                                        phase2ResolverRef.current(false);
                                        phase2ResolverRef.current = null;
                                    }
                                    setShowAnalysisModal(false);
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors text-white border border-white/10"
                             >
                                <X className="w-4 h-4" /> {t('退出', 'Exit')}
                             </button>
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
                                                  executeAdvancedAnalysis(userPrompt, systemPrompt, 0, true);
                                              }
                                              setShowAnalysisModal(false);
                                          }}
                                disabled={isAnalyzing && !phase2ResolverRef.current}
                                className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                             >
                                {(isAnalyzing && !phase2ResolverRef.current) ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                                          {t('开始执行第一阶段', 'Run Stage 1')}
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

 

