
import FunctionApiSelector from '../../../components/FunctionApiSelector';
import { useFunctionApis } from '../../../components/useFunctionApis';
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
import { PROJECT_ASPECT_RATIO_OPTIONS } from '../projectOptionConfig';

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
    PROJECT_EP_COUNTRY_REGION_OPTIONS,
    PROJECT_EP_LANGUAGE_OPTIONS,
    PROJECT_EP_BASE_POSITIONING_OPTIONS,
    PROJECT_EP_GLOBAL_STYLE_OPTIONS,
    PROJECT_EP_TONE_OPTIONS,
    PROJECT_EP_LIGHTING_OPTIONS,
    PROJECT_EP_QUALITY_OPTIONS,
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
export const EpisodeInfo = ({ episode, onUpdate, project, projectId, uiLang = 'en', mergedSimplified = false }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [info, setInfo] = useState({
        e_global_info: {
            script_title: "",
            series_episode: "",
            base_positioning: "现代职场 / Modern Workplace",
            type: "实拍（写实/电影感8K） / Live Action (Realism/Cinematic 8K)",
            Global_Style: "写实电影感，8k杰作 / Photorealistic, Cinematic Lighting, 8k, Masterpiece",
            tech_params: {
                visual_standard: {
                    horizontal_resolution: "3840",
                    vertical_resolution: "2160",
                    frame_rate: "24",
                    aspect_ratio: "9:16",
                    quality: "超高 / Ultra High",
                    image_size: "4K"
                }
            },
            tone: "肤色优化，梦幻感 / Skin Tone Optimized, Dreamy",
            lighting: "",
            language: "英文 / English",
            borrowed_films: ["King Kong (2005)", "Joker (2019)", "The Truman Show"],
            notes: ""
        }
    });

    useEffect(() => {
        if (episode) {
             const loaded = episode.episode_info || {};
             
             // Ensure structure exists even if loaded data is partial
             const merged = {
                 e_global_info: {
                     ...info.e_global_info, // default structure
                     ...(loaded.e_global_info || {}), // loaded data
                 },
             };

             // Deep merge tech_params if they exist
             if (loaded.e_global_info?.tech_params?.visual_standard) {
                 merged.e_global_info.tech_params = {
                     ...merged.e_global_info.tech_params,
                     visual_standard: {
                         ...merged.e_global_info.tech_params.visual_standard,
                         ...loaded.e_global_info.tech_params.visual_standard
                     }
                 };
             }
             merged.e_global_info.type = normalizeProjectEpisodeType(merged.e_global_info.type);
             merged.e_global_info.language = normalizeProjectEpisodeLanguage(merged.e_global_info.language);
             merged.e_global_info.base_positioning = normalizeProjectEpisodeBasePositioning(merged.e_global_info.base_positioning);
             merged.e_global_info.era = normalizeProjectSceneAnalysisEra(merged.e_global_info.era);
             merged.e_global_info.broadcast_safety_level = normalizeProjectSceneAnalysisSafety(merged.e_global_info.broadcast_safety_level);
             merged.e_global_info.Global_Style = normalizeProjectEpisodeGlobalStyle(merged.e_global_info.Global_Style);
             merged.e_global_info.tone = normalizeProjectEpisodeTone(merged.e_global_info.tone);
             merged.e_global_info.lighting = normalizeProjectEpisodeLighting(merged.e_global_info.lighting);
             if (merged.e_global_info.tech_params?.visual_standard) {
                 merged.e_global_info.tech_params.visual_standard.quality = normalizeProjectEpisodeQuality(merged.e_global_info.tech_params.visual_standard.quality);
             }
             
             setInfo(merged);
        }
    }, [episode]);

    const handleSave = async () => {
        try {
            await onUpdate(episode.id, { episode_info: info });
            alert("Episode global info saved!");
        } catch (e) {
            console.error("Failed to save", e);
            alert(`Failed to save: ${e?.message || 'Unknown error'}`);
        }
    };

    const handleSyncFromProjectOverview = async () => {
        const isNonEmptyValue = (value) => {
            if (value === null || value === undefined) return false;
            if (typeof value === 'string') return value.trim() !== '';
            if (Array.isArray(value)) return value.length > 0;
            if (typeof value === 'object') return Object.keys(value).length > 0;
            return true;
        };

        const keepNonEmptyFields = (obj = {}) => {
            return Object.fromEntries(
                Object.entries(obj).filter(([_, value]) => isNonEmptyValue(value))
            );
        };

        let source = project?.global_info;
        if (projectId) {
            try {
                const latestProject = await fetchProject(projectId);
                if (latestProject?.global_info && typeof latestProject.global_info === 'object') {
                    source = latestProject.global_info;
                }
            } catch (e) {
                console.warn('Failed to fetch latest project before sync, using local project cache.', e);
            }
        }

        if (!source || typeof source !== 'object') {
            alert("No Project Overview data found to sync.");
            return;
        }

        const sourceTechParams = source.tech_params && typeof source.tech_params === 'object'
            ? source.tech_params
            : {};
        const sourceVisualStandard = sourceTechParams.visual_standard && typeof sourceTechParams.visual_standard === 'object'
            ? sourceTechParams.visual_standard
            : {};

        const sourceGlobalInfo = keepNonEmptyFields(source);
        const sourceTechParamsNonEmpty = keepNonEmptyFields(sourceTechParams);
        const sourceVisualStandardNonEmpty = keepNonEmptyFields(sourceVisualStandard);

        const mappedVisualStandard = keepNonEmptyFields({
            horizontal_resolution: sourceVisualStandardNonEmpty.horizontal_resolution ?? source.horizontal_resolution,
            vertical_resolution: sourceVisualStandardNonEmpty.vertical_resolution ?? source.vertical_resolution,
            frame_rate: sourceVisualStandardNonEmpty.frame_rate ?? source.frame_rate,
            aspect_ratio: sourceVisualStandardNonEmpty.aspect_ratio ?? source.aspect_ratio,
            quality: sourceVisualStandardNonEmpty.quality ?? source.quality,
        });

        const mappedTone = isNonEmptyValue(source.tone)
            ? source.tone
            : (isNonEmptyValue(source.mood) ? source.mood : undefined);
        const mappedLighting = isNonEmptyValue(source.lighting)
            ? source.lighting
            : (isNonEmptyValue(source.light) ? source.light : undefined);

        const nextGlobalInfo = {
            ...info.e_global_info,
            ...sourceGlobalInfo,
            type: normalizeProjectEpisodeType(sourceGlobalInfo.type ?? info.e_global_info.type),
            language: normalizeProjectEpisodeLanguage(sourceGlobalInfo.language ?? info.e_global_info.language),
            base_positioning: normalizeProjectEpisodeBasePositioning(sourceGlobalInfo.base_positioning ?? info.e_global_info.base_positioning),
            Global_Style: normalizeProjectEpisodeGlobalStyle(sourceGlobalInfo.Global_Style ?? info.e_global_info.Global_Style),
            ...(mappedTone !== undefined ? { tone: normalizeProjectEpisodeTone(mappedTone) } : {}),
            ...(mappedLighting !== undefined ? { lighting: normalizeProjectEpisodeLighting(mappedLighting) } : {}),
            tech_params: {
                ...info.e_global_info.tech_params,
                ...sourceTechParamsNonEmpty,
                visual_standard: {
                    ...info.e_global_info.tech_params?.visual_standard,
                    ...sourceVisualStandardNonEmpty,
                    ...mappedVisualStandard,
                    quality: normalizeProjectEpisodeQuality(
                        sourceVisualStandardNonEmpty.quality
                        ?? mappedVisualStandard.quality
                        ?? info.e_global_info.tech_params?.visual_standard?.quality
                    ),
                },
            },
        };

        const nextInfo = {
            ...info,
            e_global_info: nextGlobalInfo,
        };

        setInfo(nextInfo);

        try {
            await onUpdate(episode.id, { episode_info: nextInfo });
            alert("Synced from Project Overview.");
        } catch (e) {
            console.error("Failed to sync from project overview", e);
            alert("Sync failed. Please try again.");
        }
    };

    const updateField = (key, value) => {
        setInfo(prev => ({
            ...prev,
            e_global_info: {
                ...prev.e_global_info,
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
                            : value
            }
        }));
    };

    const updateTech = (key, value) => {
        setInfo(prev => ({
            ...prev,
            e_global_info: {
                ...prev.e_global_info,
                tech_params: {
                    ...prev.e_global_info.tech_params,
                    visual_standard: {
                        ...prev.e_global_info.tech_params.visual_standard,
                        [key]: key === 'quality' ? normalizeProjectEpisodeQuality(value) : value
                    }
                }
            }
        }));
    };
    
    const handleBorrowedFilmsChange = (str) => {
        const arr = str.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        updateField('borrowed_films', arr);
    };

    if (!episode) return <div className="p-8 text-muted-foreground">{t('请选择分集以查看信息。', 'Select an episode to view info.')}</div>;

    const data = info.e_global_info;
    const prefix = "ep-";

    if (mergedSimplified) {
        return (
            <div className="px-4 sm:px-6 lg:px-8 pb-8">
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-5">
                    <div className="flex items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold text-primary">{t('分集信息（简化）', 'Episode Info (Simplified)')}</h3>
                        <button
                            onClick={handleSave}
                            className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2"
                        >
                            <SettingsIcon className="w-4 h-4" /> {t('保存分集信息', 'Save Episode Info')}
                        </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <InputGroup
                            idPrefix={prefix}
                            label={t('系列/分集', 'Series/Episode')}
                            value={data.series_episode}
                            onChange={v => updateField('series_episode', v)}
                            placeholder={t('例如：S01E01', 'e.g. S01E01')}
                        />
                        <InputGroup
                            idPrefix={prefix}
                            label={t('分集剧本标题', 'Episode Script Title')}
                            value={data.script_title}
                            onChange={v => updateField('script_title', v)}
                            placeholder={t('分集剧本标题', 'Episode Script Title')}
                        />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('分集补充备注', 'Episode Notes')}</label>
                        <textarea
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={data.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder={t('仅填写分集级别补充内容，其它通用信息请在上方项目总览维护。', 'Only fill episode-level notes here; maintain shared fields above in project overview.')}
                        />
                    </div>
                </div>
            </div>
        );
    }

    return (
           <div className="p-3 sm:p-6 lg:p-8 w-full h-full overflow-y-auto">
               <div className="flex flex-wrap justify-between items-center gap-3 mb-6 sm:mb-8">
                <h2 className="text-2xl font-bold">{t('分集全局信息', 'Episode Global Info')}</h2>
                <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                    <button
                        onClick={handleSyncFromProjectOverview}
                        className="flex-1 sm:flex-none px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={!projectId && !project?.global_info}
                    >
                        <RefreshCw className="w-4 h-4" /> {t('从项目总览同步', 'Sync from Project Overview')}
                    </button>
                    <button onClick={handleSave} className="flex-1 sm:flex-none px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center justify-center gap-2">
                        <SettingsIcon className="w-4 h-4" /> {t('保存修改', 'Save Changes')}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 sm:gap-8 w-full">
                 {/* Basic Info */}
                <div className="bg-card border border-white/10 p-4 sm:p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">{t('基本信息', 'Basic Information')}</h3>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix} label={t('剧本标题', 'Script Title')} value={data.script_title} onChange={v => updateField('script_title', v)} placeholder={t('分集剧本标题', 'Episode Script Title')} />
                        <InputGroup idPrefix={prefix} label={t('系列/分集', 'Series/Episode')} value={data.series_episode} onChange={v => updateField('series_episode', v)} placeholder={t('例如：S01E01', 'e.g. S01E01')} />
                    </div>

                    <InputGroup idPrefix={prefix}
                        label={t('剧本模式 (基础定位)', 'Script Mode (Base Positioning)')} 
                        value={data.base_positioning} 
                        onChange={v => updateField('base_positioning', v)} 
                        list={PROJECT_EP_BASE_POSITIONING_OPTIONS}
                        placeholder={t('例如：悬疑 / 惊悚', 'e.g. Mystery / Thriller')}
                    />
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label={t('类型', 'Type')}
                            value={data.type}
                            onChange={v => updateField('type', v)}
                            list={PROJECT_EP_TYPE_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('国家地域', 'Country/Region')}
                            value={data.country_region}
                            onChange={v => updateField('country_region', v)}
                            list={PROJECT_EP_COUNTRY_REGION_OPTIONS}
                        />
                        <InputGroup idPrefix={prefix}
                            label={t('语言', 'Language')}
                            value={data.language}
                            onChange={v => updateField('language', v)}
                            list={PROJECT_EP_LANGUAGE_OPTIONS}
                        />
                         <InputGroup idPrefix={prefix} label={t('创作力', 'Creativity')} value={data.creativity} onChange={v => updateField('creativity', v)} list={PROJECT_EP_CREATIVITY_OPTIONS} />
                    </div>
<InputGroup idPrefix={prefix}
                        label={t('全局风格', 'Global Style')} 
                        value={data.Global_Style} 
                        onChange={v => updateField('Global_Style', v)} 
                        multi={true}
                        list={PROJECT_EP_GLOBAL_STYLE_OPTIONS}
                        placeholder={t('例如：赛博朋克', 'e.g. Cyberpunk')}
                    />

                     <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('借鉴影片', 'Borrowed Films')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={(data.borrowed_films || []).join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder={t('例如：消失的爱人, 小丑', 'e.g. Gone Girl, Joker')}
                        />
                    </div>
                </div>

                {/* Tech Params */}
                 <div className="bg-card border border-white/10 p-4 sm:p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">{t('技术与氛围', 'Technical & Mood')}</h3>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                         <InputGroup idPrefix={prefix} label={t('横向分辨率', 'H. Resolution')} value={data.tech_params?.visual_standard?.horizontal_resolution} onChange={v => updateTech('horizontal_resolution', v)} placeholder="3840" list={["3840", "1920", "1280", "1080"]}/>
                         <InputGroup idPrefix={prefix} label={t('纵向分辨率', 'V. Resolution')} value={data.tech_params?.visual_standard?.vertical_resolution} onChange={v => updateTech('vertical_resolution', v)} placeholder="2160" list={["2160", "1920", "1080", "720"]}/>
                    </div>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                         <InputGroup idPrefix={prefix} label={t('帧率', 'Frame Rate')} value={data.tech_params?.visual_standard?.frame_rate} onChange={v => updateTech('frame_rate', v)} list={["24", "30", "60"]} />
                         <InputGroup idPrefix={prefix} label={t('画幅比例', 'Aspect Ratio')} value={data.tech_params?.visual_standard?.aspect_ratio} onChange={v => updateTech('aspect_ratio', v)} list={PROJECT_ASPECT_RATIO_OPTIONS} />
                         <InputGroup idPrefix={prefix} label={t('质量等级', 'Quality')} value={data.tech_params?.visual_standard?.quality} onChange={v => updateTech('quality', v)} list={PROJECT_EP_QUALITY_OPTIONS} />
                        <InputGroup idPrefix={prefix} label={t('图像尺寸', 'Image Size')} value={data.tech_params?.visual_standard?.image_size} onChange={v => updateTech('image_size', v)} list={["0.5K", "1K", "2K", "4K"]} />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                         <InputGroup idPrefix={prefix}
                            label={t('色调', 'Tone')} 
                            value={data.tone} 
                            onChange={v => updateField('tone', v)} 
                            multi={true}
                                     list={PROJECT_EP_TONE_OPTIONS}
                         />
                         <InputGroup idPrefix={prefix}
                            label={t('光照', 'Lighting')} 
                            value={data.lighting} 
                            onChange={v => updateField('lighting', v)} 
                            multi={true}
                                     list={PROJECT_EP_LIGHTING_OPTIONS}
                         />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">{t('备注', 'Notes')}</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={data.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder={t('补充风格说明...', 'Additional Style Notes...')}
                        />
                    </div>
                 </div>

            </div>
        </div>
    );
};


