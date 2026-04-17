
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
export const ImportModal = ({ isOpen, onClose, onImport, defaultType = 'auto', project, activeEpisodeId = null, uiLang = 'zh' }) => {
    const functionApiConfigs = useFunctionApis();
    const [text, setText] = useState('');
    const [importType, setImportType] = useState(defaultType); // auto, json, script, scene, shot
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isImporting, setIsImporting] = useState(false);
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    
    // Reset type when modal opens
    useEffect(() => {
        if (isOpen) setImportType(defaultType);
    }, [isOpen, defaultType]);

    if (!isOpen) return null;
    
    const handleImportClick = async () => {
        if (!text.trim() || isImporting) return;
        setIsImporting(true);
        let watchdog = null;
        try {
            watchdog = window.setTimeout(() => {
                alert(t('导入处理中，请稍候（大文本可能需要更久）。', 'Import is in progress, please wait (large text may take longer).'));
            }, 2500);
            await onImport(text, importType, { autoSupplementSceneSubjects: false });
        } catch (e) {
            alert(t('导入失败：', 'Import failed: ') + (e?.message || e));
        } finally {
            if (watchdog) window.clearTimeout(watchdog);
            setIsImporting(false);
        }
    };

    const handleAIAnalysis = async () => {
        if (!text.trim()) return;
        setIsAnalyzing(true);
        try {
            const token = localStorage.getItem('token');
            const body = {
                  text: text,
                  project_id: project?.id,
                  prompt_file: "skills/scene_analysis_feature_stack/scene_planning.md",
                  include_negative_prompt: true,
                  function_name: "script_analysis",
                  system_api_id: Number(localStorage.getItem('func_api_script_analysis')) || null,
              };
            if (project?.global_info) {
                body.project_metadata = project.global_info;
            }
            if (activeEpisodeId) {
                body.episode_id = activeEpisodeId;
            }

            const res = await fetch(`${API_BASE_URL}/analyze_scene`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(body)
            });
            
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || t('分析失败', 'Analysis Failed'));
            }
            
            const data = await res.json();
            setText(data.result); // Replace content with analysis result
            alert(t('AI 分析完成！请查看下方生成的 markdown。', 'AI Analysis Complete! Review the generated markdown below.'));
        } catch (e) {
            alert(`${t('分析错误', 'Analysis Error')}: ${e.message}`);
            console.error(e);
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-[#09090b] border border-white/20 rounded-xl p-4 sm:p-6 w-full max-w-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
                <div className="flex justify-between items-center mb-4 shrink-0">
                     <h3 className="font-bold text-white flex items-center gap-2"><Upload className="w-5 h-5 text-primary"/> {t('导入与 AI 分析', 'Import & AI Analysis')}</h3>
                     <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground hover:text-white"/></button>
                </div>
                
                {/* Type Selection */}
                <div className="flex flex-wrap gap-3 sm:gap-4 mb-4 text-xs font-semibold text-gray-400 shrink-0">
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="auto" checked={importType === 'auto'} onChange={e => setImportType(e.target.value)} />
                        {t('自动识别（兼容）', 'Auto-Detect (Legacy)')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="json" checked={importType === 'json'} onChange={e => setImportType(e.target.value)} />
                        {t('JSON（项目/设置）', 'JSON (Project/Settings)')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="script" checked={importType === 'script'} onChange={e => setImportType(e.target.value)} />
                        {t('剧本表格', 'Script Table')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer text-white">
                        <input type="radio" name="itype" value="scene" checked={importType === 'scene'} onChange={e => setImportType(e.target.value)} />
                        {t('仅场景', 'Scenes Only')}
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer text-white">
                        <input type="radio" name="itype" value="shot" checked={importType === 'shot'} onChange={e => setImportType(e.target.value)} />
                        {t('仅镜头', 'Shots Only')}
                    </label>
                </div>

                <div className="text-xs text-gray-400 mb-2 shrink-0">
                   {t('可粘贴原始剧本文本进行 AI 分析，或粘贴格式化 JSON/表格进行导入。', 'Paste raw script text for AI Analysis, or paste formatted JSON/Table for Import.')}
                </div>
                <textarea 
                    className="flex-1 bg-black/40 border border-white/10 rounded-lg p-4 text-xs text-white font-mono focus:border-primary/60 outline-none resize-none mb-4 custom-scrollbar"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={t('在此粘贴剧本或数据...', 'Paste script or data here...')}
                />
                <div className="flex justify-between gap-2 shrink-0 items-center">
                      <div className="flex items-center gap-2">
                          <FunctionApiSelector functionName="script_analysis" configs={functionApiConfigs} />
                          <button
                              onClick={handleAIAnalysis}
                        disabled={!text.trim() || isAnalyzing}
                        className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 border border-purple-500/30 text-purple-200 hover:bg-purple-500/20 transition-all ${isAnalyzing ? 'opacity-50' : ''}`}
                    >
                        <Sparkles className={`w-3 h-3 ${isAnalyzing ? 'animate-spin' : ''}`} />
                        {isAnalyzing ? t('正在分析场景...', 'Analyzing Scene...') : t('剧本分析', 'Script Analysis')}
                          </button>
                      </div>

                      <div className="flex gap-2 items-center">
                        <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:bg-white/5">{t('取消', 'Cancel')}</button>
                        <button 
                            onClick={handleImportClick} 
                            disabled={!text.trim() || isImporting}
                            className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 disabled:opacity-50"
                        >
                            {isImporting ? t('导入中...', 'Importing...') : t('导入数据', 'Import Data')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )

};

